"""
Notion Integration Routes
Complete Notion OAuth integration with secure token storage
"""

from datetime import datetime, timedelta
import logging
import os
from typing import Dict, List, Optional
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.models import NotionToken, User

logger = logging.getLogger(__name__)

# Auth Type: OAuth2
router = APIRouter(prefix="/api/notion", tags=["notion"])

# Feature flags
NOTION_OAUTH_ENABLED = os.getenv("NOTION_OAUTH_ENABLED", "true").lower() == "true"
EMERGENCY_OAUTH_BYPASS = os.getenv("EMERGENCY_OAUTH_BYPASS", "false").lower() == "true"

# Pydantic models
class NotionSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"

class NotionSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    timestamp: str


@router.get("/auth/url")
async def get_auth_url(current_user: User = Depends(get_current_user)):
    """
    Get Notion OAuth URL for user authentication.

    Returns the Notion OAuth URL that users should visit to authorize
    Atom to access their Notion workspace.
    """
    notion_client_id = os.getenv("NOTION_CLIENT_ID")
    if not notion_client_id:
        raise HTTPException(
            status_code=500,
            detail="Notion client ID not configured. Please set NOTION_CLIENT_ID environment variable."
        )

    redirect_uri = os.getenv("NOTION_REDIRECT_URI", "http://localhost:8000/api/notion/callback")

    auth_url = (
        f"https://api.notion.com/v1/oauth/authorize"
        f"?client_id={notion_client_id}"
        f"&response_type=code"
        f"&owner=user"
        f"&redirect_uri={redirect_uri}"
        f"&state={current_user.id}"  # Use user_id as state for verification
    )

    return {
        "success": True,
        "url": auth_url,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/callback")
async def handle_oauth_callback(
    code: str,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Handle Notion OAuth callback.

    Exchange the authorization code for access tokens and store them in the database.

    Args:
        code: Authorization code from Notion
        state: State parameter (user_id) for CSRF protection
        error: Error code if authorization failed
        error_description: Error description if authorization failed
        db: Database session
    """
    # Handle authorization errors
    if error:
        logger.error(f"Notion OAuth error: {error} - {error_description}")
        raise HTTPException(
            status_code=400,
            detail=f"Notion authorization failed: {error_description or error}"
        )

    notion_client_id = os.getenv("NOTION_CLIENT_ID")
    notion_client_secret = os.getenv("NOTION_CLIENT_SECRET")
    notion_redirect_uri = os.getenv("NOTION_REDIRECT_URI", "http://localhost:8000/api/notion/callback")

    if not all([notion_client_id, notion_client_secret]):
        raise HTTPException(
            status_code=500,
            detail="Notion client credentials not configured. Please set NOTION_CLIENT_ID and NOTION_CLIENT_SECRET environment variables."
        )

    try:
        # Exchange authorization code for access token
        import requests

        token_response = requests.post(
            "https://api.notion.com/v1/oauth/token",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": notion_redirect_uri,
                "client_id": notion_client_id,
                "client_secret": notion_client_secret,
            }
        )

        if token_response.status_code != 200:
            logger.error(f"Notion token exchange failed: {token_response.text}")
            raise HTTPException(
                status_code=400,
                detail="Failed to exchange authorization code for access token"
            )

        token_data = token_response.json()

        # Extract token information
        access_token = token_data.get("access_token")
        workspace_id = token_data.get("workspace_id")
        workspace_name = token_data.get("workspace_name")
        workspace_icon = token_data.get("workspace_icon")
        bot_id = token_data.get("bot_id")
        owner_type = token_data.get("owner", {}).get("type")  # "user" or "workspace"

        # Get user from state (if provided) or use a default
        user_id = state

        if not user_id:
            raise HTTPException(
                status_code=400,
                detail="Invalid state parameter. Please restart the OAuth flow."
            )

        # Check if user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        # Deactivate old tokens for this user and workspace
        db.query(NotionToken).filter(
            NotionToken.user_id == user_id,
            NotionToken.workspace_id == workspace_id,
            NotionToken.status == "active"
        ).update({"status": "revoked"})

        # Notion access tokens don't expire, but we set a default for safety
        expires_at = datetime.utcnow() + timedelta(days=365)

        # Store new token
        notion_token = NotionToken(
            user_id=user_id,
            access_token=access_token,
            refresh_token=None,  # Notion doesn't use refresh tokens
            notion_user_id=bot_id,
            workspace_name=workspace_name,
            workspace_icon=workspace_icon,
            workspace_id=workspace_id,
            token_type="bearer",
            owner_type=owner_type,
            expires_at=expires_at,
            status="active"
        )

        db.add(notion_token)
        db.commit()

        logger.info(f"Successfully stored Notion token for user {user_id}, workspace {workspace_name}")

        return {
            "success": True,
            "status": "success",
            "workspace_id": workspace_id,
            "workspace_name": workspace_name,
            "message": "Notion authentication successful",
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Notion OAuth callback error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Notion authentication failed: {str(e)}"
        )


# Dependency for Notion access token
async def get_notion_access_token(
    authorization: Optional[str] = Header(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> str:
    """
    Get Notion access token from request headers or database.

    Priority order:
    1. Authorization header (Bearer token) - for API access
    2. Database lookup - for web/app access with user session

    Args:
        authorization: Authorization header value
        current_user: Current authenticated user from session
        db: Database session

    Returns:
        str: Valid Notion access token

    Raises:
        HTTPException: If no valid token found
    """
    # 1. Check Authorization header first (API access)
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        # For API access, we trust the header if user is authenticated
        logging.info(f"Using Notion access token from Authorization header for user {current_user.id}")
        return token

    # 2. Check database for stored token (web/app access)
    notion_token = db.query(NotionToken).filter(
        NotionToken.user_id == current_user.id,
        NotionToken.status == "active"
    ).first()

    if notion_token:
        # Check if token is expired
        if notion_token.expires_at and notion_token.expires_at < datetime.utcnow():
            logging.warning(f"Notion token for user {current_user.id} is expired")
            # Mark as expired
            notion_token.status = "expired"
            db.commit()
            raise HTTPException(
                status_code=401,
                detail="Notion access token expired. Please re-authenticate with Notion."
            )

        # Update last_used timestamp
        notion_token.last_used = datetime.utcnow()
        db.commit()

        logging.info(f"Using Notion access token from database for user {current_user.id}")
        return notion_token.access_token

    # 3. No token found
    logging.warning(f"No Notion token found for user {current_user.id}")
    raise HTTPException(
        status_code=401,
        detail="Notion authentication required. Please connect your Notion workspace."
    )


@router.get("/status")
async def notion_status(access_token: str = Depends(get_notion_access_token)):
    """Get Notion integration status"""
    try:
        # Validate token by making a simple API call
        import requests

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Notion-Version": "2022-06-28"
        }

        response = requests.get("https://api.notion.com/v1/users/me", headers=headers)

        if response.status_code == 200:
            user_data = response.json()
            return {
                "success": True,
                "service": "notion",
                "status": "connected",
                "user": user_data,
                "message": "Notion integration is active and connected",
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return {
                "success": False,
                "service": "notion",
                "status": "disconnected",
                "error": f"Token validation failed: {response.status_code}",
                "message": "Notion integration is disconnected",
                "timestamp": datetime.now().isoformat(),
            }

    except Exception as e:
        logger.error(f"Failed to check Notion status: {e}")
        return {
            "success": False,
            "service": "notion",
            "status": "error",
            "error": str(e),
            "message": "Failed to check Notion integration status",
            "timestamp": datetime.now().isoformat(),
        }


@router.post("/search")
async def notion_search(
    request: NotionSearchRequest,
    access_token: str = Depends(get_notion_access_token)
):
    """Search Notion pages and databases"""
    logger.info(f"Searching Notion for: {request.query}")

    try:
        import requests

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }

        # Use Notion's search API
        search_body = {
            "query": request.query,
            "filter": {
                "value": "page",
                "property": "object"
            }
        }

        response = requests.post(
            "https://api.notion.com/v1/search",
            headers=headers,
            json=search_body
        )

        if response.status_code != 200:
            logger.error(f"Notion search failed: {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Notion search failed: {response.text}"
            )

        data = response.json()

        # Transform results to match expected format
        results = []
        for result in data.get("results", []):
            if result.get("object") == "page":
                page_id = result.get("id", "")
                title = "Untitled"
                properties = result.get("properties", {})

                # Try to extract title from properties
                if "Name" in properties:
                    title_obj = properties["Name"]
                    if title_obj.get("type") == "title" and title_obj.get("title"):
                        title = title_obj["title"][0].get("plain_text", "Untitled")

                results.append({
                    "id": page_id.replace("-", ""),
                    "title": title,
                    "type": "page",
                    "url": result.get("url", ""),
                    "last_edited": result.get("last_edited_time", ""),
                    "snippet": f"Page matching '{request.query}'",
                })

        return {
            "success": True,
            "ok": True,
            "query": request.query,
            "results": results,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Notion search error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Notion search failed: {str(e)}"
        )


@router.get("/pages/{page_id}")
async def get_notion_page(
    page_id: str,
    access_token: str = Depends(get_notion_access_token)
):
    """Get a specific Notion page"""
    try:
        import requests

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Notion-Version": "2022-06-28"
        }

        # Add hyphens to page ID if needed (Notion IDs are 32 chars with hyphens)
        formatted_id = page_id
        if len(page_id) == 32 and "-" not in page_id:
            formatted_id = f"{page_id[0:8]}-{page_id[8:12]}-{page_id[12:16]}-{page_id[16:20]}-{page_id[20:32]}"

        response = requests.get(
            f"https://api.notion.com/v1/pages/{formatted_id}",
            headers=headers
        )

        if response.status_code != 200:
            logger.error(f"Notion page fetch failed: {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to fetch Notion page: {response.text}"
            )

        data = response.json()

        # Extract page content
        title = "Untitled"
        properties = data.get("properties", {})

        if "Name" in properties:
            title_obj = properties["Name"]
            if title_obj.get("type") == "title" and title_obj.get("title"):
                title = title_obj["title"][0].get("plain_text", "Untitled")

        return {
            "success": True,
            "ok": True,
            "page_id": page_id,
            "title": title,
            "content": data,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Notion page fetch error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch Notion page: {str(e)}"
        )


@router.get("/health")
async def notion_health():
    """Check Notion integration health"""
    return {
        "success": True,
        "ok": True,
        "service": "notion",
        "status": "available",
        "message": "Notion integration is available",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/")
async def notion_root():
    """Notion integration root endpoint"""
    return {
        "service": "notion",
        "status": "available",
        "endpoints": [
            "/auth/url",
            "/callback",
            "/status",
            "/search",
            "/pages/{page_id}",
            "/health",
        ],
        "description": "Notion workspace and content integration",
    }
