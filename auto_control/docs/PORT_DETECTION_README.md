# Serial Port Detection and Configuration

This document explains the automated port detection system for all serial devices in the sputter control system.

## Overview

The system uses **hardcoded port configuration** for reliable startup, with automated detection scripts to configure ports during initial setup or after hardware changes. This approach:

- ✅ Eliminates startup delays from port scanning
- ✅ Prevents port conflicts between multiple serial devices
- ✅ Reduces serial communication timeouts
- ✅ Provides consistent, reproducible configuration

## Serial Devices

The system communicates with three types of serial devices:

1. **Arduino Mega 2560** - Relay controller (23 relays, 4 digital inputs, 4 analog inputs)
2. **Raspberry Pi Pico** - RFID card reader (USB serial, 115200 baud)
3. **Alicat MFCs** - Gas flow controllers (3 units: Ar, N2, O2 on shared serial bus)

## Configuration Files

### sput.yml (Arduino & RFID)

Main configuration file (`auto_control/sput.yml`):

```yaml
serial:
  baud: 9600
  
  # Hardcoded serial port for Arduino Mega 2560
  arduino_port: '/dev/ttyACM0'  # Windows: COMx, Linux: /dev/ttyACMx
  
  # Hardcoded serial port for RFID reader (Raspberry Pi Pico)
  rfid_port: '/dev/ttyACM1'  # Windows: COMx, Linux: /dev/ttyACMx
  
  # Fallback ports (deprecated - prefer hardcoded)
  preferred_ports: [/dev/ttyACM0, /dev/ttyUSB3]
```

### gas_control/config.yml (MFCs)

Gas controller configuration (`auto_control/python/gas_control/config.yml`):

```yaml
mfcs:
  Ar:
    unit_id: 'A'
    serial_port: '/dev/ttyUSB0'
    max_flow: 200.0
    
  N2:
    unit_id: 'B'
    serial_port: '/dev/ttyUSB0'  # Often shared port
    max_flow: 100.0
    
  O2:
    unit_id: 'C'
    serial_port: '/dev/ttyUSB0'
    max_flow: 100.0
```

## Automated Setup Script

### Quick Start - One Command Setup

The `setup_ports.sh` (Linux/Mac) or `detect_all_ports.ps1` (Windows) script detects and configures all three device types automatically.

**Location:** `auto_control/python/setup_ports.sh` (or `port_setup/detect_all_ports.ps1`)

**Usage:**

```bash
# Linux/Mac - Full detection and configuration
cd auto_control/python
./setup_ports.sh

# With options
./setup_ports.sh --verbose    # Show detailed scanning info
./setup_ports.sh --dry-run    # Preview without updating config
```

```powershell
# Windows PowerShell - Full detection and configuration
cd auto_control\python\port_setup
.\detect_all_ports.ps1

# With options
.\detect_all_ports.ps1 -Verbose   # Show detailed scanning info
.\detect_all_ports.ps1 -DryRun    # Preview without updating config
```

**What it does:**
1. Detects Arduino Mega 2560 and updates `sput.yml`
2. Detects RFID reader (excluding Arduino port) and updates `sput.yml`
3. Detects MFC controllers (excluding Arduino & RFID) and updates `gas_control/config.yml`
4. Displays summary of all detected devices
5. Verifies system is ready to start

**Example output:**
```
╔════════════════════════════════════════════════════════════════╗
║     Sputter Control - Serial Port Detection & Setup           ║
╚════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔌 Step 1: Detecting Arduino Mega 2560 Relay Controller
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✓ Arduino detected on: /dev/ttyACM0

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📡 Step 2: Detecting RFID Reader (Raspberry Pi Pico)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✓ RFID reader detected on: /dev/ttyACM1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌬️  Step 3: Detecting Alicat MFC Gas Controllers (Ar, N2, O2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✓ MFC controllers detected and configured

╔════════════════════════════════════════════════════════════════╗
║                  Port Detection Complete                       ║
╚════════════════════════════════════════════════════════════════╝

🔍 Detected Devices:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ Arduino:      /dev/ttyACM0
   ✅ RFID Reader:  /dev/ttyACM1
   ✅ MFC Units:    See gas_control/config.yml

✅ System ready! You can now start the sputter control GUI:
   cd ..
   python main.py
```

