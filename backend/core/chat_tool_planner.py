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

import datetime as _dt_module
import asyncio
import logging
import re
from pathlib import Path
import os
from typing import Any, Dict, List, Optional, Tuple

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
# own dedicated leg). Defined HERE, ahead of the derived sets below: a
# ``_LOCAL_STORE_SERVICES`` built from ``_COMMUNICATION_SERVICES`` before the
# tuple existed raised NameError at import and took the whole planner down.
_COMMUNICATION_SERVICES = (
    "gmail", "slack", "teams", "discord", "google_chat", "telegram",
    "whatsapp", "zoho_mail",
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
# (Tuple defined above, before _LOCAL_STORE_SERVICES derives from it.)
# Mailbox providers that support the on-demand `ingest` intent (pull a
# message's body + attachments from the integration INTO memory).
_MAILBOX_SERVICES = ("outlook", "gmail")


# Where QUOTED content can live locally: the correspondence/file stores.
# The provenance floor only ever diverts a live record-app plan into these.
_LOCAL_STORE_SERVICES = frozenset(
    {"memory", "documents", "datasets", "outlook", "gmail"}
    | set(_STORAGE_SERVICES)
    | set(_COMMUNICATION_SERVICES)
)

# Services with no upstream integration to pull FROM: the platform web tools
# and the local memory/dataset stores. Any other service supports `ingest`.
_INGEST_EXCLUDED_SERVICES = frozenset(
    {"web_search", "web_fetch", "memory", "datasets", "documents"}
)
# Distinguishes "kill switch" from "autonomy gate" in ingest-core results so
# each block can keep its original user-facing wording.
_INGEST_DISABLED_REASON = "__ingest_disabled__"


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
    "outlook": "email mailbox — correspondence with customers/dealers/suppliers: search messages by name, subject, company, keyword (top hits return with FULL bodies); `read` intent pulls FULL message bodies incl. quoted/forwarded threads when previews are cut off; `ingest` intent pulls a named message's body AND attachments into memory when they are not there yet (PDF/DOCX text; images OCR'd, textless photos described)",
    "gmail": "email mailbox — search messages; `ingest` intent pulls a message's body + attachments into memory on demand",
    "slack": "team chat — search messages and channels",
    "teams": "team chat — search messages",
    "discord": "community chat — search messages",
    "telegram": "messenger — search messages",
    "zoho_crm": "CRM — search leads, contacts, deals, accounts",
    "zoho_inventory": "YOUR OWN warehouse records — item quantities on hand in the inventory app, searched by exact model code ('WG-350DSAV', one code as the whole query — Zoho matches whole words only). A vendor's/dealer's price or availability inside THEIR email is their offer — find the message (memory/outlook), not here",
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
    # Knowledge VFS: the agent's file-system view over everything ingestion
    # stored. The lane that makes the grounding rule's 'full: …' citations
    # executable — open the COMPLETE line-numbered message behind a
    # truncated excerpt, or regex-search every stored email/file.
    "documents": "workspace files & FULL email threads — `cat` intent: query is the VFS path cited on evidence lines ('full: knowledge/conversations/<id>/content.lines') and returns the COMPLETE line-numbered message; `grep` intent: query is an exact string/regex ('5,350', 'F-5216'), optionally ' … in knowledge/conversations', scanning EVERY stored message and file; `head`/`tail`/`ls` skim. Use when a search excerpt is truncated or a value hides mid-thread; for open questions prefer memory/datasets",
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
    "if read from the source. "
    "BEFORE concluding anything is missing: mailbox/document lines are "
    "EXCERPTS and long quoted threads run to tens of thousands of chars. "
    "Every [ingested mailbox] line carries "
    "'full: knowledge/conversations/<id>' — the COMPLETE line-numbered "
    "message. Open it with documents.cat(path + '/content.lines') (skim with "
    "documents.head / documents.tail); to search EVERY stored message use "
    "documents.grep with path_prefix 'knowledge/conversations'. Only after "
    "that may you say a value is not in the mailbox."
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
    # Knowledge VFS (documents.cat/grep over complete stored threads): the
    # planner can only offer what the catalog lists — without this entry the
    # grounding rule's 'open it with documents.cat' advice was a dead end
    # (no service, no lane). Cheap env-flag check only.
    if "documents" not in services:
        try:
            from core.knowledge_vfs_config import knowledge_vfs_enabled

            if knowledge_vfs_enabled():
                services.append("documents")
        except Exception:  # noqa: BLE001 — catalog entry is best-effort
            pass
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
- Read-only EXCEPT the `ingest` intent: search/list intents for
  lookups; `read` intent ONLY for the
  file-storage services, when the user wants a specific row, value, price,
  figure or section OUT OF a named document ("open the catalog and find the
  ABC-1234 row" → read; "what files do I have about X" → search — search
  returns only file names/metadata and can never answer what a file SAYS),
  and for the outlook mailbox, when a search's snippets cut off a quoted or
  forwarded thread ("open that email, get the full thread below the
  signature" → outlook read — its search already carries full bodies for
  the top hits; read extends that to the rest and to longer bodies).
  For the `documents` service, OPENING a cited thread/message is intent
  `cat` with the cited VFS path as the whole query
  ('knowledge/conversations/<id>/content.lines' — the 'full:' path from an
  evidence line or a grep hit); `grep` is for FINDING messages by exact
  string, not for opening one already cited.
  A message that only says WHERE the file lives ("it's an excel file in
  WorkDrive") after a content request is still a READ — the earlier turns
  own the what-for ("check X for the price"), this message adds the where;
  planning search again just re-lists the file name the user already named.
- NEVER plan sends, deletes, or edits. The ONE exception is the `ingest`
  intent, valid for ANY connected integration: it pulls content that is NOT
  already in memory from the integration INTO the workspace's own memory and
  is idempotent (a repeat ask is a no-op). Use it before ever telling the user
  that content is inaccessible. What it pulls depends on the service: mailbox
  (outlook/gmail) → the message body AND attachments (images OCR'd); file
  storage → the file's contents; record apps (CRM, Books, Inventory, support,
  tickets, project trackers, …) → the matching record's fields rendered to
  searchable text. Query = the identifying terms (sender/subject, file name,
  model code, person/company) or the exact provider id when one is known.
  Never plan `ingest` for web_search/web_fetch/memory/datasets — they have no
  upstream to pull from.
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
- PROVENANCE BEATS WORDING. When a PROVENANCE block is present it was
  resolved from the workspace's own ingested stores BEFORE this call: if it
  says the ingested mail contains the token, the text is a message the
  workspace already received — plan "memory" (or "outlook" for the live
  mailbox) for it even when the wording sounds like inventory/stock/CRM. A
  token listed as present in the DATASET CATALOG belongs to a spreadsheet.
  Only when the block names neither may you route on wording alone.
- PASTED / QUOTED TEXT IS MAIL, NOT A CATALOG QUERY. When the message
  quotes a line the user read somewhere (a price, an offer, a discount, a
  term — often pasted verbatim and prefixed with "search for this one:",
  "find this:", "this one:"), the artefact is an ingested MESSAGE and the
  answer is in the mailbox, not in a stock/inventory/CRM/web index. Route
  to "memory" (which searches every ingested message, email and record)
  with the quoted line's distinctive terms — NOT to zoho_inventory, a CRM,
  or the web, even when the quote contains the word "stock": "in stock"
  inside a vendor's quoted line describes THEIR offer, not your warehouse.
  Only plan inventory when the question is about QUANTITIES ON HAND in the
  inventory app for an item the user named as such. Getting this wrong is
  expensive: a live lookup against the wrong system returns nothing (or
  times out) and the user is told their own quote cannot be found.
- INTERNAL RECORDS vs CORRESPONDENCE — WHOSE data: the record apps
  (inventory, books/invoices, CRM) hold YOUR OWN company's state —
  quantities on hand of YOUR items, YOUR invoices, YOUR deals. Mailboxes
  and memory hold messages OTHERS sent you (customers, dealers,
  suppliers): their quotes, offers, availability claims. A price,
  discount, "in stock" or lead time inside a message is the SENDER's
  claim about THEIR offer — plan the message lookup (memory/outlook).
  Plan a record app only for YOUR OWN state.
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
  say which integration is missing in `reason`.
- DATE EXTRACTION: when the user's latest message states WHEN something was
  sent, received or happened ("sent 9/11 friday", "the august 26 quote",
  "yesterday's email"), set mentioned_date to that date as YYYY-MM-DD,
  resolved against TODAY (weekdays = the most recent past one). Omit the
  field when no date is stated or resolvable. Never invent one."""

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
    # Date PIGGYBACK (2026-09-15): the planner reads the same message the
    # date parser does — let it resolve messy relative expressions the
    # regex cannot ('end of last month', 'two Tuesdays ago') at zero extra
    # call cost. Optional by contract: absent/unparseable -> the regex
    # parser and then plain recency, exactly as before this field existed.
    mentioned_date: Optional[str] = None

    @field_validator("mentioned_date", mode="before")
    @classmethod
    def _normalize_mentioned_date(cls, v: Any) -> Optional[str]:
        # Lenient ISO coercion: models emit '2026-09-11', '9/11/2026' or
        # bare '9/11' (resolved to the current year, last year if that
        # lands in the future). Prose ('september 11') drops silently —
        # the prompt asks for YYYY-MM-DD.
        if v is None:
            return None
        import datetime as _dt

        s = str(v).strip()
        if not s:
            return None
        s = s.replace("/", "-")
        try:
            return _dt.date.fromisoformat(s[:10]).isoformat()
        except ValueError:
            pass
        parts = s.split("-")
        try:
            if len(parts) == 3:
                if len(parts[0]) == 4:  # YYYY-MM-DD
                    day = _dt.date(int(parts[0]), int(parts[1]), int(parts[2]))
                else:  # MM-DD-YYYY ('9/11/2026')
                    day = _dt.date(
                        int(parts[2]), int(parts[0]), int(parts[1]))
            elif len(parts) == 2:
                today = _dt.date.today()
                day = _dt.date(today.year, int(parts[0]), int(parts[1]))
                if day > today:
                    day = day.replace(year=day.year - 1)
            else:
                return None
        except ValueError:
            return None
        return day.isoformat()

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


#: How much of the open canvas rides along on the planner prompt. The planner
#: only needs to recognise WHAT KIND of artefact is open and who/what it is
#: about — not read it. Hard-capped so a 30 KB canvas body cannot bloat the
#: cheap planning call or push the catalog out of a small model's window.
_PLANNER_CANVAS_CHARS = int(os.getenv("ATOM_PLANNER_CANVAS_CHARS", "700") or 700)


def _planner_canvas_block(canvas: Optional[Dict[str, Any]]) -> str:
    """A SHORT description of the open canvas for the planner prompt.

    Live 2026-09-14 (canvas ``a1a13834…``): the user pasted a line out of a
    vendor email and the planner routed it to ``zoho_inventory`` — because the
    quote contains the word "stock" — while the email it came from was OPEN in
    the panel beside the chat. The reply model has always received a canvas
    block; the PLANNER never did, so it chose a tool without knowing that the
    thing being discussed was a mail thread. This closes that gap.

    Deliberately tiny and structural: type, title, subject, participants and a
    truncated body head — enough to answer "is this an email/mail question?",
    never enough to answer the question from the prompt instead of the tools.
    Empty string when there is no canvas."""
    if not isinstance(canvas, dict):
        return ""
    kind = str(canvas.get("canvas_type") or canvas.get("type") or "").strip()
    title = str(canvas.get("title") or canvas.get("name") or "").strip()
    content = canvas.get("content")
    bits: List[str] = []
    if kind:
        bits.append(f"type: {kind}")
    if title:
        bits.append(f"title: {title[:160]}")
    if isinstance(content, dict):
        for key in ("to", "from", "sender", "cc", "subject"):
            val = str(content.get(key) or "").strip()
            if val:
                bits.append(f"{key}: {val[:160]}")
        body = str(content.get("body") or content.get("content") or "")
        body = re.sub(r"\s+", " ", re.sub(r"<[^>]{0,200}>", " ", body)).strip()
        if body:
            bits.append(f"body head: {body[:_PLANNER_CANVAS_CHARS]}")
    elif isinstance(content, str) and content.strip():
        flat = re.sub(r"\s+", " ", content).strip()
        bits.append(f"content head: {flat[:_PLANNER_CANVAS_CHARS]}")
    if not bits:
        return ""
    return (
        "Open canvas (what the user is looking at RIGHT NOW — \"this one\", "
        "\"the draft\", \"the email\", \"this quote\" refer to THIS):\n  "
        + "\n  ".join(bits)
    )


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
    canvas: Optional[Dict[str, Any]] = None,
    provenance: str = "",
) -> Optional[ToolPlan]:
    """Decide (via cheap structured LLM output) whether this turn needs live
    integration data, and which connected service to query. Returns None on
    any failure — the caller then simply runs without a tool block.

    ``canvas`` is the open canvas (bounded — see ``_planner_canvas_block``).
    Routing without it was the 2026-09-14 mis-route: a line pasted out of an
    OPEN email was planned into the inventory app because nothing told the
    planner a mail thread was on screen."""
    if llm_service is None:
        return None
    connected = get_connected_services(user_id)
    catalog = _catalog_line(connected)
    canvas_block = _planner_canvas_block(canvas)
    prompt = (
        f"{_PLANNER_SYSTEM}\n\n"
        f"TODAY IS {_dt_module.date.today().isoformat()}.\n"
        f"Available tools:\n{catalog}\n\n"
        + (f"{canvas_block}\n\n" if canvas_block else "")
        + (f"{provenance}\n\n" if provenance else "")
        + f"Recent conversation:\n{_history_transcript(history, message)}\n\n"
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
                llm_service, defect, connected, catalog, history, message, canvas)
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
        # `ingest` (pull content that is NOT in memory yet from the
        # integration) is valid for EVERY connected integration — the platform
        # web tools and the local memory/dataset stores have no upstream.
        if plan.service not in _INGEST_EXCLUDED_SERVICES:
            allowed_intents.add("ingest")
        if plan.intent not in allowed_intents:
            plan.intent = "search"
        if not (plan.query or "").strip():
            plan.query = message[:120]
        # PROVENANCE FLOOR (the obedience rung, mirrors the explicit-
        # web-research floor): a QUOTE-LOOKUP message whose quoted wording
        # verifiably lives in the ingested mail must not be planned into a
        # live record app — the artifact is a stored message. One repair
        # pass with the provenance fact; only if the model still insists
        # on the record app does the deterministic memory rung fire.
        # Narrow by construction: no provenance match, or no quote-lookup
        # shape ("is WG-350DSAV in stock?" — a genuine stock question —
        # matches neither condition), and the plan passes untouched.
        if (
            provenance
            and "INGESTED MAIL contains" in provenance
            and _quote_lookup_shape(message)
            and plan.service
            and plan.service not in _LOCAL_STORE_SERVICES
        ):
            defect = (
                "the user's message quotes content that verifiably lives in "
                "the workspace's ingested mail (the PROVENANCE block names "
                "the messages). A quoted line is a stored MESSAGE the "
                f"workspace received — not a {plan.service} record. Re-plan "
                "as a memory (or outlook) search whose query is the quoted "
                "line's distinctive terms."
            )
            repaired = await _repair_plan_via_llm(
                llm_service, defect, connected, catalog, history, message)
            if repaired and repaired.use_tool and (
                    not repaired.service
                    or repaired.service in _LOCAL_STORE_SERVICES):
                logger.info(
                    f"tool planner: provenance repair -> "
                    f"{repaired.service}.{repaired.intent}")
                plan = repaired
            else:
                terms = (
                    _quoted_content_phrases(message)
                    or _distinctive_figure_phrases(message)
                )
                logger.info(
                    "tool planner: provenance floor -> memory.search "
                    f"(planned {plan.service!r} for a quoted-mail lookup)")
                plan.service, plan.intent = "memory", "search"
                plan.query = (terms[0] if terms else message[:120])
                plan.reason = "provenance floor: quoted wording lives in ingested mail"
    return plan


def _current_message_text(context: Optional[Dict[str, Any]]) -> str:
    """The user's current message. The explicit context ``message`` when the
    caller threaded it — both executor entry points build the context BEFORE
    this turn lands in any history (session history is written after the
    response), so the tail alone cannot see the current ask. Otherwise the
    most recent user entry from the history tail: role-shaped hydrated
    entries, or session-shaped ``{message, response}`` entries via the
    message side only — the response is the assistant's echo (same rule as
    _latest_user_figure_phrases). Empty when nothing is available."""
    ctx = context or {}
    msg = str(ctx.get("message") or "").strip()
    if msg:
        return msg
    for entry in reversed(ctx.get("history") or []):
        if not isinstance(entry, dict):
            continue
        role = str(entry.get("role") or "").lower()
        if role and role != "user":
            continue
        if role == "user":
            return _entry_text(entry)
        if "message" in entry:
            return str(entry.get("message") or "")
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


def _context_identifier_net(ctx: Dict[str, Any], query: str, limit: int = 2,
                            skip_pathlike: bool = False) -> List[str]:
    """Identifier tokens (model/SKU-shaped — _product_tokens) that the
    current message, recent history and open canvas carry but the draft
    query dropped. Shared by the storage and item-search query nets: small
    planner models drop codes that live in earlier turns (live 2026-09-04:
    the user named the exact keywords and the planner still sent
    'bandsaw' three turns running). Order-preserving, capped.
    ``skip_pathlike`` for LIVE item searches: URL-path 'identifiers' are
    never catalog codes (see _product_tokens) and can push the query past
    provider value caps; storage searches keep them — a URL IS searchable
    document text."""
    hay = " ".join(
        [_current_message_text(ctx)]
        + [_entry_text(m) for m in (ctx.get("history") or [])[-8:]]
        + [_entry_text(ctx.get("canvas") or {})]
    )
    return [
        t for t in _product_tokens(
            hay, min_len=6, skip_hexlike=True, skip_pathlike=skip_pathlike)
        if t.lower() not in (query or "").lower()
    ][:limit]


#: Bare years are not identifiers on their own.
_YEAR_RE = re.compile(r"(?:19|20)\d{2}")


def _mailbox_code_tokens(text: str, limit: int = 4) -> List[str]:
    """Codes a mailbox search should try, including the shapes the shared
    ``_product_tokens`` deliberately ignores.

    ``_product_tokens`` requires 5+ chars AND a letter, so it misses the codes
    this workspace actually files threads under: '52T' (3 chars) and '81020'
    (digits only, a Tennsmith order number). Live 2026-09-14 a question about
    the foot-shear list price could not reach a thread whose only identifiers
    were exactly those.

    Shape here: any token with at least one digit and at least one LETTER OR
    two digits ('52T', '81020', 'F-5216'), minimum two characters. Rejected:
    bare years, and digits-only tokens that are phone-shaped once separators
    are removed (the NANP screen `_is_phone_shaped` uses, which the figure
    tokenizer already relies on). Identity-shaped tokens are data-driven, so
    this does not need to know any product vocabulary."""
    out: List[str] = []
    seen: set = set()
    for tok in re.findall(r"[A-Za-z0-9][A-Za-z0-9_/-]*", text or ""):
        t = tok.strip("-_/")
        low = t.lower()
        if len(t) < 2 or low in seen:
            continue
        digits = sum(ch.isdigit() for ch in t)
        if not digits:
            continue
        if _YEAR_RE.fullmatch(t):
            continue
        stripped = re.sub(r"\D", "", t)
        if not re.search(r"[A-Za-z]", t) and len(stripped) in (10, 11):
            continue  # phone-shaped, not a code
        seen.add(low)
        out.append(t)
        if len(out) >= limit:
            break
    return out


def _code_boundary_hits(
    rows: List[Dict[str, Any]], tokens: List[str], limit: int = 3
) -> List[Dict[str, Any]]:
    """Comms rows containing a CODE token as a whole word.

    Live 2026-09-14: "check the email thread chandrakant forwarded to me about
    how list price was calculated for the foot shear" found nothing — the
    user's phrasing ("list price calculated") and the thread's wording
    ("cost", "$8,880", "52T", "81020") share almost no surface terms, and the
    thread's subject is "Re: Brake, Shear and Lock Former." The identifier
    ladder already solved this for storage/item searches; the mailbox lane had
    no equivalent, so a question asked in conceptual words could not reach a
    thread filed under catalogue codes.

    Index-built and boundary-anchored: alphanumeric runs are compared exactly
    against the token (so '81020' does not match inside '810200'), and a token
    matches a run either as written or with separators removed — the store
    holds both 'WG-350DSAV' and 'WG350DSAV' spellings of the same code.
    Newest-first; rows without an id are skipped (they cannot be cited)."""
    wanted = []
    for t in tokens or []:
        tok = str(t or "").strip().upper()
        # Two characters is enough for a code ('52T'); the CALLER decides what
        # is identifier-shaped (see _mailbox_code_tokens) — a second length
        # floor here silently dropped exactly the short codes this leg exists
        # for.
        if len(_canonical_fig_text(tok)) < 2:
            continue
        wanted.append((tok, tok.replace("-", "").replace(" ", "")))
    if not wanted:
        return []
    hits: List[Dict[str, Any]] = []
    for row in rows:
        blob = f"{row.get('subject') or ''} {row.get('content') or ''}".upper()
        runs = {
            r.replace("-", "").replace(" ", "")
            for r in re.findall(r"[A-Z0-9][A-Z0-9\- ]{2,}", blob)
        }
        runs |= set(re.findall(r"[A-Z0-9]+", blob))
        if any(plain in runs or raw in runs for raw, plain in wanted):
            hits.append(row)
    hits.sort(key=lambda r: str(r.get("timestamp") or ""), reverse=True)
    return hits[:limit]


async def _mailbox_code_lines(
    user_id, query: str, context: Optional[Dict[str, Any]], limit: int = 3
) -> List[str]:
    """Mailbox evidence for the CODES a turn is about, even when the user's
    words and the stored message share no terms.

    Two sources of tokens, both deterministic (no LLM, no embeddings):
    codes named in the query itself, plus codes the conversation/canvas
    carries that the query dropped — the classic "it refers to something
    named three turns ago" case. The scan runs off-loop; [] on anything."""
    try:
        codes = _mailbox_code_tokens(query or "", limit=4)
    except Exception:
        codes = []
    # Codes the CONVERSATION carries (the user rarely repeats them): scanned
    # with the same broader shape, because the shared identifier net requires
    # 5+ chars and misses '52T'/'81020' — the exact codes this workspace files
    # its foot-shear threads under.
    try:
        ctx_texts = [
            str((m or {}).get("message") or "")
            for m in ((context or {}).get("history") or [])[-6:]
            if isinstance(m, dict)
        ]
        ctx_texts.append(_entry_text((context or {}).get("canvas") or {}))
        codes += _mailbox_code_tokens(" ".join(ctx_texts), limit=3)
    except Exception:
        pass
    # De-dup, order-preserving, and drop codes already present in the query
    seen: set = set()
    ordered: List[str] = []
    for c in codes:
        lc = str(c).lower()
        if lc and lc not in seen:
            seen.add(lc)
            ordered.append(str(c))
    if not ordered:
        return []
    try:
        rows = await asyncio.to_thread(
            lambda: _code_boundary_hits(_comms_store_records(), ordered, limit=limit)
        )
    except Exception as e:  # noqa: BLE001
        logger.debug(f"mailbox code scan skipped: {e}")
        return []
    out: List[str] = []
    for i, row in enumerate(rows):
        if not row.get("id"):
            continue
        out.append(
            _ingested_line_from_row(
                row,
                with_body=i < _INGESTED_BODY_LINES,
                body_cap=(
                    _INGESTED_BODY_CAP_FULL if i < _INGESTED_FULL_LINES else None
                ),
            )
        )
    if out:
        logger.info(
            "mailbox code scan: %d line(s) for codes %s", len(out), ordered[:3]
        )
    return out


#: Words too generic to signal relevance when comparing a request to a
#: subject line (query verbs, articles, the meta-language of asking).
_RANK_STOPWORDS = frozenset({
    "email", "emails", "thread", "threads", "check", "find", "search", "show",
    "tell", "give", "need", "want", "about", "from", "that", "this", "with",
    "what", "when", "where", "which", "have", "has", "had", "does", "did",
    "list", "price", "prices", "cost", "quote", "quoted", "calculation",
    "calculated", "calculate", "forwarded", "forward", "sent", "send",
    "please", "could", "would", "should", "there", "their", "your", "yours",
    "mine", "ours", "into", "over", "under", "more", "most", "some", "any",
})


def _rank_address_hits(
    rows: List[Dict[str, Any]],
    addr_l: str,
    limit: int = 4,
    query: str = "",
) -> List[Dict[str, Any]]:
    """Rank raw comms rows matching an address.

    Tiers, strongest first: (1) the row is a participant AND its SUBJECT
    shares a term with the user's request, (2) participant, (3) body-only
    mention. Newest first within a tier. Rows arrive in table (insertion)
    order, not relevance: with a thread's key messages ingested late, a
    first-N cap surfaced lead forms and internal chatter while the actual
    reply sat near the end of the table (live 2026-09-06: jschulz@blumetric.ca
    — Jacob's reply and the sent quote never made the cap).

    The subject-overlap tier is the 2026-09-14 fix: a NAMED participant
    resolves to one address, but that address holds hundreds of unrelated
    messages, so "newest N" returned the six latest while the thread the user
    described ("list price … foot shear") sat below the cap. A term the user
    used that the SUBJECT also uses is the cheapest reliable relevance signal
    — and subject-only, so a common word buried in a long quoted body cannot
    promote noise. Exact duplicate rows (re-ingested copies) collapse to one
    so they don't burn cap slots."""
    seen_keys = set()
    scored = []
    q_terms = {
        t for t in re.findall(r"[a-z0-9]{4,}", (query or "").lower())
        if t not in _RANK_STOPWORDS
    }
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
        # MATCH IN THE IDENTITY COLUMNS AND THE PLAIN BODY — the only places
        # the address is the message's own text. The stored ``metadata`` holds
        # the full original HTML (median 48 KB, max 35 MB/row) and lowercasing
        # it for every row was pure cost: measured on the live store, every
        # one of the 3,777 rows whose metadata contains the address ALSO
        # contains it in sender/recipient/content, so the clause changed no
        # result. ``content`` keeps quoted-body mentions (a reply that names
        # the person without being addressed to them), which the tagger
        # already scores below true participants.
        participant = addr_l in sender.lower() or addr_l in recipient.lower()
        if not participant and addr_l not in content.lower():
            continue
        seen_keys.add(key)
        subject_hit = bool(
            q_terms & set(re.findall(r"[a-z0-9]{4,}", subj.lower()))
        )
        if participant and subject_hit:
            tier = 0
        elif participant:
            tier = 1
        else:
            tier = 2
        scored.append((tier, ts, row))
    # Two stable sorts: newest first overall, then tier wins.
    scored.sort(key=lambda t: t[1], reverse=True)
    scored.sort(key=lambda t: t[0])
    return [t[2] for t in scored[:limit]]


# ---------------------------------------------------------------------------
# PROVENANCE MENU — which ingested store already CONTAINS the token the user
# quoted, resolved BEFORE the planner chooses a tool.
#
# Live 2026-09-14 (canvas a1a13834…): the user pasted a line out of a vendor
# email — "search for this one: $ 5,350.00 - 10 % in stock" — and the planner
# sent it to the inventory app, because "in stock" is the only phrase in the
# tool catalog that mentions stock. Nothing in the planner's inputs said the
# text CAME FROM a message the workspace already held: routing was decided
# from wording alone.
#
# The generalizable fix is provenance, not another keyword rule — the ingested
# store itself is proof of where a quoted token lives.
# ---------------------------------------------------------------------------


def _canon_keys(phrases: List[str]) -> List[str]:
    """Canonical digit keys for the matcher's pre-gate.

    The gate MUST be broader than the canonical pass or it silently drops real
    matches (measured: '5,350.00' vs '5.350,00' — canonicalized both are
    '535000', but neither decorated spelling appears in the other's raw text).
    So the gate compares CANONICALIZED text against the SAME canonical key the
    pass searches for: ``_canonical_fig_text('5,350.00') == '535000'`` and
    ``_canon_find`` looks for exactly that inside the canonicalized field.
    Broader-or-equal by construction."""
    out: List[str] = []
    for p in phrases or []:
        canon = _canonical_fig_text(p)
        if len(canon) >= 4 and canon not in out:
            out.append(canon)
    return out


def _probe_variants(phrases: List[str]) -> List[str]:
    """Decorated (raw-text) spellings of each phrase for the matcher's
    containment pre-gate: as written, dot-for-comma, comma-for-space, and
    fully stripped (the ungrouped form is what the canonical fallback matches
    inside a body rendering the digits without separators).

    Raw spellings only — NOT the canonical digit form, which is covered by
    ``_canon_keys`` and is deliberately kept separate so each probe can be
    reasoned about: these keys are what actually appears in a body."""
    out: List[str] = []
    for phrase in phrases or []:
        for cand in (
            phrase,
            phrase.replace(".", ","),
            phrase.replace(",", " "),
            phrase.replace(",", "").replace(" ", ""),
            _canonical_fig_text(phrase),
        ):
            c = cand.strip()
            if len(_canonical_fig_text(c)) >= 4 and c not in out:
                out.append(c)
    return out


def _token_probe_keys(tokens: List[str]) -> List[str]:
    """Keys that identify a token at any realistic rendering, WITHOUT the
    false-positive flood of a short digit run.

    A bare '350' (the longest digit group of '5,350.00') matched 462 of 7,149
    live messages — zip codes, tracking numbers, quantities — which is useless
    as provenance. The canonical digit string ('535000') is exact for the
    amount's digits but misses every grouped rendering, so the keys are the
    canonical form PLUS the token's decorated spellings:

        '5,350.00' -> {'535000', '5,350.00', '5.350,00', '5 350,00'}

    Measured on the live store: 6 messages in 0.03s (subject+content), versus
    462 for the digit-run key. Callers keep the exact matcher as the
    authority — these keys only decide where to look first."""
    keys: List[str] = []
    for token in tokens or []:
        canon = _canonical_fig_text(token)
        if len(canon) < 4:
            continue
        if canon not in keys:
            keys.append(canon)
        for decorated in (
            token,
            token.replace(".", ","),
            token.replace(",", " "),
            token.replace(",", "").replace(" ", ""),
        ):
            d = decorated.strip()
            if len(_canonical_fig_text(d)) >= 4 and d not in keys:
                keys.append(d)
    return keys


def _mail_contains_tokens(tokens: List[str]) -> List[Dict[str, Any]]:
    """Ingested-mail rows that VERIFIABLY contain the tokens.

    Two stages, cheapest first (measured live on 7,149 rows):

    1. CANDIDATES — the canonical digit string plus the token's decorated
       spellings against ``subject``/``content`` (0.03s). A bare digit run is
       deliberately NOT used: '350' matched 462 messages of unrelated noise.
    2. VERIFY — the same exact per-field matcher the evidence line uses
       (``_match_rows_by_figure_tokens``), so a loose substring can never be
       reported as provenance: '535000' is contained in '$53,500.00' but the
       matcher's digit-edge guard rejects it. Only rows in the candidate set
       are verified, so this stays in the low seconds.

    [] when no token is distinctive enough to check — the common case, free."""
    keys = _token_probe_keys(tokens)
    if not keys:
        return []
    try:
        rows = _comms_store_records()
    except Exception:
        return []
    candidates = []
    for row in rows:
        head = f"{row.get('subject') or ''}\n{row.get('content') or ''}"
        if any(k in head for k in keys):
            candidates.append(row)
    if not candidates:
        return []
    return _match_rows_by_figure_tokens(candidates, tokens, limit=50)


def _mail_evidence_summary(rows: List[Dict[str, Any]], limit: int = 2) -> str:
    """Compact who/when/what for the provenance line — identity, not content."""
    ordered = sorted(rows, key=lambda r: str(r.get("timestamp") or ""), reverse=True)
    bits = []
    for row in ordered[:limit]:
        who = str(row.get("sender") or "?")
        subj = str(row.get("subject") or "").strip()[:60]
        when = str(row.get("timestamp") or "")[:10]
        bits.append(f"{who}{(' — ' + subj) if subj else ''} ({when})")
    return "; ".join(bits)


# Quote-lookup shape: the user is asking WHERE a quoted line came from, not
# asking a question of a business app. Combined with verbatim provenance
# (the line lives in stored mail) this is the strongest possible routing
# signal — see _provenance_floor.
_QUOTE_LOOKUP_RE = re.compile(
    r"(?:search|look)\s+(?:for|up)\s+(?:this|that)\s+one\b"
    r"|find\s+(?:this|that|the\s+(?:email|message|quote|line|note))\b"
    r"|the\s+(?:email|message|quote|line|note)\s+that\s+said\b"
    r"|where\s+did\s+(?:this|that|it)\s+come\s+from\b"
    r"|who\s+(?:said|sent|quoted)\s+(?:this|that|it)\b"
    r"|the\s+(?:email|message|quote|line|note)\s+(?:that\s+)?said\b"
    r"|\bthis\s+one\b\s*[:\u2013-]",
    re.IGNORECASE,
)
_QUOTED_SPAN_RE = re.compile("[\"\u201c\u2018]([^\"\u201d\u2019]{8,140})[\"\u201d\u2019]")
_QUOTE_LEAD_RE = re.compile(
    r"^\s*(?:(?:search|look)\s+(?:for|up)\s+(?:this|that)\s+one"
    r"|find\s+(?:this|that|the\s+(?:email|message|quote|line|note))"
    r"|the\s+(?:email|message|quote|line|note)\s+that\s+said"
    r"|where\s+did\s+(?:this|that)\s+come\s+from"
    r"|who\s+(?:said|sent|quoted)\s+(?:this|that))"
    r"(?:\s+that\s+said)?"
    r"\s*[:\u2013-]\s*",
    re.IGNORECASE,
)


def _quote_lookup_shape(message: str) -> bool:
    """True when the message is a find-the-source ask about quoted content."""
    return bool(_QUOTE_LOOKUP_RE.search(message or ""))


def _quoted_content_phrases(message: str, limit: int = 2) -> List[str]:
    """The user's QUOTED wording — quoted spans and referent tails
    ("search for this one: <tail>"). Distinctive multi-word phrases for
    verbatim containment scans; single codes/amounts are the figure
    phrases' job. Empty when the message quotes nothing."""
    text = (message or "").strip()
    if not text:
        return []
    cands: List[str] = []
    for m in _QUOTED_SPAN_RE.finditer(text):
        cands.append(m.group(1))
    tail = _QUOTE_LEAD_RE.sub("", text, count=1)
    if tail and tail != text:
        cands.append(tail.split("\n")[0])
    out: List[str] = []
    for c in cands:
        norm = re.sub(r"\s+", " ", c).strip(" \"'\u201c\u201d,.:;!?")
        # multi-word only: one-word quotes are figures/codes territory
        if len(norm) >= 8 and " " in norm and norm.lower() not in (
                x.lower() for x in out):
            out.append(norm)
        if len(out) >= limit:
            break
    return out


def _mail_contains_phrases(phrases: List[str]) -> List[Dict[str, Any]]:
    """Ingested-mail rows whose subject+content contain a quoted phrase
    VERBATIM (case-insensitive). Same cheap two-column scan as the figure
    probe (0.07s over the live 7k-row store)."""
    needles: List[str] = []
    for phrase in phrases or []:
        norm = re.sub(r"\s+", " ", phrase or "").strip().strip("\"'\u201c\u201d,.:;!?").lower()
        if len(norm) >= 8 and " " in norm and norm not in needles:
            needles.append(norm)
    if not needles:
        return []
    try:
        rows = _comms_store_records()
    except Exception:
        return []
    hits: List[Dict[str, Any]] = []
    for row in rows:
        head = re.sub(
            r"\s+", " ",
            f"{row.get('subject') or ''}\n{row.get('content') or ''}",
        ).lower()
        if any(n in head for n in needles):
            hits.append(row)
    return hits


async def _provenance_menu(
    message: str,
    context: Optional[Dict[str, Any]] = None,
    budget_s: float = 4.0,
) -> str:
    """Which local stores CONTAIN the distinctive tokens of this message.

    Runs before the planner and is rendered into its prompt. Covers the two
    stores that hold answers for pasted values: the ingested mailbox (vendors'
    quotes, offers, terms) and the dataset catalog (spreadsheets). Bounded,
    best-effort, fault-isolated: on timeout or error the menu omits a line, so
    the planner behaves exactly as it did before this existed.

    The wording is deliberately HEDGED — absence here means "not found by this
    cheap check", never "not in the store"."""
    detected: List[str] = []
    try:
        detected.extend(_distinctive_figure_phrases(message))
    except Exception:
        pass
    if not detected:
        # A 'try again' turn usually names the token in a user turn just back.
        try:
            detected.extend(_latest_user_figure_phrases(context or {}))
        except Exception:
            pass
    quoted_phrases: List[str] = []
    try:
        quoted_phrases = _quoted_content_phrases(message)
    except Exception:
        quoted_phrases = []
    if not detected and not quoted_phrases:
        return ""
    lines: List[str] = []
    try:
        mail_rows = await asyncio.to_thread(_mail_contains_tokens, detected)
        if mail_rows:
            lines.append(
                f"- the workspace's INGESTED MAIL contains your quoted text "
                f"({len(mail_rows)} message(s): {_mail_evidence_summary(mail_rows)})"
                f" — this is a MESSAGE that was received"
            )
    except Exception as e:  # noqa: BLE001
        logger.debug(f"provenance mail check skipped: {e}")
    if quoted_phrases:
        # Non-figure quotes ("find the email that said: put 25 percent
        # only") — the figure probe keys on digit runs and misses them.
        try:
            phrase_rows = await asyncio.to_thread(
                _mail_contains_phrases, quoted_phrases)
            if phrase_rows:
                lines.append(
                    f"- the workspace's INGESTED MAIL contains your quoted "
                    f"wording ({len(phrase_rows)} message(s): "
                    f"{_mail_evidence_summary(phrase_rows)})"
                    f" — this is a MESSAGE that was received"
                )
        except Exception as e:  # noqa: BLE001
            logger.debug(f"provenance phrase mail check skipped: {e}")
    try:
        from core.sheet_dataset_service import (
            candidate_probe_tokens,
            search_all_datasets_sync,
            sheet_datasets_enabled,
        )

        probe_tokens = candidate_probe_tokens(detected)
        if sheet_datasets_enabled() and probe_tokens:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    search_all_datasets_sync,
                    " ".join(probe_tokens), None,
                    (context or {}).get("workspace_id"), 1, 200, [],
                ),
                timeout=budget_s,
            )
            hits = (result or {}).get("hits") or []
            matched = (result or {}).get("token")
            if hits and matched:
                files = {
                    str((h or {}).get("file") or (h or {}).get("source") or "?")
                    for h in hits
                }
                lines.append(
                    f"- the DATASET CATALOG (ingested spreadsheets) contains "
                    f"'{matched}' in {len(files)} file(s)"
                )
    except Exception as e:  # noqa: BLE001 — probe is best-effort
        logger.debug(f"provenance dataset check skipped: {e}")
    if not lines:
        return ""
    return (
        "PROVENANCE — resolved from the workspace's OWN ingested stores BEFORE "
        "you plan (tokens checked: " + ", ".join(f"'{t}'" for t in detected[:3]) + "):\n"
        + "\n".join(lines)
        + "\nA token found in the ingested mail is a MESSAGE the workspace "
        "already received: plan a mailbox/memory lookup for it, NOT an "
        "inventory/CRM/web lookup. (This check covers only the stores listed "
        "above; no line means 'not found by this check', never 'not ingested'.)"
    )


