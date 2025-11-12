# Gas Flow Control Module for Sputter Control System

This module provides comprehensive gas flow control for Alicat APEX mass flow controllers (MFCs) integrated with the sputter control system.

## Features

- **Thread-safe MFC communication** with automatic reconnection
- **Safety system integration** with configurable limits and interlocks
- **Recipe-based gas mixing** with step-by-step execution
- **PyQt5 GUI widgets** for operator control and monitoring
- **Real-time monitoring** of flow rates, pressures, and temperatures
- **Emergency stop functionality** with fail-safe operation

## Hardware Requirements

- 3x Alicat APEX Mass Flow Controllers (Ar, O2, N2)
- Serial communication (USB/RS-232/RS-485)
- Integration with existing sputter control safety systems

## Installation

1. Ensure the Alicat driver is available:
   ```bash
   # Either add the alicat folder to your Python path, or:
   pip install alicat
   ```

2. Add the gas_control module to your auto_control/python directory

3. Update your `sput.yml` configuration (see `config_example.yml`)

## Quick Start

### Basic Usage

```python
from gas_control import create_gas_controller, GasFlowSafetyIntegration
from gas_control.gui_widgets import GasControlWidget

# Load configuration from sput.yml
config = load_config()
gas_config = config.get('gas_control', {})

# Create gas controller
gas_controller = create_gas_controller(gas_config)

# Start the controller
if gas_controller.start():
    print("Gas control system started successfully")
    
    # Set flow rates
    gas_controller.set_flow_rate("Ar", 50.0)  # 50 sccm Argon
    gas_controller.set_flow_rate("O2", 10.0)  # 10 sccm Oxygen
    
    # Get current readings
    readings = gas_controller.get_all_readings()
    for channel, reading in readings.items():
        print(f"{channel}: {reading.mass_flow:.1f} sccm")
    
    # Stop all flows
    gas_controller.stop_all_flows()
    
    # Stop controller
    gas_controller.stop()
```

### GUI Integration

```python
from PyQt5.QtWidgets import QApplication, QMainWindow
from gas_control.gui_widgets import GasControlWidget

app = QApplication([])
window = QMainWindow()

# Create gas control widget
gas_widget = GasControlWidget(gas_controller, safety_integration)
window.setCentralWidget(gas_widget)

window.show()
app.exec_()
```

### Recipe Usage

```python
from gas_control.recipes import GasRecipe, GasStep, RecipeExecutor

# Create a recipe
steps = [
    GasStep("Purge", 60.0, {"Ar": 50.0, "O2": 0.0, "N2": 0.0}),
    GasStep("Process", 300.0, {"Ar": 40.0, "O2": 10.0, "N2": 0.0}),
    GasStep("Stop", 30.0, {"Ar": 0.0, "O2": 0.0, "N2": 0.0})
]

recipe = GasRecipe("Sputtering Process", "Standard Ar/O2 sputtering", steps)

# Execute recipe
executor = RecipeExecutor(gas_controller)
executor.execute_recipe(recipe)

# Monitor execution
while executor.is_executing:
    status = executor.get_execution_status()
    print(f"Step {status['current_step']}: {status['progress']:.1%} complete")
    time.sleep(1)
```

## Configuration

Add this section to your `sput.yml` file:

```yaml
gas_control:
  auto_reconnect: true
  reconnect_interval: 5.0
  read_interval: 1.0
  
  mfcs:
    Ar:
      unit_id: 'A'
      serial_port: 'COM3'  # Adjust for your system
      max_flow: 200.0
      gas_type: 'Ar'
      enabled: true
    
    O2:
      unit_id: 'B'
      serial_port: 'COM4'
      max_flow: 100.0
      gas_type: 'O2'
      enabled: true
    
    N2:
      unit_id: 'C'
      serial_port: 'COM5'
      max_flow: 150.0
      gas_type: 'N2'
      enabled: true
  
  safety:
    max_individual_flow: 200.0
    max_total_flow: 400.0
    max_oxygen_percentage: 30.0
    min_pressure_for_flow: 1e-3
    emergency_stop_flow: 1000.0
```

