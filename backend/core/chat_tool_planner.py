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
# Deferred annotations: functions above reference ToolPlan in their
# signatures before the class is defined; Python 3.14 (server) evaluates
# annotations lazily (PEP 649) but 3.11 tooling evaluates eagerly and the
# import died with NameError.
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

# Connects provider names as stored in integration_tokens to the service
# names UniversalIntegrationService dispatches on.
_PROVIDER_ALIASES = {
    "microsoft": "outlook",
    "office365": "outlook",
    "azure": "outlook",
    "google": "gmail",
    "gdrive": "google_drive",
    # The canonical suite-wide OAuth grant fans out to zoho_* provider rows,
    # but the "zoho" row itself is a service name nobody implements — as a
    # connected entry it invited the planner to plan a dead service. Its
    # searchable face is the CRM.
    "zoho": "zoho_crm",
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
    # Inventory has no generic "search" handler in _execute_finance — without
    # this row a planned zoho_inventory.search matched no branch and every
    # "is it in stock" answer was really the ingested-file memory search
    # (live 2026-09-03: WG-350DSAV in stock, agent said "no live stock
    # records").
    "zoho_inventory": {"search": "search_items", "list": "list_items"},
}

# File-storage services expose a `read` intent (download + extract + return a
# query-anchored excerpt). The 3-step file journey — find the file, OPEN it,
# find the row — previously dead-ended after step 1: search returned only
# metadata, no executor action existed for opening, so the model narrated the
# row it could not see (live 2026-09-03 price-book miss). Hybrid search over
# the ingested workspace stays the FAST path for "what's the price?"-style
# questions; `read` is for when the user explicitly wants the file opened.
_STORAGE_SERVICES = (
    "zoho_workdrive", "google_drive", "onedrive", "dropbox", "box",
)
# Mailbox/chat services routed through the universal path (outlook has its
# own dedicated leg). Every one of them shares Graph's failure class: the
# live search ranks by opaque provider relevance, misses sender ADDRESSES,
# and fills its slots with unrelated recent traffic — while the ingested
# comms store holds deterministic sender/recipient copies of everything the
# workspace has seen. Their blocks therefore get the same ranked ingested-
# copy supplement (live 2026-09-06: the jschulz thread sat in the store
# while outlook's live search returned other customers' lead forms; the
# identical shape is one token grant away for gmail/slack/telegram).
_COMMUNICATION_SERVICES = (
    "gmail", "slack", "teams", "discord", "google_chat", "telegram",
    "whatsapp", "zoho_mail",
)
# Mailbox providers that support the on-demand `ingest` intent (pull a
# message's body + attachments from the integration INTO memory).
_MAILBOX_SERVICES = ("outlook", "gmail")


def _haystack_has_address(query: str, context: Optional[Dict[str, Any]]) -> bool:
    """True when an email-address fragment appears in the query or recent
    history — the trigger for the ingested-mailbox supplement on ANY
    service (a CRM lead lookup by address benefits from the thread copies
    just as much as a mailbox search does)."""
    import re as _re

    hay = query + " " + " ".join(
        _entry_text(m) for m in ((context or {}).get("history") or [])[-6:]
    )
    return bool(_re.search(r"[\w.+-]+@[\w.-]+\.\w+", hay))

# Live search services whose queries identifiers must never be lost from.
# Two tolerance grades, both safe for the net (the net only fires when the
# draft query carries NO identifier token, and only APPENDS ≤2 codes from
# the conversation):
#   - zoho_inventory: server APIs match whole NAME tokens (Zoho search_text
#     ANDs its tokens; "Linmac WG-350DSAV" → 0 hits though the item is in
#     stock) — ZohoInventoryService.search_items breaks the enriched query
#     into per-token attempts (live 2026-09-04, three consecutive turns
#     planned only "bandsaw" while the conversation carried WG-350DSAV).
#   - the client-side-filtered families (finance, zoho_crm, linear, asana,
#     github, mailchimp, google_calendar): UniversalIntegrationService
#     filters them with the ranked any-term filter
#     (core.identifier_search.filter_by_terms), so extra terms widen
#     rather than zero out the match set.
# Deliberately EXCLUDED: services whose search is a provider-side API with
# unverified multi-term semantics (monday, jira, trello, freshdesk,
# intercom, gitlab, salesforce, hubspot, notion) — an appended token can
# zero those out server-side; add them only with a tolerance check first.
_ITEM_SEARCH_SERVICES = (
    "zoho_inventory",
    # finance — invoices/payments/items carry catalog codes
    "zoho_books", "quickbooks", "xero", "stripe",
    # crm — deals/leads reference the products
    "zoho_crm",
    # pm / dev / marketing / calendar — client-side ranked filters
    "linear", "asana", "github", "mailchimp", "google_calendar",
)
for _storage_svc in _STORAGE_SERVICES:
    _INTENT_ACTIONS[_storage_svc] = {
        "search": "search",
        "list": "list",
        "read": "read_file",
    }

# Short human descriptions the planner reads (kept compact — this prompt
# rides on every chat turn).
_SERVICE_DESCRIPTIONS = {
    "outlook": "email mailbox — search messages by name, subject, company, keyword (top hits return with FULL bodies); `read` intent pulls FULL message bodies incl. quoted/forwarded threads when previews are cut off; `ingest` intent pulls a named message's body AND attachments into memory when they are not there yet (PDF/DOCX text; images OCR'd, textless photos described)",
    "gmail": "email mailbox — search messages; `ingest` intent pulls a message's body + attachments into memory on demand",
    "slack": "team chat — search messages and channels",
    "teams": "team chat — search messages",
    "discord": "community chat — search messages",
    "telegram": "messenger — search messages",
    "zoho_crm": "CRM — search leads, contacts, deals, accounts",
    "zoho_inventory": "stock inventory — search items by exact model code ('WG-350DSAV', one code as the whole query — Zoho matches whole words only) and check what is in stock",
    "salesforce": "CRM — search leads, contacts, opportunities",
    "hubspot": "CRM — search contacts, companies, deals",
    "google_drive": "file storage — search documents and files; `read` intent opens a file and returns its contents (row-level)",
    "dropbox": "file storage — search files; `read` intent opens a file and returns its contents (row-level)",
    "onedrive": "file storage — search files; `read` intent opens a file and returns its contents (row-level)",
    "box": "file storage — search files; `read` intent opens a file and returns its contents (row-level)",
    "notion": "workspace docs — search pages",
    "zoho_workdrive": "file storage — search files; `read` intent opens a file and returns its contents (row-level)",
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
    # Platform web tools: not OAuth integrations — available to every user
    # when a Tavily key is configured (env or tenant BYOK). Without these
    # the planner told agents "no web access exists" for website questions
    # and the reply model confabulated research findings instead.
    "web_search": "web search — search the public internet for facts about a company, person, product, or topic",
    "web_fetch": "browser — fetch and read a specific website page; put the site address (e.g. https://example.com) in the query",
    # Ingested-workspace memory: hybrid search over EVERYTHING ingestion
    # stored (emails, chats, documents, CRM records) — vector + lexical.
    # The first tool that queries the business's own ingested data directly;
    # available to every agent, no OAuth.
    "memory": "ingested workspace memory — search ALL emails, chats, documents and records the business has received or stored (emails by person/company/address, quotes, threads, file contents)",
    # SQL-queryable dataset catalog: every ingested spreadsheet materialized
    # into per-sheet tables (core/sheet_dataset_service). Answers WHERE a
    # value lives and returns the exact rows — the user should never have to
    # name the file.
    "datasets": "dataset catalog — for a specific value, code, model or part number: searches EVERY ingested spreadsheet and returns the exact rows plus the file and sheet they live in",
}

# Web tools that ship with the platform (key-gated, no user OAuth needed).
_PLATFORM_SERVICES = ("web_search", "web_fetch")


# Anti-fabrication contract appended to every LIVE TOOL RESULTS block. Live
# 2026-09-03: asked for a machine's price "from the consolidated price list",
# the reply model quoted $14,500.00 and even rendered an "exact row" from the
# workbook — a row that existed nowhere. The evidence excerpts never carried
# the figure, but nothing told the model to say so instead of filling the
# gap from plausibility (and when the user quoted the true value, $14,145.00,
# the model immediately "found the exact row" for that too). Same pattern the
# production harnesses solve with grounded/cited generation: specific values
# may come ONLY from attached evidence; absence must be reported, not paved.
_GROUNDING_RULE = (
    "GROUNDING RULE: specific facts (names, figures, prices, dates, "
    "quotations) must come from the evidence above. If the exact value the "
    "user asks about is not visible in this evidence, say what was found "
    "and that the source itself must be opened for the exact value — do "
    "not fill the gap from memory and do not present recalled values as "
    "if read from the source."
)


def _with_grounding(block: Optional[str]) -> Optional[str]:
    """Attach the grounding contract to a tool-results block."""
    if not block:
        return block
    return f"{block}\n\n{_GROUNDING_RULE}"
# Available unconditionally — memory searches the workspace's OWN ingested
# data (no external key, no OAuth). Coupling it to the Tavily key gate made
# it vanish wherever web search wasn't configured.
# `datasets` is also gated only by runtime state (feature enabled + catalog
# non-empty), checked in _available_platform_services below.
_ALWAYS_AVAILABLE_SERVICES = ("memory",)


def _datasets_service_available() -> bool:
    """Cheap 60s-cached gate: datasets show up in the planner catalog only
    when the feature is on AND at least one dataset exists."""
    global _datasets_avail_cache  # noqa: PLW0603
    import time

    now = time.monotonic()
    cached = _datasets_avail_cache
    if cached and now - cached[0] < 60:
        return cached[1]
    available = False
    try:
        from core.sheet_dataset_service import (
            catalog_has_entries_sync,
            sheet_datasets_enabled,
        )

        available = bool(sheet_datasets_enabled() and catalog_has_entries_sync())
    except Exception:  # noqa: BLE001 — planner must never fail on this
        available = False
    _datasets_avail_cache = (now, available)
    return available


_datasets_avail_cache: Optional[tuple] = None


def _available_platform_services() -> List[str]:
    """Platform web tools usable right now. Tavily key check is env-only
    here (cheap, every chat turn); tenant BYOK keys are resolved at
    execution time inside mcp_service."""
    # memory is always available — it searches the workspace's OWN ingested
    # data (no external key). Only key-gated web tools depend on Tavily.
    services = [
        s for s in _PLATFORM_SERVICES
        if s not in _ALWAYS_AVAILABLE_SERVICES and os.getenv("TAVILY_API_KEY")
    ]
    services.extend(_ALWAYS_AVAILABLE_SERVICES)
    if "datasets" not in services and _datasets_service_available():
        services.append("datasets")
    return services

_PLANNER_SYSTEM = """You are the tool planner for an AI automation platform.
Given the recent conversation and the user's latest message, decide whether
answering needs FRESH data from one of the available tools
(listed below with what they contain), or whether the conversation itself is
enough.

Rules:
- Retry phrases ("try again", "any luck?", "still nothing", "didn't work")
  mean RE-RUN the most recent data request in the conversation — EVEN IF
  that earlier attempt failed or the assistant earlier said it couldn't.
  A failed attempt plus "try again" is precisely a request to attempt it
  again now. Plan use_tool=true with the same service and query terms.
- query must be the minimal search terms (names, companies, subjects,
  keywords) — not the whole user message. For web_fetch the query is the
  website address itself.
- NAMED ENTITIES OVER GENERIC NOUNS: resolve "the lead", "the company",
  "them", "this contact" from the conversation and put the ACTUAL names in
  the query. A query like "determine if lead is end user or dealer" searches
  for the metal lead; the useful query names the subject — e.g. "Blumetric
  Jacob Schulz company". If the transcript names a company or person, the
  query MUST contain that name.
- Return exactly ONE plan. If a search and a URL check would both help,
  plan ONLY web_fetch when the address is known, otherwise web_search.
- READ vs FIND: web_fetch is only for READING a page whose full address is
  already known or stated in the conversation. When the user asks you to
  FIND the page/URL/link ON a site ("find the product page on brennan.ca
  for this model"), the target address is the UNKNOWN being asked for —
  plan web_search with the site name AND the subject terms (e.g.
  "brennan.ca WG-350DSAV"). Search results carry the real URLs; fetching
  the site's homepage cannot enumerate a site, and inventing a URL from a
  pattern (adding "/products/…" to the model number) is fabrication.
- Read-only EXCEPT the mailbox `ingest` intent: search/list intents for
  lookups; `read` intent ONLY for the
  file-storage services, when the user wants a specific row, value, price,
  figure or section OUT OF a named document ("open the catalog and find the
  ABC-1234 row" → read; "what files do I have about X" → search — search
  returns only file names/metadata and can never answer what a file SAYS),
  and for the outlook mailbox, when a search's snippets cut off a quoted or
  forwarded thread ("open that email, get the full thread below the
  signature" → outlook read — its search already carries full bodies for
  the top hits; read extends that to the rest and to longer bodies).
  A message that only says WHERE the file lives ("it's an excel file in
  WorkDrive") after a content request is still a READ — the earlier turns
  own the what-for ("check X for the price"), this message adds the where;
  planning search again just re-lists the file name the user already named.
- NEVER plan sends, deletes, or edits. The ONE exception is the mailbox
  `ingest` intent (outlook/gmail): it copies a named message's body AND
  attachments (images via OCR) from the connected mailbox INTO the
  workspace's own memory, so content the poller never indexed becomes
  recallable. Plan it when the user needs content that lives in an email —
  an attachment, a product image, a quoted/forwarded thread — and the
  conversation shows it is NOT already available; it is idempotent, so a
  repeat ask is a no-op. Never report email content as inaccessible without
  planning `ingest` first. Query = the sender/subject/keywords that name the
  message (or the provider message id itself).
- ALSO classify the turn for routing: suggested_intent is ONE of
  search_request | message_send | task_management | workflow_creation |
  scheduling | data_analysis | automation_trigger | integration_setup |
  status_check | help_request | multi_step_process | business_health | crm
  | agent_request — what the user wants DONE with the answer. Classify by
  the turn's GOAL verb: search/find/read/summarize/check is search_request
  EVEN WHEN the data lives in email ("search my email for X and summarize"
  = search_request — reading mail, not sending it); message_send is ONLY
  when the goal is to SEND/forward/reply/draft to a recipient. Give honest
  routing_confidence 0.0–1.0 (a bare number, e.g. 0.9); below 0.6 the
  consumer falls back to a deeper classifier, so don't pad it.
- VALUE LOOKUPS WITHOUT A NAMED SOURCE ("what's the price of WG-350DSAV?",
  "find invoice 123", "look up policy 7.2"): plan service "datasets",
  intent "search", query = the exact code/value ALONE. The dataset catalog
  searches every ingested spreadsheet and returns the file, sheet and
  exact rows — the user should never have to say where a value lives.
  Stock/quantity questions still go to the inventory app; when the user
  DOES name a document, keep using the file-storage read.
- The query MUST carry every identifying code — model, SKU, part, order or
  invoice number — EXACTLY as written anywhere in the conversation or open
  canvas, even when the user's latest message doesn't repeat it ("check the
  catalog file again and find the row" still means the code mentioned three
  turns ago).
- If the conversation or memory already clearly answers it, use_tool=false.
- Questions about a company/person/website the conversation cannot answer
  from its own content need web_search (topic facts) or web_fetch (read a
  specific site). Only conclude "no lookup needed" when the answer is
  genuinely already present.
- If the needed integration is NOT in the available list, use_tool=false and
  say which integration is missing in `reason`."""

# The planner does NOT pin a model — routing is BPC's job. Planning prompts are
# tiny, so the call is SHAPED cheaply (``disable_reasoning=True``,
# temperature 0) instead of naming a model.
#
# The pin was removed because a ``provider_model`` pin collapses the handler's
# candidate list to one tuple, which deletes every provider fallback: the same
# single point of failure that took the canvas editor down on a transient 429
# (2026-09-10). Its original justification — unpinned routing preferring an
# unreachable local Ollama client — is handled by BPC itself, which excludes
# connection-dead providers (`_filter_by_health` +
# provider circuit breaker). Do not reintroduce a PLANNER_MODEL constant.


# Explicit web-research phrasings. DETECTOR ONLY — it never chooses the
# service or the query (that stays with the LLM, per the repo standard of
# LLM routing over intent regexes); it only decides whether a DECLINED plan
# earns one corrective pass plus a deterministic floor. Live 2026-09-08:
# "web research lead's bandsaw … compare it to our bandsaw" got use_tool=false
# from the planner and the reply claimed the agent had no research ability.
_NEGATED_WEB_RESEARCH_RE = re.compile(
    r"\b(?:no|not|don'?t|do\s*not|doesn'?t|never|without|skip(?:ping)?|"
    r"avoid|stop|except|instead\s+of)\b[^.!?;]{0,30}$",
    re.IGNORECASE,
)
_EXPLICIT_WEB_RESEARCH_RE = re.compile(
    r"\bweb\s+research(?:ing|ed)?\b"
    r"|\bsearch(?:ing)?\s+the\s+(?:web|internet)\b"
    r"|\bgoogle\b\s+(?:it|this|that|them|him|her|the|for)\b"
    r"|\b(?:research|look|find|check|search)\b[^!?;\n]{0,40}?\bonline\b"
    r"|\b(?:research|look)\b[^!?;\n]{0,40}?\bover\s+the\s+web\b"
    r"|\bonline\s+research\b",
    re.IGNORECASE,
)


def _explicit_web_research_requested(message: str) -> bool:
    """True when the user's message itself instructs web research, and the
    mention is not negated ("don't web research" / "no web research" must
    NOT trigger the floor)."""
    if not message:
        return False
    for m in _EXPLICIT_WEB_RESEARCH_RE.finditer(message):
        before = message[max(0, m.start() - 40):m.start()]
        if _NEGATED_WEB_RESEARCH_RE.search(before):
            continue
        return True
    return False


async def _escalate_declined_web_research(
    llm_service: Any,
    declined: Optional[ToolPlan],
    connected: List[str],
    catalog: str,
    history: List[Dict[str, Any]],
    message: str,
) -> Optional[ToolPlan]:
    """Force the web question back onto web tools. Covers every non-web
    outcome of the first pass on a message that EXPLICITLY asks for web
    research: a declined plan, a failed plan, or a valid plan that routed
    elsewhere (memory/CRM — live 2026-09-08: pass 1 returned a legitimate
    memory.search plan and the reply STILL claimed no web-search tool
    exists). Hybrid per repo standards: the regex detector only flags the
    instruction; one corrective structured pass still owns HOW to search
    the web (web_search vs web_fetch); only when that pass fails to name a
    WEB tool does a deterministic web_search rung fire, with the query
    built by build_search_query from the conversation — not from
    pattern-matched nouns. The user's words name the source, and they said
    the web."""
    allowed = set(connected) | set(_available_platform_services())
    if "web_search" not in allowed:
        # Honestly unavailable in this workspace — keep the decline.
        return declined
    if declined is None:
        # NO decision at all (provider outage / unparseable output). A
        # corrective LLM call into the same degraded provider just
        # multiplies latency — the deterministic rung answers immediately
        # (live 2026-09-08: 429 storms made each planner attempt cost
        # 25s+; the repair pass doubled that before failing too).
        from core.intelligent_search import build_search_query

        query = build_search_query(message, history_turns=history) or message[:120]
        logger.info(
            f"tool planner: explicit-web-research floor (no plan from "
            f"provider) -> web_search {query!r}")
        return ToolPlan(
            use_tool=True, service="web_search", intent="search", query=query,
            reason="explicit web research instruction",
        )
    defect = (
        "the user EXPLICITLY asked for web research in their latest message, "
        "but the plan declined to use any tool "
        f"({(declined.reason if declined else '') or 'no reason given'}). "
        "The corrected plan MUST use web_search (or web_fetch when the "
        "message names a specific page to read)"
    )
    repaired = await _repair_plan_via_llm(
        llm_service, defect, connected, catalog, history, message)
    if (repaired and repaired.use_tool
            and repaired.service in ("web_search", "web_fetch")):
        logger.info(
            f"tool planner: explicit-web-research repair -> "
            f"{repaired.service}.{repaired.intent}")
        return repaired
    from core.intelligent_search import build_search_query

    query = build_search_query(message, history_turns=history) or message[:120]
    logger.info(
        f"tool planner: explicit-web-research floor -> web_search {query!r}")
    return ToolPlan(
        use_tool=True, service="web_search", intent="search", query=query,
        reason="explicit web research instruction",
    )


class ToolPlan(BaseModel):
    use_tool: bool = False
    service: Optional[str] = None
    intent: Optional[str] = "search"
    query: Optional[str] = None
    reason: str = ""
    # Routing consolidation (2026-09-09): the same structured call also
    # classifies the turn for feature routing, so the separate NLU LLM
    # parse (ai/nlp_engine.parse_command — one completion per message) can
    # be skipped when these are present and confident. Optional by
    # contract: consumers fall back to the NLU parse when absent,
    # low-confidence, or unrecognized.
    suggested_intent: Optional[str] = None
    routing_confidence: Optional[float] = None

    @field_validator("routing_confidence", mode="before")
    @classmethod
    def _coerce_numeric_string(cls, v: Any) -> Any:
        # Small models emit quoted numbers through tool-call arguments
        # ("routing_confidence": "0.9"). Pydantic's strict float rejects
        # strings, and one rejection sends instructor into a regeneration
        # loop that outlives the planner's whole time budget (live
        # 2026-09-09: 4+ identical generations, plan lost, 25s timeout).
        if isinstance(v, str):
            try:
                return float(v.strip())
            except ValueError:
                return None
        return v


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
    try:
        from integrations.universal_integration_service import SEARCHABLE_SERVICES
    except Exception:
        SEARCHABLE_SERVICES = frozenset()
    for svc in list(connected) + _available_platform_services():
        desc = _SERVICE_DESCRIPTIONS.get(svc)
        if desc is None:
            if svc in SEARCHABLE_SERVICES or svc in _INTENT_ACTIONS:
                desc = "integration data — live search supported"
            else:
                # Honest catalog: a service without a live search would
                # otherwise get planned and then dead-end into the memory
                # fallback while the model CLAIMED a live search ran.
                desc = ("integration data — no live search; use memory for "
                        "its ingested records")
        lines.append(f"- {svc}: {desc}")
    return "\n".join(lines) if lines else "- (none connected)"


def _history_transcript(history: List[Dict[str, Any]], current: str) -> str:
    """USER turns only. What tool action the user wants is a function of
    their requests; assistant replies add nothing here and actively hurt:
    in a session with several failed attempts the transcript is a wall of
    refusals, which both bloats the prompt past the timeout budget and
    biases the planner into agreeing that 'there is nothing to retry'."""
    lines: List[str] = []
    for h in (history or [])[-10:]:
        u = str((h or {}).get("message") or "").strip()
        if u:
            lines.append(f"User: {u[:200]}")
    lines.append(f"User: {current[:400]}")
    return "\n".join(lines)


async def _structured_with_fallback(
    llm_service: Any, *, prompt: str, response_model: Any,
    system_instruction: str,
) -> Any:
    """Planner structured call routed by BPC (no model pin).

    Delegates to :mod:`core.llm.pinned_planning` with NO pin, so BPC ranks the
    candidates and the call keeps the provider fallback that a pin would remove.
    The prompt is still SHAPED as a small non-reasoning plan via
    ``pinned_structured_call``'s ``disable_reasoning=True`` default.

    Historically this pinned ``("openrouter", PLANNER_MODEL)`` with one unpinned
    retry. That retry existed only to undo the pin; with no pin there is nothing
    to undo, so exactly one call is issued.
    """
    from core.llm.pinned_planning import pinned_structured_call

    return await pinned_structured_call(
        llm_service,
        prompt=prompt,
        response_model=response_model,
        system_instruction=system_instruction,
        call_kwargs=None,  # no pin — BPC ranks the candidates
        log_label="tool planner",
        task_type="planning",
    )


_REPAIR_SYSTEM = """You repair an invalid tool plan for an AI automation
platform. The previous plan JSON was rejected: {defect}.

Available tools:
{catalog}

Recent conversation:
{transcript}

Return a CORRECTED plan:
- service MUST be one of the exact names in the available list (or null with
  use_tool=false when no tool can help).
- intent: search or list for lookups; `read` only for file-storage services
  when the user wants a specific row/value/section out of a named document,
  or for outlook when the full body of an email (quoted/forwarded thread)
  is needed beyond its search snippets.
- query: minimal retrieval terms that name the subject AND carry every
  identifying code (model, SKU, part, order, invoice number) exactly as
  written anywhere in the conversation — the user's current message often
  says "check the file again" while the code lives in earlier turns."""


