# Vent Valve Manual Override During Vent Procedure

## Problem Description

The vent valve (`btnValveVent`) could not be manually controlled during the vent procedure (`pushButton_3`) in Normal mode. The safety system was blocking manual button operations even though this specific control is needed for safety reasons during venting.

## Root Cause

The `safe_button_click()` method in `app.py` had two restriction layers:

1. **Procedure Running Check**: Blocks manual control during auto procedures (except Override mode)
2. **Normal Mode Check**: Blocks manual button operations in Normal mode

Even though there was already a special exception for gas valves during sputter procedure, there was no equivalent exception for the vent valve during vent procedure.

## Solution Implemented

Added three-layer protection to allow manual vent valve control during vent procedure:

### Layer 1: Procedure Running Exception (Lines 444-467)
Added vent valve to the list of allowed manual controls during its associated procedure:

```python
vent_procedure_names = ['pushButton_3', 'vent_procedure']

# Allow vent valve during vent procedure (manual control for safety)
elif (button_name == 'btnValveVent' and 
      any(proc in str(self.current_procedure) for proc in vent_procedure_names)):
    print(f"🌟 Allowing {button_name} during vent procedure (manual override)")
    allowed = True
```

### Layer 2: Normal Mode Exception (Lines 493-498)
Added vent valve exception to Normal mode restrictions:

```python
# Special exception: Allow vent valve during vent procedure (manual override for safety)
vent_procedure_names = ['pushButton_3', 'vent_procedure']
if (button_name == 'btnValveVent' and 
    self.current_procedure is not None and
    any(proc in str(self.current_procedure) for proc in vent_procedure_names)):
    allowed = True
    print(f"🌟 Allowing {button_name} in Normal mode during vent procedure (manual safety override)")
```

### Layer 3: Auto Procedure Treatment (Lines 520-534)
Treat vent valve as auto procedure operation during vent, bypassing mode restrictions while still enforcing safety conditions:

```python
# Determine if this should be treated as an auto procedure operation
# This bypasses mode restrictions while still enforcing safety conditions
treat_as_auto_procedure = False

# Vent valve during vent procedure should bypass mode restrictions
vent_procedure_names = ['pushButton_3', 'vent_procedure']
if (button_name == 'btnValveVent' and 
    self.current_procedure is not None and
    any(proc in str(self.current_procedure) for proc in vent_procedure_names)):
    treat_as_auto_procedure = True
    print(f"🔧 Treating {button_name} as auto procedure operation during vent (bypasses mode restrictions)")

# Check safety conditions
safety_result = self.safety_controller.check_button_safety(button_name, is_auto_procedure=treat_as_auto_procedure)
```

## How It Works

1. **Detection**: System checks if `btnValveVent` is being operated while `current_procedure` is `'pushButton_3'` or `'vent_procedure'`

2. **Bypass Procedure Block**: First exception allows operation during procedure (doesn't wait for procedure completion)

3. **Bypass Normal Mode**: Second exception allows operation in Normal mode (doesn't require switching to Manual/Override)

4. **Bypass Mode Restrictions in Safety Check**: By passing `is_auto_procedure=True` to `check_button_safety()`, the safety controller skips mode restriction checks (as defined in `safety_controller.py` line 155)

5. **Safety Conditions Still Apply**: All other safety conditions from `safety_conditions.yml` are still enforced:
   - Forbidden conditions (e.g., gate valves must be closed)
   - Required conditions (if any)
   - Emergency conditions

## Benefits

- **Safety**: Allows operator to manually intervene with vent valve during venting for safety reasons
- **Flexibility**: Works in Normal mode without requiring mode switch
- **Protection**: Still enforces all safety interlocks and forbidden conditions
- **Consistency**: Uses same pattern as gas valve override during sputter procedure

## Testing Procedure

1. Start app in Normal mode: `python -m python.app`
2. Run vent procedure: Click "VENT" button (pushButton_3)
3. During venting, try to manually operate vent valve (open/close)
4. **Expected Result**: Vent valve responds to manual clicks without "Manual Control Disabled" error
5. **Safety Check**: Verify that forbidden conditions are still enforced (e.g., cannot open if gate valve open)

## Code Locations

- **File**: `python/app.py`
- **Method**: `safe_button_click()` (lines 435-570)
- **Changes**: 
  - Lines 444-467: Procedure running exception
  - Lines 493-498: Normal mode exception  
  - Lines 520-534: Auto procedure treatment for safety check

## Related Configuration

- **Safety Config**: `python/safety/safety_conditions.yml`
  - Lines 169-183: `btnValveVent` safety conditions
  - Already has confirmation bypass for vent procedure (safety_controller.py lines 282-286)

## Future Enhancements

This pattern can be extended to other buttons that need manual override during specific procedures:
1. Add button name to exception list
2. Add procedure name check
3. Set `treat_as_auto_procedure = True` for that combination
4. Ensure safety conditions in YAML allow the operation

## Date
October 21, 2025
