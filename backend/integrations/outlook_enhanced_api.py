from flask import Blueprint, request, jsonify, current_app
from typing import Dict, List, Optional, Any
import logging
import json
import asyncio
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import os
import requests
from functools import wraps

logger = logging.getLogger(__name__)

# Create blueprint for Outlook enhanced API
outlook_enhanced_bp = Blueprint("outlook_enhanced", __name__)


# Data Models
@dataclass
class OutlookUser:
    """Outlook user profile information"""

    id: str
    display_name: str
    mail: str
    user_principal_name: str
    job_title: Optional[str] = None
    office_location: Optional[str] = None
    business_phones: Optional[List[str]] = None
    mobile_phone: Optional[str] = None


@dataclass
class OutlookEmail:
    """Outlook email message representation"""

    id: str
    subject: str
    body_preview: str
    body: Optional[Dict[str, Any]] = None
    sender: Optional[Dict[str, Any]] = None
    from_field: Optional[Dict[str, Any]] = None
    to_recipients: Optional[List[Dict[str, Any]]] = None
    cc_recipients: Optional[List[Dict[str, Any]]] = None
    bcc_recipients: Optional[List[Dict[str, Any]]] = None
    received_date_time: Optional[str] = None
    sent_date_time: Optional[str] = None
    has_attachments: bool = False
    importance: str = "normal"
    is_read: bool = False
    web_link: Optional[str] = None
    conversation_id: Optional[str] = None
    parent_folder_id: Optional[str] = None


@dataclass
class OutlookCalendarEvent:
    """Outlook calendar event representation"""

    id: str
    subject: str
    body: Optional[Dict[str, Any]] = None
    start: Optional[Dict[str, Any]] = None
    end: Optional[Dict[str, Any]] = None
    location: Optional[Dict[str, Any]] = None
    attendees: Optional[List[Dict[str, Any]]] = None
    organizer: Optional[Dict[str, Any]] = None
    is_all_day: bool = False
    show_as: str = "busy"
    web_link: Optional[str] = None
    created_date_time: Optional[str] = None
    last_modified_date_time: Optional[str] = None


@dataclass
class OutlookContact:
    """Outlook contact representation"""

    id: str
    display_name: str
    given_name: Optional[str] = None
    surname: Optional[str] = None
    email_addresses: Optional[List[Dict[str, Any]]] = None
    business_phones: Optional[List[str]] = None
    mobile_phone: Optional[str] = None
    home_phones: Optional[List[str]] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    office_location: Optional[str] = None
    created_date_time: Optional[str] = None
    last_modified_date_time: Optional[str] = None


@dataclass
class OutlookTask:
    """Outlook task representation"""

    id: str
    subject: str
    body: Optional[Dict[str, Any]] = None
    importance: str = "normal"
    status: str = "notStarted"
    created_date_time: Optional[str] = None
    last_modified_date_time: Optional[str] = None
    due_date_time: Optional[Dict[str, Any]] = None
    completed_date_time: Optional[Dict[str, Any]] = None
    categories: Optional[List[str]] = None


# Utility functions
def get_outlook_service():
    """Get Outlook service instance"""
    try:
        from backend.integrations.outlook_service import OutlookService

        return OutlookService()
    except ImportError:
        logger.error("OutlookService not available")
        return None


def handle_service_error(func):
    """Decorator to handle service errors"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Service error in {func.__name__}: {e}")
            return jsonify(
                {
                    "success": False,
                    "error": f"Service error: {str(e)}",
                    "service": "outlook",
                }
            ), 500

    return wrapper


def validate_user_id(func):
    """Decorator to validate user_id parameter"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        data = request.get_json() or {}
        user_id = data.get("user_id")
        if not user_id:
            return jsonify(
                {
                    "success": False,
                    "error": "Missing required parameter: user_id",
                    "service": "outlook",
                }
            ), 400
        return func(*args, **kwargs)

    return wrapper


