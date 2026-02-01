"""
Multi-Agent Canvas Coordination Service

Manages collaboration between multiple agents on shared canvases with:
- Session management
- Role-based permissions
- Conflict resolution
- Real-time coordination
"""

import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from sqlalchemy.sql import func as sql_func

from core.models import (
    CanvasCollaborationSession,
    CanvasAgentParticipant,
    CanvasConflict,
    AgentRegistry,
    CanvasAudit
)

logger = logging.getLogger(__name__)


class CollaborationMode(str, Enum):
    """Collaboration modes for multi-agent sessions."""
    SEQUENTIAL = "sequential"  # Agents take turns (default)
    PARALLEL = "parallel"  # Agents work simultaneously with locks
    LOCKED = "locked"  # First agent to claim component wins


class AgentRole(str, Enum):
    """Agent roles in collaboration sessions."""
    OWNER = "owner"  # Full control
    CONTRIBUTOR = "contributor"  # Can add/edit components
    REVIEWER = "reviewer"  # Read-only with suggestions
    VIEWER = "viewer"  # Read-only


class CanvasCollaborationService:
    """
    Service for managing multi-agent collaboration on canvases.

    Enables multiple agents to work together on shared canvases with
    proper coordination, conflict resolution, and permission management.
    """

    def __init__(self, db: Session):
        self.db = db

    # ========================================================================
    # Session Management
    # ========================================================================

    def create_collaboration_session(
        self,
        canvas_id: str,
        session_id: str,
        user_id: str,
        collaboration_mode: str = "sequential",
        max_agents: int = 5,
        initial_agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new multi-agent collaboration session.

        Args:
            canvas_id: Canvas identifier
            session_id: Canvas session identifier
            user_id: Owner user ID
            collaboration_mode: sequential, parallel, or locked
            max_agents: Maximum number of agents
            initial_agent_id: Optional first agent to add

        Returns:
            Created session data
        """
        # Create session
        collab_session = CanvasCollaborationSession(
            id=str(uuid.uuid4()),
            canvas_id=canvas_id,
            session_id=session_id,
            user_id=user_id,
            collaboration_mode=collaboration_mode,
            max_agents=max_agents,
            status="active"
        )

        self.db.add(collab_session)
        self.db.commit()
        self.db.refresh(collab_session)

        # Add initial agent if provided
        if initial_agent_id:
            self.add_agent_to_session(
                collab_session.id,
                initial_agent_id,
                user_id,
                role="owner"
            )

        logger.info(
            f"Created collaboration session {collab_session.id} "
            f"for canvas {canvas_id} in mode {collaboration_mode}"
        )

        return {
            "session_id": collab_session.id,
            "canvas_id": canvas_id,
            "collaboration_mode": collaboration_mode,
            "max_agents": max_agents,
            "status": "active",
            "participants": []
        }

    def add_agent_to_session(
        self,
        collaboration_session_id: str,
        agent_id: str,
        user_id: str,
        role: str = "contributor",
        permissions: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add an agent to a collaboration session.

        Args:
            collaboration_session_id: Session ID
            agent_id: Agent to add
            user_id: User initiating the agent
            role: Agent role (owner, contributor, reviewer, viewer)
            permissions: Optional specific permissions

        Returns:
            Participant data
        """
        # Validate session exists and is active
        session = self.db.query(CanvasCollaborationSession).filter(
            CanvasCollaborationSession.id == collaboration_session_id
        ).first()

        if not session:
            return {
                "error": f"Collaboration session '{collaboration_session_id}' not found"
            }

        if session.status != "active":
            return {
                "error": f"Session is {session.status}, cannot add agents"
            }

        # Check if agent already in session
        existing = self.db.query(CanvasAgentParticipant).filter(
            and_(
                CanvasAgentParticipant.collaboration_session_id == collaboration_session_id,
                CanvasAgentParticipant.agent_id == agent_id
            )
        ).first()

        if existing:
            return {
                "error": f"Agent '{agent_id}' is already in this session"
            }

        # Check max agents limit
        participant_count = self.db.query(func.count(CanvasAgentParticipant.id)).filter(
            CanvasAgentParticipant.collaboration_session_id == collaboration_session_id
        ).scalar()

        if participant_count >= session.max_agents:
            return {
                "error": f"Session has reached maximum agent capacity ({session.max_agents})"
            }

        # Validate agent exists
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            return {
                "error": f"Agent '{agent_id}' not found"
            }

        # Create participant
        participant = CanvasAgentParticipant(
            id=str(uuid.uuid4()),
            collaboration_session_id=collaboration_session_id,
            agent_id=agent_id,
            user_id=user_id,
            role=role,
            permissions=permissions or self._get_default_permissions(role)
        )

        self.db.add(participant)
        self.db.commit()
        self.db.refresh(participant)

        logger.info(
            f"Added agent {agent_id} to collaboration session "
            f"{collaboration_session_id} with role {role}"
        )

        return {
            "participant_id": participant.id,
            "agent_id": agent_id,
            "agent_name": agent.name,
            "role": role,
            "permissions": participant.permissions,
            "status": participant.status
        }

    def remove_agent_from_session(
        self,
        collaboration_session_id: str,
        agent_id: str
    ) -> Dict[str, Any]:
        """
        Remove an agent from a collaboration session.

        Args:
            collaboration_session_id: Session ID
            agent_id: Agent to remove

        Returns:
            Updated session data
        """
        participant = self.db.query(CanvasAgentParticipant).filter(
            and_(
                CanvasAgentParticipant.collaboration_session_id == collaboration_session_id,
                CanvasAgentParticipant.agent_id == agent_id
            )
        ).first()

        if not participant:
            return {
                "error": f"Agent '{agent_id}' not found in session"
            }

        # Release any held locks
        if participant.held_locks:
            self._release_all_locks(participant)

        # Mark as left
        participant.left_at = datetime.now()
        participant.status = "completed"
        self.db.commit()

        logger.info(f"Removed agent {agent_id} from collaboration session {collaboration_session_id}")

        return {
            "agent_id": agent_id,
            "status": "removed"
        }

    def get_session_status(self, collaboration_session_id: str) -> Dict[str, Any]:
        """
        Get current status of a collaboration session.

        Args:
            collaboration_session_id: Session ID

        Returns:
            Session status with participants
        """
        session = self.db.query(CanvasCollaborationSession).filter(
            CanvasCollaborationSession.id == collaboration_session_id
        ).first()

        if not session:
            return {
                "error": f"Collaboration session '{collaboration_session_id}' not found"
            }

        # Get active participants (exclude completed/left)
        participants = self.db.query(CanvasAgentParticipant).filter(
            and_(
                CanvasAgentParticipant.collaboration_session_id == collaboration_session_id,
                CanvasAgentParticipant.status != "completed"
            )
        ).all()

        return {
            "session_id": session.id,
            "canvas_id": session.canvas_id,
            "status": session.status,
            "collaboration_mode": session.collaboration_mode,
            "max_agents": session.max_agents,
            "created_at": session.created_at.isoformat(),
            "participants": [
                {
                    "participant_id": p.id,
                    "agent_id": p.agent_id,
                    "role": p.role,
                    "status": p.status,
                    "actions_count": p.actions_count,
                    "held_locks": p.held_locks or [],
                    "last_activity": p.last_activity_at.isoformat()
                }
                for p in participants
            ]
        }

    # ========================================================================
    # Permission Management
    # ========================================================================

    def check_agent_permission(
        self,
        collaboration_session_id: str,
        agent_id: str,
        action: str,
        component_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check if an agent has permission to perform an action.

        Args:
            collaboration_session_id: Session ID
            agent_id: Agent to check
            action: Action to perform (read, write, delete, lock)
            component_id: Optional specific component

        Returns:
            Permission check result
        """
        participant = self.db.query(CanvasAgentParticipant).filter(
            and_(
                CanvasAgentParticipant.collaboration_session_id == collaboration_session_id,
                CanvasAgentParticipant.agent_id == agent_id
            )
        ).first()

        if not participant:
            return {
                "allowed": False,
                "reason": f"Agent '{agent_id}' is not in this collaboration session"
            }

        # Check if agent is active
        if participant.status != "active":
            return {
                "allowed": False,
                "reason": f"Agent status is '{participant.status}'"
            }

        # Check role-based permissions
        permissions = participant.permissions or {}

        # Specific component permissions
        if component_id and "components" in permissions:
            component_perms = permissions["components"].get(component_id, {})
            if action in component_perms:
                return {
                    "allowed": component_perms[action],
                    "reason": "Component-specific permission"
                }

        # General permissions
        if action in permissions:
            return {
                "allowed": permissions[action],
                "reason": "General permission"
            }

        # Role-based defaults
        role = participant.role

        if role == "viewer":
            return {
                "allowed": action == "read",
                "reason": "Viewer role only allows read access"
            }

        if role == "reviewer":
            return {
                "allowed": action in ["read", "suggest"],
                "reason": "Reviewer role allows read and suggest"
            }

        if role in ["contributor", "owner"]:
            return {
                "allowed": True,
                "reason": f"{role} role has full permissions"
            }

        return {
            "allowed": False,
            "reason": "Unknown role or permission"
        }

    # ========================================================================
    # Conflict Resolution
    # ========================================================================

    def check_for_conflicts(
        self,
        collaboration_session_id: str,
        agent_id: str,
        component_id: str,
        action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check if an action conflicts with other agents' work.

        Args:
            collaboration_session_id: Session ID
            agent_id: Agent performing action
            component_id: Component being modified
            action: Action details

        Returns:
            Conflict check result
        """
        session = self.db.query(CanvasCollaborationSession).filter(
            CanvasCollaborationSession.id == collaboration_session_id
        ).first()

        if not session:
            return {
                "has_conflict": False,
                "reason": "Session not found"
            }

        # In sequential mode, check if another agent is active
        if session.collaboration_mode == "sequential":
            recent_activity = self.db.query(CanvasAgentParticipant).filter(
                and_(
                    CanvasAgentParticipant.collaboration_session_id == collaboration_session_id,
                    CanvasAgentParticipant.agent_id != agent_id,
                    CanvasAgentParticipant.last_activity_at >= datetime.now() - timedelta(seconds=5)
                )
            ).first()

            if recent_activity:
                return {
                    "has_conflict": True,
                    "conflict_type": "sequential",
                    "conflicting_agent": recent_activity.agent_id,
                    "reason": f"Agent {recent_activity.agent_id} was recently active (sequential mode)"
                }

        # In parallel mode, check for locks
        if session.collaboration_mode == "parallel":
            locked_by = self.db.query(CanvasAgentParticipant).filter(
                and_(
                    CanvasAgentParticipant.collaboration_session_id == collaboration_session_id,
                    CanvasAgentParticipant.agent_id != agent_id,
                    CanvasAgentParticipant.status == "active"
                )
            ).all()

            for participant in locked_by:
                if component_id in (participant.held_locks or []):
                    return {
                        "has_conflict": True,
                        "conflict_type": "locked",
                        "conflicting_agent": participant.agent_id,
                        "reason": f"Component {component_id} is locked by agent {participant.agent_id}"
                    }

        # In locked mode, first agent wins
        # Check if any other agent has recently worked on this component (held locks)
        if session.collaboration_mode == "locked" and component_id:
            locked_by = self.db.query(CanvasAgentParticipant).filter(
                and_(
                    CanvasAgentParticipant.collaboration_session_id == collaboration_session_id,
                    CanvasAgentParticipant.agent_id != agent_id,
                    CanvasAgentParticipant.status == "active"
                )
            ).all()

            for participant in locked_by:
                if component_id in (participant.held_locks or []):
                    return {
                        "has_conflict": True,
                        "conflict_type": "locked",
                        "conflicting_agent": participant.agent_id,
                        "reason": f"Component {component_id} is locked by agent {participant.agent_id}"
                    }

        return {
            "has_conflict": False,
            "reason": "No conflicts detected"
        }

    def resolve_conflict(
        self,
        collaboration_session_id: str,
        agent_a_id: str,
        agent_b_id: str,
        component_id: str,
        agent_a_action: Dict[str, Any],
        agent_b_action: Dict[str, Any],
        resolution_strategy: str = "first_come_first_served"
    ) -> Dict[str, Any]:
        """
        Resolve a conflict between two agents.

        Args:
            collaboration_session_id: Session ID
            agent_a_id: First agent
            agent_b_id: Second agent
            component_id: Contested component
            agent_a_action: First agent's action
            agent_b_action: Second agent's action
            resolution_strategy: How to resolve (first_come_first_served, priority, merge)

        Returns:
            Resolution result
        """
        # Log conflict
        conflict = CanvasConflict(
            id=str(uuid.uuid4()),
            collaboration_session_id=collaboration_session_id,
            canvas_id=None,  # Will be filled from session
            component_id=component_id,
            agent_a_id=agent_a_id,
            agent_b_id=agent_b_id,
            agent_a_action=agent_a_action,
            agent_b_action=agent_b_action,
            resolution="pending"
        )

        # Get session for canvas_id
        session = self.db.query(CanvasCollaborationSession).filter(
            CanvasCollaborationSession.id == collaboration_session_id
        ).first()

        if session:
            conflict.canvas_id = session.canvas_id

        self.db.add(conflict)

        # Apply resolution strategy
        if resolution_strategy == "first_come_first_served":
            # Agent A wins (they came first)
            resolution = "agent_a_wins"
            resolved_action = agent_a_action

        elif resolution_strategy == "priority":
            # Agent with higher role wins
            participant_a = self.db.query(CanvasAgentParticipant).filter(
                and_(
                    CanvasAgentParticipant.collaboration_session_id == collaboration_session_id,
                    CanvasAgentParticipant.agent_id == agent_a_id
                )
            ).first()

            participant_b = self.db.query(CanvasAgentParticipant).filter(
                and_(
                    CanvasAgentParticipant.collaboration_session_id == collaboration_session_id,
                    CanvasAgentParticipant.agent_id == agent_b_id
                )
            ).first()

            role_priority = {"owner": 4, "contributor": 3, "reviewer": 2, "viewer": 1}

            if participant_a and participant_b:
                if role_priority.get(participant_a.role, 0) >= role_priority.get(participant_b.role, 0):
                    resolution = "agent_a_wins"
                    resolved_action = agent_a_action
                else:
                    resolution = "agent_b_wins"
                    resolved_action = agent_b_action
            else:
                resolution = "agent_a_wins"
                resolved_action = agent_a_action

        elif resolution_strategy == "merge":
            # Try to merge both actions
            resolution = "merged"
            resolved_action = self._merge_actions(agent_a_action, agent_b_action)

        else:
            resolution = "agent_a_wins"
            resolved_action = agent_a_action

        # Update conflict record
        conflict.resolution = resolution
        conflict.resolved_by = "system"
        conflict.resolved_action = resolved_action
        conflict.resolved_at = datetime.now()

        self.db.commit()

        logger.info(
            f"Resolved conflict between {agent_a_id} and {agent_b_id} "
            f"for component {component_id} using strategy: {resolution}"
        )

        return {
            "conflict_id": conflict.id,
            "resolution": resolution,
            "resolved_action": resolved_action
        }

    # ========================================================================
    # Activity Tracking
    # ========================================================================

    def record_agent_action(
        self,
        collaboration_session_id: str,
        agent_id: str,
        action: str,
        component_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record an agent's action in the collaboration session.

        Args:
            collaboration_session_id: Session ID
            agent_id: Agent performing action
            action: Action performed
            component_id: Optional component ID

        Returns:
            Recorded action data
        """
        participant = self.db.query(CanvasAgentParticipant).filter(
            and_(
                CanvasAgentParticipant.collaboration_session_id == collaboration_session_id,
                CanvasAgentParticipant.agent_id == agent_id
            )
        ).first()

        if not participant:
            return {
                "error": f"Agent '{agent_id}' not found in session"
            }

        # Update activity tracking
        participant.actions_count += 1
        participant.last_activity_at = datetime.now()

        # Track locks in parallel mode
        if component_id and action in ["update", "lock"]:
            if component_id not in (participant.held_locks or []):
                participant.held_locks = (participant.held_locks or []) + [component_id]
                # Mark JSON field as modified for SQLAlchemy
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(participant, 'held_locks')

        self.db.commit()
        self.db.refresh(participant)

        return {
            "agent_id": agent_id,
            "action": action,
            "component_id": component_id,
            "actions_count": participant.actions_count
        }

    def release_agent_lock(
        self,
        collaboration_session_id: str,
        agent_id: str,
        component_id: str
    ) -> Dict[str, Any]:
        """
        Release a lock held by an agent on a component.

        Args:
            collaboration_session_id: Session ID
            agent_id: Agent holding lock
            component_id: Component to unlock

        Returns:
            Release result
        """
        participant = self.db.query(CanvasAgentParticipant).filter(
            and_(
                CanvasAgentParticipant.collaboration_session_id == collaboration_session_id,
                CanvasAgentParticipant.agent_id == agent_id
            )
        ).first()

        if not participant:
            return {
                "error": f"Agent '{agent_id}' not found in session"
            }

        if participant.held_locks and component_id in participant.held_locks:
            participant.held_locks.remove(component_id)
            # Mark JSON field as modified for SQLAlchemy
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(participant, 'held_locks')
            self.db.commit()
            self.db.refresh(participant)

            logger.info(
                f"Released lock on {component_id} by agent {agent_id} "
                f"in session {collaboration_session_id}"
            )

            return {
                "agent_id": agent_id,
                "component_id": component_id,
                "status": "released"
            }

        return {
            "error": f"Agent {agent_id} does not hold lock for {component_id}"
        }

    # ========================================================================
    # Session Completion
    # ========================================================================

    def complete_session(
        self,
        collaboration_session_id: str
    ) -> Dict[str, Any]:
        """
        Complete a collaboration session.

        Args:
            collaboration_session_id: Session to complete

        Returns:
            Completion summary
        """
        session = self.db.query(CanvasCollaborationSession).filter(
            CanvasCollaborationSession.id == collaboration_session_id
        ).first()

        if not session:
            return {
                "error": f"Collaboration session '{collaboration_session_id}' not found"
            }

        # Mark all active participants as completed
        self.db.query(CanvasAgentParticipant).filter(
            and_(
                CanvasAgentParticipant.collaboration_session_id == collaboration_session_id,
                CanvasAgentParticipant.status == "active"
            )
        ).update({
            "status": "completed",
            "left_at": datetime.now()
        })

        # Mark session as completed
        session.status = "completed"
        session.completed_at = datetime.now()
        self.db.commit()

        # Get summary
        participants = self.db.query(CanvasAgentParticipant).filter(
            CanvasAgentParticipant.collaboration_session_id == collaboration_session_id
        ).all()

        # Get conflicts
        conflicts = self.db.query(CanvasConflict).filter(
            CanvasConflict.collaboration_session_id == collaboration_session_id
        ).count()

        logger.info(f"Completed collaboration session {collaboration_session_id}")

        return {
            "session_id": collaboration_session_id,
            "status": "completed",
            "completed_at": session.completed_at.isoformat(),
            "total_participants": len(participants),
            "total_actions": sum(p.actions_count for p in participants),
            "total_conflicts": conflicts
        }

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    def _get_default_permissions(self, role: str) -> Dict[str, Any]:
        """Get default permissions for a role."""
        if role == "owner":
            return {
                "read": True,
                "write": True,
                "delete": True,
                "lock": True
            }
        elif role == "contributor":
            return {
                "read": True,
                "write": True,
                "delete": False,
                "lock": False
            }
        elif role == "reviewer":
            return {
                "read": True,
                "suggest": True,
                "write": False,
                "delete": False
            }
        else:  # viewer
            return {
                "read": True
            }

    def _release_all_locks(self, participant: CanvasAgentParticipant):
        """Release all locks held by a participant."""
        participant.held_locks = []
        self.db.commit()

    def _merge_actions(self, action_a: Dict[str, Any], action_b: Dict[str, Any]) -> Dict[str, Any]:
        """Attempt to merge two conflicting actions."""
        # For now, prefer action_a
        # In production, implement smart merging based on action type
        return action_a
