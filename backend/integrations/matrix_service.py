"""
Matrix Service for ATOM Platform
Simple Matrix client implementation for sending messages
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

class MatrixService:
    def __init__(self):
        self.homeserver = os.getenv("MATRIX_HOMESERVER", "https://matrix.org")
        self.access_token = os.getenv("MATRIX_ACCESS_TOKEN")
        self.user_id = os.getenv("MATRIX_USER_ID")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        # Start audit logging
        audit_ctx = log_integration_attempt("matrix", "close", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("matrix"):
                logger.warning(f"Circuit breaker is open for matrix")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Matrix integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("matrix")
            if is_limited:
                logger.warning(f"Rate limit exceeded for matrix")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for matrix"
                )

        await self.client.aclose()

    async def send_message(self, room_id: str, text: str) -> bool:
        """Send a message to a Matrix room"""
        if not self.access_token:
            logger.error("MATRIX_ACCESS_TOKEN not set")
            return False

        txn_id = f"atom_{int(datetime.now().timestamp() * 1000)}"
        url = f"{self.homeserver}/_matrix/client/r0/rooms/{room_id}/send/m.room.message/{txn_id}"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "msgtype": "m.text",
            "body": text
        }
        
        try:
            response = await self.client.put(url, headers=headers, json=data)
            response.raise_for_status()
            logger.info(f"Matrix message sent to {room_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Matrix message: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        # Start audit logging
        audit_ctx = log_integration_attempt("matrix", "health_check", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("matrix"):
                logger.warning(f"Circuit breaker is open for matrix")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Matrix integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("matrix")
            if is_limited:
                logger.warning(f"Rate limit exceeded for matrix")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for matrix"
                )

        return {
            "ok": True,
            "status": "healthy" if self.access_token else "degraded",
            "service": "matrix",
            "timestamp": datetime.now().isoformat()
        }

# Singleton instance
matrix_service = MatrixService()

        # Start audit logging
        audit_ctx = log_integration_attempt("matrix", "send_message", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("matrix"):
                logger.warning(f"Circuit breaker is open for matrix")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Matrix integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("matrix")
            if is_limited:
                logger.warning(f"Rate limit exceeded for matrix")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for matrix"
                )
