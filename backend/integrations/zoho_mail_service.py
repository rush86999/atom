import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class ZohoMailService:
    """Zoho Mail API Service Implementation"""
    
    def __init__(self):
        self.base_url = "https://mail.zoho.com/api/v1"
        self.client_id = os.getenv("ZOHO_CLIENT_ID")
        self.client_secret = os.getenv("ZOHO_CLIENT_SECRET")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_accounts(self, access_token: str) -> List[Dict[str, Any]]:
        """Get Zoho Mail accounts"""
        try:
            url = f"{self.base_url}/accounts"
            headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except Exception as e:
            logger.error(f"Failed to fetch Zoho Mail accounts: {e}")
            return []

    async def get_messages(self, access_token: str, account_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch recent messages for a specific account"""
        try:
            # We look at the 'inbox' folder by default (folderId: 1 usually)
            url = f"{self.base_url}/accounts/{account_id}/messages/view"
            headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
            params = {"limit": limit}
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except Exception as e:
            logger.error(f"Failed to fetch Zoho Mail messages: {e}")
            return []

    async def get_recent_inbox(self, access_token: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch messages from the primary account's inbox"""
        try:
            accounts = await self.get_accounts(access_token)
            if not accounts:
                return []
            
            # Use the first account (primary)
            account_id = accounts[0].get("accountId")
            return await self.get_messages(access_token, account_id, limit=limit)
        except Exception as e:
            logger.error(f"Failed to fetch recent Zoho Mail: {e}")
            return []
