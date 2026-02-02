"""
View Coordinator Service

Manages multi-view orchestration for agent-coordinated browser, terminal,
and canvas views with real-time guidance.

Features:
- View switching (browser, terminal, canvas)
- Layout management (split, tabs, grid)
- View state tracking
- Agent-controlled view orchestration
"""

import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from core.websockets import manager as ws_manager
from core.models import (
    ViewOrchestrationState,
    AgentRegistry,
    CanvasAudit
)

logger = logging.getLogger(__name__)


# Feature flags
import os
VIEW_COORDINATION_ENABLED = os.getenv("VIEW_COORDINATION_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"


class ViewCoordinator:
    """
    Multi-view orchestration system for agent-coordinated views.

    Manages browser, terminal, and canvas views with real-time agent guidance.
    """

    def __init__(self, db: Session):
        self.db = db

    async def switch_to_browser_view(
        self,
        user_id: str,
        agent_id: str,
        url: str,
        guidance: str,
        session_id: Optional[str] = None
    ):
        """
        Switch to browser view with canvas guidance.

        Args:
            user_id: User ID
            agent_id: Agent ID controlling the view
            url: URL to open in browser
            guidance: Canvas guidance message
            session_id: Optional session ID for state persistence
        """
        if not VIEW_COORDINATION_ENABLED:
            return

        try:
            session_id = session_id or self._get_or_create_session(user_id)

            # Update orchestration state
            state = self.db.query(ViewOrchestrationState).filter(
                ViewOrchestrationState.session_id == session_id
            ).first()

            if not state:
                state = ViewOrchestrationState(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    session_id=session_id,
                    active_views=[],
                    layout="canvas",
                    controlling_agent=agent_id
                )
                self.db.add(state)
            else:
                state.controlling_agent = agent_id

            # Add browser view if not active
            browser_view = {
                "view_id": f"browser_{uuid.uuid4().hex[:8]}",
                "view_type": "browser",
                "title": f"Browser: {url[:50]}",
                "status": "active",
                "position": {"x": 0, "y": 0},
                "size": {"width": "full", "height": "full"},
                "url": url
            }

            # Update active views
            existing_view_ids = [v.get("view_id") for v in state.active_views]
            if browser_view["view_id"] not in existing_view_ids:
                state.active_views.append(browser_view)

            state.layout = "split_vertical"
            state.updated_at = datetime.utcnow()
            self.db.commit()

            # Broadcast view switch
            await ws_manager.broadcast(
                f"user:{user_id}",
                {
                    "type": "view:switch",
                    "data": {
                        "view_type": "browser",
                        "view_id": browser_view["view_id"],
                        "url": url,
                        "canvas_guidance": {
                            "agent_id": agent_id,
                            "message": guidance,
                            "what_youre_seeing": f"I'm opening {url}",
                            "controls": [
                                {"label": "Take Control", "action": "manual_control"},
                                {"label": "Pause Automation", "action": "pause"}
                            ]
                        },
                        "layout": state.layout
                    }
                }
            )

            # Create audit
            await self._create_audit(
                agent_id=agent_id,
                user_id=user_id,
                session_id=session_id,
                action="switch_to_browser",
                metadata={"url": url, "guidance": guidance}
            )

            logger.info(f"Switched to browser view for user {user_id}, agent {agent_id}")

        except Exception as e:
            logger.error(f"Failed to switch to browser view: {e}")

    async def switch_to_terminal_view(
        self,
        user_id: str,
        agent_id: str,
        command: str,
        guidance: str,
        session_id: Optional[str] = None
    ):
        """
        Switch to terminal view with canvas guidance.

        Args:
            user_id: User ID
            agent_id: Agent ID controlling the view
            command: Command to execute
            guidance: Canvas guidance message
            session_id: Optional session ID
        """
        if not VIEW_COORDINATION_ENABLED:
            return

        try:
            session_id = session_id or self._get_or_create_session(user_id)

            # Update orchestration state
            state = self.db.query(ViewOrchestrationState).filter(
                ViewOrchestrationState.session_id == session_id
            ).first()

            if not state:
                state = ViewOrchestrationState(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    session_id=session_id,
                    active_views=[],
                    layout="canvas",
                    controlling_agent=agent_id
                )
                self.db.add(state)
            else:
                state.controlling_agent = agent_id

            # Add terminal view
            terminal_view = {
                "view_id": f"terminal_{uuid.uuid4().hex[:8]}",
                "view_type": "terminal",
                "title": "Terminal",
                "status": "active",
                "position": {"x": 0, "y": 0},
                "size": {"width": "full", "height": "half"},
                "command": command
            }

            # Update active views
            existing_view_ids = [v.get("view_id") for v in state.active_views]
            if terminal_view["view_id"] not in existing_view_ids:
                state.active_views.append(terminal_view)

            state.layout = "split_horizontal"
            state.updated_at = datetime.utcnow()
            self.db.commit()

            # Broadcast view switch
            await ws_manager.broadcast(
                f"user:{user_id}",
                {
                    "type": "view:switch",
                    "data": {
                        "view_type": "terminal",
                        "view_id": terminal_view["view_id"],
                        "command": command,
                        "canvas_guidance": {
                            "agent_id": agent_id,
                            "message": guidance,
                            "what_youre_seeing": f"Executing: {command}",
                            "controls": [
                                {"label": "Take Control", "action": "manual_control"},
                                {"label": "Stop Execution", "action": "stop"}
                            ]
                        },
                        "layout": state.layout
                    }
                }
            )

            # Create audit
            await self._create_audit(
                agent_id=agent_id,
                user_id=user_id,
                session_id=session_id,
                action="switch_to_terminal",
                metadata={"command": command, "guidance": guidance}
            )

            logger.info(f"Switched to terminal view for user {user_id}, agent {agent_id}")

        except Exception as e:
            logger.error(f"Failed to switch to terminal view: {e}")

    async def set_layout(
        self,
        user_id: str,
        layout: str,
        session_id: Optional[str] = None
    ):
        """
        Set multi-view layout.

        Args:
            user_id: User ID
            layout: Layout type (canvas, split_horizontal, split_vertical, tabs, grid)
            session_id: Optional session ID
        """
        if not VIEW_COORDINATION_ENABLED:
            return

        try:
            session_id = session_id or self._get_or_create_session(user_id)

            # Get or create state
            state = self.db.query(ViewOrchestrationState).filter(
                ViewOrchestrationState.session_id == session_id
            ).first()

            if state:
                state.layout = layout
                state.updated_at = datetime.utcnow()
                self.db.commit()

            # Broadcast layout change
            await ws_manager.broadcast(
                f"user:{user_id}",
                {
                    "type": "view:layout_change",
                    "data": {
                        "layout": layout,
                        "session_id": session_id
                    }
                }
            )

            logger.info(f"Set layout to {layout} for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to set layout: {e}")

    async def activate_view(
        self,
        user_id: str,
        view_type: str,
        position: Optional[str] = None,
        size: Optional[str] = None,
        url: Optional[str] = None,
        command: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        """
        Activate a view and add it to active views.

        Args:
            user_id: User ID
            view_type: Type of view (canvas, browser, terminal, app)
            position: Position (left, right, top, bottom)
            size: Size (1/3, 1/2, 2/3, full)
            url: URL for browser view
            command: Command for terminal view
            session_id: Optional session ID
        """
        if not VIEW_COORDINATION_ENABLED:
            return

        try:
            session_id = session_id or self._get_or_create_session(user_id)

            # Get or create state
            state = self.db.query(ViewOrchestrationState).filter(
                ViewOrchestrationState.session_id == session_id
            ).first()

            if not state:
                state = ViewOrchestrationState(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    session_id=session_id,
                    active_views=[],
                    layout="canvas"
                )
                self.db.add(state)

            # Create view object
            view = {
                "view_id": f"{view_type}_{uuid.uuid4().hex[:8]}",
                "view_type": view_type,
                "title": view_type.capitalize(),
                "status": "active",
                "position": {"x": 0, "y": 0},
                "size": {"width": size or "full", "height": size or "full"}
            }

            # Add view-specific data
            if view_type == "browser" and url:
                view["url"] = url
                view["title"] = f"Browser: {url[:50]}"
            elif view_type == "terminal" and command:
                view["command"] = command

            # Add to active views
            existing_view_ids = [v.get("view_id") for v in state.active_views]
            if view["view_id"] not in existing_view_ids:
                state.active_views.append(view)
                state.updated_at = datetime.utcnow()
                self.db.commit()

            # Broadcast view activation
            await ws_manager.broadcast(
                f"user:{user_id}",
                {
                    "type": "view:activated",
                    "data": {
                        "view": view,
                        "layout": state.layout
                    }
                }
            )

            logger.info(f"Activated {view_type} view for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to activate view: {e}")

    async def update_view_guidance(
        self,
        user_id: str,
        view_id: str,
        guidance: str,
        session_id: Optional[str] = None
    ):
        """
        Update canvas guidance for active view.

        Args:
            user_id: User ID
            view_id: View ID to update guidance for
            guidance: New guidance message
            session_id: Optional session ID
        """
        if not VIEW_COORDINATION_ENABLED:
            return

        try:
            # Broadcast guidance update
            await ws_manager.broadcast(
                f"user:{user_id}",
                {
                    "type": "view:guidance_update",
                    "data": {
                        "view_id": view_id,
                        "guidance": guidance
                    }
                }
            )

            logger.debug(f"Updated guidance for view {view_id}")

        except Exception as e:
            logger.error(f"Failed to update view guidance: {e}")

    async def close_view(
        self,
        user_id: str,
        view_id: str,
        session_id: Optional[str] = None
    ):
        """
        Close an active view.

        Args:
            user_id: User ID
            view_id: View ID to close
            session_id: Optional session ID
        """
        if not VIEW_COORDINATION_ENABLED:
            return

        try:
            session_id = session_id or self._get_or_create_session(user_id)

            # Get state
            state = self.db.query(ViewOrchestrationState).filter(
                ViewOrchestrationState.session_id == session_id
            ).first()

            if state:
                # Remove view from active views
                state.active_views = [
                    v for v in state.active_views
                    if v.get("view_id") != view_id
                ]
                state.updated_at = datetime.utcnow()
                self.db.commit()

            # Broadcast view close
            await ws_manager.broadcast(
                f"user:{user_id}",
                {
                    "type": "view:closed",
                    "data": {
                        "view_id": view_id
                    }
                }
            )

            logger.info(f"Closed view {view_id} for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to close view: {e}")

    def _get_or_create_session(self, user_id: str) -> str:
        """Get or create session ID for user."""
        return f"session_{user_id}_{uuid.uuid4().hex[:8]}"

    async def _create_audit(
        self,
        agent_id: str,
        user_id: str,
        session_id: str,
        action: str,
        metadata: Dict[str, Any]
    ):
        """Create canvas audit entry."""
        try:
            audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                agent_id=agent_id,
                agent_execution_id=None,
                user_id=user_id,
                canvas_id=None,
                session_id=session_id,
                component_type="view_orchestrator",
                component_name="view_coordinator",
                action=action,
                audit_metadata=metadata,
                governance_check_passed=True
            )
            self.db.add(audit)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to create audit: {e}")


# Singleton instance helper
def get_view_coordinator(db: Session) -> ViewCoordinator:
    """Get or create view coordinator instance."""
    return ViewCoordinator(db)
