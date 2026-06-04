<#
setup-headroom.ps1

Pulls the headroom proxy Docker image into lotr-docker-service.
The proxy is started automatically by docker.ps1 run.

Usage:
  PowerShell -ExecutionPolicy Bypass -File build/docker/setup-headroom.ps1
  PowerShell -ExecutionPolicy Bypass -File build/docker/setup-headroom.ps1 -NoPause
  PowerShell -ExecutionPolicy Bypass -File build/docker/setup-headroom.ps1 -DistroName lotr-docker-service
#>

param(
    [string]$DistroName    = 'lotr-docker-service',
    [string]$HeadroomImage = 'ghcr.io/chopratejas/headroom:latest',
    [switch]$NoPause
)

Set-StrictMode -Version Latest

function Write-Log {
    param([string]$msg)
    $timestamp = (Get-Date).ToString('o')
    $logDir = "build\docker\logs"
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
    $logFile = Join-Path $logDir "setup-headroom.log"
    Add-Content -Path $logFile -Value ("$timestamp`t$msg")
    Write-Host $msg
}

Write-Log "Starting setup-headroom.ps1 (image: $HeadroomImage, distro: $DistroName)"

# Verify distro exists
$probe = wsl -d $DistroName -u root -- echo ok 2>$null
if ($probe -notmatch 'ok') {
    Write-Log "Distro '$DistroName' not found. Run setup-wsl-docker.ps1 first."
    if (-not $NoPause) { Write-Host "Press any key to exit..."; $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') }
    exit 2
}

# Verify Docker is responsive
wsl -d $DistroName -u root -- docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Log "Docker not responsive in '$DistroName'. Start Docker first with start-wsl-docker.ps1."
    if (-not $NoPause) { Write-Host "Press any key to exit..."; $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') }
    exit 3
}

# Pull headroom image (idempotent -- docker pull skips if already up to date)
Write-Log "Pulling headroom image $HeadroomImage ..."
wsl -d $DistroName -u root -- docker pull $HeadroomImage
if ($LASTEXITCODE -ne 0) {
    Write-Log ("Failed to pull headroom image (exit {0})." -f $LASTEXITCODE)
    if (-not $NoPause) { Write-Host "Press any key to exit..."; $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') }
    exit 4
}

Write-Log "Headroom image '$HeadroomImage' ready."
Write-Log "setup-headroom.ps1 complete. Proxy starts automatically via docker.ps1 run."

if (-not $NoPause) {
    Write-Host "`nSetup complete. Press any key to exit..." -ForegroundColor Green
    try { $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') }
    catch { Start-Sleep -Seconds 1 }
}

exit 0
