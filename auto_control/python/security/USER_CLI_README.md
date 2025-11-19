# User Account Management CLI

Command-line tool for managing user accounts in the Sputter Control System.

## Features

- List all user accounts
- View detailed user information
- Change user permission levels (requires master password)
- Delete user accounts
- Enroll/remove RFID cards for users

## Installation

No installation required! The tool uses the existing Python environment.

## Usage

### Windows (PowerShell)

```powershell
# Navigate to the security directory
cd auto_control\python\security

# Run commands using Python directly
python manage_users.py <command> [arguments]

# Or use the PowerShell wrapper
.\manage_users.ps1 <command> [arguments]
```

### Linux/macOS (Bash)

```bash
# Navigate to the security directory
cd auto_control/python/security

# Make the bash wrapper executable (first time only)
chmod +x manage_users.sh

# Run commands using Python directly
python3 manage_users.py <command> [arguments]

# Or use the bash wrapper
./manage_users.sh <command> [arguments]
```

## Commands

### List All Users

Display a table of all registered users with their permission levels and login statistics.

```bash
python manage_users.py list
```

**Example Output:**
```
============================================================
  User Accounts
============================================================

Username             Level  Type            Logins   Last Login
---------------------------------------------------------------------------
admin                4      Administrator   25       2025-11-18
john_doe             2      Technician      10       2025-11-17
jane_smith           3      Master          5        2025-11-16

Total users: 3
```

### View User Details

Show detailed information about a specific user.

```bash
python manage_users.py info <username>
```

**Example:**
```bash
python manage_users.py info john_doe
```

**Output:**
```
============================================================
  User Information: john_doe
============================================================

Username:        john_doe
Permission Level: 2 - Technician
Created:         2025-11-10T09:30:00
Created By:      admin
Last Login:      2025-11-17T14:22:00
Login Count:     10
RFID Card:       08:5C:D1:4C ✓
```

### Change User Permission Level

Change a user's access level (requires master password).

```bash
python manage_users.py set-level <username> <level>
```

**Permission Levels:**
- **1** - Operator (Basic operation only)
- **2** - Technician (Normal + Manual modes)
- **3** - Master (All modes including Override)
- **4** - Administrator (User management + Level 3 permissions)

**Example:**
```bash
python manage_users.py set-level john_doe 3
```

**Interactive Prompts:**
```
Current level: 2 (Technician)
New level:     3 (Master)

Proceed with level change? [y/N]: y

Enter your username (administrator): admin
Enter master password: ********

✅ User 'john_doe' level changed from 2 to 3.
```

### Delete User Account

Remove a user account from the system.

```bash
python manage_users.py delete <username>
```

**Example:**
```bash
python manage_users.py delete old_user
```

**Interactive Prompts:**
```
⚠️  WARNING: This action cannot be undone!

Type 'old_user' to confirm deletion: old_user

Enter your username (administrator): admin

✅ User 'old_user' deleted successfully.
```

### Enroll RFID Card

Associate an RFID card with a user account.

```bash
python manage_users.py enroll-card <username> <card_id>
```

**Example:**
```bash
python manage_users.py enroll-card john_doe 08:5C:D1:4C
```

**Output:**
```
✅ RFID card '08:5C:D1:4C' enrolled for user 'john_doe'.
```

### Remove RFID Card

Remove RFID card enrollment from a user.

```bash
python manage_users.py remove-card <username>
```

**Example:**
```bash
python manage_users.py remove-card john_doe
```

## Common Workflows

### Promote User to Administrator

```bash
# Check current level
python manage_users.py info john_doe

# Promote to administrator (level 4)
python manage_users.py set-level john_doe 4
```

### Add RFID Card to Existing User

```bash
# Check if user already has card
python manage_users.py info john_doe

# Enroll new card
python manage_users.py enroll-card john_doe 08:5C:D1:4C
```

### Reset User by Deletion and Recreation

```bash
# Delete old account
python manage_users.py delete john_doe

# User creates new account via login dialog
# Then promote if needed:
python manage_users.py set-level john_doe 2
```

## Security Notes

### Master Password

The **master password** is required for:
- Changing user permission levels
- Any operation involving level 2+ user creation

It is **NOT** required for:
- Listing users
- Viewing user info
- Deleting users
- RFID card management

### Best Practices

1. **Keep master password secure** - Only share with trusted administrators
2. **Limit admin accounts** - Not every user needs level 4
3. **Use RFID cards** - Faster and more secure than passwords
4. **Regular audits** - Use `list` command to review user accounts

## Troubleshooting

### "Could not import UserAccountManager"

Make sure you're running the script from the correct directory:
```bash
cd auto_control/python/security
python manage_users.py list
```

### "Failed to load user database"

Check that the user database exists:
- **Location:** `~/.sputter_control/users.enc`
- **Fix:** Run the main application once to create the database

### "Invalid master password"

The master password is set during first-time setup. If you've forgotten it:
1. **Warning:** This will delete all user accounts
2. Delete `~/.sputter_control/` directory
3. Restart main application to recreate database

### Permission Denied (Linux/macOS)

Make the bash wrapper executable:
```bash
chmod +x manage_users.sh
```

## Advanced Usage

### Batch Operations

You can script multiple operations using shell scripting:

**PowerShell:**
```powershell
# Promote multiple users
$users = @("user1", "user2", "user3")
foreach ($user in $users) {
    python manage_users.py set-level $user 2
}
```

**Bash:**
```bash
# List all users and save to file
python3 manage_users.py list > users_report.txt

# Enroll multiple cards
while IFS=',' read -r username card_id; do
    python3 manage_users.py enroll-card "$username" "$card_id"
done < cards.csv
```

### Integration with Other Scripts

The CLI returns exit codes:
- **0** - Success
- **1** - Error

**Example:**
```bash
if python3 manage_users.py info john_doe; then
    echo "User exists"
else
    echo "User not found"
fi
```

## File Locations

- **CLI Script:** `auto_control/python/security/manage_users.py`
- **Bash Wrapper:** `auto_control/python/security/manage_users.sh`
- **PowerShell Wrapper:** `auto_control/python/security/manage_users.ps1`
- **User Database:** `~/.sputter_control/users.enc`

## Related Documentation

- [User Account Management](../docs/user_accounts.md) - Full documentation
- [Security README](../docs/SECURITY_README.md) - Security architecture
- [RFID Integration](../docs/RFID_INTEGRATION.md) - RFID card system

## Quick Reference

```bash
# List users
python manage_users.py list

# View user
python manage_users.py info <username>

# Change level (requires master password)
python manage_users.py set-level <username> <1-4>

# Delete user
python manage_users.py delete <username>

# RFID cards
python manage_users.py enroll-card <username> <card_id>
python manage_users.py remove-card <username>
```
