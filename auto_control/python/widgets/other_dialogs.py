from typing import List, Optional
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QMessageBox
from PyQt5.QtCore import Qt


class LoadUnloadDialog(QDialog):
    """Dialog for load/unload procedure user interaction.
    
    Shows instructions for using the load-lock arm and waits for confirmation
    that the arm has been returned to the home position.
    """
    def __init__(self, arduino_controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Load/Unload Sample")
        self.setModal(True)
        self.arduino = arduino_controller
        
        # Make dialog larger and non-resizable
        self.setFixedSize(600, 300)
        
        layout = QVBoxLayout()
        layout.setSpacing(20)
        
        # Main instruction label with large font
        instruction_label = QLabel("Use load-lock arm to load/unload sample,\nreturn arm to home position and then click the button below.")
        instruction_label.setAlignment(Qt.AlignCenter)
        instruction_label.setWordWrap(True)
        instruction_label.setStyleSheet("""
            QLabel {
                font-size: 18pt;
                font-weight: bold;
                color: #2c3e50;
                padding: 20px;
                border: 2px solid #3498db;
                border-radius: 10px;
                background-color: #ecf0f1;
            }
        """)
        layout.addWidget(instruction_label)
        
        # Status label for feedback
        self.status_label = QLabel("Load-lock gate valve is open. You may now operate the load-lock arm.")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 12pt;
                color: #27ae60;
                padding: 10px;
            }
        """)
        layout.addWidget(self.status_label)
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Single button for Load/Unload Finished or Cancel
        self.finish_btn = QPushButton("Load/Unload Finished or Cancel")
        self.finish_btn.setDefault(True)
        self.finish_btn.setStyleSheet("""
            QPushButton {
                font-size: 12pt;
                padding: 10px 20px;
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        self.finish_btn.clicked.connect(self._on_ok_clicked)
        
        button_layout.addWidget(self.finish_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def _on_ok_clicked(self):
        """Handle OK button click - check if arm is in home position."""
        try:
            # Read digital inputs to check arm position
            digital_inputs = self.arduino.get_digital_inputs()
            
            if digital_inputs is None:
                QMessageBox.warning(
                    self,
                    "Communication Error",
                    "Cannot read digital inputs from Arduino.\nPlease check connection and try again."
                )
                return
            
            if len(digital_inputs) < 3:
                QMessageBox.warning(
                    self,
                    "Configuration Error", 
                    "Insufficient digital inputs available.\nCannot verify arm position."
                )
                return
            
            # Check if load-lock arm is in home position (digital_inputs[1] should be True)
            arm_home = bool(digital_inputs[1])
            
            if arm_home:
                # Arm is in home position - close dialog successfully
                self.status_label.setText("✓ Load-lock arm confirmed in home position")
                self.status_label.setStyleSheet("""
                    QLabel {
                        font-size: 12pt;
                        color: #27ae60;
                        font-weight: bold;
                        padding: 10px;
                    }
                """)
                # Force update before accepting to prevent painting issues
                self.status_label.repaint()
                self.repaint()
                self.accept()
            else:
                # Arm is not in home position - show warning
                self._show_arm_not_home_warning()
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error checking arm position: {str(e)}\nPlease try again."
            )
    
    def _show_arm_not_home_warning(self):
        """Show warning that arm is not in home position."""
        # Update status label first (before creating dialog to avoid painting conflicts)
        self.status_label.setText("⚠ Please return load-lock arm to home position")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 12pt;
                color: #e74c3c;
                font-weight: bold;
                padding: 10px;
            }
        """)
        
        # Force immediate update and process events to prevent recursive painting
        self.status_label.repaint()
        self.repaint()
        
        # Create warning dialog as standalone (not child of this dialog) to prevent event loop conflicts
        warning_dialog = QMessageBox()
        warning_dialog.setWindowTitle("Load-Lock Arm Not Home")
        warning_dialog.setIcon(QMessageBox.Warning)
        warning_dialog.setText("Load-lock arm is not in home position!")
        warning_dialog.setInformativeText(
            "The load-lock arm must be returned to the home position before the gate valve can be closed.\n\n"
            "Please return the arm to its home position and then click the button below."
        )
        warning_dialog.setStandardButtons(QMessageBox.Ok)
        warning_dialog.setStyleSheet("""
            QMessageBox {
                font-size: 12pt;
            }
            QMessageBox QLabel {
                font-size: 12pt;
            }
        """)
        
        # Show dialog and ensure it's properly cleaned up
        try:
            warning_dialog.exec()
        finally:
            warning_dialog.deleteLater()


class SetSystemStateDialog(QDialog):
    """Dialog to select and confirm a manual system state change.

    Usage:
        dlg = SetSystemStateDialog(current_state, safety_controller, parent)
        if dlg.exec() == QDialog.Accepted:
            new_state = dlg.get_selected_state()
    """
    def __init__(self, current_state: str, safety_controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set System State")
        self.setModal(True)

        self._current_state = current_state
        self._safety = safety_controller

        layout = QVBoxLayout()

        # Current state
        current_layout = QHBoxLayout()
        current_layout.addWidget(QLabel("Current State:"))
        current_label = QLabel(self._current_state.title())
        current_label.setStyleSheet("font-weight: bold; color: blue;")
        current_layout.addWidget(current_label)
        current_layout.addStretch()
        layout.addLayout(current_layout)

        # State selection
        select_layout = QHBoxLayout()
        select_layout.addWidget(QLabel("New State:"))

        self.state_combo = QComboBox()
        available_states = self._get_available_states()
        self._available_states = available_states
        self.state_combo.addItems([s.title() for s in available_states])
        # set current index
        try:
            idx = available_states.index(self._current_state)
        except Exception:
            idx = 0
        self.state_combo.setCurrentIndex(idx)
        select_layout.addWidget(self.state_combo)
        layout.addLayout(select_layout)

        # Warning
        warning_label = QLabel("⚠️ Warning: Manually changing system state may bypass safety checks!")
        warning_label.setStyleSheet("color: red; font-weight: bold;")
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        ok_btn = QPushButton("Set State")
        ok_btn.setDefault(True)
        cancel_btn.clicked.connect(self.reject)
        ok_btn.clicked.connect(self._on_accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def _get_available_states(self) -> List[str]:
        if hasattr(self._safety, 'safety_config') and self._safety and self._safety.safety_config:
            system_status_config = self._safety.safety_config.get('system_status', {})
            states_config = system_status_config.get('states', {})
            if isinstance(states_config, dict) and states_config:
                return list(states_config.keys())
        # fallback
        return ['vented', 'pumping', 'pumped', 'venting', 'sputtering', 'loadlock_venting', 'load_unload', 'error']

    def _on_accept(self) -> None:
        selected = self._available_states[self.state_combo.currentIndex()]
        # Confirm the change
        reply = QMessageBox.question(
            self,
            "Confirm State Change",
            f"Change system state from '{self._current_state}' to '{selected}'?\n\nThis may affect safety checks and procedure availability.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.accept()

    def get_selected_state(self) -> Optional[str]:
        if self.result() == QDialog.Accepted:
            return self._available_states[self.state_combo.currentIndex()]
        return None
