"""MCP tool definitions and handlers.

Each tool wraps an existing atom service (routing, compression, governance,
health). Tools are self-describing (name, description, inputSchema) per the
MCP spec so agents can discover them via tools/list.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MCPTool:
    """A single MCP tool definition + handler."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Callable[..., Any],
    ) -> None:
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.handler = handler

    def to_dict(self) -> Dict[str, Any]:
        """MCP tool/list entry format."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


# --- Tool input schemas (JSON Schema format) -------------------------------

_PROMPT_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string", "description": "The prompt text to route/analyze"},
        "task_type": {"type": "string", "description": "Optional task type hint (chat, code, analysis)"},
    },
    "required": ["prompt"],
}

_TEXT_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string", "description": "The text to compress"},
    },
    "required": ["text"],
}

_NO_INPUT_SCHEMA = {
    "type": "object",
    "properties": {},
}

_BOOLEAN_SCHEMA = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean", "description": "True to enable, False to disable"},
    },
    "required": ["enabled"],
}

_FUSION_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string", "description": "The prompt for fusion generation"},
        "system_instruction": {"type": "string", "description": "Optional system instruction"},
        "task_type": {"type": "string", "description": "Optional task type (must NOT be agentic/extraction)"},
    },
    "required": ["prompt"],
}


# --- Tool handlers ---------------------------------------------------------
# Each handler receives a dict of arguments and returns a dict result.
# Handlers are best-effort: errors are caught and returned as error dicts.


async def _handle_resolve_route(args: Dict[str, Any]) -> Dict[str, Any]:
    """Dry-run routing: show which model+provider atom would pick."""
    try:
        from core.llm.byok_handler import BYOKHandler
        handler = BYOKHandler()
        prompt = args.get("prompt", "")
        task_type = args.get("task_type", "chat")
        complexity = handler.analyze_query_complexity(prompt, task_type)
        options = await handler.get_ranked_providers(complexity, task_type)
        return {
            "complexity": complexity,
            "top_candidates": [
                {"provider": p, "model": m, "rank": i + 1}
                for i, (p, m) in enumerate(options[:5])
            ],
            "total_candidates": len(options),
        }
    except Exception as e:
        return {"error": str(e)}


async def _handle_list_models(args: Dict[str, Any]) -> Dict[str, Any]:
    """List available models with metadata."""
    try:
        from core.llm.byok_handler import BYOKHandler
        handler = BYOKHandler()
        registry = getattr(handler, "_model_registry", {}) or {}
        models = []
        for model_id, spec in registry.items():
            models.append({
                "model_id": model_id,
                "provider": getattr(spec, "provider", "unknown"),
                "quality_score": getattr(spec, "quality_score", 0),
                "cost_per_million": getattr(spec, "cost_per_million", 0),
                "tier": getattr(spec, "tier", "standard"),
            })
        return {"models": models[:50], "total": len(models)}
    except Exception as e:
        return {"error": str(e)}


async def _handle_compress_text(args: Dict[str, Any]) -> Dict[str, Any]:
    """Compress tool/terminal output via RTK engine."""
    try:
        from core.llm.compression import get_compression_pipeline
        text = args.get("text", "")
        result, metrics = get_compression_pipeline().compress_tool_output(text)
        return {
            "compressed_text": result[:500],  # preview
            "metrics": metrics.to_dict(),
        }
    except Exception as e:
        return {"error": str(e)}


async def _handle_set_compression(args: Dict[str, Any]) -> Dict[str, Any]:
    """Toggle compression on/off."""
    try:
        import core.llm.compression as comp
        enabled = args.get("enabled", True)
        comp.COMPRESSION_ENABLED = enabled
        comp.RTK_ENABLED = enabled
        return {"compression_enabled": comp.COMPRESSION_ENABLED}
    except Exception as e:
        return {"error": str(e)}


async def _handle_get_spend(args: Dict[str, Any]) -> Dict[str, Any]:
    """Query current spend against budget."""
    try:
        from core.llm_usage_tracker import llm_usage_tracker
        workspace = args.get("workspace_id", "default")
        return {
            "budget_exceeded": llm_usage_tracker.is_budget_exceeded(workspace),
            "workspace": workspace,
        }
    except Exception as e:
        return {"error": str(e)}


async def _handle_get_health(args: Dict[str, Any]) -> Dict[str, Any]:
    """Provider health and circuit breaker states."""
    try:
        from core.provider_health_monitor import get_health_monitor
        monitor = get_health_monitor()
        providers = {}
        for pid in ("openai", "anthropic", "deepseek", "moonshot", "minimax"):
            health = monitor.get_provider_health(pid)
            if health:
                providers[pid] = health
        return {"providers": providers}
    except Exception as e:
        return {"error": str(e)}


async def _handle_fusion_generate(args: Dict[str, Any]) -> Dict[str, Any]:
    """Run a fusion (panel+judge) generation."""
    try:
        from core.llm.byok_handler import BYOKHandler
        from core.llm.fusion_router import is_fusion_eligible, run_fusion
        handler = BYOKHandler()
        prompt = args.get("prompt", "")
        system_instruction = args.get("system_instruction", "You are a helpful assistant.")
        task_type = args.get("task_type", "chat")
        complexity = handler.analyze_query_complexity(prompt, task_type)
        options = await handler.get_ranked_providers(complexity, task_type)
        if not is_fusion_eligible("fusion", "complex", task_type, len(options)):
            return {"error": "Fusion not eligible — requires COMPLEX tier + non-batch task + ≥2 providers"}
        result, meta = await run_fusion(
            handler, prompt, system_instruction, options, 0.7, task_type, None, None, 0
        )
        return {"result": result[:500], "metadata": meta}
    except Exception as e:
        return {"error": str(e)}


# --- Tool registry ---------------------------------------------------------

def get_all_tools() -> List[MCPTool]:
    """Return all registered MCP tools."""
    return [
        MCPTool(
            name="resolve_route",
            description="Dry-run routing: show which model+provider atom would pick for a given prompt",
            input_schema=_PROMPT_SCHEMA,
            handler=_handle_resolve_route,
        ),
        MCPTool(
            name="list_models",
            description="List available models with quality/cost/capability metadata",
            input_schema=_NO_INPUT_SCHEMA,
            handler=_handle_list_models,
        ),
        MCPTool(
            name="compress_text",
            description="Compress terminal/tool output via the RTK engine (shows savings metrics)",
            input_schema=_TEXT_SCHEMA,
            handler=_handle_compress_text,
        ),
        MCPTool(
            name="set_compression",
            description="Toggle token compression on/off",
            input_schema=_BOOLEAN_SCHEMA,
            handler=_handle_set_compression,
        ),
        MCPTool(
            name="get_spend",
            description="Query current spend against budget for a workspace",
            input_schema={
                "type": "object",
                "properties": {
                    "workspace_id": {"type": "string", "description": "Workspace ID (default: default)"},
                },
            },
            handler=_handle_get_spend,
        ),
        MCPTool(
            name="get_health",
            description="Get provider health status and circuit breaker states",
            input_schema=_NO_INPUT_SCHEMA,
            handler=_handle_get_health,
        ),
        MCPTool(
            name="fusion_generate",
            description="Run a fusion (panel+judge) generation for high-stakes tasks (COMPLEX tier only)",
            input_schema=_FUSION_SCHEMA,
            handler=_handle_fusion_generate,
        ),
    ]
