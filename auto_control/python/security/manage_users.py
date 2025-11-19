#!/usr/bin/env python3
"""
User Account Management CLI Tool

Command-line interface for managing user accounts in the Sputter Control System.
Supports changing user permission levels, listing users, and viewing user details.

Usage:
    python manage_users.py list                           # List all users
    python manage_users.py info <username>                # Show user details
    python manage_users.py set-level <username> <level>   # Change user level (requires master password)
    python manage_users.py delete <username>              # Delete user account
    python manage_users.py enroll-card <username> <card_id>  # Enroll RFID card
    python manage_users.py remove-card <username>         # Remove RFID card

Examples:
    python manage_users.py list
    python manage_users.py info john_doe
    python manage_users.py set-level john_doe 3
    python manage_users.py enroll-card john_doe 08:5C:D1:4C
"""

import sys
import argparse
from pathlib import Path
from getpass import getpass

# Add parent directory to path for imports (to access security module)
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from security.user_account_manager import UserAccountManager
except ImportError:
    print("❌ Error: Could not import UserAccountManager")
    print("Make sure you're running this from the security directory")
    sys.exit(1)


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_user_table(users: list):
    """Print users in a formatted table."""
    if not users:
        print("No users found.")
        return
    
    # Table headers
    print(f"\n{'Username':<20} {'Level':<6} {'Type':<15} {'Logins':<8} {'Last Login':<20}")
    print("-" * 75)
    
    # Table rows
    for user in users:
        username = user['username']
        level = f"{user['admin_level']}"
        level_name = user['level_name']
        login_count = user.get('login_count', 0)
        last_login = user.get('last_login')
        
        # Truncate last login datetime for display
        if last_login:
            try:
                last_login = last_login.split('T')[0]  # Just show date
            except:
                last_login = 'Never'
        else:
            last_login = 'Never'
        
        print(f"{username:<20} {level:<6} {level_name:<15} {login_count:<8} {last_login:<20}")


def cmd_list_users(uam: UserAccountManager, args):
    """List all users."""
    print_header("User Accounts")
    
    users = uam.list_users()
    
    if users is None:
        print("❌ Failed to load user database")
        return 1
    
    print_user_table(users)
    print(f"\nTotal users: {len(users)}")
    return 0


def cmd_user_info(uam: UserAccountManager, args):
    """Show detailed information about a user."""
    username = args.username
    
    print_header(f"User Information: {username}")
    
    user = uam.get_user_info(username)
    
    if user is None:
        print(f"❌ User '{username}' not found")
        return 1
    
    # Display user details
    print(f"\nUsername:        {user['username']}")
    print(f"Permission Level: {user['admin_level']} - {user['level_name']}")
    print(f"Created:         {user.get('created_date', 'Unknown')}")
    print(f"Created By:      {user.get('created_by', 'Unknown')}")
    print(f"Last Login:      {user.get('last_login', 'Never')}")
    print(f"Login Count:     {user.get('login_count', 0)}")
    
    # Check for RFID card
    card_id = uam.get_rfid_card_id(username)
    if card_id:
        print(f"RFID Card:       {card_id} ✓")
    else:
        print(f"RFID Card:       Not enrolled")
    
    return 0


def cmd_set_level(uam: UserAccountManager, args):
    """Change a user's permission level."""
    username = args.username
    new_level = args.level
    
    print_header(f"Change User Level: {username}")
    
    # Validate level
    if new_level not in [1, 2, 3, 4]:
        print("❌ Invalid level. Must be 1, 2, 3, or 4")
        print("\nPermission Levels:")
        print("  1 - Operator      (Basic operation)")
        print("  2 - Technician    (Normal + Manual modes)")
        print("  3 - Master        (All modes including Override)")
        print("  4 - Administrator (User management + Level 3)")
        return 1
    
    # Check if user exists
    user = uam.get_user_info(username)
    if user is None:
        print(f"❌ User '{username}' not found")
        return 1
    
    print(f"\nCurrent level: {user['admin_level']} ({user['level_name']})")
    print(f"New level:     {new_level} ({UserAccountManager.LEVEL_NAMES[new_level]})")
    
    # Confirm action
    confirm = input("\nProceed with level change? [y/N]: ").lower().strip()
    if confirm != 'y':
        print("Cancelled.")
        return 0
    
    # Get admin username
    admin_user = input("\nEnter your username (administrator): ").strip()
    if not admin_user:
        print("❌ Administrator username is required")
        return 1
    
    # Get master password
    master_password = getpass("Enter master password: ")
    if not master_password:
        print("❌ Master password is required")
        return 1
    
    # Attempt to change level
    print("\n🔄 Changing user level...")
    success, message = uam.change_user_level(
        target_user=username,
        new_level=new_level,
        admin_user=admin_user,
        master_password=master_password
    )
    
    if success:
        print(f"✅ {message}")
        return 0
    else:
        print(f"❌ {message}")
        return 1


