"""Managed-agent runtime resolution (marketplace) — upstream engine port.

Self-hosted counterpart of backend-saas/core/marketplace_runtime.py.

Installed marketplace agents carry a *reference* configuration
(template_id, version, tunables) — not the publisher's prompts or memory.
This module turns that reference into an executable agent:

- loads the manifest (system prompts / tool surface / guidance) from the
  local AgentTemplate row when one exists (local publishes and legacy
  payloads)
- applies the template's permission profile guardrails
- enforces kill switches: template deactivated, installation inactive

UPSTREAM DIVERGENCE vs the SaaS resolver: no entitlement gating (billing is
SaaS-only by sync policy), and a MISSING local template degrades gracefully
(agent runs with its default prompt) instead of blocking — a self-hosted
operator deleting a local template row should not brick installed agents.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_MAX_GUIDANCE_HEURISTICS = 10
_MAX_GUIDANCE_GOLDEN_PATHS = 3
_GUIDANCE_CHAR_BUDGET = 4000


class ManagedAgentBlockedError(Exception):
    """A managed marketplace agent may not run (kill switch tripped)."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def is_managed_agent(agent: Any) -> bool:
    """True when the AgentRegistry row is a marketplace-managed reference."""
    config = getattr(agent, "configuration", None) or {}
    return bool(config.get("marketplace_managed") and config.get("template_id"))


def resolve_managed_agent(
    db: Any,
    agent: Any,
    tenant_id: Optional[str] = None,
    sync_version: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Resolve a managed agent's runtime overrides from its template manifest.

    Returns None for non-managed agents; raises ManagedAgentBlockedError when
    a kill switch tripped; returns default-prompt overrides (with a warning)
    when the local template manifest is absent.
    """
    if not is_managed_agent(agent):
        return None

    from core.models import AgentInstallation, AgentTemplate

    config = agent.configuration or {}
    template_id = str(config["template_id"])

    template = db.query(AgentTemplate).filter(AgentTemplate.id == template_id).first()

    installation_query = db.query(AgentInstallation).filter(
        AgentInstallation.instantiated_agent_id == agent.id
    )
    if tenant_id is not None:
        installation_query = installation_query.filter(AgentInstallation.tenant_id == tenant_id)
    installation = installation_query.first()

    if installation is not None and not installation.is_active:
        raise ManagedAgentBlockedError("this installation is inactive")

    if template is None:
        # Upstream divergence: no local manifest (e.g. listing-only payload
        # from the SaaS marketplace). Run with defaults rather than blocking.
        logger.warning(
            f"Managed agent {agent.id}: no local manifest for template "
            f"{template_id}; running with default prompt"
        )
        return {
            "template_id": template_id,
            "version": config.get("managed_version"),
            "system_prompt": None,
            "allowed_tools": None,
            "blocked_tools": [],
            "guidance": {"heuristics": [], "golden_paths": []},
            "tunables": config.get("tunables") or {},
        }

    if not getattr(template, "is_active", True):
        raise ManagedAgentBlockedError("the listing has been deactivated")

    manifest = template.configuration or {}
    profile = getattr(template, "permission_profile", None) or {}

    allowed_tools, blocked_tools = _resolve_tool_surface(
        manifest.get("tools", "*"), profile
    )

    guidance = _build_guidance(getattr(template, "anonymized_memory_bundle", None) or {})

    if sync_version and installation is not None:
        template_version = template.version
        if template_version and template_version != installation.installed_version:
            installation.installed_version = template_version
            if hasattr(installation, "last_synced_version"):
                installation.last_synced_version = template_version
            try:
                db.commit()
            except Exception:
                db.rollback()
                logger.warning(
                    f"Failed to sync installation {installation.id} to {template_version}"
                )

    return {
        "template_id": template_id,
        "version": template.version,
        "system_prompt": manifest.get("system_prompt"),
        "allowed_tools": allowed_tools,
        "blocked_tools": blocked_tools,
        "guidance": guidance,
        "tunables": config.get("tunables") or {},
    }


def _resolve_tool_surface(manifest_tools: Any, profile: Dict[str, Any]) -> tuple[Any, list]:
    """Manifest tool list ∩ profile allowed − profile blocked."""
    allowed = profile.get("allowed_tools")
    blocked = [str(t) for t in (profile.get("blocked_tools") or [])]

    if isinstance(manifest_tools, list):
        tools = [str(t) for t in manifest_tools]
        if allowed:
            tools = [t for t in tools if t in set(allowed)]
        if blocked:
            tools = [t for t in tools if t not in set(blocked)]
        return tools, []

    if allowed:
        return [str(t) for t in allowed if t not in set(blocked)], []
    if blocked:
        return "*", blocked
    return "*", []


def _build_guidance(memory_bundle: Dict[str, Any]) -> Dict[str, Any]:
    """Cap and sanitize publisher knowledge for read-only prompt injection."""
    heuristics = []
    for h in (memory_bundle.get("heuristics") or [])[:_MAX_GUIDANCE_HEURISTICS]:
        if not isinstance(h, dict):
            continue
        heuristics.append(
            {
                "error_type": str(h.get("error_type") or "general"),
                "error_code": str(h.get("error_code") or ""),
                "resolution": str(h.get("resolution") or "")[:500],
            }
        )

    golden_paths = []
    for p in (memory_bundle.get("golden_paths") or [])[:_MAX_GUIDANCE_GOLDEN_PATHS]:
        if not isinstance(p, dict):
            continue
        sequence = p.get("sequence") or []
        if isinstance(sequence, list) and sequence:
            golden_paths.append([str(step) for step in sequence[:20]])

    return {"heuristics": heuristics, "golden_paths": golden_paths}


def render_guidance_block(guidance: Optional[Dict[str, Any]]) -> str:
    """
    Render the read-only publisher-guidance prompt block (bounded). Empty
    string when there is nothing to inject.
    """
    if not guidance:
        return ""
    lines: list[str] = []

    heuristics = guidance.get("heuristics") or []
    if heuristics:
        lines.append("PROVEN PLAYBOOK (publisher-provided, read-only —")
        lines.append("known failure signatures and the resolutions that worked):")
        for h in heuristics:
            code = f" [{h['error_code']}]" if h.get("error_code") else ""
            lines.append(f"- When {h['error_type']}{code}: {h['resolution']}")

    golden_paths = guidance.get("golden_paths") or []
    if golden_paths:
        if lines:
            lines.append("")
        lines.append("PROVEN SEQUENCES (publisher-provided, read-only —")
        lines.append("tool orders with historically high success for tasks like this):")
        for i, sequence in enumerate(golden_paths, start=1):
            lines.append(f"- Sequence {i}: {' -> '.join(sequence)}")

    if not lines:
        return ""

    lines.append("")
    lines.append(
        "Treat the above as strong defaults from the publisher's operational "
        "experience; adapt to the actual task and record your own evidence."
    )

    block = "\n".join(lines)
    if len(block) > _GUIDANCE_CHAR_BUDGET:
        block = block[:_GUIDANCE_CHAR_BUDGET] + "\n…(truncated)"
    return block
