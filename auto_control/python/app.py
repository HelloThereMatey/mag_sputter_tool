from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Dict

from PyQt5 import uic
from PyQt5.QtCore import QTimer, Qt, QRunnable, QThreadPool, pyqtSignal, QObject, QEvent
from PyQt5.QtWidgets import QMainWindow, QWidget, QMessageBox, QApplication
import builtins
# Support both package and script execution
try:
    from .config import load_config  # type: ignore
    from .widgets.indicators import set_interlock_indicator  # type: ignore
    from .widgets.mode_dialog import ModeSelectionDialog  # type: ignore
    from .widgets.mfc_dialog import show_mfc_setpoint_dialog  # type: ignore
    from .safety import SafetyController, SafetyResult  # type: ignore
    from .arduino_controller import ArduinoController  # type: ignore
    from .widgets.plotter_widget import PlotterWindow  # type: ignore
    from .widgets.analog_recorder import AnalogRecorderDialog, AnalogRecorderWindow  # type: ignore
    from .widgets.logbook_widget import LogbookWidget  # type: ignore
    from .widgets.login_dialog import LoginDialog  # type: ignore
    from .widgets.about_dialog import AboutDialog  # type: ignore
    #from .gas_control.controller import GasFlowController  # type: ignore
    from .gas_control.subprocess_controller import GasFlowController
except ImportError:
    from config import load_config  # type: ignore
    from widgets.indicators import set_interlock_indicator  # type: ignore
    from widgets.mode_dialog import ModeSelectionDialog  # type: ignore
    from widgets.mfc_dialog import show_mfc_setpoint_dialog  # type: ignore
    from safety import SafetyController, SafetyResult  # type: ignore
    from arduino_controller import ArduinoController  # type: ignore
    from widgets.plotter_widget import PlotterWindow  # type: ignore
    from widgets.analog_recorder import AnalogRecorderDialog, AnalogRecorderWindow  # type: ignore
    from widgets.logbook_widget import LogbookWidget  # type: ignore
    from widgets.login_dialog import LoginDialog  # type: ignore
    from widgets.about_dialog import AboutDialog  # type: ignore
    #from gas_control.controller import GasFlowController  # type: ignore
    from gas_control.subprocess_controller import GasFlowController #try subprocess method instead


# Background procedure runner
class ProcedureSignals(QObject):
    """Signals for background auto-procedure execution."""
    finished = pyqtSignal(bool, str)  # success, message


class ProcedureWorker(QRunnable):
    """QRunnable wrapper to run an auto-procedure function in a background thread."""
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = ProcedureSignals()

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            # Handle special return values for load/unload procedure
            if result == "GATE_OPEN_WAITING_USER":
                # Special case: procedure needs user interaction in main thread
                self.signals.finished.emit(True, "GATE_OPEN_WAITING_USER")
            # Expect result True/False or (success, message)
            elif isinstance(result, tuple) and len(result) >= 1:
                success = builtins.bool(result[0])
                message = '' if len(result) < 2 else str(result[1])
                self.signals.finished.emit(success, message)
            else:
                success = builtins.bool(result)
                message = ''
                self.signals.finished.emit(success, message)
        except Exception as e:
            self.signals.finished.emit(False, str(e))


