"""
Twilio Service for ATOM Platform
Provides comprehensive Twilio SMS and voice communication integration functionality
"""

import base64
from datetime import datetime
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
import httpx

logger = logging.getLogger(__name__)

class TwilioService:
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.phone_number = os.getenv("TWILIO_PHONE_NUMBER")
        self.base_url = f"https://api.twilio.com/2010-04-01"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        credentials = f"{self.account_sid}:{self.auth_token}"
        b64_credentials = base64.b64encode(credentials.encode()).decode()
        
        return {
            "Authorization": f"Basic {b64_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

    async def send_sms(
        self,
        to: str,
        body: str,
        from_number: str = None
    ) -> Dict[str, Any]:
        """Send an SMS message"""
        try:
            if not self.account_sid or not self.auth_token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            sender = from_number or self.phone_number
            
            if not sender:
                raise HTTPException(status_code=400, detail="No sender phone number configured")
            
            data = {
                "To": to,
                "From": sender,
                "Body": body
            }
            
            url = f"{self.base_url}/Accounts/{self.account_sid}/Messages.json"
            
            response = await self.client.post(url, headers=headers, data=data)
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to send SMS: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to send SMS: {str(e)}"
            )

    async def get_messages(
        self,
        to: str = None,
        from_number: str = None,
        page_size: int = 50
    ) -> List[Dict[str, Any]]:
        """Get message list"""
        try:
            if not self.account_sid or not self.auth_token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            params = {"PageSize": page_size}
            
            if to:
                params["To"] = to
            if from_number:
                params["From"] = from_number
            
            url = f"{self.base_url}/Accounts/{self.account_sid}/Messages.json"
            
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            return data.get("messages", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get messages: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get messages: {str(e)}"
            )

    async def make_call(
        self,
        to: str,
        twiml_url: str,
        from_number: str = None
    ) -> Dict[str, Any]:
        """Make a voice call"""
        try:
            if not self.account_sid or not self.auth_token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            sender = from_number or self.phone_number
            
            if not sender:
                raise HTTPException(status_code=400, detail="No sender phone number configured")
            
            data = {
                "To": to,
                "From": sender,
                "Url": twiml_url
            }
            
            url = f"{self.base_url}/Accounts/{self.account_sid}/Calls.json"
            
            response = await self.client.post(url, headers=headers, data=data)
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to make call: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to make call: {str(e)}"
            )

    async def get_calls(
        self,
        to: str = None,
        from_number: str = None,
        page_size: int = 50
    ) -> List[Dict[str, Any]]:
        """Get call list"""
        try:
            if not self.account_sid or not self.auth_token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            params = {"PageSize": page_size}
            
            if to:
                params["To"] = to
            if from_number:
                params["From"] = from_number
            
            url = f"{self.base_url}/Accounts/{self.account_sid}/Calls.json"
            
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            return data.get("calls", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get calls: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get calls: {str(e)}"
            )

    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        try:
            if not self.account_sid or not self.auth_token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            url = f"{self.base_url}/Accounts/{self.account_sid}.json"
            
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get account info: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get account info: {str(e)}"
            )

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Twilio service"""
        try:
            return {
                "ok": True,
                "status": "healthy",
                "service": "twilio",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unhealthy",
                "service": "twilio",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

# Singleton instance
twilio_service = TwilioService()

def get_twilio_service() -> TwilioService:
    """Get Twilio service instance"""
    return twilio_service
