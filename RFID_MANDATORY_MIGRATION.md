# RFID Mandatory Authentication Migration

## Overview

The system has been migrated from hybrid password/RFID authentication to **RFID-only authentication**. All new user accounts must have an RFID card enrolled. Legacy accounts with passwords remain functional for backward compatibility.

---

## Changes Made

### 1. User Account Manager (`security/user_account_manager.py`)

**Method Signature Changes:**
- `create_user(username, password, admin_level, creator)` → `create_user(username, card_id, admin_level, creator)`
- `authenticate_user(username, password)` → `authenticate_user(username, password=None)` [marked deprecated]

**Database Schema Changes:**
- **Old fields (legacy accounts only):** `password_hash`, `password_salt`
- **New fields (all accounts):** `rfid_card_id`, `rfid_enrolled_date`

**Key Changes:**
- `card_id` parameter is now **required** in `create_user()`
- Validates no duplicate card enrollments
- `authenticate_user()` marked deprecated - only works for legacy password accounts
- New RFID-only accounts cannot use password authentication
- Primary authentication method: `authenticate_by_rfid(card_id)`

---

### 2. Login Dialog (`widgets/login_dialog.py`)

**UI Changes:**
- **Removed:** Username input field, password input field, "Remember username" checkbox, "Login" button
- **Added:** Large "Card Status" group box showing RFID detection status
- **Changed:** Subtitle from "User Authentication Required" → "RFID Card Authentication"

**Workflow Changes:**
- Login now **RFID-only** - present card to authenticate automatically
- Account creation requires **mandatory RFID card enrollment** via `_wait_for_card_enrollment()`
- First admin account also requires RFID card
- Auto-login on card detection (1 second confirmation delay)

**Methods Removed:**
- `_on_login()` - password-based login
- `_save_remembered_username()` - username persistence
- `_load_remembered_username()` - username auto-fill

**Methods Added:**
- `_wait_for_card_enrollment(username, is_first_admin) -> Optional[str]` - Non-blocking enrollment dialog with 30s timeout, returns card_id or None

---

## User Experience Changes

### For New Users
1. Click "Create New Account"
2. Enter username and select admin level
3. **Card enrollment dialog appears automatically**
4. Present RFID card within 30 seconds
5. Account created with card association
6. **Cannot login without card**

### For Existing Users (Legacy)
- Users with passwords can still authenticate via `authenticate_user()` (backward compatibility)
- **Recommended:** Migrate to RFID by enrolling a card via admin tools

### For Administrators
- First-time setup still requires master password (for managing elevated permissions)
- First admin account **must have RFID card** enrolled during setup
- Master password remains for creating/managing level 2+ users

---

## Auto-Login Flow

When RFID card detected:
1. System calls `user_manager.authenticate_by_rfid(card_id)`
2. If card registered → auto-login with 1s confirmation
3. If card not registered → status message shown, wait for account creation

---

## Enrollment Dialog Features

**Non-blocking design:**
- Uses QTimer to check for card detection every second
- Shows progress bar with 30-second countdown
- Auto-closes when card detected
- Returns card_id string on success, None on cancel/timeout

**User feedback:**
- Clear instructions: "Please present your RFID card to the reader now..."
- Live status updates: "Waiting for card... (X s remaining)"
- Cancel button for abort

---

## Migration Path

### For Development/Testing
- Delete existing user database to start fresh
- First admin will be prompted to enroll RFID card

### For Production Systems
**⚠️ Migration utility NOT YET IMPLEMENTED**

Planned migration process:
1. Admin tool to enumerate existing users
2. Prompt admin to enroll RFID cards for each user
3. Preserve user data (admin_level, login_count, preferences)
4. Optional: Disable password authentication after migration

---

## Security Considerations

### Strengths
✅ **Eliminates password complexity** - no weak passwords, no password resets
✅ **Physical token required** - cannot remote hack without card
✅ **Fast authentication** - single card scan vs. typing credentials
✅ **Audit trail** - RFID enrollment timestamps stored

### Limitations
⚠️ **Card loss/theft** - Physical security becomes critical
⚠️ **RFID reader failure** - System lockout if reader unavailable
⚠️ **Legacy accounts** - Existing password accounts still vulnerable until migrated

### Recommendations
1. **Implement card deactivation** - Admin tool to disable lost/stolen cards
2. **RFID reader redundancy** - Backup reader for critical systems
3. **Emergency admin access** - Fallback mechanism if RFID system fails
4. **Migration enforcement** - Force password users to enroll cards within grace period

---

## Configuration

### RFID Reader Settings (`rfid/config.py`)
- Baud rate: 115200
- Port caching: `~/.sputter_control/rfid_port_cache.json`
- Card debounce: 500ms (prevents duplicate reads)

### Safety Integration
- RFID authentication integrated with SafetyController
- User access level determines available operations (Operator/Technician/Master/Administrator)

---

## Testing Checklist

- [x] New account creation requires card enrollment
- [x] First admin account requires card enrollment
- [x] Enrollment dialog auto-closes on card detection
- [x] Enrollment dialog timeout (30s) works correctly
- [x] Auto-login works when registered card detected
- [x] Status messages shown for unregistered cards
- [ ] Legacy password authentication still functional
- [ ] Master password still required for elevated user management
- [ ] Card duplication prevented (error if card already enrolled)
- [ ] RFID reader connection failure handled gracefully

---

## Files Modified

1. **`security/user_account_manager.py`** (80 lines modified)
   - `create_user()` signature change
   - `authenticate_user()` deprecation
   - Database schema update

2. **`widgets/login_dialog.py`** (400 lines modified)
   - UI simplification (removed password fields)
   - `_wait_for_card_enrollment()` implementation
   - `_on_create_account()` and `_create_first_admin()` updated
   - Obsolete methods removed

---

## Known Issues

1. **Migration Utility Missing** - No tool yet for migrating existing password users to RFID
2. **Emergency Access** - No fallback if RFID reader completely fails
3. **Card Management** - No admin UI for deactivating/reassigning cards

---

## Future Enhancements

### Phase 2: Card Management
- Admin tool to view all enrolled cards
- Deactivate lost/stolen cards
- Reassign cards between users
- Audit log of card usage

### Phase 3: Migration Utility
- Script to migrate legacy accounts
- Batch card enrollment process
- Grace period enforcement

### Phase 4: Redundancy
- Support multiple RFID readers
- Fallback authentication mechanism
- Emergency admin override

---

## Rollback Procedure

If RFID-only authentication proves problematic:

1. **Revert `create_user()` signature** - Change back to `password` parameter
2. **Restore password UI** - Re-add username/password fields to login dialog
3. **Re-enable password login** - Uncomment `_on_login()` method
4. **Mark RFID as optional** - Change enrollment from mandatory to optional

**Backup files NOT created** - use git history to revert changes.

---

## Support Contacts

For issues with RFID authentication:
1. Check RFID reader connection (USB serial port)
2. Verify port caching in `~/.sputter_control/rfid_port_cache.json`
3. Test reader with `rfid_receiver.py` standalone script
4. Check logs for authentication errors

For emergency access:
1. Use existing password account (if available)
2. Delete user database to force first-time setup (loses all user data)
3. Contact system administrator for manual database edit

---

## Change Log

**2025-01-XX** - Initial RFID-only migration
- Removed password authentication from new accounts
- Made RFID card enrollment mandatory
- Updated login dialog UI for card-first workflow
- Preserved backward compatibility for legacy accounts
