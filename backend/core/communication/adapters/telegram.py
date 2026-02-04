import logging
import os
from typing import Any, Dict, Optional
import httpx
from fastapi import Request

from core.communication.adapters.base import PlatformAdapter

logger = logging.getLogger(__name__)

class TelegramAdapter(PlatformAdapter):
    """
    Adapter for Telegram Bot API.
    """
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.secret_token = os.getenv("TELEGRAM_SECRET_TOKEN") # For verification
        self.api_base = f"https://api.telegram.org/bot{self.bot_token}"

    async def verify_request(self, request: Request, body_bytes: bytes) -> bool:
        if not self.secret_token:
             # If no secret token configured, we skip verification (Dev) or fail (Prod)
             # Ideally Telegram sets X-Telegram-Bot-Api-Secret-Token
             return True
             
        header_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if header_token == self.secret_token:
            return True
        return False

    async def normalize_payload(self, request: Request, body_bytes: bytes) -> Dict[str, Any]:
        """
        Normalize standard Telegram JSON update.
        """
        import json
        try:
            data = json.loads(body_bytes)
        except json.JSONDecodeError:
            return {}
            
        # We handle 'message' updates
        message = data.get("message", {})
        
        user_id = str(message.get("from", {}).get("id", ""))
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "")
        
        # Detect Voice
        if "voice" in message:
            text = "[Voice Message]"
            data["media_id"] = message["voice"]["file_id"]
            data["media_type"] = "voice"
        
        # Handle username for nice logs
        username = message.get("from", {}).get("username", "")
        
        return {
            "platform": "telegram",
            "user_id": user_id,
            "username": username,
            "channel_id": chat_id, # Can be DM or Group
            "content": text,
            "metadata": data
        }

    async def send_message(self, target_id: str, message: str, metadata: Dict = None) -> bool:
        if not self.bot_token:
            logger.error("Telegram token not set.")
            return False
            
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "chat_id": target_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }
                response = await client.post(f"{self.api_base}/sendMessage", json=payload)
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    async def get_media(self, media_id: str) -> Optional[bytes]:
        """Downloads voice/file from Telegram."""
        if not self.bot_token:
            return None
        try:
            async with httpx.AsyncClient() as client:
                # 1. Get file path
                res = await client.get(f"{self.api_base}/getFile", params={"file_id": media_id})
                res.raise_for_status()
                file_path = res.json().get("result", {}).get("file_path")
                if not file_path:
                    return None
                
                # 2. Download
                download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
                media_res = await client.get(download_url)
                media_res.raise_for_status()
                return media_res.content
        except Exception as e:
            logger.error(f"Telegram media download failed: {e}")
            return None
