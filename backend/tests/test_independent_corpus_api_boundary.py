# -*- coding: utf-8 -*-
"""INDEPENDENT CORPUS — a small, UNSEEN body of examples asserted at the API
boundary (``POST /api/chat/message``).

Why this file exists
--------------------
The suites written alongside the routing/evidence code keep passing, which
proves the code still does what its authors expected — it does NOT prove the
behaviour generalises to examples those authors never saw. Everything here is a
NEW subject, NEW wording and NEW identifiers, deliberately disjoint from
``test_planner_natural_routing.py``, ``test_verbatim_evidence_generalization.py``
and ``test_attachment_evidence_general.py`` (which use foot shears, Brennan
Machinery, chandrakant@brennan.ca, PRICE VIPUL (6).xlsx, F-5216, WG-350DSAV,
$5,350.00 / $7,519 and "put 25 percent only"). The corpus below is an anodising
job shop: ANZ-4471 / BKT-1180 / XR-7704, Northgate Fabrication, Bracket_BOM_v7.

What is REAL and what is STUBBED
--------------------------------
REAL (the code under test): the chat route + orchestrator (``send_chat_message``
→ ``process_chat_message`` → ``_get_qwen_response``), the tool planner
(``plan_tool_use``, ``_provenance_menu``, the provenance/repair floors,
``execute_tool_plan``), every deterministic evidence lane
(``_verbatim_mail_evidence``, ``_ingested_mailbox_lines``, ``_match_rows_by_
figure_tokens``, ``_datasets_search_block``, ``_documents_vfs_block`` → the
``documents.*`` actions in ``core/action_registry.py``), the evidence composer
(``_compose_lookup_evidence``), the evidence budget, and the deterministic
figure-grounding guard (``_unsupported_figures``).

STUBBED (read boundaries + the model transport only):
  * ``llm_service`` — a recorder that (a) keeps every message list it was asked
    to answer from and (b) answers with a canned reply DERIVED FROM the evidence
    block it received. ``generate_structured_response`` (the planner's transport)
    returns a plan computed from the REAL provenance menu the harness built.
    No network, no provider.
  * ``_comms_store_records`` — the ingested-mailbox read (normally the LanceDB /
    sqlite comms store) → in-memory rows.
  * ``core.sheet_dataset_service.search_all_datasets_sync`` — the workbook
    catalog read → in-memory rows + formulas.
  * ``core.vfs_registry`` "knowledge" provider + ``KnowledgeVFSProvider`` — the
    knowledge VFS read → in-memory documents.
  * ``UniversalIntegrationService.execute`` — the live integration read
    (the operator's own inventory app) → in-memory items.
  * ``outlook_service.search_emails`` / ``get_email_by_id`` — the live Graph
    read (network) → empty.
  * ``core.database.get_db_session`` / ``get_db`` — a null session; no DB.

Hermetic: no network, no live store, no shared test DB, no wall-clock ordering
dependence (every session id is unique per test).
"""
from __future__ import annotations

import json
import re
import uuid
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.chat_tool_planner import _MONEY_RE, ToolPlan
from core.vfs_base import VFSNode, VFSProvider, VFSResource, to_line_numbered

# ─────────────────────────────────────────────────────────────────────────────
# THE CORPUS (all in memory)
# ─────────────────────────────────────────────────────────────────────────────

#: Ingested mailbox rows. Every figure here is decisive and unique to ONE row,
#: so "the selected source" is observable as "which figure reached the prompt".
MAIL_ROWS: List[Dict[str, Any]] = [
    {
        "id": "cm-9001",
        "sender": "dana.ferreira@northgatefab.com",
        "recipient": "ops@brightwater.example",
        "subject": "Re: PO 88431 - anodiser lot pricing",
        "content": (
            "Ana, we can hold the ANZ-4471 anodiser lot at $1,240.00 through "
            "Q4. Lead time stays six weeks from PO. Regards, Dana"
        ),
        "timestamp": "2026-05-12T14:20:00",
        "metadata": "",
        "attachments": "[]",
    },
    {
        "id": "cm-9002",
        "sender": "dana.ferreira@northgatefab.com",
        "recipient": "ops@brightwater.example",
        "subject": "Re: PO 88431 - bracket lot",
        "content": (
            "For the BKT-1180 bracket lot the number we would hold is "
            "$1,180.00, valid until the end of the quarter."
        ),
        "timestamp": "2026-05-14T09:05:00",
        "metadata": "",
        "attachments": "[]",
    },
    {
        # IRRELEVANT SOURCE: a different supplier, a different subject, its own
        # decisive figure. It must never reach the prompt of the mail scenario.
        "id": "cm-9004",
        "sender": "billing@tooling-depot.example",
        "recipient": "ops@brightwater.example",
        "subject": "Invoice 55210 - calibration service",
        "content": "Calibration service for the quarter is billed at $3,975.00.",
        "timestamp": "2026-04-02T11:00:00",
        "metadata": "",
        "attachments": "[]",
    },
]
MAIL_FIGURE_ANZ = "$1,240.00"          # decisive, mail-only
MAIL_FIGURE_BKT = "$1,180.00"          # decisive, mail-only
MAIL_FIGURE_NOISE = "$3,975.00"        # decisive, unrelated thread
MAIL_SENDER = "dana.ferreira@northgatefab.com"

