import logging
import os
import httpx
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from core.models import IntegrationToken

logger = logging.getLogger(__name__)

class ZohoOAuthService:
    """
    Core service for Zoho OAuth 2.0 flow.
    Handles token exchange, refresh, and intelligent DC (api_domain) discovery.
    """
    
    DEFAULT_TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"

    @staticmethod
    async def exchange_code_for_token(
        db: Session, 
        code: str, 
        tenant_id: str,
        api_domain: Optional[str] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Exchanges authorization code for tokens and persists with DC discovery.
        """
        # 1. Resolve Instance URL (Multi-DC Auto-Detection)
        instance_url = api_domain or location or os.getenv("ZOHO_DEFAULT_API_DOMAIN", "https://www.zohoapis.com")
        if not instance_url.startswith("http"):
            instance_url = f"https://{instance_url}"

        # 2. Exchange Code
        data = {
            "grant_type": "authorization_code",
            "client_id": os.getenv("ZOHO_CLIENT_ID"),
            "client_secret": os.getenv("ZOHO_CLIENT_SECRET"),
            "redirect_uri": os.getenv("ZOHO_REDIRECT_URI"),
            "code": code
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(ZohoOAuthService.DEFAULT_TOKEN_URL, data=data)
                response.raise_for_status()
                token_data = response.json()
                
                # 3. Persist Token
                token_record = db.query(IntegrationToken).filter(
                    IntegrationToken.tenant_id == tenant_id,
                    IntegrationToken.provider == "zoho"
                ).first()
                
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 3600))
                
                if token_record:
                    token_record.access_token = token_data.get("access_token")
                    token_record.refresh_token = token_data.get("refresh_token") or token_record.refresh_token
                    token_record.expires_at = expires_at
                    token_record.instance_url = instance_url
                    token_record.last_used_at = datetime.now(timezone.utc)
                else:
                    token_record = IntegrationToken(
                        tenant_id=tenant_id,
                        provider="zoho",
                        access_token=token_data.get("access_token"),
                        refresh_token=token_data.get("refresh_token"),
                        expires_at=expires_at,
                        instance_url=instance_url,
                        token_type="Bearer",
                        status="active"
                    )
                    db.add(token_record)
                
                db.commit()
                return {
                    "success": True, 
                    "instance_url": instance_url, 
                    "expires_at": expires_at.isoformat()
                }
                
        except Exception as e:
            logger.error(f"Zoho OAuth exchange failed: {e}")
            raise ValueError(f"Failed to exchange Zoho code: {str(e)}")

    @staticmethod
    async def refresh_token(db: Session, token_record: IntegrationToken) -> Optional[str]:
        """Refreshes the Zoho token using the DC-specific or global accounts URL."""
        if not token_record.refresh_token:
            return None
            
        data = {
            "grant_type": "refresh_token",
            "client_id": os.getenv("ZOHO_CLIENT_ID"),
            "client_secret": os.getenv("ZOHO_CLIENT_SECRET"),
            "refresh_token": token_record.refresh_token
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(ZohoOAuthService.DEFAULT_TOKEN_URL, data=data)
                response.raise_for_status()
                res_data = response.json()
                
                token_record.access_token = res_data["access_token"]
                token_record.expires_at = datetime.now(timezone.utc) + timedelta(seconds=res_data.get("expires_in", 3600))
                db.commit()
                return token_record.access_token
        except Exception as e:
            logger.error(f"Zoho token refresh failed: {e}")
            return None
