"""
Tool Registry System for Atom

Provides tool discovery, metadata management, and versioning for all available tools.
Similar to ClawHub but optimized for Atom's governance-focused architecture.

Features:
- Automatic tool discovery
- Tool metadata (name, version, description, complexity)
- Governance integration (maturity requirements)
- Dependency tracking
- Tool health monitoring
"""

import logging
import importlib
import inspect
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class ToolMetadata:
    """Metadata for a registered tool."""

    def __init__(
        self,
        name: str,
        function: Callable,
        version: str = "1.0.0",
        description: str = "",
        category: str = "general",
        complexity: int = 2,  # 1=LOW, 2=MODERATE, 3=HIGH, 4=CRITICAL
        maturity_required: str = "INTERN",  # STUDENT, INTERN, SUPERVISED, AUTONOMOUS
        dependencies: List[str] = None,
        parameters: Dict[str, Any] = None,
        examples: List[Dict[str, Any]] = None,
        author: str = "Atom Team",
        tags: List[str] = None
    ):
        self.name = name
        self.function = function
        self.version = version
        self.description = description
        self.category = category
        self.complexity = complexity
        self.maturity_required = maturity_required
        self.dependencies = dependencies or []
        self.parameters = parameters or {}
        self.examples = examples or []
        self.author = author
        self.tags = tags or []
        self.registered_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        # Extract function signature
        sig = inspect.signature(self.function)

        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "category": self.category,
            "complexity": self.complexity,
            "maturity_required": self.maturity_required,
            "dependencies": self.dependencies,
            "parameters": {
                name: {
                    "type": str(param.annotation) if param.annotation != inspect.Parameter.empty else "Any",
                    "default": str(param.default) if param.default != inspect.Parameter.empty else None,
                    "required": param.default == inspect.Parameter.empty
                }
                for name, param in sig.parameters.items()
                if name != 'self'  # Skip self for methods
            },
            "examples": self.examples,
            "author": self.author,
            "tags": self.tags,
            "registered_at": self.registered_at.isoformat(),
            "function_path": f"{self.function.__module__}.{self.function.__name__}"
        }


