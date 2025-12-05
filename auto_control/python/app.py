from __future__ import annotations

import sys
import time
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
    from .gas_control.gas_methods import execute_zero_gas_flows  # type: ignore
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
    from gas_control.gas_methods import execute_zero_gas_flows  # type: ignore


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
            # Log the full traceback for debugging
            import traceback
            error_details = traceback.format_exc()
            print(f"❌ Exception in procedure execution:\n{error_details}")
            self.signals.finished.emit(False, f"Exception: {str(e)}")


# Helper function for conditional imports
def _import_from_auto_procedures(function_name: str):
    """Helper to import functions from auto_procedures with fallback.
    
    Args:
        function_name: Name of the function to import
        
    Returns:
        The imported function
    """
    try:
        from . import auto_procedures
        return getattr(auto_procedures, function_name)
    except (ImportError, AttributeError):
        import auto_procedures
        return getattr(auto_procedures, function_name)


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
            # Pass hardcoded port from config if available
            arduino_port = self.cfg.serial.arduino_port
            if arduino_port:
                print(f"🔌 DEBUG: Using configured Arduino port: {arduino_port}")
            else:
                print("🔌 DEBUG: No configured port, will use auto-detection")
            self.arduino = ArduinoController(config_port=arduino_port)
        else:
            print("🔌 DEBUG: Using pre-initialized Arduino controller from run()")
            self.arduino = arduino
        print(f"🔌 DEBUG: Arduino controller assigned, connected: {self.arduino.is_connected if self.arduino else False}")

        # Safety Controller
        print("⚠️ DEBUG: Creating SafetyController...")
        self.safety_controller = SafetyController()
        print("⚠️ DEBUG: SafetyController created")

        # Gas Flow Controller (MFC) - Initialize ONLY when sputter mode is entered
        print("🌀 DEBUG: GasFlowController will be initialized on-demand (sputter mode only)")
        self.gas_controller = None
        self._gas_controller_initializing = False
        
        # NOTE: Gas controller is NOT initialized automatically on startup
        # It will be initialized by _ensure_gas_controller_running() when entering sputter mode
        # This prevents serial port contention with Arduino during startup

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
        
        # Arduino connection health tracking
        self.arduino_consecutive_failures = 0
        self.arduino_reconnection_in_progress = False
        self.max_consecutive_failures = 3  # Trigger reconnection after 3 failures
        
        # Gas flow state for restoration after reconnection
        self.saved_gas_flow_state = {}  # Store MFC setpoints for recovery
        
        # Gas flow state for restoration after reconnection
        self.saved_gas_flow_state = {}  # Store MFC setpoints for recovery

        # Light bulb auto-off timer - turns off chamber light after 300 seconds
        self.light_timer = QTimer(self)
        self.light_timer.setSingleShot(True)  # One-shot timer
        self.light_timer.setInterval(300000)  # 300 seconds
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
        # Note: _wire_mfc_controls() is called after gas controller initialization completes

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

        # Auto-open logbook after GUI loads and Arduino connects
        # Delayed to 2000ms to ensure Arduino connection completes first
        QTimer.singleShot(2000, self.open_logbook)

        # Check if Arduino is already connected from run(), otherwise setup auto-connect
        if self.arduino is not None and self.arduino.is_connected:
            print("DEBUG: Arduino already connected from run(), calling on_connected()")
            self.on_connected()
        else:
            print("DEBUG: Arduino not connected yet, setting up auto-connect timer...")
            # Increased priority - connect Arduino first before other operations
            QTimer.singleShot(100, self.auto_connect)  # Changed from 300ms to 100ms for faster connection
            print("DEBUG: Auto-connect timer ENABLED")

        # Add Tools menu action for plotter
        try:
            menubar = self.menuBar()
        except Exception:
            menubar = None

        if menubar is not None:
            # Add Tools menu items
            tools_menu = None
            for action in menubar.actions():
                if action.text() == "Tools":
                    tools_menu = action.menu()
                    break
            
            if tools_menu:
                # Add Standby Quick Reset action
                quick_reset_action = tools_menu.addAction("Standby Quick Reset")
                quick_reset_action.triggered.connect(self.run_quick_reset_to_standby)
                print("✅ Added 'Standby Quick Reset' to Tools menu")
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
            
            # Add zero gas flows action
            zero_gas_action = tools_menu.addAction('Zero Gas Flows')
            zero_gas_action.triggered.connect(self.zero_gas_flows)
            zero_gas_action.setStatusTip("Stop all gas flows, close valves, and shutdown gas controller")
            
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
            
            # Manage gas controller based on state transitions
            if new_status == 'sputter':
                # Start gas controller when entering sputter mode
                self._ensure_gas_controller_running()
            elif self.previous_system_status == 'sputter':
                # Stop gas controller when leaving sputter mode
                QTimer.singleShot(1000, self._stop_gas_controller_if_not_needed)
            
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

    def _init_gas_controller_background(self) -> None:
        """Initialize gas controller in background thread to prevent GUI freezing."""
        if self._gas_controller_initializing or self.gas_controller is not None:
            return
            
        self._gas_controller_initializing = True
        print("🌀 DEBUG: Starting background gas controller initialization...")
        
        class GasControllerInitWorker(QRunnable):
            def __init__(self, parent_window):
                super().__init__()
                self.parent = parent_window
                self.signals = ProcedureSignals()
                
            def run(self):
                try:
                    # Exclude Arduino port if connected
                    excluded = []
                    if self.parent.arduino and self.parent.arduino.is_connected and self.parent.arduino.serial_port:
                        excluded.append(self.parent.arduino.serial_port.port)
                        print(f"🌀 DEBUG: Excluding Arduino port {self.parent.arduino.serial_port.port} from MFC scan")
                    
                    # Create gas controller
                    gas_controller = GasFlowController(
                        self.parent.cfg.gas_control, 
                        self.parent.safety_controller, 
                        excluded_ports=excluded,
                        arduino_controller=self.parent.arduino
                    )
                    
                    self.signals.finished.emit(True, "Gas controller initialized")
                    # Store controller reference (will be accessed in main thread)
                    self.parent.gas_controller = gas_controller
                    print("✅ DEBUG: GasFlowController created successfully in background")
                    
                except Exception as e:
                    print(f"❌ DEBUG: Failed to create GasFlowController in background: {e}")
                    import traceback
                    traceback.print_exc()
                    self.signals.finished.emit(False, str(e))
        
        worker = GasControllerInitWorker(self)
        worker.signals.finished.connect(self._on_gas_controller_init_finished)
        QThreadPool.globalInstance().start(worker)
    
    def _on_gas_controller_init_finished(self, success: bool, message: str) -> None:
        """Handle completion of background gas controller initialization."""
        self._gas_controller_initializing = False
        
        if success:
            print(f"✅ Gas controller initialization complete: {message}")
            # Wire MFC controls now that gas controller is ready
            try:
                self._wire_mfc_controls()
            except Exception as e:
                print(f"⚠️ Could not wire MFC controls: {e}")
            # Update UI if needed
            try:
                self.update_mfc_displays()
            except Exception as e:
                print(f"⚠️ Could not update MFC display: {e}")
        else:
            print(f"❌ Gas controller initialization failed: {message}")
            QMessageBox.warning(
                self,
                "Gas Controller Warning",
                f"Failed to initialize gas flow controller:\n{message}\n\n"
                "MFC control will not be available. Check that:\n"
                "- Alicat MFCs are powered and connected\n"
                "- Serial ports are configured correctly in gas_control/config.yml\n"
                "- USB cables are properly connected"
            )

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
            
            if procedure_name not in allowed_list:
                print(f"DEBUG: Procedure '{procedure_name}' is NOT allowed in state '{self.system_status}'")
                return False
            
            # Procedure is allowed for this state - now check safety conditions
            # Update safety controller with current state before checking
            self.update_safety_state()
            
            safety_result = self.safety_controller.check_procedure_safety(procedure_name)
            if not safety_result.allowed:
                print(f"⚠️ Procedure safety check failed: {safety_result.message}")
                # Store the message so we can show it to the user
                if not hasattr(self, '_last_procedure_safety_error'):
                    self._last_procedure_safety_error = {}
                self._last_procedure_safety_error[procedure_name] = safety_result.message
                return False
            
            #print(f"DEBUG: Procedure '{procedure_name}' passed all checks")
            return True
                
        except Exception as err:
            print(f"DEBUG: Error checking procedure safety: {err}")
            import traceback
            traceback.print_exc()
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
                abort_and_go_default = _import_from_auto_procedures('abort_and_go_default')

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
                        toggle_ion_gauge = _import_from_auto_procedures('toggle_ion_gauge')
                        
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
            
            db_path = Path(__file__).parent.parent.parent / "logbook.db"
            
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
        # Start timers
        self.status_timer.start()
        
        # Delay input timer start to ensure communication thread is ready
        # Arduino may need a moment after connection to be fully responsive
        print("⏰ DEBUG: Delaying input timer start by 1 second to ensure Arduino ready...")
        QTimer.singleShot(1000, lambda: (
            self.input_timer.start(),
            print("✅ DEBUG: Input timer started")
        ))
        
        # Gas controller will start conditionally only during sputter mode
        # This saves CPU resources when not actively controlling gas flow
        print("DEBUG: Gas controller will start on-demand during sputter operations")

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
    
    def _save_gas_flow_state(self) -> None:
        """Save current gas flow settings for restoration after reconnection."""
        try:
            if self.gas_controller and hasattr(self.gas_controller, '_last_readings'):
                self.saved_gas_flow_state = {}
                for channel_name, reading in self.gas_controller._last_readings.items():
                    if hasattr(reading, 'setpoint') and reading.setpoint > 0:
                        self.saved_gas_flow_state[channel_name] = reading.setpoint
                        print(f"  💾 Saved {channel_name}: {reading.setpoint} sccm")
                
                if self.saved_gas_flow_state:
                    print(f"  ✅ Saved {len(self.saved_gas_flow_state)} gas flow setpoint(s)")
                else:
                    print("  📭 No active gas flows to save")
            else:
                print("  ⚠️ Gas controller not available to save state")
        except Exception as e:
            print(f"  ❌ Error saving gas flow state: {e}")
    
    def _restore_gas_flow_state(self) -> None:
        """Restore gas flow settings after reconnection."""
        try:
            if not self.saved_gas_flow_state:
                print("  📭 No saved gas flow state to restore")
                return
            
            if not self.gas_controller:
                print("  ⚠️ Cannot restore gas flow - controller not initialized")
                return
            
            print(f"  🔄 Restoring {len(self.saved_gas_flow_state)} gas flow setpoint(s)...")
            
            for channel_name, setpoint in self.saved_gas_flow_state.items():
                try:
                    # Restore the setpoint
                    self.gas_controller.set_flow_rate(channel_name, setpoint)
                    print(f"    ✅ Restored {channel_name}: {setpoint} sccm")
                    time.sleep(0.3)  # Small delay between commands
                except Exception as e:
                    print(f"    ❌ Failed to restore {channel_name}: {e}")
            
            print("  ✅ Gas flow state restoration complete")
            
            # Clear saved state after restoration
            self.saved_gas_flow_state = {}
            
        except Exception as e:
            print(f"  ❌ Error restoring gas flow state: {e}")
    
    def attempt_arduino_reconnection(self) -> bool:
        """Attempt to reconnect to Arduino after detecting communication failures.
        
        Returns:
            True if reconnection successful, False otherwise
        """
        if self.arduino_reconnection_in_progress:
            print("🔄 Arduino reconnection already in progress, skipping...")
            return False
        
        self.arduino_reconnection_in_progress = True
        print("\\n" + "="*70)
        print("🔄 ARDUINO COMMUNICATION FAILURE - AUTOMATIC RECONNECTION")
        print("="*70)
        
        # Step 1: Save current gas flow state
        print("📦 Step 1: Saving current gas flow state...")
        self._save_gas_flow_state()
        
        try:
            # Step 2: Stop timers during reconnection
            timers_to_restart = []
            if self.status_timer.isActive():
                self.status_timer.stop()
                timers_to_restart.append('status')
            if self.input_timer.isActive():
                self.input_timer.stop()
                timers_to_restart.append('input')
            
            # Attempt reconnection
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                print(f"🔄 Reconnection attempt {attempt}/{max_attempts}...")
                
                try:
                    # Disconnect first
                    if self.arduino.is_connected:
                        print("🔌 Disconnecting from Arduino...")
                        self.arduino.disconnect()
                        time.sleep(0.5)
                    
                    # Try to reconnect
                    print("🔌 Attempting auto-connect...")
                    if self.arduino.auto_connect():
                        print(f"✅ Arduino reconnection successful on attempt {attempt}")
                        
                        # Verify connection with test command
                        time.sleep(0.5)
                        test_result = self.arduino.send_command("GET_RELAY_STATES", timeout=3.0)
                        if test_result and test_result != "TIMEOUT" and test_result != "ERROR":
                            print(f"✅ Arduino communication verified")
                            
                            # Reset failure counter
                            self.arduino_consecutive_failures = 0
                            
                            # Restart timers
                            if 'status' in timers_to_restart:
                                self.status_timer.start()
                            if 'input' in timers_to_restart:
                                QTimer.singleShot(1000, lambda: self.input_timer.start())
                            
                            # Restore gas flow state
                            print("🔄 Step 4: Restoring gas flow state...")
                            QTimer.singleShot(1500, self._restore_gas_flow_state)
                            
                            print("="*70)
                            print("✅ RECONNECTION COMPLETE - SYSTEM OPERATIONAL")
                            print("="*70 + "\n")
                            
                            # Show success message to user
                            QMessageBox.information(
                                self,
                                "Arduino Reconnected",
                                "Arduino connection has been restored.\n\nGas flow settings are being restored...\n\nSystem operation can continue."
                            )
                            
                            return True
                        else:
                            print(f"⚠️ Reconnection succeeded but communication test failed")
                    else:
                        print(f"⚠️ Reconnection attempt {attempt} failed")
                        
                except Exception as e:
                    print(f"❌ Error during reconnection attempt {attempt}: {e}")
                
                # Wait before next attempt
                if attempt < max_attempts:
                    wait_time = attempt * 2.0
                    print(f"⏳ Waiting {wait_time}s before next attempt...")
                    time.sleep(wait_time)
            
            # All attempts failed
            print(f"❌ Failed to reconnect Arduino after {max_attempts} attempts")
            QMessageBox.critical(
                self,
                "Arduino Connection Lost",
                f"Failed to reconnect to Arduino after {max_attempts} attempts.\n\n"
                "System is now in error state. Please check:\n"
                "1. Arduino USB connection\n"
                "2. Arduino power\n"
                "3. USB cable quality\n\n"
                "You may need to restart the application."
            )
            return False
            
        finally:
            self.arduino_reconnection_in_progress = False
    
    def _ensure_gas_controller_running(self) -> bool:
        """Ensure gas controller is running, start if needed. Returns True if running."""
        # If gas controller not initialized yet, initialize it synchronously
        if not self.gas_controller:
            print("🌀 Gas controller not initialized - initializing now for sputter mode...")
            try:
                # Exclude Arduino port if connected
                excluded = []
                if self.arduino and self.arduino.is_connected and self.arduino.serial_port:
                    excluded.append(self.arduino.serial_port.port)
                    print(f"🌀 Excluding Arduino port {self.arduino.serial_port.port} from MFC scan")
                
                # Create gas controller synchronously (we need it NOW for sputter mode)
                self.gas_controller = GasFlowController(
                    self.cfg.gas_control, 
                    self.safety_controller, 
                    excluded_ports=excluded,
                    arduino_controller=self.arduino
                )
                print("✅ Gas controller initialized successfully")
                
                # Wire MFC controls now that gas controller is ready
                try:
                    self._wire_mfc_controls()
                except Exception as e:
                    print(f"⚠️ Could not wire MFC controls: {e}")
                
            except Exception as e:
                print(f"❌ Failed to initialize gas controller: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        try:
            # Check if already running (subprocess controller has _process attribute)
            if hasattr(self.gas_controller, '_process') and self.gas_controller._process is not None:
                return True
            
            # Start gas controller
            print("🌀 Starting gas controller for sputter operation...")
            self.gas_controller.start()
            
            # Start MFC timer for monitoring
            if not self.mfc_timer.isActive():
                self.update_mfc_timer_interval()
                self.mfc_timer.start()
                print("DEBUG: MFC timer started")
            
            # Initialize MFC cache
            QTimer.singleShot(500, self.schedule_mfc_update)
            return True
            
        except Exception as e:
            print(f"❌ Failed to start gas controller: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _stop_gas_controller_if_not_needed(self) -> None:
        """Stop gas controller if not in sputter mode to save resources."""
        if not self.gas_controller:
            return
        
        # Only keep running during sputter operations
        if self.system_status == 'sputter':
            return
        
        try:
            # Check if running
            if hasattr(self.gas_controller, '_process') and self.gas_controller._process is not None:
                print("🌀 Stopping gas controller (not in sputter mode)...")
                self.gas_controller.stop()
                
                # Stop MFC timer to reduce overhead
                if self.mfc_timer.isActive():
                    self.mfc_timer.stop()
                    print("DEBUG: MFC timer stopped")
                    
        except Exception as e:
            print(f"⚠️ Error stopping gas controller: {e}")

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
                go_to_standby = _import_from_auto_procedures('go_to_standby')
                
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
                        print("💡 Chamber light turned ON - will auto-off in 300 seconds")
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
            go_to_default_state = _import_from_auto_procedures('go_to_default_state')
            
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
                        # Set cursor to pointer to indicate clickability
                        widget.setCursor(Qt.PointingHandCursor)
                        print(f"DEBUG: Successfully wired click handler for {widget_name}")
                    except Exception as e:
                        print(f"DEBUG: Failed to wire {widget_name}: {e}")
                else:
                    print(f"DEBUG: Widget {widget_name} not found for MFC {mfc_id}")

    def _show_mfc_setpoint_dialog(self, mfc_id: str) -> None:
        """Show setpoint dialog for the specified MFC."""
        print(f"🎛️ DEBUG: _show_mfc_setpoint_dialog called for {mfc_id}")
        print(f"    System status: {self.system_status}")
        print(f"    Gas controller: {self.gas_controller}")
        print(f"    Gas controller running: {hasattr(self.gas_controller, '_process') and self.gas_controller._process is not None if self.gas_controller else False}")
        
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
    
    def zero_gas_flows(self) -> None:
        """Zero all gas flows, close gas valves, and shutdown gas controller.
        
        This is a utility function accessible from Tools menu for safely
        shutting down gas system without needing to be in sputter mode.
        """
        print("🌀 Starting Zero Gas Flows procedure...")
        
        # Show confirmation dialog
        reply = QMessageBox.question(
            self, "Zero Gas Flows",
            "This will:\n"
            "1. Start gas controller (if not running)\n"
            "2. Set all MFC flows to 0 SCCM\n"
            "3. Close all gas valves\n"
            "4. Stop gas controller\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            print("❌ Zero Gas Flows cancelled by user")
            return
        
        # Execute in background thread using the gas_methods module function
        class ZeroFlowsWorker(QRunnable):
            def __init__(self, parent_window):
                super().__init__()
                self.parent = parent_window
                self.signals = ProcedureSignals()
            
            def run(self):
                # Call the module function with all required parameters
                success, message = execute_zero_gas_flows(
                    gas_controller=self.parent.gas_controller,
                    arduino_controller=self.parent.arduino,
                    safety_controller=self.parent.safety_controller,
                    relay_map=self.parent.relay_map,
                    mfc_timer=self.parent.mfc_timer if hasattr(self.parent, 'mfc_timer') else None
                )
                self.signals.finished.emit(success, message)
        
        def on_complete(success: bool, message: str):
            """Handle completion in main thread."""
            if success:
                QMessageBox.information(self, "Success", message)
            else:
                QMessageBox.warning(self, "Failed", message)
            print(f"🌀 Zero Gas Flows procedure complete: {message}")
        
        # Start worker
        worker = ZeroFlowsWorker(self)
        worker.signals.finished.connect(on_complete)
        
        if hasattr(self, 'threadpool') and self.threadpool is not None:
            self.threadpool.start(worker)
        else:
            # Fallback: show warning that this will block
            QMessageBox.warning(
                self, "Warning",
                "Thread pool not available. This operation may block the GUI briefly."
            )
            success, message = execute_zero_gas_flows(
                gas_controller=self.gas_controller,
                arduino_controller=self.arduino,
                safety_controller=self.safety_controller,
                relay_map=self.relay_map,
                mfc_timer=self.mfc_timer if hasattr(self, 'mfc_timer') else None
            )
            on_complete(success, message)

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
    
    def _start_procedure_worker(self, procedure_func, on_finished_callback):
        """Start a procedure in background thread with standardized error handling.
        
        Args:
            procedure_func: The procedure function to execute
            on_finished_callback: Callback function(success: bool, message: str)
        """
        worker = ProcedureWorker(
            procedure_func,
            arduino=self.arduino,
            safety=self.safety_controller,
            relay_map=self.relay_map
        )
        worker.signals.finished.connect(on_finished_callback)
        
        if hasattr(self, 'threadpool') and self.threadpool is not None:
            self.threadpool.start(worker)
        else:
            # Fallback: run synchronously
            result = procedure_func(
                arduino=self.arduino,
                safety=self.safety_controller,
                relay_map=self.relay_map
            )
            on_finished_callback(builtins.bool(result), '' if result is True else str(result))
    
    def _run_procedure(self, procedure_name: str, button_name: str, 
                      new_status: str, success_status: str,
                      confirmation_dialog_func=None,
                      custom_success_handler=None):
        """Generic procedure runner - eliminates repetitive code.
        
        Args:
            procedure_name: Name of procedure function in auto_procedures module
            button_name: Button identifier for tracking current procedure
            new_status: System status to set when procedure starts
            success_status: System status to set when procedure completes successfully
            confirmation_dialog_func: Optional function returning True/False for confirmation
            custom_success_handler: Optional function(message: str) for custom success handling
        """
        print(f"Running {procedure_name.upper().replace('_', ' ')}...")
        
        # Check if procedure can be started
        if not self.can_start_procedure(procedure_name):
            # Check if we have a specific safety error message
            error_msg = f"Cannot start {procedure_name.replace('_', ' ')} in current system state: {self.system_status}"
            if hasattr(self, '_last_procedure_safety_error') and procedure_name in self._last_procedure_safety_error:
                error_msg = self._last_procedure_safety_error[procedure_name]
            
            QMessageBox.warning(
                self, "Cannot Start Procedure",
                error_msg
            )
            return
        
        # Optional confirmation dialog
        if confirmation_dialog_func is not None:
            if not confirmation_dialog_func():
                print(f"{procedure_name} cancelled by user")
                return
        
        # Set current procedure and update system status
        self.current_procedure = button_name
        self.set_system_status(new_status)
        self._update_auto_procedure_button_states()
        
        try:
            # Import procedure function
            procedure_func = _import_from_auto_procedures(procedure_name)
            
            # Define completion handler
            def on_finished(success: bool, message: str) -> None:
                if success:
                    # Check for custom success handler (e.g., load/unload gate open)
                    if custom_success_handler is not None:
                        custom_success_handler(message)
                    else:
                        # Standard success handling
                        QMessageBox.information(
                            self, "Success",
                            f"{procedure_name.replace('_', ' ').title()} completed successfully!"
                        )
                        self.set_system_status(success_status)
                        self.update_safety_state()
                        QTimer.singleShot(100, lambda: self._clear_current_procedure())
                else:
                    # Failure handling - return to default state for safety
                    print(f"⚠️ Procedure '{procedure_name}' failed - returning system to default state")
                    
                    # Show error message to user
                    if message:
                        QMessageBox.warning(
                            self, "Procedure Failed",
                            f"{procedure_name.replace('_', ' ').title()} failed: {message}\n\n"
                            "System will return to default state for safety."
                        )
                    else:
                        QMessageBox.warning(
                            self, "Procedure Failed",
                            f"{procedure_name.replace('_', ' ').title()} failed. Check console for details.\n\n"
                            "System will return to default state for safety."
                        )
                    
                    # Attempt to return to default state
                    self._return_to_default_after_failure()
            
            # Start the procedure worker
            self._start_procedure_worker(procedure_func, on_finished)
            
        except ImportError:
            QMessageBox.critical(self, "Error", "Auto procedures module not found.\n\nSystem will return to default state.")
            self._return_to_default_after_failure()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"{procedure_name.replace('_', ' ').title()} failed: {str(e)}\n\nSystem will return to default state.")
            self._return_to_default_after_failure()
    
    def _return_to_default_after_failure(self) -> None:
        """Return system to default state after procedure failure.
        
        This runs in a background worker to avoid blocking the GUI.
        """
        try:
            go_to_default_state = _import_from_auto_procedures('go_to_default_state')
            
            def on_default_complete(success: bool, message: str) -> None:
                if success:
                    print("✅ System successfully returned to default state after procedure failure")
                    self.set_system_status('default')
                    self.update_safety_state()
                else:
                    print(f"⚠️ Warning: Failed to return to default state: {message}")
                    QMessageBox.warning(
                        self, "Default State Failed",
                        f"Could not return system to default state.\n\n{message}\n\n"
                        "Please manually verify system state and use 'Go to Default' if needed."
                    )
                    self.set_system_status('error')
                
                self._clear_current_procedure()
            
            # Start background worker to go to default state
            self._start_procedure_worker(go_to_default_state, on_default_complete)
            
        except Exception as e:
            print(f"❌ Exception while attempting to return to default state: {e}")
            self.set_system_status('error')
            self._clear_current_procedure()
            QMessageBox.critical(
                self, "Critical Error",
                f"Failed to return system to default state after procedure failure.\n\n{str(e)}\n\n"
                "Please manually verify system state and take appropriate action."
            )
    
    def run_pump_procedure(self) -> None:
        """Run the automatic pump procedure."""
        self._run_procedure('pump_procedure', 'pushButton_2', 'pumping', 'high_vacuum')

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
        def confirm_vent():
            """Show confirmation dialog for venting."""
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

            dialog.resize(700, 200)
            return dialog.exec() == QDialog.Accepted and confirmed
        
        self._run_procedure('vent_procedure', 'pushButton_3', 'venting', 'vented',
                           confirmation_dialog_func=confirm_vent)

    def run_sputter_procedure(self) -> None:
        """Run the automatic sputter procedure."""
        def custom_sputter_success_handler(message: str):
            """Custom success handler for sputter procedure."""
            # Always stop MFC flows when sputter procedure ends
            self.stop_all_mfc_flows()
            
            QMessageBox.information(self, "Success", "Sputter procedure completed successfully!")
            # After sputter completes the system returns to high vacuum
            self.set_system_status('high_vacuum')  # This triggers gas controller stop
            self.update_safety_state()
            QTimer.singleShot(100, lambda: self._clear_current_procedure())
        
        def custom_sputter_failure_handler():
            """Custom failure handler for sputter procedure."""
            self.stop_all_mfc_flows()
            # Gas controller will be stopped by set_system_status call in error handler
        
        # Store original state before modifying _run_procedure behavior
        print(f"DEBUG: Setting current_procedure = 'pushButton_6'")
        
        # Call parent procedure runner with sputter-specific settings
        # We need to set procedure first so state transitions work
        self.current_procedure = 'pushButton_6'
        print(f"DEBUG: Setting system status to 'sputter'")
        self.set_system_status('sputter')
        self._update_auto_procedure_button_states()
        
        print(f"DEBUG: Updating safety state after setting procedure")
        self.update_safety_state()
        
        # Ensure gas controller is running before starting flows
        if not self._ensure_gas_controller_running():
            QMessageBox.warning(self, "Gas Controller Error", 
                              "Failed to start gas controller. Sputter procedure cannot proceed.")
            self.set_system_status(self.previous_system_status)
            self._clear_current_procedure()
            return
        
        # Start MFC flows for sputter procedure (if configured)
        self.start_sputter_mfc_flows()
        
        try:
            procedure_func = _import_from_auto_procedures('sputter_procedure')
            
            def on_finished(success: bool, message: str) -> None:
                if success:
                    custom_sputter_success_handler(message)
                else:
                    custom_sputter_failure_handler()
                    if message:
                        QMessageBox.warning(self, "Procedure Failed", f"Sputter procedure failed: {message}")
                    else:
                        QMessageBox.warning(self, "Procedure Failed", "Sputter procedure failed. Check console for details.")
                    self.set_system_status(self.previous_system_status)
                    self.current_procedure = None
                    self._update_auto_procedure_button_states()
            
            self._start_procedure_worker(procedure_func, on_finished)
            
        except (ImportError, Exception) as e:
            QMessageBox.critical(self, "Error", f"Sputter procedure failed: {e}")
            self.stop_all_mfc_flows()
            self.set_system_status(self.previous_system_status)
            self._clear_current_procedure()

    def run_vent_loadlock_procedure(self) -> None:
        """Run the automatic load-lock vent procedure."""
        self._run_procedure('vent_loadlock_procedure', 'pushButton_4', 
                           'loadlock_venting', 'high_vacuum')

    def run_load_unload_procedure(self) -> None:
        """Run the automatic load/unload procedure."""
        def custom_load_unload_success_handler(message: str):
            """Custom handler for load/unload special case."""
            if message == "GATE_OPEN_WAITING_USER":
                # Show the load/unload dialog in the main thread
                self._show_load_unload_dialog()
            else:
                # Normal success
                QMessageBox.information(self, "Success", "Load/unload procedure completed successfully!")
                self.set_system_status('high_vacuum')
                self.update_safety_state()
                QTimer.singleShot(100, lambda: self._clear_current_procedure())
        
        self._run_procedure('load_unload_procedure', 'pushButton_5', 
                           'load_unload', 'high_vacuum',
                           custom_success_handler=custom_load_unload_success_handler)

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
                set_relay_safe = _import_from_auto_procedures('set_relay_safe')
                
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
                set_relay_safe = _import_from_auto_procedures('set_relay_safe')
                
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
        gate_closed = False
        light_turned_off = False
        
        try:
            # Import the procedure function to close the gate valve
            set_relay_safe = _import_from_auto_procedures('set_relay_safe')
            
            # Update safety state before closing valve
            self.update_safety_state()
            
            # CRITICAL SAFETY CHECK: Verify arm is in home position before closing gate valve
            print("🔍 Verifying load-lock arm is in home position before closing gate valve...")
            arm_home = False
            try:
                digital_inputs = self.arduino.get_digital_inputs()
                if digital_inputs and len(digital_inputs) > 1:
                    arm_home = bool(digital_inputs[1])  # digital_inputs[1] = arm home interlock
                    if arm_home:
                        print("✅ Load-lock arm verified in home position")
                    else:
                        print("❌ CRITICAL: Load-lock arm NOT in home position!")
                else:
                    print("⚠️ Warning: Could not read digital inputs")
            except Exception as e:
                print(f"⚠️ Warning: Error reading arm position: {e}")
            
            if not arm_home:
                # CRITICAL: Cannot close gate valve if arm not home
                QMessageBox.critical(
                    self,
                    "CRITICAL SAFETY: Arm Not Home",
                    "Cannot close load-lock gate valve!\n\n"
                    "The load-lock arm is NOT in home position.\n\n"
                    "WARNING: Gate valve remains OPEN until arm is returned to home position.\n\n"
                    "Please return the arm to home position and try closing the gate valve manually."
                )
                self.set_system_status('error')
                self._clear_current_procedure()
                return
            
            # ARM IS HOME - Safe to close gate valve
            print("Completing load/unload procedure - closing gate valve...")
            if set_relay_safe('btnValveLoadLockGate', False, self.arduino, self.safety_controller, self.relay_map):
                print("✅ Load-lock gate valve closed successfully")
                gate_closed = True
                
                # Turn off chamber light after load/unload complete
                print("💡 Turning off chamber light...")
                if set_relay_safe('btnLightBulb', False, self.arduino, self.safety_controller, self.relay_map):
                    print("✅ Chamber light turned off")
                    light_turned_off = True
                else:
                    print("⚠️ Warning: Failed to turn off chamber light (non-critical)")
                
                QMessageBox.information(self, "Success", "Load/unload procedure completed successfully!")
                # Return to high_vacuum as specified in YAML
                self.set_system_status('high_vacuum')
                self.update_safety_state()
                QTimer.singleShot(100, lambda: self._clear_current_procedure())
            else:
                print("❌ CRITICAL: Failed to close load-lock gate valve!")
                QMessageBox.critical(
                    self,
                    "CRITICAL: Valve Close Failed",
                    "Failed to close load-lock gate valve!\n\n"
                    "WARNING: Gate valve remains OPEN!\n\n"
                    "Please manually close the gate valve immediately."
                )
                self.set_system_status('error')
                self._clear_current_procedure()
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"❌ CRITICAL ERROR in load/unload completion:\n{error_details}")
            
            # EMERGENCY: Try to close gate valve with direct relay command
            # BUT ONLY IF ARM IS IN HOME POSITION
            if not gate_closed:
                print("🚨 EMERGENCY: Checking arm position before attempting gate valve close...")
                
                # CRITICAL SAFETY CHECK: Verify arm home position
                arm_home = False
                try:
                    digital_inputs = self.arduino.get_digital_inputs()
                    if digital_inputs and len(digital_inputs) > 1:
                        arm_home = bool(digital_inputs[1])
                        if arm_home:
                            print("✅ ARM IS HOME - Safe to attempt emergency gate valve close")
                        else:
                            print("❌ CRITICAL: ARM NOT HOME - Cannot close gate valve!")
                except Exception as e2:
                    print(f"⚠️ Could not verify arm position: {e2}")
                
                if arm_home:
                    # ARM IS HOME - Safe to attempt emergency close
                    try:
                        gate_valve_relay = self.relay_map.get('btnValveLoadLockGate')
                        if gate_valve_relay and self.arduino and self.arduino.is_connected:
                            self.arduino.set_relay(gate_valve_relay, False)
                            self.safety_controller.relay_states['btnValveLoadLockGate'] = False
                            print("✅ Emergency gate valve close successful")
                            gate_closed = True
                    except Exception as e3:
                        print(f"❌ Emergency gate valve close failed: {e3}")
                else:
                    print("🚨 SAFETY OVERRIDE PREVENTED: Gate valve NOT closed because arm not in home position")
            
            # Try to turn off light
            if not light_turned_off:
                try:
                    light_relay = self.relay_map.get('btnLightBulb')
                    if light_relay and self.arduino and self.arduino.is_connected:
                        self.arduino.set_relay(light_relay, False)
                        print("✅ Chamber light turned off")
                except Exception:
                    pass  # Light is non-critical
            
            # Show error to user
            error_msg = f"Error completing load/unload procedure: {str(e)}\n\n"
            if gate_closed:
                error_msg += "Gate valve was closed successfully via emergency command."
            else:
                error_msg += "CRITICAL: Gate valve remains OPEN!\n\n"
                # Check if it's because arm not home
                try:
                    digital_inputs = self.arduino.get_digital_inputs()
                    if digital_inputs and len(digital_inputs) > 1 and not bool(digital_inputs[1]):
                        error_msg += "SAFETY: Gate valve cannot close because load-lock arm is not in home position.\n\n"
                        error_msg += "Please return arm to home position and close gate valve manually."
                    else:
                        error_msg += "Please close manually immediately!"
                except Exception:
                    error_msg += "Please close manually immediately!"
            
            QMessageBox.critical(
                self,
                "Load/Unload Completion Error",
                error_msg
            )
            self.set_system_status('error' if not gate_closed else 'high_vacuum')
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
                    # Reset failure counter on successful communication
                    self.arduino_consecutive_failures = 0
                    
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
                    # No connection or error - increment failure counter
                    self.arduino_consecutive_failures += 1
                    print(f"⚠️ Arduino communication failure ({self.arduino_consecutive_failures}/{self.max_consecutive_failures})")
                    
                    # Trigger automatic reconnection after threshold
                    if self.arduino_consecutive_failures >= self.max_consecutive_failures:
                        print(f"🔴 Maximum consecutive failures reached - triggering reconnection")
                        # Reset counter to prevent repeated triggers
                        self.arduino_consecutive_failures = 0
                        # Attempt reconnection in background using QTimer to avoid blocking
                        QTimer.singleShot(100, self.attempt_arduino_reconnection)
                    
                    # Set all to False for safety
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

    def run_quick_reset_to_standby(self) -> None:
        """Run quick reset to standby procedure - forces all relays OFF immediately."""
        # Confirm with user
        reply = QMessageBox.warning(
            self,
            "Quick Reset to Standby",
            "This will immediately force ALL relays OFF, bypassing normal shutdown sequences.\n\n"
            "⚠️ WARNING: This bypasses safety checks and normal procedures.\n"
            "Only use this for emergency resets or when relay states are incorrect.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Import the procedure
        quick_reset_to_standby = _import_from_auto_procedures('quick_reset_to_standby')
        
        # Check if another procedure is running
        if self.current_procedure is not None:
            cancel_reply = QMessageBox.question(
                self,
                "Procedure Running",
                f"Procedure '{self.current_procedure}' is currently running.\n\n"
                "Cancel it and proceed with quick reset?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if cancel_reply != QMessageBox.StandardButton.Yes:
                return
            
            # Cancel the running procedure
            cancel_running_procedures = _import_from_auto_procedures('cancel_running_procedures')
            
            cancel_running_procedures()
            self.current_procedure = None
            self._update_auto_procedure_button_states()
        
        # Set current procedure
        self.current_procedure = 'quick_reset'
        self._update_auto_procedure_button_states()
        
        # Define the worker function
        def worker_fn():
            return quick_reset_to_standby(
                arduino=self.arduino,
                safety=self.safety_controller,
                relay_map=self.relay_map
            )
        
        # Run in background thread
        worker = ProcedureWorker(worker_fn)
        worker.signals.finished.connect(
            lambda success, msg: self._on_quick_reset_complete(success, msg)
        )
        self.threadpool.start(worker)
        
        print("⚡ Quick reset to standby initiated...")
    
    def _on_quick_reset_complete(self, success: bool, message: str) -> None:
        """Handle completion of quick reset procedure."""
        self.current_procedure = None
        self._update_auto_procedure_button_states()
        
        if success:
            QMessageBox.information(
                self,
                "Quick Reset Complete",
                "All relays have been forced OFF.\n\n"
                "System is now in standby state."
            )
            # Update system status display
            self.set_system_status('standby')
        else:
            QMessageBox.warning(
                self,
                "Quick Reset Issues",
                f"Quick reset encountered errors:\n\n{message}\n\n"
                "Some relays may not have been set to OFF state.\n"
                "Check system state and try again if needed."
            )

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
    # Load config to get Arduino port
    from config import load_config
    cfg = load_config()
    arduino_port = cfg.serial.arduino_port if cfg.serial.arduino_port else None
    
    if arduino_port:
        print(f"📍 Using configured Arduino port: {arduino_port}")
    else:
        print("⚠️  No configured Arduino port, using auto-detection")
        print("    💡 Run detect_arduino_port.py to configure a specific port")
    
    arduino = ArduinoController(config_port=arduino_port)
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
    
    # Execute login dialog (blocks until user authenticates or cancels)
    dialog_result = login_dialog.exec()
    
    # CRITICAL: Cleanup RFID thread immediately after dialog completes
    # This ensures thread stops regardless of how dialog closed
    print("🧹 DEBUG: Cleaning up RFID thread after login dialog closed...")
    if hasattr(login_dialog, '_cleanup_rfid'):
        try:
            login_dialog._cleanup_rfid()
            print("✅ DEBUG: RFID thread cleanup completed")
        except Exception as e:
            print(f"⚠️ DEBUG: Error during RFID cleanup: {e}")
    
    # Check if login was successful
    if dialog_result != LoginDialog.Accepted:
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
