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

from datetime import datetime
import importlib
import inspect
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


def _type_name(annotation: Any) -> str:
    """Render a type annotation as a stable name.

    Python 3.11's ``str(annotation)`` for a plain type yields
    ``"<class 'str'>"`` instead of ``"str"``. Extract the canonical name when
    available; fall back to ``str()`` for complex ``typing`` constructs.
    """
    if annotation is inspect.Parameter.empty:
        return "Any"
    name = getattr(annotation, "__name__", None)
    if name is not None:
        return str(name)
    return str(annotation)


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
        tags: List[str] = None,
        cacheable: bool = False
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
        # R72 Workstream H: idempotent read-only tools may be memoized for
        # ATOM_TOOL_CACHE_TTL seconds. Never True for state-changing tools.
        self.cacheable = cacheable
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
                    "type": _type_name(param.annotation),
                    "default": str(param.default) if param.default != inspect.Parameter.empty else None,
                    "required": param.default == inspect.Parameter.empty
                }
                for name, param in sig.parameters.items()
                if name != 'self'  # Skip self for methods
            },
            "examples": self.examples,
            "author": self.author,
            "tags": self.tags,
            "cacheable": self.cacheable,
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
        tags: List[str] = None,
        cacheable: bool = False
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
            cacheable: True for idempotent read-only tools whose results may
                be memoized for a short TTL (R72 Workstream H). Never True
                for state-changing tools.

        Returns:
            ToolMetadata: Registered tool metadata

        Raises:
            ValueError: If tool already registered
        """
        if name in self._tools:
            logger.warning(f"Tool '{name}' already registered, updating...")

        # Fall back to the function docstring when no explicit description is
        # supplied (test_tool_documentation expects auto-capture).
        if not description:
            description = inspect.getdoc(function) or ""

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
            tags=tags,
            cacheable=cacheable
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

    def get_simplified_tools(self) -> List[Dict[str, Any]]:
        """Return simplified tool definitions for the agent loop / OpenAI converter.

        Produces the same ``{name, description, parameters}`` shape that
        ``integrations.mcp_service.get_all_tools`` renders for action_registry
        tools (param name -> ``"<type> (optional)"``), so a chat agent can
        enumerate core tools alongside ontology actions.
        """
        simplified = []
        for metadata in self._tools.values():
            parameters = {}
            for p_name, p_info in metadata.to_dict()["parameters"].items():
                p_type = p_info.get("type", "string")
                if not p_info.get("required"):
                    p_type = f"{p_type} (optional)"
                parameters[p_name] = p_type
            simplified.append({
                "name": metadata.name,
                "description": metadata.description,
                "parameters": parameters,
            })
        return simplified

    def discover_tools(self, tool_modules: List[str] = None) -> int:
        """
        Automatically discover and register tools from modules.

        Args:
            tool_modules: List of module names to scan (e.g., ['tools.canvas_tool'])
                         If None, scans all tools in backend/tools/

        Returns:
            Number of tools discovered and registered
        """
        discovered_count = 0

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

                    # Infer complexity from function name. The CRITICAL check
                    # must come FIRST: "execute_command" also contains
                    # "execute" and "delete" also matched the HIGH branch, so
                    # the CRITICAL tier was unreachable (auto-discovered
                    # command-execution tools were gated SUPERVISED instead of
                    # AUTONOMOUS).
                    complexity = 2  # Default to MODERATE
                    if any(keyword in name for keyword in ["execute_command", "deploy"]):
                        complexity = 4  # CRITICAL
                    elif any(keyword in name for keyword in ["present", "get", "read", "fetch", "list"]):
                        complexity = 1  # LOW
                    elif any(keyword in name for keyword in ["create", "update", "send", "post", "execute", "delete"]):
                        complexity = 3  # HIGH

                    # Infer maturity from complexity
                    maturity_map = {1: "STUDENT", 2: "INTERN", 3: "SUPERVISED", 4: "AUTONOMOUS"}
                    maturity_required = maturity_map.get(complexity, "INTERN")

                    # R72 Workstream H: heuristic for idempotent read-only
                    # tools (safe to memoize briefly). Conservative — only
                    # read/list/get/fetch/search verbs are flagged; mutating
                    # verbs (create/update/send/delete/execute) stay uncached.
                    cacheable = any(
                        keyword in name for keyword in ["read", "get", "fetch", "list", "search"]
                    ) and not any(
                        keyword in name for keyword in ["write", "create", "update", "delete", "send"]
                    )

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
                        tags=[category, "auto-discovered"],
                        cacheable=cacheable
                    )

                    discovered_count += 1
                    logger.debug(f"Auto-registered tool: {name} from {module_name}")

            except Exception as e:
                logger.error(f"Failed to discover tools from {module_name}: {e}")

        self._initialized = True
        logger.info(f"Tool discovery complete. Discovered {discovered_count} new tools. Total tools: {len(self._tools)}")

        return discovered_count

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
        self._register_productivity_tools()
        self._register_memory_tools()
        # Integration memory index: structure search + just-in-time file
        # ingestion across connected drives and record apps (universal —
        # adapters in core/drive_tree_ingestion.py).
        self._register_integration_index_tools()
        # B10: data-analysis & predictive tools carry explicit metadata that
        # the auto-discovery inference cannot recover (e.g. analyze_data is
        # SUPERVISED/3, not INTERN/2, because it runs arbitrary sandboxed
        # code; forecast/run_model live in predictive_tools.py which the
        # *_tool.py discovery glob never matches). Wire them here so the
        # production registry reflects their real governance surface.
        self._register_data_tools()
        # AgentRadio lateral coordination: radio.create_thread /
        # send_message / wait_for_mention / read_inbox (mention-first,
        # passive-awareness messaging between team members).
        self._register_agent_radio_tools()
        # Email-canvas attachment CRUD: agent attach/remove/ingest/read of
        # email attachments (governed by the email_attachment autonomy topic;
        # sending WITH attachments stays on the send_email circuit).
        self._register_email_attachment_tools()
        # PDF canvas tools: reads are STUDENT; draft mutations (page ops,
        # merge, submit-review) are INTERN under the pdf_canvas autonomy
        # topic; APPROVE and attach-to-email are SUPERVISED — review and
        # approval follow agent maturity (gated hires propose instead).
        self._register_pdf_canvas_tools()

        logger.info(f"Tool registry initialized with {len(self._tools)} tools")

    def _register_pdf_canvas_tools(self):
        """Register PDF canvas tools with maturity metadata.

        Maturity ladder (mirrors blast radius): reads 1/STUDENT, draft
        mutations 2/INTERN (same tier as update_canvas — reversible, and the
        pdf_canvas autonomy topic can still force proposals), lifecycle
        approval + email handoff 3/SUPERVISED (an INTERN that reaches them
        proposes; a human confirms).
        """

        pdf_canvas_tools = [
            ("pdf_canvas_get_state", 1, "STUDENT",
             "Read a PDF canvas's state (filename, page count, lifecycle, versions)", True),
            ("pdf_canvas_read_text", 1, "STUDENT",
             "Read a PDF canvas's per-page extracted TEXT — never raw bytes", True),
            ("pdf_canvas_list_versions", 1, "STUDENT",
             "List a PDF canvas's version history (hash, action, author, time)", True),
            ("pdf_canvas_get_form_fields", 1, "STUDENT",
             "List a PDF canvas's AcroForm fields (name, type, current value)", True),
            ("pdf_canvas_apply_page_ops", 2, "INTERN",
             "Commit a page map (reorder/delete/rotate) to a PDF canvas as a new version", False),
            ("pdf_canvas_merge_canvas", 2, "INTERN",
             "Append every page of another PDF canvas onto this one", False),
            ("pdf_canvas_submit_for_review", 2, "INTERN",
             "Move a PDF canvas from drafting to in_review (requests approval)", False),
            ("pdf_canvas_set_form_fields", 2, "INTERN",
             "Fill AcroForm field values (fields stay interactive until flattened)", False),
            ("pdf_canvas_flatten", 2, "INTERN",
             "Burn form values into the content and strip the interactive layer", False),
            ("pdf_canvas_annotate", 2, "INTERN",
             "Add real PDF annotations (note/freetext/rect)", False),
            ("pdf_canvas_generate_from_data", 2, "INTERN",
             "Generate a NEW PDF canvas from business data (quote/invoice/letter template)", False),
            ("pdf_canvas_approve", 3, "SUPERVISED",
             "Approve a PDF canvas — content becomes immutable until reopened", False),
            ("pdf_canvas_attach_to_email", 3, "SUPERVISED",
             "Stage the current version onto an email draft (flatten option; send stays on the email HITL circuit)", False),
            ("pdf_canvas_redact", 3, "SUPERVISED",
             "TRUE redaction: permanently remove exact text (content-stream removal + verification)", False),
            ("pdf_canvas_stamp_signature", 3, "SUPERVISED",
             "Stamp the internal signature (text + attribution) on a page", False),
            ("pdf_canvas_archive_to_onedrive", 3, "SUPERVISED",
             "Archive the current version to the owner's OneDrive", False),
            ("pdf_canvas_send_to_docusign", 3, "SUPERVISED",
             "Send the current version out for external signing via the DocuSign envelope API", False),
        ]

        for name, complexity, maturity, description, cacheable in pdf_canvas_tools:
            try:
                func = self._get_function("tools.pdf_canvas_tool", name)
                if not func:
                    continue
                params: Dict[str, Any] = {
                    "user_id": {"type": "str", "description": "Owning user id"},
                    "canvas_id": {"type": "str", "description": "PDF canvas id"},
                    "agent_id": {"type": "str", "optional": True, "description": "Agent id for audit + maturity gate"},
                }
                if name == "pdf_canvas_read_text":
                    params = {
                        "user_id": {"type": "str", "description": "Owning user id"},
                        "canvas_id": {"type": "str", "description": "PDF canvas id"},
                        "max_chars": {"type": "int", "optional": True, "description": "Cap on returned text (default 8000)"},
                    }
                elif name == "pdf_canvas_apply_page_ops":
                    params.update({
                        "pages": {"type": "List[Dict]", "description": "Page map: [{src_index, rotation 0|90|180|270}] — order/omission/absolute rotation"},
                        "base_hash": {"type": "str", "optional": True, "description": "Version hash the map was computed against (conflict guard)"},
                        "reasoning": {"type": "str", "optional": True, "description": "Why — shown to the human on a proposal"},
                    })
                elif name == "pdf_canvas_merge_canvas":
                    params.update({
                        "from_canvas_id": {"type": "str", "description": "Source PDF canvas id (same owner)"},
                        "reasoning": {"type": "str", "optional": True, "description": "Why — shown to the human on a proposal"},
                    })
                elif name == "pdf_canvas_set_form_fields":
                    params.update({
                        "values": {"type": "Dict", "description": "{field_name: value} — unknown names are refused"},
                        "base_hash": {"type": "str", "optional": True, "description": "Version hash the fields were read against"},
                        "reasoning": {"type": "str", "optional": True, "description": "Why — shown to the human on a proposal"},
                    })
                elif name == "pdf_canvas_annotate":
                    params.update({
                        "items": {"type": "List[Dict]", "description": "[{page, kind: note|freetext|rect, rect: [x0,y0,x1,y1], text?}]"},
                        "reasoning": {"type": "str", "optional": True, "description": "Why — shown to the human on a proposal"},
                    })
                elif name == "pdf_canvas_redact":
                    params.update({
                        "items": {"type": "List[Dict]", "description": "[{page, text}] — exact text to remove permanently"},
                        "reasoning": {"type": "str", "optional": True, "description": "Why — shown to the human on a proposal"},
                    })
                elif name == "pdf_canvas_stamp_signature":
                    params = {
                        "user_id": {"type": "str", "description": "Owning user id"},
                        "canvas_id": {"type": "str", "description": "PDF canvas id"},
                        "signature_lines": {"type": "List[str]", "description": "Signer's signature text lines"},
                        "page": {"type": "int", "optional": True, "description": "0-based page index (default 0)"},
                        "rect": {"type": "List[float]", "optional": True, "description": "[x0,y0,x1,y1] PDF coordinates"},
                        "label": {"type": "str", "optional": True, "description": "Attribution line (date/name)"},
                        "reasoning": {"type": "str", "optional": True, "description": "Why — shown to the human on a proposal"},
                        "agent_id": {"type": "str", "optional": True, "description": "Agent id for audit + maturity gate"},
                    }
                elif name == "pdf_canvas_generate_from_data":
                    params = {
                        "user_id": {"type": "str", "description": "Owning user id"},
                        "template": {"type": "str", "description": "quote | invoice | letter"},
                        "doc": {"type": "Dict", "description": "{company, customer, items: [{description, amount}], body}"},
                        "title": {"type": "str", "optional": True, "description": "Canvas/PDF title"},
                        "reasoning": {"type": "str", "optional": True, "description": "Why — shown to the human on a proposal"},
                        "agent_id": {"type": "str", "optional": True, "description": "Agent id for audit + maturity gate"},
                    }
                elif name == "pdf_canvas_archive_to_onedrive":
                    params.update({
                        "folder_path": {"type": "str", "optional": True, "description": "OneDrive folder (root when empty)"},
                        "reasoning": {"type": "str", "optional": True, "description": "Why — shown to the human on a proposal"},
                    })
                elif name == "pdf_canvas_send_to_docusign":
                    params.update({
                        "signer_email": {"type": "str", "description": "External signer's email"},
                        "signer_name": {"type": "str", "description": "External signer's name"},
                        "reasoning": {"type": "str", "optional": True, "description": "Why — shown to the human on a proposal"},
                    })
                elif name in ("pdf_canvas_submit_for_review", "pdf_canvas_approve", "pdf_canvas_flatten"):
                    params = {
                        "user_id": {"type": "str", "description": "Owning user id"},
                        "canvas_id": {"type": "str", "description": "PDF canvas id"},
                        "reasoning": {"type": "str", "optional": True, "description": "Why — shown to the human on a proposal"},
                        "agent_id": {"type": "str", "optional": True, "description": "Agent id for audit + maturity gate"},
                    }
                elif name == "pdf_canvas_attach_to_email":
                    params.update({
                        "email_canvas_id": {"type": "str", "optional": True, "description": "Target email canvas (omit to create a fresh draft)"},
                        "flatten": {"type": "bool", "optional": True, "description": "Stage a flattened copy (form values burned in) without mutating the canvas"},
                        "reasoning": {"type": "str", "optional": True, "description": "Why — shown to the human on a proposal"},
                    })

                self.register(
                    name=name,
                    function=func,
                    version="1.0.0",
                    description=description,
                    category="canvas",
                    complexity=complexity,
                    maturity_required=maturity,
                    dependencies=[],
                    parameters=params,
                    examples=[{
                        "description": description,
                        "code": f"await {name}(user_id='user-1', canvas_id='canvas-1')",
                    }],
                    author="Atom Team",
                    tags=["canvas", "pdf", "document"],
                )
            except Exception as e:
                logger.warning(f"Failed to register pdf canvas tool {name}: {e}")

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

        # read_canvas
        self.register(
            name="read_canvas",
            function=self._get_function("tools.canvas_crud_tool", "read_canvas"),
            version="1.0.0",
            description="Read the current content of a canvas by ID (any canvas type)",
            category="canvas",
            complexity=1,
            maturity_required="STUDENT",
            dependencies=[],
            parameters={
                "user_id": {"type": "str", "description": "User requesting the action"},
                "canvas_id": {"type": "str", "description": "Canvas ID to read"},
            },
            author="Atom Team",
            tags=["canvas", "read", "crud", "NEW"],
            cacheable=True  # idempotent read — safe to memoize briefly
        )

        # update_canvas_content
        self.register(
            name="update_canvas_content",
            function=self._get_function("tools.canvas_crud_tool", "update_canvas_content"),
            version="1.0.0",
            description="Update the content of an existing canvas (any type: sheets, email, docs, etc.)",
            category="canvas",
            complexity=2,
            maturity_required="INTERN",
            dependencies=["websockets"],
            parameters={
                "user_id": {"type": "str", "description": "User requesting the action"},
                "canvas_id": {"type": "str", "description": "Canvas ID to update"},
                "content": {"type": "any", "description": "New content"},
                "canvas_type": {"type": "str", "optional": True, "description": "Canvas type"},
                "title": {"type": "str", "optional": True, "description": "New title"},
            },
            author="Atom Team",
            tags=["canvas", "update", "crud", "NEW"]
        )

        # delete_canvas
        self.register(
            name="delete_canvas",
            function=self._get_function("tools.canvas_crud_tool", "delete_canvas"),
            version="1.0.0",
            description="Delete (close) a specific canvas by ID",
            category="canvas",
            complexity=1,
            maturity_required="STUDENT",
            dependencies=["websockets"],
            parameters={
                "user_id": {"type": "str", "description": "User requesting the action"},
                "canvas_id": {"type": "str", "description": "Canvas ID to delete"},
            },
            author="Atom Team",
            tags=["canvas", "delete", "crud", "NEW"]
        )

        # list_canvases
        self.register(
            name="list_canvases",
            function=self._get_function("tools.canvas_crud_tool", "list_canvases"),
            version="1.0.0",
            description="List all canvases for a user, optionally filtered by type",
            category="canvas",
            complexity=1,
            maturity_required="STUDENT",
            dependencies=[],
            parameters={
                "user_id": {"type": "str", "description": "User requesting the action"},
                "canvas_type": {"type": "str", "optional": True, "description": "Filter by type"},
                "include_deleted": {"type": "bool", "optional": True, "description": "Include deleted"},
            },
            author="Atom Team",
            tags=["canvas", "list", "crud", "NEW"],
            cacheable=True  # idempotent list — safe to memoize briefly
        )

    def _register_email_attachment_tools(self):
        """Register email-canvas attachment tools with metadata.

        Reads are complexity 1 (STUDENT); draft mutations are 2 (INTERN,
        same tier as update_canvas — attaching to a draft is reversible).
        Sending WITH attachments stays gated by send_email (3) on the send
        circuit; per-user mode control is the email_attachment autonomy topic.
        """

        email_attachment_tools = [
            (
                "email_attachment_list",
                1,
                "STUDENT",
                "List attachments on an email canvas draft (metadata only — no file content)",
                True,
            ),
            (
                "email_attachment_get_text",
                1,
                "STUDENT",
                "Read the extracted TEXT of an email attachment (PDF/DOCX/XLSX/text) — never raw bytes",
                True,
            ),
            (
                "email_attachment_stage_file",
                2,
                "INTERN",
                "Stage a small generated file (<=256KB) onto the email draft as an attachment",
                False,
            ),
            (
                "email_attachment_attach",
                2,
                "INTERN",
                "Attach a file from a received email in the thread onto the outgoing draft",
                False,
            ),
            (
                "email_attachment_remove",
                2,
                "INTERN",
                "Remove an attachment from the email draft (staged files deleted; received ones detached)",
                False,
            ),
            (
                "email_attachment_ingest",
                2,
                "INTERN",
                "Index an email attachment's text into memory so its content is recallable across chats",
                False,
            ),
        ]

        for name, complexity, maturity, description, cacheable in email_attachment_tools:
            try:
                func = self._get_function("tools.email_attachment_tool", name)
                if not func:
                    continue
                params: Dict[str, Any] = {
                    "user_id": {"type": "str", "description": "Owning user id"},
                    "canvas_id": {"type": "str", "description": "Email canvas id"},
                }
                if name == "email_attachment_get_text":
                    params.update({
                        "attachment_id": {"type": "str", "description": "Attachment record id"},
                        "max_chars": {"type": "int", "optional": True, "description": "Cap on returned text (default 8000)"},
                    })
                elif name == "email_attachment_stage_file":
                    params.update({
                        "filename": {"type": "str", "description": "File name (extension must be allowed)"},
                        "content_b64": {"type": "str", "description": "Base64 file content (<=256KB)"},
                        "content_type": {"type": "str", "optional": True, "description": "MIME type"},
                        "agent_id": {"type": "str", "optional": True, "description": "Agent id for audit"},
                    })
                elif name in ("email_attachment_attach",):
                    params.update({
                        "message_id": {"type": "str", "description": "Thread message the file arrived on"},
                        "attachment_id": {"type": "str", "description": "Attachment id within that message"},
                        "agent_id": {"type": "str", "optional": True, "description": "Agent id for audit"},
                    })
                elif name in ("email_attachment_remove", "email_attachment_ingest"):
                    params.update({
                        "attachment_id": {"type": "str", "description": "Attachment record id"},
                        "agent_id": {"type": "str", "optional": True, "description": "Agent id for audit"},
                    })

                self.register(
                    name=name,
                    function=func,
                    version="1.0.0",
                    description=description,
                    category="email",
                    complexity=complexity,
                    maturity_required=maturity,
                    dependencies=[],
                    parameters=params,
                    author="Atom Team",
                    tags=["email", "attachment", "canvas"],
                    cacheable=cacheable,
                )
            except Exception as e:
                logger.warning(f"Could not register email attachment tool {name}: {e}")

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

    def _register_productivity_tools(self):
        """Register productivity tools (Calendar, Notion) with metadata."""
        try:
            from tools.calendar_tool import register_calendar_tool
            register_calendar_tool(self)
        except Exception as e:
            logger.warning(f"Could not register calendar tool: {e}")

        try:
            from tools.productivity_tool import register_notion_tool
            register_notion_tool(self)
        except Exception as e:
            logger.warning(f"Could not register notion tool: {e}")

    def _register_memory_tools(self):
        """Register agent-callable memory tools (remember / forget)."""
        try:
            from tools.memory_tool import register_memory_tool
            register_memory_tool(self)
        except Exception as e:
            logger.warning(f"Could not register memory tools: {e}")

    def _register_integration_index_tools(self):
        """Register integration-memory tools (structure search + JIT ingest)."""
        try:
            from tools.drive_tool import register_drive_tools
            register_drive_tools(self)
        except Exception as e:
            logger.warning(f"Could not register integration index tools: {e}")

    def _register_data_tools(self):
        """Register data-analysis & predictive-modeling tools with explicit
        metadata (B10).

        Auto-discovery infers analyze_data as INTERN/2 and misses
        forecast/run_model entirely (predictive_tools.py doesn't match the
        *_tool.py glob). These explicit registrations override the inferred
        entries with the correct governance metadata."""
        try:
            from tools.data_analysis_tool import register_data_analysis_tools
            register_data_analysis_tools(self)
        except Exception as e:
            logger.warning(f"Could not register data analysis tools: {e}")
        try:
            from tools.predictive_tools import register_predictive_tools
            register_predictive_tools(self)
        except Exception as e:
            logger.warning(f"Could not register predictive tools: {e}")

    def _register_agent_radio_tools(self):
        """Register lateral coordination tools (radio.* — AgentRadio-style
        mention-first peer messaging between agents on a shared thread)."""
        try:
            from tools.agent_radio_tool import register_agent_radio_tools
            register_agent_radio_tools(self)
        except Exception as e:
            logger.warning(f"Could not register agent radio tools: {e}")

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
