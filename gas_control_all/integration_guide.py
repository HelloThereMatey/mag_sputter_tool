"""Integration guide for adding gas flow control to auto_control GUI.

This module provides examples and instructions for integrating the gas flow
control system into the existing sputter control GUI.
"""

from __future__ import annotations

from typing import Optional
import logging

# Example integration into app.py
INTEGRATION_EXAMPLE = """
# Add to app.py imports:
from .gas_control import GasFlowController, GasFlowSafetyIntegration, create_gas_controller
from .gas_control.gui_widgets import GasControlWidget

# Add to AutoControlWindow.__init__():
class AutoControlWindow(QMainWindow):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        # ... existing initialization ...
        
        # Initialize gas flow control
        self._init_gas_control()
        
        # Add gas control to menu (after existing Tools menu setup)
        if menubar is not None:
            gas_action = tools_menu.addAction('Gas Flow Control')
            gas_action.triggered.connect(self.open_gas_control)
        
        self._gas_control_window = None

    def _init_gas_control(self) -> None:
        '''Initialize gas flow control system.'''
        try:
            # Get gas control config from sput.yml
            gas_config = self.cfg.get('gas_control', {})
            if not gas_config:
                self.logger.warning("No gas_control configuration found in sput.yml")
                return
            
            # Create gas flow controller
            self.gas_controller = create_gas_controller(gas_config, self.safety_controller)
            
            # Create safety integration
            self.gas_safety_integration = GasFlowSafetyIntegration(
                self.gas_controller, 
                self.safety_controller
            )
            
            # Configure safety limits from config
            safety_limits = gas_config.get('safety', {})
            if safety_limits:
                self.gas_safety_integration.configure_limits(safety_limits)
            
            # Start the gas controller
            if self.gas_controller.start():
                self.logger.info("Gas flow control system initialized successfully")
            else:
                self.logger.error("Failed to start gas flow control system")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize gas flow control: {e}")
            self.gas_controller = None
            self.gas_safety_integration = None

    def open_gas_control(self) -> None:
        '''Open the gas flow control window.'''
        if not self.gas_controller:
            QMessageBox.warning(
                self, 
                "Gas Control Unavailable",
                "Gas flow control system is not initialized.\\n\\n"
                "Please check your configuration and MFC connections."
            )
            return
            
        if self._gas_control_window is None:
            self._gas_control_window = GasControlWidget(
                self.gas_controller,
                self.gas_safety_integration,
                parent=self
            )
            self._gas_control_window.setAttribute(Qt.WA_DeleteOnClose, True)
            self._gas_control_window.destroyed.connect(
                lambda: setattr(self, '_gas_control_window', None)
            )
            self._gas_control_window.show()
        else:
            self._gas_control_window.raise_()
            self._gas_control_window.activateWindow()

    def closeEvent(self, event) -> None:
        # ... existing cleanup ...
        
        # Stop gas controller
        if hasattr(self, 'gas_controller') and self.gas_controller:
            self.gas_controller.stop()
        
        super().closeEvent(event)
"""

# Example config.py modifications
CONFIG_EXAMPLE = """
# Add to config.py:

def load_config(config_path: str = None) -> Dict[str, Any]:
    # ... existing config loading ...
    
    # Validate gas control configuration
    if 'gas_control' in config:
        _validate_gas_config(config['gas_control'])
    
    return config

def _validate_gas_config(gas_config: Dict[str, Any]) -> None:
    '''Validate gas control configuration.'''
    mfcs = gas_config.get('mfcs', {})
    if not mfcs:
        logging.warning("No MFCs configured in gas_control section")
        return
    
    for name, mfc_config in mfcs.items():
        required_fields = ['unit_id', 'serial_port', 'max_flow', 'gas_type']
        for field in required_fields:
            if field not in mfc_config:
                raise ValueError(f"Missing required field '{field}' for MFC '{name}'")
        
        # Validate gas type
        from alicat import FlowController
        if mfc_config['gas_type'] not in FlowController.gases:
            logging.warning(f"Gas type '{mfc_config['gas_type']}' for MFC '{name}' not in Alicat gas list")
"""

# Example safety integration
SAFETY_INTEGRATION_EXAMPLE = """
# Add to safety/safety_conditions.yml:

gas_flow:
  # Gas flow safety conditions
  max_individual_flow:
    condition: "gas_flow_rate <= max_individual_limit"
    message: "Individual gas flow rate exceeds safety limit"
    modes: ["Normal", "Manual"]
    
  max_total_flow:
    condition: "total_gas_flow <= max_total_limit"
    message: "Total gas flow rate exceeds safety limit"
    modes: ["Normal", "Manual"]
    
  oxygen_percentage:
    condition: "oxygen_percentage <= max_oxygen_percentage"
    message: "Oxygen percentage exceeds safety limit (combustion risk)"
    modes: ["Normal", "Manual"]
    confirmation_required: true
    confirmation_message: "High oxygen concentration detected. Continue?"

# Add to safety_controller.py:
class SafetyController:
    def __init__(self):
        # ... existing initialization ...
        self.gas_safety_callbacks = []
    
    def register_gas_safety_callback(self, callback):
        '''Register callback for gas safety events.'''
        self.gas_safety_callbacks.append(callback)
    
    def check_gas_flow_safety(self, channel: str, flow_rate: float, 
                             current_flows: Dict[str, float]) -> SafetyResult:
        '''Check safety for gas flow request.'''
        # Implementation based on your safety system
        # Return SafetyResult with allowed/denied status
        pass
"""


