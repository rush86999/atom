"""
Social Media Integration Routes

Provides endpoints for posting to social media platforms.
Supports Twitter (X), LinkedIn, Facebook, and other platforms.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import OAuthToken, SocialMediaAudit, User
from core.security_dependencies import get_current_user

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
    agent_id: Optional[str] = Field(None, description="Agent ID requesting the post")

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
    link_url: str = None,
    agent_id: Optional[str] = None,
    agent_execution_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Session = None
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
    link_url: str = None,
    agent_id: Optional[str] = None,
    agent_execution_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Session = None
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
    link_url: str = None,
    agent_id: Optional[str] = None,
    agent_execution_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Session = None
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create and post to social media platforms.

    Supports immediate posting to Twitter/X, LinkedIn, and Facebook.
    Requires OAuth tokens for each target platform.

    Rate Limits:
    - 10 posts per hour per user (across all platforms)
    - Content length validation per platform

    Governance:
    - SUPERVISED+ maturity required for social media posting
    - All actions are logged to SocialMediaAudit
    - Agent attribution tracked if agent_id provided
    """
    agent_id = None
    agent_execution_id = None
    agent_maturity = None
    governance_check_passed = True
    required_approval = False
    approval_granted = None

    try:

        # Resolve agent if provided
        if payload.agent_id:
            resolver = AgentContextResolver(db)
            agent, context = await resolver.resolve_agent_for_request(
                user_id=str(current_user.id),
                requested_agent_id=payload.agent_id,
                action_type="social_media_post"
            )

            if agent:
                agent_id = str(agent.id)
                agent_maturity = agent.status

                # Check governance
                governance = AgentGovernanceService(db)
                governance_check = governance.can_perform_action(
                    agent_id=agent_id,
                    action_type="social_media_post"
                )

                governance_check_passed = governance_check.get("allowed", False)
                required_approval = governance_check.get("requires_human_approval", False)

                if not governance_check_passed:
                    # Create audit entry for failed governance check
                    audit = SocialMediaAudit(
                        user_id=str(current_user.id),
                        agent_id=agent_id,
                        agent_execution_id=agent_execution_id,
                        platform="multiple",
                        action_type="post",
                        content=payload.text,
                        media_urls=payload.media_urls,
                        link_url=payload.link_url,
                        success=False,
                        error_message="Governance check failed",
                        agent_maturity=agent_maturity,
                        governance_check_passed=False,
                        required_approval=required_approval,
                        approval_granted=False,
                        request_id=str(uuid.uuid4())
                    )
                    db.add(audit)
                    db.commit()

                    raise router.permission_denied_error("social media", "post")

        # Validate platforms
        if not payload.platforms:
            raise router.validation_error("platforms", "At least one platform must be specified")

        # Validate content for each platform
        for platform in payload.platforms:
            valid, error_msg = PlatformConfig.validate_content(platform, payload.text)
            if not valid:
                raise router.validation_error("content", error_msg)

        # Check rate limits
        if not rate_limit_check(current_user.id, db):
            raise router.error_response(
                status_code=429,
                message="Rate limit exceeded: Maximum 10 posts per hour"
            )

        # Handle scheduled posts
        if payload.scheduled_for and payload.scheduled_for > datetime.utcnow():
            from core.task_queue import enqueue_scheduled_post

            post_id = str(uuid.uuid4())

            # Enqueue the scheduled post
            job_id = enqueue_scheduled_post(
                post_id=post_id,
                platforms=payload.platforms,
                text=payload.text,
                scheduled_for=payload.scheduled_for,
                media_urls=payload.media_urls,
                link_url=payload.link_url,
                user_id=current_user.id
            )

            # Check if task queue is available
            if job_id is None:
                raise router.internal_error(
                    message="Task queue is not available",
                    details={"scheduled_posts_disabled": True}
                )

            # Create history record
            from core.models import SocialPostHistory
            history = SocialPostHistory(
                user_id=current_user.id,
                content=payload.text,
                platforms=payload.platforms,
                media_urls=payload.media_urls,
                link_url=payload.link_url,
                scheduled_for=payload.scheduled_for,
                status="scheduled",
                job_id=job_id
            )
            db.add(history)
            db.commit()

            return SocialPostResponse(
                success=True,
                post_id=post_id,
                platform_results={"job_id": job_id},
                scheduled=True,
                scheduled_for=payload.scheduled_for
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

                    # Create audit entry for missing OAuth token
                    audit = SocialMediaAudit(
                        user_id=str(current_user.id),
                        agent_id=agent_id,
                        agent_execution_id=agent_execution_id,
                        platform=platform,
                        action_type="post",
                        content=payload.text,
                        media_urls=payload.media_urls,
                        link_url=payload.link_url,
                        success=False,
                        error_message=f"No active {config['name']} account connected",
                        agent_maturity=agent_maturity or "NONE",
                        governance_check_passed=governance_check_passed,
                        required_approval=required_approval,
                        approval_granted=approval_granted
                    )
                    db.add(audit)
                    db.commit()

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
                    link_url=payload.link_url,
                    agent_id=agent_id,
                    agent_execution_id=agent_execution_id,
                    user_id=str(current_user.id),
                    db=db
                )

                platform_results[platform] = result

                # Create audit entry
                audit = SocialMediaAudit(
                    user_id=str(current_user.id),
                    agent_id=agent_id,
                    agent_execution_id=agent_execution_id,
                    platform=platform,
                    action_type="post",
                    post_id=result.get("post_id"),
                    content=payload.text,
                    media_urls=payload.media_urls,
                    link_url=payload.link_url,
                    success=result.get("success", False),
                    error_message=result.get("error"),
                    platform_response=result,
                    agent_maturity=agent_maturity or "NONE",
                    governance_check_passed=governance_check_passed,
                    required_approval=required_approval,
                    approval_granted=approval_granted
                )
                db.add(audit)

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

        # Commit any token updates and audit entries
        db.commit()

        # Generate post ID
        post_id = str(uuid.uuid4())

        logger.info(
            f"Social post created: user={current_user.id}, "
            f"agent={agent_id}, "
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
        raise router.internal_error(
            message="Failed to create social post",
            details={"error": str(e)}
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List connected social media accounts for the current user.
    """
    try:

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check rate limit status for the current user.
    """
    try:

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
