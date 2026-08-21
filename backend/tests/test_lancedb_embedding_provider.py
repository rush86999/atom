"""
LanceDB handler embedding-provider wiring tests.

Pins the fixes that made document ingestion (and therefore hybrid search +
Knowledge VFS) work on installs without an OpenAI key:
- the handler's embedder is EmbeddingService honoring EMBEDDING_PROVIDER
  (default fastembed), not the chat LLMService router
- the `vector` column is sized to the active provider's output dim (384 for
  fastembed), not a fixed 1536
- provider resolution is identical on both sides (no dim mismatch)
"""

import os
os.environ.setdefault("TESTING", "1")
os.environ["EMBEDDING_PROVIDER"] = "fastembed"
os.environ.setdefault("LANCEDB_URI", "/tmp/test_lancedb_provider")

import shutil
import pytest

shutil.rmtree("/tmp/test_lancedb_provider", ignore_errors=True)

from core.lancedb_handler import LanceDBHandler


@pytest.fixture()
def handler():
    h = LanceDBHandler(db_path="/tmp/test_lancedb_provider")
    yield h


class TestEmbeddingProviderWiring:
    def test_default_provider_is_fastembed(self, handler):
        # Offline default — works without any API key.
        assert handler.embedding_provider == "fastembed"

    def test_embedder_is_embedding_service(self, handler):
        from core.embedding_service import EmbeddingService

        assert isinstance(handler.embedding_service, EmbeddingService)

    def test_embedder_provider_matches_handler(self, handler):
        assert handler.embedding_service.provider == handler.embedding_provider

    def test_vector_column_sized_to_provider(self, handler):
        handler._ensure_db()
        table = handler.create_table("documents")
        assert table is not None
        # fastembed bge-small-en-v1.5 → 384 dims, not the legacy 1536
        assert "384" in str(table.schema.field("vector").type)

    def test_round_trip_add_and_search(self, handler):
        ok = handler.add_document(
            "documents",
            "AccurPress 50-ton press brake price policy for brennan.ca",
            source="policy.txt",
        )
        assert ok is True
        rows = handler.search("documents", "press brake price", limit=3)
        assert len(rows) >= 1
