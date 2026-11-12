param(
    [ValidateSet('2026.10.4', '2026.11.1')]
    [string]$HaVersion = '2026.10.4'
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$runId = [guid]::NewGuid().ToString('N')
$name = "alarmmesh-update-$HaVersion-$($runId.Substring(0,12))"
$network = "$name-net"
$root = Join-Path $repoRoot "config/update-checks/$HaVersion/$runId"
& git -C $repoRoot check-ignore -q -- 'config/update-checks/local-data'
if ($LASTEXITCODE -ne 0) { throw 'Update evidence must be ignored by Git.' }
New-Item -ItemType Directory -Path $root | Out-Null
$packageRoot = Join-Path $repoRoot "config/release-packages/$runId"
$utf8 = [System.Text.UTF8Encoding]::new($false)
$report = [ordered]@{
    base_commit = (& git -C $repoRoot rev-parse HEAD)
    previous_revision = (& git -C $repoRoot rev-parse '0e7ba38^{commit}')
    ha_version = $HaVersion
    result = 'FAIL'
    scope = 'file replacement and stopped-file snapshot recovery; not Marketplace/HACS or HA backup acceptance'
    stages = [ordered]@{}
}
$stage = 'packages'
$networkCreated = $false
$cleanupFailed = $false

function Assert-OwnPath {
    param([string]$Path)
    $full = [System.IO.Path]::GetFullPath($Path)
    if (-not $full.StartsWith($root + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Test path is outside this new run.'
    }
}

function Invoke-Phase {
    param([string]$Phase, [string]$ConfigPath, [string]$InstallPath)
    $args = @('run', '--rm', '--name', "$name-$Phase", '--network', $network,
        '--label', 'org.alarmmesh.purpose=update-check', '--label', "org.alarmmesh.run=$runId",
        '-e', 'PYTHONDONTWRITEBYTECODE=1',
        '--mount', "type=bind,source=$ConfigPath,target=/config",
        '--mount', "type=bind,source=$InstallPath,target=/config/custom_components/alarmmesh,readonly",
        '--mount', "type=bind,source=$PSScriptRoot,target=/check,readonly",
        '--mount', "type=bind,source=$root,target=/evidence",
        '--entrypoint', 'python', "ghcr.io/home-assistant/home-assistant:$HaVersion",
        '/check/check_update.py', '--phase', $Phase, '--ha-version', $HaVersion)
    & docker @args > (Join-Path $root "$Phase.log") 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Update phase $Phase failed (exit $LASTEXITCODE)." }
    $result = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $root "$Phase-result.json") | ConvertFrom-Json
    if ($result.result -ne 'PASS' -or $result.actual_ha_version -ne $HaVersion) { throw 'Update phase report mismatch.' }
    $report.stages[$Phase] = 'PASS'
}

try {
    & python (Join-Path $PSScriptRoot 'package.py') --output (Join-Path $packageRoot 'current') > (Join-Path $root 'package-current.log') 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'Current package failed.' }
    & python (Join-Path $PSScriptRoot 'package.py') --revision 0e7ba38 --output (Join-Path $packageRoot 'previous') > (Join-Path $root 'package-previous.log') 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'Previous package failed.' }
    $current = Join-Path $packageRoot 'current/alarmmesh.zip'
    $previous = Join-Path $packageRoot 'previous/alarmmesh.zip'
    $report.package_sha256 = (Get-FileHash -LiteralPath $current -Algorithm SHA256).Hash.ToLowerInvariant()
    $report.previous_package_sha256 = (Get-FileHash -LiteralPath $previous -Algorithm SHA256).Hash.ToLowerInvariant()
    $report.identical_integration_payload = $report.package_sha256 -eq $report.previous_package_sha256
    $report.stages['packages'] = 'PASS'
    $config = Join-Path $root 'config'
    $installed = Join-Path $root 'installed'
    New-Item -ItemType Directory -Path $config,$installed | Out-Null
    Copy-Item -LiteralPath (Join-Path $repoRoot 'dev/mvp-acceptance/configuration.yaml'),(Join-Path $repoRoot 'dev/mvp-acceptance/ui-lovelace.yaml') -Destination $config
    Expand-Archive -LiteralPath $previous -DestinationPath $installed
    & docker network create --internal --label org.alarmmesh.purpose=update-check --label "org.alarmmesh.run=$runId" $network > (Join-Path $root 'network.log') 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'Cannot create own internal update network.' }
    $networkCreated = $true
    $stage = 'seed'
    Invoke-Phase 'seed' $config $installed
    # The seed process has exited normally before any snapshot or file update.
    $backup = Join-Path $root 'stopped-file-backup'
    Assert-OwnPath $backup
    New-Item -ItemType Directory -Path $backup | Out-Null
    Copy-Item -LiteralPath $config -Destination (Join-Path $backup 'config') -Recurse
    Copy-Item -LiteralPath $installed -Destination (Join-Path $backup 'installed') -Recurse
    $report.backup_type = 'copy of normally stopped test files; not the Home Assistant backup feature'
    $stage = 'update'
    $inventory = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $packageRoot 'previous/inventory.json') | ConvertFrom-Json
    $actual = @(Get-ChildItem -LiteralPath $installed -File -Recurse)
    if ($actual.Count -ne $inventory.files.Count) { throw 'Unexpected files in owned installation; not overwritten.' }
    foreach ($file in $inventory.files) {
        $path = Join-Path $installed $file.path
        Assert-OwnPath $path
        if ((Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant() -ne $file.sha256) { throw 'Owned previous install changed; not overwritten.' }
    }
    Expand-Archive -LiteralPath $current -DestinationPath $installed -Force
    Invoke-Phase 'update' $config $installed
    $stage = 'restore'
    $restoreRoot = Join-Path $root 'restored'
    Assert-OwnPath $restoreRoot
    New-Item -ItemType Directory -Path $restoreRoot | Out-Null
    Copy-Item -LiteralPath (Join-Path $backup 'config') -Destination (Join-Path $restoreRoot 'config') -Recurse
    Copy-Item -LiteralPath (Join-Path $backup 'installed') -Destination (Join-Path $restoreRoot 'installed') -Recurse
    Invoke-Phase 'restore' (Join-Path $restoreRoot 'config') (Join-Path $restoreRoot 'installed')
    $report.result = 'PASS'
} catch {
    $report.stages[$stage] = 'FAIL'
    $report.failed_stage = $stage
    [System.IO.File]::WriteAllText((Join-Path $root 'host-failure.log'), ($_ | Out-String) + $_.ScriptStackTrace, $utf8)
} finally {
    try {
        foreach ($phase in @('seed','update','restore')) {
            $container = "$name-$phase"
            $existing = & docker container ls -a --filter ('name=^/' + $container + '$') --format '{{.Names}}'
            if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect own container cleanup.' }
            if ($existing) {
                $label = & docker inspect $container --format '{{index .Config.Labels "org.alarmmesh.run"}}'
                if ($LASTEXITCODE -ne 0 -or $label -ne $runId) { throw 'Cannot verify update container ownership.' }
                & docker rm -f $container > (Join-Path $root "cleanup-$phase.log") 2>&1
                if ($LASTEXITCODE -ne 0) { throw 'Own update container cleanup failed.' }
            }
        }
        if ($networkCreated) {
            $label = & docker network inspect $network --format '{{index .Labels "org.alarmmesh.run"}}'
            if ($LASTEXITCODE -ne 0 -or $label -ne $runId) { throw 'Cannot verify own update network.' }
            & docker network rm $network > (Join-Path $root 'cleanup-network.log') 2>&1
            if ($LASTEXITCODE -ne 0) { throw 'Own update network cleanup failed.' }
        }
    } catch {
        $cleanupFailed = $true
        $report.result = 'FAIL'
        [System.IO.File]::WriteAllText((Join-Path $root 'cleanup-failure.log'), ($_ | Out-String), $utf8)
    }
    $report.cleanup = if ($cleanupFailed) { 'FAIL' } else { 'PASS' }
    [System.IO.File]::WriteAllText((Join-Path $root 'update-result.json'), ($report | ConvertTo-Json -Depth 8), $utf8)
}
Write-Output "$($report.result): $root"
if ($report.result -ne 'PASS') { throw "Update/recovery check failed; see local evidence under $root." }
