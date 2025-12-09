"""
Base Integration Service - Shared functionality for all integrations
Reduces code duplication and provides consistent patterns across services
"""

import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import httpx
import aiohttp
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class IntegrationStatus(Enum):
    """Integration status enum"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PENDING = "pending"
    RATE_LIMITED = "rate_limited"

@dataclass
class IntegrationConfig:
    """Configuration for integrations"""
    name: str
    base_url: str
    api_key_env_var: str
    oauth_enabled: bool = True
    rate_limit_per_minute: int = 100
    timeout_seconds: int = 30
    retry_attempts: int = 3
    backoff_factor: float = 2.0

@dataclass
class IntegrationResponse:
    """Standard response format for integrations"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    status_code: Optional[int] = None
    rate_limit_remaining: Optional[int] = None
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

class BaseIntegrationService(ABC):
    """Base class for all integration services"""

    def __init__(self, config: IntegrationConfig):
        self.config = config
        self.api_key = None
        self.http_client = None
        self.session_pool = {}
        self._rate_limit_tracker = {}
        self._status = IntegrationStatus.INACTIVE

        # Initialize API key from environment
        self._load_api_key()

    def _load_api_key(self):
        """Load API key from environment variables"""
        import os
        self.api_key = os.getenv(self.config.api_key_env_var)
        if not self.api_key:
            logger.warning(f"API key not found for {self.config.name} in {self.config.api_key_env_var}")
            self._status = IntegrationStatus.PENDING
        else:
            self._status = IntegrationStatus.ACTIVE

    @asynccontextmanager
    async def get_http_client(self):
        """Context manager for HTTP client with proper resource management"""
        if not self.http_client:
            timeout = httpx.Timeout(
                connect=self.config.timeout_seconds / 3,
                read=self.config.timeout_seconds
            )
            self.http_client = httpx.AsyncClient(
                timeout=timeout,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=5)
            )

        try:
            yield self.http_client
        except Exception as e:
            logger.error(f"HTTP client error in {self.config.name}: {e}")
            raise

    async def check_rate_limit(self, user_id: str = None) -> bool:
        """Check if we're rate limited"""
        now = datetime.now()
        key = user_id or "global"

        if key not in self._rate_limit_tracker:
            self._rate_limit_tracker[key] = []

        # Clean old requests (older than 1 minute)
        self._rate_limit_tracker[key] = [
            req_time for req_time in self._rate_limit_tracker[key]
            if now - req_time < timedelta(minutes=1)
        ]

        return len(self._rate_limit_tracker[key]) < self.config.rate_limit_per_minute

    async def record_request(self, user_id: str = None):
        """Record a request for rate limiting"""
        key = user_id or "global"
        if key not in self._rate_limit_tracker:
            self._rate_limit_tracker[key] = []

        self._rate_limit_tracker[key].append(datetime.now())

    async def make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        user_id: Optional[str] = None
    ) -> IntegrationResponse:
        """Make HTTP request with retry logic and rate limiting"""

        if not self.api_key:
            return IntegrationResponse(
                success=False,
                error="API key not configured"
            )

        # Check rate limiting
        if not await self.check_rate_limit(user_id):
            self._status = IntegrationStatus.RATE_LIMITED
            return IntegrationResponse(
                success=False,
                error="Rate limit exceeded",
                status_code=429
            )

        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        default_headers = self._get_default_headers()
        if headers:
            default_headers.update(headers)

        last_exception = None

        for attempt in range(self.config.retry_attempts):
            try:
                async with self.get_http_client() as client:
                    response = await client.request(
                        method=method.upper(),
                        url=url,
                        json=data if method.upper() in ['POST', 'PUT', 'PATCH'] else None,
                        params=params,
                        headers=default_headers
                    )

                    # Record successful request
                    await self.record_request(user_id)

                    # Handle rate limiting response
                    if response.status_code == 429:
                        retry_after = int(response.headers.get('Retry-After', 60))
                        wait_time = self.config.backoff_factor ** attempt * retry_after

                        logger.warning(f"Rate limited for {self.config.name}, waiting {wait_time}s")
                        await asyncio.sleep(wait_time)
                        continue

                    # Success response
                    if 200 <= response.status_code < 300:
                        try:
                            response_data = response.json()
                        except:
                            response_data = {"text": response.text}

                        self._status = IntegrationStatus.ACTIVE

                        return IntegrationResponse(
                            success=True,
                            data=response_data,
                            status_code=response.status_code,
                            rate_limit_remaining=int(response.headers.get('X-RateLimit-Remaining', 0)) if 'X-RateLimit-Remaining' in response.headers else None
                        )

                    # Error response
                    else:
                        error_text = response.text
                        logger.error(f"API error for {self.config.name}: {response.status_code} - {error_text}")

                        return IntegrationResponse(
                            success=False,
                            error=error_text,
                            status_code=response.status_code
                        )

            except httpx.HTTPError as e:
                last_exception = e
                wait_time = self.config.backoff_factor ** attempt

                logger.warning(f"HTTP error for {self.config.name} (attempt {attempt + 1}): {e}")

                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(wait_time)
                    continue

            except Exception as e:
                last_exception = e
                logger.error(f"Unexpected error for {self.config.name}: {e}")
                break

        self._status = IntegrationStatus.ERROR

        return IntegrationResponse(
            success=False,
            error=f"Request failed after {self.config.retry_attempts} attempts: {str(last_exception)}"
        )

    @abstractmethod
    def _get_default_headers(self) -> Dict[str, str]:
        """Get default headers for requests (to be implemented by subclasses)"""
        pass

    @abstractmethod
    async def test_connection(self) -> IntegrationResponse:
        """Test API connection (to be implemented by subclasses)"""
        pass

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        try:
            connection_test = await self.test_connection()

            return {
                "service": self.config.name,
                "status": self._status.value,
                "api_key_configured": bool(self.api_key),
                "connection_test": connection_test.success,
                "last_checked": datetime.now().isoformat(),
                "rate_limit_info": {
                    "limit_per_minute": self.config.rate_limit_per_minute,
                    "current_requests": len(self._rate_limit_tracker.get("global", []))
                },
                "error": connection_test.error if not connection_test.success else None
            }
        except Exception as e:
            logger.error(f"Health check failed for {self.config.name}: {e}")
            return {
                "service": self.config.name,
                "status": IntegrationStatus.ERROR.value,
                "error": str(e),
                "last_checked": datetime.now().isoformat()
            }

    async def cleanup(self):
        """Cleanup resources"""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None

        self._rate_limit_tracker.clear()
        logger.info(f"Cleaned up resources for {self.config.name}")

