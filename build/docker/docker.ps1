<#
docker.ps1

Build or run the lotr dev container.

Commands:
  build  -- build both the lotr-dev image (build/docker/Dockerfile) and the
            lotr-ai image (build/docker/ai/Dockerfile)
  run    -- (re)start the MCP container in the background (port 3100), then open an
            interactive shell in the lotr-dev container

The Docker daemon must already be running inside lotr-docker-service before using
this script. Start it with:
  PowerShell -ExecutionPolicy Bypass -File build/docker/start-wsl-docker.ps1

Usage:
    PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 build
    PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 build --fresh
    PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 build -GpuVariant rocm
    PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 run
    PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 run   -GpuVariant rocm
    PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 build -Tag my-image:v2 -McpTag my-mcp:v2
    PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 run   -Tag my-image:v2 -McpTag my-mcp:v2
#>

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('build', 'run')]
    [string]$Command,

    [string]$DistroName  = 'lotr-docker-service',
    [string]$Tag         = 'lotr-dev:latest',
    [string]$McpTag      = '',
    [string]$HostOllamaModels = '',
    [Alias('HostPort')]
    [int]$HostOllamaPort = 11435,
    # Leave blank to auto-detect from host GPU (AMD->rocm, NVIDIA->cuda, else cpu)
    [ValidateSet('','cpu','rocm','cuda')]
    [string]$GpuVariant  = '',
    [switch]$Fresh,
    [switch]$NoPause,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs = @()
)

Set-StrictMode -Version Latest

# ---------------------------------------------------------------------------
# GPU auto-detection (Windows host)
# ---------------------------------------------------------------------------
function Resolve-GpuVariant {
    try {
        $gpus = Get-CimInstance -ClassName Win32_VideoController -ErrorAction Stop |
                Select-Object -ExpandProperty Name
        foreach ($name in $gpus) {
            if ($name -match 'AMD|Radeon|RX ') { return 'rocm' }
            if ($name -match 'NVIDIA|GeForce|Quadro|Tesla|RTX|GTX') { return 'cuda' }
        }
    } catch {
        # CIM not available (non-Windows or access denied) - fall through to cpu
    }
    return 'cpu'
}

if (-not $GpuVariant) {
    $GpuVariant = Resolve-GpuVariant
    Write-Host ("[gpu-detect] Auto-detected GPU_VARIANT={0}" -f $GpuVariant)
}

# Resolve McpTag default based on GpuVariant (allows explicit override via -McpTag)
if (-not $McpTag) {
    $McpTag = if ($GpuVariant -eq 'cpu') { 'lotr-ai:latest' } else { "lotr-ai:$GpuVariant" }
}

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
# Docker readiness helpers
# ---------------------------------------------------------------------------
function Test-DockerResponsive {
    param([string]$Distro)
    wsl -d $Distro -u root -- docker version >$null 2>&1
    return ($LASTEXITCODE -eq 0)
}

function Wait-For-Docker {
    param([string]$Distro, [int]$MaxAttempts = 15, [int]$IntervalSeconds = 2)
    for ($i = 1; $i -le $MaxAttempts; $i++) {
        Write-Log ("Checking docker availability (attempt {0}/{1})" -f $i, $MaxAttempts)
        wsl -d $Distro -u root -- docker version >$null 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Log ("Docker is running in {0}" -f $Distro)
            return $true
        }
        Start-Sleep -Seconds $IntervalSeconds
    }
    return $false
}

