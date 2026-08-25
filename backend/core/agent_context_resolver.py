"""
Agent Context Resolver

Implements multi-layer fallback to determine which agent governs a request:
1. Explicit agent_id in request
2. Session context agent
3. Workspace default agent
4. System default "Chat Assistant"

This ensures all actions have proper agent attribution for governance and audit trails.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus, ChatSession, User
from core.personal_scope import PERSONAL_TENANT_ID, PERSONAL_WORKSPACE_ID  # type: ignore[import-untyped]

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
        session_id: Optional[str] = None,
        requested_agent_id: Optional[str] = None,
        action_type: str = "chat"
    ) -> Tuple[Optional[AgentRegistry], Dict[str, Any]]:
        """
        Resolve the appropriate agent for a request using fallback chain.

        Args:
            user_id: User making the request
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
            "session_id": session_id,
            "requested_agent_id": requested_agent_id,
            "action_type": action_type,
            "resolution_path": [],
            "resolved_at": datetime.now(timezone.utc).isoformat()
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

        # Level 3: System default "Chat Assistant"
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
                # Heal legacy rows created before workspace scoping: a
                # Chat Assistant with workspace_id=None is invisible to
                # AgentGovernanceService (which filters workspace_id="default"),
                # so every governance check fails with "Agent not found".
                if agent.workspace_id is None or agent.tenant_id is None:
                    if agent.workspace_id is None:
                        agent.workspace_id = PERSONAL_WORKSPACE_ID
                    if agent.tenant_id is None:
                        agent.tenant_id = PERSONAL_TENANT_ID
                    self.db.commit()
                    logger.info(
                        "Backfilled workspace/tenant scope on system default agent: %s",
                        agent.id,
                    )
                # Heal pre-Round-86 rows born STUDENT: the fallback chat
                # surface needs level-2 actions (stream_chat) to function at
                # all. Never demotes an agent that already graduated higher.
                if agent.status == AgentStatus.STUDENT.value:
                    agent.status = AgentStatus.INTERN.value
                    if (agent.confidence_score or 0) < 0.6:
                        agent.confidence_score = 0.6
                    self.db.commit()
                    logger.info(
                        "Healed system Chat Assistant %s to INTERN (fallback "
                        "chat surface cannot run at STUDENT)", agent.id,
                    )
                return agent

            # Create system default agent.
            #
            # Birth state rationale: the Chat Assistant is the platform's
            # fallback interaction surface — every unmatched request lands
            # here. STUDENT maturity would block `stream_chat` (a level-2
            # INTERN action in the governance ladder), breaking chat before
            # the agent ever trains. It is born INTERN (like the onboarding
            # Demo Assistant) with the same evidence-gate exemption as all
            # system agents; level-3+ actions still require graduation.
            logger.info("Creating system default Chat Assistant agent")
            agent = AgentRegistry(
                name="Chat Assistant",
                description="System default agent for general chat and assistance",
                category="system",
                module_path="system",
                class_name="ChatAssistant",
                status=AgentStatus.INTERN.value,
                confidence_score=0.6,
                workspace_id=PERSONAL_WORKSPACE_ID,
                tenant_id=PERSONAL_TENANT_ID,
                configuration={
                    "system_prompt": "You are a helpful assistant for business automation and integrations.",
                    "capabilities": ["chat", "stream_chat", "present_chart", "present_markdown"],
                    "system_agent": True,
                    "role": "chat",
                    # Learning contract: atom_main is the designated mentor
                    # (fast pathway); observation runs in parallel. System
                    # agents skip the apprenticeship evidence gate, but the
                    # learning log still accumulates for graduation beyond
                    # INTERN.
                    "learning": {
                        "teacher_agent_id": "atom_main",
                        "pathways": ["teacher", "observation"],
                        "curriculum": ["chat_facilitation", "canvas_presentation"],
                    },
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

            # Verify that the agent exists
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            if not agent:
                logger.warning(f"Cannot set non-existent agent {agent_id} on session {session_id}")
                return False

            # Update metadata. Copy so SQLAlchemy sees a new object — JSONColumn
            # has no mutable tracking, so reusing the same dict and assigning it
            # back is a no-op (no UPDATE issued) and the agent_id is lost.
            metadata = dict(session.metadata_json or {})
            metadata["agent_id"] = agent_id
            session.metadata_json = metadata

            self.db.commit()
            logger.info(f"Set agent {agent_id} on session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting session agent: {e}")
            return False



    def validate_agent_for_action(
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
