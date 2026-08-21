"""
Twitter (X) API v2 Service for ATOM Platform
Provides tweet posting, user timelines, and recent search
"""

import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

TWITTER_BASE_URL = "https://api.twitter.com/2"

# Note: TWITTER_API_KEY / TWITTER_API_SECRET (consumer credentials) are not
# used by this service; the v2 endpoints here only require the bearer token.


def twitter_configured() -> bool:
    """Check whether Twitter/X credentials are configured."""
    return bool(os.getenv("TWITTER_BEARER_TOKEN"))


class TwitterService:
    """Service for Twitter (X) API v2 interactions"""

    def __init__(self, bearer_token: str = None):
        self.bearer_token = bearer_token or os.getenv("TWITTER_BEARER_TOKEN", "")
        # Kept for completeness / future OAuth 1.0a user-context calls.
        self.api_key = os.getenv("TWITTER_API_KEY", "")
        self.api_secret = os.getenv("TWITTER_API_SECRET", "")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()

    def _check_configured(self):
        """Raise if the service is not configured"""
        if not self.bearer_token:
            raise HTTPException(
                status_code=503,
                detail="Twitter integration not configured. Set TWITTER_BEARER_TOKEN."
            )

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
        }

    async def _make_request(
        self, method: str, endpoint: str, json: Dict = None, params: Dict = None
    ) -> Any:
        """Make authenticated request to the Twitter API v2"""
        self._check_configured()
        url = f"{TWITTER_BASE_URL}/{endpoint}"
        headers = self._get_headers()

        try:
            response = await self.client.request(
                method, url, headers=headers, json=json, params=params
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Twitter API returned {e.response.status_code} for {method} {endpoint}")
            raise HTTPException(
                status_code=e.response.status_code if e.response.status_code >= 400 else 400,
                detail=f"Twitter API error: {e.response.status_code}"
            )
        except httpx.HTTPError as e:
            logger.error(f"Twitter API request failed: {e}")
            raise HTTPException(status_code=502, detail="Internal error")

        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    async def post_tweet(self, text: str) -> Dict[str, Any]:
        """Post a tweet (POST /tweets)"""
        if not text:
            raise HTTPException(status_code=400, detail="Tweet text is required")
        return await self._make_request("POST", "tweets", json={"text": text})

    async def get_user_tweets(
        self, username: str, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Get a user's recent tweets (GET /users/by/username/{username}/tweets)"""
        result = await self._make_request(
            "GET",
            f"users/by/username/{username}/tweets",
            params={"max_results": max_results},
        )
        return result.get("data", [])

    async def search_recent_tweets(
        self, query: str, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search recent tweets (GET /tweets/search/recent)"""
        if not query:
            raise HTTPException(status_code=400, detail="Search query is required")
        result = await self._make_request(
            "GET",
            "tweets/search/recent",
            params={"query": query, "max_results": max_results},
        )
        return result.get("data", [])

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Twitter service"""
        return {
            "ok": twitter_configured(),
            "status": "healthy" if twitter_configured() else "not_configured",
            "service": "twitter",
            "configured": twitter_configured(),
        }


# Singleton instance
twitter_service = TwitterService()


def get_twitter_service() -> TwitterService:
    """Get Twitter service instance"""
    return twitter_service
