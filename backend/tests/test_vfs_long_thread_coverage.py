"""Long email threads must be VISIBLE and SEARCHABLE by agents.

Live 2026-09-13 (canvas `a1a13834…`, Seguin vendor-cost lookup): the mailbox
store held 7,009 messages and 3,395 of them are longer than the 2,500-char
excerpt cap (the longest is 79,017 chars — a quoted thread), but the agent's
knowledge VFS could only ever see the first 200 rows of the store:

* ``ls knowledge/conversations`` → ``table.head(200)`` — messages 201+ were
  simply absent from the tree, so the agent could not discover them at all;
* ``grep`` → the same first-200 window, so a figure/name living in message
  5,000 was unfindable no matter what the agent searched for;
* ``cat`` on an id beyond the head window fell back to a kNN+``where`` read
  (needs an embedder, and the write path stores ZERO vectors when none is
  configured — the "Open existing atom_communications table" + "comm vectors
  will be zeros" warning in the live log), so even a known id could come back
  empty;
* ``to_arrow()`` cannot project columns on this lancedb build (``to_lance()``
  needs the optional ``lance`` package), so a naive full scan materializes the
  two 384-dim vector columns plus ``metadata`` (median 49 KB/row, max 33 MB)
  — 3.0 GB of Arrow for 7k rows.

These tests pin the fix: a FULL but bounded, vector-free, metadata-free scan
on all three conversation operations, a visible cap with an honest note when
the store is larger than what one listing can carry, and per-message citation
caps in grep so a common word cannot flood the agent's context.
"""

import os

os.environ.setdefault("TESTING", "1")

import asyncio
import json

import pytest

from integrations.vfs.knowledge_vfs import KnowledgeVFSProvider


# --------------------------------------------------------------------------- #
# A fake comms table with MORE rows than any head window, whose only match
# lives at the very END of the store — the exact shape of the live failure.
# --------------------------------------------------------------------------- #

ROWS = 500
MATCH_ROW = ROWS - 1  # message #500, far past head(200)/head(2000) windows


class _FakeArrow:
    """Minimal Arrow-ish table: records + select() column projection."""

    def __init__(self, records):
        self._records = records

    def select(self, cols):
        return _FakeArrow([{c: r.get(c) for c in cols} for r in self._records])

    def slice(self, offset, length=None):
        end = None if length is None else offset + length
        return _FakeArrow(self._records[offset:end])

    def to_pylist(self):
        return list(self._records)


def _records():
    out = []
    for i in range(ROWS):
        out.append({
            "id": f"msg-{i:04d}",
            "app_type": "outlook",
            "timestamp": f"2026-08-{(i % 28) + 1:02d}T10:00:00",
            "direction": "inbound",
            "sender": f"person{i % 7}@supplier.example",
            "recipient": "sales@brennan.ca",
            "subject": f"RE: RFQ thread {i % 13}",
            "content": (
                "ordinary thread body " * 20
                if i != MATCH_ROW
                else "… long quoted history …\n$ 5,350.00 – 10 % in stock\n…"
            ),
            # The real column: median 49 KB, max 33 MB. A correct reader must
            # never pull it for ls/grep.
            "metadata": json.dumps({"html_body": "x" * 4000}),
            "vector": [0.0] * 16,
        })
    return out


class _FakeTable:
    def __init__(self, records=None):
        self._records = records if records is not None else _records()
        self.head_calls = []
        self.full_scan_calls = 0

    # The buggy path: only ever the first N rows.
    def head(self, n):
        self.head_calls.append(n)
        return _FakeArrow(self._records[:n])

    # The fixed path.
    def to_arrow(self):
        self.full_scan_calls += 1
        return _FakeArrow(self._records)

    def count_rows(self):
        return len(self._records)

    def search(self, *a, **k):
        raise AssertionError("conversation read must not need a vector search")

    def schema(self):
        return None


def _provider(monkeypatch, table):
    v = KnowledgeVFSProvider()
    monkeypatch.setattr(v, "_comms_table", lambda: table)
    return v


def _run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------- #
# searchable: grep must reach the whole store
# --------------------------------------------------------------------------- #

