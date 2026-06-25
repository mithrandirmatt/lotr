<#
llm-checker.ps1

Repeatable LLM path checker for this repository.

What it verifies:
1) Endpoint reachability for proxy/headroom/ollama.
2) A controlled OpenAI-compatible chat request through the proxy.
3) Effective context override by parsing build/docker/logs/ollama_proxy.log.
4) Optional direct endpoint probes to help isolate 5xx failures.

Examples:
  PowerShell -ExecutionPolicy Bypass -File build/docker/llm-checker.ps1
  PowerShell -ExecutionPolicy Bypass -File build/docker/llm-checker.ps1 -ExpectedNumCtx 262144 -Strict
  PowerShell -ExecutionPolicy Bypass -File build/docker/llm-checker.ps1 -Model "lotr-agentic-rx7900xtx-agentic-qwen35-262k:latest"
#>

param(
    [string]$Model = "lotr-agentic-rx7900xtx-agentic-qwen35-262k:latest",
    [string]$ProxyBaseUrl = "http://localhost:11436",
    [string]$HeadroomBaseUrl = "http://localhost:8787",
    [string]$OllamaBaseUrl = "http://localhost:11434",
    [int]$ExpectedNumCtx = 262144,
    [int]$CallerNumCtx = 4096,
    [int]$MaxTokens = 16,
    [int]$TimeoutSec = 30,
    [int]$RetryTimeoutSec = 120,
    [int]$HealthTimeoutSec = 5,
    [string]$Prompt = "Reply with exactly OK.",
    [string]$ProxyLogPath = "",
    [switch]$SkipRequest,
    [switch]$SkipDirectProbes,
    [switch]$Strict,
    [switch]$Quiet
)

Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($ProxyLogPath)) {
    $ProxyLogPath = Join-Path $PSScriptRoot "logs\ollama_proxy.log"
}

function Write-Info {
    param([string]$Message)
    if (-not $Quiet) { Write-Host "[INFO] $Message" }
}

function Write-WarnMsg {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-ErrMsg {
    param([string]$Message)
    Write-Host "[ERR ] $Message" -ForegroundColor Red
}

function Invoke-HttpGet {
    param(
        [string]$Url,
        [int]$TimeoutSecLocal = 5
    )

    try {
        $resp = Invoke-WebRequest -Uri $Url -Method GET -TimeoutSec $TimeoutSecLocal -UseBasicParsing -ErrorAction Stop
        return [pscustomobject]@{
            Url        = $Url
            Success    = $true
            StatusCode = [int]$resp.StatusCode
            Body       = ($resp.Content | Out-String).Trim()
            Error      = ""
        }
    } catch {
        $statusCode = 0
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            $statusCode = [int]$_.Exception.Response.StatusCode
        }
        return [pscustomobject]@{
            Url        = $Url
            Success    = $false
            StatusCode = $statusCode
            Body       = ""
            Error      = $_.Exception.Message
        }
    }
}

function Invoke-JsonPost {
    param(
        [string]$Url,
        [hashtable]$Payload,
        [int]$TimeoutSecLocal = 60
    )

    $json = $Payload | ConvertTo-Json -Depth 10
    try {
        $resp = Invoke-WebRequest -Uri $Url -Method POST -ContentType "application/json" -Body $json -TimeoutSec $TimeoutSecLocal -UseBasicParsing -ErrorAction Stop
        return [pscustomobject]@{
            Url        = $Url
            Success    = $true
            StatusCode = [int]$resp.StatusCode
            Body       = ($resp.Content | Out-String).Trim()
            Error      = ""
            IsTimeout  = $false
        }
    } catch {
        $statusCode = 0
        $body = ""
        $isTimeout = $false
        if ($_.Exception.Message -match 'timed out|operation has timed out') {
            $isTimeout = $true
        }
        if ($_.Exception.Response) {
            try {
                $statusCode = [int]$_.Exception.Response.StatusCode
                $stream = $_.Exception.Response.GetResponseStream()
                if ($stream) {
                    $reader = New-Object System.IO.StreamReader($stream)
                    $body = $reader.ReadToEnd()
                    $reader.Close()
                }
            } catch {
                # Best effort only.
            }
        }
        return [pscustomobject]@{
            Url        = $Url
            Success    = $false
            StatusCode = $statusCode
            Body       = ($body | Out-String).Trim()
            Error      = $_.Exception.Message
            IsTimeout  = $isTimeout
        }
    }
}

