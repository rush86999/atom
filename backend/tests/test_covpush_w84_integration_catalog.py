# -*- coding: utf-8 -*-
"""Coverage wave 84 — core/integration_catalog_service (standalone, mocked
registry-level deps, real in-memory SQLite for TenantIntegrationConfig).

- _validate_tenant_id: canonical UUID / canonicalization, invalid → ValueError.
- search_integrations: name/description matching, limit, tenant status
  enrichment from TenantIntegrationConfig (enabled/connected_user_count),
  default-true when no config row, invalid tenant.
- filter_by_category: match / no match / enrich.
- get_categories: with/without category keys, dedup, sorted.
- get_integration_config: found ±config row, missing integration → None.
- update_integration_config: enabled only / sync_settings only / both /
  invalid sync settings (frequency_hours, data_limit_mb, entity_types).
- _validate_sync_settings unit coverage for every guard.
- Registry-bound tests drive the REAL IntegrationRegistry methods
  (get_tenant_config / set_tenant_enabled / update_sync_settings) — these
  were missing from the v1 registry (AttributeError bug) and are fixed in
  core/integration_registry.py.
"""
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.integration_catalog_service import IntegrationCatalogService
from core.integration_registry import IntegrationRegistry
from core.models import TenantIntegrationConfig


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _tid():
    return str(uuid.uuid4())


@pytest.fixture()
def svc(db):
    return IntegrationCatalogService(db)


def _add_config(db, tenant_id, integration_id, enabled=True, sync_settings=None,
                connected_user_count=3, last_activity_at="2026-08-01T10:00:00Z",
                last_sync_at="2026-08-02T11:00:00Z"):
    cfg = TenantIntegrationConfig(
        tenant_id=tenant_id,
        integration_id=integration_id,
        enabled=enabled,
        config_json={
            "sync_settings": sync_settings or {},
            "connected_user_count": connected_user_count,
            "last_activity_at": last_activity_at,
            "last_sync_at": last_sync_at,
        },
        schema_hash="v1",
    )
    db.add(cfg)
    db.commit()
    return cfg


# ============================================================================
# _validate_tenant_id
# ============================================================================

class TestValidateTenantId:
    def test_valid_uuid(self, svc):
        raw = str(uuid.uuid4())
        assert svc._validate_tenant_id(raw) == raw

    def test_canonicalizes_uuid(self, svc):
        raw = "00000000-0000-0000-0000-000000000000"
        assert svc._validate_tenant_id(raw) == raw

    def test_invalid_raises(self, svc):
        with pytest.raises(ValueError, match="Invalid tenant_id format"):
            svc._validate_tenant_id("not-a-uuid")

    def test_none_raises(self, svc):
        with pytest.raises(ValueError, match="Invalid tenant_id format"):
            svc._validate_tenant_id(None)

    def test_empty_raises(self, svc):
        with pytest.raises(ValueError, match="Invalid tenant_id format"):
            svc._validate_tenant_id("")


# ============================================================================
# search_integrations
# ============================================================================

class TestSearchIntegrations:
    async def test_search_by_name_with_tenant_status(self, db, svc):
        tenant_id = _tid()
        _add_config(db, tenant_id, "slack", enabled=False, connected_user_count=5)

        results = await svc.search_integrations(tenant_id, "slack")
        ids = [r["id"] for r in results]
        assert "slack" in ids
        slack = next(r for r in results if r["id"] == "slack")
        assert slack["enabled"] is False
        assert slack["connected_user_count"] == 5
        assert slack["name"] == "Slack"

    async def test_search_no_config_defaults_enabled(self, svc):
        results = await svc.search_integrations(_tid(), "slack")
        slack = next(r for r in results if r["id"] == "slack")
        assert slack["enabled"] is True
        assert slack["connected_user_count"] == 0

    async def test_search_respects_limit(self, svc):
        results = await svc.search_integrations(_tid(), "s", limit=2)
        assert len(results) == 2

    async def test_search_matches_description_when_present(self, svc):
        tenant_id = _tid()
        fake_integrations = [
            {"id": "alpha", "name": "Alpha", "description": "handles payroll"},
            {"id": "beta", "name": "Beta", "description": "nothing here"},
        ]
        with patch.object(svc.registry, "get_all_integrations", return_value=fake_integrations):
            results = await svc.search_integrations(tenant_id, "payroll")
        assert [r["id"] for r in results] == ["alpha"]

    async def test_search_no_match(self, svc):
        results = await svc.search_integrations(_tid(), "zzz_nothing_zzz")
        assert results == []

    async def test_search_invalid_tenant(self, svc):
        with pytest.raises(ValueError):
            await svc.search_integrations("bad-tenant", "slack")


