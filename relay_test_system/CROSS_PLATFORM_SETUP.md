# Cross-Platform Setup for PyQt5 Relay Control System

This relay test system now supports Windows, Linux, and Raspberry Pi. Follow the platform-specific instructions below.

## System Requirements

- Python 3.7 or higher
- PyQt5
- pyserial
- Arduino Mega 2560 with uploaded firmware

## Platform-Specific Setup

### Windows 10/11

1. **Install Python dependencies:**
   ```cmd
   pip install -r requirements.txt
   ```

2. **Connect Arduino:**
   - Arduino will appear as COM ports (COM3, COM4, etc.)
   - Check Device Manager > Ports (COM & LPT) if needed

3. **Run the application:**
   ```cmd
   python main.py
   ```

### Linux (Ubuntu/Debian)

1. **Install system packages:**
   ```bash
   sudo apt update
   sudo apt install python3-pip python3-dev
   ```

2. **Install Python dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```
   
   Alternative for system packages:
   ```bash
   conda install pyqt  # Now available in conda-forge!
   ```

3. **Set up user permissions:**
   ```bash
   # Add user to dialout group for serial port access
   sudo usermod -a -G dialout $USER
   
   # Logout and login again for changes to take effect
   ```

4. **Check Arduino connection:**
   ```bash
   # Check if Arduino is detected
   lsusb | grep -i arduino
   
   # Look for serial devices
   ls -la /dev/tty* | grep -E '(ACM|USB)'
   ```

5. **Run the application:**
   ```bash
   python3 main.py
   ```

### Raspberry Pi (Raspberry Pi OS)

1. **Update system:**
   ```bash
   sudo apt update && sudo apt upgrade
   ```

2. **Install dependencies:**
   ```bash
   # Install system packages
   conda install pyqt  # PyQt5 available via conda-forge
   
   # Install Python packages
   pip3 install pyserial
   ```

3. **Set up permissions:**
   ```bash
   # Add user to dialout group
   sudo usermod -a -G dialout $USER
   
   # Check current groups
   groups $USER
   
   # Logout and login again
   ```

4. **Connect Arduino:**
   - On Raspberry Pi, Arduino typically appears as `/dev/ttyACM0` or `/dev/ttyUSB0`
   - Check connection: `dmesg | tail` after plugging in Arduino

5. **Run the application:**
   ```bash
   python3 main.py
   ```

## Testing and Troubleshooting

### Quick System Test
```bash
python3 setup_test.py
```

### Cross-Platform Detection Test
```bash
python3 platform_test.py
```

### Manual Port Testing
```bash
python3 port_tester.py
```

### Common Issues

#### Linux/Raspberry Pi: Permission Denied
```
Error: [Errno 13] Permission denied: '/dev/ttyACM0'
```

**Solution:**
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER

# Verify group membership
groups $USER

# Logout and login again
```

#### Linux: No Serial Ports Found
**Check USB connection:**
```bash
lsusb | grep -i arduino
dmesg | tail
```

**Look for devices:**
```bash
ls -la /dev/tty* | grep -E '(ACM|USB)'
```

#### Windows: Arduino Not Detected
- Check Device Manager > Ports (COM & LPT)
- Install Arduino drivers from Arduino IDE
- Try different USB cable/port

## Platform-Specific Port Names

| Platform | Typical Port Names | Example |
|----------|-------------------|---------|
| Windows | COM1, COM2, etc. | COM3 |
| Linux | /dev/ttyACM*, /dev/ttyUSB* | /dev/ttyACM0 |
| Raspberry Pi | /dev/ttyACM*, /dev/ttyUSB* | /dev/ttyACM0 |
| macOS | /dev/cu.usbmodem*, /dev/cu.usbserial* | /dev/cu.usbmodem14101 |

## Hardware Notes

### Arduino Connection
- Arduino Mega 2560 recommended
- USB cable for communication and power
- Upload the firmware from `arduino/relay_controller/relay_controller.ino`

### Relay Modules
- Connect relay modules to pins 22-37 (for relays 1-16)
- Additional relays 17-20 use pins 44-47
- Ensure proper power supply for relay modules

## Performance Notes

### Raspberry Pi Optimization
- For better GUI performance on Raspberry Pi:
  ```bash
  # Enable GPU memory split
  sudo raspi-config
  # Advanced Options > Memory Split > 128
  ```

### Linux/Pi Auto-login (Optional)
- To avoid permission issues, enable auto-login in raspi-config
- Or run application with: `sudo python3 main.py` (not recommended for production)

## Development

### Adding New Platforms
The auto-detection logic in `arduino_controller.py` can be extended for additional platforms by modifying the `_sort_ports_by_likelihood()` method.

### Debugging Serial Issues
Use the provided test scripts:
- `platform_test.py` - Comprehensive platform analysis
- `port_tester.py` - Manual port testing
- `setup_test.py` - System setup verification
