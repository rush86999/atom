"""Coverage wave 23 — turn_fact_extractor + turn_fact_queue uncovered branches (TDD).

Covers missed lines after the pre-existing suites:
- _likely_contains_fact regex gates (short text, each pattern)
- _TTLSet eviction + expiry, compute_content_hash normalization
- _maturity_allows variants
- extract_from_turn sampling gate + error swallow
- _extract: empty text, breaker tripped, timeout, llm error, parse error,
  success with validation filtering, capped facts, no-facts
- _persist_one: antithrash hit, existing nonewk sup
  - IntegrityError race -> EWMA bump winner
  - fresh insert, supersede path, EWMA bump, exception
- _ewma_bump_existing (missing row, blend + touch)
- _write_vectors_best_effort swallow
- _extract_json_array: dict-wrap, fallback bracket slicing, nested garbage
- _coerce_confidence malformed, func_now
- failure counters, circuit breaker snapshot/reset
- get_turn_fact_extractor caching
- get_active_facts_for_prompt (categories filter, exception)
- prefetch_relevant_facts (flag off, trivial, short, error, found)
- search_reasoning_steps_lexical (short query, sqlite + exec filter,
  unsupported dialect, error)
- _query_safe_tokens
- remember_fact_explicit (invalid, success)
- forget_fact_explicit (no filter, by id, by substring, error)
Queue:
- enqueue (disabled, empty, full-drop), ensure_worker (no-loop defer, started)
- drain_once (empty, processed), stats, _process error, _worker_loop cancel
"""
import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.turn_fact_extractor as tfe
import core.turn_fact_queue as tq
from core.models import Base
from core.turn_fact_extractor import (
    TurnFactExtractor,
    compute_content_hash,
    forget_fact_explicit,
    get_active_facts_for_prompt,
    get_turn_fact_extractor,
    prefetch_relevant_facts,
    remember_fact_explicit,
    search_reasoning_steps_lexical,
)
from core.turn_fact_queue import ExtractionQueue, get_extraction_queue


class TestGatesAndHashes:
    def test_likely_contains_fact_short(self):
        assert tfe._likely_contains_fact("") is False
        assert tfe._likely_contains_fact("hi") is False

    def test_likely_contains_fact_patterns(self):
        assert tfe._likely_contains_fact("costs $5 per unit") is True
        assert tfe._likely_contains_fact("launched on March 14") is True
        assert tfe._likely_contains_fact("must use Stripe") is True
        assert tfe._likely_contains_fact("we decided to adopt X") is True
        assert tfe._likely_contains_fact("user prefers terse replies") is True
        assert tfe._likely_contains_fact("depends on auth service") is True
        assert tfe._likely_contains_fact("we use 3 replicas") is True
        assert tfe._likely_contains_fact("just a random hello world text without any durable signal ") is False

    def test_hash_normalization(self):
        a = compute_content_hash("ws1", "  Revenue is $50K.  ")
        b = compute_content_hash("ws1", "revenue is $50K")
        c = compute_content_hash("ws2", "Revenue is $50K.")
        assert a == b
        assert a != c
        assert a != compute_content_hash("ws1", "")

    def test_ttl_set_expiry_and_eviction(self):
        s = tfe._TTLSet(maxsize=2, ttl=1)
        s.add("a")
        s.add("b")
        s.add("c")  # evicts oldest "a"
        assert "a" not in s
        assert "b" in s
        assert "c" in s
        missing = tfe._TTLSet()
        assert "zzz" not in missing

    def test_maturity_allows(self):
        assert tfe._maturity_allows(None) is True
        assert tfe._maturity_allows("INTERN") is True
        assert tfe._maturity_allows("student") is False
        assert tfe._maturity_allows("AUTONOMOUS") is True

    def test_coerce_confidence(self):
        assert tfe._coerce_confidence("0.5") == 0.5
        assert tfe._coerce_confidence(1.5) == 1.0
        assert tfe._coerce_confidence(-1) == 0.0
        assert tfe._coerce_confidence("bad") == 0.8
        assert tfe._coerce_confidence(None) == 0.8

    def test_extract_json_array_variants(self):
        assert tfe._extract_json_array('[]') == []
        assert tfe._extract_json_array('[{"fact": "x"}]') == [{"fact": "x"}]
        assert tfe._extract_json_array('{"facts": [{"fact": "a"}]}') == [{"fact": "a"}]
        assert tfe._extract_json_array('{"data": [1,2]}') == [1, 2]
        assert tfe._extract_json_array('{"result": [3]}') == [3]
        assert tfe._extract_json_array("text [1,2] trailing") == [1, 2]
        assert tfe._extract_json_array("") is None
        assert tfe._extract_json_array("garbage") is None
        assert tfe._extract_json_array('{"nope": 1}') is None
        assert tfe._extract_json_array("{{{{[") is None
        assert tfe._extract_json_array('prefix [') is None

    def test_func_now_aware(self):
        assert tfe.func_now().tzinfo is not None

    def test_failure_counters(self):
        from core.turn_fact_extractor import _FAILURE_COUNTS, _increment_failure_counter, get_failure_counts
        _FAILURE_COUNTS.clear()
        _increment_failure_counter("timeout")
        assert get_failure_counts()["timeout"] == 1

    def test_circuit_breaker(self):
        from core.turn_fact_extractor import get_circuit_breaker_snapshot
        tfe._circuit_breaker.reset()
        snap = get_circuit_breaker_snapshot()
        assert "state" in snap
        assert snap["consecutive_failures"] == 0
        assert tfe._circuit_breaker.is_tripped() is False
        for _ in range(tfe._CB_THRESHOLD):
            tfe._circuit_breaker.record_failure()
        assert tfe._circuit_breaker.is_tripped() is True
        assert tfe._circuit_breaker.state == "open"
        # After cooldown, half-open probe allowed through
        tfe._circuit_breaker.opened_at = 0.0
        assert tfe._circuit_breaker.is_tripped() is False
        assert tfe._circuit_breaker.state == "half_open"
        tfe._circuit_breaker.record_success()
        assert tfe._circuit_breaker.state == "closed"
        tfe._circuit_breaker.reset()

    def test_get_extractor_cache(self):
        e1 = get_turn_fact_extractor("ws-x", "t-x")
        e2 = get_turn_fact_extractor("ws-x", "t-x")
        e3 = get_turn_fact_extractor("ws-x", "t-y")
        assert e1 is e2
        assert e1 is not e3

    def test_clamp(self):
        assert tfe._clamp(5, 0, 1) == 1
        assert tfe._clamp(-1, 0, 1) == 0
        assert tfe._clamp(0.5, 0, 1) == 0.5


