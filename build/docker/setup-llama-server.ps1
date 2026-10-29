<#
setup-llama-server.ps1

Builds and runs llama.cpp's `llama-server` DIRECTLY ON THE WINDOWS HOST
(never inside WSL2/Docker) so it can bind the AMD RX 7900 XTX the same way
Ollama already does, and serves our own locally-trained GGUF model behind an
OpenAI-compatible /v1/chat/completions endpoint that properly honors
reasoning/thinking controls (unlike Ollama 0.32.1's OpenAI-compat shim).

This is a HOST script, same category as build/docker/docker.ps1 -- do not
run it via `docker.ps1 exec` / inside the dev container. It has no
dependency on WSL or Docker at all.

Commands:
  prereqs  -- check (and optionally install) build prerequisites
  build    -- clone/update llama.cpp and compile llama-server
  run      -- start llama-server in the background (native Windows process)
  stop     -- stop the background llama-server process
  restart  -- stop then run
  status   -- report whether llama-server is running and healthy

Usage:
    PowerShell -ExecutionPolicy Bypass -File build/docker/setup-llama-server.ps1 prereqs
    PowerShell -ExecutionPolicy Bypass -File build/docker/setup-llama-server.ps1 prereqs -InstallPrereqs
    PowerShell -ExecutionPolicy Bypass -File build/docker/setup-llama-server.ps1 build
    PowerShell -ExecutionPolicy Bypass -File build/docker/setup-llama-server.ps1 build -Fresh
    PowerShell -ExecutionPolicy Bypass -File build/docker/setup-llama-server.ps1 run
    PowerShell -ExecutionPolicy Bypass -File build/docker/setup-llama-server.ps1 run -ModelPath C:\path\to\model.gguf -Port 8090
    PowerShell -ExecutionPolicy Bypass -File build/docker/setup-llama-server.ps1 status
    PowerShell -ExecutionPolicy Bypass -File build/docker/setup-llama-server.ps1 stop
    PowerShell -ExecutionPolicy Bypass -File build/docker/setup-llama-server.ps1 restart -GpuBackend hip

Notes:
- Requires ROCm HIP SDK for Windows already installed for -GpuBackend hip
  (this repo's host already has it at $env:HIP_PATH -- confirmed 7.1).
- Compiling ANY backend (hip/vulkan/cpu) with ROCm's bundled clang still
  needs Visual Studio Build Tools' MSVC STL headers (ROCm's clang does not
  bundle its own C++ standard library on Windows) -- run `prereqs` first.
#>

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('prereqs', 'build', 'run', 'stop', 'restart', 'status')]
    [string]$Command,

    [string]$RepoRoot     = '',
    [string]$LlamaCppDir  = '',
    [string]$ModelPath    = '',
    [string]$BindHost     = '127.0.0.1',
    [int]$Port            = 8090,
    # 131072 matches the rx7900xtx-agentic profile's declared runtime.num_ctx
    # and the *-yarn131k.gguf default model's grafted YaRN context (see
    # $ModelPath default below for the full explanation of why a plain
    # 262144/32768 ContextSize on the ORIGINAL gguf doesn't work).
    [int]$ContextSize     = 131072,
    [int]$NGpuLayers      = 999,
    [ValidateSet('', 'hip', 'vulkan', 'cpu')]
    [string]$GpuBackend   = '',
    [string]$AmdGpuTarget = 'gfx1100',
    # This host's ROCm/ggml-hip enumeration reports TWO ROCm devices for the
    # single physical RX 7900 XTX -- "ROCm0: AMD Radeon(TM) Graphics" (a
    # phantom/generic entry, not a real usable compute device; `hipInfo.exe`
    # only ever sees one real device) and "ROCm1: AMD Radeon RX 7900 XTX"
    # (the real gfx1100 card). Dispatching to device 1 as-is crashes with
    # "ROCm error: device kernel image is invalid". Masking to just the real
    # device via HIP_VISIBLE_DEVICES fixes it (confirmed: --list-devices then
    # shows exactly one device). Set to '' to disable masking.
    [string]$HipVisibleDevices = '1',
    [string]$ApiKey       = '',
    [switch]$InstallPrereqs,
    [switch]$Fresh,
    [string]$PidFile      = '',
    [string]$LogFile      = ''
)

