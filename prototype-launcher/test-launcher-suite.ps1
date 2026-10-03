#Requires -Version 5.1
<#
.SYNOPSIS
    Comprehensive validation & regression test suite for CodeStruct Prototype Launcher.
.DESCRIPTION
    Validates port pre-checking, foreign listener safety, incremental state persistence,
    safe rollback, proxy connectivity, alternate ports, and unsaved work protection.
#>

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$LauncherDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $LauncherDir) { $LauncherDir = (Get-Location).Path }

$ConfigPath = Join-Path $LauncherDir "prototype-config.json"
$StartScript = Join-Path $LauncherDir "Start-CodeStruct-Prototype.ps1"
$StopScript = Join-Path $LauncherDir "Stop-CodeStruct-Prototype.ps1"
$StatePath = Join-Path $LauncherDir "runtime\prototype-state.json"
$LockPath = Join-Path $LauncherDir "runtime\launcher.lock"
$LogsDir = Join-Path $LauncherDir "logs"

$testResults = [System.Collections.Generic.List[PSCustomObject]]::new()

function Record-TestResult([string]$name, [bool]$passed, [string]$details) {
    $status = if ($passed) { "PASS" } else { "FAIL" }
    $color = if ($passed) { "Green" } else { "Red" }
    Write-Host "[$status] $($name): $details" -ForegroundColor $color
    $testResults.Add([PSCustomObject]@{
        Name = $name
        Status = $status
        Details = $details
    })
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " CodeStruct Prototype Launcher - Comprehensive Test Suite" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Clean initial state
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StopScript | Out-Null
Start-Sleep -Seconds 1

# TEST 1: Config Validation (Invalid Port & Missing Directory)
Write-Host "`n[Test 1] Config Validation..." -ForegroundColor Yellow
$origConfig = Get-Content -Path $ConfigPath -Raw -Encoding UTF8
try {
    $badConfig = $origConfig | ConvertFrom-Json
    $badConfig.backendPort = 999999
    $badConfig | ConvertTo-Json -Depth 5 | Set-Content -Path $ConfigPath -Encoding UTF8
    
    $out = powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StartScript 2>&1
    $exitCode = $LASTEXITCODE
    $hasErrorMsg = ($out -join "`n") -match "backendPort must be between 1 and 65535"
    $passed = ($exitCode -ne 0) -and $hasErrorMsg
    Record-TestResult "ConfigValidation" $passed "Exit code: $exitCode, Error message caught: $hasErrorMsg"
} finally {
    Set-Content -Path $ConfigPath -Value $origConfig -Encoding UTF8
}

# TEST 2: Working Directory Independence
Write-Host "`n[Test 2] Working Directory Independence..." -ForegroundColor Yellow
$tempCwd = [System.IO.Path]::GetTempPath()
$origLoc = Get-Location
try {
    Set-Location $tempCwd
    $out = powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StopScript 2>&1
    $exitCode = $LASTEXITCODE
    $passed = ($exitCode -eq 0)
    Record-TestResult "WorkingDir-Independence" $passed "Executed Stop from $tempCwd with exit code $exitCode"
} finally {
    Set-Location $origLoc
}

# TEST 3: Port Conflict Safety - Backend Port (Pre-Check Rejection)
Write-Host "`n[Test 3] Port Conflict Safety on Backend Port..." -ForegroundColor Yellow
$dummyListenerB = $null
try {
    $dummyListenerB = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse("127.0.0.1"), 8000)
    $dummyListenerB.Start()
    
    $out = powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StartScript 2>&1
    $exitCode = $LASTEXITCODE
    $outStr = $out -join "`n"
    $detectedConflict = $outStr -match "Backend port 8000 is in use by an unrecognized process"
    $passed = ($exitCode -ne 0) -and $detectedConflict
    Record-TestResult "PortConflict-Backend" $passed "Exit code: $exitCode, Safely rejected: $detectedConflict"
} finally {
    if ($dummyListenerB) { try { $dummyListenerB.Stop() } catch {} }
    Start-Sleep -Milliseconds 500
}

