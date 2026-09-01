"""
Memory Context Assembler tests — the P0 unified turn-time retrieval block.

All external legs (GraphRAG, comm search, episodes, turn facts) are patched;
these tests pin the contract: fault isolation, budgets, flag gating, block
rendering.
"""

import os
os.environ.setdefault("TESTING", "1")

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import core.memory_context_assembler as mca
from core.memory_context_assembler import (
    assemble_memory_context,
    assembly_enabled,
    _bounded_lines,
)


def test_flag_defaults_on(monkeypatch):
    monkeypatch.delenv("MEMORY_CONTEXT_ASSEMBLY", raising=False)
    assert assembly_enabled() is True


def test_flag_off(monkeypatch):
    monkeypatch.setenv("MEMORY_CONTEXT_ASSEMBLY", "false")
    assert assembly_enabled() is False


def test_bounded_lines_respects_cap():
    lines = ["x" * 100 for _ in range(10)]
    out = _bounded_lines(lines, cap=250)
    # Each line costs 101 chars ("- " + 100); cap 250 → 2 lines fit
    assert out.count("\n") == 1


def test_bounded_lines_skips_empty():
    assert _bounded_lines(["", "ok"], cap=100) == "- ok"


@pytest.fixture(autouse=True)
def _stub_lessons_leg():
    """Keep the taught-lessons leg hermetic by default (it opens its own DB
    session). Tests that exercise the leg patch mca._lessons_leg themselves
    and win for the duration."""
    with patch.object(mca, "_lessons_leg", AsyncMock(return_value="")):
        yield


@pytest.mark.asyncio
async def test_all_legs_rendered(monkeypatch):
    monkeypatch.setenv("MEMORY_CONTEXT_ASSEMBLY", "true")

    async def fake_graph(message, ws, tn):
        return "ACME Fabrication — raised inquiry about press brake"

    async def fake_knowledge(message, ws):
        return ["[communication: whatsapp — 2026-08-19] Sarah needs a quote on the press brake"]

    async def fake_episodes(message, agent):
        return ["Created quote Q-2024-0142 for ACME (outcome: success)"]

    async def fake_facts(message, ws):
        return ["ACME Fab budget is around $80K"]

    with patch.object(mca, "_graph_leg", fake_graph), \
         patch.object(mca, "_knowledge_leg", fake_knowledge), \
         patch.object(mca, "_integration_records_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_episodes_leg", fake_episodes), \
         patch.object(mca, "_facts_leg", fake_facts):
        block = await assemble_memory_context("what did ACME ask about?")

    assert block is not None
    assert block.startswith("RELEVANT MEMORY")
    for expected in (
        "KNOWLEDGE GRAPH CONTEXT",
        "ACME Fabrication",
        "RELATED KNOWLEDGE & CONVERSATIONS",
        "RELEVANT PAST EPISODES",
        "DURABLE FACTS",
        "$80K",
    ):
        assert expected in block, f"missing {expected!r}"


@pytest.mark.asyncio
async def test_leg_failure_isolated(monkeypatch):
    """A raising leg yields an empty block, others still render."""
    monkeypatch.setenv("MEMORY_CONTEXT_ASSEMBLY", "true")

    async def boom(*a, **k):
        raise RuntimeError("store down")

    async def fine_graph(message, ws, tn):
        return "graph context here"

    with patch.object(mca, "_graph_leg", fine_graph), \
         patch.object(mca, "_knowledge_leg", boom), \
         patch.object(mca, "_integration_records_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_episodes_leg", boom), \
         patch.object(mca, "_facts_leg", boom):
        block = await assemble_memory_context("anything")

    assert block is not None
    assert "graph context here" in block
    assert "RELATED KNOWLEDGE & CONVERSATIONS" not in block


@pytest.mark.asyncio
async def test_leg_timeout_isolated(monkeypatch):
    monkeypatch.setenv("MEMORY_CONTEXT_ASSEMBLY", "true")

    async def slow_graph(message, ws, tn):
        await asyncio.sleep(5)
        return "too late"

    async def fast_facts(message, ws):
        return ["a durable fact"]

    with patch.object(mca, "_graph_leg", slow_graph), \
         patch.object(mca, "_knowledge_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_integration_records_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_episodes_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_facts_leg", fast_facts):
        block = await asyncio.wait_for(
            assemble_memory_context("anything"), timeout=3
        )

    assert block is not None
    assert "a durable fact" in block
    assert "too late" not in block


