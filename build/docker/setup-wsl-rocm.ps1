<#
.SYNOPSIS
    Install ROCm + ROCDXG inside a WSL2 distro non-interactively.

    Usage examples:
      PowerShell -ExecutionPolicy Bypass -File build/docker/setup-wsl-rocm.ps1
      PowerShell -ExecutionPolicy Bypass -File build/docker/setup-wsl-rocm.ps1 -DistroName lotr-docker-service -NoPause
#>
param(
    [string]$DistroName = 'lotr-docker-service',
    [switch]$NoPause,
    [string]$RocmMetaPackage = 'amdrocm7.12-gfx950',
    [string]$AmdGPURepoVersion = '30.30'
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$LogDir = Join-Path $ScriptDir 'logs'
if (-not (Test-Path $LogDir)) { New-Item -Path $LogDir -ItemType Directory -Force | Out-Null }
$MainLog = Join-Path $LogDir 'setup-wsl-rocm.log'
# Per-run log to avoid concurrent file locks
$RunLog = Join-Path $LogDir ("setup-wsl-rocm-{0:yyyyMMdd-HHmmss}-{1}.log" -f (Get-Date), ([guid]::NewGuid().ToString().Substring(0,8)))

function Log {
    param([string]$m)
    $t = (Get-Date).ToString("u")
    $line = "$t $m`n"
    if (-not (Test-Path $RunLog)) {
        [System.IO.File]::WriteAllText($RunLog, $line, [System.Text.Encoding]::UTF8)
    } else {
        [System.IO.File]::AppendAllText($RunLog, $line, [System.Text.Encoding]::UTF8)
    }
}

Log "Starting setup-wsl-rocm.ps1 (Distro=$DistroName RocmMeta=$RocmMetaPackage AMDRepo=$AmdGPURepoVersion)"

# Check WSL availability
try {
    & wsl -l -v > $null 2>&1
} catch {
    Log "WSL not available"
    Write-Error "WSL not available on host. Install and enable WSL2."
    exit 1
}

# Check distro exists (robust)
try {
    $rawList = & wsl -l -v 2>&1
} catch {
    $rawList = $_.Exception.Message
}
$distros = if ($rawList -is [System.Array]) { ($rawList -join "`n") -replace "`0", "" } else { ([string]$rawList) -replace "`0", "" }
Log "WSL list: $distros"
if ([string]::IsNullOrWhiteSpace($distros) -or $distros -notlike "*$DistroName*") {
    Log "Distro '$DistroName' not found in WSL list"
    Write-Error "Distro '$DistroName' not found. Create it first or pass -DistroName."
    exit 2
}

# Bash install script (written to Windows temp then copied into WSL)
$bash = @'
#!/usr/bin/env bash
set -euo pipefail

ROCM_KEY_URLS=(
  "https://repo.amd.com/rocm/packages/gpg/rocm.gpg.key"
  "https://repo.amd.com/rocm/packages/gpg/rocm.gpg"
  "https://repo.amd.com/rocm/rocm.gpg.key"
  "https://repo.amd.com/rocm/rocm.gpg"
  "https://repo.amd.com/rocm/packages/gpg/amdrocm.gpg"
  "https://repo.radeon.com/rocm/rocm.gpg.key"
)
ROCM_REPO_URL="https://repo.amd.com/rocm/packages/ubuntu2404"
AMDGPU_REPO_URL="https://repo.radeon.com/amdgpu/30.30/ubuntu"
ROCM_META_PKG="amdrocm7.12-gfx950"

export DEBIAN_FRONTEND=noninteractive

# initial update (best-effort)
apt-get update || true

# Try to capture missing key IDs and fetch them from multiple sources
update_out=$(apt-get update 2>&1 || true)
echo "$update_out"
missing_keys=$(echo "$update_out" | sed -n 's/.*NO_PUBKEY //p' | tr '\n' ' ')
if [ -n "$missing_keys" ]; then
    for k in $missing_keys; do
        echo "Attempting to fetch missing key $k via gpg keyserver"
        # try multiple keyservers with gpg
        gpg --no-default-keyring --keyring /tmp/attempt.keyring --keyserver hkps://keyserver.ubuntu.com --recv-keys "$k" || true
        # gpg --export outputs binary directly; write it without dearmoring
        gpg --no-default-keyring --keyring /tmp/attempt.keyring --export "$k" >/etc/apt/keyrings/amdrocm.gpg 2>/dev/null || true
        echo "Attempting apt-key adv for $k"
        apt-key adv --keyserver hkps://keyserver.ubuntu.com --recv-keys "$k" || true
    done
    apt-get update || true
fi

# Ensure tools installed
apt-get install -y --no-install-recommends gnupg wget ca-certificates lsb-release apt-transport-https software-properties-common build-essential cmake git || true

mkdir -p /etc/apt/keyrings

# Try multiple remote key URLs and heuristics
key_ok=false
for url in "${ROCM_KEY_URLS[@]}"; do
    echo "Fetching key from $url"
    wget -qO /tmp/rocm_key_temp "$url" || true
    if [ ! -s /tmp/rocm_key_temp ]; then continue; fi
    if grep -q "BEGIN PGP" /tmp/rocm_key_temp 2>/dev/null; then
        # ASCII armored - dearmor to binary
        gpg --dearmor /tmp/rocm_key_temp -o /etc/apt/keyrings/amdrocm.gpg 2>/dev/null || true
    else
        # Already binary GPG format - copy directly (gpg --dearmor only converts ASCII->binary)
        cp /tmp/rocm_key_temp /etc/apt/keyrings/amdrocm.gpg
    fi
    if [ -s /etc/apt/keyrings/amdrocm.gpg ]; then
        echo "Wrote /etc/apt/keyrings/amdrocm.gpg from $url"
        key_ok=true
        break
    fi
done

# fallback: try amdgpu repo key
if [ "$key_ok" = false ]; then
    echo "Attempting to fetch AMDGPU key as fallback"
    if wget -qO- https://repo.radeon.com/amdgpu/rocm.gpg.key | gpg --dearmor -o /etc/apt/keyrings/amdrocm.gpg 2>/dev/null; then
        key_ok=true
    fi
fi

# fallback: export from legacy /etc/apt/trusted.gpg (apt-key may have deposited FA296B056C5BB456 there)
if [ "$key_ok" = false ] && [ -f /etc/apt/trusted.gpg ]; then
    gpg --no-default-keyring --keyring /etc/apt/trusted.gpg \
        --export FA296B056C5BB456 >/etc/apt/keyrings/amdrocm.gpg 2>/dev/null || true
    if [ -s /etc/apt/keyrings/amdrocm.gpg ]; then
        echo "Exported FA296B056C5BB456 from legacy trusted.gpg"
        key_ok=true
    fi
fi

# write sources, prefer signed-by when key present
if [ "$key_ok" = true ] && [ -s /etc/apt/keyrings/amdrocm.gpg ]; then
    cat >/etc/apt/sources.list.d/rocm.list <<EOF
deb [arch=amd64 signed-by=/etc/apt/keyrings/amdrocm.gpg] $ROCM_REPO_URL stable main
EOF
    cat >/etc/apt/sources.list.d/amdgpu.list <<EOF
deb [arch=amd64,i386 signed-by=/etc/apt/keyrings/amdrocm.gpg] $AMDGPU_REPO_URL noble main
EOF
else
    echo "WARNING: Could not fetch AMD ROCm GPG key; adding repos as trusted to continue (UNVERIFIED)."
    cat >/etc/apt/sources.list.d/rocm.list <<EOF
deb [arch=amd64 trusted=yes] $ROCM_REPO_URL stable main
EOF
    cat >/etc/apt/sources.list.d/amdgpu.list <<EOF
deb [arch=amd64,i386 trusted=yes] $AMDGPU_REPO_URL noble main
EOF
fi

# Update and detect remaining missing keys; if present, switch to trusted=yes for AMD repos
update_out2=$(apt-get update 2>&1 || true)
echo "$update_out2"
if echo "$update_out2" | grep -q "NO_PUBKEY"; then
    echo "Still missing pubkeys after fetch attempts. Enabling trusted=yes for AMD repos to continue."
    sed -i 's/signed-by=\/etc\/apt\/keyrings\/amdrocm.gpg/trusted=yes/g' /etc/apt/sources.list.d/rocm.list || true
    sed -i 's/signed-by=\/etc\/apt\/keyrings\/amdrocm.gpg/trusted=yes/g' /etc/apt/sources.list.d/amdgpu.list || true
    apt-get update || true
fi

# Remove conflicting packages if present (ignore errors)
apt-get remove -y libhsa-runtime64-1 libhsakmt1 || true

# Install additional packages and ROCm meta package (best-effort)
apt-get install -y --no-install-recommends libatomic1 libquadmath0 || true
apt-get install -y --no-install-recommends $ROCM_META_PKG || true

# Install WSL-specific HSA runtime (package name may vary; || true if absent)
apt-get install -y --no-install-recommends hsa-runtime-rocr4wsl-amdgpu hsa-runtime-rocr4wsl || true

# Build and install librocdxg (best-effort; failure does not abort the script)
# Requires WIN_SDK env var pointing to the Windows SDK Include directory, e.g.:
#   /mnt/c/Program Files (x86)/Windows Kits/10/Include/10.0.26100.0
# cmake expects: -DWIN_SDK=<path-to-sdk-shared-subdir>
build_librocdxg() {
    # Resolve the 'shared' subdirectory of the Windows SDK
    local win_sdk_shared=""
    if [ -n "${WIN_SDK:-}" ] && [ -d "${WIN_SDK}/shared" ]; then
        # Symlink avoids spaces in the path when passed to cmake
        ln -sfn "${WIN_SDK}/shared" /tmp/winsdk_shared 2>/dev/null || true
        win_sdk_shared="/tmp/winsdk_shared"
        echo "librocdxg: using Windows SDK shared headers -> ${WIN_SDK}/shared"
    elif [ -f "/usr/lib/wsl/include/ntstatus.h" ]; then
        win_sdk_shared="/usr/lib/wsl/include"
        echo "librocdxg: using /usr/lib/wsl/include"
    else
        echo "WARNING: WIN_SDK not set or Windows SDK 'shared' dir not found; skipping librocdxg build"
        return 1
    fi

    cd /tmp
    rm -rf librocdxg
    git clone https://github.com/ROCm/librocdxg.git || return 1
    cd librocdxg
    git checkout develop 2>&1 || true
    mkdir -p build && cd build
    cmake .. "-DWIN_SDK=${win_sdk_shared}" -DCMAKE_INSTALL_PREFIX=/opt/rocm 2>&1 || { echo "cmake failed"; return 1; }
    make -j"$(nproc)" 2>&1 || { echo "make failed"; return 1; }
    make install 2>&1 || true
}
build_librocdxg || echo "WARNING: librocdxg build failed (non-fatal; ROCm packages are still installed)"

# Post-install env
cat >/etc/profile.d/set-rocm-env.sh <<EOT
export LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/core/lib/rocm_sysdeps/lib:\$LD_LIBRARY_PATH
EOT
chmod +x /etc/profile.d/set-rocm-env.sh

# Verify
echo "=== ROCm files ==="
ls -l /opt/rocm* || true
echo "=== librocdxg ==="
ldconfig || true
'@

# Prefer running the persistent installer script from the repository to avoid transfer issues
$repoScript = Join-Path $ScriptDir 'install-rocm-wsl.sh'
if (-not (Test-Path $repoScript)) {
    Log "Repository installer $repoScript not found; falling back to temporary transfer"
    # fallback behavior: write temp file as before
    $tmpFile = Join-Path $env:TEMP ("install-rocm-rocdxg-$([guid]::NewGuid()).sh")
    $bashLF = $bash -replace "`r`n","`n"
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($tmpFile, $bashLF, $utf8NoBom)
    Log "Wrote temporary bash script $tmpFile"
    $drive = $tmpFile.Substring(0,1).ToLower()
    $rest = $tmpFile.Substring(2) -replace '\\','/'
    $wslTmpPath = "/mnt/$drive/$rest"
    & wsl -d $DistroName -u root -- bash -lc "cp '$wslTmpPath' /tmp/install-rocm.sh && chmod +x /tmp/install-rocm.sh"
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to copy temp script into WSL. See log $RunLog"; exit 5 }
    & wsl -d $DistroName -u root -- bash -n /tmp/install-rocm.sh
    if ($LASTEXITCODE -ne 0) { Write-Error "Syntax check failed in WSL. See $RunLog"; exit 6 }
    Log "Executing /tmp/install-rocm.sh in $DistroName"
} else {
    # Use the repo script file via /mnt path to execute directly in WSL
    $absRepo = (Resolve-Path $repoScript).Path
    $drive = $absRepo.Substring(0,1).ToLower()
    $rest = $absRepo.Substring(2) -replace '\\','/'
    $wslRepoPath = "/mnt/$drive/$rest"
    Log "Executing repository installer $absRepo -> WSL path $wslRepoPath"

    # If a vendored keyring is present in the repository, copy it into WSL
    $repoKeyDir = Join-Path $ScriptDir 'keyrings'
    $repoKeyBin = Join-Path $repoKeyDir 'amdrocm.gpg'
    $repoKeyB64 = Join-Path $repoKeyDir 'amdrocm.gpg.b64'
    $repoKeyAscii = Join-Path $repoKeyDir 'rocm.gpg.key'
    if (Test-Path $repoKeyBin) {
        try {
            $absKeyBin = (Resolve-Path $repoKeyBin).Path
            $drive = $absKeyBin.Substring(0,1).ToLower()
            $rest = $absKeyBin.Substring(2) -replace '\\','/'
            $wslKeyBinPath = "/mnt/$drive/$rest"
            Log "Copying vendored keyring $absKeyBin -> WSL /etc/apt/keyrings/amdrocm.gpg"
            & wsl -d $DistroName -u root -- bash -lc "mkdir -p /etc/apt/keyrings; cp '$wslKeyBinPath' /etc/apt/keyrings/amdrocm.gpg; chmod 644 /etc/apt/keyrings/amdrocm.gpg; rm -f /etc/apt/sources.list.d/rocm.list /etc/apt/sources.list.d/amdgpu.list" 2>&1 | Tee-Object -FilePath $RunLog -Append
            & wsl -d $DistroName -u root -- bash -lc "apt-get update" 2>&1 | Tee-Object -FilePath $RunLog -Append
        } catch {
            Log "Failed to copy vendored keyring: $_"
        }
    } elseif (Test-Path $repoKeyB64) {
        try {
            $absKeyB64 = (Resolve-Path $repoKeyB64).Path
            $drive = $absKeyB64.Substring(0,1).ToLower()
            $rest = $absKeyB64.Substring(2) -replace '\\','/'
            $wslKeyB64Path = "/mnt/$drive/$rest"
            Log "Decoding vendored base64 key $absKeyB64 -> WSL /etc/apt/keyrings/amdrocm.gpg"
            & wsl -d $DistroName -u root -- bash -lc "mkdir -p /etc/apt/keyrings; base64 -d '$wslKeyB64Path' > /etc/apt/keyrings/amdrocm.gpg; chmod 644 /etc/apt/keyrings/amdrocm.gpg; rm -f /etc/apt/sources.list.d/rocm.list /etc/apt/sources.list.d/amdgpu.list" 2>&1 | Tee-Object -FilePath $RunLog -Append
            & wsl -d $DistroName -u root -- bash -lc "apt-get update" 2>&1 | Tee-Object -FilePath $RunLog -Append
        } catch {
            Log "Failed to decode/copy vendored base64 key: $_"
        }
    } elseif (Test-Path $repoKeyAscii) {
        try {
            $absKeyAscii = (Resolve-Path $repoKeyAscii).Path
            $drive = $absKeyAscii.Substring(0,1).ToLower()
            $rest = $absKeyAscii.Substring(2) -replace '\\','/'
            $wslKeyAsciiPath = "/mnt/$drive/$rest"
            Log "Copying vendored ASCII key $absKeyAscii -> WSL and dearmoring to /etc/apt/keyrings/amdrocm.gpg"
            & wsl -d $DistroName -u root -- bash -lc "mkdir -p /etc/apt/keyrings; cp '$wslKeyAsciiPath' /tmp/rocm_key.asc; gpg --dearmor /tmp/rocm_key.asc -o /etc/apt/keyrings/amdrocm.gpg 2>/dev/null || true; chmod 644 /etc/apt/keyrings/amdrocm.gpg; rm -f /etc/apt/sources.list.d/rocm.list /etc/apt/sources.list.d/amdgpu.list" 2>&1 | Tee-Object -FilePath $RunLog -Append
            & wsl -d $DistroName -u root -- bash -lc "apt-get update" 2>&1 | Tee-Object -FilePath $RunLog -Append
        } catch {
            Log "Failed to copy/dearmor vendored ASCII key: $_"
        }
    } else {
        Log "No vendored keyring found in repo ($repoKeyBin or $repoKeyB64)"
    }
}
# Detect Windows SDK on the host and pass it into the WSL environment when available
$winSdkWsl = $null
try {
    $sdkBase = 'C:\Program Files (x86)\Windows Kits\10\Include'
    if (Test-Path $sdkBase) {
        $versions = @(Get-ChildItem -Path $sdkBase -Directory -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name | Sort-Object -Descending)
        if ($versions.Count -gt 0) {
            $ver = $versions[0]
            # Construct WSL-accessible path
            $escaped = ($sdkBase -replace '\\','/').Replace('C:','/mnt/c')
            $winSdkWsl = "$escaped/$ver"
            Log "Detected host Windows SDK: $sdkBase\\$ver -> WSL path: $winSdkWsl"
        }
    }
} catch {
    Log "Windows SDK detection failed: $_"
}

# Write WSL runtime output to the per-run log to avoid concurrent locks
try {
    if ($wslRepoPath) {
        $cmdNoSdk = "bash '$wslRepoPath'"
        $cmdWithSdk = "export WIN_SDK='$winSdkWsl'; bash '$wslRepoPath'"
        if ($winSdkWsl) {
            $wslOut = & wsl -d $DistroName -u root -- bash -lc $cmdWithSdk 2>&1
        } else {
            $wslOut = & wsl -d $DistroName -u root -- bash -lc $cmdNoSdk 2>&1
        }
    } else {
        $cmdNoSdk = "/tmp/install-rocm.sh"
        $cmdWithSdk = "export WIN_SDK='$winSdkWsl'; /tmp/install-rocm.sh"
        if ($winSdkWsl) {
            $wslOut = & wsl -d $DistroName -u root -- bash -lc $cmdWithSdk 2>&1
        } else {
            $wslOut = & wsl -d $DistroName -u root -- bash -lc $cmdNoSdk 2>&1
        }
    }
    if ($wslOut -ne $null) { $wslOut | Tee-Object -FilePath $RunLog -Append }
    $rc = $LASTEXITCODE
} catch {
    Log "WSL execution failed: $_"
    $_ | Out-String | Tee-Object -FilePath $RunLog -Append
    $rc = 1
}
Log "Execution finished with exit code $rc"

# Cleanup
if ($tmpFile -and (Test-Path $tmpFile)) { Remove-Item -Path $tmpFile -Force -ErrorAction SilentlyContinue; Log "Removed temporary file $tmpFile" }

# Merge per-run log into aggregated main log (best-effort with retries)
for ($attempt = 0; $attempt -lt 5; $attempt++) {
    try {
        if (-not (Test-Path $MainLog)) { New-Item -Path $MainLog -ItemType File -Force | Out-Null }
        Get-Content -Raw -Encoding UTF8 $RunLog | Out-File -FilePath $MainLog -Encoding UTF8 -Append
        break
    } catch {
        Start-Sleep -Seconds (1 + $attempt)
    }
}
Log "Appended run log to $MainLog"

if (-not $NoPause) {
    Write-Host "Installation script finished with exit code $rc. Press Enter to continue..."
    Read-Host | Out-Null
}

exit $rc




