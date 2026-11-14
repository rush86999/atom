"""Agent-facing actions for workspace-approved reviewed executable skills.

The reviewed executable lifecycle (``core.reviewed_improvement`` ->
``SkillRegistryService`` -> ``HazardSandbox``) is the authorization and
execution authority.  This module only exposes it on the ordinary tool
surface so an agent can discover and invoke an approved artifact without a
human calling ``POST /api/skills/execute``.

Design (matches mature harness practice):

* discovery is metadata-only — MCP tool definitions are model-controlled
  (https://modelcontextprotocol.io/specification/2025-06-18/server/tools)
  and Agent Skills load metadata before code/resources
  (https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview);
  the generated code never enters a prompt;
* ``skills.list`` reports only entries whose exact review binding, linked
  ``Skill`` row, workspace assignment, tenant and employee still match, and
  for which the same read-only artifact authorization (current candidate and
  registered-code digests, review revision/digest) still passes; a changed or
  revoked artifact is never advertised as currently approved;
* ``skills.execute`` resolves the model-supplied NAME again at dispatch time
  and delegates to ``SkillRegistryService.execute_skill``, which authorizes
  the full artifact before creating an execution row or touching Docker.

Identity is never taken from model arguments: the dispatch layer supplies a
server-owned ``_skill_scope`` (tenant/workspace/employee).  A manual RPC call
has no employee scope and is refused, so this is not a new human API path.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.action_registry import register_action

logger = logging.getLogger(__name__)


def _trusted_skill_scope(context: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """Extract the authenticated agent scope for a skill invocation.

    ``_skill_scope`` is stamped by the agent dispatch layer from its own
    runtime identity.  The fallback accepts a normal agent dispatch context
    (all three keys present); a request/user-only RPC context is refused.
    """
    ctx = context or {}
    scope = ctx.get("_skill_scope")
    if isinstance(scope, dict):
        tenant_id = str(scope.get("tenant_id") or "").strip()
        workspace_id = str(scope.get("workspace_id") or "").strip()
        agent_id = str(scope.get("agent_id") or "").strip()
        if tenant_id and workspace_id and agent_id:
            return {
                "tenant_id": tenant_id,
                "workspace_id": workspace_id,
                "agent_id": agent_id,
                "user_id": str(scope.get("user_id") or "").strip(),
            }
        return None

    tenant_id = str(ctx.get("tenant_id") or "").strip()
    workspace_id = str(ctx.get("workspace_id") or "").strip()
    agent_id = str(ctx.get("agent_id") or "").strip()
    if tenant_id and workspace_id and agent_id:
        return {
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "user_id": str(ctx.get("user_id") or "").strip(),
        }
    return None


@register_action(
    "skills.list",
    description=(
        "List the reviewed executable skills approved for this employee in "
        "this workspace. Returns each skill's callable name, plain-language "
        "purpose and runtime. Use skills.execute to run one; generated code "
        "is never shown."
    ),
    parameters_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
    effects=[{"effect": "read", "scope": "local"}],
)
async def _skills_list(
    args: Dict[str, Any], context: Dict[str, Any]
) -> Dict[str, Any]:
    scope = _trusted_skill_scope(context)
    if scope is None:
        return {
            "success": False,
            "error": "skills_agent_scope_required: an agent workspace scope "
                     "is required to list executable skills",
            "blocked_by": "skill_scope",
        }
    try:
        from core.database import get_db_session
        from core.skill_registry_service import SkillRegistryService

        with get_db_session() as db:
            entries = SkillRegistryService(db).list_invocable_skills(
                tenant_id=scope["tenant_id"],
                workspace_id=scope["workspace_id"],
                agent_id=scope["agent_id"],
            )
    except Exception as exc:  # noqa: BLE001 - report, never leak internals
        logger.error("skills.list failed: %s", exc)
        return {
            "success": False,
            "error": "skills_list_unavailable",
            "blocked_by": "skill_registry",
        }
    return {
        "success": True,
        "count": len(entries),
        "skills": entries,
        "invoke_with": "skills.execute",
    }


@register_action(
    "skills.execute",
    description=(
        "Run one workspace-approved reviewed executable skill by name. Set "
        "skill to a name returned by skills.list (or the skills block in your "
        "instructions) and inputs to the object the skill's execute(inputs) "
        "function expects. The artifact is re-authorized against its exact "
        "review binding, tenant, workspace and employee before the Docker "
        "sandbox runs; unreviewed or changed artifacts are refused."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "skill": {
                "type": "string",
                "description": "Approved executable skill name",
            },
            "inputs": {
                "type": "object",
                "description": "Object passed to execute(inputs)",
            },
        },
        "required": ["skill"],
    },
    # A reviewed benign computation changes no external/business state. It
    # does append the platform-owned execution receipt, but declaring a
    # mutation would force the generic loop's outbound-operation claim for a
    # deterministic local computation.
    effects=[{"effect": "read", "scope": "local"}],
)
async def _skills_execute(
    args: Dict[str, Any], context: Dict[str, Any]
) -> Dict[str, Any]:
    identifier = str(
        (args or {}).get("skill")
        or (args or {}).get("skill_name")
        or ""
    ).strip()
    raw_inputs = (args or {}).get("inputs")
    inputs = {} if raw_inputs is None else raw_inputs
    if not identifier:
        return {
            "success": False,
            "error": "skills_execute_skill_required",
            "blocked_by": "skill_arguments",
        }
    if not isinstance(inputs, dict):
        return {
            "success": False,
            "error": "skills_execute_inputs_must_be_object",
            "blocked_by": "skill_arguments",
        }
    scope = _trusted_skill_scope(context)
    if scope is None:
        return {
            "success": False,
            "error": "skills_agent_scope_required: an agent workspace scope "
                     "is required to execute a reviewed skill",
            "blocked_by": "skill_scope",
        }

    try:
        from core.database import get_db_session
        from core.skill_registry_service import SkillRegistryService

        with get_db_session() as db:
            service = SkillRegistryService(db)
            entry = service.resolve_invocable_skill(
                identifier,
                tenant_id=scope["tenant_id"],
                workspace_id=scope["workspace_id"],
                agent_id=scope["agent_id"],
            )
            if entry is None:
                # Not advertised for this exact scope: no artifact was
                # authorized, so the sandbox leaf is never constructed.
                return {
                    "success": False,
                    "error": "skills_execute_not_available: no approved "
                             "executable skill with that name is assigned to "
                             "this employee and workspace",
                    "blocked_by": "skill_authorization",
                }
            try:
                result = await service.execute_skill(
                    skill_id=entry["skill_id"],
                    inputs=inputs,
                    agent_id=scope["agent_id"],
                    tenant_id=scope["tenant_id"],
                    workspace_id=scope["workspace_id"],
                    user_id=scope["user_id"],
                )
            except ValueError as exc:
                # Reviewed-executable authorization failures are raised
                # before a SkillExecution row exists and before Docker.
                return {
                    "success": False,
                    "error": str(exc),
                    "blocked_by": "skill_authorization",
                    "skill": entry["name"],
                }
    except Exception as exc:  # noqa: BLE001 - report, never leak internals
        logger.error("skills.execute failed: %s", exc)
        return {
            "success": False,
            "error": "skills_execute_unavailable",
            "blocked_by": "skill_registry",
        }

    response = dict(result) if isinstance(result, dict) else {
        "success": False,
        "error": "skills_execute_invalid_result",
    }
    response.setdefault("skill", entry["name"])
    response.setdefault("skill_tool", "skills.execute")
    return response