# ============================================================================
# filter_by_category / get_categories
# ============================================================================

class TestFilterByCategory:
    async def test_matches_category(self, db, svc):
        tenant_id = _tid()
        fake_integrations = [
            {"id": "alpha", "name": "Alpha", "category": "CRM"},
            {"id": "beta", "name": "Beta", "category": "Communication"},
        ]
        with patch.object(svc.registry, "get_all_integrations", return_value=fake_integrations):
            results = await svc.filter_by_category(tenant_id, "CRM")
        assert [r["id"] for r in results] == ["alpha"]

    async def test_no_match(self, svc):
        fake_integrations = [{"id": "alpha", "name": "Alpha", "category": "CRM"}]
        with patch.object(svc.registry, "get_all_integrations", return_value=fake_integrations):
            results = await svc.filter_by_category(_tid(), "Finance")
        assert results == []

    async def test_enrichment(self, db, svc):
        tenant_id = _tid()
        _add_config(db, tenant_id, "alpha", enabled=False, connected_user_count=2)
        fake_integrations = [{"id": "alpha", "name": "Alpha", "category": "CRM"}]
        with patch.object(svc.registry, "get_all_integrations", return_value=fake_integrations):
            results = await svc.filter_by_category(tenant_id, "CRM")
        assert results[0]["enabled"] is False
        assert results[0]["connected_user_count"] == 2

    async def test_invalid_tenant(self, svc):
        with pytest.raises(ValueError):
            await svc.filter_by_category("nope", "CRM")

    async def test_get_categories_sorted_dedup(self, svc):
        fake = [
            {"id": "a", "name": "A", "category": "CRM"},
            {"id": "b", "name": "B", "category": "Communication"},
            {"id": "c", "name": "C", "category": "CRM"},
        ]
        with patch.object(svc.registry, "get_all_integrations", return_value=fake):
            assert await svc.get_categories() == ["CRM", "Communication"]

    async def test_get_categories_skips_missing(self, svc):
        fake = [{"id": "a", "name": "A"}, {"id": "b", "name": "B", "category": "HR"}]
        with patch.object(svc.registry, "get_all_integrations", return_value=fake):
            assert await svc.get_categories() == ["HR"]

    async def test_get_categories_empty(self, svc):
        with patch.object(svc.registry, "get_all_integrations", return_value=[]):
            assert await svc.get_categories() == []


# ============================================================================
# get_integration_config
# ============================================================================

class TestGetIntegrationConfig:
    async def test_returns_full_config(self, db, svc):
        tenant_id = _tid()
        _add_config(db, tenant_id, "slack", enabled=True,
                    sync_settings={"frequency_hours": 24}, connected_user_count=7,
                    last_activity_at="2026-08-01T10:00:00Z",
                    last_sync_at="2026-08-02T11:00:00Z")
        config = await svc.get_integration_config(tenant_id, "slack")
        assert config["id"] == "slack"
        assert config["enabled"] is True
        assert config["sync_settings"] == {"frequency_hours": 24}
        assert config["connected_user_count"] == 7
        assert config["last_activity_at"] == "2026-08-01T10:00:00Z"
        assert config["last_sync_at"] == "2026-08-02T11:00:00Z"

    async def test_no_config_row_defaults(self, svc):
        config = await svc.get_integration_config(_tid(), "slack")
        assert config["enabled"] is True
        assert config["sync_settings"] == {}
        assert config["connected_user_count"] == 0
        assert config["last_activity_at"] is None
        assert config["last_sync_at"] is None

    async def test_unknown_integration_returns_none(self, svc):
        assert await svc.get_integration_config(_tid(), "no_such_integration_xyz") is None

    async def test_invalid_tenant(self, svc):
        with pytest.raises(ValueError):
            await svc.get_integration_config("bad", "slack")


