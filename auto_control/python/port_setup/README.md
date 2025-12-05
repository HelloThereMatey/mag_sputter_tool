# Port Setup Scripts

This folder contains automated serial port detection scripts for the sputter control system.

## Quick Start

**One-command setup for all devices:**

```bash
# Linux/Mac - run from auto_control/python/
cd ..
./setup_ports.sh

# Windows - run from this folder
.\detect_all_ports.ps1
```

This will detect and configure:
1. Arduino Mega 2560 (relay controller)
2. Raspberry Pi Pico (RFID reader)
3. Alicat MFC units (gas controllers)

## Scripts

### detect_all_ports.ps1 (Windows)
Unified detection script for all three device types.

**Usage:**
```powershell
.\detect_all_ports.ps1           # Full auto-detection
.\detect_all_ports.ps1 -Verbose  # Show detailed info
.\detect_all_ports.ps1 -DryRun   # Preview without changes
```

### detect_arduino_port.py
Detects Arduino Mega 2560 relay controller, updates `../../sput.yml`.

**Usage:**
```bash
python detect_arduino_port.py [--verbose] [--dry-run]
```

### detect_rfid_port.py
Detects Raspberry Pi Pico RFID reader, updates `../../sput.yml`.

**Usage:**
```bash
python detect_rfid_port.py [--exclude-port PORT] [--verbose] [--dry-run]
```

### Legacy Scripts

- `detect_ports.sh` - Old detection script (deprecated)
- `detect_ports.bat` - Old Windows batch script (deprecated)

These are kept for reference but should not be used. Use the scripts above instead.

## When to Run

Run the setup script when:
- Setting up the system on a new machine
- USB ports change after reconnection
- Replacing hardware components
- After OS reinstallation

## Configuration Output

Scripts update these configuration files:
- `../../sput.yml` - Arduino and RFID ports
- `../gas_control/config.yml` - MFC controller ports

## Full Documentation

See `../../docs/PORT_DETECTION_README.md` for complete documentation including:
- Detailed troubleshooting
- Platform-specific notes
- Manual testing procedures
- Advanced configuration options

## Requirements

**Python packages:**
```bash
pip install pyserial pyyaml
pip install alicat  # For MFC detection only
```

**Hardware:**
- Arduino Mega 2560 with `relay_controller.ino` firmware
- Raspberry Pi Pico with `pico_rfid_serial.py` firmware
- Alicat MFC controllers (optional, for sputter mode)

## Example Output

```
╔════════════════════════════════════════════════════════════════╗
║     Sputter Control - Serial Port Detection & Setup           ║
╚════════════════════════════════════════════════════════════════╝

🔌 Step 1: Detecting Arduino Mega 2560 Relay Controller
   ✓ Arduino detected on: /dev/ttyACM0

📡 Step 2: Detecting RFID Reader (Raspberry Pi Pico)
   ✓ RFID reader detected on: /dev/ttyACM1

🌬️  Step 3: Detecting Alicat MFC Gas Controllers (Ar, N2, O2)
   ✓ MFC controllers detected and configured

✅ System ready! You can now start the sputter control GUI:
   cd ..
   python main.py
```

## Troubleshooting

**Arduino not found:**
```bash
# Check USB connection
dmesg | tail          # Linux
# Device Manager      # Windows

# Verify firmware uploaded
# Use Arduino IDE Serial Monitor, send: GET_RELAY_STATES
```

**RFID not found:**
```bash
# Test manually
screen /dev/ttyACM1 115200  # Should see PICO_RFID_READY
```

**MFC not found:**
```bash
# Verify alicat CLI installed
pip install alicat

# Test manually
alicat /dev/ttyUSB0 --unit A
```

**Permissions error (Linux):**
```bash
sudo usermod -a -G dialout $USER
# Log out and back in
```

For detailed troubleshooting, see `../../docs/PORT_DETECTION_README.md`.
