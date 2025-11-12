# RFID Integration Guide

## Overview

The Magnetron Sputter Control System now includes integrated RFID card reading capabilities for user authentication. The system uses a **Raspberry Pi Pico** with an RFID reader module that communicates via USB serial to the main control system (Raspberry Pi 5).

### Key Features

✅ **Automatic RFID Detection** - System auto-detects Pico RFID reader on startup
✅ **Quick Card Login** - Present RFID card to automatically log in registered users
✅ **RFID Enrollment** - New users can enroll their RFID card during account creation
✅ **RFID/Password Hybrid** - Supports both RFID and traditional password authentication
✅ **Thread-Safe** - RFID reader runs in background thread without blocking GUI
✅ **Fallback Support** - Manual login available if RFID reader unavailable

---

## Hardware Setup

### Required Components

- **Raspberry Pi Pico** (RP2040 microcontroller)
- **I2C RFID Reader Module** (e.g., PiicoDev RFID)
- **USB Cable** (Pico to Raspberry Pi 5)

### Wiring

```
Pico I2C Pins:
  GP0 (SDA) -> RFID Module SDA
  GP1 (SCL) -> RFID Module SCL
  GND       -> RFID Module GND
  
Pico USB:
  Micro USB -> Raspberry Pi 5 USB Port
```

### Pico Firmware

Upload the RFID reader firmware to Pico:

```python
# File: pico_rfid_serial.py
# Copy to Pico as main.py

from PiicoDev_RFID import PiicoDev_RFID
from PiicoDev_Unified import sleep_ms
import time

rfid = PiicoDev_RFID()
last_card_id = None
last_read_time = 0

print("PICO_RFID_READY:v1.0")

while True:
    if rfid.tagPresent():
        card_id = rfid.readID()
        current_time = time.ticks_ms()
        
        if card_id != last_card_id or (current_time - last_read_time) > 500:
            print(card_id)
            last_card_id = card_id
            last_read_time = current_time
    
    sleep_ms(100)
```

---

## Software Architecture

### Module Structure

```
auto_control/
├── python/
│   ├── rfid/                    # NEW RFID Package
│   │   ├── __init__.py
│   │   ├── config.py            # RFID configuration & port detection
│   │   └── reader_thread.py     # Background RFID reader thread
│   ├── security/
│   │   └── user_account_manager.py  # UPDATED: RFID methods
│   ├── widgets/
│   │   └── login_dialog.py      # UPDATED: RFID integration
│   └── ...
```

### Class Hierarchy

#### RFIDConfig
- **Purpose**: RFID hardware configuration and port auto-detection
- **Key Methods**:
  - `find_rfid_port()` - Auto-detect Pico RFID reader serial port
  - `try_cached_port()` - Use previously successful port
  - `get_available_ports()` - List all serial ports

#### RFIDReaderThread
- **Purpose**: Background thread for reading RFID cards
- **Inherits**: `QThread` (PyQt5)
- **Signals**:
  - `card_detected(str)` - Emitted when card is read
  - `device_ready()` - Emitted when Pico is initialized
  - `device_lost()` - Emitted when connection lost
  - `error_occurred(str)` - Emitted on error
  - `status_changed(str)` - Status updates
- **Key Methods**:
  - `run()` - Main thread loop
  - `stop()` - Gracefully stop thread
  - `is_connected()` - Check connection status

#### UserAccountManager (UPDATED)
- **New RFID Methods**:
  - `enroll_rfid_card(username, card_id)` - Register card for user
  - `authenticate_by_rfid(card_id)` - Auto-login by card ID
  - `remove_rfid_card(username)` - Unenroll card
  - `get_rfid_card_id(username)` - Get user's card ID

#### LoginDialog (UPDATED)
- **New Features**:
  - RFID reader startup on dialog init
  - Real-time RFID status display
  - Auto-login on card detection
  - RFID enrollment during account creation
  - Graceful RFID thread shutdown on dialog close

---

## User Workflow

### 1. System Startup

```
┌─────────────────────────────────────────────────┐
│  App Launch                                     │
├─────────────────────────────────────────────────┤
│  ↓                                              │
│  LoginDialog created                            │
│  ↓                                              │
│  RFID reader thread started in background       │
│  ↓                                              │
│  Pico detected on serial port                   │
│  ↓                                              │
│  RFID reader ready for cards                    │
│  ↓                                              │
│  Status: "✓ RFID ready - Present card to login" │
└─────────────────────────────────────────────────┘
```

### 2. RFID Auto-Login

