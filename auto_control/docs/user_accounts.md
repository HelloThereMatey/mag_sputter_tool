# User Account Management

## Overview

The Sputter Control System supports multi-user authentication with role-based access control. User accounts are encrypted and stored in `~/.sputter_control/users.enc`.

## User Permission Levels

Four permission levels are available:

| Level | Name | Capabilities |
|-------|------|--------------|
| 1 | **Operator** | Basic system operation only |
| 2 | **Technician** | Normal and Manual modes |
| 3 | **Master** | All modes including Override mode |
| 4 | **Administrator** | User management + Level 3 permissions |

## Creating User Accounts

### First-Time Setup

On first application launch, you will be prompted to:

1. **Set the master password** - Required for sensitive operations like changing user levels
2. **Create the first administrator account** - This account is automatically Level 4

### Creating Additional Accounts

During login, click **"Create Account"** to add new users:

1. Enter a username
2. Enter and confirm a password
3. Account is created with **Level 1 (Operator)** permissions by default
4. Optionally enroll an RFID card for quick login

## Changing User Permission Levels

### Using Python Code

```python
from security.user_account_manager import UserAccountManager

uam = UserAccountManager()

# Change a user's permission level
success, message = uam.change_user_level(
    target_user="john_doe",
    new_level=UserAccountManager.LEVEL_ADMINISTRATOR,  # 1-4
    admin_user="admin",  # Currently logged-in admin
    master_password="your_master_password"
)

if success:
    print(message)
else:
    print(f"Failed: {message}")
```

### Permission Level Constants

```python
UserAccountManager.LEVEL_OPERATOR = 1
UserAccountManager.LEVEL_TECHNICIAN = 2
UserAccountManager.LEVEL_MASTER = 3
UserAccountManager.LEVEL_ADMINISTRATOR = 4
```

### Important Notes

- **Master password is required** to change user levels (security feature)
- Only **Level 4 (Administrator)** users can change other users' levels
- The operation is logged in the user record with timestamp and admin username

## Making an Existing User an Admin

To promote an existing user to administrator:

```python
uam = UserAccountManager()

success, message = uam.change_user_level(
    target_user="existing_user",
    new_level=UserAccountManager.LEVEL_ADMINISTRATOR,
    admin_user="current_admin",  
    master_password="master_password"
)
```

## RFID Card Enrollment

Users can enroll RFID cards for quick authentication:

1. During account creation, choose to enroll a card
2. Present RFID card to reader when prompted
3. Card ID is stored in user record (e.g., "08:5C:D1:4C")
4. User can log in by presenting the card instead of typing credentials

### Managing RFID Cards via Code

```python
# Enroll a card for a user
success, msg = uam.enroll_rfid_card("username", "08:5C:D1:4C")

# Get user's enrolled card ID
card_id = uam.get_rfid_card_id("username")

# Remove card enrollment
success, msg = uam.remove_rfid_card("username")

# Authenticate user by card ID
success, user_info, msg = uam.authenticate_by_rfid("08:5C:D1:4C")
```

## User Database Location

User accounts are stored in encrypted format:

- **File**: `~/.sputter_control/users.enc`
- **Encryption**: AES-256 (Fernet)
- **Key Derivation**: PBKDF2 with 100,000 iterations

Related files:
- `salt.bin` - Random salt for key derivation
- `master.hash` - Hashed master password (for sensitive operations)
- `remembered_username.txt` - Last remembered username for auto-fill

## User Record Structure

Each user has the following fields:

```json
{
  "username": "john_doe",
  "admin_level": 2,
  "created_date": "2025-11-12T10:30:00",
  "created_by": "system",
  "last_login": "2025-11-12T14:20:00",
  "login_count": 5,
  "rfid_card_id": "08:5C:D1:4C",  // Optional
  "rfid_enrolled_date": "2025-11-12T10:35:00"  // Optional
}
```

## Recovery and Reset

### Resetting User Passwords

If a user forgets their password, an administrator can delete and recreate their account:

```python
# Delete user account
success, msg = uam.delete_user("username", admin_user="admin")

# Create new account with same username
success, msg = uam.create_user(
    "username", 
    "new_password", 
    UserAccountManager.LEVEL_OPERATOR,
    "admin"
)
```

### If You Forget the Master Password

1. Delete the `~/.sputter_control/` directory
2. Restart the application
3. You'll be prompted to set up a new master password and create the first admin account

**Warning**: This will delete all existing user accounts and RFID enrollments.

## Security Best Practices

1. **Master password** - Keep secure, do not share
2. **User passwords** - Encourage strong passwords (8+ characters)
3. **RFID cards** - Treat like access badges, don't share
4. **Admin accounts** - Limit number of Level 4 administrators
5. **Audit logs** - Check `last_login` and `login_count` periodically

## Technical Details

### Password Hashing

- **Algorithm**: PBKDF2-HMAC-SHA256
- **Iterations**: 100,000
- **Salt**: 16 bytes random per password

### Master Password Hashing

- **Algorithm**: PBKDF2-HMAC-SHA256
- **Iterations**: 100,000
- **Salt**: 16 bytes stored in `master.hash`
- **Purpose**: Verify permission level changes only (not user login)

### Database Encryption

- **Algorithm**: Fernet (AES-128 in CBC mode)
- **Key derivation**: PBKDF2 with fixed system key + random salt
- **Purpose**: Protects all user accounts and RFID enrollments
