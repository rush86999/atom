"""
Sales agent tools — the tool layer of the AI sales agent.

Each handler follows the action-registry contract:
``async def handler(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]``
returning ``{"success": bool, ...}`` and never raising. Governance (maturity
gating, sandbox, audit) is layered on top by the action-registry dispatch.

First-version scope (honest): case CRUD + ask-human are real; inventory and
quote tools search the ingested knowledge (documents/emails/price lists via
hybrid search) rather than claiming a live Zoho Inventory connection — the
results say so, so the agent doesn't over-trust them.
"""

import logging
from typing import Any, Dict, Optional

from core.sales_case import (
    ask_human as _ask_human,
    case_to_dict,
    create_case as _create_case,
    get_case as _get_case,
    list_cases as _list_cases,
    transition as _transition,
)

logger = logging.getLogger(__name__)


def _context_user_id(context: Dict[str, Any]) -> Optional[str]:
    """Best-effort actor id from the dispatch context (never from args)."""
    if not context:
        return None
    for key in ("user_id", "userId", "actor_id"):
        val = context.get(key)
        if val:
            return str(val)
    user = context.get("user")
    if user is not None:
        uid = getattr(user, "id", None)
        if uid:
            return str(uid)
    return None


def _actor(context: Dict[str, Any]) -> str:
    return _context_user_id(context) or "agent"


# --------------------------------------------------------------------------- #
# Case lifecycle
# --------------------------------------------------------------------------- #

async def sales_case_create(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new sales case from an inbound customer email/query."""
    customer_email = (args.get("customer_email") or "").strip()
    if not customer_email:
        return {"success": False, "error": "customer_email is required"}
    try:
        case = _create_case(
            workspace_id=str(context.get("workspace_id") or "default"),
            user_id=_context_user_id(context),
            tenant_id=str(context.get("tenant_id") or "default"),
            customer_name=str(args.get("customer_name") or ""),
            customer_email=customer_email,
            subject=str(args.get("subject") or ""),
            email_id=args.get("email_id"),
            conversation_id=args.get("conversation_id"),
            intent=str(args.get("intent") or ""),
            products=args.get("products") or [],
            requirements=args.get("requirements") or [],
        )
        return {"success": True, "case": case}
    except Exception as e:
        logger.warning(f"sales_case_create failed: {e}")
        return {"success": False, "error": "case_creation_failed"}


async def sales_case_get(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Load a sales case by id."""
    case_id = args.get("case_id")
    if not case_id:
        return {"success": False, "error": "case_id is required"}
    try:
        case = _get_case(str(case_id))
        if case is None:
            return {"success": False, "error": "case_not_found"}
        return {"success": True, "case": case}
    except Exception as e:
        logger.warning(f"sales_case_get failed: {e}")
        return {"success": False, "error": "case_load_failed"}


async def sales_case_list(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """List sales cases, optionally filtered by status (e.g. all open waits)."""
    try:
        status = (args.get("status") or "").strip() or None
        limit = int(args.get("limit") or 50)
        cases = _list_cases(status=status, limit=max(1, min(limit, 200)))
        return {"success": True, "cases": cases, "count": len(cases)}
    except Exception as e:
        logger.warning(f"sales_case_list failed: {e}")
        return {"success": False, "error": "case_list_failed"}


async def sales_case_transition(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Advance a case to a valid next status (validated state machine)."""
    case_id = args.get("case_id")
    next_status = (args.get("status") or "").strip()
    if not case_id or not next_status:
        return {"success": False, "error": "case_id and status are required"}
    try:
        result = _transition(str(case_id), next_status,
                             reason=str(args.get("reason") or ""),
                             actor=_actor(context))
        return result
    except Exception as e:
        logger.warning(f"sales_case_transition failed: {e}")
        return {"success": False, "error": "transition_failed"}


async def sales_case_ask_human(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Pause the case and ask a human a question (creates a HITL approval)."""
    case_id = args.get("case_id")
    question = (args.get("question") or "").strip()
    if not case_id or not question:
        return {"success": False, "error": "case_id and question are required"}
    try:
        result = _ask_human(str(case_id), question,
                            agent_id=str(context.get("agent_id") or "sales_agent"),
                            priority=str(args.get("priority") or "MEDIUM"))
        return result
    except Exception as e:
        logger.warning(f"sales_case_ask_human failed: {e}")
        return {"success": False, "error": "ask_human_failed"}


# --------------------------------------------------------------------------- #
# Domain tools (first version: search the ingested knowledge, be honest)
# --------------------------------------------------------------------------- #

async def _hybrid_search(query: str, limit: int = 3) -> list:
    """Search ingested documents (price lists, shipping docs, emails, ...)."""
    try:
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

        result = await DocumentsHybridSearch().search(query=query[:500], limit=limit)
        hits = []
        for hit in (result or {}).get("results", []) or []:
            hits.append({
                "source": str(hit.get("source") or "doc"),
                "title": str(hit.get("title") or ""),
                "preview": str(hit.get("preview") or "")[:300],
            })
        return hits
    except Exception as e:
        logger.debug(f"sales inventory/quote search failed: {e}")
        return []


async def sales_inventory_check(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Check availability of a product across ingested sources.

    First version searches the ingested knowledge (emails, shipping docs,
    Zoho sync records) — it does NOT yet query the live Zoho Inventory API,
    so the result is marked 'not authoritative'. The agent should treat a
    finding as a lead to verify, not a fact.
    """
    product = (args.get("product") or "").strip()
    if not product:
        return {"success": False, "error": "product is required"}
    try:
        hits = await _hybrid_search(f"{product} availability stock shipped", limit=4)
        # Any explicit availability language? Best-effort heuristic, honest about it.
        keywords = ("in stock", "available", "shipped", "in transit", "on order")
        hints = [
            h for h in hits
            if any(k in h["preview"].lower() for k in keywords)
        ]
        return {
            "success": True,
            "product": product,
            "sources_checked": ["ingested_documents", "emails", "zoho_sync_records"],
            "findings": hits,
            "availability_hints": hints,
            "in_stock": "unknown",  # do not guess — verification is the oracle's job
            "note": "First-version check over ingested knowledge only; not "
                    "authoritative. Verify against live Zoho Inventory before quoting.",
        }
    except Exception as e:
        logger.warning(f"sales_inventory_check failed: {e}")
        return {"success": False, "error": "inventory_check_failed"}


async def sales_quote_calculate(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Build a preliminary quote for a case from its products + price-list docs.

    Returns a DRAFT quote; prices found in ingested price-list documents are
    marked with their source. Missing prices are left null — the agent must
    not invent them (ask vendor / ask human instead).
    """
    case_id = args.get("case_id")
    if not case_id:
        return {"success": False, "error": "case_id is required"}
    try:
        case = _get_case(str(case_id))
        if case is None:
            return {"success": False, "error": "case_not_found"}

        line_items = []
        for product in case.get("products") or []:
            name = str(product.get("name") or "")
            qty = int(product.get("qty") or 1)
            item = {"product": name, "qty": qty, "unit_price": None,
                    "line_total": None, "price_source": None}
            if name:
                hits = await _hybrid_search(f"{name} price", limit=2)
                for h in hits:
                    # Do NOT extract numbers — present the source so the
                    # agent/human can verify before committing.
                    item["price_source"] = {
                        "source": h["source"],
                        "preview": h["preview"],
                    }
                    break
            line_items.append(item)

        quote = {
            "case_id": case_id,
            "customer": case.get("customer_name") or case.get("customer_email") or "",
            "status": "draft",
            "currency": "USD",
            "line_items": line_items,
            "subtotal": None,
            "note": "Draft quote — prices must be verified against the price "
                    "list before approval; missing prices need vendor/human input.",
        }
        return {"success": True, "quote": quote}
    except Exception as e:
        logger.warning(f"sales_quote_calculate failed: {e}")
        return {"success": False, "error": "quote_calculation_failed"}
