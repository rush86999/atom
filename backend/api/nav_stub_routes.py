"""
Sidebar navigation endpoint stubs for missing nav routes.

These endpoints provide the response shapes the frontend pages expect, so
every sidebar nav item resolves end-to-end. They query real data where models
exist (UserTask, SupportTicket) and return structured empty defaults where the
underlying data layer isn't wired yet (communication analytics).

Response shapes match what the consuming frontend components parse:
- TaskManagement.tsx expects { tasks: [...] }
- useLiveSupport.ts expects { tickets: [...] } or [...]
- CommunicationCommandCenter.tsx expects { success, analytics: {...} }
- IntegrationsPage expects per-provider health-check endpoints
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.database import get_db

logger = logging.getLogger(__name__)

router = BaseAPIRouter(tags=["Nav Stubs"])


# ============================================================================
# Tasks — /api/v1/tasks (Tasks sidebar nav)
# ============================================================================

@router.get("/api/v1/tasks")
async def list_tasks(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List tasks for the current user."""
    try:
        from core.models import UserTask
        tasks = (
            db.query(UserTask)
            .filter(UserTask.user_id == str(current_user.id))
            .order_by(UserTask.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {
            "tasks": [
                {
                    "id": str(t.id),
                    "title": t.title if hasattr(t, "title") else str(getattr(t, "description", "")),
                    "description": getattr(t, "description", ""),
                    "status": getattr(t, "status", "pending"),
                    "priority": getattr(t, "priority", "medium"),
                    "dueDate": getattr(t, "due_date", None),
                    "createdAt": t.created_at.isoformat() if hasattr(t, "created_at") and t.created_at else None,
                    "updatedAt": getattr(t, "updated_at", None),
                    "projectId": getattr(t, "project_id", None),
                }
                for t in tasks
            ]
        }
    except Exception as e:
        logger.warning(f"Task list query failed, returning empty: {e}")
        return {"tasks": []}


@router.get("/api/v1/projects")
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List projects for the current user."""
    return {"projects": []}


# ============================================================================
# Support Tickets — /api/atom/communication/live/support/tickets
# ============================================================================

@router.get("/api/atom/communication/live/support/tickets")
async def list_support_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List support tickets."""
    try:
        from core.models import SupportTicket
        tickets = (
            db.query(SupportTicket)
            .filter(SupportTicket.user_id == str(current_user.id))
            .order_by(SupportTicket.created_at.desc())
            .limit(50)
            .all()
        )
        return {
            "tickets": [
                {
                    "id": str(t.id),
                    "subject": getattr(t, "subject", ""),
                    "status": getattr(t, "status", "open"),
                    "priority": getattr(t, "priority", "medium"),
                    "created_at": t.created_at.isoformat() if hasattr(t, "created_at") and t.created_at else None,
                }
                for t in tickets
            ]
        }
    except Exception as e:
        logger.warning(f"Support ticket query failed, returning empty: {e}")
        return {"tickets": []}


# ============================================================================
# Communication Analytics — /api/atom/communication/memory/analytics
# ============================================================================

@router.get("/api/atom/communication/memory/analytics")
async def communication_analytics(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Communication memory analytics for the Communication Command Center."""
    return {
        "success": True,
        "analytics": {
            "status_distribution": {
                "unread": 0,
                "read": 0,
                "responded": 0,
            },
            "summary": {
                "unique_apps": 0,
                "total_messages": 0,
            },
            "performance": {
                "response_rate": 0.0,
                "avg_response_time": "0m",
            },
        },
    }


@router.get("/api/atom/communication/memory/apps")
async def communication_apps(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """List configured communication apps."""
    return {"apps": []}


# ============================================================================
# Integration Health — /api/integrations/{provider}/health
# ============================================================================

@router.get("/api/integrations/{provider}/health")
async def integration_health(
    provider: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Health check for a specific integration provider."""
    return {
        "provider": provider,
        "status": "not_configured",
        "health": "unknown",
        "message": f"{provider} integration is not configured",
    }
