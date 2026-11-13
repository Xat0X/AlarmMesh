param(
    [ValidateSet('Start', 'Status', 'Stop')][string]$Action = 'Status',
    [ValidateSet('2026.10.4', '2026.11.1')][string]$HaVersion = '2026.11.1',
    [ValidateRange(1024, 65535)][int]$Port = 8128,
    [ValidateSet('Panel', 'Linking')][string]$Mode = 'Panel'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$purpose = if ($Mode -eq 'Linking') { 'linking-ui' } else { 'panel-ui' }
$root = Join-Path $repo "config/$purpose"
$current = Join-Path $root 'current-run.json'
function Docker-Checked {
    param([string[]]$Arguments)
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker failed (exit $LASTEXITCODE)" }
}
function Assert-Owner($run) {
    $details = & docker inspect $run.name | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or $details.Count -ne 1 -or
        $details.Config.Labels.'org.alarmmesh.purpose' -ne $purpose -or
        $details.Config.Labels.'org.alarmmesh.run' -ne $run.id -or
        $details.Config.Image -ne $run.image -or $details.HostConfig.Privileged -or
        $details.HostConfig.Devices.Count -gt 0 -or $details.Mounts.Count -ne $(if ($Mode -eq 'Linking') { 3 } else { 2 })) {
        throw 'Panel simulation ownership/isolation mismatch'
    }
    $binding = $details.HostConfig.PortBindings.'8123/tcp'
    $product = @($details.Mounts | Where-Object Destination -eq '/config/custom_components/alarmmesh')
    $config = @($details.Mounts | Where-Object Destination -eq '/config')
    if ($binding.Count -ne 1 -or $binding.HostIp -ne '127.0.0.1' -or
        $binding.HostPort -ne [string]$run.port -or $product.Count -ne 1 -or
        $product[0].RW -or $product[0].Source -ne (Join-Path $repo 'custom_components/alarmmesh') -or
        $config.Count -ne 1 -or $config[0].Source -ne $run.config) {
        throw 'Panel simulation mounts/port mismatch'
    }
    if ($Mode -eq 'Linking') {
        $fixture = @($details.Mounts | Where-Object Destination -eq '/config/custom_components/alarmmesh_simulation')
        if ($fixture.Count -ne 1 -or $fixture[0].RW -or $fixture[0].Source -ne (Join-Path $repo 'dev/linking-simulation/alarmmesh_simulation')) {
            throw 'Linking simulation fixture mount mismatch'
        }
    }
}
if (-not (Test-Path -LiteralPath $current)) {
    if ($Action -ne 'Start') { throw 'No panel simulation has been prepared.' }
    & git -C $repo check-ignore -q -- "config/$purpose/private"
    if ($LASTEXITCODE -ne 0) { throw 'Panel configuration must be Git-ignored' }
    $probe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    try { $probe.Start() } finally { $probe.Stop() }
    $id = [guid]::NewGuid().ToString('N')
    $name = "alarmmesh-$purpose-$($id.Substring(0,12))"
    $directory = Join-Path $root $id
    $configuration = Join-Path $directory 'config'
    New-Item -ItemType Directory -Path $configuration | Out-Null
    $template = if ($Mode -eq 'Linking') { 'linking-simulation' } else { 'mvp-acceptance' }
    $yaml = Get-Content -Raw -Encoding UTF8 (Join-Path $PSScriptRoot "$template/configuration.yaml")
    $yaml = $yaml.Replace('AlarmMesh MVP - SIMULATED', 'AlarmMesh PANEL - SIMULATION ONLY')
    [System.IO.File]::WriteAllText((Join-Path $configuration 'configuration.yaml'), $yaml)
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "$template/ui-lovelace.yaml") -Destination $configuration
    $image = "ghcr.io/home-assistant/home-assistant:$HaVersion"
    $network = "$name-net"
    Docker-Checked @('network','create','--label',"org.alarmmesh.purpose=$purpose",'--label',"org.alarmmesh.run=$id",$network) | Out-Null
    $mounts = @('--mount',"type=bind,source=$configuration,target=/config",'--mount',"type=bind,source=$(Join-Path $repo 'custom_components/alarmmesh'),target=/config/custom_components/alarmmesh,readonly")
    if ($Mode -eq 'Linking') { $mounts += @('--mount',"type=bind,source=$(Join-Path $repo 'dev/linking-simulation/alarmmesh_simulation'),target=/config/custom_components/alarmmesh_simulation,readonly") }
    & docker run --rm --name "$name-check" --network $network @mounts --entrypoint python $image -m homeassistant --script check_config -c /config > (Join-Path $directory 'configuration-check.log') 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Configuration failed; review $directory/configuration-check.log" }
    Docker-Checked (@('create','--name',$name,'--label',"org.alarmmesh.purpose=$purpose",'--label',"org.alarmmesh.run=$id",'--network',$network,'--publish',"127.0.0.1:${Port}:8123") + $mounts + @($image)) | Out-Null
    $run = [ordered]@{id=$id;name=$name;network=$network;image=$image;ha_version=$HaVersion;port=$Port;url="http://127.0.0.1:$Port/alarmmesh";config=$configuration;evidence=$directory;configuration_check='PASS';network_boundary='Own bridge permits outbound traffic; not a LAN firewall. No production data/devices.'}
    $run | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -LiteralPath $current
}
$run = Get-Content -Raw -Encoding UTF8 -LiteralPath $current | ConvertFrom-Json
Assert-Owner $run
if ($Action -eq 'Start') {
    Docker-Checked @('start',$run.name) | Out-Null
    Docker-Checked @('exec',$run.name,'python','-c',"from homeassistant.const import __version__; assert __version__ == '$($run.ha_version)'; print(__version__)")
}
if ($Action -eq 'Stop') { Docker-Checked @('stop','--timeout','30',$run.name) | Out-Null }
Docker-Checked @('inspect',$run.name,'--format','{{.State.Status}}')
Write-Output $run.url
Write-Output "Account/configuration kept at $($run.config). No installer/backup environments modified."