def _canonical_with_offsets(s: Any) -> Tuple[str, List[int]]:
    """Separator-insensitive canonical form of ``_canonical_fig_text`` plus
    the raw-string index of every canonical character — so a canonical match
    can be mapped back to a window of the ORIGINAL text (match regions must
    quote the body as stored, not the canonical mush)."""
    chars: List[str] = []
    offs: List[int] = []
    for idx, ch in enumerate(str(s or "").lower()):
        if ch.isalnum():
            chars.append(ch)
            offs.append(idx)
    return "".join(chars), offs


def _sep_canonical_with_offsets(s: Any) -> Tuple[str, List[int]]:
    """Lowercased text with every non-alphanum RUN collapsed to one '·'
    marker, plus the raw index each canonical char came from. Separator
    STRUCTURE survives: '5,350.00', '5.350,00' and '5 350,00' all become
    '5·350·00' (the grouping separators land in the same slots), while a
    longer amount '$53,500.00' becomes '53·500·00' and does NOT contain
    '5·350·00'."""
    chars: List[str] = []
    offs: List[int] = []
    run_start = -1
    for idx, ch in enumerate(str(s or "").lower()):
        if ch.isalnum():
            if run_start >= 0:
                chars.append("·")
                offs.append(run_start)
                run_start = -1
            chars.append(ch)
            offs.append(idx)
        elif run_start < 0:
            run_start = idx
    return "".join(chars), offs


