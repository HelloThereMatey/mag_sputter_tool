"""
Auto Procedures Module for Sputter Control System

This module contains automated procedures for vacuum system operations,
ensuring all safety conditions are met before performing actions.
"""

import time
from typing import Dict, List, Optional, Callable
from pathlib import Path
import builtins

# Global cancellation flag for long-running procedures
_procedure_cancelled = False

def cancel_running_procedures():
    """Signal all running procedures to cancel."""
    global _procedure_cancelled
    _procedure_cancelled = True
    print("🛑 Cancellation signal sent to all running procedures")

def reset_cancellation_flag():
    """Reset the cancellation flag before starting new procedures."""
    global _procedure_cancelled
    _procedure_cancelled = False

def is_procedure_cancelled() -> bool:
    """Check if procedures should be cancelled."""
    return _procedure_cancelled

# Import controllers (assuming relative imports work)
try:
    from .arduino_controller import ArduinoController
    from .safety.safety_controller import SafetyController, SafetyResult
    from .config import load_config
except ImportError:
    from arduino_controller import ArduinoController
    from safety.safety_controller import SafetyController, SafetyResult
    from config import load_config

def toggle_ion_gauge(desired_state: bool, arduino: ArduinoController, 
                     safety: SafetyController, relay_map: Dict[str, int]) -> bool:
    """
    Special handler for ion gauge on/off control.
    
    The ion gauge hardware toggles on/off with each momentary pulse.
    This function checks the current state and only pulses if needed.
    
    Args:
        desired_state: True to turn ON, False to turn OFF
        arduino: ArduinoController instance
        safety: SafetyController instance  
        relay_map: Dictionary mapping button names to relay numbers
        
    Returns:
        True if successful, False otherwise
    """
    relay = relay_map.get('btnIonGauge')
    if relay is None:
        print("❌ Error: btnIonGauge not found in relay_map")
        return False
        
    if arduino is None:
        print("❌ Error: Arduino controller is None")
        return False
    
    try:
        # Check current ion gauge state
        current_state = None
        if safety is not None and hasattr(safety, 'is_ion_gauge_on'):
            current_state = safety.is_ion_gauge_on()
        
        # If we can determine current state and it matches desired, no action needed
        if current_state is not None and current_state == desired_state:
            print(f"📏 Ion gauge already in desired state ({desired_state})")
            return True
            
        # Pulse the relay to toggle the ion gauge
        print(f"📏 Pulsing ion gauge relay to set state to {desired_state}")
        
        # Set relay ON
        if not arduino.set_relay(relay, True):
            print("❌ Failed to pulse ion gauge relay ON")
            return False
            
        # Update safety controller bookkeeping
        if safety is not None:
            safety.relay_states['btnIonGauge'] = desired_state
            
        # Hold pulse for 1 second
        time.sleep(1.0)
        
        # Set relay OFF
        if not arduino.set_relay(relay, False):
            print("❌ Failed to turn off ion gauge relay after pulse")
            
        return True
        
    except Exception as e:
        print(f"❌ Exception in toggle_ion_gauge: {e}")
        return False

def turbo_protection_procedure(safety: SafetyController, 
                                arduino: ArduinoController, 
                                relay_map: Dict[str, int]) -> bool:
    """
    Turbo Protection Procedure
    Quick shutdown of turbo pump and ion gauge & most importantly closing turbo gate, to protect hardware.
    """

    # Turn off Ion Gauge if on
    print("📏 Turning OFF Ion Gauge if it is ON")
    if safety.is_ion_gauge_on():
        if not toggle_ion_gauge(False, arduino, safety, relay_map):
            print("❌ Failed to turn off Ion Gauge")
            return False
    # Turn off turbo pump if on
    print("🌀 Turning OFF turbo pump if it is ON")
    if safety.relay_states.get('btnPumpTurbo', False):
        if not set_relay_safe('btnPumpTurbo', False, arduino, safety, relay_map):
            print("❌ Failed to turn off turbo pump")
            return False
        time.sleep(4.0)  # brief pause to ensure turbo off 

    # Close turbo gate
    print("🔀 Closing turbo gate valve to protect it from gas exposure.")
    if not set_relay_safe('btnValveTurboGate', False, arduino, safety, relay_map):
        print("❌ Failed to close turbo gate valve")
        return False
    time.sleep(5.0)  # brief pause to ensure valve closed

    # Close turbo backing valve
    print("🔀 Closing turbo backing valve to protect it from gas exposure.")
    if not set_relay_safe('btnValveBacking', False, arduino, safety, relay_map):
        print("❌ Failed to close turbo backing valve")
        return False
    time.sleep(4.0)  # brief pause to ensure valve closed
    
    return True

# Helper to safely set relay and update safety.relay_states if available
def set_relay_safe(name: str, value: bool, arduino: ArduinoController, 
                   safety: SafetyController, 
                   relay_map: Dict[str, int],
                   suppress_logging: bool = False) -> bool:
    """Set a relay via the Arduino and update the safety controller's relay state.

    Special-case for the Ion Gauge (`btnIonGauge`): the hardware expects a
    momentary pulse to toggle ON/OFF. For the ion gauge we always pulse the
    relay HIGH for ~1 second and then release it. The `value` argument is
    treated as the intended logical state and is stored in `safety.relay_states`
    for bookkeeping, but the physical state is reported by analog input.
    
    IMPORTANT: This function performs safety checks using is_auto_procedure=True,
    which bypasses mode restrictions in Normal mode but still enforces all other
    safety conditions including forbidden_conditions.
    """
    relay = relay_map.get(name)
    if relay is None:
        print(f"❌ Error: {name} not found in relay_map")
        return False

    # Defensive: ensure arduino provided
    if arduino is None:
        print("❌ Error: Arduino controller is None")
        return False

    try:
        # Check if relay is already in the desired state
        current_state = safety.relay_states.get(name, False)
        if current_state == value:
            #print(f"Relay {name} is already in desired state ({value}) - no action needed")
            return True
        
        # Perform safety check for this button operation
        # Use is_auto_procedure=True to bypass mode restrictions but keep all other safety checks
        safety_result = safety.check_button_safety(name, is_auto_procedure=True)
        if not safety_result.allowed:
            print(f"⚠️ Safety check failed for {name}: {safety_result.message}")
            return False
        
        # Ion gauge requires special handling: use dedicated function
        if name == 'btnIonGauge':
            return toggle_ion_gauge(value, arduino, safety, relay_map)

        # Default behavior for other relays: set to requested value
        ok = arduino.set_relay(relay, value, suppress_logging = suppress_logging)
        if ok:
            try:
                safety.relay_states[name] = value
            except Exception:
                pass
        return builtins.bool(ok)
    except Exception as e:
        print(f"❌ Exception setting relay {name}: {e}")
        return False

