"""
Arduino Port Tester - Test serial communication with Arduino
Cross-platform support for Windows, Linux, and Raspberry Pi
Run this to debug connection issues without the GUI
"""

import serial
import serial.tools.list_ports
import time
import sys
import platform

def list_all_ports():
    """List all available serial ports with details."""
    print("🔍 Scanning for serial ports...")
    print(f"📱 Platform: {platform.system()} {platform.release()}")
    
    ports = serial.tools.list_ports.comports()
    
    if not ports:
        print("❌ No serial ports found")
        if platform.system().lower() == "linux":
            print("💡 On Linux, you might need to:")
            print("   - Add your user to the 'dialout' group: sudo usermod -a -G dialout $USER")
            print("   - Check if the Arduino is properly connected")
            print("   - Look for devices with: ls -la /dev/tty*")
        return []
    
    print(f"\n📋 Found {len(ports)} serial port(s):")
    for i, port in enumerate(ports, 1):
        print(f"\n{i}. {port.device}")
        print(f"   Description: {port.description}")
        if hasattr(port, 'manufacturer') and port.manufacturer:
            print(f"   Manufacturer: {port.manufacturer}")
        if hasattr(port, 'vid') and port.vid:
            print(f"   VID: 0x{port.vid:04X}")
        if hasattr(port, 'pid') and port.pid:
            print(f"   PID: 0x{port.pid:04X}")
        if hasattr(port, 'serial_number') and port.serial_number:
            print(f"   Serial: {port.serial_number}")
            
        # Add platform-specific hints
        current_platform = platform.system().lower()
        device_lower = port.device.lower()
        
        if current_platform == "linux":
            if "/dev/ttyacm" in device_lower:
                print("   💡 This looks like an Arduino (ACM device)")
            elif "/dev/ttyusb" in device_lower:
                print("   💡 This looks like a USB serial device (possibly Arduino clone)")
        elif current_platform == "windows":
            if port.description and "arduino" in port.description.lower():
                print("   💡 This looks like an Arduino")
    
    return ports

def test_port(port_name, baudrate=9600, timeout=10.0):
    """Test connection to a specific port."""
    print(f"\n🔌 Testing connection to {port_name}")
    print(f"   Baudrate: {baudrate}")
    print(f"   Timeout: {timeout}s")
    
    try:
        # Open serial port
        ser = serial.Serial(
            port=port_name,
            baudrate=baudrate,
            timeout=timeout,
            write_timeout=timeout
        )
        
        print("✅ Serial port opened successfully")
        
        # Wait for Arduino to boot, but check for data immediately
        print("⏳ Waiting for Arduino to initialize (3s)...")
        time.sleep(1)  # Shorter wait
        
        # Check if ARDUINO_READY is already in buffer
        bytes_waiting = ser.in_waiting
        if bytes_waiting > 0:
            print(f"📨 Found {bytes_waiting} bytes in buffer")
            data = ser.read(bytes_waiting)
            print(f"   Buffer content: {data}")
            
            # Check if ARDUINO_READY is in the buffer
            try:
                buffer_text = data.decode().strip()
                print(f"   Decoded: '{buffer_text}'")
                if "ARDUINO_READY" in buffer_text:
                    print("🎉 Arduino ready message found in buffer!")
                    
                    # Test sending a command
                    print("\n🧪 Testing relay command...")
                    ser.write(b"RELAY_1_ON\n")
                    ser.flush()
                    
                    # Wait for response
                    time.sleep(0.5)
                    if ser.in_waiting > 0:
                        response = ser.readline().decode().strip()
                        print(f"📨 Command response: '{response}'")
                        
                        if response == "OK":
                            print("✅ Command test successful!")
                            
                            # Turn off the relay
                            ser.write(b"RELAY_1_OFF\n")
                            ser.flush()
                            time.sleep(0.5)
                            if ser.in_waiting > 0:
                                response = ser.readline().decode().strip()
                                print(f"📨 OFF response: '{response}'")
                        else:
                            print(f"❌ Unexpected response: {response}")
                    else:
                        print("❌ No response to command")
                    
                    ser.close()
                    return True
            except UnicodeDecodeError:
                print("⚠️  Buffer contains non-text data")
        
        # If not found in buffer, wait for new message
        print("⏳ Listening for new ARDUINO_READY message (5s)...")
        start_time = time.time()
        
        while time.time() - start_time < 5:
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode().strip()
                    print(f"📨 Received: '{line}'")
                    
                    if line == "ARDUINO_READY":
                        print("🎉 Arduino ready message received!")
                        
                        # Test sending a command
                        print("\n🧪 Testing relay command...")
                        ser.write(b"RELAY_1_ON\n")
                        ser.flush()
                        
                        # Wait for response
                        time.sleep(0.5)
                        if ser.in_waiting > 0:
                            response = ser.readline().decode().strip()
                            print(f"📨 Command response: '{response}'")
                            
                            if response == "OK":
                                print("✅ Command test successful!")
                                
                                # Turn off the relay
                                ser.write(b"RELAY_1_OFF\n")
                                ser.flush()
                                time.sleep(0.5)
                                if ser.in_waiting > 0:
                                    response = ser.readline().decode().strip()
                                    print(f"📨 OFF response: '{response}'")
                            else:
                                print(f"❌ Unexpected response: {response}")
                        else:
                            print("❌ No response to command")
                        
                        ser.close()
                        return True
                        
                except UnicodeDecodeError:
                    print("⚠️  Received non-text data")
            
            time.sleep(0.1)
        
        print("❌ Timeout waiting for ARDUINO_READY")
        ser.close()
        return False
        
    except serial.SerialException as e:
        print(f"❌ Serial error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    """Main testing function."""
    print("Arduino Port Tester - Cross Platform")
    print("=" * 40)
    
    # List all ports
    ports = list_all_ports()
    
    if not ports:
        print("\nNo ports available to test")
        current_platform = platform.system().lower()
        if current_platform == "linux":
            print("\n💡 Linux troubleshooting:")
            print("   - Check USB connection: lsusb")
            print("   - Check devices: ls -la /dev/tty* | grep -E '(ACM|USB)'")
            print("   - Add user to dialout group: sudo usermod -a -G dialout $USER")
            print("   - Then logout and login again")
        elif current_platform == "windows":
            print("\n💡 Windows troubleshooting:")
            print("   - Check Device Manager for COM ports")
            print("   - Install Arduino drivers if needed")
        return
    
    # Test each port
    print(f"\n🧪 Testing ports for Arduino communication...")
    
    for port in ports:
        success = test_port(port.device)
        if success:
            print(f"\n🎉 SUCCESS: Arduino found on {port.device}")
            break
        else:
            print(f"\n💥 FAILED: No Arduino on {port.device}")
    else:
        print(f"\n❌ No Arduino found on any port")
        print("\nTroubleshooting tips:")
        print("1. Check that Arduino is connected via USB")
        print("2. Verify that the Arduino firmware is uploaded")
        print("3. Try uploading the firmware again")
        print("4. Check Arduino IDE Serial Monitor at 9600 baud")
        
        current_platform = platform.system().lower()
        if current_platform == "linux":
            print("5. Check user permissions: groups $USER (should include 'dialout')")
            print("6. Try running with sudo (temporary test only)")

if __name__ == "__main__":
    main()

    # Uncomment the line below to test a specific port
    # test_port("COM10")  # Replace with your actual port for testing