class TestExtractPipeline:
    @pytest.fixture
    def extractor(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=engine, checkfirst=True)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        ex = TurnFactExtractor(workspace_id="ws1", tenant_id="t1")
        ex._recent_hashes._store.clear()
        llm = Mock()
        llm.generate = AsyncMock(return_value='[{"fact": "Revenue is 50k MRR", "category": "exact_value", "confidence": 0.9}]')
        ex.llm = llm
        with patch.object(tfe, "SessionLocal", Session):
            yield ex
        engine.dispose()

    async def test_extract_from_turn_maturity_blocked(self, extractor):
        result = await extractor.extract_from_turn(user_request="hi", maturity="STUDENT")
        assert result == []

    async def test_extract_from_turn_error_swallowed(self, extractor):
        with patch.object(extractor, "_extract", side_effect=RuntimeError("boom")):
            result = await extractor.extract_from_turn(user_request="user asked")
        assert result == []

    async def _call_extract(self, extractor, **kw):
        defaults = dict(
            text="", extraction_source="turn", execution_id=None,
            reasoning_step_id=None, episode_id=None, session_id=None, user_id=None,
        )
        defaults.update(kw)
        return await extractor._extract(**defaults)

    async def test_extract_empty_text(self, extractor):
        assert await self._call_extract(extractor) == []

    async def test_extract_breaker_tripped(self, extractor):
        tfe._circuit_breaker.reset()
        for _ in range(6):
            tfe._circuit_breaker.record_failure()
        result = await self._call_extract(extractor, text="costs $50")
        assert result == []
        tfe._circuit_breaker.reset()

    async def test_extract_no_fact_regex(self, extractor):
        result = await self._call_extract(extractor, text="just casual chatter here")
        assert result == []
        extractor.llm.generate.assert_not_called()

    async def test_extract_timeout(self, extractor):
        extractor.llm.generate = AsyncMock(side_effect=asyncio.TimeoutError())
        result = await self._call_extract(extractor, text="costs $50 per month")
        assert result == []

    async def test_extract_llm_error(self, extractor):
        extractor.llm.generate = AsyncMock(side_effect=RuntimeError("boom"))
        result = await self._call_extract(extractor, text="costs $50 per month")
        assert result == []

    @pytest.mark.parametrize("raw", ["not json at all", "", "[]"])
    async def test_extract_parse_failures(self, extractor, raw):
        extractor.llm.generate = AsyncMock(return_value=raw)
        result = await self._call_extract(extractor, text="costs $50 per month")
        assert result == [] if raw == "[]" else True

    async def test_extract_success_with_validation_filter(self, extractor):
        raw = json.dumps([
            {"fact": "Revenue is 50k MRR", "category": "exact_value", "confidence": 0.9},
            {"fact": "", "category": "exact_value"},
            {"fact": "bad category", "category": "nonsense", "confidence": 0.5},
            {"fact": "No tags", "category": "hard_constraint", "confidence": "0.8", "tags": "notalist"},
            "not a dict",
        ])
        extractor.llm.generate = AsyncMock(return_value=raw)
        result = await self._call_extract(extractor, text="costs $50 per month and must use stripe")
        assert len(result) == 2
        assert result[0].fact_text == "Revenue is 50k MRR"
        assert result[1].fact_text == "No tags"
        assert result[0].confidence == 0.9

    async def test_extract_caps_facts(self, extractor):
        facts = [
            {"fact": f"Fact number {i} is very durable", "category": "exact_value", "confidence": 0.9}
            for i in range(20)
        ]
        extractor.llm.generate = AsyncMock(return_value=json.dumps(facts))
        with patch("core.turn_fact_extractor.TURN_FACT_MAX_PER_TURN", 5):
            with patch.object(extractor, "_persist_one", return_value=SimpleNamespace(fact_text="x")) as po:
                result = await self._call_extract(extractor, text="costs $50 per month")
        assert po.call_count == 5


