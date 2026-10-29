<#
install-lmstudio-model.ps1

Installs a locally-exported GGUF (produced by build/agent/build.lora_export_gguf.py)
into LM Studio's local model library, so the same LoRA build artifact that
agent.mk's ollama-install-lora target loads into Ollama is also available in
LM Studio, without requiring a second manual import step.

This is a HOST script, same category as build/docker/docker.ps1 and
setup-llama-server.ps1 -- it must run where the Windows host filesystem is
directly reachable (native PowerShell, or WSL/Git-Bash with powershell.exe
interop). It will NOT do anything useful run natively inside the dev
container, since LM Studio itself only ever runs on the Windows host.

Detection is folder-existence based (no LM Studio process/API dependency):
  1. $env:LMSTUDIO_MODELS_DIR, if set, is used as-is.
  2. Otherwise the current LM Studio models dir ($env:USERPROFILE\.lmstudio\models)
     is checked.
  3. Otherwise the legacy pre-1.0 LM Studio models dir
     ($env:USERPROFILE\.cache\lm-studio\models) is checked.
If none of these exist, LM Studio is treated as "not installed" and this
script exits 0 without error, so it is safe to call unconditionally from a
build pipeline.

Usage:
    PowerShell -ExecutionPolicy Bypass -File build/docker/install-lmstudio-model.ps1 -GgufPath C:\path\to\model.gguf -ModelName my-model-name
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$GgufPath,

    [Parameter(Mandatory = $true)]
    [string]$ModelName,

    [string]$Publisher = "lotr"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $GgufPath)) {
    Write-Error "GGUF not found at $GgufPath"
    exit 1
}

function Get-LmStudioModelsDir {
    if ($env:LMSTUDIO_MODELS_DIR -and (Test-Path -LiteralPath $env:LMSTUDIO_MODELS_DIR)) {
        return $env:LMSTUDIO_MODELS_DIR
    }
    $candidates = @(
        (Join-Path $env:USERPROFILE ".lmstudio\models"),
        (Join-Path $env:USERPROFILE ".cache\lm-studio\models")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    return $null
}

$modelsDir = Get-LmStudioModelsDir
if (-not $modelsDir) {
    Write-Host "LM Studio not detected (no models directory found); skipping LM Studio install."
    Write-Host "Set LMSTUDIO_MODELS_DIR to override the detected path if LM Studio is installed elsewhere."
    exit 0
}

Write-Host "LM Studio models directory detected: $modelsDir"

$destDir = Join-Path $modelsDir "$Publisher\$ModelName"
New-Item -ItemType Directory -Path $destDir -Force | Out-Null

$destFile = Join-Path $destDir ([System.IO.Path]::GetFileName($GgufPath))
$sourceInfo = Get-Item -LiteralPath $GgufPath

if ((Test-Path -LiteralPath $destFile) -and ((Get-Item -LiteralPath $destFile).Length -eq $sourceInfo.Length)) {
    Write-Host "LM Studio model already up to date at $destFile; skipping copy."
} else {
    Write-Host "Copying $GgufPath -> $destFile"
    Copy-Item -LiteralPath $GgufPath -Destination $destFile -Force
}

$lmsCmd = Get-Command lms -ErrorAction SilentlyContinue
if ($lmsCmd) {
    Write-Host "lms CLI detected; registering model with LM Studio's index..."
    try {
        & lms import $destFile 2>&1 | ForEach-Object { Write-Host "  $_" }
    } catch {
        Write-Host "lms import failed (non-fatal): $_"
    }
} else {
    Write-Host "lms CLI not found on PATH; model file was copied but may need a manual refresh in LM Studio's My Models tab."
}

Write-Host "LM Studio install step complete: $destFile"
