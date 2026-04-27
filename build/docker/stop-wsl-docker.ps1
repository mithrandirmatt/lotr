<#
stop-wsl-docker.ps1

Stops the Docker daemon inside the lotr-docker-service WSL distro.
- If systemd is active (PID 1 is systemd), uses systemctl stop docker.
- Otherwise kills dockerd via /var/run/dockerd.pid.
- Optional -Terminate flag also runs wsl --terminate to shut down the distro entirely.

Spec: build/docker/docker-spec.md -- Docker Setup section.

Usage:
  PowerShell -File .\stop-wsl-docker.ps1
  PowerShell -File .\stop-wsl-docker.ps1 -Terminate
  PowerShell -File .\stop-wsl-docker.ps1 -NoPause
#>

param(
    [string]$DistroName = 'lotr-docker-service',
    [switch]$Terminate,
    [switch]$NoPause
)

Set-StrictMode -Version Latest

function Write-Log {
    param([string]$msg)
    $timestamp = (Get-Date).ToString('o')
    $logDir = "build\docker\logs"
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
    $logFile = Join-Path $logDir "stop-wsl-docker.log"
    Add-Content -Path $logFile -Value ("$timestamp`t$msg")
    Write-Host $msg
}

Write-Log ("Starting stop-wsl-docker.ps1 for distro {0}" -f $DistroName)

# Ensure distro exists and is running
try {
    $installed = @(wsl -l -q 2>$null)
}
catch {
    Write-Log ("WSL command failed: {0}" -f $_.Exception.Message)
    exit 2
}

if (-not ($installed -contains $DistroName)) {
    Write-Log ("Distro '{0}' not found. Nothing to stop." -f $DistroName)
    exit 3
}

# Detect whether systemd is PID 1
$pid1 = wsl -d $DistroName -u root -- cat /proc/1/comm 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Log ("Could not read /proc/1/comm -- distro may not be running (exit {0})." -f $LASTEXITCODE)
    Write-Log "Nothing to stop."
    exit 0
}
$pid1comm = ($pid1 | Out-String).Trim()
Write-Log ("PID 1 comm: {0}" -f $pid1comm)

if ($pid1comm -eq 'systemd') {
    Write-Log "systemd detected -- stopping Docker via systemctl"
    wsl -d $DistroName -u root -- systemctl stop docker
    if ($LASTEXITCODE -ne 0) {
        Write-Log ("systemctl stop docker failed (exit {0})" -f $LASTEXITCODE)
    }
    else {
        Write-Log "Docker stopped via systemctl."
    }
}
else {
    Write-Log "systemd not active -- killing dockerd via /var/run/dockerd.pid"
    $pidContent = wsl -d $DistroName -u root -- cat /var/run/dockerd.pid 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $pidContent) {
        Write-Log "No /var/run/dockerd.pid found -- Docker may already be stopped."
    }
    else {
        $dockerPid = ($pidContent | Out-String).Trim()
        Write-Log ("Sending SIGTERM to dockerd PID {0}" -f $dockerPid)
        wsl -d $DistroName -u root -- kill -TERM $dockerPid 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Log ("kill -TERM failed (exit {0})" -f $LASTEXITCODE)
        }
        else {
            Write-Log "SIGTERM sent."
        }
    }
}

if ($Terminate) {
    Write-Log ("Terminating WSL distro '{0}'" -f $DistroName)
    wsl --terminate $DistroName
    if ($LASTEXITCODE -ne 0) {
        Write-Log ("wsl --terminate failed (exit {0})" -f $LASTEXITCODE)
    }
    else {
        Write-Log ("Distro '{0}' terminated." -f $DistroName)
    }
}

Write-Log "stop-wsl-docker completed."

if (-not $NoPause) {
    Write-Host ""
    Write-Host "Done. Press any key to exit..."
    try {
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    }
    catch {
        Start-Sleep -Seconds 1
    }
}

exit 0