def wait_for_analog_condition(
    arduino: ArduinoController,
    safety: SafetyController,
    condition_fn: Callable[[List[float]], bool],
    max_wait_time: int = 300,
    poll_interval: float = 1.0,
) -> bool:
    """Wait until an analog-read based condition is true or timeout.

    Args:
        arduino: ArduinoController instance to read analog voltages from.
        safety: SafetyController to be updated with fresh readings.
        condition_fn: callable taking the voltages list and returning True when condition met.
        max_wait_time: seconds to wait before giving up.
        poll_interval: seconds between polls.

    Returns:
        True when condition met, False on timeout.
    """
    wait_start = time.time()
    failed_attempts = 0
    max_failed_attempts = 5
    
    while time.time() - wait_start < max_wait_time:
        # Check for cancellation signal
        if is_procedure_cancelled():
            print("🛑 wait_for_analog_condition cancelled by user")
            return False
            
        voltages = None
        try:
            voltages = arduino.get_analog_voltages()
        except Exception:
            voltages = None

        if voltages is None:
            failed_attempts += 1
            print(f"Failed to read analog voltages (attempt {failed_attempts}/{max_failed_attempts})")
            
            if failed_attempts >= max_failed_attempts:
                print(f"Aborting: Failed to read analog voltages {max_failed_attempts} consecutive times")
                return False
                
            time.sleep(poll_interval)
            continue
        
        # Reset failure counter on successful read
        failed_attempts = 0

        # Update safety controller with fresh readings if available
        try:
            safety.update_system_state(analog_inputs=voltages)
        except Exception:
            pass

        try:
            if condition_fn(voltages):
                return True
        except Exception:
            # If predicate raises, treat as not yet satisfied
            pass

        time.sleep(poll_interval)

    return False

def go_to_standby(arduino: ArduinoController, 
                        safety: SafetyController,
                        relay_map: Dict[str, int]) -> bool:

    """ Go to standby after going to default state.
    """
    
    # Check if already in standby state - avoid unnecessary operations
    current_state = getattr(safety, 'system_status', None)
    if current_state == 'standby':
        print("😴 System is already in standby state - no action needed")
        return True
    
    # If not in default state, go to default first
    if current_state != 'default':
        if not go_to_default_state(arduino, safety, relay_map):
            print("❌ Failed to take system to default state. Aborting.")
            return False
    
    print("😴 Putting system in standby state.")
    # Turn off scroll pump (standby has all pumps off)
    if not set_relay_safe('btnPumpScroll', False, arduino, safety, relay_map):
        print("⚠️ Warning: Failed to turn off scroll pump")
        return False

    time.sleep(3.0)
    print("✅ System taken to standby state.")
    return True

def go_to_default_state(arduino: ArduinoController, 
                        safety: SafetyController,
                        relay_map: Dict[str, int]) -> bool:
    """
    Go to the default state for the vacuum system.
    
    Default state per YAML: scroll pump ON, all other relays OFF.
    This provides a safe intermediate state for system operations.
    """
    print("🏠 Returning system to default state...")

    try:
        # Check if already in default state - avoid unnecessary operations
        try:
            current_system_state = getattr(safety, 'system_status', None)
            if current_system_state == 'default':
                print("System is already in default state - no action needed")
                return True
        except Exception:
            print("Could not determine current system state - proceeding with default procedure")

        # Get current system state for logging
        try:
            current_state = safety.get_safety_status_summary()
            print(f"Current relay states: {current_state.get('relay_states', {})}")
        except Exception:
            print("Could not read current system state")

        # Safe shutdown sequence for high-energy components
        
        # 1. Turn off mains power first for safety (ALWAYS attempt this for safety)
        try:
            print("Turning off mains power (RF/DC supplies)...")
            
            # Force update the relay state to ensure safety controller knows mains might be ON
            safety.relay_states['btnMainsPower'] = True
            
            # Always attempt to turn off mains power during default state transition
            # This ensures safety even if relay state tracking is incorrect
            if not set_relay_safe('btnMainsPower', False, arduino, safety, relay_map):
                print("⚠️ set_relay_safe failed for mains power - trying direct Arduino command...")
                # Fallback: try direct Arduino command
                try:
                    mains_relay = relay_map.get('btnMainsPower')
                    if mains_relay:
                        arduino.set_relay(mains_relay, False)
                        safety.relay_states['btnMainsPower'] = False  # Update state manually
                        print("✅ Mains power turned off via direct Arduino command")
                    else:
                        print("❌ Cannot find mains power relay in relay_map")
                except Exception as e2:
                    print(f"❌ Direct mains power shutdown also failed: {e2}")
            else:
                print("✅ Mains power turned off successfully")
            time.sleep(0.5)
        except Exception as e:
            print(f"❌ Warning: Could not turn off mains power: {e}")
            # Last resort: try direct relay command
            try:
                mains_relay = relay_map.get('btnMainsPower', 22)  # Default to pin 22
                arduino.set_relay(mains_relay, False)
                safety.relay_states['btnMainsPower'] = False
                print("✅ Mains power turned off via emergency direct command")
            except Exception as e3:
                print(f"❌ Emergency mains power shutdown failed: {e3}")
        
        # 2. Turn off Ion Gauge (if on) to protect filament
        try:
            if hasattr(safety, 'is_ion_gauge_on') and safety.is_ion_gauge_on():
                print("Turning off Ion Gauge...")
                toggle_ion_gauge(False, arduino, safety, relay_map)
                time.sleep(1.0)
        except Exception as e:
            print(f"Warning: Could not safely turn off ion gauge: {e}")

        # 3. Handle turbo pump shutdown if running
        turbo_running = False
        try:
            turbo_running = safety.relay_states.get('btnPumpTurbo', False)
        except Exception:
            pass

        if turbo_running:
            print("Turbo pump is running - performing safe shutdown...")
            
            # Turn off turbo pump
            if not set_relay_safe('btnPumpTurbo', False, arduino, safety, relay_map):
                print("Warning: Failed to turn off turbo pump")
            
            # Wait briefly for turbo to begin spinning down
            time.sleep(1.0)

            # Wait for turbo spin to drop below 90% before closing valves
            print("Waiting for turbo spin to drop below 90% (4.11 V)")
            def spin_below_90(v: List[float]) -> bool:
                try:
                    return len(v) > 3 and float(v[3]) <= 4.11
                except Exception:
                    return False
            
            # Wait up to 2 minutes for turbo to slow down
            if not wait_for_analog_condition(arduino, safety, spin_below_90, max_wait_time=120):
                print("Warning: Timeout waiting for turbo spin to drop - continuing anyway")

        # 4. Close all valves in safe order
        valve_close_order = [
            'btnValveTurboGate',    # Close turbo gate first
            'btnValveBacking',      # Then backing valve
            'btnValveRough',        # Rough valve
            'btnValveVent',         # Vent valve
            'btnValveLoadLockGate', # Load lock gate
            'btnValveLoadLockRough',# Load lock rough
            'btnValveLoadLockVent', # Load lock vent
            'btnValveGas1',         # Gas valves
            'btnValveGas2',
            'btnValveGas3',
            'btnShutter1',          # Shutters
            'btnShutter2',
        ]
        
        print("Closing all valves and shutters...")
        for valve_name in valve_close_order:
            if valve_name in relay_map:
                try:
                    set_relay_safe(valve_name, False, arduino, safety, relay_map)
                    time.sleep(0.5)  # Brief pause between valve operations
                except Exception as e:
                    print(f"Warning: Failed to close {valve_name}: {e}")

        # 4. Ensure scroll pump is ON (default state requirement)
        print("Ensuring scroll pump is ON for default state...")
        try:
            if not set_relay_safe('btnPumpScroll', True, arduino, safety, relay_map):
                print("Warning: Failed to turn on scroll pump")
        except Exception as e:
            print(f"Warning: Exception turning on scroll pump: {e}")

        # 5. Turn off any remaining relays except scroll pump
        print("Turning off any remaining relays...")
        for name, relay in relay_map.items():
            if name != 'btnPumpScroll' and name not in valve_close_order:
                try:
                    set_relay_safe(name, False, arduino, safety, relay_map)
                except Exception as e:
                    print(f"Warning: Failed to turn off {name}: {e}")

        print("System returned to default state (scroll pump ON, all others OFF)")
        time.sleep(1.0)  # Brief pause to ensure all commands processed
        return True

    except Exception as e:
        print(f"❌ Error in go_to_default_state: {e}")
        # Emergency fallback: try to turn everything off
        try:
            print("Attempting emergency all relays off...")
            arduino.all_relays_off()
            time.sleep(1.0)
            # Turn scroll pump back on for default state
            scroll_relay = relay_map.get('btnPumpScroll')
            if scroll_relay:
                arduino.set_relay(scroll_relay, True)
        except Exception as e2:
            print(f"Emergency fallback also failed: {e2}")
        return False

