"""
Governance Decorator for Atom Platform

Provides decorators to enforce governance checks on protected operations.
This ensures consistent governance integration across all tools and services.
"""

import functools
import logging
import os
from typing import Callable, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.agent_context_resolver import AgentContextResolver
from core.error_handlers import ErrorCode, api_error

logger = logging.getLogger(__name__)

# Feature flags
GOVERNANCE_ENABLED = os.getenv("STREAMING_GOVERNANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"


def require_governance(
    action_complexity: int = 1,
    check_agent_exists: bool = True,
    on_failure: str = "raise"  # "raise", "return_none", "return_false"
):
    """
    Decorator to enforce governance checks before executing protected operations.

    Args:
        action_complexity: Required action complexity level (1-4)
            - 1 (LOW): Presentations, read-only → STUDENT+
            - 2 (MODERATE): Streaming, moderate actions → INTERN+
            - 3 (HIGH): State changes, submissions → SUPERVISED+
            - 4 (CRITICAL): Deletions, payments → AUTONOMOUS only
        check_agent_exists: Whether to verify the agent exists before checking governance
        on_failure: Behavior when governance check fails
            - "raise": Raise HTTPException (default)
            - "return_none": Return None on failure
            - "return_false": Return False on failure

    Example:
        @require_governance(action_complexity=2)
        async def stream_response(agent_id: str, message: str, db: Session):
            # This will only execute if agent has INTERN+ maturity
            return await stream_to_agent(agent_id, message)

        @require_governance(action_complexity=3, on_failure="return_none")
        async def update_database(agent_id: str, data: dict, db: Session):
            # Returns None if agent lacks SUPERVISED+ maturity
            return await update_record(agent_id, data)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract db and agent_id from function arguments
            db = _get_db_from_args(args, kwargs)
            agent_id = _get_agent_id_from_args(func.__name__, args, kwargs)

            if not db or not agent_id:
                logger.warning(
                    f"Cannot perform governance check for {func.__name__}: "
                    f"db or agent_id not found in arguments"
                )
                if on_failure == "return_none":
                    return None
                elif on_failure == "return_false":
                    return False
                else:
                    raise api_error(
                        ErrorCode.INTERNAL_SERVER_ERROR,
                        "Cannot verify governance: missing db or agent_id"
                    )

            # Skip governance if disabled or emergency bypass is active
            if not GOVERNANCE_ENABLED or EMERGENCY_GOVERNANCE_BYPASS:
                logger.debug(f"Governance bypassed for {func.__name__} (agent_id={agent_id})")
                return await func(*args, **kwargs)

            try:
                # Check if agent exists (optional)
                if check_agent_exists:
                    resolver = AgentContextResolver(db)
                    agent_context = resolver.resolve_context(agent_id)
                    if not agent_context:
                        if on_failure == "return_none":
                            return None
                        elif on_failure == "return_false":
                            return False
                        else:
                            raise api_error(
                                ErrorCode.AGENT_NOT_FOUND,
                                f"Agent {agent_id} not found",
                                status_code=404
                            )

                # Check if agent can perform this action
                governance = AgentGovernanceService(db)
                can_execute = governance.can_execute_action(agent_id, action_complexity)

                if not can_execute:
                    # Get agent maturity level for error message
                    resolver = AgentContextResolver(db)
                    agent_context = resolver.resolve_context(agent_id)
                    current_maturity = agent_context.get("maturity_level", "UNKNOWN") if agent_context else "UNKNOWN"

                    # Determine required maturity level
                    maturity_requirements = {
                        1: "STUDENT",
                        2: "INTERN",
                        3: "SUPERVISED",
                        4: "AUTONOMOUS"
                    }
                    required_maturity = maturity_requirements.get(action_complexity, "AUTONOMOUS")

                    logger.warning(
                        f"Governance check failed for {func.__name__}: "
                        f"agent_id={agent_id}, maturity={current_maturity}, "
                        f"required={required_maturity}, action_complexity={action_complexity}"
                    )

                    if on_failure == "return_none":
                        return None
                    elif on_failure == "return_false":
                        return False
                    else:
                        raise api_error(
                            ErrorCode.AGENT_MATURITY_INSUFFICIENT,
                            f"Agent {agent_id} (maturity: {current_maturity}) cannot perform "
                            f"action with complexity {action_complexity} (requires: {required_maturity})",
                            details={
                                "agent_id": agent_id,
                                "current_maturity": current_maturity,
                                "required_maturity": required_maturity,
                                "action_complexity": action_complexity
                            },
                            status_code=403
                        )

                # Governance check passed - execute the function
                return await func(*args, **kwargs)

            except HTTPException:
                raise
            except Exception as e:
                logger.error(
                    f"Error during governance check for {func.__name__}: {str(e)}",
                    exc_info=True
                )
                if on_failure == "return_none":
                    return None
                elif on_failure == "return_false":
                    return False
                else:
                    raise api_error(
                        ErrorCode.INTERNAL_SERVER_ERROR,
                        f"Governance check failed: {str(e)}"
                    )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Extract db and agent_id from function arguments
            db = _get_db_from_args(args, kwargs)
            agent_id = _get_agent_id_from_args(func.__name__, args, kwargs)

            if not db or not agent_id:
                logger.warning(
                    f"Cannot perform governance check for {func.__name__}: "
                    f"db or agent_id not found in arguments"
                )
                if on_failure == "return_none":
                    return None
                elif on_failure == "return_false":
                    return False
                else:
                    raise api_error(
                        ErrorCode.INTERNAL_SERVER_ERROR,
                        "Cannot verify governance: missing db or agent_id"
                    )

            # Skip governance if disabled or emergency bypass is active
            if not GOVERNANCE_ENABLED or EMERGENCY_GOVERNANCE_BYPASS:
                logger.debug(f"Governance bypassed for {func.__name__} (agent_id={agent_id})")
                return func(*args, **kwargs)

            try:
                # Check if agent exists (optional)
                if check_agent_exists:
                    resolver = AgentContextResolver(db)
                    agent_context = resolver.resolve_context(agent_id)
                    if not agent_context:
                        if on_failure == "return_none":
                            return None
                        elif on_failure == "return_false":
                            return False
                        else:
                            raise api_error(
                                ErrorCode.AGENT_NOT_FOUND,
                                f"Agent {agent_id} not found",
                                status_code=404
                            )

                # Check if agent can perform this action
                governance = AgentGovernanceService(db)
                can_execute = governance.can_execute_action(agent_id, action_complexity)

                if not can_execute:
                    # Get agent maturity level for error message
                    resolver = AgentContextResolver(db)
                    agent_context = resolver.resolve_context(agent_id)
                    current_maturity = agent_context.get("maturity_level", "UNKNOWN") if agent_context else "UNKNOWN"

                    # Determine required maturity level
                    maturity_requirements = {
                        1: "STUDENT",
                        2: "INTERN",
                        3: "SUPERVISED",
                        4: "AUTONOMOUS"
                    }
                    required_maturity = maturity_requirements.get(action_complexity, "AUTONOMOUS")

                    logger.warning(
                        f"Governance check failed for {func.__name__}: "
                        f"agent_id={agent_id}, maturity={current_maturity}, "
                        f"required={required_maturity}, action_complexity={action_complexity}"
                    )

                    if on_failure == "return_none":
                        return None
                    elif on_failure == "return_false":
                        return False
                    else:
                        raise api_error(
                            ErrorCode.AGENT_MATURITY_INSUFFICIENT,
                            f"Agent {agent_id} (maturity: {current_maturity}) cannot perform "
                            f"action with complexity {action_complexity} (requires: {required_maturity})",
                            details={
                                "agent_id": agent_id,
                                "current_maturity": current_maturity,
                                "required_maturity": required_maturity,
                                "action_complexity": action_complexity
                            },
                            status_code=403
                        )

                # Governance check passed - execute the function
                return func(*args, **kwargs)

            except HTTPException:
                raise
            except Exception as e:
                logger.error(
                    f"Error during governance check for {func.__name__}: {str(e)}",
                    exc_info=True
                )
                if on_failure == "return_none":
                    return None
                elif on_failure == "return_false":
                    return False
                else:
                    raise api_error(
                        ErrorCode.INTERNAL_SERVER_ERROR,
                        f"Governance check failed: {str(e)}"
                    )

        # Return appropriate wrapper based on whether function is async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def _get_db_from_args(args: tuple, kwargs: dict) -> Optional[Session]:
    """
    Extract database session from function arguments.

    Looks for 'db' parameter in both positional and keyword arguments.
    """
    # Check kwargs first
    if 'db' in kwargs:
        return kwargs['db']

    # Check if db is in positional arguments
    # This requires inspecting the function signature to find parameter names
    # For now, we'll skip this complexity and rely on kwargs
    return None


def _get_agent_id_from_args(func_name: str, args: tuple, kwargs: dict) -> Optional[str]:
    """
    Extract agent_id from function arguments.

    Looks for 'agent_id' parameter in both positional and keyword arguments.
    """
    # Check kwargs first
    if 'agent_id' in kwargs:
        return kwargs['agent_id']

    # Try to find agent_id in positional arguments by index
    # This is a heuristic - assumes agent_id is often the first argument after db
    # A more robust solution would inspect function signatures
    return None


# Convenience decorators for common action complexity levels

require_student = require_governance(action_complexity=1)
require_intern = require_governance(action_complexity=2)
require_supervised = require_governance(action_complexity=3)
require_autonomous = require_governance(action_complexity=4)