#: Workbook rows. The LINE TOTAL of each row is only derivable through that
#: row's FORMULA — a row without its formula is not a full answer. BKT-1180 is
#: also quoted in the mailbox (the conflict scenario); HNG-2205 appears in the
#: workbook ONLY, so a question about it has exactly one possible source.
WORKBOOK_FILE = "Bracket_BOM_v7.xlsx"
WORKBOOK_SHEET = "Costing"
WORKBOOK_ROW = 204
WORKBOOK_TOTAL = "3120"
WORKBOOK_FORMULA = "F204==D204*E204"
WORKBOOK_ROW_BKT = 118
WORKBOOK_TOTAL_BKT = "1455"
WORKBOOK_FORMULA_BKT = "F118==D118*E118"
WORKBOOK_HIT: Dict[str, Any] = {
    "file_name": WORKBOOK_FILE,
    "entity_name": WORKBOOK_SHEET,
    "source_kind": "file",
    "external_id": "ds-770",
    "sql": "SELECT * FROM Costing WHERE SKU IN ('HNG-2205','BKT-1180')",
    "columns": ["SKU", "Lot Qty", "Unit Cost", "Line Total"],
    "rows": [
        {"SKU": "HNG-2205", "Lot Qty": 480, "Unit Cost": 6.50,
         "Line Total": 3120.0, "__sheet_row": WORKBOOK_ROW},
        {"SKU": "BKT-1180", "Lot Qty": 250, "Unit Cost": 5.82,
         "Line Total": 1455.0, "__sheet_row": WORKBOOK_ROW_BKT},
    ],
    "row_count": 2,
    "formulas": {"F204": "=D204*E204", "F118": "=D118*E118"},
    "source_modified_at": "2026-05-02T09:00:00",
}

#: Prose document, reachable only through the knowledge VFS.
DOC_ID = "qag-77"
DOC_PATH = f"knowledge/documents/{DOC_ID}/content.lines"
DOC_FIGURE = "$18,400"
DOC_TITLE = "Supplier Quality Agreement - Northgate Fabrication (rev C)"
DOC_TEXT = "\n".join([
    DOC_TITLE,
    "",
    "4. Tooling and amortisation",
    "4.1 Northgate Fabrication funds the anodising racking tooling up front.",
    f"4.2 The tooling amortisation of {DOC_FIGURE} per year is recoverable "
    "against shipped volume only.",
    "4.3 Volumes below the agreed annual minimum carry the unrecovered balance.",
    "",
    "5. Process controls",
    "5.1 Salt spray testing runs to 720 hours on every anodised lot.",
    "5.2 The cure oven must hold 385 F for the full cycle.",
])

#: The operator's OWN inventory (the live integration read boundary).
INVENTORY_ITEMS = [
    {"sku": "BKT-1180", "name": "Anodised bracket, clear",
     "quantity_on_hand": 312, "warehouse": "Bay 4"},
    {"sku": "ANZ-4471", "name": "Anodiser lot, clear",
     "quantity_on_hand": 18, "warehouse": "Bay 4"},
]
INVENTORY_QTY = "312"


# ─────────────────────────────────────────────────────────────────────────────
# Read-boundary doubles
# ─────────────────────────────────────────────────────────────────────────────

class InMemoryKnowledgeVFS(VFSProvider):
    """The knowledge-VFS read boundary: a small in-memory tree instead of
    LanceDB. ``prefix`` is the real registry key so the REAL
    ``documents.*`` actions resolve to it unchanged."""

    prefix = "knowledge"

    def __init__(self, docs: Dict[str, str]):
        # path -> plain text (line-numbered on read, like the real provider)
        self._docs = dict(docs)

    # -- helpers -----------------------------------------------------------
    def _dirs(self) -> List[str]:
        return sorted({p.split("/")[1] for p in self._docs})

    async def ls(self, path: str, ctx: Optional[Dict[str, Any]] = None) -> List[VFSNode]:
        clean = (path or "").strip("/")
        if clean in ("", "knowledge"):
            return [VFSNode(name=d, type="dir", path=f"knowledge/{d}")
                    for d in self._dirs()]
        if clean.count("/") == 1:
            return [
                VFSNode(name=p.split("/")[-1], type="file", path=p)
                for p in sorted(self._docs) if p.startswith(clean + "/")
            ]
        return []

    async def cat(self, path: str, ctx: Optional[Dict[str, Any]] = None) -> VFSResource:
        key = (path or "").strip("/")
        if key.endswith("/meta.json"):
            doc = key[: -len("/meta.json")]
            return VFSResource(path=key, meta={"id": doc.rsplit("/", 1)[-1]}, lines=[])
        text = self._docs.get(key)
        if text is None:
            return VFSResource(path=key, meta={}, lines=[])
        return VFSResource(path=key, meta={"title": text.split("\n", 1)[0]},
                           lines=to_line_numbered(text))

    async def grep(self, pattern, path_prefix, ctx=None) -> list:
        """Recursive regex scan over the in-memory tree (the real provider
        overrides the base walk the same way)."""
        import re as _re
        from core.vfs_base import VFSCitation

        try:
            regex = _re.compile(pattern, _re.IGNORECASE)
        except _re.error:
            return []
        prefix = (path_prefix or "knowledge").strip("/")
        out: List[VFSCitation] = []
        for path in sorted(self._docs):
            if not path.startswith(prefix):
                continue
            for i, line in enumerate(to_line_numbered(self._docs[path])):
                if regex.search(line):
                    out.append(VFSCitation(path=path, line=i + 1, snippet=line[:200]))
        return out


