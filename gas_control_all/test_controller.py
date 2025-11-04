#!/usr/bin/env python3
"""
Basic test for the gas_control module functionality.

This script tests the core GasFlowController before running the full examples.
It can also be used for direct MFC control via command line parameters.

Examples:
    python test_controller.py                    # Run full test
    python test_controller.py --unit_id A --set_flow 30  # Set unit A to 30 sccm
    python test_controller.py --unit_id B --set_flow 0   # Stop unit B
    python test_controller.py --list_units              # List available units
"""

import sys
import time
import logging
import argparse
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def get_default_config():
    """Get the default MFC configuration."""
    return {
        'auto_reconnect': True,
        'reconnect_interval': 5.0,
        'read_interval': 1.0,
        'mfcs': {
            'Ar': {
                'unit_id': 'A',
                'serial_port': '/dev/ttyUSB0',
                'max_flow': 200.0,
                'gas_type': 'Ar',
                'enabled': True
            },
            'O2': {
                'unit_id': 'B', 
                'serial_port': '/dev/ttyUSB0',
                'max_flow': 100.0,
                'gas_type': 'O2',
                'enabled': True
            },
            'N2': {
                'unit_id': 'C',
                'serial_port': '/dev/ttyUSB0',
                'max_flow': 150.0,
                'gas_type': 'N2',
                'enabled': True
            }
        }
    }


def find_channel_by_unit_id(config, unit_id):
    """Find the channel name for a given unit ID."""
    for channel_name, channel_config in config['mfcs'].items():
        if channel_config.get('unit_id') == unit_id:
            return channel_name
    return None


