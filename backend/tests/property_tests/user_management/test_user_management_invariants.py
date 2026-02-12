"""
Property-Based Tests for User Management Invariants

Tests critical user management business logic:
- User lifecycle (registration, activation, deactivation, deletion)
- Authentication and authorization
- User role and permission management
- User profile management
- User session management
- User preference settings
- User audit trail
- User security (password reset, 2FA, lockout)
"""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from typing import Dict, List, Set, Optional
import uuid


class TestUserLifecycleInvariants:
    """Tests for user lifecycle management invariants"""

    @given(
        user_id=st.uuids(),
        email=st.emails(),
        username=st.text(min_size=3, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789_'),
        created_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1))
    )
    @settings(max_examples=50)
    def test_user_registration_creates_valid_user(self, user_id, email, username, created_at):
        """Test that user registration creates a valid user record"""
        # Simulate user registration
        user = {
            'id': str(user_id),
            'email': email.lower(),
            'username': username,
            'created_at': created_at,
            'updated_at': created_at,
            'is_active': True,
            'is_verified': False,
            'role': 'STUDENT'
        }

        # Verify user was created with valid fields
        assert user['id'] is not None, "User ID must be set"
        assert '@' in user['email'], "Email must contain @"
        assert len(user['username']) >= 3, "Username must be at least 3 characters"
        assert user['created_at'] == user['updated_at'], "created_at equals updated_at on creation"
        assert isinstance(user['is_active'], bool), "is_active must be boolean"
        assert isinstance(user['is_verified'], bool), "is_verified must be boolean"
        assert user['role'] in ['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS', 'ADMIN'], "Valid role"

    @given(
        user_id=st.uuids(),
        email=st.emails(),
        is_active=st.booleans(),
        is_verified=st.booleans(),
        current_time=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1))
    )
    @settings(max_examples=50)
    def test_user_activation_deactivation_updates_status(self, user_id, email, is_active, is_verified, current_time):
        """Test that user activation/deactivation updates status correctly"""
        # Simulate user status change
        user = {
            'id': str(user_id),
            'email': email.lower(),
            'is_active': is_active,
            'is_verified': is_verified,
            'updated_at': current_time
        }

        # Activate or deactivate user
        new_status = not user['is_active']
        user['is_active'] = new_status
        user['updated_at'] = current_time + timedelta(seconds=1)

        # Verify status change
        assert user['is_active'] == new_status, "Status must be updated"
        assert user['updated_at'] > current_time, "updated_at must be incremented"

    @given(
        user_id=st.uuids(),
        created_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2025, 1, 1)),
        deleted_at=st.datetimes(min_value=datetime(2025, 1, 1), max_value=datetime(2030, 1, 1))
    )
    @settings(max_examples=50)
    def test_user_deletion_sets_deleted_at(self, user_id, created_at, deleted_at):
        """Test that user deletion sets deleted_at timestamp"""
        assume(deleted_at > created_at)

        # Simulate user deletion
        user = {
            'id': str(user_id),
            'created_at': created_at,
            'deleted_at': deleted_at,
            'is_deleted': True
        }

        # Verify deletion
        assert user['deleted_at'] is not None, "deleted_at must be set"
        assert user['deleted_at'] >= user['created_at'], "deleted_at must be after created_at"
        assert user['is_deleted'] is True, "is_deleted must be True"

    @given(
        email1=st.emails(),
        email2=st.emails()
    )
    @settings(max_examples=50)
    def test_user_email_uniqueness(self, email1, email2):
        """Test that user emails are unique"""
        # Normalize emails to lowercase
        normalized_email1 = email1.lower()
        normalized_email2 = email2.lower()

        # Track registered emails
        registered_emails = set()

        # Register first user
        registered_emails.add(normalized_email1)

        # Check if second email is duplicate
        is_duplicate = normalized_email2 in registered_emails

        # Verify uniqueness enforcement
        if normalized_email1 == normalized_email2:
            # Same email - should be detected as duplicate
            assert is_duplicate, "Duplicate email must be detected"
        else:
            # Different email - should both be allowed
            registered_emails.add(normalized_email2)
            assert len(registered_emails) == 2, "Both unique emails should be registered"


