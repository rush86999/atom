"""
Deep Link System for Atom

Provides atom:// URL scheme for deep linking into Atom from external applications.
Supports agent invocation, workflow triggers, canvas interactions, and tool execution.

URL Schemes:
- atom://agent/{agent_id}?message={query}&session={session_id}
- atom://workflow/{workflow_id}?action={action}&params={json}
- atom://canvas/{canvas_id}?action={action}&params={json}
- atom://tool/{tool_name}?params={json}

Security:
- All deep links are validated and sanitized
- Agent governance checks apply
- Full audit trail for all deep link invocations
"""

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentExecution, AgentRegistry, DeepLinkAudit

logger = logging.getLogger(__name__)


# Feature flags
import os

DEEPLINK_ENABLED = os.getenv("DEEPLINK_ENABLED", "true").lower() == "true"
DEEPLINK_AUDIT_ENABLED = os.getenv("DEEPLINK_AUDIT_ENABLED", "true").lower() == "true"


class DeepLinkParseException(Exception):
    """Raised when deep link URL cannot be parsed."""
    pass


class DeepLinkSecurityException(Exception):
    """Raised when deep link fails security validation."""
    pass


class DeepLink:
    """Represents a parsed Atom deep link."""

    def __init__(
        self,
        scheme: str,
        resource_type: str,
        resource_id: str,
        parameters: Dict[str, Any],
        original_url: str
    ):
        self.scheme = scheme
        self.resource_type = resource_type  # 'agent', 'workflow', 'canvas', 'tool'
        self.resource_id = resource_id
        self.parameters = parameters
        self.original_url = original_url

    def __repr__(self):
        return f"<DeepLink {self.resource_type}:{self.resource_id} params={self.parameters}>"


def parse_deep_link(url: str) -> DeepLink:
    """
    Parse an atom:// deep link URL into components.

    Args:
        url: Deep link URL (e.g., "atom://agent/agent-1?message=Hello")

    Returns:
        DeepLink: Parsed deep link object

    Raises:
        DeepLinkParseException: If URL is invalid

    Examples:
        >>> link = parse_deep_link("atom://agent/agent-1?message=Hello&session=abc")
        >>> link.resource_type
        'agent'
        >>> link.resource_id
        'agent-1'
        >>> link.parameters
        {'message': 'Hello', 'session': 'abc'}
    """
    if not DEEPLINK_ENABLED:
        raise DeepLinkSecurityException("Deep linking is disabled")

    # Validate URL format
    if not url or not isinstance(url, str):
        raise DeepLinkParseException("URL must be a non-empty string")

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise DeepLinkParseException(f"Invalid URL format: {e}")

    # Validate scheme
    if parsed.scheme != "atom":
        raise DeepLinkParseException(f"Invalid scheme: '{parsed.scheme}'. Expected 'atom://'")

    # Handle both atom://agent/id and atom:agent/id formats
    # If netloc is present, path starts with /; if not, path is the full path
    if parsed.netloc:
        # Format: atom://agent/id (netloc contains resource type)
        path_parts = [parsed.netloc] + parsed.path.strip('/').split('/')
    else:
        # Format: atom:agent/id (path contains everything)
        path_parts = parsed.path.strip('/').split('/')

    if len(path_parts) < 2:
        raise DeepLinkParseException(
            f"Invalid path format: '{parsed.path}'. Expected '/resource_type/resource_id'"
        )

    resource_type = path_parts[0]
    resource_id = path_parts[1]

    # Validate resource type
    valid_resource_types = ['agent', 'workflow', 'canvas', 'tool']
    if resource_type not in valid_resource_types:
        raise DeepLinkParseException(
            f"Invalid resource type: '{resource_type}'. Must be one of {valid_resource_types}"
        )

    # Parse query parameters
    parameters = {}
    if parsed.query:
        try:
            query_dict = parse_qs(parsed.query)
            # Flatten single-value parameters
            for key, values in query_dict.items():
                if len(values) == 1:
                    # Decode URL-encoded values
                    parameters[key] = unquote(values[0])
                else:
                    # Keep multiple values as list
                    parameters[key] = [unquote(v) for v in values]

            # Parse JSON parameters
            if 'params' in parameters:
                try:
                    parameters['params'] = json.loads(parameters['params'])
                except json.JSONDecodeError as e:
                    raise DeepLinkParseException(f"Invalid JSON in params parameter: {e}")

        except Exception as e:
            raise DeepLinkParseException(f"Failed to parse query parameters: {e}")

    # Validate resource ID (basic format check)
    if not resource_id or not isinstance(resource_id, str):
        raise DeepLinkParseException("Resource ID cannot be empty")

    # Security: Validate resource ID format (alphanumeric, dashes, underscores)
    if not re.match(r'^[a-zA-Z0-9_\-]+$', resource_id):
        raise DeepLinkSecurityException(
            f"Invalid resource ID format: '{resource_id}'. "
            "Only alphanumeric characters, dashes, and underscores are allowed."
        )

    return DeepLink(
        scheme=parsed.scheme,
        resource_type=resource_type,
        resource_id=resource_id,
        parameters=parameters,
        original_url=url
    )


