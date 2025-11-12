"""
Auto-Connection Test Script
Tests the automatic Arduino detection and connection functionality
"""

from arduino_controller import ArduinoController
import time

def test_auto_connection():
    """Test automatic Arduino connection."""
    print("Arduino Auto-Connection Test")
    print("=" * 35)
    
    controller = ArduinoController()
    
    # Test auto-connection
    success = controller.auto_connect()
    
    if success:
        print(f"\n✅ SUCCESS: Auto-connected to Arduino!")
        print(f"   Port: {controller.serial_port.port}")
        
        # Test a few relay commands
        print("\n🧪 Testing relay commands...")
        
        # Turn on relay 1
        if controller.set_relay(1, True):
            print("✅ Relay 1 ON - Success")
        else:
            print("❌ Relay 1 ON - Failed")
        
        time.sleep(1)
        
        # Turn off relay 1
        if controller.set_relay(1, False):
            print("✅ Relay 1 OFF - Success")
        else:
            print("❌ Relay 1 OFF - Failed")
        
        # Get status
        states = controller.get_status()
        if states:
            print(f"✅ Status query - Success: {states}")
        else:
            print("❌ Status query - Failed")
        
        # Disconnect
        controller.disconnect()
        print("🔌 Disconnected from Arduino")
        
    else:
        print("\n❌ FAILED: Could not auto-connect to Arduino")
        print("\nTroubleshooting:")
        print("1. Check Arduino is connected via USB")
        print("2. Verify firmware is uploaded")
        print("3. Check no other programs are using the serial port")

if __name__ == "__main__":
    test_auto_connection()
