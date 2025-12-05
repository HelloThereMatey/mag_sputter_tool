# ==============================================================================
# Sputter Control System - Serial Port Detection & Configuration
# ==============================================================================
# This script detects all serial devices (Arduino, RFID, MFCs) and updates
# configuration files automatically. Run this after hardware changes or on
# fresh system installation.
#
# Usage:
#   .\detect_all_ports.ps1 [-Verbose] [-DryRun]
#
# Options:
#   -Verbose   : Show detailed scanning information
#   -DryRun    : Show results without updating config files
# ==============================================================================

param(
    [switch]$Verbose,
    [switch]$DryRun
)

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     Sputter Control - Serial Port Detection & Setup           ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

# Build argument strings
$verboseArg = if ($Verbose) { "--verbose" } else { "" }
$dryRunArg = if ($DryRun) { "--dry-run" } else { "" }

# ==============================================================================
# Step 1: Detect Arduino Mega 2560
# ==============================================================================
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "🔌 Step 1: Detecting Arduino Mega 2560 Relay Controller" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray

$args = @("detect_arduino_port.py", $verboseArg, $dryRunArg) | Where-Object { $_ -ne "" }
& python @args
$arduinoResult = $LASTEXITCODE

if ($arduinoResult -ne 0) {
    Write-Host ""
    Write-Host "❌ Failed to detect Arduino port" -ForegroundColor Red
    Write-Host "   Please check Arduino USB connection and try again" -ForegroundColor Red
    Write-Host ""
    exit 1
}

# Get Arduino port for exclusion in subsequent scans
$arduinoPort = (Get-Content ..\..\sput.yml | Select-String "arduino_port:" | ForEach-Object { $_.ToString().Split(":")[1].Trim().Trim("'`"") })
Write-Host "   ✓ Arduino detected on: $arduinoPort" -ForegroundColor Green

# ==============================================================================
# Step 2: Detect RFID Reader (Raspberry Pi Pico)
# ==============================================================================
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "📡 Step 2: Detecting RFID Reader (Raspberry Pi Pico)" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray

if ($arduinoPort) {
    Write-Host "   Excluding Arduino port: $arduinoPort" -ForegroundColor Gray
    $args = @("detect_rfid_port.py", "--exclude-port", $arduinoPort, $verboseArg, $dryRunArg) | Where-Object { $_ -ne "" }
} else {
    $args = @("detect_rfid_port.py", $verboseArg, $dryRunArg) | Where-Object { $_ -ne "" }
}
& python @args
$rfidResult = $LASTEXITCODE

if ($rfidResult -eq 0) {
    $rfidPort = (Get-Content ..\..\sput.yml | Select-String "rfid_port:" | ForEach-Object { $_.ToString().Split(":")[1].Trim().Trim("'`"") })
    Write-Host "   ✓ RFID reader detected on: $rfidPort" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "⚠️  Warning: RFID reader not detected" -ForegroundColor Yellow
    Write-Host "   The system will work, but card authentication won't be available" -ForegroundColor Yellow
    Write-Host ""
}

# ==============================================================================
# Step 3: Detect Alicat MFC Gas Controllers
# ==============================================================================
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "🌬️  Step 3: Detecting Alicat MFC Gas Controllers (Ar, N2, O2)" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray

# Build exclusion list
$excludeArgs = @()
if ($arduinoPort) {
    $excludeArgs += "--exclude-port"
    $excludeArgs += $arduinoPort
}
if ($rfidResult -eq 0 -and $rfidPort) {
    $excludeArgs += "--exclude-port"
    $excludeArgs += $rfidPort
}

Write-Host "   Excluding ports: $arduinoPort $rfidPort" -ForegroundColor Gray
Set-Location ..\gas_control

$args = @("detect_mfc_ports.py") + $excludeArgs + @($verboseArg, $dryRunArg) | Where-Object { $_ -ne "" }
& python @args
$mfcResult = $LASTEXITCODE

if ($mfcResult -eq 0) {
    Write-Host "   ✓ MFC controllers detected and configured" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "⚠️  Warning: MFC controllers not detected" -ForegroundColor Yellow
    Write-Host "   Sputter mode will not be available without gas control" -ForegroundColor Yellow
    Write-Host ""
}

# ==============================================================================
# Summary
# ==============================================================================
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                  Port Detection Complete                       ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

if (-not $DryRun) {
    Write-Host "📝 Configuration files updated:" -ForegroundColor White
    Write-Host "   • sput.yml (Arduino & RFID ports)" -ForegroundColor Gray
    Write-Host "   • gas_control/config.yml (MFC ports)" -ForegroundColor Gray
    Write-Host ""
    
    Write-Host "🔍 Detected Devices:" -ForegroundColor White
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    
    if ($arduinoResult -eq 0) {
        Write-Host "   ✅ Arduino:      $arduinoPort" -ForegroundColor Green
    } else {
        Write-Host "   ❌ Arduino:      Not detected" -ForegroundColor Red
    }
    
    if ($rfidResult -eq 0) {
        Write-Host "   ✅ RFID Reader:  $rfidPort" -ForegroundColor Green
    } else {
        Write-Host "   ❌ RFID Reader:  Not detected" -ForegroundColor Red
    }
    
    if ($mfcResult -eq 0) {
        Write-Host "   ✅ MFC Units:    See gas_control/config.yml" -ForegroundColor Green
    } else {
        Write-Host "   ❌ MFC Units:    Not detected" -ForegroundColor Red
    }
    
    Write-Host ""
    
    if ($arduinoResult -eq 0) {
        Write-Host "✅ System ready! You can now start the sputter control GUI:" -ForegroundColor Green
        Write-Host "   cd .." -ForegroundColor Cyan
        Write-Host "   python main.py" -ForegroundColor Cyan
    } else {
        Write-Host "⚠️  Arduino not detected - GUI cannot start without relay controller" -ForegroundColor Yellow
        Write-Host "   Please connect Arduino and run this script again" -ForegroundColor Yellow
    }
} else {
    Write-Host "🔍 DRY RUN MODE - No configuration files were modified" -ForegroundColor Yellow
    Write-Host "   Remove -DryRun flag to apply changes" -ForegroundColor Yellow
}

Write-Host ""