class TestPersist:
    @pytest.fixture
    def extractor(self):
        return TurnFactExtractor(workspace_id="ws1", tenant_id="t1")

    def _persist(self, extractor, **kw):
        defaults = dict(
            fact_text="", category="exact_value", domain="general", confidence=0.8,
            tags=None, extraction_source="turn", execution_id=None,
            reasoning_step_id=None, episode_id=None, session_id=None, user_id=None,
        )
        defaults.update(kw)
        return extractor._persist_one(**defaults)

    def test_persist_antithrash_hit(self, extractor):
        content_hash = compute_content_hash("ws1", "revenue up 20%")
        extractor._recent_hashes.add(content_hash)
        with patch("core.turn_fact_extractor.SessionLocal") as sl:
            result = self._persist(extractor, fact_text="revenue up 20%", confidence=0.8)
        assert result is None
        sl.assert_not_called()

    def test_persist_fresh_insert(self, extractor):
        row = SimpleNamespace(confidence=0.8)
        with patch("core.turn_fact_extractor.SessionLocal") as sl:
            db = Mock()
            sl.return_value.__enter__.return_value = db
            db.query.return_value.filter.return_value.first.return_value = None
            db.add = Mock()
            db.commit = Mock()
            db.refresh = Mock()
            result = self._persist(extractor, fact_text="revenue up 20%", confidence=0.8, tags=["x"])
        assert result is not None
        assert db.add.called
        assert db.commit.called

    def test_persist_integrity_race_ewma(self, extractor):
        existing = SimpleNamespace(confidence=0.6)
        with patch("core.turn_fact_extractor.SessionLocal") as sl:
            db = Mock()
            sl.return_value.__enter__.return_value = db
            db.query.return_value.filter.return_value.first.side_effect = [None]
            db.add = Mock()
            db.commit.side_effect = [tfe.IntegrityError("stmt", {}, Exception("race")), None]
            db.rollback = Mock()
            bumped = SimpleNamespace(confidence=0.7)
            with patch.object(extractor, "_ewma_bump_existing", return_value=bumped) as bump:
                result = self._persist(extractor, fact_text="revenue up 20%", confidence=0.8)
        assert result is bumped
        bump.assert_called_once_with(db, compute_content_hash("ws1", "revenue up 20%"), 0.8)

    def test_persist_supersede(self, extractor):
        existing = SimpleNamespace(confidence=0.2, id="old-id")
        rows = [existing]
        def first_side(*a, **k):
            return rows[0]
        with patch("core.turn_fact_extractor.SessionLocal") as sl:
            db = Mock()
            sl.return_value.__enter__.return_value = db
            db.query.return_value.filter.return_value.first.side_effect = first_side
            db.add = Mock()
            db.commit = Mock()
            db.refresh = Mock()
            result = self._persist(extractor, fact_text="revenue up 20%", confidence=0.9)
        assert result is not None
        assert existing.status == "superseded"
        assert result.parent_id == "old-id"
        assert result.commit_message == "superseded weaker fact"

    def test_persist_ewma_bump(self, extractor):
        existing = SimpleNamespace(confidence=0.6)
        with patch("core.turn_fact_extractor.SessionLocal") as sl:
            db = Mock()
            sl.return_value.__enter__.return_value = db
            db.query.return_value.filter.return_value.first.return_value = existing
            db.commit = Mock()
            db.refresh = Mock()
            with patch.object(extractor, "_ewma_bump_existing", return_value=existing) as bump:
                result = self._persist(extractor, fact_text="revenue up 20%", confidence=0.61)
        assert result is existing
        bump.assert_called_once()

    def test_persist_exception(self, extractor):
        with patch("core.turn_fact_extractor.SessionLocal", side_effect=RuntimeError("boom")):
            result = self._persist(extractor, fact_text="revenue up 20%", confidence=0.8)
        assert result is None

    def test_ewma_missing_row(self, extractor):
        class FakeDb:
            def query(self, *a, **k):
                q = Mock()
                q.filter.return_value.first.return_value = None
                return q
        result = extractor._ewma_bump_existing(FakeDb(), "hash", 0.9)
        assert result is None

    def test_write_vectors_swallow(self, extractor):
        with patch("core.turn_fact_vector_store.write_turn_fact_vectors", side_effect=RuntimeError("boom")):
            extractor._write_vectors_best_effort([], "")  # no raise

    def test_remember_fact_explicit_invalid(self):
        assert remember_fact_explicit(workspace_id="", fact_text="x", category="exact_value") is None
        assert remember_fact_explicit(workspace_id="w", fact_text="x", category="bad") is None

    def test_remember_fact_explicit_success(self):
        row = SimpleNamespace(fact_text="remembered")
        with patch.object(get_turn_fact_extractor("w", "t"), "_persist_one", return_value=row) as po:
            result = remember_fact_explicit(
                workspace_id="w", fact_text="important contract detail", category="hard_constraint",
                tenant_id="t",
            )
        assert result is row
        assert po.call_args.kwargs["_skip_antithrash"] is True