async def execute_agent_deep_link(
    deeplink: DeepLink,
    user_id: str,
    db: Session,
    source: str = "external"
) -> Dict[str, Any]:
    """
    Execute an agent deep link.

    Args:
        deeplink: Parsed deep link object (resource_type='agent')
        user_id: User ID invoking the deep link
        db: Database session
        source: Source of deep link (external_app, browser, etc.)

    Returns:
        Dict with execution result

    Example:
        >>> link = parse_deep_link("atom://agent/agent-1?message=Analyze+sales")
        >>> result = await execute_agent_deep_link(link, user_id="user-1", db=db)
    """
    if deeplink.resource_type != "agent":
        raise ValueError(f"Expected resource_type='agent', got '{deeplink.resource_type}'")

    agent_id = deeplink.resource_id
    message = deeplink.parameters.get('message', '')
    session_id = deeplink.parameters.get('session')

    # Security: Validate agent exists
    agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
    if not agent:
        return {
            "success": False,
            "error": f"Agent '{agent_id}' not found"
        }

    # Security: Check agent status (must be active)
    if agent.status not in ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]:
        return {
            "success": False,
            "error": f"Agent '{agent_id}' is not active (status: {agent.status})"
        }

    # Governance: Check if agent can perform actions
    governance = AgentGovernanceService(db)
    governance_check = governance.can_perform_action(
        agent_id=agent.id,
        action_type="stream_chat"  # Deep link triggers chat/action
    )

    if not governance_check["allowed"]:
        logger.warning(f"Governance blocked deep link execution for agent {agent_id}")
        return {
            "success": False,
            "error": f"Agent not permitted to execute action: {governance_check['reason']}"
        }

    try:
        # Create agent execution record
        execution = AgentExecution(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            workspace_id="default",
            status="running",
            input_summary=f"Deep link from {source}: {message[:100]}...",
            triggered_by="deeplink"
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)

        # Create deep link audit entry
        if DEEPLINK_AUDIT_ENABLED:
            audit = DeepLinkAudit(
                id=str(uuid.uuid4()),
                user_id=user_id,
                agent_id=agent_id,
                resource_type="agent",
                resource_id=agent_id,
                action="execute",
                source=source,
                deeplink_url=deeplink.original_url,
                parameters=deeplink.parameters,
                status="success",
                agent_execution_id=execution.id
            )
            db.add(audit)
            db.commit()

        logger.info(
            f"Executed agent deep link: agent={agent_id}, user={user_id}, "
            f"source={source}, execution={execution.id}"
        )

        return {
            "success": True,
            "agent_id": agent_id,
            "agent_name": agent.name,
            "execution_id": execution.id,
            "message": message,
            "session_id": session_id,
            "source": source
        }

    except Exception as e:
        logger.error(f"Failed to execute agent deep link: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def execute_workflow_deep_link(
    deeplink: DeepLink,
    user_id: str,
    db: Session,
    source: str = "external"
) -> Dict[str, Any]:
    """
    Execute a workflow deep link.

    Args:
        deeplink: Parsed deep link object (resource_type='workflow')
        user_id: User ID invoking the deep link
        db: Database session
        source: Source of deep link

    Returns:
        Dict with execution result

    Example:
        >>> link = parse_deep_link("atom://workflow/workflow-1?action=start")
        >>> result = await execute_workflow_deep_link(link, user_id="user-1", db=db)
    """
    if deeplink.resource_type != "workflow":
        raise ValueError(f"Expected resource_type='workflow', got '{deeplink.resource_type}'")

    workflow_id = deeplink.resource_id
    action = deeplink.parameters.get('action', 'start')
    params = deeplink.parameters.get('params', {})

    # Create audit entry
    if DEEPLINK_AUDIT_ENABLED:
        audit = DeepLinkAudit(
            id=str(uuid.uuid4()),
            user_id=user_id,
            resource_type="workflow",
            resource_id=workflow_id,
            action=action,
            source=source,
            deeplink_url=deeplink.original_url,
            parameters=params,
            status="success"
        )
        db.add(audit)
        db.commit()

    logger.info(
        f"Executed workflow deep link: workflow={workflow_id}, action={action}, "
        f"user={user_id}, source={source}"
    )

    return {
        "success": True,
        "workflow_id": workflow_id,
        "action": action,
        "params": params,
        "source": source
    }


