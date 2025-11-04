"""GUI widget for gas flow control integration.

This module provides PyQt5 widgets for displaying and controlling
gas flow in the sputter control GUI.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Any, Callable
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QPushButton, QSpinBox, QDoubleSpinBox, QComboBox, QProgressBar,
    QTextEdit, QGroupBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox
)
from PyQt5.QtCore import QTimer, pyqtSignal, Qt
from PyQt5.QtGui import QFont

# Support both package and script execution
try:
    from .controller import GasFlowController, MFCChannel, MFCReading  # type: ignore
    from .recipes import GasRecipe, RecipeExecutor, RecipeManager  # type: ignore
    from .safety_integration import GasFlowSafetyIntegration  # type: ignore
except ImportError:
    try:
        from controller import GasFlowController, MFCChannel, MFCReading  # type: ignore
        from recipes import GasRecipe, RecipeExecutor, RecipeManager  # type: ignore
        from safety_integration import GasFlowSafetyIntegration  # type: ignore
    except ImportError:
        # For development/testing
        GasFlowController = None
        MFCChannel = None
        MFCReading = None
        GasRecipe = None
        RecipeExecutor = None
        RecipeManager = None
        GasFlowSafetyIntegration = None


class MFCChannelWidget(QWidget):
    """Widget for controlling a single MFC channel."""
    
    flow_requested = pyqtSignal(str, float)  # channel_name, flow_rate
    
    def __init__(self, channel_name: str, channel_config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.channel_name = channel_name
        self.channel_config = channel_config
        self.logger = logging.getLogger(__name__)
        
        self.setup_ui()
        
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)  # Update every second
        
        # Current reading
        self.current_reading: Optional[MFCReading] = None
        
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Channel name header
        header = QLabel(f"{self.channel_name} ({self.channel_config.get('gas_type', 'Unknown')})")
        header.setFont(QFont("Arial", 12, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        # Status indicator
        self.status_label = QLabel("Disconnected")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.status_label)
        
        # Current readings group
        readings_group = QGroupBox("Current Readings")
        readings_layout = QGridLayout(readings_group)
        
        # Flow rate display
        readings_layout.addWidget(QLabel("Flow Rate:"), 0, 0)
        self.flow_display = QLabel("0.0 sccm")
        self.flow_display.setStyleSheet("font-weight: bold; color: blue;")
        readings_layout.addWidget(self.flow_display, 0, 1)
        
        # Setpoint display
        readings_layout.addWidget(QLabel("Setpoint:"), 1, 0)
        self.setpoint_display = QLabel("0.0 sccm")
        readings_layout.addWidget(self.setpoint_display, 1, 1)
        
        # Pressure display
        readings_layout.addWidget(QLabel("Pressure:"), 2, 0)
        self.pressure_display = QLabel("0.0 psia")
        readings_layout.addWidget(self.pressure_display, 2, 1)
        
        # Temperature display
        readings_layout.addWidget(QLabel("Temperature:"), 3, 0)
        self.temperature_display = QLabel("0.0 °C")
        readings_layout.addWidget(self.temperature_display, 3, 1)
        
        layout.addWidget(readings_group)
        
        # Control group
        control_group = QGroupBox("Flow Control")
        control_layout = QVBoxLayout(control_group)
        
        # Flow rate input
        flow_input_layout = QHBoxLayout()
        flow_input_layout.addWidget(QLabel("Set Flow:")
                                   )
        self.flow_spinbox = QDoubleSpinBox()
        self.flow_spinbox.setRange(0.0, self.channel_config.get('max_flow', 100.0))
        self.flow_spinbox.setDecimals(1)
        self.flow_spinbox.setSuffix(" sccm")
        flow_input_layout.addWidget(self.flow_spinbox)
        
        self.set_flow_button = QPushButton("Set Flow")
        self.set_flow_button.clicked.connect(self.on_set_flow_clicked)
        flow_input_layout.addWidget(self.set_flow_button)
        
        control_layout.addLayout(flow_input_layout)
        
        # Quick buttons
        quick_layout = QHBoxLayout()
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.on_stop_clicked)
        self.stop_button.setStyleSheet("background-color: #ff6b6b; color: white; font-weight: bold;")
        quick_layout.addWidget(self.stop_button)
        
        control_layout.addLayout(quick_layout)
        
        layout.addWidget(control_group)
        
        # Initially disable controls
        self.set_controls_enabled(False)
    
    def set_controls_enabled(self, enabled: bool):
        """Enable or disable control widgets."""
        self.flow_spinbox.setEnabled(enabled)
        self.set_flow_button.setEnabled(enabled)
        self.stop_button.setEnabled(enabled)
    
    def update_reading(self, reading: Optional[MFCReading]):
        """Update the widget with new reading data."""
        self.current_reading = reading
        # Display will be updated by timer
    
    def update_status(self, status: Dict[str, Any]):
        """Update status display."""
        connection_status = status.get('connection_status', 'unknown')
        
        if connection_status == 'connected':
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.set_controls_enabled(True)
        elif connection_status == 'error':
            error_msg = status.get('last_error', 'Unknown error')
            self.status_label.setText(f"Error: {error_msg}")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            self.set_controls_enabled(False)
        else:
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            self.set_controls_enabled(False)
    
    def update_display(self):
        """Update display with current reading."""
        if not self.current_reading:
            return
        
        try:
            # Update flow rate
            self.flow_display.setText(f"{self.current_reading.mass_flow:.1f} sccm")
            
            # Update setpoint
            self.setpoint_display.setText(f"{self.current_reading.setpoint:.1f} sccm")
            
            # Update pressure
            self.pressure_display.setText(f"{self.current_reading.pressure:.2f} psia")
            
            # Update temperature
            self.temperature_display.setText(f"{self.current_reading.temperature:.1f} °C")
            
        except Exception as e:
            self.logger.error(f"Error updating display for {self.channel_name}: {e}")
    
    def on_set_flow_clicked(self):
        """Handle set flow button click."""
        flow_rate = self.flow_spinbox.value()
        self.flow_requested.emit(self.channel_name, flow_rate)
    
    def on_stop_clicked(self):
        """Handle stop button click."""
        self.flow_requested.emit(self.channel_name, 0.0)
        self.flow_spinbox.setValue(0.0)


class GasControlWidget(QWidget):
    """Main gas control widget for the sputter GUI."""
    
    def __init__(self, gas_controller: Optional[GasFlowController] = None, 
                 safety_integration: Optional[GasFlowSafetyIntegration] = None,
                 parent=None):
        super().__init__(parent)
        self.gas_controller = gas_controller
        self.safety_integration = safety_integration
        self.logger = logging.getLogger(__name__)
        
        # Channel widgets
        self.channel_widgets: Dict[str, MFCChannelWidget] = {}
        
        # Recipe components
        self.recipe_manager: Optional[RecipeManager] = None
        self.recipe_executor: Optional[RecipeExecutor] = None
        
        self.setup_ui()
        
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(2000)  # Update every 2 seconds
        
        # Initialize if controller is available
        if self.gas_controller:
            self.initialize_controller()
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Gas Flow Control")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Main content in horizontal layout
        main_layout = QHBoxLayout()
        
        # Left side: Channel controls
        channels_group = QGroupBox("MFC Channels")
        channels_layout = QHBoxLayout(channels_group)
        
        # Placeholder for channel widgets (will be populated when controller is set)
        self.channels_container = QWidget()
        self.channels_container_layout = QHBoxLayout(self.channels_container)
        channels_layout.addWidget(self.channels_container)
        
        main_layout.addWidget(channels_group, 2)  # 2/3 of width
        
        # Right side: Status and controls
        right_panel = QVBoxLayout()
        
        # Safety status
        safety_group = QGroupBox("Safety Status")
        safety_layout = QVBoxLayout(safety_group)
        
        self.safety_status_label = QLabel("Safety status unknown")
        safety_layout.addWidget(self.safety_status_label)
        
        self.total_flow_label = QLabel("Total Flow: 0.0 sccm")
        self.total_flow_label.setFont(QFont("Arial", 10, QFont.Bold))
        safety_layout.addWidget(self.total_flow_label)
        
        right_panel.addWidget(safety_group)
        
        # Emergency controls
        emergency_group = QGroupBox("Emergency Controls")
        emergency_layout = QVBoxLayout(emergency_group)
        
        self.emergency_stop_button = QPushButton("EMERGENCY STOP")
        self.emergency_stop_button.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #cc3333;
            }
        """)
        self.emergency_stop_button.clicked.connect(self.on_emergency_stop)
        emergency_layout.addWidget(self.emergency_stop_button)
        
        self.stop_all_button = QPushButton("Stop All Flows")
        self.stop_all_button.setStyleSheet("background-color: orange; color: black; font-weight: bold;")
        self.stop_all_button.clicked.connect(self.on_stop_all)
        emergency_layout.addWidget(self.stop_all_button)
        
        right_panel.addWidget(emergency_group)
        
        # Recipe controls (simplified)
        recipe_group = QGroupBox("Quick Recipes")
        recipe_layout = QVBoxLayout(recipe_group)
        
        # Quick recipe buttons
        self.recipe_buttons = []
        quick_recipes = [
            ("Ar Only", {"Ar": 50.0, "O2": 0.0, "N2": 0.0}),
            ("Ar + O2", {"Ar": 40.0, "O2": 10.0, "N2": 0.0}),
            ("All Stop", {"Ar": 0.0, "O2": 0.0, "N2": 0.0})
        ]
        
        for recipe_name, flows in quick_recipes:
            button = QPushButton(recipe_name)
            button.clicked.connect(lambda checked, f=flows: self.set_quick_recipe(f))
            recipe_layout.addWidget(button)
            self.recipe_buttons.append(button)
        
        right_panel.addWidget(recipe_group)
        
        # Add stretch to push everything to top
        right_panel.addStretch()
        
        # Add right panel to main layout
        right_widget = QWidget()
        right_widget.setLayout(right_panel)
        main_layout.addWidget(right_widget, 1)  # 1/3 of width
        
        layout.addLayout(main_layout)
        
        # Initially disable controls
        self.set_controls_enabled(False)
    
    def set_gas_controller(self, gas_controller: GasFlowController):
        """Set the gas controller and initialize UI."""
        self.gas_controller = gas_controller
        self.initialize_controller()
    
    def set_safety_integration(self, safety_integration: GasFlowSafetyIntegration):
        """Set the safety integration."""
        self.safety_integration = safety_integration
    
    def initialize_controller(self):
        """Initialize UI components based on gas controller."""
        if not self.gas_controller:
            return
        
        # Clear existing channel widgets
        for widget in self.channel_widgets.values():
            widget.setParent(None)
        self.channel_widgets.clear()
        
        # Create channel widgets
        for channel_name, channel in self.gas_controller.channels.items():
            widget = MFCChannelWidget(
                channel_name, 
                {
                    'gas_type': channel.gas_type,
                    'max_flow': channel.max_flow
                },
                self
            )
            widget.flow_requested.connect(self.on_flow_requested)
            
            self.channel_widgets[channel_name] = widget
            self.channels_container_layout.addWidget(widget)
        
        # Initialize recipe components
        try:
            self.recipe_manager = RecipeManager()
            self.recipe_executor = RecipeExecutor(self.gas_controller)
        except Exception as e:
            self.logger.error(f"Failed to initialize recipe components: {e}")
        
        self.set_controls_enabled(True)
        self.logger.info(f"Initialized gas control UI with {len(self.channel_widgets)} channels")
    
    def set_controls_enabled(self, enabled: bool):
        """Enable or disable all controls."""
        for widget in self.channel_widgets.values():
            widget.set_controls_enabled(enabled)
        
        for button in self.recipe_buttons:
            button.setEnabled(enabled)
        
        self.stop_all_button.setEnabled(enabled)
        # Emergency stop should always be enabled
        self.emergency_stop_button.setEnabled(True)
    
    def update_status(self):
        """Update status displays."""
        if not self.gas_controller:
            return
        
        try:
            # Update channel widgets
            all_status = self.gas_controller.get_all_status()
            for channel_name, status in all_status.items():
                if channel_name in self.channel_widgets:
                    widget = self.channel_widgets[channel_name]
                    widget.update_status(status)
                    
                    # Update reading if available
                    reading_data = status.get('current_reading')
                    if reading_data:
                        # Convert dict back to MFCReading if needed
                        reading = MFCReading(
                            timestamp=reading_data.get('timestamp', 0.0),
                            pressure=reading_data.get('pressure', 0.0),
                            temperature=reading_data.get('temperature', 0.0),
                            volumetric_flow=reading_data.get('volumetric_flow', 0.0),
                            mass_flow=reading_data.get('mass_flow', 0.0),
                            setpoint=reading_data.get('setpoint', 0.0),
                            gas=reading_data.get('gas', ''),
                            control_point=reading_data.get('control_point', 'mass flow')
                        )
                        widget.update_reading(reading)
            
            # Update total flow
            total_flow = self.gas_controller.get_total_flow_rate()
            self.total_flow_label.setText(f"Total Flow: {total_flow:.1f} sccm")
            
            # Update safety status
            if self.safety_integration:
                safety_status = self.safety_integration.get_safety_status()
                self.update_safety_display(safety_status)
                
        except Exception as e:
            self.logger.error(f"Error updating gas control status: {e}")
    
    def update_safety_display(self, safety_status: Dict[str, Any]):
        """Update safety status display."""
        gas_enabled = safety_status.get('gas_flow_enabled', False)
        emergency_active = safety_status.get('emergency_stop_active', False)
        violations = safety_status.get('safety_violations', [])
        
        if emergency_active:
            status_text = "EMERGENCY STOP ACTIVE"
            status_color = "red"
        elif not gas_enabled:
            status_text = "Gas flow DISABLED"
            status_color = "orange"
        elif violations:
            status_text = f"Safety violations: {len(violations)}"
            status_color = "orange"
        else:
            status_text = "Safety OK"
            status_color = "green"
        
        self.safety_status_label.setText(status_text)
        self.safety_status_label.setStyleSheet(f"color: {status_color}; font-weight: bold;")
    
    def on_flow_requested(self, channel: str, flow_rate: float):
        """Handle flow rate change request."""
        if not self.gas_controller:
            self.show_error("Gas controller not available")
            return
        
        # Check safety if integration is available
        if self.safety_integration:
            approved, reason = self.safety_integration.get_flow_approval(channel, flow_rate)
            if not approved:
                self.show_error(f"Flow request denied: {reason}")
                return
        
        # Set the flow rate
        success = self.gas_controller.set_flow_rate(channel, flow_rate)
        if not success:
            self.show_error(f"Failed to set flow rate for {channel}")
    
    def set_quick_recipe(self, flows: Dict[str, float]):
        """Set flows for a quick recipe."""
        if not self.gas_controller:
            return
        
        for channel, flow_rate in flows.items():
            if channel in self.gas_controller.channels:
                self.gas_controller.set_flow_rate(channel, flow_rate)
                
                # Update spinbox in widget
                if channel in self.channel_widgets:
                    self.channel_widgets[channel].flow_spinbox.setValue(flow_rate)
    
    def on_stop_all(self):
        """Handle stop all flows button."""
        if not self.gas_controller:
            return
        
        reply = QMessageBox.question(
            self, 
            "Stop All Flows",
            "Are you sure you want to stop all gas flows?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success = self.gas_controller.stop_all_flows()
            if success:
                # Reset all spinboxes
                for widget in self.channel_widgets.values():
                    widget.flow_spinbox.setValue(0.0)
            else:
                self.show_error("Failed to stop all flows")
    
    def on_emergency_stop(self):
        """Handle emergency stop button."""
        reply = QMessageBox.critical(
            self,
            "EMERGENCY STOP",
            "This will immediately stop all gas flows and disable the gas system.\n\n"
            "Are you sure you want to trigger emergency stop?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.safety_integration:
                self.safety_integration._trigger_emergency_gas_stop("Manual emergency stop")
            elif self.gas_controller:
                self.gas_controller.stop_all_flows()
                
            # Reset all spinboxes
            for widget in self.channel_widgets.values():
                widget.flow_spinbox.setValue(0.0)
    
    def show_error(self, message: str):
        """Show error message to user."""
        QMessageBox.critical(self, "Gas Control Error", message)
        self.logger.error(f"Gas control error: {message}")
    
    def closeEvent(self, event):
        """Handle widget close event."""
        # Stop update timer
        self.update_timer.stop()
        super().closeEvent(event)