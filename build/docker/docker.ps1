<#
docker.ps1

Build or run the lotr dev container.

Commands:
  build  -- build both the lotr-dev image (build/docker/Dockerfile) and the
            lotr-mcp image (build/docker/mcp/Dockerfile)
  run    -- (re)start the MCP container in the background (port 3100), then open an
            interactive shell in the lotr-dev container

The Docker daemon must already be running inside lotr-docker-service before using
this script. Start it with:
  PowerShell -ExecutionPolicy Bypass -File build/docker/start-wsl-docker.ps1

Usage:
    PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 build
    PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 build --fresh
    PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 run
    PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 build -Tag my-image:v2 -McpTag my-mcp:v2
    PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 run   -Tag my-image:v2 -McpTag my-mcp:v2
#>

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('build', 'run')]
    [string]$Command,

    [string]$DistroName = 'lotr-docker-service',
    [string]$Tag        = 'lotr-dev:latest',
    [string]$McpTag     = 'lotr-mcp:latest',
    [switch]$Fresh,
    [switch]$NoPause,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs = @()
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
if ($ExtraArgs -contains '--fresh') {
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

    # Build MCP image
    $mcpContextWslPath = "$wslRepoRoot/build/docker/mcp"
    Write-Log ("Building MCP image '{0}' ..." -f $McpTag)

    wsl -d $DistroName -u root -- docker build `
        --tag  $McpTag `
        $noCacheFlag `
        $mcpContextWslPath

    if ($LASTEXITCODE -ne 0) {
        Write-Log ("MCP build FAILED (exit {0})." -f $LASTEXITCODE)
        if (-not $NoPause) { Write-Host "Press any key to exit..."; $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') }
        exit $LASTEXITCODE
    }

    Write-Log ("MCP image '{0}' built successfully." -f $McpTag)
}

# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------
if ($Command -eq 'run') {
    Write-Log ("Running interactive shell in image '{0}' ..." -f $Tag)
    Write-Log ("Mounting {0} -> /workspace" -f $wslRepoRoot)

# Resolve Windows SSH key folder as a WSL path for the volume mount
$sshWinPath  = Join-Path $env:USERPROFILE ".ssh"
$sshDrive    = $sshWinPath.Substring(0, 1).ToLower()
$sshRelPath  = $sshWinPath.Substring(2) -replace '\\', '/'
$wslSshPath  = ("/mnt/{0}{1}" -f $sshDrive, $sshRelPath)

Write-Log ("SSH keys (WSL):   {0}" -f $wslSshPath)

# Resolve Windows .gitconfig as a WSL path for the volume mount
$gitconfigWinPath = Join-Path $env:USERPROFILE ".gitconfig"
$gitconfigDrive   = $gitconfigWinPath.Substring(0, 1).ToLower()
$gitconfigRelPath = $gitconfigWinPath.Substring(2) -replace '\\', '/'
$wslGitconfigPath = ("/mnt/{0}{1}" -f $gitconfigDrive, $gitconfigRelPath)

Write-Log ("Git config (WSL): {0}" -f $wslGitconfigPath)

# Resolve Windows .continue folder as a WSL path for the volume mount
$continueWinPath = Join-Path $env:USERPROFILE ".continue"
$continueDrive   = $continueWinPath.Substring(0, 1).ToLower()
$continueRelPath = $continueWinPath.Substring(2) -replace '\\', '/'
$wslContinuePath = ("/mnt/{0}{1}" -f $continueDrive, $continueRelPath)

Write-Log ("Continue (WSL):   {0}" -f $wslContinuePath)

    # Ensure shared network exists so dev and mcp containers can reach each other
    $netExists = wsl -d $DistroName -u root -- docker network ls --filter "name=lotr-net" -q 2>$null
    if (-not $netExists) {
        Write-Log "Creating Docker network lotr-net..."
        wsl -d $DistroName -u root -- docker network create lotr-net | Out-Null
    }

    # (Re)start MCP container — always stop any existing instance so the
    # container picks up the latest image and environment on every `run`.
    $mcpRunning = wsl -d $DistroName -u root -- docker ps --filter "name=lotr-mcp" --filter "status=running" -q 2>$null
    if ($mcpRunning) {
        Write-Log "Stopping existing MCP container..."
        wsl -d $DistroName -u root -- docker rm -f lotr-mcp 2>$null | Out-Null
    } else {
        # Remove any stopped lotr-mcp container that may be holding the name
        wsl -d $DistroName -u root -- docker rm -f lotr-mcp 2>$null | Out-Null
    }
    Write-Log "Starting MCP container on port 3100..."
    wsl -d $DistroName -u root -- docker run `
        --detach `
        --name lotr-mcp `
        --restart on-failure:10 `
        --network lotr-net `
        --publish 3100:3100 `
        --volume "${wslRepoRoot}:/workspace" `
        $McpTag
    if ($LASTEXITCODE -ne 0) {
        Write-Log ("MCP container start FAILED (exit {0}). Continuing anyway." -f $LASTEXITCODE)
    } else {
        Write-Log "MCP container started."
    }

    # -it: interactive + pseudo-TTY
    # --rm: remove container on exit
    # -v:   repo -> /workspace; Windows .ssh (ppk source) -> /root/.ssh:rw;
    #        named volume lotr-ssh-keys -> /root/.ssh_keys (Linux fs, chmod works, persistent);
    #        .gitconfig -> /root/.gitconfig:ro
    #        .continue  -> /host-continue:rw (for sync_continue make target)
    # -w:   set working directory inside container
    # --network lotr-net: shared network so dev container can reach mcp at http://lotr-mcp:3100/sse
    wsl -d $DistroName -u root -- docker run `
        --rm `
        --interactive `
        --tty `
        --network lotr-net `
        --volume  "${wslRepoRoot}:/workspace" `
        --volume  "${wslSshPath}:/root/.ssh:rw" `
        --volume  "lotr-ssh-keys:/root/.ssh_keys" `
        --volume  "${wslGitconfigPath}:/root/.gitconfig:ro" `
        --volume  "${wslContinuePath}:/host-continue:rw" `
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
