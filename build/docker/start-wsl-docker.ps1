<#
start-wsl-docker.ps1

Starts the Docker daemon inside the `lotr-docker-service` WSL distro.
Behavior:
- Uses `systemd` path when available (`systemctl enable --now docker`).
- Otherwise invokes `/usr/local/bin/lotr-start-docker.sh` wrapper created by the setup script.
- Waits until Docker responds to `docker version` (retries).
- By default the script blocks and "Press any key to exit" — it will only exit when a key is pressed.
  This matches the project spec. Use `-NoPause` to run non-interactively (for automation).

Usage:
  PowerShell -File .\start-wsl-docker.ps1
  PowerShell -File .\start-wsl-docker.ps1 -NoPause
#>

param(
    [string]$DistroName = 'lotr-docker-service',
    [switch]$NoPause
)

Set-StrictMode -Version Latest

function Write-Log {
    param([string]$msg)
    $timestamp = (Get-Date).ToString('o')
    $line = "$timestamp`t$msg"
    $logDir = "build\docker\logs"
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
    $logFile = Join-Path $logDir "start-wsl-docker.log"
    Add-Content -Path $logFile -Value $line
    Write-Host $msg
}

Write-Log "Starting start-wsl-docker.ps1 for distro $DistroName"

# Ensure distro exists
try {
    $installed = @(wsl -l -q 2>$null)
}
catch {
    Write-Log "WSL not available on this host or wsl command failed: $_"
    exit 2
}

if (-not ($installed -contains $DistroName)) {
    Write-Log "Distro '$DistroName' not found. Create or import it first."
    exit 3
}

# Ensure WSL distro is running (trigger by invoking a noop)
$runningList = @(wsl -l -v 2>$null)
$foundLine = $runningList | Where-Object { $_ -match $DistroName }
if ($foundLine -notmatch 'Running') {
    Write-Log "Starting WSL distro $DistroName"
    try {
        wsl -d $DistroName -u root -- bash -lc 'echo starting >/dev/null'
    }
    catch {
        Write-Log "Failed to start distro: $_"
        exit 4
    }
}
else {
    Write-Log "Distro $DistroName already running"
}

# Detect systemd presence by checking /proc/1/comm
try {
    $proc1 = wsl -d $DistroName -u root -- bash -lc 'cat /proc/1/comm' 2>$null
    $proc1 = $proc1 -replace "\r|\n", ''
}
catch {
    $proc1 = ""
}

if ($proc1 -eq 'systemd') {
    Write-Log "systemd detected (PID 1 = systemd). Using systemctl to start Docker."
    try {
        wsl -d $DistroName -u root -- bash -lc 'systemctl enable --now docker' 2>&1 | Write-Log
    }
    catch {
        Write-Log "systemctl start failed: $_"
    }
}
else {
    Write-Log "systemd not detected. Launching dockerd via persistent Windows process (keeps WSL session alive)."
    # Check if dockerd is already running in the distro
    $alreadyRunning = $false
    try {
        wsl -d $DistroName -u root -- bash -c "test -S /var/run/docker.sock" 2>$null
        if ($LASTEXITCODE -eq 0) { $alreadyRunning = $true }
    } catch { }

    if (-not $alreadyRunning) {
        # Start-Process keeps the WSL session open so dockerd survives after this script exits.
        # Without this, WSL terminates the distro when the last session closes, killing dockerd.
        Start-Process -FilePath "wsl.exe" `
            -ArgumentList @("-d", $DistroName, "-u", "root", "--", "dockerd", "--host", "unix:///var/run/docker.sock") `
            -WindowStyle Hidden
        Write-Log "dockerd started as background Windows process."
    } else {
        Write-Log "dockerd socket already present, skipping start."
    }
}

# Wait for Docker to respond
$maxAttempts = 15
$attempt = 0
$dockerReady = $false
while ($attempt -lt $maxAttempts) {
    $attempt++
    Write-Log "Checking docker availability (attempt $attempt/$maxAttempts)"
    try {
        wsl -d $DistroName -u root -- docker version > $null 2>&1
        if ($LASTEXITCODE -eq 0) { $dockerReady = $true; break }
    }
    catch { }
    Start-Sleep -Seconds 2
}

if (-not $dockerReady) {
    Write-Log "Docker did not become ready after $maxAttempts attempts"
    exit 6
}

Write-Log "Docker is running in $DistroName"
wsl -d $DistroName -u root -- docker version | Write-Log

if (-not $NoPause) {
    Write-Host "\nDocker started. Press any key to exit and leave Docker running..." -ForegroundColor Green
    $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
    Write-Log "User pressed key; exiting start script"
}
else {
    Write-Log "NoPause specified; not waiting for key press"
}

exit 0
