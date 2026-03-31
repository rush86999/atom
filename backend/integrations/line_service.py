"""
Line Service for ATOM Platform
Handles Line Messaging API interactions
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

class LineService:
    def __init__(self):
        # Line uses Channel Access Token
        self.channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        self.base_url = "https://api.line.me/v2/bot/message"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        # Start audit logging
        audit_ctx = log_integration_attempt("line", "close", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("line"):
                logger.warning(f"Circuit breaker is open for line")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Line integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("line")
            if is_limited:
                logger.warning(f"Rate limit exceeded for line")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for line"
                )

        await self.client.aclose()

    async def send_message(self, to: str, text: str) -> bool:
        """Send a push message via Line Messaging API"""
        if not self.channel_access_token:
            logger.error("LINE_CHANNEL_ACCESS_TOKEN not set")
            return False

        url = f"{self.base_url}/push"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.channel_access_token}"
        }
        
        data = {
            "to": to,
            "messages": [
                {
                    "type": "text",
                    "text": text
                }
            ]
        }
        
        try:
            response = await self.client.post(url, headers=headers, json=data)
            response.raise_for_status()
            logger.info(f"Line message pushed to {to}")
            return True
        except Exception as e:
            logger.error(f"Failed to push Line message: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        # Start audit logging
        audit_ctx = log_integration_attempt("line", "health_check", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("line"):
                logger.warning(f"Circuit breaker is open for line")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Line integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("line")
            if is_limited:
                logger.warning(f"Rate limit exceeded for line")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for line"
                )

        return {
            "ok": True,
            "status": "healthy" if self.channel_access_token else "degraded",
            "service": "line",
            "timestamp": datetime.now().isoformat()
        }

# Singleton instance
line_service = LineService()

        # Start audit logging
        audit_ctx = log_integration_attempt("line", "send_message", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("line"):
                logger.warning(f"Circuit breaker is open for line")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Line integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("line")
            if is_limited:
                logger.warning(f"Rate limit exceeded for line")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for line"
                )
