"""
Security Tests for JWT Token Structure and Validation

Tests comprehensive JWT token scenarios including:
- JWT token structure validation
- JWT token expiration handling
- JWT token validation on protected endpoints
- JWT token with invalid signature
- JWT token with malformed structure
- JWT token algorithm security
"""

# Set TESTING before any imports
import os
os.environ["TESTING"] = "1"

import pytest
from datetime import timedelta, datetime
from sqlalchemy.orm import Session
from core.models import User
from core.auth import get_password_hash, create_access_token, SECRET_KEY, ALGORITHM
from jose import jwt
import time


class TestJWTTokenStructure:
    """Test JWT token has correct structure"""

    def test_jwt_token_has_three_parts(self, client, db_session: Session):
        """Test JWT token consists of header.payload.signature"""
        # Create user
        user = User(
            email="jwt@example.com",
            password_hash=get_password_hash("SecurePass123!"),
            first_name="JWT",
            last_name="Test",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        # Login
        response = client.post(
            "/api/auth/login",
            json={
                "username": "jwt@example.com",
                "password": "SecurePass123!"
            }
        )

        assert response.status_code == 200
        token = response.json()["access_token"]

        # Verify JWT structure
        parts = token.split(".")
        assert len(parts) == 3, "JWT must have 3 parts: header.payload.signature"

    def test_jwt_header_contains_algorithm(self, client, db_session: Session):
        """Test JWT header contains algorithm information"""
        user = User(
            email="header@example.com",
            password_hash=get_password_hash("SecurePass123!"),
            first_name="Header",
            last_name="Test",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/auth/login",
            json={
                "username": "header@example.com",
                "password": "SecurePass123!"
            }
        )

        token = response.json()["access_token"]

        # Decode header (without verification)
        header = jwt.get_unverified_header(token)
        assert "alg" in header
        assert header["alg"] == "HS256"

    def test_jwt_header_contains_type(self, client, db_session: Session):
        """Test JWT header contains token type"""
        user = User(
            email="type@example.com",
            password_hash=get_password_hash("SecurePass123!"),
            first_name="Type",
            last_name="Test",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/auth/login",
            json={
                "username": "type@example.com",
                "password": "SecurePass123!"
            }
        )

        token = response.json()["access_token"]

        # Decode header
        header = jwt.get_unverified_header(token)
        assert "typ" in header or "type" in header


class TestJWTTokenExpiration:
    """Test JWT token expiration handling"""

    def test_jwt_token_contains_expiration_claim(self, client, db_session: Session):
        """Test JWT token contains 'exp' claim"""
        user = User(
            email="expclaim@example.com",
            password_hash=get_password_hash("SecurePass123!"),
            first_name="Exp",
            last_name="Claim",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/auth/login",
            json={
                "username": "expclaim@example.com",
                "password": "SecurePass123!"
            }
        )

        token = response.json()["access_token"]

        # Decode token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload
        assert payload["exp"] is not None

    def test_jwt_token_expires_in_future(self, client, db_session: Session):
        """Test JWT token expiration is in the future"""
        user = User(
            email="future@example.com",
            password_hash=get_password_hash("SecurePass123!"),
            first_name="Future",
            last_name="Exp",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/auth/login",
            json={
                "username": "future@example.com",
                "password": "SecurePass123!"
            }
        )

        token = response.json()["access_token"]

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        current_time = time.time()

        # Expiration should be in the future
        assert payload["exp"] > current_time

    def test_jwt_token_expires_after_24_hours(self, client, db_session: Session):
        """Test JWT token expiration is approximately 24 hours from issuance"""
        user = User(
            email="24h@example.com",
            password_hash=get_password_hash("SecurePass123!"),
            first_name="24",
            last_name="Hour",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/auth/login",
            json={
                "username": "24h@example.com",
                "password": "SecurePass123!"
            }
        )

        token = response.json()["access_token"]

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        current_time = time.time()
        time_until_expiry = payload["exp"] - current_time

        # 24 hours = 86400 seconds
        # Allow 5 second tolerance for test execution time
        assert 86395 <= time_until_expiry <= 86405


class TestJWTTokenValidation:
    """Test JWT token is validated on protected endpoints"""

    def test_valid_token_allows_access(self, client, db_session: Session):
        """Test valid JWT token allows access to protected endpoint"""
        user = User(
            email="valid@example.com",
            password_hash=get_password_hash("SecurePass123!"),
            first_name="Valid",
            last_name="Token",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        # Login to get token
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": "valid@example.com",
                "password": "SecurePass123!"
            }
        )
        token = login_response.json()["access_token"]

        # Access protected endpoint
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data or "email" in data

    def test_missing_token_denies_access(self, client):
        """Test missing JWT token denies access to protected endpoint"""
        response = client.get("/api/auth/me")

        assert response.status_code == 401

    def test_invalid_token_denies_access(self, client):
        """Test invalid JWT token denies access to protected endpoint"""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )

        assert response.status_code == 401

    def test_malformed_token_denies_access(self, client):
        """Test malformed JWT token denies access"""
        malformed_tokens = [
            "invalid",
            "invalid.invalid",
            "invalid.invalid.invalid.invalid",
            "not-a-jwt",
            ""
        ]

        for token in malformed_tokens:
            response = client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 401