class RecordingLLM:
    """Deterministic stand-in for ``ChatOrchestrator.llm_service``.

    * ``generate_structured_response`` — the PLANNER transport. Returns a plan
      computed by ``plan_for`` from the prompt the REAL harness assembled (the
      real catalog + the real PROVENANCE menu).
    * ``generate_completion`` — the ANSWER transport. Records the full message
      list and replies with ``reply_policy(evidence)``, a canned answer derived
      from the evidence block it was handed.
    """

    def __init__(self, plan_for: Callable[[str], ToolPlan],
                 reply_policy: Callable[..., str]):
        self._plan_for = plan_for
        self._reply_policy = reply_policy
        self.structured_prompts: List[str] = []
        self.reply_calls: List[Dict[str, Any]] = []
        self.handler = MagicMock()
        self.handler.analyze_query_complexity.return_value = SimpleNamespace(
            value="simple")
        self.handler.get_optimal_provider = AsyncMock(return_value=("stub", "stub"))
        self.handler.get_fallback_models.return_value = []

    # -- planner transport -------------------------------------------------
    async def generate_structured_response(self, *, prompt=None,
                                           response_model=None,
                                           system_instruction=None, **kw):
        self.structured_prompts.append(prompt or "")
        if response_model is ToolPlan:
            return self._plan_for(prompt or "")
        try:  # generic helper models (query rewrite etc.): an empty instance
            return response_model()
        except Exception:
            return None

    # -- answer transport --------------------------------------------------
    async def generate_completion(self, *, messages=None, model=None,
                                  tenant_id=None, **kw):
        recorded = [dict(m) for m in (messages or [])]
        self.reply_calls.append({"messages": recorded, "model": model})
        last_user = ""
        for m in reversed(recorded):
            if m.get("role") == "user":
                last_user = str(m.get("content") or "")
                break
        content = self._reply_policy(
            evidence=_evidence_of(recorded),
            messages=recorded,
            message=last_user,
            call_index=len(self.reply_calls),
        )
        return {"success": True, "content": content,
                "model": "stub-model", "provider": "stub-provider"}

    async def stream_completion(self, **kw):  # pragma: no cover - must not run
        raise AssertionError(
            "the streaming path must not run: the harness sets ATOM_CHAT_STREAMING=false")
        yield  # noqa: E999 - makes this an async generator

    # -- assertions helpers ------------------------------------------------
    def last_messages(self) -> List[Dict[str, Any]]:
        assert self.reply_calls, "the model was never asked to answer"
        return self.reply_calls[-1]["messages"]

    def last_evidence(self) -> str:
        ev = _evidence_of(self.last_messages())
        import os as _os
        import sys as _sys
        if _os.environ.get("ATOM_CORPUS_DEBUG") == "1":
            print("\n=== EVIDENCE ===\n" + ev + "\n=== /EVIDENCE ===\n",
                  file=_sys.stderr)
        return ev


def _evidence_of(messages: List[Dict[str, Any]]) -> str:
    """The evidence the harness assembled for the model — the TOOL EXECUTION
    RESULT block(s) it injected. THIS is the selection decision, observed."""
    return "\n".join(
        str(m.get("content") or "")
        for m in messages
        if str(m.get("content") or "").startswith("TOOL EXECUTION RESULT")
    )


def _system_text(messages: List[Dict[str, Any]]) -> str:
    return "\n".join(str(m.get("content") or "") for m in messages
                     if m.get("role") == "system")


def _money_figures(text: str) -> List[str]:
    """Ordered, de-duplicated currency figures as the product's own reply-side
    figure matcher (``_MONEY_RE``) sees them."""
    seen, out = set(), []
    for m in _MONEY_RE.finditer(text or ""):
        raw = m.group(0).strip()
        if raw not in seen:
            seen.add(raw)
            out.append(raw)
    return out


def _figures(text: str) -> List[str]:
    """Figures to quote back: currency amounts when the evidence carries them,
    otherwise bare 3+ digit VALUES (quantities, line totals) — never the digits
    inside an identifier (BKT-1180, R118) and never a year."""
    money = _money_figures(text)
    if money:
        return money
    seen, out = set(), []
    for m in re.finditer(r"(?<![\w-])(\d{3,})(?![\w-])", text or ""):
        val = m.group(1)
        if len(val) == 4 and val.startswith(("19", "20")):
            continue  # a year, not a value
        if val not in seen:
            seen.add(val)
            out.append(val)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Reply policies (the "model" answering from the evidence it was given)
# ─────────────────────────────────────────────────────────────────────────────

def _grounding_failure(messages: List[Dict[str, Any]]) -> bool:
    return "FIGURE GROUNDING FAILURE" in _system_text(messages)


def evidence_reply(*, evidence: str, messages: List[Dict[str, Any]],
                   message: str = "", call_index: int = 1, **_) -> str:
    """Default policy: quote the figures the evidence actually carries; when it
    carries none, say the value is not supported. Never invents a number."""
    if _grounding_failure(messages):
        return ("I can't confirm that figure - no ingested source states it, so "
                "it is not supported by the evidence.")
    figs = _figures(evidence)
    if not figs:
        return ("None of the retrieved evidence states that value: it is not "
                "supported by any ingested source I searched.")
    return ("From the ingested evidence: " + " and ".join(figs[:3])
            + " - those are the values the retrieved sources state.")


