# Digital Input Mapping Reference

## Correct Pin Assignments (Per sput.yml and Hardware)

The digital inputs are mapped as follows across the entire system:

### Hardware (Arduino Mega 2560)
- **Pin 45** → Water Flow Interlock
- **Pin 47** → Load-lock Arm Home (Rod) Interlock  
- **Pin 49** → Chamber Door Interlock
- **Pin 51** → Spare Interlock (not used)

### Software Array Indices
- **digital_inputs[0]** = Water Flow (pin 45)
- **digital_inputs[1]** = Rod/Arm Home (pin 47)
- **digital_inputs[2]** = Door (pin 49)
- **digital_inputs[3]** = Spare (pin 51)

### GUI Indicator Order (Top to Bottom)
- **indWater** ← digital_inputs[0] (pin 45)
- **indRod** ← digital_inputs[1] (pin 47)
- **indDoor** ← digital_inputs[2] (pin 49)

### File References

#### 1. `sput.yml`
```yaml
inputs:
  water_switch: 45
  rod_switch: 47
  door_switch: 49
  spare_switch: 51
  digital_labels: [Water, Rod, Door, Spare]
```

#### 2. `relay_controller/relay_controller.ino`
```cpp
const int DIGITAL_INPUT_PINS[4] = {
  45, 47, 49, 51  // Water(45), Rod(47), Door(49), Spare(51)
};
```

#### 3. `python/safety/safety_conditions.yml`
```yaml
digital_interlocks:
  water_flow_interlock:
    input: 0  # Digital input array index 0 (Arduino pin 45 - Water)
  arm_home_interlock:
    input: 1  # Digital input array index 1 (Arduino pin 47 - Arm Home)
  door_interlock:
    input: 2  # Digital input array index 2 (Arduino pin 49 - Door)
```

#### 4. `python/app.py` (refresh_inputs function)
```python
# Update visual indicators for first 3: Arduino sends Water(0), Rod(1), Door(2)
for idx, obj_name in enumerate(["indWater", "indRod", "indDoor"]):
    w = getattr(self, obj_name, None)
    if w is not None and idx < len(di):
        indicator_state = bool(di[idx])
        set_interlock_indicator(w, indicator_state)
```

#### 5. `python/auto_procedures.py` (vent_procedure)
```python
# Door input: digital_inputs[2] = Door interlock (Arduino pin 49)
# Per sput.yml and safety_conditions.yml: [0]=Water, [1]=Rod, [2]=Door, [3]=Spare
door_idx = 2
```

## Safety Logic

### Hardware Level
- **Pull-up resistors enabled** on all digital input pins
- **Active-low logic**: Switches connect pin to ground when closed
- **LOW** at pin (switch closed) = **SAFE** condition
- **HIGH** at pin (switch open) = **UNSAFE** condition

### Arduino Firmware
- Reads raw pin states
- **Inverts logic** before sending to Python
- Python receives: `true` = safe, `false` = unsafe

### Python Application
- Receives inverted boolean values from Arduino
- `True` = interlock satisfied (safe)
- `False` = interlock violated (unsafe)

## Common Usage Patterns

### Checking Door Status
```python
# In Python code with access to safety controller or digital_inputs list:
door_closed = digital_inputs[2]  # True if door closed (safe), False if open (unsafe)
```

### Checking Water Flow
```python
water_ok = digital_inputs[0]  # True if water flowing (safe), False if no flow (unsafe)
```

### Checking Rod/Arm Position
```python
rod_home = digital_inputs[1]  # True if arm in home position (safe), False otherwise (unsafe)
```

## Emergency Conditions (safety_conditions.yml)

### Water Flow Emergency
```yaml
emergency_stop:
  condition: "digital_inputs[1] == False"  # NOTE: This appears to be WRONG - should be [0]
  message: "EMERGENCY: Water flow lost - all pumps stopped"
```

**⚠️ POTENTIAL BUG**: The emergency_stop condition checks `digital_inputs[1]` but the comment says "Water flow lost". This should probably be `digital_inputs[0]` since Water is at index 0.

### Mains Power Safety
```yaml
mains_power_safety:
  condition: "relay_state['btnMainsPower'] == True and (digital_inputs[0] == False or digital_inputs[1] == False or digital_inputs[2] == False)"
  message: "CRITICAL SAFETY: Mains power disabled due to interlock violation"
```

This checks all three critical interlocks: Water[0], Rod[1], Door[2] ✓

## Testing & Verification

When debugging digital input issues:

1. **Check Arduino firmware output**: Look for "DEBUG - Raw pin readings" messages
2. **Check Python digital_inputs values**: Print `safety.digital_inputs` array
3. **Verify GUI indicators**: Visual feedback should match array values
4. **Confirm procedure logic**: Procedures should reference correct indices

## Updated: October 16, 2025
Fixed door index in `auto_procedures.py` vent_procedure from incorrect index 0 to correct index 2.
