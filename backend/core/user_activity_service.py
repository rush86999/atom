"""
User Activity Service

Tracks user activity state (online/away/offline) for supervision routing.
Determines if users are available to supervise INTERN and SUPERVISED agents.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from core.models import (
    User,
    UserActivity,
    UserActivitySession,
    UserState,
)

logger = logging.getLogger(__name__)

# Configuration constants
ONLINE_THRESHOLD_SECONDS = 5 * 60  # 5 minutes - online to away transition
AWAY_THRESHOLD_SECONDS = 15 * 60   # 15 minutes - away to offline transition
SESSION_HEARTBEAT_INTERVAL = 30     # 30 seconds - expected heartbeat interval
SESSION_STALE_THRESHOLD = 60 * 60  # 1 hour - stale session cleanup


class UserActivityService:
    """
    Manage user activity tracking and state transitions.

    Users can be in three states:
    - online: Active within last 5 minutes (can supervise)
    - away: Active 5-15 minutes ago (can supervise)
    - offline: No activity for 15+ minutes (cannot supervise)

    State transitions happen automatically based on activity, but can be
    manually overridden with optional expiry.
    """

    def __init__(self, db: Session):
        self.db = db

    async def record_heartbeat(
        self,
        user_id: str,
        session_token: str,
        session_type: str = "web",
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> UserActivity:
        """
        Record user activity heartbeat and update state.

        Creates or updates session record and refreshes user activity state.
        User is considered online if ANY session has recent heartbeat.

        Args:
            user_id: User sending heartbeat
            session_token: Unique session identifier
            session_type: Session type ("web" or "desktop")
            user_agent: Optional user agent string
            ip_address: Optional IP address

        Returns:
            Updated UserActivity record
        """
        # Get or create UserActivity
        activity = self.db.query(UserActivity).filter(
            UserActivity.user_id == user_id
        ).first()

        if not activity:
            activity = UserActivity(
                id=f"ua_{uuid.uuid4()}",
                user_id=user_id,
                state=UserState.offline,
                last_activity_at=datetime.utcnow()
            )
            self.db.add(activity)
            self.db.commit()
            self.db.refresh(activity)

        # Get or create UserActivitySession
        session = self.db.query(UserActivitySession).filter(
            UserActivitySession.session_token == session_token
        ).first()

        if not session:
            session = UserActivitySession(
                id=f"us_{uuid.uuid4()}",
                user_id=user_id,
                activity_id=activity.id,
                session_type=session_type,
                session_token=session_token,
                user_agent=user_agent,
                ip_address=ip_address,
                last_heartbeat=datetime.utcnow()
            )
            self.db.add(session)
        else:
            # Update existing session
            session.last_heartbeat = datetime.utcnow()
            session.terminated_at = None  # Clear termination if resuming

        self.db.commit()
        self.db.refresh(session)

        # Update activity state based on heartbeat
        await self._update_activity_state_from_heartbeat(activity)

        return activity

    async def get_user_state(self, user_id: str) -> UserState:
        """
        Get current user state (online/away/offline).

        Returns user's current availability state based on recent activity.

        Args:
            user_id: User to check

        Returns:
            UserState enum value
        """
        activity = self.db.query(UserActivity).filter(
            UserActivity.user_id == user_id
        ).first()

        if not activity:
            return UserState.offline

        # Check if manual override is active
        if activity.manual_override:
            if activity.manual_override_expires_at:
                if datetime.utcnow() < activity.manual_override_expires_at:
                    return activity.state
                else:
                    # Manual override expired, clear it
                    activity.manual_override = False
                    activity.manual_override_expires_at = None
                    self.db.commit()
            else:
                # Manual override without expiry (permanent until cleared)
                return activity.state

        # Calculate state based on actual activity
        await self._recalculate_activity_state(activity)
        return activity.state

    async def set_manual_override(
        self,
        user_id: str,
        state: UserState,
        expires_at: Optional[datetime] = None
    ) -> UserActivity:
        """
        Manually set user state with optional expiry.

        Allows users to override automatic activity tracking.
        Useful for setting "away" status while at desk, or "online" while inactive.

        Args:
            user_id: User to override
            state: State to set
            expires_at: Optional expiry time for override

        Returns:
            Updated UserActivity record
        """
        activity = self.db.query(UserActivity).filter(
            UserActivity.user_id == user_id
        ).first()

        if not activity:
            activity = UserActivity(
                id=f"ua_{uuid.uuid4()}",
                user_id=user_id,
                state=state,
                last_activity_at=datetime.utcnow(),
                manual_override=True,
                manual_override_expires_at=expires_at
            )
            self.db.add(activity)
        else:
            activity.state = state
            activity.manual_override = True
            activity.manual_override_expires_at = expires_at

        self.db.commit()
        self.db.refresh(activity)

        logger.info(
            f"Manual override set for user {user_id}: {state.value}"
            + (f" (expires {expires_at})" if expires_at else "")
        )

        return activity

    async def clear_manual_override(self, user_id: str) -> UserActivity:
        """
        Clear manual override and return to automatic activity tracking.

        Args:
            user_id: User to clear override for

        Returns:
            Updated UserActivity record
        """
        activity = self.db.query(UserActivity).filter(
            UserActivity.user_id == user_id
        ).first()

        if not activity:
            raise ValueError(f"UserActivity not found for user {user_id}")

        activity.manual_override = False
        activity.manual_override_expires_at = None

        # Recalculate state based on actual activity
        await self._recalculate_activity_state(activity)

        self.db.commit()
        self.db.refresh(activity)

        logger.info(f"Manual override cleared for user {user_id}")

        return activity

    async def get_available_supervisors(
        self,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get list of users available for supervision (online or away).

        Args:
            category: Optional category filter (not implemented yet)

        Returns:
            List of available supervisor dicts with user info
        """
        # Query users with online or away state
        available_activities = self.db.query(UserActivity).filter(
            UserActivity.state.in_([UserState.online, UserState.away])
        ).all()

        supervisors = []
        for activity in available_activities:
            user = self.db.query(User).filter(
                User.id == activity.user_id
            ).first()

            if user and user.status == "ACTIVE":
                supervisors.append({
                    "user_id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "state": activity.state.value,
                    "last_activity_at": activity.last_activity_at.isoformat(),
                    "specialty": user.specialty
                })

        return supervisors

    def should_supervise(self, user_activity: UserActivity) -> bool:
        """
        Check if user is available to supervise (online or away).

        Args:
            user_activity: UserActivity record to check

        Returns:
            True if user can supervise, False otherwise
        """
        return user_activity.state in [UserState.online, UserState.away]

    async def get_active_sessions(
        self,
        user_id: str
    ) -> List[UserActivitySession]:
        """
        Get all active (non-terminated) sessions for a user.

        Args:
            user_id: User to get sessions for

        Returns:
            List of active UserActivitySession records
        """
        sessions = self.db.query(UserActivitySession).filter(
            UserActivitySession.user_id == user_id,
            UserActivitySession.terminated_at.is_(None)
        ).all()

        return sessions

    async def terminate_session(
        self,
        session_token: str
    ) -> bool:
        """
        Terminate a specific session (e.g., user logout).

        Args:
            session_token: Session token to terminate

        Returns:
            True if session was terminated, False if not found
        """
        session = self.db.query(UserActivitySession).filter(
            UserActivitySession.session_token == session_token
        ).first()

        if not session:
            return False

        session.terminated_at = datetime.utcnow()
        self.db.commit()

        # Recalculate activity state for user
        activity = self.db.query(UserActivity).filter(
            UserActivity.id == session.activity_id
        ).first()

        if activity:
            await self._recalculate_activity_state(activity)

        return True

    # ========================================================================
    # State Management Helpers
    # ========================================================================

    async def _update_activity_state_from_heartbeat(
        self,
        activity: UserActivity
    ) -> None:
        """Update activity state after receiving heartbeat."""
        # Skip if manual override is active
        if activity.manual_override:
            return

        # Update last activity time
        activity.last_activity_at = datetime.utcnow()

        # Set to online (heartbeat means user is actively using the system)
        if activity.state != UserState.online:
            old_state = activity.state
            activity.state = UserState.online
            logger.info(
                f"User {activity.user_id} state: {old_state} → online "
                f"(heartbeat received)"
            )

        self.db.commit()

    async def _recalculate_activity_state(
        self,
        activity: UserActivity
    ) -> None:
        """
        Recalculate activity state based on actual session activity.

        Called when manual override is cleared or periodic state transitions.
        """
        # Skip if manual override is active
        if activity.manual_override:
            return

        # Check if user has any active sessions with recent heartbeat
        now = datetime.utcnow()
        active_sessions = self.db.query(UserActivitySession).filter(
            UserActivitySession.activity_id == activity.id,
            UserActivitySession.terminated_at.is_(None)
        ).all()

        if not active_sessions:
            # No active sessions, user is offline
            if activity.state != UserState.offline:
                old_state = activity.state
                activity.state = UserState.offline
                logger.info(
                    f"User {activity.user_id} state: {old_state} → offline "
                    f"(no active sessions)"
                )
            self.db.commit()
            return

        # Find most recent heartbeat across all sessions
        most_recent_heartbeat = max(
            (s.last_heartbeat for s in active_sessions),
            default=activity.last_activity_at
        )

        # Calculate time since last activity
        time_since_activity = (now - most_recent_heartbeat).total_seconds()

        # Determine state based on thresholds
        old_state = activity.state
        new_state = old_state

        if time_since_activity < ONLINE_THRESHOLD_SECONDS:
            new_state = UserState.online
        elif time_since_activity < AWAY_THRESHOLD_SECONDS:
            new_state = UserState.away
        else:
            new_state = UserState.offline

        if new_state != old_state:
            logger.info(
                f"User {activity.user_id} state: {old_state} → {new_state} "
                f"(inactive for {int(time_since_activity)}s)"
            )
            activity.state = new_state

        self.db.commit()

    async def transition_state_batch(
        self,
        limit: int = 100
    ) -> Dict[str, int]:
        """
        Process state transitions for a batch of users.

        Called by background worker to check for state transitions.

        Args:
            limit: Maximum number of users to process

        Returns:
            Dict with transition counts
        """
        # Get all activities that need state recalculation
        # (no manual override, updated more than 1 minute ago)
        cutoff_time = datetime.utcnow() - timedelta(minutes=1)

        activities = self.db.query(UserActivity).filter(
            UserActivity.manual_override == False,
            UserActivity.updated_at < cutoff_time
        ).limit(limit).all()

        transitions = {
            "online_to_away": 0,
            "away_to_offline": 0,
            "offline_to_online": 0,
            "away_to_online": 0,
            "online_to_offline": 0,
            "total_processed": 0
        }

        for activity in activities:
            old_state = activity.state
            await self._recalculate_activity_state(activity)
            new_state = activity.state

            if old_state != new_state:
                transition_key = f"{old_state}_to_{new_state}"
                if transition_key in transitions:
                    transitions[transition_key] += 1

            transitions["total_processed"] += 1

        logger.info(
            f"State transition batch processed: {transitions['total_processed']} users, "
            f"{sum(v for k, v in transitions.items() if k != 'total_processed')} transitions"
        )

        return transitions

    async def cleanup_stale_sessions(
        self,
        limit: int = 50
    ) -> int:
        """
        Clean up stale sessions (no heartbeat for >1 hour).

        Args:
            limit: Maximum number of sessions to clean up

        Returns:
            Number of sessions cleaned up
        """
        cutoff_time = datetime.utcnow() - timedelta(seconds=SESSION_STALE_THRESHOLD)

        stale_sessions = self.db.query(UserActivitySession).filter(
            UserActivitySession.terminated_at.is_(None),
            UserActivitySession.last_heartbeat < cutoff_time
        ).limit(limit).all()

        count = 0
        for session in stale_sessions:
            session.terminated_at = datetime.utcnow()
            count += 1

        self.db.commit()

        if count > 0:
            logger.info(f"Cleaned up {count} stale sessions")

        return count
