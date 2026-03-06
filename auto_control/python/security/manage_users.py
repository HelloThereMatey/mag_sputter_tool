#!/usr/bin/env python3
"""
User Account Management CLI Tool

Command-line interface for managing user accounts in the Sputter Control System.
Supports changing user permission levels, listing users, viewing user details,
and setting user passwords.

Usage:
    python manage_users.py list                           # List all users
    python manage_users.py info <username>                # Show user details
    python manage_users.py set-level <username> <level>   # Change user level (requires master password)
    python manage_users.py delete <username>              # Delete user account
    python manage_users.py set-password <username>        # Set/change user password
"""

import sys
import argparse
from pathlib import Path
from getpass import getpass
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from security.user_account_manager import UserAccountManager
except ImportError:
    print("❌ Error: Could not import UserAccountManager")
    print("Make sure you're running this from the security directory")
    sys.exit(1)


def print_header(text: str):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_user_table(users: list):
    if not users:
        print("No users found.")
        return

    print(f"\n{'Username':<20} {'Level':<6} {'Type':<15} {'Logins':<8} {'Last Login':<20}")
    print("-" * 75)

    for user in users:
        username = user['username']
        level = f"{user['admin_level']}"
        level_name = user['level_name']
        login_count = user.get('login_count', 0)
        last_login = user.get('last_login')

        if last_login:
            try:
                last_login = last_login.split('T')[0]
            except Exception:
                last_login = 'Never'
        else:
            last_login = 'Never'

        print(f"{username:<20} {level:<6} {level_name:<15} {login_count:<8} {last_login:<20}")


def cmd_list_users(uam: UserAccountManager, args):
    print_header("User Accounts")
    users = uam.list_users()

    if users is None:
        print("❌ Failed to load user database")
        return 1

    print_user_table(users)
    print(f"\nTotal users: {len(users)}")
    return 0


def cmd_user_info(uam: UserAccountManager, args):
    username = args.username

    print_header(f"User Information: {username}")

    user = uam.get_user_info(username)

    if user is None:
        print(f"❌ User '{username}' not found")
        return 1

    print(f"\nUsername:         {user['username']}")
    print(f"Permission Level: {user['admin_level']} - {user['level_name']}")
    print(f"Created:          {user.get('created_date', 'Unknown')}")
    print(f"Created By:       {user.get('created_by', 'Unknown')}")
    print(f"Last Login:       {user.get('last_login', 'Never')}")
    print(f"Login Count:      {user.get('login_count', 0)}")

    return 0


def cmd_set_level(uam: UserAccountManager, args):
    username = args.username
    new_level = args.level

    print_header(f"Change User Level: {username}")

    if new_level not in [1, 2, 3, 4]:
        print("❌ Invalid level. Must be 1, 2, 3, or 4")
        return 1

    user = uam.get_user_info(username)
    if user is None:
        print(f"❌ User '{username}' not found")
        return 1

    print(f"\nCurrent level: {user['admin_level']} ({user['level_name']})")
    print(f"New level:     {new_level} ({UserAccountManager.LEVEL_NAMES[new_level]})")

    confirm = input("\nProceed with level change? [y/N]: ").lower().strip()
    if confirm != 'y':
        print("Cancelled.")
        return 0

    admin_user = input("\nEnter your username (administrator): ").strip()
    if not admin_user:
        print("❌ Administrator username is required")
        return 1

    master_password = getpass("Enter master password: ")
    if not master_password:
        print("❌ Master password is required")
        return 1

    print("\n🔄 Changing user level...")
    success, message = uam.change_user_level(
        target_user=username,
        new_level=new_level,
        admin_user=admin_user,
        master_password=master_password,
    )

    if success:
        print(f"✅ {message}")
        return 0

    print(f"❌ {message}")
    return 1


