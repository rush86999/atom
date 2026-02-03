import logging
import os
import time
from typing import Any, Dict, Optional
import httpx
from fastapi import Request
from jose import jwk, jwt
from jose.utils import base64url_decode

from core.communication.adapters.base import PlatformAdapter

logger = logging.getLogger(__name__)

class TeamsAdapter(PlatformAdapter):
    """
    Adapter for Microsoft Teams via Azure Bot Framework.
    """
    OPENID_METADATA_URL = "https://login.botframework.com/v1/.well-known/openidconfiguration"
    
    def __init__(self):
        self.app_id = os.getenv("MICROSOFT_APP_ID")
        self.app_password = os.getenv("MICROSOFT_APP_PASSWORD")
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
            # Decode JWT header to get key ID (kid)
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")

            if not kid:
                logger.error("JWT header missing 'kid' parameter")
                return False

            # Fetch JWKS keys from Microsoft
            keys = await self._get_jwks_keys()
            if not keys:
                logger.error("Failed to fetch JWKS keys from Microsoft")
                return False

            # Find matching key by kid
            public_key = None
            for key in keys:
                if key.get("kid") == kid:
                    try:
                        # Construct public key from JWK
                        public_key = jwk.construct(key).to_pem()
                        break
                    except Exception as e:
                        logger.error(f"Failed to construct public key from JWK: {e}")
                        return False

            if not public_key:
                logger.error(f"No matching JWK found for kid: {kid}")
                return False

            # Verify signature AND claims
            # Use RS256 algorithm (Microsoft's standard)
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=self.app_id,
                issuer=["https://api.botframework.com", "https://sts.windows.net/"]
            )

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
        
        # Channel ID is crucial for replies, but 'conversation.id' is what we send to.
        # But 'channelId' field tells us if it's 'msteams', 'slack', etc.
        # We need to store 'serviceUrl' and 'conversation.id' to reply.
        
        conversation_id = data.get("conversation", {}).get("id")
        service_url = data.get("serviceUrl")
        
        text = data.get("text", "")
        # Remove mentions if needed (Teams includes <at>Bot</at>)
        
        # We pack serviceUrl and conversation_id into metadata or channel_id
        # channel_id in Atom is a single string. We might need a composite key or use metadata.
        # Let's stringify the reply info into channel_id or use metadata lookup.
        # Strategy: Use conversation_id as channel_id. Store serviceUrl in metadata.
        
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
        # target_id -> conversation_id
        # metadata -> should contain serviceUrl
        
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
                
                # Reply to activity typically requires creating a new activity in the conversation
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
