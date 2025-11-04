#!/usr/bin/env python3
"""
Robust Alicat MFC test that handles parsing issues.

This script includes error handling for the common zip() length mismatch issue.
"""

import asyncio
from alicat import FlowController


class DebugFlowController(FlowController):
    """FlowController with debug information for troubleshooting."""
    
    async def get_debug(self):
        """Get method with debug output to help troubleshoot parsing issues."""
        command = f'{self.unit}'
        line = await self._write_and_read(command)
        
        print(f"Raw response: {repr(line)}")
        
        if not line:
            raise OSError("Could not read values")
        
        spl = line.split()
        unit, values = spl[0], spl[1:]
        
        print(f"Unit: {unit}")
        print(f"Values: {values}")
        print(f"Number of values: {len(values)}")
        print(f"Expected keys: {self.keys}")
        print(f"Number of keys: {len(self.keys)}")
        
        # Handle over range errors
        while values and values[-1].upper() in ['MOV', 'VOV', 'POV', 'TOV']:
            removed = values.pop()
            print(f"Removed over-range indicator: {removed}")
        
        if unit != self.unit:
            raise ValueError("Flow controller unit ID mismatch.")
        
        # Handle lock indicator
        if values and values[-1].upper() == 'LCK':
            self.button_lock = True
            values.pop()
            print("Removed lock indicator")
        else:
            self.button_lock = False
        
        # Dynamic key adjustment based on response length
        keys = self.keys.copy()
        
        if len(values) == 5 and len(keys) == 6:
            keys.remove('setpoint')  # Remove setpoint for 5-value response
            print("Adjusted: Removed setpoint from keys")
        elif len(values) == 7 and len(keys) == 6:
            keys.insert(5, 'total_flow')  # Add total flow for 7-value response
            print("Adjusted: Added total_flow to keys")
        elif len(values) == 2 and len(keys) == 6:
            keys = ['unit_id', 'setpoint']  # Minimal response
            print("Adjusted: Using minimal key set")
        
        print(f"Final keys: {keys}")
        print(f"Final values: {values}")
        
        if len(keys) != len(values):
            print(f"⚠️  Still have length mismatch: {len(keys)} keys vs {len(values)} values")
            # Create a safe mapping
            result = {}
            for i, key in enumerate(keys):
                if i < len(values):
                    value = values[i]
                    # Try to convert to float if possible
                    try:
                        result[key] = float(value)
                    except ValueError:
                        result[key] = value
                else:
                    result[key] = None
            return result
        
        # Normal mapping
        result = {}
        for key, value in zip(keys, values):
            try:
                result[key] = float(value)
            except ValueError:
                result[key] = value
        
        return result


async def robust_test():
    """Test with robust error handling."""
    print("Robust Alicat MFC Test")
    print("=" * 30)
    
    for unit_id in ['A', 'B', 'C']:
        print(f"\nTesting unit {unit_id}:")
        print("-" * 20)
        
        try:
            fc = DebugFlowController('/dev/ttyUSB0', unit=unit_id, timeout=2)
            
            # Use our debug get method
            result = await fc.get_debug()
            print(f"✅ Success! Result: {result}")
            
            await fc.close()
            
        except Exception as e:
            print(f"❌ Failed: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(robust_test())