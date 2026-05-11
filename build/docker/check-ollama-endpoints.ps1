$urls = @(
    'http://host.docker.internal:11435/models',
    'http://host.docker.internal:11435/v1/models',
    'http://host.docker.internal:11435/api/models',
    'http://host.docker.internal:11435/'
)

foreach ($u in $urls) {
    Write-Host "==== $u ===="
    try {
        $resp = Invoke-RestMethod -Uri $u -Method Get -TimeoutSec 5 -ErrorAction Stop
        Write-Host "Status: OK"
        if ($resp -is [string]) { Write-Host $resp } else { $resp | ConvertTo-Json -Depth 6 | Write-Host }
    } catch {
        Write-Host "ERROR: $($_.Exception.Message)"
    }
}