def _canon_find(hay: str, tok: str) -> int:
    """First digit-edge-anchored occurrence of canonical ``tok`` in
    canonical ``hay`` (-1 when absent). Plain containment lets '5,350.00'
    match inside '$53,500.00' — a longer amount for a different machine
    (measured live 2026-09-13: the July Seguin thread's $53,500 10' shear
    quote matched the Aug '$ 5,350.00' query and took a full-body slot).
    Only DIGIT edges are anchored — but note the stripped form also erases
    the gap between two adjacent numbers ('5,350.00 – 10%' → '535000010'),
    which is why callers try the separator-preserving form FIRST."""
    if len(tok) < 4:
        return -1
    m = re.search(rf"(?<![0-9]){re.escape(tok)}(?![0-9])", hay)
    return m.start() if m else -1


def _fig_occurrence(text: str, phrase: str) -> int:
    """Raw index of the first convincing occurrence of a figure ``phrase``
    in ``text``; -1 when absent. Separator-structure match first (locale
    variants align; longer amounts don't contain the token), then the
    digit-stripped fallback with digit-edge guards (catches ungrouped
    renders like '5350.00' without re-admitting the '$53,500.00' prefix
    collision)."""
    if not phrase:
        return -1
    sep, sep_offs = _sep_canonical_with_offsets(text)
    tok_sep, _ = _sep_canonical_with_offsets(phrase)
    if tok_sep:
        i = sep.find(tok_sep)
        if i >= 0 and sep_offs:
            return sep_offs[i]
    dig, dig_offs = _canonical_with_offsets(text)
    j = _canon_find(dig, _canonical_fig_text(phrase))
    if j >= 0 and dig_offs:
        return dig_offs[j]
    return -1


def _first_visible_anchor(text: str, anchors: List[str]) -> Optional[str]:
    """The first anchor with a convincing occurrence in ``text`` — the check
    that decides whether a rendered line already shows the evidence."""
    for a in anchors or []:
        if _fig_occurrence(text, a) >= 0:
            return a
    return None


def _fig_match_window(
    body: str, anchors: List[str], before: int = 120, after: int = 320
) -> Optional[Tuple[str, str]]:
    """(anchor, window) around the FIRST convincing occurrence of any anchor
    in ``body``, quoted from the raw text. None when no anchor matches —
    the caller then shows the line unchanged."""
    for a in anchors or []:
        raw = _fig_occurrence(body, a)
        if raw < 0:
            continue
        window = re.sub(
            r"\s+", " ", str(body[max(0, raw - before):raw + after]).strip()
        )
        return a, window
    return None


def _ingested_line_from_row(
    row: Dict[str, Any],
    with_body: bool,
    anchors: Optional[List[str]] = None,
    body_cap: Optional[int] = None,
) -> str:
    """One [ingested mailbox] listing line; with_body appends the FULL
    message text. Bodies come from metadata.html_body (ingestion's store
    choke point for original markup) with the plain content column as
    fallback — the 260-char content excerpt cut mid-signature, exactly
    where quoted/forwarded originals begin (live 2026-09-09 ryershov
    thread). Head+tail capped like the Graph hydration.

    ``anchors`` (figure phrases the row was matched BY) guarantee the
    evidence stays visible: matched amounts live mid-quote in replies and
    below signatures in forwards, so head-biased excerpts and the 60/40
    body elision can render a line that matched '5,350.00' without showing
    it anywhere (live 2026-09-13: the agent correctly reported 'the
    $5,350.00 figure isn't visible in what came back' while every scan HAD
    matched the right emails). When no anchor is visible in the rendered
    line, a MATCH window around the canonical occurrence is appended.

    Every line also carries ``full: knowledge/conversations/<id>`` — the VFS
    path that resolves to this message's COMPLETE body as line-numbered text
    (``documents.cat``). Threads run to 79k chars live; the excerpt here is
    bounded on purpose (context budget), so the remainder must stay
    reachable on demand rather than silently lost."""
    row_id = str(row.get("id") or "")
    cite = f" | full: knowledge/conversations/{row_id}" if row_id else ""
    line = (
        f"- [ingested mailbox] From: {row.get('sender')} | "
        f"{str(row.get('subject') or '')[:90]} | "
        f"received: {str(row.get('timestamp') or '')[:19]}"
        f"{cite}"
    )
    if not with_body:
        snippet = str(row.get("content") or "")[:260]
        if anchors and not _first_visible_anchor(snippet, anchors):
            win = _fig_match_window(str(row.get("content") or ""), anchors)
            if win:
                snippet += f" … MATCH for '{win[0]}': …{win[1]}…"
        return line + f" | {snippet}"
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
    full_body = body
    # The attachments footer (ingestion appends '--- Attachments ---' to the
    # plain content column only) is often the evidence that ties a quote to
    # the exact machine — e.g. the '$ 5,350.00' email carrying the Fintek
    # F5216 spec-sheet .doc (live 2026-09-13: the agent could name the price
    # but 'couldn't confirm a spec sheet was attached'). The styled
    # html_body preferred above does not include it — re-attach it.
    content_col = str(row.get("content") or "")
    att_i = content_col.rfind("--- Attachments ---")
    if att_i >= 0:
        attachments = content_col[att_i:].strip()
        if attachments and attachments[:60] not in body:
            body = (body + "\n\n" + attachments).strip()
            full_body = (full_body + "\n\n" + attachments).strip()
    if len(body) > (body_cap or _INGESTED_BODY_CAP):
        cap = body_cap or _INGESTED_BODY_CAP
        head = int(cap * 0.6)
        body = (
            body[:head]
            + "\n[…middle of this quoted thread elided…]\n"
            + body[-(cap - head):]
        )
    if anchors and not _first_visible_anchor(body, anchors):
        # Window sources in order: the rendered body, the UN-elided body
        # (the elision is what hid the figure), then the raw content column
        # (when the styled html_body simply lacks the quoted text the plain
        # copy carries).
        win = (
            _fig_match_window(body, anchors)
            or _fig_match_window(full_body, anchors)
            or _fig_match_window(str(row.get("content") or ""), anchors)
        )
        if win:
            body += f"\n[MATCH for '{win[0]}' inside this thread: …{win[1]}…]"
    return line + " | FULL BODY:\n" + (body or "(empty message)")


# (2026-09-13 review, P2-8/P3-14) ONE shared load of the ingested comms
# table per turn. A single outlook search used to full-table-load
# atom_communications 3-5 times (address scan, figure-token scan, styled
# lookup, the ingest fallback's re-read — ~4s per walk at 3.5k rows). The
# cache is deliberately SHORT-TTL (default 5s — comfortably one turn, never
# a cross-turn staleness window) and is invalidated explicitly whenever the
# planner itself writes to the store (the ingest fallback must re-read its
# own pull). Path resolution goes through the ONE resolver
# (core.lancedb_handler._resolve_local_db_path) instead of a second
# hand-rolled Path(__file__)-relative source of truth, so legacy-store
# adoption and LANCEDB_URI overrides behave like every other reader.
_COMMS_CACHE_TTL_SECONDS = float(
    os.getenv("ATOM_PLANNER_COMMS_CACHE_TTL_SECONDS", "5") or 5
)
_comms_store_cache: Dict[str, tuple] = {}


def invalidate_comms_store_cache() -> None:
    """Drop the cached comms snapshot (called after this planner WRITES to
    the store so the re-search sees its own pull; also tests)."""
    _comms_store_cache.clear()


def _comms_store_db_path() -> str:
    """Directory of the `default` workspace memory store, resolved the same
    way every other reader resolves it (never a CWD-relative guess)."""
    try:
        from core.lancedb_handler import _resolve_local_db_path

        base = _resolve_local_db_path(
            os.getenv("LANCEDB_URI", "./data/atom_memory")
        )
        return str(Path(base) / "default")
    except Exception:  # noqa: BLE001 — same anchor as before, never raises
        return str(
            Path(__file__).resolve().parent.parent / "data" / "atom_memory" / "default"
        )


def _comms_store_records() -> List[Dict[str, Any]]:
    """All atom_communications rows as dicts — the ONE cached load shared by
    the address scan, the figure-token scan and the styled-body lookup."""
    import time as _time

    path = _comms_store_db_path()
    now = _time.monotonic()
    hit = _comms_store_cache.get(path)
    if hit and now - hit[0] < _COMMS_CACHE_TTL_SECONDS:
        return hit[1]
    import lancedb

    db = lancedb.connect(path)
    table = db.open_table("atom_communications")
    records = table.to_arrow().to_pandas().to_dict("records")
    _comms_store_cache[path] = (now, records)
    return records


