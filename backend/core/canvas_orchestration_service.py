"""
Orchestration Deck Canvas Service

Backend service for agent-driven workflow orchestration with human-in-the-loop guidance.
Agents orchestrate multi-step interactions toward end goals while maturing from STUDENT level
with meta-agent supervision to autonomous operation.

Perfect for:
- New agents (STUDENT level) learning workflows with meta-agent guidance
- Agent-driven multi-step processes with human oversight
- Progress tracking as agents mature and gain confidence
- Complex goals requiring coordinated agent actions
"""
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from core.models import CanvasAudit

logger = logging.getLogger(__name__)


class WorkflowTask:
    """Represents a task in a workflow."""
    def __init__(
        self,
        task_id: str,
        title: str,
        status: str = "todo",  # todo, in_progress, done
        assignee: Optional[str] = None,
        due_date: Optional[datetime] = None,
        tags: List[str] = None,
        integrations: List[str] = None  # App integrations involved
    ):
        self.task_id = task_id
        self.title = title
        self.status = status
        self.assignee = assignee
        self.due_date = due_date
        self.tags = tags or []
        self.integrations = integrations or []


class IntegrationNode:
    """Represents an app integration node in a workflow."""
    def __init__(
        self,
        node_id: str,
        app_name: str,
        node_type: str,  # trigger, action, condition
        config: Dict[str, Any] = None,
        position: Optional[Dict] = None
    ):
        self.node_id = node_id
        self.app_name = app_name
        self.node_type = node_type
        self.config = config or {}
        self.position = position or {"x": 0, "y": 0}


class WorkflowConnection:
    """Represents a connection between integration nodes."""
    def __init__(
        self,
        connection_id: str,
        from_node: str,
        to_node: str,
        condition: Optional[str] = None
    ):
        self.connection_id = connection_id
        self.from_node = from_node
        self.to_node = to_node
        self.condition = condition


