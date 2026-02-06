"""
Social Media Worker for Background Post Processing

Handles scheduled social media posts in the background using RQ.
Processes posts at their scheduled time and logs results to the database.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


async def process_scheduled_post(
    post_id: str,
    platforms: List[str],
    text: str,
    scheduled_for: datetime,
    media_urls: Optional[List[str]] = None,
    link_url: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict[str, any]:
    """
    Process a scheduled social media post.

    This function is called by the RQ worker when a scheduled post is due.
    It posts to each platform and logs the results.

    Args:
        post_id: Unique identifier for the post
        platforms: List of platform names (twitter, linkedin, facebook)
        text: Post content
        scheduled_for: When the post was scheduled (for logging)
        media_urls: Optional list of image/video URLs
        link_url: Optional link to include in the post
        user_id: User ID for tracking

    Returns:
        Dictionary with platform results
    """
    from core.database import SessionLocal
    from core.models import SocialPostHistory, OAuthToken

    db = SessionLocal()

    try:
        logger.info(f"Processing scheduled post {post_id} for {len(platforms)} platforms")

        # Update status to processing
        history = db.query(SocialPostHistory).filter(
            SocialPostHistory.post_id == post_id
        ).first()

        if not history:
            logger.error(f"SocialPostHistory record not found for post_id={post_id}")
            return {"error": "Post not found in database"}

        history.status = "posting"
        history.posted_at = datetime.utcnow()
        db.commit()

        # Get platform poster functions
        from api.social_media_routes import post_to_twitter, post_to_linkedin, post_to_facebook

        platform_posters = {
            "twitter": post_to_twitter,
            "linkedin": post_to_linkedin,
            "facebook": post_to_facebook,
        }

        platform_results = {}
        successful_posts = 0

        # Post to each platform
        for platform in platforms:
            platform = platform.lower()

            logger.info(f"Posting to {platform} for post {post_id}")

            try:
                # Get OAuth token for this platform and user
                oauth_token = db.query(OAuthToken).filter(
                    OAuthToken.user_id == user_id,
                    OAuthToken.provider == platform,
                    OAuthToken.status == "active"
                ).first()

                if not oauth_token:
                    platform_results[platform] = {
                        "success": False,
                        "error": f"No active {platform} account connected. Please connect your account first."
                    }
                    logger.warning(f"No OAuth token found for {platform}")
                    continue

                # Get the poster function
                poster_func = platform_posters.get(platform)

                if not poster_func:
                    platform_results[platform] = {
                        "success": False,
                        "error": f"Platform {platform} not yet implemented"
                    }
                    logger.warning(f"No poster function for {platform}")
                    continue

                # Post to platform
                result = await poster_func(
                    text=text,
                    access_token=oauth_token.access_token,
                    media_urls=media_urls,
                    link_url=link_url
                )

                platform_results[platform] = result

                if result.get("success"):
                    successful_posts += 1
                    logger.info(f"Successfully posted to {platform}")
                else:
                    logger.error(f"Failed to post to {platform}: {result.get('error')}")

                # Update last_used timestamp
                oauth_token.last_used = datetime.utcnow()

            except Exception as e:
                logger.error(f"Error posting to {platform}: {e}", exc_info=True)
                platform_results[platform] = {
                    "success": False,
                    "error": str(e)
                }

        # Update history with results
        if successful_posts == len(platforms):
            history.status = "posted"
            logger.info(f"Post {post_id} successfully posted to all platforms")
        elif successful_posts > 0:
            history.status = "partial"
            logger.warning(f"Post {post_id} partially posted ({successful_posts}/{len(platforms)})")
        else:
            history.status = "failed"
            history.error_message = "Failed to post to any platform"
            logger.error(f"Post {post_id} failed completely")

        history.platform_results = platform_results
        history.posted_at = datetime.utcnow()
        db.commit()

        return {
            "success": successful_posts > 0,
            "post_id": post_id,
            "platforms": platforms,
            "platform_results": platform_results,
            "successful_posts": successful_posts,
            "total_platforms": len(platforms),
            "status": history.status
        }

    except Exception as e:
        logger.error(f"Failed to process scheduled post {post_id}: {e}", exc_info=True)

        # Update history to failed
        try:
            history = db.query(SocialPostHistory).filter(
                SocialPostHistory.post_id == post_id
            ).first()

            if history:
                history.status = "failed"
                history.error_message = str(e)
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update history: {db_error}")

        raise

    finally:
        db.close()


def process_scheduled_post_sync(*args, **kwargs):
    """
    Synchronous wrapper for process_scheduled_post.

    RQ workers require synchronous functions, so this wrapper
    handles the async execution properly.
    """
    import asyncio

    try:
        # Get or create event loop
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # No event loop in this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(process_scheduled_post(*args, **kwargs))
