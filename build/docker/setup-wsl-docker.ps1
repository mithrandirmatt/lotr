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
    [switch]$NoPause,
    [switch]$InstallKernel,
    [string]$KernelUrl = "",
    [string]$RocmMetaPackage = 'amdrocm7.12-gfx950',
    [string]$AmdGPURepoVersion = '30.30',
    [switch]$SkipRocm
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

# Robust distro-exists check: wsl -l -q outputs UTF-16LE which confuses Select-String.
# Instead probe the distro directly; if it answers we know it is registered.
# wsl -l -q outputs UTF-16LE which confuses Select-String, so probe directly.
$distroExists = $false
try {
    $probe = wsl -d $DistroName -u root -- echo ok 2>$null
    $distroExists = ($probe -match 'ok')
} catch { $distroExists = $false }

if ($distroExists) {
    Write-Log "Distro '$DistroName' already exists -- skipping import, re-running Docker/ROCDXG setup."
} else {
    # Call the importer helper. Supports a provided tarball or downloads Ubuntu 24.04.
    $importer = Join-Path $PSScriptRoot 'ensure-lotr-distro.ps1'
    if (-not (Test-Path $importer)) {
        Write-Log "Importer script not found at $importer"
        exit 7
    }
    Write-Log "Calling importer: $importer"
    & $importer -TarballPath $TarballPath -InstallPath $InstallPath -DistroName $DistroName -ManifestPath $ManifestPath
    $importerExit = $LASTEXITCODE
    if ($importerExit -eq 2) {
        Write-Log "Importer reports distro already exists -- continuing to configuration."
    } elseif ($importerExit -ne 0) {
        Write-Log ("Importer failed with exit code {0}" -f $importerExit)
        exit 8
    }
} # end distro-import gate

# ---------------------------------------------------------------------------
# Docker install (always runs -- idempotent; safe to re-run on existing distro)
# ---------------------------------------------------------------------------
$installScript = @'
#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y ca-certificates curl gnupg lsb-release apt-transport-https

    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --batch --yes --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
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

# Ensure dockerd is running (idempotent -- wrapper checks PID 1 / systemd itself)
Write-Log "Starting Docker daemon inside distro (if not already running)..."
# Ensure dockerd is running via a persistent Windows-side process.
# WSL2 kills background processes when the last session exits, so we must
# launch dockerd from Start-Process (keeps the WSL session alive from Windows).
Write-Log "Starting Docker daemon inside distro (if not already running)..."

# Check if dockerd is already running inside the distro
$daemonRunning = wsl -d $DistroName -u root -- bash -c 'docker info >/dev/null 2>&1 && echo yes || echo no' 2>$null
if ($daemonRunning -match 'yes') {
    Write-Log "Docker daemon already running -- skipping start."
} else {
    # Check if systemd is PID 1 (then it manages dockerd itself)
    $pid1 = wsl -d $DistroName -u root -- bash -c 'cat /proc/1/comm 2>/dev/null' 2>$null
    if ($pid1 -match 'systemd') {
        Write-Log "systemd detected -- enabling and starting docker via systemctl."
        wsl -d $DistroName -u root -- systemctl enable --now docker 2>$null
    } else {
        Write-Log "No systemd -- launching dockerd via Start-Process (persistent Windows-side session)."
        # Kill any stale dockerd first
        wsl -d $DistroName -u root -- bash -c 'pkill -f dockerd || true' 2>$null
        Start-Sleep -Seconds 1
        $null = Start-Process -FilePath 'wsl' `
            -ArgumentList @('-d', $DistroName, '-u', 'root', '--',
                            'dockerd', '--host', 'unix:///var/run/docker.sock') `
            -WindowStyle Hidden -PassThru
        Write-Log "dockerd launched; waiting for socket..."
        Start-Sleep -Seconds 4
    }
}