# Email Endpoints
@outlook_enhanced_bp.route("/api/integrations/outlook/emails", methods=["POST"])
@validate_user_id
@handle_service_error
def outlook_emails():
    """Handle email operations (list, send, compose)"""
    data = request.get_json()
    user_id = data.get("user_id")
    operation = data.get("operation", "list")

    service = get_outlook_service()
    if not service:
        return jsonify(
            {
                "success": False,
                "error": "Outlook service not available",
                "service": "outlook",
            }
        ), 503

    try:
        if operation == "list":
            # List emails with filtering
            folder = data.get("folder", "inbox")
            query = data.get("query")
            max_results = data.get("max_results", 50)
            skip = data.get("skip", 0)

            emails = asyncio.run(
                service.get_user_emails(
                    user_id=user_id,
                    folder=folder,
                    query=query,
                    max_results=max_results,
                    skip=skip,
                )
            )

            return jsonify(
                {
                    "success": True,
                    "service": "outlook",
                    "operation": operation,
                    "data": emails,
                    "count": len(emails),
                    "folder": folder,
                }
            ), 200

        elif operation == "send":
            # Send email
            email_data = data.get("data", {})
            if not email_data:
                return jsonify(
                    {
                        "success": False,
                        "error": "Missing email data",
                        "service": "outlook",
                    }
                ), 400

            result = asyncio.run(
                service.send_email(
                    user_id=user_id,
                    to_recipients=email_data.get("to", []),
                    subject=email_data.get("subject", ""),
                    body=email_data.get("body", ""),
                    cc_recipients=email_data.get("cc", []),
                    bcc_recipients=email_data.get("bcc", []),
                )
            )

            return jsonify(
                {
                    "success": True,
                    "service": "outlook",
                    "operation": operation,
                    "data": result,
                    "message": "Email sent successfully",
                }
            ), 200

        elif operation == "compose":
            # Compose email (save as draft)
            email_data = data.get("data", {})
            if not email_data:
                return jsonify(
                    {
                        "success": False,
                        "error": "Missing email data",
                        "service": "outlook",
                    }
                ), 400

            result = asyncio.run(
                service.create_draft_email(
                    user_id=user_id,
                    to_recipients=email_data.get("to", []),
                    subject=email_data.get("subject", ""),
                    body=email_data.get("body", ""),
                    cc_recipients=email_data.get("cc", []),
                    bcc_recipients=email_data.get("bcc", []),
                )
            )

            return jsonify(
                {
                    "success": True,
                    "service": "outlook",
                    "operation": operation,
                    "data": result,
                    "message": "Draft email created successfully",
                }
            ), 200

        else:
            return jsonify(
                {
                    "success": False,
                    "error": f"Unsupported operation: {operation}",
                    "service": "outlook",
                    "supported_operations": ["list", "send", "compose"],
                }
            ), 400

    except Exception as e:
        logger.error(f"Email operation error: {e}")
        return jsonify(
            {
                "success": False,
                "error": f"Email operation failed: {str(e)}",
                "service": "outlook",
            }
        ), 500


@outlook_enhanced_bp.route(
    "/api/integrations/outlook/emails/<email_id>", methods=["GET", "DELETE"]
)
@validate_user_id
@handle_service_error
def outlook_email_operations(email_id):
    """Handle individual email operations (get, delete)"""
    data = request.get_json() or {}
    user_id = data.get("user_id")

    service = get_outlook_service()
    if not service:
        return jsonify(
            {
                "success": False,
                "error": "Outlook service not available",
                "service": "outlook",
            }
        ), 503

    try:
        if request.method == "GET":
            # Get specific email
            email = asyncio.run(service.get_email_by_id(user_id, email_id))

            if email:
                return jsonify(
                    {
                        "success": True,
                        "service": "outlook",
                        "operation": "get",
                        "data": email,
                    }
                ), 200
            else:
                return jsonify(
                    {"success": False, "error": "Email not found", "service": "outlook"}
                ), 404

        elif request.method == "DELETE":
            # Delete email
            result = asyncio.run(service.delete_email(user_id, email_id))

            return jsonify(
                {
                    "success": True,
                    "service": "outlook",
                    "operation": "delete",
                    "data": result,
                    "message": "Email deleted successfully",
                }
            ), 200

    except Exception as e:
        logger.error(f"Email operation error: {e}")
        return jsonify(
            {
                "success": False,
                "error": f"Email operation failed: {str(e)}",
                "service": "outlook",
            }
        ), 500


# Calendar Endpoints
@outlook_enhanced_bp.route(
    "/api/integrations/outlook/calendar/events", methods=["POST"]
)
@validate_user_id
@handle_service_error
def outlook_calendar_events():
    """Handle calendar event operations (list, create)"""
    data = request.get_json()
    user_id = data.get("user_id")
    operation = data.get("operation", "list")

    service = get_outlook_service()
    if not service:
        return jsonify(
            {
                "success": False,
                "error": "Outlook service not available",
                "service": "outlook",
            }
        ), 503

    try:
        if operation == "list":
            # List calendar events
            time_min = data.get("time_min")
            time_max = data.get("time_max")
            max_results = data.get("max_results", 50)

            events = asyncio.run(
                service.get_calendar_events(
                    user_id=user_id,
                    time_min=time_min,
                    time_max=time_max,
                    max_results=max_results,
                )
            )

            return jsonify(
                {
                    "success": True,
                    "service": "outlook",
                    "operation": operation,
                    "data": events,
                    "count": len(events),
                }
            ), 200

        elif operation == "create":
            # Create calendar event
            event_data = data.get("data", {})
            if not event_data:
                return jsonify(
                    {
                        "success": False,
                        "error": "Missing event data",
                        "service": "outlook",
                    }
                ), 400

            result = asyncio.run(
                service.create_calendar_event(
                    user_id=user_id,
                    subject=event_data.get("subject", ""),
                    body=event_data.get("body", ""),
                    start=event_data.get("start"),
                    end=event_data.get("end"),
                    location=event_data.get("location"),
                    attendees=event_data.get("attendees", []),
                )
            )

            return jsonify(
                {
                    "success": True,
                    "service": "outlook",
                    "operation": operation,
                    "data": result,
                    "message": "Calendar event created successfully",
                }
            ), 200

        else:
            return jsonify(
                {
                    "success": False,
                    "error": f"Unsupported operation: {operation}",
                    "service": "outlook",
                    "supported_operations": ["list", "create"],
                }
            ), 400

    except Exception as e:
        logger.error(f"Calendar operation error: {e}")
        return jsonify(
            {
                "success": False,
                "error": f"Calendar operation failed: {str(e)}",
                "service": "outlook",
            }
        ), 500


