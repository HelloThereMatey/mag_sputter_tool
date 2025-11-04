from __future__ import annotations

import os
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


class SecurePasswordManager:
    """Manages encrypted password storage for mode protection."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            # Store in user's home directory, hidden folder
            config_dir = Path.home() / ".sputter_control"
        
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        self.password_file = self.config_dir / "mode_auth.enc"
        self.salt_file = self.config_dir / "salt.bin"
        
    def _generate_key(self, password: str, salt: bytes) -> bytes:
        """Generate encryption key from password and salt."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,  # Strong iteration count
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def _get_or_create_salt(self) -> bytes:
        """Get existing salt or create new one."""
        if self.salt_file.exists():
            return self.salt_file.read_bytes()
        else:
            salt = os.urandom(16)
            self.salt_file.write_bytes(salt)
            return salt
    
    def has_passwords_configured(self) -> bool:
        """Check if passwords are already configured."""
        return self.password_file.exists()
    
    def is_setup(self) -> bool:
        """Alias for has_passwords_configured for consistency."""
        return self.has_passwords_configured()
    
    def setup_passwords(self, master_password: str, mode_passwords: Dict[str, str]) -> bool:
        """Set up encrypted password storage."""
        try:
            salt = self._get_or_create_salt()
            key = self._generate_key(master_password, salt)
            fernet = Fernet(key)
            
            # Hash the mode passwords for storage
            hashed_passwords = {}
            for mode, password in mode_passwords.items():
                hashed_passwords[mode] = hashlib.sha256(password.encode()).hexdigest()
            
            # Encrypt and save
            encrypted_data = fernet.encrypt(json.dumps(hashed_passwords).encode())
            self.password_file.write_bytes(encrypted_data)
            
            return True
            
        except Exception as e:
            print(f"❌ Error setting up passwords: {e}")
            return False
    
    def verify_password(self, master_password: str, mode: str, password: str) -> bool:
        """Verify a password for a specific mode."""
        try:
            if not self.password_file.exists():
                return False
            
            salt = self._get_or_create_salt()
            key = self._generate_key(master_password, salt)
            fernet = Fernet(key)
            
            # Decrypt password data
            encrypted_data = self.password_file.read_bytes()
            decrypted_data = fernet.decrypt(encrypted_data)
            password_hashes = json.loads(decrypted_data.decode())
            
            # Check password
            if mode.lower() in password_hashes:
                provided_hash = hashlib.sha256(password.encode()).hexdigest()
                return provided_hash == password_hashes[mode.lower()]
            
            return False
            
        except Exception as e:
            print(f"❌ Error verifying password: {e}")
            return False
    
    def verify_mode_password_only(self, mode: str, password: str, master_password: str = None) -> bool:
        """
        Verify a mode password with optional master password.
        If master_password is None, tries common master passwords.
        """
        try:
            if not self.password_file.exists():
                return False
            
            salt = self._get_or_create_salt()
            
            # If master password provided, try it first
            if master_password:
                try:
                    key = self._generate_key(master_password, salt)
                    fernet = Fernet(key)
                    encrypted_data = self.password_file.read_bytes()
                    decrypted_data = fernet.decrypt(encrypted_data)
                    password_hashes = json.loads(decrypted_data.decode())
                    
                    if mode.lower() in password_hashes:
                        provided_hash = hashlib.sha256(password.encode()).hexdigest()
                        return provided_hash == password_hashes[mode.lower()]
                except:
                    pass
            
            # Try common master passwords if none provided or failed
            common_masters = ["admin", "master", "password", "sputter", "default"]
            
            for master in common_masters:
                try:
                    key = self._generate_key(master, salt)
                    fernet = Fernet(key)
                    encrypted_data = self.password_file.read_bytes()
                    decrypted_data = fernet.decrypt(encrypted_data)
                    password_hashes = json.loads(decrypted_data.decode())
                    
                    if mode.lower() in password_hashes:
                        provided_hash = hashlib.sha256(password.encode()).hexdigest()
                        if provided_hash == password_hashes[mode.lower()]:
                            return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            print(f"❌ Error verifying mode password: {e}")
            return False

    def verify_master_password(self, master_password: str) -> tuple[bool, str]:
        """
        Verify if the master password is correct by attempting to decrypt the password file.
        Returns (success, message) tuple.
        """
        try:
            if not self.password_file.exists():
                return False, "Password file does not exist"
            
            salt = self._get_or_create_salt()
            key = self._generate_key(master_password, salt)
            fernet = Fernet(key)
            
            # Try to decrypt the password data
            encrypted_data = self.password_file.read_bytes()
            decrypted_data = fernet.decrypt(encrypted_data)
            
            # Try to parse as JSON
            password_hashes = json.loads(decrypted_data.decode())
            
            # If we got here, the master password is correct
            return True, "Master password is correct"
            
        except Exception as e:
            return False, f"Invalid master password: {str(e)}"

    def debug_verify_password(self, master_password: str, mode: str, password: str) -> tuple[bool, str]:
        """Debug version of verify_password that returns detailed info."""
        try:
            if not self.password_file.exists():
                return False, "Password file does not exist"
            
            salt = self._get_or_create_salt()
            key = self._generate_key(master_password, salt)
            fernet = Fernet(key)
            
            # Decrypt password data
            encrypted_data = self.password_file.read_bytes()
            decrypted_data = fernet.decrypt(encrypted_data)
            password_hashes = json.loads(decrypted_data.decode())
            
            # Check password
            if mode.lower() in password_hashes:
                provided_hash = hashlib.sha256(password.encode()).hexdigest()
                stored_hash = password_hashes[mode.lower()]
                
                if provided_hash == stored_hash:
                    return True, f"Password correct for mode {mode}"
                else:
                    return False, f"Password hash mismatch. Provided: {provided_hash[:10]}..., Stored: {stored_hash[:10]}..."
            else:
                available_modes = list(password_hashes.keys())
                return False, f"Mode '{mode}' not found. Available modes: {available_modes}"
            
        except Exception as e:
            return False, f"Error verifying password: {e}"

    def reset_passwords(self) -> bool:
        """Reset all password data (requires re-setup)."""
        try:
            if self.password_file.exists():
                self.password_file.unlink()
            if self.salt_file.exists():
                self.salt_file.unlink()
            return True
        except Exception as e:
            print(f"❌ Error resetting passwords: {e}")
            return False
    
    def change_master_password(self, old_master: str, new_master: str) -> bool:
        """Change the master password (re-encrypts data)."""
        try:
            if not self.password_file.exists():
                return False
            
            # Decrypt with old password
            salt = self._get_or_create_salt()
            old_key = self._generate_key(old_master, salt)
            fernet_old = Fernet(old_key)
            
            encrypted_data = self.password_file.read_bytes()
            decrypted_data = fernet_old.decrypt(encrypted_data)
            
            # Re-encrypt with new password
            new_salt = os.urandom(16)
            new_key = self._generate_key(new_master, new_salt)
            fernet_new = Fernet(new_key)
            
            new_encrypted_data = fernet_new.encrypt(decrypted_data)
            
            # Save new data
            self.salt_file.write_bytes(new_salt)
            self.password_file.write_bytes(new_encrypted_data)
            
            return True
            
        except Exception as e:
            print(f"❌ Error changing master password: {e}")
            return False

    def verify_mode_password_simple(self, mode: str, password: str) -> bool:
        """
        Verify mode password by trying all possible master passwords.
        This allows mode verification without knowing the master password.
        """
        try:
            if not self.password_file.exists():
                return False
            
            salt = self._get_or_create_salt()
            
            # Try all possible master passwords that could have been used
            possible_masters = [
                "admin", "master", "password", "sputter", "default",
                "123", "test", "root", "user", "control", "GoodD0ggy"
            ]
            
            # First try to find ANY working master password
            for master_candidate in possible_masters:
                try:
                    key = self._generate_key(master_candidate, salt)
                    fernet = Fernet(key)
                    encrypted_data = self.password_file.read_bytes()
                    decrypted_data = fernet.decrypt(encrypted_data)
                    password_hashes = json.loads(decrypted_data.decode())
                    
                    # If we can decrypt, now check the mode password
                    if mode.lower() in password_hashes:
                        provided_hash = hashlib.sha256(password.encode()).hexdigest()
                        if provided_hash == password_hashes[mode.lower()]:
                            return True
                    
                except:
                    continue
            
            return False
            
        except Exception as e:
            print(f"❌ Error verifying mode password (simple): {e}")
            return False
