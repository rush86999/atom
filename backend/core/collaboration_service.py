"""
Collaboration Service
Manages real-time collaboration features for workflows
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.models import (
    CollaborationAudit,
    CollaborationComment,
    CollaborationSessionParticipant,
    EditLock,
    User,
    WorkflowCollaborationSession,
    WorkflowShare,
)

logger = logging.getLogger(__name__)


class CollaborationService:
    """Service for managing workflow collaboration features"""

    def __init__(self, db: Session):
        self.db = db

    # Session Management

    def create_collaboration_session(
        self,
        workflow_id: str,
        user_id: str,
        collaboration_mode: str = "parallel",
        max_users: int = 10
    ) -> WorkflowCollaborationSession:
        """Create a new collaboration session"""
        try:
            session_id = f"collab_{uuid.uuid4().hex[:12]}"

            session = WorkflowCollaborationSession(
                session_id=session_id,
                workflow_id=workflow_id,
                created_by=user_id,
                collaboration_mode=collaboration_mode,
                max_users=max_users,
                active_users=[user_id],
                last_activity=datetime.now()
            )

            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

            # Auto-join creator as first participant
            self.add_participant_to_session(
                session_id=session_id,
                user_id=user_id,
                role="owner"
            )

            # Audit log
            self._audit_action(
                workflow_id=workflow_id,
                user_id=user_id,
                action_type="create_session",
                resource_type="session",
                resource_id=session_id
            )

            logger.info(f"Created collaboration session {session_id} for workflow {workflow_id}")
            return session

        except Exception as e:
            logger.error(f"Error creating collaboration session: {e}")
            self.db.rollback()
            raise

    def get_active_session(self, workflow_id: str) -> Optional[WorkflowCollaborationSession]:
        """Get active collaboration session for workflow"""
        try:
            # Session is considered active if last activity was within 30 minutes
            threshold = datetime.now() - timedelta(minutes=30)

            session = self.db.query(WorkflowCollaborationSession).filter(
                and_(
                    WorkflowCollaborationSession.workflow_id == workflow_id,
                    WorkflowCollaborationSession.last_activity >= threshold
                )
            ).first()

            return session

        except Exception as e:
            logger.error(f"Error getting active session: {e}")
            return None

    def update_session_activity(self, session_id: str) -> None:
        """Update session last activity timestamp"""
        try:
            session = self.db.query(WorkflowCollaborationSession).filter(
                WorkflowCollaborationSession.session_id == session_id
            ).first()

            if session:
                session.last_activity = datetime.now()
                self.db.commit()

        except Exception as e:
            logger.error(f"Error updating session activity: {e}")
            self.db.rollback()

    # Participant Management

    def add_participant_to_session(
        self,
        session_id: str,
        user_id: str,
        role: str = "editor",
        user_name: Optional[str] = None,
        user_color: Optional[str] = None
    ) -> CollaborationSessionParticipant:
        """Add user to collaboration session"""
        try:
            # Get user info if not provided
            if not user_name:
                user = self.db.query(User).filter(User.id == user_id).first()
                if user:
                    user_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email

            # Generate color if not provided
            if not user_color:
                user_color = self._generate_user_color(user_id)

            participant = CollaborationSessionParticipant(
                session_id=session_id,
                user_id=user_id,
                user_name=user_name,
                user_color=user_color,
                role=role,
                can_edit=role in ["owner", "editor"],
                joined_at=datetime.now(),
                last_heartbeat=datetime.now()
            )

            self.db.add(participant)

            # Update session's active users list
            session = self.db.query(WorkflowCollaborationSession).filter(
                WorkflowCollaborationSession.session_id == session_id
            ).first()

            if session:
                active_users = session.active_users or []
                if user_id not in active_users:
                    active_users.append(user_id)
                session.active_users = active_users
                session.last_activity = datetime.now()

            self.db.commit()
            self.db.refresh(participant)

            logger.info(f"Added user {user_id} to session {session_id}")
            return participant

        except Exception as e:
            logger.error(f"Error adding participant: {e}")
            self.db.rollback()
            raise

    def remove_participant_from_session(self, session_id: str, user_id: str) -> None:
        """Remove user from collaboration session"""
        try:
            # Delete participant record
            participant = self.db.query(CollaborationSessionParticipant).filter(
                and_(
                    CollaborationSessionParticipant.session_id == session_id,
                    CollaborationSessionParticipant.user_id == user_id
                )
            ).first()

            if participant:
                self.db.delete(participant)

            # Update session's active users list
            session = self.db.query(WorkflowCollaborationSession).filter(
                WorkflowCollaborationSession.session_id == session_id
            ).first()

            if session:
                active_users = [u for u in (session.active_users or []) if u != user_id]
                session.active_users = active_users

            self.db.commit()

            logger.info(f"Removed user {user_id} from session {session_id}")

        except Exception as e:
            logger.error(f"Error removing participant: {e}")
            self.db.rollback()

    def update_participant_heartbeat(
        self,
        session_id: str,
        user_id: str,
        cursor_position: Optional[Dict[str, Any]] = None,
        selected_node: Optional[str] = None
    ) -> None:
        """Update participant's heartbeat and cursor position"""
        try:
            participant = self.db.query(CollaborationSessionParticipant).filter(
                and_(
                    CollaborationSessionParticipant.session_id == session_id,
                    CollaborationSessionParticipant.user_id == user_id
                )
            ).first()

            if participant:
                participant.last_heartbeat = datetime.now()
                if cursor_position:
                    participant.cursor_position = cursor_position
                if selected_node:
                    participant.selected_node = selected_node

                self.db.commit()

        except Exception as e:
            logger.error(f"Error updating heartbeat: {e}")
            self.db.rollback()

    def get_session_participants(self, session_id: str) -> List[CollaborationSessionParticipant]:
        """Get all active participants in session"""
        try:
            # Consider participants inactive if no heartbeat in 2 minutes
            threshold = datetime.now() - timedelta(minutes=2)

            participants = self.db.query(CollaborationSessionParticipant).filter(
                and_(
                    CollaborationSessionParticipant.session_id == session_id,
                    CollaborationSessionParticipant.last_heartbeat >= threshold
                )
            ).all()

            return participants

        except Exception as e:
            logger.error(f"Error getting participants: {e}")
            return []

    # Edit Locking

    def acquire_edit_lock(
        self,
        session_id: str,
        workflow_id: str,
        user_id: str,
        resource_type: str,
        resource_id: str,
        lock_reason: Optional[str] = None,
        duration_minutes: int = 30
    ) -> Optional[EditLock]:
        """Acquire edit lock on a resource"""
        try:
            # Check if lock already exists
            existing_lock = self.db.query(EditLock).filter(
                and_(
                    EditLock.session_id == session_id,
                    EditLock.resource_type == resource_type,
                    EditLock.resource_id == resource_id,
                    EditLock.is_active == True
                )
            ).first()

            if existing_lock:
                # Check if lock has expired
                if existing_lock.expires_at and existing_lock.expires_at < datetime.now():
                    existing_lock.is_active = False
                else:
                    # Lock is held by someone else
                    return None

            expires_at = datetime.now() + timedelta(minutes=duration_minutes)

            lock = EditLock(
                session_id=session_id,
                workflow_id=workflow_id,
                resource_type=resource_type,
                resource_id=resource_id,
                locked_by=user_id,
                locked_at=datetime.now(),
                expires_at=expires_at,
                lock_reason=lock_reason,
                is_active=True
            )

            self.db.add(lock)
            self.db.commit()
            self.db.refresh(lock)

            logger.info(f"Lock acquired for {resource_type}:{resource_id} by {user_id}")
            return lock

        except Exception as e:
            logger.error(f"Error acquiring lock: {e}")
            self.db.rollback()
            return None

    def release_edit_lock(
        self,
        session_id: str,
        resource_type: str,
        resource_id: str,
        user_id: str
    ) -> bool:
        """Release edit lock"""
        try:
            lock = self.db.query(EditLock).filter(
                and_(
                    EditLock.session_id == session_id,
                    EditLock.resource_type == resource_type,
                    EditLock.resource_id == resource_id,
                    EditLock.locked_by == user_id,
                    EditLock.is_active == True
                )
            ).first()

            if lock:
                lock.is_active = False
                self.db.commit()
                logger.info(f"Lock released for {resource_type}:{resource_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error releasing lock: {e}")
            self.db.rollback()
            return False

    def get_active_locks(self, workflow_id: str) -> List[EditLock]:
        """Get all active locks for workflow"""
        try:
            locks = self.db.query(EditLock).filter(
                and_(
                    EditLock.workflow_id == workflow_id,
                    EditLock.is_active == True
                )
            ).all()

            # Filter out expired locks
            active_locks = []
            for lock in locks:
                if lock.expires_at and lock.expires_at < datetime.now():
                    lock.is_active = False
                else:
                    active_locks.append(lock)

            self.db.commit()

            return active_locks

        except Exception as e:
            logger.error(f"Error getting locks: {e}")
            return []

    # Sharing

    def create_workflow_share(
        self,
        workflow_id: str,
        user_id: str,
        share_type: str = "link",
        permissions: Optional[Dict[str, bool]] = None,
        expires_in_days: Optional[int] = None,
        max_uses: Optional[int] = None
    ) -> WorkflowShare:
        """Create workflow share link"""
        try:
            share_id = f"share_{uuid.uuid4().hex[:12]}"
            share_link = f"/share/{share_id}"

            # Default permissions
            if not permissions:
                permissions = {
                    "can_view": True,
                    "can_edit": False,
                    "can_comment": True,
                    "can_share": False
                }

            # Calculate expiry
            expires_at = None
            if expires_in_days:
                expires_at = datetime.now() + timedelta(days=expires_in_days)

            share = WorkflowShare(
                share_id=share_id,
                workflow_id=workflow_id,
                created_by=user_id,
                share_link=share_link,
                share_type=share_type,
                permissions=permissions,
                expires_at=expires_at,
                max_uses=max_uses,
                use_count=0,
                is_active=True
            )

            self.db.add(share)
            self.db.commit()
            self.db.refresh(share)

            # Audit log
            self._audit_action(
                workflow_id=workflow_id,
                user_id=user_id,
                action_type="share_workflow",
                resource_type="share",
                resource_id=share_id
            )

            logger.info(f"Created share {share_id} for workflow {workflow_id}")
            return share

        except Exception as e:
            logger.error(f"Error creating share: {e}")
            self.db.rollback()
            raise

    def get_workflow_share(self, share_id: str) -> Optional[WorkflowShare]:
        """Get workflow share by ID"""
        try:
            share = self.db.query(WorkflowShare).filter(
                and_(
                    WorkflowShare.share_id == share_id,
                    WorkflowShare.is_active == True
                )
            ).first()

            # Check expiry
            if share:
                if share.expires_at and share.expires_at < datetime.now():
                    share.is_active = False
                    self.db.commit()
                    return None

                if share.max_uses and share.use_count >= share.max_uses:
                    share.is_active = False
                    self.db.commit()
                    return None

                # Update last accessed
                share.last_accessed = datetime.now()
                share.use_count += 1
                self.db.commit()

            return share

        except Exception as e:
            logger.error(f"Error getting share: {e}")
            return None

    def revoke_workflow_share(self, share_id: str, user_id: str) -> bool:
        """Revoke workflow share"""
        try:
            share = self.db.query(WorkflowShare).filter(
                WorkflowShare.share_id == share_id
            ).first()

            if share and share.created_by == user_id:
                share.is_active = False
                share.revoked_at = datetime.now()
                share.revoked_by = user_id

                self.db.commit()

                # Audit log
                self._audit_action(
                    workflow_id=share.workflow_id,
                    user_id=user_id,
                    action_type="revoke_share",
                    resource_type="share",
                    resource_id=share_id
                )

                logger.info(f"Revoked share {share_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error revoking share: {e}")
            self.db.rollback()
            return False

    # Comments

    def add_comment(
        self,
        workflow_id: str,
        user_id: str,
        content: str,
        context_type: Optional[str] = None,
        context_id: Optional[str] = None,
        parent_comment_id: Optional[str] = None
    ) -> CollaborationComment:
        """Add comment to workflow"""
        try:
            comment = CollaborationComment(
                workflow_id=workflow_id,
                author_id=user_id,
                content=content,
                context_type=context_type,
                context_id=context_id,
                parent_comment_id=parent_comment_id,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

            self.db.add(comment)
            self.db.commit()
            self.db.refresh(comment)

            # Audit log
            self._audit_action(
                workflow_id=workflow_id,
                user_id=user_id,
                action_type="add_comment",
                resource_type="comment",
                resource_id=comment.id
            )

            logger.info(f"Added comment {comment.id} to workflow {workflow_id}")
            return comment

        except Exception as e:
            logger.error(f"Error adding comment: {e}")
            self.db.rollback()
            raise

    def get_workflow_comments(
        self,
        workflow_id: str,
        context_type: Optional[str] = None,
        context_id: Optional[str] = None,
        include_resolved: bool = False
    ) -> List[CollaborationComment]:
        """Get comments for workflow"""
        try:
            query = self.db.query(CollaborationComment).filter(
                CollaborationComment.workflow_id == workflow_id
            )

            if not include_resolved:
                query = query.filter(CollaborationComment.is_resolved == False)

            if context_type:
                query = query.filter(CollaborationComment.context_type == context_type)

            if context_id:
                query = query.filter(CollaborationComment.context_id == context_id)

            # Order by created date, newest first
            comments = query.order_by(CollaborationComment.created_at.desc()).all()

            return comments

        except Exception as e:
            logger.error(f"Error getting comments: {e}")
            return []

    def resolve_comment(self, comment_id: str, user_id: str) -> bool:
        """Mark comment as resolved"""
        try:
            comment = self.db.query(CollaborationComment).filter(
                CollaborationComment.id == comment_id
            ).first()

            if comment:
                comment.is_resolved = True
                comment.resolved_by = user_id
                comment.resolved_at = datetime.now()

                self.db.commit()

                # Audit log
                self._audit_action(
                    workflow_id=comment.workflow_id,
                    user_id=user_id,
                    action_type="resolve_comment",
                    resource_type="comment",
                    resource_id=comment_id
                )

                logger.info(f"Resolved comment {comment_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error resolving comment: {e}")
            self.db.rollback()
            return False

    # Audit

    def _audit_action(
        self,
        workflow_id: str,
        user_id: str,
        action_type: str,
        resource_type: str,
        resource_id: str,
        action_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log collaboration action to audit table"""
        try:
            audit = CollaborationAudit(
                workflow_id=workflow_id,
                user_id=user_id,
                action_type=action_type,
                resource_type=resource_type,
                resource_id=resource_id,
                action_details=action_details or {},
                created_at=datetime.now()
            )

            self.db.add(audit)
            self.db.commit()

        except Exception as e:
            logger.error(f"Error auditing action: {e}")

    def get_audit_log(
        self,
        workflow_id: str,
        limit: int = 100
    ) -> List[CollaborationAudit]:
        """Get audit log for workflow"""
        try:
            audits = self.db.query(CollaborationAudit).filter(
                CollaborationAudit.workflow_id == workflow_id
            ).order_by(
                CollaborationAudit.created_at.desc()
            ).limit(limit).all()

            return audits

        except Exception as e:
            logger.error(f"Error getting audit log: {e}")
            return []

    # Helper Methods

    def _generate_user_color(self, user_id: str) -> str:
        """Generate consistent color for user based on user_id"""
        # Predefined colors for good visibility
        colors = [
            "#2196F3",  # Blue
            "#4CAF50",  # Green
            "#FF9800",  # Orange
            "#9C27B0",  # Purple
            "#F44336",  # Red
            "#00BCD4",  # Cyan
            "#FFEB3B",  # Yellow
            "#795548",  # Brown
            "#607D8B",  # Blue Grey
            "#E91E63",  # Pink
        ]

        # Hash user_id to get index
        hash_val = hash(user_id)
        index = abs(hash_val) % len(colors)

        return colors[index]

    def cleanup_inactive_participants(self, session_id: str) -> int:
        """Remove inactive participants from session"""
        try:
            # Remove participants with no heartbeat in 5 minutes
            threshold = datetime.now() - timedelta(minutes=5)

            deleted = self.db.query(CollaborationSessionParticipant).filter(
                and_(
                    CollaborationSessionParticipant.session_id == session_id,
                    CollaborationSessionParticipant.last_heartbeat < threshold
                )
            ).delete()

            self.db.commit()

            count = deleted or 0
            if count > 0:
                logger.info(f"Cleaned up {count} inactive participants from session {session_id}")

            return count

        except Exception as e:
            logger.error(f"Error cleaning up participants: {e}")
            self.db.rollback()
            return 0

    def cleanup_expired_locks(self) -> int:
        """Clean up expired locks"""
        try:
            now = datetime.now()

            updated = self.db.query(EditLock).filter(
                and_(
                    EditLock.is_active == True,
                    EditLock.expires_at < now
                )
            ).update({"is_active": False})

            self.db.commit()

            count = updated or 0
            if count > 0:
                logger.info(f"Cleaned up {count} expired locks")

            return count

        except Exception as e:
            logger.error(f"Error cleaning up locks: {e}")
            self.db.rollback()
            return 0