class AutoControlWindow(QMainWindow):
    def __init__(self, parent: Optional[QWidget] = None, arduino: ArduinoController = None, current_user: Dict = None, master_password: str = None) -> None:
        print("🐛 DEBUG: *** AutoControlWindow.__init__ started ***")
        print(f"🐛 DEBUG: Arduino parameter received: {arduino is not None}")
        if arduino is not None:
            print(f"🐛 DEBUG: Arduino connection status: {arduino.is_connected}")
        super().__init__(parent)
        print("🐛 DEBUG: super().__init__ completed")
        
        # Store user information
        self.current_user = current_user
        self.master_password = master_password
        if current_user:
            print(f"👤 DEBUG: Logged in as: {current_user['username']} (Level {current_user['admin_level']}: {current_user['level_name']})")
        
        self.cfg = load_config()
        print("🐛 DEBUG: config loaded")

        # Load UI into a central widget so QMainWindow menu bar is visible
        ui_path = Path(__file__).resolve().parents[1] / 'vacuum_system_gui.ui'
        central_widget = QWidget()
        print("🔧 DEBUG: Loading UI...")
        uic.loadUi(ui_path, central_widget)
        print("🔧 DEBUG: UI loaded")
        self.setCentralWidget(central_widget)
        print("🔧 DEBUG: Central widget set")

        # Expose child widgets as attributes on self so older code using getattr(self, name) still works
        print("🔧 DEBUG: Exposing child widgets...")
        for child in central_widget.findChildren(QWidget):
            name = child.objectName()
            if name:
                try:
                    setattr(self, name, child)
                except Exception:
                    pass
        print("🔧 DEBUG: Child widgets exposed")

        # Operation mode
        self.current_mode = "Normal"
        
        # Auto procedure tracking
        self.current_procedure = None  # Track which procedure is running
        self.auto_procedure_buttons = {}  # Map procedure names to procedure info
        
        # System status tracking
        self.system_status = "vented"  # Current system state
        self.previous_system_status = None  # For state transitions
        
        # Ion gauge auto-toggle safety control
        self.ion_gauge_auto_toggle_enabled = True  # Controls automatic ion gauge safety logic

        # Relay map: objectName -> controller RELAY index (1-based)
        # YAML relays use Arduino pin numbers. Translate to RELAY_n using relay_pins order.
        self.relay_map: Dict[str, int] = {}
        pin_to_relay_index = {pin: idx + 1 for idx, pin in enumerate(self.cfg.relay_pins)}
        for obj_name, arduino_pin in self.cfg.relays.items():
            relay_idx = pin_to_relay_index.get(int(arduino_pin))
            if relay_idx is not None:
                self.relay_map[obj_name] = relay_idx
            else:
                # Fallback: assume value is already a relay index
                try:
                    self.relay_map[obj_name] = int(arduino_pin)
                except Exception:
                    pass

        # Arduino Controller Assignment
        print("🔌 DEBUG: Assigning Arduino controller...")
        if arduino is None:
            print("🔌 DEBUG: No Arduino provided, creating new ArduinoController instance")
            self.arduino = ArduinoController()
        else:
            print("🔌 DEBUG: Using pre-initialized Arduino controller from run()")
            self.arduino = arduino
        print(f"🔌 DEBUG: Arduino controller assigned, connected: {self.arduino.is_connected if self.arduino else False}")

        # Safety Controller
        print("⚠️ DEBUG: Creating SafetyController...")
        self.safety_controller = SafetyController()
        print("⚠️ DEBUG: SafetyController created")

        # Gas Flow Controller (MFC)
        print("🌀 DEBUG: Creating GasFlowController...")
        self.gas_controller = None
        if hasattr(self.cfg, 'gas_control') and self.cfg.gas_control:
            try:
                self.gas_controller = GasFlowController(self.cfg.gas_control, self.safety_controller)
                print("🌀 DEBUG: GasFlowController created successfully")
            except Exception as e:
                print(f"❌ DEBUG: Failed to create GasFlowController: {e}")
                self.gas_controller = None
        else:
            print("⚠️ DEBUG: No gas_control configuration found in sput.yml")

        # Initialize safety state tracking
        self.last_analog_inputs = [0.0, 0.0, 0.0, 0.0]
        self.last_digital_inputs = [False, False, False, False]

        # Moving-average buffer for Turbo Spin percent (3-sample)
        # These are display-only buffers (store scaled percent values)
        # Keep simple assignment for broad Python version compatibility
        self._turbo_ma = []
        self._turbo_window = []  # stores recent scaled percent values (not raw volts)

        # Timers
        self.status_timer = QTimer(self)
        self.status_timer.setInterval(1000)  # relay status sync
        self.status_timer.timeout.connect(self.refresh_status)

        self.input_timer = QTimer(self)
        self.input_timer.setInterval(700)  # DI/AI polling
        self.input_timer.timeout.connect(self.refresh_inputs)

        # Alive/watchdog timer to confirm event loop is running (low-volume)
        self.alive_timer = QTimer(self)
        self.alive_timer.setInterval(300000)  # 5 minutes
        self.alive_timer.timeout.connect(lambda: print("watchdog: event loop alive", flush=True))
        # Start alive timer regardless of Arduino connection so we can detect a blocked loop
        self.alive_timer.start()
        print("DEBUG: Alive timer started")

        # MFC update timer - use dynamic interval based on system state
        self.mfc_timer = QTimer(self)
        self.mfc_timer.setInterval(5000)  # Default: Update MFC readings every 5 seconds
        self.mfc_timer.timeout.connect(self.schedule_mfc_update)
        
        # Cache for MFC readings to prevent blocking GUI
        self.mfc_readings_cache = {}
        self.mfc_update_in_progress = False

        # Light bulb auto-off timer - turns off chamber light after 30 seconds
        self.light_timer = QTimer(self)
        self.light_timer.setSingleShot(True)  # One-shot timer
        self.light_timer.setInterval(30000)  # 30 seconds
        self.light_timer.timeout.connect(self._auto_turn_off_light)

        # Plotter window handle and thread pool for background tasks
        self._plotter_window = None
        self._recorder_window = None  # Handle for analog recorder window
        # Thread pool for background tasks (keeps GUI responsive)
        self.threadpool = QThreadPool()

        # Wire buttons
        self._wire_buttons()
        self._wire_mode_button()
        self._wire_special_buttons()
        self._wire_auto_procedure_buttons()
        self._wire_mfc_controls()  # Wire MFC layout click handlers

        # Connect system state display label
        print("DEBUG: Looking for QLabel 'label_5'...")
        self.systemStateLabel = None

        # Try multiple ways to find the QLabel
        def find_label_recursive(widget, name):
            if widget.objectName() == name:
                return widget
            for child in widget.children():
                if hasattr(child, 'objectName'):
                    result = find_label_recursive(child, name)
                    if result:
                        return result
            return None

        self.systemStateLabel = find_label_recursive(self, 'label_5')

        if self.systemStateLabel:
            print(f"DEBUG: QLabel found recursively: {self.systemStateLabel}")
        else:
            print("DEBUG: QLabel 'label_5' not found recursively")
            # Create a fallback QLabel
            from PyQt5.QtWidgets import QLabel
            self.systemStateLabel = QLabel("System Status: QLabel not found")
            self.systemStateLabel.setStyleSheet("QLabel { color: red; font-weight: bold; }")
            print(f"DEBUG: Created fallback QLabel: {self.systemStateLabel}")

        # Initial UI state
        print("DEBUG: Setting initial UI state...")
        self._set_controls_enabled(False)
        self._update_mode_display()
        self._update_system_state_display()
        self._update_gun_target_labels()  # Load latest target info from logbook
        self._update_user_label()  # Display logged-in username
        print("DEBUG: Initial UI state set")

        # Auto-open logbook after GUI loads so user can update targets
        QTimer.singleShot(500, self.open_logbook)

        # Check if Arduino is already connected from run(), otherwise setup auto-connect
        if self.arduino is not None and self.arduino.is_connected:
            print("DEBUG: Arduino already connected from run(), calling on_connected()")
            self.on_connected()
        else:
            print("DEBUG: Arduino not connected yet, setting up auto-connect timer...")
            QTimer.singleShot(300, self.auto_connect)  # Re-enabled after fixing AttributeError issues
            print("DEBUG: Auto-connect timer ENABLED")

        # Add Tools menu action for plotter
        try:
            menubar = self.menuBar()
        except Exception:
            menubar = None

        if menubar is not None:
            tools_menu = menubar.addMenu('Tools')
            plot_action = tools_menu.addAction('Open Plotter')
            plot_action.triggered.connect(self.open_plotter)
            
            # Add analog recorder action
            recorder_action = tools_menu.addAction('Record Analog Inputs')
            recorder_action.triggered.connect(self.open_analog_recorder)
            
            # Add logbook action
            logbook_action = tools_menu.addAction('Logbook')
            logbook_action.triggered.connect(self.open_logbook)
            
            # Add separator
            tools_menu.addSeparator()
            
            # Add ion gauge auto-toggle menu item (checkable)
            self.ion_gauge_auto_toggle_action = tools_menu.addAction('Ion Gauge Auto-Toggle')
            self.ion_gauge_auto_toggle_action.setCheckable(True)
            self.ion_gauge_auto_toggle_action.setChecked(True)  # Enabled by default
            self.ion_gauge_auto_toggle_action.triggered.connect(self._on_ion_gauge_auto_toggle_changed)
            self.ion_gauge_auto_toggle_action.setStatusTip("Enable/disable automatic ion gauge toggle safety logic")
            
            # Add system state management action
            try:
                # Import the dialog from widgets package if available
                try:
                    from .widgets.other_dialogs import SetSystemStateDialog  # type: ignore
                except Exception:
                    from widgets.other_dialogs import SetSystemStateDialog  # type: ignore

                set_state_action = tools_menu.addAction('Set System State')
                set_state_action.triggered.connect(self.show_system_state_dialog)
            except Exception:
                # Leave out if import fails
                pass
            
            # Add Run Procedure menu
            procedure_menu = menubar.addMenu('Run Procedure')
            self._setup_procedure_menu(procedure_menu)
            
            # Add Help menu
            help_menu = menubar.addMenu('Help')
            about_action = help_menu.addAction('About')
            about_action.triggered.connect(self.show_about_dialog)
    def set_system_status(self, new_status: str) -> None:
        """Set the system status and update the display."""
        if self.system_status != new_status:
            self.previous_system_status = self.system_status
            self.system_status = new_status
            
            # Update safety controller with new status
            try:
                if hasattr(self.safety_controller, 'system_status'):
                    self.safety_controller.system_status = new_status
            except Exception:
                pass
                
            try:
                self._update_system_state_display()
            except Exception:
                pass
            # Update button states when system status changes
            try:
                self._update_auto_procedure_button_states()
            except Exception as e:
                print(f"DEBUG: Error updating button states after status change: {e}")
            # Update MFC timer interval based on new system state
            try:
                self.update_mfc_timer_interval()
            except Exception as e:
                print(f"DEBUG: Error updating MFC timer interval after status change: {e}")
            print(f"System status changed to: {new_status}")

    @staticmethod
    def voltage_to_pressure_torr(voltage: float) -> float:
        """
        Convert voltage reading from chamber pirani gauge to pressure in Torr.
        
        Calibrated equation derived from actual gauge controller display:
        P = 10^(2.239072*V - 4.012614)
        
        Args:
            voltage: Voltage reading from analog input (0-5V)
            
        Returns:
            Pressure in Torr
        """
        import math
        try:
            # Apply calibrated conversion equation
            log_pressure = 2.239072 * voltage - 4.012614
            pressure_torr = 10 ** log_pressure
            return pressure_torr
        except (ValueError, OverflowError):
            # Return a sensible default for invalid/extreme values
            return 0.0

    def can_start_procedure(self, procedure_name: str) -> bool:
        """Check if a procedure can be started based on current system status."""
        # Must have safety configuration
        if not hasattr(self, 'safety_controller') or not self.safety_controller.safety_config:
            print(f"DEBUG: No safety controller or config for procedure '{procedure_name}'")
            return False

        cfg = self.safety_controller.safety_config
        #print(f"DEBUG: Checking if procedure '{procedure_name}' can start in state '{self.system_status}'")
        #print(f"DEBUG: Current procedure is: '{self.current_procedure}'")
        #print(f"DEBUG: Safety controller current_procedure: '{getattr(self.safety_controller, 'current_procedure', 'None')}'")
        #print(f"DEBUG: Safety controller system_status: '{getattr(self.safety_controller, 'system_status', 'None')}')")

        # Check if procedure is in the current system state's allowed_procedures list
        try:
            state_cfg = cfg.get('system_status', {}).get('states', {})
            #print(f"DEBUG: Available states in config: {list(state_cfg.keys())}")
            
            current_state_info = state_cfg.get(self.system_status, {})
            #print(f"DEBUG: State info for '{self.system_status}': {current_state_info}")
            
            allowed_list = current_state_info.get('allowed_procedures', [])
            
            #print(f"DEBUG: Current state '{self.system_status}' allows: {allowed_list}")
            #print(f"DEBUG: Looking for procedure: '{procedure_name}'")
            #print(f"DEBUG: Is '{procedure_name}' in allowed list? {procedure_name in allowed_list}")
            
            if procedure_name in allowed_list:
                #print(f"DEBUG: Procedure '{procedure_name}' is allowed")
                return True
            else:
                print(f"DEBUG: Procedure '{procedure_name}' is NOT allowed")
                return False
                
        except Exception as err:
            print(f"DEBUG: Error checking allowed_procedures: {err}")
            return False
    

    def cancel_auto_procedure(self, button_name: str, procedure_name: str) -> None:
        """Cancel the currently running auto procedure."""
        reply = QMessageBox.question(
            self,
            "Cancel Procedure",
            f"Are you sure you want to cancel the {procedure_name} procedure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            print(f"Cancelling {procedure_name} procedure...")
            
            # Stop MFC flows if cancelling sputter procedure
            if button_name == 'pushButton_6':  # Sputter procedure button
                self.stop_all_mfc_flows()
            
            # Run a cleanup to return system to the configured 'default' state.
            # Use the auto_procedures.abort_and_go_default helper so this runs
            # in the background and the UI remains responsive.
            try:
                try:
                    from .auto_procedures import abort_and_go_default
                except Exception:
                    from auto_procedures import abort_and_go_default

                def on_finished(success: bool, message: str) -> None:
                    # Runs in UI thread via signal
                    if success:
                        QMessageBox.information(self, "Cancelled", "Procedure cancelled. System returned to default state.")
                        # Align with YAML 'default' state name
                        try:
                            self.set_system_status('default')
                            self.update_safety_state()
                            QTimer.singleShot(100, lambda: self._clear_current_procedure())
                        except Exception:
                            self._clear_current_procedure()
                    else:
                        QMessageBox.warning(self, "Cancel Failed", f"Failed to return to default state: {message}")
                        # restore previous state if possible
                        try:
                            self.set_system_status(self.previous_system_status)
                        except Exception:
                            pass
                        self._clear_current_procedure()

                # Start worker to perform abort/cleanup in background
                worker = ProcedureWorker(abort_and_go_default, arduino=self.arduino, safety=self.safety_controller, relay_map=self.relay_map)
                worker.signals.finished.connect(on_finished)
                if hasattr(self, 'threadpool') and self.threadpool is not None:
                    self.threadpool.start(worker)
                else:
                    # Fallback synchronous call
                    res = abort_and_go_default(self.arduino, self.safety_controller, self.relay_map)
                    ok, msg = (builtins.bool(res[0]), '' if len(res) < 2 else str(res[1])) if isinstance(res, tuple) else (builtins.bool(res), '')
                    on_finished(ok, msg)
            except Exception as e:
                print(f"❌ Error while attempting to cancel procedure: {e}")
                # Best-effort clearing UI state
                self._clear_current_procedure()

    def safe_button_click(self, button_name: str, original_handler, *args, **kwargs):
        """
        Safety wrapper for button click handlers.
        Checks safety conditions before allowing operation.
        In Override mode, bypasses all safety checks.
        In Normal mode, blocks manual operations except those explicitly allowed.
        """
        print(f"Safety check for button: {button_name} (Mode: {self.current_mode})")
        
        # Block manual control during auto procedures (except in Override mode)
        if self.current_procedure is not None and self.current_mode != "Override":
            # DEBUG: Show current procedure state
            print(f"🔍 DEBUG: current_procedure = '{self.current_procedure}', button = '{button_name}'")
            
            # Special exceptions for manual control during procedures
            gas_valves = ['btnValveGas1', 'btnValveGas2', 'btnValveGas3']
            shutters = ['btnShutter1', 'btnShutter2']
            sputter_procedure_names = ['pushButton_6', 'sputter_procedure']  # Handle both GUI button name and procedure name
            vent_procedure_names = ['pushButton_3', 'vent_procedure']  # Handle both GUI button name and procedure name
            
            allowed = False
            
            # Allow gas valves during sputter procedure
            if (button_name in gas_valves and 
                any(proc in str(self.current_procedure) for proc in sputter_procedure_names) and
                hasattr(self, 'safety_controller') and 
                self.safety_controller.is_sputter_procedure_active()):
                print(f"🌟 Allowing {button_name} during sputter procedure")
                allowed = True
            
            # Allow turbo gate valve during sputter procedure (for RF ignition control)
            elif (button_name == 'btnValveTurboGate' and
                  any(proc in str(self.current_procedure) for proc in sputter_procedure_names) and
                  hasattr(self, 'safety_controller') and
                  self.safety_controller.is_sputter_procedure_active()):
                print(f"🌟 Allowing {button_name} during sputter procedure (RF ignition control)")
                allowed = True
            
            # Allow vent valve during vent procedure (manual control for safety)
            elif button_name == 'btnValveVent':
                print(f"🔍 DEBUG: Checking vent valve exception...")
                print(f"🔍 DEBUG: vent_procedure_names = {vent_procedure_names}")
                print(f"🔍 DEBUG: current_procedure in names? {any(proc in str(self.current_procedure) for proc in vent_procedure_names)}")
                if any(proc in str(self.current_procedure) for proc in vent_procedure_names):
                    print(f"🌟 Allowing {button_name} during vent procedure (manual override)")
                    allowed = True
                else:
                    print(f"❌ DEBUG: Vent valve NOT allowed - procedure name mismatch")
            
            # Allow light bulb during any procedure
            elif button_name == 'btnLightBulb':
                print(f"🌟 Allowing {button_name} - light bulb can be operated during any procedure")
                allowed = True
            
            # Allow shutters during any procedure
            elif button_name in shutters:
                print(f"🌟 Allowing {button_name} - shutters can be operated during any procedure")
                allowed = True
            
            if not allowed:
                QMessageBox.information(
                    self,
                    "Procedure Running",
                    f"Manual control is disabled while {self.current_procedure} is running.\n\n"
                    "Please wait for the procedure to complete or cancel it first."
                )
                return
        
        # Normal mode: check if this specific button is allowed
        if self.current_mode == "Normal":
            # Check if this button is explicitly allowed in Normal mode
            allowed = False
            if hasattr(self, 'safety_controller') and self.safety_controller.safety_config:
                mode_restrictions = self.safety_controller.safety_config.get('mode_restrictions', {})
                normal_mode_config = mode_restrictions.get('Normal', {})
                allowed_buttons = normal_mode_config.get('allowed_buttons', [])
                
                if button_name in allowed_buttons:
                    allowed = True
                
                # Special exception: Allow gas valves during sputter procedure
                gas_valves = ['btnValveGas1', 'btnValveGas2', 'btnValveGas3']
                if (button_name in gas_valves and 
                    hasattr(self, 'safety_controller') and 
                    self.safety_controller.is_sputter_procedure_active()):
                    allowed = True
                    print(f"🌟 Allowing {button_name} in Normal mode during sputter procedure")
                
                # Special exception: Allow turbo gate valve during sputter procedure (for RF ignition control)
                sputter_procedure_names = ['pushButton_6', 'sputter_procedure']
                if (button_name == 'btnValveTurboGate' and
                    self.current_procedure is not None and
                    any(proc in str(self.current_procedure) for proc in sputter_procedure_names) and
                    hasattr(self, 'safety_controller') and 
                    self.safety_controller.is_sputter_procedure_active()):
                    allowed = True
                    print(f"🌟 Allowing {button_name} in Normal mode during sputter procedure (RF ignition control)")
                
                # Special exception: Allow vent valve during vent procedure (manual override for safety)
                vent_procedure_names = ['pushButton_3', 'vent_procedure']
                if (button_name == 'btnValveVent' and 
                    self.current_procedure is not None and
                    any(proc in str(self.current_procedure) for proc in vent_procedure_names)):
                    allowed = True
                    print(f"🌟 Allowing {button_name} in Normal mode during vent procedure (manual safety override)")
            
            if not allowed:
                QMessageBox.information(
                    self,
                    "Manual Control Disabled",
                    f"Manual control of {button_name} is disabled in Normal mode.\n\n"
                    "Use the automatic procedure buttons to control the system safely."
                )
                return
        
        # Override mode bypasses all safety checks
        if self.current_mode == "Override":
            print(f"Override mode: Bypassing all safety checks for {button_name}")
            try:
                original_handler(*args, **kwargs)
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Operation Failed",
                    f"Operation failed: {str(e)}"
                )
            return
        
        # Update safety state with latest readings for Manual mode and allowed Normal mode buttons
        self.update_safety_state()
        
        # Determine if this should be treated as an auto procedure operation
        # This bypasses mode restrictions while still enforcing safety conditions
        treat_as_auto_procedure = False
        
        # Vent valve during vent procedure should bypass mode restrictions
        vent_procedure_names = ['pushButton_3', 'vent_procedure']
        if (button_name == 'btnValveVent' and 
            self.current_procedure is not None and
            any(proc in str(self.current_procedure) for proc in vent_procedure_names)):
            treat_as_auto_procedure = True
            print(f"🔧 Treating {button_name} as auto procedure operation during vent (bypasses mode restrictions)")
        
        # Check safety conditions
        safety_result = self.safety_controller.check_button_safety(button_name, is_auto_procedure=treat_as_auto_procedure)
        
        print(f"Safety result: allowed={safety_result.allowed}, message='{safety_result.message}'")
        
        if not safety_result.allowed:
            # Show error message
            QMessageBox.critical(
                self, 
                "Safety Interlock", 
                f"Operation blocked by safety system:\n\n{safety_result.message}"
            )
            return
        
        # Check if confirmation is required
        if safety_result.confirmation_required:
            reply = QMessageBox.question(
                self,
                "Confirm Operation",
                safety_result.confirmation_message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Safety checks passed, perform the operation
        try:
            print(f"Executing operation for {button_name}")
            original_handler(*args, **kwargs)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Operation Failed",
                f"Operation failed: {str(e)}"
            )

    def update_safety_state(self):
        """Update safety controller with current system state."""
        try:
            # Get current analog and digital readings
            analog_readings = self.last_analog_inputs  # Now contains voltage values
            digital_readings = self.last_digital_inputs
            
            # DEBUG: Print digital readings for troubleshooting
            #print(f"DEBUG update_safety_state: digital_readings = {digital_readings}")
            #print(f"DEBUG update_safety_state: current_procedure = {self.current_procedure}")
            
            # Get current relay states
            relay_states = {}
            for button_name in self.relay_map.keys():
                relay_states[button_name] = self.get_button_state(button_name)
            
            # Update safety controller with procedure info
            self.safety_controller.update_system_state(
                analog_inputs=analog_readings,
                digital_inputs=digital_readings,
                relay_states=relay_states,
                current_mode=self.current_mode,
                current_procedure=self.current_procedure,
                system_status=self.system_status
            )
            
            # Let the SafetyController determine the best-matching system state
            # BUT: Don't override procedure-specific states while auto-procedures are running
            procedure_states = {
                'pushButton_2': 'pumping',           # pump_procedure
                'pushButton_3': 'venting',           # vent_procedure  
                'pushButton_4': 'loadlock_venting',  # vent_loadlock_procedure
                'pushButton_5': 'load_unload',       # load_unload_procedure
                'pushButton_6': 'sputter',           # sputter_procedure
                'btnCloseAll': 'default'             # close_all_relays
            }
            
            # Check if we should override automatic state determination
            should_override_state = False
            if self.current_procedure is not None:
                expected_state = procedure_states.get(self.current_procedure)
                if expected_state and self.system_status == expected_state:
                    # Procedure is running and we're in the correct procedure state - don't change it
                    should_override_state = True
                    #print(f"DEBUG: State override active - maintaining '{self.system_status}' during procedure '{self.current_procedure}'")
            
            if not should_override_state:
                try:
                    if hasattr(self.safety_controller, 'determine_system_state'):
                        new_state = self.safety_controller.determine_system_state(suppress_debug=True)

                        # Debug code to add to app.py in the update_safety_state method
                        if new_state and new_state != getattr(self, 'system_status', None):
                            print(f"DEBUG: System state changing from {getattr(self, 'system_status', None)} to {new_state}")

                    else:
                        new_state = None
                except Exception:
                    new_state = None

                # If a state was determined and differs from the app's state, apply it
                if new_state and new_state != getattr(self, 'system_status', None):
                    # set_system_status will update previous_system_status and refresh the UI
                    try:
                        self.set_system_status(new_state)
                    except Exception:
                        # best-effort only
                        pass
            else:
                pass
                #print(f"DEBUG: Skipping automatic state determination - procedure '{self.current_procedure}' is running")

            # Keep SafetyController.system_status in sync with UI/app state for other logic
            try:
                if hasattr(self.safety_controller, 'system_status'):
                    self.safety_controller.system_status = self.system_status
            except Exception:
                pass
            
            # Safety check: Turn off ion gauge if it's on but not in high vacuum state
            # ONLY if auto-toggle is enabled (can be disabled via Tools menu)
            if self.ion_gauge_auto_toggle_enabled:
                try:
                    if (hasattr(self.safety_controller, 'is_ion_gauge_on') and 
                        self.safety_controller.is_ion_gauge_on() and 
                        self.system_status not in ['high_vacuum', 'pumping']):
                        
                        print(f"DEBUG: Ion gauge is ON but system state is '{self.system_status}' (not high_vacuum) - turning off ion gauge for safety")
                        
                        # Import the toggle function from auto_procedures
                        try:
                            from .auto_procedures import toggle_ion_gauge
                        except ImportError:
                            from auto_procedures import toggle_ion_gauge
                        
                        # Turn off ion gauge safely
                        if toggle_ion_gauge(False, self.arduino, self.safety_controller, self.relay_map):
                            print("DEBUG: Ion gauge turned off successfully for safety")
                        else:
                            print("DEBUG: Warning - failed to turn off ion gauge")
                            
                except Exception as e:
                    print(f"DEBUG: Error in ion gauge safety check: {e}")
            else:
                # Auto-toggle is disabled - log this for debugging
                try:
                    if (hasattr(self.safety_controller, 'is_ion_gauge_on') and 
                        self.safety_controller.is_ion_gauge_on() and 
                        self.system_status not in ['high_vacuum', 'pumping']):
                        print(f"DEBUG: Ion gauge auto-toggle DISABLED - not turning off ion gauge (manual control only)")
                except Exception:
                    pass
                
        except Exception as e:
            print(f"❌ Error updating safety state: {e}")

    def get_button_state(self, button_name: str) -> bool:
        """Get the current state of a button/relay."""
        try:
            btn = getattr(self, button_name, None)
            if btn and hasattr(btn, 'isChecked'):
                return btn.isChecked()
            return False
        except Exception:
            return False

    def _update_mode_display(self) -> None:
        """Update the mode button text to show current mode."""
        if hasattr(self, 'btnModeToggle'):
            self.btnModeToggle.setText(f"Mode: {self.current_mode}")
            
            # Style based on mode
            if self.current_mode == "Normal":
                style = "QPushButton { background: #2d4f8e; border: 2px solid #4a7bc8; color: white; font-size: 11pt; font-weight: bold; }"
            elif self.current_mode == "Manual":
                style = "QPushButton { background: #8e6b2d; border: 2px solid #c8a14a; color: white; font-size: 11pt; font-weight: bold; }"
            else:  # Override
                style = "QPushButton { background: #8e2d2d; border: 2px solid #c84a4a; color: white; font-size: 11pt; font-weight: bold; }"
            
            self.btnModeToggle.setStyleSheet(style)
        
        # Update button operability based on mode
        self._update_auto_procedure_button_states()

    def _update_system_state_display(self) -> None:
        """Update the system state display in the System State group box."""
        print(f"🖥️ DEBUG: _update_system_state_display called with system_status='{self.system_status}'")
        
        # Ensure systemStateLabel exists
        if not hasattr(self, 'systemStateLabel') or self.systemStateLabel is None:
            raise RuntimeError("💥 CRITICAL: systemStateLabel not found - UI initialization failed")
        
        # Ensure safety controller is properly initialized
        if not hasattr(self, 'safety_controller') or not self.safety_controller:
            raise RuntimeError("💥 CRITICAL: Safety controller not initialized")
        
        if not self.safety_controller.safety_config:
            raise RuntimeError("💥 CRITICAL: Safety configuration not loaded - safety_conditions.yml missing or invalid")
        
        # Get state information from safety_conditions.yml
        states_config = self.safety_controller.safety_config.get('system_status', {}).get('states', {})
        print(f"📋 DEBUG: Available states in safety config: {list(states_config.keys())}")
        
        state_info = states_config.get(self.system_status, {})
        print(f"📊 DEBUG: State info for '{self.system_status}': {state_info}")
        
        if not state_info:
            raise RuntimeError(f"💥 CRITICAL: System state '{self.system_status}' not defined in safety_conditions.yml")
        
        description = state_info.get('description')
        if not description:
            raise RuntimeError(f"💥 CRITICAL: No description defined for system state '{self.system_status}' in safety_conditions.yml")
        
        color = state_info.get('color', 'white')
        
        print(f"🎨 DEBUG: Setting QLabel text to: '{description}' with color: {color}")
        self.systemStateLabel.setText(description)
        self.systemStateLabel.setStyleSheet(f"QLabel {{ color: {color}; font-weight: bold; font-size: 12pt; }}")

    def _update_gun_target_labels(self) -> None:
        """Update Gun1Target and Gun2Target labels from logbook database."""
        try:
            # Import here to avoid circular dependency
            from pathlib import Path
            import sqlite3
            
            db_path = Path(__file__).parent.parent / "logbook.db"
            
            # Check if database exists
            if not db_path.exists():
                return
            
            # Get latest entry
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT gun1_target, gun2_target FROM logbook ORDER BY date DESC LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            
            if result:
                gun1, gun2 = result[0], result[1]
                
                # Update Gun1Target label
                if hasattr(self, 'Gun1Target'):
                    self.Gun1Target.setText(f"Gun #1: {gun1}")
                
                # Update Gun2Target label
                if hasattr(self, 'Gun2Target'):
                    self.Gun2Target.setText(f"Gun #2: {gun2}")
            else:
                # No entries in database, set default text
                if hasattr(self, 'Gun1Target'):
                    self.Gun1Target.setText("Gun #1: ")
                if hasattr(self, 'Gun2Target'):
                    self.Gun2Target.setText("Gun #2: ")
                    
        except Exception as e:
            print(f"DEBUG: Error updating gun target labels: {e}")

    def _update_user_label(self) -> None:
        """Update user label with formatted username (bold 'USER:' and normal username)."""
        try:
            if hasattr(self, 'user') and self.current_user:
                username = self.current_user.get('username', 'Unknown')
                # Use HTML to format: bold "USER:" and normal username
                formatted_text = f'<b>USER:</b> {username}'
                self.user.setText(formatted_text)
        except Exception as e:
            print(f"DEBUG: Error updating user label: {e}")

    def _update_auto_procedure_button_states(self) -> None:
        """Update auto procedure button states based on current procedure."""
        # Get connection state - handle None arduino
        connection_state = self.arduino is not None and self.arduino.is_connected
        if not connection_state:
            print(f"🔌 DEBUG: Auto procedure connection state: {connection_state}")
        
        # Determine initial enabled/checked states
        for btn_name, btn_info in self.auto_procedure_buttons.items():
            btn = btn_info['button']
            if btn is None:
                continue

            # Skip btnCloseAll here - it has special handling later
            if btn_name == 'btnCloseAll':
                continue

            # Default: disabled when no connection
            enabled = builtins.bool(connection_state)
            checked = False

            # If a procedure is currently running
            if self.current_procedure is not None:
                if self.current_procedure == btn_name:
                    # This one is running
                    enabled = True
                    checked = True
                else:
                    # another procedure is running -> disable
                    enabled = False
                    checked = False
            else:
                # No procedure running - check if this procedure can be started
                procedure_key = btn_info.get('procedure_key')
                if procedure_key and connection_state and btn_info.get('type') == 'gui_button':
                    #print(f"🔍 DEBUG: Checking if {btn_name} ({procedure_key}) can start...")
                    try:
                        enabled = self.can_start_procedure(procedure_key)
                        #print(f"✅ DEBUG: {btn_name} enabled = {enabled}")
                    except Exception as e:
                        print(f"❌ Error checking if {procedure_key} can start: {e}")
                        enabled = False
                else:
                    print(f"🔌 DEBUG: {btn_name} disabled due to no procedure_key or no connection")
                    enabled = False

            btn.setEnabled(enabled)
            # Only set checked when it really is running; other transitions should not force checked
            try:
                btn.blockSignals(True)
                btn.setChecked(checked)
                btn.blockSignals(False)
            except Exception:
                pass

        # Now apply per-button styles to reflect enabled/available/running states
        for btn_name, btn_info in self.auto_procedure_buttons.items():
            btn = btn_info.get('button')
            if btn is None:
                continue

            running = (self.current_procedure == btn_name)
            enabled = btn.isEnabled()

            # Choose colors
            if running:
                bg = "#1da237"   # green
                fg = "#ffffff"
                border = "#178a2a"
            elif not enabled:
                bg = "#555555"   # grey
                fg = "#aaaaaa"
                border = "#444444"
            else:
                bg = "#ff8c00"   # yellow/orange (accessible)
                fg = "#ffffff"
                border = "#c86a00"

            # Apply an inline stylesheet so the whole button color changes
            try:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {bg}; color: {fg}; border: 2px solid {border}; font-weight: bold; }} "
                    f"QPushButton:checked {{ background: {bg}; color: {fg}; }} "
                    f"QPushButton:disabled {{ background: {bg}; color: {fg}; }}"
                )
            except Exception:
                pass

        # Update manual control buttons based on mode and connection
        manual_control_buttons = list(self.relay_map.keys())
        for btn_name in manual_control_buttons:
            btn = getattr(self, btn_name, None)
            if btn is not None:
                # Keep buttons enabled for visual feedback, but safety wrapper will prevent manual control during procedures
                btn.setEnabled(connection_state)

        # Special handling for btnCloseAll - determine enabled state first
        if hasattr(self, 'btnCloseAll') and self.btnCloseAll is not None:
            if self.current_procedure is not None:
                # If btnCloseAll is running, it should stay enabled
                # If another procedure is running, btnCloseAll should be disabled
                if self.current_procedure == 'btnCloseAll':
                    self.btnCloseAll.setEnabled(True)
                else:
                    self.btnCloseAll.setEnabled(False)
            else:
                # No procedure running - enable based on connection state
                self.btnCloseAll.setEnabled(connection_state)

            # Apply styling AFTER enabled state is set
            running = (self.current_procedure == 'btnCloseAll')
            enabled = self.btnCloseAll.isEnabled()

            # Choose colors (same as auto procedure buttons)
            if running:
                bg = "#1da237"   # green
                fg = "#ffffff"
                border = "#178a2a"
            elif not enabled:
                bg = "#555555"   # grey
                fg = "#aaaaaa"
                border = "#444444"
            else:
                bg = "#ff8c00"   # yellow/orange (accessible)
                fg = "#ffffff"
                border = "#c86a00"

            # Apply styling to btnCloseAll
            try:
                # Always apply color styling (same logic as auto procedure buttons)
                self.btnCloseAll.setStyleSheet(
                    f"QPushButton {{ background: {bg}; color: {fg}; border: 2px solid {border}; font-weight: bold; }} "
                    f"QPushButton:checked {{ background: {bg}; color: {fg}; }} "
                    f"QPushButton:disabled {{ background: {bg}; color: {fg}; }}"
                )
            except Exception:
                pass

        # Special handling for Ion Gauge - check if it's allowed in current mode
        if hasattr(self, 'btnIonGauge') and self.btnIonGauge is not None:
            ion_gauge_enabled = connection_state
            
            # Check if Ion Gauge is allowed in current mode
            if connection_state and hasattr(self, 'safety_controller') and self.safety_controller.safety_config:
                mode_restrictions = self.safety_controller.safety_config.get('mode_restrictions', {})
                current_mode_config = mode_restrictions.get(self.current_mode, {})
                
                # Check if explicitly forbidden
                forbidden_buttons = current_mode_config.get('forbidden_buttons', [])
                if 'btnIonGauge' in forbidden_buttons:
                    ion_gauge_enabled = False
                
                # Check if only specific buttons are allowed (Normal mode)
                allowed_buttons = current_mode_config.get('allowed_buttons', None)
                if allowed_buttons is not None and 'btnIonGauge' not in allowed_buttons:
                    ion_gauge_enabled = False
            
            self.btnIonGauge.setEnabled(ion_gauge_enabled)

    def _set_controls_enabled(self, enabled: bool) -> None:
        """Enable/disable controls based on connection state and mode restrictions."""
        if enabled:
            # If enabling, use mode-based operability logic
            self._update_auto_procedure_button_states()
        else:
            # If disabling (no connection), disable ALL buttons
            # Disable relay buttons
            for obj_name in self.relay_map.keys():
                w = getattr(self, obj_name, None)
                if w is not None:
                    w.setEnabled(False)
            
            # Disable special buttons
            if hasattr(self, 'btnCloseAll'):
                self.btnCloseAll.setEnabled(False)
            if hasattr(self, 'btnIonGauge'):
                self.btnIonGauge.setEnabled(False)
            
            # Disable automatic procedure buttons
            auto_procedure_buttons = ['pushButton_2', 'pushButton_3', 'pushButton_4', 'pushButton_5', 'pushButton_6']
            for btn_name in auto_procedure_buttons:
                btn = getattr(self, btn_name, None)
                if btn is not None:
                    btn.setEnabled(False)

    # --- Connection ---
    def auto_connect(self) -> None:
        print("DEBUG: Starting auto_connect...")
        if self.arduino is not None and self.arduino.is_connected:
            print("DEBUG: Already connected, calling on_connected...")
            self.on_connected()
            return
        if self.arduino is not None:
            # preferred ports can guide auto detection inside controller if supported
            print("DEBUG: Calling arduino.auto_connect()...")
            success = self.arduino.auto_connect()
            print(f"DEBUG: arduino.auto_connect() returned: {success}")
            if success:
                print("DEBUG: Connection successful, calling on_connected...")
                self.on_connected()
            else:
                print("DEBUG: Connection failed, calling on_disconnected...")
                self.on_disconnected()
        else:
            print("DEBUG: Arduino controller is None, cannot connect")
            self.on_disconnected()
        print("DEBUG: auto_connect completed")

    def on_connected(self) -> None:
        print("🔌 DEBUG: on_connected() - Arduino connection established")
        print("🔌 DEBUG: No relay operations should occur during initialization")
        self._set_controls_enabled(True)
        # Start timers (no verbose per-connection debug)
        self.status_timer.start()
        self.input_timer.start()
        
        # Start gas controller and MFC timer if available
        if self.gas_controller:
            try:
                self.gas_controller.start()
                # Set initial MFC timer interval based on current system state
                self.update_mfc_timer_interval()
                self.mfc_timer.start()
                # Initialize MFC cache with first reading
                QTimer.singleShot(1000, self.schedule_mfc_update)  # Start after 1 second
                print("DEBUG: Gas controller started and MFC timer activated")
            except Exception as e:
                print(f"DEBUG: Failed to start gas controller: {e}")

    def on_disconnected(self) -> None:
        self._set_controls_enabled(False)
        self.status_timer.stop()
        self.input_timer.stop()
        self.mfc_timer.stop()
        
        # Stop gas controller
        if self.gas_controller:
            try:
                self.gas_controller.stop()
                print("DEBUG: Gas controller stopped")
            except Exception as e:
                print(f"DEBUG: ❌ Error stopping gas controller: {e}")

    # --- Mode Management ---
    def show_mode_dialog(self) -> None:
        """Show the mode selection dialog."""
        # Get user level (default to 1 if no user logged in)
        user_level = self.current_user.get('admin_level', 1) if self.current_user else 1
        
        dialog = ModeSelectionDialog(self.current_mode, self, user_level=user_level)
        
        if dialog.exec() == ModeSelectionDialog.DialogCode.Accepted:
            new_mode = dialog.get_selected_mode()
            
            if new_mode != self.current_mode:
                self.current_mode = new_mode
                self._update_mode_display()
                self._update_auto_procedure_button_states()
                
                # Update safety controller with new mode
                self.update_safety_state()
                
                print(f"Mode changed to: {self.current_mode}")

    def get_current_mode(self) -> str:
        """Get the current operation mode."""
        return self.current_mode

    def _show_standby_dialog(self) -> None:
        """Show dialog asking if user wants to put system in standby after reaching default state."""
        reply = QMessageBox.question(
            self,
            "Put System in Standby?",
            "System is now in default state.\n\nWould you like to put the system in standby?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes  # Default to Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            print("User chose to put system in standby...")
            
            # Set current procedure to indicate standby procedure is running
            self.current_procedure = 'go_to_standby'
            self._update_auto_procedure_button_states()
            
            try:
                # Import the standby procedure
                try:
                    from .auto_procedures import go_to_standby
                except ImportError:
                    from auto_procedures import go_to_standby
                
                def on_standby_finished(success: bool, message: str) -> None:
                    """Handle completion of standby procedure."""
                    print(f"DEBUG: standby procedure finished: success={success}, message='{message}'")
                    
                    if success:
                        # Update system status to standby
                        self.set_system_status('standby')
                        print("System successfully put in standby state.")
                        QMessageBox.information(self, "Standby Complete", "System is now in standby state.")
                    else:
                        print(f"Failed to put system in standby: {message}")
                        QMessageBox.warning(self, "Standby Failed", f"Failed to put system in standby: {message}")
                    
                    # Clear current procedure and update button states
                    self._clear_current_procedure()
                
                # Create worker to run standby procedure in background
                worker = ProcedureWorker(go_to_standby, arduino=self.arduino, 
                                       safety=self.safety_controller, relay_map=self.relay_map)
                worker.signals.finished.connect(on_standby_finished)
                
                # Start worker via threadpool if available
                if hasattr(self, 'threadpool') and self.threadpool is not None:
                    self.threadpool.start(worker)
                else:
                    # Fallback: run synchronously
                    print("DEBUG: Running standby procedure synchronously (no threadpool)")
                    result = go_to_standby(arduino=self.arduino, safety=self.safety_controller, relay_map=self.relay_map)
                    on_standby_finished(builtins.bool(result), '' if result is True else str(result))
                    
            except ImportError:
                print("DEBUG: auto_procedures not available for standby")
                QMessageBox.critical(self, "Error", "Standby procedure not available.")
                self._clear_current_procedure()
            except Exception as e:
                print(f"DEBUG: Exception in standby procedure: {e}")
                QMessageBox.critical(self, "Standby Failed", f"Standby procedure failed: {e}")
                self._clear_current_procedure()
        else:
            print("User chose to keep system in default state.")

    # --- Button actions ---
    def on_toggle(self, btn, relay_num: int, checked: bool) -> None:
        if self.arduino is not None:
            ok = self.arduino.set_relay(relay_num, checked)
            if not ok:
                # revert UI state if failed
                btn.blockSignals(True)
                btn.setChecked(not checked)
                btn.blockSignals(False)
            else:
                # Immediately update safety state after successful relay operation
                self.update_safety_state()
                
                # Manage light bulb auto-off timer
                if hasattr(btn, 'objectName') and btn.objectName() == 'btnLightBulb':
                    if checked:
                        # Light turned ON - start 30 second auto-off timer
                        print("💡 Chamber light turned ON - will auto-off in 30 seconds")
                        self.light_timer.start()
                    else:
                        # Light turned OFF manually - stop the timer
                        print("💡 Chamber light turned OFF manually - cancelling auto-off timer")
                        self.light_timer.stop()
        else:
            print("DEBUG: Arduino controller is None, cannot toggle relay")
            # revert UI state
            btn.blockSignals(True)
            btn.setChecked(not checked)
            btn.blockSignals(False)

    def _auto_turn_off_light(self) -> None:
        """Automatically turn off the chamber light after timeout."""
        print("⏰ Auto-off timer expired - turning off chamber light")
        
        # Find the light bulb button and relay
        if not hasattr(self, 'btnLightBulb'):
            print("Warning: btnLightBulb not found")
            return
        
        relay_num = self.relay_map.get('btnLightBulb')
        if relay_num is None:
            print("Warning: btnLightBulb not in relay_map")
            return
        
        # Check if light is currently on
        if not self.btnLightBulb.isChecked():
            print("Light is already off, no action needed")
            return
        
        # Turn off the relay
        if self.arduino is not None:
            ok = self.arduino.set_relay(relay_num, False)
            if ok:
                # Update button state
                self.btnLightBulb.blockSignals(True)
                self.btnLightBulb.setChecked(False)
                self.btnLightBulb.blockSignals(False)
                
                # Update safety state
                self.update_safety_state()
                print("✅ Chamber light automatically turned OFF")
            else:
                print("❌ Failed to turn off chamber light")
        else:
            print("❌ Arduino controller not available")

    def close_all_relays(self) -> None:
        """Close all relays using proper shutdown sequence and update button states."""
        print("🏠 DEBUG: close_all_relays called - using go_to_default_state")
        
        if self.arduino is None:
            print("DEBUG: Arduino controller is None, skipping shutdown")
            QMessageBox.warning(self, "Cannot Close All", "Arduino not connected")
            return
        
        # Check if another procedure is already running
        if self.current_procedure is not None:
            QMessageBox.warning(self, "Procedure Running", 
                              "Another procedure is currently running. Please wait for it to complete.")
            return
        
        # Set current procedure and update button states to show it's running
        self.current_procedure = 'btnCloseAll'
        self._update_auto_procedure_button_states()
        
        try:
            # Import the proper shutdown function
            try:
                from .auto_procedures import go_to_default_state
            except ImportError:
                from auto_procedures import go_to_default_state
            
            def on_finished(success: bool, message: str) -> None:
                """Handle completion of close all procedure."""
                print(f"DEBUG: close_all_relays finished: success={success}, message='{message}'")
                
                if success:
                    # Update system status to default
                    self.set_system_status('default')
                    print("All relays closed using proper shutdown sequence.")
                    
                    # Show dialog asking if user wants to put system in standby
                    self._show_standby_dialog()
                else:
                    print("Failed to execute proper shutdown sequence - falling back to emergency all off.")
                    # Fallback to emergency all off
                    try:
                        emergency_success = self.arduino.all_relays_off()
                        if emergency_success:
                            self.set_system_status('standby')
                            print("Emergency all relays off completed.")
                        else:
                            print("Emergency all relays off failed.")
                            QMessageBox.critical(self, "Shutdown Failed", 
                                               "Both normal and emergency shutdown procedures failed.")
                    except Exception as e:
                        print(f"Emergency shutdown also failed: {e}")
                        QMessageBox.critical(self, "Shutdown Failed", 
                                           f"Shutdown procedures failed: {e}")
                
                # Clear current procedure and update button states
                self._clear_current_procedure()
                
                # Always refresh UI state regardless of success/failure
                try:
                    self.refresh_status()
                except Exception as e:
                    print(f"DEBUG: Failed to refresh status: {e}")
                    # If refresh fails, manually update button states to OFF
                    for obj_name in self.relay_map.keys():
                        btn = getattr(self, obj_name, None)
                        if btn is not None:
                            btn.blockSignals(True)
                            btn.setChecked(False)
                            btn.blockSignals(False)

            # Create worker to run shutdown procedure in background
            worker = ProcedureWorker(go_to_default_state, arduino=self.arduino, 
                                   safety=self.safety_controller, relay_map=self.relay_map)
            worker.signals.finished.connect(on_finished)

            # Start worker via threadpool if available
            if hasattr(self, 'threadpool') and self.threadpool is not None:
                self.threadpool.start(worker)
            else:
                # Fallback: run synchronously
                print("DEBUG: Running close_all synchronously (no threadpool)")
                result = go_to_default_state(arduino=self.arduino, safety=self.safety_controller, relay_map=self.relay_map)
                on_finished(builtins.bool(result), '' if result is True else str(result))
                
        except ImportError:
            print("DEBUG: auto_procedures not available, using emergency all_relays_off")
            try:
                success = self.arduino.all_relays_off()
                if success:
                    self.set_system_status('standby')
                    print("Emergency all relays off completed.")
                else:
                    print("Emergency all relays off failed.")
                    QMessageBox.critical(self, "Shutdown Failed", "Emergency shutdown failed.")
            except Exception as e:
                print(f"Emergency shutdown failed: {e}")
                QMessageBox.critical(self, "Shutdown Failed", f"Emergency shutdown failed: {e}")
            finally:
                self._clear_current_procedure()
                
        except Exception as e:
            print(f"DEBUG: Exception in close_all_relays: {e}")
            QMessageBox.critical(self, "Shutdown Failed", f"Shutdown procedure failed: {e}")
            self._clear_current_procedure()

    def _wire_buttons(self) -> None:
        """Wire standard relay buttons to their handlers (safety-wrapped)."""
        for obj_name, relay_num in self.relay_map.items():
            btn = getattr(self, obj_name, None)
            if btn is None:
                continue
            try:
                btn.setCheckable(True)
            except Exception:
                pass

            # Skip wiring persistent toggle handler for ion gauge: it is momentary/pulse-controlled
            if obj_name == 'btnIonGauge':
                continue

            def create_handler(button_name, relay_number, button_widget):
                def original_handler(checked):
                    self.on_toggle(button_widget, relay_number, checked)
                return lambda checked: self.safe_button_click(button_name, original_handler, checked)

            try:
                btn.clicked.connect(create_handler(obj_name, relay_num, btn))
            except Exception:
                pass

    def _wire_mode_button(self) -> None:
        """Wire the mode toggle button."""
        if hasattr(self, 'btnModeToggle'):
            try:
                # Hide mode button for Level 1 (Operator) users
                user_level = self.current_user.get('admin_level', 1) if self.current_user else 1
                
                if user_level == 1:
                    self.btnModeToggle.hide()
                    print("👤 Mode button hidden for Level 1 (Operator) user")
                else:
                    self.btnModeToggle.clicked.connect(self.show_mode_dialog)
            except Exception:
                pass

    def _wire_special_buttons(self) -> None:
        """Wire special function buttons like Close All and Ion Gauge."""
        # Wire Close All button (no safety check needed - it's a safety feature)
        if hasattr(self, 'btnCloseAll'):
            try:
                self.btnCloseAll.clicked.connect(self.close_all_relays)
            except Exception:
                pass

        # Wire Ion Gauge button with safety wrapper
        if hasattr(self, 'btnIonGauge'):
            def ion_gauge_handler():
                self.toggle_ion_gauge()

            try:
                self.btnIonGauge.clicked.connect(
                    lambda: self.safe_button_click('btnIonGauge', ion_gauge_handler)
                )
                # Set an initial placeholder text; actual state shown from analog in refresh_inputs
                self.btnIonGauge.setText("Ion\nGauge:\n---")
            except Exception:
                pass

    def _wire_auto_procedure_buttons(self) -> None:
        """Wire automatic procedure buttons to their handlers."""
        auto_procedures = {
            'pushButton_2': ('PUMP', 'pump_procedure', self.run_pump_procedure),
            'pushButton_3': ('VENT', 'vent_procedure', self.run_vent_procedure),
            'pushButton_4': ('VENT Load-lock', 'vent_loadlock_procedure', self.run_vent_loadlock_procedure),
            'pushButton_5': ('Load/Unload', 'load_unload_procedure', self.run_load_unload_procedure),
            'pushButton_6': ('SPUTTER', 'sputter_procedure', self.run_sputter_procedure)
        }

        # Populate auto_procedure_buttons with GUI buttons and special procedures
        for btn_name, (display_name, procedure_key, method) in auto_procedures.items():
            btn = getattr(self, btn_name, None)
            if btn is not None:
                try:
                    btn.setCheckable(True)
                except Exception:
                    pass

                # Store button ref and procedure info using button name as key
                self.auto_procedure_buttons[btn_name] = {
                    'button': btn,
                    'procedure_name': display_name,
                    'procedure_key': procedure_key,
                    'method': method,
                    'type': 'gui_button'
                }

        # Add special procedures that don't have GUI buttons
        self.auto_procedure_buttons.update({
            'btnCloseAll': {
                'button': getattr(self, 'btnCloseAll', None),
                'procedure_name': 'Close All Relays',
                'procedure_key': 'close_all',
                'method': self.close_all_relays,
                'type': 'special_button'
            },
            'go_to_standby': {
                'button': None,
                'procedure_name': 'Go to Standby',
                'procedure_key': 'go_to_standby',
                'method': None,  # Handled internally
                'type': 'internal_procedure'
            },
            'go_to_default_state': {
                'button': None,
                'procedure_name': 'Go to Default State',
                'procedure_key': 'go_to_default_state',
                'method': None,  # Handled internally
                'type': 'internal_procedure'
            }
        })
        
        # Add menu-initiated procedures (populated dynamically when menu procedures run)
        for function_name in ['pump_procedure', 'vent_procedure', 'sputter_procedure', 'vent_loadlock_procedure', 'load_unload_procedure', 'go_to_standby', 'go_to_default_state']:
            menu_key = f"menu_{function_name}"
            self.auto_procedure_buttons[menu_key] = {
                'button': None,
                'procedure_name': f'Menu: {function_name.replace("_", " ").title()}',
                'procedure_key': function_name,
                'method': None,  # Handled by menu system
                'type': 'menu_procedure'
            }

        # Wire the GUI button handlers
        for btn_name, (display_name, procedure_key, method) in auto_procedures.items():
            btn = getattr(self, btn_name, None)
            if btn is not None:
                # Create handler that reverts the button checked state if the procedure cannot start.
                def create_handler(button_widget, button_name, proc_display_name, proc_key, proc_method):
                    def handler():
                        # If currently running this procedure, that click is a cancel request
                        if self.current_procedure == button_name:
                            self.cancel_auto_procedure(button_name, proc_display_name)
                            return

                        # Check if procedure can be started using the correct procedure key
                        can_start = False
                        try:
                            can_start = self.can_start_procedure(proc_key)
                        except Exception:
                            can_start = False

                        if not can_start:
                            # Revert visual checked state immediately so the button never appears running
                            try:
                                button_widget.blockSignals(True)
                                button_widget.setChecked(False)
                                button_widget.blockSignals(False)
                            except Exception:
                                pass
                            QMessageBox.warning(self, "Cannot Start Procedure",
                                                f"Cannot start {proc_display_name} procedure in current system state: {self.system_status}")
                            # Also refresh styles to ensure consistent appearance
                            self._update_auto_procedure_button_states()
                            return

                        # Start the procedure (proc_method is responsible for setting current_procedure)
                        proc_method()

                    return handler

                try:
                    btn.clicked.connect(create_handler(btn, btn_name, display_name, procedure_key, method))
                except Exception:
                    pass

    def _wire_mfc_controls(self) -> None:
        """Wire MFC layout click events to show setpoint dialogs."""
        print("DEBUG: _wire_mfc_controls called")
        if not self.gas_controller:
            print("DEBUG: No gas controller available, skipping MFC control wiring")
            return
            
        print(f"DEBUG: Gas controller channels: {list(self.gas_controller.channels.keys())}")
        
        # Get MFC configurations from the gas controller
        for mfc_id in self.gas_controller.channels.keys():
            # Wire both read and setpoint LCD widgets for each MFC
            widget_names = [f"{mfc_id}_read", f"{mfc_id}_setpoint"]
            
            for widget_name in widget_names:
                widget = getattr(self, widget_name, None)
                if widget:
                    print(f"DEBUG: Found widget {widget_name} for MFC {mfc_id}")
                    # Create a simple click handler
                    def create_click_handler(mfc_name):
                        def handler(event):
                            print(f"DEBUG: Click handler triggered for {mfc_name}")
                            self._show_mfc_setpoint_dialog(mfc_name)
                        return handler
                    
                    # Connect mousePressEvent to the LCD widget
                    try:
                        click_handler = create_click_handler(mfc_id)
                        widget.mousePressEvent = click_handler
                        print(f"DEBUG: Successfully wired click handler for {widget_name}")
                    except Exception as e:
                        print(f"DEBUG: Failed to wire {widget_name}: {e}")
                else:
                    print(f"DEBUG: Widget {widget_name} not found for MFC {mfc_id}")

    def _show_mfc_setpoint_dialog(self, mfc_id: str) -> None:
        """Show setpoint dialog for the specified MFC."""
        # Only allow gas flow setting when system is in sputter state
        if self.system_status != 'sputter':
            QMessageBox.information(
                self,
                "Gas Flow Control Restricted",
                f"Gas flow can only be adjusted when the system is in sputter state.\n\n"
                f"Current system state: {self.system_status.replace('_', ' ').title()}"
            )
            return
            
        if not self.gas_controller:
            print(f"DEBUG: No gas controller available for {mfc_id}")
            # Still show dialog with default values for testing
            new_setpoint = show_mfc_setpoint_dialog(mfc_id, 0.0, 200.0, self)
            if new_setpoint is not None:
                print(f"DEBUG: Would set {mfc_id} to {new_setpoint} (no controller)")
            return
            
        # Get current setpoint from cache first (fast), fallback to reading if needed
        current_setpoint = 0.0
        cached_reading = self.mfc_readings_cache.get(mfc_id)
        print(f"DEBUG: Cached reading for {mfc_id}: {cached_reading}")
        
        if cached_reading and 'setpoint' in cached_reading:
            current_setpoint = cached_reading['setpoint']
            print(f"DEBUG: Using cached setpoint for {mfc_id}: {current_setpoint}")
        else:
            # Only do blocking read if no cache available
            print(f"DEBUG: No cache for {mfc_id}, attempting direct read...")
            try:
                reading = self.gas_controller.get_reading(mfc_id)
                current_setpoint = reading.setpoint if reading else 0.0
                print(f"DEBUG: Direct read setpoint for {mfc_id}: {current_setpoint}")
            except Exception as e:
                print(f"Failed to get current setpoint for {mfc_id}: {e}")
                current_setpoint = 0.0
        
        print(f"DEBUG: Final current_setpoint for dialog: {current_setpoint}")
        
        # Show dialog using the imported function with controllers for valve operation
        new_setpoint = show_mfc_setpoint_dialog(
            mfc_id, current_setpoint, 200.0, self,
            arduino_controller=self.arduino,
            safety_controller=self.safety_controller,
            relay_map=self.relay_map
        )
        
        if new_setpoint is not None:
            # Apply new setpoint in background to avoid blocking GUI
            self.set_mfc_setpoint_background(mfc_id, new_setpoint)

    def set_mfc_setpoint_background(self, mfc_id: str, setpoint: float) -> None:
        """Set MFC setpoint in background thread to avoid blocking GUI."""
        print(f"DEBUG: Setting {mfc_id} setpoint to {setpoint} in background")
        
        def set_setpoint_worker():
            """Background function to set MFC setpoint."""
            try:
                success = self.gas_controller.set_flow_rate(mfc_id, setpoint)
                return {'success': success, 'mfc_id': mfc_id, 'setpoint': setpoint}
            except Exception as e:
                return {'success': False, 'error': str(e), 'mfc_id': mfc_id, 'setpoint': setpoint}
        
        class SetpointSignals(QObject):
            finished = pyqtSignal(dict)
        
        class SetpointWorker(QRunnable):
            def __init__(self, worker_function):
                super().__init__()
                self.worker_function = worker_function
                self.signals = SetpointSignals()
                
            def run(self):
                result = self.worker_function()
                self.signals.finished.emit(result)
        
        # Create and start the background worker
        worker = SetpointWorker(set_setpoint_worker)
        worker.signals.finished.connect(self.on_setpoint_update_complete)
        
        if hasattr(self, 'threadpool') and self.threadpool is not None:
            self.threadpool.start(worker)
        else:
            # Fallback: show warning and do synchronous operation
            print("WARNING: No threadpool available, setpoint update may block GUI")
            try:
                success = self.gas_controller.set_flow_rate(mfc_id, setpoint)
                if not success:
                    QMessageBox.warning(self, "❌ Error", f"Failed to set {mfc_id} flow rate to {setpoint}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error setting {mfc_id} flow rate: {str(e)}")

    def on_setpoint_update_complete(self, result: dict) -> None:
        """Handle completion of setpoint update (runs in main thread)."""
        if result['success']:
            print(f"Successfully set {result['mfc_id']} setpoint to {result['setpoint']}")
            
            # Clear cache for this MFC to force fresh reading
            if result['mfc_id'] in self.mfc_readings_cache:
                print(f"DEBUG: Clearing cache for {result['mfc_id']} after setpoint update")
                del self.mfc_readings_cache[result['mfc_id']]
            
            # Implement aggressive polling after setpoint change
            self.start_aggressive_polling_after_setpoint(result['mfc_id'], result['setpoint'])
            
        else:
            error_msg = result.get('error', 'Unknown error')
            # Check if it's a timeout error and provide more helpful message
            if 'timeout' in error_msg.lower() or 'Command timeout' in error_msg:
                QMessageBox.warning(self, "MFC Communication Timeout", 
                                  f"MFC setpoint command timed out for {result['mfc_id']}.\n\n"
                                  f"This may indicate a communication issue with the MFC hardware.\n"
                                  f"Check the MFC connection and try again.\n\n"
                                  f"Note: Arduino and MFC use separate serial ports, so no interference expected.")
            else:
                QMessageBox.warning(self, "Error", f"Failed to set {result['mfc_id']} flow rate to {result['setpoint']}: {error_msg}")

    def start_aggressive_polling_after_setpoint(self, mfc_id: str, target_setpoint: float) -> None:
        """Start aggressive polling after setpoint change to get faster feedback."""
        print(f"DEBUG: Starting aggressive polling for {mfc_id} expecting setpoint {target_setpoint}")
        
        # Initialize polling state
        if not hasattr(self, 'aggressive_polling_state'):
            self.aggressive_polling_state = {}
        
        self.aggressive_polling_state[mfc_id] = {
            'target_setpoint': target_setpoint,
            'retry_count': 0,
            'max_retries': 15,  # Poll for up to 15 times
            'interval_ms': 500  # Every 500ms
        }
        
        # Start first poll immediately
        QTimer.singleShot(500, lambda: self.aggressive_poll_mfc(mfc_id))

    def aggressive_poll_mfc(self, mfc_id: str) -> None:
        """Poll a specific MFC aggressively after setpoint change."""
        if not hasattr(self, 'aggressive_polling_state') or mfc_id not in self.aggressive_polling_state:
            return
        
        state = self.aggressive_polling_state[mfc_id]
        state['retry_count'] += 1
        
        print(f"DEBUG: Aggressive poll #{state['retry_count']} for {mfc_id}")
        
        # Try to get fresh reading
        try:
            reading = self.gas_controller.get_reading(mfc_id)
            if reading:
                # Update cache immediately
                self.mfc_readings_cache[mfc_id] = {
                    'mass_flow': reading.mass_flow,
                    'setpoint': reading.setpoint,
                    'timestamp': reading.timestamp
                }
                print(f"DEBUG: Aggressive poll got reading - Setpoint: {reading.setpoint}, Flow: {reading.mass_flow}")
                
                # Check if setpoint has updated to target value
                if abs(reading.setpoint - state['target_setpoint']) < 0.1:
                    print(f"DEBUG: MFC {mfc_id} setpoint confirmed updated to {reading.setpoint}, stopping aggressive polling")
                    # Force GUI update immediately
                    self.update_mfc_displays()
                    # Clean up polling state
                    del self.aggressive_polling_state[mfc_id]
                    return
                
        except Exception as e:
            print(f"DEBUG: Error in aggressive poll for {mfc_id}: {e}")
        
        # Continue polling if not done and retries remaining
        if state['retry_count'] < state['max_retries']:
            QTimer.singleShot(state['interval_ms'], lambda: self.aggressive_poll_mfc(mfc_id))
        else:
            print(f"DEBUG: Aggressive polling for {mfc_id} completed after {state['retry_count']} attempts")
            # Clean up polling state
            del self.aggressive_polling_state[mfc_id]
            # Force one final GUI update
            self.update_mfc_displays()

    def schedule_mfc_update(self) -> None:
        """Schedule MFC reading update in background to avoid blocking GUI."""
        if not self.gas_controller or self.mfc_update_in_progress:
            return
            
        interval_ms = self.mfc_timer.interval() if hasattr(self, 'mfc_timer') else 5000
        #print(f"DEBUG: Scheduling background MFC update (system_status={self.system_status}, interval={interval_ms}ms)")
        self.mfc_update_in_progress = True
        
        # Use QTimer.singleShot to defer the actual update to prevent blocking
        QTimer.singleShot(0, self.update_mfc_readings_background)

    def update_mfc_readings_background(self) -> None:
        """Update MFC readings in background using ThreadPool."""
        if not self.gas_controller:
            self.mfc_update_in_progress = False
            return
            
        # Create a worker to fetch MFC readings without blocking GUI
        def fetch_mfc_readings():
            """Background function to fetch MFC readings."""
            readings = {}
            try:
                for mfc_id in self.gas_controller.channels.keys():
                    try:
                        # This is the potentially blocking operation
                        reading = self.gas_controller.get_reading(mfc_id)
                        if reading:
                            readings[mfc_id] = {
                                'mass_flow': reading.mass_flow,
                                'setpoint': reading.setpoint,
                                'timestamp': reading.timestamp
                            }
                    except Exception as e:
                        print(f"DEBUG: Error reading MFC {mfc_id}: {e}")
                        readings[mfc_id] = None
            except Exception as e:
                print(f"DEBUG: Error in fetch_mfc_readings: {e}")
            return readings
        
        # Create signals for the background worker
        class MFCUpdateSignals(QObject):
            finished = pyqtSignal(dict)
        
        class MFCUpdateWorker(QRunnable):
            def __init__(self, fetch_function):
                super().__init__()
                self.fetch_function = fetch_function
                self.signals = MFCUpdateSignals()
                
            def run(self):
                try:
                    readings = self.fetch_function()
                    self.signals.finished.emit(readings)
                except Exception as e:
                    print(f"DEBUG: Exception in MFC worker: {e}")
                    self.signals.finished.emit({})
        
        # Create and start the background worker
        worker = MFCUpdateWorker(fetch_mfc_readings)
        worker.signals.finished.connect(self.on_mfc_readings_updated)
        
        if hasattr(self, 'threadpool') and self.threadpool is not None:
            self.threadpool.start(worker)
        else:
            # Fallback: run in main thread but warn user
            print("WARNING: No threadpool available, MFC update may block GUI")
            QTimer.singleShot(0, lambda: self.on_mfc_readings_updated(fetch_mfc_readings()))

    def on_mfc_readings_updated(self, readings: dict) -> None:
        """Update GUI with cached MFC readings (runs in main thread)."""
        # if readings:  # Only print debug if we actually got new readings
        #     print(f"DEBUG: MFC cache updated with {len(readings)} channels")
        self.mfc_update_in_progress = False
        
        # Update cache
        self.mfc_readings_cache.update(readings)
        
        # Update GUI displays with cached data
        self.update_mfc_displays_from_cache()

    def update_mfc_displays_from_cache(self) -> None:
        """Update MFC displays using cached readings (fast, non-blocking)."""
        if not self.gas_controller:
            return
            
        try:
            for mfc_id in self.gas_controller.channels.keys():
                cached_reading = self.mfc_readings_cache.get(mfc_id)
                if cached_reading:
                    # Update read flow display (e.g., "Ar_read", "O2_read")
                    read_widget_name = f"{mfc_id}_read"
                    read_widget = getattr(self, read_widget_name, None)
                    if read_widget:
                        read_widget.display(f"{cached_reading['mass_flow']:.1f}")
                    
                    # Update setpoint display (e.g., "Ar_setpoint", "O2_setpoint")
                    setpoint_widget_name = f"{mfc_id}_setpoint"
                    setpoint_widget = getattr(self, setpoint_widget_name, None)
                    if setpoint_widget:
                        setpoint_widget.display(f"{cached_reading['setpoint']:.1f}")
                        
        except Exception as e:
            # Reduce debug verbosity since this now runs every 700ms
            pass

    def update_mfc_displays(self) -> None:
        """Legacy method - now just updates from cache if available."""
        print("DEBUG: update_mfc_displays called (using cache)")
        self.update_mfc_displays_from_cache()

    def update_mfc_timer_interval(self) -> None:
        """Update MFC timer interval based on current system state."""
        if not self.gas_controller or not hasattr(self, 'mfc_timer'):
            return
            
        # Use 1-second interval during sputter state for more frequent monitoring
        if self.system_status == 'sputter':
            new_interval = 1000  # 1 second
            print("DEBUG: Setting MFC timer to 1s interval (sputter state)")
        else:
            new_interval = 5000  # 5 seconds
            print("DEBUG: Setting MFC timer to 5s interval (normal state)")
        
        # Only update if interval has changed to avoid unnecessary timer restarts
        if self.mfc_timer.interval() != new_interval:
            was_active = self.mfc_timer.isActive()
            if was_active:
                self.mfc_timer.stop()
            self.mfc_timer.setInterval(new_interval)
            if was_active:
                self.mfc_timer.start()

    def start_sputter_mfc_flows(self) -> None:
        """Start MFC flows for sputter procedure (if configured) - non-blocking."""
        if not self.gas_controller:
            return
            
        print("DEBUG: Starting sputter MFC flows in background")
        
        def set_sputter_flows_worker():
            """Background function to set sputter flows."""
            results = []
            try:
                # Check if there are any default sputter flow rates configured
                sputter_flows = getattr(self.cfg.gas_control, 'sputter_flows', {})
                
                for mfc_id, flow_rate in sputter_flows.items():
                    if mfc_id in self.gas_controller.channels:
                        print(f"Setting sputter flow for {mfc_id}: {flow_rate} sccm")
                        try:
                            success = self.gas_controller.set_flow_rate(mfc_id, flow_rate)
                            results.append({'mfc_id': mfc_id, 'flow_rate': flow_rate, 'success': success})
                        except Exception as e:
                            results.append({'mfc_id': mfc_id, 'flow_rate': flow_rate, 'success': False, 'error': str(e)})
                            
            except Exception as e:
                print(f"❌ Error in sputter flows worker: {e}")
            return results
        
        # Use threadpool if available, otherwise just print a message
        if hasattr(self, 'threadpool') and self.threadpool is not None:
            class SputterFlowWorker(QRunnable):
                def run(self):
                    set_sputter_flows_worker()
            
            worker = SputterFlowWorker()
            self.threadpool.start(worker)
        else:
            # Non-blocking fallback using QTimer
            QTimer.singleShot(0, lambda: set_sputter_flows_worker())

    def stop_all_mfc_flows(self) -> None:
        """Stop all MFC flows (set to 0) - non-blocking."""
        if not self.gas_controller:
            return
            
        print("DEBUG: Stopping all MFC flows in background")
        
        def stop_flows_worker():
            """Background function to stop all flows."""
            try:
                for mfc_id in self.gas_controller.channels.keys():
                    print(f"Stopping flow for {mfc_id}")
                    try:
                        success = self.gas_controller.set_flow_rate(mfc_id, 0.0)
                        if not success:
                            print(f"Warning: Failed to stop flow for {mfc_id}")
                    except Exception as e:
                        print(f"❌ Error stopping flow for {mfc_id}: {e}")
                        
            except Exception as e:
                print(f"❌ Error stopping MFC flows: {e}")
        
        # Use threadpool if available, otherwise use QTimer for non-blocking operation
        if hasattr(self, 'threadpool') and self.threadpool is not None:
            class StopFlowWorker(QRunnable):
                def run(self):
                    stop_flows_worker()
            
            worker = StopFlowWorker()
            self.threadpool.start(worker)
        else:
            # Non-blocking fallback using QTimer
            QTimer.singleShot(0, lambda: stop_flows_worker())

    def test_mfc_integration(self) -> None:
        """Test function to check MFC integration status."""
        print("=== MFC Integration Test ===")
        print(f"Gas controller available: {self.gas_controller is not None}")
        
        if self.gas_controller:
            print(f"Gas controller channels: {list(self.gas_controller.channels.keys())}")
            
            # Test widget availability
            test_widgets = ['Ar_read', 'Ar_setpoint', 'N2_read', 'N2_setpoint', 'O2_read', 'O2_setpoint']
            for widget_name in test_widgets:
                widget = getattr(self, widget_name, None)
                print(f"Widget {widget_name}: {'Found' if widget else 'Not found'}")
                
            # Test MFC wiring
            self._wire_mfc_controls()
            
            # Test non-blocking display update
            print("Testing non-blocking MFC update...")
            self.schedule_mfc_update()
            
            # Show cached readings if available
            if self.mfc_readings_cache:
                print("Cached MFC readings:")
                for mfc_id, reading in self.mfc_readings_cache.items():
                    print(f"  {mfc_id}: {reading}")
            else:
                print("No cached readings available yet")
        else:
            print("Gas controller not available - checking config...")
            print(f"Config has gas_control: {hasattr(self.cfg, 'gas_control') and self.cfg.gas_control is not None}")
            if hasattr(self.cfg, 'gas_control'):
                print(f"Gas control config: {self.cfg.gas_control}")
        
        print("=== End MFC Test ===")

    def toggle_ion_gauge(self) -> None:
        """Toggle the ion gauge relay and update button text."""
        # Ion gauge is toggled via a momentary pulse to the relay. The actual
        # ON/OFF state is determined by the analog voltage on ai_volts[2].
        if not hasattr(self, 'btnIonGauge'):
            return

        relay_num = self.relay_map.get('btnIonGauge')
        if relay_num is None:
            QMessageBox.critical(self, "Error", "Ion gauge relay not configured")
            return

        if self.arduino is None:
            QMessageBox.critical(self, "Error", "Arduino not connected")
            return

        # Pulse the relay for 1 second (1000 ms). Do not change the checked state
        # here; the UI reflects actual gauge state from analog readings in refresh_inputs.
        print(f"DEBUG: Pulsing ion gauge relay {relay_num} for 1s")
        self._pulse_relay(relay_num, 1000, btn_name='btnIonGauge')

    def _pulse_relay(self, relay_num: int, duration_ms: int, btn_name: Optional[str] = None) -> None:
        """Pulse a relay ON for duration_ms milliseconds, then turn it OFF.

        This method is safe to call from the GUI thread. It uses the ArduinoController
        to set the relay and schedules a QTimer.singleShot to clear it.
        """
        if self.arduino is None:
            print("DEBUG: _pulse_relay called but arduino is None")
            return

        try:
            # Set relay ON
            ok_on = self.arduino.set_relay(relay_num, True)
            print(f"DEBUG: _pulse_relay set_relay({relay_num}, True) -> {ok_on}")
            if not ok_on:
                QMessageBox.critical(self, "Error", f"Failed to pulse relay {relay_num} ON")
                return

            # Schedule turning it OFF after duration
            def turn_off():
                try:
                    ok_off = True
                    if self.arduino is not None:
                        ok_off = self.arduino.set_relay(relay_num, False)
                    print(f"DEBUG: _pulse_relay set_relay({relay_num}, False) -> {ok_off}")
                    if not ok_off:
                        print(f"DEBUG: Failed to turn off relay {relay_num} after pulse")
                except Exception as e:
                    print(f"DEBUG: Exception while turning off relay {relay_num}: {e}")
                finally:
                    # After pulse completes, refresh status and inputs so UI reflects true state
                    try:
                        self.refresh_status()
                        self.refresh_inputs()
                    except Exception:
                        pass

            QTimer.singleShot(duration_ms, turn_off)
        except Exception as e:
            print(f"DEBUG: Exception in _pulse_relay: {e}")

    # --- Automatic Procedures ---
    def run_pump_procedure(self) -> None:
        """Run the automatic pump procedure."""
        print("Running PUMP procedure...")
        
        # Check if procedure can be started
        if not self.can_start_procedure('pump_procedure'):
            QMessageBox.warning(self, "Cannot Start Procedure", 
                              f"Cannot start pump procedure in current system state: {self.system_status}")
            return
        
        # Set current procedure and update system status
        self.current_procedure = 'pushButton_2'
        self.set_system_status('pumping')  # Set to pumping state
        self._update_auto_procedure_button_states()
        
        try:
            try:
                from .auto_procedures import pump_procedure
            except ImportError:
                from auto_procedures import pump_procedure

            def on_finished(success: bool, message: str) -> None:
                # This handler runs in the main thread via signal
                if success:
                    QMessageBox.information(self, "Success", "Pump procedure completed successfully!")
                    # Set system status BEFORE clearing current procedure
                    self.set_system_status('high_vacuum')
                    # Update safety controller with completed state
                    self.update_safety_state()
                    # Small delay to ensure state is properly set
                    QTimer.singleShot(100, lambda: self._clear_current_procedure())
                else:
                    if message:
                        QMessageBox.warning(self, "Procedure Failed", f"Pump procedure failed: {message}")
                    else:
                        QMessageBox.warning(self, "Procedure Failed", "Pump procedure failed. Check console for details.")
                    self.set_system_status(self.previous_system_status)
                    self._clear_current_procedure()

            # Create worker to run procedure in background
            worker = ProcedureWorker(pump_procedure, arduino=self.arduino, safety=self.safety_controller, relay_map=self.relay_map)
            worker.signals.finished.connect(on_finished)

            # Start worker via threadpool if available
            if hasattr(self, 'threadpool') and self.threadpool is not None:
                self.threadpool.start(worker)
            else:
                # Fallback: run synchronously
                result = pump_procedure(arduino=self.arduino, safety=self.safety_controller, relay_map=self.relay_map)
                on_finished(builtins.bool(result), '' if result is True else str(result))
        except ImportError:
            QMessageBox.critical(self, "Error", "Auto procedures module not found.")
            self.set_system_status(self.previous_system_status)
            self._clear_current_procedure()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Pump procedure failed: {str(e)}")
            self.set_system_status(self.previous_system_status)
            self._clear_current_procedure()

    def _clear_current_procedure(self):
        """Helper method to clear current procedure and update UI."""
        self.current_procedure = None
        # Clear procedure state override in safety controller
        try:
            if hasattr(self.safety_controller, 'clear_procedure_state_override'):
                self.safety_controller.clear_procedure_state_override()
            else:
                self.safety_controller.current_procedure = None
            # Allow automatic state determination to resume
            self.update_safety_state()
        except Exception:
            pass
        self._update_auto_procedure_button_states()

    def run_vent_procedure(self) -> None:
        """Run the automatic vent procedure."""
        print("Running VENT procedure...")
        
        # Check if procedure can be started
        if not self.can_start_procedure('vent_procedure'):
            QMessageBox.warning(self, "Cannot Start Procedure", 
                              f"Cannot start vent procedure in current system status: {self.system_status}")
            return
        
        # Set current procedure and update system status
        self.current_procedure = 'pushButton_3'
        self.set_system_status('venting')  # Set to venting state
        self._update_auto_procedure_button_states()
        
        # Confirmation dialog: require explicit user consent before venting
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
        from PyQt5.QtCore import Qt

        dialog = QDialog(self)
        dialog.setWindowTitle("CONFIRM VENTING")
        dialog.setModal(True)
        layout = QVBoxLayout()

        msg = QLabel("CONFIRM THAT THE DOOR LATCHES HAVE BEEN REMOVED FIRST BEFORE VENTING!  ")
        msg.setWordWrap(True)
        msg.setAlignment(Qt.AlignCenter)
        msg.setStyleSheet("QLabel { color: red; font-weight: bold; font-size: 18pt; }")
        layout.addWidget(msg)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        ok_btn = QPushButton("I CONFIRM")
        ok_btn.setDefault(True)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        dialog.setLayout(layout)

        confirmed = False
        def on_ok():
            nonlocal confirmed
            confirmed = True
            dialog.accept()

        def on_cancel():
            dialog.reject()

        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(on_cancel)

        # Show dialog larger than typical by resizing
        dialog.resize(700, 200)
        if dialog.exec() != QDialog.Accepted or not confirmed:
            print("Vent procedure cancelled by user")
            self._clear_current_procedure()
            return

        try:
            try:
                from .auto_procedures import vent_procedure
            except ImportError:
                from auto_procedures import vent_procedure

            def on_finished(success: bool, message: str) -> None:
                if success:
                    QMessageBox.information(self, "Success", "Vent procedure completed successfully!")
                    self.set_system_status('vented')
                    self.update_safety_state()
                    QTimer.singleShot(100, lambda: self._clear_current_procedure())
                else:
                    if message:
                        QMessageBox.warning(self, "Procedure Failed", f"Vent procedure failed: {message}")
                    else:
                        QMessageBox.warning(self, "Procedure Failed", "Vent procedure failed. Check console for details.")
                    self.set_system_status(self.previous_system_status)
                    self._clear_current_procedure()

            worker = ProcedureWorker(vent_procedure, arduino=self.arduino, safety=self.safety_controller, relay_map=self.relay_map)
            worker.signals.finished.connect(on_finished)
            if hasattr(self, 'threadpool') and self.threadpool is not None:
                self.threadpool.start(worker)
            else:
                result = vent_procedure(arduino=self.arduino, safety=self.safety_controller, relay_map=self.relay_map)
                on_finished(builtins.bool(result), '' if result is True else str(result))
        except ImportError:
            QMessageBox.critical(self, "Error", "Auto procedures module not found.")
            self.set_system_status(self.previous_system_status)
            self._clear_current_procedure()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Vent procedure failed: {str(e)}")
            self.set_system_status(self.previous_system_status)
            self._clear_current_procedure()

    def run_sputter_procedure(self) -> None:
        """Run the automatic sputter procedure."""
        print("Running SPUTTER procedure...")
        
        # Check if procedure can be started
        if not self.can_start_procedure('sputter_procedure'):
            QMessageBox.warning(self, "Cannot Start Procedure", 
                              f"Cannot start sputter procedure in current system state: {self.system_status}")
            return
        
        # Set current procedure and update system status
        print(f"DEBUG: Setting current_procedure = 'pushButton_6'")
        self.current_procedure = 'pushButton_6'
        # Align with safety_conditions.yml state name 'sputter'
        print(f"DEBUG: Setting system status to 'sputter'")
        self.set_system_status('sputter')  # Set to sputter state
        self._update_auto_procedure_button_states()
        
        # Update safety state immediately after setting procedure
        print(f"DEBUG: Updating safety state after setting procedure")
        self.update_safety_state()
        
        # Start MFC flows for sputter procedure (if configured)
        self.start_sputter_mfc_flows()
        
        try:
            try:
                from .auto_procedures import sputter_procedure
            except ImportError:
                from auto_procedures import sputter_procedure

            def on_finished(success: bool, message: str) -> None:
                # Always stop MFC flows when sputter procedure ends
                self.stop_all_mfc_flows()
                
                if success:
                    QMessageBox.information(self, "Success", "Sputter procedure completed successfully!")
                    # After sputter completes the system returns to high vacuum
                    self.set_system_status('high_vacuum')
                else:
                    if message:
                        QMessageBox.warning(self, "Procedure Failed", f"Sputter procedure failed: {message}")
                    else:
                        QMessageBox.warning(self, "Procedure Failed", "Sputter procedure failed. Check console for details.")
                    self.set_system_status(self.previous_system_status)

                self.current_procedure = None
                self._update_auto_procedure_button_states()

            worker = ProcedureWorker(sputter_procedure, arduino=self.arduino, safety=self.safety_controller, relay_map=self.relay_map)
            worker.signals.finished.connect(on_finished)
            if hasattr(self, 'threadpool') and self.threadpool is not None:
                self.threadpool.start(worker)
            else:
                result = sputter_procedure(arduino=self.arduino, safety=self.safety_controller, relay_map=self.relay_map)
                on_finished(builtins.bool(result), '' if result is True else str(result))
        except ImportError:
            QMessageBox.critical(self, "Error", "Auto procedures module not found.")
            self.stop_all_mfc_flows()  # Stop MFC flows on error
            self.set_system_status(self.previous_system_status)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Sputter procedure failed: {str(e)}")
            self.stop_all_mfc_flows()  # Stop MFC flows on error
            self.set_system_status(self.previous_system_status)

    def run_vent_loadlock_procedure(self) -> None:
        """Run the automatic load-lock vent procedure."""
        print("Running VENT Load-lock procedure...")
        
        # Check if procedure can be started
        if not self.can_start_procedure('vent_loadlock_procedure'):
            QMessageBox.warning(self, "Cannot Start Procedure", 
                              f"Cannot start vent load-lock procedure in current system state: {self.system_status}")
            return
        
        # Set current procedure and update system status
        self.current_procedure = 'pushButton_4'
        self.set_system_status('loadlock_venting')  # Set to loadlock_venting state
        self._update_auto_procedure_button_states()
        
        try:
            try:
                from .auto_procedures import vent_loadlock_procedure
            except ImportError:
                from auto_procedures import vent_loadlock_procedure

            def on_finished(success: bool, message: str) -> None:
                if success:
                    QMessageBox.information(self, "Success", "Load-lock vent procedure completed successfully!")
                    # Return to previous state or high_vacuum as specified in YAML
                    self.set_system_status('high_vacuum')  # or use previous_system_status if preferred
                    self.update_safety_state()
                    QTimer.singleShot(100, lambda: self._clear_current_procedure())
                else:
                    if message:
                        QMessageBox.warning(self, "Procedure Failed", f"Load-lock vent procedure failed: {message}")
                    else:
                        QMessageBox.warning(self, "Procedure Failed", "Load-lock vent procedure failed. Check console for details.")
                    self.set_system_status(self.previous_system_status)
                    self._clear_current_procedure()

            worker = ProcedureWorker(vent_loadlock_procedure, arduino=self.arduino, safety=self.safety_controller, relay_map=self.relay_map)
            worker.signals.finished.connect(on_finished)
            if hasattr(self, 'threadpool') and self.threadpool is not None:
                self.threadpool.start(worker)
            else:
                result = vent_loadlock_procedure(arduino=self.arduino, safety=self.safety_controller, relay_map=self.relay_map)
                on_finished(builtins.bool(result), '' if result is True else str(result))
        except ImportError:
            QMessageBox.critical(self, "Error", "Auto procedures module not found.")
            self.set_system_status(self.previous_system_status)
            self._clear_current_procedure()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Load-lock vent procedure failed: {str(e)}")
            self.set_system_status(self.previous_system_status)
            self._clear_current_procedure()

    def run_load_unload_procedure(self) -> None:
        """Run the automatic load/unload procedure."""
        print("Running Load/Unload procedure...")
        
        # Check if procedure can be started
        if not self.can_start_procedure('load_unload_procedure'):
            QMessageBox.warning(self, "Cannot Start Procedure", 
                              f"Cannot start load/unload procedure in current system state: {self.system_status}")
            return
        
        # Set current procedure and update system status
        self.current_procedure = 'pushButton_5'
        self.set_system_status('load_unload')  # Set to load_unload state
        self._update_auto_procedure_button_states()
        
        try:
            try:
                from .auto_procedures import load_unload_procedure
            except ImportError:
                from auto_procedures import load_unload_procedure

            def on_finished(success: bool, message: str) -> None:
                if success:
                    # Check if this is the special case where gate valve is open and waiting for user
                    if message == "GATE_OPEN_WAITING_USER":
                        # Show the load/unload dialog in the main thread
                        self._show_load_unload_dialog()
                    else:
                        QMessageBox.information(self, "Success", "Load/unload procedure completed successfully!")
                        # Return to high_vacuum as specified in YAML
                        self.set_system_status('high_vacuum')
                        self.update_safety_state()
                        QTimer.singleShot(100, lambda: self._clear_current_procedure())
                else:
                    if message and message != "GATE_OPEN_WAITING_USER":
                        QMessageBox.warning(self, "Procedure Failed", f"Load/unload procedure failed: {message}")
                    else:
                        QMessageBox.warning(self, "Procedure Failed", "Load/unload procedure failed. Check console for details.")
                    self.set_system_status(self.previous_system_status)
                    self._clear_current_procedure()

            worker = ProcedureWorker(load_unload_procedure, arduino=self.arduino, safety=self.safety_controller, relay_map=self.relay_map)
            worker.signals.finished.connect(on_finished)
            if hasattr(self, 'threadpool') and self.threadpool is not None:
                self.threadpool.start(worker)
            else:
                result = load_unload_procedure(arduino=self.arduino, safety=self.safety_controller, relay_map=self.relay_map)
                on_finished(builtins.bool(result), '' if result is True else str(result))
        except ImportError:
            QMessageBox.critical(self, "Error", "Auto procedures module not found.")
            self.set_system_status(self.previous_system_status)
            self._clear_current_procedure()

    def _show_load_unload_dialog(self) -> None:
        """Show the load/unload dialog in the main thread and complete the procedure."""
        try:
            # Import the dialog
            try:
                from .widgets.other_dialogs import LoadUnloadDialog
            except ImportError:
                from widgets.other_dialogs import LoadUnloadDialog
            
            # Create and show the dialog
            print("Showing load/unload dialog to user in main thread...")
            dialog = LoadUnloadDialog(self.arduino, self)
            result = dialog.exec()
            
            if result == LoadUnloadDialog.Accepted:
                # User confirmed arm is in home position - close the gate valve
                self._complete_load_unload_procedure()
            else:
                # User cancelled - turn off light and warn about gate valve being open
                try:
                    from .auto_procedures import set_relay_safe
                except ImportError:
                    from auto_procedures import set_relay_safe
                
                # Turn off chamber light
                print("💡 Turning off chamber light (cancelled)...")
                if set_relay_safe('btnLightBulb', False, self.arduino, self.safety_controller, self.relay_map):
                    print("✅ Chamber light turned off")
                else:
                    print("Warning: Failed to turn off chamber light (non-critical)")
                
                QMessageBox.warning(
                    self,
                    "Load/Unload Cancelled",
                    "Load/unload procedure cancelled.\n\n"
                    "WARNING: Load-lock gate valve remains OPEN!\n"
                    "Please manually verify arm is in home position before closing gate valve."
                )
                self.set_system_status(self.previous_system_status)
                self._clear_current_procedure()
                
        except Exception as e:
            # Turn off chamber light on error
            try:
                try:
                    from .auto_procedures import set_relay_safe
                except ImportError:
                    from auto_procedures import set_relay_safe
                
                print("💡 Turning off chamber light (error)...")
                set_relay_safe('btnLightBulb', False, self.arduino, self.safety_controller, self.relay_map)
            except Exception:
                pass  # Ignore light errors during error handling
            
            QMessageBox.critical(
                self,
                "Dialog Error",
                f"Error showing load/unload dialog: {str(e)}\n\n"
                "WARNING: Load-lock gate valve may remain open!"
            )
            self.set_system_status(self.previous_system_status)
            self._clear_current_procedure()

    def _complete_load_unload_procedure(self) -> None:
        """Complete the load/unload procedure by closing the gate valve."""
        try:
            # Import the procedure function to close the gate valve
            try:
                from .auto_procedures import set_relay_safe
            except ImportError:
                from auto_procedures import set_relay_safe
            
            # Update safety state before closing valve
            self.update_safety_state()
            
            # Close load-lock gate valve with safety checks
            print("Completing load/unload procedure - closing gate valve...")
            if set_relay_safe('btnValveLoadLockGate', False, self.arduino, self.safety_controller, self.relay_map):
                print("Load-lock gate valve closed successfully")
                
                # Turn off chamber light after load/unload complete
                print("💡 Turning off chamber light...")
                if set_relay_safe('btnLightBulb', False, self.arduino, self.safety_controller, self.relay_map):
                    print("✅ Chamber light turned off")
                else:
                    print("Warning: Failed to turn off chamber light (non-critical)")
                
                QMessageBox.information(self, "Success", "Load/unload procedure completed successfully!")
                # Return to high_vacuum as specified in YAML
                self.set_system_status('high_vacuum')
                self.update_safety_state()
                QTimer.singleShot(100, lambda: self._clear_current_procedure())
            else:
                QMessageBox.warning(
                    self,
                    "Valve Close Failed",
                    "Failed to close load-lock gate valve.\n"
                    "Please check safety conditions and close manually if needed."
                )
                self.set_system_status(self.previous_system_status)
                self._clear_current_procedure()
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Completion Error",
                f"Error completing load/unload procedure: {str(e)}"
            )
            self.set_system_status(self.previous_system_status)
            self._clear_current_procedure()

    # --- Polling ---
    def refresh_status(self) -> None:
        """Refresh relay status from Arduino."""
        #print("DEBUG: refresh_status called")
        if self.arduino is not None:
            try:
                #print("DEBUG: Getting status from arduino...")
                states = self.arduino.get_status()
                #print(f"DEBUG: Got {len(states)} relay states")
                if not states:
                    # lost connection
                    self.on_disconnected()
                    return
                # reflect states back onto buttons (robust against desync)
                for obj_name, relay_num in self.relay_map.items():
                    btn = getattr(self, obj_name, None)
                    if btn is None:
                        continue
                    idx = relay_num - 1
                    if 0 <= idx < len(states):
                        # For most relays we reflect Arduino-reported relay states.
                        # Ion gauge is a momentary-control device; its ON/OFF state
                        # is determined from the analog voltage (ai_volts[2]).
                        if obj_name == 'btnIonGauge':
                            try:
                                ion_on = False
                                if len(self.last_analog_inputs) > 2:
                                    # Use threshold from config instead of hardcoded value
                                    ion_threshold = self.safety_controller.safety_config.get('pressure_thresholds', {}).get('ion_gauge_on_threshold', 4.2)
                                    ion_on = float(self.last_analog_inputs[2]) <= ion_threshold
                                btn.blockSignals(True)
                                btn.setChecked(bool(ion_on))
                                btn.blockSignals(False)
                                btn.setText("Ion\nGauge:\nON" if ion_on else "Ion\nGauge:\nOFF")
                            except Exception:
                                # Fallback to showing unknown state
                                btn.blockSignals(True)
                                btn.setChecked(False)
                                btn.blockSignals(False)
                                btn.setText("Ion\nGauge:\n---")
                        else:
                            current = btn.isChecked()
                            desired = bool(states[idx])
                            if current != desired:
                                btn.blockSignals(True)
                                btn.setChecked(desired)
                                btn.blockSignals(False)
            except Exception as e:
                print(f"DEBUG: Error refreshing status: {e}")
        else:
            print("DEBUG: Arduino controller is None, skipping refresh_status")

    def refresh_inputs(self) -> None:
        """Refresh input status from Arduino."""
        #print("DEBUG: refresh_inputs called")
        if self.arduino is not None:
            try:
                #   print("DEBUG: Getting inputs from arduino...")
                # Digital
                di = self.arduino.get_digital_inputs()
                if di is not None:
                    # Store for safety controller (4 digital inputs: Door, Water, Rod, Spare)
                    previous_states = self.last_digital_inputs.copy()
                    self.last_digital_inputs = [bool(di[i]) if i < len(di) else False for i in range(4)]

                    # Update visual indicators for first 3: Arduino sends Water(0), Rod(1), Door(2)
                    for idx, obj_name in enumerate(["indWater", "indRod", "indDoor"]):
                        w = getattr(self, obj_name, None)
                        if w is not None and idx < len(di):
                            indicator_state = bool(di[idx])
                            set_interlock_indicator(w, indicator_state)
                else:
                    # No connection or error - set all to False for safety
                    # digital_inputs order: [water_flow, rod_home, door_close, spare]
                    self.last_digital_inputs = [False, False, False, False]
                    for idx, obj_name in enumerate(["indWater", "indRod", "indDoor"]):
                        w = getattr(self, obj_name, None)
                        if w is not None:
                            set_interlock_indicator(w, None)

                # Analog
                ai_raw = self.arduino.get_analog_inputs()  # Raw ADC values
                ai_volts = self.arduino.get_analog_voltages()  # Converted voltages

                if ai_raw and ai_volts and hasattr(self, "groupAnalog"):
                    # Store voltage values for safety controller (use voltages, not raw ADC)
                    self.last_analog_inputs = [float(ai_volts[i]) if i < len(ai_volts) else 0.0 for i in range(4)]

                    lcds = [getattr(self, f"lcdAnalog{i}", None) for i in range(1, 5)]
                    for i, voltage in enumerate(ai_volts[:4]):
                        if i < len(self.cfg.analog_channels):
                            scale = float(self.cfg.analog_channels[i].get("scale", 1.0))
                            offset = float(self.cfg.analog_channels[i].get("offset", 0.0))
                        else:
                            scale, offset = 1.0, 0.0

                        # Turbo channel handling: compute percent = voltage*scale + offset,
                        # clamp to 0..100, apply 3-sample moving average, then display as int
                        if i == 3:
                            try:
                                percent = float(voltage) * scale + offset
                                percent = max(0.0, min(100.0, percent))
                                # Update MA buffer
                                self._turbo_ma.append(percent)
                                if len(self._turbo_ma) > 3:
                                    self._turbo_ma.pop(0)
                                avg = sum(self._turbo_ma) / len(self._turbo_ma)
                                disp_val = int(round(avg))
                            except Exception:
                                disp_val = 0

                            if i < len(lcds) and lcds[i] is not None:
                                # Display integer percent (LCD shows digits only)
                                lcds[i].display(f"{disp_val}")
                            continue

                        # Chamber pressure (index 1): convert voltage to pressure in Torr
                        if i == 1:  # Chamber pressure analog input (A2, index 1)
                            try:
                                pressure_torr = self.voltage_to_pressure_torr(float(voltage))
                                if i < len(lcds) and lcds[i] is not None:
                                    # Display pressure in scientific notation for very small values
                                    if pressure_torr > 1e-3:
                                        lcds[i].display(f"{pressure_torr:.2e}")
                                    else:
                                        lcds[i].display(f"{pressure_torr:.4f}")
                            except Exception:
                                # Fallback to voltage display if conversion fails
                                val = float(voltage) * scale + offset
                                if i < len(lcds) and lcds[i] is not None:
                                    lcds[i].display(f"{val:7.2f}")
                            continue

                        # Default: display scaled voltage for other channels
                        val = float(voltage) * scale + offset
                        if i < len(lcds) and lcds[i] is not None:
                            lcds[i].display(f"{val:7.2f}")
                    # Update Ion Gauge button state/text based on ai_volts[2]
                    try:
                        if hasattr(self, 'btnIonGauge') and self.btnIonGauge is not None:
                            ion_on = False
                            if len(self.last_analog_inputs) > 2:
                                # Use threshold from config instead of hardcoded value
                                ion_threshold = self.safety_controller.safety_config.get('pressure_thresholds', {}).get('ion_gauge_on_threshold', 4.2)
                                ion_on = float(self.last_analog_inputs[2]) <= ion_threshold
                            self.btnIonGauge.blockSignals(True)
                            self.btnIonGauge.setChecked(bool(ion_on))
                            self.btnIonGauge.blockSignals(False)
                            self.btnIonGauge.setText("Ion\nGauge:\nON" if ion_on else "Ion\nGauge:\nOFF")
                    except Exception:
                        pass
                else:
                    # No connection - set all to 0 for safety
                    self.last_analog_inputs = [0.0, 0.0, 0.0, 0.0]
            except Exception as e:
                print(f"DEBUG: Error refreshing inputs: {e}")
            
            # Always update safety state with latest readings (even after errors)
            self.update_safety_state()
        else:
            print("DEBUG: Arduino controller is None, skipping refresh_inputs")
            # Set defaults when arduino is None
            self.last_digital_inputs = [False, False, False, False]
            self.last_analog_inputs = [0.0, 0.0, 0.0, 0.0]
        
        # Update MFC displays from cache during regular GUI refresh (700ms cycle)
        # This provides much faster updates than the separate MFC timer (5s cycle)
        if self.gas_controller and self.mfc_readings_cache:
            try:
                self.update_mfc_displays_from_cache()
            except Exception:
                # Silently ignore errors since this runs frequently
                pass
        
        # Always update safety state with latest readings
        self.update_safety_state()

    # --- Cleanup ---
    def closeEvent(self, event) -> None:  # type: ignore[override]
        try:
            # Stop light timer if running
            if hasattr(self, 'light_timer') and self.light_timer is not None:
                self.light_timer.stop()
                print("Stopped light auto-off timer")
            
            # Close recorder window if open
            if hasattr(self, '_recorder_window') and self._recorder_window is not None:
                print("Closing analog recorder window...")
                self._recorder_window.close()
                self._recorder_window = None
            
            if hasattr(self, 'arduino') and self.arduino and self.arduino.is_connected:
                # Check current state and decide on shutdown approach
                self.update_safety_state()  # Ensure latest readings
                current_state = getattr(self.safety_controller, 'system_status', None)
                
                print(f"Performing safe shutdown on close from state: {current_state}")
                
                # If already in a safe state (standby or default), minimal action needed
                if current_state in ['standby', 'default']:
                    print(f"System already in safe state ({current_state}) - minimal shutdown")
                    try:
                        # Just ensure no dangerous operations are running
                        if self.current_procedure is not None:
                            print("Clearing current procedure...")
                            self._clear_current_procedure()
                    except Exception as e:
                        print(f"Warning: Failed to clear procedure: {e}")
                else:
                    # System not in safe state - perform full safe shutdown
                    print("System not in safe state - performing full safe shutdown...")
                    try:
                        # Import and use go_to_default_state for safe shutdown
                        from auto_procedures import go_to_default_state
                        go_to_default_state(arduino=self.arduino, safety=self.safety_controller, relay_map=self.relay_map)
                    except ImportError:
                        print("Warning: auto_procedures not available, using emergency all_relays_off")
                        self.arduino.all_relays_off()
                    except Exception as e:
                        print(f"Warning: Safe shutdown failed ({e}), using emergency all_relays_off")
                        self.arduino.all_relays_off()
                
                # Disconnect Arduino based on persistence setting
                try:
                    # For now, always keep connection alive (user can force disconnect if needed)
                    print("🔄 Preserving Arduino connection for next session...")
                    self.arduino.disconnect(force_disconnect=False)  # Keep alive
                except Exception as e:
                    print(f"Warning: Arduino disconnect failed: {e}")
            else:
                print("No Arduino connection to close")
        finally:
            super().closeEvent(event)

    def get_analog_voltages(self):
        """Get current analog voltage readings for plotting/recording.
        
        Returns a list of 4 voltage values (floats) from the last known analog inputs.
        This method is used by both the plotter window and analog recorder.
        """
        vals = list(self.last_analog_inputs)
        while len(vals) < 4:
            vals.append(0.0)
        return vals

    def open_plotter(self) -> None:
        """Open the analog plotter window."""
        if self._plotter_window is None:
            # Show warning dialog before opening plotter
            reply = QMessageBox.warning(
                self,
                "Plotter Window Warning",
                "⚠️ WARNING: The plotter window may cause the GUI to crash in this version.\n\n"
                "Consider using 'Record Analog Inputs' from the Tools menu instead "
                "for stable long-term data logging.\n\n"
                "Do you wish to proceed with opening the plotter?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No  # Default to No for safety
            )
            
            if reply != QMessageBox.Yes:
                return  # User chose not to open plotter
            
            self._plotter_window = PlotterWindow(self.get_analog_voltages, parent=self)
            self._plotter_window.destroyed.connect(lambda *_: setattr(self, '_plotter_window', None))
            self._plotter_window.show()

        else:
            self._plotter_window.raise_()
            self._plotter_window.activateWindow()

    def open_analog_recorder(self) -> None:
        """Open dialog to configure and start analog input recording to CSV."""
        # Check if Arduino is connected
        if not self.arduino or not self.arduino.is_connected:
            QMessageBox.warning(
                self,
                "Arduino Not Connected",
                "Cannot record analog inputs: Arduino is not connected."
            )
            return
        
        # Check if recorder is already running
        if self._recorder_window is not None and not self._recorder_window.isHidden():
            try:
                QMessageBox.information(
                    self,
                    "Recorder Already Running",
                    "Analog input recording is already in progress.\n\n"
                    "Close the recorder window to stop recording."
                )
                self._recorder_window.raise_()
                self._recorder_window.activateWindow()
                return
            except RuntimeError:
                # Window was deleted but reference not cleared
                print("⚠️ Recorder window reference was stale, clearing it")
                self._recorder_window = None
        
        # Clear stale reference if window was closed
        if self._recorder_window is not None:
            try:
                # Test if window still exists
                self._recorder_window.isVisible()
            except RuntimeError:
                print("🧹 Clearing stale recorder window reference")
                self._recorder_window = None
        
        # Show dialog to select file
        dialog = AnalogRecorderDialog(self)
        if dialog.exec() == AnalogRecorderDialog.DialogCode.Accepted:
            file_path = dialog.get_file_path()
            if file_path:
                # Create and show recorder window using shared voltage reader method
                print(f"📊 Creating recorder window for: {file_path}")
                self._recorder_window = AnalogRecorderWindow(file_path, self.get_analog_voltages, self)
                
                # Connect finished signal instead of destroyed (more reliable)
                self._recorder_window.finished.connect(self._on_recorder_window_closed)
                
                # Also connect destroyed as backup
                self._recorder_window.destroyed.connect(self._on_recorder_window_destroyed)
                
                self._recorder_window.show()
                print("✅ Recorder window created and shown")
    
    def open_logbook(self) -> None:
        """Open the logbook window as an independent window."""
        # Check if window exists and is still valid
        if hasattr(self, '_logbook_window') and self._logbook_window is not None:
            try:
                # Check if window is still alive by testing a method
                if self._logbook_window.isVisible():
                    # Window exists and is visible, just raise it
                    self._logbook_window.raise_()
                    self._logbook_window.activateWindow()
                    return
                else:
                    # Window exists but hidden, show it
                    self._logbook_window.show()
                    self._logbook_window.raise_()
                    self._logbook_window.activateWindow()
                    return
            except (RuntimeError, AttributeError):
                # Window was deleted but reference not cleared
                print("⚠️ Logbook window reference was stale, clearing it")
                self._logbook_window = None
        
        # Create new logbook window with current user
        print("📔 Creating new logbook window")
        self._logbook_window = LogbookWidget(parent=self, current_user=self.current_user)
        self._logbook_window.destroyed.connect(lambda: self._on_logbook_window_destroyed())
        self._logbook_window.show()
    
    def _on_logbook_window_destroyed(self):
        """Handle logbook window destruction."""
        print("📔 Logbook window destroyed - clearing reference")
        self._logbook_window = None
    
    def _on_recorder_window_closed(self):
        """Handle recorder window finished signal (more reliable than destroyed)."""
        print("📊 Recorder window finished signal - clearing reference")
        self._recorder_window = None
    
    def _on_recorder_window_destroyed(self):
        """Handle recorder window destruction (backup cleanup)."""
        print("📊 Recorder window destroyed signal - clearing reference")
        self._recorder_window = None

    def _on_ion_gauge_auto_toggle_changed(self) -> None:
        """Handle ion gauge auto-toggle menu item state change."""
        new_state = self.ion_gauge_auto_toggle_action.isChecked()
        self.ion_gauge_auto_toggle_enabled = new_state
        
        status_msg = "✅ Ion Gauge Auto-Toggle ENABLED" if new_state else "⛔ Ion Gauge Auto-Toggle DISABLED"
        print(status_msg)
        
        # Show status in a temporary status bar message if available
        if hasattr(self, 'statusbar') and self.statusbar():
            self.statusbar().showMessage(status_msg, 3000)  # Show for 3 seconds

    def _setup_procedure_menu(self, procedure_menu) -> None:
        """Set up the Run Procedure menu with all available auto procedures."""
        # Define the available procedures with their display names and function names
        procedures = [
            ("Pump Procedure", "pump_procedure"),
            ("Vent Procedure", "vent_procedure"),
            ("Sputter Procedure", "sputter_procedure"),
            ("Vent Load-lock Procedure", "vent_loadlock_procedure"),
            ("Load/Unload Procedure", "load_unload_procedure"),
            ("-", None),  # Separator
            ("Go to Standby", "go_to_standby"),
            ("Go to Default State", "go_to_default_state"),
        ]
        
        for display_name, function_name in procedures:
            if display_name == "-":
                # Add separator
                procedure_menu.addSeparator()
            else:
                action = procedure_menu.addAction(display_name)
                # Use lambda with default parameter to capture function_name
                action.triggered.connect(lambda checked, fn=function_name, name=display_name: self._run_procedure_from_menu(fn, name))

    def _run_procedure_from_menu(self, function_name: str, display_name: str) -> None:
        """Run a procedure selected from the menu with safety checks."""
        print(f"Menu procedure requested: {function_name} ({display_name})")
        
        # Check if Arduino is connected
        if self.arduino is None or not self.arduino.is_connected:
            QMessageBox.warning(self, "Cannot Run Procedure", "Arduino not connected")
            return
        
        # Check if another procedure is already running
        if self.current_procedure is not None:
            QMessageBox.warning(self, "Procedure Running", 
                              "Another procedure is currently running. Please wait for it to complete.")
            return
        
        # Apply the same safety checks as GUI buttons
        can_run = False
        
        # Map function names to their corresponding GUI procedure names for safety checks
        procedure_safety_map = {
            "pump_procedure": "pump_procedure",
            "vent_procedure": "vent_procedure", 
            "sputter_procedure": "sputter_procedure",
            "vent_loadlock_procedure": "vent_loadlock_procedure",
            "load_unload_procedure": "load_unload_procedure",
            "go_to_standby": "go_to_standby",
            "go_to_default_state": "go_to_default_state"
        }
        
        safety_key = procedure_safety_map.get(function_name)
        if safety_key:
            # Use the same safety check logic as GUI buttons
            if safety_key in ["pump_procedure", "vent_procedure", "sputter_procedure", "vent_loadlock_procedure", "load_unload_procedure"]:
                can_run = self.can_start_procedure(safety_key)
            else:
                # For go_to_standby and go_to_default_state, always allow if connected
                can_run = True
        else:
            can_run = False
        
        if not can_run:
            QMessageBox.warning(self, "Cannot Start Procedure", 
                              f"Cannot start {display_name} in current system state: {self.system_status}")
            return
        
        # Special confirmation for vent procedure (same as GUI button)
        if function_name == "vent_procedure":
            reply = QMessageBox.question(
                self,
                "CONFIRM VENTING",
                "CONFIRM THAT THE DOOR LATCHES HAVE BEEN REMOVED FIRST BEFORE VENTING!\n\nProceed with venting?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Run the procedure
        try:
            # Import the procedure function
            try:
                from . import auto_procedures
            except ImportError:
                import auto_procedures
            
            procedure_function = getattr(auto_procedures, function_name, None)
            if procedure_function is None:
                QMessageBox.critical(self, "Error", f"Procedure function '{function_name}' not found")
                return
            
            # Set current procedure and update button states
            self.current_procedure = f"menu_{function_name}"
            self._update_auto_procedure_button_states()
            
            # Set appropriate system status for certain procedures
            if function_name == "pump_procedure":
                self.set_system_status('pumping')
            elif function_name == "vent_procedure":
                self.set_system_status('venting')
            elif function_name == "sputter_procedure":
                self.set_system_status('sputtering')
            elif function_name == "load_unload_procedure":
                self.set_system_status('loading')
            elif function_name == "vent_loadlock_procedure":
                self.set_system_status('venting_loadlock')
            
            def on_finished(success: bool, message: str) -> None:
                """Handle completion of menu-initiated procedure."""
                print(f"DEBUG: menu procedure {function_name} finished: success={success}, message='{message}'")
                
                if success:
                    print(f"{display_name} completed successfully.")
                    
                    # Set appropriate final state
                    if function_name in ["pump_procedure"]:
                        self.set_system_status('high_vacuum')
                    elif function_name in ["vent_procedure", "vent_loadlock_procedure"]:
                        self.set_system_status('vented')
                    elif function_name == "go_to_standby":
                        self.set_system_status('standby')
                    elif function_name == "go_to_default_state":
                        self.set_system_status('default')
                    
                    QMessageBox.information(self, "Procedure Complete", f"{display_name} completed successfully.")
                else:
                    print(f"{display_name} failed: {message}")
                    QMessageBox.warning(self, "Procedure Failed", f"{display_name} failed: {message}")
                    # Restore previous state if available
                    if hasattr(self, 'previous_system_status') and self.previous_system_status:
                        self.set_system_status(self.previous_system_status)
                
                # Clear current procedure and update button states
                self._clear_current_procedure()
            
            # Create worker to run procedure in background
            worker = ProcedureWorker(procedure_function, arduino=self.arduino, 
                                   safety=self.safety_controller, relay_map=self.relay_map)
            worker.signals.finished.connect(on_finished)
            
            # Start worker via threadpool if available
            if hasattr(self, 'threadpool') and self.threadpool is not None:
                self.threadpool.start(worker)
            else:
                # Fallback: run synchronously
                print(f"DEBUG: Running {function_name} synchronously (no threadpool)")
                result = procedure_function(arduino=self.arduino, safety=self.safety_controller, relay_map=self.relay_map)
                on_finished(builtins.bool(result), '' if result is True else str(result))
                
        except ImportError:
            QMessageBox.critical(self, "Error", "Auto procedures module not available.")
            self._clear_current_procedure()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to run {display_name}: {str(e)}")
            self._clear_current_procedure()

    def show_system_state_dialog(self) -> None:
        """Show dialog for manually setting system state."""
        try:
            try:
                from .widgets.other_dialogs import SetSystemStateDialog
            except Exception:
                from widgets.other_dialogs import SetSystemStateDialog

            dlg = SetSystemStateDialog(self.system_status, getattr(self, 'safety_controller', None), parent=self)
            if dlg.exec() == dlg.Accepted:
                new_state = dlg.get_selected_state()
                if new_state and new_state != self.system_status:
                    self.set_system_status(new_state)
                    from PyQt5.QtWidgets import QMessageBox
                    QMessageBox.information(self, "State Changed", f"System state changed to: {new_state.title()}")
        except Exception as e:
            print(f"❌ Error showing SetSystemStateDialog: {e}")

    def show_about_dialog(self) -> None:
        """Show the About dialog with software information."""
        try:
            about_dlg = AboutDialog(parent=self)
            about_dlg.exec()
        except Exception as e:
            print(f"❌ Error showing About dialog: {e}")
            QMessageBox.information(
                self,
                "About Sputter Control System",
                "Sputter Control System v2.0\n\n"
                "Automated control software for magnetron sputtering.\n"
                "Built on Raspberry Pi 5 with Arduino Mega 2560 R3."
            )


def run() -> int:    
    """Run the Auto Control application."""
    import signal
    
    # Setup signal handler for graceful shutdown on Ctrl+C
    def signal_handler(signum, frame):
        print("\n🔄 Ctrl+C received - preserving Arduino connection...")
        if 'arduino' in locals() and hasattr(arduino, 'disconnect'):
            arduino.disconnect(force_disconnect=False)  # Keep connection alive
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # ========================================
    # CRITICAL: Initialize Arduino FIRST to prevent unwanted relay operations during GUI setup
    # ========================================
    print("🔌 DEBUG: *** STEP 1: Creating ArduinoController BEFORE GUI ***")
    arduino = ArduinoController()
    print("✅ DEBUG: ArduinoController instance created successfully")
    
    # Attempt Arduino connection before GUI initialization to establish communication early
    print("🔍 DEBUG: *** STEP 2: Attempting Arduino auto-connect BEFORE GUI creation ***")
    print("DEBUG: *** STEP 2: Attempting Arduino auto-connect BEFORE GUI creation ***")
    try:
        connection_success = arduino.auto_connect()
        if arduino.is_connected:
            print("DEBUG: ✅ Arduino connected successfully BEFORE GUI initialization")
            print("DEBUG: This ensures no unwanted relay operations during GUI setup")
        else:
            print("DEBUG: ⚠️  Arduino not connected yet, will retry after GUI initialization")
    except Exception as e:
        # Check if this is a critical safety error from Arduino firmware
        error_msg = str(e)
        if "ARDUINO_SAFETY_HALT" in error_msg or "LOAD-LOCK ARM IS NOT IN HOME POSITION" in error_msg:
            print("\n" + "="*80)
            print("🚨 CRITICAL SAFETY ERROR DETECTED 🚨")
            print("="*80)
            print("")
            print("LOAD-LOCK ARM IS NOT IN HOME POSITION!!")
            print("")
            print("RETURN TO HOME POSITION AND THEN REBOOT GUI.")
            print("")
            print("="*80)
            print("GUI INITIALIZATION ABORTED FOR SAFETY")
            print("="*80)
            
            return 1  # Exit with error code
        else:
            print(f"DEBUG: ❌ Arduino connection failed before GUI: {e}")

    print("DEBUG: Starting QApplication...")
    # Force X11 backend on Linux to avoid Wayland issues
    import os
    if sys.platform.startswith('linux'):
        os.environ['QT_QPA_PLATFORM'] = 'xcb'
        print("DEBUG: Forced X11 backend for Linux")
    
    app = QApplication(sys.argv)
    
    # ========================================
    # STEP 3: User Authentication
    # ========================================
    print("👤 DEBUG: *** STEP 3: User Authentication ***")
    login_dialog = LoginDialog()
    
    if login_dialog.exec() != LoginDialog.Accepted:
        print("❌ Login cancelled - exiting application")
        return 0
    
    current_user = login_dialog.get_authenticated_user()
    master_password = login_dialog.get_master_password()
    
    print(f"✅ User authenticated: {current_user['username']} (Level {current_user['admin_level']})")
    
    print("DEBUG: *** STEP 4: Creating AutoControlWindow with pre-initialized Arduino controller ***")
    win = AutoControlWindow(arduino=arduino, current_user=current_user, master_password=master_password)
    win.setWindowTitle("Sputter Auto Control")

    # Initial guess for client area size. We'll correct outer size after showing
    # because window frame/titlebar sizes are platform-dependent.
    win.resize(1280, 800)
    print("DEBUG: Showing window...")
    win.show()

    # Process events so the window system reports real geometry values
    print("DEBUG: Processing initial events...")
    app.processEvents()
    print("DEBUG: Initial events processed, window should be visible")
    
    # Force window to be visible and on top
    print("DEBUG: Raising and activating window...")
    win.raise_()
    win.activateWindow()
    win.show()
    print("DEBUG: Window raised and activated")
    
    # Additional window management for Linux/Wayland
    print("DEBUG: Setting window properties...")
    win.setWindowState(win.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
    win.repaint()
    print("DEBUG: Window properties set")
    
    # Test GUI responsiveness
    print("DEBUG: Testing GUI responsiveness...")
    QTimer.singleShot(1000, lambda: print("DEBUG: 1 second timer fired - GUI is responsive"))
    QTimer.singleShot(5000, lambda: print("DEBUG: 5 second timer fired - GUI still responsive"))

    try:
        # Desired total outer size (including title bar + frame + menubar)
        desired_outer_height = 800

        # frameGeometry is the outer rectangle (includes title bar & window frame)
        # geometry is the client area inside the window frame. Their difference
        # is the decoration height (title bar + frame thickness).
        decoration_height = win.frameGeometry().height() - win.geometry().height()
        print("Decoration height of window: ", decoration_height)

        # Compute the inner/client height needed so the outer height equals desired
        inner_height = max(100, desired_outer_height - decoration_height)
        print("Final height of window: ", decoration_height)

        # Resize the top-level window's client area so outer height ~= desired_outer_height
        print("Resizing window to 760 pixels in height to account for menubar..")
        win.resize(1280, 760)
    except Exception:
        # Best-effort only; if anything fails just continue with the shown size
        print("Exception occurred on measuring widow height for re-adjustment....")
        pass

    return app.exec()