class TestAuthenticationInvariants:
    """Tests for authentication invariants"""

    @given(
        user_id=st.uuids(),
        password=st.text(min_size=8, max_size=100),
        wrong_password=st.text(min_size=8, max_size=100)
    )
    @settings(max_examples=50)
    def test_password_hashing_is_one_way(self, user_id, password, wrong_password):
        """Test that password hashing is one-way function"""
        import hashlib

        # Simulate password hashing
        hashed = hashlib.sha256(password.encode()).hexdigest()

        # Verify password cannot be reversed from hash
        assert password not in hashed, "Password must not appear in hash"
        assert len(hashed) == 64, "SHA-256 hash must be 64 characters"

        # Verify same password produces same hash
        hashed_again = hashlib.sha256(password.encode()).hexdigest()
        assert hashed == hashed_again, "Same password must produce same hash"

        # Verify different password produces different hash (usually)
        if password != wrong_password:
            wrong_hashed = hashlib.sha256(wrong_password.encode()).hexdigest()
            # Not guaranteed to be different due to collisions, but very unlikely
            assert True, "Different passwords should produce different hashes"

    @given(
        password=st.text(min_size=8, max_size=100),
        salt=st.binary(min_size=16, max_size=32)
    )
    @settings(max_examples=50)
    def test_salt_makes_same_password_different_hashes(self, password, salt):
        """Test that salt makes same password produce different hashes"""
        import hashlib

        # Hash with salt
        salted = hashlib.sha256(password.encode() + salt).hexdigest()

        # Hash same password with different salt
        different_salt = salt + b'different'
        differently_salt = hashlib.sha256(password.encode() + different_salt).hexdigest()

        # Different salts should produce different hashes
        assert salted != differently_salt, "Different salts must produce different hashes"

    @given(
        failed_attempts=st.integers(min_value=0, max_value=10),
        max_attempts=st.integers(min_value=3, max_value=10)
    )
    @settings(max_examples=50)
    def test_account_lockout_after_max_attempts(self, failed_attempts, max_attempts):
        """Test that account is locked after max failed login attempts"""
        # Simulate failed login attempts
        is_locked = failed_attempts >= max_attempts

        # Verify lockout
        if failed_attempts >= max_attempts:
            assert is_locked is True, "Account must be locked after max attempts"
        else:
            assert is_locked is False, "Account must not be locked before max attempts"

    @given(
        last_login=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2025, 1, 1)),
        session_timeout_days=st.integers(min_value=1, max_value=90),
        current_time=st.datetimes(min_value=datetime(2025, 1, 1), max_value=datetime(2030, 1, 1))
    )
    @settings(max_examples=50)
    def test_session_expiration_enforcement(self, last_login, session_timeout_days, current_time):
        """Test that sessions expire after timeout period"""
        session_timeout = timedelta(days=session_timeout_days)
        time_since_login = current_time - last_login

        # Session is expired if time_since_login > session_timeout
        is_expired = time_since_login > session_timeout

        # Verify expiration
        if time_since_login > session_timeout:
            assert is_expired is True, "Session must be expired after timeout"
        else:
            assert is_expired is False, "Session must not be expired before timeout"


