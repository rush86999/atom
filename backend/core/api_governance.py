"""
API Governance Decorator

Provides a decorator for applying governance checks to state-changing API routes.
Enforces agent maturity levels and action complexity for security.

Usage:
    from core.api_governance import require_governance

    @router.post("/sessions/create")
    @require_governance(action_complexity=2, action_name="create_browser_session")
    async def create_browser_session(...):
        # Clean implementation - governance handled by decorator
        pass
"""
import functools
import logging
from typing import Callable, List, Optional
from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.feature_flags import FeatureFlags
from core.models import AgentRegistry

logger = logging.getLogger(__name__)


# ============================================================================
# Action Complexity Levels
# ============================================================================

class ActionComplexity:
    """
    Action complexity levels for governance enforcement.

    Level 1 (LOW): Presentations, read-only
    Level 2 (MODERATE): Streaming, moderate actions
    Level 3 (HIGH): State changes, submissions
    Level 4 (CRITICAL): Deletions, payments
    """
    LOW = 1
    MODERATE = 2
    HIGH = 3
    CRITICAL = 4

    @classmethod
    def get_required_maturity(cls, complexity: int) -> str:
        """
        Get minimum agent maturity level required for action complexity.

        Args:
            complexity: Action complexity level (1-4)

        Returns:
            Required maturity level string
        """
        mapping = {
            1: "STUDENT",      # Presentations, read-only
            2: "INTERN",       # Streaming, moderate actions
            3: "SUPERVISED",   # State changes, submissions
            4: "AUTONOMOUS"    # Deletions, payments
        }
        return mapping.get(complexity, "AUTONOMOUS")


# ============================================================================
# Governance Decorator
# ============================================================================