function Stop-HostOllamaIfPresent {
    Write-Log "Checking for host Ollama process (Windows)..."
    try {
        $ollamaProcs = Get-Process -Name 'ollama' -ErrorAction SilentlyContinue
        if ($ollamaProcs) {
            foreach ($p in $ollamaProcs) {
                Write-Log ("Found host Ollama process PID {0} (Name={1}); stopping..." -f $p.Id, $p.ProcessName)
                try {
                    Stop-Process -Id $p.Id -Force -ErrorAction Stop
                    Write-Log ("Stopped host Ollama PID {0}." -f $p.Id)
                } catch {
                    Write-Log ("Failed to stop host Ollama PID {0}: {1}" -f $p.Id, $_)
                }
            }
            return
        }
    } catch {
        Write-Log "Get-Process failed or running on non-Windows host; skipping name-based check."
    }

    # Fallback: check for a listener on the configured Ollama host port on the Windows host
    try {
        $conn = Get-NetTCPConnection -LocalPort $HostOllamaPort -State Listen -ErrorAction SilentlyContinue
        if ($conn) {
            $pid = $conn.OwningProcess
            $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Log ("Detected host process {0} (PID {1}) listening on {2}; attempting to stop..." -f $proc.ProcessName, $pid, $HostOllamaPort)
                try {
                    Stop-Process -Id $pid -Force -ErrorAction Stop
                    Write-Log ("Stopped process PID {0} listening on {1}." -f $pid, $HostOllamaPort)
                } catch {
                    Write-Log ("Failed to stop process PID {0} listening on {1}: {2}" -f $pid, $HostOllamaPort, $_)
                }
            }
        }
    } catch {
        Write-Log "Get-NetTCPConnection unavailable or failed; skipping port-based host check."
    }
}

function Remove-Containers-PublishingPort {
    param([string]$Distro, [int]$Port)
    Write-Log ("Checking Docker for containers publishing port {0}..." -f $Port)
    try {
        $containers = wsl -d $Distro -u root -- docker ps --filter "publish=$Port" -q 2>$null
        if ($containers -and $containers.Trim()) {
            $ids = $containers -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
            foreach ($id in $ids) {
                Write-Log ("Stopping container {0} that publishes port {1}..." -f $id, $Port)
                wsl -d $Distro -u root -- docker rm -f $id 2>$null | Out-Null
            }
        } else {
            Write-Log ("No containers found publishing port {0}." -f $Port)
        }
    } catch {
        Write-Log ("Docker container check for port {0} failed: {1}" -f $Port, $_)
    }
}

# Default start script path and args (used when auto-starting Docker)
$startScript = Join-Path $PSScriptRoot 'start-wsl-docker.ps1'
$startArgs = @('-DistroName', $DistroName, '-NoPause')

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

