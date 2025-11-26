import sys
import time
import os
from pathlib import Path

# Add parent directory to path to allow imports
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
sys.path.append(str(parent_dir))

try:
    from arduino_controller import ArduinoController
except ImportError:
    print("Error: Could not import ArduinoController. Make sure you are running this from the correct directory.")
    sys.exit(1)

def test_arduino():
    print("="*60)
    print("ARDUINO CONNECTION & DIGITAL INPUTS TEST")
    print("="*60)

    controller = ArduinoController()
    
    # 1. Connect
    print("\n1. Attempting connection...")
    # Force full detection to be sure
    port = controller.find_arduino_port_with_test()
    if not port:
        print("❌ Could not find Arduino port.")
        return

    print(f"   Found Arduino on: {port}")
    if controller.connect(port):
        print("✅ Connected successfully.")
    else:
        print("❌ Failed to connect.")
        return

    # 2. Test Loop
    print("\n2. Starting test loop (Press Ctrl+C to stop)...")
    print(f"   Testing GET_DIGITAL_INPUTS and STATUS every 1 second.")
    
    try:
        count = 0
        while True:
            count += 1
            print(f"\n--- Iteration {count} ---")
            
            # Test Digital Inputs
            start_time = time.time()
            inputs = controller.get_digital_inputs()
            duration = time.time() - start_time
            
            if inputs is not None:
                print(f"✅ Digital Inputs ({duration:.3f}s): {inputs}")
                # Interpret inputs (Door, Water, Rod, Spare)
                # Note: True = Safe/Closed, False = Unsafe/Open
                labels = ["Door", "Water", "Rod", "Spare"]
                status_str = ", ".join([f"{l}:{'Safe' if s else 'ALARM'}" for l, s in zip(labels, inputs)])
                print(f"   Status: {status_str}")
            else:
                print(f"❌ Digital Inputs ({duration:.3f}s): FAILED/TIMEOUT")

            # Test Status (Relays)
            start_time = time.time()
            status = controller.get_status()
            duration = time.time() - start_time
            
            if status is not None:
                # Just print count of ON relays to keep it short
                on_count = sum(1 for s in status if s)
                print(f"✅ Relay Status   ({duration:.3f}s): {on_count} relays ON")
            else:
                print(f"❌ Relay Status   ({duration:.3f}s): FAILED/TIMEOUT")
                
            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\nTest stopped by user.")
    finally:
        print("\n3. Disconnecting...")
        controller.disconnect()
        print("Done.")

if __name__ == "__main__":
    test_arduino()
