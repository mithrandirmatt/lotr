<#
trouble-shoot.ps1

Troubleshoot WSL, Docker, and ROCDXG (librocdxg) setup for this repo.

Writes a timestamped log to build/docker/logs/trouble-shoot.ps1.log and prints
diagnostic output to the console. Designed to be safe to run from a user
PowerShell prompt; many WSL commands use `-u root` inside WSL where needed.

Usage examples:
  PowerShell -ExecutionPolicy Bypass -File build/docker/trouble-shoot.ps1 -Action all
  PowerShell -ExecutionPolicy Bypass -File build/docker/trouble-shoot.ps1 -Action devices -DistroName lotr-docker-service

Actions (comma-separated):
  all      : run wsl,docker,devices,rocdxg checks
  wsl      : list WSL distros and WSL status
  docker   : run `docker version`, `docker info`, `docker ps -a`
  devices  : inspect /dev nodes and bridge libraries inside the distro
  rocdxg   : show install log, env and run `rocminfo` inside the distro
  strace   : run `strace` on `rocminfo` (requires `strace` present in WSL)

#>

param(
    [string]$DistroName = "lotr-docker-service",
    [string]$Action = "all"
)

Set-StrictMode -Version Latest

$logDir = Join-Path $PSScriptRoot 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
# Use a per-run timestamped log to avoid file-lock contention; update canonical log at end
$timeStamp = (Get-Date).ToString('yyyyMMddTHHmmss')
$logFile = Join-Path $logDir ("trouble-shoot.$timeStamp.$PID.log")
$canonicalLog = Join-Path $logDir 'trouble-shoot.ps1.log'

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $ts = (Get-Date).ToString('o')
    $line = "$ts`t[$Level]`t$Message"
    Add-Content -Path $logFile -Value $line
    Write-Host $line
}

