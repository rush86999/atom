"""
Intercom API Routes
Complete Intercom integration endpoints for the ATOM platform
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

# Configure logging
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/intercom", tags=["intercom"])


# Pydantic models for Intercom
class IntercomAuthRequest(BaseModel):
    code: str
    redirect_uri: str


class IntercomContact(BaseModel):
    id: str
    type: str = "contact"
    email: str
    name: Optional[str] = None
    phone: Optional[str] = None
    role: str = "user"
    created_at: datetime
    updated_at: datetime
    last_seen_at: Optional[datetime] = None
    custom_attributes: Optional[Dict[str, Any]] = None
    tags: List[str] = []
    companies: List[Dict[str, Any]] = []


class IntercomConversation(BaseModel):
    id: str
    type: str = "conversation"
    created_at: datetime
    updated_at: datetime
    waiting_since: Optional[datetime] = None
    snoozed_until: Optional[datetime] = None
    source: Dict[str, Any]
    contacts: List[Dict[str, Any]]
    conversation_rating: Optional[Dict[str, Any]] = None
    conversation_parts: List[Dict[str, Any]]
    tags: List[str] = []
    assignee: Optional[Dict[str, Any]] = None
    open: bool = True
    read: bool = True
    priority: str = "not_priority"


class IntercomTeam(BaseModel):
    id: str
    type: str = "team"
    name: str
    admin_ids: List[str]
    created_at: datetime
    updated_at: datetime


class IntercomAdmin(BaseModel):
    id: str
    type: str = "admin"
    name: str
    email: str
    job_title: Optional[str] = None
    away_mode_enabled: bool = False
    away_mode_reassign: bool = False
    has_inbox_seat: bool = True
    team_ids: List[str]
    created_at: datetime
    updated_at: datetime


class IntercomTag(BaseModel):
    id: str
    type: str = "tag"
    name: str
    applied_count: int
    created_at: datetime
    updated_at: datetime


class IntercomSearchRequest(BaseModel):
    query: str
    type: str = "contact"
    limit: int = 50
    offset: int = 0


class IntercomSearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    total_count: int
    has_more: bool


class IntercomStats(BaseModel):
    total_contacts: int
    total_conversations: int
    open_conversations: int
    unassigned_conversations: int
    team_count: int
    admin_count: int
    response_time_avg: Optional[float] = None
    satisfaction_rating: Optional[float] = None


class IntercomMessageRequest(BaseModel):
    contact_id: str
    message: str
    message_type: str = "comment"


# Mock service for development
class IntercomService:
    def __init__(self):
        self.base_url = "https://api.intercom.io"
        self.access_token = None
        self.refresh_token = None

    async def authenticate(self, auth_request: IntercomAuthRequest) -> Dict[str, Any]:
        """Authenticate with Intercom using OAuth 2.0"""
        try:
            # In a real implementation, this would exchange the code for tokens
            # For now, return mock tokens
            self.access_token = "mock_intercom_access_token"
            self.refresh_token = "mock_intercom_refresh_token"

            return {
                "access_token": self.access_token,
                "token_type": "bearer",
                "expires_in": 3600,
                "refresh_token": self.refresh_token,
                "workspace_id": "mock_workspace_id",
            }
        except Exception as e:
            logger.error(f"Intercom authentication failed: {str(e)}")
            raise HTTPException(
                status_code=401, detail="Intercom authentication failed"
            )

    async def get_contacts(
        self, limit: int = 100, offset: int = 0
    ) -> List[IntercomContact]:
        """Get list of contacts"""
        try:
            # Mock data for development
            contacts = []
            for i in range(10):
                contacts.append(
                    IntercomContact(
                        id=f"contact_{i}",
                        email=f"user{i}@example.com",
                        name=f"Contact User {i}",
                        phone=f"+1-555-000-{i:04d}",
                        role="user",
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                        last_seen_at=datetime.now(timezone.utc),
                        custom_attributes={
                            "plan": "premium",
                            "signup_date": "2024-01-01",
                        },
                        tags=["active", "premium"],
                        companies=[{"id": f"company_{i}", "name": f"Company {i}"}],
                    )
                )
            return contacts
        except Exception as e:
            logger.error(f"Failed to get contacts: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch contacts")

    async def get_conversations(
        self, limit: int = 100, offset: int = 0, open_only: bool = False
    ) -> List[IntercomConversation]:
        """Get list of conversations"""
        try:
            # Mock data for development
            conversations = []
            for i in range(8):
                conversations.append(
                    IntercomConversation(
                        id=f"conversation_{i}",
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                        waiting_since=datetime.now(timezone.utc)
                        if i % 3 == 0
                        else None,
                        source={"type": "email", "id": f"email_{i}"},
                        contacts=[{"id": f"contact_{i}", "type": "contact"}],
                        conversation_parts=[
                            {
                                "id": f"part_{i}",
                                "type": "conversation_part",
                                "part_type": "comment",
                                "body": f"Sample conversation message {i}",
                                "author": {"id": f"contact_{i}", "type": "contact"},
                                "created_at": datetime.now(timezone.utc).isoformat(),
                            }
                        ],
                        tags=["support", "urgent"] if i % 2 == 0 else ["general"],
                        assignee={"id": f"admin_{i % 3}", "type": "admin"}
                        if i % 2 == 0
                        else None,
                        open=i < 4,
                        read=i > 2,
                        priority="priority" if i % 3 == 0 else "not_priority",
                    )
                )
            return conversations
        except Exception as e:
            logger.error(f"Failed to get conversations: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch conversations")

    async def get_teams(self) -> List[IntercomTeam]:
        """Get list of teams"""
        try:
            # Mock data for development
            teams = []
            for i in range(3):
                teams.append(
                    IntercomTeam(
                        id=f"team_{i}",
                        name=f"Support Team {i}",
                        admin_ids=[f"admin_{i}", f"admin_{(i + 1) % 3}"],
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                )
            return teams
        except Exception as e:
            logger.error(f"Failed to get teams: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch teams")

    async def get_admins(self) -> List[IntercomAdmin]:
        """Get list of admins"""
        try:
            # Mock data for development
            admins = []
            for i in range(5):
                admins.append(
                    IntercomAdmin(
                        id=f"admin_{i}",
                        name=f"Admin User {i}",
                        email=f"admin{i}@example.com",
                        job_title="Support Agent",
                        away_mode_enabled=i == 0,
                        away_mode_reassign=False,
                        has_inbox_seat=True,
                        team_ids=[f"team_{i % 3}"],
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                )
            return admins
        except Exception as e:
            logger.error(f"Failed to get admins: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch admins")

    async def get_tags(self) -> List[IntercomTag]:
        """Get list of tags"""
        try:
            # Mock data for development
            tags = []
            tag_names = ["urgent", "premium", "billing", "technical", "feature-request"]
            for i, name in enumerate(tag_names):
                tags.append(
                    IntercomTag(
                        id=f"tag_{i}",
                        name=name,
                        applied_count=(i + 1) * 10,
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                )
            return tags
        except Exception as e:
            logger.error(f"Failed to get tags: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch tags")

    async def search_content(
        self, search_request: IntercomSearchRequest
    ) -> IntercomSearchResponse:
        """Search Intercom content"""
        try:
            # Mock search results
            results = []
            for i in range(min(10, search_request.limit)):
                results.append(
                    {
                        "id": f"search_result_{i}",
                        "type": search_request.type,
                        "name": f"Search Result {i}",
                        "email": f"result{i}@example.com",
                        "description": f"Description for search result {i}",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "score": 0.9 - (i * 0.1),
                    }
                )

            return IntercomSearchResponse(
                results=results,
                total_count=len(results),
                has_more=len(results) >= search_request.limit,
            )
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            raise HTTPException(status_code=500, detail="Search failed")

    async def send_message(
        self, message_request: IntercomMessageRequest
    ) -> Dict[str, Any]:
        """Send a message to a contact"""
        try:
            # Mock message sending
            return {
                "id": f"message_{datetime.now().timestamp()}",
                "type": "conversation_part",
                "part_type": message_request.message_type,
                "body": message_request.message,
                "author": {"id": "current_admin", "type": "admin"},
                "created_at": datetime.now(timezone.utc).isoformat(),
                "conversation_id": f"conversation_{message_request.contact_id}",
            }
        except Exception as e:
            logger.error(f"Message sending failed: {str(e)}")
            raise HTTPException(status_code=500, detail="Message sending failed")

    async def get_stats(self) -> IntercomStats:
        """Get Intercom statistics"""
        try:
            contacts = await self.get_contacts()
            conversations = await self.get_conversations()
            teams = await self.get_teams()
            admins = await self.get_admins()

            open_conversations = [c for c in conversations if c.open]
            unassigned_conversations = [c for c in conversations if not c.assignee]

            return IntercomStats(
                total_contacts=len(contacts),
                total_conversations=len(conversations),
                open_conversations=len(open_conversations),
                unassigned_conversations=len(unassigned_conversations),
                team_count=len(teams),
                admin_count=len(admins),
                response_time_avg=2.5,
                satisfaction_rating=4.2,
            )
        except Exception as e:
            logger.error(f"Failed to get stats: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch stats")

    async def create_contact(
        self, email: str, name: Optional[str] = None
    ) -> IntercomContact:
        """Create a new contact"""
        try:
            # Mock contact creation
            return IntercomContact(
                id=f"new_contact_{datetime.now().timestamp()}",
                email=email,
                name=name,
                role="user",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                custom_attributes={"created_via": "atom_platform"},
                tags=["new"],
                companies=[],
            )
        except Exception as e:
            logger.error(f"Contact creation failed: {str(e)}")
            raise HTTPException(status_code=500, detail="Contact creation failed")

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Intercom service"""
        try:
            return {
                "status": "healthy",
                "service": "intercom",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.0.0",
                "features": {
                    "contacts": True,
                    "conversations": True,
                    "teams": True,
                    "admins": True,
                    "tags": True,
                    "search": True,
                    "messaging": True,
                    "analytics": True,
                },
            }
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            raise HTTPException(status_code=500, detail="Health check failed")