# Verification: wait for docker to become available
Write-Log "Verifying Docker service inside distro"
$maxAttempts = 10
$ok = $false
for ($i=1; $i -le $maxAttempts; $i++) {
    wsl -d $DistroName -u root -- docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $ok = $true; break }
    Write-Log "Docker daemon not ready yet (attempt $i/$maxAttempts), sleeping 3s"
    Start-Sleep -Seconds 3
}
if (-not $ok) { Write-Log "Docker did not become available"; exit 12 }

Write-Log "Docker appears available. Gathering verification info..."
wsl -d $DistroName -u root -- docker version
wsl -d $DistroName -u root -- docker info
wsl -d $DistroName -u root -- cat /etc/wsl.conf

# ---------------------------------------------------------------------------
# WSL HSA / KFD verification + optional custom kernel installation
# ---------------------------------------------------------------------------
function Test-WSLHsa {
    param([string]$Distro)
    try {
        $out = wsl -d $Distro -u root -- bash -lc "if [ -c /dev/kfd ]; then echo yes; elif [ -f /proc/config.gz ]; then zcat /proc/config.gz | grep -q CONFIG_HSA_AMD && echo yes || echo no; else echo no; fi" 2>$null
        return $out.Trim() -eq 'yes'
    } catch {
        return $false
    }
}

function Ensure-WSLHsa {
    param(
        [string]$Distro,
        [switch]$InstallKernel,
        [string]$KernelUrl
    )

    Write-Log "Checking WSL distro '$Distro' for HSA/KFD support..."
    if (Test-WSLHsa -Distro $Distro) { Write-Log "HSA/KFD present in $Distro"; return $true }

    Write-Log "HSA/KFD missing. Running 'wsl --update' and restarting WSL (best-effort) to pick up vendor kernel..."
    try { wsl --update 2>$null } catch {}
    try { wsl --shutdown 2>$null } catch {}
    Start-Sleep -Seconds 3

    if (Test-WSLHsa -Distro $Distro) { Write-Log "HSA/KFD available after wsl --update/shutdown"; return $true }

    Write-Log "HSA/KFD still missing after update."
    if (-not $InstallKernel) {
        Write-Log "To auto-fix, re-run with -InstallKernel -KernelUrl <url-to-prebuilt-wsl-kernel>."
        Write-Log "Or update the Windows AMD driver / vendor WSL kernel per vendor guidance."
        return $false
    }

    if ([string]::IsNullOrEmpty($KernelUrl)) {
        Write-Log "-InstallKernel was requested but no -KernelUrl provided; aborting kernel install."
        return $false
    }

    $kernelDir = Join-Path $env:USERPROFILE '.wsl-kernels\lotr'
    if (-not (Test-Path $kernelDir)) { New-Item -ItemType Directory -Path $kernelDir -Force | Out-Null }
    $kernelWinPath = Join-Path $kernelDir 'kernel'

    Write-Log ("Downloading custom WSL kernel from {0} to {1}" -f $KernelUrl, $kernelWinPath)
    try {
        Invoke-WebRequest -Uri $KernelUrl -OutFile $kernelWinPath -UseBasicParsing -ErrorAction Stop
    } catch {
        Write-Log ("Failed to download kernel: {0}" -f $_)
        return $false
    }

    $wslConfigPath = Join-Path $env:USERPROFILE '.wslconfig'
    if (Test-Path $wslConfigPath) {
        Copy-Item $wslConfigPath ($wslConfigPath + ".bak." + ((Get-Date).ToString('yyyyMMddHHmmss'))) -Force
        $content = Get-Content $wslConfigPath -Raw
        if ($content -match '\[wsl2\]') {
            if ($content -match 'kernel\s*=') {
                $content = [Regex]::Replace($content, '(?m)^\s*kernel\s*=.*$', "kernel=$kernelWinPath")
            } else {
                $content = $content + "`nkernel=$kernelWinPath`n"
            }
        } else {
            $content = $content + "`n[wsl2]`nkernel=$kernelWinPath`n"
        }
        Set-Content -Path $wslConfigPath -Value $content -Encoding ASCII
    } else {
        "[wsl2]`nkernel=$kernelWinPath`n" | Out-File -FilePath $wslConfigPath -Encoding ASCII
    }

    Write-Log "Updated .wslconfig to use custom kernel; shutting down WSL to apply changes."
    try { wsl --shutdown 2>$null } catch {}
    Start-Sleep -Seconds 3

    if (Test-WSLHsa -Distro $Distro) { Write-Log "HSA/KFD now present after custom kernel install"; return $true }
    Write-Log "HSA/KFD still not present after custom kernel install. Manual intervention required.";
    return $false
}

