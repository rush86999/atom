"""
Messenger Service for ATOM Platform
Handles Facebook Messenger Messaging API interactions
"""

from datetime import datetime
import logging
import os
from typing import Any, Dict, Optional
import httpx
from core.circuit_breaker import circuit_breaker
from core.rate_limiter import rate_limiter, should_retry, calculate_backoff
from core.audit_logger import log_integration_call, log_integration_error, log_integration_attempt, log_integration_complete
from fastapi import HTTPException


logger = logging.getLogger(__name__)

class MessengerService:
    def __init__(self):
        self.page_access_token = os.getenv("MESSENGER_PAGE_ACCESS_TOKEN")
        self.api_version = os.getenv("MESSENGER_API_VERSION", "v19.0")
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        # Start audit logging
        audit_ctx = log_integration_attempt("messenger", "close", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("messenger"):
                logger.warning(f"Circuit breaker is open for messenger")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Messenger integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("messenger")
            if is_limited:
                logger.warning(f"Rate limit exceeded for messenger")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for messenger"
                )

        await self.client.aclose()

    async def send_message(self, recipient_id: str, text: str) -> bool:
        """Send a message via Facebook Messenger Send API"""
        if not self.page_access_token:
            logger.error("MESSENGER_PAGE_ACCESS_TOKEN not set")
            return False

        url = f"{self.base_url}/me/messages"
        params = {"access_token": self.page_access_token}
        
        data = {
            "recipient": {"id": recipient_id},
            "message": {"text": text}
        }
        
        try:
            response = await self.client.post(url, params=params, json=data)
            response.raise_for_status()
            logger.info(f"Messenger message sent to {recipient_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Messenger message: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        # Start audit logging
        audit_ctx = log_integration_attempt("messenger", "health_check", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("messenger"):
                logger.warning(f"Circuit breaker is open for messenger")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Messenger integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("messenger")
            if is_limited:
                logger.warning(f"Rate limit exceeded for messenger")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for messenger"
                )

        return {
            "ok": True,
            "status": "healthy" if self.page_access_token else "degraded",
            "service": "messenger",
            "timestamp": datetime.now().isoformat()
        }

# Singleton instance
messenger_service = MessengerService()

        # Start audit logging
        audit_ctx = log_integration_attempt("messenger", "send_message", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("messenger"):
                logger.warning(f"Circuit breaker is open for messenger")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Messenger integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("messenger")
            if is_limited:
                logger.warning(f"Rate limit exceeded for messenger")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for messenger"
                )