def pump_procedure(arduino: ArduinoController, 
                   safety: SafetyController, 
                   relay_map: Dict[str, int]) -> bool:
    """
    Execute the automated pump procedure for the vacuum system.
    
    Steps:
    1. Turn on scroll pump
    2. Wait 15 seconds
    3. Open rough valve
    4. Wait until chamber pressure < chamber_medium_vacuum
    5. Close rough valve
    6. Open backing valve
    7. Wait 15 seconds
    8. Open turbo gate valve
    9. Wait until chamber pressure < chamber_medium_vacuum
    10. Turn on turbo pump

    To do:
    11. Wait for turbo pump > 80 % spin speed
    12. Wait until chamber pressure gauge reads < 0.65 V (make pressure conversion later)
    
    Args:
        arduino: ArduinoController instance
        safety: SafetyController instance
        relay_map: Dictionary mapping button names to relay numbers
        config_path: Path to config file (optional)
        
    Returns:
        True if procedure completed successfully, False otherwise
    """

    # Reset cancellation flag at start of procedure
    reset_cancellation_flag()

    # Get pressure thresholds
    safety_config = safety.safety_config
    chamber_medium_vacuum = safety_config.get('pressure_thresholds', {}).get('chamber_medium_vacuum', 2.0)
    # Default wait times
    chamber_wait_time = 1500  # seconds to wait for chamber to reach medium vacuum
    
    print("🚀 Starting pump procedure...")
    # Ensure system is in the default starting configuration before pumping
    try:
        if not go_to_default_state(arduino, safety, relay_map):
            print("Failed to return to default state before pump procedure")
            return False
    except Exception as e:
        print(f"Exception while returning to default state: {e}")
        return False
    
    # Step 1: Turn on scroll pump
    print("🌊 Step 1: Turning on scroll pump")
    # Check safety before turning on scroll pump
    safety_result = safety.check_button_safety('btnPumpScroll', is_auto_procedure=True)
    if not safety_result.allowed:
        print(f"⚠️ Safety check failed for btnPumpScroll: {safety_result.message}")
        return False

    if not set_relay_safe('btnPumpScroll', True, arduino, safety, relay_map):
        print("❌ Failed to turn on scroll pump")
        return False

    print("✅ Scroll pump turned on")
    
    # Step 2: Wait 15 seconds
    print("⏳ Step 2: Waiting 15 seconds for scroll pump to stabilize")
    time.sleep(15)
    
    # Step 3: Open rough valve
    print("🔀 Step 3: Opening rough valve")
    # Check safety
    safety_result = safety.check_button_safety('btnValveRough', is_auto_procedure=True)
    if not safety_result.allowed:
        print(f"⚠️ Safety check failed for btnValveRough: {safety_result.message}")
        return False

    if not set_relay_safe('btnValveRough', True, arduino, safety, relay_map):
        print("❌ Failed to open rough valve")
        return False

    print("✅ Rough valve opened")
    
    # Check if we're starting from atmospheric pressure - only then do the initial drop check
    # This guards against a slightly-open door causing continued leakage when pumping from atmosphere
    chamber_atmospheric = safety_config.get('pressure_thresholds', {}).get('chamber_atmospheric', 4.5)
    
    try:
        # Read current chamber pressure to see if we're starting from atmosphere
        baseline_volts = None
        try:
            volts = arduino.get_analog_voltages()
            if volts and len(volts) > 1:
                baseline_volts = float(volts[1])
        except Exception:
            baseline_volts = None

        # Only do the pressure drop check if starting from atmospheric pressure
        if baseline_volts is not None and baseline_volts > chamber_atmospheric:
            print(f"📈 Starting from atmospheric pressure ({baseline_volts:.3f} V > {chamber_atmospheric} V)")
            print("🔍 Performing initial pressure drop check to detect door leaks...\n\
                  ⚡📝 If pressure does not begin to drop within 20s, the procedure will abort.")

            # Define small drop threshold (0.02 V) to indicate pressure is beginning to fall
            drop_threshold = 0.02
            def pressure_begins_to_drop(v: List[float]) -> bool:
                try:
                    return len(v) > 1 and float(v[1]) < (baseline_volts - drop_threshold)
                except Exception:
                    return False

            # Wait up to 20 seconds for any sign of pressure decreasing
            began_drop = wait_for_analog_condition(
                arduino=arduino,
                safety=safety,
                condition_fn=pressure_begins_to_drop,
                max_wait_time=20,
                poll_interval=1.0
            )

            if not began_drop:
                print("🚨 Abort: Chamber pressure did not begin to drop within 20s after opening rough valve. Closing rough valve and aborting pump procedure.")
                try:
                    set_relay_safe('btnValveRough', False, arduino, safety, relay_map)
                except Exception:
                    print("❌ Failed to close rough valve during abort")
                return False
            else:
                print("✅ Pressure has begun to drop after opening rough valve; continuing pump procedure.")
        else:
            if baseline_volts is not None:
                print(f"📈 Starting from lower pressure ({baseline_volts:.3f} V <= {chamber_atmospheric} V) - skipping initial drop check")
            else:
                print("⚠️ Warning: could not read baseline chamber pressure - skipping initial drop check")
    except Exception as e:
        print(f"❌ Error while checking for initial pressure drop: {e}")
        # If the check fails unexpectedly, just continue (don't abort unless we know there's a problem)
        print("⚠️ Continuing pump procedure despite pressure check error")

    # Step 4: Wait until chamber pressure < chamber_medium_vacuum
    print(f"⏳ Step 4: Waiting for chamber pressure to drop below {chamber_medium_vacuum} V.\nMaximum wait time: {chamber_wait_time} seconds")
    # Wait for chamber to reach medium vacuum
    if not wait_for_analog_condition(
        arduino=arduino,
        safety=safety,
        condition_fn=lambda v: len(v) > 1 and float(v[1]) < chamber_medium_vacuum - 0.5,
        max_wait_time=chamber_wait_time,
        poll_interval=1.0
    ):
        print("⏰ Timeout waiting for chamber pressure to drop")
        return False
    
    # Step 5: Close rough valve
    print("🔀 Step 5: Closing rough valve")
    # Check safety (though closing should always be safe)
    safety_result = safety.check_button_safety('btnValveRough', is_auto_procedure=True)
    if not safety_result.allowed:
        print(f"Safety check failed for closing btnValveRough: {safety_result.message}")
        return False

    if not set_relay_safe('btnValveRough', False, arduino, safety, relay_map):
        print("Failed to close rough valve")
        return False

    print("Rough valve closed")
    
    # Step 6: Open backing valve
    print("🔀 Step 6: Opening backing valve")
    # Check safety
    safety_result = safety.check_button_safety('btnValveBacking', is_auto_procedure=True)
    if not safety_result.allowed:
        print(f"⚠️ Safety check failed for btnValveBacking: {safety_result.message}")
        return False

    if not set_relay_safe('btnValveBacking', True, arduino, safety, relay_map):
        print("❌ Failed to open backing valve")
        return False

    print("✅ Backing valve opened")
    
    # Step 7: Wait 5 seconds
    print("⏳ Step 7: Waiting 5 seconds for backing valve")
    time.sleep(5)
    
    # Step 8: Open turbo gate valve
    print("🔀 Step 8: Opening turbo gate valve")
    # Check safety
    safety_result = safety.check_button_safety('btnValveTurboGate', is_auto_procedure=True)
    if not safety_result.allowed:
        print(f"⚠️ Safety check failed for btnValveTurboGate: {safety_result.message}")
        return False

    if not set_relay_safe('btnValveTurboGate', True, arduino, safety, relay_map):
        print("❌ Failed to open turbo gate valve")
        return False

    print("✅ Turbo gate valve opened")
    
    # Step 9: Wait until chamber pressure < chamber_medium_vacuum again
    print(f"⏳ Step 9: Waiting for chamber pressure to drop below {chamber_medium_vacuum} V again")
    # Wait again after opening turbo gate for chamber pressure to reach medium vacuum
    if not wait_for_analog_condition(
        arduino=arduino,
        safety=safety,
        condition_fn=lambda v: len(v) > 1 and float(v[1]) < chamber_medium_vacuum,
        max_wait_time=chamber_wait_time,
        poll_interval=1.0
    ):
        print("⏰ Timeout waiting for chamber pressure to drop again")
        return False
    
    time.sleep(10)  # brief pause before next step

    # Step 10: Turn on turbo pump
    print("🌀 Step 10: Turning on turbo pump")
    # Check safety
    safety_result = safety.check_button_safety('btnPumpTurbo', is_auto_procedure=True)
    if not safety_result.allowed:
        print(f"⚠️ Safety check failed for btnPumpTurbo: {safety_result.message}")
        return False

    if not set_relay_safe('btnPumpTurbo', True, arduino, safety, relay_map):
        print("❌ Failed to turn on turbo pump")
        return False

    print("✅ Turbo pump turned on")

    # Step 11: Wait for turbo pump > 80 % spin speed
    print("🌀 Step 11: Waiting for turbo pump to reach > 80% spin speed")

    def turbo_spin_condition(v: List[float]) -> bool:
        # v[3] expected to be turbo spin percentage (0-100) or scaled value
        try:
            if len(v) <= 3:
                return False
            spin_val = float(v[3])
            return spin_val >= 3.5 # 3.5 V is about 80% speed for a 4.5V max gauge
        except Exception:
            return False

    if not wait_for_analog_condition(
        arduino=arduino,
        safety=safety,
        condition_fn=turbo_spin_condition,
        max_wait_time=300,
        poll_interval=1.0
    ):
        print("Timeout waiting for turbo pump to reach spin speed")
        return False
    
    # Step 12: Turn on Ion Gauge
    print("Step 12: Turning on Ion Gauge")  
    chamber_high_vacuum = safety_config.get('pressure_thresholds', {}).get('chamber_high_vacuum', 0.7)
    if arduino.get_analog_voltages()[1] < chamber_high_vacuum:
        # Check safety
        safety_result = safety.check_button_safety('btnIonGauge', is_auto_procedure=True)
        if not safety_result.allowed:
            print(f"Safety check failed for btnIonGauge: {safety_result.message}")
            return False
        # Use the dedicated toggle function
        if not toggle_ion_gauge(True, arduino, safety, relay_map):
            print("Failed to turn on Ion Gauge")
            return False
    
    print("✅ Pump procedure completed successfully!")
    return True


