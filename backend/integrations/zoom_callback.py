"""
Zoom OAuth Callback with PKCE Support
Handles Zoom OAuth 2.0 authorization code flow with PKCE for enhanced security
"""

import os
import hashlib
import base64
import secrets
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import httpx
from fastapi import HTTPException
from loguru import logger

# Import services
from zoom_service import ZoomService
from core.token_storage import token_storage

logger = logging.getLogger(__name__)

class ZoomOAuthCallback:
    """Enhanced Zoom OAuth callback handler with PKCE support"""

    def __init__(self):
        self.zoom_service = ZoomService()
        self.code_verifier_timeout = 600  # 10 minutes
        self.state_timeout = 600  # 10 minutes

    def generate_pkce_challenge(self) -> Dict[str, str]:
        """Generate PKCE code verifier and challenge"""
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

        # Create code challenge
        sha256_hash = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(sha256_hash).decode('utf-8').rstrip('=')

        # Store code verifier temporarily (in production, use Redis or secure storage)
        # For now, we'll include it in the state parameter for simplicity
        return {
            'code_verifier': code_verifier,
            'code_challenge': code_challenge,
            'challenge_method': 'S256'
        }

    def get_oauth_url(
        self,
        redirect_uri: str,
        state: Optional[str] = None,
        use_pkce: bool = True
    ) -> str:
        """Generate OAuth authorization URL with optional PKCE"""

        if not state:
            state = secrets.token_urlsafe(32)

        params = {
            "response_type": "code",
            "client_id": self.zoom_service.client_id,
            "redirect_uri": redirect_uri,
            "state": state
        }

        # Add PKCE parameters if enabled
        if use_pkce:
            pkce_data = self.generate_pkce_challenge()
            params.update({
                "code_challenge": pkce_data['code_challenge'],
                "code_challenge_method": pkce_data['challenge_method']
            })

            # In production, store the code_verifier securely associated with the state
            # For now, we'll include a hash of it in the state
            verifier_hash = hashlib.sha256(pkce_data['code_verifier'].encode()).hexdigest()[:16]
            enhanced_state = f"{state}_{verifier_hash}"
            params['state'] = enhanced_state

            # Store the code verifier (in production, use secure storage)
            self._store_code_verifier(enhanced_state, pkce_data['code_verifier'])

        # Build authorization URL
        auth_url = f"{self.zoom_service.auth_url}?" + "&".join([f"{k}={v}" for k, v in params.items()])

        logger.info(f"Generated Zoom OAuth URL with PKCE: {use_pkce}")
        return auth_url

    def _store_code_verifier(self, state: str, code_verifier: str):
        """Store code verifier temporarily (in production, use Redis/secure storage)"""
        # For development, we can use a simple file-based storage
        # In production, this should be replaced with Redis or secure database
        storage_data = {
            'code_verifier': code_verifier,
            'timestamp': datetime.utcnow().isoformat(),
            'state': state
        }

        try:
            # Create a temporary storage directory if it doesn't exist
            storage_dir = '/tmp/zoom_oauth'
            os.makedirs(storage_dir, exist_ok=True)

            # Store the code verifier
            storage_file = os.path.join(storage_dir, f"code_verifier_{state}.json")
            with open(storage_file, 'w') as f:
                json.dump(storage_data, f)

            logger.info(f"Stored code verifier for state: {state}")

        except Exception as e:
            logger.error(f"Failed to store code verifier: {e}")
            raise HTTPException(status_code=500, detail="Failed to store OAuth state")

    def _retrieve_code_verifier(self, state: str) -> Optional[str]:
        """Retrieve code verifier from temporary storage"""
        try:
            storage_file = f'/tmp/zoom_oauth/code_verifier_{state}.json'

            if not os.path.exists(storage_file):
                logger.warning(f"Code verifier not found for state: {state}")
                return None

            with open(storage_file, 'r') as f:
                storage_data = json.load(f)

            # Check if the verifier has expired
            stored_time = datetime.fromisoformat(storage_data['timestamp'])
            if datetime.utcnow() - stored_time > timedelta(seconds=self.code_verifier_timeout):
                logger.warning(f"Code verifier expired for state: {state}")
                os.remove(storage_file)  # Clean up expired file
                return None

            # Clean up the storage file
            os.remove(storage_file)

            logger.info(f"Retrieved code verifier for state: {state}")
            return storage_data['code_verifier']

        except Exception as e:
            logger.error(f"Failed to retrieve code verifier: {e}")
            return None

    async def exchange_code_for_token(
        self,
        code: str,
        redirect_uri: str,
        state: str,
        use_pkce: bool = True
    ) -> Dict[str, Any]:
        """Exchange authorization code for access token with optional PKCE"""

        try:
            token_data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri
            }

            # Add PKCE code verifier if available
            if use_pkce:
                code_verifier = self._retrieve_code_verifier(state)
                if code_verifier:
                    token_data["code_verifier"] = code_verifier
                    logger.info("Using PKCE code verifier for token exchange")
                else:
                    logger.warning("PKCE code verifier not found, proceeding without it")

            # Make token request
            headers = {
                "Authorization": f"Basic {self._get_basic_auth()}",
                "Content-Type": "application/x-www-form-urlencoded"
            }

            async with self.zoom_service.client.post(
                self.zoom_service.token_url,
                headers=headers,
                data=token_data
            ) as response:
                if response.status_code == 200:
                    token_data = response.json()

                    # Validate token response
                    if not self._validate_token_response(token_data):
                        raise HTTPException(status_code=400, detail="Invalid token response")

                    # Store tokens securely
                    await self._store_tokens(token_data, state)

                    logger.info(f"Successfully exchanged code for tokens for state: {state}")
                    return {
                        "success": True,
                        "access_token": token_data["access_token"],
                        "refresh_token": token_data.get("refresh_token"),
                        "expires_in": token_data.get("expires_in", 3600),
                        "token_type": token_data.get("token_type", "Bearer"),
                        "scope": token_data.get("scope", ""),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                else:
                    error_text = response.text
                    logger.error(f"Token exchange failed: {response.status_code} - {error_text}")
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Token exchange failed: {error_text}"
                    )

        except Exception as e:
            logger.error(f"Error exchanging code for token: {e}")
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=f"Token exchange failed: {str(e)}")

    def _get_basic_auth(self) -> str:
        """Get basic auth token for token exchange"""
        if not self.zoom_service.client_id or not self.zoom_service.client_secret:
            raise HTTPException(status_code=500, detail="Zoom OAuth credentials not configured")

        credentials = f"{self.zoom_service.client_id}:{self.zoom_service.client_secret}"
        return base64.b64encode(credentials.encode()).decode()

    def _validate_token_response(self, token_data: Dict[str, Any]) -> bool:
        """Validate token response from Zoom"""
        required_fields = ["access_token"]

        for field in required_fields:
            if field not in token_data:
                logger.error(f"Missing required field in token response: {field}")
                return False

        # Additional validation
        if not token_data["access_token"]:
            logger.error("Empty access token in response")
            return False

        return True

    async def _store_tokens(self, token_data: Dict[str, Any], state: str):
        """Store tokens securely using token storage service"""
        try:
            # Prepare token data for storage
            stored_token_data = {
                "access_token": token_data["access_token"],
                "refresh_token": token_data.get("refresh_token"),
                "expires_in": token_data.get("expires_in", 3600),
                "token_type": token_data.get("token_type", "Bearer"),
                "scope": token_data.get("scope", ""),
                "state": state,
                "timestamp": datetime.utcnow().isoformat(),
                "service": "zoom"
            }

            # Calculate expiry time
            if "expires_in" in token_data:
                expiry_time = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
                stored_token_data["expires_at"] = expiry_time.isoformat()

            # Store using token storage service
            token_storage.save_token("zoom", stored_token_data)

            logger.info(f"Successfully stored Zoom tokens for state: {state}")

        except Exception as e:
            logger.error(f"Failed to store tokens: {e}")
            raise HTTPException(status_code=500, detail="Failed to store tokens")

    async def refresh_tokens(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access tokens"""
        try:
            token_data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            }

            headers = {
                "Authorization": f"Basic {self._get_basic_auth()}",
                "Content-Type": "application/x-www-form-urlencoded"
            }

            async with self.zoom_service.client.post(
                self.zoom_service.token_url,
                headers=headers,
                data=token_data
            ) as response:
                if response.status_code == 200:
                    new_token_data = response.json()

                    # Store new tokens
                    await self._store_tokens(new_token_data, "refresh")

                    return {
                        "success": True,
                        "access_token": new_token_data["access_token"],
                        "refresh_token": new_token_data.get("refresh_token"),
                        "expires_in": new_token_data.get("expires_in", 3600)
                    }
                else:
                    error_text = response.text
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Token refresh failed: {error_text}"
                    )

        except Exception as e:
            logger.error(f"Error refreshing tokens: {e}")
            raise HTTPException(status_code=500, detail=f"Token refresh failed: {str(e)}")

    async def revoke_token(self, access_token: str) -> Dict[str, Any]:
        """Revoke access token"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            async with self.zoom_service.client.post(
                f"{self.zoom_service.base_url}/users/me/tokens/revoke",
                headers=headers
            ) as response:
                if response.status_code == 204:
                    logger.info("Successfully revoked Zoom token")
                    return {"success": True, "message": "Token revoked successfully"}
                else:
                    error_text = response.text
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Token revocation failed: {error_text}"
                    )

        except Exception as e:
            logger.error(f"Error revoking token: {e}")
            raise HTTPException(status_code=500, detail=f"Token revocation failed: {str(e)}")


# Global callback handler instance
zoom_oauth_callback = ZoomOAuthCallback()

# Utility functions
def get_zoom_oauth_callback() -> ZoomOAuthCallback:
    """Get Zoom OAuth callback handler instance"""
    return zoom_oauth_callback