```
User presents RFID card:
  ↓
Card detected by Pico
  ↓
Card ID read via serial
  ↓
RFIDReaderThread emits card_detected signal
  ↓
LoginDialog._on_rfid_card_detected() called
  ↓
Database lookup: authenticate_by_rfid(card_id)
  ↓
  IF card found:
    ├─ Retrieve user info
    ├─ Update login stats
    └─ Auto-login & close dialog
  ELSE:
    └─ Show message "Card not registered"
```

### 3. New Account with RFID Enrollment

```
Click "Create Account":
  ↓
Enter username & password
  ↓
Account created
  ↓
Prompt: "Enroll RFID card?"
  ↓
  IF user clicks YES:
    ├─ Show "Present card now"
    ├─ Wait for card detection (30s timeout)
    ├─ When card detected:
    │   ├─ Call enroll_rfid_card(username, card_id)
    │   ├─ Store card ID in database
    │   └─ Confirm success
    └─ Resume login form
  ELSE:
    └─ Skip enrollment, return to login
```

---

## Database Schema (RFID Fields)

User records now include RFID fields:

```json
{
  "username_lower": {
    "username": "john_doe",
    "password_hash": "...",
    "password_salt": "...",
    "admin_level": 1,
    "created_date": "2025-11-11T10:30:00",
    "rfid_card_id": "08:5C:D1:4C",           // NEW: Card ID
    "rfid_enrolled_date": "2025-11-11T10:35:00",  // NEW: When enrolled
    "last_login": "2025-11-11T14:20:00",
    "last_login_method": "rfid_card",       // NEW: rfid_card or password
    "login_count": 5
  }
}
```

---

## Configuration

### RFID Settings

Edit `python/rfid/config.py`:

```python
class RFIDConfig:
    DEFAULT_BAUDRATE = 115200       # Pico serial speed
    READY_MESSAGE = "PICO_RFID_READY"  # Expected startup message
    CARD_ID_TIMEOUT = 5.0           # Timeout for card ID read
    PORT_CACHE_FILE = ...           # Location of port cache
```

### Platform-Specific Port Detection

The system auto-detects the Pico on different platforms:

**Windows:**
- Looks for "USB Serial Device"
- Falls back to COMX ports in reverse order
- Avoids system ports (Intel, Management)

**Linux/Raspberry Pi:**
- Prefers `/dev/ttyACM0` (CDC ACM)
- Falls back to `/dev/ttyUSB0` (USB serial)

**Port Caching:**
- Successful port is cached in `~/.sputter_control/rfid_port.txt`
- Used for faster reconnection on next startup

---

## API Reference

### RFIDConfig

```python
from rfid import RFIDConfig

# Auto-detect Pico
port = RFIDConfig.find_rfid_port()

# Try cached port first
cached = RFIDConfig.try_cached_port()

# Get all available ports
ports = RFIDConfig.get_available_ports()
# Returns: [("COM5", "USB Serial Device"), ...]

# Clear cache if port changes
RFIDConfig.clear_port_cache()
```

### RFIDReaderThread

```python
from rfid import RFIDReaderThread

# Create and configure
reader = RFIDReaderThread()
reader.set_port("COM5")           # Optional, auto-detects if not set
reader.set_baudrate(115200)       # Default is correct

# Connect signals
reader.card_detected.connect(on_card_detected)
reader.device_ready.connect(on_device_ready)
reader.device_lost.connect(on_device_lost)
reader.error_occurred.connect(on_error)

# Start reading
reader.start()

# Check connection
if reader.is_connected():
    print("RFID reader ready")

# Stop gracefully
reader.stop()
```

### UserAccountManager RFID Methods

```python
from security.user_account_manager import UserAccountManager

uam = UserAccountManager()

# Enroll card for user
success, msg = uam.enroll_rfid_card("john_doe", "08:5C:D1:4C")

# Auto-login by card ID
success, user_info, msg = uam.authenticate_by_rfid("08:5C:D1:4C")
if success:
    print(f"Welcome {user_info['username']}")

# Get user's card ID
card_id = uam.get_rfid_card_id("john_doe")

# Remove card enrollment
success, msg = uam.remove_rfid_card("john_doe")
```

---

## Error Handling

### Connection Failures

| Error | Cause | Action |
|-------|-------|--------|
| RFID reader not found | Pico not connected | Check USB cable, verify Pico has firmware |
| Port permission denied | Linux permissions | Run as sudo or add user to dialout group |
| Timeout waiting for ready | Pico firmware issue | Re-upload firmware to Pico |
| Card not registered | First-time card | Show message, allow manual login |