## Individual Detection Scripts

Scripts are located in `auto_control/python/port_setup/` for modular use.

### detect_arduino_port.py

Detects Arduino Mega 2560 relay controller.

**Usage:**
```bash
cd port_setup
python detect_arduino_port.py                        # Detect and configure
python detect_arduino_port.py --verbose              # Detailed output
python detect_arduino_port.py --dry-run              # Preview only
python detect_arduino_port.py --exclude-port COM5    # Skip specific port
```

**Detection method:**
- Scans all serial ports, filters HID devices
- Prioritizes ACM ports and Arduino VID (0x2341, 0x2A03)
- Sends `GET_RELAY_STATES` command
- Verifies `RELAY_STATES:` response
- Updates `sput.yml` with detected port

### detect_rfid_port.py

Detects Raspberry Pi Pico RFID reader.

**Usage:**
```bash
cd port_setup
python detect_rfid_port.py                              # Detect and configure
python detect_rfid_port.py --exclude-port /dev/ttyACM0  # Exclude Arduino
python detect_rfid_port.py --verbose                    # Detailed output
python detect_rfid_port.py --dry-run                    # Preview only
```

**Detection method:**
- Filters HID devices, prioritizes USB Serial/ACM ports
- Toggles DTR to reset Pico
- Waits for `PICO_RFID_READY` startup message (115200 baud)
- Updates `sput.yml` with detected port

### detect_mfc_ports.py

Detects Alicat MFC gas flow controllers.

**Location:** `auto_control/python/gas_control/detect_mfc_ports.py`

**Usage:**
```bash
cd gas_control
python detect_mfc_ports.py                                    # Detect all MFCs
python detect_mfc_ports.py --exclude-port /dev/ttyACM0        # Exclude Arduino
python detect_mfc_ports.py --exclude-port /dev/ttyACM1        # Exclude RFID
python detect_mfc_ports.py --verbose                          # Detailed output
python detect_mfc_ports.py --dry-run                          # Preview only
```

**Detection method:**
- Requires `alicat` CLI tool (`pip install alicat`)
- Scans ports for unit IDs: A (Ar), B (N2), C (O2)
- Tests each port with `alicat <port> --unit <id>` command
- Updates `gas_control/config.yml` with detected ports

## Initial System Setup

**First-time setup on new hardware:**

1. **Connect all devices:**
   - Arduino Mega 2560 via USB
   - Raspberry Pi Pico (RFID) via USB
   - Alicat MFC controllers via USB-to-serial adapter(s)

2. **Run automated setup:**
   ```bash
   cd auto_control/python
   ./setup_ports.sh
   ```
   
   Or on Windows:
   ```powershell
   cd auto_control\python\port_setup
   .\detect_all_ports.ps1
   ```

3. **Verify configuration:**
   ```bash
   # Check Arduino & RFID ports
   grep -A 5 "serial:" auto_control/sput.yml
   
   # Check MFC ports
   grep -A 3 "serial_port:" auto_control/python/gas_control/config.yml
   ```

4. **Start application:**
   ```bash
   cd auto_control/python
   python main.py
   ```

## System Startup Behavior

### Connection Priority

When the GUI starts, each serial device attempts connection in this order:

1. **Hardcoded port** from config file (fastest, most reliable)
2. **Cached port** from previous session (`~/.sputter_control/`)
3. **Auto-detection** scan (slowest, fallback only)

### Code Locations

- **Arduino:** `arduino_controller.py:auto_connect()` - Uses `config_port` parameter
- **RFID:** `widgets/login_dialog.py:_start_rfid_reader()` - Loads `cfg.serial.rfid_port`
- **MFCs:** `gas_control/controller.py` - Reads ports from `gas_control/config.yml`

## Troubleshooting

### Arduino Not Detected

**Symptoms:**
- "No Arduino found" error
- Timeout waiting for responses
- GUI fails to start

**Solutions:**

1. **Run detection script:**
   ```bash
   cd auto_control/python/port_setup
   python detect_arduino_port.py --verbose
   ```

