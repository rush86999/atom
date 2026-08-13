# -*- coding: utf-8 -*-
"""Coverage wave 91 — core/health (perform_health_checks + per-service probes).

All three dependency probes are patched (SessionLocal, redis_cache,
get_lancedb_handler) — zero network, no real DB, no LLM.

- _check_database: execute ok → operational; execute raises / import fails →
  degraded.
- _check_redis: enabled True → operational; enabled False → degraded;
  import fails → degraded.
- _check_vector_store: live handler.db.db → operational; uninitialized /
  missing handler / import failure → degraded.
- perform_health_checks: all operational → healthy; any degraded → degraded.
"""
from types import SimpleNamespace

from core import health


class _FakeSession:
    def __init__(self, fail=False):
        self.fail = fail
        self.closed = False

    def execute(self, *args, **kwargs):
        if self.fail:
            raise RuntimeError("db down")
        return object()

    def close(self):
        self.closed = True


# ============================================================================
# _check_database
# ============================================================================

def test_check_database_operational(monkeypatch):
    session = _FakeSession()
    monkeypatch.setattr("core.database.SessionLocal", lambda: session)
    assert health._check_database() == "operational"
    assert session.closed is True


def test_check_database_degraded_on_execute_error(monkeypatch):
    monkeypatch.setattr("core.database.SessionLocal", lambda: _FakeSession(fail=True))
    assert health._check_database() == "degraded"


def test_check_database_degraded_on_import_error(monkeypatch):
    def _boom():
        raise ImportError("no SessionLocal")
    monkeypatch.setattr("core.database.SessionLocal", _boom)
    assert health._check_database() == "degraded"


# ============================================================================
# _check_redis
# ============================================================================

def test_check_redis_operational(monkeypatch):
    monkeypatch.setattr("core.cache.redis_cache", SimpleNamespace(enabled=True))
    assert health._check_redis() == "operational"


def test_check_redis_degraded_when_disabled(monkeypatch):
    monkeypatch.setattr("core.cache.redis_cache", SimpleNamespace(enabled=False))
    assert health._check_redis() == "degraded"


def test_check_redis_degraded_on_import_error(monkeypatch):
    import sys

    monkeypatch.delattr(sys.modules["core.cache"], "redis_cache", raising=False)
    assert health._check_redis() == "degraded"


# ============================================================================
# _check_vector_store
# ============================================================================

def test_check_vector_store_operational(monkeypatch):
    handler = SimpleNamespace(db=SimpleNamespace(db=object()))
    monkeypatch.setattr("core.lancedb_handler.get_lancedb_handler", lambda: handler)
    assert health._check_vector_store() == "operational"


def test_check_vector_store_degraded_uninitialized(monkeypatch):
    handler = SimpleNamespace(db=SimpleNamespace(db=None))
    monkeypatch.setattr("core.lancedb_handler.get_lancedb_handler", lambda: handler)
    assert health._check_vector_store() == "degraded"


def test_check_vector_store_degraded_no_handler(monkeypatch):
    monkeypatch.setattr("core.lancedb_handler.get_lancedb_handler", lambda: None)
    assert health._check_vector_store() == "degraded"


def test_check_vector_store_degraded_on_exception(monkeypatch):
    def _boom():
        raise RuntimeError("lancedb down")
    monkeypatch.setattr("core.lancedb_handler.get_lancedb_handler", _boom)
    assert health._check_vector_store() == "degraded"


# ============================================================================
# perform_health_checks
# ============================================================================

def test_perform_health_checks_all_operational(monkeypatch):
    monkeypatch.setattr("core.database.SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr("core.cache.redis_cache", SimpleNamespace(enabled=True))
    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler",
        lambda: SimpleNamespace(db=SimpleNamespace(db=object())),
    )
    out = health.perform_health_checks()
    assert out["status"] == "healthy"
    assert out["services"] == {
        "database": "operational",
        "redis": "operational",
        "vector_store": "operational",
    }


def test_perform_health_checks_degraded(monkeypatch):
    monkeypatch.setattr("core.database.SessionLocal", lambda: _FakeSession(fail=True))
    monkeypatch.setattr("core.cache.redis_cache", SimpleNamespace(enabled=False))
    monkeypatch.setattr("core.lancedb_handler.get_lancedb_handler", lambda: None)
    out = health.perform_health_checks()
    assert out["status"] == "degraded"
    assert out["services"] == {
        "database": "degraded",
        "redis": "degraded",
        "vector_store": "degraded",
    }