# ============================================================================
# update_integration_config
# ============================================================================

class TestUpdateIntegrationConfig:
    async def test_enabled_only(self, db, svc):
        tenant_id = _tid()
        _add_config(db, tenant_id, "slack", enabled=True)
        result = await svc.update_integration_config(tenant_id, "slack", enabled=False)
        assert result["enabled"] is False

    async def test_sync_settings_only(self, db, svc):
        tenant_id = _tid()
        _add_config(db, tenant_id, "slack", enabled=True)
        result = await svc.update_integration_config(
            tenant_id, "slack", sync_settings={"frequency_hours": 12})
        assert result["sync_settings"] == {"frequency_hours": 12}
        assert result["enabled"] is True

    async def test_both(self, db, svc):
        tenant_id = _tid()
        result = await svc.update_integration_config(
            tenant_id, "slack", enabled=True,
            sync_settings={"frequency_hours": 6, "data_limit_mb": 100})
        assert result["enabled"] is True
        assert result["sync_settings"] == {"frequency_hours": 6, "data_limit_mb": 100}

    async def test_invalid_tenant(self, svc):
        with pytest.raises(ValueError):
            await svc.update_integration_config("bad", "slack", enabled=True)

    async def test_invalid_sync_settings_frequency_non_int(self, svc):
        with pytest.raises(ValueError, match="frequency_hours"):
            await svc.update_integration_config(_tid(), "slack",
                                          sync_settings={"frequency_hours": "24"})

    async def test_invalid_sync_settings_frequency_too_small(self, svc):
        with pytest.raises(ValueError, match="frequency_hours"):
            await svc.update_integration_config(_tid(), "slack",
                                          sync_settings={"frequency_hours": 0})

    async def test_invalid_sync_settings_frequency_too_big(self, svc):
        with pytest.raises(ValueError, match="frequency_hours"):
            await svc.update_integration_config(_tid(), "slack",
                                          sync_settings={"frequency_hours": 169})

    async def test_invalid_sync_settings_limit_non_int(self, svc):
        with pytest.raises(ValueError, match="data_limit_mb"):
            await svc.update_integration_config(_tid(), "slack",
                                          sync_settings={"data_limit_mb": 1.5})

    async def test_invalid_sync_settings_limit_range(self, svc):
        with pytest.raises(ValueError, match="data_limit_mb"):
            await svc.update_integration_config(_tid(), "slack",
                                          sync_settings={"data_limit_mb": 10001})

    async def test_invalid_sync_settings_entity_types_not_list(self, svc):
        with pytest.raises(ValueError, match="entity_types"):
            await svc.update_integration_config(_tid(), "slack",
                                          sync_settings={"entity_types": "contact"})

    async def test_invalid_sync_settings_entity_types_non_string(self, svc):
        with pytest.raises(ValueError, match="entity_types"):
            await svc.update_integration_config(_tid(), "slack",
                                          sync_settings={"entity_types": ["contact", 42]})


# ============================================================================
# _validate_sync_settings (unit)
# ============================================================================

class TestValidateSyncSettings:
    def test_empty_ok(self, svc):
        svc._validate_sync_settings({})

    def test_valid_all_fields(self, svc):
        svc._validate_sync_settings({
            "frequency_hours": 24,
            "data_limit_mb": 500,
            "entity_types": ["contact", "deal"],
        })


