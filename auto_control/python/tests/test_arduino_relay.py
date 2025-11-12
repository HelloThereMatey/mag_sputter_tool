#!/usr/bin/env python3
"""
Simple Arduino Relay Test Script
Tests connection to Arduino and operates relays via serial communication.

This script provides basic functionality to:
1. Auto-detect Arduino port
2. Test connection 
3. Control individual relays
4. Read digital and analog inputs
5. Get relay status

Based on your relay_controller.ino firmware.
"""

import serial
import serial.tools.list_ports
import time
import sys
from typing import Optional

class SimpleArduinoTester:
    """Simple Arduino tester for relay operations."""
    
    def __init__(self, baudrate: int = 9600):
        self.serial_port: Optional[serial.Serial] = None
        self.baudrate = baudrate
        self.is_connected = False
        
    def find_arduino_port(self) -> Optional[str]:
        """Auto-detect Arduino port by testing for ARDUINO_READY message."""
        print("🔍 Searching for Arduino...")
        ports = serial.tools.list_ports.comports()
        
        if not ports:
            print("❌ No serial ports found")
            return None
            
        print(f"📋 Found {len(ports)} serial port(s):")
        for port in ports:
            print(f"   {port.device} - {port.description}")
        
        # Test each port
        for port in ports:
            print(f"\n🔌 Testing {port.device}...")
            try:
                # Open port with settings that match your Arduino
                test_serial = serial.Serial(
                    port=port.device,
                    baudrate=self.baudrate,
                    timeout=2.0,
                    write_timeout=2.0,
                    dsrdtr=False,  # Don't reset Arduino
                    rtscts=False
                )
                
                print(f"   📡 Port opened successfully")
                
                # Wait for Arduino to respond
                time.sleep(1.0)
                
                # Check if ARDUINO_READY is in buffer
                if test_serial.in_waiting > 0:
                    data = test_serial.read(test_serial.in_waiting)
                    try:
                        buffer_text = data.decode().strip()
                        print(f"   📨 Buffer content: '{buffer_text}'")
                        
                        # Check for safety errors first
                        if "CRITICAL_SAFETY_ERROR" in buffer_text or "ARDUINO_SAFETY_HALT" in buffer_text:
                            print(f"   🚨 SAFETY ERROR DETECTED!")
                            print(f"   {buffer_text}")
                            test_serial.close()
                            continue
                            
                        if "ARDUINO_READY" in buffer_text:
                            print(f"   ✅ Arduino found!")
                            test_serial.close()
                            return port.device
                    except UnicodeDecodeError:
                        print(f"   📝 Buffer contained binary data")
                
                # Wait for new ARDUINO_READY message
                print(f"   ⏳ Waiting for ARDUINO_READY message...")
                start_time = time.time()
                while time.time() - start_time < 3.0:  # 3 second timeout
                    if test_serial.in_waiting > 0:
                        try:
                            line = test_serial.readline().decode().strip()
                            print(f"   📨 Received: '{line}'")
                            
                            # Check for safety errors
                            if "CRITICAL_SAFETY_ERROR" in line or "ARDUINO_SAFETY_HALT" in line:
                                print(f"   🚨 SAFETY ERROR: {line}")
                                test_serial.close()
                                return None  # Stop searching on safety error
                                
                            if line == "ARDUINO_READY":
                                print(f"   ✅ Arduino found!")
                                test_serial.close()
                                return port.device
                        except UnicodeDecodeError:
                            pass
                    time.sleep(0.1)
                
                test_serial.close()
                print(f"   ❌ No Arduino response")
                
            except (serial.SerialException, OSError) as e:
                print(f"   ❌ Cannot open port: {e}")
                continue
                
        print("❌ No Arduino found on any port")
        return None
    
    def connect(self, port: Optional[str] = None) -> bool:
        """Connect to Arduino on specified port or auto-detect."""
        if self.is_connected:
            print("ℹ️  Already connected")
            return True
            
        if port is None:
            port = self.find_arduino_port()
            
        if port is None:
            return False
            
        try:
            print(f"\n🔌 Connecting to Arduino on {port}...")
            self.serial_port = serial.Serial(
                port=port,
                baudrate=self.baudrate,
                timeout=2.0,
                write_timeout=2.0
            )
            
            print(f"✅ Connected successfully!")
            print(f"   Port: {self.serial_port.port}")
            print(f"   Baudrate: {self.serial_port.baudrate}")
            
            # Wait for Arduino and check for ready message
            time.sleep(1.0)
            
            # Check for any startup messages
            if self.serial_port.in_waiting > 0:
                data = self.serial_port.read(self.serial_port.in_waiting)
                try:
                    startup_msg = data.decode().strip()
                    if startup_msg:
                        print(f"📨 Arduino startup message:")
                        for line in startup_msg.split('\n'):
                            if line.strip():
                                print(f"   {line.strip()}")
                except UnicodeDecodeError:
                    print("📝 Received binary startup data")
            
            self.is_connected = True
            return True
            
        except (serial.SerialException, OSError) as e:
            print(f"❌ Connection failed: {e}")
            if self.serial_port:
                self.serial_port.close()
                self.serial_port = None
            return False
    
    def disconnect(self):
        """Disconnect from Arduino."""
        if self.serial_port:
            print("🔌 Disconnecting from Arduino...")
            # Turn off all relays before disconnecting (safety)
            self.send_command("ALL_OFF")
            self.serial_port.close()
            self.serial_port = None
            self.is_connected = False
            print("✅ Disconnected")
    
    def send_command(self, command: str) -> str:
        """Send command to Arduino and get response."""
        if not self.is_connected or not self.serial_port:
            return "ERROR: Not connected"
            
        try:
            # Send command
            cmd_bytes = f"{command}\n".encode()
            self.serial_port.write(cmd_bytes)
            self.serial_port.flush()
            
            # Wait for response
            response = self.serial_port.readline().decode().strip()
            return response
            
        except (serial.SerialException, OSError, UnicodeDecodeError) as e:
            print(f"❌ Communication error: {e}")
            return "ERROR: Communication failed"
    
    def turn_relay_on(self, relay_num: int) -> bool:
        """Turn on specific relay (1-23)."""
        if relay_num < 1 or relay_num > 23:
            print(f"❌ Invalid relay number: {relay_num} (must be 1-23)")
            return False
            
        command = f"RELAY_{relay_num}_ON"
        response = self.send_command(command)
        
        if response == "OK":
            print(f"✅ Relay {relay_num} turned ON")
            return True
        else:
            print(f"❌ Failed to turn ON relay {relay_num}: {response}")
            return False
    
    def turn_relay_off(self, relay_num: int) -> bool:
        """Turn off specific relay (1-23)."""
        if relay_num < 1 or relay_num > 23:
            print(f"❌ Invalid relay number: {relay_num} (must be 1-23)")
            return False
            
        command = f"RELAY_{relay_num}_OFF"
        response = self.send_command(command)
        
        if response == "OK":
            print(f"✅ Relay {relay_num} turned OFF")
            return True
        else:
            print(f"❌ Failed to turn OFF relay {relay_num}: {response}")
            return False
    
    def get_status(self) -> Optional[str]:
        """Get status of all relays."""
        response = self.send_command("STATUS")
        if response.startswith("STATUS:"):
            status_data = response[7:]  # Remove "STATUS:" prefix
            return status_data
        else:
            print(f"❌ Failed to get status: {response}")
            return None
    
    def print_relay_status(self):
        """Print formatted relay status."""
        status = self.get_status()
        if status:
            states = status.split(",")
            print("\n📊 Relay Status:")
            for i, state in enumerate(states):
                relay_num = i + 1
                state_text = "ON" if state == "1" else "OFF"
                print(f"   Relay {relay_num:2d}: {state_text}")
        else:
            print("❌ Could not retrieve relay status")
    
    def get_digital_inputs(self) -> Optional[str]:
        """Get digital input states."""
        response = self.send_command("GET_DIGITAL_INPUTS")
        if response.startswith("DIGITAL_INPUTS:"):
            return response[15:]  # Remove prefix
        else:
            print(f"❌ Failed to get digital inputs: {response}")
            return None
    
    def print_digital_inputs(self):
        """Print formatted digital input status."""
        inputs = self.get_digital_inputs()
        if inputs:
            states = inputs.split(",")
            input_names = ["Door", "Water", "Rod", "Spare"]
            print("\n🔘 Digital Inputs (Safety Interlocks):")
            for i, state in enumerate(states):
                if i < len(input_names):
                    name = input_names[i]
                    status = "SAFE" if state == "1" else "UNSAFE"
                    emoji = "✅" if state == "1" else "⚠️"
                    print(f"   {emoji} {name}: {status}")
        else:
            print("❌ Could not retrieve digital inputs")
    
    def get_analog_inputs(self) -> Optional[str]:
        """Get analog input values."""
        response = self.send_command("GET_ANALOG_INPUTS")
        if response.startswith("ANALOG_INPUTS:"):
            return response[14:]  # Remove prefix
        else:
            print(f"❌ Failed to get analog inputs: {response}")
            return None
    
    def print_analog_inputs(self):
        """Print formatted analog input values."""
        inputs = self.get_analog_inputs()
        if inputs:
            values = inputs.split(",")
            input_names = ["Load-lock", "Chamber", "Ion Gauge", "Turbo Spin"]
            print("\n📈 Analog Inputs:")
            for i, value in enumerate(values):
                if i < len(input_names):
                    name = input_names[i]
                    # Convert to voltage (0-1023 = 0-5V)
                    voltage = int(value) * 5.0 / 1023.0
                    print(f"   {name}: {value} ({voltage:.2f}V)")
        else:
            print("❌ Could not retrieve analog inputs")
    
    def all_relays_off(self) -> bool:
        """Turn off all relays (emergency)."""
        response = self.send_command("ALL_OFF")
        if response == "OK":
            print("✅ All relays turned OFF")
            return True
        else:
            print(f"❌ Failed to turn off all relays: {response}")
            return False


