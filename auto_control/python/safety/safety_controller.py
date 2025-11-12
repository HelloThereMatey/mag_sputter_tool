"""
Safety Controller for Sputter Control System

This module handles all safety condition checking and interlock logic
for the vacuum system operations.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass


@dataclass
class SafetyResult:
    """Result of a safety condition check."""
    allowed: bool
    message: str
    confirmation_required: bool = False
    confirmation_message: str = ""


class SafetyController:
    """Handles safety condition evaluation and interlock logic."""
    
    def __init__(self, safety_config_path: Optional[Path] = None):
        """Initialize the safety controller."""
        if safety_config_path is None:
            # Default to safety_conditions.yml in the same directory as this file
            safety_config_path = Path(__file__).parent / "safety_conditions.yml"
        
        self.config_path = safety_config_path
        self.safety_config = self._load_safety_config()
        
        # Current system state (updated by main application)
        self.analog_inputs: List[float] = [0.0, 0.0, 0.0, 0.0]
        # Digital input states (Door, Water, Rod, Spare)
        self.digital_inputs: List[bool] = [False, False, False, False]
        self.relay_states: Dict[str, bool] = {}
        self.current_mode: str = "Normal"
        
        # Add procedure tracking
        self.current_procedure: Optional[str] = None
        self.system_status: str = "vented"  # Track current system status
        
        # Special flag for sputter procedure gas valve override
        self._sputter_procedure_active: bool = False
        
    def _load_safety_config(self) -> Dict[str, Any]:
        """Load safety configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            print(f"Warning: Safety config file not found: {self.config_path}")
            return {}
        except yaml.YAMLError as e:
            print(f"❌ Error loading safety config: {e}")
            return {}
    
    def update_system_state(self, 
                           analog_inputs: List[float] = None,
                           digital_inputs: List[bool] = None,
                           relay_states: Dict[str, bool] = None,
                           current_mode: str = None,
                           current_procedure: str = None,
                           system_status: str = None):
        """Update the current system state for safety evaluation."""
        if analog_inputs is not None:
            self.analog_inputs = analog_inputs
        if digital_inputs is not None:
            self.digital_inputs = digital_inputs
        if relay_states is not None:
            self.relay_states = relay_states
        if current_mode is not None:
            self.current_mode = current_mode
        if current_procedure is not None:
            self.current_procedure = current_procedure
        if system_status is not None:
            self.system_status = system_status

    def set_procedure_state_override(self, procedure_name: str, target_state: str) -> None:
        """
        Force set system status for procedure execution.
        This bypasses automatic state determination to maintain procedure-specific states.
        """
        print(f"🐛 DEBUG: Setting procedure state override: '{procedure_name}' -> '{target_state}'")
        self.system_status = target_state
        self.current_procedure = procedure_name

    def clear_procedure_state_override(self) -> None:
        """
        Clear procedure state override and allow automatic state determination to resume.
        """
        print(f"🐛 DEBUG: Clearing procedure state override for '{self.current_procedure}'")
        self.current_procedure = None
        # Don't clear system_status here - let automatic determination handle it

    def set_sputter_procedure_active(self, active: bool) -> None:
        """
        Set the sputter procedure active state for gas valve override.
        
        Args:
            active: True when sputter procedure starts, False when it ends
        """
        self._sputter_procedure_active = active
        status = "ACTIVE" if active else "INACTIVE"
        print(f"🌟 Sputter procedure gas valve override: {status}")
        
    def is_sputter_procedure_active(self) -> bool:
        """
        Check if sputter procedure is currently active.
        
        Returns:
            True if sputter procedure is active and gas valves should be allowed
        """
        return self._sputter_procedure_active

    def is_ion_gauge_on(self) -> bool:
        """Return True if ion gauge is considered ON based on analog input and config.

        The threshold is read from safety_config.pressure_thresholds.ion_gauge_on_threshold
        if available; otherwise defaults to 4.4 V.
        """

        threshold = 4.4  # Default threshold (V)
        try:
            if self.safety_config and 'pressure_thresholds' in self.safety_config:
                threshold = float(self.safety_config.get('pressure_thresholds', {}).get('ion_gauge_on_threshold', threshold))

            # ai_volts index 2 corresponds to analog input 3 in UI code
            if len(self.analog_inputs) > 2:
                return float(self.analog_inputs[2]) <= threshold and float(self.analog_inputs[2]) > 0.25
            return False
        except Exception:
            return False
    
    def check_button_safety(self, button_name: str, is_auto_procedure: bool = False) -> SafetyResult:
        """
        Check if a button operation is safe to perform.
        
        Args:
            button_name: Name of the button (e.g., 'btnPumpTurbo')
            is_auto_procedure: Whether this check is for an automatic procedure
            
        Returns:
            SafetyResult with allowed status and message
        """
        # Check if safety config is loaded
        if not self.safety_config:
            return SafetyResult(False, "Safety configuration not loaded")
        
        # Check mode restrictions first (skip for auto procedures in Normal mode)
        if not (is_auto_procedure and self.current_mode == "Normal"):
            mode_check = self._check_mode_restrictions(button_name)
            if not mode_check.allowed:
                return mode_check
        
        # Check emergency conditions
        emergency_check = self._check_emergency_conditions()
        if not emergency_check.allowed:
            return emergency_check
        
        # Check button-specific safety conditions
        button_conditions = self.safety_config.get('button_safety_conditions', {})
        if button_name not in button_conditions:
            # If no specific conditions defined, allow operation
            return SafetyResult(True, "No specific safety conditions defined")
        
        conditions = button_conditions[button_name]
        
        # DEBUG: Special debugging for btnIonGauge
        if button_name == 'btnIonGauge':
            #print(f"DEBUG btnIonGauge: analog_inputs = {self.analog_inputs}")
            #print(f"DEBUG btnIonGauge: ai_volts[1] (chamber pressure) = {self.analog_inputs[1] if len(self.analog_inputs) > 1 else 'N/A'}")
            ion_safe_threshold = self.safety_config.get('pressure_thresholds', {}).get('ion_gauge_max_safe', 0.8)
            print(f"📏 DEBUG btnIonGauge: ion_gauge_max_safe threshold = {ion_safe_threshold}")
            if len(self.analog_inputs) > 1:
                print(f"📏 DEBUG btnIonGauge: {self.analog_inputs[1]} < {ion_safe_threshold} ? {self.analog_inputs[1] < ion_safe_threshold}")
            print(f"📏 DEBUG btnIonGauge: current system_status = '{self.system_status}'")
           #print(f"DEBUG btnIonGauge: current relay_states = {self.relay_states}")
        
        # Check required conditions
        required = conditions.get('required_conditions', [])

        # Support two styles:
        #  - Simple list: all conditions must be True (legacy behavior)
        #  - Grouped list: if any top-level item is a list, interpret as OR over groups;
        #    each group is an AND of its member conditions. This allows "either set A OR set B".
        def _node_true(node) -> bool:
            """Evaluate a node which may be a string (single condition) or a list (AND of subconditions)."""
            if isinstance(node, str):
                return self._evaluate_condition(node)
            if isinstance(node, list):
                # All entries in the list must be true (AND)
                for sub in node:
                    if not _node_true(sub):
                        return False
                return True
            # Unknown node type => treat as False for safety
            return False

        if any(isinstance(item, list) for item in required):
            # OR-over-groups mode: require at least one group (or single condition) to be true
            group_ok = False
            for group in required:
                if _node_true(group):
                    group_ok = True
                    break
            if not group_ok:
                error_msg = conditions.get('error_message', "None of the required condition groups satisfied")
                return SafetyResult(False, error_msg)
        else:
            # Legacy mode: all required conditions must be true
            for condition in required:
                if not _node_true(condition):
                    # Special debugging for btnMainsPower
                    if button_name == 'btnMainsPower':
                        print(f"DEBUG: btnMainsPower safety check failed on condition: {condition}")
                        print(f"DEBUG: Current digital_inputs: {self.digital_inputs}")
                        print(f"DEBUG: Current current_procedure: {self.current_procedure}")
                        print(f"DEBUG: Evaluating condition '{condition}': {self._evaluate_condition(condition, suppress_debug=False)}")
                    
                    # DEBUG: Special debugging for btnIonGauge condition failures
                    if button_name == 'btnIonGauge':
                        print(f"DEBUG btnIonGauge: FAILED condition: '{condition}'")
                        print(f"DEBUG btnIonGauge: Condition evaluation result: {self._evaluate_condition(condition)}")
                        try:
                            # Try to evaluate and show the specific values
                            if 'ai_volts[1]' in condition and 'ion_gauge_max_safe' in condition:
                                chamber_voltage = self.analog_inputs[1] if len(self.analog_inputs) > 1 else 'N/A'
                                threshold = self.safety_config.get('pressure_thresholds', {}).get('ion_gauge_max_safe', 0.8)
                                print(f"DEBUG btnIonGauge: Condition details - chamber voltage: {chamber_voltage}, threshold: {threshold}")
                            elif 'system_status' in condition:
                                print(f"DEBUG btnIonGauge: System status check - current: '{self.system_status}', required: ['high_vacuum', 'mid_vacuum', 'pumping']")
                            elif 'relay_state' in condition:
                                print(f"DEBUG btnIonGauge: Relay state condition details: {condition}")
                        except Exception as e:
                            print(f"DEBUG btnIonGauge: Error getting condition details: {e}")
                    
                    error_msg = conditions.get('error_message', f"Safety condition failed: {condition}")
                    return SafetyResult(False, error_msg)
        
        # Check forbidden conditions
        forbidden = conditions.get('forbidden_conditions', [])
        for condition in forbidden:
            if self._evaluate_condition(condition):
                error_msg = conditions.get('error_message', f"Forbidden condition detected: {condition}")
                return SafetyResult(False, error_msg)
        
        # Check if confirmation is required (skip for auto procedures)
        if not is_auto_procedure:
            confirmation_required = conditions.get('confirmation_required', False)
            confirmation_message = conditions.get('confirmation_message', f"Confirm operation: {button_name}")
            
            # Special case: Skip confirmation for vent valve during vent procedure
            if button_name == 'btnValveVent' and self.current_procedure == 'pushButton_3':
                confirmation_required = False
                confirmation_message = ""
        else:
            confirmation_required = False
            confirmation_message = ""
        
        return SafetyResult(
            True, 
            "Safety conditions satisfied",
            confirmation_required,
            confirmation_message
        )
    
    def _check_mode_restrictions(self, button_name: str) -> SafetyResult:
        """Check if button is allowed in current mode."""
        mode_restrictions = self.safety_config.get('mode_restrictions', {})
        current_mode_config = mode_restrictions.get(self.current_mode, {})
        
        # Check if button is explicitly forbidden
        forbidden_buttons = current_mode_config.get('forbidden_buttons', [])
        if button_name in forbidden_buttons:
            return SafetyResult(False, f"Button {button_name} not allowed in {self.current_mode} mode")
        
        # Check if only specific buttons are allowed (Normal mode)
        allowed_buttons = current_mode_config.get('allowed_buttons', None)
        if allowed_buttons is not None and button_name not in allowed_buttons:
            # Special exception: Allow gas valves in Normal mode when sputter procedure is active
            gas_valves = ['btnValveGas1', 'btnValveGas2', 'btnValveGas3']
            if button_name in gas_valves and self.is_sputter_procedure_active():
                print(f"🌟 Gas valve {button_name} allowed in Normal mode during sputter procedure")
                # Still need to check other safety conditions, so continue with the checks
            # Special exception: Allow turbo gate valve in Normal mode during sputter procedure (RF ignition control)
            elif button_name == 'btnValveTurboGate' and self.is_sputter_procedure_active():
                print(f"🌟 Turbo gate valve {button_name} allowed in Normal mode during sputter procedure (RF ignition control)")
                # Still need to check other safety conditions, so continue with the checks
            # Special exception: Allow vent valve in Normal mode during vent procedure (pushButton_3)
            elif button_name == 'btnValveVent' and self.current_procedure == 'pushButton_3':
                print(f"🌟 Vent valve {button_name} allowed in Normal mode during vent procedure (pushButton_3)")
                # Still need to check other safety conditions, so continue with the checks
            else:
                return SafetyResult(False, f"Only automatic procedures allowed in {self.current_mode} mode")
        
        # Check extra safety conditions for this mode
        extra_conditions = current_mode_config.get('extra_safety_conditions', [])
        for condition in extra_conditions:
            if not self._evaluate_condition(condition):
                return SafetyResult(False, f"Mode safety condition failed: {condition}")
        
        return SafetyResult(True, "Mode restrictions satisfied")
    
    def _check_emergency_conditions(self) -> SafetyResult:
        """Check for emergency stop conditions."""
        emergency_conditions = self.safety_config.get('emergency_conditions', {})
        
        for emergency_name, emergency_config in emergency_conditions.items():
            condition = emergency_config.get('condition', '')
            if self._evaluate_condition(condition):
                message = emergency_config.get('message', f"Emergency condition: {emergency_name}")
                return SafetyResult(False, f"EMERGENCY: {message}")
        
        return SafetyResult(True, "No emergency conditions detected")
    
    def _evaluate_condition(self, condition: str, suppress_debug: bool = True) -> bool:
        """
        Evaluate a safety condition string.
        
        Args:
            condition: Condition string like "ai_volts[0] < 0.1"
            suppress_debug: If True, suppress debug print statements
            
        Returns:
            True if condition is met, False otherwise
        """
        try:
            # Ensure analog_inputs are properly converted to floats to prevent type comparison errors
            safe_analog_inputs = []
            for val in self.analog_inputs:
                try:
                    safe_analog_inputs.append(float(val))
                except (ValueError, TypeError):
                    safe_analog_inputs.append(0.0)  # Default to 0.0 on conversion error
            
            # Create context for evaluation
            context = {
                'ai_volts': safe_analog_inputs,
                'digital_inputs': self.digital_inputs,
                'relay_state': self.relay_states,
                'current_mode': self.current_mode,
                'pressure_thresholds': self.safety_config.get('pressure_thresholds', {}),
                'current_procedure': self.current_procedure,
                'system_status': self.system_status,
                'float': float,  # Make float() available in eval context for explicit conversions
            }

            # Provide ion_gauge_on boolean and a lightweight safety_summary for YAML usage.
            # IMPORTANT: build this locally to avoid recursive calls to get_safety_status_summary()
            try:
                ion_on = self.is_ion_gauge_on()
            except Exception:
                ion_on = False

            context['ion_gauge_on'] = ion_on
            context['safety_summary'] = {
                'ion_gauge_on': ion_on,
                'analog_inputs': list(safe_analog_inputs),
                'digital_inputs': list(self.digital_inputs),
                'relay_states': dict(self.relay_states),
                'current_mode': self.current_mode,
                'pressure_thresholds': self.safety_config.get('pressure_thresholds', {}),
            }
            
            # Add nested dictionary access for thresholds and relay states
            def get_nested_value(obj, path):
                """Get value from nested dictionary using dot notation.""" 
                keys = path.split('.')
                for key in keys:
                    if isinstance(obj, dict) and key in obj:
                        obj = obj[key]
                    else:
                        return None
                return obj
            
            # Replace dot notation in condition string
            import re
            
            # Handle pressure_thresholds.xxx patterns
            pattern = r'pressure_thresholds\.([a-zA-Z_][a-zA-Z0-9_]*)'
            matches = re.findall(pattern, condition)
            
            for match in matches:
                full_path = f"pressure_thresholds.{match}"
                value = get_nested_value(self.safety_config, full_path)
                if value is not None:
                    condition = condition.replace(full_path, str(value))
            
            # Don't replace relay_state patterns - let them be evaluated naturally through the context
            # The context already contains 'relay_state': self.relay_states, so expressions like
            # relay_state.get('btnIonGauge', False) will work correctly
            
            # Debug print to see what's being evaluated
            if not suppress_debug:
                print(f"Evaluating condition: {condition}")
                #print(f"Relay states: {self.relay_states}")
            
            # Use a restricted eval environment (no builtins) and the prepared context as locals.
            safe_globals = {"__builtins__": {}}
            result = eval(condition, safe_globals, context)
            if not suppress_debug:
                print(f"Condition result: {result}")
            return bool(result)
            
        except Exception as e:
            if not suppress_debug:
                print(f"❌ Error evaluating condition '{condition}': {e}")
                print(f"Context ai_volts: {context.get('ai_volts')} (types: {[type(x) for x in context.get('ai_volts', [])]})")
                print(f"Analog inputs raw: {self.analog_inputs} (types: {[type(x) for x in self.analog_inputs]})")
            return False
    
    def get_safety_status_summary(self) -> Dict[str, Any]:
        """Get a summary of current safety status."""
        try:
            ion_on = self.is_ion_gauge_on()
        except Exception:
            ion_on = False

        return {
            'analog_inputs': self.analog_inputs,
            'digital_inputs': self.digital_inputs,
            'relay_states': self.relay_states,
            'current_mode': self.current_mode,
            'ion_gauge_on': ion_on,
            'pressure_thresholds': self.safety_config.get('pressure_thresholds', {}),
            'emergency_status': self._check_emergency_conditions().allowed,
            'interlock_status': {
                f"digital_{i}": state for i, state in enumerate(self.digital_inputs)
            }
        }

    # --- New: determine best-matching system state ---
    def determine_system_state(self, suppress_debug: bool = True) -> str:
        """
        Determine the best matching system state from safety_conditions.yml based
        on current analog/digital/relay readings. Returns the state name (string).
        
        Priority logic:
        1. If a procedure is active, prioritize states that match that procedure
        2. Look for exact matches (score == 1.0) first
        3. Fall back to best partial match
        4. Finally fall back to initial_state or 'default'
        """
        try:
            state_cfg = self.safety_config.get('system_status', {}).get('states', {})
            if not state_cfg:
                return self.safety_config.get('system_status', {}).get('initial_state', 'default')

            # Helper to evaluate a node which may be string or nested list (AND within a list)
            def _node_true(node) -> bool:
                if isinstance(node, str):
                    return self._evaluate_condition(node, suppress_debug=True)
                if isinstance(node, list):
                    # All entries must be true (AND)
                    for sub in node:
                        if not _node_true(sub):
                            return False
                    return True
                return False

            # If a procedure is active, prioritize procedure-based states
            procedure_priority_states = []
            if self.current_procedure:
                # Map procedures to their expected states
                procedure_state_map = {
                    'pushButton_2': 'pumping',      # pump_procedure
                    'pushButton_3': 'venting',      # vent_procedure  
                    'pushButton_4': 'loadlock_venting',  # vent_loadlock_procedure
                    'pushButton_5': 'load_unload',   # load_unload_procedure
                    'pushButton_6': 'sputter',      # sputter_procedure
                }
                expected_state = procedure_state_map.get(self.current_procedure)
                if expected_state and expected_state in state_cfg:
                    procedure_priority_states.append(expected_state)

            best_state = None
            best_score = -1.0

            # Check procedure-priority states first
            for state_name in procedure_priority_states:
                info = state_cfg[state_name]
                conditions = info.get('conditions', [])
                if not conditions:
                    continue

                matched = 0
                total = len(conditions)

                for cond in conditions:
                    try:
                        res = _node_true(cond)
                    except Exception:
                        res = False
                    if res:
                        matched += 1

                score = (matched / total) if total > 0 else 0.0
                if not suppress_debug:
                    print(f"DEBUG: Procedure-priority state '{state_name}' score: {score}")
                
                # For procedure-based states, accept lower threshold (e.g., 0.8)
                # since some conditions might be transient during procedure execution
                if score >= 0.8:
                    if not suppress_debug:
                        print(f"DEBUG: Using procedure-priority state '{state_name}' (score: {score})")
                    return state_name

                # Track best procedure state even if not good enough
                if score > best_score:
                    best_score = score
                    best_state = state_name

            # If no good procedure state found, check all states for exact matches
            for state_name, info in state_cfg.items():
                # Skip if already checked as procedure-priority
                if state_name in procedure_priority_states:
                    continue
                    
                conditions = info.get('conditions', [])
                if not conditions:
                    continue

                matched = 0
                total = len(conditions)

                for cond in conditions:
                    try:
                        res = _node_true(cond)
                    except Exception:
                        res = False
                    if res:
                        matched += 1

                score = (matched / total) if total > 0 else 0.0
                
                # Perfect match -> return immediately
                if score == 1.0:
                    if not suppress_debug:
                        print(f"DEBUG: Found perfect match state '{state_name}'")
                    return state_name

                # Track best partial match
                if score > best_score:
                    best_score = score
                    best_state = state_name

            # If we have a best state with reasonable score, use it
            if best_state and best_score > 0.5:
                if not suppress_debug:
                    print(f"DEBUG: Using best partial match state '{best_state}' (score: {best_score})")
                return best_state
                
            # If no matching state found, fall back to initial_state or 'default'
            fallback = self.safety_config.get('system_status', {}).get('initial_state', 'default')
            print(f"DEBUG: No good state match found, falling back to '{fallback}'")
            return fallback
            
        except Exception as e:
            print(f"❌ Error determining system state: {e}")
            return self.safety_config.get('system_status', {}).get('initial_state', 'default')