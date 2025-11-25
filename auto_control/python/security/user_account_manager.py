"""
User Account Manager for Sputter Control System

Extends SecurePasswordManager to provide multi-user authentication with role-based access control.
Supports 4 user levels:
- Level 1 (Operator): Basic operation only
- Level 2 (Technician): Normal and Manual modes
- Level 3 (Master): All modes including Override
- Level 4 (Administrator): User management + Level 3 permissions
"""

from __future__ import annotations

import os
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

try:
    from .password_manager import SecurePasswordManager
except ImportError:
    from password_manager import SecurePasswordManager


class UserAccountManager(SecurePasswordManager):
    """Manages encrypted user accounts with role-based access control."""
    
    # User permission levels
    LEVEL_OPERATOR = 1
    LEVEL_TECHNICIAN = 2
    LEVEL_MASTER = 3
    LEVEL_ADMINISTRATOR = 4
    
    LEVEL_NAMES = {
        1: "Operator",
        2: "Technician",
        3: "Master",
        4: "Administrator"
    }
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize user account manager."""
        super().__init__(config_dir)
        
        self.users_file = self.config_dir / "users.enc"
        self.master_password_hash_file = self.config_dir / "master.hash"
        
    def has_users_configured(self) -> bool:
        """Check if any users exist."""
        return self.users_file.exists()
    
    def has_master_password(self) -> bool:
        """Check if master password is set."""
        return self.master_password_hash_file.exists()
    
    def _hash_password(self, password: str, salt: Optional[bytes] = None) -> Tuple[str, bytes]:
        """Hash password with salt. Returns (hash_hex, salt)."""
        if salt is None:
            salt = os.urandom(16)
        
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        return password_hash.hex(), salt
    
    def setup_master_password(self, master_password: str) -> bool:
        """Set up the master password (required for first-time setup)."""
        try:
            password_hash, salt = self._hash_password(master_password)
            
            master_data = {
                'hash': password_hash,
                'salt': salt.hex(),
                'created': datetime.now().isoformat()
            }
            
            self.master_password_hash_file.write_text(json.dumps(master_data))
            return True
            
        except Exception as e:
            print(f"❌ Error setting up master password: {e}")
            return False
    
    def verify_master_password(self, master_password: str) -> bool:
        """Verify the master password."""
        try:
            if not self.master_password_hash_file.exists():
                return False
            
            master_data = json.loads(self.master_password_hash_file.read_text())
            stored_hash = master_data['hash']
            salt = bytes.fromhex(master_data['salt'])
            
            provided_hash, _ = self._hash_password(master_password, salt)
            
            return provided_hash == stored_hash
            
        except Exception as e:
            print(f"❌ Error verifying master password: {e}")
            return False
    
    def _get_encryption_key(self) -> bytes:
        """Generate encryption key from a fixed system key (not master password)."""
        salt = self._get_or_create_salt()
        # Use a fixed key for general encryption (not master password)
        # Master password is only needed for permission level changes
        system_key = "sputter_control_system_key_v1"
        return self._generate_key(system_key, salt)
    
    def _migrate_old_database(self, master_password: str) -> bool:
        """Migrate database from master password encryption to system key encryption."""
        try:
            print("🔄 Attempting to migrate user database to new encryption...")
            
            if not self.users_file.exists():
                return False
            
            # Try to load with old master password-based encryption
            salt = self._get_or_create_salt()
            old_key = self._generate_key(master_password, salt)
            fernet = Fernet(old_key)
            
            encrypted_data = self.users_file.read_bytes()
            decrypted_data = fernet.decrypt(encrypted_data)
            users = json.loads(decrypted_data.decode())
            
            print(f"✅ Successfully decrypted old database with {len(users)} users")
            
            # Re-save with new system key encryption
            new_key = self._get_encryption_key()
            new_fernet = Fernet(new_key)
            new_encrypted_data = new_fernet.encrypt(json.dumps(users).encode())
            self.users_file.write_bytes(new_encrypted_data)
            
            print("✅ Successfully migrated database to new encryption")
            return True
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            return False
    
    def _load_users(self) -> Optional[Dict]:
        """Load and decrypt user database (no master password needed)."""
        try:
            if not self.users_file.exists():
                return {}
            
            key = self._get_encryption_key()
            fernet = Fernet(key)
            
            encrypted_data = self.users_file.read_bytes()
            decrypted_data = fernet.decrypt(encrypted_data)
            users = json.loads(decrypted_data.decode())
            
            return users
            
        except Exception as e:
            print(f"❌ Error loading users: {e}")
            return None
    
    def _save_users(self, users: Dict) -> bool:
        """Encrypt and save user database (no master password needed)."""
        try:
            key = self._get_encryption_key()
            fernet = Fernet(key)
            
            encrypted_data = fernet.encrypt(json.dumps(users).encode())
            self.users_file.write_bytes(encrypted_data)
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving users: {e}")
            return False
    
    def create_user(self, username: str, password: str, card_id: str, admin_level: int, 
                   creator: str, master_password: str = None) -> Tuple[bool, str]:
        """
        Create a new user account with mandatory RFID card AND password.
        
        Args:
            username: New username
            password: User password (can be empty string, but required parameter)
            card_id: RFID card ID (REQUIRED)
            admin_level: Permission level (1-4)
            creator: Username of creating user
            master_password: Master password (NOT required, kept for compatibility)
        
        Returns:
            (success, message) tuple
        """
        try:
            # Validate admin level
            if admin_level not in [1, 2, 3, 4]:
                return False, "Invalid admin level. Must be 1-4."
            
            # Validate card_id is provided
            if not card_id or not card_id.strip():
                return False, "RFID card is required to create an account."
            
            # Password must be provided (can be empty string)
            if password is None:
                return False, "Password parameter is required (can be empty string for no password)."
            
            # Load existing users
            users = self._load_users()
            if users is None:
                return False, "Failed to load user database."
            
            # Check if user already exists
            if username.lower() in users:
                return False, f"User '{username}' already exists."
            
            # Check if card is already enrolled
            for existing_user in users.values():
                if existing_user.get('rfid_card_id') == card_id:
                    return False, f"This RFID card is already enrolled to user '{existing_user['username']}'."
            
            # Hash password (even if empty string)
            password_hash, salt = self._hash_password(password)
            
            # Create user record (with both password and RFID)
            users[username.lower()] = {
                'username': username,  # Store original case
                'password_hash': password_hash,
                'password_salt': salt.hex(),
                'rfid_card_id': card_id,
                'rfid_enrolled_date': datetime.now().isoformat(),
                'admin_level': admin_level,
                'created_date': datetime.now().isoformat(),
                'created_by': creator,
                'last_login': None,
                'login_count': 0
            }
            
            # Save users
            if self._save_users(users):
                return True, f"User '{username}' created successfully with level {admin_level} ({self.LEVEL_NAMES[admin_level]})."
            else:
                return False, "Failed to save user database."
            
        except Exception as e:
            return False, f"Error creating user: {e}"
    
    def authenticate_user(self, username: str, password: str) -> Tuple[bool, Optional[Dict], str]:
        """
        Authenticate a user with username and password (fallback method).
        
        Args:
            username: Username
            password: User password
        
        Returns:
            (success, user_info, message) tuple
        """
        try:
            # Load users
            users = self._load_users()
            if users is None:
                return False, None, "Failed to load user database."
            
            # Check if user exists
            username_lower = username.lower()
            if username_lower not in users:
                return False, None, "Invalid username or password."
            
            user = users[username_lower]
            
            # Check if user has password hash
            if 'password_hash' not in user:
                return False, None, "This account does not have password authentication enabled."
            
            # Verify password
            stored_hash = user['password_hash']
            salt = bytes.fromhex(user['password_salt'])
            
            provided_hash, _ = self._hash_password(password, salt)
            
            if provided_hash != stored_hash:
                return False, None, "Invalid username or password."
            
            # Update login statistics
            user['last_login'] = datetime.now().isoformat()
            user['login_count'] = user.get('login_count', 0) + 1
            user['last_login_method'] = 'password'
            
            # Save updated stats
            self._save_users(users)
            
            # Return user info (without sensitive data)
            user_info = {
                'username': user['username'],
                'admin_level': user['admin_level'],
                'level_name': self.LEVEL_NAMES[user['admin_level']],
                'last_login': user['last_login'],
                'login_count': user['login_count']
            }
            
            return True, user_info, "Authentication successful."
            
        except Exception as e:
            return False, None, f"Authentication error: {e}"
    
    def change_user_level(self, target_user: str, new_level: int, 
                         admin_user: str, master_password: str) -> Tuple[bool, str]:
        """
        Change a user's permission level.
        MASTER PASSWORD REQUIRED - This is a sensitive operation.
        
        Args:
            target_user: Username to modify
            new_level: New admin level (1-4)
            admin_user: Username of administrator making change
            master_password: Master password (REQUIRED)
        
        Returns:
            (success, message) tuple
        """
        try:
            # Validate new level
            if new_level not in [1, 2, 3, 4]:
                return False, "Invalid admin level. Must be 1-4."
            
            # Verify master password - REQUIRED for this operation
            if not self.verify_master_password(master_password):
                return False, "Invalid master password."
            
            # Load users (using system key)
            users = self._load_users()
            if users is None:
                return False, "Failed to load user database."
            
            # Check if target user exists
            target_lower = target_user.lower()
            if target_lower not in users:
                return False, f"User '{target_user}' not found."
            
            # Update level
            old_level = users[target_lower]['admin_level']
            users[target_lower]['admin_level'] = new_level
            users[target_lower]['level_modified_date'] = datetime.now().isoformat()
            users[target_lower]['level_modified_by'] = admin_user
            
            # Save users
            if self._save_users(users):
                return True, f"User '{target_user}' level changed from {old_level} to {new_level}."
            else:
                return False, "Failed to save user database."
            
        except Exception as e:
            return False, f"Error changing user level: {e}"
    
    def delete_user(self, target_user: str, admin_user: str) -> Tuple[bool, str]:
        """
        Delete a user account.
        
        Args:
            target_user: Username to delete
            admin_user: Username of administrator
        
        Returns:
            (success, message) tuple
        """
        try:
            # Load users
            users = self._load_users()
            if users is None:
                return False, "Failed to load user database."
            
            # Check if target user exists
            target_lower = target_user.lower()
            if target_lower not in users:
                return False, f"User '{target_user}' not found."
            
            # Prevent deleting yourself
            if target_lower == admin_user.lower():
                return False, "Cannot delete your own account."
            
            # Delete user
            del users[target_lower]
            
            # Save users
            if self._save_users(users):
                return True, f"User '{target_user}' deleted successfully."
            else:
                return False, "Failed to save user database."
            
        except Exception as e:
            return False, f"Error deleting user: {e}"
    
    def get_user_info(self, username: str) -> Optional[Dict]:
        """Get user information (without password)."""
        try:
            users = self._load_users()
            if users is None:
                return None
            
            username_lower = username.lower()
            if username_lower not in users:
                return None
            
            user = users[username_lower]
            
            return {
                'username': user['username'],
                'admin_level': user['admin_level'],
                'level_name': self.LEVEL_NAMES[user['admin_level']],
                'created_date': user.get('created_date'),
                'created_by': user.get('created_by'),
                'last_login': user.get('last_login'),
                'login_count': user.get('login_count', 0)
            }
            
        except Exception as e:
            print(f"❌ Error getting user info: {e}")
            return None
    
    def list_users(self) -> Optional[List[Dict]]:
        """List all users."""
        try:
            users = self._load_users()
            if users is None:
                return None
            
            user_list = []
            for username_lower, user in users.items():
                user_list.append({
                    'username': user['username'],
                    'admin_level': user['admin_level'],
                    'level_name': self.LEVEL_NAMES[user['admin_level']],
                    'created_date': user.get('created_date'),
                    'last_login': user.get('last_login'),
                    'login_count': user.get('login_count', 0)
                })
            
            return user_list
            
        except Exception as e:
            print(f"❌ Error listing users: {e}")
            return None
    
    def change_user_password(self, username: str, old_password: str, new_password: str) -> Tuple[bool, str]:
        """Change a user's password."""
        try:
            # Authenticate with old password first
            success, user_info, msg = self.authenticate_user(username, old_password)
            if not success:
                return False, "Old password is incorrect."
            
            # Load users
            users = self._load_users()
            if users is None:
                return False, "Failed to load user database."
            
            # Hash new password
            password_hash, salt = self._hash_password(new_password)
            
            # Update password
            username_lower = username.lower()
            users[username_lower]['password_hash'] = password_hash
            users[username_lower]['password_salt'] = salt.hex()
            users[username_lower]['password_changed'] = datetime.now().isoformat()
            
            # Save users
            if self._save_users(users):
                return True, "Password changed successfully."
            else:
                return False, "Failed to save user database."
            
        except Exception as e:
            return False, f"Error changing password: {e}"
    
    # ==================== RFID Card Integration ====================
    
    def enroll_rfid_card(self, username: str, card_id: str) -> Tuple[bool, str]:
        """
        Enroll an RFID card for a user.
        
        Args:
            username: Username to enroll card for
            card_id: RFID card ID (e.g., "08:5C:D1:4C")
        
        Returns:
            (success, message) tuple
        """
        try:
            # Load users
            users = self._load_users()
            if users is None:
                return False, "Failed to load user database."
            
            # Check if user exists
            username_lower = username.lower()
            if username_lower not in users:
                return False, f"User '{username}' not found."
            
            # Check if card is already registered to another user
            for u_name, u_data in users.items():
                if u_data.get('rfid_card_id') == card_id and u_name != username_lower:
                    return False, f"Card already registered to user '{u_data['username']}'."
            
            # Enroll card
            users[username_lower]['rfid_card_id'] = card_id
            users[username_lower]['rfid_enrolled_date'] = datetime.now().isoformat()
            
            # Save users
            if self._save_users(users):
                return True, f"RFID card '{card_id}' enrolled for user '{username}'."
            else:
                return False, "Failed to save user database."
            
        except Exception as e:
            return False, f"Error enrolling RFID card: {e}"
    
    def authenticate_by_rfid(self, card_id: str) -> Tuple[bool, Optional[Dict], str]:
        """
        Authenticate a user by RFID card ID.
        
        Args:
            card_id: RFID card ID to look up
        
        Returns:
            (success, user_info, message) tuple
        """
        try:
            # Load users
            users = self._load_users()
            if users is None:
                return False, None, "Failed to load user database."
            
            # Find user with matching RFID card
            for username_lower, user in users.items():
                if user.get('rfid_card_id') == card_id:
                    # Update login statistics
                    user['last_login'] = datetime.now().isoformat()
                    user['login_count'] = user.get('login_count', 0) + 1
                    user['last_login_method'] = 'rfid_card'
                    
                    # Save updated stats
                    self._save_users(users)
                    
                    # Return user info
                    user_info = {
                        'username': user['username'],
                        'admin_level': user['admin_level'],
                        'level_name': self.LEVEL_NAMES[user['admin_level']],
                        'last_login': user['last_login'],
                        'login_count': user['login_count'],
                        'rfid_card_id': card_id
                    }
                    
                    return True, user_info, f"Welcome, {user['username']}!"
            
            return False, None, "Card not registered. Please log in with username/password."
            
        except Exception as e:
            return False, None, f"RFID authentication error: {e}"
    
    def remove_rfid_card(self, username: str) -> Tuple[bool, str]:
        """
        Remove RFID card enrollment for a user.
        
        Args:
            username: Username to remove card from
        
        Returns:
            (success, message) tuple
        """
        try:
            # Load users
            users = self._load_users()
            if users is None:
                return False, "Failed to load user database."
            
            # Check if user exists
            username_lower = username.lower()
            if username_lower not in users:
                return False, f"User '{username}' not found."
            
            # Check if user has RFID card
            if 'rfid_card_id' not in users[username_lower]:
                return False, f"User '{username}' has no RFID card enrolled."
            
            # Remove card
            card_id = users[username_lower].pop('rfid_card_id', None)
            users[username_lower].pop('rfid_enrolled_date', None)
            
            # Save users
            if self._save_users(users):
                return True, f"RFID card '{card_id}' removed from user '{username}'."
            else:
                return False, "Failed to save user database."
            
        except Exception as e:
            return False, f"Error removing RFID card: {e}"
    
    def get_rfid_card_id(self, username: str) -> Optional[str]:
        """
        Get the RFID card ID for a user (if enrolled).
        
        Args:
            username: Username to look up
        
        Returns:
            Card ID string or None if not enrolled
        """
        try:
            users = self._load_users()
            if users is None:
                return None
            
            username_lower = username.lower()
            if username_lower not in users:
                return None
            
            return users[username_lower].get('rfid_card_id')
            
        except Exception:
            return None