class TestJWTTokenInvalidSignature:
    """Test JWT token with invalid signature"""

    def test_token_with_wrong_signature_fails(self, client, db_session: Session):
        """Test token signed with wrong secret is rejected"""
        user = User(
            email="sig@example.com",
            password_hash=get_password_hash("SecurePass123!"),
            first_name="Wrong",
            last_name="Sig",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        # Create token with wrong secret
        payload = {
            "sub": str(user.id),
            "exp": int(time.time()) + 3600
        }
        wrong_token = jwt.encode(payload, "wrong_secret", algorithm="HS256")

        # Try to use token
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {wrong_token}"}
        )

        assert response.status_code == 401

    def test_tampered_token_fails(self, client, db_session: Session):
        """Test tampered token is rejected"""
        user = User(
            email="tamper@example.com",
            password_hash=get_password_hash("SecurePass123!"),
            first_name="Tam",
            last_name="per",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        # Get valid token
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": "tamper@example.com",
                "password": "SecurePass123!"
            }
        )
        token = login_response.json()["access_token"]

        # Tamper with token (change last character)
        tampered_token = token[:-1] + ("0" if token[-1] != "0" else "1")

        # Try to use tampered token
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {tampered_token}"}
        )

        assert response.status_code == 401


class TestJWTTokenMalformedStructure:
    """Test JWT token with malformed structure"""

    def test_token_without_payload_fails(self, client):
        """Test token without payload section is rejected"""
        malformed_token = "header..signature"

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {malformed_token}"}
        )

        assert response.status_code == 401

    def test_token_without_signature_fails(self, client):
        """Test token without signature section is rejected"""
        malformed_token = "header.payload"

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {malformed_token}"}
        )

        assert response.status_code == 401

    def test_token_with_invalid_base64_fails(self, client):
        """Test token with invalid base64 encoding is rejected"""
        malformed_token = "not-valid-base64.not-valid-base64.not-valid-base64"

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {malformed_token}"}
        )

        assert response.status_code == 401


class TestJWTTokenAlgorithmSecurity:
    """Test JWT token algorithm security"""

    def test_token_uses_hs256_algorithm(self, client, db_session: Session):
        """Test JWT token uses HS256 algorithm (not 'none')"""
        user = User(
            email="algo@example.com",
            password_hash=get_password_hash("SecurePass123!"),
            first_name="Algo",
            last_name="Test",
            status="active"
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/auth/login",
            json={
                "username": "algo@example.com",
                "password": "SecurePass123!"
            }
        )

        token = response.json()["access_token"]

        # Decode header
        header = jwt.get_unverified_header(token)
        assert header["alg"] == "HS256"
        assert header["alg"].lower() != "none"

    def test_none_algorithm_rejected(self, client):
        """Test tokens with 'none' algorithm are rejected"""
        # Create malicious token with 'none' algorithm
        header = {"alg": "none", "typ": "JWT"}
        payload = {"sub": "admin", "exp": int(time.time()) + 3600}

        # Encode with 'none' algorithm
        none_token = jwt.encode(payload, "", algorithm="none")

        # Try to use token
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {none_token}"}
        )

        # Should be rejected
        assert response.status_code == 401
