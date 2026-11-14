param(
    [ValidateSet('Prepare', 'Check', 'Start', 'Stop', 'Restart', 'Status')]
    [string]$Action = 'Status',
    [ValidateSet('2026.10.4', '2026.11.1')]
    [string]$HaVersion = '2026.10.4',
    [string]$ReportPath
)

$ErrorActionPreference = 'Stop'
if ($Action -ne 'Check' -and $HaVersion -ne '2026.10.4') {
    throw 'HaVersion applies only to Check. The web environment stays on 2026.10.4.'
}
if ($ReportPath) {
    if ($Action -ne 'Check') { throw 'ReportPath applies only to Check.' }
    if (Test-Path -LiteralPath $ReportPath) { throw 'ReportPath already exists; refusing stale output.' }
    $ReportPath = [System.IO.Path]::GetFullPath($ReportPath)
    if (-not (Test-Path -LiteralPath (Split-Path -Parent $ReportPath))) {
        throw 'ReportPath parent directory does not exist.'
    }
}
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$runtimePath = Join-Path $repoRoot 'config/mvp-acceptance'
$composePath = Join-Path $PSScriptRoot 'compose.yaml'
$containerName = 'alarmmesh-mvp-acceptance'
$webNetworkName = 'alarmmesh-mvp-acceptance-web'
$imageName = "ghcr.io/home-assistant/home-assistant:$HaVersion"
$exampleFiles = @('configuration.yaml', 'ui-lovelace.yaml')

function Invoke-Docker {
    param([string[]]$DockerArgs)
    & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker failed (exit $LASTEXITCODE)." }
}

function Prepare-Config {
    & git -C $repoRoot check-ignore -q -- 'config/mvp-acceptance/local-data'
    if ($LASTEXITCODE -ne 0) { throw 'Runtime directory must be ignored by Git.' }
    foreach ($file in $exampleFiles) {
        $target = Join-Path $runtimePath $file
        if (Test-Path -LiteralPath $target) {
            if ((Get-FileHash -LiteralPath $target).Hash -ne
                (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $file)).Hash) {
                throw "Existing file differs; it will not be overwritten: $target"
            }
        }
    }
    New-Item -ItemType Directory -Path $runtimePath -Force | Out-Null
    foreach ($file in $exampleFiles) {
        $target = Join-Path $runtimePath $file
        if (-not (Test-Path -LiteralPath $target)) {
            Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination $target
        }
    }
}

function Assert-LocalPortFree {
    $probe = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback, 8124
    )
    try { $probe.Start() }
    finally { $probe.Stop() }
}

function Ensure-IsolatedNetwork {
    param([string]$Name, [bool]$Internal)
    $networks = & docker network ls --filter "name=^$Name`$" --format '{{.Name}}'
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect Docker networks.' }
    if ($networks) {
        $network = & docker network inspect $Name | ConvertFrom-Json
        if ($LASTEXITCODE -ne 0 -or $network[0].Internal -ne $Internal -or
            $network[0].Labels.'org.alarmmesh.purpose' -ne 'mvp-acceptance') {
            throw 'Existing network is not this isolated acceptance network.'
        }
    } else {
        $networkArgs = @('network', 'create', '--driver', 'bridge', '--label', 'org.alarmmesh.purpose=mvp-acceptance')
        if ($Internal) { $networkArgs += '--internal' }
        Invoke-Docker -DockerArgs ($networkArgs + @($Name))
    }
}

function Get-OwnedContainer {
    $names = & docker container ls -a --filter "name=^/$containerName`$" --format '{{.Names}}'
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect containers.' }
    if (-not $names) { return $null }
    $details = & docker inspect $containerName | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect acceptance container.' }
    if ($details[0].Config.Labels.'org.alarmmesh.purpose' -ne 'mvp-acceptance' -or
        $details[0].Config.Labels.'com.docker.compose.project' -ne 'alarmmesh-mvp-acceptance') {
        throw 'The existing named container is not owned by this test environment.'
    }
    $binding = $details[0].HostConfig.PortBindings.'8123/tcp'
    $integration = @($details[0].Mounts | Where-Object { $_.Destination -eq '/config/custom_components/alarmmesh' })
    $configMount = @($details[0].Mounts | Where-Object { $_.Destination -eq '/config' })
    if ($details[0].Config.Image -ne $imageName -or $details[0].HostConfig.Privileged -or
        $details[0].HostConfig.NetworkMode -eq 'host' -or $details[0].HostConfig.Devices.Count -gt 0 -or
        $details[0].HostConfig.DeviceRequests.Count -gt 0 -or $details[0].Mounts.Count -ne 2 -or
        @($details[0].HostConfig.PortBindings.PSObject.Properties).Count -ne 1 -or
        $binding.Count -ne 1 -or $binding[0].HostIp -ne '127.0.0.1' -or $binding[0].HostPort -ne '8124' -or
        $integration.Count -ne 1 -or $integration[0].RW -or
        $integration[0].Source -ne (Join-Path $repoRoot 'custom_components/alarmmesh') -or
        $configMount.Count -ne 1 -or $configMount[0].Source -ne $runtimePath) {
        throw 'Existing container configuration differs; it will not be modified.'
    }
    return $details[0]
}