@pytest.mark.asyncio
async def test_no_memory_returns_none(monkeypatch):
    monkeypatch.setenv("MEMORY_CONTEXT_ASSEMBLY", "true")
    with patch.object(mca, "_graph_leg", AsyncMock(return_value="")), \
         patch.object(mca, "_knowledge_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_integration_records_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_episodes_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_facts_leg", AsyncMock(return_value=[])):
        assert await assemble_memory_context("hello") is None


@pytest.mark.asyncio
async def test_empty_message_short_circuits():
    assert await assemble_memory_context("   ") is None


@pytest.mark.asyncio
async def test_total_budget_enforced(monkeypatch):
    monkeypatch.setenv("MEMORY_CONTEXT_ASSEMBLY", "true")

    async def huge_graph(message, ws, tn):
        return "G" * 50_000

    with patch.object(mca, "_graph_leg", huge_graph), \
         patch.object(mca, "_knowledge_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_integration_records_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_episodes_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_facts_leg", AsyncMock(return_value=[])):
        block = await assemble_memory_context("anything")

    # Graph leg caps at 3200 and total caps at 10k — either way, well short of 50k
    assert len(block) < mca.TOTAL_CHAR_BUDGET + 200


# --------------------------------------------------------------------------- #
# Universal ingestion (shape-based comm routing) + integration-records leg
# --------------------------------------------------------------------------- #

class TestCommunicationRecordClassifier:
    def test_known_comm_integration_always_routes(self):
        from core.ingestion_pipeline import IngestionPipelineService
        for app in ("telegram", "whatsapp", "slack", "gmail", "outlook"):
            assert IngestionPipelineService._is_communication_record(app, {}) is True

    def test_message_shaped_record_from_unknown_integration_routes(self):
        from core.ingestion_pipeline import IngestionPipelineService
        record = {"content": "Sarah needs a quote", "sender": "sarah@acme.com", "timestamp": "2026-08-19"}
        assert IngestionPipelineService._is_communication_record("some_new_app", record) is True

    def test_non_conversational_record_does_not_route(self):
        from core.ingestion_pipeline import IngestionPipelineService
        # Product/invoice-like record: has text but no actor/timestamp shape
        record = {"name": "Press Brake", "price": 84500.0, "sku": "BP-50T"}
        assert IngestionPipelineService._is_communication_record("zoho_inventory", record) is False

    def test_text_without_actor_or_time_does_not_route(self):
        from core.ingestion_pipeline import IngestionPipelineService
        assert IngestionPipelineService._is_communication_record("x", {"text": "just text"}) is False

    def test_non_dict_is_safe(self):
        from core.ingestion_pipeline import IngestionPipelineService
        assert IngestionPipelineService._is_communication_record("x", "not a dict") is False


@pytest.mark.asyncio
async def test_integration_records_leg_rendered(monkeypatch):
    monkeypatch.setenv("MEMORY_CONTEXT_ASSEMBLY", "true")

    async def fake_integration(message, ws, agent_role=None):
        return ["[zoho_crm] ACME Fabrication — raised inquiry about press brake"]

    with patch.object(mca, "_graph_leg", AsyncMock(return_value="")), \
         patch.object(mca, "_knowledge_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_integration_records_leg", fake_integration), \
         patch.object(mca, "_episodes_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_facts_leg", AsyncMock(return_value=[])):
        block = await assemble_memory_context("what did ACME ask about?")

    assert block is not None
    assert "RELATED INTEGRATION RECORDS" in block
    assert "ACME Fabrication" in block