def test_grep_finds_a_match_in_the_last_message(monkeypatch):
    """RED before the fix: grep only scanned the first 200 rows, so the
    '$ 5,350.00' message at row 500 was invisible to the agent."""
    table = _FakeTable()
    v = _provider(monkeypatch, table)

    hits = _run(v.grep(r"\$?\s*5,350\.00", "knowledge/conversations"))

    assert hits, "grep must scan the WHOLE comms store, not the head window"
    assert hits[0].path == f"knowledge/conversations/msg-{MATCH_ROW:04d}"
    assert "5,350.00" in hits[0].snippet


def test_grep_never_materializes_metadata(monkeypatch):
    """metadata is 49 KB/row median (33 MB max live) and vectors add 3 KB/row.
    Scanning it for a regex would blow the agent's memory budget for data it
    never reads."""
    seen_columns = []

    class RecordingArrow(_FakeArrow):
        def select(self, cols):
            seen_columns.append(tuple(cols))
            return super().select(cols)

    class RecordingTable(_FakeTable):
        def to_arrow(self):
            self.full_scan_calls += 1
            return RecordingArrow(self._records)

    v = _provider(monkeypatch, RecordingTable())
    _run(v.grep("ordinary", "knowledge/conversations"))

    assert seen_columns, "the scan must project columns"
    for cols in seen_columns:
        assert "metadata" not in cols and "vector" not in cols, cols


def test_grep_caps_citations_per_message(monkeypatch):
    """"the" appears hundreds of times in a long thread; one message must not
    eat the agent's whole result budget."""
    table = _FakeTable()
    v = _provider(monkeypatch, table)

    hits = _run(v.grep("ordinary", "knowledge/conversations"))

    per_path = {}
    for h in hits:
        per_path[h.path] = per_path.get(h.path, 0) + 1
    assert per_path, "expected hits"
    assert max(per_path.values()) <= 5, per_path


def test_grep_anchored_pattern_matches_past_the_first_line(monkeypatch):
    """grep semantics: `^`/`$` anchor per LINE. The whole-text fast-skip in
    _cites_for_text used to swallow any `^…` pattern whose match is not at
    the very start of the message — silent false negatives, the same family
    as the head-window bug this file pins."""
    recs = _records()
    recs[7]["content"] = "intro line\nquoted history line"
    v = _provider(monkeypatch, _FakeTable(recs))

    hits = _run(v.grep("^quoted", "knowledge/conversations"))

    assert hits, "a line-anchored pattern must match at any line start"
    assert hits[0].line == 2
    assert "quoted history line" in hits[0].snippet


def test_projection_drift_degrades_to_present_columns():
    """Real pyarrow select() raises KeyError for a missing column. The
    fallback must project to the requested-∩-existing columns (schema drift
    on an open_table'd store) — NEVER return the unprojected table, which on
    this build materializes the vector + metadata columns (GBs for the live
    comms store)."""
    import pyarrow as pa

    class _PaWrap:
        def __init__(self, t):
            self._t = t

        def to_arrow(self):
            return self._t

    tbl = _PaWrap(pa.table({
        "id": ["a", "b"],
        "content": ["x", "y"],
        "metadata": ["m1", "m2"],
    }))

    out = KnowledgeVFSProvider()._projected_table(tbl, ["id", "content", "nope"])

    assert list(out.column_names) == ["id", "content"], list(out.column_names)
    assert "metadata" not in set(out.column_names), (
        "a drifted projection must never leak the unprojected columns"
    )


