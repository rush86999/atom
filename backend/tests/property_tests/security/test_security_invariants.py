"""
Property-Based Tests for Security Invariants

⚠️  PROTECTED PROPERTY-BASED TEST ⚠️

This file tests CRITICAL SECURITY INVARIANTS for the Atom platform.

DO NOT MODIFY THIS FILE unless:
1. You are fixing a TEST BUG (not an implementation bug)
2. You are ADDING new invariants
3. You have EXPLICIT APPROVAL from engineering lead

These tests must remain IMPLEMENTATION-AGNOSTIC.
Test only observable behaviors and public API contracts.

Protection: tests/.protection_markers/PROPERTY_TEST_GUARDIAN.md

Tests:
    - 12 comprehensive property-based tests for security operations
    - Coverage targets: 100% of security.py and security_dependencies.py
    - Runtime target: <20s
"""

import pytest
import jwt
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
from typing import Dict, List
import secrets
import hashlib
import re
from core.security import (
    SecurityManager,
    TokenEncryption,
    RateLimiter,
    PasswordHasher,
    PermissionChecker,
    AuditLogger
)
from core.security_dependencies import (
    validate_api_key,
    validate_oauth_state,
    validate_session_token,
    validate_password_requirements,
    sanitize_user_input,
    check_csrf_token
)


