# User Account Management System Plan

## Project Overview
Implementation plan for a multi-user authentication system with role-based access control (RBAC) for the sputter control GUI. This system will extend the existing encrypted password manager to support multiple user accounts with different permission levels.

## System Requirements

### Core Requirements
1. **Login Window**: Popup on GUI launch with username/password fields, create account, cancel, and enter buttons
2. **Encrypted Storage**: Usernames and passwords stored in encrypted file/database (extension of current password manager)
3. **Three Admin Levels**: User accounts with different permission levels (1, 2, 3)
4. **Master Password Protection**: Creating users with level 2+ requires master password
6. **User Management**: Ability to modify user admin status post-creation (requires master password)

### User Permission Levels
- **Level 1 (Operator)**: Basic operation only, no mode switching capabilities
- **Level 2 (Technician)**: Can access Normal and Manual modes
- **Level 3 (Master)**: Full access including Override mode.
- **Level 4 (Administrator)**: For the system administrator only. Can manage user accounts in addition to level 3 permissions.

## Technical Architecture

### Database Schema
```json
{
  "users": {
    "username": {
      "password_hash": "sha256_hash",
      "admin_level": 1|2|3,
      "created_date": "ISO_timestamp",
      "last_login": "ISO_timestamp",
      "login_count": "number",
      "created_by": "creator_username"
    }
  },
  "system": {
    "master_password_hash": "sha256_hash",
    "version": "1.0",
    "last_backup": "ISO_timestamp",
    "failed_login_attempts": {}
  }
}
```

### File Structure
```
auto_control/
├── python/
│   ├── security/
│   │   ├── password_manager.py (existing)
│   │   └── user_account_manager.py (new - extends password_manager)
│   ├── widgets/
│   │   ├── login_dialog.py (new - initial authentication)
│   │   ├── user_management_dialog.py (new - admin user management)
│   │   ├── mode_dialog.py (update - level-based restrictions)
│   │   └── password_setup_dialog.py (existing)
│   └── app.py (update - integration with user system)
```

### Encryption Strategy
- **Two-tier encryption**: User database encrypted with master password
- **Password hashing**: Individual user passwords hashed with salt before encryption
- **Session management**: Temporary authentication tokens for admin operations
- **File storage**: Encrypted files saved in `~/.sputter_control/users.enc`

## Component Implementation Plan

### Phase 1: Core User Management Backend
**File**: `python/security/user_account_manager.py`

**Key Methods**:
- `create_user(username, password, admin_level, creator, master_password)`
- `authenticate_user(username, password)`
- `change_user_level(target_user, new_level, admin_user, master_password)`
- `delete_user(target_user, admin_user, master_password)`
- `verify_master_password(master_password)`
- `get_user_info(username)`
- `list_users(admin_user, master_password)`

### Phase 2: Login Interface
**File**: `python/widgets/login_dialog.py`

**Features**:
- Username and password input fields
- Login, Create Account, Cancel buttons
- Remember username checkbox
- Password strength indicator for new accounts
- Account creation validation
- Error handling for failed authentication

### Phase 3: Main Application Integration
**File**: `python/app.py` (updates)

**Changes**:
- Show login dialog before main GUI
- Load GUI features based on user admin level
- Hide mode button for Level 1 users
- Implement logout functionality
- Session timeout management

### Phase 4: User Management Interface
**File**: `python/widgets/user_management_dialog.py`

**Features**:
- List all users with current levels
- Create new user interface (master password required for level 2+)
- Modify user admin level (master password required)
- Delete user accounts (master password required)
- View user login history and statistics
- Change user passwords

### Phase 5: Enhanced Mode Control
**File**: `python/widgets/mode_dialog.py` (updates)

**Changes**:
- Accept user level parameter in constructor
- Hide/disable modes based on user permissions:
  - Level 1: No access (mode button hidden in main GUI)
  - Level 2: Normal and Manual modes only
  - Level 3: All modes (Normal, Manual, Override)

## Security Features

### Authentication Security
- **Password strength requirements**: Minimum length, complexity rules
- **Failed login protection**: Account lockout after multiple failed attempts
- **Session timeout**: Auto-logout after period of inactivity
- **Master password verification**: Required for all admin-level operations

### Data Protection
- **Encrypted storage**: All user data encrypted with master password
- **Secure password hashing**: SHA-256 with salt for user passwords
- **No plaintext storage**: Passwords never stored in readable format
- **Backup and recovery**: Secure backup mechanisms for user database

### Audit and Logging
- **Login tracking**: Record all authentication attempts
- **Action logging**: Track user management operations
- **Access control**: Log mode switching and permission changes
- **Security events**: Alert on suspicious activities

## User Experience Flow

### First-Time Setup
1. **No users exist**: Force creation of first administrator account
2. **Master password setup**: Required for initial admin creation
3. **Default accounts**: Optional creation of operator accounts

### Daily Usage Flow
```
App Launch
    ↓
Login Dialog (username/password)
    ↓
Authentication Check
    ↓
Load GUI with Level-Based Features
    ↓
Level 1: Basic controls only
Level 2: + Mode button (Normal/Manual)
Level 3: + Full mode access + User Management
```

### User Management Flow (Admin Only)
```
Admin Login
    ↓
Access User Management (requires master password)
    ↓
Create/Modify/Delete Users
    ↓
Level 2+ Creation requires master password confirmation
    ↓
Changes logged and saved to encrypted database
```

## Implementation Timeline

### Priority 1 (Core Functionality)
- Extend `SecurePasswordManager` to `UserAccountManager`
- Create basic `LoginDialog` with authentication
- Integrate login requirement into main application

### Priority 2 (Access Control)
- Implement level-based GUI feature hiding
- Update mode dialog with permission restrictions
- Add logout functionality

### Priority 3 (User Management)
- Create admin user management interface
- Implement user creation/modification/deletion
- Add session management and timeout

### Priority 4 (Security Hardening)
- Implement failed login protection
- Add comprehensive audit logging
- Create backup and recovery mechanisms

## Configuration Integration

### YAML Configuration Extension
```yaml
security:
  password_dir: "~/.sputter_control"  # Custom password storage location
  session_timeout: 3600  # Session timeout in seconds
  max_login_attempts: 3   # Lockout threshold
  password_requirements:
    min_length: 8
    require_special: true
    require_numbers: true
```

## Testing Strategy

### Unit Testing
- User creation, authentication, and deletion
- Permission level enforcement
- Encryption/decryption operations
- Master password verification

### Integration Testing
- Login dialog workflow
- GUI feature hiding based on user level
- User management operations
- Session management and timeout

### Security Testing
- Password strength enforcement
- Encryption key security
- Failed login protection
- Session hijacking prevention

## Future Enhancements

### Advanced Features
- **Multi-factor authentication**: SMS or email verification
- **Password recovery**: Secure password reset mechanism
- **User groups**: Role-based group assignments
- **Remote authentication**: LDAP/Active Directory integration
- **Certificate-based auth**: Smart card or certificate authentication

### Monitoring and Analytics
- **Usage statistics**: Track user activity patterns
- **Performance monitoring**: System resource usage by user
- **Security dashboards**: Real-time security event monitoring
- **Compliance reporting**: Generate audit reports for regulations

## Dependencies

### Required Packages
- `cryptography` (already included)
- `PyQt5` (already included)
- `hashlib` (built-in Python)
- `datetime` (built-in Python)
- `json` (built-in Python)

### No Additional Dependencies Required
The user account system builds entirely on existing project dependencies and Python standard library components.

---

*This document serves as the complete implementation roadmap for the user account management system. Implementation can proceed in phases while maintaining system security and usability.*