# Placeholder for other procedures
def vent_procedure(arduino: ArduinoController, 
                   safety: SafetyController, 
                   relay_map: Dict[str, int],
                   go_default_first: bool = False) -> bool:
    """
    Automated vent procedure.

    Steps:
    0): Turn off Ion Gauge if on
    1) Turn OFF turbo pump
    2) Wait for turbo spin < 65% (ai_volts[3] <= 3.05 V)
    3) Run short vent cycles for turbo braking: 100 ms open every 10 s for 5 cycles
    4) Wait for turbo spin < 20% (ai_volts[3] <= 1.3 V)
    5) Open vent valve
    6) Close vent valve after chamber pressure > atmosphere (ai_volts[1] > 4.6) and
       digital input 2 becomes False (door opened). This indicates chamber reached atmosphere
       and the door has opened.

    Returns True on success, False on failure.
    """
    print("💨 Starting vent procedure...")

    # Reset cancellation flag at start of procedure
    reset_cancellation_flag()

    # Get pressure thresholds from safety config
    safety_config = safety.safety_config

    if go_default_first:
        # Ensure system is in the default starting configuration before venting
        try:
            if not go_to_default_state(arduino, safety, relay_map):
                print("Failed to return to default state before vent procedure")
                return False
        except Exception as e:
            print(f"Exception while returning to default state: {e}")
            return False

    try:
        # Step 0: Turn off Ion Gauge if on
        print("Step 0: Turning OFF Ion Gauge if it is ON")
        if not toggle_ion_gauge(False, arduino, safety, relay_map):
            print("Failed to turn off Ion Gauge")
            return False
        
        # Step 1: Turn OFF turbo
        print("Step 1: Turning OFF turbo pump")
        # If turbo already off, skip below step
        if not safety.relay_states.get('btnPumpTurbo', False):
            print("Turbo pump is already OFF")
        else:
            if not set_relay_safe('btnPumpTurbo', False, arduino, safety, relay_map):
                print("Failed to turn off turbo pump")
                return False

        # Step 2: Wait for turbo spin < 65% (3.05 V)
        print("Step 2: Waiting for turbo spin < 65% (3.05 V)")
        def spin_below_65(v: List[float]) -> bool:
            try:
                return len(v) > 3 and float(v[3]) <= 3.05
            except Exception:
                return False

        if not wait_for_analog_condition(arduino=arduino, safety=safety, condition_fn=spin_below_65, max_wait_time=300, poll_interval=1.0):
            print("Timeout waiting for turbo spin < 65%")
            return False

        # Step 3: Short vent cycles for turbo braking
        
        print("Step 3: Performing turbo braking vent cycles")
        for cycle in range(20):
            # Check for cancellation before each cycle
            if is_procedure_cancelled():
                print("🛑 Short vent cycles cancelled by user")
                return False
                
            print(f"Short vent cycle {cycle+1}/20: opening vent for 150 ms")
            if not set_relay_safe('btnValveVent', True, arduino, safety, relay_map):
                print("Failed to open vent valve for braking")
                return False
            time.sleep(0.15)
            if not set_relay_safe('btnValveVent', False, arduino, safety, relay_map):
                print("Failed to close vent valve after braking pulse")
                return False
            # sleep until next 10s interval
            if cycle < 7:
                # Check cancellation during the 10s sleep too (split into 1s intervals)
                for _ in range(int(10.0 - 0.15)):
                    if is_procedure_cancelled():
                        print("🛑 Short vent cycles cancelled during sleep")
                        return False
                    time.sleep(1.0)
            #break if turbo spin < 25 % to save time
            volts = arduino.get_analog_voltages()
            if volts and float(volts[3]) < 1.3:
                print("Turbo spin < 25%, ready for constant vent.")
                break

        # Step 4: Wait for turbo spin < 20% (1.3 V)
        print("Step 4: Waiting for turbo spin < 20% (1.3 V)")
        def spin_below_20(v: List[float]) -> bool:
            try:
                return len(v) > 3 and float(v[3]) <= 1.3
            except Exception:
                return False

        if not wait_for_analog_condition(arduino=arduino, safety=safety, condition_fn=spin_below_20, max_wait_time=300, poll_interval=1.0):
            print("Timeout waiting for turbo spin < 20%")
            return False

        # Step 4.5: Close turbo gate valve and then backing valve for safety
        print("Step 4.5: Closing turbo gate valve and backing valve.")
        if not set_relay_safe('btnValveTurboGate', False, arduino, safety, relay_map):
            print("Failed to close turbo gate valve")
            return False
        if not set_relay_safe('btnValveBacking', False, arduino, safety, relay_map):
            print("Failed to close backing valve")
            return False
        time.sleep(5.0)  # brief pause to ensure valves closed
        
        # Step 5: Open vent valve
        print("Step 5: Opening vent valve")
        if not set_relay_safe('btnValveVent', True, arduino, safety, relay_map):
            print("Failed to open vent valve")
            return False

        # Step 6: Wait for chamber pressure > chamber_atmospheric threshold and then digital input 2 -> False
        chamber_atmospheric = safety_config.get('pressure_thresholds', {}).get('chamber_atmospheric', 4.5)
        print(f"💨 Step 6: Waiting for chamber pressure > {chamber_atmospheric} V (atmosphere) and door open signal")

        # First wait for chamber pressure to indicate atmosphere
        def chamber_atm(v: List[float]) -> bool:
            try:
                is_atm = len(v) > 1 and float(v[1]) > chamber_atmospheric
                if is_atm:
                    print(f"🎯 Chamber pressure reached atmosphere: {float(v[1]):.2f} V")
                return is_atm
            except Exception:
                return False

        if not wait_for_analog_condition(arduino=arduino, safety=safety, condition_fn=chamber_atm, max_wait_time=3600, poll_interval=2.0):
            print("⏱️ Timeout waiting for chamber to reach atmosphere")
            # Ensure vent valve closed before returning
            set_relay_safe('btnValveVent', False, arduino, safety, relay_map)
            return False

        # Now poll the door interlock until it indicates "opened".
        # Prefer using safety.digital_inputs (normalized booleans). Fall back to reading
        # raw arduino.get_digital_inputs() and normalize to bools.
        print("🚪 Chamber at atmosphere, now waiting for door-open digital input to indicate open")
        wait_start = time.time()
        max_wait = 600  # seconds
        door_opened = False
        # Door input: digital_inputs[2] = Door interlock (Arduino pin 49)
        # Per sput.yml and safety_conditions.yml: [0]=Water, [1]=Rod, [2]=Door, [3]=Spare
        door_idx = 2
        while time.time() - wait_start < max_wait:
            di_list = None
            try:
                # Use safety.digital_inputs if available (already normalized to bool)
                if hasattr(safety, 'digital_inputs') and safety.digital_inputs is not None:
                    di_list = list(safety.digital_inputs)
                else:
                    # Fall back to reading from Arduino directly
                    raw_di = arduino.get_digital_inputs()
                    if raw_di is not None:
                        di_list = [bool(x) for x in raw_di]
            except Exception:
                di_list = None

            if di_list is None:
                time.sleep(1.0)
                continue

            # If the door input exists and reports False (unsafe/open), treat as door opened
            if len(di_list) > door_idx and (not bool(di_list[door_idx])):
                door_opened = True
                print(f"🚪 Door opened detected via digital_input[{door_idx}] = {di_list[door_idx]}")
                break
            else:
                # Debug: show current door state while waiting
                if len(di_list) > door_idx:
                    print(f"⏳ Waiting for door... digital_input[{door_idx}] = {di_list[door_idx]} (need False for door open)")

            time.sleep(1.0)

        # Close vent valve regardless; ensure we always attempt to close it.
        try:
            print("🔀 Closing vent valve after venting complete")
            if not set_relay_safe('btnValveVent', False, arduino, safety, relay_map):
                print("❌ Failed to close vent valve")
        except Exception:
            print("⚠️ Warning: exception while attempting to close vent valve after venting")

        if not door_opened:
            print("⏱️ Timeout waiting for door open signal after atmosphere reached")
            return False

        print("✅ Vent procedure completed successfully")
        return True

    except Exception as e:
        print(f"Exception in vent_procedure: {e}")
        try:
            set_relay_safe('btnValveVent', False, arduino, safety, relay_map)
        except Exception:
            pass
        return False

