# User Account Management CLI

Command-line utility for local user administration.

## Supported Commands

- `list` — list all users
- `info <username>` — show one user
- `set-level <username> <1-4>` — change role (requires master password)
- `delete <username>` — remove user
- `set-password <username>` — set or change password

## Usage

### Linux/macOS

```bash
cd auto_control/python/security
python3 manage_users.py <command> [arguments]
# or
./manage_users.sh <command> [arguments]
```

### Windows PowerShell

```powershell
cd auto_control\python\security
python manage_users.py <command> [arguments]
# or
.\manage_users.ps1 <command> [arguments]
```

## Examples

```bash
python manage_users.py list
python manage_users.py info admin
python manage_users.py set-level alice 2
python manage_users.py set-password alice
python manage_users.py delete old_user
```

## Permission Levels

- `1` Operator
- `2` Technician
- `3` Master
- `4` Administrator

## Notes

- `set-level` requires the master password.
- Exit code `0` indicates success; `1` indicates error.
- User data is stored in `~/.sputter_control/users.enc`.

## Troubleshooting

### Import errors

Run from the security directory:

```bash
cd auto_control/python/security
python manage_users.py list
```

### Database issues

If user DB is missing/corrupt, run the main GUI once to recreate initial structure.

### Lost master password

Reset local security data:

1. Delete `~/.sputter_control/`
2. Start GUI and complete first-time setup

Warning: this clears local users.