2. **Check USB connection:**
   - **Linux:** `dmesg | tail` (look for ttyACM or ttyUSB)
   - **Windows:** Device Manager → Ports (COM & LPT)
   - Verify Arduino shows up as new device

3. **Verify firmware:**
   - Upload `relay_controller.ino` to Arduino
   - Test with Arduino IDE Serial Monitor (9600 baud)
   - Type `GET_RELAY_STATES` - should see response

4. **Check permissions (Linux only):**
   ```bash
   sudo usermod -a -G dialout $USER
   # Log out and back in for group change to take effect
   ```

5. **Test manually:**
   ```bash
   # Linux
   screen /dev/ttyACM0 9600
   
   # Windows - use PuTTY or Arduino Serial Monitor
   ```

### RFID Reader Not Found

**Symptoms:**
- "RFID reader not found" message during login
- 15-second initialization delays
- Falls back to password-only authentication

**Solutions:**

1. **Run detection script:**
   ```bash
   cd auto_control/python/port_setup
   python detect_rfid_port.py --exclude-port /dev/ttyACM0 --verbose
   ```

2. **Verify Pico firmware:**
   - Upload `pico_rfid_serial.py` to Raspberry Pi Pico
   - Pico must send `PICO_RFID_READY` on startup/reset

3. **Test manually:**
   ```bash
   # Linux - should see ready message after DTR reset
   screen /dev/ttyACM1 115200
   
   # Windows - use PuTTY at 115200 baud
   # Toggle DTR in settings to see ready message
   ```

4. **Check for conflicts:**
   - Ensure RFID port differs from Arduino port
   - Run `lsusb` (Linux) to verify both devices present

### MFC Controllers Not Detected

**Symptoms:**
- "MFC not found" warnings
- Sputter mode unavailable
- Gas flow setpoints don't work

**Solutions:**

1. **Install alicat CLI tool:**
   ```bash
   pip install alicat
   ```

2. **Run detection script:**
   ```bash
   cd auto_control/python/gas_control
   python detect_mfc_ports.py --exclude-port /dev/ttyACM0 --exclude-port /dev/ttyACM1 --verbose
   ```

3. **Test MFC communication manually:**
   ```bash
   # Test Argon (unit A) on port /dev/ttyUSB0
   alicat /dev/ttyUSB0 --unit A
   
   # Should return flow rate and device info
   ```

4. **Check wiring:**
   - MFCs usually share single serial port (RS-485/RS-232)
   - Verify USB-to-serial adapter is recognized
   - Check baud rate (typically 19200)

### Ports Changed After Reboot/Reconnection

**Symptoms:**
- Previously working configuration fails after USB reconnect
- Error: "Port /dev/ttyACM0 not found"

**Solutions:**

1. **Re-run setup script:**
   ```bash
   cd auto_control/python
   ./setup_ports.sh
   ```

2. **Create udev rules for persistent naming (Linux advanced):**
   ```bash
   # Find device serial numbers
   udevadm info --name=/dev/ttyACM0 | grep SERIAL
   
   # Create rule in /etc/udev/rules.d/99-sputter.rules
   SUBSYSTEM=="tty", ATTRS{serial}=="ABC123", SYMLINK+="arduino_relay"
   SUBSYSTEM=="tty", ATTRS{serial}=="XYZ789", SYMLINK+="rfid_reader"
   
   # Reload rules
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   
   # Update sput.yml to use symlinks:
   arduino_port: '/dev/arduino_relay'
   rfid_port: '/dev/rfid_reader'
   ```

### Multiple Devices on Same Port

**Symptoms:**
- Detection script reports conflicting devices
- Intermittent connection failures

**Solution:**
- Linux typically assigns different device nodes (ACM0, ACM1, USB0, USB1)
- If devices truly share a port (MFCs do this intentionally), verify unit IDs differ
- Use `--exclude-port` flags when running detection scripts

## Platform-Specific Notes

### Linux (Raspberry Pi)

**Typical port assignments:**
```
Arduino:    /dev/ttyACM0
RFID Pico:  /dev/ttyACM1
MFC units:  /dev/ttyUSB0 (all three share port, differ by unit ID)
```

**Permissions:**
```bash
# Add user to dialout group for serial port access
sudo usermod -a -G dialout sput

# Verify membership
groups sput

# Log out and back in for changes to take effect
```

