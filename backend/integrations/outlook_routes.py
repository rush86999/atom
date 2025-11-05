"""
Enhanced Outlook API Routes
Complete Outlook integration endpoints for the ATOM platform
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import asyncio

from .outlook_service import OutlookService

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/outlook", tags=["outlook"])

# Initialize Outlook service
outlook_service = OutlookService()


# Pydantic models for request/response
class EmailListRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    folder: str = Field("inbox", description="Email folder")
    query: Optional[str] = Field(None, description="Search query")
    max_results: int = Field(50, description="Maximum results")
    skip: int = Field(0, description="Skip count")


class EmailSendRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    to_recipients: List[str] = Field(..., description="To recipients")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body")
    cc_recipients: Optional[List[str]] = Field([], description="CC recipients")
    bcc_recipients: Optional[List[str]] = Field([], description="BCC recipients")


class EmailDraftRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    to_recipients: List[str] = Field(..., description="To recipients")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body")
    cc_recipients: Optional[List[str]] = Field([], description="CC recipients")
    bcc_recipients: Optional[List[str]] = Field([], description="BCC recipients")


class CalendarEventListRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    time_min: Optional[str] = Field(None, description="Start time filter")
    time_max: Optional[str] = Field(None, description="End time filter")
    max_results: int = Field(50, description="Maximum results")


class CalendarEventCreateRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    subject: str = Field(..., description="Event subject")
    body: Optional[str] = Field(None, description="Event body")
    start: Optional[Dict[str, Any]] = Field(None, description="Start time")
    end: Optional[Dict[str, Any]] = Field(None, description="End time")
    location: Optional[Dict[str, Any]] = Field(None, description="Location")
    attendees: Optional[List[str]] = Field([], description="Attendees")


class ContactListRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    query: Optional[str] = Field(None, description="Search query")
    max_results: int = Field(50, description="Maximum results")


class ContactCreateRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    display_name: str = Field(..., description="Contact display name")
    given_name: Optional[str] = Field(None, description="Given name")
    surname: Optional[str] = Field(None, description="Surname")
    email_addresses: Optional[List[Dict[str, Any]]] = Field(
        [], description="Email addresses"
    )
    business_phones: Optional[List[str]] = Field([], description="Business phones")
    company_name: Optional[str] = Field(None, description="Company name")


class TaskListRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    status: Optional[str] = Field(None, description="Task status filter")
    max_results: int = Field(50, description="Maximum results")


class TaskCreateRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    subject: str = Field(..., description="Task subject")
    body: Optional[str] = Field(None, description="Task body")
    importance: str = Field("normal", description="Task importance")
    due_date_time: Optional[Dict[str, Any]] = Field(None, description="Due date")
    categories: Optional[List[str]] = Field([], description="Categories")


class SearchRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    query: str = Field(..., description="Search query")
    max_results: int = Field(50, description="Maximum results")


# Email endpoints
@router.post("/emails", summary="List emails")
async def list_emails(request: EmailListRequest):
    """List emails with filtering and pagination"""
    try:
        emails = await outlook_service.get_user_emails(
            user_id=request.user_id,
            folder=request.folder,
            query=request.query,
            max_results=request.max_results,
            skip=request.skip,
        )
        return {
            "success": True,
            "service": "outlook",
            "operation": "list_emails",
            "data": emails,
            "count": len(emails),
            "folder": request.folder,
        }
    except Exception as e:
        logger.error(f"Error listing emails: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list emails: {str(e)}")


@router.post("/emails/send", summary="Send email")
async def send_email(request: EmailSendRequest):
    """Send email via Outlook"""
    try:
        result = await outlook_service.send_email(
            user_id=request.user_id,
            to_recipients=request.to_recipients,
            subject=request.subject,
            body=request.body,
            cc_recipients=request.cc_recipients,
            bcc_recipients=request.bcc_recipients,
        )

        if result:
            return {
                "success": True,
                "service": "outlook",
                "operation": "send_email",
                "data": result,
                "message": "Email sent successfully",
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to send email")

    except Exception as e:
        logger.error(f"Error sending email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")


@router.post("/emails/draft", summary="Create draft email")
async def create_draft_email(request: EmailDraftRequest):
    """Create draft email"""
    try:
        result = await outlook_service.create_draft_email(
            user_id=request.user_id,
            to_recipients=request.to_recipients,
            subject=request.subject,
            body=request.body,
            cc_recipients=request.cc_recipients,
            bcc_recipients=request.bcc_recipients,
        )

        if result:
            return {
                "success": True,
                "service": "outlook",
                "operation": "create_draft_email",
                "data": result,
                "message": "Draft email created successfully",
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create draft email")

    except Exception as e:
        logger.error(f"Error creating draft email: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create draft email: {str(e)}"
        )


@router.get("/emails/{email_id}", summary="Get email by ID")
async def get_email(email_id: str, user_id: str = Query(..., description="User ID")):
    """Get specific email by ID"""
    try:
        email = await outlook_service.get_email_by_id(user_id, email_id)

        if email:
            return {
                "success": True,
                "service": "outlook",
                "operation": "get_email",
                "data": email,
            }
        else:
            raise HTTPException(status_code=404, detail="Email not found")

    except Exception as e:
        logger.error(f"Error getting email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get email: {str(e)}")


@router.delete("/emails/{email_id}", summary="Delete email")
async def delete_email(email_id: str, user_id: str = Query(..., description="User ID")):
    """Delete email by ID"""
    try:
        result = await outlook_service.delete_email(user_id, email_id)

        if result:
            return {
                "success": True,
                "service": "outlook",
                "operation": "delete_email",
                "message": "Email deleted successfully",
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to delete email")

    except Exception as e:
        logger.error(f"Error deleting email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete email: {str(e)}")


# Calendar endpoints
@router.post("/calendar/events", summary="List calendar events")
async def list_calendar_events(request: CalendarEventListRequest):
    """List calendar events with time range filtering"""
    try:
        events = await outlook_service.get_calendar_events(
            user_id=request.user_id,
            time_min=request.time_min,
            time_max=request.time_max,
            max_results=request.max_results,
        )
        return {
            "success": True,
            "service": "outlook",
            "operation": "list_calendar_events",
            "data": events,
            "count": len(events),
        }
    except Exception as e:
        logger.error(f"Error listing calendar events: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list calendar events: {str(e)}"
        )


@router.post("/calendar/events/create", summary="Create calendar event")
async def create_calendar_event(request: CalendarEventCreateRequest):
    """Create calendar event"""
    try:
        result = await outlook_service.create_calendar_event(
            user_id=request.user_id,
            subject=request.subject,
            body=request.body,
            start=request.start,
            end=request.end,
            location=request.location,
            attendees=request.attendees,
        )

        if result:
            return {
                "success": True,
                "service": "outlook",
                "operation": "create_calendar_event",
                "data": result,
                "message": "Calendar event created successfully",
            }
        else:
            raise HTTPException(
                status_code=500, detail="Failed to create calendar event"
            )

    except Exception as e:
        logger.error(f"Error creating calendar event: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create calendar event: {str(e)}"
        )


# Contact endpoints
@router.post("/contacts", summary="List contacts")
async def list_contacts(request: ContactListRequest):
    """List contacts with optional search"""
    try:
        contacts = await outlook_service.get_user_contacts(
            user_id=request.user_id,
            query=request.query,
            max_results=request.max_results,
        )
        return {
            "success": True,
            "service": "outlook",
            "operation": "list_contacts",
            "data": contacts,
            "count": len(contacts),
        }
    except Exception as e:
        logger.error(f"Error listing contacts: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list contacts: {str(e)}"
        )


@router.post("/contacts/create", summary="Create contact")
async def create_contact(request: ContactCreateRequest):
    """Create contact"""
    try:
        result = await outlook_service.create_contact(
            user_id=request.user_id,
            display_name=request.display_name,
            given_name=request.given_name,
            surname=request.surname,
            email_addresses=request.email_addresses,
            business_phones=request.business_phones,
            company_name=request.company_name,
        )

        if result:
            return {
                "success": True,
                "service": "outlook",
                "operation": "create_contact",
                "data": result,
                "message": "Contact created successfully",
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create contact")

    except Exception as e:
        logger.error(f"Error creating contact: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create contact: {str(e)}"
        )


# Task endpoints
@router.post("/tasks", summary="List tasks")
async def list_tasks(request: TaskListRequest):
    """List tasks with optional status filtering"""
    try:
        tasks = await outlook_service.get_user_tasks(
            user_id=request.user_id,
            status=request.status,
            max_results=request.max_results,
        )
        return {
            "success": True,
            "service": "outlook",
            "operation": "list_tasks",
            "data": tasks,
            "count": len(tasks),
        }
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list tasks: {str(e)}")


@router.post("/tasks/create", summary="Create task")
async def create_task(request: TaskCreateRequest):
    """Create task"""
    try:
        result = await outlook_service.create_task(
            user_id=request.user_id,
            subject=request.subject,
            body=request.body,
            importance=request.importance,
            due_date_time=request.due_date_time,
            categories=request.categories,
        )

        if result:
            return {
                "success": True,
                "service": "outlook",
                "operation": "create_task",
                "data": result,
                "message": "Task created successfully",
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create task")

    except Exception as e:
        logger.error(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")


# Search endpoint
@router.post("/search", summary="Search emails")
async def search_emails(request: SearchRequest):
    """Search across Outlook emails"""
    try:
        emails = await outlook_service.search_emails(
            user_id=request.user_id,
            query=request.query,
            max_results=request.max_results,
        )
        return {
            "success": True,
            "service": "outlook",
            "operation": "search_emails",
            "data": emails,
            "count": len(emails),
            "query": request.query,
        }
    except Exception as e:
        logger.error(f"Error searching emails: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to search emails: {str(e)}"
        )


# User profile endpoint
@router.get("/profile", summary="Get user profile")
async def get_user_profile(user_id: str = Query(..., description="User ID")):
    """Get user profile information"""
    try:
        profile = await outlook_service.get_user_profile(user_id)

        if profile:
            return {
                "success": True,
                "service": "outlook",
                "operation": "get_user_profile",
                "data": profile,
            }
        else:
            raise HTTPException(status_code=404, detail="User profile not found")

    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get user profile: {str(e)}"
        )


# Unread emails endpoint
@router.get("/emails/unread", summary="Get unread emails")
async def get_unread_emails(
    user_id: str = Query(..., description="User ID"),
    max_results: int = Query(50, description="Maximum results"),
):
    """Get unread emails"""
    try:
        emails = await outlook_service.get_unread_emails(user_id, max_results)
        return {
            "success": True,
            "service": "outlook",
            "operation": "get_unread_emails",
            "data": emails,
            "count": len(emails),
        }
    except Exception as e:
        logger.error(f"Error getting unread emails: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get unread emails: {str(e)}"
        )


# Health check endpoint
@router.get("/health", summary="Outlook service health check")
async def health_check():
    """Check Outlook service health"""
    try:
        # Basic health check - in production, this would test actual API connectivity
        return {
            "success": True,
            "service": "outlook",
            "status": "healthy",
            "message": "Outlook service is available",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Outlook health check failed: {e}")
        raise HTTPException(
            status_code=503, detail=f"Outlook service is unhealthy: {str(e)}"
        )
