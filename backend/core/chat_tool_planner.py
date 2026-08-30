"""LLM-based tool planner for the chat path.

Replaces the regex intent gates (email-search detector, retry detector,
stopword term extraction) that only ever covered Outlook. Following the
harness patterns used in production agents (native tool-calling /
tool-retrieval; see AGENTS.md §3): a cheap structured-output LLM call reads
the conversation and decides whether answering needs FRESH data from one of
the user's CONNECTED integrations — for all 40+ services, not one.

Design notes (AGENTS.md §3 research, Aug 2026):
- Connected-first discovery (MCP "dynamic visibility"): the planner only
  sees services the user actually has tokens for, so the catalog stays
  small regardless of how many integrations the platform supports.
- Meta-tool shape: the planner returns (service, intent, query) rather than
  one schema per integration operation; `INTENT_ACTIONS` maps the intent to
  each family's real action name in UniversalIntegrationService.
- Read-only: search/list only. Mutations stay behind the maturity and
  governance gates (MCP email tools, HITL proposals) — the planner can
  never trigger a write.

Every leg is fault-isolated: a planner failure or executor error degrades
to "no tool block" and the model answers from transcript/memory, never
raising into the chat path.
"""
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Connects provider names as stored in integration_tokens to the service
# names UniversalIntegrationService dispatches on.
_PROVIDER_ALIASES = {
    "microsoft": "outlook",
    "office365": "outlook",
    "azure": "outlook",
    "google": "gmail",
    "gdrive": "google_drive",
}

# Intent -> real action name per service family in
# UniversalIntegrationService._dispatch_execution. Kept in ONE place so
# adding an integration is adding a row, not a new regex.
_INTENT_ACTIONS: Dict[str, Dict[str, str]] = {
    "default": {"search": "search", "list": "list"},
    "slack": {"search": "search_messages", "list": "list_channels"},
    "teams": {"search": "search_messages", "list": "list_channels"},
    "discord": {"search": "search_messages", "list": "list_channels"},
    "telegram": {"search": "search_messages", "list": "list_channels"},
}

# Short human descriptions the planner reads (kept compact — this prompt
# rides on every chat turn).
_SERVICE_DESCRIPTIONS = {
    "outlook": "email mailbox — search messages by name, subject, company, keyword",
    "gmail": "email mailbox — search messages",
    "slack": "team chat — search messages and channels",
    "teams": "team chat — search messages",
    "discord": "community chat — search messages",
    "telegram": "messenger — search messages",
    "zoho_crm": "CRM — search leads, contacts, deals, accounts",
    "salesforce": "CRM — search leads, contacts, opportunities",
    "hubspot": "CRM — search contacts, companies, deals",
    "google_drive": "file storage — search documents and files",
    "dropbox": "file storage — search files",
    "onedrive": "file storage — search files",
    "box": "file storage — search files",
    "notion": "workspace docs — search pages",
    "zoho_workdrive": "file storage — search files",
    "jira": "project tracker — search issues",
    "linear": "project tracker — search issues",
    "asana": "project tracker — search tasks",
    "trello": "project tracker — search cards",
    "monday": "project tracker — search items",
    "zendesk": "support desk — search tickets",
    "freshdesk": "support desk — search tickets",
    "intercom": "support chat — search conversations",
    "github": "code hosting — search repos, issues, PRs",
    "gitlab": "code hosting — search repos, issues",
    "shopify": "e-commerce — search orders, products, customers",
    "stripe": "payments — search payments, invoices",
    "quickbooks": "accounting — search invoices, customers",
}

_PLANNER_SYSTEM = """You are the tool planner for an AI automation platform.
Given the recent conversation and the user's latest message, decide whether
answering needs FRESH data from one of the user's connected integrations
(listed below with what they contain), or whether the conversation itself is
enough.

Rules:
- Retry phrases ("try again", "any luck?", "still nothing", "didn't work")
  mean RE-RUN the most recent tool action: use_tool=true with the same
  service and the same query terms as before.
- query must be the minimal search terms (names, companies, subjects,
  keywords) — not the whole user message.
- Read-only: only search/list intents. Never plan sends, writes, or deletes.
- If the conversation or memory already clearly answers it, use_tool=false.
- If the needed integration is NOT in the connected list, use_tool=false and
  say which integration is missing in `reason`."""


class ToolPlan(BaseModel):
    use_tool: bool = False
    service: Optional[str] = None
    intent: Optional[str] = "search"
    query: Optional[str] = None
    reason: str = ""


def get_connected_services(user_id: Optional[str]) -> List[str]:
    """Providers the user has ACTIVE tokens for, mapped to service names.
    Cached briefly — this is consulted every chat turn."""
    global _connected_cache  # noqa: PLW0603
    import time

    now = time.monotonic()
    cached = _connected_cache.get(user_id)
    if cached and now - cached[0] < 60:
        return cached[1]
    services: List[str] = []
    try:
        from core.database import get_db_session
        from core.models import IntegrationToken

        with get_db_session() as db:
            rows = (
                db.query(IntegrationToken.provider)
                .filter(
                    IntegrationToken.user_id == user_id,
                    IntegrationToken.status == "active",
                )
                .all()
            )
        seen = set()
        for (provider,) in rows:
            svc = _PROVIDER_ALIASES.get(str(provider).lower(), str(provider).lower())
            if svc not in seen:
                seen.add(svc)
                services.append(svc)
    except Exception as e:
        logger.warning(f"connected-service lookup failed for {user_id}: {e}")
    _connected_cache[user_id] = (now, services)
    return services


_connected_cache: Dict[str, Any] = {}


def _catalog_line(connected: List[str]) -> str:
    lines = []
    for svc in connected:
        desc = _SERVICE_DESCRIPTIONS.get(svc, "integration data")
        lines.append(f"- {svc}: {desc}")
    return "\n".join(lines) if lines else "- (none connected)"