def vent_loadlock_procedure(arduino: ArduinoController, 
                            safety: SafetyController,
                            relay_map: Dict[str, int],
                            go_to_default_first: bool = False) -> bool:
    """
    Automated vent load-lock procedure.
    """

    print("💨 Starting vent load-lock procedure...")
    
    # Reset cancellation flag at start of procedure
    reset_cancellation_flag()
    
    if go_to_default_first:
        # Ensure system is in the default starting configuration before venting
        try:
            if not go_to_default_state(arduino, safety, relay_map):
                print("Failed to return to default state before vent load-lock procedure")
                return False
        except Exception as e:
            print(f"❌ Error while returning to default state: {e}")
            return False
    else:
        if not turbo_protection_procedure(safety, arduino, relay_map):
            print("Failed to perform turbo protection procedure before venting load-lock, aborting...")
            return False

    # Open load-lock vent valve
    print("Opening load-lock vent valve")     
    safety_result = safety.check_button_safety('btnValveLoadLockVent', is_auto_procedure=True)
    if not safety_result.allowed:
        print(f"Safety check failed for btnValveLoadLockVent: {safety_result.message}")
        return False
    if not set_relay_safe('btnValveLoadLockVent', True, arduino, safety, relay_map):
        print("Failed to open load-lock vent valve")
        return False

    # Wait for load-lock pressure to indicate atmosphere (ai_volts[0] > 2.7 V)
    print("Waiting for load-lock pressure to reach atmosphere (> 2.7 V)")
    def loadlock_atm(v: List[float]) -> bool:
        try:
            return len(v) > 0 and float(v[0]) > 2.7
        except Exception:
            return False
    
    if not wait_for_analog_condition(arduino=arduino, safety=safety, condition_fn=loadlock_atm, max_wait_time=20, poll_interval=1.0):
        print("Timeout waiting for load-lock to reach atmosphere (20s timeout)")
        # Ensure vent valve closed before returning
        set_relay_safe('btnValveLoadLockVent', False, arduino, safety, relay_map)
        print("Load-lock vent valve closed due to timeout - load-lock should be at atmosphere")
        print("Load-lock vent procedure completed (with timeout)")
        return True  # Return True since load-lock should be vented even if gauge didn't reach exact threshold
    print("Load-lock has reached atmosphere")
    time.sleep(3.0)  # brief pause to ensure pressure stabilized

    # Close load-lock vent valve
    print("Closing load-lock vent valve")
    set_relay_safe('btnValveLoadLockVent', False, arduino, safety, relay_map)   
    print("Load-lock vent procedure completed successfully, load-lock is at atmosphere, proceed to load sample/s on stage.\n\
          Replace sample stage on load-lock arm once samples are in place. Then run load/unload procedure to pump down load-lock\n\
          and enable loading/unloading samples.")
    # print("Load-lock vent procedure completed successfully, load-lock is at atmosphere, putting system back to default state.")
    # if not go_to_default_state(arduino, safety, relay_map):
    #     print("Warning: Failed to return to default state after venting load-lock")
    #     return False

    return True

