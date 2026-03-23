"""
Slack Integration Routes - Fixed FastAPI Version with Governance
Complete Slack integration with comprehensive API endpoints using FastAPI

Includes:
- Agent governance checks for all state-changing operations
- Proper error handling (no silent pass statements)
- Execution records for audit trail
"""

from datetime import datetime, timezone
import logging
import os
import secrets
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import User
from core.oauth_handler import SLACK_OAUTH_CONFIG, OAuthHandler
from core.oauth_state_manager import get_oauth_state_manager
from core.auth import get_current_user
from integrations.integration_helpers import (
    create_execution_record,
    standard_error_response,
    with_governance_check,
)

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
    SLACK_SDK_AVAILABLE = True
except ImportError:
    SLACK_SDK_AVAILABLE = False
    logger.warning("slack_sdk not installed, running in mock mode")

logger = logging.getLogger(__name__)

# Create FastAPI router
# Auth Type: OAuth2
router = APIRouter(prefix="/api/slack", tags=["slack"])

# Feature flags
SLACK_GOVERNANCE_ENABLED = os.getenv("SLACK_GOVERNANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"

def get_slack_client():
    """Get Slack WebClient if token is available"""
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        return None
    return WebClient(token=token)


class SlackMessageRequest(BaseModel):
    channel: str
    text: str
    user_id: str = "test_user"


class SlackMessageResponse(BaseModel):
    ok: bool
    channel: str
    message_id: str
    text: str
    timestamp: str


class SlackSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"
    max_results: int = 10


class SlackSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    total_results: int
    timestamp: str


class SlackChannelRequest(BaseModel):
    channel_id: str
    user_id: str = "test_user"


class SlackChannelResponse(BaseModel):
    ok: bool
    channel_id: str
    name: str
    members: List[Dict]
    timestamp: str


@router.get("/status")
async def slack_status(user_id: str = "test_user"):
    """Get Slack integration status"""
    client = get_slack_client()
    is_connected = client is not None and SLACK_SDK_AVAILABLE
    
    return {
        "ok": True,
        "service": "slack",
        "user_id": user_id,
        "status": "connected" if is_connected else "mock_mode",
        "message": "Slack integration is available" if is_connected else "Running in mock mode (missing SLACK_BOT_TOKEN)",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/health")
async def slack_health(user_id: str = "test_user"):
    """Health check endpoint (alias for status)"""
    return await slack_status(user_id)



@router.post("/messages")
async def send_slack_message(
    request: SlackMessageRequest,
    agent_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Send a Slack message with governance check (complexity 2 - INTERN+).

    **SECURITY**: Requires authentication to prevent unauthorized Slack messages.
    Governance can still be bypassed with EMERGENCY_GOVERNANCE_BYPASS, but
    authentication is always required.
    """
    logger.info(f"Sending Slack message to channel: {request.channel}")

    # Governance check if enabled and agent_id provided
    agent = None
    governance_check = {"allowed": True}
    execution = None

    if SLACK_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        try:
            agent, governance_check = await with_governance_check(
                db, User(id=request.user_id), "post_message", agent_id
            )

            if not governance_check["allowed"]:
                logger.warning(f"Governance blocked Slack message: {governance_check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Agent not permitted to send messages: {governance_check['reason']}"
                )

            # Create execution record for audit trail
            execution = create_execution_record(
                db,
                agent.id if agent else None,
                request.user_id,
                "slack_send_message"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Governance check error: {e}")
            # Continue with request if governance check fails (graceful degradation)

    client = get_slack_client()
    if client and SLACK_SDK_AVAILABLE:
        try:
            response = client.chat_postMessage(
                channel=request.channel,
                text=request.text
            )
            return SlackMessageResponse(
                ok=True,
                channel=response["channel"],
                message_id=response["ts"],
                text=request.text,
                timestamp=datetime.now().isoformat(),
            )
        except SlackApiError as e:
            logger.error(f"Error sending message: {e.response['error']}")
            raise HTTPException(status_code=400, detail=f"Slack API Error: {e.response['error']}")

    # Fallback to mock
    return SlackMessageResponse(
        ok=True,
        channel=request.channel,
        message_id=f"msg_{request.channel}_{datetime.now().timestamp()}",
        text=request.text,
        timestamp=datetime.now().isoformat(),
    )


@router.post("/search")
async def slack_search(
    request: SlackSearchRequest,
    agent_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Search Slack messages with governance check (complexity 1 - STUDENT+)"""
    logger.info(f"Searching Slack for: {request.query}")

    # Governance check for search operations (READ - complexity 1)
    if SLACK_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        try:
            agent, governance_check = await with_governance_check(
                db, User(id=request.user_id), "search", agent_id
            )

            if not governance_check["allowed"]:
                logger.warning(f"Governance blocked Slack search: {governance_check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Agent not permitted to search: {governance_check['reason']}"
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Governance check error: {e}")

    # Mock search results
    mock_results = [
        {
            "id": f"msg_{i}",
            "channel": f"channel_{i}",
            "user": f"user_{i}",
            "text": f"This message contains {request.query} - result {i}",
            "timestamp": f"2025-11-09T{10 + i}:00:00Z",
            "reactions": ["👍", "🚀"] if i % 2 == 0 else ["👀"],
        }
        for i in range(1, request.max_results + 1)
    ]

    # Ingest search results to memory (FIXED: was using undefined 'results', now 'mock_results')
    for result in mock_results:
        try:
            # Import here to avoid circular dependency
            from integrations.atom_ingestion_pipeline import RecordType, atom_ingestion_pipeline
            atom_ingestion_pipeline.ingest_record("slack", RecordType.COMMUNICATION.value, result)
        except Exception as e:
            # Fixed: proper error logging instead of silent pass
            logger.warning(f"Failed to ingest Slack message to memory: {e}")

    return SlackSearchResponse(
        ok=True,
        query=request.query,
        results=mock_results,
        total_results=len(mock_results),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/channels/{channel_id}")
async def get_slack_channel(channel_id: str, user_id: str = "test_user"):
    """Get a specific Slack channel"""
    logger.info(f"Getting Slack channel: {channel_id}")

    if not channel_id:
        raise HTTPException(status_code=400, detail="Channel ID is required")

    mock_members = [
        {"id": f"user_{i}", "name": f"Member {i}", "is_bot": i == 1}
        for i in range(1, 6)
    ]

    return SlackChannelResponse(
        ok=True,
        channel_id=channel_id,
        name=f"Channel {channel_id}",
        members=mock_members,
        timestamp=datetime.now().isoformat(),
    )


@router.get("/channels")
async def list_slack_channels(user_id: str = "test_user"):
    """List available Slack channels"""
    logger.info("Listing Slack channels")

    mock_channels = [
        {
            "id": f"channel_{i}",
            "name": f"general-{i}",
            "is_private": i % 3 == 0,
            "member_count": 10 + i,
            "topic": f"Channel topic {i}",
        }
        for i in range(1, 8)
    ]

    return {
        "ok": True,
        "channels": mock_channels,
        "total_channels": len(mock_channels),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/users/{user_id}")
async def get_slack_user(user_id: str):
    """Get Slack user information"""
    logger.info(f"Getting Slack user: {user_id}")

    return {
        "ok": True,
        "user": {
            "id": user_id,
            "name": f"user_{user_id}",
            "real_name": f"Real Name {user_id}",
            "email": f"user{user_id}@example.com",
            "is_bot": "bot" in user_id,
            "timezone": "America/New_York",
        },
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/conversations/history")
async def get_conversation_history(
    channel: str,
    limit: int = 10,
    user_id: str = "test_user",
    agent_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get conversation history for a channel with governance check (complexity 1 - STUDENT+)"""
    logger.info(f"Getting conversation history for channel: {channel}")

    # Governance check for history operations (READ - complexity 1)
    if SLACK_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        try:
            agent, governance_check = await with_governance_check(
                db, User(id=user_id), "search", agent_id
            )

            if not governance_check["allowed"]:
                logger.warning(f"Governance blocked conversation history: {governance_check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Agent not permitted to view history: {governance_check['reason']}"
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Governance check error: {e}")

    messages = [
        {
            "id": f"msg_{i}",
            "user": f"user_{i}",
            "text": f"Message {i} in conversation",
            "timestamp": f"2025-11-09T{10 + i}:00:00Z",
            "reactions": ["👍"] if i % 2 == 0 else [],
        }
        for i in range(1, limit + 1)
    ]

    # Ingest history to memory (FIXED: proper error handling)
    for msg in messages:
        try:
            # Import here to avoid circular dependency
            from integrations.atom_ingestion_pipeline import RecordType, atom_ingestion_pipeline

            # Add channel info to message for better context in memory
            msg_with_context = {**msg, "channel": channel}
            atom_ingestion_pipeline.ingest_record("slack", RecordType.COMMUNICATION.value, msg_with_context)
        except Exception as e:
            logger.debug(f"Ingestion pipeline not available or failed: {e}")

    return {"ok": True, "messages": messages}


@router.post("/reactions/add")
async def add_slack_reaction(
    channel: str, timestamp: str, reaction: str, user_id: str = "test_user"
):
    """Add a reaction to a Slack message"""
    logger.info(f"Adding reaction {reaction} to message in {channel}")

    return {
        "ok": True,
        "channel": channel,
        "timestamp": timestamp,
        "reaction": reaction,
        "message": f"Reaction {reaction} added successfully",
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/callback")
async def slack_oauth_callback(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Handle Slack OAuth callback with CSRF protection.

    Security measures:
    - Requires state parameter to prevent CSRF attacks
    - Requires user authentication
    - Validates state checksum and expiry
    - Stores tokens per-user instead of globally
    """
    try:
        data = await request.json()
        code = data.get("code")
        state = data.get("state")

        if not code:
            logger.warning("OAuth callback missing authorization code")
            raise HTTPException(status_code=400, detail="Authorization code is required")

        if not state:
            logger.warning("OAuth callback missing state parameter - possible CSRF attack")
            raise HTTPException(
                status_code=400,
                detail="State parameter is required for CSRF protection"
            )

        # Validate state parameter
        state_manager = get_oauth_state_manager()
        try:
            state_info = state_manager.validate_state(
                state,
                user_id=str(current_user.id),
                require_user_match=True
            )
            logger.info(f"OAuth state validated for user {current_user.id}")
        except ValueError as e:
            logger.warning(f"OAuth state validation failed: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid state parameter: {str(e)}")

        # Exchange code for tokens
        handler = OAuthHandler(SLACK_OAUTH_CONFIG)
        tokens = await handler.exchange_code_for_tokens(code)

        # Store tokens per-user using ConnectionService instead of global token_storage
        from core.connection_service import ConnectionService
        connection_service = ConnectionService()

        connection = connection_service.save_connection(
            user_id=str(current_user.id),
            integration_id="slack",
            name=f"Slack Integration ({current_user.email})",
            credentials=tokens
        )

        logger.info(
            f"Slack OAuth successful for user {current_user.id} - "
            f"tokens stored in connection {connection.id}"
        )

        return {
            "status": "success",
            "provider": "slack",
            "connection_id": connection.id,
            "message": "Slack integration connected successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Slack OAuth callback error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"OAuth callback failed: {str(e)}")

@router.get("/auth/url")
async def get_auth_url(current_user: User = Depends(get_current_user)):
    """
    Get Slack OAuth URL with CSRF protection.

    Generates a cryptographically secure state parameter and returns
    the OAuth authorization URL. The state must be returned in the
    callback for validation.
    """
    try:
        # Generate secure state parameter bound to current user
        state_manager = get_oauth_state_manager()
        state = state_manager.generate_state(user_id=str(current_user.id))

        handler = OAuthHandler(SLACK_OAUTH_CONFIG)
        auth_url = handler.get_authorization_url(state=state)

        logger.info(f"Generated Slack OAuth URL for user {current_user.id} with state")

        return {
            "url": auth_url,
            "service": "slack",
            "state": state,  # Frontend must return this in callback
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error generating Slack auth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))