function Check-Config {
    param([switch]$UseWebConfig)
    # Check never reads web accounts/config; Start explicitly validates its YAML.
    $sourcePath = if ($UseWebConfig) { $runtimePath } else { $PSScriptRoot }
    foreach ($file in $exampleFiles) {
        if (-not (Test-Path -LiteralPath (Join-Path $sourcePath $file))) {
            throw "Missing public configuration example: $file"
        }
    }
    & git -C $repoRoot check-ignore -q -- 'config/compatibility/local-data'
    if ($LASTEXITCODE -ne 0) { throw 'Compatibility output must be ignored by Git.' }
    Invoke-Docker -DockerArgs @('compose', '-f', $composePath, 'config', '--quiet')
    $runId = [guid]::NewGuid().ToString('N')
    $runName = "alarmmesh-compat-$HaVersion-$($runId.Substring(0, 12))"
    $runNetwork = "$runName-net"
    $checksRoot = Join-Path $repoRoot "config/compatibility/$HaVersion"
    New-Item -ItemType Directory -Path $checksRoot -Force | Out-Null
    $checkPath = Join-Path $checksRoot $runId
    New-Item -ItemType Directory -Path $checkPath | Out-Null
    foreach ($file in $exampleFiles) {
        Copy-Item -LiteralPath (Join-Path $sourcePath $file) -Destination $checkPath
    }
    $commit = & git -C $repoRoot rev-parse HEAD
    if ($LASTEXITCODE -ne 0) { throw 'Cannot identify tested Git commit.' }
    $changes = @(& git -C $repoRoot status --porcelain --untracked-files=all -- custom_components/alarmmesh dev tests .github)
    if ($LASTEXITCODE -ne 0) { throw 'Cannot identify relevant local changes.' }
    $dirty = @(& git -C $repoRoot status --porcelain --untracked-files=all).Count -gt 0
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect working tree.' }
    $context = [ordered]@{
        run_id = $runId
        requested_ha_version = $HaVersion
        git_commit = $commit
        worktree_dirty = $dirty
        relevant_local_changes = $changes
    }
    $utf8 = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText((Join-Path $checkPath 'run-context.json'), ($context | ConvertTo-Json -Depth 5), $utf8)
    $report = [ordered]@{
        run_id = $runId
        scope = 'technische controle met simulatiebronnen, geen fysieke apparaatvalidatie'
        requested_ha_version = $HaVersion
        actual_ha_version = $null
        git_commit = $commit
        worktree_dirty = $dirty
        relevant_local_changes = $changes
        configuration_check = 'NIET UITGEVOERD'
        result = 'FAIL'
        scenarios = @{}
        cleanup = 'NIET UITGEVOERD'
        mqtt_broker_image = 'eclipse-mosquitto:2.0.22'
    }
    $mounts = @(
        '--mount', "type=bind,source=$checkPath,target=/config",
        '--mount', "type=bind,source=$(Join-Path $repoRoot 'custom_components/alarmmesh'),target=/config/custom_components/alarmmesh,readonly",
        '--mount', "type=bind,source=$(Join-Path $repoRoot 'dev/linking-simulation/alarmmesh_simulation'),target=/config/custom_components/alarmmesh_simulation,readonly",
        '--mount', "type=bind,source=$PSScriptRoot,target=/acceptance,readonly"
    )
    $networkCreated = $false
    $failure = $null
    $cleanupFailures = @()
    $stage = 'network'
    function Invoke-CheckContainer {
        param([string]$Phase, [string[]]$Command)
        $dockerArgs = @('run', '--rm', '--name', "$runName-$Phase", '--network', $runNetwork,
            '--label', 'org.alarmmesh.purpose=compatibility', '--label', "org.alarmmesh.run=$runId",
            '-e', 'PYTHONDONTWRITEBYTECODE=1') + $mounts + @('--entrypoint', 'python', $imageName) + $Command
        & docker @dockerArgs > (Join-Path $checkPath "$Phase.log") 2>&1
        if ($LASTEXITCODE -ne 0) { throw "Compatibility $Phase failed (exit $LASTEXITCODE)." }
    }
    try {
        Invoke-Docker -DockerArgs @('network', 'create', '--internal', '--label', 'org.alarmmesh.purpose=compatibility', '--label', "org.alarmmesh.run=$runId", $runNetwork)
        $networkCreated = $true
        $stage = 'version'
        Invoke-CheckContainer -Phase 'version' -Command @('-c', 'from homeassistant.const import __version__; print(__version__)')
        $actual = (Get-Content -LiteralPath (Join-Path $checkPath 'version.log') -Tail 1).Trim()
        if ($actual -match '^\d+\.\d+\.\d+$') { $report.actual_ha_version = $actual }
        if ($actual -ne $HaVersion) { throw 'Image version differs from requested version.' }
        $stage = 'configuration'
        Invoke-CheckContainer -Phase 'configuration' -Command @('-m', 'homeassistant', '--script', 'check_config', '--config', '/config')
        $report.configuration_check = 'PASS'
        $stage = 'runtime'
        Invoke-CheckContainer -Phase 'runtime' -Command @('/acceptance/check_runtime.py', '--ha-version', $HaVersion)
        $technical = Get-Content -Raw -LiteralPath (Join-Path $checkPath 'technical-result.json') | ConvertFrom-Json
        $report.scenarios = $technical.scenarios
        if ($technical.result -ne 'PASS' -or $technical.actual_ha_version -ne $HaVersion -or
            $technical.requested_ha_version -ne $HaVersion -or $technical.run_id -ne $runId -or
            $technical.git_commit -ne $commit -or @($technical.scenarios.PSObject.Properties).Count -ne 20 -or
            @($technical.scenarios.PSObject.Properties | Where-Object { $_.Value -ne 'PASS' }).Count -gt 0) {
            throw 'Technical report did not confirm this run, version, commit and all scenarios.'
        }
        $stage = 'drivers'
        $brokerPath = Join-Path $checkPath 'mosquitto.conf'
        [System.IO.File]::WriteAllText($brokerPath, "listener 1883`nallow_anonymous true`npersistence false`n", $utf8)
        Invoke-Docker -DockerArgs @('run', '-d', '--name', "$runName-broker", '--network', $runNetwork,
            '--network-alias', 'alarmmesh-sim-broker', '--label', 'org.alarmmesh.purpose=compatibility',
            '--label', "org.alarmmesh.run=$runId", '--mount', "type=bind,source=$brokerPath,target=/mosquitto/config/mosquitto.conf,readonly",
            'eclipse-mosquitto:2.0.22')
        Invoke-CheckContainer -Phase 'drivers' -Command @('/acceptance/check_drivers.py', '--ha-version', $HaVersion)
        $drivers = Get-Content -Raw -LiteralPath (Join-Path $checkPath 'driver-result.json') | ConvertFrom-Json
        $report.driver_checks = $drivers.scenarios
        if ($drivers.result -ne 'PASS' -or $drivers.actual_ha_version -ne $HaVersion -or
            $drivers.requested_ha_version -ne $HaVersion -or $drivers.run_id -ne $runId -or $drivers.git_commit -ne $commit -or
            @($drivers.scenarios.PSObject.Properties).Count -ne 14 -or
            @($drivers.scenarios.PSObject.Properties | Where-Object { $_.Value -ne 'PASS' }).Count -gt 0) {
            throw 'Driver report did not confirm this run, version, commit and all scenarios.'
        }
        $report.result = 'PASS'
    } catch {
        $failure = $_
        $report.failed_phase = $stage
        $report.result = 'FAIL'
        [System.IO.File]::WriteAllText((Join-Path $checkPath 'failure.log'), ($_ | Out-String) + $_.ScriptStackTrace, $utf8)
        if ($stage -eq 'configuration') { $report.configuration_check = 'FAIL' }
        $technicalPath = Join-Path $checkPath 'technical-result.json'
        if (Test-Path -LiteralPath $technicalPath) {
            $report.scenarios = (Get-Content -Raw -LiteralPath $technicalPath | ConvertFrom-Json).scenarios
        }
        $driverPath = Join-Path $checkPath 'driver-result.json'
        if (Test-Path -LiteralPath $driverPath) {
            $report.driver_checks = (Get-Content -Raw -LiteralPath $driverPath | ConvertFrom-Json).scenarios
        }
    } finally {
        # Exact run-owned names only; never touch web containers or shared networks.
        foreach ($phase in @('version', 'configuration', 'runtime', 'drivers', 'broker')) {
            try {
            $ownedName = "$runName-$phase"
            $nameFilter = 'name=^/' + $ownedName + '$'
            $leftover = & docker container ls -a --filter $nameFilter --format '{{.Names}}'
            if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect run containers during cleanup.' }
            if ($leftover) {
                $label = & docker inspect $ownedName --format '{{index .Config.Labels "org.alarmmesh.run"}}'
                if ($LASTEXITCODE -ne 0 -or $label -ne $runId) { throw 'Cannot verify run container ownership.' }
                Invoke-Docker -DockerArgs @('rm', '-f', $ownedName)
            }
            } catch { $cleanupFailures += ($_ | Out-String) }
        }
        if ($networkCreated) {
            try {
                $label = & docker network inspect $runNetwork --format '{{index .Labels "org.alarmmesh.run"}}'
                if ($LASTEXITCODE -ne 0 -or $label -ne $runId) { throw 'Cannot verify run network ownership.' }
                Invoke-Docker -DockerArgs @('network', 'rm', $runNetwork)
            } catch { $cleanupFailures += ($_ | Out-String) }
        }
        $report.cleanup = if ($cleanupFailures.Count) { 'FAIL' } else { 'PASS' }
        if ($cleanupFailures.Count) {
            $report.result = 'FAIL'
            [System.IO.File]::WriteAllText((Join-Path $checkPath 'cleanup-failure.log'), ($cleanupFailures -join [Environment]::NewLine), $utf8)
        }
        [System.IO.File]::WriteAllText((Join-Path $checkPath 'compatibility-result.json'), ($report | ConvertTo-Json -Depth 8), $utf8)
        if ($ReportPath) {
            # An explicit, new summary only; CI never uploads configuration/logs.
            [System.IO.File]::WriteAllText($ReportPath, ($report | ConvertTo-Json -Depth 8), $utf8)
        }
        Write-Output "$($report.result): requested=$HaVersion actual=$($report.actual_ha_version) commit=$commit local_changes=$dirty"
        Write-Output $report.scope
        Write-Output "Results: $checkPath"
    }
    if ($failure -or $cleanupFailures.Count) {
        throw "Compatibility failed; phase=$stage; cleanup=$($report.cleanup). See local logs under $checkPath."
    }
}