def _search_ingested_by_address(user_id, address, limit=4, query=""):
    """Deterministic LanceDB lookup of ingested messages tied to an email
    address (sender/recipient/content containment, participant rows ranked
    first — see _rank_address_hits, which uses ``query`` to prefer a row whose
    SUBJECT shares a term with the request over merely-newer mail). Graph free-text search does not
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
        for i, row in enumerate(
            _rank_address_hits(
                _comms_store_records(), address.lower(), limit=limit, query=query
            )
        ):
            out.append(
                _ingested_line_from_row(
                    row,
                    with_body=i < _INGESTED_BODY_LINES,
                    # The single best-ranked row shows the WHOLE thread (up to
                    # the full cap): an elided middle is where a quoted quote
                    # hides the answer the user just asked for.
                    body_cap=(
                        _INGESTED_BODY_CAP_FULL if i < _INGESTED_FULL_LINES else None
                    ),
                )
            )
    except Exception as e:
        logger.debug(f"ingested address search skipped: {e}")
    return out


def _canonical_fig_text(s: Any) -> str:
    """Separator-insensitive comparison form: '5,350.00', '$5,350.00' and
    '5 350.00' all canonicalize to '535000' — email bodies render amounts
    in every one of these shapes."""
    return re.sub(r"[^a-z0-9]+", "", str(s or "").lower())


#: Above this stored-metadata size the html pass runs only when the plain body
#: matched nothing. Median live metadata is 48 KB and the max is 35 MB; the
#: cap keeps mega-threads off the hot path without dropping ordinary html-only
#: matches from the ranking.
_HTML_PASS_MAX_CHARS = int(os.getenv("ATOM_HTML_PASS_MAX_CHARS", "200000") or 200000)


# A figure match within this many chars of the subject+body start counts as
# the message's OWN text — quote lines state the amount up front, quoters
# bury it under signatures and tracking-URL goo (measured live 2026-09-13
# on the Seguin '$ 5,350.00' thread: originals matched at char 14/55,
# quoting replies/forwards at 691-5344).
_FIGURE_OWN_TEXT_WINDOW = 240


def _fig_occurrence_in_fields(fields: List[str], phrase: str) -> int:
    """First position of ``phrase`` across ``fields`` (joined-offset space),
    or -1. RAW SPELLINGS FIRST, canonical forms only as a fallback.

    The canonical helpers walk a whole string character by character and keep
    an offset for every character, so running them over the html bodies of
    every gated row (median 48 KB, max 35 MB) cost 20s live. The decorated
    spelling is present verbatim in the overwhelming majority of real rows, so
    a plain ``find`` resolves those, and the canonical pass runs only for the
    genuinely differently-rendered remainder ('5 350.00', '5.350,00',
    '5350.00'). Extracted so both this matcher and the anchor logic use ONE
    occurrence rule."""
    offset = 0
    for field in fields:
        for probe in (phrase, phrase.replace(",", "").replace(" ", "")):
            if probe:
                i = field.find(probe)
                if i >= 0:
                    return offset + i
        offset += len(field) + 1
    offset = 0
    tok_sep, _ = _sep_canonical_with_offsets(phrase)
    tok_dig = _canonical_fig_text(phrase)
    for field in fields:
        dig, dig_offs = _canonical_with_offsets(field)
        sep, sep_offs = _sep_canonical_with_offsets(field)
        if tok_sep and sep_offs:
            i = sep.find(tok_sep)
            if i >= 0:
                return offset + sep_offs[i]
        if dig_offs:
            j = _canon_find(dig, tok_dig)
            if j >= 0:
                return offset + dig_offs[j]
        offset += len(field) + 1
    return -1


_WEEKDAY_NAMES = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2, "thursday": 3, "thu": 3, "thur": 3,
    "friday": 4, "fri": 4, "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}
_MONTH_NAMES = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7,
    "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12,
    "december": 12,
}
_STATED_DATE_MD_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})\b")
_STATED_DATE_MONTH_RE = re.compile(
    r"\b(" + "|".join(sorted(_MONTH_NAMES, key=len, reverse=True))
    + r")\.?\s+(\d{1,2})\b", re.IGNORECASE)
_STATED_DATE_WEEKDAY_RE = re.compile(
    r"\b(" + "|".join(_WEEKDAY_NAMES) + r")\b", re.IGNORECASE)


def _stated_date_window(
    text: str, today: Optional["datetime.date"] = None,
) -> Optional[Tuple[str, str]]:
    """The (naive-ISO start, end) day bounds for a date the USER stated, or
    None. Handles '9/11', 'september 11', 'sep 11', weekday names ('friday'
    -> the most recent past one), 'yesterday', 'today'.

    Live 2026-09-15 (canvas a1a13834): "find the email thread for f-5216.
    it was sent to me on 9/11 friday" — the code matched 17 stored rows and
    the newest-3 cap surfaced Aug 26 + Sep 14 threads while the Sep 11 rows
    the user was pointing at lost the recency race. The stated date is a
    ranking handle the lanes ignored entirely.

    Conservative by construction: the bare M/D form counts only when the
    message ALSO carries a weekday or explicit month/day word (so '7/8-inch'
    in a port spec never becomes July 8); an M/D that lands in the future is
    read as last year. Store timestamps are naive ISO ('YYYY-MM-DD HH:MM:SS');
    comparisons are lexicographic on that shape."""
    if not text:
        return None
    import datetime as _dt

    today = today or _dt.date.today()

    def _bounds(y: int, m: int, d: int) -> Optional[Tuple[str, str]]:
        try:
            day = _dt.date(y, m, d)
            if day > today:
                # A Feb 29 rolling back into a non-leap past year is not a
                # real stated date — None, exactly like Feb 30.
                day = day.replace(year=day.year - 1)
        except ValueError:
            return None
        start = day.strftime("%Y-%m-%d 00:00:00")
        end = day + _dt.timedelta(days=1)
        return (start, end.strftime("%Y-%m-%d 00:00:00"))

    t = str(text or "")

    m = _STATED_DATE_MONTH_RE.search(t)
    if m:
        bounds = _bounds(today.year, _MONTH_NAMES[m.group(1).lower()],
                         int(m.group(2)))
        if bounds:
            return bounds

    has_day_word = (
        _STATED_DATE_WEEKDAY_RE.search(t)
        or re.search(r"\b(?:yesterday|today)\b", t, re.IGNORECASE)
    )
    if has_day_word:
        m = _STATED_DATE_MD_RE.search(t)
        if m:
            mm, dd = int(m.group(1)), int(m.group(2))
            if 1 <= mm <= 12 and 1 <= dd <= 31:
                bounds = _bounds(today.year, mm, dd)
                if bounds:
                    return bounds
        mw = _STATED_DATE_WEEKDAY_RE.search(t)
        if mw:
            wd = _WEEKDAY_NAMES[mw.group(1).lower()]
            delta = (today.weekday() - wd) % 7 or 7 if today.weekday() != wd else 0
            if delta == 0 and re.search(
                    r"\b(?:yesterday|today)\b", t, re.IGNORECASE) is None:
                delta = 7
            day = today - _dt.timedelta(days=delta)
            start = day.strftime("%Y-%m-%d 00:00:00")
            end = (day + _dt.timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
            return (start, end)
        if re.search(r"\byesterday\b", t, re.IGNORECASE):
            day = today - _dt.timedelta(days=1)
            return (day.strftime("%Y-%m-%d 00:00:00"),
                    today.strftime("%Y-%m-%d 00:00:00"))
        return (today.strftime("%Y-%m-%d 00:00:00"),
                (today + _dt.timedelta(days=1)).strftime("%Y-%m-%d 00:00:00"))
    return None


def _window_from_iso_date(value: Any) -> Optional[Tuple[str, str]]:
    """Day bounds for an ISO date string (the planner's mentioned_date
    piggyback field), same shape as _stated_date_window's output. None on
    anything unparseable."""
    if not value:
        return None
    import datetime as _dt

    try:
        day = _dt.date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None
    return (
        day.strftime("%Y-%m-%d 00:00:00"),
        (day + _dt.timedelta(days=1)).strftime("%Y-%m-%d 00:00:00"),
    )


def _match_rows_by_figure_tokens(
    rows: List[Dict[str, Any]], tokens: List[str], limit: int = 4,
    date_window: Optional[Tuple[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Rank comms rows whose subject/content/html body contains EVERY figure
    token (canonical form). The amount IS the evidence in vendor-cost
    queries, so requiring all tokens keeps the scan precise; duplicate bodies
    collapse (same key semantics as _rank_address_hits).

    Own-text tier FIRST (live 2026-09-13): newest-only ranking let four
    newer replies/forwards that merely QUOTE the figure fill the whole cap
    while the original message — the amount at the top of its body, the
    spec-sheet attachment — fell one slot past it, so the listing rendered
    matches that carried the figure only inside elided quote middles. A
    match whose first canonical occurrence sits within the message's
    opening text (≤_FIGURE_OWN_TEXT_WINDOW chars of subject + body — a
    quote line names its amount up front) forms tier 0. Absolute position,
    not a length ratio: tracking URLs and signatures inflate the haystack
    so badly that deep-quote matches still score ~0.1 of total length
    (measured live on the Seguin thread: originals at pos 14/55, quoters
    at 691-5344). Every tier still sorts newest-first, so recency keeps
    deciding within tiers and unrelated same-amount threads keep their
    order."""
    import json as _json

    phrases = [t for t in tokens if len(_canonical_fig_text(t)) >= 4]
    if not phrases:
        return []
    # Gate spellings: the token as written, its separator-free form, and its
    # longest digit group (a row rendering the amount any other way still
    # contains those digits — '350' for '5,350.00').
    canon_keys = _canon_keys(phrases)
    variants = _probe_variants(phrases)
    seen_keys = set()
    scored = []

    def _consider(row, subject, content, raw_meta):
        """Score one row against every phrase; None when it does not match.

        Fields are matched SEPARATELY, never concatenated: canonicalization
        erases separators, so a subject ending in a digit and a body starting
        in one fused into a single longer number ('Quote 52' + '5350.00 net'
        → '52535000'), which the digit-edge guard then read as the '$53,500'
        prefix case and rejected — a false negative on a genuine match.
        Positions are made comparable by adding each field's start offset in
        the (vanished) joined text, which keeps the own-text tier honest."""
        if raw_meta:
            meta = raw_meta
            if isinstance(meta, str):
                try:
                    meta = _json.loads(meta)
                except Exception:
                    meta = {}
            html = str((meta or {}).get("html_body") or "") if isinstance(meta, dict) else ""
        else:
            html = ""
        positions = [
            _fig_occurrence_in_fields([subject, content, html], phrase)
            for phrase in phrases
        ]
        return positions if all(p >= 0 for p in positions) else None

    # PASS 1 — the CHEAP columns only (subject + plain body). Measured live:
    # this resolves the overwhelming majority of figure queries in ~2s and,
    # crucially, leaves the metadata column UNTOUCHED. The stored metadata is
    # the full original HTML (median 48 KB, max 35 MB/row); lowercasing and
    # substring-scanning 340 MB per query is what made this leg cost 13-22s.
    for row in rows:
        subject = str(row.get("subject") or "")
        content = str(row.get("content") or "")
        positions = _consider(row, subject, content, None)
        if positions is None:
            continue
        key = (
            str(row.get("sender") or ""),
            str(row.get("recipient") or ""),
            subject,
            content[:120],
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        tier = 0 if min(positions) <= _FIGURE_OWN_TEXT_WINDOW else 1
        scored.append((tier, str(row.get("timestamp") or ""), row))
    _plain_matched = len(scored)

    # PASS 2 — the styled html body, for every row pass 1 did not already
    # match. A RAW substring probe runs first (no lowercasing, no JSON parse):
    # it cannot reject a row the pass would match, because the keys include
    # the canonical digit string, every decorated spelling AND the ungrouped
    # form. This keeps the column's 340 MB off the hot path for the typical
    # query while still surfacing amounts that live ONLY in the html body
    # (test_match_rows_html_body_counts).
    for row in rows:
        subject = str(row.get("subject") or "")
        content = str(row.get("content") or "")
        key = (
            str(row.get("sender") or ""),
            str(row.get("recipient") or ""),
            subject,
            content[:120],
        )
        # CHEAPEST CHECK FIRST: a row the pass-1 match already counted never
        # touches its metadata.
        if key in seen_keys:
            continue
        raw_meta = row.get("metadata")
        if not isinstance(raw_meta, str) or not raw_meta:
            continue
        # ONE probe before the expensive pass, EXACTLY as broad as the matcher
        # below (variants + canonical keys, lowercased — the stored html has
        # uppercase tags). Two narrower probes were tried and both silently
        # dropped real matches: a canonical-only key is NOT a substring of
        # '5,350.00' (the commas sit inside the digits), and a case-sensitive
        # one missed uppercase html. This probe can only skip work, never a
        # match: whatever the pass could find is a substring of one of these
        # forms, and a hit still goes through the full matcher.
        meta_lc = raw_meta.lower()
        if not (
            any(v in meta_lc for v in variants)
            or any(k in meta_lc for k in canon_keys)
        ):
            continue
        # A HEAVY html body costs a full canonicalization pass. When the plain
        # body ALREADY matched rows, those matches can only be displaced by an
        # html row that outranks them — so heavy bodies are skipped and light
        # ones still compete (keeping html-only matches in the ranking for
        # ordinary messages while keeping 35 MB mega-threads off the hot
        # path). When the plain body matched NOTHING, every html row is read:
        # that is the html-only case this pass exists for.
        if _plain_matched and len(raw_meta) > _HTML_PASS_MAX_CHARS:
            continue
        positions = _consider(row, subject, content, raw_meta)
        if positions is None:
            continue
        seen_keys.add(key)
        tier = 0 if min(positions) <= _FIGURE_OWN_TEXT_WINDOW else 1
        scored.append((tier, str(row.get("timestamp") or ""), row))

    # STATED-DATE TIER (live 2026-09-15): the user's "sent 9/11 friday" is
    # a ranking handle — when the code matches more rows than the cap, the
    # in-window rows must lead regardless of recency (17 F-5216 rows fought
    # over 3 slots and the Sep 11 pair lost to Sep 14 traffic). In-window
    # rows drop one tier; every other ordering (own-text, newest-first)
    # is preserved inside each tier.
    if date_window:
        w_start, w_end = date_window
        scored = [
            ((tier - 1) if (w_start <= ts[:19].replace("T", " ") < w_end)
             else tier, ts, row)
            for (tier, ts, row) in scored
        ]
    scored.sort(key=lambda t: t[1], reverse=True)
    scored.sort(key=lambda t: t[0])
    return [r for _, _, r in scored[:limit]]


def _search_ingested_by_tokens(
    user_id, tokens: List[str], limit: int = 4,
    date_window: Optional[Tuple[str, str]] = None,
) -> List[str]:
    """Deterministic LanceDB lookup of ingested messages containing the
    query's figure tokens (amounts, model codes). Graph $search handles
    quoted currency amounts unreliably and relevance-buries them, so the
    ingested store is the authoritative leg for exact-figure queries (live
    2026-09-12: the '$5,350.00 – 10% in stock' vendor-cost email sat in the
    store while every live-API form missed it). Lines carry the tokens as
    anchors so the matched figure is guaranteed visible (see
    _ingested_line_from_row). Fault-isolated; [] on anything."""
    out: List[str] = []
    if not tokens:
        return out
    try:
        for i, row in enumerate(
            _match_rows_by_figure_tokens(
                _comms_store_records(), tokens, limit=limit,
                date_window=date_window)
        ):
            out.append(
                _ingested_line_from_row(
                    row,
                    with_body=i < _INGESTED_BODY_LINES,
                    anchors=tokens,
                    # Figure-matched rows carry the whole thread: the amount
                    # the user named is the evidence, and the surrounding
                    # quote (spec sheet, terms, attachments) lives in the
                    # middle a head+tail clip would drop.
                    body_cap=(
                        _INGESTED_BODY_CAP_FULL if i < _INGESTED_FULL_LINES else None
                    ),
                )
            )
    except Exception as e:
        logger.debug(f"ingested figure-token search skipped: {e}")
    return out


async def _ingested_mailbox_lines(
    user_id, query, context=None, cap: int = 6, hybrid_min: int = 4
) -> List[str]:
    """Ranked ingested-mailbox lines for a communication lookup — the second
    source every mailbox-shaped search gets. Figure tokens (amounts, model
    codes) lead, then address fragments (query AND recent history) drive the
    deterministic scan — ONE full-table load per distinct address (the same
    address in query and history used to trigger two); the hybrid/semantic
    search only fills slots below ``hybrid_min`` (embedding init + vector
    search was a real contributor to exec timeouts under load, live
    2026-09-06, and free-text live APIs — Graph included — do not reliably
    match sender addresses or nicknames). Fault-isolated: [] on anything."""
    store_lines: List[str] = []
    import re as _re_addr

    # STATED-DATE TIER (same handle as _mailbox_figure_lines): a date the
    # user stated ("sent 9/11 friday") ranks the figure matches when the
    # code matches many rows; the query rewrite keeps codes but drops the
    # date, so the window comes from the current message.
    _window = (
        _stated_date_window(_current_message_text(context) or "")
        or _window_from_iso_date((context or {}).get("mentioned_date"))
    )

    # FIGURE TOKENS LEAD: an amount or model code in the query is the most
    # specific evidence there is — it must not be crowded out of the cap by
    # address lines (live 2026-09-12: old Seguin thread lines filled the
    # mailbox slots while the '$5,350.00' email went unlisted) nor depend on
    # the hybrid leg running. Same off-loop rule as the address scan.
    # A figure-less retry ('try the search again') inherits the most recent
    # user figure query, so a planner rewrite that drops the amount cannot
    # disarm this leg (live 2026-09-13).
    _fig_tokens = _distinctive_figure_phrases(query, limit=_FIGURE_PHRASE_LIMIT)
    # A figure the user did NOT just name (inherited from an earlier turn)
    # ranks BELOW the named participant: when someone says "the thread
    # chandrakant forwarded about the foot shear", a previous turn's $5,350
    # quote must not fill the slots with a different thread (live 2026-09-14).
    _inherited_figs: List[str] = []
    if _fig_tokens:
        for _line in await asyncio.to_thread(
            _search_ingested_by_tokens, user_id, _fig_tokens, max(cap - 2, 2),
            _window
        ):
            if _line not in store_lines:
                store_lines.append(_line)
                if len(store_lines) >= cap:
                    break
    else:
        _inherited_figs = _latest_user_figure_phrases(context)

    _addr_haystack = query + " " + " ".join(
        _entry_text(m) for m in ((context or {}).get("history") or [])[-6:]
    )
    # Named people first: "the thread chandrakant forwarded" resolves to his
    # address even when the text carries none, and a named owner is stronger
    # evidence than an incidental address in older history (the live miss had
    # the mailbox slots filled by a different thread's address).
    _addr_order = list(_resolve_named_addresses(query or "", limit=2))
    for _a in _re_addr.findall(r"[\w.+-]+@[\w.-]+", _addr_haystack):
        if _a.lower() not in [x.lower() for x in _addr_order]:
            _addr_order.append(_a)
    _seen_addrs = set()
    for _addr in _addr_order:
        if _addr.lower() in _seen_addrs:
            continue
        _seen_addrs.add(_addr.lower())
        if len(store_lines) >= cap:
            break  # figure lines filled the cap — skip the table walk
        # SYNC-OFF-LOOP: the scan loads and walks the whole comms table
        # (~4s at 3.5k rows, live 2026-09-06) — on the loop it froze every
        # concurrent request for that long, per address.
        for _line in await asyncio.to_thread(
            _search_ingested_by_address, user_id, _addr, 4, query
        ):
            if _line not in store_lines:
                store_lines.append(_line)
                if len(store_lines) >= cap:
                    break
        if len(store_lines) >= cap:
            break

    if _inherited_figs and len(store_lines) < cap:
        # Spare capacity only: the named participant's thread has had its pick.
        for _line in await asyncio.to_thread(
            _search_ingested_by_tokens, user_id, _inherited_figs,
            max(cap - len(store_lines), 2), _window
        ):
            if _line not in store_lines:
                store_lines.append(_line)
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
    r"\b(?=[A-Za-z_/-]*\d)(?=[A-Za-z0-9_/-]*[A-Za-z])"
    r"[A-Za-z0-9][A-Za-z0-9_/-]{4,}\b"
)
_STYLED_BODY_BLOCK_CAP = 6000