# Guard: Docker socket must be reachable. If missing, attempt to start it.
$socketCheck = wsl -d $DistroName -u root -- bash -lc 'test -S /var/run/docker.sock && echo ok' 2>$null
if ($socketCheck -notmatch 'ok') {
    Write-Log "Docker socket not found. Attempting to start Docker in distro {0} via start-wsl-docker.ps1..." -f $DistroName

    try {
        & powershell -ExecutionPolicy Bypass -File $startScript @startArgs
        $startExit = $LASTEXITCODE
    }
    catch {
        Write-Log "Failed to invoke start-wsl-docker.ps1: $_"
        if (-not $NoPause) { Write-Host "Press any key to exit..."; $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') }
        exit 3
    }

    if ($startExit -ne 0) {
        Write-Log ("start-wsl-docker.ps1 failed (exit {0})." -f $startExit)
        if (-not $NoPause) { Write-Host "Press any key to exit..."; $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') }
        exit 3
    }

    # Wait for Docker to become responsive
    if (-not (Wait-For-Docker -Distro $DistroName -MaxAttempts 15 -IntervalSeconds 2)) {
        Write-Log "Docker did not become ready after 15 attempts"
        $socketCheck = wsl -d $DistroName -u root -- bash -lc 'test -S /var/run/docker.sock && echo ok || echo missing' 2>$null
        Write-Log ("Socket check: {0}" -f $socketCheck)
        $psOutput = wsl -d $DistroName -u root -- ps aux 2>&1
        Write-Log ("Process list: {0}" -f $psOutput)
        if (-not $NoPause) { Write-Host "Press any key to exit..."; $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') }
        exit 3
    }
    else {
        Write-Log "Docker is responsive."
    }
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

# Resolve host Ollama models directory (Windows path) -> WSL path for mounts
$hostModelsWinPath = if ($HostOllamaModels -and $HostOllamaModels.Trim()) { $HostOllamaModels } else { Join-Path $env:USERPROFILE ".ollama\models" }
Write-Log ("Host Ollama models (Windows): {0}" -f $hostModelsWinPath)
try {
    if (Test-Path -Path $hostModelsWinPath) {
        $modelsDrive = $hostModelsWinPath.Substring(0,1).ToLower()
        $modelsRelPath = $hostModelsWinPath.Substring(2) -replace '\\','/'
        $wslModelsPath = ("/mnt/{0}{1}" -f $modelsDrive, $modelsRelPath)
        Write-Log ("Host Ollama models (WSL): {0}" -f $wslModelsPath)
    } else {
        $wslModelsPath = $null
        Write-Log ("Host Ollama models folder not found on Windows: {0}" -f $hostModelsWinPath)
    }
} catch {
    $wslModelsPath = $null
    Write-Log ("Error resolving host Ollama models path: {0}" -f $_)
}

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

    # Build AI image (previously MCP)
    $mcpContextWslPath = "$wslRepoRoot/build/docker/ai"
    Write-Log ("Building AI image '{0}' (GPU_VARIANT={1}) ..." -f $McpTag, $GpuVariant)

    wsl -d $DistroName -u root -- docker build `
        --tag  $McpTag `
        --build-arg "GPU_VARIANT=$GpuVariant" `
        $noCacheFlag `
        $mcpContextWslPath

    if ($LASTEXITCODE -ne 0) {
        Write-Log ("AI build FAILED (exit {0})." -f $LASTEXITCODE)
        if (-not $NoPause) { Write-Host "Press any key to exit..."; $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') }
        exit $LASTEXITCODE
    }

    Write-Log ("AI image '{0}' built successfully." -f $McpTag)
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

# ------------------------------------------------------------
# Expose host Ollama to containers by default (auto-detect)
# - Prefer an 'ollama' container on the `lotr-net` network if present
# - Otherwise try host.docker.internal:<host port> (defaults to 11435)
# - Can be overridden by setting OLLAMA_URL or OLLAMA_ORIGINS in the environment
# ------------------------------------------------------------
$ollamaUrlEnv = $env:OLLAMA_URL
$ollamaOriginsEnv = $env:OLLAMA_ORIGINS
if (-not $ollamaOriginsEnv) { $ollamaOriginsEnv = '*' }

if (-not $ollamaUrlEnv) {
    Write-Log "Auto-detecting Ollama endpoint..."
    # Check for an 'ollama' container running in the distro
    $ollamaContainer = wsl -d $DistroName -u root -- docker ps --filter "name=ollama" --filter "status=running" -q 2>$null
    if ($ollamaContainer) {
        $ollamaUrlEnv = 'http://ollama:11434'
        Write-Log ("Detected running 'ollama' container; using {0}" -f $ollamaUrlEnv)
    }
    else {
        Write-Log ("Checking host.docker.internal:{0} from distro {1}..." -f $HostOllamaPort, $DistroName)
        $curlTest = wsl -d $DistroName -u root -- bash -lc "curl -sS -m 2 http://host.docker.internal:$HostOllamaPort/ || echo __CURL_ERROR__" 2>$null
        if ($curlTest -and $curlTest -ne "__CURL_ERROR__") {
            $ollamaUrlEnv = "http://host.docker.internal:$HostOllamaPort"
            Write-Log ("host.docker.internal reachable; using {0}" -f $ollamaUrlEnv)
        }
        else {
            $ollamaUrlEnv = "http://host.docker.internal:$HostOllamaPort"
            Write-Log ("Could not detect Ollama; defaulting to {0}" -f $ollamaUrlEnv)
        }
    }
}

    # Ensure Docker is still responsive before performing network/container ops
    if (-not (Test-DockerResponsive -Distro $DistroName)) {
        Write-Log "Docker not responsive when preparing network; attempting to restart..."
        & powershell -ExecutionPolicy Bypass -File $startScript @startArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Log ("Re-start failed (exit {0})." -f $LASTEXITCODE)
            if (-not $NoPause) { Write-Host "Press any key to exit..."; $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') }
            exit 3
        }
        if (-not (Wait-For-Docker -Distro $DistroName -MaxAttempts 10 -IntervalSeconds 2)) {
            Write-Log "Docker did not become ready after restart attempt. Exiting."
            if (-not $NoPause) { Write-Host "Press any key to exit..."; $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') }
            exit 3
        }
    }

    # Ensure shared network exists so dev and ai containers can reach each other
    $netExists = wsl -d $DistroName -u root -- docker network ls --filter "name=lotr-net" -q 2>$null
    if (-not $netExists) {
        Write-Log "Creating Docker network lotr-net..."
        wsl -d $DistroName -u root -- docker network create lotr-net | Out-Null
    }

    # Stop host Ollama if present (to avoid conflicts when bundling Ollama)
    Stop-HostOllamaIfPresent

    # Ensure no other container is publishing the AI port (3100) or the configured Ollama host port
    Remove-Containers-PublishingPort -Distro $DistroName -Port 3100
    Remove-Containers-PublishingPort -Distro $DistroName -Port $HostOllamaPort

    # (Re)start AI container — always stop any existing instance so the
    # container picks up the latest image and environment on every `run`.
    $mcpRunning = wsl -d $DistroName -u root -- docker ps --filter "name=lotr-ai" --filter "status=running" -q 2>$null
    if ($mcpRunning) {
        Write-Log "Stopping existing AI container..."
        wsl -d $DistroName -u root -- docker rm -f lotr-ai 2>$null | Out-Null
    } else {
        # Remove any stopped lotr-ai container that may be holding the name
        wsl -d $DistroName -u root -- docker rm -f lotr-ai 2>$null | Out-Null
    }
    # ROCm GPU device flags: two possible paths:
    #   1. Native Linux (or WSL2 with /dev/kfd exposed): map /dev/kfd + /dev/dri
    #   2. WSL2 ROCDXG path: bind /dev/dxg + librocdxg.so + libdxcore.so (requires
    #      librocdxg installed via install_rocdxg.sh / setup-wsl-docker.ps1)
    # If neither path is available, start without device flags (Ollama uses CPU).
    $gpuDeviceFlags = @()
    if ($GpuVariant -eq 'rocm') {
        $kfdExists = wsl -d $DistroName -u root -- bash -c 'test -e /dev/kfd && echo yes || echo no' 2>$null
        $driExists = wsl -d $DistroName -u root -- bash -c 'test -d /dev/dri && echo yes || echo no' 2>$null
        if ($kfdExists -match 'yes' -and $driExists -match 'yes') {
            $gpuDeviceFlags = @('--device', '/dev/kfd', '--device', '/dev/dri', '--group-add', 'video', '--group-add', 'render')
            Write-Log "ROCm mode: /dev/kfd and /dev/dri found -- adding native device flags."
        } else {
            # WSL2 ROCDXG path: /dev/dxg + librocdxg.so
            $dxgExists       = wsl -d $DistroName -u root -- bash -c 'test -c /dev/dxg        && echo yes || echo no' 2>$null
            $libdxcoreExists = wsl -d $DistroName -u root -- bash -c 'test -f /usr/lib/wsl/lib/libdxcore.so && echo yes || echo no' 2>$null
            $librocdxgExists = wsl -d $DistroName -u root -- bash -c 'test -f /opt/rocm/lib/librocdxg.so   && echo yes || echo no' 2>$null
            if ($dxgExists -match 'yes' -and $libdxcoreExists -match 'yes' -and $librocdxgExists -match 'yes') {
                Write-Log "ROCm mode (ROCDXG/WSL2): /dev/dxg + librocdxg.so found -- using DXG device path."
                $gpuDeviceFlags = @(
                    '--device',        '/dev/dxg',
                    '--volume',        '/usr/lib/wsl/lib/libdxcore.so:/usr/lib/libdxcore.so',
                    '--volume',        '/opt/rocm/lib/librocdxg.so:/usr/lib/librocdxg.so',
                    '--env',           'HSA_ENABLE_DXG_DETECTION=1',
                    '--cap-add',       'SYS_PTRACE',
                    '--security-opt',  'seccomp=unconfined',
                    '--ipc',           'host',
                    '--shm-size',      '8g'
                )
            } elseif ($dxgExists -match 'yes') {
                Write-Log "ROCm mode: /dev/dxg present but librocdxg.so not installed."
                Write-Log "  Run setup-wsl-docker.ps1 again to install ROCDXG, or:"
                Write-Log "    wsl -d $DistroName -u root -- bash /tmp/install_rocdxg.sh"
                Write-Log "  Starting container without GPU flags; Ollama will use CPU."
            } else {
                Write-Log "ROCm mode: /dev/kfd, /dev/dri, and /dev/dxg all absent. Starting without device flags; Ollama will use CPU."
            }
        }
    }

    Write-Log ("Starting AI container on port 3100 (GPU_VARIANT={0})..." -f $GpuVariant)

    # Prepare optional model volume mounts (mount Windows Ollama models into container)
    $modelVolumeFlags = @()
    $modelEnvFlags = @()
    if ($wslModelsPath) {
        try {
            $visible = wsl -d $DistroName -u root -- bash -lc "test -d '$wslModelsPath' && echo yes || echo no" 2>$null
            if ($visible -and $visible -match 'yes') {
                Write-Log ("Mounting host Ollama models from {0} into container (read-only)" -f $wslModelsPath)
                $modelVolumeFlags += '--volume'; $modelVolumeFlags += ("{0}:/root/.ollama/models:ro" -f $wslModelsPath)
                # Tell Ollama to read models from the mounted path (overrides start_services.sh default)
                $modelEnvFlags += '--env'; $modelEnvFlags += 'OLLAMA_MODELS=/root/.ollama/models'
            } else {
                Write-Log ("WSL path for host Ollama models not visible inside distro: {0}" -f $wslModelsPath)
            }
        } catch {
            Write-Log ("Failed to verify host Ollama models inside WSL: {0}" -f $_)
        }
    }
    wsl -d $DistroName -u root -- docker run `
        --detach `
        --name lotr-ai `
        --restart on-failure:10 `
        --network lotr-net `
        --add-host=host.docker.internal:host-gateway `
        --env "OLLAMA_URL=$ollamaUrlEnv" `
        --env "OLLAMA_ORIGINS=$ollamaOriginsEnv" `
        --env "GPU_VARIANT=$GpuVariant" `
        --publish 3100:3100 `
        --publish ${HostOllamaPort}:11434 `
        --volume "${wslRepoRoot}:/workspace" `
        @modelVolumeFlags `
        @modelEnvFlags `
        @gpuDeviceFlags `
        $McpTag
    if ($LASTEXITCODE -ne 0) {
        Write-Log ("MCP container start FAILED (exit {0}). Continuing anyway." -f $LASTEXITCODE)
    } else {
        Write-Log "AI container started."
        # Attempt an auto-warmup using the configuration embedded in the repo's
        # build/docker/ai/start_services.sh (AI_USE, AI_MODEL, AI_ARGS). This
        # avoids requiring an image rebuild just to trigger a model load.
        $startScriptWinPath = Join-Path $repoRoot 'build\docker\ai\start_services.sh'
        if (Test-Path $startScriptWinPath) {
            try {
                $startContent = Get-Content -Path $startScriptWinPath -Raw -ErrorAction Stop
                $aiModel = 'codellama:13b-code-fp16'
                $aiArgs = ''
                $aiUse = 'True'
                if ($startContent -match 'AI_MODEL\s*=\s*(.+)') {
                    $aiModel = $matches[1].Trim()
                    # If literal parameter expansion like ${AI_MODEL:-'name'}, extract default
                    if ($aiModel -match '^\$\{[^:}]+:-([^}]+)\}$') { $aiModel = $Matches[1].Trim() }
                    while ($aiModel.Length -gt 0 -and ($aiModel.StartsWith("'") -or $aiModel.StartsWith('"'))) { $aiModel = $aiModel.Substring(1) }
                    while ($aiModel.Length -gt 0 -and ($aiModel.EndsWith("'") -or $aiModel.EndsWith('"'))) { $aiModel = $aiModel.Substring(0, $aiModel.Length - 1) }
                }
                if ($startContent -match 'AI_ARGS\s*=\s*(.+)') {
                    $aiArgs = $matches[1].Trim()
                    # If literal parameter expansion like ${AI_ARGS:-'args'}, extract default
                    if ($aiArgs -match '^\$\{[^:}]+:-([^}]+)\}$') { $aiArgs = $Matches[1].Trim() }
                    while ($aiArgs.Length -gt 0 -and ($aiArgs.StartsWith("'") -or $aiArgs.StartsWith('"'))) { $aiArgs = $aiArgs.Substring(1) }
                    while ($aiArgs.Length -gt 0 -and ($aiArgs.EndsWith("'") -or $aiArgs.EndsWith('"'))) { $aiArgs = $aiArgs.Substring(0, $aiArgs.Length - 1) }
                }
                if ($startContent -match 'AI_USE\s*=\s*(.+)') {
                    $aiUse = $matches[1].Trim()
                    # If the value is a literal shell parameter-expansion like ${AI_USE:-'True'},
                    # extract the default value after ':-' (captures quoted defaults too).
                    if ($aiUse -match '^\$\{[^:}]+:-([^}]+)\}$') {
                        $aiUse = $Matches[1].Trim()
                    }
                    # Strip surrounding quotes if present
                    while ($aiUse.Length -gt 0 -and ($aiUse.StartsWith("'") -or $aiUse.StartsWith('"'))) { $aiUse = $aiUse.Substring(1) }
                    while ($aiUse.Length -gt 0 -and ($aiUse.EndsWith("'") -or $aiUse.EndsWith('"'))) { $aiUse = $aiUse.Substring(0, $aiUse.Length - 1) }
                }
                $aiUseLC = $aiUse.ToLower()
                if ($aiUseLC -eq 'true' -or $aiUseLC -eq '1' -or $aiUseLC -eq 'yes') {
                    Write-Log ("Auto-warmup enabled; model={0} args={1}" -f $aiModel, $aiArgs)
                    $ready = $false
                    for ($attempt = 0; $attempt -lt 30; $attempt++) {
                        try {
                            Invoke-WebRequest -Uri ("http://localhost:{0}/" -f $HostOllamaPort) -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop | Out-Null
                            $ready = $true
                            break
                        } catch {
                            Start-Sleep -Seconds 1
                        }
                    }
                    if (-not $ready) {
                        Write-Log ("Warmup skipped: Ollama at localhost:{0} not responding." -f $HostOllamaPort)
                    } else {
                        $payload = @{ model = $aiModel; prompt = 'startup warmup'; max_tokens = 1; stream = $false }
                        if ($aiArgs -and $aiArgs.Trim()) { $payload['args'] = $aiArgs }
                        $json = $payload | ConvertTo-Json -Depth 6
                        try {
                            # Start warmup as a non-blocking background job to avoid long waits
                            $jobScript = {
                                param($port, $jsonBody, $modelName)
                                try {
                                    Invoke-RestMethod -Uri ("http://localhost:{0}/api/generate" -f $port) -Method Post -Body $jsonBody -ContentType 'application/json' -TimeoutSec 3600 -ErrorAction Stop | Out-Null
                                } catch {
                                    # Best-effort; swallow errors in background job to avoid impacting caller.
                                }
                            }
                            Start-Job -ScriptBlock $jobScript -ArgumentList $HostOllamaPort, $json, $aiModel | Out-Null
                            Write-Log ("Warmup background job started for {0} (non-blocking)." -f $aiModel)
                        } catch {
                            Write-Log ("Failed to start warmup background job for {0}: {1}" -f $aiModel, $_)
                        }
                    }
                } else {
                    Write-Log ("Auto-warmup disabled by AI_USE={0}" -f $aiUse)
                }
            } catch {
                Write-Log ("Failed to read start_services.sh for warmup config: {0}" -f $_)
            }
        } else {
            Write-Log ("start_services.sh not found at {0}; skipping auto-warmup" -f $startScriptWinPath)
        }
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
        --add-host=host.docker.internal:host-gateway `
        --env "OLLAMA_URL=$ollamaUrlEnv" `
        --env "OLLAMA_ORIGINS=$ollamaOriginsEnv" `
        --volume  "${wslRepoRoot}:/workspace" `
        @modelVolumeFlags `
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