def interactive_test():
    """Interactive test session."""
    print("=" * 60)
    print("Arduino Relay Controller - Interactive Test")
    print("=" * 60)
    
    arduino = SimpleArduinoTester()
    
    try:
        # Connect to Arduino
        if not arduino.connect():
            print("❌ Failed to connect to Arduino")
            return
        
        while True:
            print("\n" + "=" * 40)
            print("Commands:")
            print("  1. Get relay status")
            print("  2. Turn relay ON")
            print("  3. Turn relay OFF") 
            print("  4. Get digital inputs (safety)")
            print("  5. Get analog inputs")
            print("  6. Turn all relays OFF")
            print("  7. Test relay sequence")
            print("  q. Quit")
            print("=" * 40)
            
            choice = input("\nEnter choice: ").strip().lower()
            
            if choice == 'q':
                break
            elif choice == '1':
                arduino.print_relay_status()
            elif choice == '2':
                try:
                    relay_num = int(input("Enter relay number (1-23): "))
                    arduino.turn_relay_on(relay_num)
                except ValueError:
                    print("❌ Invalid relay number")
            elif choice == '3':
                try:
                    relay_num = int(input("Enter relay number (1-23): "))
                    arduino.turn_relay_off(relay_num)
                except ValueError:
                    print("❌ Invalid relay number")
            elif choice == '4':
                arduino.print_digital_inputs()
            elif choice == '5':
                arduino.print_analog_inputs()
            elif choice == '6':
                arduino.all_relays_off()
            elif choice == '7':
                test_relay_sequence(arduino)
            else:
                print("❌ Invalid choice")
                
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user")
    finally:
        arduino.disconnect()


