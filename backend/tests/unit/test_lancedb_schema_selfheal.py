"""Regression test: LanceDB schema-drift self-heal (core/lancedb_handler).

An old `episodes` table that predates the agent_id prefilter column made
every agent-scoped episode recall die with "Schema error: No field named
agent_id" — the search now repairs the table (adds the missing column) and
retries once, instead of degrading the whole feature leg.

Uses a synthetic 4-dim old-schema table and a stubbed embedder, so it runs
on any interpreter (no fastembed needed).
"""
import datetime as _dt

import pyarrow as pa
import pytest

from core.lancedb_handler import LanceDBHandler


@pytest.fixture()
def handler(tmp_path):
    h = LanceDBHandler(db_path=str(tmp_path / "mem"), workspace_id="ws-t")
    h._ensure_db()
    if h.db is None:
        pytest.skip("LanceDB unavailable on this interpreter")
    # Stub the embedder: no fastembed needed; 4-dim matches the old schema.
    h.embed_text = lambda text: [0.1, 0.2, 0.3, 0.4]
    return h


def _make_old_episodes_table(handler):
    """Create an episodes table with the PRE-agent_id schema and one row."""
    schema = pa.schema([
        pa.field("id", pa.string()),
        pa.field("text", pa.string()),
        pa.field("source", pa.string()),
        pa.field("user_id", pa.string()),
        pa.field("workspace_id", pa.string()),
        pa.field("created_at", pa.timestamp("us")),
        pa.field("vector", pa.list_(pa.float32(), 4)),
    ])
    table = handler.db.create_table("episodes", schema=schema)
    table.add([{
        "id": "ep1", "text": "hello", "source": "test",
        "user_id": "u1", "workspace_id": "ws-t",
        "created_at": _dt.datetime.now(_dt.timezone.utc),
        "vector": [0.1, 0.2, 0.3, 0.4],
    }])
    assert "agent_id" not in {f.name for f in table.schema}
    return table


def test_search_selfheals_missing_column(handler):
    _make_old_episodes_table(handler)

    # Search with an agent_id prefilter against the OLD table: must not
    # raise — repair adds the column and retries (old rows have NULL
    # agent_id, so [] is the correct answer for this filter).
    results = handler.search(
        table_name="episodes", query="hello",
        filter_str="agent_id == 'a1'", limit=5,
    )
    assert results == []
    assert "agent_id" in {f.name for f in handler.get_table("episodes").schema}


def test_repair_missing_column_semantics(handler):
    _make_old_episodes_table(handler)

    err = Exception("Schema error: No field named agent_id. Did you mean 'user_id'?")

    # First call: column missing → repaired (True).
    assert handler._repair_missing_column("episodes", err) is True
    assert "agent_id" in {f.name for f in handler.get_table("episodes").schema}

    # Second call: column exists now → False (the error was something else),
    # which is what keeps the search retry from looping.
    assert handler._repair_missing_column("episodes", err) is False

    # Unrelated errors never trigger a repair.
    assert handler._repair_missing_column("episodes", Exception("connection refused")) is False


def test_known_drift_applied_on_connect(tmp_path):
    """The startup pass adds known-drift columns to tables that predate them,
    before any search runs."""
    import pyarrow as pa

    from core.lancedb_handler import LanceDBHandler

    h = LanceDBHandler(db_path=str(tmp_path / "mem2"), workspace_id="ws-t")
    h._ensure_db()

    schema = pa.schema([
        pa.field("id", pa.string()),
        pa.field("text", pa.string()),
        pa.field("user_id", pa.string()),
        pa.field("workspace_id", pa.string()),
        pa.field("source", pa.string()),
        pa.field("metadata", pa.string()),
        pa.field("created_at", pa.timestamp("us")),
        pa.field("vector", pa.list_(pa.float32(), 4)),
    ])
    h.db.create_table("exchange_examples", schema=schema)

    # A fresh handler on the same store applies the known-drift repair.
    h2 = LanceDBHandler(db_path=str(tmp_path / "mem2"), workspace_id="ws-t")
    h2._ensure_db()
    table = h2.get_table_nocheck("exchange_examples")
    assert "label" in {f.name for f in table.schema}
