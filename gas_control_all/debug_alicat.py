#!/usr/bin/env python3
"""
Debug script for Alicat MFC serial communication issues.

This script helps diagnose connection and communication problems with Alicat MFCs
connected via serial port.
"""

import asyncio
import serial
import time
from alicat import FlowController


async def test_raw_serial():
    """Test raw serial communication without the Alicat driver."""
    print("=== Testing Raw Serial Communication ===")
    
    try:
        # Open serial connection directly
        ser = serial.Serial(
            port='/dev/ttyUSB0',
            baudrate=19200,  # Standard Alicat baud rate
            timeout=1,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS
        )
        
        print(f"Serial port opened: {ser.name}")
        print(f"Baudrate: {ser.baudrate}")
        print(f"Timeout: {ser.timeout}")
        
        # Wait a moment for connection to stabilize
        time.sleep(0.5)
        
        # Try to communicate with each possible unit ID
        for unit_id in ['A', 'B', 'C']:
            print(f"\nTesting unit ID '{unit_id}':")
            
            # Send query command
            command = f'{unit_id}\r'
            ser.write(command.encode())
            print(f"  Sent: {repr(command)}")
            
            # Read response
            response = ser.readline().decode('ascii', errors='ignore').strip()
            print(f"  Received: {repr(response)}")
            
            if response:
                # Parse the response
                parts = response.split()
                print(f"  Response parts: {parts}")
                print(f"  Number of parts: {len(parts)}")
                
                if len(parts) > 1:
                    unit_resp = parts[0]
                    values = parts[1:]
                    print(f"  Unit: {unit_resp}")
                    print(f"  Values: {values}")
                    print(f"  Number of values: {len(values)}")
        
        ser.close()
        print("\nRaw serial test completed.")
        
    except Exception as e:
        print(f"Raw serial test failed: {e}")
        return False
    
    return True


async def test_alicat_driver_detailed():
    """Test the Alicat driver with detailed debugging."""
    print("\n=== Testing Alicat Driver with Debug Info ===")
    
    for unit_id in ['A', 'B', 'C']:
        print(f"\nTesting unit ID '{unit_id}':")
        
        try:
            # Create flow controller
            fc = FlowController(address='/dev/ttyUSB0', unit=unit_id)
            
            print(f"  FlowController created for unit {unit_id}")
            print(f"  Keys expected: {fc.keys}")
            
            # Try to get raw response first
            command = f'{unit_id}'
            raw_response = await fc._write_and_read(command)
            print(f"  Raw response: {repr(raw_response)}")
            
            if raw_response:
                spl = raw_response.split()
                unit_resp, values = spl[0], spl[1:]
                print(f"  Unit response: {unit_resp}")
                print(f"  Values: {values}")
                print(f"  Number of values: {len(values)}")
                print(f"  Expected keys: {fc.keys}")
                print(f"  Number of keys: {len(fc.keys)}")
                
                # Check for length mismatch
                if len(values) != len(fc.keys):
                    print(f"  ⚠️  LENGTH MISMATCH: {len(values)} values vs {len(fc.keys)} keys")
                    print(f"  This is likely causing the zip() error")
                
                # Try the full get() method
                try:
                    result = await fc.get()
                    print(f"  ✅ Success: {result}")
                except Exception as e:
                    print(f"  ❌ get() failed: {e}")
            else:
                print(f"  ❌ No response from unit {unit_id}")
            
            await fc.close()
            
        except Exception as e:
            print(f"  ❌ Failed to test unit {unit_id}: {e}")


async def test_different_baud_rates():
    """Test different baud rates to find the correct one."""
    print("\n=== Testing Different Baud Rates ===")
    
    baud_rates = [9600, 19200, 38400, 57600, 115200]
    
    for baud in baud_rates:
        print(f"\nTesting baud rate: {baud}")
        
        try:
            ser = serial.Serial(
                port='/dev/ttyUSB0',
                baudrate=baud,
                timeout=1,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            
            time.sleep(0.5)  # Let connection stabilize
            
            # Test with unit A
            command = 'A\r'
            ser.write(command.encode())
            response = ser.readline().decode('ascii', errors='ignore').strip()
            
            if response and response.startswith('A'):
                print(f"  ✅ Got valid response at {baud}: {repr(response)}")
            else:
                print(f"  ❌ No valid response at {baud}: {repr(response)}")
            
            ser.close()
            
        except Exception as e:
            print(f"  ❌ Error testing {baud}: {e}")


async def test_permissions():
    """Test if we have proper permissions to access the serial port."""
    print("\n=== Testing Serial Port Permissions ===")
    
    import os
    import stat
    
    port_path = '/dev/ttyUSB0'
    
    try:
        # Check if port exists
        if not os.path.exists(port_path):
            print(f"❌ Serial port {port_path} does not exist")
            print("Available tty devices:")
            for device in os.listdir('/dev'):
                if device.startswith('ttyUSB') or device.startswith('ttyACM'):
                    print(f"  /dev/{device}")
            return False
        
        # Check permissions
        port_stat = os.stat(port_path)
        mode = stat.filemode(port_stat.st_mode)
        print(f"Port {port_path} permissions: {mode}")
        
        # Check if readable/writable
        readable = os.access(port_path, os.R_OK)
        writable = os.access(port_path, os.W_OK)
        print(f"Readable: {readable}, Writable: {writable}")
        
        if not (readable and writable):
            print("❌ Insufficient permissions. Try:")
            print("  sudo usermod -a -G dialout $USER")
            print("  Then log out and back in")
            return False
        
        print("✅ Permissions look good")
        return True
        
    except Exception as e:
        print(f"❌ Permission check failed: {e}")
        return False


async def main():
    """Run all diagnostic tests."""
    print("Alicat MFC Serial Communication Diagnostic Tool")
    print("=" * 60)
    
    # Test permissions first
    permissions_ok = await test_permissions()
    
    if not permissions_ok:
        print("\n❌ Permission issues detected. Fix permissions before continuing.")
        return
    
    # Test different baud rates
    await test_different_baud_rates()
    
    # Test raw serial communication
    serial_ok = await test_raw_serial()
    
    if serial_ok:
        # Test Alicat driver if raw serial works
        await test_alicat_driver_detailed()
    else:
        print("\n❌ Raw serial communication failed. Check hardware connections.")
    
    print("\n" + "=" * 60)
    print("Diagnostic completed. Summary:")
    print("1. Check the debug output above for clues")
    print("2. Ensure your MFCs are powered on")
    print("3. Verify the DB9 to USB converter is working")
    print("4. Try different unit IDs (A, B, C)")
    print("5. Check if baud rate needs adjustment")


if __name__ == "__main__":
    asyncio.run(main())