def _history_transcript(history: List[Dict[str, Any]], current: str) -> str:
    lines: List[str] = []
    for h in (history or [])[-4:]:
        u = str((h or {}).get("message") or "").strip()
        a = str(((h or {}).get("response") or {}).get("message") or "").strip()
        if u:
            lines.append(f"User: {u[:220]}")
        if a:
            lines.append(f"Assistant: {a[:220]}")
    lines.append(f"User: {current[:400]}")
    return "\n".join(lines)


async def plan_tool_use(
    message: str,
    history: List[Dict[str, Any]],
    user_id: Optional[str],
    llm_service: Any,
) -> Optional[ToolPlan]:
    """Decide (via cheap structured LLM output) whether this turn needs live
    integration data, and which connected service to query. Returns None on
    any failure — the caller then simply runs without a tool block."""
    if llm_service is None:
        return None
    connected = get_connected_services(user_id)
    catalog = _catalog_line(connected)
    prompt = (
        f"{_PLANNER_SYSTEM}\n\n"
        f"Connected integrations:\n{catalog}\n\n"
        f"Recent conversation:\n{_history_transcript(history, message)}\n\n"
        "Return the tool plan."
    )
    from core.llm_service import LLMService

    plan = await llm_service.generate_structured(
        prompt=prompt,
        response_model=ToolPlan,
        system_instruction="You return only the requested JSON object.",
        temperature=0.0,
    )
    if plan is None:
        return None
    if plan.use_tool:
        if not plan.service or plan.service not in connected:
            logger.info(f"tool planner: service not connected ({plan.service!r}): {plan.reason[:80]}")
            return None
        if plan.intent not in ("search", "list"):
            plan.intent = "search"
        if not (plan.query or "").strip():
            plan.query = message[:120]
    return plan


async def execute_tool_plan(
    plan: ToolPlan, user_id: Optional[str], tenant_id: str = "default"
) -> Optional[str]:
    """Run the planned read-only action and return a text block for prompt
    injection. Returns None when nothing usable came back."""
    if not plan or not plan.use_tool or not plan.service:
        return None
    service = plan.service
    query = (plan.query or "").strip()

    # Outlook: dedicated service with per-user token handling. Graph $search
    # OR-ranks multi-word queries, so a rare surname gets buried under common
    # words ("Mark" → "Pavement Markings") — search each term separately and
    # merge, ranking hits that match more terms first, then by recency.
    if service == "outlook":
        try:
            from integrations.outlook_service import outlook_service

            tokens = [t for t in query.split() if len(t) >= 2][:3] or [query]
            merged: Dict[str, Dict[str, Any]] = {}
            for term in tokens:
                try:
                    emails = await outlook_service.search_emails(
                        user_id=user_id, query=term, max_results=10, quote=False
                    )
                except Exception as term_err:
                    logger.warning(f"outlook term search failed ({term}): {term_err}")
                    continue
                # Longer terms are rarer: a hit matching "Kellam" (6 chars)
                # is far more meaningful than one matching "Mark" (4) via
                # "Markings". Score = sum of matched-term lengths.
                weight = len(term)
                for e in emails or []:
                    eid = e.get("id")
                    if not eid:
                        continue
                    entry = merged.setdefault(eid, {"email": e, "score": 0, "received": ""})
                    entry["score"] += weight
                    received = str(e.get("received_date_time") or "")
                    if received > entry["received"]:
                        entry["received"] = received

            def _rank(entry: Dict[str, Any]):
                # Multi-term matches first, then newest — stable and cheap.
                return (-entry["score"], entry["received"], )

            ranked = sorted(merged.values(), key=_rank)
            emails = [x["email"] for x in ranked[:8]]
            if not emails:
                return (
                    f"LIVE TOOL RESULTS (outlook.search_emails, query='{query}'): "
                    "no matching messages in the mailbox."
                )
            listing = "\n".join(
                f"- From: {((e.get('from_field') or {}).get('emailAddress') or {}).get('address') or '?'} | "
                f"{str(e.get('subject') or '(no subject)')[:120]} | "
                f"{str(e.get('body_preview') or '')[:200]} | "
                f"received: {str(e.get('received_date_time'))[:19]}"
                for e in emails[:6]
            )
            return (
                f"LIVE TOOL RESULTS (outlook.search_emails, query='{query}') — "
                f"use these to answer:\n{listing}"
            )
        except Exception as e:
            logger.warning(f"outlook tool execution failed: {e}")
            return None

    # Everything else: the universal integration service (44 integrations,
    # governance + circuit breaker + masking inside).
    try:
        from integrations.universal_integration_service import UniversalIntegrationService

        action = _INTENT_ACTIONS.get(service, _INTENT_ACTIONS["default"]).get(
            plan.intent or "search", "search"
        )
        svc = UniversalIntegrationService(workspace_id="default")
        result = await svc.execute(
            service,
            action,
            {"query": query, "limit": 8},
            context={"user_id": user_id, "workspace_id": "default", "tenant_id": tenant_id},
        )
        data = result.get("data") if isinstance(result, dict) else None
        if result.get("status") != "success" or not data:
            reason = str(result.get("error") or result.get("message") or "no data")[:160]
            return (
                f"LIVE TOOL RESULTS ({service}.{action}, query='{query}'): "
                f"returned nothing usable ({reason})."
            )
        text = str(data)[:2500]
        return (
            f"LIVE TOOL RESULTS ({service}.{action}, query='{query}') — "
            f"use these to answer:\n{text}"
        )
    except Exception as e:
        logger.warning(f"tool execution failed for {service}.{plan.intent}: {e}")
        return None
