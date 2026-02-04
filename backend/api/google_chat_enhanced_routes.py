"""
Google Chat Enhanced API Routes

Complete Google Chat integration with OAuth, interactive cards, dialogs, and space management.
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import Depends, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db_session
from integrations.atom_google_chat_integration import atom_google_chat_integration

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/google-chat", tags=["Google-Chat"])

# ============================================================================
# OAuth & Authentication Endpoints
# ============================================================================

class OAuthURLRequest(BaseModel):
    """Request to get OAuth URL"""
    redirect_uri: str = Field(..., description="Redirect URI after auth")
    state: Optional[str] = Field(None, description="State parameter for security")
    access_type: str = Field("offline", description="Access type: online or offline")
    prompt: str = Field("consent", description="OAuth prompt")
    include_granted_scopes: Optional[bool] = Field(False, description="Filter to granted scopes")
    login_hint: Optional[str] = Field(None, description="Email address hint")

@router.post("/oauth/url")
async def get_oauth_url(request: OAuthURLRequest):
    """
    Get Google OAuth 2.0 authorization URL.

    Returns authorization URL for user to grant access.
    """
    try:
        oauth_url = await atom_google_chat_integration.get_oauth_url(
            redirect_uri=request.redirect_uri,
            state=request.state,
            access_type=request.access_type,
            prompt=request.prompt,
            include_granted_scopes=request.include_granted_scopes,
            login_hint=request.login_hint,
        )

        return {
            "success": True,
            "oauth_url": oauth_url,
            "state": request.state,
        }
    except Exception as e:
        logger.error(f"Error generating OAuth URL: {e}")
        return {"success": False, "error": str(e)}

class OAuthCallbackRequest(BaseModel):
    """Request to handle OAuth callback"""
    code: str = Field(..., description="Authorization code from Google")
    state: Optional[str] = Field(None, description="State parameter")
    redirect_uri: str = Field(..., description="Original redirect URI")

@router.post("/oauth/callback")
async def handle_oauth_callback(request: OAuthCallbackRequest):
    """
    Handle OAuth 2.0 callback from Google.

    Exchanges authorization code for access token.
    """
    try:
        result = await atom_google_chat_integration.handle_oauth_callback(
            code=request.code,
            state=request.state,
            redirect_uri=request.redirect_uri,
        )

        return result
    except Exception as e:
        logger.error(f"Error handling OAuth callback: {e}")
        raise router.internal_error(details=str(e))

class RefreshTokenRequest(BaseModel):
    """Request to refresh access token"""
    refresh_token: str = Field(..., description="Refresh token")

@router.post("/oauth/refresh")
async def refresh_access_token(request: RefreshTokenRequest):
    """
    Refresh an access token using refresh token.

    Returns new access token and refresh token.
    """
    try:
        result = await atom_google_chat_integration.refresh_access_token(
            refresh_token=request.refresh_token,
        )

        return result
    except Exception as e:
        logger.error(f"Error refreshing token: {e}")
        return {"success": False, "error": str(e)}

# ============================================================================
# Interactive Card Endpoints
# ============================================================================

class SendCardRequest(BaseModel):
    """Request to send interactive card"""
    space_name: str = Field(..., description="Google Chat space name")
    message: Optional[str] = Field(None, description="Card message text")
    card: Dict[str, Any] = Field(..., description="Card definition")
    thread_key: Optional[str] = Field(None, description="Thread key for reply")
    header: Optional[Dict[str, Any]] = Field(None)
    sections: List[Dict[str, Any]] = []
    widgets: List[Dict[str, Any]] = []
    cards: List[Dict[str, Any]] = []

@router.post("/send-card")
async def send_interactive_card(request: SendCardRequest):
    """
    Send an interactive card to Google Chat.

    Cards can contain:
    - Buttons (text icon, onclick actions)
    - Text paragraphs
    - Image content
    - Input widgets
    - Decorated text
    """
    try:
        result = await atom_google_chat_integration.send_card(
            space_name=request.space_name,
            message=request.message,
            card=request.card,
            thread_key=request.thread_key,
            header=request.header,
            sections=request.sections,
            widgets=request.widgets,
            cards=request.cards,
        )

        if not result.get("success"):
            raise router.internal_error(details=result.get("error", "Unknown error"))
        return result

    except Exception as e:
        logger.error(f"Error sending card: {e}")
        raise router.internal_error(details=str(e))

class UpdateCardRequest(BaseModel):
    """Request to update an existing card"""
    space_name: str = Field(..., description="Google Chat space name")
    message_name: str = Field(..., description="Update message to update")

@router.put("/update-card")
async def update_interactive_card(request: UpdateCardRequest):
    """
    Update an existing interactive card.

    Allows modifying card content after sending.
    """
    try:
        result = await atom_google_chat_integration.update_card(
            space_name=request.space_name,
            message_name=request.message_name,
        )

        return result

    except Exception as e:
        logger.error(f"Error updating card: {e}")
        return {"success": False, "error": str(e)}

# ============================================================================
# Dialog Endpoints
# ============================================================================

class OpenDialogRequest(BaseModel):
    """Request to open a dialog"""
    space_name: str = Field(..., description="Google Chat space name")
    dialog: Dict[str, Any] = Field(..., description="Dialog definition")

@router.post("/open-dialog")
async def open_dialog(request: OpenDialogRequest):
    """
    Open a dialog in Google Chat.

    Dialogs are modal windows for user interaction.
    """
    try:
        result = await atom_google_chat_integration.open_dialog(
            space_name=request.space_name,
            dialog=request.dialog,
        )

        if not result.get("success"):
            raise router.internal_error(details=result.get("error", "Unknown error"))
        return result

    except Exception as e:
        logger.error(f"Error opening dialog: {e}")
        raise router.internal_error(details=str(e))

# ============================================================================
# Space Management Endpoints
# ============================================================================

class CreateSpaceRequest(BaseModel):
    """Request to create a Google Chat space"""
    display_name: str = Field(..., description="Space display name")
    description: Optional[str] = Field(None)
    space_type: Optional[str] = Field("SPACE", description="SPACE or GROUP_CHAT")
    members: List[str] = Field([])  # List of email addresses

@router.post("/spaces/create")
async def create_space(request: CreateSpaceRequest):
    """
    Create a new Google Chat space.

    Creates a named space and adds specified members.
    """
    try:
        result = await atom_google_chat_integration.create_space(
            display_name=request.display_name,
            description=request.description,
            space_type=request.space_type,
            members=request.members,
        )

        if not result.get("success"):
            raise router.internal_error(details=result.get("error", "Unknown error"))
        return result

    except Exception as e:
        logger.error(f"Error creating space: {e}")
        raise router.internal_error(details=str(e))

@router.get("/spaces/list")
async def list_spaces():
    """List all available Google Chat spaces"""
    try:
        result = await atom_google_chat_integration.list_spaces()
        return result
    except Exception as e:
        logger.error(f"Error listing spaces: {e}")
        return {"success": False, "error": str(e), "spaces": []}

@router.get("/spaces/{space_name}/info")
async def get_space_info(space_name: str):
    """Get detailed information about a space"""
    try:
        result = await atom_google_chat_integration.get_space_info(space_name)
        return result
    except Exception as e:
        logger.error(f"Error getting space info: {e}")
        return {"success": False, "error": str(e)}

@router.post("/spaces/{space_name}/members/add")
async def add_space_members(
    space_name: str,
    members: List[str] = Query(..., description="List of email addresses")
):
    """Add members to a Google Chat space"""
    try:
        result = await atom_google_chat_integration.add_space_members(
            space_name=space_name,
            members=members,
        )

        return result
    except Exception as e:
        logger.error(f"Error adding members: {e}")
        return {"success": False, "error": str(e)}

@router.post("/spaces/{space_name}/members/remove")
async def remove_space_members(
    space_name: str,
    members: List[str] = Query(..., description="List of email addresses")
):
    """Remove members from a Google Chat space"""
    try:
        result = await atom_google_chat_integration.remove_space_members(
            space_name=space_name,
            members=members,
        )

        return result
    except Exception as e:
        logger.error(f"Error removing members: {e}")
        return {"success": False, "error": str(e)}

@router.post("/spaces/{space_name}/webhook")
async def set_space_webhook(
    space_name: str,
    webhook_url: str,
    state: Optional[str] = None,
):
    """Configure webhook for a space"""
    try:
        result = await atom_google_chat_integration.set_space_webhook(
            space_name=space_name,
            webhook_url=webhook_url,
            state=state,
        )

        return result
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return {"success": False, "error": str(e)}

# ============================================================================
# Message Endpoints
# ============================================================================

class SendMessageRequest(BaseModel):
    """Request to send message to Google Chat"""
    space_name: str = Field(..., description="Google Chat space name")
    text: str = Field(..., description="Message text")
    thread_key: Optional[str] = Field(None, description="Thread key for reply")
    message_id: Optional[str] = Field(None)  # For replying

@router.post("/send-message")
async def send_google_chat_message(request: SendMessageRequest):
    """Send a text message to Google Chat"""
    try:
        result = await atom_google_chat_integration.send_message(
            space_name=request.space_name,
            text=request.text,
            thread_key=request.thread_key,
            message_id=request.message_id,
        )

        if not result.get("success"):
            raise router.internal_error(details=result.get("error", "Unknown error"))
        return result

    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise router.internal_error(details=str(e))

class UploadFileRequest(BaseModel):
    """Request to upload a file to Google Chat"""
    space_name: str = Field(..., description="Google Chat space name")
    file_path: str = Field(..., description="Path to file to upload")
    content: Optional[str] = Field(None, description="File content for upload")
    filename: Optional[str] = Field(None)
    mime_type: Optional[str] = Field(None)

@router.post("/upload-file")
async def upload_file(request: UploadFileRequest):
    """Upload a file to Google Chat"""
    try:
        result = await atom_google_chat_integration.upload_file(
            space_name=request.space_name,
            file_path=request.file_path,
            content=request.content,
            filename=request.filename,
            mime_type=request.mime_type,
        )

        return result
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return {"success": False, "error": str(e)}

# ============================================================================
# Health & Status Endpoints
# ============================================================================

@router.get("/health")
async def google_chat_health():
    """Google Chat health check"""
    try:
        status = await atom_google_chat_integration.get_service_status()
        if status.get("status") == "active":
            return {"status": "healthy", "service": "Google Chat"}
        return {"status": "inactive", "service": "Google Chat"}
    except Exception as e:
        logger.error(f"Google Chat health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

@router.get("/status")
async def google_chat_status():
    """Get detailed Google Chat status"""
    try:
        return await atom_google_chat_integration.get_service_status()
    except Exception as e:
        logger.error(f"Google Chat status check failed: {e}")
        return {"status": "error", "error": str(e)}

@router.get("/capabilities")
async def google_chat_capabilities():
    """Get Google Chat integration capabilities"""
    return {
        "platform": "Google Chat",
        "features": {
            "messaging": True,
            "oauth": True,
            "interactive_cards": True,
            "dialogs": True,
            "space_management": True,
            "file_upload": True,
            "webhooks": True,
            "threading": True,
        },
        "governance": {
            "student": {"blocked": True},
            "intern": {"requires_approval": True},
            "supervised": {"auto_approved": True, "monitored": True},
            "autonomous": {"full_access": True},
        },
        "interactive_components": {
            "cards": True,
            "buttons": True,
            "dialogs": True,
            "input_widgets": True,
            "image_content": True,
        },
    }