function Get-LatestProxyReqFromLog {
    param(
        [string]$Path,
        [string]$ModelName
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    $escapedModel = [regex]::Escape($ModelName)
    $lines = Get-Content -LiteralPath $Path -Tail 500
    if (-not $lines) { return $null }

    for ($i = $lines.Count - 1; $i -ge 0; $i--) {
        $line = [string]$lines[$i]
        if ($line -match "REQ\s+POST\s+/v1/chat/completions\s+model=$escapedModel") {
            $effective = $null
            $caller = $null
            if ($line -match "effective_num_ctx=(\d+)") { $effective = [int]$matches[1] }
            if ($line -match "caller_num_ctx=(\d+)") { $caller = [int]$matches[1] }

            return [pscustomobject]@{
                Line            = $line
                EffectiveNumCtx = $effective
                CallerNumCtx    = $caller
            }
        }
    }

    return $null
}

Write-Info "LLM checker started"
Write-Info "Model: $Model"
Write-Info "Proxy: $ProxyBaseUrl"
Write-Info "Headroom: $HeadroomBaseUrl"
Write-Info "Ollama: $OllamaBaseUrl"
Write-Info "Expected num_ctx: $ExpectedNumCtx"
Write-Info "Proxy log: $ProxyLogPath"
Write-Info "Request timeout: ${TimeoutSec}s; retry timeout: ${RetryTimeoutSec}s; health timeout: ${HealthTimeoutSec}s"

$healthChecks = @()
Write-Info "Health check: $ProxyBaseUrl/"
$healthChecks += Invoke-HttpGet -Url "$ProxyBaseUrl/" -TimeoutSecLocal $HealthTimeoutSec
Write-Info "Health check: $HeadroomBaseUrl/"
$healthChecks += Invoke-HttpGet -Url "$HeadroomBaseUrl/" -TimeoutSecLocal $HealthTimeoutSec
Write-Info "Health check: $OllamaBaseUrl/"
$healthChecks += Invoke-HttpGet -Url "$OllamaBaseUrl/" -TimeoutSecLocal $HealthTimeoutSec

$proxyRequestResult = $null
$directProbeResults = @()
$logResult = $null

if (-not $SkipRequest) {
    $payload = @{
        model      = $Model
        messages   = @(@{ role = "user"; content = $Prompt })
        max_tokens = $MaxTokens
        stream     = $false
        options    = @{ num_ctx = $CallerNumCtx }
    }

    Write-Info "Proxy request: $ProxyBaseUrl/v1/chat/completions"
    $proxyRequestResult = Invoke-JsonPost -Url "$ProxyBaseUrl/v1/chat/completions" -Payload $payload -TimeoutSecLocal $TimeoutSec
    if ((-not $proxyRequestResult.Success) -and $proxyRequestResult.IsTimeout -and ($RetryTimeoutSec -gt $TimeoutSec)) {
        Write-WarnMsg "Proxy request timed out at ${TimeoutSec}s; retrying once with ${RetryTimeoutSec}s."
        $proxyRequestResult = Invoke-JsonPost -Url "$ProxyBaseUrl/v1/chat/completions" -Payload $payload -TimeoutSecLocal $RetryTimeoutSec
    }

    if (-not $SkipDirectProbes) {
        Write-Info "Direct probe: $HeadroomBaseUrl/v1/chat/completions"
        $headroomProbe = Invoke-JsonPost -Url "$HeadroomBaseUrl/v1/chat/completions" -Payload $payload -TimeoutSecLocal $TimeoutSec
        if ((-not $headroomProbe.Success) -and $headroomProbe.IsTimeout -and ($RetryTimeoutSec -gt $TimeoutSec)) {
            Write-WarnMsg "Headroom probe timed out at ${TimeoutSec}s; retrying once with ${RetryTimeoutSec}s."
            $headroomProbe = Invoke-JsonPost -Url "$HeadroomBaseUrl/v1/chat/completions" -Payload $payload -TimeoutSecLocal $RetryTimeoutSec
        }
        $directProbeResults += $headroomProbe
        Write-Info "Direct probe: $OllamaBaseUrl/v1/chat/completions"
        $ollamaProbe = Invoke-JsonPost -Url "$OllamaBaseUrl/v1/chat/completions" -Payload $payload -TimeoutSecLocal $TimeoutSec
        if ((-not $ollamaProbe.Success) -and $ollamaProbe.IsTimeout -and ($RetryTimeoutSec -gt $TimeoutSec)) {
            Write-WarnMsg "Ollama probe timed out at ${TimeoutSec}s; retrying once with ${RetryTimeoutSec}s."
            $ollamaProbe = Invoke-JsonPost -Url "$OllamaBaseUrl/v1/chat/completions" -Payload $payload -TimeoutSecLocal $RetryTimeoutSec
        }
        $directProbeResults += $ollamaProbe
    }

    Write-Info "Parsing latest proxy log entry for model context verification"
    $logResult = Get-LatestProxyReqFromLog -Path $ProxyLogPath -ModelName $Model
}

Write-Host ""
Write-Host "=== Endpoint Health ==="
$healthChecks | ForEach-Object {
    $state = if ($_.Success) { "UP" } else { "DOWN" }
    $status = if ($_.StatusCode -gt 0) { $_.StatusCode } else { "n/a" }
    Write-Host ("{0,-4}  {1,-30}  status={2}" -f $state, $_.Url, $status)
    if (-not $_.Success -and $_.Error) {
        Write-Host ("      error: {0}" -f $_.Error)
    }
}

if (-not $SkipRequest) {
    Write-Host ""
    Write-Host "=== Proxy Request ==="
    $proxyState = if ($proxyRequestResult.Success) { "OK" } else { "FAIL" }
    $proxyStatus = if ($proxyRequestResult.StatusCode -gt 0) { $proxyRequestResult.StatusCode } else { "n/a" }
    Write-Host ("{0}  POST {1}  status={2}" -f $proxyState, $proxyRequestResult.Url, $proxyStatus)
    if (-not $proxyRequestResult.Success) {
        if ($proxyRequestResult.Error) { Write-Host ("error: {0}" -f $proxyRequestResult.Error) }
        if ($proxyRequestResult.Body) { Write-Host ("body : {0}" -f $proxyRequestResult.Body) }
    }

    if ($directProbeResults.Count -gt 0) {
        Write-Host ""
        Write-Host "=== Direct Probes (Isolation) ==="
        $directProbeResults | ForEach-Object {
            $state = if ($_.Success) { "OK" } else { "FAIL" }
            $status = if ($_.StatusCode -gt 0) { $_.StatusCode } else { "n/a" }
            Write-Host ("{0}  {1}  status={2}" -f $state, $_.Url, $status)
            if (-not $_.Success -and $_.Error) {
                Write-Host ("      error: {0}" -f $_.Error)
            }
        }
    }

    Write-Host ""
    Write-Host "=== Context Verification (From Proxy Log) ==="
    if ($null -eq $logResult) {
        Write-WarnMsg "No matching proxy REQ log entry found for model."
    } else {
        Write-Host $logResult.Line
        if ($null -eq $logResult.EffectiveNumCtx) {
            Write-WarnMsg "Could not parse effective_num_ctx from log line."
        } else {
            $ctxPass = $logResult.EffectiveNumCtx -ge $ExpectedNumCtx
            $ctxState = if ($ctxPass) { "PASS" } else { "FAIL" }
            Write-Host ("{0}  effective_num_ctx={1}  expected>={2}" -f $ctxState, $logResult.EffectiveNumCtx, $ExpectedNumCtx)
        }
    }
}

$proxyUp = ($healthChecks | Where-Object { $_.Url -eq "$ProxyBaseUrl/" }).Success
$ctxVerified = ($logResult -and $logResult.EffectiveNumCtx -ge $ExpectedNumCtx)
$proxyRequestOk = ($proxyRequestResult -and $proxyRequestResult.Success)

Write-Host ""
Write-Host "=== Summary ==="
Write-Host ("proxy_up          : {0}" -f $proxyUp)
Write-Host ("proxy_request_ok  : {0}" -f $proxyRequestOk)
Write-Host ("ctx_verified      : {0}" -f $ctxVerified)
Write-Host ("strict_mode       : {0}" -f [bool]$Strict)

if ($Strict) {
    if ($proxyUp -and $proxyRequestOk -and $ctxVerified) {
        Write-Info "Strict checks passed."
        exit 0
    }
    Write-ErrMsg "Strict checks failed."
    exit 2
}

exit 0
