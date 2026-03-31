from datetime import datetime
import logging
import os
from typing import Any, Dict, List, Optional
import httpx
from core.circuit_breaker import circuit_breaker
from core.rate_limiter import rate_limiter, should_retry, calculate_backoff
from core.audit_logger import log_integration_call, log_integration_error, log_integration_attempt, log_integration_complete
from fastapi import HTTPException


logger = logging.getLogger(__name__)

class IntercomService:
    def __init__(self):
        self.base_url = "https://api.intercom.io"
        self.client_id = os.getenv("INTERCOM_CLIENT_ID")
        self.client_secret = os.getenv("INTERCOM_CLIENT_SECRET")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        # Start audit logging
        audit_ctx = log_integration_attempt("intercom", "close", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("intercom"):
                logger.warning(f"Circuit breaker is open for intercom")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Intercom integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("intercom")
            if is_limited:
                logger.warning(f"Rate limit exceeded for intercom")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for intercom"
                )

        await self.client.aclose()

    def _get_headers(self, access_token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def exchange_token(self, code: str) -> Dict[str, Any]:
        # Start audit logging
        audit_ctx = log_integration_attempt("intercom", "exchange_token", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("intercom"):
                logger.warning(f"Circuit breaker is open for intercom")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Intercom integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("intercom")
            if is_limited:
                logger.warning(f"Rate limit exceeded for intercom")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for intercom"
                )

        url = f"{self.base_url}/auth/eagle/token"
        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        response = await self.client.post(url, json=data)
        response.raise_for_status()
        return response.json()

    async def get_admins(self, access_token: str) -> List[Dict[str, Any]]:
        # Start audit logging
        audit_ctx = log_integration_attempt("intercom", "get_admins", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("intercom"):
                logger.warning(f"Circuit breaker is open for intercom")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Intercom integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("intercom")
            if is_limited:
                logger.warning(f"Rate limit exceeded for intercom")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for intercom"
                )

        url = f"{self.base_url}/admins"
        headers = self._get_headers(access_token)
        response = await self.client.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get("admins", [])

    async def get_contacts(self, access_token: str, limit: int = 20) -> List[Dict[str, Any]]:
        # Start audit logging
        audit_ctx = log_integration_attempt("intercom", "get_contacts", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("intercom"):
                logger.warning(f"Circuit breaker is open for intercom")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Intercom integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("intercom")
            if is_limited:
                logger.warning(f"Rate limit exceeded for intercom")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for intercom"
                )

        url = f"{self.base_url}/contacts"
        headers = self._get_headers(access_token)
        params = {"per_page": limit}
        response = await self.client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get("data", [])

    async def get_conversations(self, access_token: str, limit: int = 20) -> List[Dict[str, Any]]:
        # Start audit logging
        audit_ctx = log_integration_attempt("intercom", "get_conversations", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("intercom"):
                logger.warning(f"Circuit breaker is open for intercom")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Intercom integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("intercom")
            if is_limited:
                logger.warning(f"Rate limit exceeded for intercom")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for intercom"
                )

        url = f"{self.base_url}/conversations"
        headers = self._get_headers(access_token)
        params = {"per_page": limit}
        response = await self.client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get("conversations", [])

    async def search_contacts(self, access_token: str, query: str) -> List[Dict[str, Any]]:
        # Start audit logging
        audit_ctx = log_integration_attempt("intercom", "search_contacts", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("intercom"):
                logger.warning(f"Circuit breaker is open for intercom")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Intercom integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("intercom")
            if is_limited:
                logger.warning(f"Rate limit exceeded for intercom")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for intercom"
                )

        url = f"{self.base_url}/contacts/search"
        headers = self._get_headers(access_token)
        data = {
            "query": {
                "field": "name",
                "operator": "~",
                "value": query
            }
        }
        response = await self.client.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json().get("data", [])

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Intercom service"""
        return {
            "ok": True,
            "status": "healthy",
            "service": "intercom",
            "timestamp": datetime.now().isoformat(),
            "configured": bool(self.client_id and self.client_secret)
        }


intercom_service = IntercomService()


def get_intercom_service() -> IntercomService:
    return intercom_service


        # Start audit logging
        audit_ctx = log_integration_attempt("intercom", "health_check", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("intercom"):
                logger.warning(f"Circuit breaker is open for intercom")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Intercom integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("intercom")
            if is_limited:
                logger.warning(f"Rate limit exceeded for intercom")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for intercom"
                )
