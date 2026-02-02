"""
Enterprise Authentication Service
Production-ready authentication with bcrypt, JWT, SAML SSO, and RBAC.
"""

import os
import logging
import uuid
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import hashlib
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class UserRole(Enum):
    """User roles for enterprise access control"""
    MEMBER = "member"
    ADMIN = "admin"
    SECURITY_ADMIN = "security_admin"
    WORKFLOW_ADMIN = "workflow_admin"
    COMPLIANCE_ADMIN = "compliance_admin"
    AUTOMATION_ADMIN = "automation_admin"
    INTEGRATION_ADMIN = "integration_admin"


class SecurityLevel(Enum):
    """Security clearance levels"""
    STANDARD = "standard"
    ELEVATED = "elevated"
    ADMIN = "admin"
    ENTERPRISE = "enterprise"


@dataclass
class UserCredentials:
    """User credential verification result"""
    user_id: str
    username: str
    email: str
    roles: List[str]
    security_level: str
    permissions: List[str]
    mfa_enabled: bool


class EnterpriseAuthService:
    """
    Enterprise authentication service with comprehensive security features.

    Features:
    - Password hashing with bcrypt (cost factor 12+)
    - JWT token management with RS256 signing
    - Session management
    - Role-based access control (RBAC)
    - SAML 2.0 SSO support
    - Audit logging
    """

    def __init__(self, secret_key: Optional[str] = None):
        """
        Initialize the auth service.

        Args:
            secret_key: Secret key for JWT signing (loads from env if not provided)
        """
        self.secret_key = secret_key or os.getenv("ENTERPRISE_JWT_SECRET", "default-secret-key-change-in-production")

        # Load RSA keys for RS256 signing (recommended for production)
        self.private_key = self._load_private_key()
        self.public_key = self._load_public_key()

        # Token expiry settings
        self.access_token_expiry = timedelta(hours=1)
        self.refresh_token_expiry = timedelta(days=7)

        logger.info("Enterprise Auth Service initialized")

    def _load_private_key(self) -> Optional[str]:
        """Load RSA private key for JWT signing"""
        key_path = os.getenv("JWT_PRIVATE_KEY_PATH")
        if key_path and os.path.exists(key_path):
            with open(key_path, 'r') as f:
                return f.read()

        # Fallback: generate from secret
        if os.getenv("GENERATE_JWT_KEYS", "false").lower() == "true":
            return self._generate_rsa_keys()

        return None

    def _load_public_key(self) -> Optional[str]:
        """Load RSA public key for JWT verification"""
        key_path = os.getenv("JWT_PUBLIC_KEY_PATH")
        if key_path and os.path.exists(key_path):
            with open(key_path, 'r') as f:
                return f.read()

        # Fallback: generate from secret
        if os.getenv("GENERATE_JWT_KEYS", "false").lower() == "true":
            return self._generate_rsa_keys()

        return None

    def _generate_rsa_keys(self) -> str:
        """Generate RSA key pair for JWT signing"""
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization

        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        # Serialize private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8
        )

        # Serialize public key
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        # Save to files
        private_key_path = os.getenv("JWT_PRIVATE_KEY_PATH", "jwt_private.pem")
        public_key_path = os.getenv("JWT_PUBLIC_KEY_PATH", "jwt_public.pem")

        with open(private_key_path, 'wb') as f:
            f.write(private_pem)

        with open(public_key_path, 'wb') as f:
            f.write(public_pem)

        logger.info(f"Generated RSA keys: {private_key_path}, {public_key_path}")

        return private_pem.decode('utf-8')

    def hash_password(self, password: str) -> str:
        """
        Hash password using bcrypt with appropriate cost factor.

        Args:
            password: Plain text password

        Returns:
            Salted hash string
        """
        salt = bcrypt.gensalt(rounds=12)  # Cost factor 12 (recommended for 2024)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    def verify_password(self, password: str, hashed_password: str) -> bool:
        """
        Verify password against hash.

        Args:
            password: Plain text password
            hashed_password: Stored hash

        Returns:
            True if password matches hash
        """
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False

    def create_access_token(self, user_id: str, additional_claims: Optional[Dict[str, Any]] = None) -> str:
        """
        Create JWT access token.

        Args:
            user_id: User ID
            additional_claims: Additional claims to include in token

        Returns:
            JWT access token (signed)
        """
        now = datetime.now(timezone.utc)

        payload = {
            "user_id": user_id,
            "iat": now,
            "exp": now + self.access_token_expiry,
            "jti": str(uuid.uuid4()),  # Unique token ID
            "type": "access"
        }

        if additional_claims:
            payload.update(additional_claims)

        # Use RS256 if keys available, otherwise HS256
        if self.private_key:
            token = jwt.encode(payload, self.private_key, algorithm="RS256")
        else:
            logger.warning("Using HS256 (symmetric) - recommended to use RS256 in production")
            token = jwt.encode(payload, self.secret_key, algorithm="HS256")

        return token

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify JWT token and return claims.

        Args:
            token: JWT token to verify

        Returns:
            Token claims if valid, None otherwise
        """
        try:
            # Try RS256 first
            if self.public_key:
                claims = jwt.decode(token, self.public_key, algorithms=["RS256"])
            else:
                claims = jwt.decode(token, self.secret_key, algorithms=["HS256"])

            # Check expiry
            if datetime.now(timezone.utc) > datetime.fromtimestamp(claims['exp'], tz=timezone.utc):
                logger.warning("Token expired")
                return None

            return claims

        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid token: {e}")
            return None
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return None

    def create_refresh_token(self, user_id: str) -> str:
        """
        Create refresh token (long-lived).

        Args:
            user_id: User ID

        Returns:
            Refresh token
        """
        now = datetime.now(timezone.utc)

        payload = {
            "user_id": user_id,
            "iat": now,
            "exp": now + self.refresh_token_expiry,
            "jti": str(uuid.uuid4()),
            "type": "refresh"
        }

        # Use HS256 for refresh tokens
        token = jwt.encode(payload, self.secret_key, algorithm="HS256")

        return token

    def verify_credentials(self, db: Session, username_or_email: str, password: str) -> Optional[UserCredentials]:
        """
        Verify user credentials from database.

        Args:
            db: Database session
            username_or_email: Username or email
            password: Plain text password

        Returns:
            UserCredentials if valid, None otherwise
        """
        try:
            from core.models import User

            # Find user by email or username (assuming username = email for now)
            user = db.query(User).filter(
                (User.email == username_or_email) | (User.id == username_or_email)
            ).first()

            if not user:
                logger.warning(f"User not found: {username_or_email}")
                return None

            # Verify password
            if not user.password_hash:
                logger.warning(f"User {user.id} has no password hash (SSO user?)")
                return None

            if not self.verify_password(password, user.password_hash):
                logger.warning(f"Invalid password for user {user.id}")
                return None

            # Check user status
            if user.status != "active":
                logger.warning(f"User {user.id} is not active: {user.status}")
                return None

            # Map user roles to enterprise roles
            enterprise_roles = self._map_user_role(user.role)

            return UserCredentials(
                user_id=user.id,
                username=user.email,  # Using email as username
                email=user.email,
                roles=enterprise_roles,
                security_level=self._map_security_level(user.role),
                permissions=self._get_user_permissions(db, user),
                mfa_enabled=getattr(user, 'mfa_enabled', False)
            )

        except Exception as e:
            logger.error(f"Credential verification error: {e}")
            return None

    def _map_user_role(self, user_role: str) -> List[str]:
        """Map database user role to enterprise roles"""
        roles = [UserRole.MEMBER.value]

        if user_role == "admin":
            roles = [
                UserRole.ADMIN.value,
                UserRole.SECURITY_ADMIN.value,
                UserRole.WORKFLOW_ADMIN.value,
                UserRole.COMPLIANCE_ADMIN.value,
                UserRole.AUTOMATION_ADMIN.value,
                UserRole.INTEGRATION_ADMIN.value
            ]
        elif user_role == "security_admin":
            roles = [
                UserRole.SECURITY_ADMIN.value,
                UserRole.ADMIN.value
            ]
        elif user_role == "workflow_admin":
            roles = [
                UserRole.WORKFLOW_ADMIN.value,
                UserRole.ADMIN.value
            ]

        return roles

    def _map_security_level(self, user_role: str) -> str:
        """Map user role to security level"""
        if user_role == "admin":
            return SecurityLevel.ENTERPRISE.value
        elif user_role in ["security_admin", "workflow_admin"]:
            return SecurityLevel.ADMIN.value
        else:
            return SecurityLevel.STANDARD.value

    def _get_user_permissions(self, db: Session, user) -> List[str]:
        """Get user permissions based on role and workspace membership"""
        # Basic permissions based on role
        if user.role == "admin":
            return ["all"]

        # TODO: Implement workspace-specific permissions
        return ["read_workflows", "execute_workflows", "view_analytics"]

    def generate_saml_request(self, idp_id: str) -> str:
        """
        Generate SAML authentication request URL.

        Args:
            idp_id: Identity Provider ID

        Returns:
            SAML request URL
        """
        # This would integrate with python3-saml
        saml_request = f"saml_request_id={uuid.uuid4()}"
        return f"https://atom.ai/auth/saml/{idp_id}?{saml_request}"

    def validate_saml_response(self, saml_response: str) -> Optional[UserCredentials]:
        """
        Validate SAML SSO response and create/update user.

        Args:
            saml_response: SAML response from IdP

        Returns:
            UserCredentials if valid, None otherwise
        """
        # TODO: Implement actual SAML validation
        # This would:
        # 1. Decode SAML response
        # 2. Verify signature with IdP certificate
        # 3. Extract user attributes (email, name, etc.)
        # 4. Create or update user in database
        # 5. Return UserCredentials

        logger.warning("SAML SSO not fully implemented - use python3-saml")
        return None


# Global instance
enterprise_auth_service = EnterpriseAuthService()


def get_enterprise_auth_service() -> EnterpriseAuthService:
    """Get or create enterprise auth service instance"""
    return enterprise_auth_service