def load_unload_procedure(arduino: ArduinoController, 
                          safety: SafetyController, 
                            relay_map: Dict[str, int]) -> bool:
    """
    Automated load/unload procedure.
    Steps:
    1) Turbo protection procedure (turn off turbo, ion gauge, close turbo gate)
    2) Check load-lock vacuum state, pumpdown if needed
    3) If load-lock pressure < loadlock_rough_vacuum and chamber pressure < chamber_medium_vacuum:
       a) Open load-lock gate valve. 
       b) Begin temporary allowance of load-lock arm home (digital_inputs[1]) to be false until OK button clicked.
       c) Bring up dialog saying "Use load-lock arm to load/unload sample, return arm to home position and then click button below."
       d) Check if load-lock arm is in home position when OK button is clicked. If not, do not close the dialog and bring 
        up new dialog saying "Load-lock arm is not in home position, please return it to home and then click button below."
        e) Close load-lock gate valve only if load-lock arm is in home position as confirmed by digital_inputs[1] going from False to True.
       """
    print("🔄 Starting load/unload procedure...")
    
    # Reset cancellation flag at start of procedure
    reset_cancellation_flag()
    
    # Step 1: Turbo protection procedure
    if not turbo_protection_procedure(safety, arduino, relay_map):
        print("Failed to perform turbo protection procedure before load/unload, aborting...")
        return False

    # Step 2: Check load-lock vacuum state, pumpdown if needed
    print("Step 2: Checking load-lock vacuum state...")
    
    # Get pressure thresholds from safety config
    safety_config = safety.safety_config
    loadlock_rough_vacuum = safety_config.get('pressure_thresholds', {}).get('loadlock_rough_vacuum', 1.6)
    chamber_medium_vacuum = safety_config.get('pressure_thresholds', {}).get('chamber_medium_vacuum', 2.0)
    
    # Check current load-lock pressure
    try:
        voltages = arduino.get_analog_voltages()
        if voltages is None or len(voltages) < 1:
            print("Failed to read analog voltages")
            return False
            
        loadlock_pressure = float(voltages[0])  # ai_volts[0] is load-lock pressure
        chamber_pressure = float(voltages[1])   # ai_volts[1] is chamber pressure
        
        print(f"Load-lock pressure: {loadlock_pressure:.3f} V, Chamber pressure: {chamber_pressure:.3f} V")

        if chamber_pressure > chamber_medium_vacuum:
            print(f"Abort: Chamber pressure too high for load/unload: {chamber_pressure:.3f} V >= {chamber_medium_vacuum} V, pump chamber first.")
            return False
        
    except Exception as e:
        print(f"❌ Error reading pressures: {e}")
        return False
    
    # If load-lock pressure is too high, pump it down
    if loadlock_pressure >= loadlock_rough_vacuum:
        print("Load-lock pressure too high, pumping down...")
        
        # Ensure scroll pump is ON & chamber rough valve is closed and load-lock vent valve is closed
        print("Ensuring scroll pump is ON and relevant valves are closed...")
        system = safety.get_safety_status_summary()
        for relay in ['btnPumpScroll', 'btnValveRough', 'btnValveLoadLockVent']:
            desired_state = True if relay == 'btnPumpScroll' else False
            current_state = system['relay_states'].get(relay, None)
            if current_state != desired_state:
                if not set_relay_safe(relay, desired_state, arduino, safety, relay_map):
                    print(f"Failed to set {relay} to {'ON' if desired_state else 'OFF'}")
                    return False
        print("Relevant relays are in correct state.")

        # Open load-lock rough valve to pump down
        if not set_relay_safe('btnValveLoadLockRough', True, arduino, safety, relay_map):
            print("Failed to open load-lock rough valve")
            return False
            
        # Wait for load-lock to reach rough vacuum
        print(f"Waiting for load-lock pressure to drop below {loadlock_rough_vacuum} V...")
        def loadlock_rough(v: List[float]) -> bool:
            try:
                return len(v) > 0 and float(v[0]) < loadlock_rough_vacuum
            except Exception:
                return False
        
        if not wait_for_analog_condition(
            arduino=arduino,
            safety=safety,
            condition_fn=loadlock_rough,
            max_wait_time=300,
            poll_interval=1.0
        ):
            print("Timeout waiting for load-lock to reach rough vacuum")
            # Close rough valve and abort
            set_relay_safe('btnValveLoadLockRough', False, arduino, safety, relay_map)
            return False
            
        # Close load-lock rough valve
        print("Load-lock pumped down, closing rough valve")
        if not set_relay_safe('btnValveLoadLockRough', False, arduino, safety, relay_map):
            print("Warning: Failed to close load-lock rough valve")
    
    # Step 3: Check if conditions are met to open gate valve
    print("Step 3: Checking conditions for gate valve opening...")
    
    # Re-read pressures after potential pumpdown
    try:
        voltages = arduino.get_analog_voltages()
        if voltages is None or len(voltages) < 2:
            print("Failed to read analog voltages")
            return False
            
        loadlock_pressure = float(voltages[0])
        chamber_pressure = float(voltages[1])
        
    except Exception as e:
        print(f"❌ Error reading pressures: {e}")
        return False
    
    # Check if both chambers have sufficient vacuum
    if loadlock_pressure >= loadlock_rough_vacuum:
        print(f"Load-lock pressure still too high: {loadlock_pressure:.3f} V >= {loadlock_rough_vacuum} V")
        return False
        
    if chamber_pressure >= chamber_medium_vacuum:
        print(f"Chamber pressure too high: {chamber_pressure:.3f} V >= {chamber_medium_vacuum} V")
        return False
    
    print("Pressure conditions met for gate valve opening")
    
    # Step 3a: Open load-lock gate valve
    print("Step 3a: Opening load-lock gate valve...")
    if not set_relay_safe('btnValveLoadLockGate', True, arduino, safety, relay_map):
        print("Failed to open load-lock gate valve")
        return False
    
    print("Load-lock gate valve opened - load/unload access available")
    
    # Turn on chamber light for visibility during load/unload
    print("💡 Turning on chamber light...")
    if not set_relay_safe('btnLightBulb', True, arduino, safety, relay_map):
        print("Warning: Failed to turn on chamber light (non-critical)")
    else:
        print("✅ Chamber light turned on")
    
    # Steps 3b-3e: Handle load-lock arm and user interaction with real dialog
    print("Step 3b-3e: Load/unload arm management...")
    
    # NOTE: Dialog display causes Qt threading issues when called from background thread
    # Instead, we'll return a special status that tells the GUI to handle the dialog
    print("Load-lock gate valve is open - procedure paused for user interaction")
    print("IMPORTANT: User must return load-lock arm to home position before closing gate valve")
    
    # Return a special value indicating that the gate valve is open and waiting for user
    # The GUI thread will handle the dialog and complete the procedure
    return "GATE_OPEN_WAITING_USER"

