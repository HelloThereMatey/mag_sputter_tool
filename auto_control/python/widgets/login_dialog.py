"""
Login Dialog for Sputter Control System

Provides initial authentication before main GUI launch.
Supports user login, new account creation, and RFID card authentication.
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QMessageBox, QCheckBox, QGroupBox, QFormLayout,
                             QTabWidget, QWidget)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor
from pathlib import Path

try:
    from ..security.user_account_manager import UserAccountManager
    from ..rfid import RFIDReaderThread, RFIDConfig
except ImportError:
    try:
        from security.user_account_manager import UserAccountManager
        from rfid import RFIDReaderThread, RFIDConfig
    except ImportError:
        import sys
        sys.path.append(str(Path(__file__).parent.parent))
        from security.user_account_manager import UserAccountManager
        from rfid import RFIDReaderThread, RFIDConfig


class LoginDialog(QDialog):
    """Login dialog for user authentication with RFID support."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.user_manager = UserAccountManager()
        self.authenticated_user = None
        self.master_password = None
        
        # RFID Integration
        self.rfid_thread: RFIDReaderThread = None
        self.rfid_detected_card: str = None
        self.rfid_enabled = True
        self.current_enrollment_username: str = None
        
        self.setWindowTitle("Sputter Control - Login")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        # Set window flags to prevent closing without authentication
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        
        self._init_ui()
        self._start_rfid_reader()
        
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
        
        layout.addSpacing(10)
        
        # RFID Status
        self.rfid_status_label = QLabel("🔍 Initializing RFID reader...")
        self.rfid_status_label.setAlignment(Qt.AlignCenter)
        self.rfid_status_label.setStyleSheet("QLabel { color: blue; font-size: 11px; }")
        layout.addWidget(self.rfid_status_label)
        
        layout.addSpacing(10)
        
        # Login form
        form_group = QGroupBox("Login")
        form_layout = QFormLayout()
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter username or present RFID card")
        self.username_input.returnPressed.connect(self._on_login)
        form_layout.addRow("Username:", self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter password (or skip with RFID)")
        self.password_input.returnPressed.connect(self._on_login)
        form_layout.addRow("Password:", self.password_input)
        
        # RFID Card Status in Login Section
        self.rfid_card_label = QLabel("No card detected")
        self.rfid_card_label.setStyleSheet("QLabel { color: gray; }")
        form_layout.addRow("RFID Card:", self.rfid_card_label)
        
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
            # Show enrollment prompt
            reply = QMessageBox.question(
                self, "RFID Card Enrollment",
                f"Account '{username}' created successfully!\n\n"
                f"Permission Level: {UserAccountManager.LEVEL_NAMES[UserAccountManager.LEVEL_OPERATOR]}\n\n"
                "Would you like to enroll an RFID card for quick login?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes and self.rfid_enabled:
                self._enroll_rfid_for_user(username)
            else:
                QMessageBox.information(self, "Account Ready",
                                      f"You can now log in with your new account.")
                # Auto-fill the username field
                self.username_input.setText(username)
                self.password_input.clear()
                self.password_input.setFocus()
        else:
            QMessageBox.critical(self, "Account Creation Failed",
                               f"Failed to create account:\n{message}")
    
    def _enroll_rfid_for_user(self, username: str) -> None:
        """
        Enroll an RFID card for a newly created user.
        
        Args:
            username: Username to enroll card for
        """
        self.current_enrollment_username = username
        self.rfid_detected_card = None
        
        # Show enrollment dialog
        reply = QMessageBox.information(
            self, "RFID Enrollment",
            f"Ready to enroll RFID card for user '{username}'.\n\n"
            "Please present your RFID card to the reader now...\n\n"
            "The dialog will automatically close when the card is detected.",
            QMessageBox.Ok | QMessageBox.Cancel
        )
        
        if reply == QMessageBox.Cancel:
            self.current_enrollment_username = None
            QMessageBox.information(self, "Enrollment Cancelled",
                                  f"RFID enrollment cancelled.\n\n"
                                  "You can enroll a card later from the settings menu.")
            self.username_input.setText(username)
            self.password_input.clear()
            return
        
        # Wait for card detection with timeout
        enrollment_timer = QTimer()
        timeout_counter = [30]  # 30 seconds timeout
        
        def check_card():
            if self.rfid_detected_card:
                # Card detected - enroll it
                card_id = self.rfid_detected_card
                enrollment_timer.stop()
                self.current_enrollment_username = None
                self.rfid_detected_card = None
                
                success, msg = self.user_manager.enroll_rfid_card(username, card_id)
                
                if success:
                    QMessageBox.information(self, "Enrollment Success",
                                          f"RFID card '{card_id}' enrolled successfully!\n\n"
                                          f"User '{username}' can now use this card to log in.")
                    self.username_input.setText(username)
                    self.password_input.clear()
                else:
                    QMessageBox.warning(self, "Enrollment Failed",
                                      f"Failed to enroll card:\n{msg}")
                    self.username_input.setText(username)
                    self.password_input.clear()
            
            elif timeout_counter[0] <= 0:
                # Timeout
                enrollment_timer.stop()
                self.current_enrollment_username = None
                QMessageBox.warning(self, "Enrollment Timeout",
                                  "No card detected within 30 seconds.\n\n"
                                  "You can enroll a card later.")
                self.username_input.setText(username)
                self.password_input.clear()
            else:
                timeout_counter[0] -= 1
        
        enrollment_timer.timeout.connect(check_card)
        enrollment_timer.start(1000)  # Check every second
    
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
    
    # ==================== RFID Integration ====================
    
    def _start_rfid_reader(self) -> None:
        """Start RFID reader thread in background."""
        try:
            self.rfid_thread = RFIDReaderThread()
            
            # Connect signals
            self.rfid_thread.card_detected.connect(self._on_rfid_card_detected)
            self.rfid_thread.device_ready.connect(self._on_rfid_device_ready)
            self.rfid_thread.device_lost.connect(self._on_rfid_device_lost)
            self.rfid_thread.error_occurred.connect(self._on_rfid_error)
            self.rfid_thread.status_changed.connect(self._on_rfid_status_changed)
            
            # Start thread
            self.rfid_thread.start()
            
        except Exception as e:
            self.rfid_enabled = False
            self.rfid_status_label.setText(f"⚠️  RFID not available: {e}")
            self.rfid_status_label.setStyleSheet("QLabel { color: orange; font-size: 11px; }")
    
    def _on_rfid_status_changed(self, status: str) -> None:
        """Handle RFID status update."""
        self.rfid_status_label.setText(status)
        self.rfid_status_label.setStyleSheet("QLabel { color: blue; font-size: 11px; }")
    
    def _on_rfid_device_ready(self) -> None:
        """Handle RFID device ready signal."""
        self.rfid_status_label.setText("✓ RFID ready - Present card to login")
        self.rfid_status_label.setStyleSheet("QLabel { color: green; font-size: 11px; }")
        self.rfid_enabled = True
    
    def _on_rfid_device_lost(self) -> None:
        """Handle RFID device lost signal."""
        self.rfid_status_label.setText("❌ RFID device disconnected")
        self.rfid_status_label.setStyleSheet("QLabel { color: red; font-size: 11px; }")
        self.rfid_card_label.setText("No card detected")
        self.rfid_card_label.setStyleSheet("QLabel { color: gray; }")
        self.rfid_enabled = False
    
    def _on_rfid_error(self, error_msg: str) -> None:
        """Handle RFID error."""
        self.rfid_status_label.setText(f"⚠️  {error_msg}")
        self.rfid_status_label.setStyleSheet("QLabel { color: orange; font-size: 11px; }")
    
    def _on_rfid_card_detected(self, card_id: str) -> None:
        """
        Handle RFID card detected.
        Auto-login if card is registered, or show enrollment option if creating account.
        """
        self.rfid_detected_card = card_id
        
        # Update display
        self.rfid_card_label.setText(f"Detected: {card_id}")
        self.rfid_card_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
        
        # If we're in enrollment mode (creating account), store the card ID
        if self.current_enrollment_username:
            return  # Let the enrollment dialog handle it
        
        # Try to auto-login with RFID card
        success, user_info, message = self.user_manager.authenticate_by_rfid(card_id)
        
        if success:
            self.authenticated_user = user_info
            self.master_password = None
            
            # Show brief confirmation
            self.status_label.setText(message)
            self.status_label.setStyleSheet("QLabel { color: green; }")
            
            # Auto-accept after short delay
            QTimer.singleShot(1000, self.accept)
        else:
            # Card not registered - show message but allow manual login
            self.status_label.setText(f"⚠️  {message}")
            self.status_label.setStyleSheet("QLabel { color: orange; }")
    
    def closeEvent(self, event):
        """Handle dialog close to stop RFID thread."""
        if self.rfid_thread:
            self.rfid_thread.stop()
        super().closeEvent(event)