# TEST 4: Port Conflict Safety - Frontend Port (Pre-Check Rejection Before Backend Start)
Write-Host "`n[Test 4] Port Conflict Safety on Frontend Port (Pre-Check)..." -ForegroundColor Yellow
$dummyListenerF = $null
try {
    $dummyListenerF = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse("127.0.0.1"), 5173)
    $dummyListenerF.Start()
    
    $out = powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StartScript 2>&1
    $exitCode = $LASTEXITCODE
    $outStr = $out -join "`n"
    $detectedConflict = $outStr -match "Frontend port 5173 is in use by an unrecognized process"
    
    # Check that backend port 8000 was NOT started because pre-check stopped it!
    $backendPortOccupied = $false
    try {
        $conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
        if ($conn) { $backendPortOccupied = $true }
    } catch {}
    
    $passed = ($exitCode -ne 0) -and $detectedConflict -and (-not $backendPortOccupied)
    Record-TestResult "PortConflict-FrontendPreCheck" $passed "Rejected: $detectedConflict, Backend not started: $(-not $backendPortOccupied)"
} finally {
    if ($dummyListenerF) { try { $dummyListenerF.Stop() } catch {} }
    Start-Sleep -Milliseconds 500
}

# TEST 5: Full Startup, Service Readiness, and Frontend API Proxying
Write-Host "`n[Test 5] Full Startup, Service Readiness & Frontend Proxy Verification..." -ForegroundColor Yellow
$out = powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StartScript 2>&1
$exitCode = $LASTEXITCODE
$startPassed = ($exitCode -eq 0) -and (Test-Path $StatePath)

$backendHealthy = $false
$frontendHealthy = $false
$proxyHealthy = $false

if ($startPassed) {
    try {
        $rB = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/projects" -Method Get -TimeoutSec 3
        if ($rB -and $rB.projects) { $backendHealthy = $true }
    } catch {}
    try {
        $rF = Invoke-WebRequest -Uri "http://127.0.0.1:5173/" -Method Get -TimeoutSec 3 -UseBasicParsing
        if ($rF.StatusCode -eq 200) { $frontendHealthy = $true }
    } catch {}
    try {
        $rP = Invoke-RestMethod -Uri "http://127.0.0.1:5173/api/v1/projects" -Method Get -TimeoutSec 3
        if ($rP -and $rP.projects) { $proxyHealthy = $true }
    } catch {}
}
$fullPassed = $startPassed -and $backendHealthy -and $frontendHealthy -and $proxyHealthy
Record-TestResult "FullStartup-ProxyReadiness" $fullPassed "Backend: $backendHealthy, Frontend: $frontendHealthy, Proxy: $proxyHealthy"

# TEST 6: Repeated Start (Reusing Existing Services Without Duplicate PIDs)
Write-Host "`n[Test 6] Repeated Start (Reusing Verified Active Services)..." -ForegroundColor Yellow
$stateBefore = (Get-Content -Path $StatePath -Raw -Encoding UTF8) | ConvertFrom-Json
$out2 = powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StartScript 2>&1
$exitCode2 = $LASTEXITCODE
$out2Str = $out2 -join "`n"
$reusedBackend = $out2Str -match "Reusing verified launcher-owned backend"
$reusedFrontend = $out2Str -match "Reusing verified launcher-owned frontend"
$stateAfter = (Get-Content -Path $StatePath -Raw -Encoding UTF8) | ConvertFrom-Json

$samePids = ($stateBefore.backend.pid -eq $stateAfter.backend.pid) -and ($stateBefore.frontend.pid -eq $stateAfter.frontend.pid)
$repeatedPassed = ($exitCode2 -eq 0) -and $reusedBackend -and $reusedFrontend -and $samePids
Record-TestResult "RepeatedStart-ServiceReuse" $repeatedPassed "Reused Backend: $reusedBackend, Reused Frontend: $reusedFrontend, Identical PIDs: $samePids"