class TestSecurityInvariants:
    """Property-based tests for security invariants."""

    # ========== Token Encryption ==========

    @given(
        plaintext=st.text(min_size=0, max_size=1000),
        encryption_key=st.binary(min_size=32, max_size=32)  # 256-bit key
    )
    @settings(max_examples=100)
    def test_token_encryption_decryption_roundtrip(self, plaintext, encryption_key):
        """INVARIANT: Encrypt → Decrypt must return original plaintext."""
        encryptor = TokenEncryption(encryption_key)

        encrypted = encryptor.encrypt(plaintext)
        decrypted = encryptor.decrypt(encrypted)

        assert decrypted == plaintext

    @given(
        plaintext=st.text(min_size=0, max_size=1000),
        encryption_key=st.binary(min_size=32, max_size=32)
    )
    @settings(max_examples=100)
    def test_encryption_idempotency(self, plaintext, encryption_key):
        """INVARIANT: Encrypting ciphertext should fail or return new ciphertext."""
        encryptor = TokenEncryption(encryption_key)

        encrypted1 = encryptor.encrypt(plaintext)
        encrypted2 = encryptor.encrypt(plaintext)

        # Encrypted values should differ (due to IV/nonce)
        # but decrypt to the same plaintext
        assert encrypted1 != encrypted2
        assert encryptor.decrypt(encrypted1) == plaintext
        assert encryptor.decrypt(encrypted2) == plaintext

    @given(
        ciphertext=st.binary(min_size=1, max_size=1000),
        wrong_key=st.binary(min_size=32, max_size=32)
    )
    @settings(max_examples=100)
    def test_encryption_key_uniqueness(self, ciphertext, wrong_key):
        """INVARIANT: Decrypting with wrong key should fail."""
        correct_key = secrets.token_bytes(32)
        encryptor = TokenEncryption(correct_key)

        plaintext = "test data"
        encrypted = encryptor.encrypt(plaintext)

        wrong_encryptor = TokenEncryption(wrong_key)

        # Decrypting with wrong key should raise exception
        with pytest.raises((ValueError, KeyError, jwt.DecodeError)):
            wrong_encryptor.decrypt(encrypted)

    # ========== Rate Limiting ==========

    @given(
        requests=st.lists(
            st.fixed_dictionaries({
                'user_id': st.text(min_size=1, max_size=50),
                'timestamp': st.floats(min_value=0, max_value=1000)
            }),
            min_size=1,
            max_size=100
        ),
        rate_limit=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=100)
    def test_rate_limiting_enforcement(self, requests, rate_limit):
        """INVARIANT: Rate limiter must reject excess requests."""
        limiter = RateLimiter(rate_limit=rate_limit, window_seconds=60)

        # Count requests per user
        from collections import Counter
        user_counts = Counter(req['user_id'] for req in requests)

        rejected_count = 0
        for req in requests:
            if not limiter.allow_request(req['user_id'], req['timestamp']):
                rejected_count += 1

        # Verify users exceeding limit were rejected
        for user_id, count in user_counts.items():
            if count > rate_limit:
                # At least some requests should be rejected
                assert rejected_count > 0

    # ========== JWT Validation ==========

    @given(
        payload=st.fixed_dictionaries({
            'user_id': st.text(min_size=1, max_size=50),
            'exp': st.integers(min_value=0, max_value=2_000_000_000)
        }),
        secret=st.text(min_size=32, max_size=32)
    )
    @settings(max_examples=100)
    def test_jwt_signature_validation(self, payload, secret):
        """INVARIANT: Tampered JWT signatures must be rejected."""
        token = jwt.encode(payload, secret, algorithm="HS256")

        # Valid token should decode
        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        assert decoded['user_id'] == payload['user_id']

        # Tampered token should fail
        tampered_token = token[:-10] + "tampered" + token[-5:]
        with pytest.raises(jwt.DecodeError):
            jwt.decode(tampered_token, secret, algorithms=["HS256"])

    @given(
        payload=st.fixed_dictionaries({
            'user_id': st.text(min_size=1, max_size=50),
            'iat': st.integers(min_value=0, max_value=2_000_000_000)
        }),
        secret=st.text(min_size=32, max_size=32),
        expiration_hours=st.integers(min_value=1, max_value=168)
    )
    @settings(max_examples=100)
    def test_jwt_expiration_enforcement(self, payload, secret, expiration_hours):
        """INVARIANT: Expired JWTs must be rejected."""
        exp_time = payload['iat'] + (expiration_hours * 3600)
        payload['exp'] = exp_time

        token = jwt.encode(payload, secret, algorithm="HS256")

        # Current token should be valid
        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        assert decoded['user_id'] == payload['user_id']

        # Expired token should fail
        past_payload = payload.copy()
        past_payload['exp'] = payload['iat'] - 3600  # Expired 1 hour ago
        expired_token = jwt.encode(past_payload, secret, algorithm="HS256")

        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(expired_token, secret, algorithms=["HS256"])

    # ========== OAuth State ==========

    @given(
        state_length=st.integers(min_value=16, max_size=64)
    )
    @settings(max_examples=100)
    def test_oauth_state_uniqueness(self, state_length):
        """INVARIANT: OAuth states must be unique."""
        states = [validate_oauth_state(secrets.token_urlsafe(state_length)) for _ in range(100)]

        # All states should be unique
        assert len(set(states)) == 100

    @given(
        state=st.text(min_size=1, max_size=100)
    )
    @settings(max_examples=100)
    def test_oauth_state_validation(self, state):
        """INVARIANT: OAuth state validation must be correct."""
        # Valid state
        assert validate_oauth_state(state) == state

        # Invalid states (empty, None)
        with pytest.raises(ValueError):
            validate_oauth_state("")
        with pytest.raises(ValueError):
            validate_oauth_state(None)

    # ========== Session Expiration ==========

    @given(
        created_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now()),
        session_timeout_minutes=st.integers(min_value=5, max_value=1440)
    )
    @settings(max_examples=100)
    def test_session_expiration_enforcement(self, created_at, session_timeout_minutes):
        """INVARIANT: Sessions must expire after timeout."""
        session = {
            'created_at': created_at,
            'timeout_minutes': session_timeout_minutes
        }

        is_valid = validate_session_token(session)

        expiration_time = created_at + timedelta(minutes=session_timeout_minutes)
        now = datetime.now()

        if now > expiration_time:
            assert not is_valid, "Session should be expired"
        else:
            assert is_valid, "Session should be valid"

    # ========== Password Hashing ==========

    @given(
        password=st.text(min_size=8, max_size=128)
    )
    @settings(max_examples=100)
    def test_password_hashing_strength(self, password):
        """INVARIANT: Passwords must be hashed with strong algorithm (bcrypt)."""
        hasher = PasswordHasher()

        hashed = hasher.hash(password)

        # Hash should not equal plaintext
        assert hashed != password

        # Hash should start with $2b$ (bcrypt identifier)
        assert hashed.startswith("$2b$")

        # Verify password
        assert hasher.verify(password, hashed)

        # Wrong password should fail
        assert not hasher.verify("wrongpassword", hashed)

    @given(
        passwords=st.lists(st.text(min_size=8, max_size=128), min_size=2, max_size=10, unique=True)
    )
    @settings(max_examples=50)
    def test_password_hash_uniqueness(self, passwords):
        """INVARIANT: Same password should produce different hashes (due to salt)."""
        hasher = PasswordHasher()

        password = passwords[0]
        hash1 = hasher.hash(password)
        hash2 = hasher.hash(password)

        # Hashes should differ due to salt
        assert hash1 != hash2

        # Both should verify correctly
        assert hasher.verify(password, hash1)
        assert hasher.verify(password, hash2)

    # ========== Permission Check Matrix ==========

    @given(
        user_roles=st.lists(st.sampled_from(['admin', 'user', 'guest', 'moderator']), min_size=1, max_size=4, unique=True),
        resource=st.text(min_size=1, max_size=50),
        action=st.sampled_from(['read', 'write', 'delete', 'admin'])
    )
    @settings(max_examples=100)
    def test_permission_check_matrix(self, user_roles, resource, action):
        """INVARIANT: Permission checks must follow RBAC rules."""
        checker = PermissionChecker()

        # Define RBAC rules
        rbac_rules = {
            'admin': ['read', 'write', 'delete', 'admin'],
            'moderator': ['read', 'write', 'delete'],
            'user': ['read', 'write'],
            'guest': ['read']
        }

        for role in user_roles:
            has_permission = checker.check_permission(role, resource, action)

            expected_permission = action in rbac_rules.get(role, [])
            assert has_permission == expected_permission

    # ========== Audit Log Completeness ==========

    @given(
        events=st.lists(
            st.fixed_dictionaries({
                'event_type': st.sampled_from(['login', 'logout', 'access', 'modify', 'delete']),
                'user_id': st.text(min_size=1, max_size=50),
                'resource': st.text(min_size=1, max_size=50),
                'timestamp': st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now())
            }),
            min_size=1,
            max_size=50
        )
    )
    @settings(max_examples=100)
    def test_audit_log_completeness(self, events):
        """INVARIANT: All security events must be logged."""
        auditor = AuditLogger()

        for event in events:
            auditor.log_event(**event)

        # Retrieve all logs
        all_logs = auditor.get_all_logs()

        # All events should be logged
        assert len(all_logs) == len(events)

        # Verify log entries
        for event, log in zip(events, all_logs):
            assert log['event_type'] == event['event_type']
            assert log['user_id'] == event['user_id']
            assert log['resource'] == event['resource']

    # ========== SQL Injection Prevention ==========

    @given(
        user_input=st.text(min_size=0, max_size=1000)
    )
    @settings(max_examples=100)
    def test_sql_injection_prevention(self, user_input):
        """INVARIANT: Sanitized input must not contain SQL injection patterns."""
        sanitized = sanitize_user_input(user_input)

        # Check for common SQL injection patterns
        sql_patterns = [
            r"';.*DROP TABLE",
            r"'.*OR.*'.*='",
            r"'.*UNION.*SELECT",
            r"'.*--",
            r"'.*/\*.*\*/",
            r"1=1",
            r"admin'--",
            r"' OR '1'='1"
        ]

        for pattern in sql_patterns:
            # Sanitized input should not contain SQL injection patterns
            assert not re.search(pattern, sanitized, re.IGNORECASE), f"SQL injection pattern found: {pattern}"

    # ========== XSS Prevention ==========

    @given(
        user_input=st.text(min_size=0, max_size=1000)
    )
    @settings(max_examples=100)
    def test_xss_prevention_in_outputs(self, user_input):
        """INVARIANT: Output must be sanitized to prevent XSS."""
        sanitized = sanitize_user_input(user_input)

        # Check for XSS patterns
        xss_patterns = [
            r"<script",
            r"javascript:",
            r"onerror=",
            r"onload=",
            r"<iframe",
            r"<object",
            r"<embed",
            r"vbscript:",
            r"data:text/html"
        ]

        for pattern in xss_patterns:
            # Sanitized output should not contain XSS patterns (case-insensitive)
            assert not re.search(pattern, sanitized, re.IGNORECASE), f"XSS pattern found: {pattern}"

    # ========== CSRF Token Validation ==========

    @given(
        csrf_token=st.text(min_size=32, max_size=64),
        session_token=st.text(min_size=32, max_size=64)
    )
    @settings(max_examples=100)
    def test_csrf_token_validation(self, csrf_token, session_token):
        """INVARIANT: CSRF tokens must be validated."""
        # Valid CSRF token
        assert check_csrf_token(csrf_token, session_token)

        # Invalid CSRF tokens
        assert not check_csrf_token("", session_token)
        assert not check_csrf_token(None, session_token)
        assert not check_csrf_token("invalid", session_token)

    # ========== API Key Validation ==========

    @given(
        api_key=st.text(min_size=32, max_size=64)
    )
    @settings(max_examples=100)
    def test_api_key_format(self, api_key):
        """INVARIANT: API keys must follow secure format."""
        # Valid API key
        assert validate_api_key(api_key) == api_key

        # Invalid API keys
        with pytest.raises(ValueError):
            validate_api_key("")
        with pytest.raises(ValueError):
            validate_api_key("short")
        with pytest.raises(ValueError):
            validate_api_key(None)

    # ========== Password Requirements ==========

    @given(
        password=st.text(min_size=0, max_size=128)
    )
    @settings(max_examples=100)
    def test_password_requirements_enforcement(self, password):
        """INVARIANT: Passwords must meet strength requirements."""
        is_valid = validate_password_requirements(password)

        # Check requirements
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
        is_long_enough = len(password) >= 8

        expected_valid = is_long_enough and has_upper and has_lower and has_digit and has_special

        assert is_valid == expected_valid
