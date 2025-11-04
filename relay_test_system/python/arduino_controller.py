"""
Arduino Controller for Relay Test System
Handles serial communication with Arduino Mega 2560 controlling 16 relays
Cross-platform support for Windows, Linux, and Raspberry Pi
"""

import serial
import serial.tools.list_ports
import threading
import time
import queue
import sys
import platform
from typing import Optional, List, Tuple


class ArduinoController:
    """
    Controls Arduino-based relay system via serial communication.
    Provides thread-safe operations and automatic port detection.
    """
    NUM_RELAYS = 20
    
    def __init__(self):
        self.serial_port: Optional[serial.Serial] = None
        self.is_connected = False
        self.command_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.communication_thread = None
        self.stop_thread = False
        self.relay_states = [False] * self.NUM_RELAYS  # Track relay states locally
        self.connection_lock = threading.Lock()
        
    def auto_connect(self) -> bool:
        """
        Automatically find and connect to Arduino.
        
        Returns:
            True if connection successful, False otherwise
        """
        print("\n🚀 Starting automatic Arduino detection and connection...")
        
        if self.is_connected:
            print("ℹ️  Already connected to Arduino")
            return True
        
        # Find Arduino port
        port = self.find_arduino_port_with_test()
        if port is None:
            print("❌ Auto-connect failed: No Arduino found")
            return False
        
        # Connect to the found port
        print(f"🔌 Auto-connecting to Arduino on {port}...")
        return self.connect(port)
        
    def find_arduino_port_with_test(self) -> Optional[str]:
        """
        Find Arduino port by testing communication with each available port.
        Uses platform-specific optimizations for better detection.
        Returns the port name if Arduino is found, None otherwise.
        """
        print("🔍 Searching for Arduino with communication test...")
        ports = serial.tools.list_ports.comports()
        
        if not ports:
            print("❌ No serial ports found on system")
            return None
        
        # Sort ports by likelihood of being Arduino based on platform
        sorted_ports = self._sort_ports_by_likelihood(ports)
        
        print(f"📋 Testing {len(sorted_ports)} serial port(s) for Arduino:")
        
        for port in sorted_ports:
            print(f"\n🔌 Testing {port.device} - {port.description}")
            
            try:
                # Try to open the port
                test_serial = serial.Serial(
                    port=port.device,
                    baudrate=9600,
                    timeout=2.0,
                    write_timeout=2.0
                )
                
                # Wait briefly and check for ARDUINO_READY
                time.sleep(0.5)
                
                # Check buffer for existing message
                if test_serial.in_waiting > 0:
                    data = test_serial.read(test_serial.in_waiting)
                    try:
                        buffer_text = data.decode().strip()
                        if "ARDUINO_READY" in buffer_text:
                            print(f"✅ Arduino found on {port.device}!")
                            test_serial.close()
                            return port.device
                    except UnicodeDecodeError:
                        pass
                
                # If not in buffer, wait for new message
                start_time = time.time()
                while time.time() - start_time < 2:
                    if test_serial.in_waiting > 0:
                        try:
                            line = test_serial.readline().decode().strip()
                            if line == "ARDUINO_READY":
                                print(f"✅ Arduino found on {port.device}!")
                                test_serial.close()
                                return port.device
                        except UnicodeDecodeError:
                            pass
                    time.sleep(0.1)
                
                test_serial.close()
                print(f"❌ No Arduino response on {port.device}")
                
            except (serial.SerialException, OSError) as e:
                print(f"❌ Cannot open {port.device}: {e}")
                continue
        
        print("❌ No Arduino found on any port")
        return None
    
    def _sort_ports_by_likelihood(self, ports):
        """
        Sort ports by likelihood of being Arduino based on platform and device info.
        
        Args:
            ports: List of serial port objects
            
        Returns:
            Sorted list of ports (most likely Arduino first)
        """
        current_platform = platform.system().lower()
        
        def port_priority(port):
            """Calculate priority score for a port (lower = higher priority)."""
            score = 100  # Default score
            device = port.device.lower()
            description = port.description.lower()
            
            # Platform-specific port name preferences
            if current_platform == "windows":
                # On Windows, Arduino usually appears as COM ports
                if device.startswith("com"):
                    score -= 20
            elif current_platform in ["linux", "darwin"]:  # Linux or macOS
                # On Unix-like systems, Arduino typically uses ACM or USB devices
                if "/dev/ttyacm" in device:
                    score -= 30  # ACM devices are most common for Arduino
                elif "/dev/ttyusb" in device:
                    score -= 25  # USB serial devices
                elif "/dev/cu.usbmodem" in device:  # macOS
                    score -= 25
                elif "/dev/cu.usbserial" in device:  # macOS
                    score -= 20
            
            # Description-based detection
            arduino_keywords = ["arduino", "mega", "uno", "ch340", "cp210", "ftdi"]
            for keyword in arduino_keywords:
                if keyword in description:
                    score -= 15
                    break
            
            # VID/PID detection for known Arduino manufacturers
            if hasattr(port, 'vid') and port.vid:
                arduino_vids = [
                    0x2341,  # Arduino
                    0x1A86,  # CH340 (clone)
                    0x10C4,  # CP210x (clone)
                    0x0403,  # FTDI (some Arduinos)
                ]
                if port.vid in arduino_vids:
                    score -= 25
            
            return score
        
        # Sort by priority (lower score = higher priority)
        return sorted(ports, key=port_priority)
        
    def connect(self, port: Optional[str] = None, baudrate: int = 9600, timeout: float = 2.0) -> bool:
        """
        Connect to Arduino on specified or auto-detected port.
        
        Args:
            port: COM port name (auto-detect if None)
            baudrate: Serial communication speed
            timeout: Timeout for serial operations
            
        Returns:
            True if connection successful, False otherwise
        """
        with self.connection_lock:
            if self.is_connected:
                print("ℹ️  Already connected to Arduino")
                return True
                
            print(f"\n🔌 Attempting to connect to Arduino...")
            print(f"   Port: {port if port else 'Auto-detect'}")
            print(f"   Baudrate: {baudrate}")
            print(f"   Timeout: {timeout}s")
                
            if port is None:
                port = self.find_arduino_port_with_test()
                
            if port is None:
                print("❌ No suitable port found for connection")
                return False
                
            print(f"\n🔌 Connecting to {port}...")
            
            try:
                self.serial_port = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    timeout=timeout,
                    write_timeout=timeout
                )
                
                print(f"✅ Serial port opened successfully")
                print(f"   Port: {self.serial_port.port}")
                print(f"   Baudrate: {self.serial_port.baudrate}")
                print(f"   Timeout: {self.serial_port.timeout}")
                
                # Wait briefly for Arduino to initialize
                print("⏳ Waiting for Arduino to initialize (1s)...")
                time.sleep(1)  # Shorter wait
                
                # Check if ARDUINO_READY is already in buffer
                bytes_in_buffer = self.serial_port.in_waiting
                if bytes_in_buffer > 0:
                    print(f"📨 Found {bytes_in_buffer} bytes in buffer")
                    data = self.serial_port.read(bytes_in_buffer)
                    print(f"   Buffer content: {data}")
                    
                    # Check if ARDUINO_READY is in the buffer
                    try:
                        buffer_text = data.decode().strip()
                        print(f"   Decoded: '{buffer_text}'")
                        if "ARDUINO_READY" in buffer_text:
                            print("✅ Arduino ready message found in buffer!")
                            self.is_connected = True
                            self.start_communication_thread()
                            print("🚀 Arduino connection established successfully!")
                            return True
                    except UnicodeDecodeError:
                        print("⚠️  Buffer contains non-text data")
                
                # If not in buffer, wait for new message
                print("⏳ Waiting for new ARDUINO_READY message (5s timeout)...")
                ready_timeout = time.time() + 5  # 5 second timeout
                ready_received = False
                
                while time.time() < ready_timeout:
                    if self.serial_port.in_waiting > 0:
                        try:
                            response = self.serial_port.readline().decode().strip()
                            print(f"📨 Received: '{response}'")
                            if response == "ARDUINO_READY":
                                print("✅ Arduino ready message received!")
                                ready_received = True
                                break
                        except UnicodeDecodeError:
                            print("⚠️  Received non-text data, continuing...")
                    time.sleep(0.1)
                
                if not ready_received:
                    print("❌ Timeout waiting for ARDUINO_READY message")
                    print("   Check that Arduino firmware is uploaded correctly")
                    self.serial_port.close()
                    self.serial_port = None
                    return False
                    
                self.is_connected = True
                self.start_communication_thread()
                print("🚀 Arduino connection established successfully!")
                return True
                
            except serial.SerialException as e:
                print(f"❌ Serial port error: {e}")
                if self.serial_port:
                    self.serial_port.close()
                    self.serial_port = None
                return False
            except OSError as e:
                print(f"❌ OS error opening port: {e}")
                if self.serial_port:
                    self.serial_port.close()
                    self.serial_port = None
                return False
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
                if self.serial_port:
                    self.serial_port.close()
                    self.serial_port = None
                return False
                
    def disconnect(self):
        """Safely disconnect from Arduino."""
        with self.connection_lock:
            if not self.is_connected:
                return
                
            self.is_connected = False
            self.stop_thread = True
            
            # Turn off all relays before disconnecting
            self.send_command_direct("ALL_OFF")
            
            if self.communication_thread and self.communication_thread.is_alive():
                self.communication_thread.join(timeout=2)
                
            if self.serial_port:
                self.serial_port.close()
                self.serial_port = None
                
            # Clear queues
            self.clear_queues()
            
    def start_communication_thread(self):
        """Start background thread for handling serial communication."""
        self.stop_thread = False
        self.communication_thread = threading.Thread(
            target=self._communication_worker,
            daemon=True
        )
        self.communication_thread.start()
        
    def _communication_worker(self):
        """Background thread worker for handling serial communication."""
        while not self.stop_thread and self.is_connected:
            try:
                # Process outgoing commands
                try:
                    command = self.command_queue.get(timeout=0.1)
                    response = self.send_command_direct(command)
                    self.response_queue.put(response)
                except queue.Empty:
                    pass
                    
            except Exception as e:
                print(f"Communication thread error: {e}")
                self.is_connected = False
                break
                
    def send_command_direct(self, command: str) -> str:
        """
        Send command directly to Arduino and wait for response.
        
        Args:
            command: Command string to send
            
        Returns:
            Response string from Arduino
        """
        if not self.is_connected or not self.serial_port:
            return "ERROR"
            
        try:
            # Send command
            self.serial_port.write(f"{command}\n".encode())
            self.serial_port.flush()
            
            # Wait for response
            response = self.serial_port.readline().decode().strip()
            return response
            
        except (serial.SerialException, OSError) as e:
            print(f"Serial communication error: {e}")
            self.is_connected = False
            return "ERROR"
            
    def send_command(self, command: str, timeout: float = 2.0) -> str:
        """
        Send command via queue system (thread-safe).
        
        Args:
            command: Command string to send
            timeout: Maximum time to wait for response
            
        Returns:
            Response string from Arduino
        """
        if not self.is_connected:
            return "ERROR"
            
        # Clear old responses
        self.clear_response_queue()
        
        # Send command
        self.command_queue.put(command)
        
        # Wait for response
        try:
            response = self.response_queue.get(timeout=timeout)
            return response
        except queue.Empty:
            return "TIMEOUT"
            
    def set_relay(self, relay_number: int, state: bool) -> bool:
        """
        Set specific relay ON or OFF.
        
        Args:
            relay_number: Relay number (1-20)
            state: True for ON, False for OFF
        Returns:
            True if command successful, False otherwise
        """
        if not (1 <= relay_number <= self.NUM_RELAYS):
            return False
        command = f"RELAY_{relay_number}_{'ON' if state else 'OFF'}"
        response = self.send_command(command)
        if response == "OK":
            # Update local state tracking
            self.relay_states[relay_number - 1] = state
            return True
        return False
        
    def get_relay_state(self, relay_number: int) -> bool:
        """
        Get current state of specific relay.
        Args:
            relay_number: Relay number (1-20)
        Returns:
            True if relay is ON, False if OFF
        """
        if not (1 <= relay_number <= self.NUM_RELAYS):
            return False
        return self.relay_states[relay_number - 1]
        
    def get_all_relay_states(self) -> List[bool]:
        """Get current state of all relays."""
        return self.relay_states.copy()
        
    def all_relays_off(self) -> bool:
        """Turn off all relays (emergency function)."""
        response = self.send_command("ALL_OFF")
        if response == "OK":
            self.relay_states = [False] * self.NUM_RELAYS
            return True
        return False
        
    def get_status(self) -> Optional[List[bool]]:
        """
        Query Arduino for current relay states.
        Returns:
            List of relay states, or None if error
        """
        response = self.send_command("STATUS")
        if response.startswith("STATUS:"):
            try:
                states_str = response.split(":", 1)[1]
                states = [s == "1" for s in states_str.split(",")]
                if len(states) == self.NUM_RELAYS:
                    self.relay_states = states
                    return states
            except (ValueError, IndexError):
                pass
        return None
        
    def clear_queues(self):
        """Clear all command and response queues."""
        self.clear_command_queue()
        self.clear_response_queue()
        
    def clear_command_queue(self):
        """Clear command queue."""
        while not self.command_queue.empty():
            try:
                self.command_queue.get_nowait()
            except queue.Empty:
                break
                
    def clear_response_queue(self):
        """Clear response queue."""
        while not self.response_queue.empty():
            try:
                self.response_queue.get_nowait()
            except queue.Empty:
                break
                
    def is_arduino_connected(self) -> bool:
        """Check if Arduino is currently connected."""
        return self.is_connected
        
    def get_digital_inputs(self) -> Optional[List[bool]]:
        """
        Query Arduino for current digital input states.
        Returns:
            List of digital input states (True=HIGH, False=LOW), or None if error
        """
        response = self.send_command("GET_DIGITAL_INPUTS")
        if response.startswith("DIGITAL_INPUTS:"):
            try:
                states_str = response.split(":", 1)[1]
                states = [s == "1" for s in states_str.split(",")]
                return states
            except (ValueError, IndexError):
                pass
        return None
        
    def get_analog_inputs(self) -> Optional[List[int]]:
        """
        Query Arduino for current analog input values.
        Returns:
            List of analog input values (0-1023 raw ADC), or None if error
        """
        response = self.send_command("GET_ANALOG_INPUTS")
        if response.startswith("ANALOG_INPUTS:"):
            try:
                values_str = response.split(":", 1)[1]
                values = [int(v) for v in values_str.split(",")]
                return values
            except (ValueError, IndexError):
                pass
        return None
        
    def get_analog_voltages(self) -> Optional[List[float]]:
        """
        Query Arduino for current analog input values and convert to voltages.
        Returns:
            List of analog input voltages (0-5V), or None if error
        """
        raw_values = self.get_analog_inputs()
        if raw_values is not None:
            # Convert ADC values (0-1023) to voltages (0-5V)
            return [value * 5.0 / 1023.0 for value in raw_values]
        return None
        
    def get_available_ports(self) -> List[Tuple[str, str]]:
        """
        Get list of available serial ports with enhanced cross-platform information.
        
        Returns:
            List of tuples (port_name, description)
        """
        ports = serial.tools.list_ports.comports()
        port_list = []
        
        for port in ports:
            # Create enhanced description with platform-specific info
            description = port.description
            
            # Add manufacturer info if available
            if hasattr(port, 'manufacturer') and port.manufacturer:
                description += f" ({port.manufacturer})"
            
            # Add VID/PID info for debugging
            if hasattr(port, 'vid') and port.vid and hasattr(port, 'pid') and port.pid:
                description += f" [VID:PID={port.vid:04X}:{port.pid:04X}]"
            
            port_list.append((port.device, description))
        
        return port_list
