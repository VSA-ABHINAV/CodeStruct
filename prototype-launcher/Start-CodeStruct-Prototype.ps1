#Requires -Version 5.1
<#
.SYNOPSIS
    Starts the CodeStruct prototype services and launches Thonny with the adapter configured.
.DESCRIPTION
    Validates configuration, performs preflight port and dependency checks,
    creates/repairs Thonny profile configuration without UTF-8 BOM,
    starts or reuses backend and frontend services on loopback ports with strict rollback safety,
    verifies service readiness and API proxying, and launches Thonny with an isolated profile.
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

# Ensure runtime and logs directories exist
if (-not (Test-Path $RuntimeDir)) { New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null }
if (-not (Test-Path $LogsDir)) { New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null }

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " CodeStruct Prototype Launcher" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 2. Acquire single-start lock
$lockStream = $null
try {
    $lockFile = [System.IO.FileInfo]::new($LockPath)
    $lockStream = $lockFile.Open([System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
} catch {
    Write-Host "[ERROR] Another CodeStruct launcher operation is currently in progress." -ForegroundColor Red
    Write-Host "Please wait for it to complete or check $LockPath" -ForegroundColor Yellow
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

# Helper: Find listening PID for a TCP port
function Get-ListeningPid([int]$port) {
    try {
        $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($conn -and $conn.OwningProcess) { return [int]$conn.OwningProcess }
    } catch {}

    try {
        $output = netstat -ano -p tcp 2>$null
        foreach ($line in $output) {
            if ($line -match ":$port\s+.*LISTENING\s+(\d+)") {
                return [int]$matches[1]
            }
        }
    } catch {}
    return $null
}

# Helper: Test if host is loopback
function Test-LoopbackHost([string]$hostStr) {
    if (-not $hostStr) { return $false }
    $h = $hostStr.Trim().ToLower()
    if ($h -in @("127.0.0.1", "localhost", "::1")) { return $true }
    try {
        $ip = [System.Net.IPAddress]::Parse($h.Trim("[]"))
        return [System.Net.IPAddress]::IsLoopback($ip)
    } catch {
        return $false
    }
}

# Helper: Save state safely
function Save-LauncherState($stateObj) {
    $json = $stateObj | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText($StatePath, $json, [System.Text.Encoding]::UTF8)
}

# 3. Read and validate configuration
if (-not (Test-Path $ConfigPath)) {
    Write-Host "[ERROR] Configuration file not found: $ConfigPath" -ForegroundColor Red
    Release-Lock
    exit 1
}

try {
    $configRaw = Get-Content -Path $ConfigPath -Raw -Encoding UTF8
    $config = $configRaw | ConvertFrom-Json
} catch {
    Write-Host "[ERROR] Failed to parse configuration JSON: $_" -ForegroundColor Red
    Release-Lock
    exit 1
}

# Validation checks
$validationErrors = [System.Collections.Generic.List[string]]::new()

if (-not (Test-Path $config.codeStructDirectory)) {
    $validationErrors.Add("codeStructDirectory does not exist: '$($config.codeStructDirectory)'")
}
if (-not (Test-Path $config.backendPythonExecutable)) {
    $validationErrors.Add("backendPythonExecutable does not exist: '$($config.backendPythonExecutable)'")
}
if (-not (Test-Path $config.frontendDirectory)) {
    $validationErrors.Add("frontendDirectory does not exist: '$($config.frontendDirectory)'")
}
if (-not (Test-Path $config.thonnyDirectory)) {
    $validationErrors.Add("thonnyDirectory does not exist: '$($config.thonnyDirectory)'")
}
if (-not (Test-Path $config.thonnyPythonExecutable)) {
    $validationErrors.Add("thonnyPythonExecutable does not exist: '$($config.thonnyPythonExecutable)'")
}
if (-not (Test-Path $config.thonnyPluginDirectory)) {
    $validationErrors.Add("thonnyPluginDirectory does not exist: '$($config.thonnyPluginDirectory)'")
}
if (-not (Test-Path $config.demonstrationProjectDirectory)) {
    $validationErrors.Add("demonstrationProjectDirectory does not exist: '$($config.demonstrationProjectDirectory)'")
}
if (-not (Test-LoopbackHost $config.backendHost)) {
    $validationErrors.Add("backendHost must be a loopback address (127.0.0.1, localhost, ::1): '$($config.backendHost)'")
}
if (-not (Test-LoopbackHost $config.frontendHost)) {
    $validationErrors.Add("frontendHost must be a loopback address (127.0.0.1, localhost, ::1): '$($config.frontendHost)'")
}
if ($config.backendPort -lt 1 -or $config.backendPort -gt 65535) {
    $validationErrors.Add("backendPort must be between 1 and 65535: $($config.backendPort)")
}
if ($config.frontendPort -lt 1 -or $config.frontendPort -gt 65535) {
    $validationErrors.Add("frontendPort must be between 1 and 65535: $($config.frontendPort)")
}
if (-not $config.demonstrationRootId -or $config.demonstrationRootId.Trim() -eq "") {
    $validationErrors.Add("demonstrationRootId must be a non-empty string.")
}

if ($validationErrors.Count -gt 0) {
    Write-Host "[ERROR] Configuration validation failed:" -ForegroundColor Red
    foreach ($err in $validationErrors) {
        Write-Host "  - $err" -ForegroundColor Red
    }
    Release-Lock
    exit 1
}

$backendUrl = "http://$($config.backendHost):$($config.backendPort)"
$frontendUrl = "http://$($config.frontendHost):$($config.frontendPort)"
$rootId = $config.demonstrationRootId
$projectDir = (Resolve-Path $config.demonstrationProjectDirectory).Path
$databasePath = $config.databasePath
$profileDir = $config.thonnyUserProfileDirectory

# Ensure directories for profile and database exist
$dbDir = Split-Path -Parent $databasePath
if ($dbDir -and -not (Test-Path $dbDir)) { New-Item -ItemType Directory -Path $dbDir -Force | Out-Null }
if (-not (Test-Path $profileDir)) { New-Item -ItemType Directory -Path $profileDir -Force | Out-Null }

# 4. Safe UTF-8 Without BOM Profile Initialization & Repair
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$profileConfig = Join-Path $profileDir "configuration.ini"

if (Test-Path $profileConfig) {
    # Check for leading UTF-8 BOM (0xEF, 0xBB, 0xBF)
    try {
        $rawBytes = [System.IO.File]::ReadAllBytes($profileConfig)
        if ($rawBytes.Length -ge 3 -and $rawBytes[0] -eq 0xEF -and $rawBytes[1] -eq 0xBB -and $rawBytes[2] -eq 0xBF) {
            Write-Host "  Detected UTF-8 BOM in existing profile configuration ($profileConfig). Repairing..." -ForegroundColor Yellow
            $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
            $backupPath = "$profileConfig.bom-backup-$timestamp"
            [System.IO.File]::Copy($profileConfig, $backupPath, $true)
            Write-Host "  Backup saved to $backupPath" -ForegroundColor Gray

            $strippedBytes = New-Object byte[] ($rawBytes.Length - 3)
            [System.Array]::Copy($rawBytes, 3, $strippedBytes, 0, $strippedBytes.Length)
            [System.IO.File]::WriteAllBytes($profileConfig, $strippedBytes)
            Write-Host "  Successfully repaired profile configuration (BOM removed, settings preserved)." -ForegroundColor Green
        }
    } catch {
        Write-Host "[WARN] Unable to inspect or repair BOM in $($profileConfig): $_" -ForegroundColor Yellow
    }
} else {
    # Fresh profile creation: Write clean UTF-8 WITHOUT BOM
    $defaultIni = @"
[general]
ui_mode = regular
language = en_US
single_instance = False
"@
    [System.IO.File]::WriteAllText($profileConfig, $defaultIni, $utf8NoBom)
}

# 5. Load existing state and PRE-CHECK BOTH PORTS before starting any services
$existingState = $null
if (Test-Path $StatePath) {
    try {
        $existingState = (Get-Content -Path $StatePath -Raw -Encoding UTF8) | ConvertFrom-Json
    } catch {}
}

$occupiedBackendPid = Get-ListeningPid $config.backendPort
$occupiedFrontendPid = Get-ListeningPid $config.frontendPort

$canReuseBackend = $false
$backendPid = $null
$backendStartTime = $null

if ($occupiedBackendPid) {
    Write-Host "Checking occupied backend port $($config.backendPort) (PID $occupiedBackendPid)..." -ForegroundColor Gray
    if ($existingState -and $existingState.backend -and $existingState.backend.pid -eq $occupiedBackendPid) {
        try {
            $p = Get-Process -Id $occupiedBackendPid -ErrorAction Stop
            if ($p.StartTime.ToString("o") -eq $existingState.backend.startTime) {
                # Verify backend HTTP response and authorized root
                $resp = Invoke-RestMethod -Uri "$backendUrl/api/v1/projects" -Method Get -TimeoutSec 3 -ErrorAction Stop
                $hasRoot = $false
                if ($resp.projects) {
                    foreach ($proj in $resp.projects) {
                        if ($proj.id -eq $rootId) { $hasRoot = $true; break }
                    }
                }
                if ($hasRoot) {
                    $canReuseBackend = $true
                    $backendPid = $occupiedBackendPid
                    $backendStartTime = $existingState.backend.startTime
                    Write-Host "  Reusing verified launcher-owned backend (PID: $backendPid)." -ForegroundColor Green
                }
            }
        } catch {}
    }

    if (-not $canReuseBackend) {
        Write-Host "[ERROR] Backend port $($config.backendPort) is in use by an unrecognized process (PID $occupiedBackendPid)." -ForegroundColor Red
        Write-Host "Please terminate the conflicting process or change 'backendPort' in prototype-config.json." -ForegroundColor Yellow
        Release-Lock
        exit 1
    }
}

$canReuseFrontend = $false
$frontendPid = $null
$frontendStartTime = $null

if ($occupiedFrontendPid) {
    Write-Host "Checking occupied frontend port $($config.frontendPort) (PID $occupiedFrontendPid)..." -ForegroundColor Gray
    if ($existingState -and $existingState.frontend -and $existingState.frontend.pid -eq $occupiedFrontendPid) {
        try {
            $p = Get-Process -Id $occupiedFrontendPid -ErrorAction Stop
            if ($p.StartTime.ToString("o") -eq $existingState.frontend.startTime) {
                $resp = Invoke-WebRequest -Uri "$frontendUrl/" -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
                if ($resp.StatusCode -eq 200) {
                    $canReuseFrontend = $true
                    $frontendPid = $occupiedFrontendPid
                    $frontendStartTime = $existingState.frontend.startTime
                    Write-Host "  Reusing verified launcher-owned frontend (PID: $frontendPid)." -ForegroundColor Green
                }
            }
        } catch {}
    }

    if (-not $canReuseFrontend) {
        Write-Host "[ERROR] Frontend port $($config.frontendPort) is in use by an unrecognized process (PID $occupiedFrontendPid)." -ForegroundColor Red
        Write-Host "Please terminate the conflicting process or change 'frontendPort' in prototype-config.json." -ForegroundColor Yellow
        Release-Lock
        exit 1
    }
}

# Tracking newly started services for safe rollback on failure
$newlyStartedBackendPid = $null
$newlyStartedBackendStartTime = $null
$newlyStartedFrontendPid = $null
$newlyStartedFrontendStartTime = $null

function Rollback-NewlyStartedServices {
    Write-Host "`n[ROLLBACK] Cleaning up newly started services from this failed attempt..." -ForegroundColor Yellow
    if ($newlyStartedFrontendPid) {
        try {
            $p = Get-Process -Id $newlyStartedFrontendPid -ErrorAction Stop
            if ($p.StartTime.ToString("o") -eq $newlyStartedFrontendStartTime) {
                taskkill /PID $newlyStartedFrontendPid /T /F 2>&1 | Out-Null
                Write-Host "  Rolled back newly started frontend (PID: $newlyStartedFrontendPid)." -ForegroundColor Gray
            }
        } catch {}
    }
    if ($newlyStartedBackendPid) {
        try {
            $p = Get-Process -Id $newlyStartedBackendPid -ErrorAction Stop
            if ($p.StartTime.ToString("o") -eq $newlyStartedBackendStartTime) {
                taskkill /PID $newlyStartedBackendPid /T /F 2>&1 | Out-Null
                Write-Host "  Rolled back newly started backend (PID: $newlyStartedBackendPid)." -ForegroundColor Gray
            }
        } catch {}
    }
    
    # Restore state file to previous verified state (if any reused service remains) or remove
    if ($canReuseBackend -and -not $newlyStartedBackendPid) {
        $savedState = [ordered]@{
            backend = [ordered]@{ pid = $backendPid; startTime = $backendStartTime; port = $config.backendPort }
            rootId = $rootId
            projectDir = $projectDir
            databasePath = $databasePath
            updatedAt = (Get-Date).ToString("o")
        }
        Save-LauncherState $savedState
    } else {
        Remove-Item -Path $StatePath -Force -ErrorAction SilentlyContinue
    }
}

# 6. Start Backend Service if not reused
Write-Host "[1/4] Starting / Verifying CodeStruct Backend on $backendUrl..." -ForegroundColor Yellow

if (-not $canReuseBackend) {
    Write-Host "  Launching backend service..." -ForegroundColor Gray
    $backendLogOut = Join-Path $LogsDir "backend-out.log"
    $backendLogErr = Join-Path $LogsDir "backend-err.log"

    $backendSrc = Join-Path $config.codeStructDirectory "backend\src"
    $backendCmd = "/c set PYTHONPATH=$backendSrc&& set CODESTRUCT_AUTHORIZED_ROOTS=$rootId=$projectDir&& set CODESTRUCT_DATABASE_PATH=$databasePath&& `"$($config.backendPythonExecutable)`" -m uvicorn codestruct.api.app:create_app --factory --port $($config.backendPort) --host $($config.backendHost) > `"$backendLogOut`" 2> `"$backendLogErr`""

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = "cmd.exe"
    $psi.Arguments = $backendCmd
    $psi.WorkingDirectory = $config.codeStructDirectory
    $psi.UseShellExecute = $true
    $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden

    $parentProc = [System.Diagnostics.Process]::Start($psi)

    # Wait for backend readiness
    $ready = $false
    $timeout = [DateTime]::UtcNow.AddSeconds($config.startupTimeoutSeconds)
    while ([DateTime]::UtcNow -lt $timeout) {
        try {
            $resp = Invoke-RestMethod -Uri "$backendUrl/api/v1/projects" -Method Get -TimeoutSec 2 -ErrorAction Stop
            if ($resp -and $resp.projects) {
                foreach ($proj in $resp.projects) {
                    if ($proj.id -eq $rootId) {
                        $ready = $true
                        break
                    }
                }
            }
            if ($ready) { break }
        } catch {
            Start-Sleep -Milliseconds 300
        }
    }

    if (-not $ready) {
        Write-Host "[ERROR] Backend server failed to become ready within $($config.startupTimeoutSeconds)s." -ForegroundColor Red
        Write-Host "Check log: $backendLogErr" -ForegroundColor Yellow
        $listenPid = Get-ListeningPid $config.backendPort
        if ($listenPid) { $newlyStartedBackendPid = $listenPid; $newlyStartedBackendStartTime = (Get-Process -Id $listenPid).StartTime.ToString("o") }
        else { $newlyStartedBackendPid = $parentProc.Id; $newlyStartedBackendStartTime = $parentProc.StartTime.ToString("o") }
        Rollback-NewlyStartedServices
        Release-Lock
        exit 1
    }

    # Record actual listening PID
    $listenPid = Get-ListeningPid $config.backendPort
    if ($listenPid) {
        $backendPid = $listenPid
        $backendStartTime = (Get-Process -Id $listenPid).StartTime.ToString("o")
    } else {
        $backendPid = $parentProc.Id
        $backendStartTime = $parentProc.StartTime.ToString("o")
    }

    $newlyStartedBackendPid = $backendPid
    $newlyStartedBackendStartTime = $backendStartTime

    # Persist intermediate state immediately
    $interState = [ordered]@{
        backend = [ordered]@{ pid = $backendPid; startTime = $backendStartTime; port = $config.backendPort }
        rootId = $rootId
        projectDir = $projectDir
        databasePath = $databasePath
        updatedAt = (Get-Date).ToString("o")
    }
    Save-LauncherState $interState
    Write-Host "  Backend is ready and verified (PID: $backendPid)." -ForegroundColor Green
}

# 7. Start Frontend Service if not reused
Write-Host "[2/4] Starting / Verifying CodeStruct Frontend on $frontendUrl..." -ForegroundColor Yellow

if (-not $canReuseFrontend) {
    Write-Host "  Launching frontend service with proxy -> $backendUrl..." -ForegroundColor Gray
    $frontendLogOut = Join-Path $LogsDir "frontend-out.log"
    $frontendLogErr = Join-Path $LogsDir "frontend-err.log"

    $frontendCmd = "/c set CODESTRUCT_BACKEND_URL=$backendUrl&& npx vite --port $($config.frontendPort) --strictPort --host $($config.frontendHost) > `"$frontendLogOut`" 2> `"$frontendLogErr`""

    $psiF = [System.Diagnostics.ProcessStartInfo]::new()
    $psiF.FileName = "cmd.exe"
    $psiF.Arguments = $frontendCmd
    $psiF.WorkingDirectory = $config.frontendDirectory
    $psiF.UseShellExecute = $true
    $psiF.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden

    $parentProcF = [System.Diagnostics.Process]::Start($psiF)

    # Wait for frontend readiness and proxy verification
    $readyF = $false
    $timeoutF = [DateTime]::UtcNow.AddSeconds($config.startupTimeoutSeconds)
    while ([DateTime]::UtcNow -lt $timeoutF) {
        try {
            $resp = Invoke-WebRequest -Uri "$frontendUrl/" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
            if ($resp.StatusCode -eq 200) {
                # Also verify proxy connectivity through frontend to backend
                try {
                    $proxyResp = Invoke-RestMethod -Uri "$frontendUrl/api/v1/projects" -Method Get -TimeoutSec 2 -ErrorAction Stop
                    if ($proxyResp -and $proxyResp.projects) {
                        $readyF = $true
                        break
                    }
                } catch {
                    # Vite might still be setting up proxy; sleep and retry
                }
            }
        } catch {
            Start-Sleep -Milliseconds 300
        }
    }

    if (-not $readyF) {
        Write-Host "[ERROR] Frontend server failed to become ready or proxy to backend within $($config.startupTimeoutSeconds)s." -ForegroundColor Red
        Write-Host "Check log: $frontendLogErr" -ForegroundColor Yellow
        $listenFPid = Get-ListeningPid $config.frontendPort
        if ($listenFPid) { $newlyStartedFrontendPid = $listenFPid; $newlyStartedFrontendStartTime = (Get-Process -Id $listenFPid).StartTime.ToString("o") }
        else { $newlyStartedFrontendPid = $parentProcF.Id; $newlyStartedFrontendStartTime = $parentProcF.StartTime.ToString("o") }
        Rollback-NewlyStartedServices
        Release-Lock
        exit 1
    }

    # Record actual listening PID
    $listenFPid = Get-ListeningPid $config.frontendPort
    if ($listenFPid) {
        $frontendPid = $listenFPid
        $frontendStartTime = (Get-Process -Id $listenFPid).StartTime.ToString("o")
    } else {
        $frontendPid = $parentProcF.Id
        $frontendStartTime = $parentProcF.StartTime.ToString("o")
    }

    $newlyStartedFrontendPid = $frontendPid
    $newlyStartedFrontendStartTime = $frontendStartTime

    Write-Host "  Frontend is ready and proxy verified (PID: $frontendPid)." -ForegroundColor Green
}

# 8. Persist Complete Combined State
$stateData = [ordered]@{
    backend = [ordered]@{
        pid = $backendPid
        startTime = $backendStartTime
        port = $config.backendPort
    }
    frontend = [ordered]@{
        pid = $frontendPid
        startTime = $frontendStartTime
        port = $config.frontendPort
    }
    rootId = $rootId
    projectDir = $projectDir
    databasePath = $databasePath
    updatedAt = (Get-Date).ToString("o")
}
Save-LauncherState $stateData

# 9. Thonny Config & Adapter Preflight Check & Launch
Write-Host "[3/4] Verifying Thonny profile configuration and adapter..." -ForegroundColor Yellow

$thonnyPyPath = "$($config.thonnyDirectory);$($config.thonnyPluginDirectory)"

# Preflight: Verify Thonny config reader without error_reading_existing_file and plugin loading
$preflightCode = "import sys; sys.path.insert(0, r'$($config.thonnyPluginDirectory)'); sys.path.insert(0, r'$($config.thonnyDirectory)'); import thonny, thonny.config, thonnycontrib.codestruct; cfg = thonny.config.try_load_configuration(r'$profileConfig'); sys.exit(2 if cfg.error_reading_existing_file else 0)"
$preflightCmd = "-c `"$preflightCode`""
$preflightProc = Start-Process -FilePath $config.thonnyPythonExecutable -ArgumentList $preflightCmd -NoNewWindow -Wait -PassThru -RedirectStandardOutput (Join-Path $LogsDir "thonny-preflight.log") -RedirectStandardError (Join-Path $LogsDir "thonny-preflight-err.log")

if ($preflightProc.ExitCode -ne 0) {
    Write-Host "[ERROR] Thonny configuration / plugin preflight check failed (Exit code: $($preflightProc.ExitCode))." -ForegroundColor Red
    Write-Host "Check log: $(Join-Path $LogsDir 'thonny-preflight-err.log')" -ForegroundColor Yellow
    Rollback-NewlyStartedServices
    Release-Lock
    exit 1
}

$thonnyScriptsDir = Split-Path -Parent $config.thonnyPythonExecutable
$thonnyCmd = "/c set PATH=$thonnyScriptsDir;%PATH%&& set PYTHONPATH=$thonnyPyPath&& set CODESTRUCT_ROOT_MAPPINGS=$rootId=$projectDir&& set CODESTRUCT_BACKEND_URL=$backendUrl&& set CODESTRUCT_FRONTEND_URL=$frontendUrl&& set THONNY_USER_DIR=$profileDir&& `"$($config.thonnyPythonExecutable)`" -m thonny"

$psiT = [System.Diagnostics.ProcessStartInfo]::new()
$psiT.FileName = "cmd.exe"
$psiT.Arguments = $thonnyCmd
$psiT.WorkingDirectory = $config.thonnyDirectory
$psiT.UseShellExecute = $true
$psiT.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden

$thonnyProc = [System.Diagnostics.Process]::Start($psiT)

Write-Host "  Thonny IDE launched successfully (PID: $($thonnyProc.Id))." -ForegroundColor Green

# 10. Success Summary
Write-Host "`n[4/4] CodeStruct Prototype Started Successfully!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Backend Server:    $backendUrl (PID: $backendPid)" -ForegroundColor White
Write-Host " Frontend Viewer:   $frontendUrl (PID: $frontendPid)" -ForegroundColor White
Write-Host " Mapped Root ID:    $rootId" -ForegroundColor White
Write-Host " Target Directory:  $projectDir" -ForegroundColor White
Write-Host " Thonny Profile:    $profileDir" -ForegroundColor White
Write-Host " Logs Directory:    $LogsDir" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Instructions:" -ForegroundColor Yellow
Write-Host "  1. In Thonny, open your project file (e.g. main.py)." -ForegroundColor White
Write-Host "  2. In the top menu, click Tools -> Analyze with CodeStruct." -ForegroundColor White
Write-Host "  3. Confirm the folder to submit analysis and view results in browser." -ForegroundColor White
Write-Host "  4. To stop services, double-click 'Stop CodeStruct Prototype'." -ForegroundColor White
Write-Host "============================================================`n" -ForegroundColor Cyan

Release-Lock
exit 0