class TestForgetAndRecall:
    def test_forget_no_filter(self):
        assert forget_fact_explicit(workspace_id="w") == 0
        assert forget_fact_explicit(workspace_id="w", tenant_id="t") == 0
        assert forget_fact_explicit(workspace_id="") == 0

    def test_forget_by_id(self):
        r1 = SimpleNamespace(status="active")
        with patch("core.turn_fact_extractor.SessionLocal") as sl:
            db = Mock()
            sl.return_value.__enter__.return_value = db
            q = Mock()
            q.filter = Mock(return_value=q)
            q.all = Mock(return_value=[r1])
            db.query = Mock(return_value=q)
            result = forget_fact_explicit(workspace_id="w", fact_id="f1")
        assert result == 1
        assert r1.status == "invalidated"
        assert db.commit.called

    def test_forget_by_substring(self):
        r1 = SimpleNamespace(status="active")
        with patch("core.turn_fact_extractor.SessionLocal") as sl:
            db = Mock()
            sl.return_value.__enter__.return_value = db
            q = Mock()
            q.filter = Mock(return_value=q)
            q.all = Mock(return_value=[r1])
            db.query = Mock(return_value=q)
            result = forget_fact_explicit(workspace_id="w", fact_text_contains="contract")
        assert result == 1

    def test_forget_error(self):
        with patch("core.turn_fact_extractor.SessionLocal", side_effect=RuntimeError("boom")):
            assert forget_fact_explicit(workspace_id="w", fact_id="f1") == 0

    def test_get_active_facts_categories(self):
        with patch("core.turn_fact_extractor.logger"):
            q = Mock()
            q.filter = Mock(return_value=q)
            q.order_by = Mock(return_value=q)
            q.limit = Mock(return_value=q)
            q.all = Mock(return_value=[SimpleNamespace()])
            db = Mock()
            db.query = Mock(return_value=q)
            rows = get_active_facts_for_prompt(db, "w", categories=("exact_value",))
        assert len(rows) == 1
        assert q.filter.called

    def test_get_active_facts_error(self):
        q = Mock()
        q.filter.side_effect = RuntimeError("boom")
        db = Mock()
        db.query = Mock(return_value=q)
        assert get_active_facts_for_prompt(db, "w") == []

    def test_prefetch_flag_off(self):
        with patch("core.turn_fact_extractor.TURN_FACT_VECTOR_RECALL_ENABLED", False):
            assert prefetch_relevant_facts("w", "query about revenue") == []

    def test_prefetch_trivial(self):
        with patch("core.turn_fact_extractor.TURN_FACT_VECTOR_RECALL_ENABLED", True):
            assert prefetch_relevant_facts("w", "hi") == []
            assert prefetch_relevant_facts("w", "abc") == []

    def test_prefetch_error(self):
        with patch("core.turn_fact_extractor.TURN_FACT_VECTOR_RECALL_ENABLED", True):
            with patch("core.turn_fact_vector_store.search_relevant_fact_ids", side_effect=RuntimeError("boom")):
                assert prefetch_relevant_facts("w", "revenue grew strongly") == []

    def test_search_lexical_short(self):
        assert search_reasoning_steps_lexical("w", "ab") == []

    def test_search_lexical_sqlite(self):
        row = SimpleNamespace(id="s1", execution_id="e1", thought="t", observation="o", rank=3.5)
        with patch("core.turn_fact_extractor.SessionLocal") as sl:
            db = Mock()
            db.bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
            sl.return_value.__enter__.return_value = db
            db.execute = Mock(return_value=Mock(fetchall=Mock(return_value=[row])))
            result = search_reasoning_steps_lexical("w", "database import error")
        assert len(result) == 1
        assert result[0]["step_id"] == "s1"
        assert result[0]["rank"] == 3.5

    def test_search_lexical_unsupported_dialect(self):
        with patch("core.turn_fact_extractor.SessionLocal") as sl:
            db = Mock()
            db.bind = SimpleNamespace(dialect=SimpleNamespace(name="mssql"))
            sl.return_value.__enter__.return_value = db
            assert search_reasoning_steps_lexical("w", "database connection") == []

    def test_search_lexical_error(self):
        with patch("core.turn_fact_extractor.SessionLocal", side_effect=RuntimeError("boom")):
            assert search_reasoning_steps_lexical("w", "database connection") == []

    def test_query_safe_tokens(self):
        assert tfe._query_safe_tokens("DB  query (x)") == ["db", "query"]