## Integration with AutoControl GUI

1. **Add imports to app.py:**
   ```python
   from .gas_control import create_gas_controller, GasFlowSafetyIntegration
   from .gas_control.gui_widgets import GasControlWidget
   ```

2. **Initialize in AutoControlWindow.__init__():**
   ```python
   def _init_gas_control(self):
       gas_config = self.cfg.get('gas_control', {})
       self.gas_controller = create_gas_controller(gas_config, self.safety_controller)
       self.gas_safety_integration = GasFlowSafetyIntegration(
           self.gas_controller, self.safety_controller
       )
       self.gas_controller.start()
   ```

3. **Add menu item:**
   ```python
   gas_action = tools_menu.addAction('Gas Flow Control')
   gas_action.triggered.connect(self.open_gas_control)
   ```

4. **Add cleanup:**
   ```python
   def closeEvent(self, event):
       if hasattr(self, 'gas_controller') and self.gas_controller:
           self.gas_controller.stop()
       super().closeEvent(event)
   ```

## Safety Features

The gas control system includes comprehensive safety features:

- **Flow rate limits** (individual and total)
- **Oxygen concentration limits** (combustion safety)
- **Chamber pressure interlocks** (prevent flow at high pressure)
- **Emergency stop functionality** (immediate flow cutoff)
- **Safety system integration** (door, water, interlock monitoring)
- **Automatic error recovery** (reconnection and fault handling)

## Architecture

### Core Components

- **GasFlowController**: Main controller managing multiple MFCs
- **MFCChannel**: Individual MFC configuration and state
- **RecipeManager**: Gas recipe storage and management  
- **RecipeExecutor**: Automated recipe execution
- **GasFlowSafetyIntegration**: Safety system integration
- **GasControlWidget**: PyQt5 GUI components

### Threading Model

- **Main thread**: GUI and user interaction
- **Control thread**: MFC communication and monitoring  
- **Command queue**: Thread-safe command passing
- **Callbacks**: Status updates and error handling

### Communication Flow

```
GUI Widget → Command Queue → Control Thread → Alicat MFC
    ↑                                             ↓
Status Updates ← Callback System ← Reading Thread
```

## Error Handling

The system includes comprehensive error handling:

- **Automatic reconnection** for lost connections
- **Safety interlocks** for dangerous conditions
- **Error callbacks** for user notification
- **Graceful degradation** when MFCs are offline
- **Emergency procedures** for critical failures

## Testing

Test the system step-by-step:

1. **Configuration test:**
   ```python
   from gas_control import create_gas_controller
   config = {'mfcs': {'Ar': {'unit_id': 'A', 'serial_port': 'COM3', ...}}}
   controller = create_gas_controller(config)
   ```

2. **Connection test:**
   ```python
   controller.start()
   status = controller.get_all_status()
   print(status)
   ```

3. **Flow control test:**
   ```python
   controller.set_flow_rate("Ar", 10.0)
   reading = controller.get_reading("Ar")
   print(f"Setpoint: {reading.setpoint}, Actual: {reading.mass_flow}")
   ```

4. **Safety test:**
   ```python
   safety = GasFlowSafetyIntegration(controller)
   approved, reason = safety.get_flow_approval("Ar", 1000.0)  # Should be denied
   print(f"Approved: {approved}, Reason: {reason}")
   ```

## Troubleshooting

### Common Issues

1. **MFC not connecting:**
   - Check serial port and unit ID configuration
   - Verify physical connections and power
   - Check Alicat unit ID switches

2. **Safety system blocking flows:**
   - Check chamber interlocks (door, water, etc.)
   - Verify pressure readings are within limits
   - Check safety configuration limits

3. **GUI not updating:**
   - Verify controller.start() was called successfully
   - Check for error messages in logs
   - Ensure update timers are running

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Create controller with debug info
controller = create_gas_controller(config)
controller.start()
```

## Support

For integration support:
1. Check the `integration_guide.py` for detailed examples
2. Review log files for error messages
3. Test individual components separately
4. Verify hardware connections and configuration

## License

This module follows the same license as the parent sputter control system.