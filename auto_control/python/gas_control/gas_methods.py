"""Gas control utility methods for the sputter control system.

Provides standalone utility functions for gas flow management that can be
called from the main application without bloating app.py.
"""

import time
from typing import Tuple, Optional, Dict, Any

# Support both package and script execution
try:
    from ..auto_procedures import set_relay_safe
except ImportError:
    try:
        from auto_procedures import set_relay_safe
    except ImportError:
        # Fallback for when called from other contexts
        set_relay_safe = None


def execute_zero_gas_flows(
    gas_controller,
    arduino_controller,
    safety_controller,
    relay_map: Dict[str, int],
    mfc_timer=None
) -> Tuple[bool, str]:
    """Execute zero gas flows procedure.
    
    This function:
    1. Starts the gas controller (if not running)
    2. Sets all MFC flows to 0 SCCM
    3. Closes all gas valves with safety checks
    4. Stops the gas controller
    
    Args:
        gas_controller: GasFlowController instance
        arduino_controller: ArduinoController instance for valve control
        safety_controller: SafetyController instance for safety checks
        relay_map: Dictionary mapping button names to relay numbers
        mfc_timer: Optional QTimer to stop after gas controller shutdown
        
    Returns:
        Tuple[bool, str]: (success, message)
    """
    try:
        # Step 1: Ensure gas controller is available
        if not gas_controller:
            return (False, "Gas controller not available")
        
        print("➡️ Step 1: Ensuring gas controller is running...")
        
        # Start gas controller if not running
        if not gas_controller.is_running():
            try:
                gas_controller.start()
                time.sleep(0.5)  # Wait for initialization
                print("  ✅ Gas controller started")
            except Exception as e:
                return (False, f"Failed to start gas controller: {e}")
        else:
            print("  ℹ️ Gas controller already running")
        
        # Step 2: Zero all flows
        print("➡️ Step 2: Zeroing all MFC flows...")
        zero_failures = []
        
        for mfc_id in gas_controller.channels.keys():
            try:
                success = gas_controller.set_flow_rate(mfc_id, 0.0)
                if success:
                    print(f"  ✅ {mfc_id} flow set to 0 SCCM")
                else:
                    print(f"  ⚠️ {mfc_id} flow zero failed")
                    zero_failures.append(mfc_id)
            except Exception as e:
                print(f"  ❌ Error zeroing {mfc_id}: {e}")
                zero_failures.append(mfc_id)
        
        # Wait for flows to settle
        time.sleep(1.0)
        
        # Step 3: Close all gas valves
        print("➡️ Step 3: Closing all gas valves...")
        valve_failures = []
        
        if set_relay_safe is None:
            print("  ⚠️ Warning: set_relay_safe not available, skipping valve closure")
        else:
            gas_valve_buttons = ['btnValveAr', 'btnValveN2', 'btnValveO2']
            for valve_btn in gas_valve_buttons:
                if valve_btn in relay_map:
                    try:
                        success = set_relay_safe(
                            valve_btn, False,
                            arduino_controller, safety_controller, relay_map
                        )
                        if success:
                            print(f"  ✅ {valve_btn} closed")
                        else:
                            print(f"  ⚠️ {valve_btn} close failed (safety check)")
                            valve_failures.append(valve_btn)
                    except Exception as e:
                        print(f"  ❌ Error closing {valve_btn}: {e}")
                        valve_failures.append(valve_btn)
        
        # Step 4: Stop gas controller
        print("➡️ Step 4: Stopping gas controller...")
        try:
            gas_controller.stop()
            print("  ✅ Gas controller stopped")
        except Exception as e:
            print(f"  ⚠️ Error stopping gas controller: {e}")
        
        # Stop MFC timer if provided
        if mfc_timer is not None:
            try:
                if mfc_timer.isActive():
                    mfc_timer.stop()
                    print("  ✅ MFC timer stopped")
            except Exception as e:
                print(f"  ⚠️ Error stopping MFC timer: {e}")
        
        # Build result message
        if zero_failures or valve_failures:
            failures = []
            if zero_failures:
                failures.append(f"Flow zero failures: {', '.join(zero_failures)}")
            if valve_failures:
                failures.append(f"Valve close failures: {', '.join(valve_failures)}")
            
            message = f"Gas flows zeroed with warnings:\n" + "\n".join(failures)
            return (True, message)
        else:
            return (True, "Gas flows zeroed and system shutdown successfully")
        
    except Exception as e:
        return (False, f"Error during zero flows procedure: {str(e)}")