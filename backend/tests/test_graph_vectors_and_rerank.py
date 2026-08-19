"""
P1.5 graph node vector index + P1.4 assembler rerank tests.
"""

import os
os.environ.setdefault("TESTING", "1")

import pytest
from unittest.mock import MagicMock, patch

import core.memory_context_assembler as mca


# --------------------------------------------------------------------------- #
# P1.5 — graph node vector index
# --------------------------------------------------------------------------- #

class TestGraphNodeVectorIndex:
    def test_index_node_vector_writes_lancedb(self):
        from core.graphrag_engine import GraphRAGEngine

        engine = GraphRAGEngine.__new__(GraphRAGEngine)
        handler = MagicMock()
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=handler):
            engine._index_node_vector(
                "n1", "AccurPress Press Brake", "product", "50-ton CNC", "default"
            )
        handler.add_document.assert_called_once()
        kwargs = handler.add_document.call_args
        assert kwargs[0][0] == "graph_nodes"
        assert kwargs[1]["extra_columns"]["node_id"] == "n1"

    def test_index_node_vector_never_raises(self):
        from core.graphrag_engine import GraphRAGEngine

        engine = GraphRAGEngine.__new__(GraphRAGEngine)
        with patch("core.lancedb_handler.get_lancedb_handler",
                   side_effect=RuntimeError("lancedb down")):
            engine._index_node_vector("n1", "x", "product", None, "default")  # no raise

    def test_local_search_vector_leg_uses_lancedb(self):
        """The vector leg must not depend on the pgvector <=> operator."""
        import inspect
        from core.graphrag_engine import GraphRAGEngine

        src = inspect.getsource(GraphRAGEngine.local_search)
        assert "get_lancedb_handler" in src
        assert "ORDER BY embedding <=> " not in src  # pgvector SQL gone (comments OK)


# --------------------------------------------------------------------------- #
# P1.4 — assembler rerank (graceful degradation)
# --------------------------------------------------------------------------- #

class TestAssemblerRerank:
    """The merged upstream P1.4 rerank is budget-gated via MEMORY_CONTEXT_RERANK
    (RERANK_FLAG) and degrades gracefully without torch. We pin the flag
    contract; ordering behavior is covered by upstream's own tests."""

    def test_rerank_flag_constant(self):
        import core.memory_context_assembler as m

        assert m.RERANK_FLAG == "MEMORY_CONTEXT_RERANK"
        assert m.RERANK_MIN_LINES >= 3  # never rerank trivially small legs

    @pytest.mark.asyncio
    async def test_assembler_works_with_rerank_disabled(self, monkeypatch):
        monkeypatch.setenv("MEMORY_CONTEXT_ASSEMBLY", "true")
        monkeypatch.setenv("MEMORY_CONTEXT_RERANK", "false")

        async def fake_graph(message, ws, tn):
            return None

        async def fake_comms(message, ws):
            return ["[slack] a line"]

        async def empty2(message, ws):
            return []

        async def empty1(message, agent):
            return []

        with patch.object(mca, "_graph_leg", fake_graph), \
             patch.object(mca, "_knowledge_leg", fake_comms), \
             patch.object(mca, "_integration_records_leg", empty2), \
             patch.object(mca, "_episodes_leg", empty1), \
             patch.object(mca, "_facts_leg", empty2):
            block = await mca.assemble_memory_context("anything")

        assert block is not None and "a line" in block