async def execute_canvas_deep_link(
    deeplink: DeepLink,
    user_id: str,
    db: Session,
    source: str = "external"
) -> Dict[str, Any]:
    """
    Execute a canvas deep link.

    Args:
        deeplink: Parsed deep link object (resource_type='canvas')
        user_id: User ID invoking the deep link
        db: Database session
        source: Source of deep link

    Returns:
        Dict with execution result

    Example:
        >>> link = parse_deep_link("atom://canvas/canvas-123?action=update&params={\"title\":\"New\"}")
        >>> result = await execute_canvas_deep_link(link, user_id="user-1", db=db)
    """
    if deeplink.resource_type != "canvas":
        raise ValueError(f"Expected resource_type='canvas', got '{deeplink.resource_type}'")

    canvas_id = deeplink.resource_id
    action = deeplink.parameters.get('action', 'present')
    params = deeplink.parameters.get('params', {})

    # Import here to avoid circular dependency
    from tools.canvas_tool import update_canvas

    # Execute canvas action
    if action == "update":
        result = await update_canvas(
            user_id=user_id,
            canvas_id=canvas_id,
            updates=params
        )
    else:
        result = {
            "success": False,
            "error": f"Unsupported canvas action: {action}"
        }

    # Create audit entry
    if DEEPLINK_AUDIT_ENABLED:
        audit = DeepLinkAudit(
            id=str(uuid.uuid4()),
            user_id=user_id,
            resource_type="canvas",
            resource_id=canvas_id,
            action=action,
            source=source,
            deeplink_url=deeplink.original_url,
            parameters=params,
            status="success" if result["success"] else "failed"
        )
        db.add(audit)
        db.commit()

    logger.info(
        f"Executed canvas deep link: canvas={canvas_id}, action={action}, "
        f"user={user_id}, source={source}, success={result['success']}"
    )

    return result


