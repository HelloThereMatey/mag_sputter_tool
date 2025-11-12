#!/usr/bin/env python3
"""Example usage script for the gas flow control system.

This script demonstrates how to use the gas flow control module
with Alicat APEX MFCs in various scenarios.

Run this script to test your gas control setup before integrating
with the main sputter control GUI.
"""

import sys
import time
import logging
from pathlib import Path

# Add the parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def example_basic_usage():
    """Basic gas flow control example."""
    print("=== Basic Gas Flow Control Example ===")
    
    from gas_control import create_gas_controller
    
    # Example configuration (adjust for your hardware)
    config = {
        'auto_reconnect': True,
        'reconnect_interval': 5.0,
        'read_interval': 1.0,
        'mfcs': {
            'Ar': {
                'unit_id': 'A',
                'serial_port': '/dev/ttyUSB0',  # All MFCs on same port with different unit IDs
                'max_flow': 200.0,
                'gas_type': 'Ar',
                'enabled': True
            },
            'O2': {
                'unit_id': 'B', 
                'serial_port': '/dev/ttyUSB0',  # Same port, different unit ID
                'max_flow': 100.0,
                'gas_type': 'O2',
                'enabled': True
            },
            'N2': {
                'unit_id': 'C',
                'serial_port': '/dev/ttyUSB0',  # Same port, different unit ID
                'max_flow': 150.0,
                'gas_type': 'N2',
                'enabled': True
            }
        }
    }
    
    # Create and start controller
    print("Creating gas flow controller...")
    controller = create_gas_controller(config)
    
    print("Starting controller...")
    if not controller.start():
        print("Failed to start gas controller")
        return
    
    try:
        # Wait for connections
        print("Waiting for MFC connections...")
        time.sleep(3)
        
        # Check status
        print("\nMFC Status:")
        status = controller.get_all_status()
        for channel, ch_status in status.items():
            conn_status = ch_status.get('connection_status', 'unknown')
            print(f"  {channel}: {conn_status}")
            if ch_status.get('last_error'):
                print(f"    Error: {ch_status['last_error']}")
        
        # Set some flow rates
        print("\nSetting flow rates...")
        controller.set_flow_rate("Ar", 50.0)
        controller.set_flow_rate("O2", 10.0)
        
        # Monitor for a bit
        print("\nMonitoring flows for 10 seconds...")
        for i in range(10):
            readings = controller.get_all_readings()
            total_flow = controller.get_total_flow_rate()
            
            print(f"Time {i+1:2d}s - Total: {total_flow:5.1f} sccm", end="")
            for channel, reading in readings.items():
                if reading:
                    print(f" | {channel}: {reading.mass_flow:5.1f} sccm", end="")
            print()
            
            time.sleep(1)
        
        # Stop all flows
        print("\nStopping all flows...")
        controller.stop_all_flows()
        
        time.sleep(2)
        
        # Final reading
        print("\nFinal readings:")
        readings = controller.get_all_readings()
        for channel, reading in readings.items():
            if reading:
                print(f"  {channel}: {reading.mass_flow:.1f} sccm")
    
    finally:
        print("\nStopping controller...")
        controller.stop()
        print("Done.")


def example_recipe_usage():
    """Gas recipe example."""
    print("\n=== Gas Recipe Example ===")
    
    from gas_control import create_gas_controller
    from gas_control.recipes import GasRecipe, GasStep, RecipeExecutor, RecipeManager
    
    # Use same config as basic example (abbreviated)
    config = {
        'mfcs': {
            'Ar': {'unit_id': 'A', 'serial_port': '/dev/ttyUSB0', 'max_flow': 200.0, 'gas_type': 'Ar', 'enabled': True},
            'O2': {'unit_id': 'B', 'serial_port': '/dev/ttyUSB0', 'max_flow': 100.0, 'gas_type': 'O2', 'enabled': True}
        }
    }
    
    controller = create_gas_controller(config)
    if not controller.start():
        print("Failed to start gas controller")
        return
    
    try:
        # Create a recipe
        steps = [
            GasStep(
                name="Initial purge",
                duration=10.0,  # 10 seconds for demo
                flows={"Ar": 100.0, "O2": 0.0},
                description="Purge with pure Argon"
            ),
            GasStep(
                name="Process gas",
                duration=15.0,  # 15 seconds
                flows={"Ar": 80.0, "O2": 20.0},
                description="Process with Ar/O2 mixture"
            ),
            GasStep(
                name="Shutdown",
                duration=5.0,   # 5 seconds
                flows={"Ar": 0.0, "O2": 0.0},
                description="Stop all flows"
            )
        ]
        
        recipe = GasRecipe(
            name="Demo Recipe",
            description="Demonstration recipe for testing",
            steps=steps,
            created_by="Example Script"
        )
        
        print(f"Created recipe '{recipe.name}' with {len(recipe.steps)} steps")
        print(f"Total duration: {recipe.total_duration} seconds")
        
        # Save recipe
        manager = RecipeManager()
        if manager.save_recipe(recipe):
            print("Recipe saved successfully")
        
        # Execute recipe
        executor = RecipeExecutor(controller)
        print(f"\nStarting recipe execution...")
        
        if executor.execute_recipe(recipe):
            print("Recipe execution started")
            
            # Monitor execution
            while executor.is_executing:
                status = executor.get_execution_status()
                if status['executing']:
                    step_name = status.get('step_name', 'Unknown')
                    progress = status.get('progress', 0.0)
                    print(f"  Step {status['current_step']+1}/{status['total_steps']}: "
                          f"{step_name} - {progress:.1%} complete")
                
                time.sleep(1)
            
            print("Recipe execution completed")
        else:
            print("Failed to start recipe execution")
    
    finally:
        controller.stop()


