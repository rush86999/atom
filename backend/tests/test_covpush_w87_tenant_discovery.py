# -*- coding: utf-8 -*-
"""Coverage wave 87 — core/tenant_discovery (standalone, zero LLM spend,
no network; in-memory SQLite + injected fake cache).

- get_tenant_id_by_external_id: empty external_id short-circuit (no cache
  call), cache-hit passthrough (str coercion), cache-miss → DB lookup +
  cache write with TTL, not-found → None, DB exception → None (logged), PG
  row_security off/on bracketing when the dialect is postgresql, and the
  is_active filter (inactive mappings never resolve).
- register_external_id: NEW-mapping creation (bug 87-2 — previously returned
  False and never inserted, so OAuth pre-population was a silent no-op);
  update path re-points an existing row and invalidates BOTH old and new
  cache keys (BUG-083 regression); same-external-id update is a no-op that
  still invalidates; CROSS-TENANT CLAIM refused (bug 87-1 — a second tenant
  could register an external_id owned by tenant A, making `.first()`
  resolution ambiguous → cross-tenant webhook misrouting); commit failure →
  rollback + False; query failure → False.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
import core.models  # noqa: F401 (register models)
from core.models import TenantIntegration
from core.tenant_discovery import TenantDiscoveryService


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def cache():
    cache = MagicMock()
    cache.get_async = AsyncMock(return_value=None)
    cache.set_async = AsyncMock(return_value=True)
    cache.delete_async = AsyncMock(return_value=True)
    return cache


def _make_integration(db, tenant_id="tenant-a", connector_id="slack",
                      external_id="T012345", active=True, **kw):
    integration = TenantIntegration(
        tenant_id=tenant_id,
        connector_id=connector_id,
        external_id=external_id,
        is_active=active,
        **kw,
    )
    db.add(integration)
    db.commit()
    return integration


def _service(db, cache):
    svc = TenantDiscoveryService(db)
    svc.cache = cache
    return svc


class TestGetTenantIdByExternalId:
    def test_empty_external_id_returns_none(self, db, cache):
        svc = _service(db, cache)
        assert asyncio_run(svc.get_tenant_id_by_external_id("slack", "")) is None
        assert asyncio_run(svc.get_tenant_id_by_external_id("slack", None)) is None
        cache.get_async.assert_not_called()

    def test_cache_hit_returns_string(self, db, cache):
        cache.get_async = AsyncMock(return_value="tenant-a")
        svc = _service(db, cache)
        result = asyncio_run(svc.get_tenant_id_by_external_id("slack", "T012345"))
        assert result == "tenant-a"
        cache.get_async.assert_awaited_once_with("discovery:slack:T012345")

    def test_cache_miss_populates_cache_and_returns(self, db, cache):
        _make_integration(db, tenant_id="tenant-a")
        svc = _service(db, cache)
        result = asyncio_run(svc.get_tenant_id_by_external_id("slack", "T012345"))
        assert result == "tenant-a"
        cache.set_async.assert_awaited_once_with(
            "discovery:slack:T012345", "tenant-a", ttl=3600
        )

    def test_not_found_returns_none(self, db, cache):
        svc = _service(db, cache)
        assert asyncio_run(
            svc.get_tenant_id_by_external_id("slack", "T999999")
        ) is None

    def test_inactive_integration_does_not_resolve(self, db, cache):
        _make_integration(db, tenant_id="tenant-a", active=False)
        svc = _service(db, cache)
        assert asyncio_run(
            svc.get_tenant_id_by_external_id("slack", "T012345")
        ) is None

    def test_db_exception_returns_none(self, db, cache):
        svc = _service(db, cache)
        with patch.object(svc.db, "query", side_effect=RuntimeError("db down")):
            assert asyncio_run(
                svc.get_tenant_id_by_external_id("slack", "T012345")
            ) is None

    def test_postgresql_dialect_brackets_row_security(self, db, cache):
        _make_integration(db, tenant_id="tenant-a")
        fake_bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
        fake_db = MagicMock()
        fake_db.bind = fake_bind
        fake_db.query = db.query
        svc = _service(fake_db, cache)
        result = asyncio_run(svc.get_tenant_id_by_external_id("slack", "T012345"))
        assert result == "tenant-a"
        assert fake_db.execute.call_count == 2


class TestRegisterExternalId:
    def test_new_mapping_creates_row(self, db, cache):
        """BUG 87-2 regression: registering a brand-new (tenant, connector,
        external_id) must CREATE the mapping — previously returned False and
        inserted nothing, silently breaking OAuth pre-population."""
        svc = _service(db, cache)
        result = asyncio_run(
            svc.register_external_id("tenant-a", "slack", "T012345")
        )
        assert result is True
        row = db.query(TenantIntegration).filter(
            TenantIntegration.tenant_id == "tenant-a",
            TenantIntegration.connector_id == "slack",
        ).first()
        assert row is not None
        assert row.external_id == "T012345"
        cache.delete_async.assert_awaited_once_with("discovery:slack:T012345")

    def test_update_path_invalidates_old_and_new_keys(self, db, cache):
        _make_integration(db, tenant_id="tenant-a", external_id="T-OLD")
        svc = _service(db, cache)
        result = asyncio_run(
            svc.register_external_id("tenant-a", "slack", "T-NEW")
        )
        assert result is True
        db.refresh(db.query(TenantIntegration).first())
        assert db.query(TenantIntegration).first().external_id == "T-NEW"
        cache.delete_async.assert_any_await("discovery:slack:T-NEW")
        cache.delete_async.assert_any_await("discovery:slack:T-OLD")

    def test_update_same_external_id_is_noop(self, db, cache):
        _make_integration(db, tenant_id="tenant-a", external_id="T012345")
        svc = _service(db, cache)
        result = asyncio_run(
            svc.register_external_id("tenant-a", "slack", "T012345")
        )
        assert result is True
        cache.delete_async.assert_awaited_once_with("discovery:slack:T012345")

    def test_cross_tenant_claim_refused(self, db, cache):
        """BUG 87-1 regression: tenant B must NOT be able to register an
        external_id already owned by tenant A — two live mappings make
        `.first()` resolution non-deterministic and can route tenant A's
        webhooks to tenant B (tenant isolation breach)."""
        _make_integration(db, tenant_id="tenant-a", external_id="T012345")
        svc = _service(db, cache)
        result = asyncio_run(
            svc.register_external_id("tenant-b", "slack", "T012345")
        )
        assert result is False
        rows = db.query(TenantIntegration).filter(
            TenantIntegration.connector_id == "slack",
            TenantIntegration.external_id == "T012345",
        ).all()
        assert len(rows) == 1
        assert rows[0].tenant_id == "tenant-a"

    def test_same_tenant_reclaim_allowed(self, db, cache):
        """Updating the SAME tenant's mapping to an external_id it owns is
        still allowed (the guard excludes the tenant's own row)."""
        _make_integration(db, tenant_id="tenant-a", external_id="T012345")
        svc = _service(db, cache)
        assert asyncio_run(
            svc.register_external_id("tenant-a", "slack", "T012345")
        ) is True

    def test_commit_failure_rolls_back(self, db, cache):
        _make_integration(db, tenant_id="tenant-a", external_id="T-OLD")
        svc = _service(db, cache)
        real_rollback = db.rollback
        rollback_spy = MagicMock(side_effect=real_rollback)
        db.rollback = rollback_spy
        try:
            with patch.object(svc.db, "commit", side_effect=RuntimeError("db down")):
                result = asyncio_run(
                    svc.register_external_id("tenant-a", "slack", "T-NEW")
                )
        finally:
            db.rollback = real_rollback
        assert result is False
        rollback_spy.assert_called_once()

    def test_query_failure_returns_false(self, db, cache):
        svc = _service(db, cache)
        with patch.object(svc.db, "query", side_effect=RuntimeError("db down")):
            assert asyncio_run(
                svc.register_external_id("tenant-a", "slack", "T012345")
            ) is False


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)