# --------------------------------------------------------------------------- #
# Knowledge leg (P1.3) — DocumentsHybridSearch bridge, don't copy
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_knowledge_leg_renders_documents_and_conversations(monkeypatch):
    """Document hits (source=ingested/knowledge) and conversation hits
    (source=communication) both render as first-class lines."""
    from core.hybrid_search import documents_hybrid

    async def fake_search(self, query, limit=10, **kw):
        return {
            "success": True,
            "query": query,
            "hybrid": "bm25_vector_rrf+conversations",
            "stats": {},
            "results": [
                {
                    "source": "ingested",
                    "id": "doc1",
                    "title": "ACME press brake spec.pdf",
                    "preview": "ACME Fabrication — 50T press brake, 84,500",
                    "bridged": True,
                },
                {
                    "source": "communication",
                    "id": "c1",
                    "title": "whatsapp — 2026-08-19",
                    "preview": "Sarah needs a quote on the press brake",
                    "bridged": True,
                },
            ],
        }

    with patch.object(documents_hybrid.DocumentsHybridSearch, "search", fake_search):
        lines = await mca._knowledge_leg("what did ACME ask about?", "default")

    # Provenance spotlighting: the block is delimited as untrusted retrieved
    # data (data-not-instructions banner + closing tag) around the hits.
    assert len(lines) == 4
    assert lines[0].startswith('<provenance type="retrieved"')
    assert "untrusted" in lines[0].lower()
    assert lines[1].startswith("[ingested: ACME press brake spec.pdf]")
    assert "84,500" in lines[1]
    assert lines[2].startswith("[communication: whatsapp — 2026-08-19]")
    assert "press brake" in lines[2]
    assert lines[3] == "</provenance>"


@pytest.mark.asyncio
async def test_knowledge_leg_fault_isolated(monkeypatch):
    """A failing or empty hybrid search yields [] — never raises."""
    from core.hybrid_search import documents_hybrid

    async def boom(self, query, limit=10, **kw):
        raise RuntimeError("store down")

    with patch.object(documents_hybrid.DocumentsHybridSearch, "search", boom):
        assert await mca._knowledge_leg("anything", "default") == []

    async def empty(self, query, limit=10, **kw):
        return {"success": True, "query": query, "results": [], "hybrid": "no_results", "stats": {}}

    with patch.object(documents_hybrid.DocumentsHybridSearch, "search", empty):
        assert await mca._knowledge_leg("anything", "default") == []


# --------------------------------------------------------------------------- #
# P1.4 rerank — budget-gated, cross-encoder → fastembed cosine → no-op
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_rerank_lines_flag_off_noop(monkeypatch):
    monkeypatch.setenv("MEMORY_CONTEXT_RERANK", "false")
    lines = ["a", "b", "c"]
    assert await mca._rerank_lines("q", lines) == lines


@pytest.mark.asyncio
async def test_rerank_lines_below_min_noop(monkeypatch):
    monkeypatch.setenv("MEMORY_CONTEXT_RERANK", "true")
    assert await mca._rerank_lines("q", ["only one"]) == ["only one"]


@pytest.mark.asyncio
async def test_rerank_lines_fastembed_orders_by_similarity(monkeypatch):
    """Cross-encoder unavailable (torch broken in this env) → fastembed
    cosine re-orders so the most similar line comes first."""
    monkeypatch.setenv("MEMORY_CONTEXT_RERANK", "true")

    class FakeEmbedder:
        async def generate_embeddings_batch(self, texts):
            # query → [1,0]; "beta"/"gamma" → [0,1] (far); "alpha" → [1,0]
            return [[1.0, 0.0], [0.0, 1.0], [0.0, 1.0], [1.0, 0.0]]

    mca._RERANK_EMBEDDER = FakeEmbedder()
    try:
        out = await mca._rerank_lines(
            "query", ["beta line", "gamma line", "alpha line"]
        )
    finally:
        mca._RERANK_EMBEDDER = None
    assert out == ["alpha line", "beta line", "gamma line"]


