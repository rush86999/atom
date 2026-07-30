
import base64
import hmac
import hashlib
import json
import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import urlencode
from fastapi import HTTPException, Request
from pydantic import BaseModel

# OAuth state is signed (HMAC) so it cannot be forged. The previous code tried
# to import `backend.core.encryption` (a path that never resolves when running
# from inside backend/), fell back to PLAIN base64, and the callback trusted
# the state's user_id — so an attacker could craft state with a victim's
# user_id, run their own OAuth flow, and have the resulting tokens saved to the
# victim's account (a credential-planting IDOR). Now the state is
# base64(payload) + "." + base64(hmac), and decrypt_data verifies the HMAC.
_SECRET = os.getenv(
    "SECRET_KEY", os.getenv("UNIVERSAL_OAUTH_SECRET", "dev-universal-oauth-secret"),
).encode()


def _sign(payload_b64: str) -> str:
    return base64.urlsafe_b64encode(
        hmac.new(_SECRET, payload_b64.encode(), hashlib.sha256).digest()
    ).decode()


def encrypt_data(data: str) -> str:
    """Sign-then-encode: returns base64(payload).base64(hmac)."""
    payload_b64 = base64.urlsafe_b64encode(data.encode()).decode()
    return f"{payload_b64}.{_sign(payload_b64)}"


def decrypt_data(data: str) -> str:
    """Verify the HMAC and return the payload; raise on tamper/forge."""
    try:
        payload_b64, sig = data.split(".", 1)
    except ValueError:
        raise ValueError("Malformed OAuth state")
    expected = _sign(payload_b64)
    if not hmac.compare_digest(expected, sig):
        raise ValueError("Invalid OAuth state signature")
    return base64.urlsafe_b64decode(payload_b64.encode()).decode()


logger = logging.getLogger(__name__)

class OAuthState(BaseModel):
    integration_type: str  # 'native' or 'activepieces'
    service_id: str
    user_id: str
    redirect_path: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None

class UniversalAuthHandler:
    def __init__(self):
        self.app_domain = os.getenv("APP_DOMAIN", "localhost:3000")
        self.url_scheme = os.getenv("URL_SCHEME", "http")
        # Ensure domain doesn't have trailing slash
        if self.app_domain.endswith("/"):
            self.app_domain = self.app_domain[:-1]
            
        self.callback_url = f"{self.url_scheme}://{self.app_domain}/api/v1/integrations/universal/callback"

    def generate_oauth_url(self, 
                          auth_url: str, 
                          client_id: str, 
                          scopes: list, 
                          state_payload: OAuthState,
                          extra_params: Dict[str, str] = None) -> str:
        """
        Generates a standard OAuth 2.0 URL pointing to the provider,
        but with our Universal Callback URL as the redirect_uri.
        """
        # 1. Serialize and encrypt state
        state_json = state_payload.json()
        encrypted_state = encrypt_data(state_json)
        
        # 2. Construct params
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": self.callback_url,
            "scope": " ".join(scopes),
            "state": encrypted_state
        }
        
        if extra_params:
            params.update(extra_params)
            
        # 3. Build URL
        query_string = urlencode(params)
        return f"{auth_url}?{query_string}"

    async def handle_callback(self, code: str, state: str) -> Dict[str, Any]:
        """
        Processes the callback from the provider.
        Decodes state to determine which integration strategy to use for token exchange.
        """
        try:
            # 1. Decrypt state
            decrypted_state_json = decrypt_data(state)
            state_data = json.loads(decrypted_state_json)
            oauth_state = OAuthState(**state_data)
            
            logger.info(f"Processing callback for service: {oauth_state.service_id} ({oauth_state.integration_type})")
            
            # 2. Return info for the caller (API route) to handle the actual exchange
            # The API route will look up the client_secret and token_url based on service_id
            return {
                "code": code,
                "state": oauth_state,
                "callback_url": self.callback_url
            }
            
        except Exception as e:
            logger.error(f"Callback processing failed: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid OAuth state or callback data")

# Singleton instance
universal_auth = UniversalAuthHandler()
