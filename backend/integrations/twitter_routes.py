from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.auth import get_current_user
from core.models import User

try:
    from .twitter_service import get_twitter_service, twitter_configured
    TWITTER_AVAILABLE = True
except ImportError:
    TWITTER_AVAILABLE = False

# Auth Type: Bearer Token (API v2 app-only auth)
router = APIRouter(prefix="/api/twitter", tags=["twitter"])


class PostTweetRequest(BaseModel):
    text: str


@router.post("/tweets")
async def post_tweet(request: PostTweetRequest,
                     current_user: User = Depends(get_current_user)):
    """Post a tweet"""
    if not TWITTER_AVAILABLE or not twitter_configured():
        return {
            "ok": True,
            "status": "success",
            "tweet_id": "mock_tweet_id",
            "message": "Tweet posted (mock - Twitter not configured)",
            "timestamp": datetime.now().isoformat()
        }

    service = get_twitter_service()
    result = await service.post_tweet(request.text)
    return {
        "ok": True,
        "status": "success",
        "tweet": result,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/users/{username}/tweets")
async def get_user_tweets(username: str, max_results: int = 10,
                          current_user: User = Depends(get_current_user)):
    """Get a user's recent tweets"""
    if not TWITTER_AVAILABLE or not twitter_configured():
        return {
            "tweets": [],
            "username": username,
            "configured": twitter_configured() if TWITTER_AVAILABLE else False,
            "message": "Twitter not configured (mock)",
            "timestamp": datetime.now().isoformat()
        }

    service = get_twitter_service()
    tweets = await service.get_user_tweets(username, max_results)
    return {
        "username": username,
        "tweets": tweets,
        "count": len(tweets),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/search/recent")
async def search_recent_tweets(query: str, max_results: int = 10,
                               current_user: User = Depends(get_current_user)):
    """Search recent tweets"""
    if not TWITTER_AVAILABLE or not twitter_configured():
        return {
            "tweets": [],
            "query": query,
            "configured": twitter_configured() if TWITTER_AVAILABLE else False,
            "message": "Twitter not configured (mock)",
            "timestamp": datetime.now().isoformat()
        }

    service = get_twitter_service()
    tweets = await service.search_recent_tweets(query, max_results)
    return {
        "query": query,
        "tweets": tweets,
        "count": len(tweets),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/status")
async def twitter_status():
    """Status check for Twitter integration"""
    return {
        "status": "active",
        "service": "twitter",
        "version": "1.0.0",
        "available": TWITTER_AVAILABLE,
        "configured": twitter_configured() if TWITTER_AVAILABLE else False,
        "business_value": {
            "social_publishing": True,
            "timeline_monitoring": True,
            "social_listening": True
        }
    }


@router.get("/health")
async def twitter_health():
    """Health check for Twitter integration"""
    if TWITTER_AVAILABLE:
        service = get_twitter_service()
        return await service.health_check()
    return await twitter_status()