# ============================================================================
# IntegrationRegistry tenant-config methods (bug-fix regression)
# ============================================================================

class TestRegistryTenantConfigMethods:
    """The catalog service delegates to IntegrationRegistry; those methods
    previously did not exist (AttributeError on every catalog call)."""

    def test_get_tenant_config_none_when_missing(self, db):
        registry = IntegrationRegistry()
        assert registry.get_tenant_config(db, _tid(), "slack") is None

    def test_get_tenant_config_returns_mapped_dict(self, db):
        tenant_id = _tid()
        cfg = TenantIntegrationConfig(
            tenant_id=tenant_id,
            integration_id="slack",
            enabled=False,
            config_json={
                "sync_settings": {"frequency_hours": 24},
                "connected_user_count": 4,
                "last_activity_at": "2026-08-01T10:00:00Z",
                "last_sync_at": "2026-08-02T11:00:00Z",
            },
            schema_hash="v1",
        )
        db.add(cfg)
        db.commit()

        registry = IntegrationRegistry()
        config = registry.get_tenant_config(db, tenant_id, "slack")
        assert config["enabled"] is False
        assert config["sync_settings"] == {"frequency_hours": 24}
        assert config["connected_user_count"] == 4
        assert config["last_activity_at"] == "2026-08-01T10:00:00Z"
        assert config["last_sync_at"] == "2026-08-02T11:00:00Z"

    def test_set_tenant_enabled_updates_existing(self, db):
        tenant_id = _tid()
        _add_config(db, tenant_id, "slack", enabled=True)
        registry = IntegrationRegistry()
        registry.set_tenant_enabled(db, tenant_id, "slack", False)
        row = db.query(TenantIntegrationConfig).filter_by(
            tenant_id=tenant_id, integration_id="slack").first()
        assert row.enabled is False

    def test_set_tenant_enabled_creates_row(self, db):
        tenant_id = _tid()
        registry = IntegrationRegistry()
        registry.set_tenant_enabled(db, tenant_id, "slack", True)
        row = db.query(TenantIntegrationConfig).filter_by(
            tenant_id=tenant_id, integration_id="slack").first()
        assert row is not None
        assert row.enabled is True
        assert row.config_json == {}

    def test_update_sync_settings_updates_existing(self, db):
        tenant_id = _tid()
        _add_config(db, tenant_id, "slack", enabled=True,
                    sync_settings={"frequency_hours": 24})
        registry = IntegrationRegistry()
        registry.update_sync_settings(db, tenant_id, "slack",
                                      {"frequency_hours": 12, "data_limit_mb": 50})
        row = db.query(TenantIntegrationConfig).filter_by(
            tenant_id=tenant_id, integration_id="slack").first()
        assert row.config_json["sync_settings"] == {"frequency_hours": 12, "data_limit_mb": 50}
        assert row.enabled is True

    def test_update_sync_settings_creates_row(self, db):
        tenant_id = _tid()
        registry = IntegrationRegistry()
        registry.update_sync_settings(db, tenant_id, "slack", {"frequency_hours": 12})
        row = db.query(TenantIntegrationConfig).filter_by(
            tenant_id=tenant_id, integration_id="slack").first()
        assert row is not None
        assert row.config_json["sync_settings"] == {"frequency_hours": 12}

    async def test_end_to_end_catalog_flow(self, db, svc):
        """The previously-broken catalog → registry call chain end to end."""
        tenant_id = _tid()
        result = await svc.update_integration_config(
            tenant_id, "slack", enabled=True,
            sync_settings={"frequency_hours": 6, "data_limit_mb": 100})
        assert result["enabled"] is True
        assert result["sync_settings"] == {"frequency_hours": 6, "data_limit_mb": 100}

        results = await svc.search_integrations(tenant_id, "slack")
        slack = next(r for r in results if r["id"] == "slack")
        assert slack["enabled"] is True
        assert slack["connected_user_count"] == 0
