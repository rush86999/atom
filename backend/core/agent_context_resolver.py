"""
Agent Context Resolver

Implements multi-layer fallback to determine which agent governs a request:
1. Explicit agent_id in request
2. Session context agent
3. Workspace default agent
4. System default "Chat Assistant"

This ensures all actions have proper agent attribution for governance and audit trails.
"""

import logging
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime

from core.models import (
    AgentRegistry, AgentStatus, User, ChatSession, Workspace
)
from core.agent_governance_service import AgentGovernanceService

logger = logging.getLogger(__name__)


class AgentContextResolver:
    """
    Resolves which agent should govern a given request using a fallback chain.
    """

    def __init__(self, db: Session):
        self.db = db
        self.governance = AgentGovernanceService(db)

    async def resolve_agent_for_request(
        self,
        user_id: str,
        workspace_id: str = "default",
        session_id: Optional[str] = None,
        requested_agent_id: Optional[str] = None,
        action_type: str = "chat"
    ) -> Tuple[Optional[AgentRegistry], Dict[str, Any]]:
        """
        Resolve the appropriate agent for a request using fallback chain.

        Args:
            user_id: User making the request
            workspace_id: Workspace context
            session_id: Optional session ID for session-level agent
            requested_agent_id: Explicitly requested agent ID
            action_type: Type of action being performed

        Returns:
            Tuple of (agent, resolution_context) where:
                agent: AgentRegistry instance or None if resolution failed
                resolution_context: Dict with resolution details
        """
        resolution_context = {
            "user_id": user_id,
            "workspace_id": workspace_id,
            "session_id": session_id,
            "requested_agent_id": requested_agent_id,
            "action_type": action_type,
            "resolution_path": [],
            "resolved_at": datetime.utcnow().isoformat()
        }

        agent = None

        # Level 1: Explicit agent_id in request
        if requested_agent_id:
            agent = self._get_agent(requested_agent_id)
            if agent:
                resolution_context["resolution_path"].append("explicit_agent_id")
                logger.info(f"Resolved agent via explicit agent_id: {agent.name}")
                return agent, resolution_context
            else:
                resolution_context["resolution_path"].append("explicit_agent_id_not_found")
                logger.warning(f"Requested agent_id {requested_agent_id} not found")

        # Level 2: Session context agent
        if session_id:
            agent = self._get_session_agent(session_id)
            if agent:
                resolution_context["resolution_path"].append("session_agent")
                logger.info(f"Resolved agent via session: {agent.name}")
                return agent, resolution_context
            else:
                resolution_context["resolution_path"].append("no_session_agent")

        # Level 3: Workspace default agent
        agent = self._get_workspace_default_agent(workspace_id)
        if agent:
            resolution_context["resolution_path"].append("workspace_default")
            logger.info(f"Resolved agent via workspace default: {agent.name}")
            return agent, resolution_context
        else:
            resolution_context["resolution_path"].append("no_workspace_default")

        # Level 4: System default "Chat Assistant"
        agent = self._get_or_create_system_default()
        if agent:
            resolution_context["resolution_path"].append("system_default")
            logger.info(f"Resolved agent via system default: {agent.name}")
            return agent, resolution_context
        else:
            resolution_context["resolution_path"].append("resolution_failed")
            logger.error("Failed to resolve any agent, including system default")

        return None, resolution_context

    def _get_agent(self, agent_id: str) -> Optional[AgentRegistry]:
        """Fetch agent by ID."""
        try:
            return self.db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()
        except Exception as e:
            logger.error(f"Error fetching agent {agent_id}: {e}")
            return None

    def _get_session_agent(self, session_id: str) -> Optional[AgentRegistry]:
        """
        Get agent associated with a session.

        Checks if the session has an agent_id in its metadata.
        """
        try:
            session = self.db.query(ChatSession).filter(
                ChatSession.id == session_id
            ).first()

            if not session:
                logger.debug(f"Session {session_id} not found")
                return None

            # Check metadata for agent_id
            metadata = session.metadata_json or {}
            agent_id = metadata.get("agent_id")

            if agent_id:
                agent = self._get_agent(agent_id)
                if agent:
                    return agent

            return None
        except Exception as e:
            logger.error(f"Error getting session agent: {e}")
            return None

    def _get_workspace_default_agent(self, workspace_id: str) -> Optional[AgentRegistry]:
        """
        Get workspace's default agent.

        Checks workspace metadata for default_agent_id.
        """
        try:
            workspace = self.db.query(Workspace).filter(
                Workspace.id == workspace_id
            ).first()

            if not workspace:
                logger.debug(f"Workspace {workspace_id} not found")
                return None

            # Check metadata for default_agent_id
            metadata = workspace.metadata_json or {}
            agent_id = metadata.get("default_agent_id")

            if agent_id:
                agent = self._get_agent(agent_id)
                if agent:
                    return agent

            return None
        except Exception as e:
            logger.error(f"Error getting workspace default agent: {e}")
            return None

    def _get_or_create_system_default(self) -> Optional[AgentRegistry]:
        """
        Get or create system default "Chat Assistant" agent.

        This is the ultimate fallback for all requests.
        """
        try:
            # Try to find existing Chat Assistant
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.name == "Chat Assistant",
                AgentRegistry.category == "system"
            ).first()

            if agent:
                return agent

            # Create system default agent
            logger.info("Creating system default Chat Assistant agent")
            agent = AgentRegistry(
                name="Chat Assistant",
                description="System default agent for general chat and assistance",
                category="system",
                module_path="system",
                class_name="ChatAssistant",
                status=AgentStatus.STUDENT.value,
                confidence_score=0.5,
                configuration={
                    "system_prompt": "You are a helpful assistant for business automation and integrations.",
                    "capabilities": ["chat", "stream_chat", "present_chart", "present_markdown"]
                }
            )
            self.db.add(agent)
            self.db.commit()
            self.db.refresh(agent)

            logger.info(f"Created system default agent: {agent.id}")
            return agent
        except Exception as e:
            logger.error(f"Error creating system default agent: {e}")
            return None

    def set_session_agent(
        self,
        session_id: str,
        agent_id: str
    ) -> bool:
        """
        Associate an agent with a session.

        This allows subsequent requests in the session to use the same agent.
        """
        try:
            session = self.db.query(ChatSession).filter(
                ChatSession.id == session_id
            ).first()

            if not session:
                logger.warning(f"Cannot set agent on non-existent session {session_id}")
                return False

            # Update metadata
            metadata = session.metadata_json or {}
            metadata["agent_id"] = agent_id
            session.metadata_json = metadata

            self.db.commit()
            logger.info(f"Set agent {agent_id} on session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting session agent: {e}")
            return False

    def set_workspace_default_agent(
        self,
        workspace_id: str,
        agent_id: str
    ) -> bool:
        """
        Set the default agent for a workspace.

        This agent will be used when no explicit agent or session agent is available.
        """
        try:
            workspace = self.db.query(Workspace).filter(
                Workspace.id == workspace_id
            ).first()

            if not workspace:
                logger.warning(f"Cannot set agent on non-existent workspace {workspace_id}")
                return False

            # Update metadata
            metadata = workspace.metadata_json or {}
            metadata["default_agent_id"] = agent_id
            workspace.metadata_json = metadata

            self.db.commit()
            logger.info(f"Set default agent {agent_id} on workspace {workspace_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting workspace default agent: {e}")
            return False

    async def validate_agent_for_action(
        self,
        agent: AgentRegistry,
        action_type: str,
        require_approval: bool = False
    ) -> Dict[str, Any]:
        """
        Validate that an agent can perform a specific action.

        Convenience wrapper around governance service.
        """
        return self.governance.can_perform_action(
            agent_id=agent.id,
            action_type=action_type,
            require_approval=require_approval
        )
