<#
.SYNOPSIS
  Configure %USERPROFILE%\.wslconfig for optimal Ollama/Docker GPU performance.

.DESCRIPTION
  Ensures that WSL2 settings needed for reliable GPU access are present in
  %USERPROFILE%\.wslconfig.
  - If the file does not exist: creates it with all recommended settings.
  - If the file exists: prompts yes/no for each missing or changed setting.
    Existing settings that already match are left untouched and skipped.
    No setting is ever modified without explicit confirmation.

  Settings managed:
    [wsl2]
    vmIdleTimeout=0  -- Prevents WSL2 VM from shutting down between sessions,
                        eliminating the 30-second GPU driver cold-start that
                        causes the WSLService timeout in Windows Event Log.

.PARAMETER NoPause
  Skip the end-of-run keypress (for scripted / CI use).

.PARAMETER Force
  Apply all settings without prompting (for CI / automation use).

.EXAMPLE
  PowerShell -ExecutionPolicy Bypass -File build/docker/setup-wslconfig.ps1
  PowerShell -ExecutionPolicy Bypass -File build/docker/setup-wslconfig.ps1 -Force -NoPause
#>

param(
    [switch]$NoPause,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$wslConfigPath = Join-Path $env:USERPROFILE '.wslconfig'

# ---------------------------------------------------------------------------
# Desired settings (add more entries here as needed)
# ---------------------------------------------------------------------------
$desiredSettings = @(
    [ordered]@{
        Section     = 'wsl2'
        Key         = 'vmIdleTimeout'
        Value       = '0'
        Description = 'Prevents WSL2 VM from shutting down when idle. Eliminates GPU driver cold-start (30s WSLService timeout in Windows Event Log).'
    }
)

# ---------------------------------------------------------------------------
# INI parser: returns hashtable-of-hashtables keyed by lowercase section name
# ---------------------------------------------------------------------------
function Read-IniFile {
    param([string]$Path)
    $ini = [ordered]@{}
    if (-not (Test-Path $Path)) { return $ini }
    $currentSection = '__global__'
    foreach ($line in (Get-Content -Path $Path -Encoding UTF8)) {
        $trimmed = $line.Trim()
        if ($trimmed -match '^\[(.+)\]$') {
            $currentSection = $Matches[1].Trim().ToLower()
            if (-not $ini.ContainsKey($currentSection)) {
                $ini[$currentSection] = [ordered]@{}
            }
        } elseif ($trimmed -match '^([^=;#]+?)\s*=\s*(.*)$') {
            $k = $Matches[1].Trim()
            $v = $Matches[2].Trim()
            if (-not $ini.ContainsKey($currentSection)) {
                $ini[$currentSection] = [ordered]@{}
            }
            $ini[$currentSection][$k] = $v
        }
    }
    return $ini
}

# ---------------------------------------------------------------------------
# Insert a new key=value into an existing section, or append a new section
# ---------------------------------------------------------------------------
function Add-IniSetting {
    param(
        [string]$Path,
        [string]$Section,
        [string]$Key,
        [string]$Value
    )
    $lines = @()
    if (Test-Path $Path) {
        $lines = @(Get-Content -Path $Path -Encoding UTF8)
    }
    $sectionHeader = "[$Section]"
    $sectionIdx    = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i].Trim() -eq $sectionHeader) { $sectionIdx = $i; break }
    }

    if ($sectionIdx -ge 0) {
        # Find insertion point: end of this section (before next header or EOF)
        $insertAt = $sectionIdx + 1
        for ($i = $sectionIdx + 1; $i -lt $lines.Count; $i++) {
            if ($lines[$i].Trim() -match '^\[') { break }
            $insertAt = $i + 1
        }
        $before = if ($insertAt -gt 0)             { $lines[0..($insertAt - 1)] } else { @() }
        $after  = if ($insertAt -lt $lines.Count)  { $lines[$insertAt..($lines.Count - 1)] } else { @() }
        $newLines = @($before) + @("$Key=$Value") + @($after)
        Set-Content -Path $Path -Value $newLines -Encoding UTF8
    } else {
        # Section does not exist yet -- append
        $append = @()
        if ($lines.Count -gt 0 -and $lines[-1].Trim() -ne '') { $append += '' }
        $append += $sectionHeader
        $append += "$Key=$Value"
        Add-Content -Path $Path -Value $append -Encoding UTF8
    }
}

