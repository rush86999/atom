"""
Centralized JWT Verification Module

Provides enterprise-grade JWT validation with:
- Audience (aud) claim validation
- Issuer (iss) claim validation
- Expiration (exp) validation
- Secret key validation
- Token revocation support
- IP whitelist for DEBUG mode (optional)

Security Features:
- No DEBUG bypass in production
- Configurable IP whitelist for development
- Comprehensive logging for security audit
- Graceful degradation with security-first approach
"""

import logging
import os
from datetime import datetime, timedelta
from ipaddress import ip_address, ip_network
from typing import Any, Dict, List, Optional
import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

security = HTTPBearer()


class JWTVerificationError(Exception):
    """Custom exception for JWT verification errors"""
    pass


class JWTVerifier:
    """
    Enterprise-grade JWT verifier with comprehensive validation.

    Features:
    - Audience, issuer, expiration validation
    - Secret key validation (rejects default keys in production)
    - Optional IP whitelist for DEBUG mode
    - Token revocation check support
    - Detailed error messages for debugging (logged only)
    """

    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithm: str = "HS256",
        audience: Optional[str] = None,
        issuer: Optional[str] = None,
        debug_mode: Optional[bool] = None,
        debug_ip_whitelist: Optional[List[str]] = None,
    ):
        """
        Initialize JWT verifier.

        Args:
            secret_key: JWT secret key (defaults to JWT_SECRET env var)
            algorithm: JWT algorithm (default: HS256)
            audience: Expected audience claim (aud)
            issuer: Expected issuer claim (iss)
            debug_mode: Enable DEBUG mode (defaults to DEBUG env var)
            debug_ip_whitelist: List of IP addresses allowed in DEBUG mode (CIDR notation supported)

        Raises:
            ValueError: If configuration is invalid
        """
        self.secret_key = secret_key or os.getenv("JWT_SECRET", os.getenv("SECRET_KEY"))
        self.algorithm = algorithm
        self.audience = audience or os.getenv("JWT_AUDIENCE")
        self.issuer = issuer or os.getenv("JWT_ISSUER")

        # Allow override of debug_mode via parameter, otherwise use environment
        if debug_mode is not None:
            self.debug_mode = debug_mode
        else:
            self.debug_mode = os.getenv("DEBUG", "False").lower() == "true"

        self.debug_ip_whitelist = debug_ip_whitelist or self._parse_debug_ip_whitelist()

        # Security: Reject default secret in production
        if not self.debug_mode and self._is_default_secret():
            logger.error("JWT_VERIFICATION: Using default secret key in production")
            raise ValueError(
                "Cannot use default secret key in production. "
                "Set JWT_SECRET environment variable."
            )

        if not self.secret_key:
            logger.error("JWT_VERIFICATION: No secret key configured")
            raise ValueError("JWT_SECRET environment variable must be set")

        logger.info(
            f"JWT_VERIFIER: Initialized (debug={self.debug_mode}, "
            f"audience={self.audience}, issuer={self.issuer})"
        )

    def _parse_debug_ip_whitelist(self) -> List[str]:
        """Parse DEBUG_IP_WHITELIST from environment"""
        whitelist_str = os.getenv("DEBUG_IP_WHITELIST", "")
        if not whitelist_str:
            return []

        whitelist = [ip.strip() for ip in whitelist_str.split(",")]
        logger.info(f"JWT_VERIFIER: Debug IP whitelist: {whitelist}")
        return whitelist

    def _is_default_secret(self) -> bool:
        """Check if using default/known insecure secret keys"""
        default_secrets = [
            "your-secret-key-here-change-in-production",
            "secret",
            "changeme",
            "default-secret-key",
        ]
        return self.secret_key in default_secrets

    def _is_ip_whitelisted(self, client_ip: str) -> bool:
        """Check if client IP is in debug whitelist"""
        if not self.debug_ip_whitelist:
            return False

        try:
            client_ip_obj = ip_address(client_ip)
            for whitelisted in self.debug_ip_whitelist:
                # Check if it's a CIDR range or single IP
                if "/" in whitelisted:
                    if client_ip_obj in ip_network(whitelisted):
                        return True
                elif str(client_ip_obj) == whitelisted:
                    return True
            return False
        except ValueError as e:
            logger.error(f"JWT_VERIFICATION: Invalid IP address or whitelist: {e}")
            return False

    def verify_token(
        self,
        credentials: HTTPAuthorizationCredentials,
        client_ip: Optional[str] = None,
        check_revocation: bool = False,
    ) -> Dict[str, Any]:
        """
        Verify and decode JWT token with comprehensive validation.

        Args:
            credentials: HTTPAuthorizationCredentials from FastAPI Security
            client_ip: Client IP address for DEBUG whitelist validation
            check_revocation: Whether to check token revocation status

        Returns:
            Decoded JWT payload as dictionary

        Raises:
            HTTPException: If token is invalid (401)
            JWTVerificationError: If verification fails with details
        """
        if not credentials or not credentials.credentials:
            logger.warning("JWT_VERIFICATION: No credentials provided")
            raise HTTPException(
                status_code=401,
                detail="No authentication credentials provided",
            )

        token = credentials.credentials

        # DEBUG mode with IP whitelist check
        if self.debug_mode:
            if client_ip and self._is_ip_whitelisted(client_ip):
                logger.info(f"JWT_VERIFICATION: DEBUG mode - allowing whitelisted IP: {client_ip}")
                # Still decode to catch malformed tokens, but skip validation
                try:
                    payload = jwt.decode(token, options={"verify_signature": False})
                    logger.debug(f"JWT_VERIFICATION: DEBUG mode - decoded token (no validation)")
                    return payload
                except Exception as e:
                    logger.error(f"JWT_VERIFICATION: DEBUG mode - malformed token: {e}")
                    raise HTTPException(status_code=401, detail="Malformed token")
            elif not self.debug_ip_whitelist:
                logger.warning(
                    "JWT_VERIFICATION: DEBUG mode enabled without IP whitelist - "
                    "require proper authentication"
                )
                # Fall through to normal verification
            else:
                logger.warning(
                    f"JWT_VERIFICATION: DEBUG mode - IP {client_ip} not in whitelist"
                )
                # Fall through to normal verification

        # Normal JWT verification
        try:
            # Decode options
            decode_options = {
                "require": ["exp"],  # Require expiration claim
                "verify_exp": True,  # Verify expiration
            }

            # Add audience validation if configured
            if self.audience:
                decode_options["verify_aud"] = True
            else:
                decode_options["verify_aud"] = False

            # Add issuer validation if configured
            if self.issuer:
                decode_options["verify_iss"] = True
            else:
                decode_options["verify_iss"] = False

            # Decode token
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                audience=self.audience,
                issuer=self.issuer,
                options=decode_options,
            )

            # Additional validations
            if not payload.get("sub"):
                logger.error("JWT_VERIFICATION: Token missing 'sub' claim")
                raise HTTPException(status_code=401, detail="Invalid token: missing subject")

            # Check token age (optional - warn if token is very old)
            if "iat" in payload:
                iat = datetime.fromtimestamp(payload["iat"])
                token_age = datetime.now() - iat
                if token_age > timedelta(days=30):
                    logger.warning(
                        f"JWT_VERIFICATION: Token is very old ({token_age.days} days)"
                    )

            # Check revocation if enabled (implement in your application)
            if check_revocation:
                if self._is_token_revoked(payload):
                    logger.warning(f"JWT_VERIFICATION: Token has been revoked: {payload.get('sub')}")
                    raise HTTPException(status_code=401, detail="Token has been revoked")

            logger.info(f"JWT_VERIFICATION: Token validated successfully for sub={payload.get('sub')}")
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("JWT_VERIFICATION: Token has expired")
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidAudienceError as e:
            logger.warning(f"JWT_VERIFICATION: Invalid audience: {e}")
            raise HTTPException(status_code=401, detail="Invalid token audience")
        except jwt.InvalidIssuerError as e:
            logger.warning(f"JWT_VERIFICATION: Invalid issuer: {e}")
            raise HTTPException(status_code=401, detail="Invalid token issuer")
        except jwt.InvalidTokenError as e:
            logger.warning(f"JWT_VERIFICATION: Invalid token: {e}")
            raise HTTPException(status_code=401, detail="Invalid token")
        except Exception as e:
            logger.error(f"JWT_VERIFICATION: Unexpected error: {e}")
            raise HTTPException(status_code=401, detail="Could not validate credentials")

    def _is_token_revoked(self, payload: Dict[str, Any]) -> bool:
        """
        Check if token has been revoked.

        Override this method to implement token revocation checking.
        Examples:
        - Check against a Redis blacklist
        - Query a database for revoked tokens
        - Check a token version in user record

        Args:
            payload: Decoded JWT payload

        Returns:
            True if token is revoked, False otherwise
        """
        # TODO: Implement token revocation checking
        # Example implementations:
        # 1. Redis: return redis_client.get(f"revoked:{payload['jti']}") is not None
        # 2. Database: return db.query(RevokedToken).filter_by(jti=payload['jti']).first()
        return False

    def create_token(
        self,
        subject: str,
        expires_delta: Optional[timedelta] = None,
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a JWT token (for testing or internal use).

        Args:
            subject: Subject identifier (usually user ID)
            expires_delta: Token expiration time (default: 24 hours)
            additional_claims: Additional claims to include in token

        Returns:
            Encoded JWT token string
        """
        if expires_delta is None:
            expires_delta = timedelta(hours=24)

        payload = {
            "sub": subject,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + expires_delta,
        }

        if self.audience:
            payload["aud"] = self.audience

        if self.issuer:
            payload["iss"] = self.issuer

        if additional_claims:
            payload.update(additional_claims)

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        logger.info(f"JWT_VERIFICATION: Token created for sub={subject}")
        return token


# Global verifier instance
_jwt_verifier: Optional[JWTVerifier] = None


def get_jwt_verifier() -> JWTVerifier:
    """Get or create global JWT verifier instance"""
    global _jwt_verifier
    if _jwt_verifier is None:
        _jwt_verifier = JWTVerifier()
    return _jwt_verifier


def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
    client_ip: Optional[str] = None,
) -> Dict[str, Any]:
    """
    FastAPI dependency for JWT verification.

    Usage:
        @router.get("/protected")
        async def protected_endpoint(payload: Dict[str, Any] = Depends(verify_token)):
            user_id = payload["sub"]
            ...

    Args:
        credentials: HTTPAuthorizationCredentials from FastAPI
        client_ip: Client IP address for DEBUG whitelist

    Returns:
        Decoded JWT payload

    Raises:
        HTTPException: If token is invalid (401)
    """
    verifier = get_jwt_verifier()
    return verifier.verify_token(credentials, client_ip=client_ip)


# Convenience function for manual token verification
def verify_token_string(token: str, client_ip: Optional[str] = None) -> Dict[str, Any]:
    """
    Verify a JWT token string manually.

    Args:
        token: JWT token string
        client_ip: Client IP address for DEBUG whitelist

    Returns:
        Decoded JWT payload

    Raises:
        HTTPException: If token is invalid
    """
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    return verify_token(credentials, client_ip=client_ip)