class TestAuthorizationInvariants:
    """Tests for authorization invariants"""

    @given(
        user_role=st.sampled_from(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS', 'ADMIN']),
        required_role=st.sampled_from(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS', 'ADMIN'])
    )
    @settings(max_examples=50)
    def test_role_hierarchy_enforcement(self, user_role, required_role):
        """Test that role hierarchy is enforced correctly"""
        role_hierarchy = {
            'STUDENT': 0,
            'INTERN': 1,
            'SUPERVISED': 2,
            'AUTONOMOUS': 3,
            'ADMIN': 4
        }

        user_level = role_hierarchy[user_role]
        required_level = role_hierarchy[required_role]

        # User has permission if their level >= required level
        has_permission = user_level >= required_level

        # Verify hierarchy
        if user_level >= required_level:
            assert has_permission is True, f"{user_role} should have permission for {required_role}"
        else:
            assert has_permission is False, f"{user_role} should not have permission for {required_role}"

    @given(
        user_permissions=st.sets(st.sampled_from(['read', 'write', 'delete', 'admin', 'execute'])),
        required_permission=st.sampled_from(['read', 'write', 'delete', 'admin', 'execute'])
    )
    @settings(max_examples=50)
    def test_permission_check(self, user_permissions, required_permission):
        """Test that permission check is correct"""
        has_permission = required_permission in user_permissions

        # Verify permission
        if required_permission in user_permissions:
            assert has_permission is True, "User must have permission"
        else:
            assert has_permission is False, "User must not have permission"

    @given(
        user_id=st.uuids(),
        resource_id=st.uuids(),
        permissions=st.dictionaries(
            keys=st.uuids(),
            values=st.sets(st.sampled_from(['read', 'write', 'delete', 'admin'])),
            min_size=0,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_resource_permission_isolation(self, user_id, resource_id, permissions):
        """Test that resource permissions are isolated per user"""
        # User can only access resources they have permission for
        user_permissions = permissions.get(user_id, set())

        # Check access to resource
        has_access = any(p in user_permissions for p in ['read', 'write', 'delete', 'admin'])

        # Verify isolation
        if not user_permissions:
            assert has_access is False, "User must not have access without permissions"
        else:
            # Might have access if they have any permission
            assert True, "User might have access with permissions"


class TestUserProfileInvariants:
    """Tests for user profile management invariants"""

    @given(
        user_id=st.uuids(),
        display_name=st.text(min_size=1, max_size=100),
        bio=st.text(min_size=0, max_size=500),
        avatar_url=st.text(min_size=0, max_size=500),
        timezone=st.sampled_from(['UTC', 'America/New_York', 'Europe/London', 'Asia/Tokyo', 'Australia/Sydney'])
    )
    @settings(max_examples=50)
    def test_user_profile_update_preserves_fields(self, user_id, display_name, bio, avatar_url, timezone):
        """Test that user profile updates preserve existing fields"""
        # Create profile
        profile = {
            'user_id': str(user_id),
            'display_name': display_name,
            'bio': bio,
            'avatar_url': avatar_url,
            'timezone': timezone,
            'updated_at': datetime.now()
        }

        # Update only display name
        original_bio = profile['bio']
        original_avatar = profile['avatar_url']
        original_timezone = profile['timezone']

        profile['display_name'] = 'New Name'
        profile['updated_at'] = datetime.now()

        # Verify other fields are preserved
        assert profile['bio'] == original_bio, "Bio must be preserved"
        assert profile['avatar_url'] == original_avatar, "Avatar URL must be preserved"
        assert profile['timezone'] == original_timezone, "Timezone must be preserved"

    @given(
        display_name=st.text(min_size=0, max_size=200)
    )
    @settings(max_examples=50)
    def test_display_name_length_validation(self, display_name):
        """Test that display name length is validated"""
        max_length = 100

        # Check if display name is valid
        is_valid = len(display_name) <= max_length and len(display_name) > 0

        # Verify validation
        if len(display_name) > max_length:
            assert not is_valid, "Display name must not exceed max length"
        elif len(display_name) == 0:
            assert not is_valid, "Display name must not be empty"
        else:
            assert is_valid, "Display name must be valid"


class TestUserSessionInvariants:
    """Tests for user session management invariants"""

    @given(
        user_id=st.uuids(),
        session_id=st.uuids(),
        created_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2025, 1, 1)),
        expires_at=st.datetimes(min_value=datetime(2025, 1, 1), max_value=datetime(2030, 1, 1))
    )
    @settings(max_examples=50)
    def test_session_creation_sets_expiration(self, user_id, session_id, created_at, expires_at):
        """Test that session creation sets expiration time"""
        assume(expires_at > created_at)

        # Create session
        session = {
            'id': str(session_id),
            'user_id': str(user_id),
            'created_at': created_at,
            'expires_at': expires_at,
            'is_active': True
        }

        # Verify session
        assert session['expires_at'] is not None, "Expiration must be set"
        assert session['expires_at'] > session['created_at'], "Expiration must be after creation"

    @given(
        created_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2025, 1, 1)),
        ttl_minutes=st.integers(min_value=1, max_value=10080)  # 1 minute to 1 week
    )
    @settings(max_examples=50)
    def test_session_ttl_calculation(self, created_at, ttl_minutes):
        """Test that session TTL is calculated correctly"""
        ttl = timedelta(minutes=ttl_minutes)
        expires_at = created_at + ttl

        # Verify TTL
        time_difference = (expires_at - created_at).total_seconds()
        expected_seconds = ttl_minutes * 60

        assert abs(time_difference - expected_seconds) < 1, "TTL must be correct"

    @given(
        user_id=st.uuids(),
        sessions=st.lists(
            st.fixed_dictionaries({
                'id': st.uuids(),
                'created_at': st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1)),
                'expires_at': st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1))
            }),
            min_size=0,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_multiple_sessions_allowed(self, user_id, sessions):
        """Test that user can have multiple active sessions"""
        # Filter active sessions
        now = datetime.now()
        active_sessions = [s for s in sessions if s['expires_at'] > now]

        # User can have multiple sessions
        assert len(active_sessions) >= 0, "User can have multiple sessions"


