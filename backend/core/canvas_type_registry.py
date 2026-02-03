"""
Canvas Type Registry Service

Central registry for specialized canvas types with metadata, validation,
and governance requirements.

Each canvas type defines:
- Type identifier and metadata
- Supported components
- Available layouts
- Governance requirements
- Agent maturity requirements
"""
import logging
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CanvasType(str, Enum):
    """Supported canvas types."""
    GENERIC = "generic"
    DOCS = "docs"
    EMAIL = "email"
    SHEETS = "sheets"
    ORCHESTRATION = "orchestration"
    TERMINAL = "terminal"
    CODING = "coding"


class MaturityLevel(str, Enum):
    """Agent maturity levels (from governance system)."""
    STUDENT = "student"
    INTERN = "intern"
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"


class CanvasTypeMetadata:
    """Metadata for a canvas type."""
    def __init__(
        self,
        canvas_type: str,
        display_name: str,
        description: str,
        components: List[str],
        layouts: List[str],
        min_maturity: MaturityLevel,
        permissions: Dict[str, List[str]],
        examples: List[str]
    ):
        self.canvas_type = canvas_type
        self.display_name = display_name
        self.description = description
        self.components = components
        self.layouts = layouts
        self.min_maturity = min_maturity
        self.permissions = permissions
        self.examples = examples