# Initialize service
intercom_service = IntercomService()


# API Routes
@router.post("/auth")
async def intercom_auth(auth_request: IntercomAuthRequest):
    """Authenticate with Intercom"""
    try:
        result = await intercom_service.authenticate(auth_request)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Intercom auth error: {str(e)}")
        raise HTTPException(status_code=500, detail="Authentication failed")


@router.get("/contacts")
async def get_contacts(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Get Intercom contacts"""
    try:
        contacts = await intercom_service.get_contacts(limit, offset)
        return {"success": True, "data": contacts, "count": len(contacts)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get contacts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch contacts")


@router.get("/conversations")
async def get_conversations(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    open_only: bool = Query(False, description="Only show open conversations"),
):
    """Get Intercom conversations"""
    try:
        conversations = await intercom_service.get_conversations(
            limit, offset, open_only
        )
        return {"success": True, "data": conversations, "count": len(conversations)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch conversations")


@router.get("/teams")
async def get_teams():
    """Get Intercom teams"""
    try:
        teams = await intercom_service.get_teams()
        return {"success": True, "data": teams, "count": len(teams)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get teams: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch teams")


@router.get("/admins")
async def get_admins():
    """Get Intercom admins"""
    try:
        admins = await intercom_service.get_admins()
        return {"success": True, "data": admins, "count": len(admins)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get admins: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch admins")


@router.get("/tags")
async def get_tags():
    """Get Intercom tags"""
    try:
        tags = await intercom_service.get_tags()
        return {"success": True, "data": tags, "count": len(tags)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tags: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch tags")


@router.post("/search")
async def search_content(search_request: IntercomSearchRequest):
    """Search Intercom content"""
    try:
        results = await intercom_service.search_content(search_request)
        return {"success": True, "data": results}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Search failed")


@router.post("/messages")
async def send_message(message_request: IntercomMessageRequest):
    """Send message to contact"""
    try:
        message = await intercom_service.send_message(message_request)
        return {"success": True, "data": message}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Message sending failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Message sending failed")


@router.get("/stats")
async def get_stats():
    """Get Intercom statistics"""
    try:
        stats = await intercom_service.get_stats()
        return {"success": True, "data": stats}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch stats")

    # Error handlers
    @router.get("/")
    async def intercom_root():
        """Intercom integration root endpoint"""
        return {
            "message": "Intercom integration API",
            "version": "1.0.0",
            "endpoints": [
                "/auth",
                "/contacts",
                "/conversations",
                "/teams",
                "/admins",
                "/tags",
                "/search",
                "/messages",
                "/stats",
                "/health",
            ],
        }
