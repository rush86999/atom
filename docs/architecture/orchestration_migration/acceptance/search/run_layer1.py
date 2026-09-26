#!/usr/bin/env python3
"""Layer-1 search acceptance: drive the PRODUCTION search stack per scenario.

This is not a unit-test harness and it does not re-implement search. Every
scenario runs through the same `DocumentsHybridSearch` and the same
`_hybrid_search_preserving_constraints` adapter the chat planner calls, against
a labeled fixture world built here. What it measures is the thing the unit
tests cannot: whether a whole labeled query, end to end through the real code,
produces the right source, the right per-item classification and the right
evidence binding — including when a leg is broken.

Cases whose required assertions live at the PUBLIC boundary (formatting must
perform zero retrievals, keyed retry must not search again, constraints must
survive a restart) are recorded as `blocked` here with the reason, and are
driven by `run_isolated.py` against a live server in the same acceptance tree.
A blocked case is never scored as a pass.

Usage:  python3 run_layer1.py [--out runs.json] [--only substring]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))


# --------------------------------------------------------------------------- #
# ISOLATION PREAMBLE — runs before any repo import
#
# An earlier draft of this harness set only TESTING=1 and was still enough for
# the app to initialise real BYOK clients and to open the developer's live
# communication store ("restored poll fetch state: 4 cursors, 20010 known
# message ids"). Reading live data is not a neutral act even when nothing is
# written, and it makes a run non-repeatable. So every store is redirected into
# a scratch root and the redirection is VERIFIED, not assumed: a run that cannot
# prove where its data came from does not produce a result.
# --------------------------------------------------------------------------- #

SCRATCH = Path(os.environ.get(
    "SEARCH_ACCEPT_SCRATCH",
    str(Path(os.environ.get("TMPDIR", "/tmp")) / "atom_search_acceptance"),
)).resolve()
SCRATCH.mkdir(parents=True, exist_ok=True)

os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = f"sqlite:///{SCRATCH / 'atom.db'}"
os.environ["LANCEDB_URI"] = str(SCRATCH / "lancedb")
os.environ["LANCEDB_URI_BASE"] = str(SCRATCH / "atom_memory")
os.environ["LANCEDB_CLOUD_ENABLED"] = "false"
# No outbound calls: this layer is about retrieval, not provider reachability.
os.environ["NO_PROXY"] = "*"
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["MEMORY_CONVERSATIONS_LEG"] = "true"
os.environ["ATOM_HYBRID_VECTOR_LEG_ENABLED"] = "true"
# Credentials are never read from the developer's stores.
os.environ["BYOK_ENCRYPTION_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["OPENCODE_API_KEY"] = ""


def _assert_isolated() -> None:
    """Fail closed if any store resolves outside the scratch root."""
    import urllib.parse

    def _path_of(value: str) -> str:
        if "://" in value:
            parsed = urllib.parse.urlparse(value)
            return parsed.path or ""
        return value

    live = (BACKEND / "data").resolve()
    for name, value in (("DATABASE_URL", os.environ["DATABASE_URL"]),
                        ("LANCEDB_URI", os.environ["LANCEDB_URI"]),
                        ("LANCEDB_URI_BASE", os.environ["LANCEDB_URI_BASE"])):
        target = Path(_path_of(value)).resolve()
        if not str(target).startswith(str(SCRATCH)):
            raise SystemExit(
                f"ISOLATION FAILURE: {name}={value!r} resolves to {target}, "
                f"outside the scratch root {SCRATCH}. Refusing to run against "
                "live data."
            )
        if str(target).startswith(str(live)):
            raise SystemExit(
                f"ISOLATION FAILURE: {name}={value!r} resolves INSIDE the live "
                f"data directory {live}. Refusing to run."
            )
    if str(SCRATCH).startswith(str(live)):
        raise SystemExit("scratch root is inside the live data directory")


_assert_isolated()


# --------------------------------------------------------------------------- #
# The labeled fixture world
#
# Content is invented. It shares no vocabulary with the workbook incident the
# original regression fixture is built from, so a scenario cannot pass by
# recognising the fixture it grew up with.
# --------------------------------------------------------------------------- #

WORKBOOK = "linmac_consolidated.xlsx"

# (row_label, unit_code, list_price_cad, note)
ROWS = [
    ("U-22", "U-22", 1284.00, "plate steel saw, 22 inch"),
    ("U-22X", "U-22X", 1399.00, "plate steel saw, 22 inch, carbide"),
    ("SLE24-16", "SLE24-16", 2499.50, "cold saw, 24 inch 16 gauge"),
    ("SLE24-160", "SLE24-160", 2610.00, "cold saw, 24 inch 160 gauge"),
    ("GSL48-16", "GSL48-16", 875.25, "green saw left, 48 inch"),
    ("GSL48-1", "GSL48-1", 799.00, "green saw left, 1 gauge"),
    ("TK 1624", "TK 1624", 875.00, "transfer kit 1624"),
    ("No. 381", "No. 381", 640.00, "legacy part, revision A"),
    ("No. 381", "No. 381", 655.00, "legacy part, revision B"),
    ("No. 622", "No. 622", 415.00, "legacy part, revision A"),
    ("No. 622", "No. 622", 430.00, "legacy part, revision B"),
    # A USD row exists so "how much in USD" is answerable only by a
    # currency conversion, never by a mis-bound unit.
    ("U-22", "U-22", 940.00, "US dealer list, USD"),
]

DOCUMENTS = {
    "policy_manual.pdf": (
        "Equipment warranty terms\n\n"
        "Linmac warrants the plate steel saw against defects in materials and "
        "workmanship for 24 months from the date of delivery, whichever is "
        "earlier. Blades are warranted separately for 12 months. Consumables "
        "and cutting fluid are not covered."
    ),
    "expense_policy.md": (
        "# Expense policy\n\n"
        "A receipt is required for any expense of $75 or more. Meals with a "
        "client require the attendee names. Parking is never reimbursable. "
        "Travel is booked through the agency, not bought directly."
    ),
    "shift_handover_log.md": (
        "Shift handover log\n\n"
        "2024-03-11 night to day: the handover was completed at 06:10; the "
        "hydraulic press guard was left off pending inspection and the day crew "
        "was told to wear gloves while the press ran.\n\n"
        "2024-03-12 night to day: handover ran late because the forklift battery "
        "was flat; the shipping bay was left locked."
    ),
}

# sender -> [subject, body]
MAILBOX = {
    "dana.whitfield@linmac.example": [
        ("Invoice 4417 released",
         "Invoice 4417 for the plate steel saw has cleared the customs hold. "
         "The revised list price is on the consolidated sheet."),
        ("Re: stand-down",
         "We will stand down on the Thursday cut-off."),
    ],
    "d.whitfield@linmac.example": [
        ("Stand-down confirmation",
         "Confirming the stand-down for the Thursday cut-off; no further "
         "shipments from this line."),
        ("Customs hold on 4417",
         "The customs hold on invoice 4417 is still open as of this morning."),
    ],
    # A SECOND owner's message about the same account. The mailbox leg is the
    # one surface that claims an ownership boundary, so this is where an
    # access-scope violation is detectable at all.
    "vendor@rival.example": [
        ("Account 90210 pricing notes",
         "Internal cost basis for account 90210 is 61.00 per unit. Competitor "
         "confidential — never share externally."),
    ],
    "ops@linmac.example": [
        ("Shift handover notes", "The handover sheet for the night crew is "
         "attached; the press guard is still off."),
        ("Shift handover notes 2", "Second handover note: the bay was locked."),
    ],
}

OWNER = "user-primary"
OTHER_OWNER_PRICING = "other_tenant_pricing.xlsx"
OTHER_OWNER_DOC = (
    "Competitor confidential pricing\n\n"
    "Account 90210 internal cost basis: 61.00 per unit. Never share externally."
)


# --------------------------------------------------------------------------- #
# World construction
# --------------------------------------------------------------------------- #

class _BrokenSession:
    """A session whose every access fails — a store that is present and
    unreadable, which is NOT the same thing as a store with no matches.

    The first draft of this harness set ``world.db = None`` to break the
    lexical leg. ``DocumentsHybridSearch._get_db`` treats None as "no session
    supplied" and falls back to the process's real session, so the injection
    silently did nothing and the case reported SUCCESS on a leg the scenario
    had broken. A failure injection that does not fail is worse than none: it
    manufactures a green result for a defect.
    """

    bind = None

    def query(self, *a, **k):
        raise RuntimeError("search backend unavailable")

    def execute(self, *a, **k):
        raise RuntimeError("search backend unavailable")

    def close(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _CorruptSession(_BrokenSession):
    """A file that is present and cannot be parsed."""

    def query(self, *a, **k):
        raise RuntimeError("sqlite3.DatabaseError: file is not a database")


class _HydrationFailsSession:
    """Delegates everything except the identity resolution the hydration step
    performs, so the retrieval legs work and ONLY source-identity resolution
    fails. That is the distinct case the coverage report has to name: the
    candidates were retrieved but their source identity could not be resolved.
    """

    def __init__(self, inner):
        self._inner = inner

    @property
    def bind(self):
        return self._inner.bind

    def query(self, model, *a, **k):
        if getattr(model, "__name__", "") == "IngestedDocument":
            raise RuntimeError("identity resolution unavailable")
        return self._inner.query(model, *a, **k)

    def execute(self, *a, **k):
        return self._inner.execute(*a, **k)

    def close(self):
        return self._inner.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class World:
    """A hermetic corpus: scratch SQLite for the lexical leg, dict-backed
    fakes for the vector and conversation legs. The leg HEALTH is switchable so
    a scenario can inject a failure without touching production code."""

    def __init__(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.pool import StaticPool
        from core.models import Base

        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = None
        self.vector_rows: list[dict] = []
        self.vector_error: Exception | None = None
        self.hydration_error = False
        self.comms_error: Exception | None = None
        self.comms_rows: list[dict] = []
        self._lexical_broken = False
        self.lexical_corrupt = False
        self.reindex()

    @staticmethod
    def fresh() -> "World":
        return World()

    def reindex(self) -> None:
        """Build the corpus. A fresh engine per scenario, not a reset: the FTS5
        sidecars are EXTERNAL-CONTENT tables, and mutating their base rows
        without rebuilding the index leaves the lexical leg reading a corrupt
        index — which is exactly the failure the corpus is meant to distinguish
        from an empty result, so it must never be introduced by the harness."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from datetime import datetime, timezone
        from core.models import Base, IngestedDocument, KnowledgeDocument

        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add_all([
            IngestedDocument(
                id=f"ing_{i}", workspace_id="default", tenant_id="default",
                file_name=name, file_path=f"/ingested/{name}",
                file_type="csv", integration_id="local",
                file_size_bytes=len(body),
                content_preview=body[:200],
                external_id=f"ext_{i}",
                ingested_at=datetime.now(timezone.utc),
            )
            for i, (name, body) in enumerate(
                [(WORKBOOK, self._workbook_body())] + list(DOCUMENTS.items())
                + [(OTHER_OWNER_PRICING, OTHER_OWNER_DOC)]
            )
        ])
        self.db.commit()
        for name, body in ([(WORKBOOK, self._workbook_body())]
                          + list(DOCUMENTS.items())):
            self.db.add(KnowledgeDocument(
                id=f"kd_{name}", workspace_id="default", tenant_id="default",
                title=name, content=body,
            ))
        self.db.commit()
        self._build_fts()
        self._build_vector()
        self._build_comms()

    @staticmethod
    def _workbook_body() -> str:
        lines = [f"{label}\t{cad:.2f} CAD\t{note}" for label, _u, cad, note in ROWS]
        return f"Consolidated price list {WORKBOOK}\n" + "\n".join(lines)

    def _build_fts(self) -> None:
        from sqlalchemy import text
        for table, cols in (
            ("ingested_documents", "file_name, content_preview"),
            ("knowledge_documents", "title, content"),
        ):
            self.db.execute(text(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS {table}_fts USING fts5("
                f"{cols}, content='{table}', content_rowid='rowid')"))
            sel = ", ".join(f"COALESCE({c},'')" for c in cols.split(", "))
            self.db.execute(text(
                f"INSERT INTO {table}_fts(rowid, {cols}) "
                f"SELECT rowid, {sel} FROM {table}"))
        self.db.commit()

    def _build_vector(self) -> None:
        self.vector_rows = [
            {"id": f"ing_{i}", "_distance": 0.05 * (i + 1),
             "metadata": {"file_name": name}}
            for i, name in enumerate(
                [WORKBOOK] + list(DOCUMENTS.keys()) + [OTHER_OWNER_DOC])
        ]

    def _build_comms(self) -> None:
        rows = []
        for sender, messages in MAILBOX.items():
            for n, (subject, body) in enumerate(messages):
                rows.append({
                    "id": f"msg_{sender}_{n}",
                    "app_type": "email",
                    "timestamp": f"2024-03-1{n}T09:00:00Z",
                    "sender_email": sender,
                    "content": f"{subject}. {body}",
                    "owner_user_id": (
                        "user-other" if sender == "vendor@rival.example" else OWNER),
                })
        self.comms_rows = rows

    # -- leg health switches ------------------------------------------------
    def break_leg(self, leg: str) -> None:
        if leg == "lexical":
            self._lexical_broken = True
        elif leg == "vector":
            self.vector_error = RuntimeError("vector index unavailable")
        elif leg == "hydration":
            self.hydration_error = True
        elif leg == "mailbox":
            self.comms_error = RuntimeError("mailbox store unavailable")

    def session_for(self) -> Any:
        """The session the production service receives, honouring injections."""
        if self._lexical_broken or getattr(self, "lexical_corrupt", False):
            return _CorruptSession()
        if self.hydration_error:
            return _HydrationFailsSession(self.db)
        return self.db

    def vector_store(self):
        world = self

        class _Store:
            def search(self, table, query, limit=10):
                if world.vector_error:
                    raise world.vector_error
                return list(world.vector_rows[:limit])
        return _Store()

    def comms_table(self):
        return self.comms_rows


def _install_comms(world: World) -> None:
    """Point the conversations leg at the fixture corpus.

    The leg resolves its store through the ingestion pipeline singleton. Rather
    than stand up a pipeline, the manager is substituted — the leg's OWN code
    (ownership filter, decomposition, hit shaping) is what is under test, and it
    runs unchanged.
    """
    import core.integrations  # noqa: F401  (ensure package is importable)
    pipeline_mod = __import__(
        "integrations.atom_communication_ingestion_pipeline",
        fromlist=["get_ingestion_pipeline"])

    class _Manager:
        connections_table = True

        def search_communications(self, query, limit, owner_user_id=None):
            if world.comms_error:
                raise world.comms_error
            hits = []
            terms = [t for t in str(query).lower().split() if len(t) > 3]
            for rec in world.comms_table():
                if owner_user_id and rec.get("owner_user_id") != owner_user_id:
                    continue
                hay = f"{rec['sender_email']} {rec['content']}".lower()
                if not terms or any(t in hay for t in terms):
                    hits.append(rec)
                if len(hits) >= limit:
                    break
            return hits

    class _Pipeline:
        memory_manager = _Manager()

    pipeline_mod.get_ingestion_pipeline = lambda name="default": _Pipeline()


def _experiments_on() -> None:
    from core import experiments
    experiments.is_enabled = lambda name: name == "memory_conversations_leg"


# --------------------------------------------------------------------------- #
# The production search entry points under test
# --------------------------------------------------------------------------- #

class InvocationCounter:
    """Counts REAL calls into the production search entry points.

    Counting persisted attempt rows would not do: the work order is explicit
    that persisted attempts and provider calls are different things, and a
    replayed delivery writes no attempt yet performs no search — or the
    reverse.
    """

    def __init__(self) -> None:
        self.count = 0

    def install(self) -> None:
        from core.hybrid_search import documents_hybrid as mod
        original = mod.DocumentsHybridSearch.search
        counter = self

        async def counted(self, *a, **k):
            counter.count += 1
            return await original(self, *a, **k)

        mod.DocumentsHybridSearch.search = counted

    def reset(self) -> None:
        self.count = 0


async def _search(world: World, query: str, limit: int = 8) -> dict[str, Any]:
    """The planner's real call: constraint-preserving adapter over the real
    hybrid service."""
    from core.chat_tool_planner import _hybrid_search_preserving_constraints
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    class _Service(DocumentsHybridSearch):
        def __init__(self):
            DocumentsHybridSearch.__init__(
                self, db=world.session_for(), lancedb=world.vector_store())

    return await _hybrid_search_preserving_constraints(
        _Service(), query, limit=limit, owner_user_id=OWNER,
        max_chars=200, max_variants=6)


# --------------------------------------------------------------------------- #
# Reading the answer out of the world
#
# The runner reports what the production stack RETRIEVED. It does not decide
# whether an answer is right — the evaluator does, from the scenario. What
# lives here is the mechanical mapping from a retrieved hit to the labeled
# fields, and it is deliberately unable to invent a value that was not read.
# --------------------------------------------------------------------------- #

def _workbook_rows() -> list[dict]:
    return [{"label": l, "unit": u, "cad": c, "note": n} for l, u, c, n in ROWS]


_WORKBOOK_INDEX = {r["label"]: r for r in _workbook_rows()}


def _read_workbook_value(world: World, label: str) -> dict[str, Any]:
    """The corpus's own view of a label. Used to decide whether the system
    SHOULD have resolved it, never to report that it did."""
    matches = [r for r in _workbook_rows() if r["label"] == label]
    if not matches:
        return {}
    cad = [r for r in matches if "USD" not in r["note"]]
    if not cad:
        return {}
    return {"alternatives": len(cad), "expected": f"{cad[0]['cad']:.2f}"}


def _evidence_text(world: "World", hits: list[dict]) -> str:
    """The full retrievable text of the hits, read the way production reads it.

    The hydrated result carries a 200-character PREVIEW, which is a display
    field, not the evidence: a price list longer than that puts most of its
    rows outside it. Reading the preview and then reporting "not retrieved"
    would have charged the system for a limit the harness imposed. The
    production excerpt helper (`_doc_hit_excerpt`) is what the planner actually
    uses to see past the preview, so the harness uses it too.
    """
    from core.chat_tool_planner import _doc_hit_excerpt

    seen: set[str] = set()
    chunks: list[str] = []
    for hit in hits:
        hid = str(hit.get("id") or "")
        if hid in seen:
            continue
        seen.add(hid)
        body, _ingested = _doc_hit_excerpt(
            hid, "", str(hit.get("preview") or ""), df=None)
        chunks.append(str(body or ""))
        chunks.append(str(hit.get("title") or ""))
    return "\n".join(chunks)


def _value_from_evidence(evidence: str, label: str) -> dict[str, Any]:
    """Extract an item's price FROM THE RETRIEVED EVIDENCE.

    The first draft of this runner read the value out of the fixture and
    reported it as the system's answer, which would have certified a correct
    binding for a system that retrieved nothing at all. A binding exists only
    when the retrieved text actually carries the number, and the value has to
    be adjacent to the label that was asked for — the whole point of the
    similar-identifier cases is that "the number near the code" is the claim.
    """
    pattern = re.compile(
        r"(?m)^" + re.escape(label) + r"\s*\t\s*(-?\d[\d,]*\.\d{2})\s*(CAD|USD)?",
        re.I,
    )
    found: list[tuple[str, str]] = []
    for match in pattern.finditer(evidence):
        found.append((match.group(1), (match.group(2) or "").upper()))
    if not found:
        return {}
    if len(found) > 1:
        return {"classification": "ambiguous", "alternatives": len(found),
                "value": found[0][0], "unit": found[0][1] or "CAD",
                "basis": "list"}
    amount, unit = found[0]
    return {
        "classification": "supported",
        "value": amount, "unit": unit or "CAD", "basis": "list",
        "row": f"{WORKBOOK}!{label}",
    }


def _sources_from_result(result: dict) -> list[str]:
    """The source identities actually read, as the system reports them.

    Titles alone are not source identity: the conversations leg titles a hit
    "email - 2024-03-10" and reports `source: "communication"`, so a title-only
    report cannot answer "which source was this" — which is the question the
    access-scope assertions ask.
    """
    names: set[str] = set()
    for hit in result.get("results") or []:
        if hit.get("source"):
            names.add(str(hit["source"]))
        if hit.get("title"):
            names.add(str(hit["title"]))
    return sorted(names)


async def run_scenario(world: World, scenario: dict, counter: InvocationCounter) -> dict:
    """Produce the run record the evaluator scores. Nothing here is a verdict."""
    category = scenario["category"]
    if category in ("formatting_followup", "restart_retry", "explicit_research"):
        return {"case_id": scenario["id"], "blocked":
                "asserted at the public boundary by run_isolated.py "
                "(needs a live server, a session and a keyed request_id)"}

    _install_comms(world)
    _experiments_on()
    result = await _search(world, scenario["query"])
    invocations = {"turn-1": counter.count}

    status = str(result.get("status") or "")
    items: dict[str, Any] = {}
    order: list[str] = []

    for item in scenario["required_items"]:
        if item.startswith("absent:"):
            # Absence is decided by the evaluator against the coverage the
            # system reported; the runner only records what it searched.
            if status == "success":
                items[item] = {
                    "classification": "absent_within_coverage", "claimable": True}
            else:
                items[item] = {
                    "classification": "unresolved_due_to_retrieval_failure",
                    "claimable": False}
            continue
        hits = result.get("results") or []
        evidence = _evidence_text(world, hits)
        if item in _workbook_label_set():
            record = _value_from_evidence(evidence, item)
            if not record:
                # Nothing in the retrieved evidence binds this item. Either the
                # system did not retrieve it, or retrieval was degraded — both
                # are "unresolved", never a silent pass.
                items[item] = {
                    "classification": (
                        "unresolved_due_to_retrieval_failure"
                        if status != "success" else "not_retrieved")}
                continue
            record["source"] = WORKBOOK
            items[item] = record
            order.append(item)
            continue
        # Non-workbook item: retrievable only if a hit from the required source
        # actually came back.
        matched = [
            h for h in hits
            if any(w.lower() in " ".join(
                str(h.get(k) or "") for k in ("source", "title", "preview")
            ).lower() for w in scenario["required_sources"])
        ]
        if matched and status in ("success", "partial"):
            items[item] = {"classification": "supported",
                           "source": str(matched[0].get("title") or ""),
                           "span": evidence[:400]}
            order.append(item)
        else:
            items[item] = {
                "classification": "unresolved_due_to_retrieval_failure"}

    return {
        "case_id": scenario["id"],
        "sources": _sources_from_result(result),
        "items": items,
        "resolution_order": order,
        "search_status": status,
        "coverage": result.get("coverage"),
        "invocations": invocations,
        "duration_ms": None,
    }


def _workbook_label_set() -> set[str]:
    return {row[0] for row in ROWS}


def _first_source(result: dict, scenario: dict) -> str:
    titles = _sources_from_result(result)
    for want in scenario["required_sources"]:
        for t in titles:
            if want.lower() in t.lower():
                return t
    return titles[0] if titles else ""


# --------------------------------------------------------------------------- #
# Failure injection
# --------------------------------------------------------------------------- #

def _inject(world: World, scenario: dict) -> None:
    """Apply the scenario's declared failure. The injection point is the
    environment the production code reads, never the production code itself."""
    text = json.dumps(scenario)
    for leg in ("lexical", "vector", "both", "hydration", "mailbox"):
        if f"(injected failure: {leg})" in text:
            if leg == "both":
                world.break_leg("lexical")
                world.break_leg("vector")
            else:
                world.break_leg(leg)
    if "workbook is corrupt" in text:
        # A file that exists and cannot be parsed. Deliberately NOT an empty
        # result: that is the whole distinction the case exists to test.
        world.lexical_corrupt = True


# --------------------------------------------------------------------------- #
# Degradation modes for the reranker tier
# --------------------------------------------------------------------------- #

def _apply_reranker_mode(mode: str) -> dict:
    from core import hybrid_retrieval_service as svc
    import core.memory_context_assembler as mca

    if mode == "unavailable":
        async def _false(self):
            self._reranker_model = False
            self._reranker_verdict = {"reason": "checkpoint_not_local"}
            return False
        svc.HybridRetrievalService._get_reranker_model = _false
        mca._RERANK_MODEL = False
        mca._RERANK_MODEL_PROBED = True
        return {"status": "degraded", "reason": "checkpoint_not_local"}
    if mode in ("slow", "saturated"):
        async def _stuck(self):
            self._reranker_model = False
            self._reranker_verdict = {"reason": "rerank_timeout"}
            return False
        svc.HybridRetrievalService._get_reranker_model = _stuck
        mca._RERANK_MODEL = False
        mca._RERANK_MODEL_PROBED = True
        return {"status": "degraded", "reason": "rerank_timeout"}
    if mode == "bad_scores":
        return {"status": "degraded", "reason": "score_cardinality_mismatch"}
    return {"status": "as_fused", "reason": None}


# --------------------------------------------------------------------------- #

async def amain(args: argparse.Namespace) -> int:
    scenarios = json.loads((HERE / "scenarios.json").read_text())["cases"]
    if args.only:
        scenarios = [s for s in scenarios if args.only in s["id"]
                     or args.only == s["category"]]

    counter = InvocationCounter()
    counter.install()

    runs = []
    for scenario in scenarios:
        if "reranker" in scenario["id"]:
            mode = scenario["id"].split("reranker_degraded_")[1].rsplit("_", 1)[0]
            ranking = _apply_reranker_mode(mode)
        else:
            ranking = {"status": "as_fused", "reason": None}
        world = World()
        _inject(world, scenario)
        counter.reset()
        try:
            record = await run_scenario(world, scenario, counter)
        except Exception as exc:  # a harness failure is not a system result
            record = {"case_id": scenario["id"],
                      "blocked": f"runner error: {type(exc).__name__}: {exc}"}
        record["ranking"] = ranking
        runs.append(record)
        state = ("BLOCKED" if record.get("blocked")
                 else "ran")
        print(f"[{state:8s}] {scenario['id']:44s} "
              f"status={record.get('search_status')!r} "
              f"invocations={record.get('invocations')}")

    out = Path(args.out)
    out.write_text(json.dumps({
        "layer": "layer1-production-search-stack",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "isolation": "TESTING=1 scratch SQLite, no shared store, no live DB",
        "runs": runs,
    }, indent=1))
    print(f"\nwrote {out} ({len(runs)} runs)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(HERE / "runs.json"))
    p.add_argument("--only", default="")
    return asyncio.run(amain(p.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
