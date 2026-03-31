import os
from typing import Any, Dict, List, Optional
import httpx
from core.circuit_breaker import circuit_breaker
from core.rate_limiter import rate_limiter, should_retry, calculate_backoff
from core.audit_logger import log_integration_call, log_integration_error, log_integration_attempt, log_integration_complete
from fastapi import HTTPException



class MailchimpService:
    def __init__(self):
        self.client_id = os.getenv("MAILCHIMP_CLIENT_ID")
        self.client_secret = os.getenv("MAILCHIMP_CLIENT_SECRET")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        # Start audit logging
        audit_ctx = log_integration_attempt("mailchimp", "close", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("mailchimp"):
                logger.warning(f"Circuit breaker is open for mailchimp")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Mailchimp integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("mailchimp")
            if is_limited:
                logger.warning(f"Rate limit exceeded for mailchimp")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for mailchimp"
                )

        await self.client.aclose()

    def _get_base_url(self, server_prefix: str) -> str:
        return f"https://{server_prefix}.api.mailchimp.com/3.0"

    def _get_headers(self, access_token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

    async def exchange_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        # Start audit logging
        audit_ctx = log_integration_attempt("mailchimp", "exchange_token", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("mailchimp"):
                logger.warning(f"Circuit breaker is open for mailchimp")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Mailchimp integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("mailchimp")
            if is_limited:
                logger.warning(f"Rate limit exceeded for mailchimp")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for mailchimp"
                )

        url = "https://login.mailchimp.com/oauth2/token"
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": redirect_uri,
            "code": code
        }
        response = await self.client.post(url, data=data)
        response.raise_for_status()
        return response.json()

    async def get_metadata(self, access_token: str) -> Dict[str, Any]:
        # Start audit logging
        audit_ctx = log_integration_attempt("mailchimp", "get_metadata", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("mailchimp"):
                logger.warning(f"Circuit breaker is open for mailchimp")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Mailchimp integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("mailchimp")
            if is_limited:
                logger.warning(f"Rate limit exceeded for mailchimp")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for mailchimp"
                )

        url = "https://login.mailchimp.com/oauth2/metadata"
        headers = {"Authorization": f"OAuth {access_token}"}
        response = await self.client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    async def get_audiences(self, access_token: str, server_prefix: str, limit: int = 20) -> List[Dict[str, Any]]:
        # Start audit logging
        audit_ctx = log_integration_attempt("mailchimp", "get_audiences", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("mailchimp"):
                logger.warning(f"Circuit breaker is open for mailchimp")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Mailchimp integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("mailchimp")
            if is_limited:
                logger.warning(f"Rate limit exceeded for mailchimp")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for mailchimp"
                )

        url = f"{self._get_base_url(server_prefix)}/lists"
        headers = self._get_headers(access_token)
        params = {"count": limit}
        response = await self.client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get("lists", [])

    async def get_campaigns(self, access_token: str, server_prefix: str, limit: int = 20, status: Optional[str] = None) -> List[Dict[str, Any]]:
        # Start audit logging
        audit_ctx = log_integration_attempt("mailchimp", "get_campaigns", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("mailchimp"):
                logger.warning(f"Circuit breaker is open for mailchimp")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Mailchimp integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("mailchimp")
            if is_limited:
                logger.warning(f"Rate limit exceeded for mailchimp")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for mailchimp"
                )

        url = f"{self._get_base_url(server_prefix)}/campaigns"
        headers = self._get_headers(access_token)
        params = {"count": limit}
        if status:
            params["status"] = status
        response = await self.client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get("campaigns", [])

    async def get_account_info(self, access_token: str, server_prefix: str) -> Dict[str, Any]:
        # Start audit logging
        audit_ctx = log_integration_attempt("mailchimp", "get_account_info", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("mailchimp"):
                logger.warning(f"Circuit breaker is open for mailchimp")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Mailchimp integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("mailchimp")
            if is_limited:
                logger.warning(f"Rate limit exceeded for mailchimp")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for mailchimp"
                )

        url = f"{self._get_base_url(server_prefix)}/"
        headers = self._get_headers(access_token)
        response = await self.client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
