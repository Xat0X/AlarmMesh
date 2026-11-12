param()

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runId = [guid]::NewGuid().ToString('N')
$runName = "alarmmesh-validate-$($runId.Substring(0, 12))"
$resultRoot = Join-Path $repoRoot "config/validation/$runId"
& git -C $repoRoot check-ignore -q -- 'config/validation/local-data'
if ($LASTEXITCODE -ne 0) { throw 'Validation results must be ignored by Git.' }
New-Item -ItemType Directory -Path $resultRoot | Out-Null
# Export only Git-visible working files, including review changes. Ignored web
# accounts/configuration and .git are never mounted into validation containers.
$sourceRoot = Join-Path $resultRoot 'source'
New-Item -ItemType Directory -Path $sourceRoot | Out-Null
$files = @(& git -C $repoRoot ls-files --cached --others --exclude-standard)
if ($LASTEXITCODE -ne 0) { throw 'Cannot inventory validation source.' }
foreach ($relative in $files) {
    $source = Join-Path $repoRoot $relative
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { continue }
    $destination = Join-Path $sourceRoot $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination
}
$utf8 = [System.Text.UTF8Encoding]::new($false)
$commit = & git -C $repoRoot rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw 'Cannot identify repository commit.' }
$report = [ordered]@{
    run_id = $runId
    git_commit = $commit
    scope = 'technical checks with simulated sources; no physical-device validation'
    result = 'FAIL'
    checks = [ordered]@{}
}

function Invoke-NativeCheck {
    param([string]$Name, [string[]]$DockerArgs)
    & docker @DockerArgs > (Join-Path $resultRoot "$Name.log") 2>&1
    if ($LASTEXITCODE -ne 0) { throw "$Name failed (exit $LASTEXITCODE)." }
}

function Invoke-Step {
    param([string]$Name, [scriptblock]$Work)
    try {
        & $Work
        $report.checks[$Name] = 'PASS'
    } catch {
        $report.checks[$Name] = 'FAIL'
        [System.IO.File]::WriteAllText((Join-Path $resultRoot "$Name-failure.log"), ($_ | Out-String) + $_.ScriptStackTrace, $utf8)
    }
    Write-Output "$Name`: $($report.checks[$Name])"
}

Invoke-Step 'powershell' {
    foreach ($script in Get-ChildItem -LiteralPath $PSScriptRoot -Recurse -Filter '*.ps1') {
        $parseErrors = $null
        [System.Management.Automation.Language.Parser]::ParseFile($script.FullName, [ref]$null, [ref]$parseErrors) | Out-Null
        if ($parseErrors) { throw ($parseErrors | Out-String) }
    }
    & (Join-Path $PSScriptRoot 'tests/test-compatibility.ps1')
}
Invoke-Step 'compose' {
    Invoke-NativeCheck 'compose' @('compose', '-f', (Join-Path $PSScriptRoot 'mvp-acceptance/compose.yaml'), 'config', '--quiet')
}
Invoke-Step 'baseline' {
    # Dependencies and Python 3.14 stay identical to the existing test workflow.
    $command = 'python -m pip install -r requirements-dev.txt > /results/dependencies.log 2>&1 && python -m ruff check --no-cache . && python -m ruff format --check --no-cache . && python -m pytest -p no:cacheprovider --junitxml=/results/pytest.xml'
    Invoke-NativeCheck 'baseline' @('run', '--rm', '--name', "$runName-baseline",
        '--label', 'org.alarmmesh.purpose=validation', '--label', "org.alarmmesh.run=$runId",
        '--mount', "type=bind,source=$sourceRoot,target=/workspace,readonly",
        '--mount', "type=bind,source=$resultRoot,target=/results",
        '-w', '/workspace', '-e', 'PYTHONDONTWRITEBYTECODE=1', 'python:3.14-bookworm', 'sh', '-c', $command)
}
Invoke-Step 'hassfest' {
    Invoke-NativeCheck 'hassfest' @('run', '--rm', '--name', "$runName-hassfest",
        '--label', 'org.alarmmesh.purpose=validation', '--label', "org.alarmmesh.run=$runId",
        '--mount', "type=bind,source=$sourceRoot,target=/github/workspace,readonly", 'ghcr.io/home-assistant/hassfest:latest')
}
foreach ($version in @('2026.10.4', '2026.11.1')) {
    Invoke-Step "compatibility-$version" {
        & (Join-Path $PSScriptRoot 'mvp-acceptance/mvp-acceptance.ps1') -Action Check -HaVersion $version -ReportPath (Join-Path $resultRoot "compatibility-$version.json")
    }
}

# Inspect exact names AND ownership; never prune or remove another project's work.
Invoke-Step 'cleanup' {
    foreach ($phase in @('baseline', 'hassfest')) {
        $name = "$runName-$phase"
        $leftover = & docker container ls -a --filter ('name=^/' + $name + '$') --format '{{.Names}}'
        if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect validation cleanup.' }
        if ($leftover) {
            $label = & docker inspect $name --format '{{index .Config.Labels "org.alarmmesh.run"}}'
            if ($LASTEXITCODE -ne 0 -or $label -ne $runId) { throw 'Cannot verify validation container ownership.' }
            Invoke-NativeCheck "cleanup-$phase" @('rm', '-f', $name)
        }
    }
}
if (@($report.checks.Values | Where-Object { $_ -ne 'PASS' }).Count -eq 0) { $report.result = 'PASS' }
[System.IO.File]::WriteAllText((Join-Path $resultRoot 'validation-result.json'), ($report | ConvertTo-Json -Depth 8), $utf8)
Write-Output "$($report.result): $resultRoot"
if ($report.result -ne 'PASS') { throw "Validation failed. Review local logs under $resultRoot." }
