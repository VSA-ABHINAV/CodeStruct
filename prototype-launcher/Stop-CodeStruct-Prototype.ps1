#Requires -Version 5.1
<#
.SYNOPSIS
    Stops the CodeStruct prototype services (Backend and Frontend) started by the launcher.
.DESCRIPTION
    Verifies process identity (PID and StartTime) against prototype-state.json before stopping.
    Leaves Thonny open so the user does not lose unsaved work.
#>

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# 1. Resolve launcher directory and paths
$LauncherDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $LauncherDir) { $LauncherDir = (Get-Location).Path }

$ConfigPath = Join-Path $LauncherDir "prototype-config.json"
$RuntimeDir = Join-Path $LauncherDir "runtime"
$LogsDir = Join-Path $LauncherDir "logs"
$LockPath = Join-Path $RuntimeDir "launcher.lock"
$StatePath = Join-Path $RuntimeDir "prototype-state.json"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " CodeStruct Prototype - Stop Services" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 2. Acquire lock
$lockStream = $null
try {
    $lockFile = [System.IO.FileInfo]::new($LockPath)
    $lockStream = $lockFile.Open([System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
} catch {
    Write-Host "[ERROR] Another CodeStruct launcher operation is in progress." -ForegroundColor Red
    exit 1
}

function Release-Lock {
    if ($lockStream) {
        try {
            $lockStream.Close()
            $lockStream.Dispose()
        } catch {}
    }
}

# 3. Check for state file
if (-not (Test-Path $StatePath)) {
    Write-Host "[INFO] No active CodeStruct prototype state found. Services are not running." -ForegroundColor Green
    Release-Lock
    exit 0
}

try {
    $state = (Get-Content -Path $StatePath -Raw -Encoding UTF8) | ConvertFrom-Json
} catch {
    Write-Host "[WARN] State file could not be parsed. Removing corrupted state file." -ForegroundColor Yellow
    Remove-Item -Path $StatePath -Force -ErrorAction SilentlyContinue
    Release-Lock
    exit 0
}

# Helper to safely stop a verified process
function Stop-VerifiedProcess([string]$name, [int]$targetPid, [string]$targetStartTime) {
    if (-not $targetPid) { return $true }
    
    try {
        $p = Get-Process -Id $targetPid -ErrorAction Stop
        if ($p.StartTime.ToString("o") -eq $targetStartTime) {
            Write-Host "Stopping $name (PID: $targetPid)..." -ForegroundColor Yellow
            
            # Use taskkill /T /F to clean up the verified process tree
            $tkOutput = taskkill /PID $targetPid /T /F 2>&1
            
            # Verify process is gone
            Start-Sleep -Milliseconds 300
            try {
                $check = Get-Process -Id $targetPid -ErrorAction Stop
                Write-Host "[ERROR] Failed to terminate $name (PID: $targetPid)." -ForegroundColor Red
                return $false
            } catch {
                Write-Host "  $name stopped successfully." -ForegroundColor Green
                return $true
            }
        } else {
            Write-Host "[INFO] Process with PID $targetPid is running but does not match launcher StartTime. Skipping to avoid killing unrelated process." -ForegroundColor Yellow
            return $true
        }
    } catch {
        # Process is already dead or not found
        Write-Host "  $name (PID: $targetPid) is no longer running." -ForegroundColor Gray
        return $true
    }
}

$allStopped = $true

# 4. Stop backend and frontend if verified
if ($state.backend -and $state.backend.pid) {
    $bRes = Stop-VerifiedProcess "Backend" ([int]$state.backend.pid) ([string]$state.backend.startTime)
    if (-not $bRes) { $allStopped = $false }
}

if ($state.frontend -and $state.frontend.pid) {
    $fRes = Stop-VerifiedProcess "Frontend" ([int]$state.frontend.pid) ([string]$state.frontend.startTime)
    if (-not $fRes) { $allStopped = $false }
}

# 5. Clean up state file only if all targets stopped or handled
if ($allStopped) {
    try {
        Remove-Item -Path $StatePath -Force -ErrorAction SilentlyContinue
        Write-Host "Runtime state file cleared." -ForegroundColor Gray
    } catch {}

    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "[SUCCESS] CodeStruct services have been stopped." -ForegroundColor Green
    Write-Host "NOTE: Thonny was left open to preserve any unsaved editor changes." -ForegroundColor Cyan
    Write-Host "You can close Thonny normally whenever you are ready." -ForegroundColor Cyan
    Write-Host "============================================================`n" -ForegroundColor Cyan
    Release-Lock
    exit 0
} else {
    Write-Host "[ERROR] Some services could not be stopped. State file preserved for retry." -ForegroundColor Red
    Release-Lock
    exit 1
}