class ToolRegistry:
    """
    Central registry for all Atom tools.

    Automatically discovers and manages tools with metadata,
    governance requirements, and dependencies.
    """

    def __init__(self):
        self._tools: Dict[str, ToolMetadata] = {}
        self._categories: Dict[str, List[str]] = {}
        self._initialized = False

    def register(
        self,
        name: str,
        function: Callable,
        version: str = "1.0.0",
        description: str = "",
        category: str = "general",
        complexity: int = 2,
        maturity_required: str = "INTERN",
        dependencies: List[str] = None,
        parameters: Dict[str, Any] = None,
        examples: List[Dict[str, Any]] = None,
        author: str = "Atom Team",
        tags: List[str] = None
    ) -> ToolMetadata:
        """
        Register a tool with metadata.

        Args:
            name: Unique tool name
            function: Callable function
            version: Tool version (semantic versioning)
            description: Tool description
            category: Tool category (canvas, browser, device, etc.)
            complexity: Action complexity (1-4)
            maturity_required: Minimum agent maturity level
            dependencies: List of required dependencies
            parameters: Parameter descriptions
            examples: Usage examples
            author: Tool author
            tags: Search tags

        Returns:
            ToolMetadata: Registered tool metadata

        Raises:
            ValueError: If tool already registered
        """
        if name in self._tools:
            logger.warning(f"Tool '{name}' already registered, updating...")

        metadata = ToolMetadata(
            name=name,
            function=function,
            version=version,
            description=description,
            category=category,
            complexity=complexity,
            maturity_required=maturity_required,
            dependencies=dependencies,
            parameters=parameters,
            examples=examples,
            author=author,
            tags=tags
        )

        self._tools[name] = metadata

        # Update category index
        if category not in self._categories:
            self._categories[category] = []
        if name not in self._categories[category]:
            self._categories[category].append(name)

        logger.info(f"Registered tool: {name} v{version} ({category})")
        return metadata

    def get(self, name: str) -> Optional[ToolMetadata]:
        """Get tool metadata by name."""
        return self._tools.get(name)

    def get_function(self, name: str) -> Optional[Callable]:
        """Get tool function by name."""
        metadata = self._tools.get(name)
        return metadata.function if metadata else None

    def list_all(self) -> List[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def list_by_category(self, category: str) -> List[str]:
        """List tools by category."""
        return self._categories.get(category, [])

    def list_by_maturity(self, maturity: str) -> List[str]:
        """List tools accessible by maturity level."""
        maturity_order = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]

        try:
            maturity_idx = maturity_order.index(maturity)
        except ValueError:
            logger.warning(f"Invalid maturity level: {maturity}")
            return []

        accessible_maturities = maturity_order[:maturity_idx + 1]

        return [
            name for name, metadata in self._tools.items()
            if metadata.maturity_required in accessible_maturities
        ]

    def search(self, query: str) -> List[ToolMetadata]:
        """Search tools by name, description, or tags."""
        query_lower = query.lower()

        return [
            metadata for metadata in self._tools.values()
            if (
                query_lower in metadata.name.lower() or
                query_lower in metadata.description.lower() or
                any(query_lower in tag.lower() for tag in metadata.tags)
            )
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        return {
            "total_tools": len(self._tools),
            "categories": {
                category: len(tools)
                for category, tools in self._categories.items()
            },
            "complexity_distribution": {
                "LOW": len([t for t in self._tools.values() if t.complexity == 1]),
                "MODERATE": len([t for t in self._tools.values() if t.complexity == 2]),
                "HIGH": len([t for t in self._tools.values() if t.complexity == 3]),
                "CRITICAL": len([t for t in self._tools.values() if t.complexity == 4]),
            },
            "maturity_distribution": {
                maturity: len([t for t in self._tools.values() if t.maturity_required == maturity])
                for maturity in ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]
            }
        }

    def export_all(self) -> List[Dict[str, Any]]:
        """Export all tools as dictionaries."""
        return [metadata.to_dict() for metadata in self._tools.values()]

    def discover_tools(self, tool_modules: List[str] = None):
        """
        Automatically discover and register tools from modules.

        Args:
            tool_modules: List of module names to scan (e.g., ['tools.canvas_tool'])
                         If None, scans all tools in backend/tools/
        """
        if tool_modules is None:
            # Default to scanning all tool modules
            tools_dir = Path(__file__).parent
            tool_modules = [
                f"tools.{file.stem}" for file in tools_dir.glob("*_tool.py")
                if not file.name.startswith("_")
            ]

        logger.info(f"Discovering tools from modules: {tool_modules}")

        for module_name in tool_modules:
            try:
                module = importlib.import_module(module_name)

                # Look for async functions with specific naming patterns
                for name, obj in inspect.getmembers(module, inspect.isfunction):
                    # Look for public async functions
                    if name.startswith("_"):
                        continue

                    if not inspect.iscoroutinefunction(obj):
                        continue

                    # Skip already registered
                    if name in self._tools:
                        continue

                    # Auto-register with default metadata
                    # In production, tools should explicitly register with proper metadata
                    category = module_name.replace("tools.", "").replace("_tool", "")

                    # Infer complexity from function name
                    complexity = 2  # Default to MODERATE
                    if any(keyword in name for keyword in ["present", "get", "read", "fetch", "list"]):
                        complexity = 1  # LOW
                    elif any(keyword in name for keyword in ["create", "update", "send", "post", "execute", "delete"]):
                        complexity = 3  # HIGH
                    elif any(keyword in name for keyword in ["execute_command", "delete", "deploy"]):
                        complexity = 4  # CRITICAL

                    # Infer maturity from complexity
                    maturity_map = {1: "STUDENT", 2: "INTERN", 3: "SUPERVISED", 4: "AUTONOMOUS"}
                    maturity_required = maturity_map.get(complexity, "INTERN")

                    # Extract docstring
                    description = inspect.getdoc(obj) or ""

                    self.register(
                        name=name,
                        function=obj,
                        version="1.0.0",
                        description=description,
                        category=category,
                        complexity=complexity,
                        maturity_required=maturity_required,
                        author="Atom Team (Auto-discovered)",
                        tags=[category, "auto-discovered"]
                    )

                    logger.debug(f"Auto-registered tool: {name} from {module_name}")

            except Exception as e:
                logger.error(f"Failed to discover tools from {module_name}: {e}")

        self._initialized = True
        logger.info(f"Tool discovery complete. Total tools: {len(self._tools)}")

    def initialize(self):
        """Initialize the tool registry with default tools."""
        if self._initialized:
            logger.info("Tool registry already initialized")
            return

        logger.info("Initializing tool registry...")

        # Discover all tools
        self.discover_tools()

        # Manually register key tools with detailed metadata
        self._register_canvas_tools()
        self._register_browser_tools()
        self._register_device_tools()

        logger.info(f"Tool registry initialized with {len(self._tools)} tools")

    def _register_canvas_tools(self):
        """Register canvas presentation tools with metadata."""

        # present_chart
        self.register(
            name="present_chart",
            function=self._get_function("tools.canvas_tool", "present_chart"),
            version="1.2.0",  # Updated for session isolation
            description="Present charts (line, bar, pie) to user canvas with governance tracking",
            category="canvas",
            complexity=1,  # LOW - read-only visualization
            maturity_required="STUDENT",
            dependencies=["websockets"],
            parameters={
                "user_id": {"type": "str", "description": "User to present to"},
                "chart_type": {"type": "str", "description": "line_chart, bar_chart, or pie_chart"},
                "data": {"type": "List[Dict]", "description": "Chart data points"},
                "title": {"type": "str", "optional": True, "description": "Chart title"},
                "agent_id": {"type": "str", "optional": True, "description": "Agent ID for governance"},
                "session_id": {"type": "str", "optional": True, "description": "Session ID for isolation"}
            },
            examples=[
                {
                    "description": "Present a sales trend line chart",
                    "code": "await present_chart(user_id='user-1', chart_type='line_chart', data=[{'x': 'Jan', 'y': 100}], title='Sales Trend')"
                }
            ],
            author="Atom Team",
            tags=["canvas", "visualization", "chart", "presentation"]
        )

        # present_markdown
        self.register(
            name="present_markdown",
            function=self._get_function("tools.canvas_tool", "present_markdown"),
            version="1.2.0",
            description="Present markdown content to user canvas with governance tracking",
            category="canvas",
            complexity=1,
            maturity_required="STUDENT",
            dependencies=["websockets"],
            parameters={
                "user_id": {"type": "str", "description": "User to present to"},
                "content": {"type": "str", "description": "Markdown formatted content"},
                "title": {"type": "str", "optional": True, "description": "Content title"},
                "agent_id": {"type": "str", "optional": True, "description": "Agent ID for governance"},
                "session_id": {"type": "str", "optional": True, "description": "Session ID for isolation"}
            },
            examples=[
                {
                    "description": "Present a report",
                    "code": "await present_markdown(user_id='user-1', content='# Report\\n\\nSummary here...', title='Q4 Report')"
                }
            ],
            author="Atom Team",
            tags=["canvas", "markdown", "presentation", "document"]
        )

        # present_form
        self.register(
            name="present_form",
            function=self._get_function("tools.canvas_tool", "present_form"),
            version="1.2.0",
            description="Present interactive forms to user canvas with governance tracking",
            category="canvas",
            complexity=2,  # MODERATE - form presentation
            maturity_required="INTERN",
            dependencies=["websockets"],
            parameters={
                "user_id": {"type": "str", "description": "User to present to"},
                "form_schema": {"type": "Dict", "description": "Form schema with fields and validation"},
                "title": {"type": "str", "optional": True, "description": "Form title"},
                "agent_id": {"type": "str", "optional": True, "description": "Agent ID for governance"},
                "session_id": {"type": "str", "optional": True, "description": "Session ID for isolation"}
            },
            examples=[
                {
                    "description": "Present a data collection form",
                    "code": "await present_form(user_id='user-1', form_schema={'fields': [{'name': 'email', 'type': 'email', 'required': True}]}, title='Contact Info')"
                }
            ],
            author="Atom Team",
            tags=["canvas", "form", "interaction", "input"]
        )

        # update_canvas (NEW)
        self.register(
            name="update_canvas",
            function=self._get_function("tools.canvas_tool", "update_canvas"),
            version="1.0.0",
            description="Update existing canvas without re-presenting (bidirectional updates)",
            category="canvas",
            complexity=2,  # MODERATE - canvas update
            maturity_required="INTERN",
            dependencies=["websockets"],
            parameters={
                "user_id": {"type": "str", "description": "User to update"},
                "canvas_id": {"type": "str", "description": "Canvas ID to update"},
                "updates": {"type": "Dict", "description": "Update data (e.g., {'data': [...], 'title': 'New'})"},
                "agent_id": {"type": "str", "optional": True, "description": "Agent ID for governance"},
                "session_id": {"type": "str", "optional": True, "description": "Session ID for isolation"}
            },
            examples=[
                {
                    "description": "Update chart data dynamically",
                    "code": "await update_canvas(user_id='user-1', canvas_id='canvas-123', updates={'data': [{'x': 1, 'y': 20}]})"
                }
            ],
            author="Atom Team",
            tags=["canvas", "update", "dynamic", "bidirectional", "NEW"]
        )

    def _register_browser_tools(self):
        """Register browser automation tools with metadata."""

        browser_functions = [
            "browser_create_session",
            "browser_navigate",
            "browser_screenshot",
            "browser_fill_form",
            "browser_click",
            "browser_extract_text",
            "browser_execute_script",
            "browser_close_session",
            "browser_get_info"
        ]

        for func_name in browser_functions:
            try:
                func = self._get_function("tools.browser_tool", func_name)
                if func:
                    # Determine complexity based on function
                    complexity = 2  # Default for browser actions
                    if "execute" in func_name or "close" in func_name:
                        complexity = 3  # HIGH

                    self.register(
                        name=func_name,
                        function=func,
                        version="1.0.0",
                        description=inspect.getdoc(func) or f"Browser automation: {func_name}",
                        category="browser",
                        complexity=complexity,
                        maturity_required="INTERN",  # All browser actions require INTERN+
                        dependencies=["playwright", "websockets"],
                        tags=["browser", "automation", "web", "cdp"]
                    )
            except Exception as e:
                logger.warning(f"Could not register browser tool {func_name}: {e}")

    def _register_device_tools(self):
        """Register device capability tools with metadata."""

        device_functions = [
            ("device_camera_snap", 2, "INTERN"),
            ("device_screen_record_start", 3, "SUPERVISED"),
            ("device_screen_record_stop", 3, "SUPERVISED"),
            ("device_get_location", 2, "INTERN"),
            ("device_send_notification", 2, "INTERN"),
            ("device_execute_command", 4, "AUTONOMOUS"),  # CRITICAL - AUTONOMOUS only
        ]

        for func_name, complexity, maturity in device_functions:
            try:
                func = self._get_function("tools.device_tool", func_name)
                if func:
                    self.register(
                        name=func_name,
                        function=func,
                        version="1.0.0",
                        description=inspect.getdoc(func) or f"Device capability: {func_name}",
                        category="device",
                        complexity=complexity,
                        maturity_required=maturity,
                        dependencies=["websockets", "tauri"],
                        tags=["device", "hardware", "native"]
                    )
            except Exception as e:
                logger.warning(f"Could not register device tool {func_name}: {e}")

    def _get_function(self, module_name: str, function_name: str) -> Optional[Callable]:
        """Get function from module."""
        try:
            module = importlib.import_module(module_name)
            return getattr(module, function_name, None)
        except Exception as e:
            logger.error(f"Failed to get function {module_name}.{function_name}: {e}")
            return None


# Global tool registry instance
_global_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    global _global_registry

    if _global_registry is None:
        _global_registry = ToolRegistry()
        _global_registry.initialize()

    return _global_registry
