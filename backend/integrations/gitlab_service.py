
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

class GitLabService:
    """GitLab API Service Implementation"""
    
    def __init__(self):
        self.base_url = "https://gitlab.com/api/v4"
        self.client_id = os.getenv("GITLAB_CLIENT_ID")
        self.client_secret = os.getenv("GITLAB_CLIENT_SECRET")
        self.client = httpx.AsyncClient(timeout=30.0)

    def _get_headers(self, access_token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }

    async def exchange_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        try:
            url = "https://gitlab.com/oauth/token"
            data = {
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": redirect_uri
            }
            
            response = await self.client.post(url, data=data)
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"GitLab token exchange failed: {e}")
            raise HTTPException(status_code=400, detail=f"Token exchange failed: {str(e)}")

    async def get_user(self, access_token: str) -> Dict[str, Any]:
        """Get authenticated user info"""
        # Start audit logging
        audit_ctx = log_integration_attempt("gitlab", "exchange_token", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("gitlab"):
                logger.warning(f"Circuit breaker is open for gitlab")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Gitlab integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("gitlab")
            if is_limited:
                logger.warning(f"Rate limit exceeded for gitlab")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for gitlab"
                )

        try:
            url = f"{self.base_url}/user"
            headers = self._get_headers(access_token)
            
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch user info: {str(e)}")

    async def get_projects(self, access_token: str, limit: int = 20, membership: bool = True) -> List[Dict[str, Any]]:
        """Get list of projects"""
        # Start audit logging
        audit_ctx = log_integration_attempt("gitlab", "get_user", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("gitlab"):
                logger.warning(f"Circuit breaker is open for gitlab")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Gitlab integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("gitlab")
            if is_limited:
                logger.warning(f"Rate limit exceeded for gitlab")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for gitlab"
                )

        try:
            url = f"{self.base_url}/projects"
            headers = self._get_headers(access_token)
            params = {
                "per_page": limit,
                "membership": str(membership).lower(),
                "order_by": "updated_at"
            }
            
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get projects: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch projects: {str(e)}")

    async def get_issues(self, access_token: str, project_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get list of issues (globally or for a project)"""
        # Start audit logging
        audit_ctx = log_integration_attempt("gitlab", "get_projects", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("gitlab"):
                logger.warning(f"Circuit breaker is open for gitlab")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Gitlab integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("gitlab")
            if is_limited:
                logger.warning(f"Rate limit exceeded for gitlab")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for gitlab"
                )

        try:
            if project_id:
                url = f"{self.base_url}/projects/{project_id}/issues"
            else:
                url = f"{self.base_url}/issues"
                
            headers = self._get_headers(access_token)
            params = {"per_page": limit, "scope": "all"}
            
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get issues: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch issues: {str(e)}")

    async def search_projects(self, access_token: str, query: str) -> List[Dict[str, Any]]:
        """Search for projects"""
        # Start audit logging
        audit_ctx = log_integration_attempt("gitlab", "get_issues", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("gitlab"):
                logger.warning(f"Circuit breaker is open for gitlab")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Gitlab integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("gitlab")
            if is_limited:
                logger.warning(f"Rate limit exceeded for gitlab")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for gitlab"
                )

        try:
            url = f"{self.base_url}/projects"
            headers = self._get_headers(access_token)
            params = {"search": query, "per_page": 20}
            
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

        # Start audit logging
        audit_ctx = log_integration_attempt("gitlab", "search_projects", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("gitlab"):
                logger.warning(f"Circuit breaker is open for gitlab")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Gitlab integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("gitlab")
            if is_limited:
                logger.warning(f"Rate limit exceeded for gitlab")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for gitlab"
                )
