"""
Login Dialog for Sputter Control System

Provides initial authentication before main GUI launch.
Supports username/password login and account creation.
"""

from typing import Optional
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
)
from PyQt5.QtCore import Qt, QTimer
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
        self.setMinimumWidth(500)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)

        self._init_ui()

        if not self.user_manager.has_users_configured():
            self._show_first_time_setup()
        else:
            self._check_and_migrate_database()

    def _check_and_migrate_database(self):
        """Check if database needs migration and attempt it."""
        from PyQt5.QtWidgets import QInputDialog

        test_users = self.user_manager._load_users()

        if test_users is None and self.user_manager.has_users_configured():
            reply = QMessageBox.question(
                self,
                "Database Migration",
                "User database needs to be migrated to new encryption format.\n\n"
                "Enter master password to migrate:",
                QMessageBox.Ok | QMessageBox.Cancel,
            )

            if reply == QMessageBox.Ok:
                master_password, ok = QInputDialog.getText(
                    self,
                    "Master Password",
                    "Enter master password:",
                    QLineEdit.Password,
                )

                if ok and master_password:
                    if self.user_manager._migrate_old_database(master_password):
                        QMessageBox.information(
                            self,
                            "Success",
                            "Database migrated successfully!\n\n"
                            "You can now log in.",
                        )
                    else:
                        QMessageBox.critical(
                            self,
                            "Migration Failed",
                            "Failed to migrate database.\n\n"
                            "Please contact system administrator.",
                        )

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        title = QLabel("Sputter Control System")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("User Authentication")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("QLabel { font-size: 12pt; font-weight: bold; }")
        layout.addWidget(subtitle)

        layout.addSpacing(20)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter username")
        layout.addWidget(self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self._on_password_login)
        layout.addWidget(self.password_input)

        layout.addSpacing(12)

        password_login_button = QPushButton("Login")
        password_login_button.clicked.connect(self._on_password_login)
        password_login_button.setStyleSheet(
            """
            QPushButton {
                font-size: 10pt;
                padding: 8px 16px;
                background-color: #16a085;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #138d75;
            }
        """
        )
        layout.addWidget(password_login_button)

        layout.addSpacing(20)

        button_layout = QHBoxLayout()

        self.create_account_button = QPushButton("Create New Account")
        self.create_account_button.clicked.connect(self._on_create_account)
        self.create_account_button.setStyleSheet(
            """
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
        """
        )
        button_layout.addWidget(self.create_account_button)

        self.cancel_button = QPushButton("Exit Application")
        self.cancel_button.clicked.connect(self._on_cancel)
        self.cancel_button.setStyleSheet(
            """
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
        """
        )
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("QLabel { color: red; font-size: 10pt; }")
        layout.addWidget(self.status_label)

    def _on_password_login(self):
        """Handle password login button click."""
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username:
            self.status_label.setText("Please enter username")
            self.status_label.setStyleSheet("QLabel { color: red; font-size: 10pt; }")
            return

        success, user_info, message = self.user_manager.authenticate_user(username, password)

        if success:
            self.authenticated_user = user_info
            self.master_password = None

            self.status_label.setText(f"✓ {message}")
            self.status_label.setStyleSheet("QLabel { color: green; font-size: 10pt; }")
            QTimer.singleShot(500, self.accept)
        else:
            self.status_label.setText(f"✗ {message}")
            self.status_label.setStyleSheet("QLabel { color: red; font-size: 10pt; }")
            self.password_input.clear()

    def _show_first_time_setup(self):
        """Show first-time setup dialog to create master password and first admin."""
        msg = QMessageBox(self)
        msg.setWindowTitle("First-Time Setup")
        msg.setIcon(QMessageBox.Information)
        msg.setText(
            "No user accounts exist.\n\n"
            "You will now create the master password and first administrator account.\n\n"
            "The master password is required to create users with elevated permissions."
        )
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()

        master_password = self._get_master_password_setup()
        if not master_password:
            self._on_cancel()
            return

        success = self._create_first_admin(master_password)
        if not success:
            self._on_cancel()

    def _get_master_password_setup(self) -> Optional[str]:
        """Get master password during first-time setup."""
        from PyQt5.QtWidgets import QInputDialog

        while True:
            password, ok = QInputDialog.getText(
                self,
                "Master Password Setup",
                "Enter master password:\n(Required for managing users with level 2+ permissions)",
                QLineEdit.Password,
            )

            if not ok:
                return None

            if not password:
                QMessageBox.warning(self, "Empty Password", "Master password cannot be empty.")
                continue

            confirm, ok = QInputDialog.getText(
                self,
                "Confirm Master Password",
                "Confirm master password:",
                QLineEdit.Password,
            )

            if not ok:
                return None

            if password != confirm:
                QMessageBox.warning(self, "Mismatch", "Passwords do not match.")
                continue

            if self.user_manager.setup_master_password(password):
                QMessageBox.information(self, "Success", "Master password created successfully.")
                return password

            QMessageBox.critical(self, "Error", "Failed to create master password.")
            return None

    def _create_first_admin(self, master_password: str) -> bool:
        """Create first administrator account."""
        from PyQt5.QtWidgets import QInputDialog

        QMessageBox.information(
            self,
            "Create Administrator",
            "Now create the first administrator account.\n\n"
            "Level 4 (Administrator) has full system access\n"
            "and can manage other user accounts.",
        )

        username, ok = QInputDialog.getText(
            self,
            "Administrator Username",
            "Enter administrator username:",
        )

        if not ok or not username:
            return False

        while True:
            password, ok = QInputDialog.getText(
                self,
                "Administrator Password",
                "Enter administrator password:",
                QLineEdit.Password,
            )

            if not ok:
                return False

            if not password:
                QMessageBox.warning(self, "Empty Password", "Password cannot be empty.")
                continue

            confirm, ok = QInputDialog.getText(
                self,
                "Confirm Password",
                "Confirm administrator password:",
                QLineEdit.Password,
            )

            if not ok:
                return False

            if password != confirm:
                QMessageBox.warning(self, "Mismatch", "Passwords do not match.")
                continue

            break

        success, message = self.user_manager.create_user(
            username,
            password,
            None,
            UserAccountManager.LEVEL_ADMINISTRATOR,
            "system",
        )

        if success:
            QMessageBox.information(
                self,
                "Success",
                f"Administrator account '{username}' created.\n\n"
                "You can now log in with username/password.",
            )
            return True

        QMessageBox.critical(self, "Error", f"Failed to create administrator:\n{message}")
        return False

    def _on_create_account(self):
        """Handle create account button click."""
        from PyQt5.QtWidgets import QInputDialog

        username, ok = QInputDialog.getText(
            self,
            "Create New Account",
            "Enter username for new account:",
        )

        if not ok or not username.strip():
            return

        username = username.strip()

        QMessageBox.information(
            self,
            "Password Setup",
            f"Creating account '{username}'.\n\n"
            "You must set a password (can be empty for no password).",
        )

        password, ok = QInputDialog.getText(
            self,
            "Set Password",
            f"Enter password for '{username}':\n(Leave empty for no password)",
            QLineEdit.Password,
        )

        if not ok:
            return

        confirm_password, ok = QInputDialog.getText(
            self,
            "Confirm Password",
            "Confirm password:",
            QLineEdit.Password,
        )

        if not ok:
            return

        if password != confirm_password:
            QMessageBox.warning(
                self,
                "Password Mismatch",
                "Passwords do not match. Account creation cancelled.",
            )
            return

        success, message = self.user_manager.create_user(
            username,
            password,
            None,
            UserAccountManager.LEVEL_OPERATOR,
            "self-registration",
        )

        if success:
            password_msg = "Password set" if password else "No password set"
            QMessageBox.information(
                self,
                "Account Created",
                f"Account '{username}' created successfully!\n\n"
                f"Permission Level: {UserAccountManager.LEVEL_NAMES[UserAccountManager.LEVEL_OPERATOR]}\n"
                f"{password_msg}\n\n"
                "Logging you in now...",
            )

            user_info = self.user_manager.get_user_info(username)
            if user_info:
                self.authenticated_user = user_info
                self.master_password = None
                QTimer.singleShot(500, self.accept)
        else:
            QMessageBox.critical(self, "Account Creation Failed", f"Failed to create account:\n{message}")

    def _on_cancel(self):
        """Handle cancel/exit button click."""
        reply = QMessageBox.question(
            self,
            "Exit Application",
            "Are you sure you want to exit?\n\nYou must log in to use the application.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.reject()

    def get_authenticated_user(self):
        """Get authenticated user info."""
        return self.authenticated_user

    def get_master_password(self):
        """Get master password (for user management operations)."""
        return self.master_password
