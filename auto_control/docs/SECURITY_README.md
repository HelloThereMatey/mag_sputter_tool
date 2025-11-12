# Secure Password System for Sputter Control

## Overview
The mode passwords are now stored using military-grade encryption (AES-256) with the following security features:

### Security Features
- **No plaintext storage**: Passwords never stored in readable form
- **Master password protection**: All mode passwords encrypted with a master password
- **PBKDF2 key derivation**: 100,000 iterations with salt for brute-force protection
- **SHA-256 hashing**: Mode passwords are hashed before encryption
- **Secure random salts**: Each installation uses unique encryption keys

### Storage Location
- **Linux/macOS**: `~/.sputter_control/`
- **Windows**: `C:\Users\[Username]\.sputter_control\`

Files created:
- `mode_auth.enc` - Encrypted password data
- `salt.bin` - Random salt for key derivation

## Installation

### 1. Install cryptography dependency:
```bash
# If using conda environment
conda activate sput
pip install cryptography

# Or update your environment
conda env update -f sput.yml
```

### 2. First-time setup:
When you first access Manual or Override mode, you'll be prompted to:
1. Set a **master password** (8+ characters) - Remember this! Cannot be recovered if lost
2. Set **Manual mode password** (6+ characters)
3. Set **Override mode password** (6+ characters)

### 3. Daily usage:
- **Normal mode**: No password required
- **Manual/Override modes**: 
  - Enter master password (first time per session)
  - Enter mode-specific password

## Security Notes

### ⚠️ Important
- **Master password cannot be recovered** - write it down securely
- Mode passwords can be different from each other
- All passwords are case-sensitive
- Passwords are only stored encrypted, never in plain text

### Password Reset
If you forget your master password:
1. Delete the folder: `~/.sputter_control/`
2. Restart the application
3. Set up new passwords when prompted

### Changing Passwords
Currently requires manual reset (delete config folder). Future versions will include password change dialogs.

## Technical Details
- **Encryption**: AES-256 in Fernet mode (symmetric encryption)
- **Key Derivation**: PBKDF2-HMAC-SHA256 with 100,000 iterations
- **Password Hashing**: SHA-256 for mode password verification
- **Salt**: 16-byte random salt per installation
- **Library**: Python `cryptography` package (industry standard)

This implementation follows security best practices and is suitable for industrial/laboratory environments.
