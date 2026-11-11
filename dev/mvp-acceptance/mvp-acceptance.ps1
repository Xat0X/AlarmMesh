param(
    [ValidateSet('Prepare', 'Check', 'Start', 'Stop', 'Restart', 'Status')]
    [string]$Action = 'Status'
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$runtimePath = Join-Path $repoRoot 'config/mvp-acceptance'
$composePath = Join-Path $PSScriptRoot 'compose.yaml'
$containerName = 'alarmmesh-mvp-acceptance'
$networkName = 'alarmmesh-mvp-acceptance'
$webNetworkName = 'alarmmesh-mvp-acceptance-web'
$imageName = 'ghcr.io/home-assistant/home-assistant:2026.10.4'
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
    foreach ($file in $exampleFiles) {
        if (-not (Test-Path -LiteralPath (Join-Path $runtimePath $file))) {
            throw 'Run Prepare first. No files will be overwritten.'
        }
    }
    Invoke-Docker -DockerArgs @('compose', '-f', $composePath, 'config', '--quiet')
    Ensure-IsolatedNetwork -Name $networkName -Internal $true
    Ensure-IsolatedNetwork -Name $webNetworkName -Internal $false
    $checksRoot = Join-Path $runtimePath 'technical-checks'
    New-Item -ItemType Directory -Path $checksRoot -Force | Out-Null
    $checkPath = Join-Path $checksRoot ([guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $checkPath | Out-Null
    foreach ($file in $exampleFiles) {
        Copy-Item -LiteralPath (Join-Path $runtimePath $file) -Destination $checkPath
    }
    $mounts = @(
        '--mount', "type=bind,source=$checkPath,target=/config",
        '--mount', "type=bind,source=$(Join-Path $repoRoot 'custom_components/alarmmesh'),target=/config/custom_components/alarmmesh,readonly",
        '--mount', "type=bind,source=$PSScriptRoot,target=/acceptance,readonly"
    )
    $common = @('run', '--rm', '--network', $networkName, '-e', 'PYTHONDONTWRITEBYTECODE=1') + $mounts + @('--entrypoint', 'python', $imageName)
    Invoke-Docker -DockerArgs ($common + @('-m', 'homeassistant', '--script', 'check_config', '--config', '/config'))
    Invoke-Docker -DockerArgs ($common + @('/acceptance/check_runtime.py'))
    Write-Output "Technical results retained under: $checkPath"
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
        Check-Config
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