# Currency amounts across locales and business types: any major-economy
# symbol, ISO code before or after ("CAD 5,350", "5.350,00 EUR"), both
# decimal conventions (1,234.56 en / 1.234,56 de), space-grouped
# thousands (10 000, fr-CA), and Indian lakh grouping (1,00,000). These
# are the tokens a mailbox search must match EXACTLY — per-term
# shredding turns them into noise ("5" "350" "00") and Graph relevance
# buries them.
_CURRENCY_SYMBOLS = "$€£¥₹₩₽₺"
_CURRENCY_CODE_RE = (
    r"(?:USD|CAD|EUR|GBP|INR|JPY|AUD|NZD|CHF|CNY|HKD|SGD|MXN|BRL|ZAR"
    r"|SEK|NOK|DKK|PLN|AED|SAR|TRY|RUB|KRW|ILS|TWD|THB|IDR|VND|PHP|MYR)"
)
# Separator-class-aware amount matching (2026-09-13 review): the space-
# grouped form is also how phone numbers, dates and plain quantities render
# ("+1 555 123 4567", "10 000 units", "12 345"), so it requires an ADJACENT
# currency signal (symbol or ISO code); comma/dot-grouped amounts stay
# allowed without one but are screened for phone-shaped digit runs and
# version/section contexts below (the phrase feeds a quoted Graph search
# with boost=len(phrase) AND an ALL-tokens-required store scan — one junk
# token crowds out or zeroes the true email).
_AMOUNT_PHRASE_RE = re.compile(
    # 1) Indian lakh/crore grouping first — the bare-symbol branch below
    #    would otherwise eat its leading group as a decimal ("₹1,00" of
    #    "₹1,00,000").
    rf"(?:{_CURRENCY_CODE_RE}\s*)?[{_CURRENCY_SYMBOLS}]?\s*"
    rf"\d{{1,2}}(?:,\d{{2}})+,\d{{3}}(?:\.\d{{1,2}})?\b"
    # 2) Space-grouped thousands WITH a leading currency signal.
    rf"|(?:{_CURRENCY_CODE_RE}\s*|[{_CURRENCY_SYMBOLS}]\s*)"
    rf"\d{{1,3}}(?:\s\d{{3}})+(?:[.,]\d{{1,2}})?(?:\s*{_CURRENCY_CODE_RE})?\b"
    # 3) Space-grouped thousands with a TRAILING ISO code ("10 000 CAD").
    rf"|\d{{1,3}}(?:\s\d{{3}})+(?:[.,]\d{{1,2}})?\s*{_CURRENCY_CODE_RE}\b"
    # 4) Comma-grouped (en-US/CA amounts).
    rf"|(?:{_CURRENCY_CODE_RE}\s*)?[{_CURRENCY_SYMBOLS}]?\s*"
    rf"\d{{1,3}}(?:,\d{{3}})+(?:[.,]\d{{1,2}})?(?:\s*{_CURRENCY_CODE_RE})?\b"
    # 5) Dot-grouped (EU thousands, "5.350,00").
    rf"|(?:{_CURRENCY_CODE_RE}\s*)?[{_CURRENCY_SYMBOLS}]?\s*"
    rf"\d{{1,3}}(?:\.\d{{3}})+(?:,\d{{1,2}})?(?:\s*{_CURRENCY_CODE_RE})?\b"
    # 6) Bare currency symbol.
    rf"|[{_CURRENCY_SYMBOLS}]\s*\d+(?:[.,]\d{{1,2}})?"
)
_AMOUNT_TRIM_RE = re.compile(
    rf"^(?:{_CURRENCY_CODE_RE}\s*)?[{_CURRENCY_SYMBOLS}]?\s*"
    rf"|\s*(?:{_CURRENCY_CODE_RE})?$"
)
# Document-structure words that commonly precede NON-amount digit groups
# ("version 1.234", "section 3.456") — cheap preceding-word screen.
_FIG_CONTEXT_RE = re.compile(
    r"\b(?:version|ver|rev|v|section|sect|sec|paragraph|para|page|fig"
    r"|figure|step|phase|clause|chapter|appendix|serial)\s*[.:#]?\s*$",
    re.IGNORECASE,
)
# Digits/separators of one contiguous number-ish run (no spaces — two
# genuine amounts separated by a space must not merge into one "run").
_DIGIT_RUN_CHARS = ".,+-()"
_ADDR_IN_QUERY_RE = re.compile(r"[\w.+-]+@[\w.-]+")
# ONE figure-phrase limit for every consumer (the _collect/resolve ladder
# used to cap at 2 while the store scan capped at 3 — one deterministic
# rule, parametrized once).
_FIGURE_PHRASE_LIMIT = 3
# Phrase-search rank boost cap: junk 13-char phone-shaped phrases used to
# outrank genuine term hits via boost=len(phrase).
_PHRASE_BOOST_CAP = 12


def _run_digits(text: str, start: int, end: int) -> str:
    """Digits of the contiguous number-ish run AROUND text[start:end]
    (digits joined by .,+-() — never spaces, so two genuine amounts
    separated by a space never merge). '1,555,123' inside '1,555,123,4567'
    yields 11 digits, exposing the phone shape the regex's \\b backtrack
    would otherwise hide."""
    l, r = start, end
    while l > 0 and (text[l - 1].isdigit() or text[l - 1] in _DIGIT_RUN_CHARS):
        l -= 1
    while r < len(text) and (text[r].isdigit() or text[r] in _DIGIT_RUN_CHARS):
        r += 1
    return re.sub(r"\D", "", text[l:r])


def _is_phone_shaped(text: str, start: int, end: int) -> bool:
    """NANP phone shape: 10 digits, or 11 starting with '1'."""
    digits = _run_digits(text, start, end)
    return len(digits) == 10 or (len(digits) == 11 and digits.startswith("1"))


def _distinctive_figure_phrases(
    text: str, limit: int = _FIGURE_PHRASE_LIMIT
) -> List[str]:
    """Exact-form search phrases for the query's distinctive evidence:
    currency amounts and product/model codes, across locales and
    industries. 'CAD 5,350.00', '€ 5.350,00', '₹1,00,000' and '$ 5,350'
    all reduce to the bare amount ('5,350.00', '5.350,00', '1,00,000') —
    bodies render symbols and codes inconsistently, and the store-side
    comparison is separator-insensitive. Small bare numbers are NOT
    distinctive and are skipped. False-positive screens (2026-09-13):
    space-grouped runs need a currency signal; phone-shaped digit runs and
    version/section contexts never become figure tokens."""
    out: List[str] = []
    text = text or ""
    for m in _AMOUNT_PHRASE_RE.finditer(text):
        raw = m.group(0)
        phrase = _AMOUNT_TRIM_RE.sub("", raw).strip()
        has_currency = phrase != raw.strip()
        if not has_currency:
            if _is_phone_shaped(text, m.start(), m.end()):
                continue
            if _FIG_CONTEXT_RE.search(text[max(0, m.start() - 20):m.start()]):
                continue
        if len(phrase) >= 4 and phrase not in out:
            out.append(phrase)
    for m in _PRODUCT_TOKEN_RE.finditer(text):
        tok = m.group(0)
        if tok not in out:
            out.append(tok)
    return out[:limit]


def _latest_user_figure_phrases(
    context: Optional[Dict[str, Any]], limit: int = _FIGURE_PHRASE_LIMIT
) -> List[str]:
    """Figure phrases from the most recent USER turn that carries one — the
    referent for 'try the search again'-style turns whose own text names no
    amount. Assistant replies are skipped deliberately: they echo every
    figure the conversation ever mentioned, so harvesting them would aim
    the deterministic scan at stale amounts (live 2026-09-13: the canvas
    history held $7,519.00 / $3,500.00 / $4,000.00 assistant echoes while
    the user's target was the '$ 5,350.00 – 10%' quote)."""
    for entry in reversed((context or {}).get("history") or []):
        if not isinstance(entry, dict):
            continue
        role = str(entry.get("role") or "").lower()
        if role and role != "user":
            continue
        if not role and "message" in entry:
            # Session shape {message, response}: the response side is the
            # assistant's echo of every figure ever mentioned — user side only.
            text = str(entry.get("message") or "")
        else:
            text = _entry_text(entry)
        phrases = _distinctive_figure_phrases(text, limit=limit)
        if phrases:
            return phrases
    return []


#: name-hint → addresses, built from the comms store's sender/recipient
#: columns. Cheap (7k rows, 0.01s) but rebuilt per query at most once per TTL.
_PEOPLE_INDEX: Dict[str, Any] = {}
_PEOPLE_INDEX_TTL_S = float(os.getenv("ATOM_PEOPLE_INDEX_TTL_S", "60") or 60)


def _people_index() -> Dict[str, List[str]]:
    """``name-hint → [addresses]`` from every sender/recipient in the store.

    The mailbox's own identity map: 'chandrakant' → chandrakant@brennan.ca,
    'joel' → joelseguin@seguinmach.com. Built from the store rather than from
    any hardcoded roster (per-install identity is DATA — CLAUDE.md invariant
    #4), short-TTL cached, and fault-isolated to {}."""
    import time as _time

    now = _time.monotonic()
    hit = _PEOPLE_INDEX.get("cache")
    if hit and now - hit[0] < _PEOPLE_INDEX_TTL_S:
        return hit[1]
    index: Dict[str, List[str]] = {}
    try:
        addr_re = re.compile(r"[\w.+-]+@[\w.-]+")
        for row in _comms_store_records():
            blob = f"{row.get('sender') or ''} {row.get('recipient') or ''}"
            for addr in addr_re.findall(blob):
                local = addr.lower().split("@", 1)[0]
                index.setdefault(local, [])
                if addr.lower() not in index[local]:
                    index[local].append(addr.lower())
    except Exception as e:  # noqa: BLE001
        logger.debug(f"people index unavailable: {e}")
        index = {}
    _PEOPLE_INDEX["cache"] = (now, index)
    return index


#: Local-parts that name a FUNCTION, not a person — never resolved as people.
_GENERIC_MAILBOX_WORDS = frozenset({
    "email", "mail", "emails", "info", "sales", "support", "admin", "contact",
    "team", "hello", "office", "accounts", "account", "billing", "service",
    "webmaster", "help", "shop", "store", "orders", "order", "noreply",
    "notifications", "notification", "marketing", "enquiries", "inquiries",
    "general", "reception", "desk", "news", "updates", "alerts", "system",
    "postmaster", "no-reply", "donotreply", "customerservice", "hr", "jobs",
})


def _extract_named_people(message: str, limit: int = 2) -> List[str]:
    """Person names the USER wrote, as name-hints to resolve against the store.

    'check the email thread chandrakant forwarded to me' names its owner
    directly — often in lowercase, which is why capitalisation is NOT the
    filter. Precision comes from the store instead: a word counts only when it
    is a local-part of an address that actually appears in the mailbox, so
    'the thread forwarded to me' resolves to nobody and this never invents a
    person. Longest match first, so a full first name beats a coincidental
    substring."""
    if not message:
        return []
    index = _people_index()
    if not index:
        return []
    words = {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z.'-]{3,}", message or "")}
    # Generic mailbox local-parts are not people: 'email@…', 'sales@…',
    # 'info@…' would otherwise resolve the word "email" in any ordinary
    # sentence into a mailbox scan.
    words -= _GENERIC_MAILBOX_WORDS
    hits = [hint for hint in index if hint in words]
    # Longest first: 'chandrakant' over a shorter accidental match.
    hits.sort(key=len, reverse=True)
    return hits[:limit]


def _resolve_named_addresses(
    message: str, limit: int = 2, per_name: int = 1
) -> List[str]:
    """Addresses for the people the message NAMES — the missing bridge from
    'who the user said' to 'which rows to read'.

    Live 2026-09-14: the user asked for "the email thread chandrakant
    forwarded to me about the foot shear". The mailbox legs key off addresses
    found in the query/history TEXT, and the conversational history carried a
    different thread's address — so the chandrakant thread was never scanned,
    even though every one of his messages is filed under one address. No new
    keyword rules: this resolves a NAME to the store's own address for it."""
    index = _people_index()
    out: List[str] = []
    for hint in _extract_named_people(message, limit=limit):
        for addr in (index.get(hint) or [])[:per_name]:
            if addr not in out:
                out.append(addr)
    return out


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
    # A NAME the user wrote resolves through the store's own identity map even
    # when no address appears anywhere in the text.
    for addr in _resolve_named_addresses(query or "", limit=2):
        if addr not in out:
            out.append(addr)
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

        rows = sorted(
            _comms_store_records(),
            key=lambda r: str(r.get("timestamp") or ""),
            reverse=True,
        )
        for row in rows:
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
#
# The small cap is a FLOOR for the deeper rows only: stored threads run to
# 79k chars (3,395 of 7,009 live messages exceed 2,500) and a head+tail clip
# of a quoted thread hides exactly the middle an agent is asked about — the
# live 2026-09-13 Seguin turn answered "the $5,350.00 figure isn't visible in
# what came back" from a clipped body while the full text sat in the store.
# The TOP `_INGESTED_FULL_LINES` ranked rows therefore carry their whole body
# up to `_INGESTED_BODY_CAP_FULL`, so one long thread cannot consume the
# whole evidence budget while the thread that actually matched stays
# readable. Every line also carries its `full: knowledge/conversations/<id>`
# VFS path, so even a capped remainder is one documents.cat away.
_INGESTED_BODY_LINES = 2
_INGESTED_BODY_CAP = 2500
_INGESTED_FULL_LINES = int(os.getenv("ATOM_INGESTED_FULL_BODY_LINES", "1") or 1)
# 32k chars ≈ 8k tokens for the ONE best-ranked row — it renders **98.9% of the
# live store's messages in full** (6,933 of 7,009; the remainder are 67k–79k
# mega-threads) and is only ever spent when a mailbox search actually matched.
# Anything past it still shows the match window (see _fig_match_window) plus
# the VFS citation.
_INGESTED_BODY_CAP_FULL = int(
    os.getenv("ATOM_INGESTED_FULL_BODY_CAP", "32000") or 32000
)
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
                    limit: int = 3, skip_pathlike: bool = False) -> List[str]:
    """Identifier candidates for exact-copy lookups: tokens that MIX letters
    with digits — the one shape every industry's catalog codes share (model
    numbers 'WG350DSAV', electronics parts 'LM358', chemical catalog
    'S318500', apparel SKUs 'NK-AQ0818', invoice refs 'INV-2024-118') and
    that prose, years, prices and quantities never do. Pure-digit tokens are
    excluded by the same logic. ``skip_hexlike`` drops 6-hex-digit tokens
    (canvas HTML style attributes like #1F3864 are layout noise; a genuine
    hex-shaped code from user-typed text still passes). ``skip_pathlike``
    drops tokens containing '/' — URL paths match the code shape (letters,
    digits, '/') but are never catalog codes, and appended to a live item
    search they blow provider value caps and AND-queries (live 2026-09-13,
    canvas a1a13834: a brennan.ca product-URL path became a 59-char
    'identifier' and pushed the Zoho search_text past its 100-char cap —
    HTTP 400 code 15 on every attempt, before auth). Order-preserving
    dedupe, capped at ``limit``."""
    out: List[str] = []
    for m in _PRODUCT_TOKEN_RE.finditer(text or ""):
        tok = m.group(0)
        if len(tok) < min_len or tok in out:
            continue
        if skip_hexlike and _HEX_COLOR_RE.match(tok):
            continue
        if skip_pathlike and "/" in tok:
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


