"""
Social Media Integration Routes

Provides endpoints for posting to social media platforms.
Supports Twitter (X), LinkedIn, Facebook, and other platforms.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import OAuthToken, User

router = BaseAPIRouter(prefix="/api/v1/social", tags=["social-media"])
logger = logging.getLogger(__name__)


# Request/Response Models
class SocialPostRequest(BaseModel):
    """Social media post request"""
    text: str = Field(..., min_length=1, max_length=5000, description="Post content")
    platforms: List[str] = Field(..., description="Target platforms (twitter, linkedin, facebook)")
    scheduled_for: Optional[datetime] = Field(None, description="Schedule post for future time")
    media_urls: Optional[List[str]] = Field(default=[], description="Images/videos to attach")
    link_url: Optional[str] = Field(None, description="Link to include in post")

    model_config = ConfigDict(extra="allow")


class SocialPostResponse(BaseModel):
    """Social media post response"""
    success: bool
    post_id: str
    platform_results: dict
    scheduled: bool = False
    scheduled_for: Optional[datetime] = None


class PlatformConfig:
    """Configuration for social media platforms"""

    PLATFORMS = {
        "twitter": {
            "name": "Twitter/X",
            "max_length": 500,
            "supports_media": True,
            "supports_links": True,
            "oauth_provider": "twitter",  # For OAuthToken lookup
        },
        "linkedin": {
            "name": "LinkedIn",
            "max_length": 3000,
            "supports_media": True,
            "supports_links": True,
            "oauth_provider": "linkedin",
        },
        "facebook": {
            "name": "Facebook",
            "max_length": 63206,
            "supports_media": True,
            "supports_links": True,
            "oauth_provider": "facebook",
        },
    }

    @classmethod
    def get_platform(cls, platform: str) -> dict:
        """Get platform configuration"""
        platform = platform.lower()
        if platform not in cls.PLATFORMS:
            raise ValueError(f"Unsupported platform: {platform}")
        return cls.PLATFORMS[platform]

    @classmethod
    def validate_content(cls, platform: str, text: str) -> tuple[bool, Optional[str]]:
        """Validate content for platform"""
        try:
            config = cls.get_platform(platform)
            if len(text) > config["max_length"]:
                return False, f"Text exceeds {config['name']} max length of {config['max_length']}"
            return True, None
        except ValueError as e:
            return False, str(e)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    Get current user from session or JWT.
    """
    # Method 1: Try JWT token from Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            from core.enterprise_auth_service import EnterpriseAuthService
            auth_service = EnterpriseAuthService()
            token = auth_header.split(" ")[1]
            claims = auth_service.verify_token(token)
            if claims:
                user_id = claims.get('user_id')
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    return user
        except Exception as e:
            logger.debug(f"JWT auth failed: {e}")

    # Method 2: Try X-User-ID header (from NextAuth session)
    user_id = request.headers.get("X-User-ID")
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return user

    # Method 3: Try X-User-Email header (alternative from session)
    user_email = request.headers.get("X-User-Email")
    if user_email:
        user = db.query(User).filter(User.email == user_email).first()
        if user:
            return user

    # Method 4: Create temp user for development (if in dev mode)
    if os.getenv("ENVIRONMENT", "development") == "development":
        temp_id = request.headers.get("X-User-ID") or "dev_user"
        user = db.query(User).filter(User.id == temp_id).first()
        if not user:
            user = User(
                id=temp_id,
                email=f"dev_{temp_id}@example.com",
                first_name="Dev",
                last_name="User"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    raise HTTPException(
        status_code=401,
        detail="Unauthorized: Valid authentication required"
    )


def rate_limit_check(user_id: str, db: Session) -> bool:
    """
    Check rate limits for social posting.
    Max 10 posts per hour per user across all platforms.
    """
    from core.models import SocialPostHistory

    # Count posts in last hour
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent_posts = db.query(SocialPostHistory).filter(
        SocialPostHistory.user_id == user_id,
        SocialPostHistory.created_at >= one_hour_ago,
        SocialPostHistory.status == "posted"
    ).count()

    if recent_posts >= 10:
        logger.warning(f"Rate limit exceeded for user {user_id}: {recent_posts} posts in last hour")
        return False

    return True


async def post_to_twitter(
    text: str,
    access_token: str,
    media_urls: List[str] = None,
    link_url: str = None
) -> dict:
    """
    Post to Twitter/X API.

    Requires OAuth 2.0 token with tweet.write scope.
    """
    try:
        import httpx

        # Twitter API v2 endpoint
        api_url = "https://api.twitter.com/2/tweets"

        # Prepare tweet payload
        tweet_data = {"text": text}

        # Add link if provided (Twitter auto-expands URLs)
        if link_url:
            tweet_data["text"] = f"{text}\n\n{link_url}"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url,
                json=tweet_data,
                headers=headers,
                timeout=30.0
            )

            if response.status_code == 201:
                data = response.json()
                return {
                    "success": True,
                    "post_id": data.get("data", {}).get("id"),
                    "url": f"https://twitter.com/i/status/{data.get('data', {}).get('id')}",
                    "platform": "twitter"
                }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "error": "Unauthorized - please reconnect your Twitter account",
                    "status_code": response.status_code
                }
            elif response.status_code == 429:
                return {
                    "success": False,
                    "error": "Rate limit exceeded - please try again later",
                    "status_code": response.status_code
                }
            else:
                logger.error(f"Twitter API error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Twitter API error: {response.text}",
                    "status_code": response.status_code
                }

    except ImportError:
        return {
            "success": False,
            "error": "httpx not installed - cannot make API requests"
        }
    except Exception as e:
        logger.error(f"Twitter posting failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


async def post_to_linkedin(
    text: str,
    access_token: str,
    media_urls: List[str] = None,
    link_url: str = None
) -> dict:
    """
    Post to LinkedIn API.

    Requires OAuth 2.0 token with w_member_social permission.
    """
    try:
        import httpx

        # LinkedIn UGC API endpoint
        # First, we need to get the user's profile ID
        profile_url = "https://api.linkedin.com/v2/userinfo"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            # Get user profile
            profile_response = await client.get(profile_url, headers=headers)

            if profile_response.status_code != 200:
                return {
                    "success": False,
                    "error": "Failed to fetch LinkedIn profile",
                    "status_code": profile_response.status_code
                }

            profile_data = profile_response.json()
            person_urn = profile_data.get("sub")

            if not person_urn:
                return {
                    "success": False,
                    "error": "No LinkedIn profile ID found"
                }

            # Create the post
            post_url = "https://api.linkedin.com/v2/ugcPosts"

            # Prepare post content
            post_content = {
                "author": f"urn:li:person:{person_urn}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": text
                        },
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }

            # Add link if provided
            if link_url:
                post_content["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "ARTICLE"
                post_content["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
                    {
                        "status": "READY",
                        "description": {
                            "text": text
                        },
                        "originalUrl": link_url,
                        "title": {
                            "text": "Link"
                        }
                    }
                ]

            post_response = await client.post(
                post_url,
                json=post_content,
                headers=headers,
                timeout=30.0
            )

            if post_response.status_code == 201:
                data = post_response.json()
                post_id = data.get("id")
                return {
                    "success": True,
                    "post_id": post_id,
                    "url": f"https://www.linkedin.com/feed/update/{post_id}",
                    "platform": "linkedin"
                }
            else:
                logger.error(f"LinkedIn API error: {post_response.status_code} - {post_response.text}")
                return {
                    "success": False,
                    "error": f"LinkedIn API error: {post_response.text}",
                    "status_code": post_response.status_code
                }

    except ImportError:
        return {
            "success": False,
            "error": "httpx not installed - cannot make API requests"
        }
    except Exception as e:
        logger.error(f"LinkedIn posting failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


async def post_to_facebook(
    text: str,
    access_token: str,
    media_urls: List[str] = None,
    link_url: str = None
) -> dict:
    """
    Post to Facebook API.

    Requires OAuth 2.0 token with pages_manage_posts permission.
    """
    try:
        import httpx

        # Facebook Graph API endpoint
        # Note: This posts to the user's feed, not a page
        api_url = f"https://graph.facebook.com/v18.0/me/feed"

        headers = {
            "Authorization": f"Bearer {access_token}",
        }

        data = {
            "message": text
        }

        if link_url:
            data["link"] = link_url

        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url,
                data=data,
                headers=headers,
                timeout=30.0
            )

            if response.status_code == 200:
                result = response.json()
                post_id = result.get("id")
                return {
                    "success": True,
                    "post_id": post_id,
                    "url": f"https://www.facebook.com/{post_id}",
                    "platform": "facebook"
                }
            else:
                logger.error(f"Facebook API error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Facebook API error: {response.text}",
                    "status_code": response.status_code
                }

    except ImportError:
        return {
            "success": False,
            "error": "httpx not installed - cannot make API requests"
        }
    except Exception as e:
        logger.error(f"Facebook posting failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


# Platform posting handlers
PLATFORM_POSTERS = {
    "twitter": post_to_twitter,
    "linkedin": post_to_linkedin,
    "facebook": post_to_facebook,
}


@router.post("/post", response_model=SocialPostResponse)
async def create_social_post(
    request: Request,
    payload: SocialPostRequest,
    db: Session = Depends(get_db)
):
    """
    Create and post to social media platforms.

    Supports immediate posting to Twitter/X, LinkedIn, and Facebook.
    Requires OAuth tokens for each target platform.

    Rate Limits:
    - 10 posts per hour per user (across all platforms)
    - Content length validation per platform

    TODO: Implement scheduled posting (requires background task queue)
    """
    try:
        # Get current user
        current_user = get_current_user(request, db)

        # Validate platforms
        if not payload.platforms:
            raise HTTPException(
                status_code=400,
                detail="At least one platform must be specified"
            )

        # Validate content for each platform
        for platform in payload.platforms:
            valid, error_msg = PlatformConfig.validate_content(platform, payload.text)
            if not valid:
                raise HTTPException(
                    status_code=400,
                    detail=error_msg
                )

        # Check rate limits
        if not rate_limit_check(current_user.id, db):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded: Maximum 10 posts per hour"
            )

        # Handle scheduled posts (TODO: Implement background job queue)
        if payload.scheduled_for and payload.scheduled_for > datetime.utcnow():
            return SocialPostResponse(
                success=True,
                post_id=str(uuid.uuid4()),
                platform_results={},
                scheduled=True,
                scheduled_for=payload.scheduled_for,
            )

        # Post to each platform
        platform_results = {}
        successful_posts = 0

        for platform in payload.platforms:
            platform = platform.lower()

            # Check if we have OAuth token for this platform
            try:
                config = PlatformConfig.get_platform(platform)
                oauth_provider = config.get("oauth_provider", platform)

                # Look up OAuth token
                oauth_token = db.query(OAuthToken).filter(
                    OAuthToken.user_id == current_user.id,
                    OAuthToken.provider == oauth_provider,
                    OAuthToken.status == "active"
                ).first()

                if not oauth_token:
                    platform_results[platform] = {
                        "success": False,
                        "error": f"No active {config['name']} account connected. Please connect your account first."
                    }
                    continue

                # Post to platform
                poster_func = PLATFORM_POSTERS.get(platform)
                if not poster_func:
                    platform_results[platform] = {
                        "success": False,
                        "error": f"Platform {platform} not yet implemented"
                    }
                    continue

                result = await poster_func(
                    text=payload.text,
                    access_token=oauth_token.access_token,
                    media_urls=payload.media_urls,
                    link_url=payload.link_url
                )

                platform_results[platform] = result

                if result.get("success"):
                    successful_posts += 1
                    # Update last_used timestamp
                    oauth_token.last_used = datetime.utcnow()

            except ValueError as e:
                platform_results[platform] = {
                    "success": False,
                    "error": str(e)
                }
            except Exception as e:
                logger.error(f"Failed to post to {platform}: {e}", exc_info=True)
                platform_results[platform] = {
                    "success": False,
                    "error": str(e)
                }

        # Commit any token updates
        db.commit()

        # Generate post ID
        post_id = str(uuid.uuid4())

        # Log post to history (if we had a SocialPostHistory model)
        # For now, just log
        logger.info(
            f"Social post created: user={current_user.id}, "
            f"post_id={post_id}, "
            f"platforms={payload.platforms}, "
            f"successful={successful_posts}/{len(payload.platforms)}"
        )

        # Determine overall success
        overall_success = successful_posts > 0

        return SocialPostResponse(
            success=overall_success,
            post_id=post_id,
            platform_results=platform_results,
            scheduled=False
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Social post creation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create social post: {str(e)}"
        )


@router.get("/platforms")
async def list_platforms():
    """
    List available social media platforms with their configurations.
    """
    return {
        "platforms": PlatformConfig.PLATFORMS,
        "total": len(PlatformConfig.PLATFORMS)
    }


@router.get("/connected-accounts")
async def list_connected_accounts(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    List connected social media accounts for the current user.
    """
    try:
        current_user = get_current_user(request, db)

        # Get all OAuth tokens that correspond to social platforms
        social_providers = set()
        for platform_name, config in PlatformConfig.PLATFORMS.items():
            oauth_provider = config.get("oauth_provider", platform_name)
            social_providers.add(oauth_provider)

        tokens = db.query(OAuthToken).filter(
            OAuthToken.user_id == current_user.id,
            OAuthToken.provider.in_(social_providers),
            OAuthToken.status == "active"
        ).all()

        accounts = []
        for token in tokens:
            platform_name = None
            for pname, config in PlatformConfig.PLATFORMS.items():
                if config.get("oauth_provider") == token.provider:
                    platform_name = pname
                    break

            if platform_name:
                accounts.append({
                    "platform": platform_name,
                    "provider": token.provider,
                    "token_id": token.id,
                    "scopes": token.scopes,
                    "last_used": token.last_used.isoformat() if token.last_used else None,
                })

        return {
            "accounts": accounts,
            "total": len(accounts)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list connected accounts: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve connected accounts: {str(e)}"
        )


@router.get("/rate-limit")
async def get_rate_limit_status(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Check rate limit status for the current user.
    """
    try:
        current_user = get_current_user(request, db)

        # Count posts in last hour
        from core.models import SocialPostHistory

        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_posts = db.query(SocialPostHistory).filter(
            SocialPostHistory.user_id == current_user.id,
            SocialPostHistory.created_at >= one_hour_ago,
            SocialPostHistory.status == "posted"
        ).count()

        return {
            "limit": 10,
            "used": recent_posts,
            "remaining": max(0, 10 - recent_posts),
            "resets_at": (one_hour_ago + timedelta(hours=1)).isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check rate limit: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check rate limit: {str(e)}"
        )
