"""
Setup and Test Script for Relay Test System
Cross-platform compatibility for Windows, Linux, and Raspberry Pi
Checks dependencies, tests basic functionality, and provides setup guidance
"""

import sys
import importlib.util
import platform

def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3.7, 0):
        print("❌ Python 3.7 or higher is required")
        print(f"   Current version: {sys.version}")
        return False
    else:
        print(f"✅ Python version: {sys.version.split()[0]}")
        return True

def check_dependencies():
    """Check if required dependencies are installed."""
    dependencies = {
    'PyQt5': 'PyQt5',
        'serial': 'pyserial'
    }
    
    missing = []
    
    for import_name, package_name in dependencies.items():
        try:
            importlib.import_module(import_name)
            print(f"✅ {package_name} is installed")
        except ImportError:
            print(f"❌ {package_name} is NOT installed")
            missing.append(package_name)
    
    return missing

def check_serial_ports():
    """Check available serial ports with platform-specific guidance."""
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        
        current_platform = platform.system().lower()
        
        if ports:
            print(f"\n✅ Found {len(ports)} serial port(s):")
            for port in ports:
                description = port.description
                if hasattr(port, 'manufacturer') and port.manufacturer:
                    description += f" ({port.manufacturer})"
                print(f"   {port.device} - {description}")
                
                # Platform-specific hints
                device_lower = port.device.lower()
                if current_platform == "linux":
                    if "/dev/ttyacm" in device_lower:
                        print("     💡 Likely Arduino (ACM device)")
                    elif "/dev/ttyusb" in device_lower:
                        print("     💡 Likely USB serial (Arduino clone)")
        else:
            print("\n⚠️  No serial ports found")
            if current_platform == "linux":
                print("   💡 Linux users:")
                print("     - Check USB connection: lsusb")
                print("     - Add user to dialout group: sudo usermod -a -G dialout $USER")
                print("     - Logout and login again")
                print("     - Check for devices: ls -la /dev/tty* | grep -E '(ACM|USB)'")
            elif current_platform == "windows":
                print("   💡 Windows users:")
                print("     - Check Device Manager for COM ports")
                print("     - Install Arduino drivers if needed")
            print("   Make sure Arduino is connected via USB")
        
        return len(ports) > 0
    except ImportError:
        print("\n❌ Cannot check serial ports (pyserial not installed)")
        return False

def test_basic_imports():
    """Test basic imports to catch any issues."""
    try:
        # Test Arduino controller import
        from arduino_controller import ArduinoController
        print("✅ Arduino controller module loads correctly")
        
        # Test GUI import
        from gui import RelayTestWindow
        print("✅ GUI module loads correctly")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Other error: {e}")
        return False

def main():
    """Main setup and test function."""
    print("Relay Test System - Setup and Test (Cross Platform)")
    print("=" * 55)
    print(f"📱 Platform: {platform.system()} {platform.release()}")
    
    # Check Python version
    if not check_python_version():
        return False
    
    print("\nChecking dependencies...")
    missing_deps = check_dependencies()
    
    if missing_deps:
        print(f"\n❌ Missing dependencies: {', '.join(missing_deps)}")
        print("\nTo install missing dependencies, run:")
        print("   pip install -r requirements.txt")
        print("\nOr install individually:")
        for dep in missing_deps:
            print(f"   pip install {dep}")
        
        # Platform-specific installation notes
        current_platform = platform.system().lower()
        if current_platform == "linux":
            print("\n💡 Linux/Raspberry Pi notes:")
            print("   - You might need to install system packages first:")
            print("   - sudo apt update && sudo apt install python3-pip python3-dev")
            print("   - For PyQt5: conda install pyqt (pyqt provides Qt5 bindings)")
            
        return False
    
    print("\nChecking serial ports...")
    has_ports = check_serial_ports()
    
    print("\nTesting module imports...")
    imports_ok = test_basic_imports()
    
    print("\n" + "=" * 55)
    
    if imports_ok:
        print("✅ Setup check PASSED")
        print("\nNext steps:")
        print("1. Upload arduino/relay_controller.ino to your Arduino Mega 2560")
        print("2. Connect relay modules to pins 22-37")
        print("3. Run the application: python main.py")
        
        if not has_ports:
            print("\n⚠️  Warning: No serial ports detected")
            print("   Make sure Arduino is connected before running the application")
            
            current_platform = platform.system().lower()
            if current_platform == "linux":
                print("   On Linux/Pi: Check user permissions and dialout group membership")
        
        return True
    else:
        print("❌ Setup check FAILED")
        print("   Fix the issues above before running the application")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
