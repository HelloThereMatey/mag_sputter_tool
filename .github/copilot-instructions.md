# AI Coding Agent Instructions for mag_sputter_tool

## Project Overview

**mag_sputter_tool** is a production control system for DC/RF magnetron sputtering deposition on Raspberry Pi 5 + Arduino Mega 2560. It replaces aging LabVIEW systems with open-source hardware/software.

**Architecture**: PyQt5 GUI → Safety Controller + Arduino Controller + Gas Flow Controller → Hardware (23 relays, 4 digital inputs, 4 analog inputs, Alicat MFCs)

---

## Critical Safety & Architecture Patterns

### 1. Safety-First Design
All procedures must integrate with `SafetyController` (python/safety/) before executing:
- **Check pattern**: `safety.check_button_safety(button_name, is_auto_procedure=True)` returns `SafetyResult`
- **Config-driven**: Safety rules in `safety/safety_conditions.yml` (pressure thresholds, digital interlocks, forbidden relay combinations)
- **Mode system**: Normal (automated only, full safety) | Manual (all controls, full safety) | Override (no safety, admin only)
- **Key invariant**: Ion gauge requires momentary pulse via special handler `toggle_ion_gauge()`, not direct relay control

See `auto_procedures.py:set_relay_safe()` as the pattern for all hardware changes.

### 2. YAML Configuration System
Configuration-as-code drives the system:
- `sput.yml`: Relay pin mappings, serial baud rate, preferred ports, analog channel scaling
- `safety_conditions.yml`: Pressure thresholds, digital interlock mappings (e.g., water_switch at input index 0)
- `gas_control/config.yml`: MFC serial ports, max flows, gas types
- **Update both code AND YAML** when adding relays/sensors

### 3. Serial Communication (Arduino)
- **Baud**: 9600, 9-bit protocol (port caching in `~/.sputter_control/`)
- **Pattern**: `ArduinoController` queues commands, background thread communicates
- **Relay firmware**: 1-based index in firmware (relay 1 → pin 22), 0-based in Python code
- **Port detection**: Loops through preferred ports + auto-detection; cache mechanism for fast reconnection

### 4. Procedure Pattern
Long-running operations live in `auto_procedures.py`. Key patterns:
- Check global `_procedure_cancelled` flag periodically for cancellation
- Use `wait_for_analog_condition()` for vacuum level waits (with timeout)
- Always call `set_relay_safe()` for hardware control (not direct Arduino calls)
- Procedures run in `QThreadPool` background threads via `ProcedureWorker` (app.py)

### 5. Async Gas Flow Control
`GasFlowController` (gas_control/) manages Alicat MFCs:
- Uses subprocess/threading to avoid blocking GUI (implements `subprocess_controller.py`)
- Safety integration: checks `SafetyController` before setting flows
- Recipes: `recipes.yml` defines gas ramp sequences, recipes are executed step-by-step
- Connection retry logic: validates MFC presence before operations

---

## Key File Structure

```
auto_control/
  sput.yml ......................... [EDIT THIS] Main config (pins, baud, serial ports)
  python/
    app.py ......................... Main PyQt5 window, timer loop (700ms refresh), thread management
    main.py ........................ Entry point, path setup, platform-specific Qt fixes
    config.py ...................... YAML loader, SerialConfig + AppConfig dataclasses
    arduino_controller.py .......... Serial communication, relay state tracking
    auto_procedures.py ............. All automated procedures (pump-down, vent, sputter, etc.)
    safety/
      safety_controller.py ......... [CORE] Safety evaluation, forbidden states
      safety_conditions.yml ........ [EDIT THIS] Pressure thresholds, interlock mappings
    gas_control/
      controller.py ................ MFC communication, thread-safe
      subprocess_controller.py ..... Alternative subprocess-based controller
      recipes.py ................... Gas ramp recipes (YAML-driven)
      config.yml ................... [EDIT THIS] MFC port, gas type configs
    security/
      user_account_manager.py ...... Role-based access (4 levels: Operator→Technician→Master→Admin)
    widgets/ ........................ PyQt5 UI components (mode dialog, MFC setpoint, analog recorder, etc.)
    tests/ .......................... Unit tests (pytest)
  relay_controller.ino ............. Arduino firmware (matches pin assignments in sput.yml)

rfid_read/ .......................... RFID card reader (Pico USB serial, port caching)
gas_control_all/ .................... Development sandbox for MFC integration (testing only)
relay_test_system/ .................. Standalone relay testing GUI (for debugging hardware)
```

