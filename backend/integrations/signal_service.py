"""
Signal Service for ATOM Platform
Handles interaction with signal-cli-rest-api
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

class SignalService:
    def __init__(self):
        # signal-cli-rest-api base URL
        self.base_url = os.getenv("SIGNAL_API_URL", "http://localhost:8080")
        self.sender_number = os.getenv("SIGNAL_SENDER_NUMBER")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        # Start audit logging
        audit_ctx = log_integration_attempt("signal", "close", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("signal"):
                logger.warning(f"Circuit breaker is open for signal")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Signal integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("signal")
            if is_limited:
                logger.warning(f"Rate limit exceeded for signal")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for signal"
                )

        await self.client.aclose()

    async def send_message(self, recipient: str, text: str) -> bool:
        """Send a message via signal-cli-rest-api"""
        if not self.sender_number:
            logger.error("SIGNAL_SENDER_NUMBER not set")
            return False

        url = f"{self.base_url}/v1/send"
        
        # signal-cli-rest-api format
        data = {
            "message": text,
            "number": self.sender_number,
            "recipients": [recipient]
        }
        
        try:
            response = await self.client.post(url, json=data)
            response.raise_for_status()
            logger.info(f"Signal message sent to {recipient}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Signal message: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        # Start audit logging
        audit_ctx = log_integration_attempt("signal", "health_check", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("signal"):
                logger.warning(f"Circuit breaker is open for signal")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Signal integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("signal")
            if is_limited:
                logger.warning(f"Rate limit exceeded for signal")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for signal"
                )

        try:
            url = f"{self.base_url}/v1/about"
            response = await self.client.get(url)
            ok = response.status_code == 200
            return {
                "ok": ok,
                "status": "healthy" if ok else "unhealthy",
                "service": "signal",
                "timestamp": datetime.now().isoformat()
            }
        except Exception:
            return {
                "ok": False,
                "status": "down",
                "service": "signal",
                "timestamp": datetime.now().isoformat()
            }

# Singleton instance
signal_service = SignalService()

        # Start audit logging
        audit_ctx = log_integration_attempt("signal", "send_message", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("signal"):
                logger.warning(f"Circuit breaker is open for signal")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Signal integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("signal")
            if is_limited:
                logger.warning(f"Rate limit exceeded for signal")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for signal"
                )