class OrchestrationCanvasService:
    """
    Service for managing agent-driven orchestration canvases.

    Supports:
    - STUDENT agents learning workflows with meta-agent guidance
    - Agent-driven multi-step processes with human oversight
    - Task and node-based workflow visualization
    - Progress tracking as agents mature to higher levels
    """

    def __init__(self, db: Session):
        self.db = db

    def create_orchestration_canvas(
        self,
        user_id: str,
        title: str,
        canvas_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        layout: str = "board",
        tasks: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new agent-driven orchestration canvas.

        Designed for agents (especially STUDENT level) to orchestrate multi-step
        interactions with human-in-the-loop guidance from meta-agents or users.

        Args:
            user_id: User ID
            title: Canvas title (e.g., "Customer Onboarding Workflow")
            canvas_id: Optional canvas ID
            agent_id: Optional agent ID (STUDENT agents start here)
            layout: Layout (board, timeline, calendar)
            tasks: Optional initial tasks for the workflow

        Returns:
            Dict with canvas details

        Example:
            # Student agent creates onboarding workflow with meta-agent guidance
            service.create_orchestration_canvas(
                user_id="user-1",
                title="Customer Onboarding",
                agent_id="student-agent-1",
                tasks=[
                    {"title": "Send welcome email", "status": "todo", "assignee": "student-agent-1"},
                    {"title": "Schedule training call", "status": "todo", "assignee": "student-agent-1"},
                    {"title": "Meta-agent review", "status": "todo", "assignee": "atom-meta-agent"}
                ]
            )
        """
        try:
            canvas_id = canvas_id or str(uuid.uuid4())

            # Initialize tasks
            task_objects = []
            for task_data in (tasks or []):
                task = WorkflowTask(
                    task_id=str(uuid.uuid4()),
                    title=task_data.get("title", ""),
                    status=task_data.get("status", "todo"),
                    assignee=task_data.get("assignee"),
                    tags=task_data.get("tags", []),
                    integrations=task_data.get("integrations", [])
                )
                task_objects.append(self._task_to_dict(task))

            audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                agent_id=agent_id,
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="orchestration",
                component_type="kanban_board",
                action="create",
                audit_metadata={
                    "title": title,
                    "layout": layout,
                    "tasks": task_objects,
                    "nodes": [],  # Integration nodes
                    "connections": [],  # Node connections
                    "milestones": [],
                    "integrations": []  # Connected apps
                }
            )

            self.db.add(audit)
            self.db.commit()

            logger.info(f"Created orchestration canvas {canvas_id}: {title}")

            return {
                "success": True,
                "canvas_id": canvas_id,
                "title": title,
                "tasks": task_objects
            }

        except Exception as e:
            logger.error(f"Failed to create orchestration canvas: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def add_workflow_node(
        self,
        canvas_id: str,
        user_id: str,
        node_name: str,
        node_type: str,
        config: Dict[str, Any] = None,
        position: Dict[str, int] = None,
        assigned_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add a workflow node to the orchestration.

        Nodes represent steps in an agent-driven workflow:
        - Agent actions (what the agent should do)
        - Human approvals (human-in-the-loop checkpoints)
        - Meta-agent guidance (supervision for student agents)
        - Integrations (app actions when needed)

        Args:
            canvas_id: Canvas ID
            user_id: User ID
            node_name: Node name (e.g., "Send Email", "Meta-Agent Review", "Human Approval")
            node_type: Node type (action, approval, guidance, integration)
            config: Node configuration (goals, parameters, etc.)
            position: Position on canvas {x, y}
            assigned_agent: Optional agent ID responsible for this node

        Returns:
            Dict with node details

        Example:
            # Student agent workflow with meta-agent guidance
            service.add_workflow_node(
                canvas_id=canvas_id,
                user_id="user-1",
                node_name="Draft welcome email",
                node_type="action",
                config={"goal": "Personalized welcome for new customer"},
                assigned_agent="student-agent-1"
            )

            # Meta-agent supervision checkpoint
            service.add_workflow_node(
                canvas_id=canvas_id,
                user_id="user-1",
                node_name="Meta-agent review",
                node_type="guidance",
                config={"check": "Quality, tone, accuracy"},
                assigned_agent="atom-meta-agent"
            )
        """
        try:
            from sqlalchemy import desc

            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "orchestration"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Orchestration canvas not found"}

            metadata = audit.audit_metadata
            nodes = metadata.get("nodes", [])
            integrations = metadata.get("integrations", [])

            # Create workflow node
            node = IntegrationNode(
                node_id=str(uuid.uuid4()),
                app_name=node_name,  # Use node_name as the app/workflow name
                node_type=node_type,
                config=config,
                position=position
            )

            nodes.append(self._node_to_dict(node))

            # Track connected apps
            if node_name not in integrations:
                integrations.append(node_name)
            metadata["integrations"] = integrations
            metadata["nodes"] = nodes

            update_audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="orchestration",
                component_type="workflow_diagram",
                action="add_node",
                audit_metadata=metadata
            )

            self.db.add(update_audit)
            self.db.commit()

            logger.info(f"Added workflow node {node_name} to canvas {canvas_id}")

            return {
                "success": True,
                "node_id": node.node_id,
                "node_name": node_name,
                "message": f"Added {node_name} workflow node"
            }

        except Exception as e:
            logger.error(f"Failed to add integration node: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def connect_nodes(
        self,
        canvas_id: str,
        user_id: str,
        from_node: str,
        to_node: str,
        condition: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Connect two integration nodes.

        Args:
            canvas_id: Canvas ID
            user_id: User ID
            from_node: Source node ID
            to_node: Target node ID
            condition: Optional condition for connection

        Returns:
            Dict with connection details
        """
        try:
            from sqlalchemy import desc

            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "orchestration"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Orchestration canvas not found"}

            metadata = audit.audit_metadata
            connections = metadata.get("connections", [])

            connection = WorkflowConnection(
                connection_id=str(uuid.uuid4()),
                from_node=from_node,
                to_node=to_node,
                condition=condition
            )

            connections.append(self._connection_to_dict(connection))
            metadata["connections"] = connections

            update_audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="orchestration",
                component_type="workflow_diagram",
                action="connect_nodes",
                audit_metadata=metadata
            )

            self.db.add(update_audit)
            self.db.commit()

            return {"success": True, "connection_id": connection.connection_id}

        except Exception as e:
            logger.error(f"Failed to connect nodes: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def add_task(
        self,
        canvas_id: str,
        user_id: str,
        title: str,
        status: str = "todo",
        assignee: Optional[str] = None,
        integrations: List[str] = None
    ) -> Dict[str, Any]:
        """
        Add a task to the workflow.

        Args:
            canvas_id: Canvas ID
            user_id: User ID
            title: Task title
            status: Task status
            assignee: Assignee
            integrations: Associated integrations

        Returns:
            Dict with task details
        """
        try:
            from sqlalchemy import desc

            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "orchestration"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Orchestration canvas not found"}

            metadata = audit.audit_metadata
            tasks = metadata.get("tasks", [])

            task = WorkflowTask(
                task_id=str(uuid.uuid4()),
                title=title,
                status=status,
                assignee=assignee,
                integrations=integrations
            )

            tasks.append(self._task_to_dict(task))
            metadata["tasks"] = tasks

            update_audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="orchestration",
                component_type="kanban_board",
                action="add_task",
                audit_metadata=metadata
            )

            self.db.add(update_audit)
            self.db.commit()

            return {"success": True, "task_id": task.task_id, "title": title}

        except Exception as e:
            logger.error(f"Failed to add task: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def _task_to_dict(self, task: WorkflowTask) -> Dict[str, Any]:
        """Convert task to dict."""
        return {
            "task_id": task.task_id,
            "title": task.title,
            "status": task.status,
            "assignee": task.assignee,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "tags": task.tags,
            "integrations": task.integrations
        }

    def _node_to_dict(self, node: IntegrationNode) -> Dict[str, Any]:
        """Convert node to dict."""
        return {
            "node_id": node.node_id,
            "app_name": node.app_name,
            "node_type": node.node_type,
            "config": node.config,
            "position": node.position
        }

    def _connection_to_dict(self, connection: WorkflowConnection) -> Dict[str, Any]:
        """Convert connection to dict."""
        return {
            "connection_id": connection.connection_id,
            "from_node": connection.from_node,
            "to_node": connection.to_node,
            "condition": connection.condition
        }