def control_mfc_direct(unit_id, flow_rate):
    """Directly control a specific MFC unit."""
    print(f"=== Direct MFC Control: Unit {unit_id} ===")
    
    try:
        from controller import GasFlowController
        
        config = get_default_config()
        
        # Find the channel for this unit ID
        channel_name = find_channel_by_unit_id(config, unit_id)
        if not channel_name:
            print(f"❌ Unit ID '{unit_id}' not found in configuration")
            print("Available units:")
            for name, ch_config in config['mfcs'].items():
                print(f"  {ch_config['unit_id']}: {name}")
            return False
        
        print(f"Found unit {unit_id} -> Channel: {channel_name}")
        
        # Create and start controller
        controller = GasFlowController(config)
        
        if not controller.start():
            print("❌ Failed to start controller")
            return False
        
        try:
            # Wait for connection
            print("Connecting to MFC...")
            time.sleep(3)
            
            # Check if this specific unit is connected
            status = controller.get_channel_status(channel_name)
            if status['connection_status'] != 'connected':
                print(f"❌ Unit {unit_id} ({channel_name}) not connected")
                print(f"Status: {status['connection_status']}")
                if status['last_error']:
                    print(f"Error: {status['last_error']}")
                return False
            
            print(f"✅ Unit {unit_id} ({channel_name}) connected")
            
            # Get current reading
            current_reading = controller.get_reading(channel_name)
            if current_reading:
                print(f"Current state: {current_reading.mass_flow:.2f} sccm, "
                      f"{current_reading.temperature:.1f}°C, "
                      f"{current_reading.pressure:.2f} psia")
            
            # Set the requested flow rate
            print(f"Setting flow rate to {flow_rate} sccm...")
            if controller.set_flow_rate(channel_name, flow_rate):
                print(f"✅ Successfully set unit {unit_id} to {flow_rate} sccm")
                
                # Wait and read back
                time.sleep(2)
                new_reading = controller.get_reading(channel_name)
                if new_reading:
                    print(f"New flow rate: {new_reading.mass_flow:.2f} sccm")
                    print(f"Setpoint: {new_reading.setpoint:.2f} sccm")
                
                return True
            else:
                print(f"❌ Failed to set flow rate for unit {unit_id}")
                return False
                
        finally:
            controller.stop()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def list_available_units():
    """List all available MFC units from configuration."""
    print("=== Available MFC Units ===")
    
    config = get_default_config()
    
    try:
        from controller import GasFlowController
        
        controller = GasFlowController(config)
        if not controller.start():
            print("❌ Failed to start controller")
            return False
        
        try:
            print("Checking connections...")
            time.sleep(3)
            
            status = controller.get_all_status()
            
            print(f"\n{'Unit ID':<8} {'Channel':<8} {'Status':<12} {'Max Flow':<10} {'Gas Type':<8}")
            print("-" * 60)
            
            for channel_name, ch_status in status.items():
                unit_id = ch_status.get('name', 'Unknown')
                # Find unit_id from config
                for name, ch_config in config['mfcs'].items():
                    if name == channel_name:
                        unit_id = ch_config.get('unit_id', 'Unknown')
                        break
                
                conn_status = ch_status.get('connection_status', 'unknown')
                max_flow = ch_status.get('max_flow', 0)
                gas_type = ch_status.get('gas_type', 'Unknown')
                
                status_symbol = "✅" if conn_status == 'connected' else "❌"
                print(f"{unit_id:<8} {channel_name:<8} {status_symbol} {conn_status:<10} {max_flow:<10.1f} {gas_type:<8}")
                
                if ch_status.get('last_error'):
                    print(f"         Error: {ch_status['last_error']}")
            
            return True
            
        finally:
            controller.stop()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_gas_controller_basic():
    """Test basic gas controller functionality."""
    print("=== Testing Gas Controller Module ===")
    
    try:
        # Check if we can import the controller
        from controller import GasFlowController, MFCChannel
        print("✅ Successfully imported GasFlowController")
        
        # Test configuration
        config = get_default_config()
        
        # Create controller
        print("Creating GasFlowController...")
        controller = GasFlowController(config)
        print("✅ GasFlowController created successfully")
        
        # Check channel configuration
        print(f"Configured channels: {list(controller.channels.keys())}")
        
        # Start controller
        print("Starting controller...")
        if controller.start():
            print("✅ Controller started successfully")
            
            try:
                # Wait for connections
                print("Waiting for MFC connections (5 seconds)...")
                time.sleep(5)
                
                # Check status
                print("\nMFC Status:")
                status = controller.get_all_status()
                connected_count = 0
                
                for channel, ch_status in status.items():
                    conn_status = ch_status.get('connection_status', 'unknown')
                    print(f"  {channel}: {conn_status}")
                    if conn_status == 'connected':
                        connected_count += 1
                    if ch_status.get('last_error'):
                        print(f"    Error: {ch_status['last_error']}")
                
                print(f"\nConnected MFCs: {connected_count}/3")
                
                if connected_count > 0:
                    print("✅ At least one MFC connected successfully")
                    
                    # Try to get readings
                    print("\nGetting readings...")
                    readings = controller.get_all_readings()
                    for channel, reading in readings.items():
                        if reading:
                            print(f"  {channel}: {reading.mass_flow:.2f} sccm, "
                                  f"{reading.temperature:.1f}°C, "
                                  f"{reading.pressure:.2f} psia")
                    
                    # Test setting a small flow rate
                    test_channel = list(controller.channels.keys())[0]  # First channel
                    print(f"\nTesting flow control on {test_channel}...")
                    
                    if controller.set_flow_rate(test_channel, 5.0):
                        print(f"✅ Successfully set {test_channel} to 5.0 sccm")
                        time.sleep(2)
                        
                        # Read back
                        reading = controller.get_reading(test_channel)
                        if reading:
                            print(f"  Current flow: {reading.mass_flow:.2f} sccm")
                        
                        # Return to zero
                        controller.set_flow_rate(test_channel, 0.0)
                        print(f"✅ Returned {test_channel} to 0.0 sccm")
                    else:
                        print(f"❌ Failed to set flow rate for {test_channel}")
                
                else:
                    print("⚠️  No MFCs connected - check your hardware setup")
                    
            finally:
                print("\nStopping controller...")
                controller.stop()
                print("✅ Controller stopped")
        else:
            print("❌ Failed to start controller")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're in the gas_control directory")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def check_dependencies():
    """Check if all required modules are available."""
    print("=== Checking Dependencies ===")
    
    required_modules = [
        'alicat',
        'serial',
        'asyncio',
        'threading',
        'logging',
        'yaml'
    ]
    
    missing = []
    
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError:
            print(f"❌ {module} - MISSING")
            missing.append(module)
    
    if missing:
        print(f"\n⚠️  Missing modules: {missing}")
        print("Install missing modules with:")
        for mod in missing:
            if mod == 'serial':
                print("  pip install pyserial")
            elif mod == 'yaml':
                print("  pip install PyYAML")
            else:
                print(f"  pip install {mod}")
        return False
    else:
        print("\n✅ All required modules available")
        return True


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Gas Control Module Test and Direct MFC Control',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Run full test suite
  %(prog)s --unit_id A --set_flow 30    # Set unit A to 30 sccm
  %(prog)s --unit_id B --set_flow 0     # Stop unit B flow
  %(prog)s --list_units                 # List all available units
  %(prog)s --unit_id C --get_reading    # Get current reading from unit C
        """
    )
    
    parser.add_argument('--unit_id', type=str, 
                       help='MFC unit ID (A, B, C, etc.)')
    parser.add_argument('--set_flow', type=float,
                       help='Set flow rate in sccm')
    parser.add_argument('--get_reading', action='store_true',
                       help='Get current reading from specified unit')
    parser.add_argument('--list_units', action='store_true',
                       help='List all available MFC units and their status')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    return parser.parse_args()


def get_unit_reading(unit_id):
    """Get current reading from a specific MFC unit."""
    print(f"=== Reading from Unit {unit_id} ===")
    
    try:
        from controller import GasFlowController
        
        config = get_default_config()
        
        # Find the channel for this unit ID
        channel_name = find_channel_by_unit_id(config, unit_id)
        if not channel_name:
            print(f"❌ Unit ID '{unit_id}' not found")
            return False
        
        controller = GasFlowController(config)
        
        if not controller.start():
            print("❌ Failed to start controller")
            return False
        
        try:
            print("Connecting...")
            time.sleep(3)
            
            # Check connection
            status = controller.get_channel_status(channel_name)
            if status['connection_status'] != 'connected':
                print(f"❌ Unit {unit_id} not connected")
                return False
            
            # Get reading
            reading = controller.get_reading(channel_name)
            if reading:
                print(f"✅ Unit {unit_id} ({channel_name}) Reading:")
                print(f"  Mass Flow:     {reading.mass_flow:.2f} sccm")
                print(f"  Setpoint:      {reading.setpoint:.2f} sccm")
                print(f"  Temperature:   {reading.temperature:.1f} °C")
                print(f"  Pressure:      {reading.pressure:.2f} psia")
                print(f"  Gas Type:      {reading.gas}")
                print(f"  Control Point: {reading.control_point}")
                return True
            else:
                print(f"❌ No reading available from unit {unit_id}")
                return False
                
        finally:
            controller.stop()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    args = parse_arguments()
    
    # Configure logging based on verbosity
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Gas Control Module - Test & Control Tool")
    print("=" * 50)
    
    # Handle specific commands
    if args.list_units:
        list_available_units()
    elif args.unit_id and args.set_flow is not None:
        control_mfc_direct(args.unit_id, args.set_flow)
    elif args.unit_id and args.get_reading:
        get_unit_reading(args.unit_id)
    elif args.unit_id:
        print("❌ Please specify --set_flow or --get_reading with --unit_id")
        print("Use --help for usage examples")
    else:
        # Run full test suite
        if not check_dependencies():
            print("\n❌ Cannot proceed - missing dependencies")
            sys.exit(1)
        
        if test_gas_controller_basic():
            print("\n" + "=" * 50)
            print("✅ Basic test completed successfully!")
            print("\nNow you can use direct control:")
            print("  python test_controller.py --unit_id A --set_flow 30")
            print("  python test_controller.py --list_units")
            print("  python test_controller.py --unit_id B --get_reading")
        else:
            print("\n" + "=" * 50)
            print("❌ Basic test failed")
            print("Fix the issues above before proceeding")