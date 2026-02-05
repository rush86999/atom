"""
Governance Helper Functions

Standardized helper functions for governance checks with consistent error handling.
Provides a simple interface for common permission checking operations.

Usage:
    from core.governance_helpers import check_agent_permission

    # Automatic error handling
    check_agent_permission(db, "agent123", "update_agent", complexity=3)

    # Manual handling
    if check_agent_permission(db, "agent123", "update_agent", 3, raise_on_denied=False):
        # Agent is permitted
        pass
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from core.api_governance import ActionComplexity
from core.base_routes import BaseAPIRouter
from core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)

# Global router instance for error methods
_router = BaseAPIRouter()


def check_agent_permission(
    db: Session,
    agent_id: str,
    action: str,
    complexity: int,
    raise_on_denied: bool = True
) -> bool:
    """
    Standardized permission check with consistent error handling.

    This helper function checks if an agent has permission to perform an action
    based on its maturity level and the action complexity. It provides consistent
    error messages and logging across all governance checks.

    Args:
        db: Database session
        agent_id: Agent ID to check
        action: Action name (e.g., "update_agent", "delete_resource")
        complexity: Action complexity level (1-4)
            - 1 (LOW): Read-only, presentations
            - 2 (MODERATE): Streaming, moderate actions
            - 3 (HIGH): State changes, submissions
            - 4 (CRITICAL): Deletions, payments
        raise_on_denied: If True, raise exception on denial; if False, return bool

    Returns:
        True if agent is permitted, False if denied (only when raise_on_denied=False)

    Raises:
        HTTPException: If agent not permitted and raise_on_denied=True (403 Forbidden)

    Example:
        # Automatic error handling (recommended)
        check_agent_permission(db, "agent123", "update_agent", complexity=3)

        # Manual handling
        if check_agent_permission(db, "agent123", "update_agent", 3, raise_on_denied=False):
            # Agent is permitted
            perform_update()
        else:
            # Agent is not permitted
            return {"error": "Not allowed"}
    """
    try:
        # Get governance service via factory
        governance = ServiceFactory.get_governance_service(db)

        # Check permission
        permitted = governance.can_execute_action(agent_id, complexity)

        if not permitted:
            # Get details for error message
            try:
                current_maturity = governance.get_agent_maturity(agent_id)
                required_maturity = governance.get_required_maturity(complexity)
            except Exception as e:
                logger.warning(f"Could not get maturity details: {e}")
                current_maturity = "UNKNOWN"
                required_maturity = "UNKNOWN"

            # Log denial
            logger.info(
                f"Permission denied: agent={agent_id}, action={action}, "
                f"current_maturity={current_maturity}, required_maturity={required_maturity}, "
                f"complexity={complexity}"
            )

            # Raise error if requested
            if raise_on_denied:
                raise _router.permission_denied_error(
                    action=action,
                    resource=f"agent:{agent_id}",
                    details={
                        "agent_id": agent_id,
                        "current_maturity": current_maturity,
                        "required_maturity": required_maturity,
                        "complexity": complexity
                    }
                )

            return False

        # Log permission grant
        logger.debug(
            f"Permission granted: agent={agent_id}, action={action}, complexity={complexity}"
        )

        return True

    except Exception as e:
        # If it's already an HTTPException (from permission_denied_error), re-raise
        if hasattr(e, 'status_code'):
            raise

        # Log unexpected error
        logger.error(f"Governance check failed: agent={agent_id}, action={action}, error={e}")

        # Fail securely: deny permission if check fails
        if raise_on_denied:
            raise _router.internal_error(
                message="Permission check failed",
                details={"agent_id": agent_id, "action": action}
            )

        return False


def check_agent_action(
    db: Session,
    agent_id: str,
    action: str,
    action_complexity: ActionComplexity = ActionComplexity.MODERATE,
    raise_on_denied: bool = True
) -> bool:
    """
    Check agent permission using ActionComplexity enum.

    This is a convenience wrapper around check_agent_permission that uses
    the ActionComplexity enum instead of raw integers.

    Args:
        db: Database session
        agent_id: Agent ID to check
        action: Action name (for error messages)
        action_complexity: Action complexity enum value
        raise_on_denied: If True, raise exception on denial

    Returns:
        True if permitted, False if denied

    Example:
        from core.api_governance import ActionComplexity

        check_agent_action(
            db, "agent123", "delete_resource",
            action_complexity=ActionComplexity.CRITICAL
        )
    """
    complexity_value = action_complexity.value if isinstance(action_complexity, ActionComplexity) else action_complexity
    return check_agent_permission(db, agent_id, action, complexity_value, raise_on_denied)


def get_agent_maturity(db: Session, agent_id: str) -> Optional[str]:
    """
    Get agent maturity level with error handling.

    Args:
        db: Database session
        agent_id: Agent ID to check

    Returns:
        Maturity level (e.g., "STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS")
        or None if agent not found

    Example:
        maturity = get_agent_maturity(db, "agent123")
        if maturity == "AUTONOMOUS":
            # Agent can perform any action
            pass
    """
    try:
        governance = ServiceFactory.get_governance_service(db)
        return governance.get_agent_maturity(agent_id)
    except Exception as e:
        logger.error(f"Failed to get agent maturity: agent_id={agent_id}, error={e}")
        return None


def can_agent_perform(
    db: Session,
    agent_id: str,
    complexity: int
) -> bool:
    """
    Check if agent can perform action at given complexity level.

    This is a simple boolean check that doesn't raise exceptions.

    Args:
        db: Database session
        agent_id: Agent ID to check
        complexity: Action complexity level (1-4)

    Returns:
        True if agent can perform action, False otherwise

    Example:
        if can_agent_perform(db, "agent123", complexity=3):
            # Agent can perform high-complexity actions
            perform_update()
    """
    return check_agent_permission(
        db, agent_id,
        action=f"complexity_{complexity}",
        complexity=complexity,
        raise_on_denied=False
    )


def enforce_governance_check(
    db: Session,
    agent_id: str,
    action: str,
    complexity: int
) -> None:
    """
    Enforce governance check - raises exception if not permitted.

    This is a convenience function that always raises on denial.

    Args:
        db: Database session
        agent_id: Agent ID to check
        action: Action name (for error messages)
        complexity: Action complexity level (1-4)

    Raises:
        HTTPException: If agent not permitted (403 Forbidden)

    Example:
        enforce_governance_check(db, "agent123", "delete_user", complexity=4)
        # If we get here, agent is permitted
        delete_user()
    """
    check_agent_permission(db, agent_id, action, complexity, raise_on_denied=True)