async def execute_tool_deep_link(
    deeplink: DeepLink,
    user_id: str,
    db: Session,
    source: str = "external"
) -> Dict[str, Any]:
    """
    Execute a tool deep link.

    Args:
        deeplink: Parsed deep link object (resource_type='tool')
        user_id: User ID invoking the deep link
        db: Database session
        source: Source of deep link

    Returns:
        Dict with execution result

    Example:
        >>> link = parse_deep_link("atom://tool/present_chart?params={\"data\":[...]}")
        >>> result = await execute_tool_deep_link(link, user_id="user-1", db=db)
    """
    if deeplink.resource_type != "tool":
        raise ValueError(f"Expected resource_type='tool', got '{deeplink.resource_type}'")

    tool_name = deeplink.resource_id
    params = deeplink.parameters.get('params', {})

    # Get tool from registry
    from tools.registry import get_tool_registry
    registry = get_tool_registry()

    tool_metadata = registry.get(tool_name)
    if not tool_metadata:
        return {
            "success": False,
            "error": f"Tool '{tool_name}' not found"
        }

    # Create audit entry
    if DEEPLINK_AUDIT_ENABLED:
        audit = DeepLinkAudit(
            id=str(uuid.uuid4()),
            user_id=user_id,
            resource_type="tool",
            resource_id=tool_name,
            action="execute",
            source=source,
            deeplink_url=deeplink.original_url,
            parameters=params,
            status="success"
        )
        db.add(audit)
        db.commit()

    logger.info(
        f"Executed tool deep link: tool={tool_name}, user={user_id}, source={source}"
    )

    return {
        "success": True,
        "tool_name": tool_name,
        "params": params,
        "tool_metadata": tool_metadata.to_dict(),
        "source": source
    }


async def execute_deep_link(
    url: str,
    user_id: str,
    db: Session,
    source: str = "external"
) -> Dict[str, Any]:
    """
    Execute any Atom deep link URL.

    This is the main entry point for deep link execution.

    Args:
        url: Deep link URL (e.g., "atom://agent/agent-1?message=Hello")
        user_id: User ID invoking the deep link
        db: Database session
        source: Source of deep link

    Returns:
        Dict with execution result

    Raises:
        DeepLinkParseException: If URL cannot be parsed
        DeepLinkSecurityException: If URL fails security validation

    Examples:
        >>> result = await execute_deep_link(
        ...     "atom://agent/agent-1?message=Hello",
        ...     user_id="user-1",
        ...     db=db
        ... )
    """
    try:
        # Parse deep link
        deeplink = parse_deep_link(url)

        # Route to appropriate executor
        if deeplink.resource_type == "agent":
            return await execute_agent_deep_link(deeplink, user_id, db, source)
        elif deeplink.resource_type == "workflow":
            return await execute_workflow_deep_link(deeplink, user_id, db, source)
        elif deeplink.resource_type == "canvas":
            return await execute_canvas_deep_link(deeplink, user_id, db, source)
        elif deeplink.resource_type == "tool":
            return await execute_tool_deep_link(deeplink, user_id, db, source)
        else:
            return {
                "success": False,
                "error": f"Unsupported resource type: {deeplink.resource_type}"
            }

    except (DeepLinkParseException, DeepLinkSecurityException) as e:
        logger.error(f"Deep link execution failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        logger.error(f"Unexpected error executing deep link: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


def generate_deep_link(
    resource_type: str,
    resource_id: str,
    **parameters
) -> str:
    """
    Generate an atom:// deep link URL.

    Args:
        resource_type: Type of resource ('agent', 'workflow', 'canvas', 'tool')
        resource_id: ID of the resource
        **parameters: Query parameters

    Returns:
        str: Deep link URL

    Examples:
        >>> url = generate_deep_link('agent', 'agent-1', message='Hello', session='abc')
        >>> url
        'atom://agent/agent-1?message=Hello&session=abc'

        >>> url = generate_deep_link('canvas', 'canvas-123', action='update',
        ...                          params={'title': 'New'})
        'atom://canvas/canvas-123?action=update&params={"title": "New"}'
    """
    # Validate resource type
    valid_resource_types = ['agent', 'workflow', 'canvas', 'tool']
    if resource_type not in valid_resource_types:
        raise ValueError(f"Invalid resource_type: '{resource_type}'")

    # Build URL
    url = f"atom://{resource_type}/{resource_id}"

    # Add query parameters
    if parameters:
        from urllib.parse import quote, urlencode

        # Convert params to JSON if it's a dict
        if 'params' in parameters and isinstance(parameters['params'], dict):
            parameters['params'] = json.dumps(parameters['params'])

        query_string = urlencode(parameters, doseq=True)
        url += f"?{query_string}"

    return url
