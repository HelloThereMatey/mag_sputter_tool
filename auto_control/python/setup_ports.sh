#!/bin/bash
# ==============================================================================
# Sputter Control System - Serial Port Detection & Configuration
# ==============================================================================
# This script detects all serial devices (Arduino, RFID, MFCs) and updates
# configuration files automatically. Run this after hardware changes or on
# fresh system installation.
#
# Usage:
#   ./setup_ports.sh [--verbose] [--dry-run]
#
# Options:
#   --verbose   : Show detailed scanning information
#   --dry-run   : Show results without updating config files
# ==============================================================================

# Parse command line arguments
VERBOSE=""
DRY_RUN=""
for arg in "$@"; do
    case $arg in
        --verbose)
            VERBOSE="--verbose"
            ;;
        --dry-run)
            DRY_RUN="--dry-run"
            ;;
    esac
done

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     Sputter Control - Serial Port Detection & Setup           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Change to port_setup directory
cd "$(dirname "$0")/port_setup" || exit 1

# ==============================================================================
# Step 1: Detect Arduino Mega 2560
# ==============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔌 Step 1: Detecting Arduino Mega 2560 Relay Controller"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python detect_arduino_port.py $VERBOSE $DRY_RUN
arduino_result=$?

if [ $arduino_result -ne 0 ]; then
    echo ""
    echo "❌ Failed to detect Arduino port"
    echo "   Please check Arduino USB connection and try again"
    echo ""
    exit 1
fi

# Get Arduino port for exclusion in subsequent scans
arduino_port=$(grep "arduino_port:" ../../sput.yml | awk '{print $2}' | tr -d "'\"")
echo "   ✓ Arduino detected on: $arduino_port"

# ==============================================================================
# Step 2: Detect RFID Reader (Raspberry Pi Pico)
# ==============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📡 Step 2: Detecting RFID Reader (Raspberry Pi Pico)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -n "$arduino_port" ]; then
    echo "   Excluding Arduino port: $arduino_port"
    python detect_rfid_port.py --exclude-port "$arduino_port" $VERBOSE $DRY_RUN
else
    python detect_rfid_port.py $VERBOSE $DRY_RUN
fi

rfid_result=$?
if [ $rfid_result -eq 0 ]; then
    rfid_port=$(grep "rfid_port:" ../../sput.yml | awk '{print $2}' | tr -d "'\"")
    echo "   ✓ RFID reader detected on: $rfid_port"
else
    echo ""
    echo "⚠️  Warning: RFID reader not detected"
    echo "   The system will work, but card authentication won't be available"
    echo ""
fi

# ==============================================================================
# Step 3: Detect Alicat MFC Gas Controllers
# ==============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌬️  Step 3: Detecting Alicat MFC Gas Controllers (Ar, N2, O2)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Build exclusion list
exclude_args=""
if [ -n "$arduino_port" ]; then
    exclude_args="--exclude-port $arduino_port"
fi
if [ $rfid_result -eq 0 ] && [ -n "$rfid_port" ]; then
    exclude_args="$exclude_args --exclude-port $rfid_port"
fi

echo "   Excluding ports: $arduino_port $rfid_port"
cd ../gas_control || exit 1
python detect_mfc_ports.py $exclude_args $VERBOSE $DRY_RUN
mfc_result=$?

if [ $mfc_result -eq 0 ]; then
    echo "   ✓ MFC controllers detected and configured"
else
    echo ""
    echo "⚠️  Warning: MFC controllers not detected"
    echo "   Sputter mode will not be available without gas control"
    echo ""
fi

# ==============================================================================
# Summary
# ==============================================================================
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                  Port Detection Complete                       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

if [ -z "$DRY_RUN" ]; then
    echo "📝 Configuration files updated:"
    echo "   • sput.yml (Arduino & RFID ports)"
    echo "   • gas_control/config.yml (MFC ports)"
    echo ""
    
    echo "🔍 Detected Devices:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if [ $arduino_result -eq 0 ]; then
        echo "   ✅ Arduino:      $arduino_port"
    else
        echo "   ❌ Arduino:      Not detected"
    fi
    
    if [ $rfid_result -eq 0 ]; then
        echo "   ✅ RFID Reader:  $rfid_port"
    else
        echo "   ❌ RFID Reader:  Not detected"
    fi
    
    if [ $mfc_result -eq 0 ]; then
        echo "   ✅ MFC Units:    See gas_control/config.yml"
    else
        echo "   ❌ MFC Units:    Not detected"
    fi
    
    echo ""
    
    if [ $arduino_result -eq 0 ]; then
        echo "✅ System ready! You can now start the sputter control GUI:"
        echo "   cd .."
        echo "   python main.py"
    else
        echo "⚠️  Arduino not detected - GUI cannot start without relay controller"
        echo "   Please connect Arduino and run this script again"
    fi
else
    echo "🔍 DRY RUN MODE - No configuration files were modified"
    echo "   Remove --dry-run flag to apply changes"
fi

echo ""
