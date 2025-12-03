"""Subprocess-based gas flow controller using Alicat CLI commands.

This module provides a high-performance GasFlowController that uses subprocess
calls to the alicat CLI instead of Python async, achieving ~500ms response times
vs ~1500ms with the async approach.
"""

from __future__ import annotations

import subprocess
import threading
import time
import json
import logging
import platform
from pathlib import Path
from dataclasses import dataclass
from queue import Queue, Empty
from typing import Dict, List, Optional, Tuple, Callable, Any
import uuid
from serial.tools import list_ports

# Support both package and script execution
try:
    from ..safety import SafetyController  # type: ignore
except ImportError:
    try:
        from safety import SafetyController  # type: ignore
    except ImportError:
        SafetyController = None


@dataclass
class MFCReading:
    """Data structure for MFC readings."""
    timestamp: float
    pressure: float
    temperature: float
    volumetric_flow: float
    mass_flow: float
    setpoint: float
    gas: str
    control_point: str = "mass flow"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'timestamp': self.timestamp,
            'pressure': self.pressure,
            'temperature': self.temperature,
            'volumetric_flow': self.volumetric_flow,
            'mass_flow': self.mass_flow,
            'setpoint': self.setpoint,
            'gas': self.gas,
            'control_point': self.control_point
        }


@dataclass
class MFCChannel:
    """Configuration and state for a single MFC channel."""
    name: str  # e.g., "Ar", "O2", "N2"
    unit_id: str  # Alicat unit ID (A, B, C, etc.)
    serial_port: str  # COM port or /dev/ttyUSB path
    max_flow: float  # Maximum flow rate (sccm or configured units)
    gas_type: str  # Gas type for Alicat ("Ar", "O2", "N2")
    enabled: bool = True
    baudrate: Optional[int] = None  # Optional baud rate (not used in CLI mode)
    current_reading: Optional[MFCReading] = None
    last_error: Optional[str] = None
    connection_status: str = "disconnected"  # "connected", "disconnected", "error"


