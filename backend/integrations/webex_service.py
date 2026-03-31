import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
import httpx
from core.circuit_breaker import circuit_breaker
from core.rate_limiter import rate_limiter, should_retry, calculate_backoff
from core.audit_logger import log_integration_call, log_integration_error, log_integration_attempt, log_integration_complete
from fastapi import HTTPException


logger = logging.getLogger(__name__)

class WebexService:
    """Cisco Webex API Service"""
    
    def __init__(self):
        self.base_url = "https://webexapis.com/v1"
        self.access_token = os.getenv("WEBEX_ACCESS_TOKEN")
        self.client = httpx.AsyncClient(timeout=30.0)

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    async def list_rooms(self) -> List[Dict[str, Any]]:
        """List Webex rooms (now called Spaces)"""
        try:
            if not self.access_token:
                # Stub data
                return [{
                    "id": "mock_room_id",
                    "title": "Strategy Room (MOCK)",
                    "type": "group",
                    "isLocked": False
                }]

            url = f"{self.base_url}/rooms"
            response = await self.client.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json().get("items", [])
        except Exception as e:
            logger.error(f"Webex list_rooms failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def check_health(self) -> Dict[str, Any]:
        """Check Webex connectivity"""
        # Start audit logging
        audit_ctx = log_integration_attempt("webex", "list_rooms", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("webex"):
                logger.warning(f"Circuit breaker is open for webex")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Webex integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("webex")
            if is_limited:
                logger.warning(f"Rate limit exceeded for webex")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for webex"
                )

        return {
            "status": "active" if self.access_token else "partially_configured",
            "service": "webex",
            "mode": "real" if self.access_token else "mock"
        }

# Global instance
webex_service = WebexService()

        # Start audit logging
        audit_ctx = log_integration_attempt("webex", "check_health", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("webex"):
                logger.warning(f"Circuit breaker is open for webex")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Webex integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("webex")
            if is_limited:
                logger.warning(f"Rate limit exceeded for webex")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for webex"
                )