class OAuthIntegrationService(BaseIntegrationService):
    """Base class for OAuth-based integrations"""

    def __init__(self, config: IntegrationConfig, token_storage=None):
        super().__init__(config)
        self.token_storage = token_storage
        self.config.oauth_enabled = True

    async def get_access_token(self, user_id: str) -> Optional[str]:
        """Get access token for user"""
        if not self.token_storage:
            logger.error("Token storage not configured")
            return None

        try:
            # This would integrate with your existing token storage
            token_data = await self.token_storage.get_token(user_id, self.config.name)
            return token_data.get('access_token') if token_data else None
        except Exception as e:
            logger.error(f"Failed to get access token for {user_id}: {e}")
            return None

    async def store_tokens(self, user_id: str, token_data: Dict[str, Any]) -> bool:
        """Store OAuth tokens for user"""
        if not self.token_storage:
            logger.error("Token storage not configured")
            return False

        try:
            await self.token_storage.store_token(user_id, self.config.name, token_data)
            return True
        except Exception as e:
            logger.error(f"Failed to store tokens for {user_id}: {e}")
            return False

class APIKeyIntegrationService(BaseIntegrationService):
    """Base class for API key-based integrations"""

    def _get_default_headers(self) -> Dict[str, str]:
        """Default headers for API key authentication"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        if self.api_key:
            # This should be overridden by subclasses for specific auth patterns
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers