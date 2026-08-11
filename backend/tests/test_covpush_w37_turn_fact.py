"""Coverage wave 37 — core/turn_fact_extractor.py (89% → 90%+).

Completes the remaining branches: _TTLSet expiry/prune, sample-rate skip,
extract_from_prompt_before_truncation success+exception, vector-write
swallow, EWMA bump on existing rows, _compose_turn_text part matrix,
_extract_json_array fallback exception, prefetch_relevant_facts relevance
ordering, lexical search (empty tokens / postgresql branch / execution_id
filter), remember_fact_explicit exception tolerance.
"""
import time as _time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.turn_fact_extractor as tfe
from core.database import Base
from core.turn_fact_extractor import (
    TurnFactExtractor,
    _compose_turn_text,
    _extract_json_array,
    prefetch_relevant_facts,
    remember_fact_explicit,
    search_reasoning_steps_lexical,
)


@pytest.fixture
def extractor():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine, checkfirst=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    ex = TurnFactExtractor(workspace_id="ws1", tenant_id="t1")
    ex._recent_hashes._store.clear()
    llm = Mock()
    llm.generate = AsyncMock(
        return_value='[{"fact": "Revenue is 50k MRR", "category": "exact_value", "confidence": 0.9}]'
    )
    ex.llm = llm
    with patch.object(tfe, "SessionLocal", Session):
        yield ex
    engine.dispose()