async def _repair_plan_via_llm(
    llm_service: Any,
    defect: str,
    connected: List[str],
    catalog: str,
    history: List[Dict[str, Any]],
    message: str,
) -> Optional[ToolPlan]:
    """Second structured LLM pass that FIXES routing instead of guessing it
    from surface patterns. Regex repair (service-name matching, file nouns,
    recently-used fallback) kept misrouting fluid conversations — the words
    that justify a route ("the file", "try again") don't reliably name the
    service, and only the model sees the context that does (live 2026-09-03:
    "check consolidated price list file" regex-routed to the mailbox). One
    corrective call, then deterministic handoff; returns None on failure."""
    if llm_service is None:
        return None
    prompt = (
        f"{_REPAIR_SYSTEM.format(defect=defect, catalog=catalog, transcript=_history_transcript(history, message))}\n\n"
        "Return the corrected plan."
    )
    try:
        return await _structured_with_fallback(
            llm_service,
            prompt=prompt,
            response_model=ToolPlan,
            system_instruction="You return only the requested JSON object.",
        )
    except Exception as e:  # noqa: BLE001 — repair is best-effort
        logger.warning(f"tool planner: repair re-plan failed: {e}")
        return None


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
        f"Available tools:\n{catalog}\n\n"
        f"Recent conversation:\n{_history_transcript(history, message)}\n\n"
        "Return the tool plan."
    )
    plan = await _structured_with_fallback(
        llm_service,
        prompt=prompt,
        response_model=ToolPlan,
        system_instruction="You return only the requested JSON object.",
    )
    # EXPLICIT-RESEARCH FLOOR: a message that explicitly instructs web
    # research must END in a web tool whenever web is configured — whether
    # the first pass declined, failed, or validly routed somewhere else
    # (live 2026-09-08: pass 1 returned a legitimate memory.search plan and
    # the reply still claimed no web-search tool exists). The escalation
    # lets the LLM re-route among web tools and falls to a deterministic
    # web_search rung only when it won't.
    if _explicit_web_research_requested(message) and (
            plan is None or not plan.use_tool
            or (plan.service or "") not in ("web_search", "web_fetch")):
        plan = await _escalate_declined_web_research(
            llm_service, plan, connected, catalog, history, message)
    if plan is None:
        return None
    if plan.use_tool:
        allowed = set(connected) | set(_available_platform_services())
        if not plan.service or plan.service not in allowed:
            # Planner models emit service names in loose forms ("Zoho CRM",
            # "zoho-inventory") — normalize separators/case against the
            # allowed set before treating the plan as invalid. Mechanical
            # aliasing of the LLM's own choice, not a routing decision.
            if plan.service:
                normalized = re.sub(r"[^a-z0-9]", "", plan.service.lower())
                alias = {re.sub(r"[^a-z0-9]", "", s): s for s in allowed}
                candidate = alias.get(normalized)
                if candidate and candidate != plan.service:
                    logger.info(
                        f"tool planner: normalized service "
                        f"{plan.service!r} -> {candidate!r}")
                    plan.service = candidate
        if not plan.service or plan.service not in allowed:
            # Free planner models occasionally emit use_tool=true with a
            # null/unknown service ("try again", vague messages). Routing
            # stays with the LLM: one corrective structured pass that sees
            # the catalog, the conversation and the specific defect, instead
            # of pattern-matching the message's nouns — the words that
            # justify a route ("the file", "try again") don't reliably name
            # the service, and only the model sees the context that does
            # (live 2026-09-03: "check consolidated price list file"
            # pattern-routed to the recently-used mailbox).
            defect = ("no service was named" if not plan.service
                      else f"service {plan.service!r} is not in the available list")
            repaired = await _repair_plan_via_llm(
                llm_service, defect, connected, catalog, history, message)
            if (repaired and repaired.use_tool
                    and repaired.service in allowed):
                logger.info(
                    f"tool planner: LLM repair -> "
                    f"{repaired.service}.{repaired.intent}")
                plan = repaired
            elif repaired and not repaired.use_tool:
                # The repair pass looked at the context and concluded no
                # tool can help — honor that instead of forcing memory.
                logger.info("tool planner: LLM repair declined tool use")
                return None
        if not plan.service or plan.service not in allowed:
            if plan.service is None and "memory" in allowed:
                # Terminal rung after BOTH passes failed to name a service:
                # memory is always available and searches the workspace's
                # OWN ingested data. A constant default, not a content-based
                # guess — the ingested-store supplement on every other leg
                # makes this the safest place to land.
                logger.info(
                    "tool planner: both passes failed — defaulting to "
                    "always-available memory search")
                plan.service = "memory"
                plan.intent = "search"
                if not (plan.query or "").strip():
                    plan.query = message[:120]
            else:
                logger.info(f"tool planner: service not connected ({plan.service!r}): {plan.reason[:80]}")
                return None
        allowed_intents = {"search", "list"}
        if plan.service in _STORAGE_SERVICES or plan.service == "outlook":
            allowed_intents.add("read")
        if plan.service in _MAILBOX_SERVICES:
            allowed_intents.add("ingest")
        if plan.intent not in allowed_intents:
            plan.intent = "search"
        if not (plan.query or "").strip():
            plan.query = message[:120]
    return plan


def _current_message_text(context: Optional[Dict[str, Any]]) -> str:
    """The user's current message, from the hydrated history tail (last
    user-role entry). Empty when history is unavailable."""
    for entry in reversed((context or {}).get("history") or []):
        if isinstance(entry, dict) and entry.get("role") == "user":
            return _entry_text(entry)
    return ""


def _entry_text(entry: Any) -> str:
    """All string content of a history entry, whatever its shape — session
    history, planner history and hydrated turns don't share one schema."""
    if isinstance(entry, dict):
        return " ".join(
            str(v) for v in entry.values() if isinstance(v, (str, int, float))
        )
    return str(entry or "")


class _StorageQuery(BaseModel):
    """LLM-authored retrieval query for a storage-service leg."""
    query: str


_STORAGE_QUERY_SYSTEM = """You compose the retrieval query for one
file-storage lookup (search = find files by name; read = open a file and
extract the region a question is about).

Rules:
- Name the document (its name, type, or the phrase the user used for it)
  AND every identifying code — model, SKU, part, order or invoice number —
  EXACTLY as written anywhere in the conversation or open canvas, even when
  the user's latest message doesn't repeat it ("check the catalog file
  again and find the row" still means the code from earlier turns).
- Keep it to retrieval terms: no instructions, no full sentences.
- If the draft query already does this, return it unchanged."""


async def _rewrite_storage_query(
    llm_service: Any, query: str, intent: str,
    context: Optional[Dict[str, Any]],
) -> str:
    """LLM-authored storage query. The planner's query inherits the current
    message's wording and drops identifiers that live in earlier turns or
    the open canvas — a read excerpt then anchors on boilerplate and the
    row stays invisible (live 2026-09-04: three turns). Routing already
    belongs to the LLM; query AUTHORSHIP does too — pattern scans of the
    context kept mis-deciding what counts as an identifier. Bounded: on any
    failure the draft query passes through unchanged."""
    if llm_service is None:
        return query
    ctx = context or {}
    canvas = _entry_text(ctx.get("canvas") or {})[:1200]
    transcript = _history_transcript(
        ctx.get("history") or [], canvas or query)[:2000]
    prompt = (
        f"{_STORAGE_QUERY_SYSTEM}\n\n"
        f"Intent: {intent}\n"
        f"Draft query from the planner: {query!r}\n\n"
        f"Open canvas (may hold the identifiers):\n{canvas}\n\n"
        f"Recent conversation:\n{transcript}\n\n"
        "Return the query."
    )
    try:
        result = await asyncio.wait_for(
            _structured_with_fallback(
                llm_service,
                prompt=prompt,
                response_model=_StorageQuery,
                system_instruction="You return only the requested JSON object.",
            ),
            timeout=10,
        )
        rewritten = (getattr(result, "query", "") or "").strip()
        return rewritten or query
    except Exception as e:  # noqa: BLE001 — the draft query still works
        logger.warning(f"storage query rewrite skipped: {e}")
        return query


def _context_identifier_net(ctx: Dict[str, Any], query: str, limit: int = 2) -> List[str]:
    """Identifier tokens (model/SKU-shaped — _product_tokens) that the
    current message, recent history and open canvas carry but the draft
    query dropped. Shared by the storage and item-search query nets: small
    planner models drop codes that live in earlier turns (live 2026-09-04:
    the user named the exact keywords and the planner still sent
    'bandsaw' three turns running). Order-preserving, capped."""
    hay = " ".join(
        [_current_message_text(ctx)]
        + [_entry_text(m) for m in (ctx.get("history") or [])[-8:]]
        + [_entry_text(ctx.get("canvas") or {})]
    )
    return [
        t for t in _product_tokens(hay, min_len=6, skip_hexlike=True)
        if t.lower() not in (query or "").lower()
    ][:limit]


def _rank_address_hits(rows: List[Dict[str, Any]], addr_l: str, limit: int = 4) -> List[Dict[str, Any]]:
    """Rank raw comms rows matching an address. Participant rows (the
    address appears in sender/recipient — actual thread members) outrank
    body-only mentions (quoted threads, lead-form echoes); newest first
    within a tier. Rows arrive in table (insertion) order, not relevance:
    with a thread's key messages ingested late, a first-N cap surfaced lead
    forms and internal chatter while the actual reply sat near the end of
    the table (live 2026-09-06: jschulz@blumetric.ca — Jacob's reply and the
    sent quote never made the cap). Exact duplicate rows (re-ingested
    copies) collapse to one so they don't burn cap slots."""
    seen_keys = set()
    scored = []
    for row in rows:
        sender = str(row.get("sender") or "")
        recipient = str(row.get("recipient") or "")
        subj = str(row.get("subject") or "")
        content = str(row.get("content") or "")
        ts = str(row.get("timestamp") or "")
        # Body prefix in the key: re-ingested copies can carry a re-stamped
        # timestamp (so (sender, recipient, subject, ts) misses them, live
        # 2026-09-06) but near-identical bodies. Distinct replies in one
        # thread differ in body well within the prefix.
        key = (sender, recipient, subj, content[:120])
        if key in seen_keys:
            continue
        blob = f"{sender} {recipient} {content} {subj}".lower()
        if addr_l not in blob:
            continue
        seen_keys.add(key)
        participant = addr_l in sender.lower() or addr_l in recipient.lower()
        scored.append((0 if participant else 1, ts, row))
    # Two stable sorts: newest first overall, then participant tier wins.
    scored.sort(key=lambda t: t[1], reverse=True)
    scored.sort(key=lambda t: t[0])
    return [t[2] for t in scored[:limit]]


def _ingested_line_from_row(row: Dict[str, Any], with_body: bool) -> str:
    """One [ingested mailbox] listing line; with_body appends the FULL
    message text. Bodies come from metadata.html_body (ingestion's store
    choke point for original markup) with the plain content column as
    fallback — the 260-char content excerpt cut mid-signature, exactly
    where quoted/forwarded originals begin (live 2026-09-09 ryershov
    thread). Head+tail capped like the Graph hydration."""
    line = (
        f"- [ingested mailbox] From: {row.get('sender')} | "
        f"{str(row.get('subject') or '')[:90]} | "
        f"received: {str(row.get('timestamp') or '')[:19]}"
    )
    if not with_body:
        return line + f" | {str(row.get('content') or '')[:260]}"
    body = ""
    try:
        import json as _json

        meta = row.get("metadata")
        if isinstance(meta, str):
            try:
                meta = _json.loads(meta)
            except Exception:
                meta = None
        html = (meta or {}).get("html_body") if isinstance(meta, dict) else None
        if html:
            from core.communication_styling import html_to_text

            body = html_to_text(str(html))
    except Exception:
        body = ""
    body = (body or str(row.get("content") or "")).strip()
    if len(body) > _INGESTED_BODY_CAP:
        head = int(_INGESTED_BODY_CAP * 0.6)
        body = (
            body[:head]
            + "\n[…middle of this quoted thread elided…]\n"
            + body[-(_INGESTED_BODY_CAP - head):]
        )
    return line + " | FULL BODY:\n" + (body or "(empty message)")


def _search_ingested_by_address(user_id, address, limit=4):
    """Deterministic LanceDB lookup of ingested messages tied to an email
    address (sender/recipient/content containment, participant rows ranked
    first — see _rank_address_hits). Graph free-text search does not
    reliably match sender ADDRESSES (live 2026-09-02: Jacob Schulz's reply
    never surfaced because 'jschulz' is only the local part of the sender
    address) — the ingested copy is authoritative here and needs no
    embeddings. The top rows carry their FULL bodies (see
    _ingested_line_from_row): on 2026-09-09 Graph's relevance ranking
    returned unrelated mail for ryershov@nettinc.com and every listing line
    clipped the thread's quoted content away. Fault-isolated; [] on
    anything."""
    out = []
    if not address or "@" not in address:
        return out
    try:
        import lancedb

        base = Path(__file__).resolve().parent.parent / "data" / "atom_memory"
        db = lancedb.connect(str(base / "default"))
        table = db.open_table("atom_communications")
        df = table.to_arrow().to_pandas()
        for i, row in enumerate(
            _rank_address_hits(df.to_dict("records"), address.lower(), limit=limit)
        ):
            out.append(_ingested_line_from_row(row, with_body=i < _INGESTED_BODY_LINES))
    except Exception as e:
        logger.debug(f"ingested address search skipped: {e}")
    return out


async def _ingested_mailbox_lines(
    user_id, query, context=None, cap: int = 6, hybrid_min: int = 4
) -> List[str]:
    """Ranked ingested-mailbox lines for a communication lookup — the second
    source every mailbox-shaped search gets. Address fragments (query AND
    recent history) drive the deterministic scan — ONE full-table load per
    distinct address (the same address in query and history used to trigger
    two); the hybrid/semantic search only fills slots below ``hybrid_min``
    (embedding init + vector search was a real contributor to exec timeouts
    under load, live 2026-09-06, and free-text live APIs — Graph included —
    do not reliably match sender addresses or nicknames). Fault-isolated:
    [] on anything."""
    store_lines: List[str] = []
    import re as _re_addr

    _addr_haystack = query + " " + " ".join(
        _entry_text(m) for m in ((context or {}).get("history") or [])[-6:]
    )
    _seen_addrs = set()
    for _addr in _re_addr.findall(r"[\w.+-]+@[\w.-]+", _addr_haystack):
        if _addr.lower() in _seen_addrs:
            continue
        _seen_addrs.add(_addr.lower())
        # SYNC-OFF-LOOP: the scan loads and walks the whole comms table
        # (~4s at 3.5k rows, live 2026-09-06) — on the loop it froze every
        # concurrent request for that long, per address.
        for _line in await asyncio.to_thread(_search_ingested_by_address, user_id, _addr):
            if _line not in store_lines:
                store_lines.append(_line)
                if len(store_lines) >= cap:
                    break
        if len(store_lines) >= cap:
            break

    if len(store_lines) < hybrid_min:
        try:
            from core.hybrid_search.documents_hybrid import (
                DocumentsHybridSearch,
            )

            store_result = await DocumentsHybridSearch().search(
                query=query[:200], limit=6, owner_user_id=user_id
            )
            for hit in (store_result or {}).get("results") or []:
                if str(hit.get("source") or "") != "communication":
                    continue
                sender = str(hit.get("sender") or "?")
                title = str(hit.get("title") or "")
                snippet = str(hit.get("preview") or "")[:220]
                ts = str(hit.get("as_of") or "")
                line = (
                    f"- [ingested mailbox] From: {sender} | {title} | {snippet} | {ts}"
                )
                if line not in store_lines:
                    store_lines.append(line)
                if len(store_lines) >= cap:
                    break
        except Exception as store_err:
            logger.debug(f"comms-store supplement skipped: {store_err}")
    return store_lines


