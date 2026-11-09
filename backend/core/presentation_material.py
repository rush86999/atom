"""Canonical presentation material and digests.

Both the executor (frozen authorized request) and the canvas tools (observed
audit payload) derive material through THIS module, so their digests cannot
drift. Title, length and point count are diagnostics; the material bytes plus
the governed operation are the identity.

API used by the current presentation binding:
    presentation_material(action, args) -> dict
    material_sha256(material) -> str
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Tuple

# Arguments that describe the delivery envelope, not the material.
PRESENTATION_META = {
    "canvas_id", "operation_id", "workspace_id", "tenant_id", "session_id",
    "agent_id", "title", "component_type", "_oracle_action",
}
CHART_META = PRESENTATION_META | {"chart_type", "type", "data", "chart"}


def normalize_markdown(content: Any) -> str:
    """Stable text: newline normalization only; never trim or rewrite."""
    return str(content if content is not None else "").replace(
        "\r\n", "\n").replace("\r", "\n")


def normalize_chart(args: Dict[str, Any]) -> Tuple[str, Any, Dict[str, Any]]:
    """Return (chart_type, data, config) from flat or nested chart arguments."""
    args = args or {}
    chart_type = args.get("chart_type") or args.get("type")
    data = args.get("data")
    nested = args.get("chart")
    if isinstance(nested, dict):
        chart_type = chart_type or nested.get("type") or nested.get("chart_type")
        if data is None:
            data = nested.get("data")
        if data is None and nested.get("categories") is not None:
            data = [
                {"x": category, "y": value}
                for category, value in zip(
                    nested.get("categories") or [], nested.get("values") or [])
            ]
        nested_config = nested.get("config")
        if isinstance(nested_config, dict):
            args = {**nested_config, **args}
    config = {
        str(key): value for key, value in args.items()
        if key not in CHART_META and not str(key).startswith("_")
    }
    return str(chart_type or ""), data, config


def chart_config(args: Dict[str, Any]) -> Dict[str, Any]:
    return normalize_chart(args)[2]


def normalize_form_schema(args: Dict[str, Any]) -> Any:
    """Return the form schema from either producer or action argument shape.

    ``present_form`` exposes ``form_schema`` while the canvas event carries
    ``schema``. Both names must resolve to the SAME material; ``None`` is the
    only absent value, so an explicit empty schema is preserved.
    """
    args = args or {}
    schema = args.get("form_schema")
    if schema is None:
        schema = args.get("schema")
    return schema


def presentation_material(action: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """One canonical material object for the action's authorized arguments."""
    name = str(action or "")
    args = args or {}
    if name.endswith("canvas.present_markdown") or name.endswith(
            "present_markdown"):
        content = args.get("content")
        if content is None or content == "":
            return None
        return {
            "kind": "markdown",
            "content": normalize_markdown(content),
        }
    if name.endswith("canvas.present_chart") or name.endswith(
            "present_chart"):
        chart_type, data, config = normalize_chart(args)
        if not chart_type or data is None:
            return None
        return {
            "kind": "chart",
            "chart_type": chart_type,
            "data": data,
            "config": config,
        }
    if name.endswith("canvas.present_form") or name.endswith("present_form"):
        schema = normalize_form_schema(args)
        if schema is None:
            return None
        return {
            "kind": "form",
            "schema": schema,
        }
    raise ValueError(f"unsupported presentation action {action!r}")


def material_sha256(material: Any) -> str:
    """Canonical digest of a material object (stable key order)."""
    return _digest(material if isinstance(material, dict) else {})


def markdown_digest(content: Any) -> str:
    return material_sha256({
        "kind": "markdown", "content": normalize_markdown(content)})


def chart_digest(
    chart_type: Any, data: Any, config: Dict[str, Any] | None = None,
) -> str:
    return material_sha256({
        "kind": "chart",
        "chart_type": str(chart_type or ""),
        "data": data,
        "config": config or {},
    })


def form_digest(schema: Any) -> str:
    return material_sha256({"kind": "form", "schema": schema})


def presentation_digest(kind: str, material: Dict[str, Any]) -> str:
    if kind == "markdown":
        return markdown_digest(material.get("content"))
    if kind == "chart":
        return chart_digest(
            material.get("chart_type"), material.get("data"),
            material.get("config") or {})
    if kind == "form":
        return form_digest(material.get("schema"))
    raise ValueError(f"unsupported presentation kind {kind!r}")


def _digest(material: Dict[str, Any]) -> str:
    blob = json.dumps(
        material, sort_keys=True, separators=(",", ":"), default=str,
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
