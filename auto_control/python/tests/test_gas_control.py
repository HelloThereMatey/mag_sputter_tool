import sys
import time
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from auto_control.python.gas_control.subprocess_controller import GasFlowController

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_gas_controller():
    print("="*60)
    print("GAS FLOW CONTROLLER DIAGNOSTIC TOOL")
    print("="*60)
    
    # 1. Configuration
    config = {
        'serial_port': None,  # Force auto-detection
        'mfcs': {
            'Ar': {'unit_id': 'A', 'max_flow': 200.0, 'gas_type': 'Ar'},
            'N2': {'unit_id': 'B', 'max_flow': 100.0, 'gas_type': 'N2'},
            'O2': {'unit_id': 'C', 'max_flow': 100.0, 'gas_type': 'O2'}
        }
    }
    
    print("\n1. Initializing Controller...")
    # Exclude nothing for this standalone test, or maybe exclude known Arduino ports if running on the real system
    # For now, we assume this script is run when the main app is NOT running, so no conflicts.
    controller = GasFlowController(config)
    
    print(f"\n   Configured Port: {controller.config.get('serial_port')}")
    
    if not controller.config.get('serial_port'):
        print("❌ Failed to detect port during initialization.")
        return
        
    # 2. Start Controller
    print("\n2. Starting Controller...")
    if controller.start():
        print("✅ Controller started successfully.")
    else:
        print("❌ Failed to start controller.")
        return
        
    # 3. Test Readings
    print("\n3. Testing Readings (5 seconds)...")
    for i in range(5):
        print(f"   Reading {i+1}/5:")
        readings = controller.get_all_readings()
        for name, reading in readings.items():
            if reading:
                print(f"     {name}: {reading.mass_flow:.2f} sccm (Setpoint: {reading.setpoint:.2f})")
            else:
                print(f"     {name}: No reading")
        time.sleep(1)
        
    # 4. Test Setpoint (Safe low value)
    test_mfc = 'Ar'
    test_flow = 10.0
    print(f"\n4. Testing Setpoint on {test_mfc} -> {test_flow} sccm...")
    
    if controller.set_flow_rate(test_mfc, test_flow):
        print(f"✅ Command sent. Verifying...")
        time.sleep(2)
        reading = controller.get_reading(test_mfc)
        if reading:
            print(f"   Current Flow: {reading.mass_flow:.2f} sccm")
            print(f"   Current Setpoint: {reading.setpoint:.2f} sccm")
            if abs(reading.setpoint - test_flow) < 0.5:
                print("✅ Setpoint verified!")
            else:
                print("❌ Setpoint mismatch.")
        else:
            print("❌ Could not get reading.")
    else:
        print("❌ Failed to set flow rate.")
        
    # 5. Stop Flow
    print(f"\n5. Stopping Flow on {test_mfc}...")
    controller.set_flow_rate(test_mfc, 0.0)
    time.sleep(1)
    reading = controller.get_reading(test_mfc)
    if reading:
        print(f"   Current Setpoint: {reading.setpoint:.2f} sccm")
        
    # 6. Shutdown
    print("\n6. Shutting down...")
    controller.stop()
    print("✅ Done.")

if __name__ == "__main__":
    test_gas_controller()
