"""
Governance Wrapper for Service Layer

Provides decorators and utilities to integrate agent governance checks
into service layer functions. This ensures all AI-agent actions are
properly authorized based on agent maturity levels.

Usage:
    from core.governance_wrapper import require_governance

    @require_governance("accounting_transaction_create", "INTERN", "transaction")
    async def create_transaction(self, agent_id: str, amount: float, ...):
        # Function only executes if governance check passes
        pass
"""

import functools
import logging
from typing import Any, Callable, Dict, List, Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class GovernanceDeniedError(HTTPException):
    """
    Exception raised when governance check fails.

    Attributes:
        message: Human-readable error message
        maturity_level: Agent's current maturity level
        required_maturity: Required maturity level for the action
        reason: Detailed reason for denial
    """

    def __init__(
        self,
        message: str,
        maturity_level: Optional[str] = None,
        required_maturity: Optional[str] = None,
        reason: Optional[str] = None
    ):
        super().__init__(status_code=403, detail=message)
        self.maturity_level = maturity_level
        self.required_maturity = required_maturity
        self.reason = reason


class GovernableAction:
    """
    Registry of governable actions with their maturity requirements.

    Maps action types to required maturity levels and resource types.
    """

    # Accounting actions
    ACCOUNTING_READ = ("accounting_read", "STUDENT", "transaction")
    ACCOUNTING_WRITE = ("accounting_write", "INTERN", "transaction")
    ACCOUNTING_SUBMIT = ("accounting_submit", "SUPERVISED", "transaction")
    ACCOUNTING_DELETE = ("accounting_delete", "AUTONOMOUS", "transaction")
    ACCOUNTING_PAYMENT = ("accounting_payment", "AUTONOMOUS", "payment")

    # Integration actions
    INTEGRATION_READ = ("integration_read", "STUDENT", "message")
    INTEGRATION_POST = ("integration_post", "SUPERVISED", "message")
    INTEGRATION_DELETE = ("integration_delete", "AUTONOMOUS", "message")
    INTEGRATION_WEBHOOK = ("integration_webhook", "INTERN", "webhook")

    # Canvas actions
    CANVAS_READ = ("canvas_read", "STUDENT", "canvas")
    CANVAS_PRESENT = ("canvas_present", "INTERN", "canvas")
    CANVAS_SUBMIT = ("canvas_submit", "SUPERVISED", "form")
    CANVAS_DELETE = ("canvas_delete", "AUTONOMOUS", "canvas")

    # Browser actions
    BROWSER_READ = ("browser_read", "INTERN", "page")
    BROWSER_INTERACT = ("browser_interact", "INTERN", "page")
    BROWSER_SUBMIT = ("browser_submit", "SUPERVISED", "form")
    BROWSER_AUTOMATE = ("browser_automate", "AUTONOMOUS", "workflow")

    # Device actions
    DEVICE_CAMERA = ("device_camera", "INTERN", "device")
    DEVICE_SCREEN_RECORD = ("device_screen_record", "SUPERVISED", "device")
    DEVICE_LOCATION = ("device_location", "INTERN", "device")
    DEVICE_NOTIFICATION = ("device_notification", "INTERN", "device")
    DEVICE_COMMAND = ("device_command", "AUTONOMOUS", "device")