def test_whole_store_read_uses_the_streaming_projection(monkeypatch):
    """The ladder's first rung must be the query-builder projection: full
    ``to_arrow()`` on the live comms store materializes 3.07 GB of vectors +
    metadata (measured) versus 34 MB projected."""
    import pyarrow as pa

    seen = {}

    class _Builder:
        def select(self, cols):
            seen["selected"] = list(cols)
            return self

        def limit(self, n):
            seen["limit"] = n
            return self

        def to_batches(self, batch_size=None):
            seen["batch_size"] = batch_size
            return iter([pa.record_batch({"id": ["a"], "content": ["x"]})])

        def to_arrow(self):
            seen["to_arrow"] = True
            return pa.table({"id": ["a"], "content": ["x"], "metadata": ["m"]})

    class _Table:
        def search(self):
            return _Builder()

        def to_arrow(self):
            raise AssertionError(
                "the full-table read is the 3 GB path this reader exists to avoid"
            )

    rows = list(KnowledgeVFSProvider()._stream_rows(
        _Table(), ["id", "content"], None, 500
    ))

    assert rows == [{"id": "a", "content": "x"}]
    assert seen.get("selected") == ["id", "content"], seen
    assert seen.get("to_arrow") is not True, "must stream, not materialize"


# --------------------------------------------------------------------------- #
# discoverable: the search surfaces that hand the agent a 400-char excerpt
# must also hand it the way to the full message
# --------------------------------------------------------------------------- #

def test_search_communications_results_cite_the_full_thread(monkeypatch):
    """`search_communications` clips content at 400 chars. A live quote thread
    is 79k chars, so the clip MUST come with (a) the real length and (b) the
    VFS path that resolves to the whole message — otherwise the agent reads a
    head excerpt and reports the figure as 'not ingested' (live 2026-09-13)."""
    import core.action_registry as ar

    long_body = "intro\n" + ("quoted history " * 500) + "price $ 5,350.00 net"

    class _Pipeline:
        class memory_manager:
            connections_table = object()

            @staticmethod
            def initialize():
                return True

            @staticmethod
            def search_communications(query, limit):
                return [{
                    "id": "msg-42", "app_type": "outlook",
                    "timestamp": "2026-08-26T14:06:28", "content": long_body,
                }]

    monkeypatch.setattr(
        "integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline",
        lambda *a, **k: _Pipeline(),
    )

    res = _run(ar.action_registry.execute_action(
        "search_communications", {"query": "seguin shear", "limit": 5}, {}
    ))

    assert res.get("success"), res
    hit = res["results"][0]
    assert len(hit["content"]) == 400, "excerpt stays bounded"
    assert hit["content_chars"] == len(long_body), "the real length must be visible"
    assert hit["full_path"] == "knowledge/conversations/msg-42", (
        "the agent needs the citable path to the complete thread"
    )


def test_grounding_rule_teaches_recursive_expansion():
    """Every tool block carries the grounding contract. If it does not say how
    to expand an excerpt, the agent's only honest option is 'not in the data' —
    the exact wrong answer from the incident."""
    import core.chat_tool_planner as ctp

    rule = ctp._GROUNDING_RULE
    assert "documents.cat" in rule
    assert "knowledge/conversations" in rule
    assert "documents.grep" in rule
    assert "EXCERPT" in rule.upper()


# --------------------------------------------------------------------------- #
# visible: ls must reach the whole store (with an honest cap)
# --------------------------------------------------------------------------- #

def test_ls_lists_messages_beyond_the_head_window(monkeypatch):
    """RED before the fix: ls returned the 200 newest (head) rows only."""
    table = _FakeTable()
    v = _provider(monkeypatch, table)

    nodes = _run(v.ls("knowledge/conversations"))

    names = {n.name for n in nodes}
    assert f"msg-{MATCH_ROW:04d}" in names, "the oldest/last message must be listed"
    assert len(nodes) > 200


def test_ls_carries_sender_subject_and_date(monkeypatch):
    """A bare id tells the agent nothing about which thread to open — the
    listing must carry who/when/what so a 7k-message mailbox is navigable."""
    v = _provider(monkeypatch, _FakeTable())

    nodes = _run(v.ls("knowledge/conversations"))
    target = next(n for n in nodes if n.name == "msg-0003")

    meta = target.meta or {}
    assert "2026-08" in str(target.modified or "")
    assert meta.get("sender") == "person3@supplier.example"
    assert "RFQ thread" in str(meta.get("subject") or "")
    assert target.size, "body size tells the agent this is a long thread"


