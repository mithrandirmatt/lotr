try {
    $script = Get-Content -Raw 'build/docker/docker.ps1'
    [System.Management.Automation.Language.Parser]::ParseInput($script, [ref]$null, [ref]$null)
    Write-Output 'PARSE-OK'
} catch {
    Write-Output 'PARSE-ERROR'
    Write-Output ('Message: ' + $_.Exception.Message)
    Write-Output ('ErrorRecord: ' + ($_.ToString()))
    $_ | Format-List * -Force
    exit 1
}