def sputter_procedure(arduino: ArduinoController, 
                      safety: SafetyController, 
                      relay_map: Dict[str, int]) -> bool:
    """
    Sputter procedure. This procedure is used for performing magnetron sputtering.
    This does:

    1) Turbo pump standby spin control (maintain turbo at ~66% speed). Turbo will be turned on & off
    to target 60% spin speed to reduce turbo wear when exposed to gas load.
    2) Gas is then introduced manually by the user via the GUI to reach desired pressure for sputtering.
    3) When sputtering is complete, user clicks sputter button again to cancel sputter_procedure and have system go 
    back to default state.
    
    Note: This procedure runs indefinitely until cancelled by clicking the sputter button again.
    When cancelled, the system will be returned to default state via abort_and_go_default.
    """
    print("⚡ Starting sputter procedure...")
    print("🌀 Turbo pump will maintain standby speed (60% spin)for sputtering operations")
    print("💨 User can manually control gas valves. Set gas flow and open valve to bring in gas.")
    print("🛑 Click the sputter button again to cancel this procedure and return to default state")

    # Reset cancellation flag at start of procedure
    reset_cancellation_flag()
    
    #Turn off ion gauge if it is on:
    if not toggle_ion_gauge(False, arduino, safety, relay_map):  # Ensure ion gauge is off
        print("Failed to turn off ion gauge")
        return False
    
    # Set sputter procedure active state to enable gas valve override
    safety.set_sputter_procedure_active(True)
    print("🌟 Gas valves are now available for manual control during sputter procedure")

    # Turn ON mains power for RF/DC supplies (pin 22)
    print("⚡ Turning ON mains power for sputtering supplies...")
    if not set_relay_safe('btnMainsPower', True, arduino, safety, relay_map):
        print("❌ Failed to turn ON mains power - aborting sputter procedure")
        safety.set_sputter_procedure_active(False)
        return False
    print("✅ Mains power enabled - RF/DC supplies ready")

    try:
        # Run turbo standby spin control indefinitely until cancelled
        # The GUI will handle cancellation by stopping this procedure and calling abort_and_go_default
        result = turbo_standby_spin_control(arduino, safety, relay_map)
        
        # Check results after turbo standby control completes
        if is_procedure_cancelled():
            print("🛑 Sputter procedure was cancelled")
            # Don't return here - let finally block handle cleanup
        elif not result:
            print("Failed to perform turbo standby spin control for sputter procedure")
            # Don't return here - let finally block handle cleanup
        else:
            # If we reach here, the turbo standby control completed normally
            print("Sputter procedure completed")
        
    finally:
        # Always clean up when procedure ends (whether cancelled, failed, or completed)
        print("🧹 Cleaning up sputter procedure...")
        
        # Turn OFF mains power first for safety
        try:
            print("⚡ Turning OFF mains power...")
            
            # Force update the relay state to ensure safety controller knows mains is currently ON
            safety.relay_states['btnMainsPower'] = True
            
            # Try the safe method first
            if not set_relay_safe('btnMainsPower', False, arduino, safety, relay_map):
                print("⚠️ set_relay_safe failed for mains power - trying direct Arduino command...")
                # Fallback: try direct Arduino command
                try:
                    mains_relay = relay_map.get('btnMainsPower')
                    if mains_relay:
                        arduino.set_relay(mains_relay, False)
                        safety.relay_states['btnMainsPower'] = False  # Update state manually
                        print("✅ Mains power turned off via direct Arduino command")
                    else:
                        print("❌ Cannot find mains power relay in relay_map")
                except Exception as e2:
                    print(f"❌ Direct mains power shutdown also failed: {e2}")
            else:
                print("✅ Mains power disabled - RF/DC supplies turned off")
        except Exception as e:
            print(f"❌ Warning: Failed to turn OFF mains power: {e}")
            # Last resort: try direct relay command
            try:
                mains_relay = relay_map.get('btnMainsPower', 22)  # Default to pin 22
                arduino.set_relay(mains_relay, False)
                print("✅ Mains power turned off via emergency direct command")
            except Exception as e3:
                print(f"❌ Emergency mains power shutdown failed: {e3}")
        
        # Close all gas valves for safety
        gas_valves = ['btnValveGas1', 'btnValveGas2', 'btnValveGas3']
        for gas_valve in gas_valves:
            try:
                if safety.relay_states.get(gas_valve, False):  # Only close if currently open
                    print(f"Closing {gas_valve} after sputter procedure")
                    set_relay_safe(gas_valve, False, arduino, safety, relay_map)
            except Exception as e:
                print(f"Warning: Failed to close {gas_valve}: {e}")
        
        # Clear sputter procedure active state
        safety.set_sputter_procedure_active(False)
        print("🌟 Gas valve override disabled - sputter procedure ended")
    
    # Return success if cancelled or completed normally, failure if turbo control failed
    if is_procedure_cancelled():
        return True  # Cancellation is considered successful
    else:
        return result  # Return the actual result from turbo standby control