_PRODUCT_TOKEN_RE = re.compile(
    r"\b(?=[A-Za-z-]*\d)(?=[A-Za-z0-9-]*[A-Za-z])[A-Za-z0-9][A-Za-z0-9-]{4,}\b"
)
_STYLED_BODY_BLOCK_CAP = 6000


def _candidate_addresses(user_id, query, context=None, limit: int = 3) -> List[str]:
    """Email addresses named in the query or the last few history turns —
    the same haystack _ingested_mailbox_lines uses, so the styled-base
    lookup agrees with the listing about WHO the conversation is about."""
    import re as _re_addr

    hay = (query or "") + " " + " ".join(
        _entry_text(m) for m in ((context or {}).get("history") or [])[-6:]
    )
    out: List[str] = []
    for addr in _re_addr.findall(r"[\w.+-]+@[\w.-]+", hay):
        if addr.lower() not in [x.lower() for x in out]:
            out.append(addr.lower())
        if len(out) >= limit:
            break
    return out


def _latest_styled_ingested(user_id, addresses: List[str]) -> Optional[Dict[str, str]]:
    """Newest ingested message among ``addresses`` carrying style-bearing
    raw HTML. Ingestion persists every comm app's original markup under
    metadata.html_body (core.communication_styling, store choke point) —
    this surfaces it so the model can base a NEW draft on the REAL styled
    message instead of retyping from a 220-char text snippet. Lance filter
    on the (now internal) store, off-loop; fault-isolated → None."""
    if not addresses:
        return None
    try:
        import json as _json

        import lancedb

        base = Path(__file__).resolve().parent.parent / "data" / "atom_memory"
        table = lancedb.connect(str(base / "default")).open_table(
            "atom_communications"
        )
        rows = table.to_arrow().to_pandas().sort_values(
            "timestamp", ascending=False
        )
        for _, row in rows.iterrows():
            blob = (str(row.get("sender") or "") + " " + str(row.get("recipient") or "")).lower()
            if not any(a in blob for a in addresses):
                continue
            meta = row.get("metadata")
            if isinstance(meta, str):
                try:
                    meta = _json.loads(meta)
                except Exception:
                    continue
            html = (meta or {}).get("html_body") if isinstance(meta, dict) else None
            if html and "<" in str(html):
                return {
                    "sender": str(row.get("sender") or "?"),
                    "subject": str(row.get("subject") or ""),
                    "html": str(html)[:_STYLED_BODY_BLOCK_CAP],
                }
        return None
    except Exception as e:
        logger.debug(f"styled ingested body lookup skipped: {e}")
        return None


def _styled_base_section(styled: Optional[Dict[str, str]]) -> str:
    """Prompt section that hands the model a real styled message as a draft
    BASE. Copying the markup (not retyping from a snippet) is the point —
    the canvas and send path preserve raw HTML end to end."""
    if not styled:
        return ""
    return (
        f"\n\nSTYLED HTML BODY — newest styled message matching this lookup "
        f"(From: {styled.get('sender')} | {str(styled.get('subject') or '')[:90]}). "
        "To base a NEW draft on it: copy this markup as the canvas body and edit "
        "the wording in place; keep the styling tags intact (the canvas and send "
        "path preserve raw HTML):\n"
        + str(styled.get("html") or "")
    )


