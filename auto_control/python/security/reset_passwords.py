#!/usr/bin/env python3
"""
Command-line password reset utility for Sputter Control System.
Allows resetting mode passwords with master password verification.
"""

import sys
import os
import getpass
from pathlib import Path

# Add parent directory to path for imports
wd = os.path.dirname((os.path.abspath(__file__)))
python_path = os.path.dirname(wd)
print(python_path)
sys.path.append(python_path)

try:
    from security.password_manager import SecurePasswordManager
except ImportError:
    print("Error: Could not import SecurePasswordManager")
    print("Make sure you're running this from the auto_control/python directory.")
    print(f"Current directory: {Path.cwd()}")
    print(f"Expected directory: .../auto_control/python")
    sys.exit(1)


def main():
    """Main password reset utility."""
    print("=" * 60)
    print("SPUTTER CONTROL SYSTEM - PASSWORD RESET UTILITY")
    print("=" * 60)
    print()
    
    password_manager = SecurePasswordManager()
    
    # Check if passwords are configured
    if not password_manager.has_passwords_configured():
        print("No passwords are currently configured.")
        print("Run the main application first to set up initial passwords.")
        return
    
    print("This utility will reset the mode passwords for Manual and Override modes.")
    print("You will need to provide the current master password to proceed.")
    print()
    
    # Get master password
    master_password = getpass.getpass("Enter current master password: ")
    
    if not master_password:
        print("Master password cannot be empty.")
        return
    
    # Verify master password properly
    print("Verifying master password...")
    is_valid, message = password_manager.verify_master_password(master_password)
    
    if not is_valid:
        print(f"❌ Error: {message}")
        print("Password reset cancelled.")
        print()
        print("Troubleshooting tips:")
        print("- Make sure you're entering the correct master password")
        print("- Try running debug_passwords.py to test different master passwords")
        print("- If passwords are completely lost, use: python reset_passwords.py --reset-all")
        return
    
    print("✓ Master password verified successfully.")
    print()
    
    # Get new mode passwords
    print("Enter new passwords for protected modes:")
    print("(Press Enter to keep existing password)")
    print()
    
    new_passwords = {}
    
    # Manual mode password
    manual_password = getpass.getpass("Manual mode password: ")
    if manual_password:
        manual_confirm = getpass.getpass("Confirm manual mode password: ")
        if manual_password != manual_confirm:
            print("Manual mode password confirmation does not match.")
            return
        new_passwords["manual"] = manual_password
    
    # Override mode password
    override_password = getpass.getpass("Override mode password: ")
    if override_password:
        override_confirm = getpass.getpass("Confirm override mode password: ")
        if override_password != override_confirm:
            print("Override mode password confirmation does not match.")
            return
        new_passwords["override"] = override_password
    
    if not new_passwords:
        print("No new passwords provided. No changes made.")
        return
    
    # Get existing passwords and update only the specified ones
    try:
        salt = password_manager._get_or_create_salt()
        key = password_manager._generate_key(master_password, salt)
        
        from cryptography.fernet import Fernet
        import json
        
        fernet = Fernet(key)
        encrypted_data = password_manager.password_file.read_bytes()
        decrypted_data = fernet.decrypt(encrypted_data)
        existing_passwords = json.loads(decrypted_data.decode())
        
        # Update with new passwords
        for mode, password in new_passwords.items():
            import hashlib
            existing_passwords[mode] = hashlib.sha256(password.encode()).hexdigest()
            print(f"Updated password for {mode} mode.")
        
        # Re-encrypt and save
        updated_data = fernet.encrypt(json.dumps(existing_passwords).encode())
        password_manager.password_file.write_bytes(updated_data)
        
        print()
        print("Password reset completed successfully!")
        print("The new passwords will take effect immediately.")
        
    except Exception as e:
        print(f"❌ Error updating passwords: {e}")
        print("Password reset failed.")


def reset_all_passwords():
    """Complete password reset - removes all password data."""
    print("=" * 60)
    print("COMPLETE PASSWORD RESET")
    print("=" * 60)
    print()
    print("WARNING: This will completely remove all password data.")
    print("You will need to set up passwords again from scratch.")
    print()
    
    confirm = input("Type 'RESET' to confirm complete password removal: ")
    if confirm != "RESET":
        print("Reset cancelled.")
        return
    
    password_manager = SecurePasswordManager()
    
    if password_manager.reset_passwords():
        print("All password data has been removed.")
        print("Run the main application to set up new passwords.")
    else:
        print("Error removing password data.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--reset-all":
        reset_all_passwords()
    else:
        main()
