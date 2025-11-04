#!/usr/bin/env python3
"""
Optimized GasFlowController using CLI-style connections for better performance.

This version uses fresh connections per operation (like the CLI) instead of 
persistent connections, reducing the response time from 1500ms to ~500ms.
"""

from __future__ import annotations
import asyncio
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from queue import Queue, Empty
from typing import Dict, List, Optional, Tuple, Callable, Any

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


class OptimizedGasFlowController:
    """High-performance gas flow controller using CLI-style connections.
    
    This controller uses fresh connections per operation instead of persistent
    connections, reducing response times from 1500ms to ~500ms per operation.
    
    Key optimizations:
    - Fresh connection per operation (like CLI tool)
    - Reduced timeout values for faster failure detection  
    - Simplified error handling
    - Thread-safe operation queuing
    """
    
    def __init__(self, config: Dict[str, Any], safety_controller: Optional[object] = None):
        """Initialize the optimized gas flow controller.
        
        Args:
            config: Configuration dictionary from sput.yml gas_control section
            safety_controller: Optional SafetyController for safety integration
        """
        self.config = config
        self.safety_controller = safety_controller
        
        # Initialize logging
        self.logger = logging.getLogger(__name__)
        
        # Initialize state tracking
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
        
        # Optimized settings
        self.default_timeout = config.get('default_timeout', 1.0)  # Reduced from 2.0
        self.max_retries = config.get('max_retries', 2)  # Reduced from 3
        
        # Status callbacks
        self._status_callbacks: List[Callable] = []
        self._error_callbacks: List[Callable] = []
        
    def _init_channels(self) -> None:
        """Initialize MFC channels from configuration."""
        mfc_config = self.config.get('mfcs', {})
        
        for name, channel_config in mfc_config.items():
            channel = MFCChannel(
                name=name,
                unit_id=channel_config.get('unit_id', 'A'),
                serial_port=channel_config.get('serial_port', '/dev/ttyUSB0'),
                max_flow=float(channel_config.get('max_flow', 100.0)),
                gas_type=channel_config.get('gas_type', name),
                enabled=channel_config.get('enabled', True),
                baudrate=channel_config.get('baudrate')
            )
            self.channels[name] = channel
            self._setpoints[name] = 0.0
            
        self.logger.info(f"Initialized {len(self.channels)} MFC channels: {list(self.channels.keys())}")
    
    async def _fast_mfc_operation(self, channel_name: str, operation: str, **kwargs) -> Optional[Any]:
        """Perform a fast MFC operation using CLI-style connection.
        
        Args:
            channel_name: Name of the MFC channel
            operation: Operation to perform ('get', 'set_flow', 'set_gas')
            **kwargs: Additional arguments for the operation
            
        Returns:
            Result of the operation or None if failed
        """
        if channel_name not in self.channels:
            self.logger.error(f"Unknown MFC channel: {channel_name}")
            return None
            
        channel = self.channels[channel_name]
        if not channel.enabled:
            return None
        
        # Determine timeout - use shorter timeout for faster operations
        timeout = kwargs.get('timeout', self.default_timeout)
        
        try:
            # Use CLI-style fresh connection (like fast_test.py)
            connection_params = {
                'address': channel.serial_port,
                'unit': channel.unit_id,
                'timeout': timeout
            }
            
            if channel.baudrate:
                connection_params['baudrate'] = channel.baudrate
            
            start_time = time.perf_counter()
            
            async with FlowController(**connection_params) as fc:
                if operation == 'get':
                    result = await fc.get()
                    
                    # Update reading cache
                    if result:
                        reading = MFCReading(
                            timestamp=time.time(),
                            pressure=result.get('pressure', 0.0),
                            temperature=result.get('temperature', 0.0),
                            volumetric_flow=result.get('volumetric_flow', 0.0),
                            mass_flow=result.get('mass_flow', 0.0),
                            setpoint=result.get('setpoint', 0.0),
                            gas=result.get('gas', ''),
                            control_point=result.get('control_point', 'mass flow')
                        )
                        self._last_readings[channel_name] = reading
                        channel.current_reading = reading
                        channel.connection_status = "connected"
                        channel.last_error = None
                    
                    return result
                    
                elif operation == 'set_flow':
                    flow_rate = kwargs.get('flow_rate', 0.0)
                    await fc.set_flow_rate(flow_rate)
                    self._setpoints[channel_name] = flow_rate
                    return True
                    
                elif operation == 'set_gas':
                    gas_type = kwargs.get('gas_type', 'Air')
                    await fc.set_gas(gas_type)
                    channel.gas_type = gas_type
                    return True
                    
                else:
                    self.logger.error(f"Unknown operation: {operation}")
                    return None
                    
        except Exception as e:
            end_time = time.perf_counter()
            operation_time = (end_time - start_time) * 1000
            
            self.logger.error(f"MFC {channel_name} {operation} failed after {operation_time:.1f}ms: {e}")
            channel.connection_status = "error"
            channel.last_error = str(e)
            return None
    
    def start(self) -> bool:
        """Start the optimized gas flow controller."""
        if self._running:
            return True
            
        try:
            self._running = True
            self._control_thread = threading.Thread(target=self._control_loop, daemon=True)
            self._control_thread.start()
            
            self.logger.info("Optimized gas flow controller started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start optimized gas flow controller: {e}")
            self._running = False
            return False
    
    def stop(self) -> None:
        """Stop the optimized gas flow controller."""
        if not self._running:
            return
            
        self.logger.info("Stopping optimized gas flow controller...")
        self._running = False
        
        # Send stop command
        self._send_command('stop', {})
        
        # Wait for control thread
        if self._control_thread and self._control_thread.is_alive():
            self._control_thread.join(timeout=3.0)
            
        self.logger.info("Optimized gas flow controller stopped")
    
    def _control_loop(self) -> None:
        """Simplified control loop for handling commands."""
        self.logger.info("Optimized gas flow control loop started")
        
        # Initialize asyncio event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            while self._running:
                # Process commands from queue
                self._process_commands(loop)
                
                # Brief sleep to prevent high CPU usage
                time.sleep(0.01)
                
        except Exception as e:
            self.logger.error(f"Error in optimized gas flow control loop: {e}")
        finally:
            loop.close()
            self.logger.info("Optimized gas flow control loop ended")
    
    def _process_commands(self, loop: asyncio.AbstractEventLoop) -> None:
        """Process commands from the command queue."""
        try:
            while not self._command_queue.empty():
                command_id, command, args = self._command_queue.get_nowait()
                
                # Execute command
                result = loop.run_until_complete(self._execute_command(command, args))
                
                # Return result if someone is waiting
                if command_id in self._result_queues:
                    self._result_queues[command_id].put(result)
                    
        except Empty:
            pass
        except Exception as e:
            self.logger.error(f"Error processing commands: {e}")
    
    async def _execute_command(self, command: str, args: Dict[str, Any]) -> Any:
        """Execute a command using optimized MFC operations."""
        if command == 'get_reading':
            channel = args.get('channel')
            return await self._fast_mfc_operation(channel, 'get')
            
        elif command == 'set_flow':
            channel = args.get('channel')
            flow_rate = args.get('flow_rate', 0.0)
            return await self._fast_mfc_operation(channel, 'set_flow', flow_rate=flow_rate)
            
        elif command == 'set_gas':
            channel = args.get('channel')
            gas_type = args.get('gas_type', 'Air')
            return await self._fast_mfc_operation(channel, 'set_gas', gas_type=gas_type)
            
        elif command == 'stop_all':
            results = []
            for channel in self.channels.keys():
                result = await self._fast_mfc_operation(channel, 'set_flow', flow_rate=0.0)
                results.append(result)
            return all(results)
            
        elif command == 'stop':
            return True
            
        else:
            self.logger.error(f"Unknown command: {command}")
            return None
    
    def _send_command(self, command: str, args: Dict[str, Any], wait_for_result: bool = False) -> Any:
        """Send a command to the control thread."""
        command_id = str(uuid.uuid4())
        
        if wait_for_result:
            self._result_queues[command_id] = Queue()
        
        self._command_queue.put((command_id, command, args))
        
        if wait_for_result:
            try:
                result = self._result_queues[command_id].get(timeout=5.0)
                del self._result_queues[command_id]
                return result
            except Exception:
                if command_id in self._result_queues:
                    del self._result_queues[command_id]
                return None
        
        return None
    
    # Public API methods (optimized for speed)
    
    def get_reading(self, channel: str) -> Optional[MFCReading]:
        """Get latest reading for a channel (fast operation)."""
        try:
            result = self._send_command('get_reading', {'channel': channel}, wait_for_result=True)
            if result:
                return self._last_readings.get(channel)
            return None
        except Exception as e:
            self.logger.error(f"Error getting reading for {channel}: {e}")
            return None
    
    def set_flow_rate(self, channel: str, flow_rate: float) -> bool:
        """Set flow rate for a channel (fast operation)."""
        # Safety checks
        if channel not in self.channels:
            self.logger.error(f"Unknown channel: {channel}")
            return False
            
        max_flow = self.channels[channel].max_flow
        if flow_rate > max_flow:
            self.logger.error(f"Flow rate {flow_rate} exceeds maximum {max_flow} for {channel}")
            return False
        
        # Safety system integration
        if self.safety_controller:
            # Add safety checks here
            pass
        
        try:
            result = self._send_command('set_flow', {
                'channel': channel, 
                'flow_rate': flow_rate
            }, wait_for_result=True)
            return bool(result)
        except Exception as e:
            self.logger.error(f"Error setting flow rate for {channel}: {e}")
            return False
    
    def set_gas_type(self, channel: str, gas_type: str) -> bool:
        """Set gas type for a channel (fast operation)."""
        try:
            result = self._send_command('set_gas', {
                'channel': channel,
                'gas_type': gas_type
            }, wait_for_result=True)
            return bool(result)
        except Exception as e:
            self.logger.error(f"Error setting gas type for {channel}: {e}")
            return False
    
    def stop_all_flows(self) -> bool:
        """Stop all flows (fast operation)."""
        try:
            result = self._send_command('stop_all', {}, wait_for_result=True)
            return bool(result)
        except Exception as e:
            self.logger.error(f"Error stopping all flows: {e}")
            return False
    
    def get_all_readings(self) -> Dict[str, MFCReading]:
        """Get latest readings for all channels."""
        return dict(self._last_readings)
    
    def get_channel_status(self, channel: str) -> Dict[str, Any]:
        """Get status for a channel."""
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
    
    def is_running(self) -> bool:
        """Check if controller is running."""
        return self._running