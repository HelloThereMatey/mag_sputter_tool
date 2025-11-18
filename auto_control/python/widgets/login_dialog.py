"""
Login Dialog for Sputter Control System

Provides initial authentication before main GUI launch.
Supports user login, new account creation, and RFID card authentication.
"""

from typing import Optional
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
        
        subtitle = QLabel("RFID Card Authentication")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("QLabel { font-size: 12pt; font-weight: bold; }")
        layout.addWidget(subtitle)
        
        layout.addSpacing(20)
        
        # RFID Status
        self.rfid_status_label = QLabel("🔍 Initializing RFID reader...")
        self.rfid_status_label.setAlignment(Qt.AlignCenter)
        self.rfid_status_label.setStyleSheet("QLabel { color: blue; font-size: 14px; font-weight: bold; }")
        layout.addWidget(self.rfid_status_label)
        
        layout.addSpacing(10)
        
        # RFID Card Status
        card_status_group = QGroupBox("Card Status")
        card_layout = QVBoxLayout()
        
        instruction_label = QLabel("Please present your RFID card to the reader")
        instruction_label.setAlignment(Qt.AlignCenter)
        instruction_label.setStyleSheet("QLabel { font-size: 11pt; color: #34495e; }")
        card_layout.addWidget(instruction_label)
        
        self.rfid_card_label = QLabel("No card detected")
        self.rfid_card_label.setAlignment(Qt.AlignCenter)
        self.rfid_card_label.setStyleSheet("QLabel { color: gray; font-size: 14pt; font-weight: bold; padding: 10px; }")
        card_layout.addWidget(self.rfid_card_label)
        
        card_status_group.setLayout(card_layout)
        layout.addWidget(card_status_group)
        
        layout.addSpacing(20)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.create_account_button = QPushButton("Create New Account")
        self.create_account_button.clicked.connect(self._on_create_account)
        self.create_account_button.setStyleSheet("""
            QPushButton {
                font-size: 11pt;
                padding: 10px 20px;
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        button_layout.addWidget(self.create_account_button)
        
        self.cancel_button = QPushButton("Exit Application")
        self.cancel_button.clicked.connect(self._on_cancel)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                font-size: 11pt;
                padding: 10px 20px;
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("QLabel { color: red; font-size: 10pt; }")
        layout.addWidget(self.status_label)
    
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
        
        # For first admin, we need a card - show enrollment dialog immediately
        QMessageBox.information(self, "RFID Card Required",
                              f"Administrator account requires RFID card enrollment.\n\n"
                              "Please present your RFID card to the reader...")
        
        # Wait for card
        self.current_enrollment_username = username
        self.rfid_detected_card = None
        
        # Create enrollment dialog
        card_id = self._wait_for_card_enrollment(username, is_first_admin=True)
        
        if not card_id:
            QMessageBox.critical(self, "Error", "RFID card enrollment is required to create administrator account.")
            return False
        
        # Create administrator account with card (no password)
        success, message = self.user_manager.create_user(
            username, card_id, UserAccountManager.LEVEL_ADMINISTRATOR, "system"
        )
        
        if success:
            QMessageBox.information(self, "Success",
                                  f"Administrator account '{username}' created.\n\n"
                                  "You can now use your RFID card to log in.")
            return True
        else:
            QMessageBox.critical(self, "Error", f"Failed to create administrator:\n{message}")
            return False
    
    def _on_create_account(self):
        """Handle create account button click - RFID card enrollment is mandatory."""
        from PyQt5.QtWidgets import QInputDialog
        
        # Get username
        username, ok = QInputDialog.getText(
            self, "Create New Account",
            "Enter username for new account:"
        )
        
        if not ok or not username.strip():
            return
        
        username = username.strip()
        
        # Show RFID enrollment requirement
        QMessageBox.information(
            self, "RFID Card Required",
            f"Creating account '{username}'.\n\n"
            "RFID card enrollment is REQUIRED to complete account creation.\n\n"
            "Please present your RFID card to the reader..."
        )
        
        # Wait for card enrollment
        card_id = self._wait_for_card_enrollment(username, is_first_admin=False)
        
        if not card_id:
            QMessageBox.warning(
                self, "Account Creation Cancelled",
                "RFID card enrollment is required to create an account.\n\n"
                "Account creation cancelled."
            )
            return
        
        # Create account with Level 1 (Operator) permissions and enrolled card
        success, message = self.user_manager.create_user(
            username, 
            card_id,  # RFID card ID instead of password
            UserAccountManager.LEVEL_OPERATOR,  # Default to Level 1
            "self-registration"
        )
        
        if success:
            QMessageBox.information(
                self, "Account Created",
                f"Account '{username}' created successfully!\n\n"
                f"Permission Level: {UserAccountManager.LEVEL_NAMES[UserAccountManager.LEVEL_OPERATOR]}\n\n"
                f"Your RFID card has been enrolled.\n"
                "You can now log in by presenting your card."
            )
        else:
            QMessageBox.critical(self, "Account Creation Failed",
                               f"Failed to create account:\n{message}")
    
    def _wait_for_card_enrollment(self, username: str, is_first_admin: bool = False) -> Optional[str]:
        """
        Wait for RFID card to be presented for enrollment.
        
        Args:
            username: Username to enroll card for
            is_first_admin: If True, this is for first-time admin setup
            
        Returns:
            Card ID if detected, None if cancelled/timeout
        """
        self.current_enrollment_username = username
        self.rfid_detected_card = None
        
        # Create a non-blocking dialog for enrollment
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar
        from PyQt5.QtCore import Qt
        
        enrollment_dialog = QDialog(self)
        enrollment_dialog.setWindowTitle("RFID Enrollment")
        enrollment_dialog.setModal(True)
        enrollment_dialog.setFixedSize(400, 200)
        
        layout = QVBoxLayout()
        
        title_label = QLabel(f"Enrolling RFID card for user '{username}'")
        title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        instruction_label = QLabel("Please present your RFID card to the reader now...")
        instruction_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(instruction_label)
        
        status_label = QLabel("Waiting for card...")
        status_label.setAlignment(Qt.AlignCenter)
        status_label.setStyleSheet("color: blue;")
        layout.addWidget(status_label)
        
        # Progress bar for timeout
        progress = QProgressBar()
        progress.setMaximum(30)  # 30 seconds
        progress.setValue(30)
        layout.addWidget(progress)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(enrollment_dialog.reject)
        layout.addWidget(cancel_button)
        
        enrollment_dialog.setLayout(layout)
        
        # Timer for checking card detection and timeout
        enrollment_timer = QTimer()
        timeout_counter = [30]  # 30 seconds timeout
        detected_card = [None]  # Store detected card ID
        
        def check_card():
            if self.rfid_detected_card:
                # Card detected - store it and close dialog
                detected_card[0] = self.rfid_detected_card
                enrollment_timer.stop()
                enrollment_dialog.accept()
                self.current_enrollment_username = None
                self.rfid_detected_card = None
            
            elif timeout_counter[0] <= 0:
                # Timeout
                enrollment_timer.stop()
                enrollment_dialog.reject()
                self.current_enrollment_username = None
            else:
                timeout_counter[0] -= 1
                progress.setValue(timeout_counter[0])
                status_label.setText(f"Waiting for card... ({timeout_counter[0]}s remaining)")
        
        enrollment_timer.timeout.connect(check_card)
        enrollment_timer.start(1000)  # Check every second
        
        # Show dialog (non-blocking internally because of timer)
        result = enrollment_dialog.exec()
        
        # Clean up
        enrollment_timer.stop()
        self.current_enrollment_username = None
        self.rfid_detected_card = None
        
        # Return card ID if successful, None if cancelled/timeout
        if result == QDialog.Accepted and detected_card[0]:
            return detected_card[0]
        else:
            return None
    
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
        
        # Set color based on status message content
        if any(indicator in status for indicator in ["✓", "ready", "Connected to", "Card detected"]):
            # Success/ready status - green
            self.rfid_status_label.setStyleSheet("QLabel { color: green; font-size: 11px; font-weight: bold; }")
        elif any(indicator in status for indicator in ["❌", "Error", "Failed", "not found", "lost"]):
            # Error status - red
            self.rfid_status_label.setStyleSheet("QLabel { color: red; font-size: 11px; }")
        elif any(indicator in status for indicator in ["⚠️", "Timeout", "Retrying"]):
            # Warning status - orange
            self.rfid_status_label.setStyleSheet("QLabel { color: orange; font-size: 11px; }")
        else:
            # Default/info status - blue
            self.rfid_status_label.setStyleSheet("QLabel { color: blue; font-size: 11px; }")
    
    def _on_rfid_device_ready(self) -> None:
        """Handle RFID device ready signal."""
        self.rfid_status_label.setText("✓ RFID ready - Present card to login")
        self.rfid_status_label.setStyleSheet("QLabel { color: green; font-size: 11px; }")
        self.rfid_enabled = True
    
    def _on_rfid_device_lost(self) -> None:
        """Handle RFID device lost signal."""
        self.rfid_status_label.setText("❌ RFID device disconnected - Try restarting GUI")
        self.rfid_status_label.setStyleSheet("QLabel { color: red; font-size: 11px; }")
        self.rfid_card_label.setText("No card detected")
        self.rfid_card_label.setStyleSheet("QLabel { color: gray; }")
        self.rfid_enabled = False
        
        # Show helpful message box
        QMessageBox.warning(
            self,
            "RFID Reader Disconnected",
            "RFID card reader has disconnected.\n\n"
            "If the reader fails to reconnect automatically:\n"
            "1. Check USB connection\n"
            "2. Close and restart the GUI application\n\n"
            "The reader will attempt to reconnect every 3 seconds."
        )
    
    def _on_rfid_error(self, error_msg: str) -> None:
        """Handle RFID error."""
        self.rfid_status_label.setText(f"⚠️  {error_msg}")
        self.rfid_status_label.setStyleSheet("QLabel { color: orange; font-size: 11px; }")
        
        # If it's a connection failure after logout, show restart suggestion
        if "not found" in error_msg.lower() or "cannot connect" in error_msg.lower():
            # Check if this is a reconnection attempt (not first startup)
            if hasattr(self, '_rfid_connection_attempts'):
                self._rfid_connection_attempts += 1
                # Show message after 3 failed attempts
                if self._rfid_connection_attempts >= 3:
                    QMessageBox.warning(
                        self,
                        "RFID Reader Connection Issue",
                        "RFID card reader cannot connect.\n\n"
                        "The reader shows as connected but may not be responding.\n"
                        "Please close and restart the GUI application.\n\n"
                        "This can happen after logout if the previous session\n"
                        "did not release the serial port properly."
                    )
                    self._rfid_connection_attempts = 0  # Reset counter
            else:
                self._rfid_connection_attempts = 1
    
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
        self._cleanup_rfid_thread()
        super().closeEvent(event)
    
    def _cleanup_rfid_thread(self):
        """Stop and cleanup RFID thread completely."""
        if self.rfid_thread:
            print("🛑 Stopping RFID reader thread...")
            
            # Disconnect signals first to prevent any callbacks during cleanup
            try:
                self.rfid_thread.card_detected.disconnect()
                self.rfid_thread.device_ready.disconnect()
                self.rfid_thread.device_lost.disconnect()
                self.rfid_thread.error_occurred.disconnect()
                self.rfid_thread.status_changed.disconnect()
            except:
                pass  # Ignore if already disconnected
            
            # Stop the thread
            self.rfid_thread.stop()
            
            # Wait for thread to actually stop with timeout
            if not self.rfid_thread.wait(5000):  # 5 second timeout
                print("⚠️ RFID thread did not stop gracefully, forcing termination")
                self.rfid_thread.terminate()
                self.rfid_thread.wait(2000)
            else:
                print("✓ RFID reader thread stopped cleanly")
            
            # Delete the thread object to ensure proper cleanup
            self.rfid_thread.deleteLater()
            self.rfid_thread = None
            
        # Clear any stored card data
        self.rfid_detected_card = None
        self.current_enrollment_username = None
        
        print("✓ RFID thread cleanup complete")