def cmd_delete_user(uam: UserAccountManager, args):
    username = args.username

    print_header(f"Delete User: {username}")

    user = uam.get_user_info(username)
    if user is None:
        print(f"❌ User '{username}' not found")
        return 1

    print(f"\nUsername:         {user['username']}")
    print(f"Permission Level: {user['admin_level']} - {user['level_name']}")

    print("\n⚠️  WARNING: This action cannot be undone!")
    confirm = input(f"\nType '{username}' to confirm deletion: ").strip()
    if confirm != username:
        print("Cancelled.")
        return 0

    admin_user = input("\nEnter your username (administrator): ").strip()
    if not admin_user:
        print("❌ Administrator username is required")
        return 1

    print("\n🔄 Deleting user...")
    success, message = uam.delete_user(target_user=username, admin_user=admin_user)

    if success:
        print(f"✅ {message}")
        return 0

    print(f"❌ {message}")
    return 1


def cmd_set_password(uam: UserAccountManager, args):
    username = args.username

    print_header(f"Set Password: {username}")

    user = uam.get_user_info(username)
    if user is None:
        print(f"❌ User '{username}' not found")
        return 1

    print(f"\nUsername:  {user['username']}")
    print(f"Level:     {user['level_name']}")
    print("\nNote: Password can be empty string for no password")

    import getpass

    try:
        new_password = getpass.getpass("\nEnter new password (or press Enter for empty): ")
        confirm_password = getpass.getpass("Confirm password: ")

        if new_password != confirm_password:
            print("\n❌ Passwords do not match")
            return 1

        users = uam._load_users()
        if users is None:
            print("❌ Failed to load user database")
            return 1

        username_lower = username.lower()
        if username_lower not in users:
            print(f"❌ User '{username}' not found")
            return 1

        password_hash, salt = uam._hash_password(new_password)

        users[username_lower]['password_hash'] = password_hash
        users[username_lower]['password_salt'] = salt.hex()
        users[username_lower]['password_changed'] = datetime.now().isoformat()

        if uam._save_users(users):
            if new_password:
                print("\n✅ Password set successfully")
            else:
                print("\n✅ Password cleared (empty password set)")
            return 0

        print("\n❌ Failed to save user database")
        return 1

    except KeyboardInterrupt:
        print("\n\nCancelled.")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="User Account Management CLI for Sputter Control System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  List all users:
    python manage_users.py list

  View user details:
    python manage_users.py info john_doe

  Change user level to Master (3):
    python manage_users.py set-level john_doe 3

  Delete a user:
    python manage_users.py delete john_doe

Permission Levels:
  1 - Operator      (Basic operation only)
  2 - Technician    (Normal and Manual modes)
  3 - Master        (All modes including Override)
  4 - Administrator (User management + Level 3 permissions)
        """,
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    subparsers.add_parser('list', help='List all users')

    info_parser = subparsers.add_parser('info', help='Show user details')
    info_parser.add_argument('username', help='Username to view')

    level_parser = subparsers.add_parser('set-level', help='Change user permission level')
    level_parser.add_argument('username', help='Username to modify')
    level_parser.add_argument('level', type=int, choices=[1, 2, 3, 4], help='New permission level (1-4)')

    delete_parser = subparsers.add_parser('delete', help='Delete user account')
    delete_parser.add_argument('username', help='Username to delete')

    password_parser = subparsers.add_parser('set-password', help='Set or change user password')
    password_parser.add_argument('username', help='Username to set password for')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    try:
        uam = UserAccountManager()
    except Exception as e:
        print(f"❌ Error initializing user account manager: {e}")
        return 1

    commands = {
        'list': cmd_list_users,
        'info': cmd_user_info,
        'set-level': cmd_set_level,
        'delete': cmd_delete_user,
        'set-password': cmd_set_password,
    }

    if args.command in commands:
        return commands[args.command](uam, args)

    print(f"❌ Unknown command: {args.command}")
    parser.print_help()
    return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