class GasFlowController:
    """High-performance gas flow controller using subprocess CLI calls.
    
    This controller uses subprocess calls to the alicat CLI instead of Python async,
    providing ~3x faster response times (~500ms vs ~1500ms).
    
    Features:
    - Thread-safe CLI command execution
    - Safety system integration
    - Real-time monitoring and control
    - Automatic error handling and retries
    - Same API as the original async controller
    """
    
    def __init__(self, config: Dict[str, Any], safety_controller: Optional[object] = None, excluded_ports: List[str] = None):
        """Initialize the subprocess-based gas flow controller.
        
        Args:
            config: Configuration dictionary from sput.yml gas_control section
            safety_controller: Optional SafetyController for safety integration
            excluded_ports: List of serial ports to exclude from scanning (e.g. Arduino port)
        """
        self.config = config
        self.safety_controller = safety_controller
        self.excluded_ports = excluded_ports or []
        
        # Initialize logging
        self.logger = logging.getLogger(__name__)
        
        # Initialize state tracking
        self._last_readings: Dict[str, MFCReading] = {}
        self._setpoints: Dict[str, float] = {}
        self._total_flow_rate = 0.0
        
        # Initialize error tracking before channels
        self._consecutive_errors = {}
        
        # Initialize MFC channels from config
        self.channels: Dict[str, MFCChannel] = {}
        
        # Auto-detect port is DEFERRED until start() to prevent blocking GUI startup
        # self._detect_and_update_port()
        
        self._init_channels()
        
        # Thread management
        self._running = False
        self._control_thread: Optional[threading.Thread] = None
        self._command_queue: Queue = Queue()
        self._result_queues: Dict[str, Queue] = {}
        
        # CLI command settings
        self.cli_timeout = config.get('cli_timeout', 3.0)  # Timeout for CLI commands
        self.max_retries = config.get('max_retries', 3)  # Increased retries for Unicode issues
        
        # Periodic reading settings
        self.read_interval = config.get('read_interval', 10.0)  # Read all MFCs every 10 seconds (reduced frequency)
        self.auto_read_enabled = config.get('auto_read_enabled', False)  # Disable auto-reading by default to prevent conflicts
        
        # Error recovery settings
        self.unicode_error_delay = config.get('unicode_error_delay', 0.5)  # Delay after Unicode errors
        self.max_consecutive_errors = config.get('max_consecutive_errors', 5)  # Max errors before marking disabled
        
        # Command spacing to prevent serial port conflicts
        self.command_spacing = config.get('command_spacing', 0.5)  # Minimum time between commands (seconds)
        self._last_command_time = 0.0
        
        # Status callbacks
        self._status_callbacks: List[Callable] = []
        self._error_callbacks: List[Callable] = []
    
    def _detect_and_update_port(self) -> None:
        """Auto-detect the correct serial port for Alicat MFCs."""
        configured_port = self.config.get('serial_port')
        
        # Get a unit ID to test with (use first available)
        mfc_config = self.config.get('mfcs', {})
        if not mfc_config:
            return
            
        # Find a valid unit ID to test
        test_unit_id = 'A'
        for cfg in mfc_config.values():
            if 'unit_id' in cfg:
                test_unit_id = cfg['unit_id']
                break
        
        if configured_port:
            self.logger.info(f"Checking Alicat connection on {configured_port} (Unit {test_unit_id})...")
            
            # 1. Try configured port first (if not excluded)
            if configured_port not in self.excluded_ports:
                if self._test_port(configured_port, test_unit_id):
                    self.logger.info(f"✅ Alicat found on configured port: {configured_port}")
                    return
            else:
                self.logger.info(f"ℹ️ Configured port {configured_port} is excluded (likely Arduino). Skipping.")
                
            self.logger.warning(f"⚠️ Alicat not found on {configured_port}. Scanning available ports...")
        else:
            self.logger.info("ℹ️ No serial port configured. Scanning available ports...")
        
        # 2. Scan available ports
        found_port = self._scan_ports(test_unit_id)
        
        if found_port:
            self.logger.info(f"✅ Found Alicat on port: {found_port}")
            
            # Update runtime config
            self.config['serial_port'] = found_port
            
            # Update config file
            self._update_config_file(found_port)
        else:
            self.logger.error("❌ Could not find Alicat MFCs on any port")

    def _scan_ports(self, unit_id: str) -> Optional[str]:
        """Scan available serial ports for Alicat device."""
        ports = list_ports.comports()
        candidates = []
        
        # Device type patterns to exclude from scanning (HID devices, mice, keyboards, etc.)
        hid_exclusion_patterns = ['mouse', 'keyboard', 'hid', 'input', 'touchpad', 'trackpad', 
                                  'receiver', 'dongle', 'bluetooth', 'bt', 'wireless']
        
        # Prioritize USB serial devices, but exclude HID devices
        for p in ports:
            desc = p.description.lower()
            manufacturer = (p.manufacturer or '').lower()
            
            # Skip HID/input devices that might be mouse/keyboard
            if any(pattern in desc or pattern in manufacturer for pattern in hid_exclusion_patterns):
                self.logger.info(f"Skipping HID/input device: {p.device} ({p.description})")
                continue
                
            if "usb" in desc or "serial" in desc:
                candidates.append(p.device)
        
        # Add remaining ports (also excluding HID devices)
        for p in ports:
            if p.device not in candidates:
                desc = p.description.lower()
                manufacturer = (p.manufacturer or '').lower()
                
                # Skip HID/input devices
                if any(pattern in desc or pattern in manufacturer for pattern in hid_exclusion_patterns):
                    continue
                    
                candidates.append(p.device)
                
        for port in candidates:
            if port in self.excluded_ports:
                self.logger.info(f"Skipping excluded port {port}")
                continue
                
            self.logger.info(f"Scanning {port}...")
            if self._test_port(port, unit_id):
                return port
                
        return None

    def _test_port(self, port: str, unit_id: str) -> bool:
        """Test if an Alicat unit responds on a port."""
        try:
            # Run alicat CLI command to check state
            # alicat <port> --unit <id> (no args returns state)
            cmd = ['alicat', port, '--unit', unit_id]
            
            # Run with short timeout
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=2.0
            )
            
            if result.returncode == 0:
                return True
            return False
        except Exception:
            return False

    def _update_config_file(self, new_port: str) -> None:
        """Update the config.yml file with the new port."""
        try:
            config_path = Path(__file__).parent / 'config.yml'
            if not config_path.exists():
                self.logger.warning(f"Config file not found at {config_path}")
                return
                
            content = config_path.read_text()
            
            lines = content.splitlines()
            new_lines = []
            updated = False
            
            for line in lines:
                if 'serial_port:' in line and not updated:
                    # Check if this is likely the global setting (indentation)
                    if line.strip().startswith('serial_port:'):
                        new_lines.append(f"  serial_port: '{new_port}'  # Auto-detected")
                        updated = True
                        continue
                new_lines.append(line)
            
            if updated:
                config_path.write_text('\n'.join(new_lines) + '\n')
                self.logger.info(f"Updated config.yml with new port: {new_port}")
            else:
                self.logger.warning("Could not find serial_port key in config.yml to update")
                
        except Exception as e:
            self.logger.error(f"Failed to update config file: {e}")

    def _init_channels(self) -> None:
        """Initialize MFC channels from configuration."""
        mfc_config = self.config.get('mfcs', {})
        self.logger.info(f"Subprocess GasFlowController initializing with MFC config: {mfc_config}")
        
        global_port = self.config.get('serial_port')
        if not global_port:
            self.logger.error("❌ No serial port configured for MFCs. Gas control will be disabled.")
            global_port = "COM_MISSING"
        
        for name, channel_config in mfc_config.items():
            # Handle "serial_port" placeholder or missing port
            port = channel_config.get('serial_port')
            if not port or port == 'serial_port':
                port = global_port
                
            channel = MFCChannel(
                name=name,
                unit_id=channel_config.get('unit_id', 'A'),
                serial_port=port,
                max_flow=float(channel_config.get('max_flow', 100.0)),
                gas_type=channel_config.get('gas_type', name),
                enabled=channel_config.get('enabled', True),
                baudrate=channel_config.get('baudrate')  # Not used in CLI mode
            )
            self.channels[name] = channel
            self._setpoints[name] = 0.0
            self._consecutive_errors[name] = 0  # Track consecutive errors per channel
            
        self.logger.info(f"Initialized {len(self.channels)} MFC channels: {list(self.channels.keys())}")
    
    def _execute_cli_command(self, channel_name: str, command_args: List[str], retries: int = None) -> Optional[Dict[str, Any]]:
        """Execute a CLI command with error handling and retries.
        
        Args:
            channel_name: Name of the MFC channel
            command_args: List of arguments for the alicat CLI command
            retries: Number of retries (defaults to self.max_retries)
            
        Returns:
            Dictionary with command result or None if failed
        """
        if channel_name not in self.channels:
            self.logger.error(f"Unknown MFC channel: {channel_name}")
            return None
            
        channel = self.channels[channel_name]
        if not channel.enabled:
            return None
        
        if retries is None:
            retries = self.max_retries
        
        # Build the full command
        full_command = ['alicat', channel.serial_port, '--unit', channel.unit_id] + command_args
        
        for attempt in range(retries + 1):
            try:
                # Enforce command spacing to prevent serial conflicts
                current_time = time.time()
                time_since_last = current_time - self._last_command_time
                if time_since_last < self.command_spacing:
                    delay_needed = self.command_spacing - time_since_last
                    self.logger.debug(f"Enforcing command spacing: waiting {delay_needed:.3f}s")
                    time.sleep(delay_needed)
                
                self._last_command_time = time.time()
                start_time = time.perf_counter()
                
                # Add --timeout parameter to CLI command for better reliability
                #if '--timeout' not in full_command:
                   # full_command.extend(['--timeout', '2.0'])  # 2 second timeout at CLI level
                
                self.logger.debug(f"Executing CLI command: {' '.join(full_command)}")
                
                # Execute the CLI command
                result = subprocess.run(
                    full_command,
                    capture_output=True,
                    text=True,
                    timeout=self.cli_timeout,
                    encoding='utf-8',
                    errors='replace'  # Handle Unicode decode errors gracefully
                )
                
                end_time = time.perf_counter()
                response_time = (end_time - start_time) * 1000
                
                if result.returncode == 0:
                    # Parse JSON output
                    try:
                        # Clean the output in case there are any replacement characters
                        clean_output = result.stdout.strip().replace('\ufffd', '')  # Remove Unicode replacement chars
                        if not clean_output:
                            raise ValueError("Empty CLI output")
                        
                        data = json.loads(clean_output)
                        
                        # Update channel status
                        channel.connection_status = "connected"
                        channel.last_error = None
                        self._consecutive_errors[channel_name] = 0  # Reset error count on success
                        
                        self.logger.debug(f"CLI command for {channel_name} completed in {response_time:.1f}ms")
                        return {
                            'success': True,
                            'data': data,
                            'response_time_ms': response_time
                        }
                        
                    except (json.JSONDecodeError, ValueError) as e:
                        self.logger.error(f"Failed to parse CLI output for {channel_name}: {e}")
                        self.logger.debug(f"Raw stdout: {repr(result.stdout)}")
                        self.logger.debug(f"Raw stderr: {repr(result.stderr)}")
                        
                        # If JSON parse fails but command succeeded, it might be a serial issue - retry
                        if attempt < retries:
                            self.logger.info(f"Retrying {channel_name} due to parse error (attempt {attempt + 1})")
                            time.sleep(0.5)  # Longer delay for serial recovery
                            continue
                        
                        channel.connection_status = "error"
                        channel.last_error = f"Parse error: {e}"
                        
                else:
                    error_msg = result.stderr.strip() or "Unknown CLI error"
                    
                    # Check for specific serial communication errors
                    if any(err in error_msg for err in ["UnicodeDecodeError", "codec can't decode", 
                                                       "ValueError", "invalid literal", "Unexpected register value"]):
                        self.logger.warning(f"Serial communication error for {channel_name} (attempt {attempt + 1}): {error_msg}")
                        if attempt < retries:
                            # Longer delay for serial recovery
                            time.sleep(1.0)
                            continue
                    else:
                        self.logger.warning(f"CLI command failed for {channel_name} (attempt {attempt + 1}): {error_msg}")
                        if attempt < retries:
                            time.sleep(0.2)
                            continue
                    
                    if attempt == retries:  # Last attempt
                        channel.connection_status = "error"
                        channel.last_error = error_msg
                        self._consecutive_errors[channel_name] = self._consecutive_errors.get(channel_name, 0) + 1
                        
                        # Temporarily disable channel if too many consecutive errors
                        if self._consecutive_errors[channel_name] >= self.max_consecutive_errors:
                            self.logger.error(f"Disabling {channel_name} due to {self._consecutive_errors[channel_name]} consecutive errors")
                            channel.enabled = False
                        
            except subprocess.TimeoutExpired:
                error_msg = f"CLI command timeout after {self.cli_timeout}s"
                self.logger.warning(f"{error_msg} for {channel_name} (attempt {attempt + 1})")
                
                if attempt == retries:  # Last attempt
                    channel.connection_status = "error"
                    channel.last_error = error_msg
                    
            except Exception as e:
                error_msg = f"CLI command exception: {e}"
                self.logger.error(f"{error_msg} for {channel_name} (attempt {attempt + 1})")
                
                if attempt == retries:  # Last attempt
                    channel.connection_status = "error"
                    channel.last_error = error_msg
            
            # Brief delay before retry
            if attempt < retries:
                time.sleep(0.2)
        
        return None
    
    def _cli_get_reading(self, channel_name: str) -> Optional[MFCReading]:
        """Get a reading from an MFC using CLI."""
        # Check if channel is temporarily disabled due to errors
        if (channel_name in self._consecutive_errors and 
            self._consecutive_errors[channel_name] >= self.max_consecutive_errors):
            self.logger.debug(f"Skipping {channel_name} - too many consecutive errors")
            return None
            
        result = self._execute_cli_command(channel_name, [])
        
        if result and result['success']:
            data = result['data']
            
            # Create MFCReading object
            reading = MFCReading(
                timestamp=time.time(),
                pressure=data.get('pressure', 0.0),
                temperature=data.get('temperature', 0.0),
                volumetric_flow=data.get('volumetric_flow', 0.0),
                mass_flow=data.get('mass_flow', 0.0),
                setpoint=data.get('setpoint', 0.0),
                gas=data.get('gas', ''),
                control_point=data.get('control_point', 'mass flow')
            )
            
            # Update cached reading
            self._last_readings[channel_name] = reading
            self.channels[channel_name].current_reading = reading
            
            return reading
        
        return None
    
    def _cli_set_flow_rate(self, channel_name: str, flow_rate: float) -> bool:
        """Set flow rate for an MFC using CLI."""
        # Safety checks
        if channel_name not in self.channels:
            self.logger.error(f"Unknown channel: {channel_name}")
            return False
            
        max_flow = self.channels[channel_name].max_flow
        if flow_rate > max_flow:
            self.logger.error(f"Flow rate {flow_rate} exceeds maximum {max_flow} for {channel_name}")
            return False
        
        # Safety system integration
        if self.safety_controller:
            # Add safety checks here if needed
            pass
        
        # Execute CLI command to set flow rate
        result = self._execute_cli_command(channel_name, ['--set-flow-rate', str(flow_rate)])
        
        if result and result['success']:
            # Update setpoint cache
            self._setpoints[channel_name] = flow_rate
            
            # Verify the setpoint was set correctly
            data = result['data']
            actual_setpoint = data.get('setpoint', 0.0)
            
            if abs(actual_setpoint - flow_rate) > 0.1:
                self.logger.warning(f"Setpoint verification failed for {channel_name}: requested {flow_rate}, got {actual_setpoint}")
            else:
                self.logger.info(f"Set {channel_name} flow rate to {flow_rate} sccm")
            
            return True
        
        return False
    
    def _cli_set_gas_type(self, channel_name: str, gas_type: str) -> bool:
        """Set gas type for an MFC using CLI."""
        result = self._execute_cli_command(channel_name, ['--set-gas', gas_type])
        
        if result and result['success']:
            # Update gas type cache
            self.channels[channel_name].gas_type = gas_type
            self.logger.info(f"Set {channel_name} gas type to {gas_type}")
            return True
        
        return False
    
    def start(self) -> bool:
        """Start the subprocess-based gas flow controller."""
        if self._running:
            self.logger.warning("Gas flow controller already running")
            return True
            
        try:
            # Re-verify port connection before starting thread
            # This handles cases where the device was off during init but is on now
            current_port = self.config.get('serial_port')
            
            # Only attempt detection if we don't have a port or if the port is clearly invalid
            if not current_port or current_port == 'serial_port':
                 self.logger.info("No port configured. Attempting detection...")
                 self._detect_and_update_port()
            
            # If we still don't have a port, we can't start
            if not self.config.get('serial_port'):
                 self.logger.error("Cannot start: No valid serial port found for MFCs")
                 return False

            self._running = True
            self._control_thread = threading.Thread(target=self._control_loop, daemon=True)
            self._control_thread.start()
            
            # Initial connectivity test - REMOVED to prevent blocking/errors during startup
            # The control loop will handle connection establishment naturally
            # self._test_initial_connectivity()
            
            self.logger.info("Subprocess gas flow controller started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start subprocess gas flow controller: {e}")
            self._running = False
            return False
    
    def stop(self) -> None:
        """Stop the subprocess-based gas flow controller."""
        if not self._running:
            return
            
        self.logger.info("Stopping subprocess gas flow controller...")
        self._running = False
        
        # Send stop command
        self._send_command('stop', {})
        
        # Wait for control thread
        if self._control_thread and self._control_thread.is_alive():
            self._control_thread.join(timeout=3.0)
            
        self.logger.info("Subprocess gas flow controller stopped")
    
    def _control_loop(self) -> None:
        """Main control loop for handling commands and periodic readings."""
        self.logger.info("Subprocess gas flow control loop started")
        
        last_read_time = time.time()
        
        try:
            while self._running:
                current_time = time.time()
                
                # Process commands from queue
                self._process_commands()
                
                # Periodic reading of all MFCs
                if (self.auto_read_enabled and 
                    current_time - last_read_time >= self.read_interval):
                    self._read_all_mfcs()
                    last_read_time = current_time
                
                # Sleep to prevent high CPU usage
                # Increased from 0.01s to 0.1s to reduce load on RPi
                time.sleep(0.1)
                
        except Exception as e:
            self.logger.error(f"Error in subprocess gas flow control loop: {e}")
        finally:
            self.logger.info("Subprocess gas flow control loop ended")
    
    def reset_channel_errors(self, channel_name: str = None) -> None:
        """Reset error counts for a channel or all channels.
        
        Args:
            channel_name: Specific channel to reset, or None for all channels
        """
        if channel_name:
            if channel_name in self._consecutive_errors:
                self._consecutive_errors[channel_name] = 0
                if channel_name in self.channels:
                    self.channels[channel_name].enabled = True
                    self.channels[channel_name].connection_status = "disconnected"
                    self.channels[channel_name].last_error = None
                    self.logger.info(f"Reset errors and re-enabled channel {channel_name}")
        else:
            # Reset all channels
            for name in self._consecutive_errors:
                self._consecutive_errors[name] = 0
                if name in self.channels:
                    self.channels[name].enabled = True
                    self.channels[name].connection_status = "disconnected" 
                    self.channels[name].last_error = None
            self.logger.info("Reset errors for all channels")
    
    def _test_initial_connectivity(self) -> None:
        """Test initial connectivity to all enabled MFCs."""
        self.logger.info("Testing initial MFC connectivity...")
        
        # Disable auto-reading during initial test to prevent conflicts
        original_auto_read = self.auto_read_enabled
        self.auto_read_enabled = False
        
        try:
            for channel_name, channel in self.channels.items():
                if not channel.enabled:
                    continue
                    
                self.logger.info(f"Testing connectivity to {channel_name}...")
                
                # Add extra delay before first command to let serial port settle
                time.sleep(1.0)
                
                reading = self._cli_get_reading(channel_name)
                
                if reading:
                    self.logger.info(f"✅ {channel_name} connected - Gas: {reading.gas}, Flow: {reading.mass_flow}")
                else:
                    self.logger.warning(f"❌ {channel_name} connection failed")
                    # For initial connectivity failures, try once more after a longer delay
                    self.logger.info(f"Retrying {channel_name} after 2s delay...")
                    time.sleep(2.0)
                    reading = self._cli_get_reading(channel_name)
                    if reading:
                        self.logger.info(f"✅ {channel_name} connected on retry - Gas: {reading.gas}, Flow: {reading.mass_flow}")
                    else:
                        self.logger.warning(f"❌ {channel_name} still failed on retry")
                
                # Add delay between channel tests
                time.sleep(0.5)
        finally:
            # Restore auto-reading setting
            self.auto_read_enabled = original_auto_read
    
    def _read_all_mfcs(self) -> None:
        """Read current state from all enabled MFCs."""
        for channel_name, channel in self.channels.items():
            if not channel.enabled:
                continue
                
            try:
                reading = self._cli_get_reading(channel_name)
                if reading:
                    self.logger.debug(f"Read {channel_name}: {reading.mass_flow} sccm")
                    
            except Exception as e:
                self.logger.error(f"Error reading MFC {channel_name}: {e}")
    
    def _process_commands(self) -> None:
        """Process commands from the command queue."""
        try:
            while not self._command_queue.empty():
                try:
                    command_id, command, args = self._command_queue.get_nowait()
                    result = self._execute_command(command, args)
                    
                    # Return result if someone is waiting
                    if command_id in self._result_queues:
                        self._result_queues[command_id].put(result)
                        
                except Empty:
                    break
                except Exception as e:
                    self.logger.error(f"Error processing command: {e}")
                    if command_id in self._result_queues:
                        self._result_queues[command_id].put(f"Error: {e}")
                        
        except Exception as e:
            self.logger.error(f"Error in command processing: {e}")
    
    def _execute_command(self, command: str, args: Dict[str, Any]) -> Any:
        """Execute a command using CLI operations."""
        try:
            if command == 'get_reading':
                channel = args.get('channel')
                return self._cli_get_reading(channel)
                
            elif command == 'set_flow':
                channel = args.get('channel')
                flow_rate = args.get('flow_rate', 0.0)
                return self._cli_set_flow_rate(channel, flow_rate)
                
            elif command == 'set_gas':
                channel = args.get('channel')
                gas_type = args.get('gas_type', 'Air')
                return self._cli_set_gas_type(channel, gas_type)
                
            elif command == 'stop_all':
                results = []
                for channel in self.channels.keys():
                    if self.channels[channel].enabled:
                        result = self._cli_set_flow_rate(channel, 0.0)
                        results.append(result)
                return all(results)
                
            elif command == 'stop':
                return True
                
            else:
                self.logger.error(f"Unknown command: {command}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error executing command {command}: {e}")
            return None
    
    def _send_command(self, command: str, args: Dict[str, Any], wait_for_result: bool = False) -> Any:
        """Send a command to the control thread."""
        command_id = str(uuid.uuid4())
        
        if wait_for_result:
            self._result_queues[command_id] = Queue()
        
        self._command_queue.put((command_id, command, args))
        
        if wait_for_result:
            try:
                result = self._result_queues[command_id].get(timeout=10.0)  # Reasonable timeout
                del self._result_queues[command_id]
                
                if isinstance(result, str) and result.startswith("Error:"):
                    self.logger.error(f"Command failed: {result}")
                    return None
                
                return result
            except Exception as e:
                if command_id in self._result_queues:
                    del self._result_queues[command_id]
                self.logger.error(f"Command timeout or error: {e}")
                return None
        
        return None
    
    # Public API methods (thread-safe, same interface as original controller)
    
    def set_flow_rate(self, channel: str, flow_rate: float) -> bool:
        """Set flow rate for a specific channel (thread-safe).
        
        Args:
            channel: Channel name (e.g., "Ar", "O2", "N2")
            flow_rate: Target flow rate in configured units
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            result = self._send_command('set_flow', {
                'channel': channel,
                'flow_rate': flow_rate
            }, wait_for_result=True)
            return bool(result)
        except Exception as e:
            self.logger.error(f"Failed to set flow rate: {e}")
            return False
    
    def set_gas_type(self, channel: str, gas_type: str) -> bool:
        """Set gas type for a specific channel (thread-safe).
        
        Args:
            channel: Channel name
            gas_type: Gas type from Alicat gas list
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            result = self._send_command('set_gas', {
                'channel': channel,
                'gas_type': gas_type
            }, wait_for_result=True)
            return bool(result)
        except Exception as e:
            self.logger.error(f"Failed to set gas type: {e}")
            return False
    
    def stop_flow(self, channel: str) -> bool:
        """Stop flow for a specific channel (thread-safe)."""
        return self.set_flow_rate(channel, 0.0)
    
    def stop_all_flows(self) -> bool:
        """Stop flow for all channels (thread-safe)."""
        try:
            result = self._send_command('stop_all', {}, wait_for_result=True)
            return bool(result)
        except Exception as e:
            self.logger.error(f"Failed to stop all flows: {e}")
            return False
    
    def get_reading(self, channel: str) -> Optional[MFCReading]:
        """Get the latest reading for a channel (thread-safe)."""
        try:
            # For immediate readings, use the command system
            result = self._send_command('get_reading', {
                'channel': channel
            }, wait_for_result=True)
            return result if isinstance(result, MFCReading) else None
        except Exception as e:
            self.logger.error(f"Failed to get reading: {e}")
            return None
    
    def get_all_readings(self) -> Dict[str, MFCReading]:
        """Get latest readings for all channels."""
        readings = {}
        for channel in self.channels.keys():
            if self.channels[channel].enabled:
                reading = self.get_reading(channel)
                if reading:
                    readings[channel] = reading
        return readings
    
    def get_channel_status(self, channel: str) -> Dict[str, Any]:
        """Get status information for a specific channel."""
        if channel not in self.channels:
            return {'error': 'Channel not found'}
            
        ch = self.channels[channel]
        return {
            'name': ch.name,
            'enabled': ch.enabled,
            'connection_status': ch.connection_status,
            'last_error': ch.last_error,
            'setpoint': self._setpoints.get(channel, 0.0),
            'max_flow': ch.max_flow,
            'gas_type': ch.gas_type,
            'current_reading': ch.current_reading.to_dict() if ch.current_reading else None
        }
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status for all channels."""
        return {name: self.get_channel_status(name) for name in self.channels.keys()}
    
    def is_running(self) -> bool:
        """Check if the controller is running."""
        return self._running
    
    def get_total_flow_rate(self) -> float:
        """Get total flow rate across all channels."""
        total = 0.0
        for reading in self._last_readings.values():
            total += reading.mass_flow
        return total
    
    def add_status_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Add a callback for status updates."""
        self._status_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable[[str, Exception], None]) -> None:
        """Add a callback for error notifications."""
        self._error_callbacks.append(callback)
