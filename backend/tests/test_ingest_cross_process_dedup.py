"""Cross-process ingest idempotency (store-level dedup guard).

Observed Sep 5, 2026: a second manually-started uvicorn instance
double-polled the same mailbox. The seen-id map is per-process, and each
instance's poll_fetch_state.json saves reverted the other's cursors — one
message was re-ingested 25x in 6h (25 duplicate rows + 25 knowledge-graph
extraction calls billed to OpenRouter's most expensive routed models).

Fix: ingest_communication now checks the SHARED LanceDB table for an
existing row (same owner or unstamped) before add() — the store is the
only cross-process authority. Different-owner rows still ingest
(ownership-scoped search keeps them invisible; same contract as
_dedup_messages). Lookup failure fails open.
"""
import os
os.environ.setdefault("TESTING", "1")

import json
import tempfile
from unittest.mock import MagicMock

import pyarrow as pa
import pytest

from integrations.atom_communication_ingestion_pipeline import (
    CommunicationData,
    LanceDBMemoryManager,
)


SCHEMA = pa.schema([
    pa.field("id", pa.string()),
    pa.field("app_type", pa.string()),
    pa.field("timestamp", pa.string()),
    pa.field("direction", pa.string()),
    pa.field("sender", pa.string()),
    pa.field("recipient", pa.string()),
    pa.field("subject", pa.string()),
    pa.field("content", pa.string()),
    pa.field("attachments", pa.string()),
    pa.field("metadata", pa.string()),
    pa.field("status", pa.string()),
    pa.field("priority", pa.string()),
    pa.field("tags", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), 4)),
    pa.field("search_vector", pa.list_(pa.float32(), 4)),
])


def _manager_with_store(rows):
    tmp = tempfile.mkdtemp()
    mgr = LanceDBMemoryManager.__new__(LanceDBMemoryManager)
    mgr.db = MagicMock()
    mgr.embedding_dim = 4
    mgr.metadata_table = MagicMock()
    mgr._metadata_pending = {}
    from datetime import datetime
    mgr._metadata_last_flush = datetime.now()
    mgr.connections_table = MagicMock()
    real = mgr.connections_table
    real.add = MagicMock()
    # A real arrow-backed table so the where() point lookup executes.
    if rows:
        real.to_arrow = MagicMock(return_value=pa.Table.from_pylist(rows, schema=SCHEMA))
    else:
        real.to_arrow = MagicMock(return_value=pa.Table.from_pylist([], schema=SCHEMA))
    return mgr, real


def _make_search_stub(arrow_result):
    """Mock the table's search() chain to filter our real arrow table the
    way LanceDB's where(prefilter) would — enough to exercise the guard's
    parsing logic without a live vector index."""
    def search(*a, **kw):
        stub = MagicMock()

        def where(expr, prefilter=False):
            stub2 = MagicMock()
            stub2.limit = MagicMock(return_value=stub2)
            stub2.to_arrow = MagicMock(return_value=arrow_result)
            return stub2
        stub.where = where
        return stub
    return search


def _comm(msg_id="AAMk-dup", owner="rush@x.com"):
    return CommunicationData(
        id=msg_id,
        app_type="outlook",
        timestamp="2026-09-05T12:00:00Z",
        direction="inbound",
        sender="a@b.com",
        recipient="rush@x.com",
        subject="quote",
        content="machine quote body",
        attachments=[],
        metadata={"user_id": owner},
        status="new",
        priority="normal",
        tags=[],
    )


def test_duplicate_same_owner_row_is_skipped():
    mgr, table = _manager_with_store([])
    table.search = _make_search_stub(pa.Table.from_pylist([
        {"id": "AAMk-dup", "metadata": json.dumps({"user_id": "rush@x.com"})},
    ]))

    assert mgr.ingest_communication(_comm()) is True
    table.add.assert_not_called()  # duplicate refused durably


def test_unstamped_row_blocks_reingest():
    mgr, table = _manager_with_store([])
    table.search = _make_search_stub(pa.Table.from_pylist([
        {"id": "AAMk-dup", "metadata": json.dumps({"user_id": ""})},
    ]))

    assert mgr.ingest_communication(_comm(owner="other@x.com")) is True
    table.add.assert_not_called()


def test_different_owner_row_still_ingests():
    """Ownership-scoped search keeps other owners' rows invisible, so this
    owner needs its own copy — same contract as _dedup_messages."""
    mgr, table = _manager_with_store([])
    table.search = _make_search_stub(pa.Table.from_pylist([
        {"id": "AAMk-dup", "metadata": json.dumps({"user_id": "someoneelse@x.com"})},
    ]))

    assert mgr.ingest_communication(_comm()) is True
    table.add.assert_called_once()


