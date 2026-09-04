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
import asyncio
import logging
import re
from pathlib import Path
import os
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
for _storage_svc in _STORAGE_SERVICES:
    _INTENT_ACTIONS[_storage_svc] = {
        "search": "search",
        "list": "list",
        "read": "read_file",
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
    "zoho_inventory": "stock inventory — search items by name or SKU and check what is in stock",
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
_ALWAYS_AVAILABLE_SERVICES = ("memory",)


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
- Read-only: search/list intents for lookups; `read` intent ONLY for the
  file-storage services, when the user asks to OPEN a named file or read a
  specific row/value out of it ("open the price list and find the WG350DSAV
  row" → service zoho_workdrive, intent read, query "Consolidated Price List
  WG350DSAV"). Never plan sends, writes, or deletes.
- If the conversation or memory already clearly answers it, use_tool=false.
- Questions about a company/person/website the conversation cannot answer
  from its own content need web_search (topic facts) or web_fetch (read a
  specific site). Only conclude "no lookup needed" when the answer is
  genuinely already present.
- If the needed integration is NOT in the available list, use_tool=false and
  say which integration is missing in `reason`."""

# Pin the planner to a known-reachable vetted model: unpinned "auto" routing
# prefers the free local Ollama client by value, which is frequently
# unreachable — the structured path retries then fails, and the whole plan
# is lost. Planner prompts are tiny; the cheap vetted workhorse is ideal.
PLANNER_MODEL = os.getenv("ATOM_TOOL_PLANNER_MODEL", "qwen/qwen3.7-flash")


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
    from core.llm_service import LLMService

    # Pin (provider, model): `model=` on generate_structured maps to
    # task_type, NOT model selection — unpinned routing preferred the free
    # local Ollama client by value, which is frequently unreachable; the
    # connection-error retries ate ~6s and often lost the plan entirely.
    # generate_structured_response forwards provider_model into the handler,
    # pinning the option list to one reachable (provider, model).
    kwargs: Dict[str, Any] = {}
    try:
        if "openrouter" in llm_service._get_handler().clients:
            kwargs["provider_model"] = ("openrouter", PLANNER_MODEL)
    except Exception:
        pass

    plan = await llm_service.generate_structured_response(
        disable_reasoning=True,
        prompt=prompt,
        response_model=ToolPlan,
        system_instruction="You return only the requested JSON object.",
        temperature=0.0,
        **kwargs,
    )
    if plan is None:
        return None
    if plan.use_tool:
        allowed = set(connected) | set(_available_platform_services())
        if not plan.service or plan.service not in allowed:
            # Planner models emit service names in loose forms ("Zoho CRM",
            # "zoho-inventory") — normalize separators/case against the
            # allowed set before treating the plan as invalid.
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
            # null/unknown service on vague retries ("try again"). Three
            # deterministic recoveries before giving up — a dead plan here
            # made the model answer from memory while CLAIMING it had
            # "rechecked" the mailbox (observed live 2026-09-02).
            #
            # Order matters: the user's OWN WORDS outrank conversation
            # history. History-first rerouted "check consolidated price list
            # FILE again" to the recently-used mailbox (live 2026-09-03
            # 20:11) because earlier turns mentioned outlook — when the
            # message's named entity (a file → storage) pointed at
            # zoho_workdrive. Named-entity first, history only for messages
            # that name nothing.
            named = _service_named_in_message(message, connected)
            if named and plan.service is None:
                logger.info(
                    f"tool planner: null service — user message names "
                    f"connected {named!r}")
                plan.service = named
                plan.intent = "search"
                if not (plan.query or "").strip():
                    plan.query = message[:120]
            elif (fallback := _fallback_service_from_history(history, connected, message)) and plan.service is None:
                logger.info(
                    f"tool planner: invalid service ({plan.service!r}) — "
                    f"falling back to recently used {fallback!r}")
                plan.service = fallback
                plan.intent = "search"
                if not (plan.query or "").strip() or len(plan.query.strip()) < 12:
                    plan.query = _retry_query_from_history(history, message)
            elif plan.service is None and "memory" in allowed:
                # Last rung, only for the planner's null-service flake: the
                # model couldn't name ANY service. memory is always available
                # and searches the workspace's OWN ingested data. Dropping the
                # plan here made the model answer "I don't have that file"
                # from a memory context whose legs had timed out — while the
                # document sat fully indexed (live 2026-09-03: Consolidated
                # Price List 2019.xlsx). A NAMED but unavailable service
                # (key-gated web tools, unconnected integrations) still
                # dead-ends below so the missing dependency stays visible.
                logger.info(
                    f"tool planner: invalid service ({plan.service!r}) — "
                    f"falling back to always-available memory search")
                plan.service = "memory"
                plan.intent = "search"
                if not (plan.query or "").strip():
                    plan.query = message[:120]
            else:
                logger.info(f"tool planner: service not connected ({plan.service!r}): {plan.reason[:80]}")
                return None
        allowed_intents = {"search", "list"}
        if plan.service in _STORAGE_SERVICES:
            allowed_intents.add("read")
        if plan.intent not in allowed_intents:
            plan.intent = "search"
        if not (plan.query or "").strip():
            plan.query = message[:120]
    return plan


_RETRY_IMPERATIVE = re.compile(
    r"\b(try again|again|keep looking|recheck|re-check|search again|"
    r"look again|find it)\b", re.IGNORECASE,
)

# Explicit "OPEN the file" language. When the user's words ask to open/read a
# document — not just locate it — a storage `search` (metadata only) cannot
# satisfy the ask; the plan upgrades to the `read` intent, which downloads
# the file, extracts its contents, and returns a query-anchored excerpt.
# Hybrid/memory search stays the fast path for lookups that DON'T name
# opening ("what's the price of X?" → search first).
_EXPLICIT_OPEN = re.compile(
    r"\b(open|look inside|contents of|find the row|show me the row|"
    r"the row for|locate the row|exact row)\b",
    re.IGNORECASE,
)


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


def _service_named_in_message(
    message: str, connected: List[str]
) -> Optional[str]:
    """The connected integration the user's own words name, if any. Matches
    service names with separators relaxed ("zoho inventory" matches
    zoho_inventory); longest name wins when several appear. Falls back to
    FILE-NOUN matching: "check the inventory workbook / client spreadsheet /
    catalog file" names a document, and documents live in whichever storage
    integration is connected (deterministic preference order, most-specific
    first). A deterministic repair for the planner's null-service flake —
    NOT an intent gate: it never fires when the planner named a valid
    service itself."""
    msg = f" {message.lower().replace('-', ' ').replace('_', ' ')} "
    best, best_len = None, 0
    for svc in connected:
        name = svc.lower().replace("_", " ")
        if name in msg and len(name) > best_len:
            best, best_len = svc, len(name)
    if best:
        return best
    # File nouns → connected storage service. These words say "the thing I
    # mean is a DOCUMENT" without naming the vendor — route to wherever this
    # user's documents live instead of whatever service was used recently.
    _FILE_NOUNS = (
        "workbook", "spreadsheet", "xlsx", "worksheet",
        "file", "document", "docx", "pdf", "catalog", "invoice", "contract",
        "deck", "presentation", "proposal",
    )
    if any(noun in msg for noun in _FILE_NOUNS):
        for storage in ("zoho_workdrive", "google_drive", "onedrive",
                        "dropbox", "box", "notion"):
            if storage in connected:
                return storage
    return best


def _fallback_service_from_history(
    history: List[Dict[str, Any]], connected: List[str], message: str = "",
) -> Optional[str]:
    """Retry continuity for 'try again' after a failed tool turn: the most
    recently mentioned connected service, scanning ALL string values of the
    history entries (schemas vary). A bare retry imperative with no service
    mentioned anywhere still defaults to the connected mailbox — a retry
    means 'retry what you just did', and the mailbox is what an email
    question was doing."""
    import re as _re

    for entry in reversed(history or []):
        text = _entry_text(entry).lower()
        for svc in connected:
            # Word-boundary match so "mail" doesn't match "gmail" etc.
            if _re.search(rf"\b{_re.escape(svc)}\b", text):
                return svc
    if _RETRY_IMPERATIVE.search(message or ""):
        for preferred in ("outlook", "gmail"):
            if preferred in connected:
                return preferred
        return connected[0] if connected else None
    return None


def _retry_query_from_history(
    history: List[Dict[str, Any]], message: str
) -> str:
    """For bare retry imperatives ('try again'), the query is the previous
    SUBSTANTIVE user message — 'try again' itself carries nothing to
    search for."""
    msg_l = (message or "").strip().lower()
    for entry in reversed(history or []):
        if not isinstance(entry, dict) or entry.get("role") != "user":
            continue
        text = str(entry.get("content") or "").strip()
        if text and text.lower() != msg_l and len(text) >= 12:
            return text[:200]
    return (message or "")[:200]


def _search_ingested_by_address(user_id, address, limit=4):
    """Deterministic LanceDB lookup of ingested messages tied to an email
    address (sender/recipient/content containment). Graph free-text search
    does not reliably match sender ADDRESSES (live 2026-09-02: Jacob Schulz's
    reply never surfaced because 'jschulz' is only the local part of the
    sender address) — the ingested copy is authoritative here and needs no
    embeddings. Fault-isolated; [] on anything."""
    out = []
    if not address or "@" not in address:
        return out
    try:
        import lancedb

        base = Path(__file__).resolve().parent.parent / "data" / "atom_memory"
        db = lancedb.connect(str(base / "default"))
        table = db.open_table("atom_communications")
        df = table.to_arrow().to_pandas()
        addr_l = address.lower()
        for _, row in df.iterrows():
            blob = " ".join(
                str(row.get(c) or "") for c in ("sender", "recipient", "content", "subject")
            ).lower()
            if addr_l in blob:
                out.append(
                    f"- [ingested mailbox] From: {row.get('sender')} | "
                    f"{str(row.get('subject') or '')[:90]} | "
                    f"{str(row.get('content') or '')[:260]} | "
                    f"{str(row.get('timestamp') or '')[:19]}"
                )
                if len(out) >= limit:
                    break
    except Exception as e:
        logger.debug(f"ingested address search skipped: {e}")
    return out


_PRODUCT_TOKEN_RE = re.compile(
    r"\b(?=[A-Za-z-]*\d)(?=[A-Za-z0-9-]*[A-Za-z])[A-Za-z0-9][A-Za-z0-9-]{4,}\b"
)
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
                    out.append(
                        f"- [document: {name}{fresh}] EXACT MATCH for '{tok}': "
                        f"…{excerpt}…"
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


def _doc_hit_excerpt(doc_id: str, query: str, fallback: str, width: int = 600) -> tuple:
    """Query-anchored excerpt from the FULL stored text of a file-ingest row
    (documents table), with the ingestion date for freshness stamping.
    Falls back to the short preview for rows that are not LanceDB file
    ingests (PG-bridged records, conversations). Returns (excerpt, ingested_date).
    Pricing/values can change at the source — the date is what lets the
    agent (and the user) see how fresh a quoted figure is."""
    ingested_date = ""
    try:
        import lancedb

        base = Path(__file__).resolve().parent.parent / "data" / "atom_memory"
        table = lancedb.connect(str(base / "default")).open_table("documents")
        df = table.to_arrow().to_pandas()
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
                hid, excerpt_corpus, fallback_preview
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
            for _line in _search_ingested_by_address(user_id, _addr):
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
            _l for _l in _search_ingested_by_exact_token(
                user_id, query, skip_ids=seen_ids)
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


async def execute_tool_plan(
    plan: ToolPlan,
    user_id: Optional[str],
    tenant_id: str = "default",
    context: Optional[Dict[str, Any]] = None,
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
                if err:
                    return _with_grounding(
                        f"LIVE TOOL RESULTS (web_search, query='{query}'): unavailable — {err[:200]}"
                    )
                answer = str(res.get("answer") or "").strip()
                results = res.get("results") or []
                if not answer and not results:
                    return _with_grounding(
                        f"LIVE TOOL RESULTS (web_search, query='{query}'): no results found."
                    )
                lines = []
                if answer:
                    lines.append(f"Summary: {answer[:800]}")
                for r in results[:5]:
                    lines.append(
                        f"- {str(r.get('title') or '(untitled)')[:120]} | {str(r.get('url') or '')[:160]}\n"
                        f"  {str(r.get('content') or '')[:400]}"
                    )
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

            # SECOND SOURCE — the ingested mailbox memory. Graph free-text
            # $search does not reliably match sender ADDRESSES or nicknames
            # (live 2026-09-02: "find Jason's response" — the sender is
            # "Jacob" Schulz, and the address local-part 'jschulz' never
            # matched), while the ingested copy carries the full content
            # plus sender/recipient fields. Supplement, don't replace.
            store_lines: List[str] = []
            try:
                from core.hybrid_search.documents_hybrid import (
                    DocumentsHybridSearch,
                )

                store_result = await DocumentsHybridSearch().search(
                    query=query[:200], limit=6, owner_user_id=user_id
                )
                seen_subjects = {
                    str(e.get("subject") or "").strip().lower() for e in emails
                }
                for hit in (store_result or {}).get("results") or []:
                    if str(hit.get("source") or "") != "communication":
                        continue
                    sender = str(hit.get("sender") or "?")
                    title = str(hit.get("title") or "")
                    snippet = str(hit.get("preview") or "")[:220]
                    ts = str(hit.get("as_of") or "")
                    store_lines.append(
                        f"- [ingested mailbox] From: {sender} | {title} | {snippet} | {ts}"
                    )
                    if len(store_lines) >= 4:
                        break
            except Exception as store_err:
                logger.debug(f"comms-store supplement skipped: {store_err}")

            # Address fragments get a DETERMINISTIC ingested lookup —
            # nicknames ("Jason" vs "Jacob") and Graph's address indexing
            # both miss these. The user's message often lacks the address
            # ("find Jason's response"), but the surrounding conversation
            # carries it — scan the recent history too.
            import re as _re_addr

            _addr_haystack = query + " " + " ".join(
                _entry_text(m) for m in ((context or {}).get("history") or [])[-6:]
            )
            for _addr in _re_addr.findall(r"[\w.+-]+@[\w.-]+", _addr_haystack):
                for _line in _search_ingested_by_address(user_id, _addr):
                    if _line not in store_lines:
                        store_lines.append(_line)
                        if len(store_lines) >= 6:
                            break
                if len(store_lines) >= 6:
                    break

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
                        f"LIVE TOOL RESULTS (outlook.search_emails, query='{query}'): "
                        f"no matching messages in the mailbox. "
                        f"Ingested-workspace matches:\n{mem_block}"
                    )
                return _with_grounding(
                    f"LIVE TOOL RESULTS (outlook.search_emails, query='{query}'): "
                    "no matching messages in the mailbox or ingested memory."
                )
            listing = "\n".join(
                f"- From: {((e.get('from_field') or {}).get('emailAddress') or {}).get('address') or '?'} | "
                f"{str(e.get('subject') or '(no subject)')[:120]} | "
                f"{str(e.get('body_preview') or '')[:200]} | "
                f"received: {str(e.get('received_date_time'))[:19]}"
                for e in emails[:6]
            )
            if store_lines:
                listing = (listing + "\n" if listing else "") + "\n".join(store_lines)
            return _with_grounding(
                f"LIVE TOOL RESULTS (outlook.search_emails, query='{query}') — "
                f"use these to answer:\n{listing}"
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

        # Search→read auto-chain: storage search planned, but the user's
        # words explicitly asked to OPEN the file ("check the price list file
        # again and see if you can find the row") — metadata results cannot
        # answer that, so upgrade to the read intent (download + extract +
        # excerpt). Only fires for storage services; other apps keep search.
        if service in _STORAGE_SERVICES and (plan.intent or "search") == "search":
            if _EXPLICIT_OPEN.search(f"{query} {_current_message_text(context)}"):
                logger.info(
                    f"tool chain: explicit open language — upgrading "
                    f"{service}.search to read_file")
                plan.intent = "read"

        # CONTEXT TOKEN ENRICHMENT — storage legs. The fallback queries
        # inherit the current message's wording ("check the catalog file
        # again and find the row") and drop the identifier that only exists
        # in the conversation/canvas — the read excerpt then anchors on
        # header boilerplate and the row stays invisible (live 2026-09-04:
        # three consecutive turns). Scan the hydrated context for identifier
        # tokens deterministically instead of hoping the planner LLM
        # includes them. Intent text (message + history) is scanned first
        # and wins; canvas markup is scanned second with hex-style tokens
        # excluded (canvas styling is layout noise, not catalog codes). At
        # most two tokens join the query — enough to identify, few enough
        # to keep server-side storage search selective.
        if service in _STORAGE_SERVICES:
            ctx = context or {}
            intent_hay = " ".join(
                [query, _current_message_text(ctx)]
                + [_entry_text(m) for m in (ctx.get("history") or [])[-8:]]
            )
            extra = [
                t for t in _product_tokens(intent_hay, min_len=6)
                if t.lower() not in query.lower()
            ]
            if len(extra) < 2:
                canvas_hay = _entry_text(ctx.get("canvas") or {})
                taken = {t.lower() for t in extra} | {
                    w.lower() for w in query.split()
                }
                extra += [
                    t for t in _product_tokens(canvas_hay, min_len=6,
                                               skip_hexlike=True)
                    if t.lower() not in taken
                ]
            extra = extra[:2]
            if extra:
                logger.info(f"tool query enriched with context tokens {extra!r}")
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
        return _with_grounding(header)
    except Exception as e:
        logger.warning(f"tool execution failed for {service}.{plan.intent}: {e}")
        return None
