# Focused fault injection for the wrapper. No Docker daemon is contacted.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$testRoot = Join-Path $repoRoot ('config/tooling-tests/' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot | Out-Null
$utf8 = [System.Text.UTF8Encoding]::new($false)

function docker {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'compose' -or ($args[0] -eq 'container' -and $args[1] -eq 'ls')) { return }
    if ($args[0] -eq 'network') {
        if ($args[1] -eq 'create') { $global:AlarmMeshToolingNetworkRunId = $args[6].Split('=')[-1] }
        if ($args[1] -eq 'inspect') { Write-Output $global:AlarmMeshToolingNetworkRunId }
        if ($args[1] -eq 'rm' -and $global:AlarmMeshToolingFault -eq 'cleanup') { $global:LASTEXITCODE = 17 }
        return
    }
    if ($args[0] -ne 'run') { throw 'Unexpected fake Docker invocation.' }
    $name = $args[[array]::IndexOf($args, '--name') + 1]
    $configMount = @($args | Where-Object { $_ -like 'type=bind,*target=/config' })[0]
    $configDir = ($configMount -replace '^type=bind,source=', '' -replace ',target=/config$', '')
    if ($name -like '*-version') { Write-Output '2026.10.4'; return }
    if ($name -like '*-configuration') {
        if ($global:AlarmMeshToolingFault -eq 'configuration') { Write-Output 'SIMULATED configuration failure'; $global:LASTEXITCODE = 42 }
        return
    }
    $context = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $configDir 'run-context.json') | ConvertFrom-Json
    $technical = [ordered]@{
        result = 'PASS'; requested_ha_version = '2026.10.4'; actual_ha_version = '2026.10.4'
        run_id = $context.run_id; git_commit = $context.git_commit; scenarios = [ordered]@{}
    }
    if ($global:AlarmMeshToolingFault -eq 'stale') { $technical.run_id = 'previous-run' }
    foreach ($i in 1..12) { $technical.scenarios["scenario-$i"] = 'PASS' }
    [System.IO.File]::WriteAllText((Join-Path $configDir 'technical-result.json'), ($technical | ConvertTo-Json -Depth 5), $utf8)
}

try {
    foreach ($fault in @('configuration', 'stale', 'cleanup')) {
        $global:AlarmMeshToolingFault = $fault
        $path = Join-Path $testRoot "$fault.json"
        $failed = $false
        try {
            & (Join-Path $repoRoot 'dev/mvp-acceptance/mvp-acceptance.ps1') -Action Check -ReportPath $path | Out-Null
        } catch { $failed = $true; $caught = $_ }
        if (-not $failed -or -not (Test-Path -LiteralPath $path)) { throw "Fault $fault did not fail with a report: $caught" }
        $result = Get-Content -Raw -Encoding UTF8 -LiteralPath $path | ConvertFrom-Json
        if ($result.result -ne 'FAIL') { throw "Fault $fault was reported as success." }
        if ($fault -eq 'configuration' -and $result.configuration_check -ne 'FAIL') { throw 'Configuration failure lost.' }
        if ($fault -eq 'stale' -and $result.failed_phase -ne 'runtime') { throw 'Stale runtime report accepted.' }
        if ($fault -eq 'cleanup' -and $result.cleanup -ne 'FAIL') { throw 'Cleanup failure lost.' }
    }
    $rejected = $false
    try {
        & (Join-Path $repoRoot 'dev/mvp-acceptance/mvp-acceptance.ps1') -Action Check -ReportPath (Join-Path $testRoot 'stale.json') | Out-Null
    } catch { $rejected = $true }
    if (-not $rejected) { throw 'Existing output path was accepted.' }
    Write-Output 'PowerShell tooling fault checks PASS (configuration, stale report, cleanup, existing output)'
} finally {
    Remove-Item Function:docker
    Remove-Variable -Name AlarmMeshToolingFault,AlarmMeshToolingNetworkRunId -Scope Global -ErrorAction SilentlyContinue
}
