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
import os
import uuid
from pathlib import Path
from typing import Optional, List, Tuple


class ArduinoController:
    """
    Controls Arduino-based relay system via serial communication.
    Provides thread-safe operations and automatic port detection.
    """
    NUM_RELAYS = 23  # Updated from 21 to 23
    
    def __init__(self):
        self.serial_port: Optional[serial.Serial] = None
        self.is_connected = False
        self.command_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.communication_thread = None
        self.stop_thread = False
        self.relay_states = [False] * self.NUM_RELAYS  # Track relay states locally
        self.connection_lock = threading.Lock()
        
        # Serial communication settings
        self.baud_rate = 9600  # Standard Arduino baudrate
        
        # Port caching for soft reconnection
        self.port_cache_file = Path.home() / ".sputter_control" / "last_arduino_port.txt"
        self.connection_state_file = Path.home() / ".sputter_control" / "arduino_connection_state.json"
        self.ensure_cache_directory()
        
        # Connection persistence settings
        self.keep_connection_alive = True  # Default to keeping connection alive
    
    def set_connection_persistence(self, keep_alive: bool):
        """Set whether to keep Arduino connection alive between GUI sessions."""
        self.keep_connection_alive = keep_alive
        print(f"🔧 Arduino connection persistence: {'enabled' if keep_alive else 'disabled'}")
        
    def ensure_cache_directory(self):
        """Ensure the cache directory exists."""
        try:
            self.port_cache_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Warning: Could not create cache directory: {e}")
    
    def save_port_to_cache(self, port: str):
        """Save the working port to cache file."""
        try:
            with open(self.port_cache_file, 'w') as f:
                f.write(port)
            print(f"📝 Cached Arduino port: {port}")
        except Exception as e:
            print(f"Warning: Could not save port to cache: {e}")
    
    def load_port_from_cache(self) -> Optional[str]:
        """Load the cached port if available."""
        try:
            if self.port_cache_file.exists():
                with open(self.port_cache_file, 'r') as f:
                    port = f.read().strip()
                if port:
                    print(f"📖 Found cached Arduino port: {port}")
                    return port
        except Exception as e:
            print(f"Warning: Could not load cached port: {e}")
        return None
    
    def save_connection_state(self):
        """Save current Arduino connection state for persistence."""
        try:
            import json
            import time
            
            state = {
                "port": self.serial_port.port if self.serial_port else None,
                "timestamp": time.time(),
                "relay_states": self.relay_states.copy(),
                "process_id": os.getpid(),
                "is_alive": True
            }
            
            with open(self.connection_state_file, 'w') as f:
                json.dump(state, f, indent=2)
            print(f"💾 Saved Arduino connection state: {self.connection_state_file}")
            
        except Exception as e:
            print(f"Warning: Could not save connection state: {e}")
    
    def load_connection_state(self) -> Optional[dict]:
        """Load saved Arduino connection state."""
        try:
            import json
            import time
            
            if self.connection_state_file.exists():
                with open(self.connection_state_file, 'r') as f:
                    state = json.load(f)
                
                # Check if state is recent (within last 5 minutes)
                if time.time() - state.get("timestamp", 0) < 300:
                    print(f"📖 Found recent Arduino connection state from PID {state.get('process_id')}")
                    return state
                else:
                    print("📖 Found old connection state, ignoring")
                    
        except Exception as e:
            print(f"Warning: Could not load connection state: {e}")
        return None
    
    def clear_connection_state(self):
        """Clear saved connection state."""
        try:
            if self.connection_state_file.exists():
                self.connection_state_file.unlink()
                print("🗑️  Cleared Arduino connection state")
        except Exception as e:
            print(f"Warning: Could not clear connection state: {e}")
    
    def restore_arduino_state(self):
        """Restore Arduino relay states from previous session."""
        try:
            state = self.load_connection_state()
            if not state:
                print("📝 No previous Arduino state to restore")
                return
            
            previous_relay_states = state.get("relay_states", [])
            if not previous_relay_states or len(previous_relay_states) != self.NUM_RELAYS:
                print("📝 No valid relay states to restore")
                return
            
            print("🔄 Restoring previous Arduino relay states...")
            restored_count = 0
            
            # Wait a moment for Arduino to be fully ready
            time.sleep(0.5)
            
            # Restore each relay to its previous state
            for relay_num, should_be_on in enumerate(previous_relay_states, 1):
                if should_be_on:  # Only restore relays that were ON
                    try:
                        success = self.set_relay(relay_num, True)
                        if success:
                            restored_count += 1
                            print(f"✅ Restored relay {relay_num} to ON state")
                        else:
                            print(f"⚠️  Failed to restore relay {relay_num}")
                        time.sleep(0.1)  # Brief delay between commands
                    except Exception as e:
                        print(f"⚠️  Error restoring relay {relay_num}: {e}")
            
            if restored_count > 0:
                print(f"🔄 Successfully restored {restored_count} relays to previous states")
                print("✅ Arduino state restoration complete!")
            else:
                print("📝 No relays needed restoration (all were OFF)")
                
        except Exception as e:
            print(f"⚠️  Could not restore Arduino state: {e}")
            # Don't raise - this is not critical, just continue
    
    def check_existing_connection(self) -> bool:
        """Check if Arduino connection exists from previous session."""
        state = self.load_connection_state()
        if not state or not state.get("port"):
            return False
            
        try:
            # Check if we can take over the existing connection
            print(f"🔍 Checking for existing Arduino connection on {state['port']}...")
            
            # Try to connect to the same port the previous session used
            print("📡 Opening serial connection for takeover...")
            test_serial = serial.Serial(
                port=state["port"],
                baudrate=self.baud_rate,
                timeout=2.0,
                write_timeout=2.0,
                dsrdtr=False,
                rtscts=False
            )
            
            print("✅ Serial port opened for connection takeover")
            
            # Give Arduino time to notice new connection
            print("⏳ Allowing Arduino to recognize connection takeover...")
            time.sleep(1.0)  # Increased wait time
            
            # Clear any initial buffer data
            if test_serial.in_waiting > 0:
                old_data = test_serial.read(test_serial.in_waiting)
                print(f"📦 Cleared {len(old_data)} bytes from buffer during takeover")
            
            # Test communication with STATUS command
            print("🧪 Testing communication with STATUS command...")
            test_serial.write("STATUS\n".encode())
            test_serial.flush()
            
            # Wait for response with timeout
            start_time = time.time()
            response_received = False
            
            while time.time() - start_time < 3.0:  # 3 second timeout
                if test_serial.in_waiting > 0:
                    try:
                        response = test_serial.readline().decode().strip()
                        print(f"📨 Takeover response: '{response}'")
                        response_received = True
                        
                        if response.startswith("STATUS:"):
                            print(f"✅ Successfully took over Arduino connection on {state['port']}!")
                            # Take over the connection
                            self.serial_port = test_serial
                            self.is_connected = True
                            self.relay_states = state.get("relay_states", [False] * self.NUM_RELAYS)
                            self.start_communication_thread()
                            return True
                        elif response == "OK" or response == "ERROR":
                            print(f"✅ Arduino responding with '{response}' - takeover successful!")
                            self.serial_port = test_serial
                            self.is_connected = True
                            self.relay_states = state.get("relay_states", [False] * self.NUM_RELAYS)
                            self.start_communication_thread()
                            return True
                        elif response:
                            print(f"📝 Unexpected response during takeover: '{response}'")
                    except UnicodeDecodeError:
                        print("📝 Received non-text data during takeover")
                        response_received = True
                time.sleep(0.1)
            
            if not response_received:
                print("❌ No response during connection takeover - Arduino may have reset")
            else:
                print("❌ Arduino responded but not with expected format")
                
            test_serial.close()
                
        except Exception as e:
            print(f"📝 Could not reuse existing connection: {e}")
            import traceback
            traceback.print_exc()
        
        return False
    
    def test_arduino_connection(self, port: str) -> bool:
        """Test if Arduino is responsive on the given port without triggering reset."""
        try:
            print(f"🔍 Testing Arduino connection on {port} (no reset)...")
            
            # Open serial port with DTR disabled to prevent Arduino reset
            test_serial = serial.Serial(
                port=port,
                baudrate=9600,
                timeout=2.0,  # Increased timeout to match full detection
                write_timeout=2.0,
                dsrdtr=False,  # Disable DTR to prevent Arduino reset
                rtscts=False   # Disable RTS/CTS
            )
            
            # Longer stabilization time - Arduino might be busy with other operations
            print("⏳ Allowing connection to stabilize...")
            time.sleep(0.8)  # Increased from 0.2s
            
            # Clear any existing buffer and log what was there
            bytes_waiting = test_serial.in_waiting
            if bytes_waiting > 0:
                old_data = test_serial.read(bytes_waiting)
                print(f"📦 Cleared {bytes_waiting} bytes from buffer: {old_data}")
                # Check if Arduino is sending continuous output (like safety errors)
                try:
                    buffer_text = old_data.decode().strip()
                    if buffer_text:
                        print(f"📄 Buffer contained text: '{buffer_text}'")
                        if "CRITICAL_SAFETY_ERROR" in buffer_text or "ARDUINO_SAFETY_HALT" in buffer_text:
                            print(f"🚨 Found safety error in buffer!")
                            test_serial.close()
                            raise Exception("ARDUINO_SAFETY_HALT: LOAD-LOCK ARM IS NOT IN HOME POSITION!!")
                        elif "ARDUINO_READY" in buffer_text:
                            print(f"✅ Found ARDUINO_READY in buffer - Arduino is running!")
                            test_serial.close()
                            return True
                except UnicodeDecodeError:
                    print("📝 Buffer contained binary data")
            
            # Arduino serial connection was closed when GUI disconnected
            # Need to "wake up" the Arduino's serial communication
            print("🔌 Waking up Arduino serial communication...")
            try:
                # Send multiple wake-up signals to get Arduino's attention
                for i in range(5):
                    test_serial.write(b"\n")  # Send newlines to wake up serial
                    time.sleep(0.1)
                test_serial.flush()
                print("✅ Wake-up signals sent")
                
                # Give Arduino more time to notice the new connection
                print("⏳ Allowing Arduino to recognize new connection...")
                time.sleep(1.0)  # Longer wait for serial re-establishment
                
            except Exception as write_e:
                print(f"❌ Serial write failed: {write_e}")
                test_serial.close()
                return False
            
            # Try multiple commands to test Arduino responsiveness
            # Start with simplest commands first
            test_commands = [
                ("STATUS", "STATUS", "STATUS:"),           # Simple status check - should always work
                ("ALL_OFF", "ALL_OFF", "OK"),             # Simple command that returns OK
                ("GET_DIGITAL_INPUTS", "GET_DIGITAL_INPUTS", "DIGITAL_INPUTS:"),  # Digital inputs
            ]
            
            for cmd_name, cmd_string, expected_prefix in test_commands:
                print(f"🧪 Testing with {cmd_name} command...")
                
                for attempt in range(2):  # 2 attempts per command
                    print(f"🔄 Attempt {attempt + 1}: Sending {cmd_name} command...")
                    
                    # Send command
                    command = f"{cmd_string}\n"
                    test_serial.write(command.encode())
                    test_serial.flush()
                    
                    # Wait for response with timeout
                    start_time = time.time()
                    response_received = False
                    
                    while time.time() - start_time < 2.0:  # 2s per attempt - Arduino might be slow after reconnection
                        if test_serial.in_waiting > 0:
                            try:
                                response = test_serial.readline().decode().strip()
                                print(f"📨 Received: '{response}'")
                                response_received = True
                                
                                # Check for expected response
                                if response.startswith(expected_prefix):
                                    print(f"✅ Arduino responsive on {port} with {cmd_name} - no reset needed!")
                                    test_serial.close()
                                    return True
                                elif "CRITICAL_SAFETY_ERROR" in response or "ARDUINO_SAFETY_HALT" in response:
                                    print(f"🚨 Safety error detected on {port}")
                                    test_serial.close()
                                    raise Exception("ARDUINO_SAFETY_HALT: LOAD-LOCK ARM IS NOT IN HOME POSITION!!")
                                elif response == "OK" or response == "ERROR":
                                    print(f"✅ Arduino responding with '{response}' - connection active!")
                                    test_serial.close()
                                    return True
                                elif response:  # Any other response
                                    print(f"📝 Unexpected response: '{response}' (Arduino is responding)")
                                    test_serial.close()
                                    return True  # Any response means Arduino is alive
                            except UnicodeDecodeError:
                                print("📝 Received non-text data (continuing)")
                                response_received = True
                        time.sleep(0.05)
                    
                    if not response_received:
                        print(f"❌ No response to {cmd_name} command (attempt {attempt + 1})")
                    
                    if attempt < 1:  # Don't wait after last attempt for this command
                        time.sleep(0.2)
                
                # Brief pause between different commands
                print("⏳ Trying next command...")
                time.sleep(0.3)
            
            test_serial.close()
            print(f"❌ No valid response from Arduino on {port} after 3 attempts")
            return False
            
        except serial.SerialException as e:
            print(f"❌ Cannot open {port}: {e}")
            return False
        except Exception as e:
            print(f"❌ Error testing {port}: {e}")
            if "ARDUINO_SAFETY_HALT" in str(e):
                raise  # Re-raise safety errors
            return False

    def auto_connect(self) -> bool:
        """
        Automatically find and connect to Arduino.
        Uses soft reconnection to avoid Arduino reset when possible.
        
        Returns:
            True if connection successful, False otherwise
        """
        print("\n🚀 Starting automatic Arduino detection and connection...")
        
        if self.is_connected:
            print("ℹ️  Already connected to Arduino")
            return True
        
        # Step 1: Skip soft reconnection for now - ANY serial connection triggers Arduino reset
        # Even with DTR/RTS disabled, opening the serial port causes Arduino to reset and run setup()
        # This triggers valve closure and safety checks, defeating the purpose of soft reconnection
        # Step 1: Check for existing Arduino connection from previous session
        # Temporarily disable connection reuse - hardware always resets Arduino
        # Check for saved state info (for restoration after connection)
        
        state = self.load_connection_state()
        # Step 2: Smart port detection - try preferred port first if available
        preferred_port = state["port"] if state and state.get("port") else None
        
        if preferred_port:
            print(f"🎯 Trying preferred port {preferred_port} first...")
            # Try the known port directly - much faster than full detection
            success = self.connect(preferred_port)
            if success:
                print(f"✅ Connected quickly to preferred port {preferred_port}!")
                self.save_port_to_cache(preferred_port)
                return True
            else:
                print(f"⚠️  Preferred port {preferred_port} failed, falling back to full detection")
        
        # Fallback: Full port detection (may trigger Arduino reset)  
        print("🔍 Performing full Arduino port detection...")
        port = self.find_arduino_port_with_test()
        if port is None:
            print("❌ Auto-connect failed: No Arduino found")
            return False
        
        # Connect to the found port and cache it
        print(f"🔌 Auto-connecting to Arduino on {port}...")
        success = self.connect(port)
        if success:
            self.save_port_to_cache(port)
        return success
        
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
                        # CRITICAL SAFETY CHECK: Check for Arduino safety halt during port detection
                        if "CRITICAL_SAFETY_ERROR" in buffer_text or "ARDUINO_SAFETY_HALT" in buffer_text or "LOAD-LOCK ARM IS NOT IN HOME POSITION" in buffer_text:
                            test_serial.close()
                            raise Exception("ARDUINO_SAFETY_HALT: LOAD-LOCK ARM IS NOT IN HOME POSITION!!")
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
                            # CRITICAL SAFETY CHECK: Check for Arduino safety halt during port detection
                            if "CRITICAL_SAFETY_ERROR" in line or "ARDUINO_SAFETY_HALT" in line or "LOAD-LOCK ARM IS NOT IN HOME POSITION" in line:
                                test_serial.close()
                                raise Exception("ARDUINO_SAFETY_HALT: LOAD-LOCK ARM IS NOT IN HOME POSITION!!")
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
                    
                    # Check if ARDUINO_READY is in the buffer - handle mixed text/binary data
                    ready_found_in_buffer = False
                    try:
                        buffer_text = data.decode().strip()
                        print(f"   Decoded: '{buffer_text}'")
                        if "ARDUINO_READY" in buffer_text:
                            print("✅ Arduino ready message found in buffer!")
                            ready_found_in_buffer = True
                    except UnicodeDecodeError:
                        print("⚠️  Buffer contains non-text data")
                        # Try to decode with error handling to extract readable parts
                        try:
                            buffer_text = data.decode('utf-8', errors='ignore').strip()
                            print(f"   Partial decode: '{buffer_text}'")
                            if "ARDUINO_READY" in buffer_text:
                                print("✅ Arduino ready message found in mixed buffer!")
                                ready_found_in_buffer = True
                        except Exception:
                            # If all else fails, check if ARDUINO_READY exists as bytes
                            if b"ARDUINO_READY" in data:
                                print("✅ Arduino ready message found as bytes in buffer!")
                                ready_found_in_buffer = True
                    
                    # CRITICAL SAFETY CHECK: Check for Arduino safety halt
                    if "CRITICAL_SAFETY_ERROR" in buffer_text or "ARDUINO_SAFETY_HALT" in buffer_text or "LOAD-LOCK ARM IS NOT IN HOME POSITION" in buffer_text:
                        self.serial_port.close()
                        self.serial_port = None
                        raise Exception("ARDUINO_SAFETY_HALT: LOAD-LOCK ARM IS NOT IN HOME POSITION!!")                # If found in buffer, clear it and we're ready to go
                if ready_found_in_buffer:
                    # Clear remaining buffer to avoid confusion with debug messages
                    try:
                        self.serial_port.reset_input_buffer()
                    except Exception:
                        pass
                else:
                    # If not in buffer, wait for new message
                    print("⏳ Waiting for new ARDUINO_READY message (5s timeout)...")
                    ready_timeout = time.time() + 5  # 5 second timeout
                    ready_received = False
                    
                    while time.time() < ready_timeout:
                        if self.serial_port.in_waiting > 0:
                            try:
                                response = self.serial_port.readline().decode().strip()
                                print(f"📨 Received: '{response}'")
                                
                                # CRITICAL SAFETY CHECK: Check for Arduino safety halt
                                if "CRITICAL_SAFETY_ERROR" in response or "ARDUINO_SAFETY_HALT" in response or "LOAD-LOCK ARM IS NOT IN HOME POSITION" in response:
                                    self.serial_port.close()
                                    self.serial_port = None
                                    raise Exception("ARDUINO_SAFETY_HALT: LOAD-LOCK ARM IS NOT IN HOME POSITION!!")
                                
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
                
                # Connection is ready - set up the communication system
                self.is_connected = True
                self.start_communication_thread()
                # Cache the successful port for future soft reconnections
                self.save_port_to_cache(port)
                
                # Restore previous Arduino state if available
                self.restore_arduino_state()
                
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
    
    def disconnect(self, force_disconnect: bool = False):
        """
        Safely disconnect from Arduino.
        
        Args:
            force_disconnect: If True, always disconnect regardless of keep_alive setting
        """
        with self.connection_lock:
            if not self.is_connected:
                return
            
            # Check if we should keep connection alive
            if self.keep_connection_alive and not force_disconnect:
                print("🔄 Keeping Arduino connection alive for next GUI session...")
                self.save_connection_state()
                # Don't actually disconnect - just stop the communication thread
                self.is_connected = False  # Mark as disconnected from GUI perspective
                self.stop_thread = True
                if self.communication_thread and self.communication_thread.is_alive():
                    self.communication_thread.join(timeout=2)
                print("✅ Connection preserved - Arduino remains active")
                return
            
            print("🔌 Fully disconnecting from Arduino...")
            self.is_connected = False
            self.stop_thread = True
            
            # Turn off all relays before disconnecting
            self.send_command_direct("ALL_OFF")
            
            if self.communication_thread and self.communication_thread.is_alive():
                self.communication_thread.join(timeout=2)
                
            if self.serial_port:
                self.serial_port.close()
                self.serial_port = None
                
            # Clear queues and connection state
            self.clear_queues()
            self.clear_connection_state()
            
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
        last_heartbeat = time.time()
        while not self.stop_thread and self.is_connected:
            try:
                # Process outgoing commands if any
                try:
                    # Expect tuple (cmd_id, command) or just command (legacy support)
                    item = self.command_queue.get(timeout=0.1)
                    
                    if isinstance(item, tuple) and len(item) == 2:
                        cmd_id, command = item
                        response = self.send_command_direct(command)
                        self.response_queue.put((cmd_id, response))
                    else:
                        # Legacy support for direct string commands (if any)
                        command = item
                        response = self.send_command_direct(command)
                        self.response_queue.put(response)
                        
                except queue.Empty:
                    pass

                # Periodic heartbeat to indicate comm thread is alive (low-volume)
                if time.time() - last_heartbeat >= 600.0:
                    try:
                        print("[comm thread] heartbeat: connected", flush=True)
                    except Exception:
                        pass
                    last_heartbeat = time.time()

            except Exception as e:
                print(f"Communication thread error: {e}", flush=True)
                self.is_connected = False
                break
                
    def send_command_direct(self, command: str, timeout: float = 2.0) -> str:
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
            command_bytes = f"{command}\n".encode()
            self.serial_port.write(command_bytes)
            self.serial_port.flush()

            # Determine expected prefix for this command
            expected_prefix = None
            if command.startswith("GET_DIGITAL_INPUTS"):
                expected_prefix = "DIGITAL_INPUTS:"
            elif command.startswith("GET_ANALOG_INPUTS"):
                expected_prefix = "ANALOG_INPUTS:"
            elif command == "STATUS":
                expected_prefix = "STATUS:"
            elif command.startswith("RELAY_") or command in ("ALL_OFF",):
                # Relay commands return OK or ERROR
                expected_prefix = "OK"

            # Read lines until we find the expected response or time out
            start = time.time()
            while time.time() - start < timeout:
                if self.serial_port.in_waiting > 0:
                    try:
                        line = self.serial_port.readline().decode().strip()
                    except UnicodeDecodeError:
                        # skip non-text
                        continue

                    if not line:
                        continue

                    # If we expect an exact 'OK'
                    if expected_prefix == "OK":
                        if line == "OK":
                            return line
                        if line == "ERROR":
                            return line
                        # otherwise unsolicited, keep waiting
                        continue

                    # If we expect a prefixed response, match it
                    if expected_prefix is None:
                        # No specific expectation: return the first non-empty line
                        return line
                    else:
                        if line.startswith(expected_prefix):
                            return line
                        # ignore unsolicited lines (e.g., DEBUG)
                        continue

                time.sleep(0.01)

            return "TIMEOUT"

        except (serial.SerialException, OSError) as e:
            print(f"Serial communication error: {e}", flush=True)
            self.is_connected = False
            return "ERROR"
            
    def send_command(self, command: str, timeout: float = 2.0) -> str:
        """
        Send command via queue system (thread-safe) with ID matching.
        
        Args:
            command: Command string to send
            timeout: Maximum time to wait for response
            
        Returns:
            Response string from Arduino
        """
        if not self.is_connected:
            return "ERROR"

        # Generate unique ID for this command
        cmd_id = str(uuid.uuid4())

        # Clear old responses (optional, but good for hygiene)
        # self.clear_response_queue() 

        # Send command with ID
        self.command_queue.put((cmd_id, command))

        # Wait for matching response
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Wait for ANY response
                item = self.response_queue.get(timeout=timeout - (time.time() - start_time))
                
                # Check if it matches our ID
                if isinstance(item, tuple) and len(item) == 2:
                    resp_id, response = item
                    if resp_id == cmd_id:
                        return response
                    else:
                        # Not our response (stale or from another thread), ignore or put back?
                        # For now, just ignore stale responses
                        continue
                else:
                    # Legacy response (string), assume it's ours if we are single threaded?
                    # Or just return it
                    return item
                    
            except queue.Empty:
                return "TIMEOUT"
                
        return "TIMEOUT"

    def set_relay(self, relay_number: int, state: bool, suppress_logging: bool = False) -> bool:
        """
        Set specific relay ON or OFF.
        
        Args:
            relay_number: Relay number (1-21)
            state: True for ON, False for OFF
        Returns:
            True if command successful, False otherwise
        """
        if not (1 <= relay_number <= self.NUM_RELAYS):
            return False
        command = f"RELAY_{relay_number}_{'ON' if state else 'OFF'}"
        # DEBUG: Log all relay operations to track unauthorized changes
        if not suppress_logging:
            print(f"🔧 RELAY OPERATION: Relay {relay_number} -> {'ON' if state else 'OFF'} (Command: {command})")
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
            relay_number: Relay number (1-21)
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
        # DEBUG: Log emergency shutdown operations
        print(f"🚨 EMERGENCY: ALL_RELAYS_OFF command being sent!")
        response = self.send_command("ALL_OFF")
        if response == "OK":
            self.relay_states = [False] * self.NUM_RELAYS
            print(f"🚨 EMERGENCY: ALL_RELAYS_OFF completed successfully")
            return True
        print(f"🚨 EMERGENCY: ALL_RELAYS_OFF failed - response: {response}")
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
        command = "GET_DIGITAL_INPUTS"
        response = self.send_command(command)
        if response.startswith("DIGITAL_INPUTS:"):
            try:
                states_str = response.split(":", 1)[1]
                states = [s == "1" for s in states_str.split(",")]
                return states
            except (ValueError, IndexError) as e:
                print(f"❌ Error parsing digital inputs: {e}")
                return None
        elif response == "ERROR":
            print("❌ Arduino firmware doesn't support GET_DIGITAL_INPUTS command")
            return None
        elif response == "TIMEOUT":
            print("⏱️ Timeout waiting for digital inputs response")
            return None
        else:
            print(f"⚠️ Unexpected response for digital inputs: '{response}'")
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