---

## Common Development Tasks

### Adding a New Relay Control Button
1. Add pin mapping to `sput.yml` relays section
2. Add button name constant to `relay_pins` list in `sput.yml` (maintains firmware order)
3. Update Arduino firmware `relay_controller.ino` pin assignments
4. Add safety rules to `safety_conditions.yml` if needed (forbidden states, required conditions)
5. Call via `set_relay_safe(button_name, desired_state, arduino, safety, relay_map)` in procedures

### Adding a New Analog Input (Pressure Gauge)
1. Configure pin in `sput.yml` analog.channels
2. Add scaling/offset formula to `safety_conditions.yml` analog_input_scaling_factors
3. Update `SafetyController.check_*()` methods if affecting safety logic
4. Access via `safety.analog_inputs[channel_index]` in procedures

### Adding Safety Rules
1. Edit `safety_conditions.yml` with new threshold/logic
2. Implement evaluation in `safety_controller.py` (e.g., `check_pump_down_safety()`)
3. Call from `check_button_safety()` or `check_procedure_safety()` as needed

### Running Tests
```bash
cd auto_control/python/tests
pytest test_arduino_relay.py        # Hardware integration
pytest test_mode_dialog.py          # UI behavior
pytest -v                           # All tests with verbose output
```

### Hardware Testing
```bash
cd relay_test_system/python
python platform_test.py             # Verify relay control
python port_tester.py               # Test serial communication
```

---

## Gotchas & Non-Obvious Behavior

1. **Ion Gauge Toggle**: NOT a simple on/off relay. Uses momentary pulse → hardware toggles. Never call `arduino.set_relay('btnIonGauge', ...)` directly; use `toggle_ion_gauge()`.

2. **Ion Gauge Auto-Toggle Safety Logic**: System has automatic safety logic that turns off the ion gauge if it's on but not in high_vacuum/pumping state. This can cause continuous toggling if there's an open circuit on the ion gauge input. **Control via Tools menu → "Ion Gauge Auto-Toggle"** to enable/disable this safety logic. When disabled, the ion gauge must be controlled manually.

3. **Digital Input Logic**: Arduino firmware inverts active-low switch readings. In Python: `true=safe`, `false=unsafe`. See `safety_conditions.yml:digital_interlocks` for mapping.

4. **GUI Timer Loop**: 700ms refresh in `app.py:timerEvent()`. Procedures block main thread if spawned synchronously; always use `QThreadPool` + `ProcedureWorker`.

5. **Serial Port Caching**: `ArduinoController` caches ports in `~/.sputter_control/`. If USB device changes, delete cache file to force re-detection.

6. **Gas Control Thread Safety**: `GasFlowController` uses internal queue + thread. Do NOT call Alicat directly; use controller methods.

7. **Config Reload**: Editing YAML files requires app restart. No hot-reload.

8. **Safety Mode Bypass**: `check_button_safety(..., is_auto_procedure=True)` bypasses mode restrictions but NOT other safety checks. Override mode fully disables all checks.

---

## Integration Points

- **PyQt5 → Arduino**: Via `ArduinoController` (thread-safe queue pattern)
- **PyQt5 → Alicat MFCs**: Via `GasFlowController` subprocess/thread wrapper
- **Safety checks**: All hardware changes must query `SafetyController` first
- **User auth**: `UserAccountManager` validates credentials; controls mode access
- **Data persistence**: Config YAMLs + user accounts in encrypted files (`~/.sputter_control/`)

---

## When Working on This Codebase

1. **Always check `SafetyController` before ANY hardware change**
2. **Update both code and `sput.yml` for hardware mapping changes**
3. **Use `set_relay_safe()` wrapper, not direct Arduino calls**
4. **Test procedures with hardware connected; fallback to relay_test_system if isolated**
5. **Review `safety_conditions.yml` when adding vacuum/pressure logic**
6. **Reference `README.md` for full setup + operation mode docs**
7. **Ion gauge auto-toggle safety can be disabled via Tools menu if needed** (e.g., for troubleshooting open circuits)