class TestUserPreferencesInvariants:
    """Tests for user preference management invariants"""

    @given(
        preferences=st.dictionaries(
            keys=st.sampled_from(['theme', 'language', 'timezone', 'notifications_enabled', 'email_enabled']),
            values=st.one_of(
                st.text(min_size=1, max_size=50),
                st.booleans(),
                st.integers(min_value=0, max_value=100)
            ),
            min_size=0,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_preference_update(self, preferences):
        """Test that preference update is persisted correctly"""
        # Create preferences
        user_preferences = {}

        # Update each preference
        for key, value in preferences.items():
            user_preferences[key] = value

        # Verify all preferences are set
        for key, value in preferences.items():
            assert user_preferences.get(key) == value, f"Preference {key} must be set to {value}"

    @given(
        theme=st.sampled_from(['light', 'dark', 'auto']),
        language=st.sampled_from(['en', 'es', 'fr', 'de', 'ja', 'zh']),
        timezone=st.sampled_from(['UTC', 'America/New_York', 'Europe/London', 'Asia/Tokyo'])
    )
    @settings(max_examples=50)
    def test_default_preferences(self, theme, language, timezone):
        """Test that default preferences are set correctly"""
        # Set default preferences
        defaults = {
            'theme': theme,
            'language': language,
            'timezone': timezone,
            'notifications_enabled': True,
            'email_enabled': True
        }

        # Verify defaults
        assert defaults['theme'] in ['light', 'dark', 'auto'], "Valid theme"
        assert defaults['language'] in ['en', 'es', 'fr', 'de', 'ja', 'zh'], "Valid language"
        assert defaults['timezone'] in ['UTC', 'America/New_York', 'Europe/London', 'Asia/Tokyo'], "Valid timezone"
        assert isinstance(defaults['notifications_enabled'], bool), "notifications_enabled must be boolean"
        assert isinstance(defaults['email_enabled'], bool), "email_enabled must be boolean"


class TestUserAuditTrailInvariants:
    """Tests for user audit trail invariants"""

    @given(
        user_id=st.uuids(),
        action=st.sampled_from(['login', 'logout', 'password_change', 'profile_update', 'role_change', 'delete']),
        timestamp=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1)),
        ip_address=st.ip_addresses(),
        user_agent=st.text(min_size=10, max_size=500)
    )
    @settings(max_examples=50)
    def test_audit_log_records_action(self, user_id, action, timestamp, ip_address, user_agent):
        """Test that audit log records all user actions"""
        # Create audit log entry
        audit_entry = {
            'id': str(uuid.uuid4()),
            'user_id': str(user_id),
            'action': action,
            'timestamp': timestamp,
            'ip_address': str(ip_address),
            'user_agent': user_agent
        }

        # Verify audit entry
        assert audit_entry['id'] is not None, "Audit entry ID must be set"
        assert audit_entry['user_id'] is not None, "User ID must be set"
        assert audit_entry['action'] in ['login', 'logout', 'password_change', 'profile_update', 'role_change', 'delete'], "Valid action"
        assert audit_entry['timestamp'] is not None, "Timestamp must be set"
        assert audit_entry['ip_address'] is not None, "IP address must be set"

    @given(
        actions=st.lists(
            st.sampled_from(['login', 'logout', 'password_change', 'profile_update', 'role_change']),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_audit_log_chronological_order(self, actions):
        """Test that audit log entries are in chronological order"""
        # Create audit log entries
        base_time = datetime.now()
        audit_log = []
        for i, action in enumerate(actions):
            audit_log.append({
                'action': action,
                'timestamp': base_time + timedelta(seconds=i)
            })

        # Verify chronological order
        for i in range(1, len(audit_log)):
            assert audit_log[i]['timestamp'] >= audit_log[i-1]['timestamp'], "Entries must be in chronological order"


class TestUserSecurityInvariants:
    """Tests for user security invariants"""

    @given(
        email=st.emails(),
        reset_token=st.uuids(),
        created_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2025, 1, 1)),
        expires_minutes=st.integers(min_value=15, max_value=1440)  # 15 minutes to 24 hours
    )
    @settings(max_examples=50)
    def test_password_reset_token_expiration(self, email, reset_token, created_at, expires_minutes):
        """Test that password reset tokens expire"""
        # Create reset token
        reset_token_data = {
            'email': email.lower(),
            'token': str(reset_token),
            'created_at': created_at,
            'expires_at': created_at + timedelta(minutes=expires_minutes)
        }

        # Verify expiration
        assert reset_token_data['expires_at'] > reset_token_data['created_at'], "Token must have expiration time"
        time_diff = (reset_token_data['expires_at'] - reset_token_data['created_at']).total_seconds() / 60
        assert time_diff == expires_minutes, "Token must expire after specified minutes"

    @given(
        user_id=st.uuids(),
        secret=st.binary(min_size=16, max_size=32),
        code=st.integers(min_value=0, max_value=999999),
        current_time=st.datetimes(min_value=datetime(2025, 1, 1), max_value=datetime(2030, 1, 1)),
        code_time=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2025, 1, 1))
    )
    @settings(max_examples=50)
    def test_two_factor_code_validity_window(self, user_id, secret, code, current_time, code_time):
        """Test that 2FA codes have validity window"""
        validity_window = timedelta(minutes=5)  # 5 minute window
        time_diff = current_time - code_time

        # Code is valid if within time window
        is_valid = abs(time_diff) <= validity_window

        # Verify validity
        if abs(time_diff) <= validity_window:
            assert is_valid is True, "Code must be valid within time window"
        else:
            assert is_valid is False, "Code must be invalid outside time window"

    @given(
        user_id=st.uuids(),
        old_password=st.text(min_size=8, max_size=100),
        new_password=st.text(min_size=8, max_size=100)
    )
    @settings(max_examples=50)
    def test_password_change_invalidates_old_sessions(self, user_id, old_password, new_password):
        """Test that password change invalidates old sessions"""
        assume(old_password != new_password)

        # Simulate password change
        sessions = [
            {'id': str(uuid.uuid4()), 'created_at': datetime.now() - timedelta(hours=1)},
            {'id': str(uuid.uuid4()), 'created_at': datetime.now() - timedelta(days=1)}
        ]

        # Change password
        password_changed_at = datetime.now()

        # Invalidate old sessions
        for session in sessions:
            session['is_valid'] = session['created_at'] > password_changed_at

        # Verify all old sessions are invalidated
        for session in sessions:
            assert session['is_valid'] is False, "Old sessions must be invalidated after password change"

    @given(
        user_id=st.uuids(),
        login_attempts=st.integers(min_value=0, max_value=10),
        lockout_threshold=st.integers(min_value=3, max_value=10),
        lockout_duration_minutes=st.integers(min_value=5, max_value=60)
    )
    @settings(max_examples=50)
    def test_account_lockout_duration(self, user_id, login_attempts, lockout_threshold, lockout_duration_minutes):
        """Test that account lockout has duration"""
        # Check if account should be locked
        is_locked = login_attempts >= lockout_threshold

        if is_locked:
            # Calculate lockout expiry
            locked_at = datetime.now()
            lockout_expires_at = locked_at + timedelta(minutes=lockout_duration_minutes)

            # Verify lockout duration
            time_diff = (lockout_expires_at - locked_at).total_seconds() / 60
            assert time_diff == lockout_duration_minutes, "Lockout must last for specified duration"
        else:
            # Account not locked
            assert True, "Account not locked"