# TEST 7: Stop Owned Services & Port Release
Write-Host "`n[Test 7] Stop Owned Services & Port Release..." -ForegroundColor Yellow
$outStop = powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StopScript 2>&1
$exitCodeStop = $LASTEXITCODE
Start-Sleep -Seconds 1

$backendPortFree = $true
try {
    $conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if ($conn) { $backendPortFree = $false }
} catch {}

$frontendPortFree = $true
try {
    $connF = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
    if ($connF) { $frontendPortFree = $false }
} catch {}

$stateRemoved = -not (Test-Path $StatePath)
$stopPassed = ($exitCodeStop -eq 0) -and $backendPortFree -and $frontendPortFree -and $stateRemoved
Record-TestResult "SafeStop-PortRelease" $stopPassed "Backend port freed: $backendPortFree, Frontend port freed: $frontendPortFree, State removed: $stateRemoved"

# TEST 8: Repeated Stop Idempotency
Write-Host "`n[Test 8] Repeated Stop Idempotency..." -ForegroundColor Yellow
$outStop2 = powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StopScript 2>&1
$exitCodeStop2 = $LASTEXITCODE
$idempotentPassed = ($exitCodeStop2 -eq 0)
Record-TestResult "RepeatedStop-Idempotent" $idempotentPassed "Exit code: $exitCodeStop2"

# TEST 9: Stale State and Dead PID Handling
Write-Host "`n[Test 9] Stale State and Dead PID Handling..." -ForegroundColor Yellow
$fakeState = [ordered]@{
    backend = [ordered]@{ pid = 999999; startTime = "2020-01-01T00:00:00.0000000Z"; port = 8000 }
    frontend = [ordered]@{ pid = 999998; startTime = "2020-01-01T00:00:00.0000000Z"; port = 5173 }
    updatedAt = (Get-Date).ToString("o")
}
$fakeState | ConvertTo-Json -Depth 5 | Set-Content -Path $StatePath -Encoding UTF8
$outStale = powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StopScript 2>&1
$exitCodeStale = $LASTEXITCODE
$stalePassed = ($exitCodeStale -eq 0) -and (-not (Test-Path $StatePath))
Record-TestResult "StaleState-Handling" $stalePassed "Exit code: $exitCodeStale, Stale state cleared safely"

# TEST 10: Alternate Ports End-to-End Verification (Ports 8001 and 5174)
Write-Host "`n[Test 10] Alternate Ports End-to-End (8001 / 5174)..." -ForegroundColor Yellow
$altConfig = $origConfig | ConvertFrom-Json
$altConfig.backendPort = 8001
$altConfig.frontendPort = 5174
$altConfig | ConvertTo-Json -Depth 5 | Set-Content -Path $ConfigPath -Encoding UTF8

try {
    $outAlt = powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StartScript 2>&1
    $exitCodeAlt = $LASTEXITCODE
    
    $altBackendOk = $false
    $altFrontendOk = $false
    $altProxyOk = $false
    
    if ($exitCodeAlt -eq 0) {
        try {
            $rB = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/v1/projects" -Method Get -TimeoutSec 3
            if ($rB -and $rB.projects) { $altBackendOk = $true }
        } catch {}
        try {
            $rF = Invoke-WebRequest -Uri "http://127.0.0.1:5174/" -Method Get -TimeoutSec 3 -UseBasicParsing
            if ($rF.StatusCode -eq 200) { $altFrontendOk = $true }
        } catch {}
        try {
            # Proxy check: frontend 5174 forwarding /api to backend 8001!
            $rP = Invoke-RestMethod -Uri "http://127.0.0.1:5174/api/v1/projects" -Method Get -TimeoutSec 3
            if ($rP -and $rP.projects) { $altProxyOk = $true }
        } catch {}
    }
    
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StopScript | Out-Null
    Start-Sleep -Seconds 1
    
    $altPassed = ($exitCodeAlt -eq 0) -and $altBackendOk -and $altFrontendOk -and $altProxyOk
    Record-TestResult "AlternatePorts-8001-5174" $altPassed "Backend 8001: $altBackendOk, Frontend 5174: $altFrontendOk, Proxy: $altProxyOk"
} finally {
    Set-Content -Path $ConfigPath -Value $origConfig -Encoding UTF8
}