def _graph_styled_fallback(emails: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """Top-ranked live Graph hit whose body is styled HTML — the base when
    the ingested store has no styled copy for this participant."""
    try:
        from core.communication_styling import has_style_markup
    except Exception:
        return None
    for e in emails[:2]:
        body = e.get("body") or {}
        content = str(body.get("content") or "")
        if str(body.get("contentType") or "").lower() == "html" and has_style_markup(content):
            return {
                "sender": (
                    ((e.get("from_field") or {}).get("emailAddress") or {}).get("address")
                    or "?"
                ),
                "subject": str(e.get("subject") or ""),
                "html": content[:_STYLED_BODY_BLOCK_CAP],
            }
    return None


# Outlook body hydration. Graph $search returns a fixed property subset:
# the body field is OMITTED and bodyPreview holds only the first 255 chars
# (Microsoft's documented pattern for the full body is a follow-up
# GET /me/messages/{id}). The tool listing's 200-char clip then shrank that
# window further, so quoted/forwarded thread content was structurally
# invisible (live 2026-09-09: Roman Yershov's machine listing sat below the
# signature of the Sep 8 "Fw: Used Equipment sell" forward — the agent
# answered from previews and told the user the thread "needs to be opened
# in full" with no tool to do it). Same shape the file-storage legs already
# have: search → read.
_OUTLOOK_SEARCH_HYDRATE = 3     # full bodies fetched on every search
_OUTLOOK_READ_HYDRATE = 4      # intent=read: more hits, larger caps
_OUTLOOK_SEARCH_BODY_CAP = 3500
_OUTLOOK_READ_BODY_CAP = 5000
# Ingested-store listing lines: how many of the top ranked rows carry a
# FULL body, and the per-body cap (head+tail). The store is the
# deterministic source Graph's relevance ranking keeps failing to be.
_INGESTED_BODY_LINES = 2
_INGESTED_BODY_CAP = 2500
# A bare Graph item id (60+ base64url chars) on a read intent is fetched
# directly; prose queries re-run the ranked search instead.
_GRAPH_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{60,}$")


def _graph_body_text(msg: Dict[str, Any], cap: int) -> str:
    """Plain text of a full Graph message, head+tail capped. Long bodies
    keep BOTH ends: quoted originals sit BELOW the newest text in
    top-posted replies, so a head-only clip would re-create the exact
    blindness the hydration exists to fix. Never raises."""
    from core.communication_styling import html_to_text

    body = (msg or {}).get("body") or {}
    content = str(body.get("content") or "")
    if str(body.get("contentType") or "").lower() == "html":
        content = html_to_text(content)
    content = content.strip()
    if len(content) > cap:
        head = int(cap * 0.6)
        content = (
            content[:head]
            + "\n[…middle of this quoted thread elided…]\n"
            + content[-(cap - head):]
        )
    return content


async def _outlook_full_bodies(
    user_id: Optional[str], emails: List[Dict[str, Any]], top_n: int, cap: int
) -> Dict[str, str]:
    """id → plain-text full body for the top-ranked search hits, fetched
    with the documented per-message GET. Fetch failures degrade that
    message to a preview line; the block's tail hint offers intent=read."""
    from integrations.outlook_service import outlook_service

    async def _one(eid: str):
        try:
            msg = await outlook_service.get_email_by_id(user_id=user_id, email_id=eid)
        except Exception as body_err:
            logger.warning(
                f"outlook body hydration failed (id {str(eid)[:24]}…): {body_err}"
            )
            return eid, None
        text = _graph_body_text(msg, cap)
        return eid, (text or None)

    pairs = await asyncio.gather(
        *(_one(e["id"]) for e in emails[:top_n] if e.get("id"))
    )
    return {eid: text for eid, text in pairs if text}


_HEX_COLOR_RE = re.compile(r"^[0-9A-Fa-f]{6}$")


def _product_tokens(text: str, min_len: int = 5, skip_hexlike: bool = False,
                    limit: int = 3) -> List[str]:
    """Identifier candidates for exact-copy lookups: tokens that MIX letters
    with digits — the one shape every industry's catalog codes share (model
    numbers 'WG350DSAV', electronics parts 'LM358', chemical catalog
    'S318500', apparel SKUs 'NK-AQ0818', invoice refs 'INV-2024-118') and
    that prose, years, prices and quantities never do. Pure-digit tokens are
    excluded by the same logic. ``skip_hexlike`` drops 6-hex-digit tokens
    (canvas HTML style attributes like #1F3864 are layout noise; a genuine
    hex-shaped code from user-typed text still passes). Order-preserving
    dedupe, capped at ``limit``."""
    out: List[str] = []
    for m in _PRODUCT_TOKEN_RE.finditer(text or ""):
        tok = m.group(0)
        if len(tok) < min_len or tok in out:
            continue
        if skip_hexlike and _HEX_COLOR_RE.match(tok):
            continue
        out.append(tok)
        if len(out) >= limit:
            break
    return out


def _nearest_column_map(
    lance: Any, doc_id: str, match_ord: int, window: int = 10,
) -> str:
    """Column-heading map for a matched workbook row. The ev4 extraction
    serializes each sheet's headers once ('COLS: A=Model | I=US LIST | …')
    and rows positionally ('R17 | WG350DSAV | … | 14145 | …') — the row
    chunk carries its ROW number but not the column names, so a coordinate
    answer ('row 17, column I — US LIST') needs the sheet's schema line
    rejoined. Workbooks store sheets sequentially, so the nearest
    PRECEDING COLS line in the same family is the matched row's schema
    (capped: a match far past it may belong to the next sheet — beyond the
    window the map is omitted rather than misattributed). '' when absent."""
    try:
        tbl = lance.to_table(
            filter=(f"id LIKE '{doc_id}::c%' AND text LIKE '%COLS:%'"),
            columns=["id", "text"],
        )
        best_ord, best_text = None, ""
        for r in tbl.to_pylist():
            raw = str(r.get("id") or "")
            try:
                o = int(raw.rsplit("::c", 1)[1])
            except (IndexError, ValueError):
                continue
            if o < match_ord and (best_ord is None or o > best_ord):
                best_ord, best_text = o, str(r.get("text") or "")
        if best_ord is None or match_ord - best_ord > window:
            return ""
        pos = best_text.find("COLS:")
        line = best_text[pos:]
        line = line.split("\n", 1)[0].strip()
        return line[:400]
    except Exception:  # noqa: BLE001 — the map is best-effort context
        return ""


def _search_ingested_by_exact_token(user_id, query, skip_ids=None, limit=3):
    """Deterministic ingested-copy lookup for identifier tokens in the
    query (model numbers, SKUs, part/catalog codes — _product_tokens for the
    shape). Vector search and lexical analyzers both mangle these: the row
    carrying the code sits mid-file among numeric columns and never cracks
    the top-8 (live 2026-09-04: 'Consolidated Price List WG350DSAV' returned
    the workbook's head chunks while the row sat in chunk c2213 of 3,797).
    A containment scan finds it exactly — the same repair pattern addresses
    get from _search_ingested_by_address. Diverse by document: at most one
    excerpt per source document, so a code appearing in several files shows
    each file rather than three chunks of one. Fault-isolated; [] on
    anything."""
    out: List[str] = []
    seen_rows: List[str] = []
    seen_docs: set = set()
    try:
        import json as _json
        import lancedb

        tokens = _product_tokens(query or "", min_len=5)
        if not tokens:
            return out
        base = Path(__file__).resolve().parent.parent / "data" / "atom_memory"
        lance = (lancedb.connect(str(base / "default"))
                 .open_table("documents").to_lance())
        for tok in tokens:
            # The same code is written both ways — prose hyphenates
            # ("WG-350DSAV") while the stored cell carries the bare form
            # ("WG350DSAV"); scan both spellings or the identifying row is
            # missed in favor of lookalike records.
            variants = [tok]
            bare = tok.replace("-", "")
            if bare != tok and bare not in variants:
                variants.append(bare)
            for variant in variants:
                safe = variant.replace("'", "''")
                tbl = lance.to_table(
                    filter=f"text LIKE '%{safe}%'",
                    columns=["id", "text", "metadata", "source"],
                )
                for row in tbl.to_pylist():
                    rid = str(row.get("id") or "")
                    if skip_ids and rid in skip_ids:
                        continue
                    if rid in seen_rows:
                        continue
                    doc = rid.split("::")[0]
                    if doc and doc in seen_docs:
                        continue
                    try:
                        md = _json.loads(row.get("metadata") or "{}")
                    except Exception:  # noqa: BLE001 — metadata is best-effort
                        md = {}
                    name = (md.get("file_name") or str(row.get("source") or "")
                            or "ingested file")
                    ingested_on = str(md.get("ingested_at") or "")[:10]
                    fresh = f" — ingested {ingested_on}" if ingested_on else ""
                    text = str(row.get("text") or "")
                    idx = text.upper().find(variant.upper())
                    if idx < 0:
                        idx = text.upper().find(tok.upper())
                    start = max(0, idx - 160)
                    excerpt = text[start:idx + 340].replace("\n", " | ")
                    # Column map for coordinate answers ("which row and
                    # column heading holds X?"): the row chunk carries the
                    # R# number; the sheet's schema line carries the names.
                    col_map = ""
                    if "::c" in rid:
                        try:
                            match_ord = int(rid.rsplit("::c", 1)[1])
                            col_map = _nearest_column_map(
                                lance, doc, match_ord)
                        except (IndexError, ValueError):
                            col_map = ""
                    coord = f" [sheet column map: {col_map}]" if col_map else ""
                    out.append(
                        f"- [document: {name}{fresh}] EXACT MATCH for '{tok}': "
                        f"…{excerpt}…{coord}"
                    )
                    seen_rows.append(rid)
                    if doc:
                        seen_docs.add(doc)
                    if len(out) >= limit:
                        return out
    except Exception as e:  # noqa: BLE001 — fault-isolated by contract
        logger.debug(f"ingested exact-token search skipped: {e}")
    return out


def _best_content_excerpt(content: str, query: str, width: int = 500) -> str:
    """Top non-overlapping windows of `content`, ranked by coverage and
    frequency of the corpus's terms. Single-row documents (file ingests store
    ONE LanceDB row) expose ~200-char previews to the model — always the
    document HEAD, so anything mid-file (pricing tabs, formulas) was
    invisible even though stored. One window is not enough: a query naming
    the file ("Consolidated Price List 2019") scores its head highest while
    the asked-about content sits mid-file — so show the best two regions.
    Terms come from the query PLUS recent conversation (callers pass both):
    the user's phrasing ("how is Full Cost calculated") carries the words
    that actually locate the region."""
    content = content.strip()
    if len(content) <= width:
        return content
    # 4+ chars: drop stopwords ("the", "how") whose frequency drowns real
    # signal in the freq term; keep "2019", "cost", "tool".
    terms: List[str] = []
    for t in re.findall(r"[a-z0-9]{4,}", (query or "").lower()):
        if t not in terms:
            terms.append(t)
    terms = terms[:12]
    lower = content.lower()
    step = max(width // 2, 1)
    scored = []
    for s in range(0, len(content) - width, step):
        window = lower[s : s + width]
        coverage = sum(1 for t in terms if t in window)
        freq = sum(window.count(t) for t in terms)
        scored.append((coverage, freq, s))
    scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
    picked: List[int] = []
    for coverage, freq, s in scored:
        if all(abs(s - p) >= width for p in picked):
            picked.append(s)
        if len(picked) >= 2:
            break
    picked.sort()
    parts = []
    for s in picked:
        excerpt = content[s : s + width]
        prefix = "[…earlier content skipped…] " if s > 0 else ""
        suffix = " […more below…]" if s + width < len(content) else ""
        parts.append(prefix + excerpt + suffix)
    return "\n".join(parts)


def _load_documents_df():
    """SYNC (callers must to_thread): full documents table for excerpt
    extraction — a file-ingest table with full text can be large, so this
    load is the expensive part and must run once per search, not per hit."""
    import lancedb

    base = Path(__file__).resolve().parent.parent / "data" / "atom_memory"
    table = lancedb.connect(str(base / "default")).open_table("documents")
    return table.to_arrow().to_pandas()


def _doc_hit_excerpt(doc_id: str, query: str, fallback: str, width: int = 600,
                     df: Any = None) -> tuple:
    """Query-anchored excerpt from the FULL stored text of a file-ingest row
    (documents table), with the ingestion date for freshness stamping.
    Falls back to the short preview for rows that are not LanceDB file
    ingests (PG-bridged records, conversations). Returns (excerpt, ingested_date).
    Pricing/values can change at the source — the date is what lets the
    agent (and the user) see how fresh a quoted figure is. Pass a preloaded
    ``df`` (see _load_documents_df) when extracting several hits: one table
    load per search, not per hit."""
    ingested_date = ""
    try:
        if df is None:
            df = _load_documents_df()
        ids = df["id"].astype(str)
        rows = df[ids == str(doc_id)]
        if rows.empty:
            # chunked layout: {doc_id}::c0, ::c1, … — join in chunk order so
            # the excerpt scorer sees the document's natural flow
            family = df[ids.str.startswith(f"{doc_id}::")]
            if not family.empty:
                order = family["id"].astype(str).str.extract(
                    r"::c(\d+)$", expand=False
                )
                family = family.assign(_ord=order.fillna("0").astype(int)).sort_values(
                    "_ord"
                )
                rows = family.drop(columns=["_ord"])
        if rows.empty:
            return fallback, ""
        records = rows.to_dict("records")
        content = "\n".join(str(r.get("text") or "") for r in records)
        if not content.strip():
            return fallback, ingested_date
        try:
            import json as _json
            md = _json.loads(records[0].get("metadata") or "{}")
            ingested_date = str(md.get("ingested_at") or "")[:10]
        except Exception:  # noqa: BLE001 — date is best-effort
            ingested_date = ""
        return _best_content_excerpt(content, query, width), ingested_date
    except Exception as e:  # noqa: BLE001 — fault-isolated by contract
        logger.debug(f"doc excerpt unavailable for {doc_id}: {e}")
        return fallback, ingested_date


async def _memory_search_block(
    user_id: Optional[str], query: str, context: Optional[Dict[str, Any]]
) -> Optional[str]:
    """Memory leg entry point: dataset-catalog evidence (when the query
    carries an identifying code) PREPENDED to the hybrid memory search — so
    the exact rows surface no matter which leg the planner picks (it
    nondeterministically chooses memory/read/inventory for value questions).
    None when neither matched."""
    ds_block = await _datasets_evidence(user_id, query, context)
    mem_block = await _memory_hybrid_block(user_id, query, context)
    if ds_block and mem_block:
        return f"{ds_block}\n\n{mem_block}"
    return ds_block or mem_block


async def _datasets_evidence(
    user_id: Optional[str], query: str, context: Optional[Dict[str, Any]]
) -> Optional[str]:
    """Positive-only dataset evidence for a code-bearing query: exact rows
    from the catalog, ungrounded (the caller's block carries the grounding
    rule). None when the query has no identifying code or the catalog has no
    match — memory then answers alone."""
    try:
        from core.sheet_dataset_service import (
            candidate_probe_tokens,
            render_dataset_answer,
            search_all_datasets_sync,
            sheet_datasets_enabled,
        )
    except ImportError:
        return None
    if not sheet_datasets_enabled():
        return None
    history_texts = [
        str(h.get("message") or "")[:500]
        for h in ((context or {}).get("history") or [])
        if isinstance(h, dict) and h.get("message")
    ][-6:]
    probe_query = query
    try:
        extra = _context_identifier_net(context or {}, query)
        if extra:
            probe_query = f"{query} {' '.join(extra)}"
    except Exception:  # noqa: BLE001 — enrichment is best-effort
        pass
    if not candidate_probe_tokens([probe_query] + history_texts):
        return None
    result = await asyncio.to_thread(
        search_all_datasets_sync, probe_query, user_id,
        (context or {}).get("workspace_id"), 2, 200, history_texts,
    )
    hits = (result or {}).get("hits") or []
    if not hits:
        return None  # augmentation is positive-only; memory answers alone
    lines = [
        f"DATASET CATALOG MATCH — every ingested spreadsheet searched for "
        f"'{result['token']}' ({result['files_searched']} files):"
    ]
    for hit in hits:
        lines.append(render_dataset_answer(hit))
    return "\n".join(lines)


async def _memory_hybrid_block(
    user_id: Optional[str], query: str, context: Optional[Dict[str, Any]]
) -> Optional[str]:
    """Hybrid search over the ingested workspace (documents, mailbox copies,
    records) formatted as a LIVE TOOL RESULTS block. The `memory` service leg
    of execute_tool_plan, factored out so other legs can fall back to it when
    their live source comes back empty. None when nothing matched."""
    try:
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

        result = await DocumentsHybridSearch().search(
            query[:200], limit=8, owner_user_id=user_id
        )
        # Excerpt corpus: the tool query names the SUBJECT; the user's own
        # words name what they want to KNOW about it. Both locate the region.
        excerpt_corpus = query + " " + " ".join(
            _entry_text(m) for m in ((context or {}).get("history") or [])[-3:]
        )
        lines: List[str] = []
        seen_ids = set()
        # SYNC-OFF-LOOP: excerpt extraction needs the FULL documents table —
        # load it once, off-loop (it was previously a full table load PER
        # HIT, up to 8 loads per search, all on the event loop).
        _doc_df = await asyncio.to_thread(_load_documents_df)
        for hit in (result or {}).get("results") or []:
            hid = str(hit.get("id") or "")
            if hid in seen_ids:
                continue
            seen_ids.add(hid)
            sender = str(hit.get("sender") or "")
            title = str(hit.get("title") or "")[:100]
            fallback_preview = str(hit.get("preview") or "")[:220].replace("\n", " ")
            # Full-content, query-anchored excerpt: the ~200-char preview
            # only ever showed a document's head, hiding pricing tabs and
            # formulas that live mid-file in single-row ingests.
            body, ingested_on = _doc_hit_excerpt(
                hid, excerpt_corpus, fallback_preview, df=_doc_df
            )
            body = body.replace("\n", " | ")
            source = str(hit.get("source") or hit.get("title") or "record")
            # Per-hit provenance: documents/files vs mailbox records vs
            # knowledge nodes. The model previously read these lines as
            # interchangeable truth and cited "the consolidated price list"
            # for content that was only ever its own prior chat reply echoed
            # back (live 2026-09-03). Naming the record type makes the
            # distinction visible at the evidence itself.
            source_kind = {
                "ingested": "document",
                "documents": "document",
                "knowledge": "knowledge-node",
                "communication": "email/chat record",
                "conversation": "email/chat record",
            }.get(source.lower(), source.lower() or "record")
            fresh = f" — ingested {ingested_on}" if (
                ingested_on and source_kind.startswith("document")
            ) else ""
            lines.append(
                f"- [{source_kind}: {source}{fresh}] {title}"
                + (f" | From: {sender}" if sender else "")
                + f" | {body}"
            )
        import re as _re_addr

        _hay = query + " " + " ".join(
            _entry_text(m) for m in ((context or {}).get("history") or [])[-6:]
        )
        for _addr in _re_addr.findall(r"[\w.+-]+@[\w.-]+", _hay):
            # SYNC-OFF-LOOP: full comms-table scan per address (~4s at 3.5k rows).
            for _line in await asyncio.to_thread(_search_ingested_by_address, user_id, _addr):
                if _line not in lines:
                    lines.append(_line)
                    if len(lines) >= 8:
                        break
            if len(lines) >= 8:
                break
        # Exact-token leg runs LAST but ranks FIRST: an exact model-number
        # match is the strongest evidence for "find the row" questions, so
        # it must not be cut by the 8-line cap when the hybrid legs already
        # filled the block.
        exact_lines = [
            _l for _l in await asyncio.to_thread(
                _search_ingested_by_exact_token, user_id, query, skip_ids=seen_ids)
            if _l not in lines
        ]
        if exact_lines:
            lines = exact_lines + lines
        if not lines:
            return None
        return _with_grounding(
            f"LIVE TOOL RESULTS (memory.search, query='{query}') — hybrid "
            f"search over ingested workspace data; use these to answer:\n"
            + "\n".join(lines[:8])
            + "\nEVIDENCE TYPES: [document]* lines are ingested file contents "
            "(searchable); [email/chat record]* lines are received messages; "
            "[knowledge-node]* lines are extracted entities. Prior assistant "
            "replies are NEVER in this evidence — a fact that appears only in "
            "the conversation is not something you 'found in a file'. "
            "FRESHNESS: [document: … — ingested YYYY-MM-DD] shows when the copy "
            "was taken. For prices, quotes, or stock that drive an answer, cite "
            "the figure WITH its ingested date; if the customer decision hinges "
            "on it being current, say the source file should be re-opened live "
            "to confirm."
        )
    except Exception as e:
        logger.warning(f"memory tool execution failed: {e}")
        return None


async def _datasets_search_block(
    user_id: Optional[str], query: str, context: Optional[Dict[str, Any]]
) -> Optional[str]:
    """Cross-file content probe over the dataset catalog, formatted as a LIVE
    TOOL RESULTS block. The `datasets` service leg of execute_tool_plan: lets
    the agent locate a value WITHOUT the user naming a file. Identifying
    (digit-bearing) tokens are probed across every ingested spreadsheet;
    a probe miss is returned as real negative evidence so the reply model
    says "not in any ingested sheet" and pivots to live sources instead of
    confabulating. Queries without an identifying token delegate to memory."""
    try:
        from core.sheet_dataset_service import (
            candidate_probe_tokens,
            render_dataset_answer,
            search_all_datasets_sync,
            sheet_datasets_enabled,
        )
    except ImportError:
        return None
    if not sheet_datasets_enabled():
        return None

    # Candidate identifiers come from the query AND the surrounding turns —
    # a 'try again' or pronoun-heavy turn may not carry the code itself.
    history_texts = [
        str(h.get("message") or "")[:500]
        for h in ((context or {}).get("history") or [])
        if isinstance(h, dict) and h.get("message")
    ][-6:]
    if not candidate_probe_tokens([query] + history_texts):
        # No identifying code — sheet-level SQL adds nothing over memory.
        return await _memory_search_block(user_id, query, context)

    result = await asyncio.to_thread(
        search_all_datasets_sync, query, user_id,
        (context or {}).get("workspace_id"), 2, 200, history_texts,
    )
    files_searched = result.get("files_searched", 0) if result else 0
    hits = (result or {}).get("hits") or []
    if hits:
        lines = [
            f"LIVE TOOL RESULTS (datasets.search, query='{query}') — every "
            f"ingested spreadsheet searched for '{result['token']}' "
            f"({files_searched} files). Exact rows, with file and sheet:"
        ]
        for hit in hits:
            lines.append(render_dataset_answer(hit))
        return _with_grounding(
            "\n".join(lines)
            + "\nThese rows come from the query-verified dataset copy; R# = "
            "spreadsheet row numbers. Cite only these values for exact figures."
        )
    tried = ", ".join(f"'{t}'" for t in ((result or {}).get("tokens_tried") or []))
    return _with_grounding(
        f"LIVE TOOL RESULTS (datasets.search, query='{query}'): every ingested "
        f"spreadsheet was searched ({files_searched} files) and the value(s) "
        f"{tried} appear in NONE of them. "
        "Say that plainly — do not estimate or fill the gap — and consider "
        "live sources (inventory/accounting apps) or asking the user where "
        "else it might live."
    )


async def _comm_per_term_retry(
    svc: Any, service: str, action: str, query: str,
    user_id: Optional[str], tenant_id: str, context: Optional[Dict[str, Any]],
) -> Optional[str]:
    """Retry a communication live search ONE TERM AT A TIME when the
    full-query search succeeded but returned nothing. Providers split into
    two failure shapes — AND-semantics searches zero out when any common
    token misses (slack/gmail), OR-ranking floods with junk (Graph; the
    outlook leg handles that with its own per-term fan-out + weighted
    merge). This is the bounded universal equivalent: ≤2 extra calls,
    longest (=rarest) terms first, longest-term matches ranked first in the
    merged block. Only the empty-success case reaches here — a hard
    provider error is not something a retry can fix."""
    try:
        tokens = sorted(
            {t for t in (query or "").split() if len(t) >= 3},
            key=len, reverse=True,
        )[:2]
        if not tokens:
            return None
        try:
            from integrations.universal_integration_service import SEARCHABLE_SERVICES
        except Exception:
            SEARCHABLE_SERVICES = frozenset()
        merged: List[str] = []
        for term in tokens:
            try:
                if action == "search" and service in SEARCHABLE_SERVICES:
                    res = await svc.search(
                        service, term,
                        context={
                            "user_id": user_id, "workspace_id": "default",
                            "tenant_id": tenant_id,
                            "agent_id": (context or {}).get("agent_id"),
                        },
                    )
                else:
                    res = await svc.execute(
                        service, action, {"query": term, "limit": 8},
                        context={
                            "user_id": user_id, "workspace_id": "default",
                            "tenant_id": tenant_id,
                            "agent_id": (context or {}).get("agent_id"),
                        },
                    )
            except Exception as term_err:
                logger.debug(f"per-term retry failed ({service} '{term}'): {term_err}")
                continue
            data = res.get("data") if isinstance(res, dict) else None
            if isinstance(res, dict) and res.get("status") == "success" and data:
                merged.append(
                    f"[matched '{term}'] {str(data)[:700]}"
                )
        if not merged:
            return None
        return _with_grounding(
            f"LIVE TOOL RESULTS ({service}.{action}, query='{query}') — the "
            f"full-query search returned nothing (provider term semantics); "
            f"per-term retries matched:\n" + "\n".join(merged)
        )
    except Exception as retry_err:
        logger.debug(f"per-term retry skipped: {retry_err}")
        return None


_DOMAIN_TOKEN_RE = re.compile(
    r"(?<![\w@.])((?:[a-z0-9-]+\.)+(?:com|ca|org|net|io|co|ai|dev|info|biz|us"
    r"|uk|de|fr|au|in|shop|store|app))(?:/[^\s]*)?",
    re.IGNORECASE,
)


async def _site_search_evidence(
    query: str,
    tenant_id: Optional[str],
    mcp: Any,
    search_err: str = "",
) -> Optional[str]:
    """When public web search yields nothing (unavailable or empty) but the
    query names a domain, read THAT site's own /search?q= results page. The
    site knows its own URLs even when the search provider doesn't — live
    2026-09-08 (canvas c3617a7f…): asked to find a product page on
    brennan.ca with search unavailable, the editor invented a
    /products/<model-number> URL that 404'd into a customer quote. Falls
    back to None on anything unusable; the caller then reports the failure
    honestly and the grounding rules keep the model from guessing."""
    try:
        match = _DOMAIN_TOKEN_RE.search(query or "")
        if not match:
            return None
        domain = match.group(1).lower()
        terms = " ".join(_DOMAIN_TOKEN_RE.sub(" ", query or "").split())
        if not terms:
            return None
        from urllib.parse import quote

        search_url = f"https://{domain}/search?q={quote(terms)}"
        res = await mcp.web_fetch(search_url, tenant_id)
        content = str(res.get("content") or "").strip()
        if not content:
            return None
        note = f" (search provider: {search_err[:120]})" if search_err else ""
        return (
            f"LIVE TOOL RESULTS (web_search, query='{query}'): no results"
            f"{note}. Fetched the SITE'S OWN search results page instead: "
            f"{search_url}\n\nThe matching page URLs are listed under "
            "'Links on this page' below — use one of them VERBATIM, do not "
            f"construct a URL:\n{content[:5000]}"
        )
    except Exception as exc:  # noqa: BLE001 — fallback must never raise
        logger.debug(f"site-search fallback skipped: {exc}")
        return None


def _planner_ingest_enabled() -> bool:
    """Kill switch for the planner's mailbox ``ingest`` leg (env > UI > on)."""
    try:
        from core.runtime_settings import get_bool_setting

        return bool(get_bool_setting("ATOM_PLANNER_INGEST_ENABLED", True))
    except Exception:  # noqa: BLE001 — a settings lookup must never block
        return True


async def _resolve_mailbox_message_ids(
    service: str, user_id: Optional[str], query: str, limit: int = 2
) -> List[str]:
    """Message ids for the ingest leg.

    A bare provider id is authoritative and used directly (Graph ids are not
    searchable text). Otherwise the mailbox is searched with the same
    per-term fan-out the search leg uses — Graph's OR-ranking buries rare
    terms under common ones — and the top hits are returned. [] on any
    failure or miss.
    """
    query = (query or "").strip()
    if not query:
        return []
    if service == "outlook" and _GRAPH_ID_RE.match(query):
        return [query]

    ids: List[str] = []

    def _remember(candidate: Any) -> None:
        if candidate and str(candidate) not in ids:
            ids.append(str(candidate))

    try:
        if service == "outlook":
            from integrations.outlook_service import (
                outlook_service,
                sanitize_graph_kql,
            )

            for term in ([t for t in query.split() if len(t) >= 2][:3] or [query]):
                kql = sanitize_graph_kql(term)
                if not kql:
                    continue
                emails = await outlook_service.search_emails(
                    user_id=user_id, query=kql, max_results=5, quote=False
                )
                for e in emails or []:
                    _remember(e.get("id"))
                if len(ids) >= limit:
                    break
        else:
            from integrations.gmail_service import GmailService

            def _search() -> List[Dict[str, Any]]:
                svc = GmailService()
                if not svc.service:
                    try:
                        svc._authenticate()
                    except Exception:  # noqa: BLE001 — reported as a miss
                        return []
                return svc.get_messages(query=query, max_results=5) or []

            for m in await asyncio.to_thread(_search):
                _remember(m.get("id"))
                if len(ids) >= limit:
                    break
    except Exception as e:  # noqa: BLE001 — the leg reports the miss honestly
        logger.warning(f"mailbox ingest message lookup failed ({service}): {e}")
        return []
    return ids[:limit]


async def _mailbox_ingest_block(
    service: str,
    user_id: Optional[str],
    query: str,
    context: Optional[Dict[str, Any]],
) -> str:
    """Pull a mailbox message's body + attachments INTO memory, then return
    the freshly indexed evidence.

    Why this leg exists: the Graph webhook path fetches messages WITHOUT
    attachment bytes, so binary attachments (product photos, scanned quotes)
    never reach memory, and mail predating the pipeline is absent too. An
    agent asked to use such content could only report it inaccessible. The
    poller is not the fix — the agent needs to be able to say "fetch it now".

    Governance: the per-user ``email_attachment`` autonomy topic gates it
    (same knob as the email_attachment_* agent tools); a pinned
    human-approval setting returns a proposal block instead of writing.
    """
    label = f"mailbox ingest, {service}, query='{query}'"
    if not _planner_ingest_enabled():
        return _with_grounding(
            f"LIVE TOOL RESULTS ({label}): on-demand ingest is disabled by "
            "configuration."
        )

    agent_id = (context or {}).get("agent_id")
    try:
        from core.database import get_db_session
        from tools.email_attachment_tool import _gate

        with get_db_session() as db:
            gated = _gate(db, user_id, agent_id)
        if gated:
            return _with_grounding(
                f"LIVE TOOL RESULTS ({label}): needs owner approval — "
                f"{gated.get('reason') or 'the email_attachment autonomy topic is pinned to review'}"
            )
    except Exception as gate_err:  # noqa: BLE001 — fail-open (reversible write)
        logger.debug(f"mailbox ingest autonomy gate skipped: {gate_err}")

    message_ids = await _resolve_mailbox_message_ids(service, user_id, query)
    if not message_ids:
        return _with_grounding(
            f"LIVE TOOL RESULTS ({label}): no matching message found in the "
            "mailbox to ingest."
        )

    from integrations.atom_communication_ingestion_pipeline import (
        ingestion_pipeline,
    )

    lines: List[str] = []
    for message_id in message_ids:
        try:
            result = await ingestion_pipeline.ingest_email_on_demand(
                service, user_id or "", message_id
            )
        except Exception as e:  # noqa: BLE001 — one bad message must not kill the leg
            logger.warning(f"on-demand ingest failed for {message_id}: {e}")
            result = {"status": "error", "reason": str(e)[:200]}
        status = result.get("status")
        short_id = message_id[:24]
        if status == "ingested":
            lines.append(
                f"- message {short_id}… INGESTED | subject: "
                f"{str(result.get('subject') or '(no subject)')[:100]} | "
                f"attachments indexed: {result.get('attachments') or 0}"
            )
        elif status == "already_ingested":
            lines.append(f"- message {short_id}… already in memory (no-op)")
        else:
            lines.append(
                f"- message {short_id}… could not be ingested: "
                f"{result.get('reason') or status}"
            )

    mem_block = await _memory_search_block(user_id, query, context)
    detail = (
        f"\n\nNow in memory:\n{mem_block}"
        if mem_block
        else "\n\n(no indexed excerpt matched the query yet — search memory "
        "again or widen the query)"
    )
    return _with_grounding(
        f"LIVE TOOL RESULTS ({label}) — content pulled from the connected "
        f"mailbox into memory just now:\n" + "\n".join(lines) + detail
    )


async def execute_tool_plan(
    plan: ToolPlan,
    user_id: Optional[str],
    tenant_id: str = "default",
    context: Optional[Dict[str, Any]] = None,
    llm_service: Any = None,
) -> Optional[str]:
    """Run the planned read-only action and return a text block for prompt
    injection. Returns None when nothing usable came back.

    ``context`` ({"history": [...], "canvas": {...}}) feeds the intelligent
    query builder: generic-noun queries ("research the lead") are rewritten
    to name the actual subject resolved from the conversation or the open
    canvas — for EVERY agent on this path, regardless of how strong the
    planning model's own query was."""
    if not plan or not plan.use_tool or not plan.service:
        return None
    service = plan.service
    query = (plan.query or "").strip()

    # Mailbox on-demand INGEST: the one write this planner performs. Runs
    # BEFORE the web-query rewrite (the query names a message, not a search
    # phrase) and before the search/read legs — the user needs the content
    # pulled from the integration into memory, not another metadata listing.
    if service in _MAILBOX_SERVICES and (plan.intent or "") == "ingest":
        return await _mailbox_ingest_block(service, user_id, query, context)

    if service in ("web_search", "web_fetch"):
        try:
            from core.intelligent_search import build_search_query

            ctx = context or {}
            rewritten = build_search_query(
                query,
                history_turns=ctx.get("history"),
                canvas_content=ctx.get("canvas"),
            )
            if rewritten and rewritten != query:
                logger.info(f"search query rewritten: {query!r} -> {rewritten!r}")
                query = rewritten
            else:
                # Rewrite skipped — make the reason visible at the default
                # log level: an un-rewritten generic query on a canvas turn
                # is how the 2026-09-08 research misses started.
                logger.info(
                    f"tool exec query kept as planned: {query!r} "
                    f"(canvas={'present' if ctx.get('canvas') else 'MISSING'}, "
                    f"history_turns={len(ctx.get('history') or [])})"
                )
        except Exception as query_err:
            logger.debug(f"intelligent query rewrite skipped: {query_err}")

    # Platform web tools (Tavily-backed, key resolved inside mcp_service).
    # Read-only like every planner leg; the full maturity-gated Playwright
    # browser_tool stays the path for interactive automation.
    if service in ("web_search", "web_fetch"):
        try:
            from integrations.mcp_service import mcp_service as _mcp

            # LOCAL KNOWLEDGE FIRST: the GraphRAG ontology already holds
            # entities/relationships extracted from the user's ingested mail
            # and docs (people, companies, what they do). A web search that
            # ignores it re-derives facts the workspace already knows — and
            # when the graph knows the lead, it also disambiguates the query.
            graph_block = ""
            try:
                from core.graphrag_engine import graphrag_engine

                graph_ctx = await asyncio.wait_for(
                    graphrag_engine.get_context_for_ai(query=query), timeout=5,
                )
                if graph_ctx and graph_ctx.strip():
                    graph_block = (
                        "LOCAL KNOWLEDGE (GraphRAG ontology — entities and "
                        "relationships extracted from this workspace's own "
                        "email and documents; authoritative for what the "
                        f"workspace already knows):\n{graph_ctx[:2500]}\n\n"
                    )
            except Exception as graph_err:
                logger.debug(f"GraphRAG context skipped: {graph_err}")

            if service == "web_search":
                res = await _mcp.web_search(query, tenant_id)
                err = str(res.get("error") or "").strip()
                answer = str(res.get("answer") or "").strip()
                results = res.get("results") or []
                if err or not (answer or results):
                    # Search unavailable (no/invalid key) or empty — but the
                    # query names a site. The site's own /search page knows
                    # its URLs even when the search provider doesn't (live
                    # 2026-09-08: with search unavailable the model invented
                    # /products/<model-number> instead). Evidence, not guess.
                    site_block = await _site_search_evidence(
                        query, tenant_id, _mcp, err
                    )
                    if site_block:
                        return _with_grounding(site_block)
                if err:
                    return _with_grounding(
                        f"LIVE TOOL RESULTS (web_search, query='{query}'): unavailable — {err[:200]}"
                    )
                lines = []
                if answer:
                    lines.append(f"Summary: {answer[:800]}")
                for r in results[:5]:
                    lines.append(
                        f"- {str(r.get('title') or '(untitled)')[:120]} | {str(r.get('url') or '')[:160]}\n"
                        f"  {str(r.get('content') or '')[:400]}"
                    )
                # DEEP FETCH for quote/product research: snippets carry a
                # fragment of the spec/pricing table; the manufacturer's or
                # primary listing's page carries the whole thing — the
                # authoritative-source-first rule quoting research uses.
                # Generalized beyond machinery model codes: fires when the
                # query carries a product identifier (WG-350DSAV, DM-10,
                # SKU/part shapes) OR research intent (specs/price/compare)
                # plus a named brand. A comparison naming TWO identifiers
                # fetches one authoritative page per side (max 2) — theirs
                # AND ours (live 2026-09-08: hydmech.com answered the DM-10
                # side fully while the WG-350DSAV side stayed snippet-less;
                # the reply had to ask for our own spec sheet).
                from core.intelligent_search import (
                    _MODEL_CODE_RE, _research_intent,
                )

                try:
                    codes = []
                    seen_codes = set()
                    for m in _MODEL_CODE_RE.finditer(query):
                        key = m.group(0).upper().replace("-", "")
                        if key not in seen_codes:
                            seen_codes.add(key)
                            codes.append(m.group(0))
                    brand_named = bool(re.search(
                        r"\b[A-Z][a-zA-Z]+[ -][A-Z][a-zA-Z0-9-]*\b", query))
                    if codes or (_research_intent(query) and brand_named):
                        # ordered tokens from the query that can identify a
                        # host (brands, site names: "hydmech", "brennan").
                        # ORDER MATTERS: our query builder puts identifiers
                        # first, so an early token matching the host (the
                        # brand) outranks a late category noun ("grill")
                        # that any blog domain contains.
                        query_tokens = [
                            t for t in dict.fromkeys(
                                re.split(r"[^a-z0-9]+", query.lower()))
                            if len(t) > 3
                        ]

                        def _host(url: str) -> str:
                            return re.sub(
                                r"^https?://(?:www\.)?", "", url).split("/")[0]

                        def _pick(target_code: Optional[str],
                                  pool: Optional[List[Any]] = None,
                                  require_code: bool = False,
                                  ) -> Optional[Dict[str, Any]]:
                            """Best unused result for this target: code-in-
                            URL/title, then host tokens weighted by query
                            position. None when no candidate scores.
                            ``require_code``: only results whose URL/title
                            carry the code count (used to decide whether a
                            side of the comparison is covered at all)."""
                            best, best_score = None, 0
                            for r in (pool if pool is not None else results)[:5]:
                                url = str(r.get("url") or "")
                                if not url or url in picked_urls:
                                    continue
                                blob = f"{url} {r.get('title') or ''}".lower()
                                score = 0
                                if target_code and target_code.lower() in blob:
                                    score += 2 + len(query_tokens)
                                elif require_code:
                                    continue
                                host = _host(url)
                                for idx, tok in enumerate(query_tokens):
                                    if tok in host:
                                        score += len(query_tokens) - idx
                                        break
                                if score > best_score:
                                    best, best_score = r, score
                            return best

                        picked_urls: List[str] = []
                        targets: List[Optional[str]] = codes[:2] if codes else [None]
                        for target_code in targets:
                            best = (_pick(target_code, require_code=True)
                                    if target_code else _pick(None))
                            via = ""
                            if target_code and best is None:
                                # UNCOVERED SIDE of the comparison: the
                                # combined query's results never mention
                                # this product (live 2026-09-08: brennan.ca
                                # didn't rank for "Hydmech DM10 Linmac
                                # WG-350DSAV …", so our own machine stayed
                                # snippet-less). A human researcher runs a
                                # SEPARATE search per product — "<code>
                                # specifications" — and reads its top page.
                                supp = await asyncio.wait_for(
                                    _mcp.web_search(
                                        f"{target_code} specifications",
                                        tenant_id),
                                    timeout=20,
                                )
                                spool = (supp or {}).get("results") or []
                                best = (_pick(target_code, pool=spool,
                                              require_code=True)
                                        or _pick(target_code, pool=spool))
                                via = " (via targeted per-product search)"
                            if best is None:
                                continue
                            fetch_url = str(best.get("url") or "")
                            picked_urls.append(fetch_url)
                            fres = await asyncio.wait_for(
                                _mcp.web_fetch(fetch_url, tenant_id),
                                timeout=20,
                            )
                            fcontent = str((fres or {}).get("content") or "").strip()
                            if fcontent:
                                label = (
                                    f" (authoritative page for {target_code}{via})"
                                    if target_code else ""
                                )
                                lines.append(
                                    f"FULL SPEC PAGE{label} ({fetch_url[:160]}) — "
                                    f"primary-source detail, prefer over snippets:\n"
                                    f"{fcontent[:4500]}"
                                )
                except Exception as deep_err:  # noqa: BLE001 — enhancement only
                    logger.debug(f"deep spec fetch skipped: {deep_err}")
                return _with_grounding(
                    f"{graph_block}"
                    f"LIVE TOOL RESULTS (web_search, query='{query}') — "
                    f"use these to answer:\n" + "\n".join(lines)
                )

            # web_fetch: read the page; when unreadable, degrade to search.
            res = await _mcp.web_fetch(query, tenant_id)
            err = str(res.get("error") or "").strip()
            content = str(res.get("content") or "").strip()
            if not content:
                # Site unreadable (bot-blocked 403, JS-only page, offline) —
                # a web_search about the same company usually still answers
                # the question, so degrade to search instead of dead-ending.
                err_note = err or "no readable text extracted"
                try:
                    search_query = f"{query} company what does this business do"
                    sres = await _mcp.web_search(search_query, tenant_id)
                    sanswer = str(sres.get("answer") or "").strip()
                    sresults = sres.get("results") or []
                    if sanswer or sresults:
                        lines = [f"(direct read of {res.get('url') or query} failed: {err_note[:120]}; fell back to web search)"]
                        if sanswer:
                            lines.append(f"Summary: {sanswer[:800]}")
                        for r in sresults[:5]:
                            lines.append(
                                f"- {str(r.get('title') or '(untitled)')[:120]} | {str(r.get('url') or '')[:160]}\n"
                                f"  {str(r.get('content') or '')[:400]}"
                            )
                        return _with_grounding(
                            f"LIVE TOOL RESULTS (web_fetch→web_search fallback, query='{search_query}') — "
                            f"use these to answer:\n" + "\n".join(lines)
                        )
                except Exception as fallback_err:
                    logger.warning(f"web_fetch→web_search fallback failed: {fallback_err}")
                return _with_grounding(
                    f"LIVE TOOL RESULTS (web_fetch, query='{query}'): page unreadable — {err_note[:200]}"
                )
            return _with_grounding(
                f"LIVE TOOL RESULTS (web_fetch, url={res.get('url')}) — the actual "
                f"content of this website; use it to answer:\n{content[:6000]}"
            )
        except Exception as e:
            logger.warning(f"web tool execution failed ({service}): {e}")
            return None

    # Memory: hybrid search over the INGESTED workspace corpus (documents +
    # communications + records — vector + lexical, conversations leg bridged
    # to the comms store). Ingestion writes the data; this is the agent tool
    # that queries it. Available to every agent, no OAuth. Address fragments
    # (query or conversation context) additionally get a deterministic
    # ingested-copy lookup, since neither Graph nor semantic search can map
    # nicknames/addresses reliably (live 2026-09-02: Jason vs Jacob Schulz).
    if service == "memory":
        block = await _memory_search_block(user_id, query, context)
        if block:
            return block
        return _with_grounding(
            f"LIVE TOOL RESULTS (memory.search, query='{query}'): "
            "nothing in the ingested workspace matched."
        )

    # Datasets: cross-file content probe over the SQL-queryable catalog —
    # the planner's answer to value questions the user asks WITHOUT naming
    # a source ("what's the price of X?"). Always returns a block: either
    # exact rows (file + sheet + R# cited) or honest negative evidence.
    if service == "datasets":
        block = await _datasets_search_block(user_id, query, context)
        if block:
            return block
        return _with_grounding(
            f"LIVE TOOL RESULTS (datasets.search, query='{query}'): "
            "no dataset catalog available."
        )

    # Outlook: dedicated service with per-user token handling. Graph $search
    # OR-ranks multi-word queries, so a rare surname gets buried under common
    # words ("Mark" → "Pavement Markings") — search each term separately and
    # merge, ranking hits that match more terms first, then by recency.
    if service == "outlook":
        try:
            from integrations.outlook_service import (
                outlook_service,
                sanitize_graph_kql,
            )

            read_mode = (plan.intent or "search") == "read"
            tool_label = "outlook.read_emails" if read_mode else "outlook.search_emails"
            body_cap = _OUTLOOK_READ_BODY_CAP if read_mode else _OUTLOOK_SEARCH_BODY_CAP

            # intent=read with a bare Graph message id fetches that message
            # directly: an id is not searchable text (the per-term search
            # below would 400 or empty the result set on it).
            if read_mode and _GRAPH_ID_RE.match(query):
                direct = await outlook_service.get_email_by_id(
                    user_id=user_id, email_id=query
                )
                if not direct:
                    return _with_grounding(
                        f"LIVE TOOL RESULTS (outlook.read_emails, id='{query[:40]}…'): "
                        "message not retrievable (deleted, moved, or no access)."
                    )
                direct_from = (
                    ((direct.get("from_field") or {}).get("emailAddress") or {}).get("address")
                    or "?"
                )
                return _with_grounding(
                    f"LIVE TOOL RESULTS (outlook.read_emails, id='{query[:40]}…') — "
                    f"FULL body; use it to answer:\n"
                    f"- From: {direct_from} | "
                    f"{str(direct.get('subject') or '(no subject)')[:120]} | "
                    f"received: {str(direct.get('received_date_time'))[:19]}\n"
                    + _graph_body_text(direct, body_cap)
                )

            tokens = [t for t in query.split() if len(t) >= 2][:3] or [query]
            merged: Dict[str, Dict[str, Any]] = {}
            for term in tokens:
                # Sanitize before the first call: an email address term
                # ("jschulz@blumetric.ca Jason response") 400s in Graph KQL
                # as-is, and that 400 used to silently empty the search —
                # the rare, selective term was exactly the one that failed.
                kql_term = sanitize_graph_kql(term)
                if not kql_term:
                    continue
                try:
                    emails = await outlook_service.search_emails(
                        user_id=user_id, query=kql_term, max_results=10, quote=False
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

            # FULL BODIES for the top hits: Graph $search omits the body
            # entirely (bodyPreview is only the first 255 chars), so quoted
            # and forwarded thread content under that window never reached
            # the model (live 2026-09-09: Roman Yershov's machine listing
            # sat under the signature of the Sep 8 "Fw: Used Equipment
            # sell" forward; the agent answered from previews). read intent
            # hydrates more hits with larger caps.
            full_bodies = await _outlook_full_bodies(
                user_id, emails,
                _OUTLOOK_READ_HYDRATE if read_mode else _OUTLOOK_SEARCH_HYDRATE,
                body_cap,
            )
            logger.info(
                f"outlook leg: hydrated {len(full_bodies)} full bodies "
                f"(intent={plan.intent}, {len(emails)} graph hits)"
            )

            # DETERMINISTIC FIRST: ranked ingested-copy lookup — shared with
            # the universal communication path (gmail/slack/telegram/…).
            store_lines = await _ingested_mailbox_lines(user_id, query, context)

            if not emails and not store_lines:
                # A mailbox miss is not the whole story: the question may be
                # about DOCUMENT content that was misrouted here (live
                # 2026-09-03: "check consolidated price list file … find the
                # row" fell back to outlook, Graph 400'd on the model number,
                # and the verify panel then stripped the row claims as
                # ungrounded). Full ingested-workspace search instead of a
                # dead end — the [document: …] source labels keep the model
                # from presenting those hits as mail.
                mem_block = await _memory_search_block(user_id, query, context)
                if mem_block:
                    return (
                        f"LIVE TOOL RESULTS ({tool_label}, query='{query}'): "
                        f"no matching messages in the mailbox. "
                        f"Ingested-workspace matches:\n{mem_block}"
                    )
                return _with_grounding(
                    f"LIVE TOOL RESULTS ({tool_label}, query='{query}'): "
                    "no matching messages in the mailbox or ingested memory."
                )
            # Deterministic thread-member lines LEAD the block: for an
            # address query, Graph's relevance ranking fills its slots with
            # unrelated recent mail (live 2026-09-06: Zoho lead forms for a
            # different customer), and the reply model anchors on the first
            # lines it reads — run 1 echoed that junk and declared the
            # thread nonexistent while the real messages sat further down.
            def _graph_line(e: Dict[str, Any]) -> str:
                frm = (
                    ((e.get("from_field") or {}).get("emailAddress") or {}).get("address")
                    or "?"
                )
                head = (
                    f"- From: {frm} | {str(e.get('subject') or '(no subject)')[:120]} | "
                    f"received: {str(e.get('received_date_time'))[:19]}"
                )
                text = full_bodies.get(e.get("id"))
                if text:
                    return head + " | FULL BODY:\n" + text
                # Hydration miss: keep the Graph preview (≤255 chars) so the
                # line still says something, and the tail hint below flags
                # the read-intent follow-up.
                return head + f" | preview: {str(e.get('body_preview') or '')[:200]}"

            listing = "\n".join(store_lines)
            graph_listing = "\n".join(_graph_line(e) for e in emails[:6])
            if graph_listing:
                listing = (listing + "\n" if listing else "") + graph_listing
            if emails and len(full_bodies) < min(len(emails), 6):
                listing += (
                    "\n(preview-only lines above: plan outlook again with "
                    "intent=read and the same query to pull those full bodies)"
                )
            if read_mode:
                return _with_grounding(
                    f"LIVE TOOL RESULTS (outlook.read_emails, query='{query}') — "
                    f"FULL message bodies (quoted/forwarded thread content "
                    f"included); use these to answer:\n{listing}"
                )
            # Styled-draft base: the newest ingested message for this
            # participant carries its original markup (metadata.html_body);
            # when the store has none, the top live hit's Graph HTML body
            # stands in. Without this the model only ever sees a 200-char
            # text preview and CANNOT honor "draft a new email that looks
            # like that message".
            styled_section = _styled_base_section(
                _latest_styled_ingested(
                    user_id, _candidate_addresses(user_id, query, context)
                )
            ) or _styled_base_section(_graph_styled_fallback(emails))
            return _with_grounding(
                f"LIVE TOOL RESULTS (outlook.search_emails, query='{query}') — "
                f"use these to answer:\n{listing}"
                f"{styled_section}"
            )
        except Exception as e:
            logger.warning(f"outlook tool execution failed: {e}")
            return None

    # Everything else: the universal integration service (44 integrations,
    # governance + circuit breaker + masking inside). Two live paths:
    #   1. explicit intent->action mappings (_INTENT_ACTIONS) run through
    #      execute() — per-service handlers (zoho_inventory.search_items,
    #      slack search_messages, storage search/read, ...);
    #   2. plain "search" intents for services with a family search
    #      implementation route through the search() router — the same
    #      mechanism MCP/entity search already uses.
    # Everything else dead-ends HONESTLY ("has no live implementation").
    # A success-without-data envelope here is what let the model claim it
    # had searched an integration that was never called (live 2026-09-03:
    # "searched Zoho Inventory, no live stock records" while the machine
    # sat in stock).
    try:
        from integrations.universal_integration_service import (
            UniversalIntegrationService,
            SEARCHABLE_SERVICES,
        )

        # Query AUTHORSHIP is an LLM job too (same principle as routing):
        # the planner's query inherits the current message's wording and
        # drops identifiers that live in earlier turns or the open canvas —
        # a read excerpt then anchors on boilerplate and the row stays
        # invisible (live 2026-09-04: three consecutive turns). The rewrite
        # fires only when the draft carries no identifier token — a COST
        # gate, not a routing decision: when it skips, the planner's query
        # already names the code, so there is nothing for the rewrite to
        # fix and the storage leg stays race-competitive with the canvas
        # co-editor's shorter edit path. On failure the draft passes
        # through and the ingested-copy supplements below still carry the
        # answer.
        if service in _STORAGE_SERVICES:
            if not _product_tokens(query):
                query = await _rewrite_storage_query(
                    llm_service, query, plan.intent or "search", context)
            # Precision net AFTER the rewrite: small planner models still
            # drop the identifier sometimes (live 2026-09-04: the rewrite
            # returned the draft unchanged with the code sitting in
            # history). Appending ≤2 context identifier tokens is not a
            # routing decision — it only adds search terms, so the exact-
            # copy scan can find the row however the models behave.
            extra = _context_identifier_net(context or {}, query)
            if extra:
                logger.info(f"storage query identifier net: {extra!r}")
                query = f"{query} {' '.join(extra)}".strip()
        elif service in _ITEM_SEARCH_SERVICES and not _product_tokens(query):
            # Same net for live item searches: the API matches whole name
            # tokens, so the draft must carry the model code, not a generic
            # noun. ZohoInventoryService.search_items retries the enriched
            # query per token, so appending (not replacing) is safe here.
            extra = _context_identifier_net(context or {}, query)
            if extra:
                logger.info(f"item-search query identifier net: {extra!r}")
                query = f"{query} {' '.join(extra)}".strip()

        intent_map = _INTENT_ACTIONS.get(service, _INTENT_ACTIONS["default"])
        action = intent_map.get(plan.intent or "search", "search")
        svc = UniversalIntegrationService(workspace_id="default")
        if (
            (plan.intent or "search") == "search"
            and action == "search"
            and service in SEARCHABLE_SERVICES
        ):
            result = await svc.search(
                service,
                query,
                context={
                    "user_id": user_id,
                    "workspace_id": "default",
                    "tenant_id": tenant_id,
                    # The acting agent — tool-error signals attach to its
                    # running execution so episodes see them.
                    "agent_id": (context or {}).get("agent_id"),
                },
            )
        else:
            result = await svc.execute(
                service,
                action,
                {"query": query, "limit": 8},
                context={
                    "user_id": user_id,
                    "workspace_id": "default",
                    "tenant_id": tenant_id,
                    "agent_id": (context or {}).get("agent_id"),
                    # The read leg's dataset fast path probes the conversation's
                    # own identifier codes ('WG-350DSAV' sat in earlier turns)
                    # — harness-side, where the reply model's no-tool-calling
                    # contract is never violated.
                    "history_texts": [
                        str(h.get("message") or "")[:500]
                        for h in ((context or {}).get("history") or [])
                        if isinstance(h, dict) and h.get("message")
                    ][-6:],
                    "llm_service": llm_service,
                },
            )
        data = result.get("data") if isinstance(result, dict) else None
        if result.get("status") != "success" or not data:
            reason = str(result.get("error") or result.get("message") or "no data")
            if reason.startswith("Routed to "):
                # The family handler's fall-through envelope: NOTHING ran
                # for this action. "Routed to ..." reads like a call happened
                # — exactly the ambiguity the model turned into "I searched
                # Zoho Inventory".
                reason = f"{service}.{action} has no live implementation"
            reason = reason[:160]
            # Communication services: the DETERMINISTIC ingested mailbox is
            # the first second source, ahead of the semantic leg — the whole
            # jschulz lesson was that semantic/free-text search misses
            # addresses while the comms store holds exact sender/recipient
            # copies (generalized from the outlook leg, live 2026-09-06).
            if service in _COMMUNICATION_SERVICES:
                mail_lines = await _ingested_mailbox_lines(user_id, query, context)
                if mail_lines:
                    styled_section = _styled_base_section(
                        _latest_styled_ingested(
                            user_id, _candidate_addresses(user_id, query, context)
                        )
                    )
                    return _with_grounding(
                        f"LIVE TOOL RESULTS ({service}.{action}, query='{query}'): "
                        f"the live {service} search returned nothing usable "
                        f"({reason}). INGESTED MAILBOX matches (deterministic "
                        f"sender/recipient lookup over the workspace's own "
                        f"copies):\n" + "\n".join(mail_lines)
                        + styled_section
                    )
                # Store has nothing either: an empty SUCCESS from an
                # AND-semantics provider is usually one common token zeroing
                # the query — retry the rarest terms individually before
                # falling through to semantic memory (outlook's per-term
                # technique, bounded).
                if result.get("status") == "success":
                    per_term = await _comm_per_term_retry(
                        svc, service, action, query, user_id, tenant_id, context,
                    )
                    if per_term:
                        return per_term
            # Empty live search is precisely where the model declares "I
            # don't have that file" about content that IS stored — the
            # ingested workspace indexes copies of these files and every
            # email. Second source instead of a dead end (live 2026-09-03:
            # price-book question routed to zoho_workdrive.search, which
            # crashed on a missing service method, while the workbook sat
            # fully ingested).
            mem_block = await _memory_search_block(user_id, query, context)
            if mem_block:
                return (
                    f"LIVE TOOL RESULTS ({service}.{action}, query='{query}'): "
                    f"the live {service} search returned nothing usable "
                    f"({reason}). Ingested-workspace matches:\n{mem_block}"
                )
            return _with_grounding(
                f"LIVE TOOL RESULTS ({service}.{action}, query='{query}'): "
                f"returned nothing usable ({reason})."
            )
        if action == "read_file" and isinstance(data, dict):
            # The file was OPENED — render the excerpt as first-class
            # evidence rather than str(dict) noise. found=False /
            # download-failure envelopes fall through to the generic path.
            if data.get("found"):
                ingested_note = (
                    "now ingested into the workspace for full-text search"
                    if data.get("ingested_into_workspace") else
                    "ingest into the workspace was skipped this run"
                )
                block = (
                    f"LIVE TOOL RESULTS ({service}.{action}, query='{query}') — "
                    f"FILE OPENED: {data.get('file_name')} "
                    f"({data.get('chars_extracted', '?')} chars extracted, "
                    f"{ingested_note}).\n"
                    f"EXCERPT around the query:\n{data.get('excerpt', '')}\n"
                    f"{data.get('note', '')}"
                )
                return _with_grounding(block)
        header = (
            f"LIVE TOOL RESULTS ({service}.{action}, query='{query}') — "
            f"use these to answer:\n{str(data)[:2500]}"
        )
        if service in _STORAGE_SERVICES and (
            (plan.intent or "search") == "search" or action == "read_file"
        ):
            # A storage search returns file RECORDS (name/id/size) — metadata
            # can never answer "what does the file say", yet the model treats
            # it as the whole truth and replies "I found the file but can't
            # read its contents" (live 2026-09-04: Consolidated Price List
            # 2019.xlsx confirmed on WorkDrive while its WG350DSAV row sat
            # fully extracted in the ingested copy one routing decision away).
            # Supplement with the ingested-workspace search — the same
            # second-source pattern the outlook branch uses for mailbox
            # copies. A successful read_file returned above, so reaching this
            # with a read intent means the open FAILED (not found / download
            # / extraction) — same dead-end class, same second source. Files
            # with no ingested copy still surface as plain metadata hits.
            mem_block = await _memory_search_block(user_id, query, context)
            if mem_block:
                return _with_grounding(
                    f"{header}\n\nThe results above are METADATA only — file "
                    f"records, not contents. INGESTED COPY, full-text search "
                    f"over the workspace's own extracted file contents "
                    f"(authoritative for what the files SAY):\n{mem_block}"
                )
        if service in _COMMUNICATION_SERVICES or _haystack_has_address(query, context):
            # Same anchoring lesson as the outlook leg: a live mailbox/chat
            # search "succeeds" with whatever the provider's relevance
            # ranking surfaced — often unrelated traffic — and the reply
            # model echoes the first lines it reads. Deterministic ingested
            # matches LEAD the block; the live payload follows as
            # supplemental. Also fires for ANY service when the conversation
            # carries an address: the ingested thread copies are the
            # authoritative record for that participant regardless of which
            # app the planner picked.
            mail_lines = await _ingested_mailbox_lines(user_id, query, context, cap=4)
            if mail_lines:
                styled_section = _styled_base_section(
                    _latest_styled_ingested(
                        user_id, _candidate_addresses(user_id, query, context)
                    )
                )
                return _with_grounding(
                    f"LIVE TOOL RESULTS ({service}.{action}, query='{query}') — "
                    f"INGESTED MAILBOX matches first (deterministic "
                    f"sender/recipient lookup; authoritative for threads):\n"
                    + "\n".join(mail_lines)
                    + f"\n\nLive {service} results (supplemental — provider "
                    f"relevance ranking, known to miss sender addresses):\n"
                    f"{str(data)[:1800]}"
                    + styled_section
                )
        return _with_grounding(header)
    except Exception as e:
        logger.warning(f"tool execution failed for {service}.{plan.intent}: {e}")
        return None
