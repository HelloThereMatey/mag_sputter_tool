#!/usr/bin/env python3
"""
Arduino Port Detection Utility

This script scans available serial ports to find the Arduino Mega 2560 relay controller
and updates the sput.yml file with the detected port.

Usage:
    python detect_arduino_port.py [--dry-run] [--verbose]

Options:
    --dry-run   : Show results without updating config file
    --verbose   : Show detailed scanning information
"""

import serial
import serial.tools.list_ports
import time
import argparse
import sys
from pathlib import Path
from typing import Optional, List
import yaml


def test_arduino_port(port: str, baudrate: int = 9600, timeout: float = 3.0, verbose: bool = False) -> bool:
    """Test if an Arduino Mega 2560 responds on a specific port.
    
    Args:
        port: Serial port to test (e.g., 'COM3' or '/dev/ttyACM0')
        baudrate: Serial baud rate (default: 9600)
        timeout: Command timeout in seconds
        verbose: Print detailed test information
        
    Returns:
        True if Arduino found, False otherwise
    """
    try:
        if verbose:
            print(f"  Testing {port}...", end=' ')
        
        # Open serial connection
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=timeout,
            write_timeout=timeout
        )
        
        # Wait for Arduino to initialize after serial connection
        time.sleep(1.5)
        
        # Clear any startup messages
        if ser.in_waiting:
            startup_data = ser.read(ser.in_waiting)
            if verbose:
                try:
                    print(f"\n    Startup: {startup_data.decode('utf-8', errors='ignore').strip()}")
                except:
                    pass
        
        # Send test command - GET_RELAY_STATES should always work
        test_cmd = "GET_RELAY_STATES\n"
        ser.write(test_cmd.encode())
        
        # Wait for response
        start_time = time.time()
        response = b""
        
        while time.time() - start_time < timeout:
            if ser.in_waiting:
                response += ser.read(ser.in_waiting)
                # Check if we have a complete response
                if b'\n' in response:
                    break
            time.sleep(0.1)
        
        ser.close()
        
        # Validate response
        if response:
            response_str = response.decode('utf-8', errors='ignore').strip()
            if verbose:
                print(f"\n    Response: {response_str[:100]}...")
            
            # Arduino should respond with RELAY_STATES: followed by binary state string
            if "RELAY_STATES:" in response_str:
                if verbose:
                    print("    ✅ FOUND - Valid Arduino relay controller")
                return True
        
        if verbose:
            print("    ❌ No valid response")
        return False
        
    except serial.SerialException as e:
        if verbose:
            print(f"    ❌ Serial error: {e}")
        return False
    except Exception as e:
        if verbose:
            print(f"    ❌ Error: {e}")
        return False


def scan_for_arduino(excluded_ports: List[str] = None, baudrate: int = 9600, verbose: bool = False) -> Optional[str]:
    """Scan all available serial ports for Arduino Mega 2560.
    
    Args:
        excluded_ports: List of ports to skip
        baudrate: Serial baud rate (default: 9600)
        verbose: Show detailed scanning information
        
    Returns:
        Serial port string if found, None otherwise
    """
    print("\n🔍 Scanning serial ports for Arduino Mega 2560...")
    
    if excluded_ports is None:
        excluded_ports = []
    
    # HID device exclusion patterns
    hid_exclusion_patterns = [
        'mouse', 'keyboard', 'hid', 'input', 'touchpad', 'trackpad',
        'receiver', 'dongle', 'bluetooth', 'bt', 'wireless'
    ]
    
    # Get all available ports
    all_ports = list(serial.tools.list_ports.comports())
    
    if not all_ports:
        print("❌ No serial ports found!")
        return None
    
    # Filter and prioritize ports
    candidate_ports = []
    
    print(f"\n📋 Found {len(all_ports)} serial port(s):")
    for p in all_ports:
        print(f"   {p.device}: {p.description}")
        
        # Skip excluded ports
        if p.device in excluded_ports:
            print(f"      ⏭️  Skipped (excluded)")
            continue
        
        # Skip HID devices
        desc = p.description.lower()
        manufacturer = (p.manufacturer or '').lower()
        
        if any(pattern in desc or pattern in manufacturer for pattern in hid_exclusion_patterns):
            if verbose:
                print(f"      ⏭️  Skipped (HID device)")
            continue
        
        # Prioritize likely Arduino ports
        priority = 50  # Default priority
        
        # Arduino vendor IDs (common ones)
        arduino_vids = [0x2341, 0x2A03]  # Official Arduino VIDs
        if hasattr(p, 'vid') and p.vid in arduino_vids:
            priority = 10
            if verbose:
                print(f"      🎯 High priority (Arduino VID)")
        
        # USB ACM devices (Arduino Mega often shows as this)
        if 'ACM' in p.device or 'Arduino' in p.description:
            priority = min(priority, 20)
            if verbose:
                print(f"      🎯 High priority (ACM/Arduino)")
        
        candidate_ports.append((priority, p.device))
    
    if not candidate_ports:
        print("\n❌ No suitable candidate ports found!")
        return None
    
    # Sort by priority (lower number = higher priority)
    candidate_ports.sort()
    
    print(f"\n📡 Testing {len(candidate_ports)} candidate port(s)...")
    
    # Test each port
    for priority, port in candidate_ports:
        print(f"\n🔌 Testing port: {port}")
        
        if test_arduino_port(port, baudrate=baudrate, timeout=3.0, verbose=verbose):
            print(f"\n✅ Arduino Mega 2560 found on {port}")
            return port
        
        # Brief delay between tests
        time.sleep(0.3)
    
    print("\n❌ No Arduino Mega 2560 found on any port")
    return None