def await_coroutine(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestTTLSet:
    def test_contains_missing(self):
        s = tfe._TTLSet()
        assert ("k" in s) is False

    def test_contains_expired_pops_and_returns_false(self):
        s = tfe._TTLSet(ttl=10)
        s.add("k")
        s._store["k"] = _time.time() - 11
        assert ("k" in s) is False
        assert "k" not in s._store

    def test_prune_removes_expired_only(self):
        s = tfe._TTLSet(ttl=10)
        s.add("fresh")
        s.add("stale")
        s._store["stale"] = _time.time() - 11
        s._prune()
        assert "fresh" in s._store
        assert "stale" not in s._store


class TestSampleRateAndPromptHook:
    async def test_sample_rate_zero_skips(self, extractor):
        with patch("core.turn_fact_extractor.TURN_FACT_EXTRACTION_SAMPLE_RATE", 0.0):
            result = await extractor.extract_from_turn(user_request="hi", maturity="AUTONOMOUS")
        assert result == []

    async def test_extract_from_prompt_success(self, extractor):
        result = await extractor.extract_from_prompt_before_truncation(
            prompt="The user said revenue is 50k MRR today",
            execution_id="e1", session_id="s1",
        )
        assert len(result) == 1
        assert result[0].extraction_source == "pre_compress"

    async def test_extract_from_prompt_exception_swallowed(self, extractor):
        with patch.object(extractor, "_extract", side_effect=RuntimeError("boom")):
            result = await extractor.extract_from_prompt_before_truncation(prompt="x")
        assert result == []


class TestVectorWriteAndEwma:
    async def test_vector_write_failure_swallowed(self, extractor):
        with patch.object(extractor, "_write_vectors_best_effort",
                          side_effect=RuntimeError("lancedb down")):
            result = await extractor.extract_from_turn(
                user_request="revenue is 50k MRR", maturity="AUTONOMOUS")
        assert len(result) == 1  # SQL row still persisted

    async def test_ewma_bump_existing(self, extractor):
        row = extractor._persist_one(
            fact_text="Revenue is 50k MRR", category="exact_value",
            domain="general", confidence=0.6, tags=None,
            extraction_source="turn", execution_id=None,
            reasoning_step_id=None, episode_id=None,
            session_id=None, user_id=None, _skip_antithrash=True,
        )
        assert row is not None
        # Direct EWMA bump on the existing row
        h = tfe.compute_content_hash("ws1", "Revenue is 50k MRR")
        from core.models import TurnFact as TF
        with tfe.SessionLocal() as db:
            existing = db.query(TF).filter(TF.content_hash == h).first()
            bumped = extractor._ewma_bump_existing(db, h, 0.9)
            assert bumped is existing
            assert existing.confidence > 0.6
            assert h in extractor._recent_hashes


class TestComposeAndJson:
    def test_compose_full_parts(self):
        text = _compose_turn_text(
            user_request="ur", thought="th", action={"name": "read"},
            observation="obs", final_answer="ans",
        )
        assert "USER: ur" in text
        assert "THOUGHT: th" in text
        assert 'ACTION: {"name": "read"}' in text
        assert "OBSERVATION: obs" in text
        assert "ANSWER: ans" in text

    def test_compose_str_action_and_none_parts(self):
        text = _compose_turn_text(
            user_request=None, thought=None, action="do_it",
            observation=None, final_answer=None)
        assert text == "ACTION: do_it"

    def test_json_array_fallback_exception_returns_none(self):
        assert _extract_json_array("[1,,2]") is None

    def test_json_array_fallback_valid(self):
        assert _extract_json_array("prefix [1, 2] suffix") == [1, 2]


class TestPrefetchAndSearch:
    def test_prefetch_disabled_returns_empty(self):
        with patch("core.turn_fact_extractor.TURN_FACT_VECTOR_RECALL_ENABLED", False):
            assert prefetch_relevant_facts("ws1", "query words", 5) == []

    def test_prefetch_no_ids_returns_empty(self):
        with patch("core.turn_fact_extractor.TURN_FACT_VECTOR_RECALL_ENABLED", True), \
             patch("core.turn_fact_vector_store.search_relevant_fact_ids",
                   return_value=[]):
            assert prefetch_relevant_facts("ws1", "query words", 5) == []

    def test_prefetch_sorts_by_relevance(self, extractor):
        from core.turn_fact_extractor import compute_content_hash
        with tfe.SessionLocal() as db:
            row_a = tfe.TurnFact(
                id="id-a", workspace_id="ws1", fact_text="alpha",
                category="exact_value", confidence=0.8, content_hash=compute_content_hash("ws1", "alpha"),
                status="active", extraction_source="turn",
            )
            row_b = tfe.TurnFact(
                id="id-b", workspace_id="ws1", fact_text="beta",
                category="exact_value", confidence=0.8, content_hash=compute_content_hash("ws1", "beta"),
                status="active", extraction_source="turn",
            )
            db.add_all([row_a, row_b])
            db.commit()
        with patch("core.turn_fact_extractor.TURN_FACT_VECTOR_RECALL_ENABLED", True), \
             patch("core.turn_fact_vector_store.search_relevant_fact_ids",
                   return_value=["id-b", "id-a"]):
            rows = prefetch_relevant_facts("ws1", "query words", 5)
        assert [r.id for r in rows] == ["id-b", "id-a"]

    def test_prefetch_trivial_query_returns_empty(self):
        with patch("core.turn_fact_extractor.TURN_FACT_VECTOR_RECALL_ENABLED", True), \
             patch("core.turn_fact_vector_store.search_relevant_fact_ids") as sri:
            assert prefetch_relevant_facts("ws1", "hi", 5) == []
            sri.assert_not_called()

    def test_prefetch_exception_returns_empty(self):
        with patch("core.turn_fact_extractor.TURN_FACT_VECTOR_RECALL_ENABLED", True), \
             patch("core.turn_fact_vector_store.search_relevant_fact_ids",
                   side_effect=RuntimeError("boom")):
            assert prefetch_relevant_facts("ws1", "query words", 5) == []

    def test_lexical_short_query_empty(self):
        assert search_reasoning_steps_lexical("ws1", "ab") == []

    def test_lexical_no_tokens_empty(self):
        assert search_reasoning_steps_lexical("ws1", "!!! ???") == []

    def test_lexical_postgresql_branch(self):
        db = MagicMock()
        db.__enter__.return_value = db
        db.bind.dialect.name = "postgresql"
        db.execute.return_value.fetchall.return_value = [
            SimpleNamespace(id="s1", execution_id="e1", thought="t", observation="o", rank=2.5),
        ]
        with patch("core.turn_fact_extractor.SessionLocal", return_value=db):
            rows = search_reasoning_steps_lexical("ws1", "query words", execution_id="e1")
        assert rows == [{
            "step_id": "s1", "execution_id": "e1",
            "thought": "t", "observation": "o", "rank": 2.5,
        }]

    def test_lexical_sqlite_branch_with_execution_filter(self):
        db = MagicMock()
        db.__enter__.return_value = db
        db.bind.dialect.name = "sqlite"
        db.execute.return_value.fetchall.return_value = [
            SimpleNamespace(id="s1", execution_id="e1", thought=None, observation=None, rank=None),
        ]
        with patch("core.turn_fact_extractor.SessionLocal", return_value=db):
            rows = search_reasoning_steps_lexical("ws1", "query words", execution_id="e1")
        assert rows[0]["thought"] == ""
        assert rows[0]["rank"] == 0.0
        args, kwargs = db.execute.call_args
        assert "AND s.execution_id" in str(args[0])

    def test_lexical_other_dialect_returns_empty(self):
        db = MagicMock()
        db.__enter__.return_value = db
        db.bind.dialect.name = "mysql"
        with patch("core.turn_fact_extractor.SessionLocal", return_value=db):
            assert search_reasoning_steps_lexical("ws1", "query words") == []


class TestRememberFactExplicit:
    async def test_empty_fact_returns_none(self, extractor):
        assert remember_fact_explicit(workspace_id="ws1", fact_text="", category="exact_value") is None

    async def test_bad_category_returns_none(self, extractor):
        assert remember_fact_explicit(workspace_id="ws1", fact_text="x", category="bogus") is None

    async def test_success_persists(self, extractor):
        row = remember_fact_explicit(
            workspace_id="ws1", fact_text="Remember: the API key lives in vault",
            category="exact_value",
        )
        assert row is not None
        assert row.extraction_source == "agent_explicit"

    async def test_extractor_error_returns_none(self):
        with patch("core.turn_fact_extractor.get_turn_fact_extractor",
                   side_effect=RuntimeError("boom")):
            assert remember_fact_explicit(
                workspace_id="ws1", fact_text="x", category="exact_value") is None
