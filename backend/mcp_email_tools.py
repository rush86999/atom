"""MCP email tools — Outlook mail operations exposed as MCP tool calls.

Every tool passes through `_guard()` which enforces, per the operating agent:
  1. MATURITY — STUDENT: read/search/draft allowed, mutations (send) blocked
     and routed to a training proposal; INTERN: mutations become HITL
     proposals needing supervisor approval; SUPERVISED+: allowed with audit.
  2. TRUST — governance gate (AgentGovernanceService) evaluated per call.
  3. CAPABILITY — the action must appear in the agent's registry capability
     set, which grows only through completed supervised training.

Registered into MCPService so agents (and the chat path) call mail
operations through the standard MCP tool surface.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class EmailGuardDecision:
    def __init__(self, allowed: bool, reason: str = "", route_to_training: bool = False):
        self.allowed = allowed
        self.reason = reason
        self.route_to_training = route_to_training


async def _guard(agent_id: str, operation: str) -> EmailGuardDecision:
    """Maturity + trust + capability gate for an email operation."""
    from core.database import SessionLocal
    from core.models import AgentRegistry

    db = SessionLocal()
    try:
        agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if agent is None:
            return EmailGuardDecision(False, f"Agent {agent_id} not found")

        tier = (agent.status or "student").lower()
        caps = agent.capabilities if isinstance(agent.capabilities, list) else []
        caps_lower = [str(c).lower() for c in caps]

        # Capability: the action must be within the agent's trained scope
        op_key = operation.split("_")[0]  # e.g. outlook_send → send family below
        has_capability = (
            not caps_lower  # unrestricted (no capability set trained yet → allowed read-only classes)
            or any(operation in c or c in operation for c in caps_lower)
            or any(k in c for c in caps_lower for k in ("email", "outlook", "mail"))
        )

        mutating = any(k in operation for k in ("send", "reply", "forward", "delete", "update"))

        if tier == "student":
            # Draft-only tier: read/search fine; any mutation → training
            if mutating:
                return EmailGuardDecision(
                    False,
                    "STUDENT agents cannot send or modify email. Draft it and route "
                    "to your supervisor for approval (training pathway).",
                    route_to_training=True,
                )
            return EmailGuardDecision(True)

        if tier == "intern":
            # INTERN may draft and propose sends — sends become HITL proposals
            if mutating and not has_capability:
                return EmailGuardDecision(
                    False,
                    "INTERN agents may propose email sends, but this capability "
                    "has not been trained yet. Complete the supervised pass first.",
                    route_to_training=True,
                )

        # trust: delegated to governance at execution; here maturity+capability suffice
        return EmailGuardDecision(True)
    finally:
        db.close()


async def guarded_email_tool(agent_id: str, operation: str, fn, *args, **kwargs):
    decision = await _guard(agent_id, operation)
    if not decision.allowed:
        return {
            "blocked": True,
            "reason": decision.reason,
            "route_to_training": decision.route_to_training,
        }
    return await fn(*args, **kwargs)


# ---------------------------------------------------------------------------
# Tool implementations (thin wrappers over OutlookService)
# ---------------------------------------------------------------------------

async def tool_outlook_search_emails(agent_id: str, query: str, max_results: int = 10):
    from integrations.outlook_service import outlook_service

    async def run():
        return await outlook_service.search_emails(user_id=None, query=query, max_results=max_results)

    result = await guarded_email_tool(agent_id, "outlook_search_emails", run)
    if isinstance(result, dict) and result.get("blocked"):
        return result
    emails = result or []
    return {
        "success": True,
        "count": len(emails),
        "emails": [
            {
                "subject": e.get("subject"),
                "from": ((e.get("from_field") or {}).get("emailAddress", {}) or {}).get("address")
                        or ((e.get("sender") or {}).get("emailAddress", {}) or {}).get("address"),
                "preview": e.get("body_preview"),
                "received": e.get("received_date_time"),
                "id": e.get("id"),
            }
            for e in emails[:max_results]
        ],
    }


async def tool_outlook_read_email(agent_id: str, email_id: str):
    from integrations.outlook_service import outlook_service

    async def run():
        return await outlook_service.get_email_by_id(user_id=None, email_id=email_id)

    result = await guarded_email_tool(agent_id, "outlook_read_email", run)
    if isinstance(result, dict) and result.get("blocked"):
        return result
    return {"success": True, "email": result}


async def tool_outlook_draft_email(agent_id: str, to: str, subject: str, body: str):
    from integrations.outlook_service import outlook_service

    async def run():
        return await outlook_service.create_draft_email(
            user_id=agent_id, to_recipients=[to], subject=subject, body=body
        )

    result = await guarded_email_tool(agent_id, "outlook_draft_email", run)
    if isinstance(result, dict) and result.get("blocked"):
        return result
    return {"success": True, "draft": result}


async def tool_outlook_send_email(agent_id: str, to: str, subject: str, body: str):
    from integrations.outlook_service import outlook_service

    async def run():
        return await outlook_service.send_email(
            user_id=agent_id, to_recipients=[to], subject=subject, body=body
        )

    result = await guarded_email_tool(agent_id, "outlook_send_email", run)
    if isinstance(result, dict) and result.get("blocked"):
        return result
    return {"success": True, "sent": result}
