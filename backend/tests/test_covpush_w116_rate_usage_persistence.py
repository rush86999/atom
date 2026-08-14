"""
Backend depth wave 116 (2026-08-13) — coverage push for
core/llm/rate_usage_persistence.py.

Covers table-ensure (incl. failure), fire-and-forget record(), cached
monthly_usage aggregates (with/without model filter, cache hit, failure),
and the singleton. Uses an in-memory SQLite engine — zero LLM spend.
"""

import threading
import time
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import core.llm.rate_usage_persistence as mod
from core.llm.rate_usage_persistence import (
    RateUsagePersistence,
    RateUsageRecord,
    get_rate_usage_persistence,
)


@pytest.fixture
def engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture
def persistence(engine):
    return RateUsagePersistence(engine=engine)


class TestEnsureTable:
    """Cover _ensure_table first-call and failure paths (lines 75-84)."""

    def test_table_created_lazily_on_first_use(self, persistence, engine):
        assert persistence._table_ready is False
        persistence.record("opencode-go", "deepseek-v4-flash", 10, 5)
        assert persistence._table_ready is True
        with engine.connect() as conn:
            tables = [
                r[0] for r in conn.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            ]
        assert "rate_usage_records" in tables

    def test_double_ensure_is_safe(self, persistence):
        persistence._ensure_table()
        persistence._ensure_table()
        assert persistence._table_ready is True

    def test_double_ensure_race_inside_lock(self, persistence):
        persistence._table_ready = False
        started = threading.Event()
        release = threading.Event()
        original = mod.Base.metadata.create_all

        def slow_create_all(*args, **kwargs):
            started.set()
            release.wait(5)
            return original(*args, **kwargs)

        with patch.object(mod.Base.metadata, "create_all", side_effect=slow_create_all):
            t = threading.Thread(target=persistence._ensure_table)
            t.start()
            assert started.wait(5)
            persistence._ensure_table()  # blocks on lock; inner check returns
            release.set()
            t.join(5)
        assert persistence._table_ready is True

    def test_ensure_table_failure_is_swallowed(self, engine):
        persistence = RateUsagePersistence(engine=engine)
        with patch.object(
            mod.Base.metadata, "create_all", side_effect=RuntimeError("db down")
        ):
            persistence._ensure_table()
        assert persistence._table_ready is False
        # record() then degrades silently
        persistence.record("opencode-go", "m", 1, 1)  # must not raise


class TestRecord:
    """Cover record() write path (lines 93-110)."""

    def test_record_persists_row(self, persistence):
        persistence.record("opencode-go", "deepseek-v4-flash", 100, 50)
        persistence.record("opencode-go", None, 10, 0)
        session = persistence._session_factory()
        try:
            rows = session.query(RateUsageRecord).all()
        finally:
            session.close()
        assert len(rows) == 2
        assert rows[0].provider_id == "opencode-go"
        assert rows[0].model_id == "deepseek-v4-flash"
        assert rows[0].input_tokens == 100
        assert rows[0].output_tokens == 50

    def test_record_defaults_none_tokens_to_zero(self, persistence):
        persistence.record("opencode-go", "m", None, None)
        session = persistence._session_factory()
        try:
            row = session.query(RateUsageRecord).one()
        finally:
            session.close()
        assert row.input_tokens == 0
        assert row.output_tokens == 0

    def test_record_clears_monthly_cache(self, persistence):
        persistence.record("opencode-go", "m", 5, 5)
        first = persistence.monthly_usage("opencode-go", "m")
        assert first["requests"] == 1
        persistence.record("opencode-go", "m", 5, 5)
        second = persistence.monthly_usage("opencode-go", "m")
        assert second["requests"] == 2  # cache was cleared by the write

    def test_record_failure_is_non_fatal(self, persistence):
        fake_factory = Mock()
        session = fake_factory.return_value
        session.commit.side_effect = RuntimeError("boom")
        persistence._session_factory = fake_factory
        persistence.record("opencode-go", "m", 1, 1)  # must not raise

    def test_record_skips_when_table_unavailable(self, persistence):
        with patch.object(
            mod.Base.metadata, "create_all", side_effect=RuntimeError("db down")
        ):
            persistence.record("opencode-go", "m", 1, 1)
        assert persistence._table_ready is False


class TestMonthlyUsage:
    """Cover monthly_usage aggregates and caching (lines 116-163)."""

    def test_aggregates_whole_provider(self, persistence):
        persistence.record("opencode-go", "deepseek-v4-flash", 100, 50)
        persistence.record("opencode-go", "kimi-k2.7-code", 10, 5)
        result = persistence.monthly_usage("opencode-go")
        assert result["requests"] == 2
        assert result["input_tokens"] == 110
        assert result["output_tokens"] == 55
        assert result["total_tokens"] == 165
        assert result["provider"] == "opencode-go"
        assert result["model"] is None
        assert result["period"] == f"{datetime.now(timezone.utc).year}-{datetime.now(timezone.utc).month:02d}"

    def test_aggregates_single_model(self, persistence):
        persistence.record("opencode-go", "deepseek-v4-flash", 100, 50)
        persistence.record("opencode-go", "kimi-k2.7-code", 10, 5)
        result = persistence.monthly_usage("opencode-go", "deepseek-v4-flash")
        assert result["requests"] == 1
        assert result["input_tokens"] == 100
        assert result["model"] == "deepseek-v4-flash"

    def test_cache_hit_avoids_db(self, persistence):
        persistence.record("opencode-go", "m", 7, 3)
        first = persistence.monthly_usage("opencode-go", "m")
        assert first["requests"] == 1
        fake_factory = Mock()
        persistence._session_factory = fake_factory
        second = persistence.monthly_usage("opencode-go", "m")
        assert second["requests"] == 1
        fake_factory.assert_not_called()

    def test_cache_expires_after_60s(self, persistence):
        persistence.record("opencode-go", "m", 7, 3)
        persistence.monthly_usage("opencode-go", "m")
        fake_time = Mock()
        fake_time.time.return_value = time.time() + MONTHLY_FAKE_OFFSET
        fake_factory = Mock()
        fake_session = fake_factory.return_value
        fake_row = Mock()
        fake_row.input_tokens = 7
        fake_row.output_tokens = 3
        fake_row.requests = 1
        fake_session.query.return_value.filter.return_value.filter.return_value.one.return_value = fake_row
        persistence._session_factory = fake_factory
        with patch.object(mod, "time", fake_time):
            result = persistence.monthly_usage("opencode-go", "m")
        assert result["requests"] == 1
        assert fake_factory.called  # fresh DB read after expiry

    def test_read_failure_returns_none(self, persistence):
        fake_factory = Mock()
        fake_session = fake_factory.return_value
        fake_session.query.side_effect = RuntimeError("boom")
        persistence._session_factory = fake_factory
        assert persistence.monthly_usage("opencode-go") is None

    def test_table_unavailable_returns_none(self, engine):
        persistence = RateUsagePersistence(engine=engine)
        with patch.object(
            mod.Base.metadata, "create_all", side_effect=RuntimeError("db down")
        ):
            assert persistence.monthly_usage("opencode-go") is None


MONTHLY_FAKE_OFFSET = 61.0


class TestSingleton:
    """Cover the singleton accessor (lines 171-179)."""

    def test_returns_same_instance(self):
        assert get_rate_usage_persistence() is get_rate_usage_persistence()

    def test_singleton_created_lazily(self):
        saved = mod._persistence
        try:
            mod._persistence = None
            instance = get_rate_usage_persistence()
            assert instance is mod._persistence
            assert instance is not None
        finally:
            mod._persistence = saved
