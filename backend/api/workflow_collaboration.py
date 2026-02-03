"""
Collaboration API Endpoints
REST API for workflow collaboration features
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.collaboration_service import CollaborationService
from core.database import get_db
from core.models import (
    CollaborationComment,
    CollaborationSessionParticipant,
    EditLock,
    WorkflowCollaborationSession,
    WorkflowShare,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/collaboration", tags=["collaboration"])

# WebSocket connections manager
class ConnectionManager:
    """Manage WebSocket connections for real-time collaboration"""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.participant_sockets: Dict[str, Dict[str, WebSocket]] = {}  # {session_id: {user_id: socket}}

    async def connect(self, websocket: WebSocket, session_id: str, user_id: str):
        """Connect WebSocket for collaboration session"""
        await websocket.accept()

        if session_id not in self.active_connections:
            self.active_connections[session_id] = []

        self.active_connections[session_id].append(websocket)

        if session_id not in self.participant_sockets:
            self.participant_sockets[session_id] = {}

        self.participant_sockets[session_id][user_id] = websocket

        logger.info(f"WebSocket connected: session={session_id}, user={user_id}")

    def disconnect(self, websocket: WebSocket, session_id: str, user_id: str):
        """Disconnect WebSocket"""
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)

        if session_id in self.participant_sockets:
            if user_id in self.participant_sockets[session_id]:
                del self.participant_sockets[session_id][user_id]

        logger.info(f"WebSocket disconnected: session={session_id}, user={user_id}")

    async def broadcast_to_session(self, session_id: str, message: dict):
        """Broadcast message to all participants in session"""
        if session_id in self.active_connections:
            for connection in self.active_connections[session_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to connection: {e}")

    async def send_to_user(self, session_id: str, user_id: str, message: dict):
        """Send message to specific user in session"""
        if session_id in self.participant_sockets:
            if user_id in self.participant_sockets[session_id]:
                try:
                    await self.participant_sockets[session_id][user_id].send_json(message)
                except Exception as e:
                    logger.error(f"Error sending to user: {e}")


manager = ConnectionManager()


# Request/Response Models

class CreateSessionRequest(BaseModel):
    """Request to create collaboration session"""
    workflow_id: str = Field(..., description="Workflow ID to collaborate on")
    collaboration_mode: str = Field(default="parallel", description="Collaboration mode")
    max_users: int = Field(default=10, description="Maximum users in session")


class SessionResponse(BaseModel):
    """Collaboration session response"""
    session_id: str
    workflow_id: str
    collaboration_mode: str
    max_users: int
    active_users: List[str]
    created_at: datetime
    last_activity: datetime


class ParticipantUpdate(BaseModel):
    """Update participant presence"""
    cursor_position: Optional[Dict[str, Any]] = None
    selected_node: Optional[str] = None


class AcquireLockRequest(BaseModel):
    """Request to acquire edit lock"""
    resource_type: str = Field(..., description="Type of resource (node, edge, workflow)")
    resource_id: str = Field(..., description="ID of resource to lock")
    lock_reason: Optional[str] = None
    duration_minutes: int = Field(default=30, description="Lock duration in minutes")


class CreateShareRequest(BaseModel):
    """Request to create workflow share"""
    workflow_id: str
    share_type: str = Field(default="link", description="link, email, workspace")
    permissions: Optional[Dict[str, bool]] = None
    expires_in_days: Optional[int] = None
    max_uses: Optional[int] = None


class CreateCommentRequest(BaseModel):
    """Request to add comment"""
    workflow_id: str
    content: str = Field(..., min_length=1, max_length=5000)
    context_type: Optional[str] = None
    context_id: Optional[str] = None
    parent_comment_id: Optional[str] = None


# REST API Endpoints

@router.post("/sessions", response_model=SessionResponse)
async def create_collaboration_session(
    request: CreateSessionRequest,
    user_id: str = Query(..., description="User ID creating the session"),
    db: Session = Depends(get_db)
):
    """Create a new collaboration session for a workflow"""
    try:
        service = CollaborationService(db)

        # Check if active session already exists
        existing = service.get_active_session(request.workflow_id)
        if existing:
            # Add user to existing session
            service.add_participant_to_session(
                session_id=existing.session_id,
                user_id=user_id,
                role="editor"
            )

            return SessionResponse(
                session_id=existing.session_id,
                workflow_id=existing.workflow_id,
                collaboration_mode=existing.collaboration_mode,
                max_users=existing.max_users,
                active_users=existing.active_users or [],
                created_at=existing.created_at,
                last_activity=existing.last_activity
            )

        # Create new session
        session = service.create_collaboration_session(
            workflow_id=request.workflow_id,
            user_id=user_id,
            collaboration_mode=request.collaboration_mode,
            max_users=request.max_users
        )

        return SessionResponse(
            session_id=session.session_id,
            workflow_id=session.workflow_id,
            collaboration_mode=session.collaboration_mode,
            max_users=session.max_users,
            active_users=session.active_users or [],
            created_at=session.created_at,
            last_activity=session.last_activity
        )

    except Exception as e:
        logger.error(f"Error creating collaboration session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}")
async def get_collaboration_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get collaboration session details"""
    try:
        service = CollaborationService(db)
        participants = service.get_session_participants(session_id)

        # Get session from DB
        session = db.query(WorkflowCollaborationSession).filter(
            WorkflowCollaborationSession.session_id == session_id
        ).first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "session_id": session.session_id,
            "workflow_id": session.workflow_id,
            "collaboration_mode": session.collaboration_mode,
            "max_users": session.max_users,
            "active_users": session.active_users or [],
            "participants": [
                {
                    "user_id": p.user_id,
                    "user_name": p.user_name,
                    "user_color": p.user_color,
                    "role": p.role,
                    "can_edit": p.can_edit,
                    "cursor_position": p.cursor_position,
                    "selected_node": p.selected_node,
                    "last_heartbeat": p.last_heartbeat.isoformat()
                }
                for p in participants
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/leave")
async def leave_collaboration_session(
    session_id: str,
    user_id: str = Query(..., description="User ID leaving the session"),
    db: Session = Depends(get_db)
):
    """Leave collaboration session"""
    try:
        service = CollaborationService(db)
        service.remove_participant_from_session(session_id, user_id)

        return {"message": "Successfully left session"}

    except Exception as e:
        logger.error(f"Error leaving session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/heartbeat")
async def update_heartbeat(
    session_id: str,
    update: ParticipantUpdate,
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """Update participant heartbeat and cursor position"""
    try:
        service = CollaborationService(db)
        service.update_participant_heartbeat(
            session_id=session_id,
            user_id=user_id,
            cursor_position=update.cursor_position,
            selected_node=update.selected_node
        )

        # Broadcast cursor update to other participants
        await manager.broadcast_to_session(session_id, {
            "type": "cursor_update",
            "user_id": user_id,
            "cursor_position": update.cursor_position,
            "selected_node": update.selected_node
        })

        return {"message": "Heartbeat updated"}

    except Exception as e:
        logger.error(f"Error updating heartbeat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/locks/acquire")
async def acquire_edit_lock(
    request: AcquireLockRequest,
    session_id: str = Query(..., description="Collaboration session ID"),
    workflow_id: str = Query(..., description="Workflow ID"),
    user_id: str = Query(..., description="User ID acquiring lock"),
    db: Session = Depends(get_db)
):
    """Acquire edit lock on a resource"""
    try:
        service = CollaborationService(db)

        lock = service.acquire_edit_lock(
            session_id=session_id,
            workflow_id=workflow_id,
            user_id=user_id,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            lock_reason=request.lock_reason,
            duration_minutes=request.duration_minutes
        )

        if not lock:
            raise HTTPException(
                status_code=409,
                detail="Resource is already locked by another user"
            )

        # Broadcast lock event to session
        await manager.broadcast_to_session(session_id, {
            "type": "lock_acquired",
            "resource_type": request.resource_type,
            "resource_id": request.resource_id,
            "locked_by": user_id
        })

        return {
            "lock_id": lock.id,
            "resource_type": lock.resource_type,
            "resource_id": lock.resource_id,
            "locked_by": lock.locked_by,
            "locked_at": lock.locked_at.isoformat(),
            "expires_at": lock.expires_at.isoformat() if lock.expires_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acquiring lock: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/locks/release")
async def release_edit_lock(
    resource_type: str,
    resource_id: str,
    session_id: str = Query(..., description="Collaboration session ID"),
    user_id: str = Query(..., description="User ID releasing lock"),
    db: Session = Depends(get_db)
):
    """Release edit lock on a resource"""
    try:
        service = CollaborationService(db)

        success = service.release_edit_lock(
            session_id=session_id,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id
        )

        if not success:
            raise HTTPException(status_code=404, detail="Lock not found")

        # Broadcast unlock event to session
        await manager.broadcast_to_session(session_id, {
            "type": "lock_released",
            "resource_type": resource_type,
            "resource_id": resource_id,
            "released_by": user_id
        })

        return {"message": "Lock released successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error releasing lock: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/locks/{workflow_id}")
async def get_active_locks(
    workflow_id: str,
    db: Session = Depends(get_db)
):
    """Get all active locks for a workflow"""
    try:
        service = CollaborationService(db)
        locks = service.get_active_locks(workflow_id)

        return {
            "locks": [
                {
                    "lock_id": lock.id,
                    "resource_type": lock.resource_type,
                    "resource_id": lock.resource_id,
                    "locked_by": lock.locked_by,
                    "locked_at": lock.locked_at.isoformat(),
                    "expires_at": lock.expires_at.isoformat() if lock.expires_at else None,
                    "lock_reason": lock.lock_reason
                }
                for lock in locks
            ]
        }

    except Exception as e:
        logger.error(f"Error getting locks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/shares")
async def create_workflow_share(
    request: CreateShareRequest,
    user_id: str = Query(..., description="User ID creating share"),
    db: Session = Depends(get_db)
):
    """Create workflow share link"""
    try:
        service = CollaborationService(db)

        share = service.create_workflow_share(
            workflow_id=request.workflow_id,
            user_id=user_id,
            share_type=request.share_type,
            permissions=request.permissions,
            expires_in_days=request.expires_in_days,
            max_uses=request.max_uses
        )

        return share

    except Exception as e:
        logger.error(f"Error creating share: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shares/{share_id}")
async def get_workflow_share(
    share_id: str,
    db: Session = Depends(get_db)
):
    """Get workflow share by share ID"""
    try:
        service = CollaborationService(db)
        share = service.get_workflow_share(share_id)

        if not share:
            raise HTTPException(status_code=404, detail="Share not found or expired")

        # Increment use count is handled in get_workflow_share
        return share

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting share: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/shares/{share_id}")
async def revoke_workflow_share(
    share_id: str,
    user_id: str = Query(..., description="User ID revoking share"),
    db: Session = Depends(get_db)
):
    """Revoke workflow share"""
    try:
        service = CollaborationService(db)
        success = service.revoke_workflow_share(share_id, user_id)

        if not success:
            raise HTTPException(status_code=404, detail="Share not found or permission denied")

        return {"message": "Share revoked successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking share: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/comments")
async def add_comment(
    request: CreateCommentRequest,
    user_id: str = Query(..., description="User ID adding comment"),
    db: Session = Depends(get_db)
):
    """Add comment to workflow"""
    try:
        service = CollaborationService(db)

        comment = service.add_comment(
            workflow_id=request.workflow_id,
            user_id=user_id,
            content=request.content,
            context_type=request.context_type,
            context_id=request.context_id,
            parent_comment_id=request.parent_comment_id
        )

        # Broadcast comment to session (if exists)
        session = service.get_active_session(request.workflow_id)
        if session:
            await manager.broadcast_to_session(session.session_id, {
                "type": "new_comment",
                "comment_id": comment.id,
                "workflow_id": comment.workflow_id,
                "author_id": comment.author_id,
                "content": comment.content,
                "context_type": comment.context_type,
                "context_id": comment.context_id,
                "created_at": comment.created_at.isoformat()
            })

        return comment

    except Exception as e:
        logger.error(f"Error adding comment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/comments/{workflow_id}")
async def get_workflow_comments(
    workflow_id: str,
    context_type: Optional[str] = None,
    context_id: Optional[str] = None,
    include_resolved: bool = False,
    db: Session = Depends(get_db)
):
    """Get comments for workflow"""
    try:
        service = CollaborationService(db)
        comments = service.get_workflow_comments(
            workflow_id=workflow_id,
            context_type=context_type,
            context_id=context_id,
            include_resolved=include_resolved
        )

        return {
            "comments": [
                {
                    "id": c.id,
                    "workflow_id": c.workflow_id,
                    "author_id": c.author_id,
                    "content": c.content,
                    "context_type": c.context_type,
                    "context_id": c.context_id,
                    "parent_comment_id": c.parent_comment_id,
                    "is_resolved": c.is_resolved,
                    "resolved_by": c.resolved_by,
                    "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
                    "created_at": c.created_at.isoformat(),
                    "updated_at": c.updated_at.isoformat()
                }
                for c in comments
            ]
        }

    except Exception as e:
        logger.error(f"Error getting comments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/comments/{comment_id}/resolve")
async def resolve_comment(
    comment_id: str,
    user_id: str = Query(..., description="User ID resolving comment"),
    db: Session = Depends(get_db)
):
    """Mark comment as resolved"""
    try:
        service = CollaborationService(db)
        success = service.resolve_comment(comment_id, user_id)

        if not success:
            raise HTTPException(status_code=404, detail="Comment not found")

        return {"message": "Comment resolved successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving comment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/{workflow_id}")
async def get_audit_log(
    workflow_id: str,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Get audit log for workflow"""
    try:
        service = CollaborationService(db)
        audits = service.get_audit_log(workflow_id, limit)

        return {
            "audit_log": [
                {
                    "id": a.id,
                    "workflow_id": a.workflow_id,
                    "user_id": a.user_id,
                    "action_type": a.action_type,
                    "action_details": a.action_details,
                    "resource_type": a.resource_type,
                    "resource_id": a.resource_id,
                    "session_id": a.session_id,
                    "created_at": a.created_at.isoformat()
                }
                for a in audits
            ]
        }

    except Exception as e:
        logger.error(f"Error getting audit log: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket Endpoint

@router.websocket("/ws/{session_id}/{user_id}")
async def websocket_collaboration(
    websocket: WebSocket,
    session_id: str,
    user_id: str,
    db: Session = Depends(get_db)
):
    """WebSocket endpoint for real-time collaboration updates"""
    await manager.connect(websocket, session_id, user_id)

    try:
        service = CollaborationService(db)

        # Add participant to session
        service.add_participant_to_session(
            session_id=session_id,
            user_id=user_id,
            role="editor"
        )

        # Broadcast user joined event
        await manager.broadcast_to_session(session_id, {
            "type": "user_joined",
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        })

        # Keep connection alive and handle messages
        while True:
            data = await websocket.receive_json()

            # Handle different message types
            message_type = data.get("type")

            if message_type == "cursor_update":
                # Update cursor position
                service.update_participant_heartbeat(
                    session_id=session_id,
                    user_id=user_id,
                    cursor_position=data.get("cursor_position"),
                    selected_node=data.get("selected_node")
                )

                # Broadcast to other users
                await manager.broadcast_to_session(session_id, {
                    "type": "cursor_update",
                    "user_id": user_id,
                    "cursor_position": data.get("cursor_position"),
                    "selected_node": data.get("selected_node"),
                    "timestamp": datetime.now().isoformat()
                })

            elif message_type == "heartbeat":
                # Just update heartbeat
                service.update_participant_heartbeat(session_id, user_id)

            elif message_type == "text_change":
                # Broadcast text/node changes to other users
                await manager.broadcast_to_session(session_id, {
                    "type": "content_update",
                    "user_id": user_id,
                    "change": data.get("change"),
                    "timestamp": datetime.now().isoformat()
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id, user_id)

        # Remove participant from session
        service.remove_participant_from_session(session_id, user_id)

        # Broadcast user left event
        await manager.broadcast_to_session(session_id, {
            "type": "user_left",
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, session_id, user_id)