# Run the WSL HSA check and optional install (idempotent)
$hsaOk = Ensure-WSLHsa -Distro $DistroName -InstallKernel:$InstallKernel -KernelUrl $KernelUrl
if (-not $hsaOk) { Write-Log "Warning: WSL HSA/KFD support not available; ROCm may not function."
    Write-Log "If you want automatic kernel install, re-run with -InstallKernel -KernelUrl <url>" }

# ---------------------------------------------------------------------------
# ROCDXG (librocdxg) -- auto-install when AMD GPU + /dev/dxg detected
# ---------------------------------------------------------------------------
function Resolve-WindowsSdkPath {
    # Try the registry first (most reliable)
    $regRoots = @(
        'HKLM:\SOFTWARE\Microsoft\Windows Kits\Installed Roots',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows Kits\Installed Roots'
    )
    foreach ($root in $regRoots) {
        try {
            $kitsRoot = (Get-ItemProperty -Path $root -ErrorAction Stop).'KitsRoot10'
            if ($kitsRoot -and (Test-Path $kitsRoot)) {
                $includeBase = Join-Path $kitsRoot 'Include'
                if (Test-Path $includeBase) {
                    $best = Get-ChildItem -Path $includeBase -Directory |
                        Where-Object { Test-Path (Join-Path $_.FullName 'shared') } |
                        Sort-Object Name -Descending |
                        Select-Object -First 1
                    if ($best) { return $best.FullName }
                }
            }
        } catch {}
    }
    # Fallback: scan common filesystem location
    $fsBase = 'C:\Program Files (x86)\Windows Kits\10\Include'
    if (Test-Path $fsBase) {
        $best = Get-ChildItem -Path $fsBase -Directory |
            Where-Object { Test-Path (Join-Path $_.FullName 'shared') } |
            Sort-Object Name -Descending |
            Select-Object -First 1
        if ($best) { return $best.FullName }
    }
    return $null
}

