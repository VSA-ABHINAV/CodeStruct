#Requires -Version 5.1
<#
.SYNOPSIS
    Creates or updates the Desktop shortcuts for Start and Stop CodeStruct Prototype.
.DESCRIPTION
    Resolves the active Desktop folder (including OneDrive redirected folders),
    inspects existing shortcuts, and points them to Start-CodeStruct-Prototype.cmd and Stop-CodeStruct-Prototype.cmd.
#>

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$LauncherDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $LauncherDir) { $LauncherDir = (Get-Location).Path }

$StartCmd = Join-Path $LauncherDir "Start-CodeStruct-Prototype.cmd"
$StopCmd = Join-Path $LauncherDir "Stop-CodeStruct-Prototype.cmd"

if (-not (Test-Path $StartCmd)) { throw "Start script not found: $StartCmd" }
if (-not (Test-Path $StopCmd)) { throw "Stop script not found: $StopCmd" }

# Resolve actual desktop path
$desktopPath = [Environment]::GetFolderPath('Desktop')
if (-not $desktopPath -or -not (Test-Path $desktopPath)) {
    # Fallback to registry query
    $regDesktop = Get-ItemPropertyValue -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" -Name "Desktop" -ErrorAction SilentlyContinue
    if ($regDesktop) {
        $desktopPath = [Environment]::ExpandEnvironmentVariables($regDesktop)
    }
}

if (-not $desktopPath -or -not (Test-Path $desktopPath)) {
    throw "Unable to resolve active Windows Desktop directory."
}

Write-Host "Resolved Desktop Directory: $desktopPath" -ForegroundColor Cyan

$wshShell = New-Object -ComObject WScript.Shell

# 1. Start shortcut
$startShortcutPath = Join-Path $desktopPath "Start CodeStruct Prototype.lnk"
$existingStart = $false
if (Test-Path $startShortcutPath) {
    $existingStart = $true
    $sc = $wshShell.CreateShortcut($startShortcutPath)
    Write-Host "Existing 'Start CodeStruct Prototype' shortcut target: $($sc.TargetPath)" -ForegroundColor Gray
}

$startShortcut = $wshShell.CreateShortcut($startShortcutPath)
$startShortcut.TargetPath = $StartCmd
$startShortcut.WorkingDirectory = $LauncherDir
$startShortcut.Description = "Start CodeStruct Prototype (Backend, Frontend, and Thonny)"
$startShortcut.Save()
Write-Host "[OK] Created/Updated: $startShortcutPath -> $StartCmd" -ForegroundColor Green

# 2. Stop shortcut
$stopShortcutPath = Join-Path $desktopPath "Stop CodeStruct Prototype.lnk"
$existingStop = $false
if (Test-Path $stopShortcutPath) {
    $existingStop = $true
    $sc = $wshShell.CreateShortcut($stopShortcutPath)
    Write-Host "Existing 'Stop CodeStruct Prototype' shortcut target: $($sc.TargetPath)" -ForegroundColor Gray
}

$stopShortcut = $wshShell.CreateShortcut($stopShortcutPath)
$stopShortcut.TargetPath = $StopCmd
$stopShortcut.WorkingDirectory = $LauncherDir
$stopShortcut.Description = "Stop CodeStruct Prototype background services"
$stopShortcut.Save()
Write-Host "[OK] Created/Updated: $stopShortcutPath -> $StopCmd" -ForegroundColor Green
