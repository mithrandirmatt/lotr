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
    PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 run   -EnableAi
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
    [switch]$MountDockerSocket,
    [switch]$StartAiOnly,
    # Pass -EnableAi to start the AI/Ollama container and related host Ollama management.
    # By default AI is disabled; use this flag when you want the container-side Ollama.
    [switch]$EnableAi,

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

# Ensure Docker is running in the given WSL distro; attempt to start if not
function Ensure-DockerRunning {
    param([string]$Distro)

    if (Test-DockerResponsive -Distro $Distro) {
        Write-Log ("Docker already responsive in {0}" -f $Distro)
        return $true
    }

    Write-Log ("Docker not responsive in {0}; attempting to start via start-wsl-docker.ps1" -f $Distro)
    try {
        & powershell -ExecutionPolicy Bypass -File $startScript @startArgs
        $startExit = $LASTEXITCODE
    } catch {
        Write-Log ("Failed to invoke start-wsl-docker.ps1: {0}" -f $_)
        return $false
    }

    if ($startExit -ne 0) {
        Write-Log ("start-wsl-docker.ps1 failed (exit {0})." -f $startExit)
        return $false
    }

    if (-not (Wait-For-Docker -Distro $Distro -MaxAttempts 20 -IntervalSeconds 2)) {
        Write-Log "Docker did not become ready after start attempt"
        return $false
    }

    Write-Log ("Docker is running in {0} after start attempt" -f $Distro)
    return $true
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

# AI-related variables -- populated inside the SkipAi block below; initialised
# here so the dev-container docker run command can reference them unconditionally.
$ollamaUrlEnv     = ''
$ollamaOriginsEnv = if ($env:OLLAMA_ORIGINS) { $env:OLLAMA_ORIGINS } else { '*' }
$wslModelsPath    = $null
$modelVolumeFlags = @()
$modelEnvFlags    = @()
$gpuDeviceFlags   = @()

# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
if ($Command -eq 'build') {
    Write-Log ("Building image '{0}' ..." -f $Tag)

    $noCacheFlag = if ($IsFresh) { '--no-cache' } else { $null }

    if ($IsFresh) { Write-Log 'Fresh build: Docker layer cache disabled.' }

    # Ensure Docker is running in the WSL distro; attempt auto-start if needed
    if (-not (Ensure-DockerRunning -Distro $DistroName)) {
        Write-Log "Unable to start Docker in $DistroName; aborting build."
        if (-not $NoPause) { Write-Host "Press any key to exit..."; $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') }
        exit 3
    }

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
    $mcpDockerfileWslPath = "$wslRepoRoot/build/docker/ai/Dockerfile"
    Write-Log ("Building AI image '{0}' (GPU_VARIANT={1}) ..." -f $McpTag, $GpuVariant)

    # Ensure Docker is still running before AI build
    if (-not (Ensure-DockerRunning -Distro $DistroName)) {
        Write-Log "Unable to start Docker in $DistroName before AI build; aborting."
        if (-not $NoPause) { Write-Host "Press any key to exit..."; $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') }
        exit 3
    }

    wsl -d $DistroName -u root -- docker build `
        --tag  $McpTag `
        --build-arg "GPU_VARIANT=$GpuVariant" `
        --network host `
        $noCacheFlag `
        --file "$mcpDockerfileWslPath" `
        "$wslRepoRoot"

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

    # ------------------------------------------------------------------
    # AI / Ollama setup -- only runs when -EnableAi is specified.
    # ------------------------------------------------------------------
    if (-not $EnableAi) {
        Write-Log "AI disabled (pass -EnableAi to start the AI/Ollama container)."
    } else {

    # Resolve Ollama endpoint (env override wins; otherwise auto-detect)
    if ($env:OLLAMA_URL) {
        $ollamaUrlEnv = $env:OLLAMA_URL
    } else {
        Write-Log "Auto-detecting Ollama endpoint..."
        $ollamaContainer = wsl -d $DistroName -u root -- docker ps --filter "name=ollama" --filter "status=running" -q 2>$null
        if ($ollamaContainer) {
            $ollamaUrlEnv = 'http://ollama:11434'
            Write-Log ("Detected running 'ollama' container; using {0}" -f $ollamaUrlEnv)
        } else {
            Write-Log ("Checking host.docker.internal:{0} from distro {1}..." -f $HostOllamaPort, $DistroName)
            $curlTest = wsl -d $DistroName -u root -- bash -lc "curl -sS -m 2 http://host.docker.internal:$HostOllamaPort/ || echo __CURL_ERROR__" 2>$null
            if ($curlTest -and $curlTest -ne '__CURL_ERROR__') {
                $ollamaUrlEnv = "http://host.docker.internal:$HostOllamaPort"
                Write-Log ("host.docker.internal reachable; using {0}" -f $ollamaUrlEnv)
            } else {
                $ollamaUrlEnv = "http://host.docker.internal:$HostOllamaPort"
                Write-Log ("Could not detect Ollama; defaulting to {0}" -f $ollamaUrlEnv)
            }
        }
    }

    # Resolve host Ollama models directory (Windows path -> WSL path)
    $hostModelsWinPath = if ($HostOllamaModels -and $HostOllamaModels.Trim()) { $HostOllamaModels } else { Join-Path $env:USERPROFILE ".ollama\models" }
    Write-Log ("Host Ollama models (Windows): {0}" -f $hostModelsWinPath)
    try {
        if (Test-Path -Path $hostModelsWinPath) {
            $modelsDrive   = $hostModelsWinPath.Substring(0,1).ToLower()
            $modelsRelPath = $hostModelsWinPath.Substring(2) -replace '\\','/'
            $wslModelsPath = ("/mnt/{0}{1}" -f $modelsDrive, $modelsRelPath)
            Write-Log ("Host Ollama models (WSL): {0}" -f $wslModelsPath)
        } else {
            Write-Log ("Host Ollama models folder not found on Windows: {0}" -f $hostModelsWinPath)
        }
    } catch {
        Write-Log ("Error resolving host Ollama models path: {0}" -f $_)
    }

    # Stop host Ollama if present (to avoid port conflicts with the AI container)
    Stop-HostOllamaIfPresent

    # Ensure no other container is already publishing the AI port (3100) or Ollama port
    Remove-Containers-PublishingPort -Distro $DistroName -Port 3100
    Remove-Containers-PublishingPort -Distro $DistroName -Port $HostOllamaPort

    # (Re)start AI container
    $mcpRunning = wsl -d $DistroName -u root -- docker ps --filter "name=lotr-ai" --filter "status=running" -q 2>$null
    if ($mcpRunning) {
        Write-Log "Stopping existing AI container..."
        wsl -d $DistroName -u root -- docker rm -f lotr-ai 2>$null | Out-Null
    } else {
        wsl -d $DistroName -u root -- docker rm -f lotr-ai 2>$null | Out-Null
    }

    # ROCm GPU device flags
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
                # Find the most stable WSL_INTEROP socket (lowest PID = init/long-lived process)
                # Avoid using $WSL_INTEROP from an ephemeral bash session -- that socket dies when the wsl.exe exits
                $wslInterop = wsl -d $DistroName -u root -- bash -c 'for s in /run/WSL/*_interop; do [ -S "$s" ] && echo "$s"; done | sort -t/ -k4 -n | head -1' 2>$null
                $wslInterop = $wslInterop.Trim()
                if (-not $wslInterop) { $wslInterop = '/run/WSL/1_interop' }
                Write-Log "WSL_INTEROP=$wslInterop"
                $gpuDeviceFlags = @(
                    '--device',        '/dev/dxg',
                    # Mount host ROCm tree read-only so container uses same userland libraries
                    '--volume',        '/opt/rocm:/opt/rocm:ro',
                    # Mount WSL DXCore user-mode libs as a directory (read-only)
                    '--volume',        '/usr/lib/wsl/lib:/usr/lib/wsl/lib:ro',
                    '--volume',        '/run/WSL:/run/WSL',
                    '--env',           'HSA_ENABLE_DXG_DETECTION=1',
                    '--env',           "WSL_INTEROP=$wslInterop",
                    '--env',           'OLLAMA_LIBRARY_PATH=/usr/local/lib/ollama/rocm:/usr/local/lib/ollama',
                    '--env',           'LD_LIBRARY_PATH=/usr/local/lib/ollama/rocm:/usr/local/lib/ollama:/opt/rocm/lib:/usr/lib/wsl/lib',
                    '--env',           'LD_PRELOAD=/opt/rocm/lib/libhsa-runtime64.so.1:/opt/rocm/lib/librocdxg.so:/usr/lib/wsl/lib/libdxcore.so:/usr/lib/wsl/lib/libd3d12.so:/usr/lib/wsl/lib/libd3d12core.so',
                    '--cap-add',       'SYS_PTRACE',
                    '--cap-add',       'SYS_ADMIN',
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
                Write-Log ("Mounting host Ollama models from {0} into container (read-write)" -f $wslModelsPath)
                $modelVolumeFlags += '--volume'; $modelVolumeFlags += ("{0}:/root/.ollama/models:rw" -f $wslModelsPath)
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
    }

    } # end -not $SkipAi block

    # ---------------------------------------------------------------------------
    # Resolve WSLg display environment for GUI containers (e.g. Godot)
    # WSLg exposes an X11 socket at /tmp/.X11-unix and sets DISPLAY=:0 inside
    # the distro.  Pass these into the dev container so graphical apps work.
    # ---------------------------------------------------------------------------
    $wslDisplay = (wsl -d $DistroName -u root -- bash -lc 'echo $DISPLAY' 2>$null).Trim()
    if (-not $wslDisplay) { $wslDisplay = ':0' }
    Write-Log ("WSLg DISPLAY: {0}" -f $wslDisplay)

    # Check if the Wayland runtime dir is available (WSLg mounts it at /mnt/wslg)
    $wslgAvailable = wsl -d $DistroName -u root -- bash -c 'test -d /mnt/wslg/runtime-dir && echo yes || echo no' 2>$null
    $displayFlags = @(
        '--env',    "DISPLAY=$wslDisplay",
        '--volume', '/tmp/.X11-unix:/tmp/.X11-unix'
    )
    if ($wslgAvailable -match 'yes') {
        $displayFlags += '--env',    'WAYLAND_DISPLAY=wayland-0'
        $displayFlags += '--env',    'XDG_RUNTIME_DIR=/mnt/wslg/runtime-dir'
        $displayFlags += '--volume', '/mnt/wslg:/mnt/wslg'
        Write-Log "WSLg Wayland runtime dir found; mounting /mnt/wslg."
    } else {
        Write-Log "WSLg /mnt/wslg not found; X11-only display forwarding."
    }

    # -it: interactive + pseudo-TTY
    # --rm: remove container on exit
    # -v:   repo -> /workspace; Windows .ssh (ppk source) -> /root/.ssh:rw;
    #        named volume lotr-ssh-keys -> /root/.ssh_keys (Linux fs, chmod works, persistent);
    #        .gitconfig -> /root/.gitconfig:ro
    #        .continue  -> /host-continue:rw (for sync_continue make target)
    # -w:   set working directory inside container
    # --network lotr-net: shared network so dev container can reach mcp at http://lotr-mcp:3100/sse
    if (-not $StartAiOnly) {
        wsl -d $DistroName -u root -- docker run `
            --rm `
            --interactive `
            --tty `
            --network lotr-net `
            --add-host=host.docker.internal:host-gateway `
            --env "OLLAMA_URL=$ollamaUrlEnv" `
            --env "OLLAMA_ORIGINS=$ollamaOriginsEnv" `
            @displayFlags `
            --volume  "${wslRepoRoot}:/workspace" `
            @modelVolumeFlags `
            --volume  "${wslSshPath}:/root/.ssh:rw" `
            @(
                if ($MountDockerSocket) { '--volume'; '/var/run/docker.sock:/var/run/docker.sock' }
            ) `
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
    else {
        Write-Log "StartAiOnly set; skipping interactive dev container shell."
    }
}

Write-Log "docker.ps1 done."
if ($Command -eq 'build' -and -not $NoPause) { Write-Host "Press any key to exit..."; $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') }
