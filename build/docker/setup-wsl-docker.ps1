<#
setup-wsl-docker.ps1

Orchestrates enabling WSL features, importing/ensuring the `lotr-docker-service` distro,
installing Docker inside the distro, and verifying the installation. Uses a robust
script-transfer method to avoid quoting/crlf issues.

Usage:
  PowerShell -ExecutionPolicy Bypass -File .\setup-wsl-docker.ps1 -TarballPath .\ubuntu-24.04-lotr.tar

#>

param(
    [string]$TarballPath,
    [string]$InstallPath = "C:\wsl\lotr-docker-service",
    [string]$DistroName = "lotr-docker-service",
    [string]$ManifestPath = "build\docker\artifacts\manifest.json",
    [switch]$NoPause
)

Set-StrictMode -Version Latest

function Write-Log {
    param([string]$msg)
    $timestamp = (Get-Date).ToString('o')
    $line = "$timestamp`t$msg"
    $logDir = "build\docker\logs"
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
    $logFile = Join-Path $logDir "setup-wsl-docker.log"
    Add-Content -Path $logFile -Value $line
    Write-Host $msg
}

function Ensure-Admin {
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        Write-Log "Not running elevated. Attempting to relaunch with elevation..."
        # Rebuild argument list to preserve parameters
        $argList = @("-NoProfile","-ExecutionPolicy","Bypass")
        # If the caller did not request NoPause, keep the elevated window open with -NoExit
        if (-not $PSBoundParameters.ContainsKey('NoPause')) {
            $argList += "-NoExit"
        }
        $argList += "-File"
        $argList += $PSCommandPath
        foreach ($k in $PSBoundParameters.Keys) {
            $v = $PSBoundParameters[$k]
            # Handle switch parameters (boolean) and normal values
            if ($v -is [bool]) {
                if ($v) { $argList += "-$k" }
            }
            else {
                $argList += "-$k"
                $argList += "$v"
            }
        }
        Start-Process -FilePath "powershell.exe" -ArgumentList $argList -Verb RunAs
        exit 0
    }
}

Write-Log "Starting setup-wsl-docker.ps1"

Ensure-Admin

# Enable WSL features
try {
    Write-Log "Enabling WSL features (if necessary)..."
    $feature = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -ErrorAction SilentlyContinue
    if ($feature -and $feature.State -ne 'Enabled') {
        Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart -ErrorAction Stop
        Write-Log "Enabled Microsoft-Windows-Subsystem-Linux"
    }
    else { Write-Log "WSL feature already enabled" }

    $vmFeature = Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -ErrorAction SilentlyContinue
    if ($vmFeature -and $vmFeature.State -ne 'Enabled') {
        Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart -ErrorAction Stop
        Write-Log "Enabled VirtualMachinePlatform"
    }
    else { Write-Log "VirtualMachinePlatform already enabled" }
}
catch {
    Write-Log "Failed to enable WSL features: $_"
    exit 6
}

# Update WSL if available
try {
    Write-Log "Updating WSL components (best-effort)..."
    wsl --update 2>$null
}
catch {
    Write-Log "wsl --update failed or not supported on this host: $_"
}

# Check whether distro exists already
try { $exists = (wsl -l -q) | Select-String -Pattern "^$DistroName$" -SimpleMatch } catch { $exists = $null }
if ($exists) {
    Write-Log "Distro '$DistroName' already exists. Aborting to avoid overwrite. To replace, run: wsl --unregister $DistroName"
    exit 2
}

# Call the importer helper. The importer supports either a provided tarball or will
# attempt to download an official Ubuntu 24.04 rootfs when no tarball is supplied.
$importer = Join-Path $PSScriptRoot 'ensure-lotr-distro.ps1'
if (-not (Test-Path $importer)) {
    Write-Log "Importer script not found at $importer"
    exit 7
}
Write-Log "Calling importer: $importer"
& $importer -TarballPath $TarballPath -InstallPath $InstallPath -DistroName $DistroName -ManifestPath $ManifestPath
if (-not $?) {
    Write-Log "Importer failed"
    exit 8
}

# Prepare install script content
$installScript = @'
#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y ca-certificates curl gnupg lsb-release apt-transport-https

mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Create start wrapper
cat > /usr/local/bin/lotr-start-docker.sh <<'EOF'
#!/bin/sh
if [ "$(cat /proc/1/comm 2>/dev/null)" = "systemd" ]; then
  systemctl enable --now docker
  exit $?
fi
nohup /usr/bin/dockerd > /var/log/dockerd.log 2>&1 &
echo $! > /var/run/dockerd.pid
EOF
chmod +x /usr/local/bin/lotr-start-docker.sh

# Try to start docker (systemd when available, otherwise wrapper)
if [ "$(cat /proc/1/comm 2>/dev/null)" = "systemd" ]; then
  systemctl daemon-reload || true
  systemctl enable --now docker || true
else
  /usr/local/bin/lotr-start-docker.sh || true
fi
'@

# Normalize and write install script to temp file with UTF8 no BOM
$tempFile = Join-Path $env:TEMP ("lotr_install_$([System.Guid]::NewGuid().ToString()).sh")
$scriptContents = $installScript -replace "`r`n","`n"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tempFile, $scriptContents, $utf8NoBom)
Write-Log "Wrote install script to $tempFile"

# Transfer script into WSL via /mnt/ path (avoids CRLF re-introduction from PowerShell pipe)
$driveLetter = $tempFile.Substring(0,1).ToLower()
$wslTempPath = '/mnt/' + $driveLetter + ($tempFile.Substring(2) -replace '\\','/')

try {
    Write-Log "Transferring install script into WSL distro $DistroName"
    wsl -d $DistroName -u root -- cp $wslTempPath /tmp/install.sh
    if ($LASTEXITCODE -ne 0) { Write-Log "Failed to copy install script into distro"; exit 11 }
    Write-Log "Running bash -n /tmp/install.sh"
    wsl -d $DistroName -u root -- bash -n /tmp/install.sh
    if ($LASTEXITCODE -ne 0) { Write-Log "Syntax check failed"; exit 9 }

    Write-Log "Executing /tmp/install.sh inside distro"
    wsl -d $DistroName -u root -- bash /tmp/install.sh
    if ($LASTEXITCODE -ne 0) { Write-Log "Install script failed"; exit 10 }
}
catch {
    Write-Log "Error transferring or executing install script: $_"
    exit 11
}

# Verification: wait for docker to become available
Write-Log "Verifying Docker service inside distro"
$maxAttempts = 10
$ok = $false
for ($i=1; $i -le $maxAttempts; $i++) {
    wsl -d $DistroName -u root -- docker version 2>$null
    if ($LASTEXITCODE -eq 0) { $ok = $true; break }
    Write-Log "Docker not ready yet (attempt $i/$maxAttempts), sleeping 3s"
    Start-Sleep -Seconds 3
}
if (-not $ok) { Write-Log "Docker did not become available"; exit 12 }

Write-Log "Docker appears available. Gathering verification info..."
wsl -d $DistroName -u root -- docker version
wsl -d $DistroName -u root -- docker info
wsl -d $DistroName -u root -- cat /etc/wsl.conf

Write-Log "setup-wsl-docker completed successfully"

if (-not $NoPause) {
    Write-Host "`nSetup complete. Press any key to exit..." -ForegroundColor Green
    try {
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    }
    catch {
        # If host doesn't support RawUI (e.g., non-interactive), just sleep briefly
        Start-Sleep -Seconds 1
    }
    Write-Log "User pressed key; exiting setup script"
}
else {
    Write-Log "NoPause specified; exiting without pause"
}

exit 0
