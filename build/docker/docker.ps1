<#
docker.ps1

Build or run the lotr dev container.

Commands:
  build  -- build the Docker image from build/docker/Dockerfile
  run    -- run the container interactively (mounts repo root as /workspace)

The Docker daemon must already be running inside lotr-docker-service before using
this script. Start it with:
  PowerShell -ExecutionPolicy Bypass -File build/docker/start-wsl-docker.ps1

Usage:
    PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 build
    PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 build --fresh
    PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 run
    PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 build -Tag my-image:v2
    PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 run   -Tag my-image:v2
#>

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('build', 'run')]
    [string]$Command,

    [string]$DistroName = 'lotr-docker-service',
    [string]$Tag        = 'lotr-dev:latest',
    [switch]$Fresh,
    [switch]$NoPause
)

Set-StrictMode -Version Latest

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
function Write-Log {
    param([string]$msg)
    $timestamp = (Get-Date).ToString('o')
    $logDir = "build\docker\logs"
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
    $logFile = Join-Path $logDir "docker.log"
    Add-Content -Path $logFile -Value ("$timestamp`t$msg")
    Write-Host $msg
}

# ---------------------------------------------------------------------------
# Guard: distro must exist
# ---------------------------------------------------------------------------
# Accept GNU-style --fresh flag (case-insensitive) in addition to the PowerShell
# switch parameter (-Fresh). This lets callers use `--fresh` when invoking the
# script from shells that expect GNU-style flags while preserving backward
# compatibility with `-Fresh`.
$IsFresh = $Fresh.IsPresent
if ($args -and ($args | Where-Object { $_ -match '^--fresh$' })) {
    $IsFresh = $true
}

Write-Log ("docker.ps1  command={0}  distro={1}  tag={2}  fresh={3}" -f $Command, $DistroName, $Tag, $IsFresh)

try {
    $installed = @(wsl -l -q 2>$null)
}
catch {
    Write-Log "WSL is not available on this host."
    exit 1
}

if (-not ($installed -contains $DistroName)) {
    Write-Log ("Distro '{0}' not found. Run setup-wsl-docker.ps1 first." -f $DistroName)
    exit 2
}

# Guard: Docker socket must be reachable
$socketCheck = wsl -d $DistroName -u root -- bash -lc 'test -S /var/run/docker.sock && echo ok' 2>$null
if ($socketCheck -notmatch 'ok') {
    Write-Log "Docker socket not found. Start Docker first with start-wsl-docker.ps1."
    exit 3
}

# ---------------------------------------------------------------------------
# Resolve the repo root as a WSL path (/mnt/<drive>/...) for volume mounts
# ---------------------------------------------------------------------------
$repoRoot    = (Get-Location).Path
$driveLetter = $repoRoot.Substring(0, 1).ToLower()
$repoRelPath = $repoRoot.Substring(2) -replace '\\', '/'
$wslRepoRoot = ("/mnt/{0}{1}" -f $driveLetter, $repoRelPath)

# Dockerfile is relative to the repo root inside WSL
$dockerfileWslPath = "$wslRepoRoot/build/docker/Dockerfile"

Write-Log ("Repo root (WSL):  {0}" -f $wslRepoRoot)
Write-Log ("Dockerfile (WSL): {0}" -f $dockerfileWslPath)

# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
if ($Command -eq 'build') {
    Write-Log ("Building image '{0}' ..." -f $Tag)

    $noCacheFlag = if ($IsFresh) { '--no-cache' } else { $null }

    if ($IsFresh) { Write-Log 'Fresh build: Docker layer cache disabled.' }

    wsl -d $DistroName -u root -- docker build `
        --file "$dockerfileWslPath" `
        --tag  $Tag `
        $noCacheFlag `
        $wslRepoRoot

    if ($LASTEXITCODE -ne 0) {
        Write-Log ("Build FAILED (exit {0})." -f $LASTEXITCODE)
        if (-not $NoPause) { Write-Host "Press any key to exit..."; $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') }
        exit $LASTEXITCODE
    }

    Write-Log ("Image '{0}' built successfully." -f $Tag)
}

# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------
if ($Command -eq 'run') {
    Write-Log ("Running interactive shell in image '{0}' ..." -f $Tag)
    Write-Log ("Mounting {0} -> /workspace" -f $wslRepoRoot)

    # -it: interactive + pseudo-TTY
    # --rm: remove container on exit
    # -v:   bind-mount repo root into /workspace
    # -w:   set working directory inside container
    wsl -d $DistroName -u root -- docker run `
        --rm `
        --interactive `
        --tty `
        --volume  "${wslRepoRoot}:/workspace" `
        --workdir "/workspace/build" `
        $Tag `
        /bin/bash

    if ($LASTEXITCODE -ne 0) {
        Write-Log ("Container exited with code {0}." -f $LASTEXITCODE)
        exit $LASTEXITCODE
    }

    Write-Log "Container session ended."
}

Write-Log "docker.ps1 done."
if ($Command -eq 'build' -and -not $NoPause) { Write-Host "Press any key to exit..."; $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') }