@pytest.mark.asyncio
async def test_rerank_lines_cross_encoder_unavailable_falls_back(monkeypatch):
    """No cached cross-encoder (unprobed/unavailable, e.g. broken torch) →
    fastembed cosine tier runs, not raise."""
    monkeypatch.setenv("MEMORY_CONTEXT_RERANK", "true")
    mca._RERANK_MODEL = False

    class FakeEmbedder:
        async def generate_embeddings_batch(self, texts):
            return [[1.0, 0.0], [0.0, 1.0], [0.0, 1.0], [1.0, 0.0]]

    try:
        with patch.object(mca, "_RERANK_EMBEDDER", FakeEmbedder()):
            out = await mca._rerank_lines(
                "query", ["beta line", "gamma line", "alpha line"]
            )
    finally:
        mca._RERANK_MODEL = None
    assert out == ["alpha line", "beta line", "gamma line"]


@pytest.mark.asyncio
async def test_rerank_lines_cached_cross_encoder_used(monkeypatch):
    """A probed cross-encoder is used (predict in thread) and fastembed is
    never touched."""
    monkeypatch.setenv("MEMORY_CONTEXT_RERANK", "true")

    class FakeModel:
        def predict(self, pairs):
            # relevance order: index 1 first
            return [0.2, 0.9, 0.5]

    mca._RERANK_MODEL = FakeModel()
    try:
        with patch.object(mca, "_RERANK_EMBEDDER", None):
            out = await mca._rerank_lines(
                "query", ["third line", "first line", "second line"]
            )
    finally:
        mca._RERANK_MODEL = None
    assert out == ["first line", "second line", "third line"]


@pytest.mark.asyncio
async def test_rerank_phase_reorders_knowledge_block(monkeypatch):
    """The assembly rerank phase re-orders candidates before the block cap
    truncates, so the most relevant line surfaces first."""
    monkeypatch.setenv("MEMORY_CONTEXT_ASSEMBLY", "true")
    monkeypatch.setenv("MEMORY_CONTEXT_RERANK", "true")

    async def fake_knowledge(message, ws):
        return [
            "[doc: zzz] third-place-content",
            "[doc: aaa] most-relevant",
            "[doc: bbb] second-place-content",
        ]

    async def fake_rerank(query, lines):
        return sorted(lines, key=lambda ln: "most-relevant" in ln, reverse=True)

    with patch.object(mca, "_graph_leg", AsyncMock(return_value="")), \
         patch.object(mca, "_knowledge_leg", fake_knowledge), \
         patch.object(mca, "_integration_records_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_episodes_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_facts_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_rerank_lines", fake_rerank):
        block = await assemble_memory_context("anything")

    assert block is not None
    assert "RELATED KNOWLEDGE & CONVERSATIONS" in block
    assert block.find("most-relevant") < block.find("third-place-content")


@pytest.mark.asyncio
async def test_rerank_phase_skipped_when_flag_off(monkeypatch):
    """MEMORY_CONTEXT_RERANK=false preserves store order (no rerank call)."""
    monkeypatch.setenv("MEMORY_CONTEXT_ASSEMBLY", "true")
    monkeypatch.setenv("MEMORY_CONTEXT_RERANK", "false")

    async def fake_knowledge(message, ws):
        return ["[doc: aaa] first", "[doc: bbb] second", "[doc: ccc] third"]

    with patch.object(mca, "_graph_leg", AsyncMock(return_value="")), \
         patch.object(mca, "_knowledge_leg", fake_knowledge), \
         patch.object(mca, "_integration_records_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_episodes_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_facts_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_rerank_lines", AsyncMock()) as mock_rerank:
        block = await assemble_memory_context("anything")

    assert block is not None
    assert "RELATED KNOWLEDGE & CONVERSATIONS" in block
    mock_rerank.assert_not_called()


# --------------------------------------------------------------------------- #
# Integration-records leg regression (surfaced by the Zoho e2e UI journey:
# synced records were NEVER recalled in chat — three stacked defects)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_integration_leg_initializes_lazy_handler(monkeypatch):
    """The leg must trigger the handler's lazy DB init before guarding on it.

    Regression: `if handler.db is None: return []` fired on every fresh
    handler (connection is lazy — only search/add init it), so the leg
    always returned [] regardless of ingested data.
    """
    import core.memory_context_assembler as mca_mod

    handler = MagicMock()
    handler.db = None  # lazy: not connected yet
    handler._ensure_db = MagicMock(
        side_effect=lambda: setattr(handler, "db", MagicMock(table_names=lambda: ["integration_zoho"]))
    )
    handler.search = MagicMock(
        return_value=[{"text": "Invoice from zoho amount: 499.99", "source": "zoho"}]
    )

    with patch("core.lancedb_handler.get_lancedb_handler", return_value=handler):
        lines = await mca_mod._integration_records_leg("any query", "ws")

    handler._ensure_db.assert_called_once()
    assert lines and "499.99" in lines[0]