def example_safety_integration():
    """Safety system integration example."""
    print("\n=== Safety Integration Example ===")
    
    from gas_control import create_gas_controller
    from gas_control.safety_integration import GasFlowSafetyIntegration
    
    # Basic config
    config = {
        'mfcs': {
            'Ar': {'unit_id': 'A', 'serial_port': '/dev/ttyUSB0', 'max_flow': 200.0, 'gas_type': 'Ar', 'enabled': True},
            'O2': {'unit_id': 'B', 'serial_port': '/dev/ttyUSB0', 'max_flow': 100.0, 'gas_type': 'O2', 'enabled': True}
        },
        'safety': {
            'max_individual_flow': 150.0,
            'max_total_flow': 250.0,
            'max_oxygen_percentage': 25.0,
            'min_pressure_for_flow': 1e-3,
            'emergency_stop_flow': 500.0
        }
    }
    
    controller = create_gas_controller(config)
    if not controller.start():
        print("Failed to start gas controller")
        return
    
    try:
        # Create safety integration
        safety = GasFlowSafetyIntegration(controller)
        
        # Configure safety limits
        safety.configure_limits(config['safety'])
        
        print("Safety system configured with limits:")
        status = safety.get_safety_status()
        limits = status['limits']
        for limit_name, value in limits.items():
            print(f"  {limit_name}: {value}")
        
        print("\nTesting flow approvals:")
        
        # Test normal flow request
        approved, reason = safety.get_flow_approval("Ar", 50.0)
        print(f"Ar 50.0 sccm: {'APPROVED' if approved else 'DENIED'} - {reason}")
        
        # Test excessive individual flow
        approved, reason = safety.get_flow_approval("Ar", 200.0)
        print(f"Ar 200.0 sccm: {'APPROVED' if approved else 'DENIED'} - {reason}")
        
        # Test excessive total flow (simulate current flows)
        current_flows = {"Ar": 200.0, "O2": 0.0}
        approved, reason = safety.check_flow_request_safety("O2", 100.0, current_flows)
        print(f"O2 100.0 sccm (with Ar 200.0): {'APPROVED' if approved else 'DENIED'} - {reason}")
        
        # Test oxygen percentage
        current_flows = {"Ar": 50.0, "O2": 0.0}
        approved, reason = safety.check_flow_request_safety("O2", 25.0, current_flows)  # 33% O2
        print(f"O2 25.0 sccm (with Ar 50.0): {'APPROVED' if approved else 'DENIED'} - {reason}")
        
        print("\nSafety system integration test completed")
    
    finally:
        controller.stop()


def example_gui_test():
    """GUI widget test example."""
    print("\n=== GUI Widget Test ===")
    
    try:
        from PyQt5.QtWidgets import QApplication
        from gas_control import create_gas_controller
        from gas_control.gui_widgets import GasControlWidget
        from gas_control.safety_integration import GasFlowSafetyIntegration
    except ImportError as e:
        print(f"PyQt5 not available or import error: {e}")
        print("Skipping GUI test")
        return
    
    config = {
        'mfcs': {
            'Ar': {'unit_id': 'A', 'serial_port': '/dev/ttyUSB0', 'max_flow': 200.0, 'gas_type': 'Ar', 'enabled': True},
            'O2': {'unit_id': 'B', 'serial_port': '/dev/ttyUSB0', 'max_flow': 100.0, 'gas_type': 'O2', 'enabled': True},
            'N2': {'unit_id': 'C', 'serial_port': '/dev/ttyUSB0', 'max_flow': 150.0, 'gas_type': 'N2', 'enabled': True}
        }
    }
    
    controller = create_gas_controller(config)
    safety = GasFlowSafetyIntegration(controller)
    
    if not controller.start():
        print("Failed to start gas controller")
        return
    
    try:
        app = QApplication(sys.argv if hasattr(sys, 'argv') else [])
        
        # Create gas control widget
        widget = GasControlWidget(controller, safety)
        widget.setWindowTitle("Gas Flow Control - Test")
        widget.resize(800, 600)
        widget.show()
        
        print("GUI test window opened")
        print("Close the window to continue...")
        
        app.exec_()
        
        print("GUI test completed")
    
    finally:
        controller.stop()


def run_all_examples():
    """Run all examples in sequence."""
    print("Gas Flow Control Module - Example Usage")
    print("=" * 50)
    
    try:
        example_basic_usage()
        example_recipe_usage() 
        example_safety_integration()
        example_gui_test()
        
        print("\n" + "=" * 50)
        print("All examples completed successfully!")
        
    except KeyboardInterrupt:
        print("\nExamples interrupted by user")
    except Exception as e:
        print(f"\nExample failed with error: {e}")
        logging.exception("Example error")


if __name__ == "__main__":
    # You can run individual examples or all of them
    if len(sys.argv) > 1:
        example_name = sys.argv[1]
        if example_name == "basic":
            example_basic_usage()
        elif example_name == "recipe":
            example_recipe_usage()
        elif example_name == "safety":
            example_safety_integration()
        elif example_name == "gui":
            example_gui_test()
        else:
            print(f"Unknown example: {example_name}")
            print("Available examples: basic, recipe, safety, gui")
    else:
        run_all_examples()