<#
ensure-lotr-distro.ps1

Downloads an official Ubuntu 24.04 WSL rootfs tarball (or uses a supplied one)
and imports it as a WSL2 distro named lotr-docker-service.

Spec: build/docker/docker-spec.md -- Ubuntu Install section.

Usage:
  .\ensure-lotr-distro.ps1
  .\ensure-lotr-distro.ps1 -TarballPath .\ubuntu-24.04-wsl.tar.gz

Exit codes:
  0  success
  2  lotr-docker-service already exists
  3  download failed and no -TarballPath supplied
  5  tarball file not found after download
  6  wsl --import failed

#>

param(
    [string]$TarballPath,
    [string]$InstallPath  = "C:\wsl\lotr-docker-service",
    [string]$DistroName   = "lotr-docker-service",
    [string]$ManifestPath = "build\docker\artifacts\manifest.json"
)

Set-StrictMode -Version Latest

function Write-Log {
    param([string]$msg)
    $timestamp = (Get-Date).ToString('o')
    $logDir = "build\docker\logs"
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
    $logFile = Join-Path $logDir "ensure-lotr-distro.log"
    Add-Content -Path $logFile -Value ("$timestamp`t$msg")
    Write-Host $msg
}

Write-Log "Starting ensure-lotr-distro.ps1"

# -----------------------------------------------------------------------
# Guard: abort if the target distro already exists
# -----------------------------------------------------------------------
try   { $installed = @(wsl -l -q 2>$null) } catch { $installed = @() }

if ($installed -contains $DistroName) {
    Write-Log ("Distro '{0}' already exists. Aborting." -f $DistroName)
    Write-Log ("To replace it, run: wsl --unregister {0}" -f $DistroName)
    exit 2
}

Write-Log ("Distro '{0}' does not exist. Proceeding." -f $DistroName)

# -----------------------------------------------------------------------
# Obtain rootfs tarball
# Per spec: (a) -TarballPath, (b) cache, (c) wsl --install Ubuntu-24.04 + export
# -----------------------------------------------------------------------
$artifactDir = Split-Path $ManifestPath -Parent
if (-not (Test-Path $artifactDir)) {
    New-Item -ItemType Directory -Path $artifactDir -Force | Out-Null
}

$cacheFile = Join-Path $artifactDir "ubuntu-24.04-wsl.tar"

if (-not $TarballPath) {
    if (Test-Path $cacheFile) {
        Write-Log ("Using cached rootfs: {0}" -f $cacheFile)
        $TarballPath = $cacheFile
    }
    else {
        # Obtain Ubuntu 24.04 via wsl --install (non-interactive with --no-launch)
        # If Ubuntu-24.04 is already installed, export it directly.
        # Otherwise install it first, then export, and leave it on the system.
        $u2404 = 'Ubuntu-24.04'
        $freshInstall = $false

        if (-not ($installed -contains $u2404)) {
            Write-Log ("Installing {0} via wsl --install --no-launch (this may take a moment)" -f $u2404)
            wsl --install $u2404 --no-launch
            if ($LASTEXITCODE -ne 0) {
                Write-Log ("wsl --install {0} failed (exit {1}). Supply -TarballPath and re-run." -f $u2404, $LASTEXITCODE)
                exit 3
            }
            $freshInstall = $true
            Write-Log ("Installed {0}." -f $u2404)
        }
        else {
            Write-Log ("Found existing {0} -- will export it." -f $u2404)
        }

        Write-Log ("Exporting {0} to {1}" -f $u2404, $cacheFile)
        wsl --export $u2404 $cacheFile
        if ($LASTEXITCODE -ne 0) {
            Write-Log ("wsl --export failed (exit {0})" -f $LASTEXITCODE)
            exit 3
        }
        Write-Log "Export complete."

        if ($freshInstall) {
            Write-Log ("Note: {0} remains installed. Unregister it with: wsl --unregister {0}" -f $u2404)
        }

        $TarballPath = $cacheFile
    }
}

if (-not (Test-Path $TarballPath)) {
    Write-Log ("TarballPath not found: {0}" -f $TarballPath)
    exit 5
}

# -----------------------------------------------------------------------
# Import as lotr-docker-service (WSL2)
# wsl --import accepts .tar and .tar.gz on WSL 2.x
# -----------------------------------------------------------------------
if (-not (Test-Path $InstallPath)) {
    New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
}

Write-Log ("Importing '{0}' as '{1}' into '{2}'" -f $TarballPath, $DistroName, $InstallPath)
wsl --import $DistroName $InstallPath $TarballPath --version 2
if ($LASTEXITCODE -ne 0) {
    Write-Log ("wsl --import failed with exit code {0}" -f $LASTEXITCODE)
    exit 6
}
Write-Log "Import successful."

# -----------------------------------------------------------------------
# Set /etc/wsl.conf default=root
# -----------------------------------------------------------------------
Write-Log "Writing /etc/wsl.conf to set default user to root"
wsl -d $DistroName -u root -- bash -c "printf '[user]\ndefault=root\n' > /etc/wsl.conf"
if ($LASTEXITCODE -ne 0) {
    Write-Log ("Warning: could not write /etc/wsl.conf (exit {0})" -f $LASTEXITCODE)
}
else {
    Write-Log "/etc/wsl.conf set: default=root"
}

# -----------------------------------------------------------------------
# Record artifact manifest
# -----------------------------------------------------------------------
try {
    $sha256 = (Get-FileHash -Algorithm SHA256 -Path $TarballPath -ErrorAction Stop).Hash
    Write-Log ("SHA256: {0}" -f $sha256)
}
catch {
    Write-Log ("Warning: SHA256 computation failed: {0}" -f $_.Exception.Message)
    $sha256 = $null
}

try {
    $entry = [PSCustomObject]@{
        distro     = $DistroName
        tarball    = (Resolve-Path $TarballPath).Path
        sha256     = $sha256
        created_at = (Get-Date).ToString('o')
    }

    if (-not (Test-Path $ManifestPath)) {
        @($entry) | ConvertTo-Json -Depth 5 | Out-File -FilePath $ManifestPath -Encoding utf8
    }
    else {
        $existing = Get-Content -Raw $ManifestPath | ConvertFrom-Json
        (@($existing) + $entry) | ConvertTo-Json -Depth 5 | Out-File -FilePath $ManifestPath -Encoding utf8
    }
    Write-Log ("Manifest updated: {0}" -f $ManifestPath)
}
catch {
    Write-Log ("Warning: manifest update failed: {0}" -f $_.Exception.Message)
}

Write-Log "ensure-lotr-distro completed."
exit 0
