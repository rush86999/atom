"""
Governance Helper Mixin for Tools

Provides standardized governance pattern enforcement across all tools.
Ensures consistent agent execution tracking, governance checks, and audit trails.

Standard Pattern:
1. Resolve agent context
2. Perform governance check
3. Create AgentExecution record
4. Execute the operation
5. Record outcome (success/failure)
6. Update AgentExecution status
"""

from datetime import datetime
from functools import wraps
import logging
from typing import Any, Awaitable, Callable, Dict, Optional
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.exceptions import AgentGovernanceError, AgentNotFoundError, InternalServerError
from core.models import AgentExecution, User

logger = logging.getLogger(__name__)


class GovernanceHelper:
    """
    Helper class for standardizing governance patterns across tools.

    Usage Example:
        helper = GovernanceHelper(db, "browser_tool")
        result = await helper.execute_with_governance(
            agent_id=agent_id,
            user_id=user_id,
            action_complexity=2,
            action_name="create_browser_session",
            action_func=lambda: _create_session(),
            action_params={"headless": True}
        )
    """

    def __init__(self, db: Session, tool_name: str):
        """
        Initialize governance helper.

        Args:
            db: Database session
            tool_name: Name of the tool using this helper
        """
        self.db = db
        self.tool_name = tool_name
        self.context_resolver = AgentContextResolver(db)
        self.governance_service = AgentGovernanceService(db)

    async def execute_with_governance(
        self,
        agent_id: Optional[str],
        user_id: str,
        action_complexity: int,
        action_name: str,
        action_func: Callable[[], Awaitable[Dict[str, Any]]] | Callable[[], Dict[str, Any]],
        action_params: Optional[Dict[str, Any]] = None,
        feature_enabled: bool = True,
        emergency_bypass: bool = False
    ) -> Dict[str, Any]:
        """
        Execute an action with full governance tracking.

        This method implements the standard governance pattern:
        1. Resolve agent context
        2. Perform governance check
        3. Create AgentExecution record
        4. Execute the operation
        5. Record outcome
        6. Handle errors

        Args:
            agent_id: Agent ID (None if user-initiated)
            user_id: User ID initiating the action
            action_complexity: Action complexity (1-4)
            action_name: Description of the action
            action_func: Function to execute (can be sync or async)
            action_params: Parameters for the action
            feature_enabled: Feature flag for governance
            emergency_bypass: Emergency bypass flag

        Returns:
            Dict containing success status and result data

        Raises:
            AgentGovernanceError: If governance check fails
            AgentNotFoundError: If agent not found
            InternalServerError: For unexpected errors
        """
        agent_execution = None
        agent = None

        try:
            # Step 1: Resolve agent context
            if agent_id:
                agent = self.context_resolver.resolve_agent(agent_id)
                if not agent:
                    raise AgentNotFoundError(agent_id)

            # Step 2: Perform governance check
            governance_result = await self._perform_governance_check(
                agent=agent,
                user_id=user_id,
                action_complexity=action_complexity,
                feature_enabled=feature_enabled,
                emergency_bypass=emergency_bypass
            )

            if not governance_result["allowed"]:
                raise AgentGovernanceError(
                    agent_id=agent_id or "system",
                    reason=governance_result.get("reason", "Governance check failed"),
                    maturity_level=getattr(agent, "maturity_level", None) if agent else None
                )

            # Step 3: Create AgentExecution record
            if agent and feature_enabled:
                agent_execution = self._create_execution_record(
                    agent_id=agent.id,
                    action_name=action_name,
                    action_params=action_params
                )

            # Step 4: Execute the operation
            logger.info(f"Executing {self.tool_name} action: {action_name}")
            start_time = datetime.now()

            # Support both sync and async functions
            import asyncio
            if asyncio.iscoroutinefunction(action_func):
                result = await action_func()
            else:
                result = action_func()

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            # Step 5: Record success outcome
            if agent and feature_enabled:
                await self.governance_service.record_outcome(
                    agent.id,
                    success=True,
                    action_complexity=action_complexity
                )

                if agent_execution:
                    self._update_execution_record(
                        execution=agent_execution,
                        status="completed",
                        output_summary=f"{action_name} completed",
                        duration_ms=duration_ms
                    )

            logger.info(f"{self.tool_name} action completed successfully: {action_name} ({duration_ms}ms)")
            return result

        except AgentGovernanceError:
            # Re-raise governance errors as-is
            if agent and agent_execution and feature_enabled:
                await self.governance_service.record_outcome(agent.id, success=False)
                self._update_execution_record(
                    execution=agent_execution,
                    status="failed",
                    error_message="Governance check failed"
                )
            raise

        except Exception as e:
            logger.error(f"{self.tool_name} action failed: {action_name} - {e}")

            # Step 6: Record failure outcome
            if agent and feature_enabled:
                try:
                    await self.governance_service.record_outcome(agent.id, success=False)

                    if agent_execution:
                        self._update_execution_record(
                            execution=agent_execution,
                            status="failed",
                            error_message=str(e)
                        )
                except Exception as inner_e:
                    logger.error(f"Failed to record execution failure: {inner_e}")

            # Return error response instead of raising
            return {
                "success": False,
                "error": str(e),
                "action": action_name,
                "tool": self.tool_name
            }

    async def _perform_governance_check(
        self,
        agent: Optional[User],
        user_id: str,
        action_complexity: int,
        feature_enabled: bool,
        emergency_bypass: bool
    ) -> Dict[str, Any]:
        """
        Perform governance check for the action.

        Args:
            agent: Agent object (None if user-initiated)
            user_id: User ID
            action_complexity: Action complexity level
            feature_enabled: Governance feature flag
            emergency_bypass: Emergency bypass flag

        Returns:
            Dict with 'allowed' boolean and optional 'reason' string
        """
        # Emergency bypass
        if emergency_bypass:
            logger.warning(f"Emergency governance bypass enabled for {self.tool_name}")
            return {"allowed": True, "reason": "Emergency bypass"}

        # User-initiated actions (no agent) are always allowed
        if not agent:
            return {"allowed": True}

        # Governance disabled by feature flag
        if not feature_enabled:
            logger.warning(f"Governance disabled for {self.tool_name}")
            return {"allowed": True, "reason": "Feature disabled"}

        # Perform governance check
        try:
            governance_check = await self.governance_service.check_agent_permission(
                agent_id=agent.id,
                action_complexity=action_complexity
            )
            return governance_check
        except Exception as e:
            logger.error(f"Governance check failed: {e}")
            # Fail closed for security
            return {
                "allowed": False,
                "reason": f"Governance check error: {str(e)}"
            }

    def _create_execution_record(
        self,
        agent_id: str,
        action_name: str,
        action_params: Optional[Dict[str, Any]]
    ) -> AgentExecution:
        """Create AgentExecution record for tracking."""
        try:
            execution = AgentExecution(
                agent_id=agent_id,
                workspace_id="default",
                status="running",
                input_summary=f"{self.tool_name}: {action_name}",
                triggered_by=self.tool_name
            )

            self.db.add(execution)
            self.db.commit()
            self.db.refresh(execution)

            return execution
        except Exception as e:
            logger.error(f"Failed to create execution record: {e}")
            # Don't fail the operation if tracking fails
            return None

    def _update_execution_record(
        self,
        execution: AgentExecution,
        status: str,
        output_summary: Optional[str] = None,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None
    ):
        """Update AgentExecution record with outcome."""
        try:
            execution.status = status
            execution.completed_at = datetime.now()

            if output_summary:
                execution.output_summary = output_summary
            elif error_message:
                execution.error_message = error_message

            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update execution record: {e}")


