"""
Canvas Context Service - Persists canvas state for agent learning and memory.

Canvas context captures the state of user interactions within a canvas session,
providing rich contextual data for agent learning and continuity across sessions.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import logging
import uuid
from sqlalchemy.orm import Session

from core.models import CanvasContext, AgentFeedback, FeedbackStatus

logger = logging.getLogger(__name__)


class CanvasContextService:
    """Manages canvas context for agent learning and memory."""

    def __init__(self, db: Session, tenant_id: Optional[str] = None):
        """
        Initialize the CanvasContextService.

        Args:
            db: Database session
            tenant_id: Optional tenant ID for multi-tenant filtering
        """
        self.db = db
        self.tenant_id = tenant_id
    
    def create_context(
        self,
        canvas_id: str,
        canvas_type: str,
        user_id: str,
        agent_id: Optional[str] = None,
        initial_state: Optional[dict] = None
    ) -> CanvasContext:
        """Create a new canvas context."""
        context = CanvasContext(
            canvas_id=canvas_id,
            tenant_id=self.tenant_id,
            canvas_type=canvas_type,
            user_id=user_id,
            agent_id=agent_id,
            current_state=initial_state or {}
        )

        self.db.add(context)
        self.db.commit()
        self.db.refresh(context)

        return context
    
    def get_context(
        self,
        canvas_id: str,
        user_id: str
    ) -> Optional[CanvasContext]:
        """Get existing context for a canvas."""
        query = self.db.query(CanvasContext).filter(
            CanvasContext.canvas_id == canvas_id,
            CanvasContext.user_id == user_id
        )
        if self.tenant_id:
            query = query.filter(CanvasContext.tenant_id == self.tenant_id)
        
        return query.first()
    
    def get_or_create_context(
        self,
        canvas_id: str,
        canvas_type: str,
        user_id: str,
        agent_id: Optional[str] = None
    ) -> CanvasContext:
        """Get existing context or create new one."""
        context = self.get_context(canvas_id, user_id)
        
        if not context:
            context = self.create_context(
                canvas_id=canvas_id,
                canvas_type=canvas_type,
                user_id=user_id,
                agent_id=agent_id
            )
        
        return context
    
    def update_state(
        self,
        canvas_id: str,
        user_id: str,
        state_update: dict
    ) -> bool:
        """Update current canvas state."""
        context = self.get_context(canvas_id, user_id)
        
        if not context:
            return False
        
        # Merge state update
        context.current_state = {**(context.current_state or {}), **state_update}
        context.last_activity_at = datetime.now(timezone.utc)
        
        self.db.commit()
        return True
    
    def add_action_to_history(
        self,
        canvas_id: str,
        user_id: str,
        action: dict
    ) -> bool:
        """Add an action to session history."""
        context = self.get_context(canvas_id, user_id)
        
        if not context:
            return False
        
        history = list(context.session_history or [])
        history.append({
            **action,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        context.session_history = history
        context.last_activity_at = datetime.now(timezone.utc)
        
        self.db.commit()
        return True
    
    def record_user_correction(
        self,
        canvas_id: str,
        user_id: str,
        original_action: dict,
        corrected_action: dict,
        context_info: Optional[str] = None
    ) -> bool:
        """
        Record a user correction for agent learning.
        """
        context = self.get_context(canvas_id, user_id)

        if not context:
            return False

        correction_data = {
            "original": original_action,
            "corrected": corrected_action,
            "context": context_info,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        corrections = list(context.user_corrections or [])
        corrections.append(correction_data)

        context.user_corrections = corrections
        context.last_activity_at = datetime.now(timezone.utc)

        self.db.commit()

        # Send to learning service for RLHF
        try:
            from core.agent_learning_enhanced import AgentLearningEnhanced

            # Extract agent_id from context if available
            agent_id = context.agent_id

            if agent_id:
                learning = AgentLearningEnhanced(self.db)

                # Create feedback record for the correction
                feedback = AgentFeedback(
                    agent_id=agent_id,
                    user_id=user_id,
                    tenant_id=self.tenant_id,
                    original_output=str(original_action),
                    user_correction=str(corrected_action),
                    input_context=str(context_info or ""),
                    feedback_type='correction',
                    status=FeedbackStatus.PENDING.value if hasattr(FeedbackStatus, 'PENDING') else "pending",
                    created_at=datetime.now(timezone.utc)
                )

                self.db.add(feedback)
                self.db.commit()

                logger.info(f"[LEARNING] Recorded user correction for agent {agent_id}")

        except Exception as e:
            logger.warning(f"[LEARNING] Failed to record user correction: {e}")

        return True
    
    def get_context_snapshot(
        self,
        canvas_id: str,
        user_id: str
    ) -> dict:
        """
        Get complete context snapshot for agent memory.
        """
        context = self.get_context(canvas_id, user_id)

        if not context:
            return {}

        return {
            "canvas_id": context.canvas_id,
            "canvas_type": context.canvas_type,
            "current_state": context.current_state,
            "recent_actions": (context.session_history or [])[-10:],  # Last 10 actions
            "user_preferences": context.user_preferences,
            "corrections_summary": self._summarize_corrections(context.user_corrections),
            "last_activity": context.last_activity_at.isoformat() if context.last_activity_at else None
        }
    
    def _summarize_corrections(self, corrections: Optional[List[dict]]) -> dict:
        """
        Summarize user corrections into actionable patterns.
        """
        if not corrections:
            return {}

        summary = {
            "total_corrections": len(corrections),
            "common_patterns": []
        }

        pattern_counts = {}
        for correction in corrections:
            orig = correction.get('original', {})
            action = orig.get('action_type', 'unknown') if isinstance(orig, dict) else 'unknown'
            pattern_counts[action] = pattern_counts.get(action, 0) + 1

        summary['common_patterns'] = [
            {'action_type': action, 'count': count}
            for action, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        return summary
    
    def reset_context(
        self,
        canvas_id: str,
        user_id: str
    ) -> bool:
        """
        Reset canvas context - user-initiated fresh start.
        """
        context = self.get_context(canvas_id, user_id)
        
        if not context:
            return False
        
        # Clear all session data
        context.session_history = []
        context.user_corrections = []
        context.current_state = {}
        context.user_preferences = {}
        context.last_activity_at = datetime.now(timezone.utc)
        
        self.db.commit()
        return True