def test_no_row_ingests_normally():
    mgr, table = _manager_with_store([])
    table.search = _make_search_stub(pa.Table.from_pylist([], schema=SCHEMA))

    assert mgr.ingest_communication(_comm()) is True
    table.add.assert_called_once()


def test_lookup_failure_fails_open():
    """A query hiccup must not drop mail — the poll-level dedup still
    applies, so failing open re-risks a duplicate but never loses data."""
    mgr, table = _manager_with_store([])
    table.search = MagicMock(side_effect=RuntimeError("lance hiccup"))

    assert mgr.ingest_communication(_comm()) is True
    table.add.assert_called_once()


# --- Content-identity guard: fresh ids on already-stored messages ---------

def test_same_content_new_id_is_skipped():
    """Some fetch paths stamp a FRESH id on an already-stored message. The
    id guard can't see those; the content-identity guard must."""
    mgr, table = _manager_with_store([])
    table.search = _make_search_stub(pa.Table.from_pylist([
        {
            "id": "OTHER-ID",
            "sender": "a@b.com",
            "recipient": "rush@x.com",
            "subject": "quote",
            "content": "machine quote body",
            "timestamp": "2026-09-05T12:00:00Z",
            "metadata": json.dumps({"user_id": "rush@x.com"}),
        },
    ]))

    assert mgr.ingest_communication(_comm(msg_id="AAMk-fresh-id")) is True
    table.add.assert_not_called()


def test_resent_message_new_timestamp_ingests():
    """A genuine re-send (new received time) is a new event, not a duplicate
    (live 2026-09-06: the Sep 4 quote under two Graph ids, 24min apart)."""
    mgr, table = _manager_with_store([])
    table.search = _make_search_stub(pa.Table.from_pylist([]))

    comm = _comm(msg_id="AAMk-resend")
    comm.timestamp = "2026-09-05T14:30:00Z"
    assert mgr.ingest_communication(comm) is True
    table.add.assert_called_once()


def test_content_guard_ignores_other_owners_rows():
    mgr, table = _manager_with_store([])
    table.search = _make_search_stub(pa.Table.from_pylist([
        {
            "id": "OTHER-ID",
            "sender": "a@b.com",
            "recipient": "rush@x.com",
            "subject": "quote",
            "content": "machine quote body",
            "timestamp": "2026-09-05T12:00:00Z",
            "metadata": json.dumps({"user_id": "someoneelse@x.com"}),
        },
    ]))

    assert mgr.ingest_communication(_comm(msg_id="AAMk-fresh-id")) is True
    table.add.assert_called_once()


def test_content_guard_fails_open():
    mgr, table = _manager_with_store([])
    table.search = MagicMock(side_effect=RuntimeError("lance hiccup"))

    assert mgr.ingest_communication(_comm()) is True
    table.add.assert_called_once()


# --- Generic records pass the same id gate -------------------------------

def test_generic_record_duplicate_is_skipped():
    from integrations.ingestion_models import AtomRecordData, RecordType

    mgr, table = _manager_with_store([])
    table.search = _make_search_stub(pa.Table.from_pylist([
        {"id": "lead-1", "metadata": json.dumps({"user_id": "rush@x.com"})},
    ]))
    mgr.generate_embedding = MagicMock(return_value=[0.0] * 4)
    mgr._update_metadata = MagicMock()

    rec = AtomRecordData(
        id="lead-1", app_type="hubspot", record_type=RecordType.LEAD,
        content="lead body", metadata={"user_id": "rush@x.com"},
        vector_embedding=[0.0] * 4,
    )
    assert mgr.ingest_generic_record(rec) is True
    table.add.assert_not_called()


def test_generic_record_fresh_ingests():
    from integrations.ingestion_models import AtomRecordData, RecordType

    mgr, table = _manager_with_store([])
    table.search = _make_search_stub(pa.Table.from_pylist([]))
    mgr.generate_embedding = MagicMock(return_value=[0.0] * 4)
    mgr._update_metadata = MagicMock()

    rec = AtomRecordData(
        id="lead-2", app_type="hubspot", record_type=RecordType.LEAD,
        content="lead body", metadata={"user_id": "rush@x.com"},
        vector_embedding=[0.0] * 4,
    )
    assert mgr.ingest_generic_record(rec) is True
    table.add.assert_called_once()


# --- One-shot startup heal -------------------------------------------------

import threading

import lancedb

_META_SCHEMA = pa.schema([
    pa.field("app_type", pa.string()),
    pa.field("last_ingested", pa.timestamp("us")),
    pa.field("total_messages", pa.int64()),
    pa.field("config", pa.string()),
    pa.field("status", pa.string()),
])