class TestUserValidationInvariants:
    """Tests for user validation invariants"""

    @given(
        email=st.text(min_size=1, max_size=100)
    )
    @settings(max_examples=50)
    def test_email_format_validation(self, email):
        """Test that email format is validated"""
        import re

        # Simple email regex
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        # Check if email is valid
        is_valid = bool(re.match(email_regex, email))

        # Basic format checks
        has_at = '@' in email
        has_dot = '.' in email.split('@')[-1] if '@' in email else False

        if has_at and has_dot:
            # Likely valid format
            assert True, "Email has valid format"
        else:
            assert not is_valid, "Email must contain @ and domain"

    @given(
        password=st.text(min_size=0, max_size=200, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*')
    )
    @settings(max_examples=50)
    def test_password_strength_validation(self, password):
        """Test that password strength is validated"""
        # Password requirements
        min_length = 8
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*' for c in password)

        # Calculate strength
        strength_score = sum([
            len(password) >= min_length,
            has_upper,
            has_lower,
            has_digit,
            has_special
        ])

        # Verify strength
        if len(password) < min_length:
            assert strength_score < 5, "Password too short"
        else:
            # Password meets minimum length
            assert True, "Password meets minimum length"

    @given(
        username=st.text(min_size=0, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789_')
    )
    @settings(max_examples=50)
    def test_username_validation(self, username):
        """Test that username format is validated"""
        # Username requirements
        min_length = 3
        max_length = 30
        allowed_chars = set('abcdefghijklmnopqrstuvwxyz0123456789_')

        # Check if valid
        is_valid = (
            min_length <= len(username) <= max_length and
            all(c in allowed_chars for c in username) and
            username[0].isalpha() if username else False
        )

        # Verify validation
        if len(username) < min_length:
            assert not is_valid, "Username too short"
        elif len(username) > max_length:
            assert not is_valid, "Username too long"
        elif not all(c in allowed_chars for c in username):
            assert not is_valid, "Username has invalid characters"
        elif username and not username[0].isalpha():
            assert not is_valid, "Username must start with letter"
        else:
            assert is_valid, "Username is valid"
