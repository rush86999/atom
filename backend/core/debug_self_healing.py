"""
Self-Healing Integration for AI Debug System

Provides autonomous issue resolution with governance validation:
- Automated resolution suggestions
- Governance validation for auto-fixes
- Audit trail for autonomous actions
- Success rate tracking and learning

Example:
    healer = DebugSelfHealer(db_session, governance_service)

    # Attempt auto-healing
    result = await healer.attempt_auto_heal(
        issue_id="issue-123",
        issue_type="high_error_rate",
        suggestion="Scale up resources"
    )
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from core.models import (
    DebugEvent,
    DebugInsight,
    DebugInsightSeverity,
    DebugEventType,
)
from core.agent_governance_service import AgentGovernanceService
from core.structured_logger import StructuredLogger


class SelfHealingAction:
    """Self-healing action types."""

    SCALE_RESOURCES = "scale_resources"
    RESTART_COMPONENT = "restart_component"
    CLEAR_CACHE = "clear_cache"
    ADJUST_TIMEOUT = "adjust_timeout"
    RETRY_OPERATION = "retry_operation"
    ISOLATE_COMPONENT = "isolate_component"


class DebugSelfHealer:
    """
    Self-healing engine for autonomous issue resolution.

    Attempts to automatically resolve issues based on insights and
    historical solutions, with full governance validation.
    """

    def __init__(
        self,
        db_session: Session,
        governance_service: Optional[AgentGovernanceService] = None,
        require_approval: bool = True,
    ):
        """
        Initialize self-healing engine.

        Args:
            db_session: SQLAlchemy database session
            governance_service: Governance service for validation
            require_approval: Whether human approval is required
        """
        self.logger = StructuredLogger(__name__)
        self.db = db_session
        self.governance = governance_service
        self.require_approval = require_approval

    async def attempt_auto_heal(
        self,
        insight_id: str,
        suggestion_text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Attempt to automatically resolve an issue based on insight.

        Args:
            insight_id: Insight ID to resolve
            suggestion_text: Suggested resolution
            context: Additional context

        Returns:
            Healing result with status and details
        """
        try:
            # Get insight
            insight = (
                self.db.query(DebugInsight)
                .filter(DebugInsight.id == insight_id)
                .first()
            )

            if not insight:
                return {
                    "status": "not_found",
                    "message": f"Insight {insight_id} not found",
                }

            # Check if auto-healing is allowed for this severity
            if insight.severity == DebugInsightSeverity.CRITICAL.value and self.require_approval:
                return {
                    "status": "requires_approval",
                    "message": "Critical issues require human approval for auto-healing",
                    "insight_id": insight_id,
                }

            # Determine action type based on suggestion
            action_type = self._determine_action_type(suggestion_text, insight)

            if not action_type:
                return {
                    "status": "unsupported_action",
                    "message": f"Auto-healing not supported for: {suggestion_text}",
                    "insight_id": insight_id,
                }

            # Governance check
            if self.governance:
                approved = await self._check_governance(
                    action_type,
                    insight,
                    context,
                )

                if not approved["allowed"]:
                    return {
                        "status": "governance_rejected",
                        "message": approved["reason"],
                        "governance_check": approved,
                        "insight_id": insight_id,
                    }

            # Execute action
            result = await self._execute_action(
                action_type,
                insight,
                context,
            )

            # Record action in audit log
            await self._record_action(
                insight_id,
                action_type,
                suggestion_text,
                result,
            )

            return result

        except Exception as e:
            self.logger.error(
                "Failed to attempt auto-heal",
                insight_id=insight_id,
                error=str(e),
            )
            return {
                "status": "error",
                "message": str(e),
                "insight_id": insight_id,
            }

    async def get_auto_heal_suggestions(
        self,
        insight_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get auto-healing suggestions for an insight.

        Args:
            insight_id: Insight ID

        Returns:
            List of suggested actions with probability of success
        """
        try:
            insight = (
                self.db.query(DebugInsight)
                .filter(DebugInsight.id == insight_id)
                .first()
            )

            if not insight or not insight.suggestions:
                return []

            suggestions = []

            # Analyze each suggestion
            for suggestion_text in insight.suggestions:
                action_type = self._determine_action_type(suggestion_text, insight)
                if action_type:
                    # Get historical success rate for this action
                    success_rate = await self._get_historical_success_rate(
                        action_type,
                        insight.insight_type,
                    )

                    suggestions.append({
                        "action_type": action_type,
                        "suggestion": suggestion_text,
                        "estimated_duration_minutes": self._estimate_duration(action_type),
                        "success_probability": success_rate,
                        "risk_level": self._assess_risk(action_type, insight),
                    })

            # Sort by success probability (descending)
            suggestions.sort(key=lambda x: x["success_probability"], reverse=True)

            return suggestions

        except Exception as e:
            self.logger.error(
                "Failed to get auto-heal suggestions",
                insight_id=insight_id,
                error=str(e),
            )
            return []

    async def execute_healing_action(
        self,
        action_type: str,
        target_component: Dict[str, str],
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a healing action.

        Args:
            action_type: Type of action to execute
            target_component: Component to act on
            parameters: Action parameters

        Returns:
            Execution result
        """
        try:
            # Record action start
            event = DebugEvent(
                id=str(uuid.uuid4()),
                event_type=DebugEventType.SYSTEM.value,
                component_type="debug_self_healer",
                component_id="system",
                correlation_id=str(uuid.uuid4()),
                level="INFO",
                message=f"Executing self-healing action: {action_type}",
                data={
                    "action_type": action_type,
                    "target_component": target_component,
                    "parameters": parameters or {},
                },
            )
            self.db.add(event)
            self.db.commit()

            # Execute the action
            result = await self._perform_action(action_type, target_component, parameters)

            return {
                "status": "success" if result["success"] else "failed",
                "action_type": action_type,
                "target_component": target_component,
                "result": result,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            self.logger.error(
                "Failed to execute healing action",
                action_type=action_type,
                target_component=target_component,
                error=str(e),
            )
            return {
                "status": "error",
                "action_type": action_type,
                "error": str(e),
            }

    async def get_healing_history(
        self,
        limit: int = 50,
        time_range: str = "last_7d",
    ) -> List[Dict[str, Any]]:
        """
        Get history of self-healing actions.

        Args:
            limit: Maximum results
            time_range: Time range for history

        Returns:
            List of healing actions
        """
        try:
            time_filter = self._parse_time_range(time_range)

            # Get self-healing events
            events = (
                self.db.query(DebugEvent)
                .filter(
                    and_(
                        DebugEvent.component_type == "debug_self_healer",
                        DebugEvent.timestamp >= time_filter,
                    )
                )
                .order_by(DebugEvent.timestamp.desc())
                .limit(limit)
                .all()
            )

            history = []
            for event in events:
                if event.data and "action_type" in event.data:
                    history.append({
                        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                        "action_type": event.data["action_type"],
                        "target_component": event.data.get("target_component"),
                        "parameters": event.data.get("parameters"),
                        "message": event.message,
                        "level": event.level,
                    })

            return history

        except Exception as e:
            self.logger.error("Failed to get healing history", error=str(e))
            return []

    def _determine_action_type(
        self,
        suggestion_text: str,
        insight: DebugInsight,
    ) -> Optional[str]:
        """Determine action type from suggestion text."""
        suggestion_lower = suggestion_text.lower()

        if "scale" in suggestion_lower and ("resource" in suggestion_lower or "up" in suggestion_lower):
            return SelfHealingAction.SCALE_RESOURCES
        elif "restart" in suggestion_lower:
            return SelfHealingAction.RESTART_COMPONENT
        elif "cache" in suggestion_lower and ("clear" in suggestion_lower or "flush" in suggestion_lower):
            return SelfHealingAction.CLEAR_CACHE
        elif "timeout" in suggestion_lower and ("increase" in suggestion_lower or "adjust" in suggestion_lower):
            return SelfHealingAction.ADJUST_TIMEOUT
        elif "retry" in suggestion_lower:
            return SelfHealingAction.RETRY_OPERATION
        elif "isolate" in suggestion_lower:
            return SelfHealingAction.ISOLATE_COMPONENT

        return None

    async def _check_governance(
        self,
        action_type: str,
        insight: DebugInsight,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Check if action is allowed by governance.

        Args:
            action_type: Type of action
            insight: Associated insight
            context: Additional context

        Returns:
            Governance check result
        """
        if not self.governance:
            return {"allowed": True, "reason": "No governance service configured"}

        try:
            # Check based on action severity and action type
            if insight.severity == DebugInsightSeverity.CRITICAL.value:
                if action_type in [SelfHealingAction.RESTART_COMPONENT, SelfHealingAction.ISOLATE_COMPONENT]:
                    return {
                        "allowed": False,
                        "reason": "Critical severity requires human approval for restart/isolate actions",
                    }

            if insight.severity == DebugInsightSeverity.WARNING.value:
                if action_type == SelfHealingAction.RESTART_COMPONENT:
                    return {
                        "allowed": False,
                        "reason": "Restart requires human approval for warning severity",
                    }

            # Check action type restrictions
            if action_type == SelfHealingAction.ISOLATE_COMPONENT:
                return {
                    "allowed": False,
                    "reason": "Component isolation requires manual intervention",
                }

            # Check confidence score
            if insight.confidence_score < 0.8:
                return {
                    "allowed": False,
                    "reason": f"Insight confidence {insight.confidence_score:.2f} below 0.8 threshold",
                }

            return {
                "allowed": True,
                "reason": "Action approved by governance",
            }

        except Exception as e:
            self.logger.error("Governance check failed", error=str(e))
            return {
                "allowed": False,
                "reason": f"Governance check error: {str(e)}",
            }

    async def _execute_action(
        self,
        action_type: str,
        insight: DebugInsight,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute the healing action."""
        # This is a placeholder - actual implementation would integrate with
        # infrastructure automation tools (Kubernetes, service mesh, etc.)
        return {
            "status": "success",
            "success": True,
            "message": f"Action {action_type} would be executed here",
            "action_type": action_type,
        }

    async def _perform_action(
        self,
        action_type: str,
        target_component: Dict[str, str],
        parameters: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Perform a healing action on a component."""
        # This is a placeholder - actual implementation would:
        # - Scale up/down pods in Kubernetes
        # - Restart services via service mesh
        # - Clear Redis/Memcached caches
        # - Update configuration files
        # - Retry operations with backoff

        # For testing, return success
        return {
            "success": True,
            "status": "success",
            "message": f"Action {action_type} executed on {target_component}",
            "action_type": action_type,
        }

    async def _record_action(
        self,
        insight_id: str,
        action_type: str,
        suggestion: str,
        result: Dict[str, Any],
    ):
        """Record self-healing action in audit log."""
        event = DebugEvent(
            id=str(uuid.uuid4()),
            event_type=DebugEventType.SYSTEM.value,
            component_type="debug_self_healer",
            component_id="system",
            correlation_id=insight_id,
            level="INFO" if result["status"] == "success" else "ERROR",
            message=f"Self-healing action {action_type}: {result.get('status', 'unknown')}",
            data={
                "insight_id": insight_id,
                "action_type": action_type,
                "suggestion": suggestion,
                "result": result,
            },
            timestamp=datetime.utcnow(),
        )

        self.db.add(event)
        self.db.commit()

    async def _get_historical_success_rate(
        self,
        action_type: str,
        insight_type: str,
    ) -> float:
        """Get historical success rate for an action."""
        # Placeholder - would query actual historical data
        # Return 0.7 (70%) as default success rate
        return 0.7

    def _estimate_duration(self, action_type: str) -> int:
        """Estimate action duration in minutes."""
        durations = {
            SelfHealingAction.SCALE_RESOURCES: 5,
            SelfHealingAction.RESTART_COMPONENT: 2,
            SelfHealingAction.CLEAR_CACHE: 1,
            SelfHealingAction.ADJUST_TIMEOUT: 1,
            SelfHealingAction.RETRY_OPERATION: 2,
            SelfHealingAction.ISOLATE_COMPONENT: 10,
        }
        return durations.get(action_type, 5)

    def _assess_risk(self, action_type: str, insight: DebugInsight) -> str:
        """Assess risk level of an action."""
        if action_type in [SelfHealingAction.RESTART_COMPONENT, SelfHealingAction.ISOLATE_COMPONENT]:
            return "high"
        elif action_type == SelfHealingAction.SCALE_RESOURCES:
            return "medium"
        else:
            return "low"

    def _parse_time_range(self, time_range: str) -> datetime:
        """Parse time range string to datetime."""
        now = datetime.utcnow()

        if time_range == "last_1h":
            return now - timedelta(hours=1)
        elif time_range == "last_24h":
            return now - timedelta(hours=24)
        elif time_range == "last_7d":
            return now - timedelta(days=7)
        else:
            return now - timedelta(hours=1)