def update_config_file(config_path: Path, detected_port: str, dry_run: bool = False) -> bool:
    """Update sput.yml with detected Arduino port.
    
    Args:
        config_path: Path to sput.yml file
        detected_port: Arduino serial port to set
        dry_run: If True, show changes without writing file
        
    Returns:
        True if successful, False otherwise
    """
    if not config_path.exists():
        print(f"\n❌ Config file not found: {config_path}")
        return False
    
    try:
        # Load YAML config
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Update arduino_port
        if 'serial' not in config:
            config['serial'] = {}
        
        old_port = config['serial'].get('arduino_port', 'not set')
        config['serial']['arduino_port'] = detected_port
        
        print(f"\n📝 Configuration update:")
        print(f"   Old arduino_port: {old_port}")
        print(f"   New arduino_port: {detected_port}")
        
        if dry_run:
            print("\n🔍 DRY RUN - No changes written to file")
            return True
        
        # Write updated config
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        print(f"\n✅ Updated config file: {config_path}")
        return True
        
    except Exception as e:
        print(f"\n❌ Error updating config file: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Detect Arduino Mega 2560 port and update sput.yml configuration'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Show results without updating config file')
    parser.add_argument('--verbose', action='store_true',
                        help='Show detailed scanning information')
    parser.add_argument('--exclude-port', action='append',
                        help='Exclude specific port from scanning (can be used multiple times)')
    parser.add_argument('--baudrate', type=int, default=9600,
                        help='Serial baud rate (default: 9600)')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Arduino Mega 2560 Port Detection Utility")
    print("=" * 60)
    
    # Scan for Arduino
    excluded_ports = args.exclude_port if args.exclude_port else []
    detected_port = scan_for_arduino(
        excluded_ports=excluded_ports,
        baudrate=args.baudrate,
        verbose=args.verbose
    )
    
    if not detected_port:
        print("\n❌ Failed to detect Arduino port")
        print("\nTroubleshooting:")
        print("  1. Ensure Arduino Mega 2560 is connected via USB")
        print("  2. Check that relay_controller.ino firmware is uploaded")
        print("  3. Verify USB cable is data-capable (not charge-only)")
        print("  4. Try unplugging and reconnecting the Arduino")
        print("  5. Check Device Manager (Windows) or dmesg (Linux) for port info")
        sys.exit(1)
    
    # Get config file path
    script_dir = Path(__file__).parent
    config_path = script_dir.parent / 'sput.yml'
    
    # Update config file
    if update_config_file(config_path, detected_port, dry_run=args.dry_run):
        print("\n✅ Detection complete!")
        print(f"\nArduino port: {detected_port}")
        
        if not args.dry_run:
            print("\n💡 You can now start the sputter control GUI")
    else:
        print("\n❌ Failed to update configuration")
        sys.exit(1)


if __name__ == '__main__':
    main()