class CanvasTypeRegistry:
    """
    Registry for all specialized canvas types.

    Provides validation, metadata lookup, and governance integration
    for canvas types.
    """

    def __init__(self):
        self._types: Dict[str, CanvasTypeMetadata] = {}
        self._initialize_types()

    def _initialize_types(self):
        """Initialize all canvas type definitions."""
        # Generic Canvas (existing)
        self._types[CanvasType.GENERIC] = CanvasTypeMetadata(
            canvas_type=CanvasType.GENERIC,
            display_name="Generic Canvas",
            description="Standard canvas with charts, markdown, and forms",
            components=["line_chart", "bar_chart", "pie_chart", "markdown", "form", "status_panel"],
            layouts=["single_column", "basic_grid", "split_view"],
            min_maturity=MaturityLevel.STUDENT,
            permissions={
                MaturityLevel.STUDENT: ["view", "create"],
                MaturityLevel.INTERN: ["view", "create", "update"],
                MaturityLevel.SUPERVISED: ["view", "create", "update", "delete"],
                MaturityLevel.AUTONOMOUS: ["view", "create", "update", "delete", "share"]
            },
            examples=[
                "Sales performance dashboard",
                "Analytics report",
                "Data visualization",
                "Summary presentation"
            ]
        )

        # Documentation Canvas
        self._types[CanvasType.DOCS] = CanvasTypeMetadata(
            canvas_type=CanvasType.DOCS,
            display_name="Documentation Canvas",
            description="Rich text editing, collaborative docs, version history",
            components=["rich_editor", "version_history", "comment_thread", "table_of_contents"],
            layouts=["document", "split_view", "focus"],
            min_maturity=MaturityLevel.INTERN,
            permissions={
                MaturityLevel.INTERN: ["view", "create"],
                MaturityLevel.SUPERVISED: ["view", "create", "update", "comment"],
                MaturityLevel.AUTONOMOUS: ["view", "create", "update", "comment", "delete", "share"]
            },
            examples=[
                "API documentation",
                "Knowledge base article",
                "Process documentation",
                "Technical specification",
                "Meeting notes"
            ]
        )

        # Email Canvas
        self._types[CanvasType.EMAIL] = CanvasTypeMetadata(
            canvas_type=CanvasType.EMAIL,
            display_name="Email Canvas",
            description="Threaded conversations, compose interface, attachments",
            components=["thread_view", "compose_form", "attachment_preview", "category_bucket"],
            layouts=["inbox", "conversation", "compose"],
            min_maturity=MaturityLevel.SUPERVISED,
            permissions={
                MaturityLevel.SUPERVISED: ["view", "create", "draft"],
                MaturityLevel.AUTONOMOUS: ["view", "create", "draft", "send", "delete", "categorize"]
            },
            examples=[
                "Email campaign",
                "Customer support response",
                "Newsletter management",
                "Bulk email operations"
            ]
        )

        # Spreadsheet Canvas
        self._types[CanvasType.SHEETS] = CanvasTypeMetadata(
            canvas_type=CanvasType.SHEETS,
            display_name="Spreadsheet Canvas",
            description="Grid editing, formulas, charts, pivot tables",
            components=["data_grid", "formula_bar", "chart_embed", "pivot_table"],
            layouts=["sheet", "dashboard", "split_pane"],
            min_maturity=MaturityLevel.INTERN,
            permissions={
                MaturityLevel.INTERN: ["view"],
                MaturityLevel.SUPERVISED: ["view", "edit", "formulas"],
                MaturityLevel.AUTONOMOUS: ["view", "edit", "formulas", "charts", "share", "export"]
            },
            examples=[
                "Financial model",
                "Data analysis",
                "Budget planning",
                "Report generation"
            ]
        )

        # Orchestration Deck Canvas
        self._types[CanvasType.ORCHESTRATION] = CanvasTypeMetadata(
            canvas_type=CanvasType.ORCHESTRATION,
            display_name="Orchestration Deck Canvas",
            description="Agent-driven workflow orchestration with human-in-the-loop guidance. Perfect for student agents learning workflows with meta-agent supervision.",
            components=["kanban_board", "gantt_chart", "workflow_diagram", "timeline_view"],
            layouts=["board", "timeline", "calendar"],
            min_maturity=MaturityLevel.SUPERVISED,
            permissions={
                MaturityLevel.STUDENT: ["view"],
                MaturityLevel.INTERN: ["view", "propose_workflows"],
                MaturityLevel.SUPERVISED: ["view", "propose_workflows", "execute_workflows", "create_tasks"],
                MaturityLevel.AUTONOMOUS: ["view", "propose_workflows", "execute_workflows", "create_tasks", "modify_workflows", "delete"]
            },
            examples=[
                "Student agent learning customer onboarding with meta-agent checkpoints",
                "Intern agent proposing workflow steps for supervisor approval",
                "Supervised agent executing data processing with human oversight",
                "Multi-step agent workflow with progress tracking",
                "Complex goal broken into agent-executable tasks"
            ]
        )

        # Terminal Canvas
        self._types[CanvasType.TERMINAL] = CanvasTypeMetadata(
            canvas_type=CanvasType.TERMINAL,
            display_name="Terminal Canvas",
            description="Command execution, logs, file trees, process monitoring",
            components=["shell_output", "file_tree", "process_list", "log_viewer"],
            layouts=["terminal", "split_shell", "monitor"],
            min_maturity=MaturityLevel.SUPERVISED,
            permissions={
                MaturityLevel.SUPERVISED: ["view", "execute_readonly"],
                MaturityLevel.AUTONOMOUS: ["view", "execute_readonly", "execute_commands", "kill_processes", "file_operations"]
            },
            examples=[
                "Command execution",
                "System monitoring",
                "Log analysis",
                "File management"
            ]
        )

        # Coding Workspace Canvas
        self._types[CanvasType.CODING] = CanvasTypeMetadata(
            canvas_type=CanvasType.CODING,
            display_name="Coding Workspace Canvas",
            description="Code editor, diff views, repository browser, PR reviews",
            components=["code_editor", "diff_view", "repo_browser", "pull_request_review"],
            layouts=["editor", "split_diff", "repo_view"],
            min_maturity=MaturityLevel.SUPERVISED,
            permissions={
                MaturityLevel.SUPERVISED: ["view", "comment"],
                MaturityLevel.AUTONOMOUS: ["view", "comment", "edit_files", "create_pr", "merge_code", "push_changes"]
            },
            examples=[
                "Code development",
                "Pull request review",
                "Debugging session",
                "Repository management"
            ]
        )

    def get_type(self, canvas_type: str) -> Optional[CanvasTypeMetadata]:
        """
        Get metadata for a canvas type.

        Args:
            canvas_type: Canvas type identifier

        Returns:
            CanvasTypeMetadata if found, None otherwise
        """
        return self._types.get(canvas_type)

    def get_all_types(self) -> Dict[str, CanvasTypeMetadata]:
        """Get all registered canvas types."""
        return self._types.copy()

    def validate_canvas_type(self, canvas_type: str) -> bool:
        """
        Validate if a canvas type is registered.

        Args:
            canvas_type: Canvas type identifier

        Returns:
            True if valid, False otherwise
        """
        return canvas_type in self._types

    def validate_component(self, canvas_type: str, component: str) -> bool:
        """
        Validate if a component is supported by a canvas type.

        Args:
            canvas_type: Canvas type identifier
            component: Component type name

        Returns:
            True if supported, False otherwise
        """
        metadata = self.get_type(canvas_type)
        if not metadata:
            return False
        return component in metadata.components

    def validate_layout(self, canvas_type: str, layout: str) -> bool:
        """
        Validate if a layout is supported by a canvas type.

        Args:
            canvas_type: Canvas type identifier
            layout: Layout name

        Returns:
            True if supported, False otherwise
        """
        metadata = self.get_type(canvas_type)
        if not metadata:
            return False
        return layout in metadata.layouts

    def check_governance_permission(
        self,
        canvas_type: str,
        maturity_level: str,
        action: str = "create"
    ) -> bool:
        """
        Check if a maturity level has permission for an action on a canvas type.

        Args:
            canvas_type: Canvas type identifier
            maturity_level: Agent maturity level
            action: Action to check (create, view, update, delete, etc.)

        Returns:
            True if permitted, False otherwise
        """
        metadata = self.get_type(canvas_type)
        if not metadata:
            logger.warning(f"Unknown canvas type: {canvas_type}")
            return False

        # Get allowed actions for this maturity level
        allowed_actions = metadata.permissions.get(maturity_level, [])

        return action in allowed_actions

    def get_min_maturity(self, canvas_type: str) -> Optional[MaturityLevel]:
        """
        Get minimum maturity level required for a canvas type.

        Args:
            canvas_type: Canvas type identifier

        Returns:
            Minimum MaturityLevel if found, None otherwise
        """
        metadata = self.get_type(canvas_type)
        if not metadata:
            return None
        return metadata.min_maturity

    def get_components_for_type(self, canvas_type: str) -> List[str]:
        """
        Get list of supported components for a canvas type.

        Args:
            canvas_type: Canvas type identifier

        Returns:
            List of component names, empty list if type not found
        """
        metadata = self.get_type(canvas_type)
        if not metadata:
            return []
        return metadata.components

    def get_layouts_for_type(self, canvas_type: str) -> List[str]:
        """
        Get list of available layouts for a canvas type.

        Args:
            canvas_type: Canvas type identifier

        Returns:
            List of layout names, empty list if type not found
        """
        metadata = self.get_type(canvas_type)
        if not metadata:
            return []
        return metadata.layouts

    def get_canvas_info(self, canvas_type: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive information about a canvas type.

        Args:
            canvas_type: Canvas type identifier

        Returns:
            Dictionary with canvas type info, or None if not found
        """
        metadata = self.get_type(canvas_type)
        if not metadata:
            return None

        return {
            "type": metadata.canvas_type,
            "display_name": metadata.display_name,
            "description": metadata.description,
            "components": metadata.components,
            "layouts": metadata.layouts,
            "min_maturity": metadata.min_maturity.value,
            "permissions": {
                level: actions for level, actions in metadata.permissions.items()
            },
            "examples": metadata.examples
        }

    def get_all_canvas_info(self) -> List[Dict[str, Any]]:
        """
        Get information about all registered canvas types.

        Returns:
            List of canvas type information dictionaries
        """
        return [
            self.get_canvas_info(canvas_type)
            for canvas_type in self._types.keys()
        ]


# Global registry instance
canvas_type_registry = CanvasTypeRegistry()
