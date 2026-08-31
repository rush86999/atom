"""Embedding-model registry + background re-embedding migration.

Covers the three ways an embedding-model switch used to break (or silently
corrupt) vector search:

1. Nothing recorded which model produced a table's vectors — swapping to a
   same-dimension model produced no error at all, just meaningless
   similarities → per-table identity registry.
2. ``create_table(mode="overwrite")`` silently DROPPED existing tables and
   every row in them → create-if-missing with explicit ``overwrite=True``.
3. Dimension/model mismatches failed every insert and search → background
   re-embedding migration that carries rows over.
"""

import json

import pyarrow as pa
import pytest

from core import embedding_registry
from core.lancedb_handler import LanceDBHandler


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    reg_file = tmp_path / "embedding_registry.json"
    monkeypatch.setenv("EMBEDDING_REGISTRY_FILE", str(reg_file))
    embedding_registry.reload()
    yield
    embedding_registry.reload()


@pytest.fixture
def handler(tmp_path, monkeypatch):
    monkeypatch.setenv("LANCEDB_URI", str(tmp_path / "lance"))
    h = LanceDBHandler()
    # Deterministic identity + embeddings — no network, no model load.
    monkeypatch.setattr(
        h, "_active_embedding_identity", lambda: {"provider": "test", "model": "m1"}
    )
    monkeypatch.setattr(h, "embed_text", lambda text: [0.5] * 384)
    # Keep scheduling deterministic; the worker is invoked directly below.
    monkeypatch.setattr(h, "_schedule_reembed", lambda table_name: None)
    LanceDBHandler._reembed_inflight.clear()
    yield h
    LanceDBHandler._reembed_inflight.clear()


def _std_row(dim=384, marker=0.0, doc_id="1"):
    return {
        "id": doc_id,
        "user_id": "u",
        "workspace_id": "default",
        "text": "hello world",
        "source": "s",
        "metadata": "{}",
        "created_at": "now",
        "vector": [marker] * dim,
    }


class TestRegistry:
    def test_set_get_persist(self, tmp_path):
        embedding_registry.set_identity("tbl", "fastembed", "BAAI/bge-small-en-v1.5", 384)
        assert embedding_registry.get("tbl") == {
            "provider": "fastembed",
            "model": "BAAI/bge-small-en-v1.5",
            "dim": 384,
        }
        embedding_registry.reload()  # simulate a fresh process
        assert embedding_registry.get("tbl")["model"] == "BAAI/bge-small-en-v1.5"

    def test_corrupt_file_fails_open(self, tmp_path):
        reg_file = tmp_path / "embedding_registry.json"
        reg_file.write_text("{ not json !!!")
        embedding_registry.reload()
        assert embedding_registry.get("tbl") is None  # no raise
        embedding_registry.set_identity("tbl", "p", "m", 384)  # recoverable
        assert embedding_registry.get("tbl")["model"] == "m"

    def test_classify_states(self):
        reg = {"provider": "fastembed", "model": "bge", "dim": 384}
        assert embedding_registry.classify(None, "fastembed", "bge", 384) == "unregistered"
        assert embedding_registry.classify(reg, "fastembed", "bge", 384) == "match"
        # Same dimension, different model — the silent-garbage case.
        assert (
            embedding_registry.classify(reg, "fastembed", "other-384-model", 384)
            == "model_changed_same_dim"
        )
        assert embedding_registry.classify(reg, "openai", "text-embedding-3-small", 1536) == (
            "dim_changed"
        )

    def test_dim_from_schema(self):
        schema = pa.schema(
            [pa.field("id", pa.string()), pa.field("vector", pa.list_(pa.float32(), 384))]
        )
        assert embedding_registry.dim_from_schema(schema) == 384
        assert embedding_registry.dim_from_schema(pa.schema([])) is None


class TestOverwriteFix:
    def test_create_if_missing_preserves_rows(self, handler):
        t = handler.create_table("docs_t")
        t.add([_std_row()])
        assert handler.get_table("docs_t").count_rows() == 1

        # Re-running create_table must NOT wipe the table (old behavior:
        # mode="overwrite" silently dropped it).
        handler.create_table("docs_t")
        assert handler.get_table("docs_t").count_rows() == 1

    def test_explicit_overwrite_resets(self, handler):
        t = handler.create_table("docs_t")
        t.add([_std_row()])
        handler.create_table("docs_t", overwrite=True)
        assert handler.get_table("docs_t").count_rows() == 0

    def test_first_sighting_registers_identity(self, handler):
        handler.create_table("docs_t")
        handler.get_table("docs_t")
        entry = embedding_registry.get("docs_t")
        assert entry == {"provider": "test", "model": "m1", "dim": 384}