**Check connected devices:**
```bash
# List USB devices
lsusb

# Monitor USB connect/disconnect events
dmesg -w

# List serial ports
ls -l /dev/tty{ACM,USB}*
```

### Windows

**Typical port assignments:**
```
Arduino:    COM3, COM4, COM5, etc.
RFID Pico:  COM6, COM7, etc.
MFC units:  COM8, COM9, etc. (or shared port)
```

**Identifying devices:**
1. Open Device Manager (`devmgmt.msc`)
2. Expand "Ports (COM & LPT)"
3. Arduino shows as "Arduino Mega 2560"
4. Pico shows as "USB Serial Device"
5. MFC adapter shows as "USB-to-Serial" or specific adapter name

**Change COM port (if needed):**
1. Right-click device → Properties
2. Port Settings tab → Advanced
3. COM Port Number dropdown
4. Restart application after change

## Best Practices

### 1. Run Detection After Hardware Changes

Always re-run `setup_ports.sh` after:
- Fresh OS installation
- USB port changes
- Hardware replacement
- System migration to new machine

### 2. Document Your Configuration

Add comments to config files for non-standard setups:

```yaml
# sput.yml
serial:
  arduino_port: '/dev/ttyACM0'  # Arduino Mega on USB hub port 2
  rfid_port: '/dev/ttyACM1'     # Pico on USB hub port 3
```

### 3. Use Exclusion Flags

When running individual detection scripts, exclude known ports:

```bash
# Detecting RFID - exclude Arduino
python detect_rfid_port.py --exclude-port /dev/ttyACM0

# Detecting MFCs - exclude Arduino and RFID
cd gas_control
python detect_mfc_ports.py --exclude-port /dev/ttyACM0 --exclude-port /dev/ttyACM1
```

### 4. Keep Backups

Before major changes:
```bash
cp sput.yml sput.yml.backup
cp gas_control/config.yml gas_control/config.yml.backup
```

### 5. Version Control

For team environments:
- Commit working configs to repository
- Use machine-specific configs with `.gitignore` if needed
- Document port assignments in commit messages

## Files and Locations

**Configuration files:**
- `auto_control/sput.yml` - Arduino & RFID ports
- `auto_control/python/gas_control/config.yml` - MFC ports

**Detection scripts:**
- `auto_control/python/setup_ports.sh` - Unified setup (Linux/Mac)
- `auto_control/python/port_setup/detect_all_ports.ps1` - Unified setup (Windows)
- `auto_control/python/port_setup/detect_arduino_port.py` - Arduino only
- `auto_control/python/port_setup/detect_rfid_port.py` - RFID only
- `auto_control/python/gas_control/detect_mfc_ports.py` - MFC only

**Application code:**
- `auto_control/python/config.py` - Config loader (`SerialConfig` dataclass)
- `auto_control/python/arduino_controller.py` - Arduino communication
- `auto_control/python/widgets/login_dialog.py` - RFID initialization
- `auto_control/python/gas_control/controller.py` - MFC communication

**Cache files (auto-generated):**
- `~/.sputter_control/last_arduino_port.txt` - Cached Arduino port
- `~/.sputter_control/rfid_port.txt` - Cached RFID port

## Quick Reference

**Full system setup:**
```bash
cd auto_control/python
./setup_ports.sh
```

**Individual device detection:**
```bash
cd auto_control/python/port_setup
python detect_arduino_port.py
python detect_rfid_port.py --exclude-port /dev/ttyACM0
cd ../gas_control
python detect_mfc_ports.py --exclude-port /dev/ttyACM0 --exclude-port /dev/ttyACM1
```

**Test manually:**
```bash
# Arduino (9600 baud)
screen /dev/ttyACM0 9600
> GET_RELAY_STATES

# RFID (115200 baud)
screen /dev/ttyACM1 115200
# Should see PICO_RFID_READY on DTR toggle

# MFC (19200 baud)
alicat /dev/ttyUSB0 --unit A
```

**Verify configuration:**
```bash
grep -A 5 "serial:" auto_control/sput.yml
grep "serial_port:" auto_control/python/gas_control/config.yml
```