async def _mailbox_figure_lines(
    user_id: Optional[str],
    query: str,
    context: Optional[Dict[str, Any]],
    limit: int = 3,
) -> List[str]:
    """The deterministic ingested-mailbox figure scan, available to EVERY
    memory-shaped lane. Amounts and model codes are the evidence in a
    vendor-cost lookup, and the hybrid/vector legs plus the address scan
    never reliably surface them (the amount sits mid-quote in replies and
    below signatures in forwards). The query's own figure tokens lead; a
    figure-less follow-up inherits the most recent USER turn's, so a planner
    rewrite ('try the search again') cannot disarm the leg. Fault-isolated:
    [] on anything."""
    try:
        figs = _distinctive_figure_phrases(query) or _latest_user_figure_phrases(
            context
        )
        if not figs:
            return []
        # The planner's query rewrite keeps the CODE but drops the user's
        # stated date ('9/11 friday'); the current message is where the
        # regex-recognizable date lives, and the planner's mentioned_date
        # field (stashed into the context by execute_tool_plan) covers the
        # messy relative expressions the parser cannot.
        window = (
            _stated_date_window(_current_message_text(context) or "")
            or _window_from_iso_date((context or {}).get("mentioned_date"))
        )
        return await asyncio.to_thread(
            _search_ingested_by_tokens, user_id, figs, limit, window)
    except Exception as e:  # noqa: BLE001 — a lane supplement must never break a turn
        logger.debug(f"mailbox figure leg skipped: {e}")
        return []