Set-StrictMode -Version Latest
# NOTE: intentionally NOT 'Stop' -- this script shells out to many native
# tools (clang, cmake, git, winget) that write harmless warnings to stderr;
# with 'Stop', PowerShell turns that stderr output into a terminating
# exception. Exit codes are checked explicitly ($LASTEXITCODE) instead.
$ErrorActionPreference = 'Continue'

# NOTE: $PSScriptRoot is not reliably populated while evaluating param()
# default values in a script that has a Mandatory parameter (a known
# Windows PowerShell quirk) -- so path defaults are resolved here in the
# script body instead of inline in the param block.
if (-not $RepoRoot)    { $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path }
if (-not $LlamaCppDir) { $LlamaCppDir = Join-Path $RepoRoot 'build\docker\cache\llama.cpp' }
# lotr-lora-rx7900xtx-agentic-q4_k_m.gguf's native trained context is only
# 32768 (confirmed via its GGUF metadata: qwen2.context_length = 32768) --
# llama-server unconditionally caps serving to that value
# (tools/server/server-context.cpp: "the slot context exceeds the training
# context of the model - capping"), and passing --rope-scaling/--rope-scale/
# --yarn-orig-ctx CLI flags does NOT override this cap (confirmed via a live
# test: still capped to 32768 even with those flags set). The *-yarn131k.gguf
# variant (produced by build/docker/graft-yarn-context.py) has the same
# weights but with qwen2.context_length raised to 131072 plus proper YaRN
# rope-scaling metadata (type=yarn, factor=4, original_context_length=32768)
# grafted in -- confirmed via a live /props check to actually serve at
# n_ctx=131072 with no capping. Use that by default.
if (-not $ModelPath)   { $ModelPath = Join-Path $RepoRoot 'do\agent\models\lotr-lora-rx7900xtx-agentic-q4_k_m-yarn131k.gguf' }
if (-not $PidFile)     { $PidFile = Join-Path $RepoRoot 'build\docker\cache\llama-server.pid' }
if (-not $LogFile)     { $LogFile = Join-Path $RepoRoot 'build\docker\logs\llama-server.log' }

