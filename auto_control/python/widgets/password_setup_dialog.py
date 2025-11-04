from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QMessageBox, QGroupBox,
    QFormLayout
)


class PasswordSetupDialog(QDialog):
    """Dialog for initial password setup with master password."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.master_password = ""
        self.mode_passwords = {}
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Security Setup - First Time Configuration")
        self.setModal(True)
        # Ensure the dialog is tall enough to comfortably show all fields
        # Use a minimum size and an initial resize so the user can still resize the dialog
        self.setMinimumSize(480, 520)
        self.resize(480, 520)
        
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Sputter Control Security Setup")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; margin: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Info text
        info = QLabel("Set up password protection for Manual and Override modes.\n"
                     "Your passwords will be encrypted and stored securely.")
        info.setStyleSheet("font-size: 10pt; margin: 10px; color: #cccccc;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Master password group
        master_group = QGroupBox("Master Password")
        master_layout = QFormLayout(master_group)
        
        self.master_field = QLineEdit()
        self.master_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.master_field.setPlaceholderText("Used to encrypt your mode passwords")
        master_layout.addRow("Master Password:", self.master_field)
        
        self.master_confirm_field = QLineEdit()
        self.master_confirm_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.master_confirm_field.setPlaceholderText("Confirm master password")
        master_layout.addRow("Confirm Master:", self.master_confirm_field)
        
        layout.addWidget(master_group)
        
        # Mode passwords group
        mode_group = QGroupBox("Mode Passwords")
        mode_layout = QFormLayout(mode_group)
        
        self.manual_field = QLineEdit()
        self.manual_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.manual_field.setPlaceholderText("Password for Manual mode")
        mode_layout.addRow("Manual Mode:", self.manual_field)
        
        self.override_field = QLineEdit()
        self.override_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.override_field.setPlaceholderText("Password for Override mode")
        mode_layout.addRow("Override Mode:", self.override_field)
        
        layout.addWidget(mode_group)
        
        # Warning
        warning = QLabel("⚠️ Remember your master password! It cannot be recovered if lost.")
        warning.setStyleSheet("color: #ff9900; font-weight: bold; margin: 10px;")
        layout.addWidget(warning)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.setup_btn = QPushButton("Setup Security")
        self.setup_btn.clicked.connect(self.on_setup_clicked)
        self.setup_btn.setDefault(True)
        
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.setup_btn)
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
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
            }
            QLineEdit { 
                background: #404040; 
                border: 1px solid #606060; 
                padding: 8px;
                color: white;
                border-radius: 3px;
            }
            QLineEdit:focus {
                border: 2px solid #4a7bc8;
            }
            QPushButton { 
                background: #505050; 
                border: 1px solid #707070; 
                padding: 10px 20px;
                color: white;
                border-radius: 3px;
            }
            QPushButton:hover { 
                background: #606060; 
            }
            QPushButton:pressed { 
                background: #404040; 
            }
            QPushButton:default {
                background: #2d4f8e;
                border: 2px solid #4a7bc8;
            }
        """)
        
    def on_setup_clicked(self):
        """Handle setup button click."""
        # Validate master password
        master = self.master_field.text()
        master_confirm = self.master_confirm_field.text()
        
        if not master:
            QMessageBox.warning(self, "Missing Master Password", 
                              "Master password is required.")
            return
            
        if len(master) < 8:
            QMessageBox.warning(self, "Weak Master Password", 
                              "Master password must be at least 8 characters.")
            return
            
        if master != master_confirm:
            QMessageBox.warning(self, "Password Mismatch", 
                              "Master password and confirmation don't match.")
            return
        
        # Validate mode passwords
        manual_pwd = self.manual_field.text()
        override_pwd = self.override_field.text()
        
        if not manual_pwd:
            QMessageBox.warning(self, "Missing Password", 
                              "Manual mode password is required.")
            return
            
        if not override_pwd:
            QMessageBox.warning(self, "Missing Password", 
                              "Override mode password is required.")
            return
            
        if len(manual_pwd) < 6 or len(override_pwd) < 6:
            QMessageBox.warning(self, "Weak Passwords", 
                              "Mode passwords must be at least 6 characters.")
            return
        
        # Store the passwords
        self.master_password = master
        self.mode_passwords = {
            "manual": manual_pwd,
            "override": override_pwd
        }
        
        self.accept()
        
    def get_passwords(self) -> tuple[str, dict[str, str]]:
        """Get the configured passwords."""
        return self.master_password, self.mode_passwords
