#!/usr/bin/env python3
"""
MFC Port Detection Utility

This script scans available serial ports to find Alicat MFC devices and
updates the gas_control/config.yml file with the detected ports.

Usage:
    python detect_mfc_ports.py [--arduino-port COMX] [--dry-run]

Options:
    --arduino-port COMX  : Specify Arduino port to exclude from scanning
    --dry-run           : Show results without updating config file
    --verbose           : Show detailed scanning information
"""

import subprocess
import sys
import time
import argparse
from pathlib import Path
from typing import Optional, List, Dict
from serial.tools import list_ports


def test_alicat_port(port: str, unit_id: str, timeout: float = 2.0, verbose: bool = False) -> bool:
    """Test if an Alicat unit responds on a specific port.
    
    Args:
        port: Serial port to test (e.g., 'COM3' or '/dev/ttyUSB0')
        unit_id: Alicat unit ID to test (e.g., 'A', 'B', 'C')
        timeout: Command timeout in seconds
        verbose: Print detailed test information
        
    Returns:
        True if Alicat device found, False otherwise
    """
    try:
        if verbose:
            print(f"  Testing {port} for unit {unit_id}...", end=' ')
        
        # Run alicat CLI command
        cmd = ['alicat', port, '--unit', unit_id]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode == 0:
            if verbose:
                print("✅ FOUND")
            return True
        else:
            if verbose:
                print("❌ No response")
            return False
            
    except subprocess.TimeoutExpired:
        if verbose:
            print("⏱️  Timeout")
        return False
    except FileNotFoundError:
        print("\n❌ ERROR: 'alicat' CLI tool not found!")
        print("   Please install: pip install alicat")
        sys.exit(1)
    except Exception as e:
        if verbose:
            print(f"❌ Error: {e}")
        return False


def scan_for_mfcs(excluded_ports: List[str], unit_ids: List[str], verbose: bool = False) -> Dict[str, str]:
    """Scan all available serial ports for Alicat MFCs.
    
    Args:
        excluded_ports: List of ports to skip (e.g., Arduino port)
        unit_ids: List of Alicat unit IDs to search for
        verbose: Show detailed scanning information
        
    Returns:
        Dictionary mapping unit_id -> serial_port
    """
    print("\n🔍 Scanning serial ports for Alicat MFCs...")
    
    # HID device exclusion patterns
    hid_exclusion_patterns = [
        'mouse', 'keyboard', 'hid', 'input', 'touchpad', 'trackpad',
        'receiver', 'dongle', 'bluetooth', 'bt', 'wireless'
    ]
    
    # Get all available ports
    all_ports = list_ports.comports()
    
    # Filter ports
    candidate_ports = []
    
    for p in all_ports:
        # Skip excluded ports
        if p.device in excluded_ports:
            print(f"⏭️  Skipping excluded port: {p.device}")
            continue
            
        # Skip HID devices
        desc = p.description.lower()
        manufacturer = (p.manufacturer or '').lower()
        
        if any(pattern in desc or pattern in manufacturer for pattern in hid_exclusion_patterns):
            if verbose:
                print(f"⏭️  Skipping HID device: {p.device} ({p.description})")
            continue
        
        candidate_ports.append(p.device)
        if verbose:
            print(f"📋 Candidate port: {p.device} - {p.description}")
    
    if not candidate_ports:
        print("❌ No suitable serial ports found!")
        return {}
    
    print(f"\n📡 Testing {len(candidate_ports)} candidate port(s) for {len(unit_ids)} unit ID(s)...")
    
    # Test each port for each unit ID
    found_units = {}
    
    for port in candidate_ports:
        print(f"\n🔌 Testing port: {port}")
        
        for unit_id in unit_ids:
            if unit_id in found_units:
                continue  # Already found this unit
                
            if test_alicat_port(port, unit_id, verbose=verbose):
                print(f"  ✅ Found Unit {unit_id} on {port}")
                found_units[unit_id] = port
                # Don't break - multiple units might share same port
        
        # Brief delay between ports
        time.sleep(0.2)
    
    return found_units


