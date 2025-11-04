#!/usr/bin/env python3
"""Serial port diagnostic and reset utility for Alicat MFCs.

This script helps diagnose and potentially fix serial communication issues
with Alicat mass flow controllers.
"""

import subprocess
import time
import sys
import os

def run_command(cmd, timeout=5):
    """Run a command and return success, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd, 
            shell=True,
            capture_output=True, 
            text=True, 
            timeout=timeout,
            encoding='utf-8',
            errors='replace'
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

def check_serial_ports():
    """Check available serial ports."""
    print("=== Checking Serial Ports ===")
    
    # Linux/Unix
    if os.path.exists("/dev"):
        print("Available /dev/tty* ports:")
        success, stdout, stderr = run_command("ls -la /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo 'No USB serial ports found'")
        print(stdout)
    
    # Try to find processes using the serial port
    print("\n=== Checking Process Usage ===")
    success, stdout, stderr = run_command("lsof /dev/ttyUSB0 2>/dev/null || echo 'No processes using /dev/ttyUSB0'")
    print(stdout)

def test_alicat_units():
    """Test connectivity to each Alicat unit."""
    print("\n=== Testing Alicat Units ===")
    
    units = ['A', 'B', 'C']
    port = '/dev/ttyUSB0'
    
    for unit in units:
        print(f"\nTesting unit {unit}...")
        
        # Try basic connection with timeout
        cmd = f"alicat {port} --unit {unit} --timeout 2.0"
        print(f"Command: {cmd}")
        
        success, stdout, stderr = run_command(cmd, timeout=10)
        
        if success:
            print(f"✅ Unit {unit}: SUCCESS")
            if stdout.strip():
                print(f"   Output: {stdout.strip()[:100]}...")
        else:
            print(f"❌ Unit {unit}: FAILED")
            if stderr.strip():
                print(f"   Error: {stderr.strip()[:200]}...")
        
        time.sleep(1)  # Brief delay between tests

def reset_serial_port():
    """Attempt to reset the serial port."""
    print("\n=== Attempting Serial Port Reset ===")
    
    port = '/dev/ttyUSB0'
    
    # Try to reset USB device
    print("Attempting USB reset...")
    success, stdout, stderr = run_command(f"sudo usbreset {port} 2>/dev/null || echo 'usbreset not available'")
    print(stdout)
    
    # Alternative: unbind and rebind USB device
    print("Checking USB device info...")
    success, stdout, stderr = run_command("lsusb | grep -i 'serial\\|ftdi\\|prolific\\|cp210'")
    if stdout:
        print(f"USB serial devices found:\n{stdout}")
    else:
        print("No obvious USB serial devices found")

def kill_alicat_processes():
    """Kill any existing Alicat processes that might be blocking the port."""
    print("\n=== Checking for Alicat Processes ===")
    
    success, stdout, stderr = run_command("ps aux | grep -i alicat | grep -v grep")
    if stdout.strip():
        print(f"Found Alicat processes:\n{stdout}")
        
        print("Attempting to kill Alicat processes...")
        run_command("pkill -f alicat")
        time.sleep(2)
        
        # Check again
        success, stdout, stderr = run_command("ps aux | grep -i alicat | grep -v grep")
        if not stdout.strip():
            print("✅ Alicat processes cleared")
        else:
            print("❌ Some Alicat processes still running")
    else:
        print("No Alicat processes found")

def main():
    """Run diagnostic sequence."""
    print("Alicat MFC Serial Diagnostic Tool")
    print("=" * 40)
    
    try:
        check_serial_ports()
        kill_alicat_processes()
        reset_serial_port()
        
        print("\n" + "=" * 40)
        print("Waiting 3 seconds for device to stabilize...")
        time.sleep(3)
        
        test_alicat_units()
        
        print("\n" + "=" * 40)
        print("Diagnostic complete!")
        print("\nRecommendations:")
        print("1. If units are still failing, try physically unplugging/replugging USB cable")
        print("2. Check if baudrate settings match MFC configuration (usually 19200)")
        print("3. Ensure only one process is accessing the serial port at a time")
        print("4. Consider adding delays between MFC commands in your application")
        
    except KeyboardInterrupt:
        print("\nDiagnostic interrupted by user")
    except Exception as e:
        print(f"\nDiagnostic failed with error: {e}")

if __name__ == "__main__":
    main()