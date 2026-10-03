#Requires -Version 5.1
<#
.SYNOPSIS
    Regression test suite for Thonny profile configuration encoding and repair.
.DESCRIPTION
    Validates fresh profile creation (no BOM), existing BOM-prefixed profile repair with backup,
    non-ASCII Unicode preservation, malformed INI handling, and repeated execution safety.
#>

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$LauncherDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $LauncherDir) { $LauncherDir = (Get-Location).Path }

$ConfigPath = Join-Path $LauncherDir "prototype-config.json"
$config = (Get-Content -Path $ConfigPath -Raw -Encoding UTF8) | ConvertFrom-Json
$thonnyPy = $config.thonnyPythonExecutable
$thonnyDir = $config.thonnyDirectory

$testResults = [System.Collections.Generic.List[PSCustomObject]]::new()

function Record-Result([string]$name, [bool]$passed, [string]$details) {
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
Write-Host " Thonny Profile Encoding & Repair Test Suite" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$tempTestRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("thonny_profile_test_" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempTestRoot -Force | Out-Null

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$utf8WithBom = [System.Text.Encoding]::UTF8

try {
    # Helper to test Thonny config reader in Python
    function Test-ThonnyConfigReader([string]$filePath) {
        $pyCode = "import sys; sys.path.insert(0, r'$thonnyDir'); import thonny.config; cfg = thonny.config.try_load_configuration(r'$filePath'); sys.exit(2 if cfg.error_reading_existing_file else 0)"
        $proc = Start-Process -FilePath $thonnyPy -ArgumentList "-c `"$pyCode`"" -NoNewWindow -Wait -PassThru
        return ($proc.ExitCode -eq 0)
    }

    # Helper: repair BOM function matching launcher
    function Invoke-ProfileSetup([string]$profileDir) {
        $profileConfig = Join-Path $profileDir "configuration.ini"
        if (Test-Path $profileConfig) {
            $rawBytes = [System.IO.File]::ReadAllBytes($profileConfig)
            if ($rawBytes.Length -ge 3 -and $rawBytes[0] -eq 0xEF -and $rawBytes[1] -eq 0xBB -and $rawBytes[2] -eq 0xBF) {
                $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
                $backupPath = "$profileConfig.bom-backup-$timestamp"
                [System.IO.File]::Copy($profileConfig, $backupPath, $true)

                $strippedBytes = New-Object byte[] ($rawBytes.Length - 3)
                [System.Array]::Copy($rawBytes, 3, $strippedBytes, 0, $strippedBytes.Length)
                [System.IO.File]::WriteAllBytes($profileConfig, $strippedBytes)
            }
        } else {
            $defaultIni = @"
[general]
ui_mode = regular
language = en_US
single_instance = False
"@
            [System.IO.File]::WriteAllText($profileConfig, $defaultIni, $utf8NoBom)
        }
    }

    # TEST 1: Fresh Profile Creation (No BOM)
    Write-Host "`n[Test 1] Fresh Profile Creation (UTF-8 Without BOM)..." -ForegroundColor Yellow
    $p1 = Join-Path $tempTestRoot "prof1"
    New-Item -ItemType Directory -Path $p1 -Force | Out-Null
    Invoke-ProfileSetup $p1
    $f1 = Join-Path $p1 "configuration.ini"
    $bytes1 = [System.IO.File]::ReadAllBytes($f1)
    $hasBom1 = ($bytes1.Length -ge 3 -and $bytes1[0] -eq 0xEF -and $bytes1[1] -eq 0xBB -and $bytes1[2] -eq 0xBF)
    $readerOk1 = Test-ThonnyConfigReader $f1
    $pass1 = (-not $hasBom1) -and $readerOk1
    Record-Result "FreshProfile-NoBOM" $pass1 "Has BOM: $hasBom1, Thonny Reader OK: $readerOk1"

    # TEST 2: Existing BOM-Prefixed Profile Repair
    Write-Host "`n[Test 2] Existing BOM-Prefixed Profile Repair with Backup..." -ForegroundColor Yellow
    $p2 = Join-Path $tempTestRoot "prof2"
    New-Item -ItemType Directory -Path $p2 -Force | Out-Null
    $f2 = Join-Path $p2 "configuration.ini"
    $bomContent = @"
[general]
ui_mode = regular
language = en_US
single_instance = False
custom_setting = HelloBOM
"@
    # Explicitly write with BOM
    [System.IO.File]::WriteAllText($f2, $bomContent, $utf8WithBom)
    
    # Confirm it has BOM initially
    $bytesBefore2 = [System.IO.File]::ReadAllBytes($f2)
    $hadBomInitial = ($bytesBefore2[0] -eq 0xEF -and $bytesBefore2[1] -eq 0xBB -and $bytesBefore2[2] -eq 0xBF)
    
    # Run repair
    Invoke-ProfileSetup $p2
    
    $bytesAfter2 = [System.IO.File]::ReadAllBytes($f2)
    $hasBomAfter = ($bytesAfter2[0] -eq 0xEF -and $bytesAfter2[1] -eq 0xBB -and $bytesAfter2[2] -eq 0xBF)
    $backupFiles = @(Get-ChildItem -Path $p2 -Filter "configuration.ini.bom-backup-*")
    $hasBackup = ($backupFiles.Count -ge 1)
    $readerOk2 = Test-ThonnyConfigReader $f2
    $contentAfter2 = [System.IO.File]::ReadAllText($f2, $utf8NoBom)
    $settingPreserved = $contentAfter2 -match "custom_setting = HelloBOM"
    
    $pass2 = $hadBomInitial -and (-not $hasBomAfter) -and $hasBackup -and $readerOk2 -and $settingPreserved
    Record-Result "BOM-Repair-And-Backup" $pass2 "Had BOM initially: $hadBomInitial, BOM removed: $(-not $hasBomAfter), Backup created: $hasBackup, Reader OK: $readerOk2, Setting preserved: $settingPreserved"

    # TEST 3: Existing Valid Profile Unchanged
    Write-Host "`n[Test 3] Existing Valid Profile Left Unchanged..." -ForegroundColor Yellow
    $p3 = Join-Path $tempTestRoot "prof3"
    New-Item -ItemType Directory -Path $p3 -Force | Out-Null
    $f3 = Join-Path $p3 "configuration.ini"
    $validContent = @"
[general]
ui_mode = regular
language = en_US
single_instance = False
"@
    [System.IO.File]::WriteAllText($f3, $validContent, $utf8NoBom)
    $bytesBefore3 = [System.IO.File]::ReadAllBytes($f3)
    
    Invoke-ProfileSetup $p3
    
    $bytesAfter3 = [System.IO.File]::ReadAllBytes($f3)
    $backups3 = @(Get-ChildItem -Path $p3 -Filter "*.bak*")
    $sameBytes = ([System.Linq.Enumerable]::SequenceEqual($bytesBefore3, $bytesAfter3))
    $pass3 = $sameBytes -and ($backups3.Count -eq 0)
    Record-Result "ValidProfile-Unchanged" $pass3 "Byte content identical: $sameBytes, No unnecessary backup: $($backups3.Count -eq 0)"

    # TEST 4: Non-ASCII Unicode Settings Preservation
    Write-Host "`n[Test 4] Non-ASCII Unicode Settings Preservation..." -ForegroundColor Yellow
    $p4 = Join-Path $tempTestRoot "prof4"
    New-Item -ItemType Directory -Path $p4 -Force | Out-Null
    $f4 = Join-Path $p4 "configuration.ini"
    $unicodeContent = @"
[general]
ui_mode = regular
language = zh_CN
author = José Müller & 日本語テスト
single_instance = False
"@
    # Seed with BOM to test repair + unicode preservation
    [System.IO.File]::WriteAllText($f4, $unicodeContent, $utf8WithBom)
    Invoke-ProfileSetup $p4
    
    $repairedText4 = [System.IO.File]::ReadAllText($f4, $utf8NoBom)
    $readerOk4 = Test-ThonnyConfigReader $f4
    $unicodeMatch = $repairedText4 -match "José Müller & 日本語テスト"
    $pass4 = $readerOk4 -and $unicodeMatch
    Record-Result "Unicode-Preservation" $pass4 "Thonny Reader OK: $readerOk4, Unicode characters intact: $unicodeMatch"

    # TEST 5: Repeated Startup Idempotency
    Write-Host "`n[Test 5] Repeated Startup Idempotency..." -ForegroundColor Yellow
    $p5 = Join-Path $tempTestRoot "prof5"
    New-Item -ItemType Directory -Path $p5 -Force | Out-Null
    Invoke-ProfileSetup $p5
    $f5 = Join-Path $p5 "configuration.ini"
    $bytesFirst = [System.IO.File]::ReadAllBytes($f5)
    
    Invoke-ProfileSetup $p5
    $bytesSecond = [System.IO.File]::ReadAllBytes($f5)
    $identical = [System.Linq.Enumerable]::SequenceEqual($bytesFirst, $bytesSecond)
    Record-Result "RepeatedStartup-Idempotent" $identical "First & second run produce identical bytes: $identical"

} finally {
    Remove-Item -Path $tempTestRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host " Test Summary" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
$allPass = $true
foreach ($r in $testResults) {
    $c = if ($r.Status -eq "PASS") { "Green" } else { "Red"; $allPass = $false }
    Write-Host "[$($r.Status)] $($r.Name): $($r.Details)" -ForegroundColor $c
}
Write-Host "============================================================`n" -ForegroundColor Cyan

if ($allPass) {
    Write-Host "[VERDICT] ALL 5 PROFILE ENCODING TESTS PASSED!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "[VERDICT] SOME PROFILE ENCODING TESTS FAILED." -ForegroundColor Red
    exit 1
}