### Fallback Behavior

- **RFID unavailable**: System falls back to password login
- **Card not registered**: Users can log in with username/password
- **Pico disconnects**: Automatic reconnection attempts on next card detection
- **Port changes**: System re-detects and caches new port

---

## Troubleshooting

### RFID Reader Not Detected

1. Check Pico is connected via USB
2. Verify Pico has RFID firmware uploaded
3. Check firmware sends `PICO_RFID_READY` message
4. Run as administrator/root if permission errors
5. Clear port cache: `RFIDConfig.clear_port_cache()`

### Cards Not Reading

1. Check RFID module has power (LED indicator)
2. Verify I2C wiring on Pico
3. Test with `pico_rfid_serial.py` directly
4. Check card format matches expected (hex pairs with colons)

### Auto-Login Not Working

1. Verify card is enrolled: `uam.get_rfid_card_id(username)`
2. Check card ID format in database
3. Test with manual username/password login
4. Check RFID thread status in logs

### Performance Issues

- RFID reading should not impact GUI (runs in separate thread)
- Debounce delay prevents duplicate reads (500ms default)
- Serial timeout is 1s to prevent blocking
- Port cache reduces startup time

---

## Security Considerations

### Card ID Security

- **Not a password**: Card ID alone should not grant access in high-security scenarios
- **Consider two-factor**: Ask for PIN in addition to card for sensitive operations
- **Card binding**: Each card enrolled is specific to one user account
- **Card revocation**: Unenroll cards immediately if lost/stolen

### Database Protection

- Card IDs stored in encrypted user database (same encryption as passwords)
- User database protected with Fernet symmetric encryption
- Master password protects user level changes (not needed for basic operations)

### Recommendations

1. **Production**: Combine RFID with secondary authentication (PIN/password)
2. **Access Logs**: Log all RFID logins for audit trail
3. **Card Inventory**: Maintain list of active cards per user
4. **Timeout**: Implement session timeout for unattended logins
5. **Lost Cards**: Have procedure for quickly unenrolling lost cards

---

## Future Enhancements

- [ ] Multiple cards per user
- [ ] Card expiration dates
- [ ] Card disable/suspend without deletion
- [ ] RFID-based access control to specific features
- [ ] Two-factor authentication (RFID + PIN)
- [ ] Card reader hardware status monitoring
- [ ] Analytics: Most common login method (RFID vs password)
- [ ] Integration with system audit log

---

## Testing

### Unit Tests

```python
# Test RFID card enrollment
def test_enroll_card():
    uam = UserAccountManager()
    success, msg = uam.enroll_rfid_card("test_user", "08:5C:D1:4C")
    assert success
    assert uam.get_rfid_card_id("test_user") == "08:5C:D1:4C"

# Test RFID authentication
def test_rfid_auth():
    success, user_info, msg = uam.authenticate_by_rfid("08:5C:D1:4C")
    assert success
    assert user_info['username'] == 'test_user'

# Test unregistered card
def test_unregistered_card():
    success, user_info, msg = uam.authenticate_by_rfid("FF:FF:FF:FF")
    assert not success
```

### Integration Tests

1. **Port Detection**: Verify Pico detected on startup
2. **Card Read**: Present card and verify detection
3. **Auto-Login**: Verify registered card logs in user
4. **Enrollment**: Create account and enroll new card
5. **Fallback**: Unplug Pico and verify password login still works
6. **Thread Safety**: Rapid card reads don't crash GUI

---

## Support and Debugging

### Enable Debug Logging

```python
# In login_dialog.py, add:
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Log RFID events
logger.debug(f"Card detected: {card_id}")
logger.debug(f"RFID thread status: {self.rfid_thread.is_connected()}")
```

### Common Issues

**Issue**: "RFID reader not found"
- Check Pico has firmware with correct baud rate (115200)
- Verify USB cable is connected and functional
- Try different USB port on RPi

**Issue**: "Card detected but no login"
- Verify card ID format in database
- Check `authenticate_by_rfid()` returns user
- Enable debug logging to see card ID being read

**Issue**: "GUI freezes during RFID read"
- RFID should run in background thread, not block
- If freezing, check thread is properly started
- Verify no blocking calls in signal handlers

---

## References

- Pico RFID Hardware: [PiicoDev RFID Module](https://core-electronics.com.au/guides/piicodev/piicodev-rfid/)
- PyQt5 Signals: [PyQt5 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt5/)
- Python Serial: [pyserial Documentation](https://pyserial.readthedocs.io/)