def with_governance(
    action_complexity: int,
    action_name: Optional[str] = None,
    feature_enabled: bool = True,
    emergency_bypass: bool = False
):
    """
    Decorator for automatic governance tracking on tool functions.

    Usage:
        @with_governance(action_complexity=2, action_name="create_session")
        async def create_browser_session(db, user_id, agent_id=None, ...):
            # Function implementation
            return {"success": True, "session_id": "..."}

    Args:
        action_complexity: Action complexity level (1-4)
        action_name: Action description (defaults to function name)
        feature_enabled: Feature flag for governance
        emergency_bypass: Emergency bypass flag
    """

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract parameters from function signature
            # Expected: db, user_id, agent_id (optional)
            db = kwargs.get('db') or args[0] if args else None
            user_id = kwargs.get('user_id') or args[1] if len(args) > 1 else None
            agent_id = kwargs.get('agent_id') or args[2] if len(args) > 2 else None

            if not db or not user_id:
                raise ValueError("Governance decorator requires 'db' and 'user_id' parameters")

            tool_name = func.__module__.split('.')[-1]
            action = action_name or func.__name__

            helper = GovernanceHelper(db, tool_name)

            return await helper.execute_with_governance(
                agent_id=agent_id,
                user_id=user_id,
                action_complexity=action_complexity,
                action_name=action,
                action_func=lambda: func(*args, **kwargs),
                feature_enabled=feature_enabled,
                emergency_bypass=emergency_bypass
            )

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we need to run in async context
            import asyncio
            return asyncio.run(async_wrapper(*args, **kwargs))

        # Return appropriate wrapper based on whether function is async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# ============================================================================
# Standard Audit Patterns
# ============================================================================

def create_audit_entry(
    db: Session,
    audit_model,
    user_id: str,
    agent_id: Optional[str],
    action_type: str,
    action_params: Dict[str, Any],
    success: bool,
    result_summary: Optional[str] = None,
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Standard pattern for creating audit entries.

    This helper creates audit records for domain-specific audit tables
    (DeviceAudit, CanvasAudit, etc.) with consistent structure.

    Args:
        db: Database session
        audit_model: The audit model class (DeviceAudit, CanvasAudit, etc.)
        user_id: User ID
        agent_id: Agent ID (optional)
        action_type: Type of action performed
        action_params: Parameters passed to the action
        success: Whether the action succeeded
        result_summary: Summary of the result
        error_message: Error message if failed
        metadata: Additional metadata

    Returns:
        Created audit record or None on error
    """
    try:
        from core.models import AgentExecution

        # Get most recent execution for this agent
        agent_execution_id = None
        if agent_id:
            execution = db.query(AgentExecution).filter(
                AgentExecution.agent_id == agent_id,
                AgentExecution.status == "running"
            ).order_by(AgentExecution.created_at.desc()).first()

            if execution:
                agent_execution_id = execution.id

        audit = audit_model(
            workspace_id="default",
            agent_id=agent_id,
            agent_execution_id=agent_execution_id,
            user_id=user_id,
            action_type=action_type,
            action_params=action_params,
            success=success,
            result_summary=result_summary,
            error_message=error_message,
            metadata_json=metadata or {}
        )

        db.add(audit)
        db.commit()

        return audit

    except Exception as e:
        logger.error(f"Failed to create audit entry: {e}")
        return None
