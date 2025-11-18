# RFID Auto-Reconnect Feature

## Problem

When the login dialog was open and attempting card enrollment, users would see "Disconnected from RFID reader" status. The RFID reader thread would fail to connect or lose connection and then stop completely, preventing card enrollment from working.

## Solution

Added automatic reconnection capability to the RFID reader thread so it continuously attempts to connect/reconnect while the thread is running.

---

## Changes Made

### `rfid/reader_thread.py`

**1. Added Auto-Reconnect Properties** (line ~52):
```python
self.auto_reconnect = True  # Enable auto-reconnection by default
self.reconnect_delay = 3.0  # Seconds between reconnection attempts
```

**2. Refactored `run()` Method** (line ~58):
- Changed from single-attempt connection to continuous retry loop
- Wraps connection attempts in `while self.running` loop
- Waits `reconnect_delay` seconds between attempts
- Exits loop only when `stop()` is called or `auto_reconnect = False`

**3. Created `_connect_to_device()` Method** (line ~93):
- Extracted connection logic from `run()` into separate method
- Returns `True` on successful connection, `False` on failure
- Clears `self.port = None` on failure to force re-detection
- Better error handling and status messages

**4. Improved Status Messages**:
- "🔄 Retrying in 3s..." - shown between reconnection attempts
- "📴 RFID reader disconnected" - only shown on clean shutdown
- Suppresses duplicate "Disconnected" messages on error

**5. Updated `disconnect()` Method** (line ~248):
- Only emits disconnect status if device was previously ready
- Prevents misleading "Disconnected" message when connection never succeeded

---

## Behavior

### Before Changes
1. RFID thread starts
2. If connection fails → thread stops, shows error
3. User sees "Disconnected from RFID reader"
4. Card enrollment fails
5. Must restart application to retry

### After Changes
1. RFID thread starts
2. If connection fails → waits 3 seconds, retries
3. Continuously attempts connection while thread running
4. User sees "🔄 Retrying in 3s..." between attempts
5. When device connects → "✓ RFID reader ready"
6. If connection lost → automatically reconnects
7. Thread keeps running until login dialog closes

---

## User Experience

**During login:**
- If RFID reader not connected → shows "❌ RFID reader not found. Is Pico connected?"
- Retries every 3 seconds automatically
- User can plug in RFID reader while login dialog is open
- Reader will be detected automatically within 3 seconds

**During enrollment:**
- Enrollment dialog opens and waits for card
- If RFID reader disconnects → reconnects automatically
- User doesn't need to cancel and retry
- Can unplug/replug USB without restarting application

**Visual Status Updates:**
- "🔍 Searching for RFID reader..." - actively searching
- "📍 Using cached port: COM5" - found cached port
- "🔌 Connecting to COM5 @ 115200 baud..." - connecting
- "✓ Connected to COM5" - serial connection established
- "✓ RFID reader ready" - device ready, can read cards
- "🔄 Retrying in 3s..." - connection lost, will retry
- "❌ RFID reader not found..." - no device detected

---

## Configuration

**Default Settings:**
- `auto_reconnect = True` - enabled by default
- `reconnect_delay = 3.0` - seconds between retry attempts

**To Disable Auto-Reconnect:**
```python
rfid_thread = RFIDReaderThread()
rfid_thread.auto_reconnect = False  # Set before calling start()
rfid_thread.start()
```

**To Change Retry Delay:**
```python
rfid_thread = RFIDReaderThread()
rfid_thread.reconnect_delay = 5.0  # 5 seconds between retries
rfid_thread.start()
```

---

## Technical Details

### Thread Lifecycle

**Old Behavior:**
```
Start → Connect → [Success: Read Loop → Exit]
                → [Failure: Exit]
```

**New Behavior:**
```
Start → Loop:
          → Connect → [Success: Read Loop → Lost? → Continue Loop]
                   → [Failure: Wait 3s → Continue Loop]
        Exit when:
          - stop() called
          - auto_reconnect = False
```

### Port Detection Strategy

1. **First attempt:** Use cached port if available
2. **On failure:** Clear cached port, force full detection
3. **Next attempt:** Search all USB serial ports
4. **Repeat:** Continues until device found or stopped

### Error Recovery

**Connection Errors:**
- Serial port busy → retry with re-detection
- USB unplugged → retry continuously
- Pico reset → reconnects automatically

**Device Ready Timeout:**
- If Pico doesn't send ready message → retry connection
- Clears port to force re-detection
- Prevents stale connection attempts

---

## Testing Scenarios

### Scenario 1: Reader Not Connected Initially
1. Open login dialog
2. See "❌ RFID reader not found"
3. Plug in RFID reader
4. Within 3 seconds: "✓ RFID reader ready"
5. Can now enroll cards

### Scenario 2: Reader Disconnected During Enrollment
1. Open enrollment dialog
2. Unplug RFID reader
3. See "🔄 Retrying in 3s..."
4. Replug RFID reader
5. Auto-reconnects, enrollment continues
6. Present card → enrollment succeeds

### Scenario 3: Pico Reset/Reboot
1. RFID reader connected and working
2. Pico reboots (power cycle, firmware update)
3. Thread detects connection lost
4. Waits 3 seconds
5. Reconnects automatically
6. Resumes normal operation

---

## Known Limitations

1. **3 Second Delay**: Reconnection attempts every 3 seconds, not instant
2. **Port Caching**: If wrong port cached, may slow first connection
3. **Multiple Devices**: No support for multiple RFID readers simultaneously
4. **Background Resource**: Thread continues retrying until dialog closes

---

## Future Enhancements

### Phase 2: Configurable Settings
- User preference for auto-reconnect on/off
- Adjustable retry delay
- Max retry attempts before giving up

### Phase 3: Advanced Detection
- Faster detection for known devices
- Support multiple reader types
- Hot-swap optimization (< 1 second reconnect)

### Phase 4: Fault Tolerance
- Queue cards read during reconnection
- Buffer mechanism for brief disconnects
- Seamless recovery without user notification

---

## Compatibility

- **Python:** 3.7+
- **PyQt5:** All versions with QThread support
- **PySerial:** 3.0+
- **Hardware:** Raspberry Pi Pico with RFID module
- **OS:** Windows, Linux, macOS (all platforms)

---

## Related Files

- `rfid/reader_thread.py` - Main RFID reader thread class
- `rfid/config.py` - Port detection and caching
- `widgets/login_dialog.py` - Uses RFID thread for authentication
- `RFID_MANDATORY_MIGRATION.md` - RFID-only authentication system

---

## Changelog

**2025-01-XX** - Initial auto-reconnect implementation
- Added `auto_reconnect` and `reconnect_delay` properties
- Refactored `run()` for continuous retry loop
- Created `_connect_to_device()` extraction method
- Improved status messages and error handling
- Updated `disconnect()` to suppress misleading messages
