"""Safety system integration for gas flow control.

This module provides integration between the gas flow control system
and the sputter control safety system, ensuring safe gas operations.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

# Support both package and script execution
try:
    from ..safety import SafetyController  # type: ignore
    from .controller import GasFlowController, MFCReading  # type: ignore
    from .recipes import GasRecipe  # type: ignore
except ImportError:
    try:
        from safety import SafetyController  # type: ignore
        from controller import GasFlowController, MFCReading  # type: ignore
        from recipes import GasRecipe  # type: ignore
    except ImportError:
        SafetyController = None
        GasFlowController = None
        MFCReading = None
        GasRecipe = None


@dataclass
class GasFlowLimits:
    """Gas flow safety limits."""
    max_individual_flow: float  # Maximum flow for any single channel
    max_total_flow: float  # Maximum total flow across all channels
    max_oxygen_percentage: float  # Maximum O2 percentage of total flow
    min_pressure_for_flow: float  # Minimum chamber pressure to allow gas flow
    emergency_stop_flow: float  # Flow rate threshold for emergency stop


class GasFlowSafetyIntegration:
    """Integrates gas flow control with the safety system."""
    
    def __init__(self, gas_controller: Optional[GasFlowController] = None, 
                 safety_controller: Optional[SafetyController] = None):
        """Initialize safety integration.
        
        Args:
            gas_controller: Gas flow controller instance
            safety_controller: Safety controller instance
        """
        self.gas_controller = gas_controller
        self.safety_controller = safety_controller
        self.logger = logging.getLogger(__name__)
        
        # Safety limits (configurable)
        self.limits = GasFlowLimits(
            max_individual_flow=200.0,  # sccm
            max_total_flow=500.0,  # sccm
            max_oxygen_percentage=50.0,  # %
            min_pressure_for_flow=1e-3,  # Torr
            emergency_stop_flow=1000.0  # sccm
        )
        
        # Safety state tracking
        self._safety_violations: List[str] = []
        self._emergency_stop_triggered = False
        self._gas_flow_enabled = True
        
        # Interlock conditions
        self._required_interlocks = [
            'door_closed',  # Chamber door must be closed
            'water_flow_ok',  # Cooling water must be flowing
        ]
        
        # Initialize safety checks if controllers are available
        if self.gas_controller and self.safety_controller:
            self._setup_safety_monitoring()
    
    def set_controllers(self, gas_controller: GasFlowController, 
                       safety_controller: SafetyController) -> None:
        """Set the controller instances after initialization."""
        self.gas_controller = gas_controller
        self.safety_controller = safety_controller
        self._setup_safety_monitoring()
    
    def _setup_safety_monitoring(self) -> None:
        """Set up safety monitoring callbacks."""
        if self.gas_controller:
            # Add callbacks to gas controller
            self.gas_controller.add_status_callback(self._check_gas_flow_safety)
            self.gas_controller.add_error_callback(self._handle_gas_error)
        
        self.logger.info("Gas flow safety monitoring enabled")
    
    def configure_limits(self, limits: Dict[str, float]) -> None:
        """Configure safety limits.
        
        Args:
            limits: Dictionary of limit_name -> value
        """
        for key, value in limits.items():
            if hasattr(self.limits, key):
                setattr(self.limits, key, value)
                self.logger.info(f"Updated safety limit {key} = {value}")
    
    def check_flow_request_safety(self, channel: str, flow_rate: float, 
                                 current_flows: Optional[Dict[str, float]] = None) -> Tuple[bool, str]:
        """Check if a flow rate request is safe.
        
        Args:
            channel: Channel name (e.g., "Ar", "O2", "N2")
            flow_rate: Requested flow rate
            current_flows: Current flow rates for all channels
            
        Returns:
            Tuple of (is_safe, reason_if_not_safe)
        """
        if not self._gas_flow_enabled:
            return False, "Gas flow is currently disabled by safety system"
        
        if self._emergency_stop_triggered:
            return False, "Emergency stop is active"
        
        # Check individual flow limit
        if flow_rate > self.limits.max_individual_flow:
            return False, f"Flow rate {flow_rate} exceeds maximum individual limit {self.limits.max_individual_flow}"
        
        # Check total flow limit
        if current_flows is None and self.gas_controller:
            current_flows = {}
            readings = self.gas_controller.get_all_readings()
            for ch, reading in readings.items():
                current_flows[ch] = reading.mass_flow if reading else 0.0
        
        if current_flows:
            total_flow = sum(current_flows.values()) - current_flows.get(channel, 0.0) + flow_rate
            if total_flow > self.limits.max_total_flow:
                return False, f"Total flow {total_flow:.1f} would exceed maximum limit {self.limits.max_total_flow}"
        
        # Check oxygen percentage (safety concern for combustion)
        if channel.upper() in ['O2', 'OXYGEN'] and current_flows:
            total_flow_without_o2 = sum(flow for ch, flow in current_flows.items() if ch.upper() not in ['O2', 'OXYGEN'])
            total_flow_with_new_o2 = total_flow_without_o2 + flow_rate
            
            if total_flow_with_new_o2 > 0:
                o2_percentage = (flow_rate / total_flow_with_new_o2) * 100
                if o2_percentage > self.limits.max_oxygen_percentage:
                    return False, f"O2 percentage {o2_percentage:.1f}% exceeds maximum {self.limits.max_oxygen_percentage}%"
        
        # Check chamber conditions
        safety_result = self._check_chamber_conditions()
        if not safety_result[0]:
            return safety_result
        
        # Check interlocks
        interlock_result = self._check_interlocks()
        if not interlock_result[0]:
            return interlock_result
        
        return True, "Flow request approved"
    
    def check_recipe_safety(self, recipe: GasRecipe) -> Tuple[bool, List[str]]:
        """Check if a gas recipe is safe to execute.
        
        Args:
            recipe: Gas recipe to check
            
        Returns:
            Tuple of (is_safe, list_of_issues)
        """
        if not self.gas_controller:
            return False, ["Gas controller not available"]
        
        issues = []
        
        if not self._gas_flow_enabled:
            issues.append("Gas flow is currently disabled by safety system")
        
        if self._emergency_stop_triggered:
            issues.append("Emergency stop is active")
        
        # Check each step
        for i, step in enumerate(recipe.steps):
            step_total_flow = sum(step.flows.values())
            
            # Check total flow for this step
            if step_total_flow > self.limits.max_total_flow:
                issues.append(f"Step {i+1} '{step.name}': Total flow {step_total_flow:.1f} exceeds limit {self.limits.max_total_flow}")
            
            # Check individual flows
            for channel, flow in step.flows.items():
                if flow > self.limits.max_individual_flow:
                    issues.append(f"Step {i+1} '{step.name}': {channel} flow {flow:.1f} exceeds individual limit {self.limits.max_individual_flow}")
            
            # Check oxygen percentage
            o2_flow = 0.0
            for channel, flow in step.flows.items():
                if channel.upper() in ['O2', 'OXYGEN']:
                    o2_flow += flow
            
            if o2_flow > 0 and step_total_flow > 0:
                o2_percentage = (o2_flow / step_total_flow) * 100
                if o2_percentage > self.limits.max_oxygen_percentage:
                    issues.append(f"Step {i+1} '{step.name}': O2 percentage {o2_percentage:.1f}% exceeds limit {self.limits.max_oxygen_percentage}%")
        
        # Check chamber conditions
        chamber_result = self._check_chamber_conditions()
        if not chamber_result[0]:
            issues.append(f"Chamber conditions: {chamber_result[1]}")
        
        # Check interlocks
        interlock_result = self._check_interlocks()
        if not interlock_result[0]:
            issues.append(f"Interlock failure: {interlock_result[1]}")
        
        return len(issues) == 0, issues
    
    def _check_chamber_conditions(self) -> Tuple[bool, str]:
        """Check chamber conditions for safe gas flow."""
        if not self.safety_controller:
            return True, "Safety controller not available"
        
        # This would be implemented based on your specific safety system
        # For now, just check if we can get pressure readings
        try:
            # Get analog inputs (pressure readings)
            # This is a placeholder - adjust based on your actual safety system API
            analog_readings = getattr(self.safety_controller, 'get_analog_readings', lambda: [0.0, 0.0, 0.0, 0.0])()
            
            # Assume chamber pressure is on analog input 1 (adjust as needed)
            if len(analog_readings) > 1:
                chamber_pressure = analog_readings[1]  # Torr
                if chamber_pressure > self.limits.min_pressure_for_flow:
                    return False, f"Chamber pressure {chamber_pressure:.2e} Torr too high for gas flow (limit: {self.limits.min_pressure_for_flow:.2e})"
            
            return True, "Chamber conditions OK"
            
        except Exception as e:
            self.logger.error(f"Error checking chamber conditions: {e}")
            return False, f"Cannot verify chamber conditions: {e}"
    
    def _check_interlocks(self) -> Tuple[bool, str]:
        """Check safety interlocks."""
        if not self.safety_controller:
            return True, "Safety controller not available"
        
        try:
            # This would be implemented based on your actual safety system API
            # For now, assume digital inputs represent interlocks
            digital_inputs = getattr(self.safety_controller, 'get_digital_inputs', lambda: [True, True, True, True])()
            
            # Check required interlocks (adjust indices based on your system)
            if len(digital_inputs) >= 3:
                door_closed = digital_inputs[0]  # Door interlock
                water_flow_ok = digital_inputs[1]  # Water flow interlock
                
                if not door_closed:
                    return False, "Chamber door is not closed"
                
                if not water_flow_ok:
                    return False, "Cooling water flow is not OK"
            
            return True, "All interlocks OK"
            
        except Exception as e:
            self.logger.error(f"Error checking interlocks: {e}")
            return False, f"Cannot verify interlocks: {e}"
    
    def _check_gas_flow_safety(self, status: Dict[str, Any]) -> None:
        """Callback to check gas flow safety based on current status."""
        if not status:
            return
        
        try:
            # Clear previous violations
            self._safety_violations.clear()
            
            # Check total flow rate
            total_flow = 0.0
            o2_flow = 0.0
            
            for channel_name, channel_status in status.items():
                if isinstance(channel_status, dict) and 'current_reading' in channel_status:
                    reading_data = channel_status['current_reading']
                    if reading_data:
                        mass_flow = reading_data.get('mass_flow', 0.0)
                        total_flow += mass_flow
                        
                        # Track oxygen flow
                        if channel_name.upper() in ['O2', 'OXYGEN']:
                            o2_flow += mass_flow
                        
                        # Check individual flow limits
                        if mass_flow > self.limits.max_individual_flow:
                            self._safety_violations.append(f"{channel_name} flow {mass_flow:.1f} exceeds individual limit")
            
            # Check total flow limit
            if total_flow > self.limits.max_total_flow:
                self._safety_violations.append(f"Total flow {total_flow:.1f} exceeds limit {self.limits.max_total_flow}")
            
            # Check emergency stop threshold
            if total_flow > self.limits.emergency_stop_flow:
                self._trigger_emergency_gas_stop(f"Total flow {total_flow:.1f} exceeds emergency threshold")
            
            # Check oxygen percentage
            if total_flow > 0 and o2_flow > 0:
                o2_percentage = (o2_flow / total_flow) * 100
                if o2_percentage > self.limits.max_oxygen_percentage:
                    self._safety_violations.append(f"O2 percentage {o2_percentage:.1f}% exceeds limit")
            
            # Log violations
            if self._safety_violations:
                for violation in self._safety_violations:
                    self.logger.warning(f"Gas flow safety violation: {violation}")
            
        except Exception as e:
            self.logger.error(f"Error in gas flow safety check: {e}")
    
    def _handle_gas_error(self, channel: str, error: Exception) -> None:
        """Handle gas flow errors."""
        self.logger.error(f"Gas flow error on {channel}: {error}")
        
        # For critical errors, disable gas flow
        critical_errors = ["connection", "timeout", "communication"]
        error_str = str(error).lower()
        
        if any(critical in error_str for critical in critical_errors):
            self.logger.critical(f"Critical gas flow error detected: {error}")
            self._trigger_emergency_gas_stop(f"Critical error on {channel}: {error}")
    
    def _trigger_emergency_gas_stop(self, reason: str) -> None:
        """Trigger emergency gas flow stop."""
        if self._emergency_stop_triggered:
            return  # Already triggered
        
        self.logger.critical(f"EMERGENCY GAS STOP TRIGGERED: {reason}")
        self._emergency_stop_triggered = True
        self._gas_flow_enabled = False
        
        # Stop all gas flows immediately
        if self.gas_controller:
            try:
                self.gas_controller.stop_all_flows()
                self.logger.info("All gas flows stopped due to emergency")
            except Exception as e:
                self.logger.error(f"Failed to stop gas flows during emergency: {e}")
        
        # Notify safety system
        if self.safety_controller:
            try:
                # This would be implemented based on your safety system API
                # For example: self.safety_controller.trigger_emergency_stop("Gas flow emergency")
                pass
            except Exception as e:
                self.logger.error(f"Failed to notify safety controller: {e}")
    
    def reset_emergency_stop(self, operator: str = "Unknown") -> bool:
        """Reset emergency stop (requires manual intervention).
        
        Args:
            operator: Name of operator performing reset
            
        Returns:
            bool: True if reset successful
        """
        if not self._emergency_stop_triggered:
            return True
        
        # Check that conditions are safe for reset
        chamber_ok, chamber_msg = self._check_chamber_conditions()
        interlocks_ok, interlock_msg = self._check_interlocks()
        
        if not chamber_ok:
            self.logger.error(f"Cannot reset emergency stop: {chamber_msg}")
            return False
        
        if not interlocks_ok:
            self.logger.error(f"Cannot reset emergency stop: {interlock_msg}")
            return False
        
        # Reset emergency state
        self._emergency_stop_triggered = False
        self._gas_flow_enabled = True
        self._safety_violations.clear()
        
        self.logger.critical(f"Emergency gas stop RESET by operator: {operator}")
        return True
    
    def enable_gas_flow(self, enabled: bool, operator: str = "System") -> None:
        """Enable or disable gas flow.
        
        Args:
            enabled: Whether to enable gas flow
            operator: Who is making the change
        """
        if enabled and self._emergency_stop_triggered:
            self.logger.error("Cannot enable gas flow: emergency stop is active")
            return
        
        self._gas_flow_enabled = enabled
        action = "ENABLED" if enabled else "DISABLED"
        self.logger.warning(f"Gas flow {action} by {operator}")
        
        # If disabling, stop all current flows
        if not enabled and self.gas_controller:
            self.gas_controller.stop_all_flows()
    
    def is_gas_flow_enabled(self) -> bool:
        """Check if gas flow is enabled."""
        return self._gas_flow_enabled and not self._emergency_stop_triggered
    
    def get_safety_status(self) -> Dict[str, Any]:
        """Get comprehensive safety status."""
        chamber_ok, chamber_msg = self._check_chamber_conditions()
        interlocks_ok, interlock_msg = self._check_interlocks()
        
        return {
            'gas_flow_enabled': self._gas_flow_enabled,
            'emergency_stop_active': self._emergency_stop_triggered,
            'safety_violations': self._safety_violations.copy(),
            'chamber_conditions': {
                'ok': chamber_ok,
                'message': chamber_msg
            },
            'interlocks': {
                'ok': interlocks_ok,
                'message': interlock_msg
            },
            'limits': {
                'max_individual_flow': self.limits.max_individual_flow,
                'max_total_flow': self.limits.max_total_flow,
                'max_oxygen_percentage': self.limits.max_oxygen_percentage,
                'min_pressure_for_flow': self.limits.min_pressure_for_flow,
                'emergency_stop_flow': self.limits.emergency_stop_flow
            }
        }
    
    def get_flow_approval(self, channel: str, flow_rate: float) -> Tuple[bool, str]:
        """Get approval for a specific flow rate change.
        
        This is the main method that should be called before any flow changes.
        
        Args:
            channel: Channel name
            flow_rate: Requested flow rate
            
        Returns:
            Tuple of (approved, reason)
        """
        # Get current flows
        current_flows = {}
        if self.gas_controller:
            readings = self.gas_controller.get_all_readings()
            for ch, reading in readings.items():
                current_flows[ch] = reading.mass_flow if reading else 0.0
        
        return self.check_flow_request_safety(channel, flow_rate, current_flows)