def test_ls_reports_the_total_and_truncation(monkeypatch):
    """When the store is bigger than one listing, say so instead of silently
    showing a prefix (the original bug was a SILENT 200-row window)."""
    table = _FakeTable(_records() * 40)  # 20,000 messages
    v = _provider(monkeypatch, table)

    nodes = _run(v.ls("knowledge/conversations"))

    # The bound is on MESSAGES; the truncation note is one extra entry.
    assert len(nodes) <= 2001, "a listing must stay bounded"
    note = getattr(nodes[-1], "type", "")
    assert note in ("note", "info") or "total" in str(getattr(nodes[-1], "path", "")), (
        "a truncated listing must carry a visible truncation note"
    )


# --------------------------------------------------------------------------- #
# readable: cat must not depend on the embedder
# --------------------------------------------------------------------------- #

def test_cat_resolves_an_id_beyond_the_head_window(monkeypatch):
    """RED before the fix: _get_conversation looked in head(2000) and then
    fell back to a kNN `where` read, which needs an embedder the host may not
    have (write path then stores zero vectors)."""
    v = _provider(monkeypatch, _FakeTable())

    res = _run(v.cat(f"knowledge/conversations/msg-{MATCH_ROW:04d}/content.lines"))

    assert res.lines, "the full body must be readable by id"
    assert any("5,350.00" in line for line in res.lines)


def test_cat_returns_the_whole_long_thread(monkeypatch):
    """Long threads are the case that matters: the body must not be clipped
    on the way out of the VFS."""
    long_body = "line one\n" + ("middle quoted history\n" * 5000) + "final line"
    recs = _records()
    recs[3]["content"] = long_body
    v = _provider(monkeypatch, _FakeTable(recs))

    res = _run(v.cat("knowledge/conversations/msg-0003/content.lines"))

    assert len(res.lines) == long_body.count("\n") + 1
    assert "final line" in res.lines[-1]
    assert res.meta.get("app_type") == "outlook" and res.meta.get("timestamp")


# --------------------------------------------------------------------------- #
# the store must be initialized on demand
# --------------------------------------------------------------------------- #

def test_comms_table_initializes_an_unopened_manager(monkeypatch):
    """Live 2026-09-13: a fresh process found ``db is None`` and the old
    guard (``table is None and db is not None``) skipped ``initialize()`` —
    which is the very call that OPENS the db and creates the table — so every
    conversation call degraded to empty until unrelated code initialized the
    pipeline. The store must come up on demand."""
    class _Manager:
        def __init__(self):
            self.db = None
            self.connections_table = None
            self.initialize_calls = 0

        def initialize(self):
            self.initialize_calls += 1
            self.db = object()
            self.connections_table = "TABLE"
            return True

    class _Pipeline:
        def __init__(self, manager):
            self.memory_manager = manager

    manager = _Manager()
    monkeypatch.setattr(
        "integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline",
        lambda *a, **k: _Pipeline(manager),
    )

    table = KnowledgeVFSProvider()._comms_table()

    assert table == "TABLE", "a not-yet-opened store must be initialized on demand"
    assert manager.initialize_calls == 1


# --------------------------------------------------------------------------- #
# a WRITE must not stay invisible behind the read cache
# --------------------------------------------------------------------------- #

def test_store_write_invalidates_the_cached_rows(monkeypatch):
    """The VFS caches projected whole-store reads for a short TTL (agents hit
    ls → grep → cat in one turn). Without an invalidation hook on the write
    path, the on-demand ingest fallback — 'search missed → pull the message →
    re-run the search' — would pull a message and immediately re-read a cache
    that predates it, so the agent still saw 'not in the mailbox'."""
    from core.vfs_registry import get_provider, register_provider
    from integrations.atom_communication_ingestion_pipeline import (
        LanceDBMemoryManager,
    )

    provider = KnowledgeVFSProvider()
    register_provider(provider)
    try:
        assert get_provider("knowledge") is provider

        provider._rows_cache[("comms", ("id", "content"), None)] = (0.0, [{"id": "old"}])
        assert provider._rows_cache, "precondition: a cached read"

        LanceDBMemoryManager._invalidate_vfs_rows_cache()

        assert provider._rows_cache == {}, (
            "ingesting a message must drop the VFS read cache so the very next "
            "search in the same turn sees it"
        )
    finally:
        provider.invalidate_rows_cache()


