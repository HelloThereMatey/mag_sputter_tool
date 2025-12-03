from __future__ import annotations

import os
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QComboBox, QPushButton, QLineEdit, QMessageBox
)

# Support both package and script execution
try:
    from ..security.password_manager import SecurePasswordManager
    from .password_setup_dialog import PasswordSetupDialog
except ImportError:
    from security.password_manager import SecurePasswordManager
    from widgets.password_setup_dialog import PasswordSetupDialog



class ModeSelectionDialog(QDialog):
    """Dialog for selecting operation mode with encrypted password protection."""
    
    MODES = ["Normal", "Manual", "Override"]
    PROTECTED_MODES = {"Manual", "Override"}
    
    def __init__(self, current_mode: str = "Normal", parent=None, master_password=None, user_level: int = 1):
        super().__init__(parent)
        self.current_mode = current_mode
        self.selected_mode = current_mode
        self.user_level = user_level  # User permission level (1-4)
        self.password_manager = SecurePasswordManager()
        self.session_master_password = master_password  # Store for this session
        # For regular mode switching, we'll use a simplified password check
        # Master password is only needed during initial setup
        
        # Check if passwords are configured
        if not self.password_manager.has_passwords_configured():
            if not self._setup_initial_passwords():
                # User cancelled setup, can't proceed
                self.reject()
                return
        
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Select Operation Mode")
        self.setModal(True)
        
        # Remove fixed size - let layout manage sizing
        self.setMinimumSize(350, 200)
        self.setMaximumSize(450, 400)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)  # Add consistent spacing
        layout.setContentsMargins(20, 20, 20, 20)  # Add margins
        
        # Title
        title = QLabel("Select Operation Mode")
        title.setStyleSheet("font-size: 14pt; font-weight: bold; margin: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Current mode info
        current_label = QLabel(f"Current Mode: {self.current_mode}")
        current_label.setStyleSheet("font-size: 11pt; margin: 5px;")
        layout.addWidget(current_label)
        
        # Mode selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("New Mode:"))
        
        self.mode_combo = QComboBox()
        
        # Add modes based on user level
        # Level 1 (Operator): No mode selection allowed (button should be hidden in main GUI)
        # Level 2 (Technician): Normal, Manual
        # Level 3+ (Master/Admin): Normal, Manual, Override
        available_modes = self._get_available_modes()
        self.mode_combo.addItems(available_modes)
        
        if self.current_mode in available_modes:
            self.mode_combo.setCurrentText(self.current_mode)
        
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        layout.addLayout(mode_layout)
        
        # Password field (initially hidden)
        self.password_layout = QHBoxLayout()
        self.password_label = QLabel("Password:")
        self.password_field = QLineEdit()
        self.password_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_field.setPlaceholderText("Enter mode password")
        
        self.password_layout.addWidget(self.password_label)
        self.password_layout.addWidget(self.password_field)
        
        layout.addLayout(self.password_layout)
        
        # Initially hide password fields
        self.set_password_visible(False)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self.on_ok_clicked)
        self.ok_btn.setDefault(True)
        
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.ok_btn)
        layout.addLayout(button_layout)
        
        # Style
        self.setStyleSheet("""
            QDialog { 
                background-color: #2b2b2b; 
                color: white; 
            }
            QLabel { 
                color: white; 
            }
            QComboBox { 
                background: #404040; 
                border: 1px solid #606060; 
                padding: 5px;
                color: white;
            }
            /* Make the drop-down list use the same dark theme so items are readable */
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                color: white;
                selection-background-color: #505050;
                selection-color: white;
            }
            QLineEdit { 
                background: #404040; 
                border: 1px solid #606060; 
                padding: 8px;
                color: white;
                min-height: 20px;
            }
            QPushButton { 
                background: #505050; 
                border: 1px solid #707070; 
                padding: 8px 15px;
                color: white;
                min-height: 30px;
            }
            QPushButton:hover { 
                background: #606060; 
            }
            QPushButton:pressed { 
                background: #404040; 
            }
        """)
        
        # Ensure proper initial sizing
        self.adjustSize()
        
        # Set minimum size based on content
        self.setMinimumSize(self.sizeHint())
        
    def set_password_visible(self, visible: bool):
        """Show/hide password field."""
        self.password_label.setVisible(visible)
        self.password_field.setVisible(visible)
        
        # Force layout recalculation and resize to fit content
        self.adjustSize()
        
        # Ensure minimum size is maintained
        current_size = self.size()
        min_width = max(350, current_size.width())
        min_height = max(200, current_size.height())
        self.resize(min_width, min_height)
        
        if visible:
            self.password_field.setFocus()
    
    def _get_available_modes(self) -> list:
        """Get list of modes available to current user based on permission level."""
        # Level 1 (Operator): Should not see mode dialog at all (button hidden in main GUI)
        # Level 2 (Technician): Normal, Manual
        # Level 3 (Master): All modes
        # Level 4 (Administrator): All modes
        
        if self.user_level >= 3:
            return ["Normal", "Manual", "Override"]
        elif self.user_level == 2:
            return ["Normal", "Manual"]
        else:  # Level 1
            return ["Normal"]  # Fallback, but button should be hidden
        
    def on_mode_changed(self, mode: str):
        """Handle mode selection change."""
        needs_password = mode in self.PROTECTED_MODES
        self.set_password_visible(needs_password)
        
        if needs_password:
            self.password_field.clear()
        
    def on_ok_clicked(self):
        """Handle OK button click."""
        selected_mode = self.mode_combo.currentText()
        
        # Check if password is required
        if selected_mode in self.PROTECTED_MODES:
            # Get mode password
            mode_password = self.password_field.text()
            if not mode_password:
                QMessageBox.warning(self, "Password Required", 
                                  f"Password is required for {selected_mode} mode.")
                return
            
            # For mode switching, we'll do a simplified validation
            # that doesn't require the master password
            if not self._verify_mode_password_simple(selected_mode.lower(), mode_password):
                QMessageBox.critical(self, "Invalid Password", 
                                   "Incorrect password. Access denied.")
                self.password_field.clear()
                self.password_field.setFocus()
                return
        
        # Password valid or not required
        self.selected_mode = selected_mode
        self.accept()

    def _setup_initial_passwords(self) -> bool:
        """Show password setup dialog for first-time configuration."""
        setup_dialog = PasswordSetupDialog(self)
        
        if setup_dialog.exec() == QDialog.DialogCode.Accepted:
            master_password, mode_passwords = setup_dialog.get_passwords()
            
            # Save encrypted passwords
            success = self.password_manager.setup_passwords(master_password, mode_passwords)
            
            if success:
                self.master_password = master_password
                QMessageBox.information(self, "Setup Complete", 
                                      "Security has been configured successfully.")
                return True
            else:
                QMessageBox.critical(self, "Setup Failed", 
                                   "Failed to save password configuration.")
                return False
        
        return False
        
    def _verify_mode_password_simple(self, mode: str, password: str) -> bool:
        """
        Verify mode password without requiring master password.
        Uses the new simple verification method.
        """
        try:
            return self.password_manager.verify_mode_password_simple(mode, password)
        except Exception as e:
            print(f"❌ Error verifying password (simple): {e}")
            return False
        
    def get_selected_mode(self) -> str:
        """Get the selected mode."""
        return self.selected_mode
