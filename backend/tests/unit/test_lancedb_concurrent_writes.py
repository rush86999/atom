"""Regression tests: LanceDB ingestion structural defect (2026-09-07).

Root cause chain (live): concurrent in-process writers hit lance's local-FS
commit path → "_transactions: File exists (os error 17)" → get_table's
names()-listing missed mid-commit tables → create_table collided with the
existing table → every write returned 0/False → ingestion silently degraded
for DAYS (nothing newer than 2026-09-06 in memory while logs looked healthy).

Fixes under test:
  1. get_table resolves by direct open_table (listing only as fallback);
  2. per-table write lock + transient-commit retry (_add_with_retry);
  3. batch + single adds succeed under threaded concurrency.
"""
import threading

import pyarrow as pa
import pytest

from core.lancedb_handler import LanceDBHandler


def _handler(tmp_path):
    h = LanceDBHandler(db_path=str(tmp_path / "mem"), workspace_id="ws-t")
    h._ensure_db()
    if h.db is None:
        pytest.skip("LanceDB unavailable on this interpreter")
    h.embed_text = lambda text: [0.1, 0.2, 0.3, 0.4]
    return h


def _mk_table(h, name="documents"):
    """Create a table whose vector dim matches the stubbed embedder (4)."""
    import pyarrow as pa

    schema = pa.schema([
        pa.field("id", pa.string()),
        pa.field("user_id", pa.string()),
        pa.field("workspace_id", pa.string()),
        pa.field("text", pa.string()),
        pa.field("source", pa.string()),
        pa.field("metadata", pa.string()),
        pa.field("created_at", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), 4)),
    ])
    return h.db.create_table(name, schema=schema)


def test_concurrent_writes_all_land(tmp_path):
    """The live failure: overlapping table.add() calls from the sync loop +
    read-path ingestion raced the commit dir. Serialized + retried, every
    thread's rows must land."""
    h = _handler(tmp_path)
    _mk_table(h)

    errors = []

    def _writer(n: int) -> None:
        for i in range(5):
            ok = h.add_document(
                table_name="documents",
                text=f"doc-{n}-{i}",
                source="test",
                doc_id=f"id-{n}-{i}",
            )
            if not ok:
                errors.append(f"writer {n} row {i} failed")

    threads = [threading.Thread(target=_writer, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors
    assert h.get_table_nocheck("documents").count_rows() == 40


def test_concurrent_batch_writes_all_land(tmp_path):
    h = _handler(tmp_path)
    _mk_table(h)

    errors = []

    def _batch_writer(n: int) -> None:
        docs = [
            {"id": f"b-{n}-{i}", "text": f"batch-{n}-{i}", "source": "t", "user_id": "u"}
            for i in range(6)
        ]
        added = h.add_documents_batch("documents", docs)
        if added != len(docs):
            errors.append(f"batch {n}: {added}/{len(docs)}")

    threads = [threading.Thread(target=_batch_writer, args=(n,)) for n in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors
    assert h.get_table_nocheck("documents").count_rows() == 36


def test_get_table_resolves_when_listing_misses(tmp_path):
    """get_table must resolve an existing table even when the names()
    listing is inconsistent (mid-commit state) — the defect sent writers to
    the create path where they collided."""
    h = _handler(tmp_path)
    _mk_table(h)
    assert h.get_table("documents") is not None

    # Simulate the mid-commit listing miss: names() returns garbage while
    # open_table still works.
    class _FlakyNames:
        def __init__(self, inner):
            self._inner = inner

        def table_names(self):
            return []  # the mid-commit state

        def open_table(self, name):
            return self._inner.open_table(name)

        def __getattr__(self, item):
            return getattr(self._inner, item)

    real_db = h.db
    h.db = _FlakyNames(real_db)
    try:
        assert h.get_table("documents") is not None  # direct open resolves it
        assert h.get_table("no_such_table") is None
    finally:
        h.db = real_db


def test_transient_commit_error_retried(tmp_path):
    """_add_with_retry retries the exact live error class
    ('File exists (os error 17)' on _transactions) and succeeds."""
    h = _handler(tmp_path)
    table = _mk_table(h)

    calls = {"n": 0}

    class _FlakyTable:
        def __init__(self, real):
            self._real = real

        def add(self, records):
            calls["n"] += 1
            if calls["n"] == 1:
                raise Exception(
                    "lance error: LanceError(IO): Generic LocalFileSystem error: "
                    "Unable to create dir /x/documents.lance/_transactions: "
                    "File exists (os error 17)"
                )
            return None  # success (record shape irrelevant to retry logic)

        def __getattr__(self, item):
            return getattr(self._real, item)

    assert LanceDBHandler._add_with_retry(_FlakyTable(table), [{"x": 1}]) is True
    assert calls["n"] == 2  # failed once, retried, landed

    # Non-transient errors raise immediately (no busy retry).
    class _BadTable:
        def add(self, records):
            raise ValueError("Field 'nope' not found in target schema")

    with pytest.raises(ValueError):
        LanceDBHandler._add_with_retry(_BadTable(), [{"x": 1}])


def test_existing_table_not_recreated(tmp_path):
    """create_table on an existing table must OPEN it, never collide or
    overwrite (29k-row store integrity)."""
    h = _handler(tmp_path)
    t1 = _mk_table(h)
    h.add_document(table_name="documents", text="keep me", source="t", doc_id="keep-1")
    t2 = h.create_table("documents")
    assert t2 is not None
    assert h.get_table_nocheck("documents").count_rows() == 1