def test_relay_sequence(arduino: SimpleArduinoTester):
    """Test a sequence of relay operations."""
    print("\n🔄 Testing relay sequence...")
    
    # Turn off all relays first
    arduino.all_relays_off()
    time.sleep(1)
    
    # Test relays 1-5 in sequence
    test_relays = [1, 2, 3, 4, 5]
    
    print("🔄 Turning relays ON in sequence...")
    for relay in test_relays:
        print(f"   Testing relay {relay}...")
        if arduino.turn_relay_on(relay):
            time.sleep(0.5)  # Brief pause
            arduino.print_relay_status()
            time.sleep(1.0)
        else:
            print(f"❌ Failed to control relay {relay}")
            break
    
    print("\n🔄 Turning relays OFF in reverse sequence...")
    for relay in reversed(test_relays):
        print(f"   Turning off relay {relay}...")
        if arduino.turn_relay_off(relay):
            time.sleep(0.5)
        else:
            print(f"❌ Failed to turn off relay {relay}")
            break
    
    print("✅ Relay sequence test completed")


def quick_test():
    """Quick connection and basic test."""
    print("🚀 Quick Arduino Test")
    print("-" * 30)
    
    arduino = SimpleArduinoTester()
    
    try:
        # Connect
        if not arduino.connect():
            return
        
        # Get initial status
        print("\n📊 Initial Status:")
        arduino.print_relay_status()
        arduino.print_digital_inputs()
        arduino.print_analog_inputs()
        
        # Test one relay
        print("\n🔄 Testing relay 1...")
        arduino.turn_relay_on(1)
        time.sleep(2)
        arduino.turn_relay_off(1)
        
        print("\n✅ Quick test completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
    finally:
        arduino.disconnect()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        quick_test()
    else:
        interactive_test()