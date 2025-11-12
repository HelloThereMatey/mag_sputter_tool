# Chamber Light Automatic Control During Load/Unload

## Overview
The chamber light (`btnLightBulb`) now automatically turns ON when the load-lock gate valve opens during the load/unload procedure, and turns OFF when the procedure completes or is cancelled.

## Implementation Details

### Automatic Light Control Flow

```
Load/Unload Procedure Started
    ↓
Turbo Protection & Pumpdown
    ↓
Load-lock Gate Valve Opens
    ↓
💡 LIGHT TURNS ON ← Automatic
    ↓
LoadUnloadDialog Shown to User
    ↓
User Loads/Unloads Sample
    ↓
User Confirms Arm in Home Position
    ↓
Load-lock Gate Valve Closes
    ↓
💡 LIGHT TURNS OFF ← Automatic
    ↓
Procedure Complete
```

### Code Locations

#### 1. Light ON - When Gate Valve Opens
**File:** `python/auto_procedures.py`
**Function:** `load_unload_procedure()`
**Location:** After opening gate valve (around line 1125)

```python
# Turn on chamber light for visibility during load/unload
print("💡 Turning on chamber light...")
if not set_relay_safe('btnLightBulb', True, arduino, safety, relay_map):
    print("Warning: Failed to turn on chamber light (non-critical)")
else:
    print("✅ Chamber light turned on")
```

#### 2. Light OFF - When Gate Valve Closes (Success)
**File:** `python/app.py`
**Function:** `_complete_load_unload_procedure()`
**Location:** After closing gate valve (around line 2298)

```python
# Turn off chamber light after load/unload complete
print("💡 Turning off chamber light...")
if set_relay_safe('btnLightBulb', False, self.arduino, self.safety_controller, self.relay_map):
    print("✅ Chamber light turned off")
else:
    print("Warning: Failed to turn off chamber light (non-critical)")
```

#### 3. Light OFF - When Procedure Cancelled
**File:** `python/app.py`
**Function:** `_show_load_unload_dialog()`
**Location:** In the cancellation handler (around line 2262)

```python
# Turn off chamber light
print("💡 Turning off chamber light (cancelled)...")
if set_relay_safe('btnLightBulb', False, self.arduino, self.safety_controller, self.relay_map):
    print("✅ Chamber light turned off")
```

#### 4. Light OFF - On Error
**File:** `python/app.py`
**Function:** `_show_load_unload_dialog()`
**Location:** In the exception handler (around line 2278)

```python
# Turn off chamber light on error
set_relay_safe('btnLightBulb', False, self.arduino, self.safety_controller, self.relay_map)
```

## Benefits

1. **Automatic Operation**: No manual light control needed during load/unload
2. **Improved Visibility**: Light is ON when the gate valve is open for better sample viewing
3. **Energy Efficiency**: Light automatically turns OFF when procedure completes
4. **Fail-Safe**: Light turns OFF even if procedure is cancelled or encounters an error
5. **Non-Critical**: Light control failures don't abort the procedure

## Safety Considerations

- Light control is marked as **non-critical** - failures won't block the procedure
- Light operations use `set_relay_safe()` which enforces safety conditions
- Light can be manually controlled at any time (allowed in all modes)
- Light control exceptions are caught and logged during error handling

## User Experience

### Normal Flow
1. User starts load/unload procedure (pushButton_5)
2. System pumps down chambers and performs safety checks
3. **Light turns ON automatically** when gate valve opens
4. User dialog appears: "Use load-lock arm to load/unload sample..."
5. User loads/unloads sample with good visibility
6. User returns arm to home position and clicks button
7. Gate valve closes
8. **Light turns OFF automatically**
9. Success message shown

### Cancellation Flow
1. User clicks "Load/Unload Finished or Cancel" without confirming
2. **Light turns OFF automatically**
3. Warning shown about gate valve remaining open
4. User must manually close gate valve if needed

### Error Flow
1. Error occurs during procedure
2. **Light turns OFF automatically** (best effort)
3. Error message shown
4. System returns to previous state

## Manual Override

Users can still manually control the light at any time:
- Light button is always available (Normal, Manual, Override modes)
- Light button works during any running procedure
- Manual control overrides automatic state

## Testing Checklist

- [ ] Light turns ON when gate valve opens
- [ ] Light turns OFF when procedure completes successfully
- [ ] Light turns OFF when user cancels procedure
- [ ] Light turns OFF when error occurs
- [ ] Manual light control still works during procedure
- [ ] Light control failures don't abort procedure
- [ ] Console messages show light status changes

## Related Files

- `python/auto_procedures.py` - Light ON logic
- `python/app.py` - Light OFF logic (completion, cancellation, error)
- `python/widgets/other_dialogs.py` - LoadUnloadDialog UI
- `python/safety/safety_conditions.yml` - Light safety config (no restrictions)

## Hardware

- **Relay**: 13 (Pin 34)
- **Button**: `btnLightBulb`
- **Control**: Latching relay (maintains state)
- **Safety**: No safety restrictions (can operate anytime)

---

**Document Version:** 1.0
**Last Updated:** January 2025
**Status:** Implemented and Ready for Testing
