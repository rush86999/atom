from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from fastapi import Request


class PlatformAdapter(ABC):
    """
    Abstract base class for Communication Platform Adapters.
    Handles platform-specific verification, normalization, and sending.
    """
    
    @abstractmethod
    async def verify_request(self, request: Request, body_bytes: bytes) -> bool:
        """Verify the authenticity of the incoming webhook request"""
        pass

    @abstractmethod
    def normalize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert platform-specific payload to standard Atom format:
        {
            "sender_id": str,
            "content": str,
            "channel_id": str,
            "metadata": dict
        }
        Returns None if message should be ignored (e.g. bot message).
        """
        pass

    @abstractmethod
    async def send_message(self, target_id: str, message: str, **kwargs) -> bool:
        """Send an outbound message to this platform"""
        pass

    async def send_approval_request(self, target_id: str, action_id: str, details: Dict[str, Any], priority: str) -> bool:
        """
        Send an interactive approval request (Approve/Reject buttons).
        Default implementation falls back to plain text send_message.
        """
        message = f"🚨 *HITL Approval Required* ({priority})\nAction: {details.get('action_type')}\nReason: {details.get('reason')}\nAction ID: {action_id}\n\nPlease reply with 'APPROVE {action_id}' or 'REJECT {action_id}'"
        return await self.send_message(target_id, message)

    async def send_direct_message(self, target_id: str, message: str, agent_name: Optional[str] = None) -> bool:
        """
        Send a proactive message from a specific agent.
        Default implementation falls back to plain text send_message.
        """
        prefix = f"[{agent_name}] " if agent_name else ""
        return await self.send_message(target_id, f"{prefix}{message}")

    async def get_media(self, media_id: str) -> Optional[bytes]:
        """Optional: Download media (audio/voice) from the platform."""
        return None

class GenericAdapter(PlatformAdapter):
    """Fallback adapter for generic webhooks (no verification by default)"""
    
    async def verify_request(self, request: Request, body_bytes: bytes) -> bool:
        return True # MVP: Open generic webhook
        
    def normalize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "sender_id": payload.get("sender_id", "unknown"),
            "content": payload.get("message") or payload.get("content", ""),
            "channel_id": payload.get("channel_id"),
            "metadata": payload
        }
        
    async def send_message(self, target_id: str, message: str, **kwargs) -> bool:
        # Generic has no outbound capability usually, or just logs
        return True