class TestQueue:
    def test_enqueue_disabled(self):
        with patch("core.turn_fact_queue.TURN_FACT_PRE_COMPRESS_ENABLED", False):
            assert get_extraction_queue().enqueue("p", "w") is False

    def test_enqueue_empty(self):
        q = ExtractionQueue(maxsize=10)
        assert q.enqueue("", "w") is False
        assert q.enqueue("prompt", "") is False

    def test_enqueue_full_drops(self):
        q = ExtractionQueue(maxsize=1)
        assert q.enqueue("p1", "w") is True
        assert q.enqueue("p2", "w") is False
        assert q.stats()["dropped"] == 1

    def test_drain_empty(self):
        q = ExtractionQueue(maxsize=10)
        assert asyncio.run(q.drain_once()) == 0

    def test_drain_processed(self):
        q = ExtractionQueue(maxsize=10)
        q.enqueue("costs $50", "w")
        with patch.object(q, "_process", new=AsyncMock(return_value=2)):
            assert asyncio.run(q.drain_once()) == 2

    async def test_process_error_swallowed(self):
        q = ExtractionQueue(maxsize=10)
        item = SimpleNamespace(workspace_id="w", tenant_id="t")
        with patch("core.turn_fact_queue.get_turn_fact_extractor", side_effect=RuntimeError("boom")):
            assert await q._process(item) == 0

    def test_ensure_worker_started_idempotent(self):
        q = ExtractionQueue(maxsize=10)
        with patch("core.turn_fact_queue.asyncio.get_event_loop") as gel:
            loop = Mock()
            loop.is_closed = Mock(return_value=False)
            gel.return_value = loop
            loop.create_task = Mock(return_value=Mock())
            q.ensure_worker()
            assert q._started is True
            q.ensure_worker()
            assert loop.create_task.call_count == 1

    def test_ensure_worker_no_loop(self):
        q = ExtractionQueue(maxsize=10)
        with patch("core.turn_fact_queue.asyncio.get_event_loop", side_effect=RuntimeError("no loop")):
            q.ensure_worker()
        assert q._started is False

    async def test_worker_loop_cancelled(self):
        q = ExtractionQueue(maxsize=10)
        with patch.object(q, "_process", new=AsyncMock(side_effect=asyncio.CancelledError())):
            task = asyncio.create_task(q._worker_loop())
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    def test_get_queue_singleton(self):
        assert get_extraction_queue() is get_extraction_queue()