async def _memory_search_block(
    user_id: Optional[str], query: str, context: Optional[Dict[str, Any]]
) -> Optional[str]:
    """Memory leg entry point: dataset-catalog evidence (when the query
    carries an identifying code) and the deterministic mailbox figure scan
    PREPENDED to the hybrid memory search — so the exact rows surface no
    matter which leg the planner picks (it nondeterministically chooses
    memory/read/inventory for value questions). None when nothing matched.

    The figure scan is guaranteed HERE, not only inside the hybrid helper:
    the live 2026-09-13 miss was a '$ 5,350.00' query routed to
    memory.search whose block came back full of unrelated document hits
    with the amount nowhere in it, while the email sat in the store. It is
    computed ONCE per call and handed to the hybrid helper (which only
    prepends it ahead of its own 8-line cap) — the scan walks every comms
    row, so a second walk per turn is pure waste."""
    ds_block = await _datasets_evidence(user_id, query, context)
    fig_lines = await _mailbox_figure_lines(user_id, query, context)
    # CODES the turn is about — the leg that reaches a thread filed under
    # catalogue numbers when the user asks in conceptual words (live
    # 2026-09-14: "how list price was calculated for the foot shear" vs a
    # thread whose text says "cost" and whose subject says "Brake, Shear and
    # Lock Former."). Runs only when the figure leg found nothing, so the
    # common turn pays a single cheap scan.
    code_lines: List[str] = []
    if not fig_lines:
        code_lines = await _mailbox_code_lines(user_id, query, context)
    mem_block = await _memory_hybrid_block(
        user_id, query, context, figure_lines=fig_lines
    )
    missing = [
        line
        for line in fig_lines + code_lines
        if line not in (mem_block or "") and line not in (ds_block or "")
    ]
    ev_block = "\n".join(missing) or None
    parts = [b for b in (ds_block, ev_block, mem_block) if b]
    return "\n\n".join(parts) or None


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
    user_id: Optional[str],
    query: str,
    context: Optional[Dict[str, Any]],
    figure_lines: Optional[List[str]] = None,
) -> Optional[str]:
    """Hybrid search over the ingested workspace (documents, mailbox copies,
    records) formatted as a LIVE TOOL RESULTS block. The `memory` service leg
    of execute_tool_plan, factored out so other legs can fall back to it when
    their live source comes back empty. None when nothing matched.

    ``figure_lines`` (see _mailbox_figure_lines) are PREPENDED ahead of the
    8-line cap: hybrid hits are relevance-ranked and routinely filled every
    slot with unrelated documents while the amount the query named sat in an
    ingested email (live 2026-09-13)."""
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
            for _line in await asyncio.to_thread(
                _search_ingested_by_address, user_id, _addr, 4, query
            ):
                if _line not in lines:
                    lines.append(_line)
                    if len(lines) >= 8:
                        break
            if len(lines) >= 8:
                break
        # Exact-token leg runs LAST but ranks FIRST: an exact model-number
        # match is the strongest evidence for "find the row" questions, so
        # it must not be cut by the 8-line cap when the hybrid legs already
        # filled the block. Figure phrases get the same treatment — the
        # deterministic amount scan is this lane's ONLY mailbox figure leg
        # (live 2026-09-13: a '$5,350.00' query routed to memory.search saw
        # hybrid previews and address-scan heads, never the figure, while
        # the outlook lane had the scan all along; the planner picks lanes
        # nondeterministically, so every search lane needs the leg). The
        # lines arrive precomputed from _memory_search_block so the store is
        # walked once per turn.
        fig_lines = [
            _l for _l in (figure_lines or []) if _l not in lines
        ]
        exact_lines = [
            _l for _l in await asyncio.to_thread(
                _search_ingested_by_exact_token, user_id, query, skip_ids=seen_ids)
            if _l not in lines and _l not in fig_lines
        ]
        if exact_lines or fig_lines:
            lines = exact_lines + fig_lines + lines
        if not lines:
            return None
        # Same weak-reader guard as the outlook lane: figure lines are
        # verbatim deterministic matches — name them so the amount and
        # attachment lists are quoted from them, not from truncated
        # previews (live 2026-09-13).
        _fig_hdr = (
            _distinctive_figure_phrases(query) or _latest_user_figure_phrases(context)
            if fig_lines else []
        )
        return _with_grounding(
            f"LIVE TOOL RESULTS (memory.search, query='{query}') — hybrid "
            f"search over ingested workspace data; use these to answer:\n"
            + "\n".join(lines[:8])
            + "\nEVIDENCE TYPES: [document]* lines are ingested file contents "
            "(searchable); [email/chat record]* lines are received messages; "
            "[knowledge-node]* lines are extracted entities."
            + (
                f" EXACT-FIGURE MATCHES: the leading [ingested mailbox] lines "
                f"match '{'; '.join(_fig_hdr)}' verbatim (MATCH windows and "
                f"'--- Attachments ---' lists included) — quote the amount "
                f"and attachment names from them."
                if _fig_hdr and fig_lines else ""
            )
            + " Prior assistant "
            "replies are NEVER in this evidence — a fact that appears only in "
            "the conversation is not something you 'found in a file'. "
            "FRESHNESS: [document: … — ingested YYYY-MM-DD] shows when the copy "
            "was taken. For prices, quotes, or stock that drive an answer, cite "
            "the figure WITH its ingested date; if the customer decision hinges "
            "on it being current, say the source file should be re-opened live "
            "to confirm. LONG THREADS: an [ingested mailbox] line is an EXCERPT "
            "(quoted threads run to tens of thousands of chars and the middle "
            "may be elided). Its 'full: knowledge/conversations/<id>' path is "
            "the COMPLETE line-numbered message — read it with "
            "documents.cat(path + '/content.lines') and skim with "
            "documents.head/tail; if the thread did not surface at all, "
            "documents.grep over 'knowledge/conversations' searches EVERY stored "
            "message. Never tell the user a figure or a reply is 'not ingested' "
            "from an excerpt alone — open the cited thread first."
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


# ─── Documents (knowledge VFS) lane ────────────────────────────────────────
#
# Search lanes hand the model bounded EXCERPTS; the grounding rule cites
# 'full: knowledge/conversations/<id>' and says to open it with
# documents.cat / search everything with documents.grep. Until this lane
# existed the chat planner had NO 'documents' service — no catalog entry,
# no dispatch — so the follow-up turn the grounding rule promises could
# never actually run (live 2026-09-13: long threads were excerpts the
# agent could not open). The actions live in core.action_registry
# (documents.ls/cat/grep/tree/head/tail/scan) behind
# ATOM_KNOWLEDGE_VFS_ENABLED; this lane only routes plans to them.

_DOCUMENTS_VFS_INTENT_ACTIONS: Dict[str, str] = {
    "search": "grep", "grep": "grep", "find": "grep",
    "cat": "cat", "read": "cat", "open": "cat", "view": "cat",
    "ls": "ls", "list": "ls",
    "head": "head", "tail": "tail",
    "tree": "tree", "scan": "scan",
}
# One cat call may inject at most this many chars of the COMPLETE message —
# threads run to 79k chars live; the middle stays reachable via grep
# (line + snippet) rather than dumped into the prompt.
_DOCUMENTS_VFS_CAT_CAP = 14_000
_VFS_LEAF_RE = re.compile(
    r"(knowledge/(?:conversations|documents)/[A-Za-z0-9_.+=:-]+"
    r"(?:/(?:content\.lines|meta\.json))?)"
)


def _normalize_vfs_path(raw: str) -> str:
    """Clean VFS path out of a planner query: strips the evidence-line
    'full: ' prefix, quotes/backticks and punctuation, and completes a bare
    message/document id path with its content.lines leaf."""
    m = _VFS_LEAF_RE.search(str(raw or ""))
    if not m:
        return ""
    path = m.group(1)
    if path.count("/") == 2:  # knowledge/<tree>/<id> — add the leaf
        path += "/content.lines"
    return path


def _split_vfs_grep_query(query: str) -> Tuple[str, str]:
    """(pattern, path_prefix) from a grep-shaped query. An optional
    '… in knowledge/conversations' suffix scopes the scan; without one the
    whole knowledge tree is searched (conversations + documents)."""
    text = str(query or "").strip().strip("\"'`")
    m = re.search(
        r"\s+(?:in|under|within)\s+((?:knowledge|documents|conversations)"
        r"(?:/[A-Za-z0-9_.+=:-]+)*)\s*$",
        text, re.IGNORECASE,
    )
    if m:
        prefix = m.group(1).lower()
        if not prefix.startswith("knowledge/"):
            prefix = f"knowledge/{prefix}"
        return text[: m.start()].strip().strip("\"'`"), prefix
    for lead in ("grep ", "search for ", "search ", "find "):
        if text.lower().startswith(lead):
            text = text[len(lead):].strip()
            break
    return text, "knowledge"


async def _documents_vfs_block(
    plan: Any, user_id: Optional[str], context: Optional[Dict[str, Any]]
) -> Optional[str]:
    """Execute a documents.* VFS action and render it as a LIVE TOOL
    RESULTS block. Fault-tolerant: registry failure or a kill-switched VFS
    returns an honest note, never None-with-a-claim."""
    query = (plan.query or "").strip()
    intent = (plan.intent or "grep").lower()
    action = _DOCUMENTS_VFS_INTENT_ACTIONS.get(intent, "grep")
    # A search-shaped plan whose query IS a VFS path is an open request the
    # planner model phrased poorly (live 2026-09-13: "open that full
    # message" → intent=search with the cited path as the query). Reroute
    # to cat deterministically instead of grepping for the path string.
    if action == "grep" and _normalize_vfs_path(query):
        _path = _normalize_vfs_path(query)
        if len(_path) >= 0.6 * max(len(query), 1):
            action = "cat"
    try:
        from core.action_registry import action_registry
        from core.knowledge_vfs_config import knowledge_vfs_enabled

        if not knowledge_vfs_enabled():
            return _with_grounding(
                "LIVE TOOL RESULTS (documents."
                f"{action}, query='{query}'): the knowledge VFS is disabled "
                "(ATOM_KNOWLEDGE_VFS_ENABLED=false)."
            )
        args: Dict[str, Any] = {}
        if action == "grep":
            pattern, prefix = _split_vfs_grep_query(query)
            if not pattern:
                return _with_grounding(
                    "LIVE TOOL RESULTS (documents.grep): no pattern in the "
                    "query — plan grep with the exact string to find."
                )
            args = {"pattern": pattern, "path_prefix": prefix}
        elif action in ("cat", "head", "tail"):
            path = _normalize_vfs_path(query)
            if not path:
                return _with_grounding(
                    f"LIVE TOOL RESULTS (documents.{action}, query='{query}'): "
                    "not a VFS path — expect "
                    "'knowledge/conversations/<id>/content.lines' (the 'full:' "
                    "path cited on mailbox evidence lines)."
                )
            args = {"path": path}
            if action in ("head", "tail"):
                args["lines"] = 60
        else:  # ls / tree / scan
            args = {"path": _normalize_vfs_path(query) or "knowledge/conversations"}
            if action == "tree":
                args["depth"] = 2
        result = await action_registry.execute_action(
            f"documents.{action}",
            args,
            {
                "user_id": user_id,
                "workspace_id": (context or {}).get("workspace_id"),
            },
        )
        if not (result or {}).get("success"):
            reason = str((result or {}).get("message") or (result or {}).get("error") or "failed")
            return _with_grounding(
                f"LIVE TOOL RESULTS (documents.{action}, query='{query}'): "
                f"returned nothing usable ({reason[:140]})."
            )
        if action == "grep":
            matches = (result.get("matches") or [])[:40]
            all_matches = result.get("matches") or []
            head = (
                f"LIVE TOOL RESULTS (documents.grep, pattern="
                f"'{result.get('pattern') or query}', under "
                f"'{args.get('path_prefix')}') — regex scan over the WHOLE "
                f"stored tree ({len(all_matches)} match line(s)"
                f"{' , showing first 40' if len(all_matches) > 40 else ''}); "
                "open any hit's full context with documents.cat(path + "
                "'/content.lines'):\n"
                + "\n".join(
                    f"- {m.get('path')}:L{m.get('line')}: {m.get('snippet')}"
                    for m in matches
                )
            )
            if not matches:
                return _with_grounding(head.rstrip(":") + " — none.")
            # TOP-HIT HYDRATION (same pattern as the outlook leg's full
            # bodies): the turn is one-shot — the reply model cannot chain a
            # cat after a grep, so a narrow result (≤3 distinct messages)
            # carries the top hit's FULL line-numbered text in this same
            # block. Without it the model correctly said "the rest of the
            # body isn't in front of me yet" while the thread sat one call
            # away (live 2026-09-13).
            hydrate = ""
            try:
                uniq = list(dict.fromkeys(
                    str(m.get("path") or "") for m in all_matches
                ))
                if 1 <= len(uniq) <= 3:
                    top = uniq[0]
                    if top.count("/") == 2:
                        top += "/content.lines"
                    cat_res = await action_registry.execute_action(
                        "documents.cat", {"path": top},
                        {
                            "user_id": user_id,
                            "workspace_id": (context or {}).get("workspace_id"),
                        },
                    )
                    content = str((cat_res or {}).get("content") or "")
                    if content.strip():
                        if len(content) > _DOCUMENTS_VFS_CAT_CAP:
                            head_c = int(_DOCUMENTS_VFS_CAT_CAP * 0.62)
                            content = (
                                content[:head_c]
                                + "\n[…middle elided — documents.grep this "
                                "path for a term to locate the middle…]\n"
                                + content[-(_DOCUMENTS_VFS_CAT_CAP - head_c):]
                            )
                        hydrate = (
                            f"\n\nFULL TEXT of the top hit ({top}), "
                            "line-numbered — quote from it:\n" + content
                        )
            except Exception as hydrate_err:  # noqa: BLE001 — hydration is additive
                logger.debug(f"grep top-hit hydration skipped: {hydrate_err}")
            return _with_grounding(head + hydrate)
        if action == "cat":
            content = str(result.get("content") or "")
            if not content.strip():
                return _with_grounding(
                    f"LIVE TOOL RESULTS (documents.cat, path="
                    f"'{args.get('path')}'): no stored message at that path "
                    "(check the id — documents.grep the thread first and cat "
                    "the cited path)."
                )
            line_count = result.get("line_count")
            meta = result.get("meta") or {}
            stamp = (
                f" | received: {str(meta.get('timestamp'))[:19]}"
                if meta.get("timestamp") else ""
            )
            if len(content) > _DOCUMENTS_VFS_CAT_CAP:
                head_c = int(_DOCUMENTS_VFS_CAT_CAP * 0.62)
                content = (
                    content[:head_c]
                    + "\n[…middle elided — the COMPLETE message is "
                    f"{line_count or '?'} lines; documents.grep this path "
                    "for a term to locate the middle…]\n"
                    + content[-(_DOCUMENTS_VFS_CAT_CAP - head_c):]
                )
            return _with_grounding(
                f"LIVE TOOL RESULTS (documents.cat, path='{args.get('path')}')"
                f"{stamp} — COMPLETE stored message, line-numbered "
                f"({line_count or len(content.splitlines())} lines); quote "
                f"line numbers (L#) when citing:\n{content}"
            )
        # ls / tree / scan / head / tail: render the returned payload.
        payload = result.get("tree") or result.get("lines") or result.get(
            "content") or result.get("entries")
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            # ls entries: note nodes FIRST (a truncated listing must say
            # what it is not showing), then compact entry lines.
            notes = [e for e in payload if str(e.get("type")) == "note"]
            rest = [e for e in payload if str(e.get("type")) != "note"]
            shown = [
                "- "
                + (f"{e.get('name')} | from: {(e.get('meta') or {}).get('sender')}"
                   f" | {(e.get('meta') or {}).get('subject') or ''}"
                   f" | {e.get('size')} chars | {str(e.get('modified'))[:19]}"
                   if e.get("meta") else str(e.get("name")))
                for e in rest[:60]
            ]
            count_note = (
                f"\n({len(rest)} entries listed — entries are message ids; "
                "documents.grep finds the right one)"
                if len(rest) > 60 else ""
            )
            payload = "\n".join(
                [str(n.get("name")) for n in notes] + shown
            ) + count_note
        elif isinstance(payload, list):
            payload = "\n".join(str(x) for x in payload[:120])
        return _with_grounding(
            f"LIVE TOOL RESULTS (documents.{action}, path="
            f"'{args.get('path')}'):\n{str(payload)[:8000]}"
        )
    except Exception as e:  # noqa: BLE001 — honest note, never a hang
        logger.warning(f"documents VFS lane failed: {e}")
        return _with_grounding(
            f"LIVE TOOL RESULTS (documents.{action}, query='{query}'): "
            f"execution failed ({str(e)[:140]})."
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


# (2026-09-13 review, P1-1) Internal budget for the automatic search-miss →
# ingest fallback. The fallback's cost is unbounded on its own (resolution
# climbs 4 rungs of Graph forms, each pull can run a vision-LLM describe
# pass per textless image, then the whole evidence collection re-runs) —
# while the lanes around it are hard-budgeted (chat: 45s around
# execute_tool_plan, canvas: 25s around the whole edit lookup). A slow pull
# therefore converted a fast empty search into a caller TIMEOUT that
# discarded the whole evidence block AFTER the memory write had landed.
# The internal budget is strictly smaller than both lane budgets so the
# fallback degrades to the pre-fallback miss path (with an honest note)
# instead of blowing the caller's budget. Env-overridable.
_INGEST_FALLBACK_BUDGET_SECONDS = float(
    os.getenv("ATOM_PLANNER_INGEST_BUDGET_SECONDS", "10") or 10
)


def _ingest_already_attempted(context: Optional[Dict[str, Any]]) -> bool:
    """One governed pull per turn, enforced by STATE, not just by the
    singleflight wrappers around the planner (2026-09-13 review, P3-13):
    a second search-miss in the SAME context (fallback re-runs, sibling
    legs) must not re-pull."""
    return bool((context or {}).get("_ingest_attempted"))


def _mark_ingest_attempted(context: Optional[Dict[str, Any]]) -> None:
    if isinstance(context, dict):
        context["_ingest_attempted"] = True


def _ingest_timeout_note(progress: Optional[Dict[str, Any]]) -> str:
    """Honest evidence-block note when the fallback's internal budget
    expired mid-pull. NEVER silent-write: if the checkpoint dict proves
    content landed, say so and that a re-search will find it; otherwise
    say the outcome is unknown and a re-search will confirm."""
    landed = list((progress or {}).get("landed") or [])
    if landed:
        return (
            "\n\nON-DEMAND PULL (partial): the pull exceeded its internal "
            "time budget mid-run, but the content below WAS pulled into "
            "memory — a re-search (or asking again) will find it:\n"
            + "\n".join(landed)
        )
    return (
        "\n(on-demand pull exceeded its internal time budget and was "
        "abandoned mid-run; if any part of it completed, that content is "
        "now in memory and a re-search will find it — do not claim the "
        "content does not exist)"
    )


def _recent_message_fields(e: Dict[str, Any]) -> tuple:
    """(id, subject, preview, from) for a newest-N message listing row —
    outlook's list_recent_emails and gmail's get_messages shapes folded
    into one, so the rung-4 local matcher below cannot fork per provider."""
    frm = (
        ((e.get("from_field") or {}).get("emailAddress") or {}).get("address")
        or str(e.get("sender") or "")
        or ""
    )
    return (
        str(e.get("id") or ""),
        str(e.get("subject") or ""),
        str(e.get("body_preview") or e.get("snippet") or ""),
        str(frm),
    )


def _match_recent_ids(
    entries, query: str, limit: int
) -> List[str]:
    """Search-free newest-window matching, shared by the outlook AND gmail
    ingest-resolution rung 4: search is the thing that failed, so list the
    newest mail and pick targets locally — ALL figure tokens (canonical
    form) or ≥2 alphabetic terms (the ≥2 guard tightened live 2026-09-12
    after a single common word matched unrelated mail)."""
    fig_canon = [
        _canonical_fig_text(p)
        for p in _distinctive_figure_phrases(query, limit=_FIGURE_PHRASE_LIMIT)
    ]
    fig_canon = [c for c in fig_canon if len(c) >= 4]
    terms = [
        t.lower() for t in re.findall(r"[A-Za-z][A-Za-z-]{3,}", query)
    ][:4]
    ids: List[str] = []
    for mid, subject, preview, frm in entries:
        if not mid:
            continue
        hay = _canonical_fig_text(" ".join([subject, preview, frm]))
        hay_raw = f"{subject} {preview} {frm}".lower()
        term_hits = sum(1 for t in terms if t in hay_raw)
        if (fig_canon and all(c in hay for c in fig_canon)) or (
            not fig_canon and term_hits >= 2
        ):
            if mid not in ids:
                ids.append(mid)
        if len(ids) >= limit:
            break
    return ids


async def _resolve_mailbox_message_ids(
    service: str,
    user_id: Optional[str],
    query: str,
    limit: int = 2,
    *,
    skip_provider_query: bool = False,
) -> List[str]:
    """Message ids for the ingest leg.

    A bare provider id is authoritative and used directly (Graph ids are not
    searchable text). Otherwise resolution climbs the same forms the search
    leg uses — figure phrases as exact phrases, sender-scoped when the query
    names an address, then the per-term fan-out — and, when EVERYTHING
    misses, falls back to a search-free newest-first scan of the mailbox
    matched locally on figure tokens/terms (live 2026-09-12: the ingest
    fallback resolved targets with the same shredded terms that had already
    missed, so "ingest if not found" could never fire for exactly the
    queries that need it). ``skip_provider_query`` is set by the automatic
    search-miss fallback: it has ALREADY run the provider's server-side
    search with this exact query, so re-running it (the old gmail behavior)
    was a dead-end duplicate — both providers go straight to their
    search-free rungs instead. [] only when nothing matches anywhere.
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

    if service == "outlook":
        from integrations.outlook_service import (
            outlook_service,
            sanitize_graph_kql,
        )

        async def _try(coro) -> None:
            try:
                for e in await coro or []:
                    _remember(e.get("id"))
            except Exception as e:  # noqa: BLE001 — each form is best-effort
                logger.debug(f"ingest resolution form failed: {e}")

        # 1) Figure phrases (amounts, codes) as exact phrases.
        for phrase in _distinctive_figure_phrases(query):
            await _try(outlook_service.search_emails(
                user_id=user_id, query=phrase, max_results=5, quote=True))
            if len(ids) >= limit:
                return ids[:limit]
        # 2) Sender-scoped when the query names an address.
        addr_m = _ADDR_IN_QUERY_RE.search(query)
        if addr_m:
            _addr = addr_m.group(0)
            _rest = " ".join(
                t for t in query.replace(_addr, " ").split() if len(t) >= 2
            )[:200]
            await _try(outlook_service.search_emails(
                user_id=user_id, query=_rest, max_results=10, quote=False,
                sender=_addr))
            if len(ids) >= limit:
                return ids[:limit]
        # 3) Per-term fan-out (legacy form).
        for term in ([t for t in query.split() if len(t.strip('"$€£¥₹%,;:()')) >= 2][:3]
                     or [query]):
            kql = sanitize_graph_kql(term)
            if not kql:
                continue
            await _try(outlook_service.search_emails(
                user_id=user_id, query=kql, max_results=5, quote=False))
            if len(ids) >= limit:
                return ids[:limit]
        # 4) Search-free recent-window scan, matched locally: search is the
        # thing that failed, so list newest mail and pick targets by token
        # (shared matcher — gmail rung 4 below uses the same function).
        try:
            recent = await outlook_service.list_recent_emails(
                user_id=user_id, max_results=50)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"recent-window ingest scan failed: {e}")
            recent = []
        for mid in _match_recent_ids(
            (_recent_message_fields(e) for e in recent), query, limit
        ):
            _remember(mid)
        return ids[:limit]

    # Gmail: the server search is AND-semantics but handles figures and
    # addresses natively — ONE query (rung 1, explicit-ingest path; the
    # search-miss fallback skips it — it just ran the same query and
    # missed). Rung 4 mirrors outlook's: newest-N listing + the SHARED
    # local matcher, so a gmail fallback no longer dead-ends at
    # "no candidate" after a duplicate provider search (2026-09-13).
    try:
        from integrations.gmail_service import GmailService

        def _gmail_fetch(q: str, n: int) -> List[Dict[str, Any]]:
            svc = GmailService()
            if not svc.service:
                try:
                    svc._authenticate()
                except Exception:  # noqa: BLE001 — reported as a miss
                    return []
            return svc.get_messages(query=q, max_results=n) or []

        if not skip_provider_query:
            for m in await asyncio.to_thread(_gmail_fetch, query, 5):
                _remember(m.get("id"))
                if len(ids) >= limit:
                    return ids[:limit]
        try:
            recent = await asyncio.to_thread(_gmail_fetch, "", 50)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"gmail recent-window ingest scan failed: {e}")
            recent = []
        for mid in _match_recent_ids(
            (_recent_message_fields(e) for e in recent), query, limit
        ):
            _remember(mid)
            if len(ids) >= limit:
                break
    except Exception as e:  # noqa: BLE001 — the leg reports the miss honestly
        logger.warning(f"mailbox ingest message lookup failed ({service}): {e}")
        return []
    return ids[:limit]


async def _mailbox_ingest_core(
    service: str,
    user_id: Optional[str],
    query: str,
    context: Optional[Dict[str, Any]],
    *,
    progress: Optional[Dict[str, Any]] = None,
    skip_provider_query: bool = False,
) -> Dict[str, Any]:
    """Gate → resolve → ingest for a mailbox, WITHOUT evidence framing.

    Shared by the explicit ``intent=ingest`` plan and the automatic
    search-miss fallback (live 2026-09-11: the agent reported "no such
    email" and asked the user to forward it while the mailbox held it —
    the ingest leg existed but only fired when the planner LLM happened
    to plan that intent). Returns
    ``{"blocked": reason|None, "lines": [...], "ingested_count": n}``;
    ``blocked`` short-circuits (kill switch or autonomy gate) with NO
    write performed.

    ``progress`` (optional caller-owned dict) records every message that
    IS in memory (ingested or already there) the moment it is known — the
    automatic fallback runs under an internal time budget, and when that
    budget expires mid-pull the caller can still report HONESTLY what
    landed instead of silently dropping a write that already happened.
    ``skip_provider_query`` forwards to the resolver for the automatic
    fallback (it already ran the provider search that just missed).
    """
    if not _planner_ingest_enabled():
        return {"blocked": _INGEST_DISABLED_REASON,
                "lines": [], "ingested_count": 0}

    agent_id = (context or {}).get("agent_id")
    try:
        from core.database import get_db_session
        from tools.email_attachment_tool import _gate

        with get_db_session() as db:
            gated = _gate(db, user_id, agent_id)
        if gated:
            return {"blocked": (
                gated.get("reason")
                or "the email_attachment autonomy topic is pinned to review"
            ), "lines": [], "ingested_count": 0}
    except Exception as gate_err:  # noqa: BLE001 — fail-open (reversible write)
        logger.debug(f"mailbox ingest autonomy gate skipped: {gate_err}")

    message_ids = await _resolve_mailbox_message_ids(
        service, user_id, query, skip_provider_query=skip_provider_query
    )
    if not message_ids:
        return {"blocked": None, "lines": [], "ingested_count": 0}

    from integrations.atom_communication_ingestion_pipeline import (
        ingestion_pipeline,
    )

    lines: List[str] = []
    ingested = 0
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
        if status in ("ingested", "already_ingested") and progress is not None:
            # Checkpoint BEFORE the user-facing line is built: a budget
            # timeout between these statements must not lose the fact that
            # this message IS in memory now.
            progress.setdefault("landed", []).append(
                f"- message {short_id}… in memory ({status}) | subject: "
                f"{str(result.get('subject') or '(no subject)')[:100]}"
            )
        if status == "ingested":
            ingested += 1
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
    if ingested:
        # The store changed — the re-search must see this pull, not a
        # cached pre-pull snapshot (P2-8 cache contract).
        invalidate_comms_store_cache()
    return {"blocked": None, "lines": lines, "ingested_count": ingested}


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
    core = await _mailbox_ingest_core(service, user_id, query, context)
    if core["blocked"] == _INGEST_DISABLED_REASON:
        return _with_grounding(
            f"LIVE TOOL RESULTS ({label}): on-demand ingest is disabled by "
            "configuration."
        )
    if core["blocked"]:
        return _with_grounding(
            f"LIVE TOOL RESULTS ({label}): needs owner approval — "
            f"{core['blocked']}"
        )
    if not core["lines"]:
        return _with_grounding(
            f"LIVE TOOL RESULTS ({label}): no matching message found in the "
            "mailbox to ingest."
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
        f"mailbox into memory just now:\n" + "\n".join(core["lines"]) + detail
    )


async def _integration_ingest_core(
    service: str,
    user_id: Optional[str],
    query: str,
    context: Optional[Dict[str, Any]],
    *,
    progress: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Gate → pull for ANY integration, WITHOUT evidence framing — the
    general partner of _mailbox_ingest_core, shared by the explicit
    ``intent=ingest`` plan and the automatic search-miss fallback. Returns
    ``{"blocked": reason|None, "lines": [...], "ingested_count": n,
    "raw": <ingest_integration_content result>|None}``.

    ``progress`` mirrors the mailbox core's contract; the general pull
    resolves in ONE call, so the checkpoint can only say it STARTED — a
    budget timeout mid-call leaves the write outcome genuinely unknown and
    the caller's note words it that way."""
    if not _planner_ingest_enabled():
        return {"blocked": _INGEST_DISABLED_REASON, "lines": [],
                "ingested_count": 0, "raw": None}

    agent_id = (context or {}).get("agent_id")
    try:
        from core.autonomy_policy import OUTCOME_PROPOSE, gate_for_topic
        from core.database import get_db_session

        with get_db_session() as db:
            gate = gate_for_topic(db, user_id, "integration_ingest", agent_id)
        if gate.get("outcome") == OUTCOME_PROPOSE:
            return {"blocked": (
                gate.get("reason")
                or "the integration_ingest autonomy topic is pinned to review"
            ), "lines": [], "ingested_count": 0, "raw": None}
    except Exception as gate_err:  # noqa: BLE001 — fail-open (reversible write)
        logger.debug(f"integration ingest autonomy gate skipped: {gate_err}")

    if progress is not None:
        progress["started"] = True
    try:
        from core.drive_tree_ingestion import ingest_integration_content

        result = await ingest_integration_content(
            service,
            user_id or "",
            query=query,
            workspace_id=(context or {}).get("workspace_id") or "default",
            agent_id=agent_id or "",
        )
    except Exception as e:  # noqa: BLE001 — reported, never raised to the turn
        logger.warning(f"integration ingest failed ({service}): {e}")
        return {"blocked": None, "ingested_count": 0, "raw": None,
                "lines": [f"- nothing ingested ({str(e)[:200]})"]}

    lines: List[str] = []
    ingested = 0
    for item in result.get("items") or []:
        status = str(item.get("status") or "error")
        ident = str(item.get("external_id") or "")[:40]
        if status == "ingested":
            ingested += 1
            extra = (
                item.get("name") or item.get("subject") or item.get("file_name") or ""
            )
            lines.append(
                f"- {ident} INGESTED"
                + (f" | {str(extra)[:100]}" if extra else "")
            )
        elif status == "already_ingested":
            lines.append(f"- {ident} already in memory (no-op)")
        else:
            lines.append(f"- {ident} {status}: {item.get('reason') or ''}".rstrip())
    if not lines:
        lines.append(
            "- nothing ingested ("
            + str(
                result.get("error")
                or result.get("message")
                or "no matching item found"
            )[:200]
            + ")"
        )
    if ingested:
        # Mailbox-strategy pulls write the comms store; record pulls write
        # documents. Dropping the whole cache is cheap and always safe.
        invalidate_comms_store_cache()
    return {"blocked": None, "lines": lines, "ingested_count": ingested,
            "raw": result}


async def _integration_ingest_block(
    service: str,
    user_id: Optional[str],
    query: str,
    context: Optional[Dict[str, Any]],
) -> str:
    """Pull an item's content from ANY connected integration INTO memory.

    The general form of the mailbox leg: drives get the file's bytes (via the
    shared find→open→read leg), record apps (CRM/Books/Inventory/support/PM/…)
    get the matching record(s) rendered to searchable text. Strategy dispatch
    and the idempotency contract live in
    ``core.drive_tree_ingestion.ingest_integration_content``; this function
    owns only the planner's governance and evidence framing.

    Governance: the ``integration_ingest`` autonomy topic (one knob for every
    family), plus the ``ATOM_PLANNER_INGEST_ENABLED`` kill switch.
    """
    label = f"integration ingest, {service}, query='{query}'"
    core = await _integration_ingest_core(service, user_id, query, context)
    if core["blocked"] == _INGEST_DISABLED_REASON:
        return _with_grounding(
            f"LIVE TOOL RESULTS ({label}): on-demand ingest is disabled by "
            "configuration."
        )
    if core["blocked"]:
        return _with_grounding(
            f"LIVE TOOL RESULTS ({label}): needs owner approval — "
            f"{core['blocked']}"
        )
    lines = core["lines"]

    mem_block = await _memory_search_block(user_id, query, context)
    detail = (
        f"\n\nNow in memory:\n{mem_block}"
        if mem_block
        else "\n\n(no indexed excerpt matched the query yet — search memory "
        "again or widen the query)"
    )
    return _with_grounding(
        f"LIVE TOOL RESULTS ({label}) — content pulled from the connected "
        f"integration into memory just now:\n" + "\n".join(lines) + detail
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

    # DATE PIGGYBACK: every downstream lane in this execution (memory
    # figure scan, mailbox lines) reads the window from the context —
    # hand them the planner's resolved mentioned_date once, here.
    if (
        isinstance(context, dict)
        and context.get("mentioned_date") is None
        and getattr(plan, "mentioned_date", None)
    ):
        context["mentioned_date"] = plan.mentioned_date

    # On-demand INGEST: the one write this planner performs. Runs BEFORE the
    # web-query rewrite (the query names an item/message, not a search phrase)
    # and before the search/read legs — the user needs the content pulled from
    # the integration into memory, not another metadata listing. Works for
    # EVERY integration family; mailbox keeps its body+attachments leg.
    if (plan.intent or "") == "ingest" and service not in _INGEST_EXCLUDED_SERVICES:
        if service in _MAILBOX_SERVICES:
            return await _mailbox_ingest_block(service, user_id, query, context)
        return await _integration_ingest_block(service, user_id, query, context)

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

    # Documents (knowledge VFS): open the COMPLETE stored message behind a
    # 'full: knowledge/conversations/<id>' citation, or regex-search EVERY
    # stored message/file. The excerpt lanes above find the thread; this
    # lane is how the agent READS past the excerpt (long quoted threads run
    # to 79k chars — live 2026-09-13 the grounding rule promised
    # documents.cat with no planner lane to run it).
    if service == "documents":
        return await _documents_vfs_block(plan, user_id, context)

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

            tokens = [
                t.strip('"$€£¥₹₩₽₺%,;:()') for t in query.split()
                if len(t.strip('"$€£¥₹₩₽₺%,;:()')) >= 2
            ][:3] or [query]

            async def _collect() -> Dict[str, Dict[str, Any]]:
                """Every live-search form, merged into one ranking pool.
                A closure so the search-miss → on-demand-ingest fallback
                below can re-run the whole collection after pulling new
                mail into memory (ingested copies surface through the
                store leg, fresh Graph state through these legs)."""
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

                # FIGURE PHRASES + SENDER SCOPE (live 2026-09-12, Seguin
                # vendor-cost miss): per-term shredding destroys the only
                # distinctive evidence — "$5,350.00" as one quoted phrase
                # matches the vendor's quote email where every single-term
                # form misses or drowns — and a named sender address scopes
                # the mailbox to their thread ('from:' clauses work in Graph
                # KQL even though a bare '@' term 400s). Both legs merge into
                # the same ranking; sender-scoped hits outrank free-text noise.
                async def _merge_hits(hit_list, boost: int) -> None:
                    for e in hit_list or []:
                        eid = e.get("id")
                        if not eid:
                            continue
                        entry = merged.setdefault(eid, {"email": e, "score": 0, "received": ""})
                        entry["score"] += boost
                        received = str(e.get("received_date_time") or "")
                        if received > entry["received"]:
                            entry["received"] = received

                for phrase in _distinctive_figure_phrases(query):
                    try:
                        phrase_emails = await outlook_service.search_emails(
                            user_id=user_id, query=phrase, max_results=15, quote=True
                        )
                    except Exception as phrase_err:
                        logger.warning(f"outlook phrase search failed ({phrase}): {phrase_err}")
                        continue
                    # Boost cap: rank by DISTINCTIVENESS, not raw length — a
                    # junk 13-char capture used to outrank genuine term hits.
                    await _merge_hits(
                        phrase_emails, boost=min(len(phrase), _PHRASE_BOOST_CAP)
                    )
                _addr_in_query = _ADDR_IN_QUERY_RE.search(query)
                if _addr_in_query:
                    _addr = _addr_in_query.group(0)
                    _rest = " ".join(
                        t for t in query.replace(_addr, " ").split() if len(t) >= 2
                    )[:200]
                    try:
                        scoped_emails = await outlook_service.search_emails(
                            user_id=user_id,
                            query=_rest,
                            max_results=25,
                            quote=False,
                            sender=_addr,
                        )
                    except Exception as scoped_err:
                        logger.warning(f"outlook sender-scoped search failed ({_addr}): {scoped_err}")
                        scoped_emails = []
                    await _merge_hits(scoped_emails, boost=40)
                return merged

            def _rank(entry: Dict[str, Any]):
                # Multi-term matches first, then newest — stable and cheap.
                return (-entry["score"], entry["received"], )

            merged = await _collect()
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

            ingest_note = ""
            if not emails and not store_lines:
                # SEARCH-MISS → ON-DEMAND INGEST (live 2026-09-11: the agent
                # answered "no such email — forward it to me" while the
                # message sat in the mailbox): one governed pull of the
                # query's targets into memory, then a single re-search.
                # Gate-respecting (kill switch / autonomy approval return a
                # note, never a write), bounded to ONE attempt per turn
                # (state flag — see _ingest_already_attempted), and run
                # under an INTERNAL time budget smaller than the lane
                # budgets so a slow pull degrades to this miss path with an
                # honest note instead of a caller timeout that discards the
                # evidence block after the write landed.
                if not _ingest_already_attempted(context):
                    _mark_ingest_attempted(context)
                    _progress: Dict[str, Any] = {}
                    ing_core: Optional[Dict[str, Any]] = None
                    try:
                        ing_core = await asyncio.wait_for(
                            _mailbox_ingest_core(
                                "outlook", user_id, query, context,
                                progress=_progress,
                                skip_provider_query=False,
                            ),
                            timeout=_INGEST_FALLBACK_BUDGET_SECONDS,
                        )
                    except asyncio.TimeoutError:
                        logger.warning(
                            "outlook ingest fallback exceeded its internal "
                            f"budget of {_INGEST_FALLBACK_BUDGET_SECONDS}s — "
                            "degrading to the miss path with a note"
                        )
                    except Exception as ing_err:  # noqa: BLE001 — fallback must not break the leg
                        logger.warning(f"outlook ingest fallback failed: {ing_err}")
                        ing_core = {"blocked": None, "lines": [], "ingested_count": 0}
                    if ing_core is None:
                        # Budget expired mid-pull: pre-fallback miss path +
                        # the honest note about what landed (never a silent
                        # write).
                        ingest_note = _ingest_timeout_note(_progress)
                    elif ing_core["blocked"] == _INGEST_DISABLED_REASON:
                        pass
                    elif ing_core["blocked"]:
                        ingest_note = (
                            f"\n(on-demand mailbox pull available but needs owner "
                            f"approval — {ing_core['blocked']})"
                        )
                    elif ing_core["ingested_count"]:
                        ingest_note = (
                            "\n\nON-DEMAND PULL: the mailbox search missed, so "
                            f"{ing_core['ingested_count']} message(s) were pulled "
                            "from the connected mailbox into memory and the search "
                            "re-ran:\n" + "\n".join(ing_core["lines"])
                        )
                        merged = await _collect()
                        ranked = sorted(merged.values(), key=_rank)
                        emails = [x["email"] for x in ranked[:8]]
                        full_bodies = await _outlook_full_bodies(
                            user_id, emails,
                            _OUTLOOK_READ_HYDRATE if read_mode else _OUTLOOK_SEARCH_HYDRATE,
                            body_cap,
                        )
                        store_lines = await _ingested_mailbox_lines(user_id, query, context)
                    else:
                        ingest_note = (
                            "\n(on-demand mailbox pull ran but found no candidate "
                            "message to ingest)"
                            if not ing_core["lines"] else
                            "\n(on-demand mailbox pull ran: its candidates are "
                            "already in memory — no new content above)"
                        )

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
                        f"Ingested-workspace matches:\n{mem_block}{ingest_note}"
                    )
                return _with_grounding(
                    f"LIVE TOOL RESULTS ({tool_label}, query='{query}'): "
                    "no matching messages in the mailbox or ingested memory."
                    f"{ingest_note}"
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

            # EXACT-FIGURE pointer: the deterministic store lines match the
            # query's amount verbatim (with MATCH windows and '--- Attachments
            # ---' lists), but they sit ABOVE several thousand chars of Graph
            # full bodies whose elision markers read like truncation — a
            # flash-tier reply model answered "the figure isn't visible in the
            # truncated results" while the figure led the block (live
            # 2026-09-13). Name the lines so no reader misses them.
            _fig_note = ""
            _fig_ph = _distinctive_figure_phrases(query)
            if _fig_ph and store_lines:
                _fig_note = (
                    "EXACT-FIGURE MATCHES (deterministic, verbatim in the stored "
                    f"copies — quote the amount and any '--- Attachments ---' "
                    f"names from these [ingested mailbox] lines, not from "
                    f"truncated live previews): {'; '.join(_fig_ph)}\n"
                )
            listing = _fig_note + "\n".join(store_lines)
            graph_listing = "\n".join(_graph_line(e) for e in emails[:6])
            if graph_listing:
                listing = (listing + "\n" if listing else "") + graph_listing
            if emails and len(full_bodies) < min(len(emails), 6):
                listing += (
                    "\n(preview-only lines above: plan outlook again with "
                    "intent=read and the same query to pull those full bodies)"
                )
            listing += ingest_note
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
            # skip_pathlike: a URL path is not a catalog code, and appended
            # it pushed the Zoho search_text past its 100-char cap — the
            # 400-aborted lookup of 2026-09-13 (canvas a1a13834).
            extra = _context_identifier_net(
                context or {}, query, skip_pathlike=True)
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
            _search_ctx = {
                "user_id": user_id,
                "workspace_id": "default",
                "tenant_id": tenant_id,
                # The acting agent — tool-error signals attach to its
                # running execution so episodes see them.
                "agent_id": (context or {}).get("agent_id"),
            }

            async def _run_call():
                return await svc.search(service, query, context=dict(_search_ctx))
        else:
            _search_ctx = {
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
            }

            async def _run_call():
                return await svc.execute(
                    service, action, {"query": query, "limit": 8},
                    context=dict(_search_ctx),
                )
        result = await _run_call()
        data = result.get("data") if isinstance(result, dict) else None

        # SEARCH-MISS → ON-DEMAND INGEST (generalized from the outlook leg,
        # live 2026-09-11 Seguin incident): an EMPTY live search is exactly
        # when the content may exist upstream but not be in memory yet —
        # pull it (governed: kill switch + autonomy gate, one attempt,
        # idempotent) and re-run the same call once before any dead end.
        ingest_note = ""
        if (
            result.get("status") == "success"
            and not data
            and (plan.intent or "search") == "search"
            and service not in _INGEST_EXCLUDED_SERVICES
        ):
            # Same one-attempt-per-turn state flag and INTERNAL budget as
            # the outlook leg (P1-1/P3-13): a slow pull degrades to this
            # miss path with an honest note, never a caller timeout.
            if not _ingest_already_attempted(context):
                _mark_ingest_attempted(context)
                _progress: Dict[str, Any] = {}
                ing_core: Optional[Dict[str, Any]] = None
                try:
                    if service in _MAILBOX_SERVICES:
                        ing_core = await asyncio.wait_for(
                            _mailbox_ingest_core(
                                service, user_id, query, context,
                                progress=_progress,
                                skip_provider_query=True,
                            ),
                            timeout=_INGEST_FALLBACK_BUDGET_SECONDS,
                        )
                    else:
                        ing_core = await asyncio.wait_for(
                            _integration_ingest_core(
                                service, user_id, query, context,
                                progress=_progress,
                            ),
                            timeout=_INGEST_FALLBACK_BUDGET_SECONDS,
                        )
                except asyncio.TimeoutError:
                    logger.warning(
                        f"{service} ingest fallback exceeded its internal "
                        f"budget of {_INGEST_FALLBACK_BUDGET_SECONDS}s — "
                        "degrading to the miss path with a note"
                    )
                except Exception as ing_err:  # noqa: BLE001 — fallback never breaks the leg
                    logger.warning(f"universal ingest fallback failed ({service}): {ing_err}")
                    ing_core = {"blocked": None, "lines": [], "ingested_count": 0}
                if ing_core is None:
                    ingest_note = _ingest_timeout_note(_progress)
                elif ing_core["blocked"] == _INGEST_DISABLED_REASON:
                    pass
                elif ing_core["blocked"]:
                    ingest_note = (
                        f"\n(on-demand pull available but needs owner approval "
                        f"— {ing_core['blocked']})"
                    )
                elif ing_core["ingested_count"]:
                    ingest_note = (
                        f"\n\nON-DEMAND PULL: the live {service} search found "
                        f"nothing, so {ing_core['ingested_count']} item(s) were "
                        "pulled from the integration into memory and the search "
                        "re-ran:\n" + "\n".join(ing_core["lines"])
                    )
                    result = await _run_call()
                    data = result.get("data") if isinstance(result, dict) else None
                else:
                    ingest_note = (
                        "\n(on-demand pull ran but found nothing upstream to "
                        "ingest for this query)"
                    )

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
                        + ingest_note
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
                    f"{ingest_note}"
                )
            return _with_grounding(
                f"LIVE TOOL RESULTS ({service}.{action}, query='{query}'): "
                f"returned nothing usable ({reason}).{ingest_note}"
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
        if ingest_note:
            header += ingest_note
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