# Contact Endpoints
@outlook_enhanced_bp.route("/api/integrations/outlook/contacts", methods=["POST"])
@validate_user_id
@handle_service_error
def outlook_contacts():
    """Handle contact operations (list, create)"""
    data = request.get_json()
    user_id = data.get("user_id")
    operation = data.get("operation", "list")

    service = get_outlook_service()
    if not service:
        return jsonify(
            {
                "success": False,
                "error": "Outlook service not available",
                "service": "outlook",
            }
        ), 503

    try:
        if operation == "list":
            # List contacts
            query = data.get("query")
            max_results = data.get("max_results", 50)

            contacts = asyncio.run(
                service.get_user_contacts(
                    user_id=user_id, query=query, max_results=max_results
                )
            )

            return jsonify(
                {
                    "success": True,
                    "service": "outlook",
                    "operation": operation,
                    "data": contacts,
                    "count": len(contacts),
                }
            ), 200

        elif operation == "create":
            # Create contact
            contact_data = data.get("data", {})
            if not contact_data:
                return jsonify(
                    {
                        "success": False,
                        "error": "Missing contact data",
                        "service": "outlook",
                    }
                ), 400

            result = asyncio.run(
                service.create_contact(
                    user_id=user_id,
                    display_name=contact_data.get("display_name", ""),
                    given_name=contact_data.get("given_name"),
                    surname=contact_data.get("surname"),
                    email_addresses=contact_data.get("email_addresses", []),
                    business_phones=contact_data.get("business_phones", []),
                    company_name=contact_data.get("company_name"),
                )
            )

            return jsonify(
                {
                    "success": True,
                    "service": "outlook",
                    "operation": operation,
                    "data": result,
                    "message": "Contact created successfully",
                }
            ), 200

        else:
            return jsonify(
                {
                    "success": False,
                    "error": f"Unsupported operation: {operation}",
                    "service": "outlook",
                    "supported_operations": ["list", "create"],
                }
            ), 400

    except Exception as e:
        logger.error(f"Contact operation error: {e}")
        return jsonify(
            {
                "success": False,
                "error": f"Contact operation failed: {str(e)}",
                "service": "outlook",
            }
        ), 500


# Task Endpoints
@outlook_enhanced_bp.route("/api/integrations/outlook/tasks", methods=["POST"])
@validate_user_id
@handle_service_error
def outlook_tasks():
    """Handle task operations (list, create)"""
    data = request.get_json()
    user_id = data.get("user_id")
    operation = data.get("operation", "list")

    service = get_outlook_service()
    if not service:
        return jsonify(
            {
                "success": False,
                "error": "Outlook service not available",
                "service": "outlook",
            }
        ), 503

    try:
        if operation == "list":
            # List tasks
            status = data.get("status")
            max_results = data.get("max_results", 50)

            tasks = asyncio.run(
                service.get_user_tasks(
                    user_id=user_id, status=status, max_results=max_results
                )
            )

            return jsonify(
                {
                    "success": True,
                    "service": "outlook",
                    "operation": operation,
                    "data": tasks,
                    "count": len(tasks),
                }
            ), 200

        elif operation == "create":
            # Create task
            task_data = data.get("data", {})
            if not task_data:
                return jsonify(
                    {
                        "success": False,
                        "error": "Missing task data",
                        "service": "outlook",
                    }
                ), 400

            result = asyncio.run(
                service.create_task(
                    user_id=user_id,
                    subject=task_data.get("subject", ""),
                    body=task_data.get("body"),
                    importance=task_data.get("importance", "normal"),
                    due_date_time=task_data.get("due_date_time"),
                    categories=task_data.get("categories", []),
                )
            )

            return jsonify(
                {
                    "success": True,
                    "service": "outlook",
                    "operation": operation,
                    "data": result,
                    "message": "Task created successfully",
                }
            ), 200

        else:
            return jsonify(
                {
                    "success": False,
                    "error": f"Unsupported operation: {operation}",
                    "service": "outlook",
                    "supported_operations": ["list", "create"],
                }
            ), 400

    except Exception as e:
        logger.error(f"Task operation error: {e}")
        return jsonify(
            {
                "success": False,
                "error": f"Task operation failed: {str(e)}",
                "service": "outlook",
            }
        ), 500


# Search Endpoint
@outlook_enhanced_bp.route("/api/integrations/outlook/search", methods=["POST"])
@validate_user_id
@handle_service_error
def outlook_search():
    """Search across Outlook services"""
    data = request.get_json()
    user_id = data.get("user_id")
    query = data.get("query")
    service_types = data.get
