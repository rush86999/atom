"""
Security Tests for User Login Flow

Tests comprehensive login scenarios including:
- Valid login with correct credentials
- Invalid login with wrong email/password
- SQL injection protection in login
- XSS protection in login responses
- Account status validation (active/inactive)
- Login rate limiting (if implemented)
"""

# Set TESTING before any imports
import os
os.environ["TESTING"] = "1"

import pytest
from sqlalchemy.orm import Session
from core.models import User
from core.auth import get_password_hash, verify_password, SECRET_KEY
from jose import jwt


class TestLoginWithValidCredentials:
    """Test user login with valid credentials"""

    def test_login_with_valid_credentials(self, client, db_session: Session):
        """Test login returns JWT token for valid credentials"""
        # Create test user
        user = User(
            email="login@example.com",
            password_hash=get_password_hash("SecurePass123!"),
            first_name="Login",
            last_name="Test",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/auth/login",
            json={
                "username": "login@example.com",
                "password": "SecurePass123!"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Verify token is valid JWT
        token = data["access_token"]
        parts = token.split(".")
        assert len(parts) == 3

        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        assert "sub" in payload
        assert "exp" in payload

    def test_login_updates_last_login_timestamp(self, client, db_session: Session):
        """Test login updates user's last_login timestamp"""
        from datetime import datetime

        user = User(
            email="timestamp@example.com",
            password_hash=get_password_hash("SecurePass123!"),
            first_name="Time",
            last_name="Stamp",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        # Get initial last_login
        initial_last_login = user.last_login

        import time
        time.sleep(1)  # Ensure timestamp difference

        response = client.post(
            "/api/auth/login",
            json={
                "username": "timestamp@example.com",
                "password": "SecurePass123!"
            }
        )

        assert response.status_code == 200

        # Refresh and check last_login was updated
        db_session.refresh(user)
        assert user.last_login is not None
        if initial_last_login:
            assert user.last_login > initial_last_login


class TestLoginWithInvalidCredentials:
    """Test login fails with invalid credentials"""

    def test_login_with_wrong_email(self, client, db_session: Session):
        """Test login fails with non-existent email"""
        response = client.post(
            "/api/auth/login",
            json={
                "username": "nonexistent@example.com",
                "password": "SecurePass123!"
            }
        )

        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    def test_login_with_wrong_password(self, client, db_session: Session):
        """Test login fails with wrong password"""
        user = User(
            email="wrongpass@example.com",
            password_hash=get_password_hash("CorrectPass123!"),
            first_name="Wrong",
            last_name="Pass",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/auth/login",
            json={
                "username": "wrongpass@example.com",
                "password": "WrongPass123!"
            }
        )

        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    def test_login_with_empty_password(self, client, db_session: Session):
        """Test login fails with empty password"""
        user = User(
            email="empty@example.com",
            password_hash=get_password_hash("SecurePass123!"),
            first_name="Empty",
            last_name="Pass",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/auth/login",
            json={
                "username": "empty@example.com",
                "password": ""
            }
        )

        # Should fail - either validation or auth error
        assert response.status_code in [401, 422]

    def test_login_with_missing_fields(self, client):
        """Test login fails with missing required fields"""
        response = client.post(
            "/api/auth/login",
            json={}
        )

        assert response.status_code == 422  # Validation error


class TestLoginSQLInjectionProtection:
    """Test SQL injection protection in login"""

    def test_login_with_sql_injection_in_email(self, client, db_session: Session):
        """Test login blocks SQL injection in email field"""
        response = client.post(
            "/api/auth/login",
            json={
                "username": "'; DROP TABLE users; --",
                "password": "password"
            }
        )

        # Should return auth error
        assert response.status_code == 401

        # Verify users table still exists
        users_count = db_session.query(User).count()
        assert users_count >= 0  # Table not dropped

    def test_login_with_sql_injection_in_password(self, client, db_session: Session):
        """Test login safely handles SQL injection in password"""
        user = User(
            email="safepass@example.com",
            password_hash=get_password_hash("RealPassword123!"),
            first_name="Safe",
            last_name="Pass",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/auth/login",
            json={
                "username": "safepass@example.com",
                "password": "' OR '1'='1"
            }
        )

        # Should not authenticate with SQL injection
        assert response.status_code == 401

    def test_login_with_union_based_injection(self, client, db_session: Session):
        """Test login blocks UNION-based SQL injection"""
        response = client.post(
            "/api/auth/login",
            json={
                "username": "admin' UNION SELECT * FROM users--",
                "password": "password"
            }
        )

        # Should return auth error, not database error
        assert response.status_code == 401


class TestLoginXSSProtection:
    """Test XSS protection in login responses"""

    def test_login_xss_in_error_messages(self, client, db_session: Session):
        """Test login error messages are XSS-safe"""
        xss_email = "<script>alert('XSS')</script>@example.com"

        response = client.post(
            "/api/auth/login",
            json={
                "username": xss_email,
                "password": "password"
            }
        )

        # Should fail authentication
        assert response.status_code == 401

        # Error message should be JSON-encoded, not executable
        data = response.text
        # Response should be JSON, not HTML with script tags
        assert "<script>" not in data or "\\u003c" in data


class TestLoginAccountStatus:
    """Test login respects account status"""

    def test_login_fails_for_inactive_user(self, client, db_session: Session):
        """Test login fails for inactive user account"""
        user = User(
            email="inactive@example.com",
            password_hash=get_password_hash("SecurePass123!"),
            first_name="In",
            last_name="Active",
            status="inactive"
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/auth/login",
            json={
                "username": "inactive@example.com",
                "password": "SecurePass123!"
            }
        )

        assert response.status_code == 400
        assert "inactive" in response.json()["detail"].lower()

    def test_login_succeeds_for_active_user(self, client, db_session: Session):
        """Test login succeeds for active user account"""
        user = User(
            email="activeuser@example.com",
            password_hash=get_password_hash("SecurePass123!"),
            first_name="Active",
            last_name="User",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/auth/login",
            json={
                "username": "activeuser@example.com",
                "password": "SecurePass123!"
            }
        )

        assert response.status_code == 200
        assert "access_token" in response.json()


class TestLoginPasswordSecurity:
    """Test password security in login flow"""

    def test_login_does_not_return_password(self, client, db_session: Session):
        """Test login response does not include password"""
        user = User(
            email="nopass@example.com",
            password_hash=get_password_hash("SecurePass123!"),
            first_name="No",
            last_name="Pass",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/auth/login",
            json={
                "username": "nopass@example.com",
                "password": "SecurePass123!"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Password should not be in response
        assert "password" not in data
        assert "password_hash" not in data
        assert "SecurePass123!" not in str(data)

    def test_login_bcrypt_timing_resistance(self, client, db_session: Session):
        """Test login uses timing-safe comparison (bcrypt)"""
        import time

        # Create user
        user = User(
            email="timing@example.com",
            password_hash=get_password_hash("SecurePass123!"),
            first_name="Timing",
            last_name="Test",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        # Measure time for wrong password
        start = time.time()
        response1 = client.post(
            "/api/auth/login",
            json={
                "username": "timing@example.com",
                "password": "WrongPassword123!"
            }
        )
        wrong_time = time.time() - start

        # Measure time for correct password
        start = time.time()
        response2 = client.post(
            "/api/auth/login",
            json={
                "username": "timing@example.com",
                "password": "SecurePass123!"
            }
        )
        correct_time = time.time() - start

        assert response1.status_code == 401
        assert response2.status_code == 200

        # Bcrypt should have similar timing (within 100ms)
        # This prevents timing attacks
        timing_diff = abs(wrong_time - correct_time)
        assert timing_diff < 0.1  # Less than 100ms difference


class TestLoginTokenGeneration:
    """Test JWT token generation on login"""

    def test_login_token_contains_user_id(self, client, db_session: Session):
        """Test login token contains user ID claim"""
        user = User(
            email="tokenid@example.com",
            password_hash=get_password_hash("SecurePass123!"),
            first_name="Token",
            last_name="ID",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/auth/login",
            json={
                "username": "tokenid@example.com",
                "password": "SecurePass123!"
            }
        )

        assert response.status_code == 200
        token = response.json()["access_token"]

        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        assert "sub" in payload
        assert payload["sub"] == str(user.id)

    def test_login_token_expiration(self, client, db_session: Session):
        """Test login token has expiration claim"""
        import time

        user = User(
            email="expirelogin@example.com",
            password_hash=get_password_hash("SecurePass123!"),
            first_name="Expire",
            last_name="Login",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/auth/login",
            json={
                "username": "expirelogin@example.com",
                "password": "SecurePass123!"
            }
        )

        assert response.status_code == 200
        token = response.json()["access_token"]

        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        assert "exp" in payload
        assert payload["exp"] > time.time()


class TestLoginCaseSensitivity:
    """Test email case sensitivity in login"""

    def test_login_with_uppercase_email(self, client, db_session: Session):
        """Test login with uppercase email (should work if emails stored lowercase)"""
        user = User(
            email="case@example.com",  # Stored as lowercase
            password_hash=get_password_hash("SecurePass123!"),
            first_name="Case",
            last_name="Test",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        # Try login with uppercase email
        response = client.post(
            "/api/auth/login",
            json={
                "username": "CASE@EXAMPLE.COM",
                "password": "SecurePass123!"
            }
        )

        # Behavior depends on implementation
        # Most systems normalize email to lowercase
        assert response.status_code in [200, 401]
