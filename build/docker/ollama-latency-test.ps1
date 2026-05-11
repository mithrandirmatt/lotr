<#
.SYNOPSIS
  Latency test for Ollama-compatible HTTP model endpoints.

.DESCRIPTION
  Sends a short JSON request to a specified HTTP endpoint and measures
  round-trip time (ms). Defaults to a local Ollama-style endpoint
  at http://localhost:11435/api/generate but `-Url` can target any
  compatible HTTP server.

.PARAMETER Url
  Full HTTP URL to POST the JSON payload to. Default: http://localhost:11434/api/generate

.PARAMETER Model
  Model name included in the JSON payload when applicable.

.PARAMETER Prompt
  Prompt text to send as the request body.

.PARAMETER Iterations
  Number of requests to send (default 3).

.PARAMETER IntervalMs
  Delay between requests in milliseconds (default 1000).

.PARAMETER TimeoutSec
  HTTP client timeout in seconds (default 30).

.PARAMETER ApiKey
  Optional bearer token to set as `Authorization: Bearer <ApiKey>`.

.PARAMETER Quiet
  Suppress per-request body output; still prints summary.

.EXAMPLE
  # Quick local test (3 requests)
  PowerShell -ExecutionPolicy Bypass -File .\ollama-latency-test.ps1

.EXAMPLE
  # Five iterations against a local Ollama server
  PowerShell -ExecutionPolicy Bypass -File .\ollama-latency-test.ps1 -Iterations 5

#>

param(
    [string]$Url = "http://localhost:11435/api/generate",
    [string]$Model = "llama3.1:8b",
    [string]$Prompt = "latency test: reply pong",
    [int]$Iterations = 3,
    [int]$IntervalMs = 1000,
    [int]$TimeoutSec = 30,
    [string]$ApiKey = "",
    [switch]$Quiet
)

if ($Iterations -lt 1) {
    Write-Error "Iterations must be >= 1"
    exit 1
}

Write-Host "Target URL: $Url"
Write-Host "Model: $Model  Prompt: $Prompt"
Write-Host "Iterations: $Iterations  Interval: ${IntervalMs}ms  Timeout: ${TimeoutSec}s"

$times = @()

for ($i = 1; $i -le $Iterations; $i++) {
    $payload = @{ model = $Model; prompt = $Prompt; max_tokens = 16 }
    $json = $payload | ConvertTo-Json -Depth 10

    $req = [System.Net.WebRequest]::Create($Url)
    $req.Method = 'POST'
    $req.ContentType = 'application/json'
    $req.Timeout = $TimeoutSec * 1000

    if ($ApiKey -ne '') { $req.Headers.Add('Authorization', "Bearer $ApiKey") }

    $reqStream = $null
    $sw = $null
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
        $req.ContentLength = $bytes.Length
        $reqStream = $req.GetRequestStream()
        $reqStream.Write($bytes, 0, $bytes.Length)
        $reqStream.Close()

        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $resp = $req.GetResponse()
        $sw.Stop()

        $elapsed = [math]::Round($sw.Elapsed.TotalMilliseconds, 2)
        $httpResp = [System.Net.HttpWebResponse]$resp
        $status = [int]$httpResp.StatusCode
        $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
        $body = $reader.ReadToEnd()
        $reader.Close()
        $resp.Close()

        $bytesLen = if ($body) { $body.Length } else { 0 }
        $times += $elapsed

        if (-not $Quiet) {
            Write-Host "[$i] ${elapsed} ms - HTTP/$status - ${bytesLen} bytes"
            if ($body) {
                $snippet = if ($body.Length -gt 300) { $body.Substring(0,300) + '...' } else { $body }
                Write-Host $snippet
            }
            Write-Host ""
        }
    } catch [System.Net.WebException] {
        if ($sw -ne $null) { $sw.Stop() }
        $elapsed = if ($sw -ne $null) { [math]::Round($sw.Elapsed.TotalMilliseconds, 2) } else { 0 }
        $err = $_.Exception.Message
        $resp = $_.Exception.Response
        $status = 'ERR'
        $body = ''
        if ($resp -ne $null) {
            try {
                $httpResp = [System.Net.HttpWebResponse]$resp
                $status = [int]$httpResp.StatusCode
                $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
                $body = $reader.ReadToEnd()
                $reader.Close()
                $resp.Close()
            } catch {}
        }
        if (-not $Quiet) {
            Write-Host "[$i] ERROR after ${elapsed} ms: $err" -ForegroundColor Red
            if ($body) { Write-Host $body }
            Write-Host ""
        }
        $times += $elapsed
    } finally {
        if ($reqStream -ne $null) { $reqStream.Dispose() }
    }

    if ($i -lt $Iterations) { Start-Sleep -Milliseconds $IntervalMs }
}

if ($times.Count -eq 0) {
    Write-Host "No timing data collected.";
    exit 1
}

$min = ($times | Measure-Object -Minimum).Minimum
$max = ($times | Measure-Object -Maximum).Maximum
$avg = ($times | Measure-Object -Average).Average
$sorted = $times | Sort-Object
$count = $sorted.Count
if ($count % 2 -eq 1) { $median = $sorted[ [int]($count/2) ] } else { $median = (($sorted[$count/2 -1] + $sorted[$count/2]) / 2) }

Write-Host "Summary - iterations: $Iterations"
Write-Host ('  min: {0} ms  max: {1} ms  avg: {2:N2} ms  median: {3} ms' -f $min, $max, $avg, $median)

exit 0