def require_governance(
    action_type: str,
    minimum_maturity: str = "INTERN",
    resource_type: Optional[str] = None,
    allow_non_agent: bool = True
):
    """
    Decorator to require governance check for service functions.

    Args:
        action_type: Type of action (e.g., "accounting_transaction_create")
        minimum_maturity: Minimum maturity level required (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
        resource_type: Type of resource being accessed (optional, for logging)
        allow_non_agent: If True, allow function to proceed without agent_id (for non-agent calls)

    Raises:
        GovernanceDeniedError: If governance check fails

    Example:
        @require_governance("accounting_transaction_create", "INTERN", "transaction")
        async def create_transaction(self, agent_id: str, amount: float, ...):
            # Function only executes if agent has INTERN+ maturity
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract agent_id from kwargs
            agent_id = kwargs.get('agent_id')

            # If no agent_id and allow_non_agent, proceed without governance
            if not agent_id:
                if allow_non_agent:
                    return await func(*args, **kwargs)
                else:
                    raise GovernanceDeniedError(
                        message="This operation requires an agent context",
                        reason="No agent_id provided"
                    )

            # Perform governance check
            governance_result = _check_governance(
                agent_id=agent_id,
                action_type=action_type,
                minimum_maturity=minimum_maturity,
                resource_type=resource_type
            )

            # Check if allowed
            if not governance_result.get("allowed", False):
                agent_maturity = governance_result.get("agent_maturity", "UNKNOWN")
                reason = governance_result.get("reason", "Insufficient maturity level")

                logger.warning(
                    f"Governance denied: agent={agent_id}, "
                    f"action={action_type}, maturity={agent_maturity}, "
                    f"required={minimum_maturity}, reason={reason}"
                )

                raise GovernanceDeniedError(
                    message=f"Agent {agent_id} (maturity: {agent_maturity}) is not authorized to perform action: {action_type}",
                    maturity_level=agent_maturity,
                    required_maturity=minimum_maturity,
                    reason=reason
                )

            # Governance check passed, execute function
            logger.info(
                f"Governance allowed: agent={agent_id}, action={action_type}, "
                f"maturity={governance_result.get('agent_maturity')}"
            )

            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Same logic for synchronous functions
            agent_id = kwargs.get('agent_id')

            if not agent_id:
                if allow_non_agent:
                    return func(*args, **kwargs)
                else:
                    raise GovernanceDeniedError(
                        message="This operation requires an agent context",
                        reason="No agent_id provided"
                    )

            governance_result = _check_governance(
                agent_id=agent_id,
                action_type=action_type,
                minimum_maturity=minimum_maturity,
                resource_type=resource_type
            )

            if not governance_result.get("allowed", False):
                agent_maturity = governance_result.get("agent_maturity", "UNKNOWN")
                reason = governance_result.get("reason", "Insufficient maturity level")

                logger.warning(
                    f"Governance denied: agent={agent_id}, "
                    f"action={action_type}, maturity={agent_maturity}, "
                    f"required={minimum_maturity}"
                )

                raise GovernanceDeniedError(
                    message=f"Agent {agent_id} (maturity: {agent_maturity}) is not authorized to perform action: {action_type}",
                    maturity_level=agent_maturity,
                    required_maturity=minimum_maturity,
                    reason=reason
                )

            logger.info(
                f"Governance allowed: agent={agent_id}, action={action_type}, "
                f"maturity={governance_result.get('agent_maturity')}"
            )

            return func(*args, **kwargs)

        # Return appropriate wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def _check_governance(
    agent_id: str,
    action_type: str,
    minimum_maturity: str,
    resource_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Perform governance check for an agent action.

    Args:
        agent_id: Agent ID
        action_type: Type of action
        minimum_maturity: Minimum maturity required
        resource_type: Type of resource

    Returns:
        Governance result dict with keys:
        - allowed: bool
        - agent_maturity: str
        - reason: Optional[str]
    """
    try:
        # Import here to avoid circular dependencies
        from core.agent_governance_service import AgentGovernanceService
        from core.database import get_db_session
        from core.governance_cache import GovernanceCache
        from core.models import AgentRegistry

        # Try cache first for performance
        cache = GovernanceCache()

        # Get agent from cache or database
        with get_db_session() as db:
            agent = db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            if not agent:
                return {
                    "allowed": False,
                    "agent_maturity": None,
                    "reason": f"Agent {agent_id} not found"
                }

            agent_maturity = agent.maturity_level

            # Check maturity level (STUDENT < INTERN < SUPERVISED < AUTONOMOUS)
            maturity_hierarchy = {
                "STUDENT": 1,
                "INTERN": 2,
                "SUPERVISED": 3,
                "AUTONOMOUS": 4
            }

            agent_level = maturity_hierarchy.get(agent_maturity, 0)
            required_level = maturity_hierarchy.get(minimum_maturity, 2)

            if agent_level >= required_level:
                # Check cache for governance result
                cache_key = f"governance:{agent_id}:{action_type}"
                cached_result = cache.get(cache_key)

                if cached_result:
                    return cached_result

                # Perform full governance check
                governance_service = AgentGovernanceService()
                governance_result = governance_service.check_agent_permission(
                    agent_id=agent_id,
                    action_type=action_type,
                    resource_type=resource_type
                )

                # Cache the result
                cache.set(cache_key, governance_result, ttl=60)

                return {
                    "allowed": governance_result.allowed,
                    "agent_maturity": agent_maturity,
                    "reason": governance_result.reason if not governance_result.allowed else None
                }
            else:
                return {
                    "allowed": False,
                    "agent_maturity": agent_maturity,
                    "reason": f"Agent maturity {agent_maturity} < required {minimum_maturity}"
                }

    except Exception as e:
        logger.error(f"Error performing governance check: {e}")

        # Fail closed for security
        return {
            "allowed": False,
            "agent_maturity": None,
            "reason": f"Governance check error: {str(e)}"
        }


# Import asyncio at module level
import asyncio


class GovernanceAudit:
    """
    Audit log for governance checks.

    Tracks all governance decisions for compliance and debugging.
    """

    @staticmethod
    def log_governance_check(
        agent_id: str,
        action_type: str,
        allowed: bool,
        agent_maturity: str,
        required_maturity: str,
        reason: Optional[str] = None
    ):
        """Log a governance check to the database"""
        try:
            from core.database import get_db_session
            from core.models import GovernanceAuditLog

            with get_db_session() as db:
                log = GovernanceAuditLog(
                    agent_id=agent_id,
                    action_type=action_type,
                    allowed=allowed,
                    agent_maturity=agent_maturity,
                    required_maturity=required_maturity,
                    reason=reason
                )
                db.add(log)
                db.commit()

        except Exception as e:
            logger.error(f"Failed to log governance check: {e}")