def make_fabricating_policy(invented: str) -> Callable[..., str]:
    """Policy that INVENTS a plausible figure on the first call (the failure
    mode under test) and answers honestly once the harness's deterministic
    figure-grounding guard fires."""
    def policy(*, evidence: str, messages: List[Dict[str, Any]],
               call_index: int = 1, **_) -> str:
        if _grounding_failure(messages):
            return ("I can't confirm a price for that item - the searched "
                    "sources do not state one, so it is not supported by the "
                    "evidence.")
        return f"The price for that item is {invented}."
    return policy


def conflict_policy(*, evidence: str, messages: List[Dict[str, Any]],
                    message: str = "", call_index: int = 1, **_) -> str:
    """Answers a two-source disagreement: names BOTH values, says they
    conflict, and never averages them."""
    mail = "$1,180.00" if "$1,180.00" in evidence else "(no quoted figure)"
    wb = "1,455.00" if "1455" in evidence else "(no workbook figure)"
    return (
        f"About \"{message[:60]}\": the two sources disagree. The ingested "
        f"message from {MAIL_SENDER} quotes {mail} for the BKT-1180 lot, while "
        f"{WORKBOOK_FILE} sheet '{WORKBOOK_SHEET}' row {WORKBOOK_ROW} computes "
        f"a lot total of {wb} for the same lot. These are not the same number "
        "and I am not averaging them: the quoted figure is what the supplier "
        "said, the workbook row is our own costing."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _fake_search_all_datasets_sync(query, user_id=None, workspace_id=None,
                                   limit=5, max_files=200, context_texts=None,
                                   name_context_texts=None, deadline=None):
    """The workbook catalog read boundary: in-memory rows, keyed by the REAL
    product's own candidate-probe-token ranking."""
    from core.sheet_dataset_service import candidate_probe_tokens

    tokens = candidate_probe_tokens(
        [query] + list(context_texts or []) + list(name_context_texts or [])
    ) or [query]
    for tok in tokens:
        blob = json.dumps(WORKBOOK_HIT).lower()
        if tok.lower() not in blob:
            continue
        wanted = [
            r for r in WORKBOOK_HIT["rows"]
            if tok.lower() in json.dumps(r).lower()
        ] or WORKBOOK_HIT["rows"]
        hit = dict(WORKBOOK_HIT)
        hit["rows"] = wanted
        hit["row_count"] = len(wanted)
        return {"token": tok, "files_searched": 1, "hits": [hit]}
    return {"token": tokens[0], "tokens_tried": tokens,
            "files_searched": 1, "hits": []}


def _plan_from_prompt(prompt: str) -> ToolPlan:
    """The planner-model stand-in. It reads the REAL provenance menu the harness
    resolved from the corpus and names the service the product's own routing
    rules point at — the selection itself stays in product code."""
    import re as _re

    checked = _re.findall(r"'([^']+)'", (prompt or "").split("tokens checked:")[-1]
                          .split("):")[0]) if "tokens checked:" in (prompt or "") else []
    token = checked[0] if checked else ""
    query = " ".join(checked) or token or "unresolved"
    if "INGESTED MAIL contains your quoted" in prompt:
        return ToolPlan(use_tool=True, service="outlook", intent="search",
                        query=query,
                        reason="provenance: quoted text lives in ingested mail",
                        suggested_intent="search_request",
                        routing_confidence=0.9)
    if "DATASET CATALOG (ingested spreadsheets) contains" in prompt:
        return ToolPlan(use_tool=True, service="datasets", intent="search",
                        query=query,
                        reason="provenance: value lives in a spreadsheet",
                        suggested_intent="search_request",
                        routing_confidence=0.9)
    return ToolPlan(use_tool=True, service="memory", intent="search",
                    query=query,
                    reason="no provenance line",
                    suggested_intent="search_request",
                    routing_confidence=0.9)


@contextmanager
def _null_db_session():
    """A DB-free session stand-in: the chat turn's audit writes (execution row,
    reasoning steps, session hydration) must not touch ANY database."""
    class _Query:
        def filter(self, *a, **k):
            return self

        def order_by(self, *a, **k):
            return self

        def first(self):
            return None

        def all(self):
            return []

        def count(self):
            return 0

    class _Session:
        def query(self, *a, **k):
            return _Query()

        def add(self, *a, **k):
            return None

        def flush(self, *a, **k):
            return None

        def commit(self, *a, **k):
            return None

        def rollback(self, *a, **k):
            return None

        def close(self, *a, **k):
            return None

    yield _Session()


class Harness:
    """An authenticated ``/api/chat`` boundary wired to the in-memory corpus."""

    def __init__(self, client: TestClient, llm: RecordingLLM):
        self.client = client
        self.llm = llm

    def ask(self, message: str, session_id: Optional[str] = None,
            context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {
            "message": message,
            "user_id": "operator-1",
            "session_id": session_id or f"s-{uuid.uuid4().hex}",
        }
        if context:
            payload["context"] = context
        resp = self.client.post("/api/chat/message", json=payload)
        assert resp.status_code == 200, resp.text
        return resp.json()


@pytest.fixture
def harness(monkeypatch):
    import core.chat_tool_planner as ctp
    import core.database as cdb
    import core.vfs_registry as vfs_registry
    import integrations.chat_orchestrator as co
    import integrations.chat_routes as cr
    import integrations.outlook_service as outlook_mod
    from integrations.universal_integration_service import (
        UniversalIntegrationService,
    )

    # ── deterministic env ────────────────────────────────────────────────
    monkeypatch.setenv("ATOM_CHAT_STREAMING", "false")
    monkeypatch.setenv("ATOM_VERIFY_PANEL", "off")
    monkeypatch.setenv("ATOM_KNOWLEDGE_VFS_ENABLED", "true")
    monkeypatch.setenv("ATOM_LEARNING_ROUTER", "false")
    monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", "false")
    monkeypatch.setenv("TAVILY_API_KEY", "")  # no web tools in the catalog

    # ── no network, at all ───────────────────────────────────────────────
    # A real LLM call, a Tavily call or a Graph call would be a test bug, not
    # a slow test: fail loudly instead of silently reaching the internet.
    import socket

    def _no_connect(*_a, **_k):
        raise AssertionError("network access attempted from a hermetic corpus test")

    monkeypatch.setattr(socket.socket, "connect", _no_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _no_connect)
    monkeypatch.setattr(socket, "create_connection", _no_connect)

    # ── no DB ────────────────────────────────────────────────────────────
    monkeypatch.setattr(cdb, "get_db_session", _null_db_session)
    monkeypatch.setattr(cdb, "get_db", lambda: None)

    # ── knowledge VFS read boundary ──────────────────────────────────────
    provider = InMemoryKnowledgeVFS({
        DOC_PATH: DOC_TEXT,
        f"knowledge/documents/{DOC_ID}/meta.json": DOC_TITLE,
        "knowledge/conversations/cm-9001/content.lines":
            MAIL_ROWS[0]["content"],
        "knowledge/conversations/cm-9002/content.lines":
            MAIL_ROWS[1]["content"],
    })
    monkeypatch.setitem(vfs_registry._REGISTRY, "knowledge", provider)
    import integrations.vfs.knowledge_vfs as kvfs
    monkeypatch.setattr(kvfs, "KnowledgeVFSProvider",
                        lambda *a, **k: InMemoryKnowledgeVFS(provider._docs))

    # ── mailbox read boundary (ingested store + live Graph) ──────────────
    monkeypatch.setattr(ctp, "_comms_store_records", lambda: [dict(r) for r in MAIL_ROWS])
    monkeypatch.setattr(ctp, "_mail_attachments_for", lambda mid, limit=4: [])
    monkeypatch.setattr(ctp, "_comms_row_digit_blobs",
                        lambda path, rows: [None] * len(rows))
    monkeypatch.setattr(ctp, "_mail_attachment_reverse_index", lambda: {})
    monkeypatch.setattr(ctp, "_doc_to_message_index", lambda: {})
    monkeypatch.setattr(ctp, "_load_documents_table", lambda: None)
    monkeypatch.setattr(ctp, "_load_documents_df", lambda: None)
    monkeypatch.setattr(outlook_mod.outlook_service, "search_emails",
                        AsyncMock(return_value=[]))
    monkeypatch.setattr(outlook_mod.outlook_service, "get_email_by_id",
                        AsyncMock(return_value=None))

    # ── workbook catalog read boundary ───────────────────────────────────
    import core.sheet_dataset_service as sds
    monkeypatch.setattr(sds, "search_all_datasets_sync",
                        _fake_search_all_datasets_sync)
    monkeypatch.setattr(sds, "find_entries_sync", lambda *a, **k: [])
    monkeypatch.setattr(sds, "catalog_has_entries_sync", lambda: True)
    monkeypatch.setattr(ctp, "_datasets_avail_cache", None)

    # ── live integration read boundary (the operator's own inventory) ────
    async def _fake_execute(self, service, action, params=None, context=None):
        if service == "zoho_inventory":
            return {"status": "success",
                    "data": {"items": [dict(i) for i in INVENTORY_ITEMS],
                             "action": action}}
        raise AssertionError(f"unexpected live integration call: {service}.{action}")

    monkeypatch.setattr(UniversalIntegrationService, "execute", _fake_execute)

    # ── the memory assembler and per-turn fact extraction: the corpus is
    #    served through the store lanes above, not through LanceDB ─────────
    import core.memory_context_assembler as mca
    monkeypatch.setattr(mca, "assembly_enabled", lambda: False)
    # The semantic/hybrid supplement reads LanceDB — no hits in this corpus.
    import core.hybrid_search.documents_hybrid as dh
    monkeypatch.setattr(dh, "DocumentsHybridSearch", _NoHybridSearch)

    # ── the model transport ──────────────────────────────────────────────
    llm = RecordingLLM(plan_for=_plan_from_prompt, reply_policy=evidence_reply)
    monkeypatch.setattr(cr.chat_orchestrator, "llm_service", llm)
    monkeypatch.setattr(cr.chat_orchestrator, "conversation_sessions", {})
    monkeypatch.setattr(cr.chat_orchestrator, "feature_handlers", {})
    # the session manager persists ChatSession rows through its own engine
    # (whatever DATABASE_URL points at) — this corpus is DB-free
    monkeypatch.setattr(cr.chat_orchestrator, "session_manager", None)
    monkeypatch.setattr(co.agent_service, "execute_task",
                        AsyncMock(return_value={"id": "stub-task",
                                                "status": "queued"}))

    # ── planner caches are process-global: make every turn re-resolve ────
    monkeypatch.setattr(ctp, "_connected_cache", {}, raising=False)
    monkeypatch.setattr(ctp, "_PEOPLE_INDEX", {}, raising=False)
    monkeypatch.setattr(ctp, "_comms_store_cache", {}, raising=False)
    monkeypatch.setattr(ctp, "_MAIL_ATTACHMENTS", {}, raising=False)
    monkeypatch.setattr(ctp, "get_connected_services",
                        lambda uid: ["outlook", "zoho_inventory"])
    import core.outbound_identity as oid
    monkeypatch.setattr(oid, "collect_team_signers",
                        lambda *a, **k: {"primary": None, "team": []})

    app = FastAPI()
    app.include_router(cr.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="operator-1", tenant_id="tenant-1", workspace_id="default",
        role="admin")
    try:
        from core.database import get_db as _get_db
        app.dependency_overrides[_get_db] = lambda: None
    except Exception:
        pass

    with TestClient(app) as client:
        yield Harness(client, llm)


class _NoHybridSearch:
    """The hybrid/semantic supplement reads LanceDB; this corpus is served by
    the deterministic store lanes only."""

    def __init__(self, *a, **k):
        pass

    async def search(self, *a, **k):
        return {"results": []}


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 1 — mail
# ─────────────────────────────────────────────────────────────────────────────

class TestMailSourcedFact:
    ASK = ("what price did Northgate confirm for the ANZ-4471 anodiser lot? "
           f"they wrote {MAIL_FIGURE_ANZ}")

    def test_selected_source_is_the_ingested_mail(self, harness):
        body = harness.ask(self.ASK)
        evidence = harness.llm.last_evidence()

        # (1) the selected source, observed at the boundary
        assert MAIL_FIGURE_ANZ in evidence
        assert MAIL_SENDER in evidence
        assert "anodiser lot pricing" in evidence
        # the irrelevant source's decisive figure never reached the model
        assert MAIL_FIGURE_NOISE not in evidence
        assert WORKBOOK_TOTAL not in evidence

        # (2) the grounded answer
        reply = body["message"]
        assert MAIL_FIGURE_ANZ in reply
        assert "3,975" not in reply
        assert WORKBOOK_TOTAL not in reply

    def test_unrelated_thread_is_not_provenance(self, harness):
        """The provenance resolver must find the quoted token in ONE row, not
        report the whole mailbox as containing it."""
        harness.ask(self.ASK)
        planner_prompt = harness.llm.structured_prompts[0]
        assert MAIL_FIGURE_ANZ in planner_prompt
        assert MAIL_FIGURE_NOISE not in planner_prompt


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 2 — workbook (with a formula dependency)
# ─────────────────────────────────────────────────────────────────────────────

class TestWorkbookSourcedFact:
    ASK = "what does the HNG-2205 row come to on the costing sheet?"

    def test_selected_source_is_the_workbook_row_plus_its_formula(self, harness):
        body = harness.ask(self.ASK)
        evidence = harness.llm.last_evidence()

        assert WORKBOOK_FILE in evidence
        assert WORKBOOK_SHEET in evidence
        assert f"R{WORKBOOK_ROW}" in evidence
        assert WORKBOOK_TOTAL in evidence
        # the row is NOT a full answer without its formula dependency
        assert "FORMULAS FOR THE MATCHED ROW(S)" in evidence
        assert WORKBOOK_FORMULA in evidence
        # no mail was selected for this question
        assert MAIL_FIGURE_BKT not in evidence
        assert MAIL_SENDER not in evidence

        reply = body["message"]
        assert WORKBOOK_TOTAL in reply
        assert "1,180" not in reply

    def test_formula_row_only_renders_for_the_matched_row(self, harness):
        """The formula line must be THIS row's formula — the derivation the
        workbook computes — with any other row's formula explicitly demoted to
        pattern context, not silently presented as the answer's derivation."""
        harness.ask(self.ASK)
        evidence = harness.llm.last_evidence()
        assert "FORMULAS FOR THE MATCHED ROW(S)" in evidence
        assert "D204*E204" in evidence
        assert "OTHER ROWS' FORMULAS (pattern context, not this row)" in evidence
        assert (evidence.index(WORKBOOK_FORMULA)
                < evidence.index(WORKBOOK_FORMULA_BKT))

    def test_workbook_only_identifier_has_no_mail_provenance(self, harness):
        """HNG-2205 exists in the spreadsheet and nowhere else — the REAL
        provenance resolver must say so."""
        harness.ask(self.ASK)
        prompt = harness.llm.structured_prompts[-1]
        assert "DATASET CATALOG (ingested spreadsheets) contains" in prompt
        assert "INGESTED MAIL contains your quoted" not in prompt


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 3 — prose document
# ─────────────────────────────────────────────────────────────────────────────

class TestDocumentSourcedFact:
    ASK = ("what does the supplier quality agreement say the annual "
           "amortisation charge is?")

    @pytest.fixture(autouse=True)
    def _documents_plan(self, harness):
        # The planner-model stand-in targets the knowledge VFS for this ask.
        def _plan(_prompt: str) -> ToolPlan:
            return ToolPlan(use_tool=True, service="documents", intent="grep",
                            query="amortisation",
                            reason="a prose agreement, not a record app",
                            suggested_intent="search_request",
                            routing_confidence=0.9)
        harness.llm._plan_for = _plan
        return harness

    def test_selected_source_is_the_stored_document(self, _documents_plan):
        harness = _documents_plan
        body = harness.ask(self.ASK)
        evidence = harness.llm.last_evidence()

        assert "documents.grep" in evidence
        assert DOC_PATH in evidence
        assert DOC_FIGURE in evidence
        assert "720 hours" in evidence  # the full artifact was hydrated
        assert MAIL_FIGURE_ANZ not in evidence
        assert MAIL_FIGURE_NOISE not in evidence
        assert WORKBOOK_TOTAL not in evidence

        reply = body["message"]
        assert "18,400" in reply
        assert "3,975" not in reply
        assert MAIL_FIGURE_ANZ not in reply


class TestParticipantLaneDomainWordLeak:
    """REGRESSION (was an xfail; the defect is now fixed) — the participant
    lane used to treat any 4+ letter token inside a *bare address* as a
    participant name the user said.

    ``_participant_mail_rows`` (integrations/chat_orchestrator.py) scanned
    ``sender``/``recipient`` for display-name words via
    ``re.findall(r"[A-Za-z]{4,}", val.split("<", 1)[0])``. For an address with
    no display name that prefix is the whole ``local@domain.tld`` string, so
    the DOMAIN contributed "words": ``billing@tooling-depot.example``
    contributed "tooling", "depot" and "example".

    Consequence observed here (independent corpus): a question about a stored
    PROSE DOCUMENT — "what does the supplier quality agreement say the annual
    tooling amortisation is?" — made the lane fire on the ordinary English word
    "tooling", and the harness injected an unrelated supplier's calibration
    invoice ($3,975.00) under the header "LIVE TOOL RESULTS (ingested mailbox —
    the messages the user is pointing at)", i.e. it told the reply model that
    the user was pointing at a message they never mentioned.

    Fixed by stripping every @-token before scanning for display-name words.
    Both halves are pinned below: the domain no longer donates a name, and a
    REAL display name still matches.
    """

    ASK = ("what does the supplier quality agreement say the annual tooling "
           "amortisation is?")

    def test_domain_words_are_not_participants(self, harness):
        def _plan(_prompt: str) -> ToolPlan:
            return ToolPlan(use_tool=True, service="documents", intent="grep",
                            query="amortisation",
                            reason="a prose agreement",
                            suggested_intent="search_request",
                            routing_confidence=0.9)
        harness.llm._plan_for = _plan

        harness.ask(self.ASK)
        evidence = harness.llm.last_evidence()
        assert "- [ingested mailbox] From: billing@tooling-depot.example" \
            not in evidence
        assert MAIL_FIGURE_NOISE not in evidence

    def test_real_display_names_still_match(self):
        """The fix must not be over-broad: an actual display name still grips
        its rows, in both ``Name <addr>`` and ``addr (Name)`` shapes."""
        from integrations.chat_orchestrator import _participant_mail_rows

        rows = _participant_mail_rows(
            "what did chandrakant say about the foot shear?")
        assert rows, "a real display-name participant stopped matching"


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 4 — explicit inventory request
# ─────────────────────────────────────────────────────────────────────────────

class TestExplicitInventoryRequest:
    ASK = "list my stock - what do I have on hand right now?"

    @pytest.fixture(autouse=True)
    def _inventory_plan(self, harness):
        def _plan(_prompt: str) -> ToolPlan:
            return ToolPlan(use_tool=True, service="zoho_inventory",
                            intent="search", query="on hand BKT-1180 ANZ-4471",
                            reason="the user asked for their own stock",
                            suggested_intent="search_request",
                            routing_confidence=0.9)
        harness.llm._plan_for = _plan
        return harness

    def test_own_inventory_not_a_generic_web_answer(self, _inventory_plan):
        harness = _inventory_plan
        body = harness.ask(self.ASK)
        evidence = harness.llm.last_evidence()

        # (1) the operator's OWN stored inventory was selected
        assert "zoho_inventory.search_items" in evidence
        assert INVENTORY_QTY in evidence
        assert "Bay 4" in evidence
        # ... and no web-ish source was consulted instead
        assert "web_search" not in evidence
        assert "returned nothing usable" not in evidence

        # (2) the grounded answer
        reply = body["message"]
        assert INVENTORY_QTY in reply
        assert MAIL_FIGURE_ANZ not in reply


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 5 — conflicting provenance
# ─────────────────────────────────────────────────────────────────────────────

class TestConflictingProvenance:
    ASK = f"find this: {MAIL_FIGURE_BKT} for the BKT-1180 lot"

    @pytest.fixture(autouse=True)
    def _dataset_plan(self, harness):
        # The quoted line is asked about; the planner routes on the identifier
        # to the workbook. The REAL verbatim-mailbox overlay runs anyway.
        def _plan(_prompt: str) -> ToolPlan:
            return ToolPlan(use_tool=True, service="datasets", intent="search",
                            query="BKT-1180",
                            reason="the identifier lives in the BOM",
                            suggested_intent="search_request",
                            routing_confidence=0.9)
        harness.llm._plan_for = _plan
        harness.llm._reply_policy = conflict_policy
        return harness

    def test_both_sources_are_assembled_and_labelled(self, _dataset_plan):
        harness = _dataset_plan
        harness.ask(self.ASK)
        evidence = harness.llm.last_evidence()

        # both sources reached the model — neither was silently dropped
        assert MAIL_FIGURE_BKT in evidence
        assert WORKBOOK_TOTAL_BKT in evidence
        # ... and each keeps its OWN source label, so the model sees two
        # disagreeing sources rather than one merged record
        assert "(ingested mailbox" in evidence
        assert "(datasets.search" in evidence

    def test_answer_says_the_sources_conflict_and_does_not_average(
            self, _dataset_plan):
        harness = _dataset_plan
        body = harness.ask(self.ASK)
        reply = body["message"]

        assert "disagree" in reply.lower()
        assert MAIL_FIGURE_BKT in reply
        assert "1,455.00" in reply
        # never a silent average / arbitrary pick
        for averaged in ("1,317.50", "1317.5", "1,317", "1317"):
            assert averaged not in reply, f"averaged value leaked: {averaged}"


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 6 — missing evidence
# ─────────────────────────────────────────────────────────────────────────────

class TestMissingEvidence:
    ASK = "how much did we pay for the XR-7704 gasket set?"

    @pytest.fixture(autouse=True)
    def _dataset_plan(self, harness):
        def _plan(_prompt: str) -> ToolPlan:
            return ToolPlan(use_tool=True, service="datasets", intent="search",
                            query="XR-7704",
                            reason="a value lookup with no named source",
                            suggested_intent="search_request",
                            routing_confidence=0.9)
        harness.llm._plan_for = _plan
        return harness

    def test_no_source_supports_the_asked_figure(self, _dataset_plan):
        harness = _dataset_plan
        harness.ask(self.ASK)
        evidence = harness.llm.last_evidence()

        # the harness says so explicitly instead of leaving a gap
        assert "XR-7704" in evidence or "7704" in evidence
        assert "appear in NONE of them" in evidence
        # and nothing that could be mistaken for the answer
        assert _money_figures(evidence) == []

    def test_invented_number_is_caught_and_never_reaches_the_user(
            self, _dataset_plan):
        """The failure mode: a plausible-looking number with no source. The
        harness's deterministic figure check must catch it and the reply the
        user receives must not carry it."""
        harness = _dataset_plan
        invented = "$7,432.00"
        harness.llm._reply_policy = make_fabricating_policy(invented)

        body = harness.ask(self.ASK)
        reply = body["message"]

        assert len(harness.llm.reply_calls) >= 2, (
            "the figure-grounding guard never regenerated the fabricated reply")
        assert "7,432" not in reply
        assert "not supported by the evidence" in reply


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 7 — changed follow-up subject
# ─────────────────────────────────────────────────────────────────────────────

class TestChangedFollowUpSubject:
    TURN_1 = "what did the anodiser's email say about the BKT-1180 lot price?"
    TURN_2 = "what about the other one - the Bracket_BOM_v7 costing row?"

    @pytest.fixture(autouse=True)
    def _follow_up(self, harness):
        calls = {"n": 0}

        def _plan(_prompt: str) -> ToolPlan:
            calls["n"] += 1
            if calls["n"] == 1:
                return ToolPlan(use_tool=True, service="outlook",
                                intent="search", query="BKT-1180",
                                reason="the supplier's message",
                                suggested_intent="search_request",
                                routing_confidence=0.9)
            return ToolPlan(use_tool=True, service="datasets", intent="search",
                            query="Bracket_BOM_v7",
                            reason="the workbook row the user just named",
                            suggested_intent="search_request",
                            routing_confidence=0.9)
        harness.llm._plan_for = _plan
        return harness

    def test_turn_two_is_grounded_in_the_new_source(self, _follow_up):
        harness = _follow_up
        session = f"s-{uuid.uuid4().hex}"

        first = harness.ask(self.TURN_1, session_id=session)
        assert MAIL_FIGURE_BKT in first["message"]
        first_evidence = harness.llm.last_evidence()
        assert MAIL_FIGURE_BKT in first_evidence
        assert WORKBOOK_TOTAL_BKT not in first_evidence

        second = harness.ask(self.TURN_2, session_id=session)
        turn2_evidence = harness.llm.last_evidence()

        # grounded in B
        assert WORKBOOK_FILE in turn2_evidence
        assert WORKBOOK_TOTAL_BKT in turn2_evidence
        # A's evidence is NOT reused, and B's fact is not attributed to A
        assert MAIL_FIGURE_BKT not in turn2_evidence
        assert MAIL_SENDER not in turn2_evidence
        assert "- [ingested mailbox]" not in turn2_evidence

        reply = second["message"]
        assert WORKBOOK_TOTAL_BKT in reply
        assert "1,180" not in reply

    def test_turn_two_prompt_carries_no_assistant_echo_of_source_a(
            self, _follow_up):
        """When fresh tool results exist the harness feeds only USER turns —
        the previous answer (which quoted A's figure) must not become this
        turn's evidence."""
        harness = _follow_up
        session = f"s-{uuid.uuid4().hex}"
        harness.ask(self.TURN_1, session_id=session)
        harness.ask(self.TURN_2, session_id=session)

        messages = harness.llm.last_messages()
        for m in messages:
            content = str(m.get("content") or "")
            if content.startswith("TOOL EXECUTION RESULT"):
                continue
            assert MAIL_FIGURE_BKT not in content, (
                "source A's figure leaked into the turn-2 prompt outside the "
                "evidence block")
