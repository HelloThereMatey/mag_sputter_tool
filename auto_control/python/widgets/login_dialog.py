"""
Login Dialog for Sputter Control System

Provides initial authentication before main GUI launch.
Supports user login and new account creation.
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QMessageBox, QCheckBox, QGroupBox, QFormLayout)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from pathlib import Path

try:
    from ..security.user_account_manager import UserAccountManager
except ImportError:
    try:
        from security.user_account_manager import UserAccountManager
    except ImportError:
        import sys
        sys.path.append(str(Path(__file__).parent.parent))
        from security.user_account_manager import UserAccountManager


class LoginDialog(QDialog):
    """Login dialog for user authentication."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.user_manager = UserAccountManager()
        self.authenticated_user = None
        self.master_password = None
        
        self.setWindowTitle("Sputter Control - Login")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        # Set window flags to prevent closing without authentication
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        
        self._init_ui()
        
        # Check if this is first-time setup
        if not self.user_manager.has_users_configured():
            self._show_first_time_setup()
        else:
            # Check if we need to migrate from old encryption
            self._check_and_migrate_database()
    
    def _check_and_migrate_database(self):
        """Check if database needs migration and attempt it."""
        from PyQt5.QtWidgets import QInputDialog
        
        # Try to load users - if it fails, might need migration
        test_users = self.user_manager._load_users()
        
        if test_users is None and self.user_manager.has_users_configured():
            # Database exists but can't be loaded - might need migration
            reply = QMessageBox.question(
                self, "Database Migration",
                "User database needs to be migrated to new encryption format.\n\n"
                "Enter master password to migrate:",
                QMessageBox.Ok | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Ok:
                master_password, ok = QInputDialog.getText(
                    self, "Master Password",
                    "Enter master password:",
                    QLineEdit.Password
                )
                
                if ok and master_password:
                    if self.user_manager._migrate_old_database(master_password):
                        QMessageBox.information(self, "Success", 
                                              "Database migrated successfully!\n\n"
                                              "You can now log in.")
                    else:
                        QMessageBox.critical(self, "Migration Failed",
                                           "Failed to migrate database.\n\n"
                                           "Please contact system administrator.")
    
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Sputter Control System")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        subtitle = QLabel("User Authentication Required")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        
        layout.addSpacing(20)
        
        # Login form
        form_group = QGroupBox("Login")
        form_layout = QFormLayout()
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter username")
        self.username_input.returnPressed.connect(self._on_login)
        form_layout.addRow("Username:", self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter password")
        self.password_input.returnPressed.connect(self._on_login)
        form_layout.addRow("Password:", self.password_input)
        
        self.remember_checkbox = QCheckBox("Remember username")
        form_layout.addRow("", self.remember_checkbox)
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        layout.addSpacing(10)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self._on_login)
        self.login_button.setDefault(True)
        button_layout.addWidget(self.login_button)
        
        self.create_account_button = QPushButton("Create Account")
        self.create_account_button.clicked.connect(self._on_create_account)
        button_layout.addWidget(self.create_account_button)
        
        self.cancel_button = QPushButton("Exit")
        self.cancel_button.clicked.connect(self._on_cancel)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("QLabel { color: red; }")
        layout.addWidget(self.status_label)
        
        # Load remembered username
        self._load_remembered_username()
    
    def _show_first_time_setup(self):
        """Show first-time setup dialog to create master password and first admin."""
        msg = QMessageBox(self)
        msg.setWindowTitle("First-Time Setup")
        msg.setIcon(QMessageBox.Information)
        msg.setText("No user accounts exist.\n\n"
                   "You will now create the master password and first administrator account.\n\n"
                   "The master password is required to create users with elevated permissions.")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()
        
        # Get master password
        master_password = self._get_master_password_setup()
        if not master_password:
            self._on_cancel()
            return
        
        # Create first admin
        success = self._create_first_admin(master_password)
        if not success:
            self._on_cancel()
            return
    
    def _get_master_password_setup(self) -> str:
        """Get master password during first-time setup."""
        from PyQt5.QtWidgets import QInputDialog
        
        while True:
            password, ok = QInputDialog.getText(
                self, "Master Password Setup",
                "Enter master password:\n(Required for managing users with level 2+ permissions)",
                QLineEdit.Password
            )
            
            if not ok:
                return None
            
            if not password:
                QMessageBox.warning(self, "Empty Password", 
                                  "Master password cannot be empty.")
                continue
            
            # Confirm password
            confirm, ok = QInputDialog.getText(
                self, "Confirm Master Password",
                "Confirm master password:",
                QLineEdit.Password
            )
            
            if not ok:
                return None
            
            if password != confirm:
                QMessageBox.warning(self, "Mismatch", "Passwords do not match.")
                continue
            
            # Set up master password
            if self.user_manager.setup_master_password(password):
                QMessageBox.information(self, "Success", "Master password created successfully.")
                return password
            else:
                QMessageBox.critical(self, "Error", "Failed to create master password.")
                return None
    
    def _create_first_admin(self, master_password: str) -> bool:
        """Create first administrator account."""
        from PyQt5.QtWidgets import QInputDialog
        
        QMessageBox.information(self, "Create Administrator",
                              "Now create the first administrator account.\n\n"
                              "Level 4 (Administrator) has full system access\n"
                              "and can manage other user accounts.")
        
        # Get username
        username, ok = QInputDialog.getText(
            self, "Administrator Username",
            "Enter administrator username:"
        )
        
        if not ok or not username:
            return False
        
        # Get password
        while True:
            password, ok = QInputDialog.getText(
                self, "Administrator Password",
                "Enter administrator password:",
                QLineEdit.Password
            )
            
            if not ok:
                return False
            
            if not password:
                QMessageBox.warning(self, "Empty Password",
                                  "Password cannot be empty.")
                continue
            
            # Confirm password
            confirm, ok = QInputDialog.getText(
                self, "Confirm Password",
                "Confirm administrator password:",
                QLineEdit.Password
            )
            
            if not ok:
                return False
            
            if password != confirm:
                QMessageBox.warning(self, "Mismatch", "Passwords do not match.")
                continue
            
            break
        
        # Create administrator account (no master password needed for user creation)
        success, message = self.user_manager.create_user(
            username, password, UserAccountManager.LEVEL_ADMINISTRATOR, "system"
        )
        
        if success:
            QMessageBox.information(self, "Success",
                                  f"Administrator account '{username}' created.\n\n"
                                  "You can now log in with this account.")
            return True
        else:
            QMessageBox.critical(self, "Error", f"Failed to create administrator:\n{message}")
            return False
    
    def _on_login(self):
        """Handle login button click."""
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        if not username or not password:
            self.status_label.setText("Please enter username and password")
            return
        
        # Authenticate (no master password required)
        success, user_info, message = self.user_manager.authenticate_user(username, password)
        
        if success:
            self.authenticated_user = user_info
            # Master password no longer needed for login
            self.master_password = None
            
            # Save username if remember is checked
            if self.remember_checkbox.isChecked():
                self._save_remembered_username(username)
            
            self.accept()
        else:
            self.status_label.setText(message)
            self.password_input.clear()
            self.password_input.setFocus()
    
    def _on_create_account(self):
        """Handle create account button click."""
        from PyQt5.QtWidgets import QInputDialog
        
        # Get username
        username, ok = QInputDialog.getText(
            self, "Create New Account",
            "Enter username for new account:"
        )
        
        if not ok or not username.strip():
            return
        
        username = username.strip()
        
        # Get password
        password, ok = QInputDialog.getText(
            self, "Create Password",
            "Enter password:",
            QLineEdit.Password
        )
        
        if not ok or not password:
            return
        
        # Confirm password
        confirm, ok = QInputDialog.getText(
            self, "Confirm Password",
            "Confirm password:",
            QLineEdit.Password
        )
        
        if not ok:
            return
        
        if password != confirm:
            QMessageBox.warning(self, "Password Mismatch",
                              "Passwords do not match. Please try again.")
            return
        
        # Create account with Level 1 (Operator) permissions
        success, message = self.user_manager.create_user(
            username, 
            password, 
            UserAccountManager.LEVEL_OPERATOR,  # Default to Level 1
            "self-registration"
        )
        
        if success:
            QMessageBox.information(self, "Account Created",
                                  f"Account '{username}' created successfully!\n\n"
                                  f"Permission Level: {UserAccountManager.LEVEL_NAMES[UserAccountManager.LEVEL_OPERATOR]}\n\n"
                                  "You can now log in with your new account.")
            # Auto-fill the username field
            self.username_input.setText(username)
            self.password_input.clear()
            self.password_input.setFocus()
        else:
            QMessageBox.critical(self, "Account Creation Failed",
                               f"Failed to create account:\n{message}")
    
    def _on_cancel(self):
        """Handle cancel/exit button click."""
        reply = QMessageBox.question(
            self, "Exit Application",
            "Are you sure you want to exit?\n\nYou must log in to use the application.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.reject()
    
    def _save_remembered_username(self, username: str):
        """Save username for auto-fill."""
        try:
            config_file = self.user_manager.config_dir / "remembered_username.txt"
            config_file.write_text(username)
        except Exception as e:
            print(f"Failed to save username: {e}")
    
    def _load_remembered_username(self):
        """Load saved username."""
        try:
            config_file = self.user_manager.config_dir / "remembered_username.txt"
            if config_file.exists():
                username = config_file.read_text().strip()
                self.username_input.setText(username)
                self.remember_checkbox.setChecked(True)
                self.password_input.setFocus()
        except Exception as e:
            print(f"Failed to load username: {e}")
    
    def get_authenticated_user(self):
        """Get authenticated user info."""
        return self.authenticated_user
    
    def get_master_password(self):
        """Get master password (for user management operations)."""
        return self.master_password
