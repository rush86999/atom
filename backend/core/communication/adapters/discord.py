import json
import logging
import os
from typing import Any, Dict, Optional
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import Request
import httpx

from core.communication.adapters.base import PlatformAdapter

logger = logging.getLogger(__name__)

class DiscordAdapter(PlatformAdapter):
    def __init__(self):
        self.public_key_hex = os.getenv("DISCORD_PUBLIC_KEY")
        self.bot_token = os.getenv("DISCORD_BOT_TOKEN")
        self.verify_key = None
        
        if self.public_key_hex:
            try:
                # Convert hex string to bytes
                self.verify_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(self.public_key_hex))
            except Exception as e:
                logger.error(f"Invalid DISCORD_PUBLIC_KEY: {e}")

    async def verify_request(self, request: Request, body_bytes: bytes) -> bool:
        if not self.verify_key:
            if os.getenv("ENVIRONMENT") == "development":
                logger.warning("DISCORD_PUBLIC_KEY not set, skipping verification (DEV ONLY)")
                return True
            return False

        signature = request.headers.get("X-Signature-Ed25519")
        timestamp = request.headers.get("X-Signature-Timestamp")

        if not signature or not timestamp:
            return False

        try:
            message = timestamp.encode() + body_bytes
            self.verify_key.verify(bytes.fromhex(signature), message)
            return True
        except (InvalidSignature, ValueError, Exception):
            return False

    def normalize_payload(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Normalize Discord Interaction payload.
        Handle PING (Type 1) and APPLICATION_COMMAND (Type 2).
        """
        interaction_type = payload.get("type")

        # Handle PING
        if interaction_type == 1:
            return {
                "type": "challenge",
                "response": {"type": 1} # Pong
            }
        
        # Handle Application Command or Message Component
        if interaction_type in [2, 3]: # COMMAND or COMPONENT
            # Extract user info (User is in 'member' for guild events, 'user' for DMs)
            member = payload.get("member", {})
            user_data = member.get("user") if member else payload.get("user")
            
            if not user_data:
                return None
            
            sender_id = user_data.get("id")
            username = user_data.get("username")
            channel_id = payload.get("channel_id")
            
            data = payload.get("data", {})
            
            # Extract content from options if it's a slash command argument
            content = ""
            if interaction_type == 2: # COMMAND
                options = data.get("options", [])
                if options:
                    content = options[0].get("value")
                else:
                    content = data.get("name", "command")
            
            elif interaction_type == 3: # COMPONENT (Button)
                custom_id = data.get("custom_id") # e.g., "approve_123"
                content = custom_id.replace("_", " ").upper() # Normalize to "APPROVE 123"
                
            return {
                "sender_id": sender_id,
                "username": username,
                "content": str(content),
                "channel_id": channel_id,
                "source": "discord",
                "raw_payload": payload,
                "is_interaction": (interaction_type == 3)
            }

        return None

    async def send_message(self, target_id: str, message: str, **kwargs) -> bool:
        """
        Send message to Discord Channel.
        target_id: Channel ID
        """
        if not self.bot_token:
            logger.error("DISCORD_BOT_TOKEN not set")
            return False

        url = f"https://discord.com/api/v10/channels/{target_id}/messages"
        headers = {
            "Authorization": f"Bot {self.bot_token}",
            "Content-Type": "application/json"
        }
        
        # Merge kwargs for advanced usage
        payload = {"content": message}
        if "embeds" in kwargs:
            payload["embeds"] = kwargs["embeds"]
        if "components" in kwargs:
            payload["components"] = kwargs["components"]

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return True
            except Exception as e:
                logger.error(f"Failed to send Discord message: {e}")
                return False

    async def send_approval_request(self, target_id: str, action_id: str, details: Dict[str, Any], priority: str) -> bool:
        """Send interactive approval request using Discord Embeds and Buttons"""
        if not self.bot_token:
            return False
            
        embed = {
            "title": "🚨 HITL Approval Required",
            "description": f"**Action:** {details.get('action_type')}\n**Reason:** {details.get('reason')}",
            "color": 0xFF0000 if priority == "URGENT" else 0xFFFF00,
            "fields": [
                {"name": "Priority", "value": priority, "inline": True},
                {"name": "Action ID", "value": f"`{action_id}`", "inline": True}
            ],
            "timestamp": datetime.now().isoformat()
        }
        
        components = [
            {
                "type": 1, # Action Row
                "components": [
                    {
                        "type": 2, # Button
                        "label": "Approve",
                        "style": 3, # Success (Green)
                        "custom_id": f"approve_{action_id}"
                    },
                    {
                        "type": 2, # Button
                        "label": "Reject",
                        "style": 4, # Danger (Red)
                        "custom_id": f"reject_{action_id}"
                    }
                ]
            }
        ]
        
        return await self.send_message(target_id, "", embeds=[embed], components=components)

    async def send_direct_message(self, target_id: str, message: str, agent_name: Optional[str] = None) -> bool:
        """Send a proactive message from a specific agent"""
        prefix = f"**[{agent_name}]** " if agent_name else ""
        return await self.send_message(target_id, f"{prefix}{message}")
