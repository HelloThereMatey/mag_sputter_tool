# Relay Test System

Full-stack relay testing application for the Magnetron Sputtering System Control Upgrade Project. This system provides a PyQt5 GUI interface to control 16 relays via an Arduino Mega 2560 through serial communication.

## Project Structure

```
relay_test_system/
├── arduino/
│   └── relay_controller.ino     # Arduino firmware
├── python/
│   ├── main.py                  # Application entry point
│   ├── gui.py                   # PyQt5 GUI implementation
│   ├── arduino_controller.py    # Arduino communication controller
│   └── requirements.txt         # Python dependencies
└── README.md                    # This file
```

## Hardware Requirements

- **Arduino Mega 2560 R3**
- **16-channel relay module** (or individual relays)
- **USB cable** for Arduino connection
- **24V power supply** for relay coils (if using external relays)
- **Jumper wires** for connections

## Pin Mapping (Arduino Mega 2560)

The firmware uses digital pins 22-37 for relay control:

```
Relay 1  -> Pin 22    Relay 9  -> Pin 30
Relay 2  -> Pin 23    Relay 10 -> Pin 31
Relay 3  -> Pin 24    Relay 11 -> Pin 32
Relay 4  -> Pin 25    Relay 12 -> Pin 33
Relay 5  -> Pin 26    Relay 13 -> Pin 34
Relay 6  -> Pin 27    Relay 14 -> Pin 35
Relay 7  -> Pin 28    Relay 15 -> Pin 36
Relay 8  -> Pin 29    Relay 16 -> Pin 37
```

## Software Setup

### 1. Arduino Setup

1. Install **Arduino IDE** (version 1.8.x or 2.x)
2. Connect Arduino Mega 2560 via USB
3. Open `arduino/relay_controller.ino` in Arduino IDE
4. Select **Board**: "Arduino Mega or Mega 2560"
5. Select correct **Port** (usually COM3, COM4, etc. on Windows)
6. Upload the firmware to Arduino

### 2. Python Environment Setup

#### Option A: Using pip (recommended)
```bash
# Navigate to python directory
cd relay_test_system/python

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

#### Option B: Using conda
```bash
# Create new environment
conda create -n relay_test python=3.9

# Activate environment
conda activate relay_test

# Navigate to python directory
cd relay_test_system/python

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### 3. Dependencies

The Python application requires:
- **PyQt5** - GUI framework
- **pyserial** (3.5) - Serial communication

## Usage Instructions

### Starting the Application

1. **Hardware Setup**:
   - Connect Arduino Mega 2560 to computer via USB
   - Ensure Arduino firmware is uploaded
   - Connect relay modules to designated pins (22-37)

2. **Launch Application**:
   ```bash
   cd relay_test_system/python
   python main.py
   ```

### Using the Interface

#### Connection
1. **Select Port**: Choose Arduino COM port from dropdown
2. **Connect**: Click "Connect" button to establish communication
3. **Status**: Monitor connection status in status bar

#### Relay Control
- **Individual Control**: Click any relay button to toggle ON/OFF
  - **Red** = Relay OFF
  - **Green** = Relay ON
- **Emergency Stop**: Click "ALL RELAYS OFF" for immediate shutdown
- **Status Refresh**: Click "Refresh Status" to sync with Arduino

#### Menu Options
- **Connection Menu**:
  - Connect/Disconnect
  - Refresh Ports
- **Control Menu**:
  - All Relays OFF
- **Help Menu**:
  - About dialog

## Serial Communication Protocol

### Command Format
- **Relay ON**: `RELAY_X_ON` (where X = 1-16)
- **Relay OFF**: `RELAY_X_OFF`
- **All OFF**: `ALL_OFF`
- **Status Query**: `STATUS`

### Response Format
- **Success**: `OK`
- **Error**: `ERROR`
- **Ready**: `ARDUINO_READY`
- **Status**: `STATUS:1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0`

## Features

### Safety Features
- **Automatic Initialization**: All relays start in OFF state
- **Emergency Stop**: Immediate all-off capability
- **Safe Disconnect**: Turns off all relays before disconnecting
- **Error Handling**: Robust error detection and recovery

### User Interface Features
- **Real-time Status**: Live relay state monitoring
- **Visual Feedback**: Color-coded relay buttons
- **Auto-detection**: Automatic Arduino port detection
- **Status Updates**: Continuous connection monitoring

### Technical Features
- **Thread-safe Communication**: Background serial handling
- **Command Queuing**: Reliable command processing
- **Timeout Protection**: Prevents application freezing
- **State Synchronization**: Local and Arduino state tracking

## Troubleshooting

### Common Issues

1. **Arduino Not Detected**:
   - Check USB cable connection
   - Verify Arduino is powered
   - Try different USB port
   - Check Windows Device Manager for COM ports

2. **Connection Failed**:
   - Ensure Arduino firmware is uploaded
   - Check baud rate (should be 9600)
   - Close other applications using the serial port
   - Try manual port selection

3. **Relay Not Responding**:
   - Verify wiring connections
   - Check relay module power supply
   - Test with multimeter for continuity
   - Ensure correct pin mapping

4. **GUI Not Responding**:
   - Check Python dependencies are installed
   - Ensure PyQt5 is properly installed
   - Try running from command line to see error messages

### Debug Mode

To enable verbose debugging, modify `main.py`:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Development Notes

### Code Architecture
- **Modular Design**: Separate files for GUI, Arduino control, and main app
- **Thread Safety**: Background communication thread
- **Error Handling**: Comprehensive exception handling
- **State Management**: Local relay state tracking

### Testing
- Test individual relay operation
- Test rapid command sequences
- Test connection loss/recovery
- Test emergency stop functionality

## Future Enhancements

### Planned Features
- Data logging and export
- Relay timing sequences
- Configuration file support
- Remote network control
- Integration with vacuum system

### Hardware Expansion
- Additional I/O channels
- Analog input processing
- PWM output control
- Sensor integration

## License

This project is part of the Magnetron Sputtering System Control Upgrade Project.
Open source implementation for educational and research purposes.

## Support

For issues or questions related to this relay test system:
1. Check this README for common solutions
2. Verify hardware connections and power
3. Test Arduino firmware independently using Serial Monitor
4. Check Python environment and dependencies

## Version History

- **v1.0** - Initial implementation
  - 16-relay control via Arduino Mega 2560
   - PyQt5 GUI with toggle buttons
  - Serial communication with error handling
  - Emergency stop functionality