switch ($Action) {
    'Prepare' { Prepare-Config }
    'Check' { Check-Config }
    'Start' {
        $existing = Get-OwnedContainer
        if ($existing -and $existing.State.Running) {
            Write-Output 'Acceptance container is already running; nothing changed.'
            break
        }
        Assert-LocalPortFree
        Check-Config -UseWebConfig
        Ensure-IsolatedNetwork -Name $webNetworkName -Internal $false
        if ($existing) {
            Invoke-Docker -DockerArgs @('start', $containerName)
        } else {
            Invoke-Docker -DockerArgs @('compose', '-f', $composePath, 'up', '-d', '--no-recreate')
        }
    }
    'Stop' {
        if (Get-OwnedContainer) {
            Invoke-Docker -DockerArgs @('stop', '--timeout', '30', $containerName)
        }
    }
    'Restart' {
        if (-not (Get-OwnedContainer)) { throw 'Acceptance container does not exist.' }
        Invoke-Docker -DockerArgs @('restart', '--timeout', '30', $containerName)
    }
    'Status' {
        $existing = Get-OwnedContainer
        if ($existing) {
            Write-Output "Container: $containerName; state: $($existing.State.Status)"
            Invoke-Docker -DockerArgs @('port', $containerName)
        } else {
            Write-Output 'Acceptance container has not been created.'
        }
    }
}
