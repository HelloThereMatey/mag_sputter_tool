"""
MFC Setpoint Dialog for Gas Flow Control

This module provides a dialog for setting MFC flow rates during sputter operations.
"""

import builtins
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QDoubleSpinBox, QPushButton, QMessageBox, QFrame)
from PyQt5.QtCore import Qt
from typing import Optional


class MFCSetpointDialog(QDialog):
    """Dialog for setting MFC flow rate setpoints."""
    
    def __init__(self, mfc_name: str, current_setpoint: float = 0.0, 
                 max_flow: float = 200.0, parent=None, 
                 arduino_controller=None, safety_controller=None, relay_map=None):
        super().__init__(parent)
        self.mfc_name = mfc_name
        self.setpoint_value = current_setpoint
        self.max_flow = max_flow
        
        # Controllers for valve operation
        self.arduino_controller = arduino_controller
        self.safety_controller = safety_controller
        self.relay_map = relay_map or {}
        
        # Determine the corresponding gas valve button name
        self.gas_valve_button = self._get_gas_valve_button(mfc_name)
        
        # Debug output to verify values being passed
        print(f"🐛 DEBUG: MFC Dialog - mfc_name={mfc_name}, current_setpoint={current_setpoint}, max_flow={max_flow}")
        print(f"🐛 DEBUG: MFC Dialog - gas_valve_button={self.gas_valve_button}")
        
        self.setWindowTitle(f"Set Flow Rate - {mfc_name} MFC")
        self.setFixedSize(380, 380)  # Increased height for proper content fit
        self.setModal(True)
        
        # Ensure dialog stays on top and is properly focused
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
        self.setup_ui()
    
    def _get_gas_valve_button(self, mfc_name: str) -> str:
        """Map MFC name to corresponding gas valve button name."""
        # Standard mapping based on sput.yml configuration
        valve_mapping = {
            'Ar': 'btnValveGas1',
            'N2': 'btnValveGas2', 
            'O2': 'btnValveGas3'
        }
        return valve_mapping.get(mfc_name, '')
        
    def setup_ui(self):
        """Setup the dialog UI."""
        # Set overall dialog styling to match main GUI
        self.setStyleSheet("""
            QDialog {
                background-color: #101418;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel(f"Set Flow Rate for {self.mfc_name} MFC")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 14pt;
                font-weight: bold;
                color: #e0e0e0;
                margin: 10px;
            }
        """)
        layout.addWidget(title_label)
        
        # Current setpoint display
        current_frame = QFrame()
        current_frame.setStyleSheet("""
            QFrame {
                background: #2a2a2a;
                border: 1px solid #555;
                border-radius: 5px;
                margin: 5px;
                padding: 5px;
            }
        """)
        current_layout = QHBoxLayout(current_frame)
        
        current_label = QLabel("Current setpoint:")
        current_label.setStyleSheet("color: #e0e0e0; font-weight: bold;")
        current_value = QLabel(f"{self.setpoint_value:.1f} sccm")
        current_value.setStyleSheet("font-weight: bold; color: #4ac85a;")
        
        current_layout.addWidget(current_label)
        current_layout.addStretch()
        current_layout.addWidget(current_value)
        layout.addWidget(current_frame)
        
        # New setpoint input
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background: #2a2a2a;
                border: 1px solid #555;
                border-radius: 5px;
                margin: 5px;
                padding: 10px;
            }
        """)
        input_layout = QHBoxLayout(input_frame)
        
        setpoint_label = QLabel("New setpoint:")
        setpoint_label.setStyleSheet("color: #e0e0e0; font-weight: bold;")
        
        self.setpoint_spinbox = QDoubleSpinBox()
        self.setpoint_spinbox.setRange(0.0, self.max_flow)
        self.setpoint_spinbox.setDecimals(1)
        self.setpoint_spinbox.setSuffix(" sccm")
        self.setpoint_spinbox.setValue(self.setpoint_value)
        
        # Make the spinbox behave more like a line edit for text input
        self.setpoint_spinbox.setFocusPolicy(Qt.StrongFocus)
        self.setpoint_spinbox.setButtonSymbols(QDoubleSpinBox.UpDownArrows)
        self.setpoint_spinbox.setAccelerated(True)
        self.setpoint_spinbox.setKeyboardTracking(True)
        
        # Get the internal line edit and configure it
        line_edit = self.setpoint_spinbox.lineEdit()
        line_edit.setReadOnly(False)
        line_edit.setAlignment(Qt.AlignRight)
        
        self.setpoint_spinbox.setStyleSheet("""
            QDoubleSpinBox {
                background: #ffffff;
                color: #000000;
                border: 2px solid #4a7bc8;
                border-radius: 5px;
                padding: 8px;
                font-size: 12pt;
                font-weight: bold;
                selection-background-color: #4a7bc8;
                selection-color: #ffffff;
                min-height: 25px;
            }
            QDoubleSpinBox:focus {
                border-color: #4ac85a;
                background: #ffffff;
            }
            QDoubleSpinBox:hover {
                border-color: #6a9be8;
            }
            QDoubleSpinBox QLineEdit {
                background: #ffffff;
                color: #000000;
                border: none;
                padding: 2px;
                selection-background-color: #4a7bc8;
                selection-color: #ffffff;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                background: #2a2a2a;
                border: 1px solid #555;
                width: 20px;
                border-radius: 3px;
            }
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
                background: #4a7bc8;
            }
            QDoubleSpinBox::up-button:pressed, QDoubleSpinBox::down-button:pressed {
                background: #2a5c98;
            }
            QDoubleSpinBox::up-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 6px solid #ffffff;
                width: 0px;
                height: 0px;
            }
            QDoubleSpinBox::up-arrow:hover {
                border-bottom-color: #ffffff;
            }
            QDoubleSpinBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #ffffff;
                width: 0px;
                height: 0px;
            }
            QDoubleSpinBox::down-arrow:hover {
                border-top-color: #ffffff;
            }
        """)
        
        input_layout.addWidget(setpoint_label)
        input_layout.addWidget(self.setpoint_spinbox)
        layout.addWidget(input_frame)
        
        # Max flow info
        info_label = QLabel(f"Maximum flow: {self.max_flow:.0f} sccm")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("color: #aaa; font-size: 10pt; margin: 5px;")
        layout.addWidget(info_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background: #7a0000;
                color: #ffffff;
                border: 2px solid #aa0000;
                border-radius: 8px;
                font-weight: bold;
                font-size: 12pt;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: #aa0000;
            }
        """)
        self.cancel_button.clicked.connect(self.reject)
        
        self.ok_button = QPushButton("Set Flow")
        self.ok_button.setStyleSheet("""
            QPushButton {
                background: #1da237;
                color: #ffffff;
                border: 2px solid #2dc653;
                border-radius: 8px;
                font-weight: bold;
                font-size: 12pt;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: #2dc653;
            }
        """)
        self.ok_button.clicked.connect(self.accept_setpoint)
        self.ok_button.setDefault(True)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # Store reference to line edit for easier access
        self.line_edit = self.setpoint_spinbox.lineEdit()
        
        # Enable keyboard shortcuts
        self.line_edit.returnPressed.connect(self.accept_setpoint)
        
        # Make sure the spinbox is properly configured for text input
        self.setpoint_spinbox.setKeyboardTracking(True)
        self.setpoint_spinbox.setAccelerated(True)
        
        # Override key events to handle Enter/Return properly
        self.setpoint_spinbox.keyPressEvent = self.spinbox_key_press_event
        
    def showEvent(self, event):
        """Override showEvent to ensure proper focus after dialog is shown."""
        super().showEvent(event)
        # Use a timer to ensure the dialog is fully rendered before setting focus
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(50, self.setup_focus)
        
    def setup_focus(self):
        """Setup focus and text selection after dialog is shown."""
        print("⌨️ DEBUG: Setting up focus for MFC dialog")
        
        # Focus on the spinbox and its line edit
        self.setpoint_spinbox.setFocus(Qt.OtherFocusReason)
        self.line_edit.setFocus(Qt.OtherFocusReason)
        
        # Select all text for easy replacement
        self.setpoint_spinbox.selectAll()
        self.line_edit.selectAll()
        
        print(f"DEBUG: Focus set, current value: {self.setpoint_spinbox.value()}")
        print(f"DEBUG: Line edit text: '{self.line_edit.text()}'")
        print(f"DEBUG: Has focus: spinbox={self.setpoint_spinbox.hasFocus()}, line_edit={self.line_edit.hasFocus()}")
        
    def spinbox_key_press_event(self, event):
        """Handle key press events for the spinbox."""
        from PyQt5.QtCore import Qt
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.accept_setpoint()
        else:
            # Call the original keyPressEvent
            QDoubleSpinBox.keyPressEvent(self.setpoint_spinbox, event)
    
    def mousePressEvent(self, event):
        """Handle mouse clicks to ensure spinbox gets focus when clicked."""
        super().mousePressEvent(event)
        # If click is near the spinbox, give it focus
        spinbox_rect = self.setpoint_spinbox.geometry()
        if spinbox_rect.contains(event.pos()):
            self.setpoint_spinbox.setFocus()
            self.line_edit.setFocus()
            self.line_edit.selectAll()
        
    def accept_setpoint(self):
        """Accept the new setpoint value and optionally open gas valve."""
        new_setpoint = self.setpoint_spinbox.value()
        
        # Validation
        if new_setpoint < 0:
            msg = QMessageBox(self)
            msg.setWindowTitle("Invalid Value")
            msg.setText("Flow rate cannot be negative.")
            msg.setIcon(QMessageBox.Warning)
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #101418;
                    color: #e0e0e0;
                }
                QMessageBox QPushButton {
                    background: #4a7bc8;
                    color: #ffffff;
                    border: 2px solid #6a9be8;
                    border-radius: 5px;
                    padding: 5px 15px;
                    font-weight: bold;
                }
                QMessageBox QPushButton:hover {
                    background: #6a9be8;
                }
            """)
            msg.exec_()
            return
            
        if new_setpoint > self.max_flow:
            msg = QMessageBox(self)
            msg.setWindowTitle("Invalid Value")
            msg.setText(f"Flow rate cannot exceed {self.max_flow:.0f} sccm.")
            msg.setIcon(QMessageBox.Warning)
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #101418;
                    color: #e0e0e0;
                }
                QMessageBox QPushButton {
                    background: #4a7bc8;
                    color: #ffffff;
                    border: 2px solid #6a9be8;
                    border-radius: 5px;
                    padding: 5px 15px;
                    font-weight: bold;
                }
                QMessageBox QPushButton:hover {
                    background: #6a9be8;
                }
            """)
            msg.exec_()
            return
        
        # Store the setpoint value
        self.setpoint_value = new_setpoint
        
        # If setpoint > 0 and we have the necessary controllers, try to open the gas valve
        if (new_setpoint > 0 and self.gas_valve_button and 
            self.arduino_controller and self.safety_controller and self.relay_map):
            self._try_open_gas_valve()
        
        self.accept()
    
    def _try_open_gas_valve(self):
        """Try to open the corresponding gas valve using safety checks."""
        try:
            # Import set_relay_safe function
            try:
                from ..auto_procedures import set_relay_safe
            except ImportError:
                from auto_procedures import set_relay_safe
            
            # Check if valve is already open
            current_valve_state = self._get_valve_state()
            if current_valve_state:
                print(f"🔀 DEBUG: Gas valve {self.gas_valve_button} is already open")
                return
            
            print(f"🔀 DEBUG: Attempting to open gas valve {self.gas_valve_button} for {self.mfc_name} MFC")
            
            # Use set_relay_safe with is_auto_procedure=True to bypass mode restrictions
            # but still enforce safety conditions (same logic as sputter mode)
            success = set_relay_safe(
                name=self.gas_valve_button,
                value=True,
                arduino=self.arduino_controller,
                safety=self.safety_controller,
                relay_map=self.relay_map
            )
            
            if success:
                print(f"✅ DEBUG: Successfully opened gas valve {self.gas_valve_button}")
                # Show brief confirmation to user
                self._show_valve_success_message()
            else:
                print(f"❌ DEBUG: Failed to open gas valve {self.gas_valve_button}")
                self._show_valve_error_message("Failed to open gas valve due to safety conditions")
                
        except Exception as e:
            print(f"❌ DEBUG: Exception opening gas valve: {e}")
            self._show_valve_error_message(f"Error opening gas valve: {str(e)}")
    
    def _get_valve_state(self) -> bool:
        """Get current state of the gas valve."""
        try:
            # Check if parent has get_button_state method (from main app)
            if hasattr(self.parent(), 'get_button_state'):
                return self.parent().get_button_state(self.gas_valve_button)
            
            # Fallback: check safety controller relay states
            if hasattr(self.safety_controller, 'relay_states'):
                return self.safety_controller.relay_states.get(self.gas_valve_button, False)
                
        except Exception as e:
            print(f"DEBUG: Error checking valve state: {e}")
        
        return False
    
    def _show_valve_success_message(self):
        """Show brief success message for valve opening."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Gas Valve Opened")
        msg.setText(f"Gas valve {self.gas_valve_button} opened successfully for {self.mfc_name} flow.")
        msg.setIcon(QMessageBox.Information)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #101418;
                color: #e0e0e0;
            }
            QMessageBox QPushButton {
                background: #1da237;
                color: #ffffff;
                border: 2px solid #2dc653;
                border-radius: 5px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QMessageBox QPushButton:hover {
                background: #2dc653;
            }
        """)
        # Auto-close after 2 seconds
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(2000, msg.accept)
        msg.exec_()
    
    def _show_valve_error_message(self, error_text: str):
        """Show error message for valve opening failure."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Gas Valve Error")
        msg.setText(f"Could not open gas valve {self.gas_valve_button}:\n\n{error_text}")
        msg.setIcon(QMessageBox.Warning)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #101418;
                color: #e0e0e0;
            }
            QMessageBox QPushButton {
                background: #7a0000;
                color: #ffffff;
                border: 2px solid #aa0000;
                border-radius: 5px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QMessageBox QPushButton:hover {
                background: #aa0000;
            }
        """)
        msg.exec_()
    
    def get_setpoint(self) -> float:
        """Get the selected setpoint value."""
        return self.setpoint_value


def show_mfc_setpoint_dialog(mfc_name: str, current_setpoint: float = 0.0, 
                           max_flow: float = 200.0, parent=None,
                           arduino_controller=None, safety_controller=None, relay_map=None) -> Optional[float]:
    """
    Show MFC setpoint dialog and return the selected value.
    
    Args:
        mfc_name: Name of the MFC (e.g., "Ar", "N2", "O2")
        current_setpoint: Current setpoint value in sccm
        max_flow: Maximum allowed flow rate in sccm
        parent: Parent widget
        arduino_controller: Arduino controller for valve operations
        safety_controller: Safety controller for safety checks
        relay_map: Dictionary mapping button names to relay numbers
        
    Returns:
        Selected setpoint value in sccm, or None if cancelled
    """
    dialog = MFCSetpointDialog(mfc_name, current_setpoint, max_flow, parent,
                              arduino_controller, safety_controller, relay_map)
    if dialog.exec_() == QDialog.Accepted:
        return dialog.get_setpoint()
    return None