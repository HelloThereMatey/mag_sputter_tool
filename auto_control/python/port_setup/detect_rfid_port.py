#!/usr/bin/env python3
"""
RFID Reader Port Detection Utility

This script scans available serial ports to find the Raspberry Pi Pico RFID reader
and updates the sput.yml file with the detected port.

Usage:
    python detect_rfid_port.py [--dry-run] [--verbose] [--exclude-port COMX]

Options:
    --dry-run           : Show results without updating config file
    --verbose           : Show detailed scanning information
    --exclude-port COMX : Exclude specific port (e.g., Arduino port)
"""

import serial
import serial.tools.list_ports
import time
import argparse
import sys
from pathlib import Path
from typing import Optional, List
import yaml


PICO_READY_MESSAGE = "PICO_RFID_READY"
PICO_BAUDRATE = 115200


def test_rfid_port(port: str, timeout: float = 3.0, verbose: bool = False) -> bool:
    """Test if a Raspberry Pi Pico RFID reader responds on a specific port.
    
    Args:
        port: Serial port to test (e.g., 'COM5' or '/dev/ttyACM1')
        timeout: Command timeout in seconds
        verbose: Print detailed test information
        
    Returns:
        True if Pico RFID reader found, False otherwise
    """
    try:
        if verbose:
            print(f"  Testing {port}...", end=' ')
        
        # Open serial connection
        ser = serial.Serial(
            port=port,
            baudrate=PICO_BAUDRATE,
            timeout=timeout
        )
        
        # Force DTR toggle to reset Pico (triggers ready message)
        ser.dtr = False
        time.sleep(0.1)
        ser.dtr = True
        
        # Wait for ready message
        start_time = time.time()
        response = b""
        
        while time.time() - start_time < timeout:
            if ser.in_waiting:
                response += ser.read(ser.in_waiting)
                
                # Check if we have the ready message
                try:
                    response_str = response.decode('utf-8', errors='ignore')
                    if PICO_READY_MESSAGE in response_str:
                        ser.close()
                        if verbose:
                            print(f"    ✅ FOUND - Pico RFID reader detected")
                        return True
                except:
                    pass
            
            time.sleep(0.1)
        
        ser.close()
        
        if verbose:
            if response:
                print(f"    ❌ No ready message (got: {response[:50]})")
            else:
                print("    ❌ No response")
        return False
        
    except serial.SerialException as e:
        if verbose:
            print(f"    ❌ Serial error: {e}")
        return False
    except Exception as e:
        if verbose:
            print(f"    ❌ Error: {e}")
        return False


def scan_for_rfid(excluded_ports: List[str] = None, verbose: bool = False) -> Optional[str]:
    """Scan all available serial ports for Raspberry Pi Pico RFID reader.
    
    Args:
        excluded_ports: List of ports to skip (e.g., Arduino port)
        verbose: Show detailed scanning information
        
    Returns:
        Serial port string if found, None otherwise
    """
    print("\n🔍 Scanning serial ports for Raspberry Pi Pico RFID reader...")
    
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
        
        # Prioritize likely Pico ports
        priority = 50  # Default priority
        
        # USB Serial Device (Pico typically shows as this on Windows)
        if 'usb serial' in desc or 'pico' in desc or 'raspberry pi' in desc:
            priority = 10
            if verbose:
                print(f"      🎯 High priority (Pico-like device)")
        
        # ttyACM devices (Pico often shows as this on Linux)
        if 'ACM' in p.device:
            priority = min(priority, 20)
            if verbose:
                print(f"      🎯 High priority (ACM device)")
        
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
        
        if test_rfid_port(port, timeout=3.0, verbose=verbose):
            print(f"\n✅ Pico RFID reader found on {port}")
            return port
        
        # Brief delay between tests
        time.sleep(0.3)
    
    print("\n❌ No Pico RFID reader found on any port")
    return None


def update_config_file(config_path: Path, detected_port: str, dry_run: bool = False) -> bool:
    """Update sput.yml with detected RFID port.
    
    Args:
        config_path: Path to sput.yml file
        detected_port: RFID reader serial port to set
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
        
        # Update rfid_port
        if 'serial' not in config:
            config['serial'] = {}
        
        old_port = config['serial'].get('rfid_port', 'not set')
        config['serial']['rfid_port'] = detected_port
        
        print(f"\n📝 Configuration update:")
        print(f"   Old rfid_port: {old_port}")
        print(f"   New rfid_port: {detected_port}")
        
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
        description='Detect Raspberry Pi Pico RFID reader port and update sput.yml configuration'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Show results without updating config file')
    parser.add_argument('--verbose', action='store_true',
                        help='Show detailed scanning information')
    parser.add_argument('--exclude-port', action='append',
                        help='Exclude specific port from scanning (can be used multiple times)')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Raspberry Pi Pico RFID Reader Port Detection Utility")
    print("=" * 60)
    
    # Scan for RFID reader
    excluded_ports = args.exclude_port if args.exclude_port else []
    detected_port = scan_for_rfid(
        excluded_ports=excluded_ports,
        verbose=args.verbose
    )
    
    if not detected_port:
        print("\n❌ Failed to detect RFID reader port")
        print("\nTroubleshooting:")
        print("  1. Ensure Raspberry Pi Pico is connected via USB")
        print("  2. Check that pico_rfid_serial.py firmware is uploaded to Pico")
        print("  3. Verify USB cable is data-capable (not charge-only)")
        print("  4. Try unplugging and reconnecting the Pico")
        print("  5. Check Device Manager (Windows) or dmesg (Linux) for port info")
        print("  6. Verify Pico sends 'PICO_RFID_READY' message on startup")
        sys.exit(1)
    
    # Get config file path
    script_dir = Path(__file__).parent
    config_path = script_dir.parent / 'sput.yml'
    
    # Update config file
    if update_config_file(config_path, detected_port, dry_run=args.dry_run):
        print("\n✅ Detection complete!")
        print(f"\nRFID reader port: {detected_port}")
        
        if not args.dry_run:
            print("\n💡 RFID reader is now configured in sput.yml")
    else:
        print("\n❌ Failed to update configuration")
        sys.exit(1)


if __name__ == '__main__':
    main()