def require_governance(
    action_complexity: int = ActionComplexity.MODERATE,
    action_name: Optional[str] = None,
    feature: Optional[str] = None,
    allow_user_initiated: bool = True
):
    """
    Decorator to apply governance checks to state-changing API routes.

    This decorator enforces:
    1. Agent maturity level requirements
    2. Action complexity restrictions
    3. Feature flag checks
    4. Emergency bypass handling

    Args:
        action_complexity: Action complexity level (1-4). Default: MODERATE (2)
        action_name: Descriptive name for logging. Default: function name
        feature: Feature flag name (e.g., 'browser', 'canvas'). Default: None
        allow_user_initiated: Whether users can call directly (vs agents only). Default: True

    Usage:
        @router.post("/sessions/create")
        @require_governance(
            action_complexity=ActionComplexity.HIGH,
            action_name="create_browser_session",
            feature="browser"
        )
        async def create_browser_session(
            request: Request,
            db: Session = Depends(get_db),
            current_user: User = Depends(get_current_user),
            ...
        ):
            # Implementation - governance already enforced
            pass

    Example:
        # Browser session creation (HIGH complexity)
        @router.post("/sessions/create")
        @require_governance(action_complexity=3, action_name="create_browser_session", feature="browser")
        async def create_session(...):
            pass

        # Canvas presentation (LOW complexity, STUDENT+ allowed)
        @router.post("/canvas/present")
        @require_governance(action_complexity=1, action_name="present_canvas", feature="canvas")
        async def present_canvas(...):
            pass

        # Payment processing (CRITICAL complexity, AUTONOMOUS only)
        @router.post("/payments/process")
        @require_governance(action_complexity=4, action_name="process_payment", feature="billing")
        async def process_payment(...):
            pass
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request and db from kwargs
            request: Optional[Request] = kwargs.get('request')
            db: Optional[Session] = kwargs.get('db')

            if not request or not db:
                # Can't perform governance check without request/db
                logger.warning(f"Governance check skipped for {func.__name__}: missing request or db")
                return await func(*args, **kwargs)

            # Check emergency bypass first
            if FeatureFlags.is_emergency_bypass_active():
                logger.warning(f"⚠️  EMERGENCY BYPASS: Governance check skipped for {func.__name__}")
                return await func(*args, **kwargs)

            # Extract agent_id from request
            agent_id = extract_agent_id(request)

            # If no agent_id and user-initiated is allowed, proceed
            if not agent_id and allow_user_initiated:
                return await func(*args, **kwargs)

            # If agent_id exists, perform governance check
            if agent_id:
                await perform_governance_check(
                    db=db,
                    agent_id=agent_id,
                    request=request,
                    action_complexity=action_complexity,
                    action_name=action_name or func.__name__,
                    feature=feature
                )

            # Proceed with the function
            return await func(*args, **kwargs)

        return wrapper
    return decorator


# ============================================================================
# Helper Functions
# ============================================================================

def extract_agent_id(request: Request) -> Optional[str]:
    """
    Extract agent_id from request.

    Checks multiple possible locations:
    - request.state.agent_id
    - request.query_params.agent_id
    - request.headers X-Agent-ID

    Args:
        request: FastAPI request object

    Returns:
        Agent ID string or None
    """
    # Check request state first
    if hasattr(request.state, 'agent_id'):
        return request.state.agent_id

    # Check query parameters
    agent_id = request.query_params.get('agent_id')
    if agent_id:
        return agent_id

    # Check headers
    agent_id = request.headers.get('X-Agent-ID')
    if agent_id:
        return agent_id

    # Check request body (if JSON)
    try:
        if hasattr(request, '_json'):
            body = request._json
            if isinstance(body, dict) and 'agent_id' in body:
                return body['agent_id']
    except Exception as e:
        logger.debug(f"Failed to extract agent_id from request body: {e}")

    return None


async def perform_governance_check(
    db: Session,
    agent_id: str,
    request: Request,
    action_complexity: int,
    action_name: str,
    feature: Optional[str] = None
):
    """
    Perform governance check for agent-initiated request.

    Args:
        db: Database session
        agent_id: Agent ID to check
        request: FastAPI request object
        action_complexity: Action complexity level (1-4)
        action_name: Action name for logging
        feature: Optional feature flag name

    Raises:
        HTTPException: If governance check fails
    """
    try:
        # Check feature flag if specified
        if feature and not FeatureFlags.should_enforce_governance(feature):
            logger.info(f"Feature flag disabled: {feature}_GOVERNANCE_ENABLED")
            return

        # Resolve agent
        resolver = AgentContextResolver(db)
        governance = AgentGovernanceService(db)

        # Get current user from request
        from core.auth import get_current_user_from_request
        try:
            current_user = await get_current_user_from_request(request)
            user_id = current_user.id if current_user else None
        except Exception:
            user_id = None

        # Resolve agent
        agent, resolution_method = await resolver.resolve_agent_for_request(
            user_id=user_id,
            requested_agent_id=agent_id,
            action_type=action_name
        )

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found"
            )

        # Perform governance check
        required_maturity = ActionComplexity.get_required_maturity(action_complexity)

        governance_check = governance.can_perform_action(
            agent_id=agent.id,
            action_complexity=action_complexity,
            action_name=action_name
        )

        if not governance_check['allowed']:
            # Check if proposal should be created (for INTERN agents)
            if agent.maturity_level == "INTERN":
                from core.proposal_service import ProposalService
                proposal_service = ProposalService(db)

                # Create proposal
                proposal = await proposal_service.create_action_proposal(
                    intern_agent_id=agent.id,
                    trigger_context={
                        'action_name': action_name,
                        'action_complexity': action_complexity,
                        'request_path': str(request.url.path),
                        'request_method': request.method
                    },
                    proposed_action={
                        'type': action_name,
                        'complexity': action_complexity
                    },
                    reasoning=f"INTERN agent requires approval for {action_name} (complexity {action_complexity})"
                )

                logger.info(f"Created proposal {proposal.id} for INTERN agent {agent.id}")

                raise HTTPException(
                    status_code=status.HTTP_202_ACCEPTED,
                    detail={
                        "message": "Action requires human approval",
                        "proposal_id": proposal.id,
                        "agent_maturity": agent.maturity_level,
                        "required_maturity": required_maturity
                    }
                )

            # For STUDENT agents, block the action
            if agent.maturity_level == "STUDENT":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "message": "STUDENT agents cannot perform state-changing actions",
                        "agent_maturity": agent.maturity_level,
                        "required_maturity": required_maturity,
                        "action": action_name,
                        "reason": "STUDENT agents are in training and can only perform read-only actions"
                    }
                )

            # Default error
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": "Agent not authorized for this action",
                    "agent_maturity": agent.maturity_level,
                    "required_maturity": required_maturity,
                    "action": action_name
                }
            )

        # Log successful governance check
        logger.info(
            f"Governance check passed: agent={agent.id} ({agent.maturity_level}), "
            f"action={action_name}, complexity={action_complexity}"
        )

    except Exception as e:
        logger.error(f"Governance check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Governance check error: {str(e)}"
        )


# ============================================================================
# Convenience Decorators
# ============================================================================

def require_browser_governance(action_complexity: int = ActionComplexity.HIGH):
    """Convenience decorator for browser automation governance."""
    return require_governance(
        action_complexity=action_complexity,
        feature='browser',
        action_name='browser_automation'
    )


def require_canvas_governance(action_complexity: int = ActionComplexity.MODERATE):
    """Convenience decorator for canvas presentation governance."""
    return require_governance(
        action_complexity=action_complexity,
        feature='canvas',
        action_name='canvas_presentation'
    )


def require_device_governance(action_complexity: int = ActionComplexity.HIGH):
    """Convenience decorator for device capabilities governance."""
    return require_governance(
        action_complexity=action_complexity,
        feature='device',
        action_name='device_access'
    )


def require_financial_governance(action_complexity: int = ActionComplexity.CRITICAL):
    """Convenience decorator for financial operations governance."""
    return require_governance(
        action_complexity=action_complexity,
        feature='financial',
        action_name='financial_operation'
    )


# ============================================================================
# Testing Helper
# ============================================================================

async def check_governance_for_testing(
    db: Session,
    agent_id: str,
    action_complexity: int
) -> dict:
    """
    Helper function for testing governance checks.

    Args:
        db: Database session
        agent_id: Agent ID to check
        action_complexity: Action complexity level

    Returns:
        Dictionary with governance check result
    """
    try:
        governance = AgentGovernanceService(db)
        return governance.can_perform_action(
            agent_id=agent_id,
            action_complexity=action_complexity,
            action_name="test_action"
        )
    except Exception as e:
        return {
            "allowed": False,
            "error": str(e)
        }
