#!/usr/bin/env python3
"""
Cross-Platform Arduino Detection Test
Tests Arduino auto-detection on Windows, Linux, and Raspberry Pi
"""

import sys
import platform
import serial.tools.list_ports
from arduino_controller import ArduinoController

def print_system_info():
    """Print detailed system information."""
    print("🖥️  System Information:")
    print(f"   Platform: {platform.system()} {platform.release()}")
    print(f"   Architecture: {platform.machine()}")
    print(f"   Python: {sys.version}")
    print(f"   Python executable: {sys.executable}")

def analyze_ports():
    """Analyze available serial ports with platform-specific insights."""
    print("\n📋 Serial Port Analysis:")
    ports = serial.tools.list_ports.comports()
    
    if not ports:
        print("   ❌ No serial ports found")
        current_platform = platform.system().lower()
        
        if current_platform == "linux":
            print("\n💡 Linux/Raspberry Pi troubleshooting:")
            print("   1. Check if Arduino is connected: lsusb | grep -i arduino")
            print("   2. Look for devices: ls -la /dev/tty* | grep -E '(ACM|USB)'")
            print("   3. Check permissions: ls -la /dev/ttyACM* /dev/ttyUSB* 2>/dev/null")
            print("   4. Add user to dialout group: sudo usermod -a -G dialout $USER")
            print("   5. Check current groups: groups $USER")
            print("   6. After adding to group, logout and login again")
        elif current_platform == "windows":
            print("\n💡 Windows troubleshooting:")
            print("   1. Check Device Manager > Ports (COM & LPT)")
            print("   2. Look for Arduino or USB Serial Device")
            print("   3. Install Arduino drivers if needed")
        return False
    
    current_platform = platform.system().lower()
    print(f"   Found {len(ports)} port(s) on {current_platform}:")
    
    arduino_candidates = []
    
    for i, port in enumerate(ports, 1):
        print(f"\n   {i}. {port.device}")
        print(f"      Description: {port.description}")
        
        if hasattr(port, 'manufacturer') and port.manufacturer:
            print(f"      Manufacturer: {port.manufacturer}")
            
        if hasattr(port, 'vid') and port.vid:
            print(f"      VID: 0x{port.vid:04X}")
            
        if hasattr(port, 'pid') and port.pid:
            print(f"      PID: 0x{port.pid:04X}")
            
        # Analyze likelihood of being Arduino
        score = 0
        reasons = []
        
        # Platform-specific port naming
        device_lower = port.device.lower()
        if current_platform == "windows":
            if device_lower.startswith("com"):
                score += 1
                reasons.append("Windows COM port")
        elif current_platform in ["linux", "darwin"]:
            if "/dev/ttyacm" in device_lower:
                score += 3
                reasons.append("ACM device (typical Arduino)")
            elif "/dev/ttyusb" in device_lower:
                score += 2
                reasons.append("USB serial device")
            elif "/dev/cu.usbmodem" in device_lower:
                score += 2
                reasons.append("macOS USB modem")
        
        # Description analysis
        desc_lower = port.description.lower()
        arduino_keywords = ["arduino", "mega", "uno"]
        for keyword in arduino_keywords:
            if keyword in desc_lower:
                score += 3
                reasons.append(f"Contains '{keyword}' in description")
                break
        
        # Clone chip detection
        clone_keywords = ["ch340", "cp210", "ftdi"]
        for keyword in clone_keywords:
            if keyword in desc_lower:
                score += 2
                reasons.append(f"Arduino-compatible chip ({keyword})")
                break
        
        # VID analysis
        if hasattr(port, 'vid') and port.vid:
            arduino_vids = {
                0x2341: "Official Arduino",
                0x1A86: "CH340 (Arduino clone)",
                0x10C4: "CP210x (Arduino clone)",
                0x0403: "FTDI (some Arduinos)"
            }
            if port.vid in arduino_vids:
                score += 3
                reasons.append(arduino_vids[port.vid])
        
        if score > 0:
            arduino_candidates.append((port, score, reasons))
            print(f"      🎯 Arduino likelihood: {score}/9")
            print(f"      💡 Reasons: {', '.join(reasons)}")
        else:
            print(f"      ❓ Unlikely to be Arduino")
    
    # Sort candidates by score
    arduino_candidates.sort(key=lambda x: x[1], reverse=True)
    
    if arduino_candidates:
        print(f"\n🎯 Arduino candidates (sorted by likelihood):")
        for i, (port, score, reasons) in enumerate(arduino_candidates, 1):
            print(f"   {i}. {port.device} (score: {score}/9)")
    
    return len(arduino_candidates) > 0

def test_auto_connection():
    """Test the automatic Arduino connection."""
    print("\n🔌 Testing Arduino Auto-Connection:")
    
    controller = ArduinoController()
    
    try:
        success = controller.auto_connect()
        
        if success:
            print("✅ Auto-connection SUCCESSFUL!")
            print(f"   Connected to: {controller.serial_port.port}")
            
            # Test a simple command
            print("\n🧪 Testing relay command...")
            if controller.set_relay(1, True):
                print("✅ Relay command successful")
                controller.set_relay(1, False)  # Turn it back off
            else:
                print("❌ Relay command failed")
            
            controller.disconnect()
            print("🔌 Disconnected successfully")
            
        else:
            print("❌ Auto-connection FAILED")
            print("   No Arduino found or communication error")
            
    except Exception as e:
        print(f"❌ Exception during auto-connection: {e}")
        if controller.is_arduino_connected():
            controller.disconnect()

def main():
    """Main test function."""
    print("Cross-Platform Arduino Detection Test")
    print("=" * 45)
    
    print_system_info()
    has_candidates = analyze_ports()
    
    if has_candidates:
        test_auto_connection()
    else:
        print("\n⚠️  No Arduino candidates found - skipping connection test")
    
    print("\n" + "=" * 45)
    print("Test completed!")

if __name__ == "__main__":
    main()