def turbo_standby_spin_control(arduino: ArduinoController,
                              safety: SafetyController,
                              relay_map: Dict[str, int],
                              target_speed_percent: float = 60.0,
                              max_run_time: int = 14400,
                              poll_interval: float = 2.0) -> bool:
    """
    Manual turbo pump standby spin mode control.
    
    Maintains turbo pump at a reduced spin speed by cycling the pump on/off
    to keep the speed oscillating around the target setpoint.
    
    Args:
        arduino: ArduinoController instance
        safety: SafetyController instance
        relay_map: Dictionary mapping button names to relay numbers
        target_speed_percent: Target spin speed percentage (default 66%)
        max_run_time: Maximum time to run standby mode in seconds (default 1 hour)
        poll_interval: How often to check and adjust speed in seconds (default 2s)
        
    Returns:
        True if standby mode completed successfully, False on error
    """
    print(f"Starting turbo pump standby spin control at {target_speed_percent}% target speed")
    
    # Convert target percentage to voltage using scaling factors from safety_conditions.yml
    # turbo_spin scaling_factor: 25.0, offset: -12.5
    # Formula: percentage = (voltage * scaling_factor) + offset
    # Inverse: voltage = (percentage - offset) / scaling_factor
    target_voltage = (target_speed_percent - (-12.5)) / 25.0
    
    # Control parameters
    tolerance = 0.1  # Voltage tolerance (±0.1V around target)
    hysteresis = 0.05  # Hysteresis to prevent rapid cycling
    
    start_time = time.time()
    pump_state = False  # Track current pump state
    
    print(f"Target voltage: {target_voltage:.2f}V (±{tolerance:.2f}V tolerance)")
    print(f"Will run for maximum {max_run_time} seconds")
    
    # Ensure turbo pump starts in OFF state
    if not set_relay_safe('btnPumpTurbo', False, arduino, safety, relay_map):
        print("Failed to ensure turbo pump starts OFF")
        return False
    
    while time.time() - start_time < max_run_time:
        # Check for cancellation signal
        if is_procedure_cancelled():
            print("🛑 Turbo standby spin control cancelled by user")
            break
            
        try:
            # Read current turbo speed voltage
            voltages = arduino.get_analog_voltages()
            if voltages is None or len(voltages) <= 3:
                print("Failed to read turbo speed voltage")
                time.sleep(poll_interval)
                continue
                
            current_speed_voltage = float(voltages[3])  # ai_volts[3] is turbo speed
            # Convert voltage to percentage using scaling factors from safety_conditions.yml
            # turbo_spin scaling_factor: 25.0, offset: -12.5
            current_speed_percent = (current_speed_voltage * 25.0) + (-12.5)
            
            # Determine if we need to turn pump on or off
            should_pump_on = False
            
            if not pump_state:  # Pump is currently OFF
                # Turn on if speed is below target minus hysteresis
                if current_speed_voltage < (target_voltage - hysteresis):
                    should_pump_on = True
            else:  # Pump is currently ON
                # Turn off if speed is above target plus hysteresis
                if current_speed_voltage < (target_voltage + hysteresis):
                    should_pump_on = True
            
            # Update pump state if needed
            if should_pump_on != pump_state:
                action = "ON" if should_pump_on else "OFF"
                #print(f"Speed: {current_speed_percent:.1f}% ({current_speed_voltage:.2f}V) - Turning pump {action}")
                
                if not set_relay_safe('btnPumpTurbo', should_pump_on, arduino, safety, relay_map, suppress_logging=True):
                    print(f"Failed to turn turbo pump {action}")
                    return False
                    
                pump_state = should_pump_on
            else:
                # Just log current status occasionally
                if int(time.time() - start_time) % 30 == 0:  # Every 30 seconds
                    status = "ON" if pump_state else "OFF"
                    print(f"Standby mode: Speed {current_speed_percent:.1f}% (target {target_speed_percent:.1f}%), pump {status}")
            
            # Update safety controller with fresh readings
            try:
                safety.update_system_state(analog_inputs=voltages)
            except Exception:
                pass
                
        except Exception as e:
            print(f"❌ Error in standby spin control: {e}")
            time.sleep(poll_interval)
            continue
            
        time.sleep(poll_interval)
    
    print(f"Turbo standby spin control completed after {max_run_time} seconds")
    
    # Turn off turbo pump when done
    print("Turning OFF turbo pump after standby mode")
    if not set_relay_safe('btnPumpTurbo', False, arduino, safety, relay_map):
        print("Warning: Failed to turn off turbo pump after standby mode")
        return False
        
    return True

def abort_and_go_default(arduino: ArduinoController,
                         safety: SafetyController,
                         relay_map: Dict[str, int]) -> tuple[bool, str]:
    """Abort current procedure by returning system to the configured default state.

    Returns:
        (success: bool, message: str)
    """
    try:
        # First, signal any running procedures to cancel
        cancel_running_procedures()
        
        # Give running procedures a moment to notice the cancellation
        time.sleep(0.5)
        
        # Special handling for sputter procedure - close gas valves and clear state
        if safety.is_sputter_procedure_active():
            print("🧹 Aborting sputter procedure - closing gas valves and turning off mains power...")
            
            # Turn OFF mains power first for safety
            try:
                print("⚡ Shutdown: Turning OFF mains power...")
                
                # Force update the relay state to ensure safety controller knows mains is currently ON
                safety.relay_states['btnMainsPower'] = True
                
                # Try the safe method first
                if not set_relay_safe('btnMainsPower', False, arduino, safety, relay_map):
                    print("⚠️ set_relay_safe failed for mains power during abort - trying direct Arduino command...")
                    # Fallback: try direct Arduino command
                    try:
                        mains_relay = relay_map.get('btnMainsPower')
                        if mains_relay:
                            arduino.set_relay(mains_relay, False)
                            safety.relay_states['btnMainsPower'] = False  # Update state manually
                            print("✅ Mains power turned off via direct Arduino command during abort")
                        else:
                            print("❌ Cannot find mains power relay in relay_map during abort")
                            raise Exception("Cannot find mains power relay in relay_map")
                    except Exception as e2:
                        print(f"❌ Direct mains power shutdown also failed during abort: {e2}")
                        raise Exception(f"Direct mains power shutdown failed: {e2}")
                else:
                    print("✅ Mains power disabled - RF/DC supplies turned off")
            except Exception as e:
                print(f"❌ Warning: Failed to turn OFF mains power during abort: {e}")
                # Last resort: try direct relay command
                try:
                    mains_relay = relay_map.get('btnMainsPower', 22)  # Default to pin 22
                    arduino.set_relay(mains_relay, False)
                    safety.relay_states['btnMainsPower'] = False
                    print("✅ Mains power turned off via emergency direct command during abort")
                except Exception as e3:
                    print(f"❌ Emergency mains power shutdown failed during abort: {e3}")
            
            gas_valves = ['btnValveGas1', 'btnValveGas2', 'btnValveGas3']
            for gas_valve in gas_valves:
                try:
                    if safety.relay_states.get(gas_valve, False):  # Only close if currently open
                        print(f"Emergency closing {gas_valve}")
                        set_relay_safe(gas_valve, False, arduino, safety, relay_map)
                except Exception as e:
                    print(f"Warning: Failed to emergency close {gas_valve}: {e}")
            
            # Clear sputter procedure active state

            safety.set_sputter_procedure_active(False)
            print("🌟 Gas valve override disabled due to procedure abort")
        
        # Now proceed with going to default state
        ok = go_to_default_state(arduino, safety, relay_map)
        if ok:
            return True, "System returned to default state"
        else:
            return False, "Failed to return to default state"
    except Exception as e:
        return False, f"Exception during abort: {e}"