def update_config_file(config_path: Path, detected_ports: Dict[str, str], dry_run: bool = False) -> None:
    """Update config.yml with detected port assignments.
    
    Args:
        config_path: Path to config.yml file
        detected_ports: Dictionary mapping unit_id -> serial_port
        dry_run: If True, show changes without writing file
    """
    if not config_path.exists():
        print(f"\n❌ Config file not found: {config_path}")
        return
    
    # Read current config
    content = config_path.read_text()
    lines = content.splitlines()
    new_lines = []
    
    # Track which units we've updated
    updated_units = set()
    in_mfcs_section = False
    current_gas = None
    
    for line in lines:
        stripped = line.strip()
        
        # Detect mfcs section
        if 'mfcs:' in stripped:
            in_mfcs_section = True
            new_lines.append(line)
            continue
        
        # Detect gas subsections (Ar:, N2:, O2:)
        if in_mfcs_section and ':' in stripped and not stripped.startswith('#'):
            # Check if this is a gas name (single word followed by colon)
            parts = stripped.split(':')
            if len(parts) >= 1 and not any(kw in parts[0] for kw in ['unit_id', 'serial_port', 'baudrate', 'max_flow', 'gas_type', 'enabled', 'relay_button']):
                current_gas = parts[0].strip()
                new_lines.append(line)
                continue
        
        # Update serial_port lines based on unit_id
        if in_mfcs_section and current_gas and 'unit_id:' in stripped:
            # Extract unit ID
            unit_id = stripped.split(':')[1].strip().strip("'\"")
            
            # Look ahead for serial_port line and update it
            new_lines.append(line)
            continue
        
        if in_mfcs_section and current_gas and 'serial_port:' in stripped:
            # Get the unit_id for this gas from the lines we've processed
            # Find the unit_id in the current gas block
            unit_id = None
            for prev_line in reversed(new_lines[-10:]):  # Look back up to 10 lines
                if 'unit_id:' in prev_line:
                    unit_id = prev_line.split(':')[1].strip().strip("'\"")
                    break
            
            if unit_id and unit_id in detected_ports:
                # Replace the serial_port line
                indent = len(line) - len(line.lstrip())
                new_port = detected_ports[unit_id]
                new_line = ' ' * indent + f"serial_port: '{new_port}'  # Auto-detected"
                new_lines.append(new_line)
                updated_units.add(unit_id)
                print(f"  📝 {current_gas} (Unit {unit_id}): {new_port}")
                continue
        
        # Keep other lines unchanged
        new_lines.append(line)
    
    # Write updated config
    new_content = '\n'.join(new_lines) + '\n'
    
    if dry_run:
        print("\n📄 DRY RUN - Would write the following config:")
        print("=" * 70)
        print(new_content)
        print("=" * 70)
    else:
        # Backup original
        backup_path = config_path.with_suffix('.yml.backup')
        config_path.rename(backup_path)
        print(f"\n💾 Backup saved: {backup_path}")
        
        # Write new config
        config_path.write_text(new_content)
        print(f"✅ Config updated: {config_path}")
    
    # Report summary
    print(f"\n📊 Updated {len(updated_units)} unit(s): {', '.join(sorted(updated_units))}")


def main():
    parser = argparse.ArgumentParser(
        description="Detect Alicat MFC serial ports and update configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--arduino-port', type=str, help='Arduino port to exclude from scanning')
    parser.add_argument('--dry-run', action='store_true', help='Show results without updating config')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed scanning information')
    parser.add_argument('--unit-ids', type=str, default='A,B,C', help='Comma-separated list of unit IDs to search for (default: A,B,C)')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("🔬 Alicat MFC Port Detection Utility")
    print("=" * 70)
    
    # Parse unit IDs
    unit_ids = [uid.strip() for uid in args.unit_ids.split(',')]
    print(f"\n🎯 Searching for unit IDs: {', '.join(unit_ids)}")
    
    # Excluded ports
    excluded = []
    if args.arduino_port:
        excluded.append(args.arduino_port)
        print(f"⛔ Excluding Arduino port: {args.arduino_port}")
    
    # Scan for MFCs
    detected_ports = scan_for_mfcs(excluded, unit_ids, verbose=args.verbose)
    
    if not detected_ports:
        print("\n❌ No Alicat MFCs detected!")
        print("\n💡 Troubleshooting tips:")
        print("   1. Ensure MFCs are powered on")
        print("   2. Check USB cable connections")
        print("   3. Verify 'alicat' CLI tool is installed: pip install alicat")
        print("   4. Try specifying Arduino port with --arduino-port if it's being scanned")
        print("   5. Check that unit IDs match your hardware (use --unit-ids A,B,C,...)")
        return 1
    
    print("\n✅ Detection complete!")
    print(f"   Found {len(detected_ports)} MFC(s):")
    for unit_id, port in sorted(detected_ports.items()):
        print(f"     • Unit {unit_id}: {port}")
    
    # Update config file
    config_path = Path(__file__).parent / 'config.yml'
    
    if args.dry_run:
        print("\n🔍 DRY RUN mode - config file will NOT be modified")
    
    update_config_file(config_path, detected_ports, dry_run=args.dry_run)
    
    if not args.dry_run:
        print("\n✅ Configuration updated successfully!")
        print("   You can now restart the sputter control application.")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