def _real_store(rows):
    tmp = tempfile.mkdtemp()
    db = lancedb.connect(tmp)
    table = db.create_table("atom_communications", schema=SCHEMA)
    if rows:
        table.add(rows)
    metadata = db.create_table("ingestion_metadata", schema=_META_SCHEMA)
    mgr = LanceDBMemoryManager.__new__(LanceDBMemoryManager)
    mgr.db = db
    mgr.connections_table = table
    mgr.metadata_table = metadata
    mgr._store_surgery_lock = threading.Lock()
    return mgr, table, metadata


def _store_row(rid, owner="rush@x.com", content="body", ts="2026-09-05T12:00:00Z",
               sender="a@b.com", subject="quote"):
    return {
        "id": rid, "app_type": "outlook", "timestamp": ts, "direction": "inbound",
        "sender": sender, "recipient": "rush@x.com", "subject": subject,
        "content": content, "attachments": "[]",
        "metadata": json.dumps({"user_id": owner}),
        "status": "new", "priority": "normal", "tags": "[]",
        "vector": [0.0] * 4, "search_vector": [0.0] * 4,
    }


def test_heal_removes_id_twin_and_restamped_twin_keeps_legit_rows():
    rows = [
        _store_row("dup-1"),                                   # original
        _store_row("dup-1"),                                   # id twin — remove
        _store_row("fresh-id", content="same body", ts="2026-09-05T12:00:00Z"),
        _store_row("fresh-id-2", content="same body", ts="2026-09-05T12:00:00Z"),  # re-stamped twin — remove
        _store_row("dup-1", owner="other@x.com"),              # different owner — keep
        _store_row("unique-1", content="other body"),          # unique — keep
        _store_row("resent", content="same body", ts="2026-09-05T18:00:00Z"),  # re-Sent — keep
    ]
    mgr, table, metadata = _real_store(rows)

    mgr._heal_duplicate_rows()

    kept = table.to_arrow().to_pylist()
    kept_ids = sorted(r["id"] + "|" + r["metadata"] for r in kept)
    assert kept_ids == sorted([
        "dup-1|" + json.dumps({"user_id": "rush@x.com"}),
        "fresh-id|" + json.dumps({"user_id": "rush@x.com"}),
        "dup-1|" + json.dumps({"user_id": "other@x.com"}),
        "unique-1|" + json.dumps({"user_id": "rush@x.com"}),
        "resent|" + json.dumps({"user_id": "rush@x.com"}),
    ])
    markers = metadata.search().where(
        f"app_type = '{mgr._HEAL_MARKER}'", prefilter=True
    ).limit(5).to_arrow().to_pylist()
    assert len(markers) == 1 and markers[0]["total_messages"] == 2


def test_heal_is_once_per_store():
    rows = [_store_row("dup-1"), _store_row("dup-1")]
    mgr, table, metadata = _real_store(rows)

    mgr._heal_duplicate_rows()
    assert table.count_rows() == 1

    # A second twin arriving after the heal must survive it — the heal is
    # once-per-store, the write-time guards own everything after.
    table.add([_store_row("dup-1")])
    mgr._heal_duplicate_rows()
    assert table.count_rows() == 2


def test_heal_on_fresh_store_is_a_clean_noop():
    mgr, table, metadata = _real_store([])
    mgr._heal_duplicate_rows()
    assert table.count_rows() == 0
    markers = metadata.search().where(
        f"app_type = '{mgr._HEAL_MARKER}'", prefilter=True
    ).limit(5).to_arrow().to_pylist()
    assert len(markers) == 1 and markers[0]["total_messages"] == 0


# --- Knowledge-extraction backfill budget ----------------------------------

def test_extraction_age_gate_blocks_old_messages(monkeypatch):
    from integrations.atom_communication_ingestion_pipeline import (
        _extraction_age_blocked,
    )

    monkeypatch.setenv("ATOM_KG_EXTRACT_MAX_AGE_DAYS", "30")
    assert _extraction_age_blocked("2026-01-19T10:00:00Z") is True   # ~8 months old
    assert _extraction_age_blocked("2026-09-06T09:00:00Z") is False  # today
    monkeypatch.setenv("ATOM_KG_EXTRACT_MAX_AGE_DAYS", "0")          # gate off
    assert _extraction_age_blocked("2026-01-19T10:00:00Z") is False


def test_extraction_age_gate_never_blocks_unparseable(monkeypatch):
    from integrations.atom_communication_ingestion_pipeline import (
        _extraction_age_blocked,
    )

    monkeypatch.setenv("ATOM_KG_EXTRACT_MAX_AGE_DAYS", "30")
    assert _extraction_age_blocked("not-a-date") is False
    assert _extraction_age_blocked(None) is False
