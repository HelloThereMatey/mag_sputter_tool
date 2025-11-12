# Gas Flow Control Module Testing

This directory contains test files and examples for the gas flow control module.

## Test Files

### example_usage.py
Comprehensive example script showing how to use all aspects of the gas control module:
- Basic MFC control and monitoring
- Recipe creation and execution
- Safety system integration
- GUI widget testing

Run with:
```bash
# Run all examples
python example_usage.py

# Run specific example
python example_usage.py basic    # Basic usage only
python example_usage.py recipe   # Recipe system only
python example_usage.py safety   # Safety integration only
python example_usage.py gui      # GUI widget test only
```

### Hardware Requirements for Testing

Before running the examples, you'll need:

1. **Alicat APEX MFCs connected via serial**
   - Update the `serial_port` values in the example configs
   - Windows: Usually COM3, COM4, COM5
   - Linux: Usually /dev/ttyUSB0, /dev/ttyUSB1, /dev/ttyUSB2

2. **Proper gas connections**
   - Ensure MFCs have appropriate gas supplies connected
   - Check that pressure is adequate for flow control

3. **Serial permissions (Linux)**
   ```bash
   sudo usermod -a -G dialout $USER
   # Then log out and back in
   ```

### Configuration Testing

The examples use test configurations. Before running:

1. **Update serial ports** in the config dictionaries to match your hardware
2. **Adjust flow limits** to match your MFC specifications
3. **Check unit IDs** - usually 'A', 'B', 'C' for Alicat MFCs

### Troubleshooting Tests

If examples fail:

1. **Check serial connections**:
   ```python
   from alicat import FlowController
   fc = FlowController('A', port='COM3')  # Your port
   print(fc.get())  # Should return MFC data
   ```

2. **Verify MFC communication**:
   - Use Alicat's FlowVision software to confirm MFC operation
   - Check baud rate (usually 19200 for APEX MFCs)
   - Verify unit IDs using FlowVision

3. **Check imports**:
   ```python
   from gas_control import create_gas_controller
   # Should import without errors
   ```

### Mock Testing

For testing without hardware, the Alicat driver supports mock mode:

```python
from alicat.mock import FlowController  # Use mock instead of real driver

# Then use in your gas control config as normal
```

This allows testing the control logic without physical MFCs.