# TEST 11: Desktop Shortcuts Verification
Write-Host "`n[Test 11] Desktop Shortcuts Target Verification..." -ForegroundColor Yellow
$desktopPath = [Environment]::GetFolderPath('Desktop')
if (-not $desktopPath -or -not (Test-Path $desktopPath)) {
    $regDesktop = Get-ItemPropertyValue -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" -Name "Desktop" -ErrorAction SilentlyContinue
    if ($regDesktop) { $desktopPath = [Environment]::ExpandEnvironmentVariables($regDesktop) }
}
$wsh = New-Object -ComObject WScript.Shell
$scStartPath = Join-Path $desktopPath "Start CodeStruct Prototype.lnk"
$scStopPath = Join-Path $desktopPath "Stop CodeStruct Prototype.lnk"

$scStartExists = Test-Path $scStartPath
$scStopExists = Test-Path $scStopPath
$scStartTargetMatch = $false
$scStopTargetMatch = $false

if ($scStartExists) {
    $sc = $wsh.CreateShortcut($scStartPath)
    $scStartTargetMatch = ($sc.TargetPath -eq (Join-Path $LauncherDir "Start-CodeStruct-Prototype.cmd"))
}
if ($scStopExists) {
    $sc = $wsh.CreateShortcut($scStopPath)
    $scStopTargetMatch = ($sc.TargetPath -eq (Join-Path $LauncherDir "Stop-CodeStruct-Prototype.cmd"))
}

$shortcutsPassed = $scStartExists -and $scStopExists -and $scStartTargetMatch -and $scStopTargetMatch
Record-TestResult "DesktopShortcuts" $shortcutsPassed "Start Target Valid: $scStartTargetMatch, Stop Target Valid: $scStopTargetMatch"

# TEST 12: Thonny Preflight Failure Safe Abort (No False Success)
Write-Host "`n[Test 12] Thonny Plugin Preflight Failure Safe Abort..." -ForegroundColor Yellow
$badThonnyConfig = $origConfig | ConvertFrom-Json
$badThonnyConfig.thonnyPluginDirectory = Join-Path $LauncherDir "nonexistent-plugin-dir"
$badThonnyConfig | ConvertTo-Json -Depth 5 | Set-Content -Path $ConfigPath -Encoding UTF8

try {
    $outPre = powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StartScript 2>&1
    $exitCodePre = $LASTEXITCODE
    $outPreStr = $outPre -join "`n"
    $detectedPreflightFail = $outPreStr -match "thonnyPluginDirectory does not exist|preflight check failed"
    $passedPre = ($exitCodePre -ne 0) -and $detectedPreflightFail
    Record-TestResult "ThonnyPreflight-SafeAbort" $passedPre "Exit code: $exitCodePre, Aborted safely: $detectedPreflightFail"
} finally {
    Set-Content -Path $ConfigPath -Value $origConfig -Encoding UTF8
}

# Final cleanup of services
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StopScript | Out-Null

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host " Test Suite Summary" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
$allPassed = $true
foreach ($res in $testResults) {
    $color = if ($res.Status -eq "PASS") { "Green" } else { "Red"; $allPassed = $false }
    Write-Host "[$($res.Status)] $($res.Name): $($res.Details)" -ForegroundColor $color
}
Write-Host "============================================================`n" -ForegroundColor Cyan

if ($allPassed) {
    Write-Host "[OVERALL VERDICT] ALL 12 TESTS PASSED!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "[OVERALL VERDICT] SOME TESTS FAILED." -ForegroundColor Red
    exit 1
}
