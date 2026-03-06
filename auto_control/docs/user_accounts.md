# User Account Management

## Overview

The Sputter Control System uses encrypted, password-based user authentication with role-based access control.

User data is stored at `~/.sputter_control/users.enc`.

## Permission Levels

| Level | Name | Capabilities |
|---|---|---|
| 1 | Operator | Basic operation |
| 2 | Technician | Normal + Manual modes |
| 3 | Master | All modes including Override |
| 4 | Administrator | User management + Level 3 permissions |

## First-Time Setup

On first launch:

1. Set the master password.
2. Create the first administrator account.

The master password is required for sensitive operations such as changing user permission levels.

## Creating Accounts

From the login dialog:

1. Click **Create New Account**.
2. Enter a username.
3. Enter and confirm a password.
4. Account is created as **Level 1 (Operator)** by default.

## Changing User Levels

Use the CLI tool:

```bash
cd auto_control/python/security
python manage_users.py set-level <username> <1-4>
```

Example:

```bash
python manage_users.py set-level john_doe 3
```

## Common CLI Commands

```bash
python manage_users.py list
python manage_users.py info <username>
python manage_users.py set-level <username> <1-4>
python manage_users.py delete <username>
python manage_users.py set-password <username>
```

## Storage and Security

- User database: `~/.sputter_control/users.enc`
- Salt file: `~/.sputter_control/salt.bin`
- Master password hash: `~/.sputter_control/master.hash`

### Password Security

- Algorithm: PBKDF2-HMAC-SHA256
- Iterations: 100,000
- Per-user random salt

### Database Encryption

- Encrypted at rest using Fernet
- Key derived from system key material + local salt

## Recovery Notes

If the master password is lost:

1. Stop the application.
2. Delete `~/.sputter_control/`.
3. Restart app and run first-time setup again.

Warning: this resets all local user accounts.