@pytest.mark.asyncio
async def test_integration_leg_uses_connection_directly(monkeypatch):
    """The leg must call table_names() on the LanceDBConnection itself.

    Regression: `handler.db.db.table_names()` raised AttributeError on
    LanceDBConnection (no nested .db) — swallowed, so the leg always []-ed.
    """
    import core.memory_context_assembler as mca_mod

    conn = MagicMock()
    conn.table_names = MagicMock(return_value=["integration_zoho"])
    handler = MagicMock()
    handler.db = conn
    handler._ensure_db = MagicMock()
    handler.search = MagicMock(return_value=[])

    with patch("core.lancedb_handler.get_lancedb_handler", return_value=handler):
        await mca_mod._integration_records_leg("q", "ws")

    conn.table_names.assert_called_once()


@pytest.mark.asyncio
async def test_get_qwen_response_receives_user_id():
    """process_chat_message must thread user_id into _get_qwen_response.

    Regression: the memory block inside _get_qwen_response referenced an
    undefined `user_id` -> NameError swallowed per turn -> memory context
    was NEVER assembled for any chat user.
    """
    from integrations.chat_orchestrator import ChatOrchestrator

    orch = ChatOrchestrator.__new__(ChatOrchestrator)  # skip heavy __init__
    orch.llm_service = None  # _get_qwen_response returns None immediately

    captured = {}

    async def fake_qwen(message, history, routing_overrides=None,
                        sticky_hint=None, user_id=None, **kwargs):
        captured["user_id"] = user_id
        return None

    async def fake_analyze(message, session):
        return {"primary_intent": MagicMock(value="search"), "confidence": 0.9}

    async def fake_route(*a, **k):
        return {}

    with patch.object(orch, "_get_or_create_session", return_value={"id": "s1", "history": []}), \
         patch.object(orch, "_get_qwen_response", side_effect=fake_qwen), \
         patch.object(orch, "_analyze_intent", side_effect=fake_analyze), \
         patch.object(orch, "_route_to_features", side_effect=fake_route), \
         patch.object(orch, "_update_session"), \
         patch.object(orch, "_dispatch_turn_fact_extraction"), \
         patch.object(orch, "_is_cancelled", return_value=False), \
         patch.object(orch, "_start_chat_execution", return_value="exec-t"), \
         patch.object(orch, "_emit_agent_status", new=AsyncMock()), \
         patch.object(orch, "_finish_chat_execution"):
        await orch.process_chat_message("user-1", "hello", session_id="s1")

    assert captured.get("user_id") == "user-1"


# --------------------------------------------------------------------------- #
# Round 80 role loop — integration-data recall half
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_integration_leg_role_scoped_first_then_general_topup(monkeypatch):
    """With a known role, the leg searches role-tagged records FIRST
    (metadata.role filter) and tops up from the general pool — additive,
    never exclusive."""
    import core.memory_context_assembler as mca_mod

    conn = MagicMock()
    conn.table_names = MagicMock(return_value=["integration_zoho"])
    handler = MagicMock()
    handler.db = conn
    handler._ensure_db = MagicMock()
    # R83 contract: ONE unfiltered server pass (limit headroom), role ranking
    # client-side via parsed metadata JSON.
    import json as _json
    handler.search = MagicMock(return_value=[
        {"id": "r1", "text": "finance invoice", "source": "zoho",
         "metadata": _json.dumps({"role": "finance"})},
        {"id": "r2", "text": "general lead", "source": "zoho"},
    ])

    with patch("core.lancedb_handler.get_lancedb_handler", return_value=handler):
        lines = await mca_mod._integration_records_leg("q", "ws", agent_role="Finance")

    # R83: metadata is a JSON *string* column, so a server-side
    # `metadata.role == …` filter could never match — role scoping now happens
    # client-side post-search. There must be NO such server filter, and the
    # additive behavior is unchanged.
    filters = [c.kwargs.get("filter_str") for c in handler.search.call_args_list]
    assert all(f != "metadata.role == 'finance'" for f in filters)
    assert len(lines) == 2
    assert "finance invoice" in lines[0]  # role-tagged record ranked first


