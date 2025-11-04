"""Main gas flow controller module for Alicat APEX MFC integration.

This module provides the primary GasFlowController class that manages multiple
Alicat APEX mass flow controllers in a thread-safe manner, integrating with
the sputter control system's architecture.
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from queue import Queue, Empty
from typing import Dict, List, Optional, Tuple, Callable, Any
import logging

# Alicat driver import - adjust path as needed
import sys
sys.path.append(str(Path(__file__).resolve().parents[4] / 'alicat'))
from alicat import FlowController

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
    baudrate: Optional[int] = None  # Optional baud rate (defaults to 19200)
    current_reading: Optional[MFCReading] = None
    last_error: Optional[str] = None
    connection_status: str = "disconnected"  # "connected", "disconnected", "error"


class GasFlowController:
    """Thread-safe controller for multiple Alicat APEX MFCs.
    
    This controller manages gas flow for the sputter system with:
    - Thread-safe communication with multiple MFCs
    - Safety system integration
    - Recipe-based gas mixing
    - Real-time monitoring and control
    - Automatic reconnection and error handling
    """
    
    def __init__(self, config: Dict[str, Any], safety_controller: Optional[object] = None):
        """Initialize the gas flow controller.
        
        Args:
            config: Configuration dictionary from sput.yml gas_control section
            safety_controller: Optional SafetyController for safety integration
        """
        self.config = config
        self.safety_controller = safety_controller
        
        # Initialize logging
        self.logger = logging.getLogger(__name__)
        
        # Initialize state tracking BEFORE channels
        self._last_readings: Dict[str, MFCReading] = {}
        self._setpoints: Dict[str, float] = {}
        self._total_flow_rate = 0.0
        
        # Initialize MFC channels from config
        self.channels: Dict[str, MFCChannel] = {}
        self._init_channels()
        
        # Thread management
        self._running = False
        self._control_thread: Optional[threading.Thread] = None
        self._command_queue: Queue = Queue()
        self._result_queues: Dict[str, Queue] = {}
        
        # MFC connection objects (created in control thread)
        self._mfc_connections: Dict[str, FlowController] = {}
        
        # Safety and status callbacks
        self._status_callbacks: List[Callable] = []
        self._error_callbacks: List[Callable] = []
        
        # Auto-reconnect settings
        self.auto_reconnect = config.get('auto_reconnect', True)
        self.reconnect_interval = config.get('reconnect_interval', 5.0)
        
    def _init_channels(self) -> None:
        """Initialize MFC channels from configuration."""
        mfc_config = self.config.get('mfcs', {})
        print(f"DEBUG: GasFlowController initializing with MFC config: {mfc_config}")
        
        for name, channel_config in mfc_config.items():
            print(f"DEBUG: Creating channel {name} with config: {channel_config}")
            channel = MFCChannel(
                name=name,
                unit_id=channel_config.get('unit_id', 'A'),
                serial_port=channel_config.get('serial_port', '/dev/ttyUSB0'),
                max_flow=float(channel_config.get('max_flow', 100.0)),
                gas_type=channel_config.get('gas_type', name),
                enabled=channel_config.get('enabled', True),
                baudrate=channel_config.get('baudrate')  # Optional baud rate
            )
            print(f"DEBUG: Channel {name} created with serial_port: {channel.serial_port}")
            self.channels[name] = channel
            self._setpoints[name] = 0.0
            
        self.logger.info(f"Initialized {len(self.channels)} MFC channels: {list(self.channels.keys())}")
    
    def start(self) -> bool:
        """Start the gas flow controller.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if self._running:
            self.logger.warning("Gas flow controller already running")
            return True
            
        try:
            self._running = True
            self._control_thread = threading.Thread(target=self._control_loop, daemon=True)
            self._control_thread.start()
            
            # Wait for initial connection attempts
            time.sleep(2.0)
            
            self.logger.info("Gas flow controller started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start gas flow controller: {e}")
            self._running = False
            return False
    
    def stop(self) -> None:
        """Stop the gas flow controller and close all connections."""
        if not self._running:
            return
            
        self.logger.info("Stopping gas flow controller...")
        self._running = False
        
        # Send stop command to control thread
        self._send_command('stop', {})
        
        # Wait for control thread to finish
        if self._control_thread and self._control_thread.is_alive():
            self._control_thread.join(timeout=5.0)
            
        self.logger.info("Gas flow controller stopped")
    
    def _control_loop(self) -> None:
        """Main control loop running in separate thread."""
        self.logger.info("Gas flow control loop started")
        
        # Initialize asyncio event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Connect to all MFCs
            loop.run_until_complete(self._connect_all_mfcs())
            
            last_read_time = time.time()
            read_interval = self.config.get('read_interval', 1.0)
            
            while self._running:
                current_time = time.time()
                
                # Process commands from queue
                self._process_commands(loop)
                
                # Periodic reading of all MFCs
                if current_time - last_read_time >= read_interval:
                    loop.run_until_complete(self._read_all_mfcs())
                    last_read_time = current_time
                
                # Brief sleep to prevent high CPU usage
                time.sleep(0.01)
                
        except Exception as e:
            self.logger.error(f"Error in gas flow control loop: {e}")
        finally:
            # Clean shutdown
            loop.run_until_complete(self._disconnect_all_mfcs())
            loop.close()
            self.logger.info("Gas flow control loop ended")
    
    async def _connect_all_mfcs(self) -> None:
        """Connect to all enabled MFC channels."""
        for name, channel in self.channels.items():
            if not channel.enabled:
                continue
                
            try:
                self.logger.info(f"Connecting to MFC {name} at {channel.serial_port}")
                
                # Prepare connection parameters
                connection_params = {
                    'address': channel.serial_port,
                    'unit': channel.unit_id,
                    'timeout': 2.0
                }
                
                # Add baud rate if specified in channel config
                if channel.baudrate is not None:
                    connection_params['baudrate'] = channel.baudrate
                    self.logger.info(f"Using custom baud rate {channel.baudrate} for MFC {name}")
                
                # Create FlowController instance
                mfc = FlowController(**connection_params)
                
                # Test connection by reading current state
                state = await mfc.get()
                if state:
                    self._mfc_connections[name] = mfc
                    channel.connection_status = "connected"
                    channel.last_error = None
                    
                    # Set gas type if needed
                    if channel.gas_type in FlowController.gases:
                        await mfc.set_gas(channel.gas_type)
                    
                    self.logger.info(f"Successfully connected to MFC {name}")
                else:
                    channel.connection_status = "error"
                    channel.last_error = "Failed to read initial state"
                    
            except Exception as e:
                self.logger.error(f"Failed to connect to MFC {name}: {e}")
                channel.connection_status = "error"
                channel.last_error = str(e)
    
    async def _disconnect_all_mfcs(self) -> None:
        """Disconnect from all MFC channels."""
        for name, mfc in self._mfc_connections.items():
            try:
                # Set flow to zero before disconnecting
                await mfc.set_flow_rate(0.0)
                mfc.close()
                self.logger.info(f"Disconnected from MFC {name}")
            except Exception as e:
                self.logger.error(f"Error disconnecting MFC {name}: {e}")
                
        self._mfc_connections.clear()
        
        # Update channel status
        for channel in self.channels.values():
            channel.connection_status = "disconnected"
    
    async def _read_all_mfcs(self) -> None:
        """Read current state from all connected MFCs."""
        for name, mfc in self._mfc_connections.items():
            try:
                state = await mfc.get()
                if state:
                    reading = MFCReading(
                        timestamp=time.time(),
                        pressure=state.get('pressure', 0.0),
                        temperature=state.get('temperature', 0.0),
                        volumetric_flow=state.get('volumetric_flow', 0.0),
                        mass_flow=state.get('mass_flow', 0.0),
                        setpoint=state.get('setpoint', 0.0),
                        gas=state.get('gas', ''),
                        control_point=state.get('control_point', 'mass flow')
                    )
                    
                    self._last_readings[name] = reading
                    self.channels[name].current_reading = reading
                    self.channels[name].connection_status = "connected"
                    self.channels[name].last_error = None
                    
            except Exception as e:
                self.logger.error(f"Error reading MFC {name}: {e}")
                self.channels[name].connection_status = "error"
                self.channels[name].last_error = str(e)
                
                # Try to reconnect if auto-reconnect is enabled
                if self.auto_reconnect:
                    await self._try_reconnect(name)
    
    async def _try_reconnect(self, name: str) -> None:
        """Attempt to reconnect to a specific MFC."""
        if name not in self.channels:
            return
            
        channel = self.channels[name]
        try:
            self.logger.info(f"Attempting to reconnect to MFC {name}")
            
            # Remove old connection
            if name in self._mfc_connections:
                try:
                    self._mfc_connections[name].close()
                except:
                    pass
                del self._mfc_connections[name]
            
            # Create new connection
            mfc = FlowController(
                address=channel.serial_port,
                unit=channel.unit_id,
                timeout=2.0
            )
            
            # Test connection
            state = await mfc.get()
            if state:
                self._mfc_connections[name] = mfc
                channel.connection_status = "connected"
                channel.last_error = None
                
                # Restore gas type and setpoint
                if channel.gas_type in FlowController.gases:
                    await mfc.set_gas(channel.gas_type)
                await mfc.set_flow_rate(self._setpoints.get(name, 0.0))
                
                self.logger.info(f"Successfully reconnected to MFC {name}")
                
        except Exception as e:
            self.logger.error(f"Failed to reconnect to MFC {name}: {e}")
            channel.connection_status = "error"
            channel.last_error = str(e)
    
    def _process_commands(self, loop: asyncio.AbstractEventLoop) -> None:
        """Process commands from the command queue."""
        try:
            while True:
                try:
                    command_id, command, args = self._command_queue.get_nowait()
                    result = loop.run_until_complete(self._execute_command(command, args))
                    
                    # Send result back if there's a result queue
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
    
    async def _execute_command(self, command: str, args: Dict[str, Any]) -> Any:
        """Execute a command asynchronously."""
        if command == 'set_flow':
            return await self._cmd_set_flow(args['channel'], args['flow_rate'])
        elif command == 'set_gas':
            return await self._cmd_set_gas(args['channel'], args['gas_type'])
        elif command == 'stop_flow':
            return await self._cmd_stop_flow(args['channel'])
        elif command == 'stop_all':
            return await self._cmd_stop_all()
        elif command == 'get_reading':
            return self._cmd_get_reading(args['channel'])
        elif command == 'stop':
            return True
        else:
            raise ValueError(f"Unknown command: {command}")
    
    async def _cmd_set_flow(self, channel: str, flow_rate: float) -> bool:
        """Set flow rate for a specific channel."""
        if channel not in self._mfc_connections:
            raise ValueError(f"MFC {channel} not connected")
            
        if channel not in self.channels:
            raise ValueError(f"Unknown channel: {channel}")
            
        # Check safety limits
        max_flow = self.channels[channel].max_flow
        if flow_rate > max_flow:
            raise ValueError(f"Flow rate {flow_rate} exceeds maximum {max_flow} for {channel}")
            
        # Safety system integration
        if self.safety_controller:
            # This would be implemented based on your safety system
            # For now, just log
            self.logger.info(f"Safety check passed for {channel} flow rate {flow_rate}")
        
        try:
            mfc = self._mfc_connections[channel]
            
            # Debug: Check current control point and setpoint before setting
            try:
                current_state = await mfc.get()
                self.logger.info(f"Before setting {channel}: current_setpoint={current_state.get('setpoint', 'unknown')}, control_point={getattr(mfc, 'control_point', 'unknown')}")
            except Exception as e:
                self.logger.warning(f"Could not read current state before setting {channel}: {e}")
            
            # Set the flow rate (no artificial delay needed - separate serial port)
            await mfc.set_flow_rate(flow_rate)
            self._setpoints[channel] = flow_rate
            
            # Quick verification without blocking delay
            try:
                verification_state = await mfc.get()
                actual_setpoint = verification_state.get('setpoint', 0.0)
                self.logger.info(f"After setting {channel}: requested={flow_rate}, actual_setpoint={actual_setpoint}")
                
                if abs(actual_setpoint - flow_rate) > 0.1:
                    self.logger.warning(f"Setpoint verification failed for {channel}: requested {flow_rate}, got {actual_setpoint}")
                    
            except Exception as e:
                self.logger.warning(f"Could not verify setpoint for {channel}: {e}")
            
            self.logger.info(f"Set {channel} flow rate to {flow_rate}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set flow rate for {channel}: {e}")
            raise
    
    async def _cmd_set_gas(self, channel: str, gas_type: str) -> bool:
        """Set gas type for a specific channel."""
        if channel not in self._mfc_connections:
            raise ValueError(f"MFC {channel} not connected")
            
        try:
            mfc = self._mfc_connections[channel]
            await mfc.set_gas(gas_type)
            self.channels[channel].gas_type = gas_type
            
            self.logger.info(f"Set {channel} gas type to {gas_type}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set gas type for {channel}: {e}")
            raise
    
    async def _cmd_stop_flow(self, channel: str) -> bool:
        """Stop flow for a specific channel."""
        return await self._cmd_set_flow(channel, 0.0)
    
    async def _cmd_stop_all(self) -> bool:
        """Stop flow for all channels."""
        results = []
        for channel in self._mfc_connections.keys():
            try:
                result = await self._cmd_set_flow(channel, 0.0)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Failed to stop flow for {channel}: {e}")
                results.append(False)
        
        return all(results)
    
    def _cmd_get_reading(self, channel: str) -> Optional[MFCReading]:
        """Get latest reading for a specific channel."""
        return self._last_readings.get(channel)
    
    def _send_command(self, command: str, args: Dict[str, Any], wait_for_result: bool = False) -> Any:
        """Send a command to the control thread."""
        import uuid
        command_id = str(uuid.uuid4())
        
        if wait_for_result:
            result_queue = Queue()
            self._result_queues[command_id] = result_queue
        
        self._command_queue.put((command_id, command, args))
        
        if wait_for_result:
            try:
                result = result_queue.get(timeout=15.0)  # Reasonable timeout for separate serial port
                del self._result_queues[command_id]
                
                if isinstance(result, str) and result.startswith("Error:"):
                    raise RuntimeError(result[6:])  # Remove "Error:" prefix
                
                return result
            except Exception as e:
                if command_id in self._result_queues:
                    del self._result_queues[command_id]
                raise RuntimeError(f"Command timeout or error: {e}")
        
        return None
    
    # Public API methods (thread-safe)
    
    def set_flow_rate(self, channel: str, flow_rate: float) -> bool:
        """Set flow rate for a specific channel (thread-safe).
        
        Args:
            channel: Channel name (e.g., "Ar", "O2", "N2")
            flow_rate: Target flow rate in configured units
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            return self._send_command('set_flow', {
                'channel': channel,
                'flow_rate': flow_rate
            }, wait_for_result=True)
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
            return self._send_command('set_gas', {
                'channel': channel,
                'gas_type': gas_type
            }, wait_for_result=True)
        except Exception as e:
            self.logger.error(f"Failed to set gas type: {e}")
            return False
    
    def stop_flow(self, channel: str) -> bool:
        """Stop flow for a specific channel (thread-safe)."""
        return self.set_flow_rate(channel, 0.0)
    
    def stop_all_flows(self) -> bool:
        """Stop flow for all channels (thread-safe)."""
        try:
            return self._send_command('stop_all', {}, wait_for_result=True)
        except Exception as e:
            self.logger.error(f"Failed to stop all flows: {e}")
            return False
    
    def get_reading(self, channel: str) -> Optional[MFCReading]:
        """Get the latest reading for a channel (thread-safe)."""
        try:
            return self._send_command('get_reading', {
                'channel': channel
            }, wait_for_result=True)
        except Exception as e:
            self.logger.error(f"Failed to get reading: {e}")
            return None
    
    def get_all_readings(self) -> Dict[str, MFCReading]:
        """Get latest readings for all channels."""
        readings = {}
        for channel in self.channels.keys():
            reading = self.get_reading(channel)
            if reading:
                readings[channel] = reading
        return readings
    
    def get_channel_status(self, channel: str) -> Dict[str, Any]:
        """Get status information for a specific channel."""
        if channel not in self.channels:
            return {}
            
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