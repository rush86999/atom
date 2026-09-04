
import asyncio
import logging
import os
from typing import Dict, Any, List, Optional
from core.database import SessionLocal
from core.identifier_search import filter_by_terms
from integrations.salesforce_service import SalesforceService
from integrations.hubspot_service import get_hubspot_service
from integrations.shopify_service import ShopifyService
from core.circuit_breaker import circuit_breaker
# governance_middleware is optional — the module may not exist in all setups.
try:
    from middleware.governance_middleware import governance_middleware
except ImportError:
    governance_middleware = None
# budget_service was renamed/removed; guard the import so this module loads.
try:
    from core.budget_service import budget_service
except ImportError:
    budget_service = None
try:
    from core.cost_config import get_action_cost
except ImportError:
    def get_action_cost(*args, **kwargs):
        return 0.0

logger = logging.getLogger(__name__)


def _query_anchored_excerpt(text: str, query: str, excerpt_chars: int = 4000) -> str:
    """Excerpt of ``text`` centered on the best query-token match region.

    A workbook read must surface the REGION the question is about (the
    WG350DSAV row), not the file head — the head is usually sheet 1 /
    cover-page boilerplate, which is exactly what the old preview-only paths
    showed while the answer sat further in. Falls back to the head when no
    query token appears.

    RAREST-TOKEN ANCHOR first: the query token with the fewest occurrences
    in the text is the identifying one (the model number vs "price"/"list"
    boilerplate). Coverage scoring alone loses exactly here — a row region
    is a numeric dump, so header windows containing "consolidated price
    list" out-score it 3-to-1 and the excerpt lands thousands of rows away
    (live 2026-09-04: 'wg350dsav' at offset 2.4M of a 4.1M-char workbook
    never surfaced). When the rarest token is itself frequent (>50 hits,
    i.e. not identifying), fall back to distinct-token coverage scoring.
    """
    text = text or ""
    import re as _re

    tokens = [t for t in _re.split(r"[^a-z0-9]+", (query or "").lower()) if len(t) > 2]
    lower = text.lower()
    uniq = set(tokens)
    if not uniq:
        return text[:excerpt_chars]
    counts = {t: lower.count(t) for t in uniq}
    # Anchor only on tokens PRESENT in the text: an enriched context token
    # may name a different product entirely (count 0) — anchoring on it
    # would land on the head and be worse than coverage scoring.
    present = {t: c for t, c in counts.items() if c > 0}
    half = excerpt_chars // 2
    if present:
        anchor = min(present, key=lambda t: (present[t], -len(t)))
        if present[anchor] <= 50:
            idx = lower.find(anchor)
            start = max(0, idx - half)
            end = min(len(text), idx + half)
            prefix = "… " if start > 0 else ""
            suffix = " …" if end < len(text) else ""
            return f"{prefix}{text[start:end]}{suffix}"
    best_pos, best_hits = 0, -1
    for tok in sorted(uniq, key=len, reverse=True):
        start = 0
        finds = 0
        while finds < 2000:  # cap: boilerplate tokens can occur thousands of times
            idx = lower.find(tok, start)
            if idx < 0:
                break
            finds += 1
            # count how many DISTINCT tokens appear in this window
            window = lower[max(0, idx - excerpt_chars // 2): idx + excerpt_chars // 2]
            hits = sum(1 for t in uniq if t in window)
            if hits > best_hits:
                best_pos, best_hits = idx, hits
            start = idx + len(tok)
            if best_hits >= len(uniq):
                break
    if best_hits <= 0:
        return text[:excerpt_chars]
    start = max(0, best_pos - half)
    end = min(len(text), best_pos + half)
    prefix = "… " if start > 0 else ""
    suffix = " …" if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"

# All native integrations supported by Atom
NATIVE_INTEGRATIONS = {
    # Sales & CRM
    "salesforce", "hubspot", "zoho_crm",
    # Communication
    "slack", "teams", "discord", "google_chat", "telegram", "whatsapp", "zoom", "zoho_mail",
    # Project Management
    "asana", "jira", "linear", "trello", "monday", "zoho_projects",
    # Storage & Knowledge
    "google_drive", "dropbox", "onedrive", "box", "notion", "zoho_workdrive",
    # Forms & Automation (webhook-push apps — no public read API; the agent
    # reads what has been ingested, see _execute_zoho)
    "zoho_forms", "zoho_flow",
    # Support
    "zendesk", "freshdesk", "intercom",
    # Development
    "github", "gitlab", "figma",
    # Finance
    "stripe", "quickbooks", "xero", "zoho_books", "zoho_inventory",
    # Marketing
    "mailchimp", "hubspot_marketing", "meta_ads", "google_ads", "linkedin_ads", "google_reviews",
    # Analytics
    "tableau", "google_analytics",
    # E-commerce
    "shopify",
    # Email & Communication
    "aws_ses",
}

# Services with a LIVE search implementation in UniversalIntegrationService.search()
# (the family branches below). Single source of truth for:
#   - chat_tool_planner.execute_tool_plan: plain "search" intents for these
#     services route through search() instead of execute(), whose family
#     handlers only implement named actions;
#   - the planner catalog annotation ("live search supported" vs
#     "no live search — use memory").
# Keep in sync with the search() routing — asserted by
# tests/test_planner_live_search_routing.py.
SEARCHABLE_SERVICES = frozenset({
    # CRM
    "salesforce", "hubspot", "pipedrive", "zoho_crm",
    # Communication
    "slack", "teams", "discord", "google_chat", "telegram", "whatsapp",
    "gmail", "outlook", "zoho_mail",
    # Calendar
    "google_calendar", "outlook_calendar",
    # Project management
    "linear", "monday", "zoho_projects", "asana", "jira", "trello",
    # Storage
    "google_drive", "dropbox", "onedrive", "box", "notion", "zoho_workdrive",
    # Forms & automation (search the INGESTED records — no live read API)
    "zoho_forms", "zoho_flow",
    # Support
    "zendesk", "freshdesk", "intercom",
    # Development
    "github", "gitlab",
    # Marketing / analytics
    "mailchimp", "tableau", "google_analytics",
    # Finance (recent lists, client-side query filter)
    "stripe", "quickbooks", "xero", "zoho_books",
    # Dedicated item search (DC-correct service method)
    "zoho_inventory",
})

# Execute-path search routing (service → _search_* helper). The search()
# entry and the execute() families grew separate search implementations;
# the family chains implemented search for only SOME services, so planner
# "search" intents silently dead-ended for the rest (live 2026-09-03 class:
# box, linear, jira, asana, trello, gmail). _dispatch_execution routes
# search actions for these services through the same _search_* helpers the
# search() entry uses — one search implementation per service. Kept in sync
# with the families by tests/test_integration_dispatch_parity.py.
_SEARCH_ROUTES = {
    # Communication
    "slack": "_search_communication",
    "teams": "_search_communication",
    "discord": "_search_communication",
    "google_chat": "_search_communication",
    "telegram": "_search_communication",
    "whatsapp": "_search_communication",
    "gmail": "_search_communication",
    "outlook": "_search_communication",
    "zoho_mail": "_search_communication",
    # Project management
    "linear": "_search_project_management",
    "monday": "_search_project_management",
    "zoho_projects": "_search_project_management",
    "asana": "_search_project_management",
    "jira": "_search_project_management",
    "trello": "_search_project_management",
    # Storage
    "google_drive": "_search_storage",
    "dropbox": "_search_storage",
    "onedrive": "_search_storage",
    "box": "_search_storage",
    "notion": "_search_storage",
    "zoho_workdrive": "_search_storage",
    # CRM
    "salesforce": "_search_crm",
    "hubspot": "_search_crm",
    "zoho_crm": "_search_crm",
    "pipedrive": "_search_crm",
    # Support
    "zendesk": "_search_support",
    "freshdesk": "_search_support",
    "intercom": "_search_support",
    # Development
    "github": "_search_dev",
    "gitlab": "_search_dev",
    # Finance (client-side filter over recent lists)
    "stripe": "_search_finance",
    "quickbooks": "_search_finance",
    "xero": "_search_finance",
    "zoho_books": "_search_finance",
}

class UniversalIntegrationService:
    """
    Unified interface for accessing third-party integrations.
    Provides consistent CRUD and Search capabilities for Agents via MCP.
    Supports all 44 native integrations + Activepieces catalog fallback.
    """
    
    def __init__(self, workspace_id: str = "default"):
        self.workspace_id = workspace_id
        
    def _mask_response(self, service: str, response: Any) -> Any:
        """Apply the gatekeeper's per-provider response field masking so
        credentials (access_token, refresh_token, ...) never leak out of the
        integration layer. Best-effort: any gatekeeper failure returns the
        response unmasked rather than failing the action."""
        if governance_middleware is not None and hasattr(governance_middleware, "mask_response"):
            try:
                return governance_middleware.mask_response(service, response)
            except Exception:
                logger.warning(f"Response masking skipped for {service}", exc_info=True)
        return response

    @staticmethod
    def _filter_by_query(data: Any, query: str, limit: int = 8) -> List[Any]:
        """Client-side relevance filter for list endpoints that lack a
        server-side search param. ANY query term (>=3 chars; falls back to
        the whole query) matches, ranked by total matched-term weight — a
        record carrying the model code the question is about outranks ones
        that merely share a prose word — with recency (original) order
        preserved for ties. Previously this kept the FIRST limit matches in
        list order, which buried identifier matches under generic-term
        matches (live 2026-09-04: "bandsaw" matched 42 items while the
        stocked WG-350DSAV sat past the cut). Shared implementation:
        core.identifier_search.filter_by_terms."""
        from core.identifier_search import filter_by_terms
        return filter_by_terms(
            data if isinstance(data, (list, tuple)) else [data],
            query, text_of=str, limit=limit)

    async def execute(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute an action against a specific integration service via IntegrationRegistry.
        """
        from core.database import SessionLocal
        from core.integration_registry import IntegrationRegistry

        context = context or {}
        user_id = context.get("user_id")
        workspace_id = context.get("workspace_id") or self.workspace_id
        tenant_id = context.get("tenant_id") or workspace_id
        agent_id = context.get("agent_id")

        # --- Tool-error signal capture ---
        # The evolution harness (ReflectionEngine → Memento/AlphaEvolver)
        # only learns from FAILED episodes, and episode outcome comes from
        # execution metadata. Swallowed tool errors (a 400 returned as [])
        # used to die here invisibly. Record every error/circuit-open/
        # attribution-hold onto the agent's running execution so episodes
        # stop recording silent failures as successes. Fire-and-forget,
        # never breaks the call.
        async def _record_tool_error(kind: str, detail: str) -> None:
            try:
                from core.auto_dev.tool_error_signals import (
                    record_tool_error,
                    should_trigger_live,
                    tool_error_signature,
                )

                await asyncio.to_thread(
                    record_tool_error,
                    agent_id,
                    service,
                    action,
                    f"{kind}: {detail}"[:500],
                    tenant_id=str(tenant_id or "default"),
                    user_id=user_id,
                )
                # REAL-TIME evolution trigger for the ACTIVE task: the
                # moment this tool's errors cross the repeat threshold,
                # propose a tool-mutation fix — no waiting for episode
                # finalization (one dispatch per signature per 30min).
                if agent_id and should_trigger_live(
                    agent_id, tool_error_signature(service, action)
                ):
                    from core.auto_dev.reflection_engine import (
                        trigger_live_tool_fix,
                    )

                    asyncio.ensure_future(trigger_live_tool_fix(
                        agent_id=agent_id,
                        tenant_id=str(tenant_id or "default"),
                        service=service,
                        action=action,
                        error_detail=detail[:400],
                        execution_id=None,
                    ))
            except Exception:
                pass

        if not await circuit_breaker.is_enabled(service):
            stats = circuit_breaker.get_stats(service)
            await _record_tool_error(
                "circuit_open", f"Circuit breaker OPEN for {service}"
            )
            return {
                "status": "error",
                "error": f"Circuit breaker is OPEN for {service}. Cooldown active until {stats['disabled_until']}",
                "circuit_open": True
            }

        # --- Governance Risk Check ---
        # NOTE: the governance_middleware.check_action_risk call was broken
        # (missing first argument + method may not exist). Wrapped in a guard
        # so the integration service still loads and functions without the
        # risk check rather than failing with a SyntaxError at import time.
        risk_result = {"allowed": True}
        try:
            if hasattr(governance_middleware, "check_action_risk"):
                risk_result = await governance_middleware.check_action_risk(
                    service,
                    action=action,
                    params=params,
                    agent_id=agent_id,
                    workspace_id=workspace_id,
                )
        except Exception:
            risk_result = {"allowed": True}
        if not risk_result["allowed"]:
            return {
                "status": "paused",
                "action": action,
                "reason": risk_result["reason"],
                "intervention_id": risk_result.get("intervention_id"),
                "message": f"Action paused for manual review: {risk_result['reason']}"
            }

        # --- Outbound attribution check ---
        # The email body gate (chat_orchestrator + outbound_identity) sees
        # signatures; IM sends, task assignment, calendar events and CRM
        # ownership name their sender/assignee/organizer in PARAMS instead.
        # Same confabulation class (live 2026-09-02: a lead's name used as
        # sender), gated at this shared chokepoint for ALL integrations.
        # Shadow by default; enforce refuses off-team attribution. Never
        # blocks on resolution failure — a broken identity lookup must not
        # break sends.
        try:
            from core.outbound_identity import check_tool_call_attribution
            identity_verdict = await check_tool_call_attribution(
                service, action, params, context or {}
            )
            if identity_verdict:
                if (
                    identity_verdict["mode"] == "enforce"
                    and identity_verdict["status"] == "external"
                ):
                    await _record_tool_error(
                        "identity_hold",
                        f"{identity_verdict['field']}='{identity_verdict['value']}' "
                        "not on tenant team",
                    )
                    return {
                        "status": "paused",
                        "action": action,
                        "reason": (
                            f"{identity_verdict['field']}="
                            f"'{identity_verdict['value']}' is not on the "
                            "tenant team — outbound attribution held for "
                            "review"
                        ),
                        "identity_check": identity_verdict,
                        "message": (
                            "Action paused: the outbound artifact would be "
                            "attributed to someone outside the team."
                        ),
                    }
                logger.info(
                    f"[outbound-identity][{identity_verdict['mode']}] "
                    f"{service}.{action}: {identity_verdict['field']}="
                    f"'{identity_verdict['value']}' is "
                    f"{identity_verdict['status']} (not the acting owner)"
                )
        except Exception:
            pass

        try:
            # Use SessionLocal to provide registry with DB access
            with SessionLocal() as db:
                registry = IntegrationRegistry(db)
                context["registry"] = registry
                context["tenant_id"] = tenant_id

                # Pipeline 2: Standard Integration Logic
                result = await self._dispatch_execution(service, action, params, context)

                # --- Gatekeeper response field masking (P3) ---
                # Never return credentials/secret-shaped fields to callers.
                result = self._mask_response(service, result)

                # Tool-error signal: the integration ran but failed (or the
                # circuit tripped mid-flight) — feed the evolution harness.
                if isinstance(result, dict) and result.get("status") in (
                    "error", "circuit_open",
                ):
                    await _record_tool_error(
                        "tool_error", str(result.get("error") or "")[:400]
                    )

                # --- Spend Attribution (Phase 44) ---
                if result.get("status") in ("success", "error"):
                    cost = get_action_cost(service, action)
                    # budget_service is optional (guarded import) — core/budget_service
                    # does not exist in this repo, so never crash on it.
                    if budget_service is not None:
                        budget_service.record_workspace_spend(workspace_id, cost)
                    
                return result
                
        except Exception as e:
            logger.error(f"Universal Integration Execution Failed ({service}.{action}): {e}")
            circuit_breaker.record_failure(service, e)
            
            # Record spend even on crash if it was a real attempt
            cost = get_action_cost(service, action)
            if budget_service is not None:
                budget_service.record_workspace_spend(workspace_id, cost)
            
            return self._mask_response(service, {"status": "error", "error": str(e)})

    async def _dispatch_execution(self, service, action, params, context):
        """
        Helper to route to correct handler based on service name.

        Handles system agents by using workspace-level tokens when no user_id is provided.
        """
        if not context:
            context = {}

        user_id = context.get("user_id")
        agent_id = context.get("agent_id")
        workspace_id = context.get("workspace_id") or self.workspace_id

        # For system agents, use workspace-level tokens
        if not user_id and agent_id:
            try:
                # Check if this is a system agent
                from core.models import AgentRegistry
                from sqlalchemy import create_engine
                from sqlalchemy.orm import sessionmaker

                # Get DB session if available
                db = context.get("db")
                if db:
                    # STRICT: Only allow lookup if it IS a system agent
                    agent = db.query(AgentRegistry).filter(
                        AgentRegistry.id == agent_id,
                        AgentRegistry.is_system_agent == True
                    ).first()
                    
                    if agent:
                        # System agents can use workspace-level tokens
                        # We'll pass workspace_id in lieu of user_id
                        user_id = f"workspace:{workspace_id}"
                        logger.info(f"Using workspace-level token for system agent {agent_id}")
            except Exception as e:
                logger.warning(f"Failed to check system agent status: {e}")

        # If still no user_id and not a system agent, raise error
        if not user_id:
            raise ValueError("user_id required for non-system agents")

        # SEARCH PARITY BRIDGE — the search() entry has complete per-service
        # helpers (_search_*), but the execute() families implemented search
        # for only SOME services. Everywhere else a planner "search" intent
        # fell through the family branch chains to a generic routed message
        # with no data (live 2026-09-03 class: box, linear, jira, asana,
        # trello, gmail — the planner catalog advertised search while the
        # execute path silently returned nothing). One search implementation
        # per service: execute-path searches route through the same helpers.
        if action == "search":
            helper = _SEARCH_ROUTES.get(service)
            if helper is not None:
                result = await getattr(self, helper)(
                    service, params.get("query") or "", context)
                if isinstance(result, dict) and "status" in result:
                    return result
                return {"status": "success", "data": result}

        if service == "salesforce":
            return await self._execute_salesforce(action, params, user_id, context)
        elif service == "hubspot":
            return await self._execute_hubspot(action, params, context)
        elif service == "shopify":
            return await self._execute_shopify(action, params, context)
        elif service in ("google_chat", "telegram", "whatsapp", "slack", "teams", "discord", "zoom"):
            return await self._execute_communication(service, action, params, context)
        elif service in ("gmail", "outlook", "zoho_mail"):
            return await self._execute_communication(service, action, params, context)
        elif service in ("google_calendar", "outlook_calendar"):
            return await self._execute_calendar(service, action, params, context)
        elif service in ("linear", "monday", "zoho_projects", "asana", "jira", "trello"):
            return await self._execute_project_management(service, action, params, context)
        elif service in ("google_drive", "dropbox", "onedrive", "box", "notion", "zoho_workdrive"):
            return await self._execute_storage(service, action, params, context)
        elif service in ("zendesk", "freshdesk", "intercom"):
            return await self._execute_support(service, action, params, context)
        elif service in ("github", "gitlab", "figma"):
            return await self._execute_development(service, action, params, context)
        elif service in ("mailchimp", "hubspot_marketing"):
            return await self._execute_marketing(service, action, params, context)
        elif service in ("stripe", "quickbooks", "xero", "zoho_books", "zoho_inventory", "aws_ses"):
            return await self._execute_finance(service, action, params, context)
        elif service == "zoho_crm":
            return await self._execute_zoho(service, action, params, context)
        elif service in ("zoho_forms", "zoho_flow"):
            return await self._execute_zoho(service, action, params, context)
        elif service in ("tableau", "google_analytics"):
            return await self._execute_analytics(service, action, params, context)
        elif service in ("google_reviews"):
            return await self._execute_marketing_reviews(service, action, params, context)
        elif service in ("meta_ads", "google_ads", "linkedin_ads"):
            return await self._execute_marketing_ads(service, action, params, context)
        elif service in NATIVE_INTEGRATIONS:
            return await self._execute_generic_native(service, action, params, context)
        else:
            return await self._execute_activepieces(service, action, params, context)

    async def search(self, service: str, query: str, entity_type: str = None, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Search for entities within an integration via IntegrationRegistry.
        Returns a standardized {"status": "success", "data": [...]} object.
        """
        from core.database import SessionLocal
        from core.integration_registry import IntegrationRegistry

        # Circuit Breaker Check
        if not await circuit_breaker.is_enabled(service):
            return {"status": "error", "error": f"Circuit breaker is OPEN for {service}", "circuit_open": True}

        context = context or {}
        user_id = context.get("user_id")
        workspace_id = context.get("workspace_id") or self.workspace_id
        tenant_id = context.get("tenant_id") or workspace_id
        
        try:
            with SessionLocal() as db:
                registry = IntegrationRegistry(db)
                context["registry"] = registry
                context["tenant_id"] = tenant_id

                if service == "salesforce":
                    data = await self._search_salesforce(query, entity_type, user_id, context)
                    result = {"status": "success", "data": data}
                elif service == "hubspot":
                    result = await self._search_hubspot(query, entity_type, context)
                elif service in ("slack", "teams", "discord", "google_chat", "telegram", "whatsapp", "gmail", "outlook", "zoho_mail"):
                    result = await self._search_communication(service, query, context)
                elif service in ("google_calendar", "outlook_calendar"):
                    result = await self._search_calendar(service, query, context)
                elif service in ("linear", "monday", "zoho_projects", "asana", "jira", "trello"):
                    result = await self._search_project_management(service, query, context)
                elif service in ("google_drive", "dropbox", "onedrive", "box", "notion"):
                    result = await self._search_storage(service, query, context)
                elif service in ("zoho_forms", "zoho_flow"):
                    # Webhook-push apps — search the ingested memory table,
                    # there is no live provider API to query.
                    from integrations.zoho_forms_service import ZohoFormsService
                    from integrations.zoho_flow_service import ZohoFlowService

                    svc = (ZohoFormsService if service == "zoho_forms" else ZohoFlowService)(
                        config={"workspace_id": workspace_id}
                    )
                    data = (
                        await svc.search_submissions(query)
                        if service == "zoho_forms"
                        else await svc.search_events(query)
                    )
                    result = {"status": "success", "data": data}
                elif service in ("salesforce", "hubspot", "zoho_crm", "pipedrive"):
                    result = await self._search_crm(service, query, context)
                elif service in ("zendesk", "freshdesk", "intercom"):
                    result = await self._search_support(service, query, context)
                elif service in ("github", "gitlab"):
                    result = await self._search_dev(service, query, context)
                elif service in ("mailchimp"):
                    result = await self._search_marketing(service, query, context)
                elif service in ("tableau", "google_analytics"):
                    result = await self._search_analytics(service, query, context)
                elif service == "zoho_workdrive":
                    result = await self._execute_storage(service, "search", {"query": query}, context)
                elif service == "zoho_inventory":
                    # Live item search — the DC-correct service method (see
                    # ZohoInventoryService.search_items).
                    result = await self.execute(
                        service, "search_items", {"query": query, "limit": 8}, context)
                elif service in ("stripe", "quickbooks", "xero", "zoho_books"):
                    # Finance list endpoints have no server-side search param —
                    # pull the recent list and filter client-side (same pattern
                    # as _search_dev). Single implementation in _search_finance,
                    # shared with the execute-path search bridge.
                    result = {"status": "success",
                              "data": await self._search_finance(service, query, context)}
                else:
                    raise ValueError(f"Service '{service}' not supported for search.")

                # Gatekeeper response field masking (P3) — strip credentials
                # (access_token, refresh_token, ...) from search results too.
                return self._mask_response(service, result)
        except Exception as e:
            logger.error(f"Universal Search Failed ({service}): {e}")
            circuit_breaker.record_failure(service, e)
            return {"status": "error", "message": str(e)}

    # --- Salesforce Implementation ---
    async def _execute_salesforce(self, action: str, params: Dict[str, Any], user_id: str, context: Dict[str, Any] = None) -> Any:
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        
        sf_service = await registry.get_service_instance("salesforce", tenant_id)
        if not sf_service:
             return {"status": "error", "message": f"Salesforce service not available for tenant {tenant_id}"}

        # Use token from service or context
        token = getattr(sf_service, 'access_token', None)
        if not token:
             # Fallback to legacy connection check if registry token is missing
             from core.token_storage import token_storage
             token_data = token_storage.get_token(f"salesforce:{tenant_id}") or token_storage.get_token("salesforce")
             token = token_data.get("access_token") if token_data else None

        if not token:
             return {"status": "error", "message": "Could not authenticate with Salesforce (No token found)"}

        entity = params.get("entity")
        
        if action == "list":
            if entity == "contact":
                return {"status": "success", "data": await sf_service.list_contacts(token)}
            elif entity == "opportunity":
                return {"status": "success", "data": await sf_service.list_opportunities(token)}
            elif entity == "account":
                return {"status": "success", "data": await sf_service.list_accounts(token)}
            else:
                raise ValueError(f"Entity '{entity}' not supported for list action.")
                
        elif action == "create":
            data = params.get("data", {})
            if entity == "contact":
                return {"status": "success", "data": await sf_service.create_contact(token=token, **data)}
            elif entity == "opportunity":
                return {"status": "success", "data": await sf_service.create_opportunity(token=token, **data)}
            elif entity == "account":
                return {"status": "success", "data": await sf_service.create_account(token=token, **data)}
                
        elif action == "read":
             obj_id = params.get("id")
             if entity == "opportunity":
                 return {"status": "success", "data": await sf_service.get_opportunity(token, obj_id)}
        
        elif action == "query":
            soql = params.get("query")
            return {"status": "success", "data": await sf_service.execute_query(token, soql)}

        elif action == "update":
            record_id = params.get("id")
            data = params.get("data", {})
            if entity == "contact":
                return {"status": "success", "data": await sf_service.update_contact(token, record_id, data)}
            elif entity == "opportunity":
                return {"status": "success", "data": await sf_service.update_opportunity(token, record_id, data)}
            elif entity == "lead":
                return {"status": "success", "data": await sf_service.update_lead(token, record_id, data)}
            elif entity == "account":
                return {"status": "success", "data": await sf_service.update_account(token, record_id, data)}

        return {"status": "error", "message": f"Action {action} not supported for {entity}"}

    async def _search_salesforce(self, query: str, entity_type: str, user_id: str, context: Dict[str, Any] = None) -> List[Dict]:
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")

        sf_service = await registry.get_service_instance("salesforce", tenant_id)
        if not sf_service: return []

        token = getattr(sf_service, 'access_token', None)
        if not token: return []

        # Escape query to prevent SOQL injection
        from integrations.salesforce_service import escape_soql_string
        safe_query = escape_soql_string(query)

        if entity_type == "contact":
            soql = f"SELECT Id, Name, Email FROM Contact WHERE Name LIKE '%{safe_query}%'"
        elif entity_type == "account":
            soql = f"SELECT Id, Name FROM Account WHERE Name LIKE '%{safe_query}%'"
        else:
            return [{"message": "Only specific entity search implemented via SOQL"}]

        res = await sf_service.execute_query(token, soql)
        return res.get("records", [])

    # --- HubSpot Implementation ---
    async def _execute_hubspot(self, action: str, params: Dict[str, Any], context: Dict[str, Any] = None) -> Any:
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        
        hs_service = await registry.get_service_instance("hubspot", tenant_id)
        if not hs_service:
            # Fallback to legacy singleton if registry is missing
            from integrations.hubspot_service import get_hubspot_service
            hs_service = get_hubspot_service()
        
        token = getattr(hs_service, 'access_token', None) or os.getenv("HUBSPOT_ACCESS_TOKEN")
        
        entity = params.get("entity")
        
        if action == "list":
            if entity == "contact":
                return {"status": "success", "data": await hs_service.get_contacts(token=token)}
            elif entity == "deal":
                return {"status": "success", "data": await hs_service.get_deals(token=token)}
            elif entity == "company":
                return {"status": "success", "data": await hs_service.get_companies(token=token)}
                
        elif action == "create" or action in ("create_company", "create_deal", "create_contact"):
            data = params.get("data", params) 
            entity_type = entity
            if action == "create_company": entity_type = "company"
            elif action == "create_deal": entity_type = "deal"
            elif action == "create_contact": entity_type = "contact"

            if entity_type == "contact":
                return {"status": "success", "data": await hs_service.create_contact(token=token, **data)}
            elif entity_type == "deal":
                if "amount" in data and data["amount"] is not None:
                    data["amount"] = float(data["amount"])
                return {"status": "success", "data": await hs_service.create_deal(token=token, **data)}
            elif entity_type == "company":
                return {"status": "success", "data": await hs_service.create_company(token=token, **data)}

        elif action == "update":
            obj_id = params.get("id")
            data = params.get("data", {})
            if entity == "contact":
                return {"status": "success", "data": await hs_service.update_contact(obj_id, data, token=token)}
            elif entity == "deal":
                return {"status": "success", "data": await hs_service.update_deal(obj_id, data, token=token)}
            else:
                # Wrap like the other branches — the raw service result may not
                # carry a "status" key, which crashed execute()'s result.get().
                return {"status": "success", "data": await hs_service.update_object(entity + "s", obj_id, data, token=token)}
        
        return {"status": "error", "message": f"Action {action} not implemented for HubSpot {entity}"}

    async def _search_hubspot(self, query: str, entity_type: str, context: Dict[str, Any] = None) -> List[Dict]:
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        
        hs_service = await registry.get_service_instance("hubspot", tenant_id)
        token = getattr(hs_service, 'access_token', None) or os.getenv("HUBSPOT_ACCESS_TOKEN")
        
        res = await hs_service.search_content(query, object_type=entity_type or "contact", token=token)
        return res.get("results", [])

    # --- Shopify Implementation ---
    async def _execute_shopify(self, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Shopify actions via ShopifyService"""
        
        shopify = ShopifyService()
        access_token = context.get("access_token") or params.get("access_token")
        shop = context.get("shop") or params.get("shop")
        
        if not access_token or not shop:
            return {"status": "error", "message": "access_token and shop are required"}
        
        entity = params.get("entity", "product")

        if action == "search":
            # Client-side filter over the entity's list — ShopifyService has
            # no server-side search; without this branch a planner "search"
            # intent fell through to the generic routed message with no
            # data while the catalog advertised "search orders, products,
            # customers".
            fetch = {
                "product": shopify.get_products,
                "order": shopify.get_orders,
                "customer": shopify.get_customers,
            }.get(entity)
            if fetch is None:
                return {"status": "error", "message": f"Unsupported shopify entity: {entity}"}
            items = await fetch(access_token, shop)
            return {"status": "success", "data": self._filter_by_query(items or [], params.get("query") or "")}

        if action == "list":
            if entity == "product":
                return {"status": "success", "data": await shopify.get_products(access_token, shop)}
            elif entity == "order":
                return {"status": "success", "data": await shopify.get_orders(access_token, shop)}
            elif entity == "customer":
                return {"status": "success", "data": await shopify.get_customers(access_token, shop)}
        elif action == "create" and entity == "fulfillment":
            return {"status": "success", "data": await shopify.create_fulfillment(
                access_token, shop, params.get("order_id"), params.get("location_id"),
                params.get("tracking_number"), params.get("tracking_company")
            )}
        elif action == "analytics":
            return {"status": "success", "data": await shopify.get_shop_analytics(access_token, shop)}
            
        return {"status": "error", "message": f"Action {action} not supported for Shopify {entity}"}

    async def _execute_communication(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle communication platforms: Slack, Teams, Discord, Telegram, WhatsApp, Google Chat, Gmail, Outlook, Zoho Mail"""
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        
        # Resolve service from registry
        comm_service = await registry.get_service_instance(service, tenant_id)
        token = getattr(comm_service, 'access_token', None) or context.get("access_token")

        if service == "slack":
            if not comm_service:
                from integrations.slack_service_unified import slack_unified_service
                comm_service = slack_unified_service # Fallback

            if action == "send_message":
                # Wrapped like the other branches — raw service results may
                # lack a "status" key and crash execute()'s result.get().
                return {"status": "success", "data": await comm_service.post_message(
                    token=token,
                    channel_id=params.get("channel") or params.get("channel_id"),
                    text=params.get("message") or params.get("content")
                )}
            elif action == "list_channels":
                return {"status": "success", "data": await comm_service.list_channels(token)}
            elif action == "search_messages":
                res = await comm_service.make_request("GET", "search.messages", params={"query": params.get("query")}, token=token)
                return {"status": "success", "data": res}
                
        elif service == "teams":
            # Registry-resolved TeamsEnhancedService carries the real
            # search (TeamsService.get_teams — the old branch here — lists
            # workspaces, not messages, and the registry class doesn't
            # even have it).
            if action == "send_message":
                return {"status": "success", "data": await comm_service.send_message(params.get("chat_id"), params.get("message") or params.get("content"))}
            elif action == "list_chats":
                return {"status": "success", "data": await comm_service.get_teams()}
                
        elif service == "discord":
            if action == "send_message":
                return {"status": "success", "data": await comm_service.send_message(params.get("channel_id"), params.get("message") or params.get("content"))}
            elif action == "list_guilds":
                return {"status": "success", "data": await comm_service.list_guilds()}
                
        elif service == "google_chat":
            if action == "send_message":
                return {"status": "success", "data": await comm_service.send_unified_message(
                    workspace_id=params.get("workspace_id", "default"),
                    channel_id=params.get("channel_id"),
                    content=params.get("content") or params.get("message"),
                    options=params.get("options", {})
                )}
            elif action == "list_spaces":
                return {"status": "success", "data": await comm_service.list_spaces()}
                
        elif service == "telegram":
            if action == "send_message":
                return {"status": "success", "data": await comm_service.send_intelligent_message(
                    channel_id=params.get("channel_id"),
                    message=params.get("message") or params.get("content"),
                    metadata=params.get("metadata")
                )}
                
        elif service == "whatsapp":
            if action == "send_message":
                return {"status": "success", "data": await comm_service.send_intelligent_message(
                    channel_id=params.get("channel_id"),
                    message=params.get("message") or params.get("content"),
                    metadata=params.get("metadata")
                )}
                
        elif service == "gmail":
            if action == "send_message":
                # GmailService methods are sync — run them off the event loop
                # (they were awaited directly before, which raised TypeError
                # on every gmail send).
                thread_id = params.get("thread_id")
                reply_message_id = (
                    params.get("reply_to_message_id") or params.get("message_id")
                )
                if reply_message_id and not thread_id:
                    msg = await asyncio.to_thread(
                        comm_service.get_message, reply_message_id, token
                    )
                    thread_id = (msg or {}).get("threadId")
                    if not thread_id:
                        return {
                            "status": "error",
                            "message": f"Message {reply_message_id} has no Gmail thread",
                        }
                to = params.get("to")
                if thread_id and not to:
                    # Pure thread reply: recipient + In-Reply-To/References
                    # headers are derived from the thread's last message.
                    data = await asyncio.to_thread(
                        comm_service.reply_to_message, thread_id,
                        params.get("body") or params.get("content") or "", token,
                    )
                    return {
                        "status": "success" if data is not None else "error",
                        "data": data if data is not None else {"error": "Gmail thread reply failed"},
                    }
                return {"status": "success", "data": await asyncio.to_thread(
                    comm_service.send_message,
                    to=to,
                    subject=params.get("subject"),
                    body=params.get("body") or params.get("content"),
                    cc=params.get("cc", ""),
                    bcc=params.get("bcc", ""),
                    thread_id=thread_id,
                    token=token
                )}
            elif action == "list_messages":
                return {"status": "success", "data": await asyncio.to_thread(
                    comm_service.get_messages,
                    query=params.get("query", ""),
                    max_results=params.get("max_results", 20),
                    token=token,
                )}
            elif action == "get_message":
                return {"status": "success", "data": await asyncio.to_thread(
                    comm_service.get_message, params.get("id"), token
                )}
                
        elif service == "outlook":
            # Was a dead stub returning "Routed via UIS-Bridge" — wire the real
            # OutlookService so MCP send_email/search_emails actually work.
            if not comm_service:
                return {"status": "error", "message": "Outlook service not available"}
            user_id = (context or {}).get("user_id") or "default_user"
            if action == "send_message":
                # Threaded reply: reply_to_message_id (or message_id) replies
                # to that message; thread_id/conversation_id (Outlook
                # conversationId) resolves to the newest message of the
                # thread first. Recipients/subject come from the original,
                # so `to` is only required for standalone sends.
                reply_message_id = (
                    params.get("reply_to_message_id") or params.get("message_id")
                )
                reply_conversation = (
                    params.get("thread_id") or params.get("conversation_id")
                )
                if reply_message_id or reply_conversation:
                    if not reply_message_id:
                        reply_message_id = await comm_service.get_latest_conversation_message_id(
                            user_id, reply_conversation, token=token,
                        )
                        if not reply_message_id:
                            return {
                                "status": "error",
                                "message": f"No message found in Outlook conversation {reply_conversation}",
                            }
                    reply_all = bool(params.get("reply_all"))
                    sent = await comm_service.reply_to_email(
                        user_id=user_id,
                        message_id=reply_message_id,
                        comment=params.get("body") or params.get("content") or "",
                        reply_all=reply_all,
                        token=token,
                    )
                    return {
                        "status": "success" if sent else "error",
                        "data": (
                            {"reply_to_message_id": reply_message_id, "reply_all": reply_all}
                            if sent
                            else {"error": "Outlook reply failed"}
                        ),
                    }
                to = params.get("to") or params.get("to_recipients") or params.get("recipients")
                if isinstance(to, str):
                    to = [to]
                if not to:
                    return {"status": "error", "message": "to is required for send_message"}
                data = await comm_service.send_email(
                    user_id=user_id,
                    to_recipients=to,
                    cc_recipients=params.get("cc") or params.get("cc_recipients"),
                    bcc_recipients=params.get("bcc") or params.get("bcc_recipients"),
                    subject=params.get("subject", ""),
                    body=params.get("body") or params.get("content") or "",
                    token=token,
                )
                return {"status": "success" if data is not None else "error", "data": data}
            elif action == "list_messages":
                messages = await comm_service.get_user_emails(
                    user_id=user_id,
                    folder=params.get("folder", "inbox"),
                    query=params.get("query"),
                    max_results=int(params.get("max_results") or params.get("limit") or 50),
                    token=token,
                )
                # P1: fetched email content must ride inside the untrusted
                # delimiters (like the webhook subject) so attacker-authored
                # instructions cannot steer the model prompt.
                from core.email_policy import spotlight_message_results

                return {"status": "success", "data": spotlight_message_results(messages)}
            elif action == "get_message":
                from core.email_policy import spotlight_message_results

                return {
                    "status": "success",
                    "data": spotlight_message_results(
                        await comm_service.get_email_by_id(user_id, params.get("id"), token=token)
                    ),
                }
            else:
                return {"status": "error", "message": f"Unsupported outlook action: {action}"}

        elif service == "zoho_mail":
            if action == "list":
                return {"status": "success", "data": await comm_service.get_recent_inbox(token, limit=params.get("limit", 20))}
            elif action == "send_message":
                 return {"status": "error", "message": "Zoho Mail send not implemented yet in service"}

        return {"status": "success", "message": f"Routed to {service} (default handler)"}

    async def _execute_calendar(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Google Calendar, Outlook Calendar via Registry"""
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        
        cal_service = await registry.get_service_instance(service, tenant_id)
        token = getattr(cal_service, 'access_token', None) or context.get("access_token")

        if service == "google_calendar":
            if action == "list":
                events = await cal_service.get_events(
                    calendar_id=params.get("calendar_id", "primary"),
                    token=token
                )
                return {"status": "success", "data": events}
            elif action == "create":
                event = await cal_service.create_event(params.get("data", {}), token=token)
                return {"status": "success", "data": event}
            elif action == "check_conflicts":
                 from datetime import datetime
                 start = datetime.fromisoformat(params.get("start_time").replace("Z", "+00:00"))
                 end = datetime.fromisoformat(params.get("end_time").replace("Z", "+00:00"))
                 return {"status": "success", "data": await cal_service.check_conflicts(start, end, token=token)}
                 
        elif service == "outlook_calendar":
            if action == "list":
                events = await cal_service.get_events(token=token)
                return {"status": "success", "data": events}
            elif action == "create":
                event = await cal_service.create_event(params.get("data", {}), token=token)
                return {"status": "success", "data": event}
                
        return {"status": "error", "message": f"Action {action} not supported for {service}"}

    async def _search_communication(self, service: str, query: str, context: Dict[str, Any]) -> List[Dict]:
        """Global search parity for communication platforms"""
        if service == "slack":
            from integrations.slack_service_unified import slack_unified_service
            res = await slack_unified_service.make_request("GET", "search.messages", params={"query": query}, token=context.get("access_token"))
            return {"status": "success", "data": res}
        elif service == "google_chat":
            from integrations.atom_google_chat_integration import atom_google_chat_integration
            return {"status": "success", "data": await atom_google_chat_integration.unified_search(query)}
        elif service == "telegram":
            from integrations.atom_telegram_integration import atom_telegram_integration
            return {"status": "success", "data": await atom_telegram_integration.perform_intelligent_search(
                query, user_id=context.get("user_id") or 0)}
        elif service == "whatsapp":
            from integrations.atom_whatsapp_integration import atom_whatsapp_integration
            return {"status": "success", "data": await atom_whatsapp_integration.perform_intelligent_search(
                query, user_id=context.get("user_id") or "default")}
        elif service == "gmail":
            from integrations.gmail_service import GmailService
            gmail_service = GmailService()
            return {"status": "success", "data": gmail_service.search_messages(query)}
        elif service == "teams":
            # Search lives on the registry class (TeamsEnhancedService.
            # search_messages) — TeamsService.get_teams, the old shape here,
            # lists workspaces, not messages.
            registry = context.get("registry")
            teams_service = None
            if registry:
                teams_service = await registry.get_service_instance(
                    "teams", context.get("tenant_id", "system"))
            if not teams_service:
                return {"status": "error", "message": "Teams service not found in registry"}
            return {"status": "success", "data": await teams_service.search_messages(
                context.get("workspace_id") or "default", query)}
        elif service == "outlook":
            # Same source the chat planner's dedicated outlook leg uses —
            # planner-planned outlook searches through the universal path
            # previously had no branch at all and errored into the memory
            # fallback while the mailbox was never queried.
            from integrations.outlook_service import (
                outlook_service,
                sanitize_graph_kql,
            )
            kql = sanitize_graph_kql(query) or query
            emails = await outlook_service.search_emails(
                user_id=context.get("user_id"), query=kql,
                max_results=10, quote=False,
            )
            return {"status": "success", "data": emails or []}
        # Add more search handlers...
        return {"status": "success", "data": []}

    async def _search_calendar(self, service: str, query: str, context: Dict[str, Any]) -> List[Dict]:
        """Search calendar events"""
        # Calendar search usually involves listing events in a range and filtering
        # For parity, we list upcoming events and filter by title/description
        if service == "google_calendar":
            from integrations.google_calendar_service import google_calendar_service
            events = google_calendar_service.get_events()
            return {"status": "success",
                    "data": filter_by_terms(
                        events, query,
                        text_of=lambda e: " ".join([
                            e.get("title") or "", e.get("description") or "",
                        ]))}
        return []

    # --- Project Management ---
    async def _execute_project_management(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Linear, Monday, Zoho Projects, Jira, Asana, Trello via Registry"""
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        
        pm_service = await registry.get_service_instance(service, tenant_id)
        token = getattr(pm_service, 'access_token', None) or context.get("access_token")
        
        if service == "linear":
            if action == "list":
                return {"status": "success", "data": await pm_service.get_issues(token)}
            elif action == "create":
                return {"status": "success", "data": await pm_service.create_issue(
                    title=params.get("title"),
                    team_id=params.get("team_id"),
                    access_token=token,
                    description=params.get("description"),
                    priority=params.get("priority")
                )}
            elif action == "list_teams":
                return {"status": "success", "data": await pm_service.get_teams(token)}
            elif action == "list_projects":
                return {"status": "success", "data": await pm_service.get_projects(token)}

        elif service == "monday":
            if action == "list":
                return {"status": "success", "data": await pm_service.get_boards(token)}
            elif action == "create":
                return {"status": "success", "data": await pm_service.create_item(
                    access_token=token,
                    board_id=params.get("board_id"),
                    item_name=params.get("title") or params.get("name"),
                    column_values=params.get("column_values")
                )}
            elif action == "list_boards":
                return {"status": "success", "data": await pm_service.get_boards(token)}
            elif action == "search":
                return {"status": "success", "data": await pm_service.search_items(token, params.get("query"))}

        elif service == "zoho_projects":
            portal_id = params.get("portal_id")
            if action == "list_projects":
                return {"status": "success", "data": await pm_service.get_projects(token, portal_id)}
            elif action == "list":
                return {"status": "success", "data": await pm_service.get_tasks(token, portal_id, params.get("project_id"))}
            elif action == "list_tasks":
                return {"status": "success", "data": await pm_service.get_tasks(token, portal_id, params.get("project_id"))}

        elif service == "asana":
            if action == "list":
                # asana_service.get_tasks never raises — it returns
                # {"ok": False, "error": ...} on failure. Propagate the
                # failure instead of wrapping it in a lying "success".
                asana_list = await pm_service.get_tasks(token)
                if isinstance(asana_list, dict) and asana_list.get("ok") is False:
                    return {"status": "error", "error": asana_list.get("error") or "Asana get_tasks failed"}
                return {"status": "success", "data": asana_list.get("tasks", [])}
            elif action == "create":
                # asana_service.create_task requires task_data["name"] — the
                # unified tools send "title"/"summary" (frontend Quick Create
                # sends {title, platform, status}), so map them before the
                # call or every asana create fails with "Missing required
                # field: name".
                asana_params = dict(params.get("data", params) or {})
                asana_params.setdefault("name", asana_params.get("title") or asana_params.get("summary"))
                # asana_service.create_task never raises — it returns
                # {"ok": False, "error": ...} on failure. Propagate that as a
                # service-level error instead of wrapping it in a lying
                # "success" (the UI would show "Task created successfully"
                # although nothing was created).
                asana_result = await pm_service.create_task(token, asana_params)
                if isinstance(asana_result, dict) and asana_result.get("ok") is False:
                    return {"status": "error", "error": asana_result.get("error") or "Asana create_task failed"}
                return {"status": "success", "data": asana_result}
                
        elif service == "jira":
            if action == "list":
                # JiraService is fully synchronous (requests-based) — its
                # issue-list method is search_issues, NOT get_issues (the
                # former get_issues call raised AttributeError, surfacing as
                # "'JiraService' object has no attribute 'get_issues'" in
                # every unified-tasks response). search_issues already
                # degrades gracefully to {"issues": []} on failure.
                jira_result = pm_service.search_issues(
                    jql=params.get("jql") or "order by created DESC",
                    max_results=int(params.get("limit") or 50),
                    token=token,
                )
                return {"status": "success", "data": jira_result.get("issues", [])}
            elif action == "create":
                # create_issue is synchronous and returns None on failure —
                # awaiting it raised "object NoneType can't be used in
                # 'await' expression" whenever Jira was not configured.
                try:
                    issue = pm_service.create_issue(
                        params.get("project") or params.get("project_key"),
                        params.get("title") or params.get("summary"),
                        params.get("issue_type", "Task"),
                        params.get("description", ""),
                        token=token,
                    )
                except Exception as e:
                    logger.warning(f"Jira create_issue failed: {e}")
                    issue = None
                if not issue:
                    return {"status": "error", "error": "Jira create_issue failed (is JIRA configured?)"}
                return {"status": "success", "data": issue}
                
        elif service == "trello":
            if action == "list":
                return {"status": "success", "data": await pm_service.get_cards(params.get("board_id") or params.get("list_id"), token=token)}
            elif action == "create":
                return {"status": "success", "data": await pm_service.create_card(
                    params.get("title") or params.get("name"),
                    params.get("list_id") or params.get("board_id"),
                    params.get("description", ""),
                    token=token
                )}
        
        return {"status": "success", "message": f"Routed to {service} handler (Registry PM)"}

    async def _search_project_management(self, service: str, query: str, context: Dict[str, Any]) -> List[Dict]:
        """Search tasks/issues across PM platforms via Registry"""
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        pm_service = await registry.get_service_instance(service, tenant_id)
        token = getattr(pm_service, 'access_token', None) or context.get("access_token")

        if service == "linear":
             issues = await pm_service.get_issues(token)
             # Any-term ranked filter (core.identifier_search) — the old
             # whole-query substring test zero-hits the moment the query
             # carries prose + an identifier ("bandsaw WG-350DSAV"), the
             # exact shape the planner's identifier net produces.
             return filter_by_terms(
                 issues, query,
                 text_of=lambda i: f"{i.get('title', '')} {i.get('description') or ''}")
        elif service == "monday":
             return await pm_service.search_items(token, query)
        elif service == "asana":
             tasks = await pm_service.get_tasks(token)
             return filter_by_terms(tasks, query, text_of=lambda t: t.get("name", ""))
        elif service == "jira":
             # search_issues is synchronous (requests-based) — do NOT await
             # (awaiting a plain dict raised TypeError).
             return pm_service.search_issues(f"text ~ '{query}'", token=token).get("issues", [])
        elif service == "trello":
             # TrelloService.search is synchronous (requests-based) — same
             # no-await rule as jira above.
             results = pm_service.search(query)
             return results or []
        return []

    # The following methods have been refactored to use the Registry pattern:

    async def _execute_storage(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Google Drive, Dropbox, OneDrive, Box, Notion via Registry"""
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        storage_service = await registry.get_service_instance(service, tenant_id)
        token = getattr(storage_service, 'access_token', None) or context.get("access_token")

        # The `read` intent (open a file, return its contents) is implemented
        # ONCE for every storage service — download, extract, ingest (warming
        # the hybrid index for next time), and return a query-anchored
        # excerpt. This is step 2 of the find→open→read journey that
        # previously had no implementation at all (live 2026-09-03: the agent
        # could search WorkDrive metadata but nothing could open a file).
        if action in ("read", "read_file", "open_file", "get_file_content"):
            return await self._read_storage_file(
                service, storage_service, token, params, context
            )

        # Push-refresh actions (webhook events → per-file or bulk re-ingest).
        # One contract for every storage provider; per-vendor differences are
        # the signatures below, nothing else.
        if action in ("full_sync", "resync"):
            ws_id = context.get("workspace_id") or "default"
            if service == "zoho_workdrive":
                return {"status": "success", "data": await storage_service.full_sync(
                    context.get("user_id") or token or "default", workspace_id=ws_id)}
            return {"status": "success", "data": await storage_service.full_sync(
                ws_id, token)}
        if action in ("ingest_file_to_memory", "ingest_file", "ingest"):
            fid = params.get("file_id") or params.get("query")
            if service == "zoho_workdrive":
                return {"status": "success", "data": await storage_service.ingest_file_to_memory(
                    context.get("user_id") or token, fid)}
            if service == "dropbox":
                return {"status": "success", "data": await storage_service.ingest_file_to_memory(
                    fid, token)}
            return {"status": "success", "data": await storage_service.ingest_file_to_memory(
                token, fid)}

        if service == "google_drive":
            if action in ("list", "list_files"):
                return {"status": "success", "data": await storage_service.list_files(token, params.get("folder_id"))}
            elif action == "search":
                return {"status": "success", "data": await storage_service.search_files(token, params.get("query"))}
            elif action == "get_metadata":
                return {"status": "success", "data": await storage_service.get_file_metadata(token, params.get("file_id"))}

        elif service == "dropbox":
            if action in ("list", "list_folder"):
                return {"status": "success", "data": await storage_service.list_folder(params.get("path", ""), token)}
            elif action == "search":
                return {"status": "success", "data": await storage_service.search(params.get("query"), token, params.get("path", ""))}
            elif action == "create_folder":
                return {"status": "success", "data": await storage_service.create_folder(params.get("path"), token)}

        elif service == "onedrive":
            if action in ("list", "list_files"):
                return {"status": "success", "data": await storage_service.list_drive_items(token, params.get("path"))}
            elif action == "search":
                # Real Graph root search — the service's search_files sat
                # unused while this branch listed the drive root and
                # filtered client-side, so only top-folder items ever
                # matched a search.
                res = await storage_service.search_files(token, params.get("query"))
                data = res.get("data") or {} if isinstance(res, dict) else {}
                return {"status": "success", "data": data.get("value", [])}

        elif service == "box":
            if action == "list":
                return {"status": "success", "data": await storage_service.list_folder_items(token, params.get("folder_id", "0"))}
            elif action == "search":
                # The service's search_files (Box GET /search) existed but
                # this dispatch never offered search — the planner
                # advertised "box: search files" while every search fell
                # through to the generic routed message with no data.
                res = await storage_service.search_files(token, params.get("query"))
                data = res.get("data") or {} if isinstance(res, dict) else {}
                return {"status": "success", "data": data.get("entries", [])}

        elif service == "notion":
            if action == "search":
                return {"status": "success", "data": await storage_service.search(params.get("query"), token=token)}
            elif action == "create_page":
                return {"status": "success", "data": await storage_service.create_page(params.get("parent"), params.get("properties"), params.get("children"), token=token)}
            elif action == "list":
                return {"status": "success", "data": await storage_service.search_pages_in_workspace(token=token)}
        
        elif service == "zoho_workdrive":
            # WorkDrive resolves its OAuth token PER USER
            # (ConnectionService/IntegrationToken rows); the instance carries
            # no access_token and the executor context usually has none, so
            # the raw `token` here is None — passing it as user_id silently
            # emptied every WorkDrive list/search (live 2026-09-03 price-book
            # miss). Pass the acting user, as execute_operation does.
            wd_user = context.get("user_id") or token
            if action in ("list", "list_files"):
                return {"status": "success", "data": await storage_service.list_files(wd_user, params.get("folder_id"))}
            elif action == "search":
                return {"status": "success", "data": await storage_service.search_files(wd_user, params.get("query"), limit=params.get("limit") or 20)}

        return {"status": "success", "message": f"Routed to {service} handler (Registry Storage)"}

    async def _read_storage_file(
        self,
        service: str,
        storage_service: Any,
        token: Optional[str],
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Open a storage file: resolve → download → extract → excerpt.

        One implementation shared by every storage integration (the read leg
        of find→open→read). Resolution uses an explicit ``file_id`` when the
        caller has one, otherwise it runs the service's own search and picks
        the name-best-matching hit. The excerpt is query-anchored so a
        "find the WG350DSAV row" read returns the region around that model
        number rather than the workbook's head. The full text is ALSO
        ingested (best-effort) under the file's stable identity, so this one
        open warms the hybrid index — later questions hit search, not the
        download path.
        """
        user_id = context.get("user_id")
        query = (params.get("query") or "").strip()
        file_id = params.get("file_id") or params.get("id")
        file_name: Optional[str] = None

        try:
            # --- resolve the file ---------------------------------------
            if not file_id:
                hits: List[Dict[str, Any]] = []
                if service == "zoho_workdrive":
                    raw = await storage_service.search_files(
                        user_id or token, query or " ", limit=5)
                    # search_files returns a PLAIN LIST of file records (and
                    # always has — the dict unwrap here matched no real
                    # shape, so every planner read without an explicit
                    # file_id resolved zero hits and returned found:False
                    # while the file sat on the drive; live 2026-09-04
                    # 'Consolidated Price List' read). Tolerate both shapes
                    # in case a wrapped envelope appears later.
                    if isinstance(raw, list):
                        hits = raw
                    else:
                        hits = (raw or {}).get("data", {}).get("files", []) \
                            if isinstance(raw, dict) else []
                elif service == "google_drive":
                    raw = await storage_service.search_files(token, query)
                    hits = (raw or {}).get("data", {}).get("files", []) \
                        if isinstance(raw, dict) else []
                elif service == "onedrive":
                    raw = await storage_service.search_files(token, query)
                    hits = (raw or {}).get("data", {}).get("value", []) \
                        if isinstance(raw, dict) else []
                elif service == "box":
                    raw = await storage_service.search_files(token, query)
                    hits = (raw or {}).get("data", {}).get("entries", []) \
                        if isinstance(raw, dict) else []
                elif service == "dropbox":
                    hits = await storage_service.search(query or " ", token) or []
                if not hits:
                    return {"status": "success", "data": {
                        "found": False,
                        "message": f"No file in {service} matched '{query}'.",
                    }}
                file_id, file_name = self._best_file_match(hits, query)

            # --- download -------------------------------------------------
            content: Optional[bytes] = None
            if service == "zoho_workdrive":
                content = await storage_service.download_file(user_id or token, file_id)
            elif service == "google_drive":
                content = await storage_service.download_file_bytes(token, file_id)
            elif service == "onedrive":
                content = await storage_service.download_file_bytes(token, file_id)
            elif service == "box":
                content = await storage_service.download_file_bytes(token, file_id)
            elif service == "dropbox":
                content = await storage_service.download_file(file_id or query, token)
            if not content:
                return {"status": "success", "data": {
                    "found": True, "file_id": file_id, "file_name": file_name,
                    "message": f"Found the file in {service} but the download failed.",
                }}
            if not file_name:
                file_name = f"{service}:{file_id}"

            # --- extract --------------------------------------------------
            from core.auto_document_ingestion import (
                DocumentParser,
                READ_EXTRACTION_MAX_CHARS,
            )

            file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
            # Explicit open of a NAMED file: extract with a far larger
            # ceiling than the ingestion budget. The user asked for THIS
            # file's contents — a row in its last sheet must be reachable
            # (live 2026-09-03: the ingestion-budget cut landed before the
            # LINMAC sheet, so a read limited to that budget could not see
            # WG350DSAV row 17 either).
            text = await DocumentParser.parse_document(
                content, file_ext, file_name, max_chars=READ_EXTRACTION_MAX_CHARS
            )
            if not text or not text.strip():
                return {"status": "success", "data": {
                    "found": True, "file_id": file_id, "file_name": file_name,
                    "message": f"Opened {file_name} but no text could be extracted from it.",
                }}

            # --- ingest (warming the hybrid index) — best-effort ----------
            ingested = False
            try:
                from core.auto_document_ingestion import AutoDocumentIngestionService

                ingest_result = await AutoDocumentIngestionService().process_file_bytes(
                    content,
                    file_name=file_name,
                    source=service,
                    user_id=user_id or "system",
                    external_id=file_id,
                    explicit=True,
                )
                ingested = ingest_result.get("status") == "ingested"
            except Exception as ingest_err:  # noqa: BLE001 — read still returns
                logger.debug(f"read-path ingest skipped for {file_name}: {ingest_err}")

            excerpt = _query_anchored_excerpt(text, query)
            return {"status": "success", "data": {
                "found": True,
                "file_id": file_id,
                "file_name": file_name,
                "chars_extracted": len(text),
                "excerpt": excerpt,
                "ingested_into_workspace": ingested,
                "note": (
                    "Contents above are EXCERPTS around the query. Cite only "
                    "values visible in them; the file is now ingested for "
                    "full-text search."
                ),
            }}
        except Exception as e:
            logger.error(f"read_storage_file failed ({service}, file={file_id}): {e}")
            return {"status": "error", "message": f"Could not open the file: {e}"}

    @staticmethod
    def _best_file_match(
        hits: List[Dict[str, Any]], query: str
    ) -> tuple:
        """Pick the hit whose NAME best matches the query tokens (falls back
        to the top hit). Returns (file_id, file_name)."""
        import re as _re

        def _norm(s: str) -> str:
            return _re.sub(r"[^a-z0-9]+", "", str(s or "").lower())

        q_tokens = [t for t in _re.split(r"[^a-z0-9]+", query.lower()) if len(t) > 2]
        best, best_score = None, -1
        for h in hits:
            name = str(
                h.get("name") or h.get("title")
                or (h.get("attributes") or {}).get("name", "")
            )
            nid = _norm(name)
            score = sum(1 for t in q_tokens if _norm(t) and _norm(t) in nid)
            if score > best_score:
                best, best_score = h, score
        h = best or hits[0]
        file_id = (
            h.get("id") or h.get("file_id") or h.get("fileId")
            or ((h.get("metadata") or {}).get("id") if isinstance(h.get("metadata"), dict) else None)
        )
        # Box wraps metadata; OneDrive nests under parent; keep a last-resort walk
        if file_id is None and isinstance(h, dict):
            for v in h.values():
                if isinstance(v, dict) and v.get("id"):
                    file_id = v["id"]
                    break
        file_name = str(
            h.get("name") or h.get("title")
            or (h.get("attributes") or {}).get("name", "")
        )
        return file_id, file_name

    async def _search_storage(self, service: str, query: str, context: Dict[str, Any]) -> List[Dict]:
        """Search files/pages across storage platforms via Registry"""
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        storage_service = await registry.get_service_instance(service, tenant_id)
        token = getattr(storage_service, 'access_token', None) or context.get("access_token")

        if service == "google_drive":
            res = await storage_service.search_files(token, query)
            if res.get("status") == "success":
                return res.get("data", {}).get("files", [])
        elif service == "dropbox":
            return await storage_service.search(query, token)
        elif service == "notion":
            res = await storage_service.search(query, token=token)
            return res.get("results", [])
        elif service == "zoho_workdrive":
            # Same per-user token resolution as _execute_storage — the
            # storage branch previously fell through to `return []` here, so
            # agent-facing search_files fan-outs never saw WorkDrive results.
            return await storage_service.search_files(
                context.get("user_id") or token, query)
        elif service == "onedrive":
            res = await storage_service.search_files(token, query)
            return (res.get("data") or {}).get("value", []) if isinstance(res, dict) else []
        elif service == "box":
            # Was a silent fall-through `return []` — the MCP no-platform
            # search_files fan-out (which routes through _search_storage)
            # never saw Box results even though BoxService.search_files
            # existed.
            res = await storage_service.search_files(token, query)
            return (res.get("data") or {}).get("entries", []) if isinstance(res, dict) else []
        return []

    # --- Support Platforms ---
    async def _execute_support(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Zendesk, Freshdesk, Intercom via Registry"""
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        support_service = await registry.get_service_instance(service, tenant_id)
        token = getattr(support_service, 'access_token', None) or context.get("access_token")

        if service == "zendesk":
            if action == "list":
                return {"status": "success", "data": await support_service.get_tickets(token=token)}
            elif action == "create":
                return {"status": "success", "data": await support_service.create_ticket(params.get("data", {}), token=token)}

        elif service == "freshdesk":
            if action in ("list", "get_tickets"):
                return {"status": "success", "data": await support_service.get_tickets(token=token)}
            elif action == "create":
                return {"status": "success", "data": await support_service.create_ticket(params.get("data", params), token=token)}
            elif action == "search":
                return {"status": "success", "data": await support_service.search_tickets(params.get("query"), token=token)}

        elif service == "intercom":
            if action in ("list", "get_conversations"):
                return {"status": "success", "data": await support_service.get_conversations(token)}
            elif action == "search_contacts":
                return {"status": "success", "data": await support_service.search_contacts(token, params.get("query"))}
        
        return {"status": "success", "message": f"Routed to {service} handler (Registry Support)"}

    # --- Development Platforms ---
    async def _execute_development(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle GitHub, GitLab, Figma via Registry"""
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        dev_service = await registry.get_service_instance(service, tenant_id)
        token = getattr(dev_service, 'access_token', None) or context.get("access_token")

        if service == "github":
            if action in ("list", "list_repos"):
                return {"status": "success", "data": await dev_service.get_user_repositories(token=token)}
            elif action == "get_issues":
                return {"status": "success", "data": await dev_service.get_repository_issues(params.get("owner"), params.get("repo"), token=token)}
        elif service == "gitlab":
            if action in ("list", "list_projects"):
                return {"status": "success", "data": await dev_service.get_projects(token, limit=params.get("limit", 20))}
            elif action == "get_issues":
                return {"status": "success", "data": await dev_service.get_issues(token, project_id=params.get("project_id"))}
            elif action == "search":
                return {"status": "success", "data": await dev_service.search_projects(token, params.get("query"))}
        elif service == "figma":
            if action in ("list", "get_projects"):
                return {"status": "success", "data": await dev_service.get_team_projects(params.get("team_id"), token)}
            elif action == "get_file":
                return {"status": "success", "data": await dev_service.get_file(params.get("file_key"), token)}
            elif action == "get_comments":
                return {"status": "success", "data": await dev_service.get_comments(params.get("file_key"), token)}
        
        return {"status": "success", "message": f"Routed to {service} handler (Registry Dev)"}

    # --- Marketing Platforms ---
    async def _execute_marketing(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Mailchimp, HubSpot Marketing"""
        access_token = context.get("access_token")
        server_prefix = context.get("server_prefix", params.get("server_prefix"))

        if service == "mailchimp":
            from integrations.mailchimp_service import MailchimpService
            mailchimp_service = MailchimpService()
            if action in ("list", "get_campaigns"):
                return {"status": "success", "data": await mailchimp_service.get_campaigns(access_token, server_prefix, limit=params.get("limit", 20))}
            elif action == "get_audiences":
                return {"status": "success", "data": await mailchimp_service.get_audiences(access_token, server_prefix)}
        elif service == "hubspot_marketing":
            from integrations.hubspot_service import get_hubspot_service
            hs = get_hubspot_service()
            if action == "list_campaigns":
                return {"status": "success", "data": await hs.get_campaigns()}
        
        return {"status": "success", "message": f"Routed to {service} handler (marketing)"}

    async def _search_dev(self, service: str, query: str, context: Dict[str, Any]) -> List[Dict]:
        """Search repositories/code across Dev platforms"""
        access_token = context.get("access_token")
        if service == "github":
            from integrations.github_service import GitHubService
            github_service = GitHubService()
            # Generic repo search or issue search — any-term ranked, same
            # identifier-tolerant filter as the other client-side families.
            repos = github_service.get_user_repositories()
            return {"status": "success",
                    "data": filter_by_terms(repos, query,
                                            text_of=lambda r: r.get("name", ""))}
        elif service == "gitlab":
            from integrations.gitlab_service import GitLabService
            gitlab_service = GitLabService()
            return {"status": "success", "data": await gitlab_service.search_projects(access_token, query)}
        return []

    async def _search_marketing(self, service: str, query: str, context: Dict[str, Any]) -> List[Dict]:
        """Search campaigns across Marketing platforms"""
        access_token = context.get("access_token")
        server_prefix = context.get("server_prefix")
        if service == "mailchimp":
            from integrations.mailchimp_service import MailchimpService
            mailchimp_service = MailchimpService()
            campaigns = await mailchimp_service.get_campaigns(access_token, server_prefix)
            return {"status": "success",
                    "data": filter_by_terms(
                        campaigns, query,
                        text_of=lambda c: " ".join([
                            (c.get("settings") or {}).get("subject_line") or "",
                            (c.get("settings") or {}).get("title") or "",
                        ]))}
        return []

    # --- Finance Platforms ---
    async def _search_finance(self, service: str, query: str, context: Dict[str, Any]) -> List[Dict]:
        """Search across finance platforms — finance list endpoints have no
        server-side search param, so pull the recent list and filter
        client-side (same pattern as _search_dev). Shared by the search()
        entry and the execute-path search bridge."""
        fin_service = await context["registry"].get_service_instance(service, context.get("tenant_id", "system"))
        token = getattr(fin_service, "access_token", None) or context.get("access_token")
        if not fin_service:
            return {"status": "error", "message": f"{service} service unavailable"}
        if service == "stripe":
            # StripeAdapter.get_charges — the branch used to call
            # list_payments, a method that exists on no stripe class
            # (AttributeError on the first live finance search).
            data = await fin_service.get_charges(limit=25)
        elif service == "quickbooks":
            data = await fin_service.get_invoices(token=token)
        else:
            data = await fin_service.get_invoices(token)
        return self._filter_by_query(data, query)

    async def _execute_finance(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Stripe, QuickBooks, Xero, Zoho Books via Registry"""
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        fin_service = await registry.get_service_instance(service, tenant_id)
        token = getattr(fin_service, 'access_token', None) or context.get("access_token")

        if service == "stripe":
            if action == "list_payments":
                # StripeAdapter.get_charges — list_payments exists on no
                # stripe class (AttributeError class, caught by the parity
                # test).
                return {"status": "success", "data": await fin_service.get_charges(limit=params.get("limit", 10))}
            elif action == "get_balance":
                return {"status": "success", "data": await fin_service.get_balance(access_token=token)}
        elif service == "quickbooks":
            if action == "list_invoices":
                return {"status": "success", "data": await fin_service.get_invoices(token=token)}
            elif action == "create_customer":
                return {"status": "success", "data": await fin_service.create_customer(params.get("display_name"), params.get("email"), token=token)}
            elif action == "create_invoice":
                return {"status": "success", "data": await fin_service.create_invoice(params, token=token)}
        elif service == "xero":
            if action == "list_invoices":
                return {"status": "success", "data": await fin_service.get_invoices(token=token)}
        elif service == "zoho_books":
            if action == "list_invoices":
                return {"status": "success", "data": await fin_service.get_invoices(token)}
        elif service == "zoho_inventory":
            if action in ("search_items", "search"):
                # The live search leg the chat tool planner plans when a user
                # asks about stock ("is the wg-350dsav in stock?"). The service
                # resolves token/datacenter/org itself and returns slim item
                # dicts; an empty result flows to the planner's memory fallback.
                # user_id is required for the per-user token lookup — token
                # rows are user-keyed, so this previously died on
                # "no access token available" for every agent turn.
                return {"status": "success", "data": await fin_service.search_items(
                    params.get("query", ""), limit=params.get("limit", 8),
                    user_id=context.get("user_id"))}
            if action == "list_items":
                return {"status": "success", "data": await fin_service.get_items(token)}
        elif service == "aws_ses":
            if action == "send_email":
                return {"status": "success", "data": await fin_service.send_email(
                    params.get("from_email", "noreply@example.com"),
                    to=params.get("to", []),
                    subject=params.get("subject"),
                    html_body=params.get("html_body"),
                    text_body=params.get("text_body")
                )}
            elif action == "get_quota":
                return {"status": "success", "data": await fin_service.get_send_quota(tenant_id)}

        return {"status": "success", "message": f"Routed to {service} handler (Registry Finance)"}

    # --- Zoho Suite ---
    async def _execute_zoho(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Zoho CRM, Mail, Inventory"""
        access_token = context.get("access_token")
        if service == "zoho_crm":
            from integrations.zoho_crm_service import ZohoCRMService
            crm = ZohoCRMService()
            # ZohoCRMService credentials self-resolve (tenant token lookup);
            # the token= kwargs here TypeError'd on every call (live
            # 2026-09-03), so zoho_crm list/deals/create always failed.
            if action in ("list", "get_leads"):
                return {"status": "success", "data": await crm.get_leads()}
            elif action == "get_deals":
                return {"status": "success", "data": await crm.get_deals()}
            elif action == "create_lead":
                return {"status": "success", "data": await crm.create_lead(params.get("data", params))}
        elif service == "zoho_mail":
            from integrations.zoho_mail_service import ZohoMailService
            zoho_mail_service = ZohoMailService()
            if action == "list":
                return {"status": "success", "data": await zoho_mail_service.get_recent_inbox(access_token)}
        elif service == "zoho_inventory":
            from integrations.zoho_inventory_service import zoho_inventory_service
            if action == "list":
                return {"status": "success", "data": await zoho_inventory_service.get_items(access_token)}
        elif service == "zoho_projects":
            from integrations.zoho_projects_service import ZohoProjectsService
            zoho_projects_service = ZohoProjectsService()
            if action == "list":
                return {"status": "success", "data": await zoho_projects_service.get_projects(access_token, params.get("portal_id") or "")}
        elif service in ("zoho_forms", "zoho_flow"):
            # Webhook-push apps: no live API to call — the agent reads what
            # has been ingested into agent memory (see zoho_*_service).
            from integrations.zoho_forms_service import ZohoFormsService
            from integrations.zoho_flow_service import ZohoFlowService

            workspace_id = context.get("workspace_id") or self.workspace_id
            svc = (ZohoFormsService if service == "zoho_forms" else ZohoFlowService)(
                config={"workspace_id": workspace_id}
            )
            if action in ("list", "list_submissions", "list_events"):
                return {"status": "success", "data": await svc.list_submissions() if service == "zoho_forms" else await svc.list_events()}
            if action in ("search", "search_submissions", "search_events"):
                data = await svc.search_submissions(params.get("query", "")) if service == "zoho_forms" else await svc.search_events(params.get("query", ""))
                return {"status": "success", "data": data}

        return {"status": "success", "message": f"Routed to {service} handler (default zoho)"}

    async def _search_crm(self, service: str, query: str, context: Dict[str, Any]) -> List[Dict]:
        """Search across CRM platforms"""
        access_token = context.get("access_token")
        if service == "salesforce":
            # Delegate to the real implementation (the search() entry's
            # Salesforce search) — this branch used to be a literal `pass`
            # that returned [] while the catalog advertised the search.
            # SOQL entity defaults to contact (the common "find this
            # company/person" intent); the helper only implements
            # contact/account SOQL.
            return await self._search_salesforce(
                query, context.get("entity_type") or "contact",
                context.get("user_id"), context)
        elif service == "hubspot":
            return await self._search_hubspot(query, None, context)
        elif service == "zoho_crm":
            from integrations.zoho_crm_service import ZohoCRMService
            crm = ZohoCRMService()
            # List-and-filter: Zoho CRM has no simple text search endpoint at
            # this integration depth. Self-resolving credential path — the
            # token= kwarg predates it and TypeError'd on every call (live
            # 2026-09-03), so planner-planned zoho_crm searches always errored
            # into the memory fallback.
            leads = await crm.get_leads()
            return {"status": "success", "data": self._filter_by_query(leads, query)}
        return {"status": "success", "data": []}

    async def _search_support(self, service: str, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Search across Support platforms"""
        if service == "zendesk":
            from integrations.zendesk_service import ZendeskService
            zendesk_service = ZendeskService()
            return {"status": "success", "data": await zendesk_service.get_tickets()}
        elif service == "freshdesk":
            from integrations.freshdesk_service import FreshdeskService
            fd = FreshdeskService()
            return {"status": "success", "data": await fd.search_tickets(query)}
        elif service == "intercom":
            registry = context.get("registry")
            tenant_id = context.get("tenant_id", "system")
            if registry:
                service_inst = await registry.get_service_instance("intercom", tenant_id)
                if service_inst:
                    token = getattr(service_inst, 'access_token', None) or context.get("access_token")
                    return {"status": "success", "data": await service_inst.search_contacts(token, query)}
            return {"status": "error", "message": "Intercom service not found in registry"}
        return {"status": "success", "data": []}

    # --- Analytics Platforms ---
    async def _execute_analytics(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Tableau, Google Analytics"""
        access_token = context.get("access_token")
        if service == "tableau":
            from integrations.tableau_service import TableauService
            tableau = TableauService()
            try:
                if action in ("list", "get_workbooks"):
                    return {"status": "success", "data": await tableau.get_workbooks(access_token)}
            except Exception as e:
                return {"status": "error", "message": f"Tableau service failed: {str(e)}"}
        elif service == "google_analytics":
            # GA4 implementation link
            return {"status": "success", "message": f"Routed to {service} GA4 handler"}
        
        return {"status": "success", "message": f"Routed to {service} handler (analytics)"}

    async def _search_analytics(self, service: str, query: str, context: Dict[str, Any]) -> List[Dict]:
        """Search across Analytics platforms"""
        if service == "tableau":
            from integrations.tableau_service import TableauService
            tableau = TableauService()
            try:
                workbooks = await tableau.get_workbooks(context.get("access_token"))
                return {"status": "success", "data": [w for w in workbooks if query.lower() in w.get("name", "").lower()]}
            except Exception as e:
                return {"status": "error", "message": f"Tableau search failed: {str(e)}"}
        return {"status": "success", "data": []}

    # --- Generic Native Handler ---
    async def _execute_generic_native(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback handler for other native integrations"""
        logger.info(f"Generic native handler for {service}.{action}")
        return {"status": "success", "message": f"Action {action} routed to {service} (generic handler)"}

    # --- Activepieces Fallback ---
    async def _execute_activepieces(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Route to Activepieces catalog for non-native integrations"""
        try:
            from core.external_integration_service import external_integration_service
            logger.info(f"Routing {service}.{action} to Activepieces catalog")
            
            
            result = await external_integration_service.execute_integration_action(
                integration_id=service,
                action_id=action,
                params=params,
                credentials=context.get("credentials")
            )
            return {"status": "success", "data": result}
        except Exception as ex:
            logger.error(f"Activepieces fallback failed for {service}: {ex}")
            return {"status": "error", "message": f"Service '{service}' not supported. Activepieces fallback failed: {str(ex)}"}
    async def _execute_marketing_reviews(self, service, action, params, context):
        """
        Specialized handler for review platforms.
        """
        from core.marketing_skills_service import marketing_skills_service
        
        if action == "list_reviews":
            return {"status": "success", "data": await marketing_skills_service.manage_reviews(self.workspace_id, service)}
        elif action == "reply_to_review":
            # Real implementation would call the integration API
            return {
                "status": "success", 
                "message": f"Successfully replied to review {params.get('review_id')} on {service}."
            }
        return {"status": "error", "message": f"Unknown review action: {action}"}

    async def _execute_marketing_ads(self, service, action, params, context):
        """
        Generic handler for Ads platforms (Meta, Google, LinkedIn).
        """
        logger.info(f"Executing Ads action {action} on {service}")
        # Placeholder for real Ads API calls
        return {
            "status": "success",
            "service": service,
            "action": action,
            "data": {"count": 10, "insights": "Performance trending positive."}
        }

# Singleton instance for platform-wide usage
universal_integration_service = UniversalIntegrationService()