# ---------------------------------------------------------------------------
# Replace an existing key=value within its section
# ---------------------------------------------------------------------------
function Set-IniSetting {
    param(
        [string]$Path,
        [string]$Section,
        [string]$Key,
        [string]$Value
    )
    $lines      = @(Get-Content -Path $Path -Encoding UTF8)
    $header     = "[$Section]"
    $inSection  = $false
    $replaced   = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i].Trim() -eq $header)                                 { $inSection = $true; continue }
        if ($inSection -and $lines[$i].Trim() -match '^\[')                { break }
        if ($inSection -and $lines[$i].Trim() -match "^${Key}\s*=") {
            $lines[$i] = "$Key=$Value"
            $replaced = $true
            break
        }
    }
    if ($replaced) {
        Set-Content -Path $Path -Value $lines -Encoding UTF8
    }
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=== setup-wslconfig.ps1 ==="
Write-Host "Config path: $wslConfigPath"
Write-Host ""

$anyChanged = $false

if (-not (Test-Path $wslConfigPath)) {
    # ---- File does not exist: create from scratch ----
    Write-Host ".wslconfig not found -- creating with recommended settings."
    $content = @(
        "# WSL2 configuration for lotr-dev",
        "# Managed by build/docker/setup-wslconfig.ps1",
        "# Docs: https://learn.microsoft.com/windows/wsl/wsl-config#wslconfig",
        ""
    )
    # Group desired settings by section
    $grouped = $desiredSettings | Group-Object -Property { $_['Section'] }
    foreach ($grp in $grouped) {
        $content += "[$($grp.Name)]"
        foreach ($s in $grp.Group) {
            $content += "# $($s['Description'])"
            $content += "$($s['Key'])=$($s['Value'])"
        }
        $content += ""
    }
    Set-Content -Path $wslConfigPath -Value $content -Encoding UTF8
    Write-Host "Created: $wslConfigPath"
    $anyChanged = $true
} else {
    # ---- File exists: check each setting individually ----
    Write-Host ".wslconfig found -- auditing settings..."
    $ini = Read-IniFile -Path $wslConfigPath

    foreach ($s in $desiredSettings) {
        $sec = $s['Section'].ToLower()
        $key = $s['Key']
        $val = $s['Value']
        $currentVal = $null
        if ($ini.ContainsKey($sec) -and $ini[$sec].ContainsKey($key)) {
            $currentVal = $ini[$sec][$key]
        }

        if ($null -eq $currentVal) {
            Write-Host ""
            Write-Host "  MISSING  [$($s['Section'])] $key"
            Write-Host "  Value  : $val"
            Write-Host "  Purpose: $($s['Description'])"
            if ($Force) {
                $answer = 'y'
                Write-Host "  (-Force) Adding automatically."
            } else {
                $answer = Read-Host "  Add this setting? [y/N]"
            }
            if ($answer -match '^[Yy]') {
                Add-IniSetting -Path $wslConfigPath -Section $s['Section'] -Key $key -Value $val
                Write-Host "  Added."
                $anyChanged = $true
            } else {
                Write-Host "  Skipped."
            }
        } elseif ($currentVal -ne $val) {
            Write-Host ""
            Write-Host "  DIFFERENT  [$($s['Section'])] $key"
            Write-Host "  Current  : $currentVal"
            Write-Host "  Recommended: $val"
            Write-Host "  Purpose  : $($s['Description'])"
            if ($Force) {
                $answer = 'y'
                Write-Host "  (-Force) Updating automatically."
            } else {
                $answer = Read-Host "  Change '$currentVal' -> '$val'? [y/N]"
            }
            if ($answer -match '^[Yy]') {
                Set-IniSetting -Path $wslConfigPath -Section $s['Section'] -Key $key -Value $val
                Write-Host "  Updated."
                $anyChanged = $true
            } else {
                Write-Host "  Skipped (keeping '$currentVal')."
            }
        } else {
            Write-Host "  OK  [$($s['Section'])] $key=$val"
        }
    }
}

Write-Host ""
if ($anyChanged) {
    Write-Host "Changes applied to $wslConfigPath"
    Write-Host ""
    Write-Host "IMPORTANT: You must restart the WSL2 VM for changes to take effect:"
    Write-Host "  wsl --shutdown"
    Write-Host "Then relaunch your dev container:"
    Write-Host "  PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 run"
} else {
    Write-Host "No changes needed -- all settings already correct."
}

Write-Host ""
if (-not $NoPause) {
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
}