class TestReembedMigration:
    def test_same_dim_model_change_reembeds(self, handler):
        # Table built with old model "m0" (384-dim); active embedder is now
        # "m1" — same dimension, so nothing would ever fail, but the vectors
        # are stale. Migration must re-embed with the active model.
        t = handler.create_table("docs_t")
        t.add([_std_row(dim=384, marker=0.0)])
        embedding_registry.set_identity("docs_t", "test", "m0", 384)

        handler._reembed_table_worker("docs_t")

        rows = handler.get_table("docs_t").to_arrow().to_pylist()
        assert len(rows) == 1
        assert rows[0]["vector"] == [0.5] * 384  # new model's output (fixture)
        assert embedding_registry.get("docs_t")["model"] == "m1"

    def test_dim_change_migration(self, handler):
        # Old table at 384; the "new" embedder emits 8 dims.
        t = handler.create_table("docs_t")
        t.add([_std_row(dim=384, marker=0.0), _std_row(dim=384, marker=0.0, doc_id="2")])
        embedding_registry.set_identity("docs_t", "test", "m0", 384)
        monkey_dims = {"n": 8}
        handler.embed_text = lambda text: [0.25] * monkey_dims["n"]

        handler._reembed_table_worker("docs_t")

        fresh = handler.get_table("docs_t")
        assert fresh.count_rows() == 2
        assert embedding_registry.dim_from_schema(fresh.schema) == 8
        assert embedding_registry.get("docs_t")["dim"] == 8
        for row in fresh.to_arrow().to_pylist():
            assert row["vector"] == [0.25] * 8

    def test_dead_embedder_aborts_without_data_loss(self, handler):
        t = handler.create_table("docs_t")
        t.add([_std_row(dim=384, marker=0.0)])
        embedding_registry.set_identity("docs_t", "test", "m0", 384)
        handler.embed_text = lambda text: None  # embedder dead

        handler._reembed_table_worker("docs_t")

        rows = handler.get_table("docs_t").to_arrow().to_pylist()
        assert len(rows) == 1 and rows[0]["vector"] == [0.0] * 384  # untouched
        assert embedding_registry.get("docs_t")["model"] == "m0"

    def test_dual_vector_column_preserved(self, handler):
        # Tables with a vector_fastembed column keep that column (built by a
        # different embedder) across migration.
        schema = pa.schema(
            [
                pa.field("id", pa.string()),
                pa.field("user_id", pa.string()),
                pa.field("workspace_id", pa.string()),
                pa.field("text", pa.string()),
                pa.field("source", pa.string()),
                pa.field("metadata", pa.string()),
                pa.field("created_at", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), 384)),
                pa.field("vector_fastembed", pa.list_(pa.float32(), 384)),
            ]
        )
        t = handler.create_table("docs_t", schema=schema)
        row = _std_row(dim=384, marker=0.0)
        row["vector_fastembed"] = [0.75] * 384  # pre-existing fastembed vector
        t.add([row])
        embedding_registry.set_identity("docs_t", "test", "m0", 384)

        handler._reembed_table_worker("docs_t")

        rows = handler.get_table("docs_t").to_arrow().to_pylist()
        assert len(rows) == 1
        assert rows[0]["vector"] == [0.5] * 384  # re-embedded
        assert rows[0]["vector_fastembed"] == [0.75] * 384  # preserved

    def test_schedule_dedupes_per_table(self, handler, monkeypatch):
        # Remove the fixture's no-op override so the real scheduling runs.
        monkeypatch.delattr(handler, "_schedule_reembed")
        created = []

        class FakeThread:
            def __init__(self, target=None, daemon=None, name=None, args=None):
                created.append(name)

            def start(self):
                pass

        import core.lancedb_handler as lh

        monkeypatch.setattr(lh.threading, "Thread", FakeThread)
        handler._schedule_reembed("tbl_a")
        handler._schedule_reembed("tbl_a")  # in-flight — deduped
        handler._schedule_reembed("tbl_b")
        assert created == ["reembed-tbl_a", "reembed-tbl_b"]

    def test_get_table_schedules_on_mismatch(self, handler, monkeypatch):
        t = handler.create_table("docs_t")
        t.add([_std_row()])
        embedding_registry.set_identity("docs_t", "test", "old-model", 384)
        scheduled = []
        monkeypatch.setattr(handler, "_schedule_reembed", lambda name: scheduled.append(name))

        handler.get_table("docs_t")  # identity check hook
        assert scheduled == ["docs_t"]
