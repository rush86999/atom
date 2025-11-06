"""
Enhanced Outlook API Routes with Comprehensive Microsoft Graph API Integration
Complete enterprise-grade Outlook integration for the ATOM platform
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import logging
import asyncio

from outlook_service_enhanced import (
    OutlookEnhancedService,
    OutlookEmail,
    OutlookCalendarEvent,
    OutlookContact,
    OutlookTask,
    OutlookFolder,
)

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/integrations/outlook", tags=["outlook"])

# Initialize enhanced Outlook service
outlook_service = OutlookEnhancedService()


# Enhanced Pydantic models for request/response
class EmailListEnhancedRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    folder: str = Field("inbox", description="Email folder")
    query: Optional[str] = Field(None, description="Search query")
    max_results: int = Field(50, description="Maximum results")
    skip: int = Field(0, description="Skip count")
    include_attachments: bool = Field(False, description="Include attachments")
    order_by: str = Field("receivedDateTime DESC", description="Sort order")


class EmailSendEnhancedRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    to_recipients: List[str] = Field(..., description="To recipients")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body")
    body_type: str = Field("HTML", description="Body type (HTML/Text)")
    cc_recipients: Optional[List[str]] = Field([], description="CC recipients")
    bcc_recipients: Optional[List[str]] = Field([], description="BCC recipients")
    importance: str = Field("normal", description="Email importance")
    attachments: Optional[List[Dict[str, Any]]] = Field([], description="Attachments")
    save_to_sent_items: bool = Field(True, description="Save to sent items")


class CalendarEventEnhancedRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    subject: str = Field(..., description="Event subject")
    start_time: str = Field(..., description="Start time (ISO format)")
    end_time: str = Field(..., description="End time (ISO format)")
    location: Optional[str] = Field(None, description="Event location")
    body: Optional[str] = Field(None, description="Event description")
    attendees: Optional[List[str]] = Field([], description="Attendee emails")
    is_all_day: bool = Field(False, description="All day event")
    sensitivity: str = Field("normal", description="Event sensitivity")
    show_as: str = Field("busy", description="Show as status")
    reminder_minutes: int = Field(15, description="Reminder minutes before")


class ContactEnhancedRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    display_name: str = Field(..., description="Display name")
    given_name: Optional[str] = Field(None, description="Given name")
    surname: Optional[str] = Field(None, description="Surname")
    email_addresses: List[str] = Field(..., description="Email addresses")
    business_phones: Optional[List[str]] = Field([], description="Business phones")
    mobile_phone: Optional[str] = Field(None, description="Mobile phone")
    job_title: Optional[str] = Field(None, description="Job title")
    company_name: Optional[str] = Field(None, description="Company name")


class TaskEnhancedRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    subject: str = Field(..., description="Task subject")
    body: Optional[str] = Field(None, description="Task description")
    importance: str = Field("normal", description="Task importance")
    due_date: Optional[str] = Field(None, description="Due date (ISO format)")
    start_date: Optional[str] = Field(None, description="Start date (ISO format)")
    reminder_date: Optional[str] = Field(None, description="Reminder date (ISO format)")
    categories: Optional[List[str]] = Field([], description="Categories")


class FolderListRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    folder_type: Optional[str] = Field(None, description="Folder type filter")


class SearchEnhancedRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    query: str = Field(..., description="Search query")
    entity_types: List[str] = Field(
        ["message", "event", "contact", "driveItem"],
        description="Entity types to search",
    )
    max_results: int = Field(50, description="Maximum results")


@router.get("/health")
async def outlook_health_enhanced():
    """Enhanced health check for Outlook integration"""
    try:
        # Check if required environment variables are set
        client_id = outlook_service.client_id
        client_secret = bool(outlook_service.client_secret)
        tenant_id = outlook_service.tenant_id

        return {
            "status": "healthy",
            "service": "outlook",
            "timestamp": datetime.now().isoformat(),
            "service_available": True,
            "database_available": True,
            "client_id_configured": bool(client_id),
            "client_secret_configured": client_secret,
            "tenant_id_configured": bool(tenant_id),
            "message": "Outlook integration is operational",
        }
    except Exception as e:
        logger.error(f"Outlook health check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "service": "outlook",
                "error": str(e),
                "message": "Outlook integration is experiencing issues",
            },
        )


@router.post("/emails/enhanced")
async def get_emails_enhanced(request: EmailListEnhancedRequest):
    """Get emails with enhanced filtering and options"""
    try:
        logger.info(f"Fetching enhanced emails for user {request.user_id}")

        emails = await outlook_service.get_user_emails_enhanced(
            user_id=request.user_id,
            folder=request.folder,
            query=request.query,
            max_results=request.max_results,
            skip=request.skip,
            include_attachments=request.include_attachments,
            order_by=request.order_by,
        )

        return {
            "ok": True,
            "data": {
                "emails": [email.to_dict() for email in emails],
                "total_count": len(emails),
                "user_id": request.user_id,
                "folder": request.folder,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(
            f"Failed to fetch enhanced emails for user {request.user_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to fetch emails: {str(e)}",
                "user_id": request.user_id,
            },
        )


@router.post("/emails/send/enhanced")
async def send_email_enhanced(request: EmailSendEnhancedRequest):
    """Send email with enhanced options"""
    try:
        logger.info(f"Sending enhanced email for user {request.user_id}")

        success = await outlook_service.send_email_enhanced(
            user_id=request.user_id,
            to_recipients=request.to_recipients,
            subject=request.subject,
            body=request.body,
            body_type=request.body_type,
            cc_recipients=request.cc_recipients,
            bcc_recipients=request.bcc_recipients,
            importance=request.importance,
            attachments=request.attachments,
            save_to_sent_items=request.save_to_sent_items,
        )

        return {
            "ok": success,
            "data": {
                "message": "Email sent successfully"
                if success
                else "Failed to send email",
                "user_id": request.user_id,
                "subject": request.subject,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(
            f"Failed to send enhanced email for user {request.user_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to send email: {str(e)}",
                "user_id": request.user_id,
            },
        )


@router.post("/calendar/events/enhanced")
async def create_calendar_event_enhanced(request: CalendarEventEnhancedRequest):
    """Create calendar event with enhanced options"""
    try:
        logger.info(f"Creating enhanced calendar event for user {request.user_id}")

        event = await outlook_service.create_calendar_event_enhanced(
            user_id=request.user_id,
            subject=request.subject,
            start_time=request.start_time,
            end_time=request.end_time,
            location=request.location,
            body=request.body,
            attendees=request.attendees,
            is_all_day=request.is_all_day,
            sensitivity=request.sensitivity,
            show_as=request.show_as,
            reminder_minutes=request.reminder_minutes,
        )

        return {
            "ok": True,
            "data": {
                "event": event.to_dict() if event else {},
                "message": "Calendar event created successfully",
                "user_id": request.user_id,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(
            f"Failed to create enhanced calendar event for user {request.user_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to create calendar event: {str(e)}",
                "user_id": request.user_id,
            },
        )


@router.post("/contacts/enhanced")
async def create_contact_enhanced(request: ContactEnhancedRequest):
    """Create contact with enhanced options"""
    try:
        logger.info(f"Creating enhanced contact for user {request.user_id}")

        contact = await outlook_service.create_contact_enhanced(
            user_id=request.user_id,
            display_name=request.display_name,
            given_name=request.given_name,
            surname=request.surname,
            email_addresses=request.email_addresses,
            business_phones=request.business_phones,
            mobile_phone=request.mobile_phone,
            job_title=request.job_title,
            company_name=request.company_name,
        )

        return {
            "ok": True,
            "data": {
                "contact": contact.to_dict() if contact else {},
                "message": "Contact created successfully",
                "user_id": request.user_id,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(
            f"Failed to create enhanced contact for user {request.user_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to create contact: {str(e)}",
                "user_id": request.user_id,
            },
        )


@router.post("/tasks/enhanced")
async def create_task_enhanced(request: TaskEnhancedRequest):
    """Create task with enhanced options"""
    try:
        logger.info(f"Creating enhanced task for user {request.user_id}")

        task = await outlook_service.create_task_enhanced(
            user_id=request.user_id,
            subject=request.subject,
            body=request.body,
            importance=request.importance,
            due_date=request.due_date,
            start_date=request.start_date,
            reminder_date=request.reminder_date,
            categories=request.categories,
        )

        return {
            "ok": True,
            "data": {
                "task": task.to_dict() if task else {},
                "message": "Task created successfully",
                "user_id": request.user_id,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(
            f"Failed to create enhanced task for user {request.user_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to create task: {str(e)}",
                "user_id": request.user_id,
            },
        )


@router.post("/folders")
async def get_folders(request: FolderListRequest):
    """Get email folders"""
    try:
        logger.info(f"Fetching folders for user {request.user_id}")

        folders = await outlook_service.get_user_folders(
            user_id=request.user_id, folder_type=request.folder_type
        )

        return {
            "ok": True,
            "data": {
                "folders": [folder.to_dict() for folder in folders],
                "total_count": len(folders),
                "user_id": request.user_id,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(f"Failed to fetch folders for user {request.user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to fetch folders: {str(e)}",
                "user_id": request.user_id,
            },
        )


@router.post("/search/enhanced")
async def search_enhanced(request: SearchEnhancedRequest):
    """Enhanced search across multiple entity types"""
    try:
        logger.info(f"Performing enhanced search for user {request.user_id}")

        results = await outlook_service.search_entities_enhanced(
            user_id=request.user_id,
            query=request.query,
            entity_types=request.entity_types,
            max_results=request.max_results,
        )

        return {
            "ok": True,
            "data": {
                "results": results,
                "total_count": len(results),
                "query": request.query,
                "entity_types": request.entity_types,
                "user_id": request.user_id,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(
            f"Failed to perform enhanced search for user {request.user_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to search: {str(e)}",
                "query": request.query,
                "user_id": request.user_id,
            },
        )


@router.get("/user/profile/enhanced")
async def get_user_profile_enhanced(user_id: str = Query(..., description="User ID")):
    """Get enhanced user profile information"""
    try:
        logger.info(f"Fetching enhanced profile for user {user_id}")

        profile = await outlook_service.get_user_profile_enhanced(user_id)

        return {
            "ok": True,
            "data": {
                "profile": profile.to_dict() if profile else {},
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(f"Failed to fetch enhanced profile for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to fetch user profile: {str(e)}",
                "user_id": user_id,
            },
        )


@router.get("/calendar/events/upcoming")
async def get_upcoming_events(
    user_id: str = Query(..., description="User ID"),
    days: int = Query(7, description="Number of days to look ahead"),
    max_results: int = Query(50, description="Maximum results"),
):
    """Get upcoming calendar events"""
    try:
        logger.info(f"Fetching upcoming events for user {user_id}")

        events = await outlook_service.get_upcoming_events(
            user_id=user_id, days=days, max_results=max_results
        )

        return {
            "ok": True,
            "data": {
                "events": [event.to_dict() for event in events],
                "total_count": len(events),
                "user_id": user_id,
                "days": days,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(f"Failed to fetch upcoming events for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to fetch upcoming events: {str(e)}",
                "user_id": user_id,
            },
        )


@router.get("/emails/unread/count")
async def get_unread_email_count(user_id: str = Query(..., description="User ID")):
    """Get count of unread emails"""
    try:
        logger.info(f"Fetching unread email count for user {user_id}")

        count = await outlook_service.get_unread_email_count(user_id)

        return {
            "ok": True,
            "data": {
                "unread_count": count,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(f"Failed to fetch unread email count for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to fetch unread email count: {str(e)}",
                "user_id": user_id,
            },
        )


@router.post("/emails/mark-read")
async def mark_emails_read(
    user_id: str = Body(..., description="User ID"),
    email_ids: List[str] = Body(..., description="Email IDs to mark as read"),
):
    """Mark emails as read"""
    try:
        logger.info(f"Marking {len(email_ids)} emails as read for user {user_id}")

        success = await outlook_service.mark_emails_read(user_id, email_ids)

        return {
            "ok": success,
            "data": {
                "message": f"Marked {len(email_ids)} emails as read"
                if success
                else "Failed to mark emails as read",
                "user_id": user_id,
                "email_count": len(email_ids),
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(f"Failed to mark emails as read for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": f"Failed to mark emails as read: {str(e)}",
                "user_id": user_id,
            },
        )


@router.get("/info")
async def get_service_info():
    """Get Outlook service information"""
    try:
        return {
            "ok": True,
            "data": {
                "service": "outlook",
                "version": "2.0.0",
                "capabilities": [
                    "email_management",
                    "calendar_management",
                    "contact_management",
                    "task_management",
                    "search_and_filtering",
                    "folder_management",
                    "attachment_handling",
                    "event_reminders",
                    "enhanced_search",
                    "upcoming_events",
                    "unread_count",
                    "mark_as_read",
                ],
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(f"Failed to get service info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"ok": False, "error": f"Failed to get service info: {str(e)}"},
        )