function Run-External {
    param([string]$Label, [string]$Exe, [Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
    $argStr = if ($Args) { $Args -join ' ' } else { '' }
    Write-Log ("RUN {0}: {1} {2}" -f $Label, $Exe, $argStr)
    $argList = if ($Args) { ($Args | ForEach-Object { "'$_'" }) -join ', ' } else { '' }
    $argCount = if ($Args) { $Args.Count } else { 0 }
    Write-Log ("Args count={0}; elements={1}" -f $argCount, $argList)
    $outFile = [System.IO.Path]::GetTempFileName()
    $errFile = [System.IO.Path]::GetTempFileName()
    try {
        # Special-case WSL to avoid argument-list quoting issues: run via cmd.exe /c "wsl ..."
        if ($Exe -match '^(wsl|wsl\.exe)$') {
            $argsCopy = @()
            foreach ($a in $Args) {
                if ($a -match '\s|;|\|') {
                    $safe = $a -replace '"','\"'
                    $argsCopy += '"' + $safe + '"'
                } else {
                    $argsCopy += $a
                }
            }
            # Use the system wsl.exe path to avoid unexpected PATH shadowing
            $wslPath = Join-Path $env:windir 'System32\wsl.exe'
            $cmdString = '"' + $wslPath + '"' + ' ' + ($argsCopy -join ' ')
            # Invoke the system wsl.exe directly with the assembled argument array
            try {
                $output = & $wslPath @Args 2>&1 | Out-String
                $exit = $LASTEXITCODE
            } catch {
                $output = $_ | Out-String
                $exit = $LASTEXITCODE
            }
            # write captured output to temp files for consistency
            Set-Content -Path $outFile -Value ($output -split "`n" | Where-Object { $_ -ne '' } ) -ErrorAction SilentlyContinue
            Set-Content -Path $errFile -Value '' -ErrorAction SilentlyContinue
            $stdout = Get-Content -Raw -ErrorAction SilentlyContinue $outFile
            $stderr = Get-Content -Raw -ErrorAction SilentlyContinue $errFile
            $output = ($stdout + "`n" + $stderr).Trim()
        }
        else {
            # Normal Start-Process invocation
            $proc = Start-Process -FilePath $Exe -ArgumentList $Args -NoNewWindow -Wait -RedirectStandardOutput $outFile -RedirectStandardError $errFile -PassThru
            $exit = $proc.ExitCode
            $stdout = Get-Content -Raw -ErrorAction SilentlyContinue $outFile
            $stderr = Get-Content -Raw -ErrorAction SilentlyContinue $errFile
            $output = ($stdout + "`n" + $stderr).Trim()
        }
    }
    catch {
        # Fallback to direct invocation if Start-Process fails for any reason
        try {
            $output = & $Exe @Args 2>&1 | Out-String
            $exit = $LASTEXITCODE
        } catch {
            $output = $_ | Out-String
            $exit = $LASTEXITCODE
        }
    }

    if ($output -and $output.Trim()) {
        foreach ($line in ($output -split "`n")) {
            $tries = 0
            while ($true) {
                try {
                    Add-Content -Path $logFile -Value $line
                    break
                } catch {
                    Start-Sleep -Milliseconds 50
                    $tries++
                    if ($tries -gt 6) { Write-Host "WARN: failed to write to log after retries"; break }
                }
            }
        }
        Write-Host $output
    }
    Write-Log ("END {0} exit {1}" -f $Label, $exit)

    Remove-Item -ErrorAction SilentlyContinue $outFile,$errFile
    return @{ExitCode=$exit; Output=$output}
}

function Convert-WindowsPathToWsl {
    param([string]$WinPath)
    if (-not $WinPath) { return $null }
    $drive = $WinPath.Substring(0,1).ToLower()
    $rest = $WinPath.Substring(2) -replace '\\','/'
    return "/mnt/$drive/$rest"
}

if (-not $PSBoundParameters.ContainsKey('Action') -or [string]::IsNullOrWhiteSpace($Action)) {
    $Action = 'all'
}

Write-Log ("Starting trouble-shoot.ps1; Action={0}; Distro={1}" -f $Action, $DistroName)

$actions = $Action -split '[,;]' | ForEach-Object { $_.Trim().ToLower() }
if ($actions -contains 'all') { $actions = @('wsl','docker','devices','rocdxg') }

if ($actions -contains 'wsl') {
    Run-External 'WSL list' 'wsl' '--list' '--verbose'
    Run-External 'WSL status' 'wsl' '--status'
}

if ($actions -contains 'docker') {
    Run-External 'Docker version (WSL)' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' 'docker version'
    Run-External 'Docker info (WSL)' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' 'docker info'
    Run-External 'Docker ps (WSL)' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' 'docker ps -a'
}

if ($actions -contains 'devices') {
    $remoteDevices = 'uname -a; echo; echo PID1:; cat /proc/1/comm 2>/dev/null || true; echo; echo DEV nodes:; ls -l /dev/dxg /dev/kfd /dev/dri 2>/dev/null || true; echo; echo libs:; ls -l /usr/lib/wsl/lib/libdxcore.so /opt/rocm/lib/librocdxg.so 2>/dev/null || true'
    Run-External 'WSL devices' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' $remoteDevices
}

if ($actions -contains 'rocdxg') {
    $rocdxgCmd = 'echo INSTALL_LOG:; cat /var/log/install_rocdxg.log 2>/dev/null || echo no install log; echo; echo ENV AND LDCONFIG:; cat /etc/profile.d/rocdxg.sh 2>/dev/null || true; ldconfig -p | grep librocdxg || true; echo; echo ROCMINFO:; source /etc/profile.d/rocdxg.sh >/dev/null 2>&1 || true; HSA_ENABLE_DXG_DETECTION=1 ROCMINFO_DEBUG=1 rocminfo || true'
    Run-External 'ROCDXG check' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' $rocdxgCmd
}

if ($actions -contains 'strace') {
    $check = Run-External 'Check strace' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' 'which strace >/dev/null 2>&1 && echo present || echo missing'
    if ($check.Output -match 'present') {
        # Normal strace run
        $straceCmd = 'strace -f -e openat -o /tmp/rocminfo.strace bash -lc "ROCMINFO_DEBUG=1 HSA_ENABLE_DXG_DETECTION=1 rocminfo" || true; echo; echo STRACE HEAD:; head -n 200 /tmp/rocminfo.strace || true'
        Run-External 'strace rocminfo' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' $straceCmd

        # Preload librocdxg and collect strace as well
        $preCmd = 'strace -f -e openat -o /tmp/rocminfo.preload.strace bash -lc "LD_PRELOAD=/opt/rocm/lib/librocdxg.so HSA_ENABLE_DXG_DETECTION=1 ROCMINFO_DEBUG=1 rocminfo" || true; echo; echo PRELOAD STRACE HEAD:; head -n 200 /tmp/rocminfo.preload.strace || true'
        Run-External 'strace rocminfo (preload)' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' $preCmd

        # Capture dynamic loader debug (LD_DEBUG=files) to help see dlopen attempts
        $lddebugCmd = 'LD_DEBUG=files HSA_ENABLE_DXG_DETECTION=1 ROCMINFO_DEBUG=1 bash -lc "rocminfo" > /tmp/rocminfo.lddebug 2>&1 || true; echo; echo LD_DEBUG HEAD:; head -n 200 /tmp/rocminfo.lddebug || true'
        Run-External 'LD_DEBUG rocminfo' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' $lddebugCmd
        # Search librocdxg for DXCore/libdxcore references and capture info
        # write all strings to a temp file and grep sequentially to avoid complex quoting
        $dxstringsCmd = 'which strings >/dev/null 2>&1 && (strings /opt/rocm/lib/librocdxg.so* > /tmp/rocdxg.allstrings 2>/dev/null || true; grep -a -i dxcore /tmp/rocdxg.allstrings >> /tmp/rocdxg.dxcore.strings 2>/dev/null || true; grep -a -i libdxcore /tmp/rocdxg.allstrings >> /tmp/rocdxg.dxcore.strings 2>/dev/null || true; grep -a -i DXCore /tmp/rocdxg.allstrings >> /tmp/rocdxg.dxcore.strings 2>/dev/null || true) || echo strings-missing; echo; echo DX STRINGS HEAD:; head -n 200 /tmp/rocdxg.dxcore.strings || true'
        Run-External 'Search librocdxg for DXCore strings' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' $dxstringsCmd

        # Show libdxcore file information (WSL-provided and any system copy)
        $dxlibInfoCmd = 'ls -l /usr/lib/wsl/lib/libdxcore.so /usr/lib/libdxcore.so 2>/dev/null || true; file /usr/lib/wsl/lib/libdxcore.so 2>/dev/null || true'
        Run-External 'Libdxcore info' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' $dxlibInfoCmd

        # Preload dxcore alone and capture strace
        $dxPreCmd = 'strace -f -e openat -o /tmp/rocminfo.dxcore.preload.strace bash -lc "LD_PRELOAD=/usr/lib/wsl/lib/libdxcore.so HSA_ENABLE_DXG_DETECTION=1 ROCMINFO_DEBUG=1 rocminfo" || true; echo; echo DXCORE PRELOAD STRACE HEAD:; head -n 200 /tmp/rocminfo.dxcore.preload.strace || true'
        Run-External 'strace rocminfo (dxcore preload)' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' $dxPreCmd

        # Preload dxcore + librocdxg combined
        $dxComboCmd = 'strace -f -e openat -o /tmp/rocminfo.dxcore.combo.strace bash -lc "LD_PRELOAD=/usr/lib/wsl/lib/libdxcore.so:/opt/rocm/lib/librocdxg.so HSA_ENABLE_DXG_DETECTION=1 ROCMINFO_DEBUG=1 rocminfo" || true; echo; echo DXCORE+ROCDXG PRELOAD STRACE HEAD:; head -n 200 /tmp/rocminfo.dxcore.combo.strace || true'
        Run-External 'strace rocminfo (dxcore+rocdxg preload)' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' $dxComboCmd

        # Symlink test: create /usr/lib/libdxcore.so -> /usr/lib/wsl/lib/libdxcore.so and run rocminfo
        # Create symlink, run strace, then remove symlink as separate steps to avoid nested quoting
        Run-External 'Create dxcore symlink' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' 'if [ -f /usr/lib/wsl/lib/libdxcore.so ]; then ln -sf /usr/lib/wsl/lib/libdxcore.so /usr/lib/libdxcore.so || true; fi'
        Run-External 'strace rocminfo (dxcore symlink)' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' 'strace -f -e openat -o /tmp/rocminfo.dxcore.symlink.strace bash -lc "HSA_ENABLE_DXG_DETECTION=1 ROCMINFO_DEBUG=1 rocminfo" || true; echo; echo SYMLINK STRACE HEAD:; head -n 200 /tmp/rocminfo.dxcore.symlink.strace || true'
        Run-External 'Remove dxcore symlink' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' 'rm -f /usr/lib/libdxcore.so || true'

        # Attempt to copy the trace and debug files into the Windows-side logs folder for easier offline inspection
        $windowsLogDir = Join-Path $PSScriptRoot 'logs'
        $wslLogDir = Convert-WindowsPathToWsl $windowsLogDir
        if ($wslLogDir) {
            Run-External 'Ensure logdir in WSL' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' "mkdir -p '$wslLogDir' || true"
            Run-External 'Copy strace to workspace' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' "cat /tmp/rocminfo.strace > '$wslLogDir/rocminfo.strace' || true"
            Run-External 'Copy preload strace to workspace' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' "cat /tmp/rocminfo.preload.strace > '$wslLogDir/rocminfo.preload.strace' || true"
            Run-External 'Copy dx strings to workspace' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' "cat /tmp/rocdxg.dxcore.strings > '$wslLogDir/rocdxg.dxcore.strings' || true"
            Run-External 'Copy dxcore preload strace' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' "cat /tmp/rocminfo.dxcore.preload.strace > '$wslLogDir/rocminfo.dxcore.preload.strace' || true"
            Run-External 'Copy dxcore combo strace' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' "cat /tmp/rocminfo.dxcore.combo.strace > '$wslLogDir/rocminfo.dxcore.combo.strace' || true"
            Run-External 'Copy dxcore symlink strace' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' "cat /tmp/rocminfo.dxcore.symlink.strace > '$wslLogDir/rocminfo.dxcore.symlink.strace' || true"
            Run-External 'Copy ld debug to workspace' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' "cat /tmp/rocminfo.lddebug > '$wslLogDir/rocminfo.lddebug' || true"
            Run-External 'List copied traces' 'wsl' '--distribution' $DistroName '--user' 'root' '--' 'bash' '-lc' "ls -l '$wslLogDir'/rocminfo.* || true"
        }
    } else {
        Write-Log 'strace not present in WSL distro; to collect, run as root: apt-get update && apt-get install -y strace'
    }
}

Write-Log 'trouble-shoot.ps1 completed'

# Attempt to update canonical log file atomically (with retries)
try {
    $attempts = 0
    while ($true) {
        try {
            Copy-Item -Path $logFile -Destination $canonicalLog -Force -ErrorAction Stop
            break
        } catch {
            Start-Sleep -Milliseconds 100
            $attempts++
            if ($attempts -gt 6) { Write-Host "WARN: failed to update canonical log $canonicalLog"; break }
        }
    }
} catch {
    Write-Host "WARN: unexpected error while copying log: $_"
}