def cmd_delete_user(uam: UserAccountManager, args):
    """Delete a user account."""
    username = args.username
    
    print_header(f"Delete User: {username}")
    
    # Check if user exists
    user = uam.get_user_info(username)
    if user is None:
        print(f"❌ User '{username}' not found")
        return 1
    
    print(f"\nUsername:        {user['username']}")
    print(f"Permission Level: {user['admin_level']} - {user['level_name']}")
    
    # Confirm deletion
    print("\n⚠️  WARNING: This action cannot be undone!")
    confirm = input(f"\nType '{username}' to confirm deletion: ").strip()
    if confirm != username:
        print("Cancelled.")
        return 0
    
    # Get admin username
    admin_user = input("\nEnter your username (administrator): ").strip()
    if not admin_user:
        print("❌ Administrator username is required")
        return 1
    
    # Delete user
    print("\n🔄 Deleting user...")
    success, message = uam.delete_user(
        target_user=username,
        admin_user=admin_user
    )
    
    if success:
        print(f"✅ {message}")
        return 0
    else:
        print(f"❌ {message}")
        return 1


def cmd_enroll_card(uam: UserAccountManager, args):
    """Enroll an RFID card for a user."""
    username = args.username
    card_id = args.card_id
    
    print_header(f"Enroll RFID Card: {username}")
    
    # Check if user exists
    user = uam.get_user_info(username)
    if user is None:
        print(f"❌ User '{username}' not found")
        return 1
    
    print(f"\nUsername:  {user['username']}")
    print(f"Card ID:   {card_id}")
    
    # Check if user already has a card
    existing_card = uam.get_rfid_card_id(username)
    if existing_card:
        print(f"\n⚠️  User already has card: {existing_card}")
        confirm = input("Replace existing card? [y/N]: ").lower().strip()
        if confirm != 'y':
            print("Cancelled.")
            return 0
    
    # Enroll card
    print("\n🔄 Enrolling card...")
    success, message = uam.enroll_rfid_card(username, card_id)
    
    if success:
        print(f"✅ {message}")
        return 0
    else:
        print(f"❌ {message}")
        return 1


def cmd_remove_card(uam: UserAccountManager, args):
    """Remove RFID card enrollment from a user."""
    username = args.username
    
    print_header(f"Remove RFID Card: {username}")
    
    # Check if user exists
    user = uam.get_user_info(username)
    if user is None:
        print(f"❌ User '{username}' not found")
        return 1
    
    # Check if user has a card
    card_id = uam.get_rfid_card_id(username)
    if not card_id:
        print(f"❌ User '{username}' has no RFID card enrolled")
        return 1
    
    print(f"\nUsername:  {user['username']}")
    print(f"Card ID:   {card_id}")
    
    # Confirm removal
    confirm = input("\nRemove RFID card enrollment? [y/N]: ").lower().strip()
    if confirm != 'y':
        print("Cancelled.")
        return 0
    
    # Remove card
    print("\n🔄 Removing card...")
    success, message = uam.remove_rfid_card(username)
    
    if success:
        print(f"✅ {message}")
        return 0
    else:
        print(f"❌ {message}")
        return 1


def main():
    """Main entry point."""
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
    
  Enroll RFID card:
    python manage_users.py enroll-card john_doe 08:5C:D1:4C
    
  Remove RFID card:
    python manage_users.py remove-card john_doe

Permission Levels:
  1 - Operator      (Basic operation only)
  2 - Technician    (Normal and Manual modes)
  3 - Master        (All modes including Override)
  4 - Administrator (User management + Level 3 permissions)
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # List users command
    subparsers.add_parser('list', help='List all users')
    
    # User info command
    info_parser = subparsers.add_parser('info', help='Show user details')
    info_parser.add_argument('username', help='Username to view')
    
    # Set level command
    level_parser = subparsers.add_parser('set-level', help='Change user permission level')
    level_parser.add_argument('username', help='Username to modify')
    level_parser.add_argument('level', type=int, choices=[1, 2, 3, 4],
                            help='New permission level (1-4)')
    
    # Delete user command
    delete_parser = subparsers.add_parser('delete', help='Delete user account')
    delete_parser.add_argument('username', help='Username to delete')
    
    # Enroll card command
    enroll_parser = subparsers.add_parser('enroll-card', help='Enroll RFID card for user')
    enroll_parser.add_argument('username', help='Username to enroll card for')
    enroll_parser.add_argument('card_id', help='RFID card ID (e.g., 08:5C:D1:4C)')
    
    # Remove card command
    remove_parser = subparsers.add_parser('remove-card', help='Remove RFID card from user')
    remove_parser.add_argument('username', help='Username to remove card from')
    
    args = parser.parse_args()
    
    # Show help if no command
    if not args.command:
        parser.print_help()
        return 0
    
    # Initialize user account manager
    try:
        uam = UserAccountManager()
    except Exception as e:
        print(f"❌ Error initializing user account manager: {e}")
        return 1
    
    # Route to appropriate command
    commands = {
        'list': cmd_list_users,
        'info': cmd_user_info,
        'set-level': cmd_set_level,
        'delete': cmd_delete_user,
        'enroll-card': cmd_enroll_card,
        'remove-card': cmd_remove_card,
    }
    
    if args.command in commands:
        return commands[args.command](uam, args)
    else:
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