def test_write_path_calls_the_invalidator():
    """The hook must be ON the write path, not merely available."""
    import inspect

    from integrations.atom_communication_ingestion_pipeline import (
        LanceDBMemoryManager,
    )

    src = inspect.getsource(LanceDBMemoryManager.ingest_communication)
    assert "_invalidate_vfs_rows_cache()" in src, (
        "ingest_communication is the single row-write choke point "
        "(ingest_batch delegates to it) — it must invalidate the VFS cache"
    )


# --------------------------------------------------------------------------- #
# CHUNKED attachments must be OPENABLE, not just greppable
# --------------------------------------------------------------------------- #

def test_cat_assembles_a_chunked_document(monkeypatch):
    """Live 2026-09-15: the F-5216 forwarded email attaches `PRICE VIPUL
    (6).xlsx`, ingested as 59 chunks (`ext_…::c0 … ::c58`) with NO row of its
    own. grep found the chunk carrying `R235 … 7519` while
    `documents.cat('knowledge/documents/ext_…')` returned nothing — so an
    agent could locate a spreadsheet row and then be unable to open the file
    it sits in. The reader now assembles the family in chunk order."""
    from integrations.vfs.knowledge_vfs import KnowledgeVFSProvider

    chunks = [
        {"id": "ext_doc::c2", "text": "third", "source": "outlook:x.xlsx",
         "metadata": "{}"},
        {"id": "ext_doc::c0", "text": "first", "source": "outlook:x.xlsx",
         "metadata": "{}"},
        {"id": "ext_doc::c10", "text": "eleventh", "source": "outlook:x.xlsx",
         "metadata": "{}"},
        {"id": "other", "text": "unrelated", "source": "outlook:y.xlsx",
         "metadata": "{}"},
    ]

    class _Arrow:
        def to_pylist(self):
            return chunks

    class _Builder:
        def select(self, cols):
            return self

        def to_arrow(self):
            return _Arrow()

    class _Table:
        def search(self):
            return _Builder()

    class _Handler:
        def get_table(self, name):
            return _Table()

        def get_document_by_id(self, table, doc_id):
            return None  # the parent has no row of its own

    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler", lambda *a, **k: _Handler()
    )

    rows = KnowledgeVFSProvider._chunk_family_rows("ext_doc")

    assert [r["id"] for r in rows] == ["ext_doc::c0", "ext_doc::c2", "ext_doc::c10"], (
        "chunks must be assembled in NUMERIC order (c10 after c2, not before)"
    )


def test_chunk_family_empty_for_unknown_doc(monkeypatch):
    from integrations.vfs.knowledge_vfs import KnowledgeVFSProvider

    class _Arrow:
        def to_pylist(self):
            return []

    class _Builder:
        def select(self, cols):
            return self

        def to_arrow(self):
            return _Arrow()

    class _Table:
        def search(self):
            return _Builder()

    class _Handler:
        def get_table(self, name):
            return _Table()

    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler", lambda *a, **k: _Handler()
    )

    assert KnowledgeVFSProvider._chunk_family_rows("nope") == []


# --------------------------------------------------------------------------- #
# BOUNDED REGION READS — the general primitive for large artifacts
# --------------------------------------------------------------------------- #
#
# A leaf can be tens of thousands of lines. The only reads were `cat`
# (everything) and head/tail (the ends), so agents either blew their context or
# skipped the file — and a skipped file is what produced an invented $8,880
# derivation while the real row sat at line 315 of a 324-line workbook.
# `documents.read(path, start_line, max_lines)` returns a self-describing
# window (start/end/total/next_start/complete) so paging is a loop the model
# can drive without guessing.


