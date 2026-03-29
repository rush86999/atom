import logging
import os
import httpx
import time
import hashlib
import hmac
from typing import Dict, Any, Optional
from fastapi import Request
from jose import jwt, jwk
from jose.utils import base64url_decode

from core.communication.adapters.base import PlatformAdapter

logger = logging.getLogger(__name__)

# Replay attack prevention - store seen JWT IDs (jti) with timestamp
# In production, use Redis for distributed systems
_seen_jwt_ids = {}  # {jti: timestamp}
JWT_ID_CACHE_TTL = 300  # 5 minutes
MAX_TIMESTAMP_AGE = 300  # 5 minutes

class TeamsAdapter(PlatformAdapter):
    """
    Adapter for Microsoft Teams via Azure Bot Framework.
    """
    OPENID_METADATA_URL = "https://login.botframework.com/v1/.well-known/openidconfiguration"
    
    def __init__(
        self,
        app_id: Optional[str] = None,
        app_password: Optional[str] = None,
    ):
        self.app_id = app_id or os.getenv("MICROSOFT_APP_ID")
        self.app_password = app_password or os.getenv("MICROSOFT_APP_PASSWORD")
        self.jwks_keys = None
        self.jwks_expiry = 0
        self._access_token = None
        self._token_expiry = 0

    async def _get_jwks_keys(self):
        """Fetch and cache Microsoft's JWKS keys."""
        if self.jwks_keys and time.time() < self.jwks_expiry:
            return self.jwks_keys
            
        try:
            async with httpx.AsyncClient() as client:
                # 1. Get OpenID Config
                resp = await client.get(self.OPENID_METADATA_URL)
                resp.raise_for_status()
                config = resp.json()
                jwks_uri = config["jwks_uri"]
                
                # 2. Get Keys
                keys_resp = await client.get(jwks_uri)
                keys_resp.raise_for_status()
                keys_data = keys_resp.json()
                
                self.jwks_keys = keys_data["keys"]
                self.jwks_expiry = time.time() + 86400 # Cache for 24h
                return self.jwks_keys
        except Exception as e:
            logger.error(f"Failed to fetch Microsoft JWKS: {e}")
            return []

    async def _get_bot_access_token(self) -> Optional[str]:
        """Get OAuth2 Access Token for the Bot."""
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token
            
        if not self.app_id or not self.app_password:
            return None
            
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "grant_type": "client_credentials",
                    "client_id": self.app_id,
                    "client_secret": self.app_password,
                    "scope": "https://api.botframework.com/.default"
                }
                resp = await client.post(
                    "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token", 
                    data=payload
                )
                resp.raise_for_status()
                data = resp.json()
                self._access_token = data["access_token"]
                self._token_expiry = time.time() + data.get("expires_in", 3500)
                return self._access_token
        except Exception as e:
            logger.error(f"Failed to get Microsoft Bot Token: {e}")
            return None

    async def verify_request(self, request: Request, body_bytes: bytes) -> bool:
        if not self.app_id:
            # Check dev mode
            if os.getenv("ENVIRONMENT") == "development":
                return True
            return False

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False
            
        token = auth_header.split(" ")[1]
        
        try:
            # Decode header to get key ID (kid)
            header = jwt.get_unverified_header(token)
            kid = header.get('kid')

            if not kid:
                logger.error("Teams token missing 'kid' in header")
                return False

            keys = await self._get_jwks_keys()
            if not keys:
                logger.error("Failed to fetch JWKS keys from Microsoft")
                return False

            # Find matching key
            public_key = None
            for key in keys:
                if key.get('kid') == kid:
                    try:
                        # Construct public key from JWK using python-jose
                        public_key = jwk.construct(key).to_pem()
                        break
                    except Exception as e:
                        logger.error(f"Failed to construct public key from JWK: {e}")
                        return False

            if not public_key:
                logger.error(f"No matching JWKS key found for kid: {kid}")
                return False

            # Verify signature AND claims
            # Use RS256 algorithm (Microsoft's standard)
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=self.app_id,
                # Microsoft uses multiple issuers depending on version/endpoint
                issuer=["https://api.botframework.com", "https://sts.windows.net/"]
            )

            # Additional verification: check token expiry
            current_time = time.time()
            if claims.get("exp", 0) < current_time:
                logger.error("Teams token expired")
                return False

            # Check issued-at timestamp (iat) to prevent replay attacks
            iat = claims.get("iat")
            if iat:
                if abs(current_time - iat) > MAX_TIMESTAMP_AGE:
                    logger.error(f"Token issued too long ago: {current_time - iat}s ago (max {MAX_TIMESTAMP_AGE}s)")
                    return False

            # Replay attack prevention - check JWT ID (jti)
            jti = claims.get("jti")
            if jti:
                global _seen_jwt_ids
                # Clean up old entries from cache
                _seen_jwt_ids = {
                    k: v for k, v in _seen_jwt_ids.items()
                    if current_time - v < JWT_ID_CACHE_TTL
                }

                # Check if this JWT ID has been seen before
                if jti in _seen_jwt_ids:
                    logger.warning(f"Replay attack detected: JWT ID {jti} already seen")
                    return False

                # Mark this JWT ID as seen
                _seen_jwt_ids[jti] = current_time

            logger.info(f"JWT verified successfully for app: {claims.get('aud')}")
            return True

        except jwt.ExpiredSignatureError:
            logger.error("Teams Token Verification Failed: Token expired")
            return False
        except jwt.JWTError as e:
            logger.error(f"Teams Token Verification Failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Teams Token Verification Failed: {e}")
            return False

    def verify_webhook_signature(self, payload: bytes, signature: str, timestamp: str) -> bool:
        """
        Verify Microsoft Teams webhook signature for security (HMAC fallback).
        """
        try:
            current_time = time.time()
            try:
                webhook_time = float(timestamp)
                if abs(current_time - webhook_time) > MAX_TIMESTAMP_AGE:
                    logger.warning(f"Webhook timestamp too old: {current_time - webhook_time}s ago")
                    return False
            except (ValueError, TypeError):
                return False

            if not signature or not self.app_password:
                return False

            # Remove prefix
            if signature.startswith("Bearer "):
                signature = signature[7:]
            elif signature.startswith("HMAC "):
                signature = signature[5:]

            message = f"{timestamp}.{payload.decode('utf-8', errors='ignore')}"
            expected_hmac = hmac.new(
                self.app_password.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).digest()

            try:
                provided_hmac = base64url_decode(signature)
            except Exception:
                return False

            return hmac.compare_digest(expected_hmac, provided_hmac)

        except Exception as e:
            logger.error(f"Webhook signature verification error: {e}")
            return False

    async def normalize_payload(self, request: Request, body_bytes: bytes) -> Dict[str, Any]:
        """
        Normalize Microsoft Bot Framework Activity.
        """
        import json
        try:
            data = json.loads(body_bytes)
        except json.JSONDecodeError:
            return {}

        activity_type = data.get("type")
        if activity_type != "message":
            return {}
            
        user_id = data.get("from", {}).get("id")
        user_name = data.get("from", {}).get("name")
        conversation_id = data.get("conversation", {}).get("id")
        service_url = data.get("serviceUrl")
        text = data.get("text", "")
        
        return {
            "platform": "teams",
            "user_id": user_id,
            "username": user_name,
            "channel_id": conversation_id, 
            "content": text,
            "metadata": {
                "serviceUrl": service_url,
                "activityId": data.get("id"),
                "full_data": data
            }
        }

    async def send_message(self, target_id: str, message: str, metadata: Dict = None) -> bool:
        if not metadata or "serviceUrl" not in metadata:
            logger.error("Teams reply requires serviceUrl in metadata.")
            return False
            
        service_url = metadata["serviceUrl"]
        token = await self._get_bot_access_token()
        if not token:
            return False
            
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
                
                url = f"{service_url.rstrip('/')}/v3/conversations/{target_id}/activities"
                payload = {
                    "type": "message",
                    "text": message
                }
                
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to send Teams message: {e}")
            return False