@pytest.mark.asyncio
async def test_integration_leg_without_role_single_unfiltered_pass():
    """No role → one unfiltered pass per table (general knowledge)."""
    import core.memory_context_assembler as mca_mod

    conn = MagicMock()
    conn.table_names = MagicMock(return_value=["integration_zoho"])
    handler = MagicMock()
    handler.db = conn
    handler._ensure_db = MagicMock()
    handler.search = MagicMock(return_value=[{"id": "g1", "text": "any", "source": "zoho"}])

    with patch("core.lancedb_handler.get_lancedb_handler", return_value=handler):
        await mca_mod._integration_records_leg("q", "ws", agent_role=None)

    assert handler.search.call_count == 1
    assert handler.search.call_args.kwargs.get("filter_str") is None


def test_resolve_agent_role_maps_category_lowercased():
    """_resolve_agent_role returns AgentRegistry.category lowercased — the
    same tag sync_integration_data stamps — and degrades to None on failure."""
    import core.memory_context_assembler as mca_mod

    agent = MagicMock()
    agent.category = "Finance"
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = agent

    class _SL:
        def __call__(self):
            return db

        def close(self):
            pass

    with patch("core.database.SessionLocal", new=_SL()):
        assert mca_mod._resolve_agent_role("agent-1") == "finance"

    with patch("core.database.SessionLocal", side_effect=RuntimeError("db down")):
        assert mca_mod._resolve_agent_role("agent-1") is None
    assert mca_mod._resolve_agent_role(None) is None


# ─────────────────────── taught-lessons leg ───────────────────────

@pytest.mark.asyncio
async def test_lessons_leg_rendered_first(monkeypatch):
    """Permanent taught lessons render as the FIRST block: they are standing
    instructions from the agent's own training and must not be the part cut
    by the total-budget tail truncation."""
    monkeypatch.setenv("MEMORY_CONTEXT_ASSEMBLY", "true")
    lessons_block = (
        "TRAINING LESSONS — PERMANENT INSTRUCTIONS you were taught:\n"
        "1. [tone] Address the client as Dr. Reyes"
    )

    async def fake_lessons(message, agent_id):
        assert agent_id == "hire-1"
        return lessons_block

    async def fake_graph(message, ws, tn):
        return "graph context"

    with patch.object(mca, "_lessons_leg", fake_lessons), \
         patch.object(mca, "_graph_leg", fake_graph), \
         patch.object(mca, "_knowledge_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_integration_records_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_episodes_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_facts_leg", AsyncMock(return_value=[])):
        block = await assemble_memory_context("anything", agent_id="hire-1")

    assert block is not None
    assert "TRAINING LESSONS" in block
    assert block.index("TRAINING LESSONS") < block.index("KNOWLEDGE GRAPH CONTEXT")


@pytest.mark.asyncio
async def test_lessons_leg_failure_isolated(monkeypatch):
    """A raising lessons leg yields no block; the rest still render."""
    monkeypatch.setenv("MEMORY_CONTEXT_ASSEMBLY", "true")

    async def boom(*a, **k):
        raise RuntimeError("registry down")

    async def fine_graph(message, ws, tn):
        return "graph context here"

    with patch.object(mca, "_lessons_leg", boom), \
         patch.object(mca, "_graph_leg", fine_graph), \
         patch.object(mca, "_knowledge_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_integration_records_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_episodes_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_facts_leg", AsyncMock(return_value=[])):
        block = await assemble_memory_context("anything")

    assert block is not None
    assert "graph context here" in block
    assert "TRAINING LESSONS" not in block


@pytest.mark.asyncio
async def test_lessons_leg_skipped_without_agent():
    """No operating agent (platform turn) → no lessons leg at all."""
    assert await mca._lessons_leg("hello", None) == ""