def test_read_region_slices_and_reports_paging():
    from core.vfs_base import VFSProvider, VFSRegion, VFSResource

    class _P(VFSProvider):
        prefix = "t"

        async def ls(self, path, ctx=None):
            return []

        async def cat(self, path, ctx=None):
            return VFSResource(
                path=path, lines=[f"L{i}: row {i}" for i in range(1, 101)]
            )

        async def grep(self, pattern, path_prefix, ctx=None):
            return []

    region = asyncio.run(_P().read_region("t/leaf", start_line=41, max_lines=10))

    assert isinstance(region, VFSRegion)
    assert region.lines[0] == "L41: row 41"
    assert len(region.lines) == 10
    assert region.total_lines == 100
    assert region.next_start == 51
    d = region.to_dict()
    assert d["start_line"] == 41 and d["end_line"] == 50
    assert d["complete"] is False and d["returned_lines"] == 10


def test_read_region_end_of_content_marks_complete():
    from core.vfs_base import VFSProvider, VFSResource

    class _P(VFSProvider):
        prefix = "t"

        async def ls(self, path, ctx=None):
            return []

        async def cat(self, path, ctx=None):
            return VFSResource(path=path, lines=["L1: a", "L2: b", "L3: c"])

        async def grep(self, pattern, path_prefix, ctx=None):
            return []

    region = asyncio.run(_P().read_region("t/leaf", start_line=3, max_lines=10))

    assert region.lines == ["L3: c"]
    assert region.next_start is None
    assert region.to_dict()["complete"] is True


def test_read_region_clamps_start_past_end():
    from core.vfs_base import VFSProvider, VFSResource

    class _P(VFSProvider):
        prefix = "t"

        async def ls(self, path, ctx=None):
            return []

        async def cat(self, path, ctx=None):
            return VFSResource(path=path, lines=["L1: a"])

        async def grep(self, pattern, path_prefix, ctx=None):
            return []

    region = asyncio.run(_P().read_region("t/leaf", start_line=99, max_lines=5))

    assert region.lines == []
    assert region.total_lines == 1
    assert region.next_start is None


def test_read_region_action_is_registered():
    """The agent-facing surface must exist and be advertised."""
    from core import action_registry as ar

    names = set(ar.action_registry.list_actions())
    assert "documents.read" in names
    definition = ar.action_registry.get_action("documents.read")
    desc = (definition.description or "").lower()
    assert "bounded" in desc and "next_start" in desc


def test_grep_citations_carry_a_runnable_bounded_read(monkeypatch):
    """A hit at line 315 of a 324-line workbook is useless unless the agent can
    fetch that region without pulling the whole file. Every citation ships the
    ready-to-run bounded read for exactly the region that shows it."""
    import pyarrow as pa

    from integrations.vfs.knowledge_vfs import KnowledgeVFSProvider

    class _FakeCommsTable:
        def head(self, n):
            return pa.table({"id": pa.array([]), "content": pa.array([])})

        def to_arrow(self):
            return self.head(0)

    rows = [
        {"id": "ext_doc::c57", "text": "R235 | F-52\"x16G | 7519.0",
         "source": "outlook:x.xlsx", "metadata": None},
    ]

    class _Arrow:
        def select(self, cols):
            return self

        def slice(self, *a):
            return self

        def to_pylist(self):
            return rows

    class _Builder:
        def select(self, cols):
            return self

        def limit(self, n):
            return self

        def to_batches(self, batch_size=None):
            return iter([pa.record_batch({"id": ["ext_doc::c57"],
                                          "text": ["R235 | F-52\"x16G | 7519.0"]})])

        def to_arrow(self):
            return _Arrow()

    class _Table:
        def search(self):
            return _Builder()

        def head(self, n):
            return _Arrow()

        def to_arrow(self):
            return _Arrow()

    class _Handler:
        def get_table(self, name):
            return _Table()

        def list_document_heads(self, *a, **k):
            return []

    v = KnowledgeVFSProvider()
    monkeypatch.setattr(v, "_comms_table", lambda: _FakeCommsTable())
    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler", lambda *a, **k: _Handler()
    )

    hits = asyncio.run(v.grep("R235", "knowledge/documents"))

    assert hits, "expected a document hit"
    snippet = hits[0].snippet
    assert "documents.read(" in snippet, snippet
    # the hint must name the SAME path the citation does, or line numbers skew
    assert hits[0].path in snippet, (hits[0].path, snippet)
    assert "start_line=" in snippet