def create_example_recipe_file():
    """Create an example gas recipe file."""
    from .recipes import GasRecipe, GasStep, RecipeManager
    
    # Create example recipe
    steps = [
        GasStep(
            name="Pump down",
            duration=60.0,  # 1 minute
            flows={"Ar": 0.0, "O2": 0.0, "N2": 0.0},
            description="Initial pump down with no gas flow"
        ),
        GasStep(
            name="Ar purge",
            duration=120.0,  # 2 minutes
            flows={"Ar": 50.0, "O2": 0.0, "N2": 0.0},
            description="Purge chamber with Argon"
        ),
        GasStep(
            name="Process gas",
            duration=300.0,  # 5 minutes
            flows={"Ar": 40.0, "O2": 10.0, "N2": 0.0},
            description="Main sputtering process with Ar/O2 mix"
        ),
        GasStep(
            name="Shutdown",
            duration=60.0,  # 1 minute
            flows={"Ar": 0.0, "O2": 0.0, "N2": 0.0},
            description="Stop all gas flows"
        )
    ]
    
    recipe = GasRecipe(
        name="Example Sputtering Recipe",
        description="Example recipe demonstrating gas flow control during sputtering",
        steps=steps,
        created_by="System"
    )
    
    # Save recipe
    manager = RecipeManager()
    manager.save_recipe(recipe)
    
    return recipe


# Example usage in GUI
GUI_USAGE_EXAMPLE = """
# Example of using gas control in a custom procedure:

def run_sputtering_with_gas(self) -> None:
    '''Run sputtering procedure with gas flow control.'''
    if not hasattr(self, 'gas_controller') or not self.gas_controller:
        self.show_error("Gas control not available")
        return
    
    try:
        # 1. Check safety conditions
        if self.gas_safety_integration:
            safety_status = self.gas_safety_integration.get_safety_status()
            if not safety_status['gas_flow_enabled']:
                self.show_error("Gas flow is disabled by safety system")
                return
        
        # 2. Set initial gas flows
        self.gas_controller.set_flow_rate("Ar", 50.0)  # 50 sccm Argon
        time.sleep(5)  # Allow flow to stabilize
        
        # 3. Start vacuum pumps (existing relay control)
        self.arduino.set_relay(self.relay_map['btnPumpTurbo'], True)
        
        # 4. Wait for pressure to stabilize
        # ... existing pressure monitoring code ...
        
        # 5. Add process gas
        self.gas_controller.set_flow_rate("O2", 10.0)  # 10 sccm Oxygen
        
        # 6. Run sputtering process
        # ... existing sputtering control code ...
        
        # 7. Shutdown gas flows
        self.gas_controller.stop_all_flows()
        
    except Exception as e:
        self.logger.error(f"Error in gas-controlled sputtering: {e}")
        # Emergency cleanup
        if self.gas_controller:
            self.gas_controller.stop_all_flows()
"""


def print_integration_instructions():
    """Print step-by-step integration instructions."""
    print("=== Gas Flow Control Integration Instructions ===")
    print()
    print("1. Add configuration to sput.yml:")
    print("   - Copy the gas_control section from config_example.yml")
    print("   - Update serial ports and MFC settings for your hardware")
    print()
    print("2. Install Alicat driver dependency:")
    print("   - Ensure the alicat folder is in your Python path")
    print("   - Or install via: pip install alicat")
    print()
    print("3. Modify app.py:")
    print("   - Add gas control imports")
    print("   - Add _init_gas_control() method to AutoControlWindow")
    print("   - Add menu item for gas control window")
    print("   - Add cleanup in closeEvent()")
    print()
    print("4. Update safety system (optional but recommended):")
    print("   - Add gas flow safety conditions to safety_conditions.yml")
    print("   - Integrate gas safety checks into SafetyController")
    print()
    print("5. Test the integration:")
    print("   - Start the GUI and check for gas control initialization messages")
    print("   - Open Tools → Gas Flow Control to test the interface")
    print("   - Verify MFC communication and safety interlocks")
    print()
    print("6. Create gas recipes:")
    print("   - Use the RecipeManager to create and save gas recipes")
    print("   - Integrate recipe execution into your automatic procedures")
    print()
    print("For detailed examples, see the docstrings in this module.")


if __name__ == "__main__":
    print_integration_instructions()