function Install-Rocdxg {
    param([string]$Distro)

    # Check for AMD/Radeon GPU on the Windows host
    $gpus = try {
        Get-CimInstance -ClassName Win32_VideoController -ErrorAction Stop |
            Select-Object -ExpandProperty Name
    } catch { @() }

    $isAmd = $gpus | Where-Object { $_ -match 'AMD|Radeon|RX ' }
    if (-not $isAmd) {
        Write-Log "ROCDXG: no AMD/Radeon GPU detected on Windows host -- skipping."
        return
    }
    Write-Log ("ROCDXG: AMD GPU found ({0})." -f ($isAmd -join ', '))

    # Check /dev/dxg inside WSL distro
    $dxgExists = wsl -d $Distro -u root -- bash -c 'test -c /dev/dxg && echo yes || echo no' 2>$null
    if ($dxgExists -notmatch 'yes') {
        Write-Log "ROCDXG: /dev/dxg not present in $Distro -- skipping (Windows driver may be too old)."
        return
    }
    Write-Log "ROCDXG: /dev/dxg confirmed. Proceeding with librocdxg installation..."

    # Detect Windows SDK path from the Windows side (registry + filesystem)
    $winSdkWin = Resolve-WindowsSdkPath
    $winSdkWsl = $null
    if ($winSdkWin) {
        $sdkDrive = $winSdkWin.Substring(0,1).ToLower()
        $winSdkWsl = '/mnt/' + $sdkDrive + ($winSdkWin.Substring(2) -replace '\\','/')
        Write-Log ("ROCDXG: Windows SDK detected at {0}" -f $winSdkWin)
        Write-Log ("ROCDXG: WSL path: {0}" -f $winSdkWsl)
    } else {
        Write-Log "ROCDXG: Windows SDK not found on host."
        Write-Log "  Install from: https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/"
        Write-Log "  Then re-run setup-wsl-docker.ps1"
        return
    }

    # Locate install_rocdxg.sh relative to this script
    $rocdxgScript = Join-Path $PSScriptRoot 'install_rocdxg.sh'
    if (-not (Test-Path $rocdxgScript)) {
        Write-Log ("ROCDXG: installer script not found at {0} -- skipping." -f $rocdxgScript)
        return
    }

    # Convert Windows path to WSL /mnt/ path
    $drive    = $rocdxgScript.Substring(0,1).ToLower()
    $wslSrc   = '/mnt/' + $drive + ($rocdxgScript.Substring(2) -replace '\\','/')
    $wslDest  = '/tmp/install_rocdxg.sh'

    Write-Log "ROCDXG: copying installer into $Distro ..."
    wsl -d $Distro -u root -- cp $wslSrc $wslDest
    if ($LASTEXITCODE -ne 0) { Write-Log "ROCDXG: failed to copy installer -- skipping."; return }

    wsl -d $Distro -u root -- chmod +x $wslDest
    if ($LASTEXITCODE -ne 0) { Write-Log "ROCDXG: chmod failed -- skipping."; return }

    Write-Log "ROCDXG: running installer (this may take several minutes) ..."
    wsl -d $Distro -u root -- bash -c "WIN_SDK='$winSdkWsl' bash $wslDest"
    if ($LASTEXITCODE -eq 0) {
        Write-Log "ROCDXG: installation succeeded."
        Write-Log "ROCDXG: verify with: wsl -d $Distro -u root -- bash -lc 'source /etc/profile.d/rocdxg.sh; rocminfo | head -n 50'"
    } elseif ($LASTEXITCODE -eq 1) {
        Write-Log "ROCDXG: /dev/dxg check failed inside WSL -- Windows driver may need updating."
    } else {
        Write-Log ("ROCDXG: installer exited with code {0} -- check WSL log at /var/log/install_rocdxg.log" -f $LASTEXITCODE)
        Write-Log "  To inspect: wsl -d $Distro -u root -- cat /var/log/install_rocdxg.log"
    }
}

Install-Rocdxg -Distro $DistroName

# ---------------------------------------------------------------------------
# ROCm stack (integrated -- replaces separate setup-wsl-rocm.ps1 invocation)
# ---------------------------------------------------------------------------
if ($SkipRocm) {
    Write-Log "SkipRocm specified -- skipping ROCm installation."
} else {
    $rocmScript = Join-Path $PSScriptRoot 'setup-wsl-rocm.ps1'
    if (Test-Path $rocmScript) {
        Write-Log "Installing ROCm stack via $rocmScript ..."
        & $rocmScript `
            -DistroName $DistroName `
            -NoPause `
            -RocmMetaPackage $RocmMetaPackage `
            -AmdGPURepoVersion $AmdGPURepoVersion
        if ($LASTEXITCODE -ne 0) {
            Write-Log ("WARNING: ROCm install reported exit code {0} -- Docker is still installed and functional." -f $LASTEXITCODE)
        } else {
            Write-Log "ROCm installation completed successfully."
        }
    } else {
        Write-Log ("WARNING: ROCm script not found at {0} -- skipping ROCm install." -f $rocmScript)
    }
}

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