# Every invocation of this script is typically a brand-new `powershell.exe`
# process (e.g. launched from a long-lived terminal session, or via the
# `agent_setup` make target). That parent session's own $env:PATH can
# predate a prior winget install (cmake/ninja get added to the registry's
# Machine/User PATH, but a process only reads that once, at process start,
# from ITS OWN parent's environment block -- not from the live registry).
# Always rebuild $env:PATH from the registry here so newly-installed tools
# are visible immediately without requiring a brand new terminal/window.
function Update-SessionPath {
    $machine = [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [System.Environment]::GetEnvironmentVariable('Path', 'User')
    $env:PATH = @($machine, $user) -join ';'
}
Update-SessionPath

# $LlamaCppDir is the shared llama.cpp checkout also used by the CONTAINER
# side (build.lora_export_gguf.py's quantize-tool build, via LLAMA_CPP_DIR
# in agent.mk) -- its `build/` subdirectory already contains a Linux
# CMakeCache.txt from that container build. Use a separate, Windows-only
# build directory here so the two builds (different OS/toolchain/generator)
# never clobber each other's CMake cache.
$BuildDir  = Join-Path $LlamaCppDir 'build-windows-host'
$ServerExe = Join-Path $BuildDir 'bin\llama-server.exe'

function Write-Log {
    param([string]$Message)
    Write-Host "[llama-server] $Message"
}

function Resolve-Backend {
    if ($GpuBackend) { return $GpuBackend }
    if ($env:HIP_PATH -and (Test-Path $env:HIP_PATH)) { return 'hip' }
    if (Get-Command vulkaninfo -ErrorAction SilentlyContinue) { return 'vulkan' }
    return 'cpu'
}

function Test-MsvcStlAvailable {
    # ROCm's clang targets x86_64-pc-windows-msvc and needs MSVC's own STL
    # headers (from a VS Build Tools/VS install) -- it does not bundle libc++
    # for Windows. Verified empirically: without VS Build Tools, `#include
    # <vector>` fails with "file not found" even though clang++ itself runs.
    $hipBin = Join-Path $env:HIP_PATH 'bin'
    $clangxx = Join-Path $hipBin 'clang++.exe'
    if (-not (Test-Path $clangxx)) { return $false }

    $tmp = Join-Path $env:TEMP "lotr-stl-check-$PID.cpp"
    $out = Join-Path $env:TEMP "lotr-stl-check-$PID.exe"
    Set-Content -Path $tmp -Encoding ascii -Value "#include <vector>`nint main(){ std::vector<int> v; v.push_back(1); return 0; }"
    try {
        & $clangxx $tmp -o $out *> $null
        return ($LASTEXITCODE -eq 0)
    } finally {
        Remove-Item -Force -ErrorAction SilentlyContinue $tmp, $out
    }
}

function Test-Prereqs {
    param([switch]$SkipInstall)

    $backend = Resolve-Backend
    Write-Log "Resolved GPU backend: $backend"

    $results = [ordered]@{
        'git'    = [bool](Get-Command git -ErrorAction SilentlyContinue)
        'cmake'  = [bool](Get-Command cmake -ErrorAction SilentlyContinue)
        'ninja'  = [bool](Get-Command ninja -ErrorAction SilentlyContinue)
    }
    if ($backend -eq 'hip') {
        $results['ROCm HIP SDK ($env:HIP_PATH)'] = [bool]($env:HIP_PATH -and (Test-Path $env:HIP_PATH))
    }
    $results['MSVC STL headers (VS Build Tools C++ workload)'] = Test-MsvcStlAvailable

    $allOk = $true
    foreach ($key in $results.Keys) {
        $status = if ($results[$key]) { 'OK' } else { 'MISSING'; $allOk = $false }
        Write-Log ("  [{0,-7}] {1}" -f $status, $key)
    }

    if (-not $allOk -and $InstallPrereqs -and -not $SkipInstall) {
        Install-Prereqs -Results $results
        Update-SessionPath
        Write-Log "Re-checking prerequisites after install..."
        return Test-Prereqs -SkipInstall
    }

    if (-not $allOk) {
        Write-Log "Missing prerequisites. Re-run with -InstallPrereqs to install via winget, e.g.:"
        Write-Log "  PowerShell -ExecutionPolicy Bypass -File build/docker/setup-llama-server.ps1 prereqs -InstallPrereqs"
        Write-Log "NOTE: installing VS Build Tools' C++ workload is a multi-GB download; winget will prompt/log progress."
        if ($SkipInstall) {
            Write-Log "Still missing after install + PATH refresh -- open a NEW PowerShell window and re-run 'prereqs' (some winget installs only take effect after a fresh session)."
        }
        if (-not $results['MSVC STL headers (VS Build Tools C++ workload)']) {
            Write-Log "MSVC STL headers are missing -- download/install the 'Desktop development with C++' workload from:"
            Write-Log "  Microsoft C++ Build Tools: https://aka.ms/vs/17/release/vs_buildtools.exe"
        }
    }
    return $allOk
}

function Install-Prereqs {
    param($Results)

    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Log "winget not found -- install the 'Desktop development with C++' workload manually from:"
        Write-Log "  Microsoft C++ Build Tools: https://aka.ms/vs/17/release/vs_buildtools.exe"
        throw "winget not found on this host; install prerequisites manually (git, cmake, ninja, VS Build Tools C++ workload)."
    }

    if (-not $Results['cmake']) {
        Write-Log "Installing CMake via winget..."
        winget install --id Kitware.CMake -e --silent --accept-package-agreements --accept-source-agreements
    }
    if (-not $Results['ninja']) {
        Write-Log "Installing Ninja via winget..."
        winget install --id Ninja-build.Ninja -e --silent --accept-package-agreements --accept-source-agreements
    }
    if (-not $Results['MSVC STL headers (VS Build Tools C++ workload)']) {
        Write-Log "Installing Visual Studio Build Tools (C++ workload) via winget -- this is a multi-GB download..."
        winget install --id Microsoft.VisualStudio.2022.BuildTools -e --accept-package-agreements --accept-source-agreements `
            --override "--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
    }

    Write-Log "Prerequisite install pass complete."
}

function Find-CompatibleVcVarsAll {
    # ROCm 7.1's HIP clang headers (__clang_hip_cmath.h) collide with the
    # newest MSVC STL's _CLANG_BUILTIN2 math macros ("cannot overload
    # __host__ __device__ function" for isgreater/isless/etc). A plain VS
    # 2022 Build Tools install (non-preview channel) ships an older MSVC
    # toolset that predates that STL change and is known-compatible.
    # Prefer that install's vcvarsall.bat over any newer/preview one.
    $candidates = @(
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat",
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat",
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvarsall.bat",
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvarsall.bat"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }
    return $null
}

function Set-VcToolsEnvironment {
    $vcvarsall = Find-CompatibleVcVarsAll
    if (-not $vcvarsall) {
        Write-Log "No VS 2022 Build Tools install found for a known-compatible MSVC toolset; continuing with whatever MSVC install is auto-detected (may hit the HIP/STL header conflict documented in Invoke-Build)."
        return
    }
    Write-Log "Pinning MSVC toolset environment via $vcvarsall"
    $lines = cmd /c "`"$vcvarsall`" x64 >nul && set"
    foreach ($line in $lines) {
        if ($line -match '^([A-Za-z_][A-Za-z0-9_\(\)]*)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
        }
    }
}

function Invoke-Build {
    $backend = Resolve-Backend
    if (-not (Test-Prereqs)) {
        if (-not (Test-MsvcStlAvailable)) {
            Write-Log "Missing MSVC STL headers -- download/install the 'Desktop development with C++' workload from:"
            Write-Log "  Microsoft C++ Build Tools: https://aka.ms/vs/17/release/vs_buildtools.exe"
        }
        throw "Prerequisites missing; run 'prereqs -InstallPrereqs' first (or install manually, see messages above)."
    }

    Set-VcToolsEnvironment

    if (-not (Test-Path $LlamaCppDir)) {
        Write-Log "Cloning llama.cpp into $LlamaCppDir ..."
        New-Item -ItemType Directory -Force -Path (Split-Path $LlamaCppDir) | Out-Null
        git clone --depth 1 https://github.com/ggml-org/llama.cpp.git $LlamaCppDir
    } elseif ($Fresh) {
        Write-Log "Updating existing llama.cpp checkout..."
        git -C $LlamaCppDir fetch --depth 1 origin
        git -C $LlamaCppDir reset --hard origin/HEAD
    } else {
        Write-Log "Reusing existing llama.cpp checkout at $LlamaCppDir (pass -Fresh to update)."
    }

    if ($Fresh -and (Test-Path $BuildDir)) {
        Write-Log "Removing existing build dir for a clean reconfigure..."
        Remove-Item -Recurse -Force $BuildDir
    }

    $cmakeArgs = @('-S', $LlamaCppDir, '-B', $BuildDir, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release')

    switch ($backend) {
        'hip' {
            # Use forward slashes for all paths passed to cmake -- CMake
            # fully supports them on Windows, and backslash-terminated
            # paths (e.g. "...\ROCm\7.1\") get mis-escaped by CMake's
            # generated CMakeRCCompiler.cmake ("Invalid character escape
            # '\P'"), which is exactly what happened when passed as-is.
            $hipBin = (Join-Path $env:HIP_PATH 'bin') -replace '\\', '/'
            $hipRoot = $env:HIP_PATH.TrimEnd('\') -replace '\\', '/'
            $cmakeArgs += @(
                "-DCMAKE_C_COMPILER=$hipBin/clang.exe",
                "-DCMAKE_CXX_COMPILER=$hipBin/clang++.exe",
                "-DCMAKE_RC_COMPILER=$hipBin/llvm-rc.exe",
                '-DGGML_HIP=ON',
                "-DAMDGPU_TARGETS=$AmdGpuTarget",
                "-DCMAKE_PREFIX_PATH=$hipRoot"
            )
            Write-Log "Configuring with HIP backend (AMDGPU_TARGETS=$AmdGpuTarget) using ROCm clang at $hipBin"
        }
        'vulkan' {
            $cmakeArgs += '-DGGML_VULKAN=ON'
            Write-Log "Configuring with Vulkan backend"
        }
        'cpu' {
            Write-Log "Configuring CPU-only backend (no GPU acceleration)"
        }
    }

    Write-Log "Running: cmake $($cmakeArgs -join ' ')"
    & cmake @cmakeArgs
    if ($LASTEXITCODE -ne 0) { throw "cmake configure failed (exit $LASTEXITCODE)" }

    Write-Log "Building llama-server (this can take a while on first build)..."
    & cmake --build $BuildDir --config Release --target llama-server -j
    if ($LASTEXITCODE -ne 0) { throw "cmake build failed (exit $LASTEXITCODE)" }

    if (-not (Test-Path $ServerExe)) {
        throw "Build finished but $ServerExe was not produced."
    }
    Write-Log "Build complete: $ServerExe"
}

function Get-RunningPid {
    if (-not (Test-Path $PidFile)) { return $null }
    $procId = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if (-not $procId) { return $null }
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($proc -and $proc.ProcessName -eq 'llama-server') { return $procId }
    return $null
}

function Test-Health {
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Uri "http://$($BindHost):$Port/health"
        return $resp.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Start-LlamaServer {
    if (Get-RunningPid) {
        Write-Log "llama-server already running (PID $(Get-RunningPid)); use 'restart' to relaunch."
        return
    }
    if (-not (Test-Path $ServerExe)) {
        throw "llama-server.exe not found at $ServerExe; run 'build' first."
    }
    if (-not (Test-Path $ModelPath)) {
        throw "Model GGUF not found at $ModelPath; pass -ModelPath to point at a real GGUF file."
    }

    New-Item -ItemType Directory -Force -Path (Split-Path $LogFile) | Out-Null
    New-Item -ItemType Directory -Force -Path (Split-Path $PidFile) | Out-Null

    $argsList = @(
        '--model', $ModelPath,
        '--host', $BindHost,
        '--port', $Port,
        '--ctx-size', $ContextSize,
        '--n-gpu-layers', $NGpuLayers,
        '--reasoning', 'off',
        '--jinja'
    )
    if ($ApiKey) { $argsList += @('--api-key', $ApiKey) }

    Write-Log "Starting llama-server on http://$($BindHost):$Port (model: $ModelPath)"

    $oldPath = $env:PATH
    $oldHipVisibleDevices = $env:HIP_VISIBLE_DEVICES
    try {
        if ($env:HIP_PATH) { $env:PATH = "$(Join-Path $env:HIP_PATH 'bin');$env:PATH" }
        if ($HipVisibleDevices) {
            Write-Log "Masking ROCm devices to HIP_VISIBLE_DEVICES=$HipVisibleDevices (works around the phantom-device enumeration bug -- see param docs)."
            $env:HIP_VISIBLE_DEVICES = $HipVisibleDevices
        }
        $proc = Start-Process -FilePath $ServerExe -ArgumentList $argsList `
            -WorkingDirectory (Split-Path $ServerExe) `
            -RedirectStandardOutput $LogFile -RedirectStandardError "$LogFile.err" `
            -WindowStyle Hidden -PassThru
    } finally {
        $env:PATH = $oldPath
        $env:HIP_VISIBLE_DEVICES = $oldHipVisibleDevices
    }

    $proc.Id | Set-Content -Path $PidFile
    Write-Log "Started PID $($proc.Id). Waiting for health check..."

    $healthy = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Health) { $healthy = $true; break }
        if ($proc.HasExited) { break }
    }

    if ($healthy) {
        Write-Log "llama-server is healthy at http://$($BindHost):$Port (log: $LogFile)"
    } else {
        Write-Log "llama-server did not report healthy within 30s -- check $LogFile / $LogFile.err"
    }
}

function Stop-LlamaServer {
    $procId = Get-RunningPid
    if (-not $procId) {
        Write-Log "llama-server is not running (no valid PID file)."
        Remove-Item -Force -ErrorAction SilentlyContinue $PidFile
        return
    }
    Write-Log "Stopping llama-server (PID $procId)..."
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    Remove-Item -Force -ErrorAction SilentlyContinue $PidFile
    Write-Log "Stopped."
}

function Get-Status {
    $procId = Get-RunningPid
    if (-not $procId) {
        Write-Log "Status: NOT RUNNING"
        return
    }
    $healthy = Test-Health
    Write-Log "Status: RUNNING (PID $procId), healthy=$healthy, endpoint=http://$($BindHost):$Port/v1/chat/completions"
}

switch ($Command) {
    'prereqs' { Test-Prereqs | Out-Null }
    'build'   { Invoke-Build }
    'run'     { Start-LlamaServer }
    'stop'    { Stop-LlamaServer }
    'restart' { Stop-LlamaServer; Start-LlamaServer }
    'status'  { Get-Status }
}
