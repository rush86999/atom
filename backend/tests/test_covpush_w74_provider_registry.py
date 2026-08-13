# -*- coding: utf-8 -*-
"""Coverage wave 74 — core/provider_registry.py (in-memory SQLite, no network).

Covers BOTH the injected-session path and the ``db=None`` path (patched
``get_db_session`` context manager bound to the fixture engine): create/get/
list/update/delete provider, model count aggregation in list_providers
(active_only both ways), create/get_models_by_provider/search_models with every
filter (vision/tools/cache/min_quality/max_cost incl. NULL-cost rows),
get_provider_stats (found with averages + not-found), upsert_provider/
upsert_model (missing id ValueError, existing update, new create), and the
get_provider_registry singleton/passthrough.
"""
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import ModelCatalog, ProviderRegistry  # noqa: F401 (register models)
from core.provider_registry import ProviderRegistryService, get_provider_registry


@pytest.fixture()
def db():
    """In-memory SQLite session with the full schema."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def session_factory(db):
    """Context-manager factory standing in for core.database.get_db_session."""

    @contextmanager
    def _factory():
        yield db

    return _factory


@pytest.fixture()
def no_db_service(session_factory):
    """Service with db=None → routes through get_db_session."""
    with __import__("unittest.mock").mock.patch(
            "core.provider_registry.get_db_session", side_effect=session_factory):
        yield ProviderRegistryService()


def _seed_provider(db, provider_id="openai", active=True, name=None, vision=False,
                   tools=False, cache=False, quality=90.0):
    provider = ProviderRegistry(
        provider_id=provider_id,
        name=name or provider_id,
        is_active=active,
        supports_vision=vision,
        supports_tools=tools,
        supports_cache=cache,
        quality_score=quality,
    )
    db.add(provider)
    db.commit()
    return provider


def _seed_model(db, model_id, provider_id="openai", input_cost=0.001,
                output_cost=0.002):
    model = ModelCatalog(
        model_id=model_id,
        provider_id=provider_id,
        name=model_id,
        input_cost_per_token=input_cost,
        output_cost_per_token=output_cost,
    )
    db.add(model)
    db.commit()
    return model


# ============================================================================
# provider CRUD — both session paths
# ============================================================================

class TestProviderCrud:
    def test_create_provider_injected_session(self, db):
        service = ProviderRegistryService(db)
        provider = service.create_provider({"provider_id": "anthropic", "name": "Anthropic"})
        assert provider.provider_id == "anthropic"
        assert provider.is_active is True
        assert db.query(ProviderRegistry).count() == 1

    def test_create_provider_via_session_factory(self, no_db_service):
        provider = no_db_service.create_provider({"provider_id": "cohere", "name": "Cohere"})
        assert provider.provider_id == "cohere"

    def test_get_provider_found(self, db):
        _seed_provider(db)
        service = ProviderRegistryService(db)
        assert service.get_provider("openai").name == "openai"

    def test_get_provider_not_found(self, db):
        assert ProviderRegistryService(db).get_provider("nope") is None

    def test_get_provider_via_session_factory(self, no_db_service):
        no_db_service.create_provider({"provider_id": "cohere", "name": "Cohere"})
        assert no_db_service.get_provider("cohere") is not None

    def test_list_providers_active_only(self, db):
        _seed_provider(db, "p1", active=True)
        _seed_provider(db, "p2", active=False)
        _seed_model(db, "m1", provider_id="p1")
        _seed_model(db, "m2", provider_id="p1")
        _seed_model(db, "m3", provider_id="p2")
        active = ProviderRegistryService(db).list_providers(active_only=True)
        assert len(active) == 1
        assert active[0]["provider_id"] == "p1"
        assert active[0]["model_count"] == 2
        assert active[0]["is_active"] is True

    def test_list_providers_all(self, db):
        _seed_provider(db, "p1", active=True)
        _seed_provider(db, "p2", active=False)
        all_providers = ProviderRegistryService(db).list_providers(active_only=False)
        assert len(all_providers) == 2
        by_id = {p["provider_id"]: p for p in all_providers}
        assert by_id["p2"]["model_count"] == 0

    def test_list_providers_via_session_factory(self, no_db_service):
        no_db_service.create_provider({"provider_id": "cohere", "name": "Cohere"})
        providers = no_db_service.list_providers()
        assert providers[0]["provider_id"] == "cohere"

    def test_update_provider(self, db):
        _seed_provider(db, quality=50.0)
        updated = ProviderRegistryService(db).update_provider(
            "openai", {"quality_score": 99.0, "name": "Renamed"})
        assert updated.quality_score == 99.0
        assert updated.name == "Renamed"

    def test_update_provider_unknown_field_ignored(self, db):
        _seed_provider(db)
        updated = ProviderRegistryService(db).update_provider(
            "openai", {"bogus_field": 1, "name": "OK"})
        assert updated.name == "OK"

    def test_update_provider_not_found(self, db):
        assert ProviderRegistryService(db).update_provider("nope", {"name": "x"}) is None

    def test_update_provider_via_session_factory(self, no_db_service):
        no_db_service.create_provider({"provider_id": "cohere", "name": "Cohere"})
        updated = no_db_service.update_provider("cohere", {"name": "Cohere2"})
        assert updated.name == "Cohere2"

    def test_delete_provider_soft(self, db):
        _seed_provider(db)
        assert ProviderRegistryService(db).delete_provider("openai") is True
        assert db.query(ProviderRegistry).filter(
            ProviderRegistry.provider_id == "openai").first().is_active is False

    def test_delete_provider_not_found(self, db):
        assert ProviderRegistryService(db).delete_provider("nope") is False

    def test_delete_provider_via_session_factory(self, no_db_service):
        no_db_service.create_provider({"provider_id": "cohere", "name": "Cohere"})
        assert no_db_service.delete_provider("cohere") is True
        # soft delete → row still exists, so a repeat delete is still True
        assert no_db_service.delete_provider("cohere") is True


# ============================================================================
# model CRUD
# ============================================================================

class TestModelCrud:
    def test_create_model(self, db):
        _seed_provider(db)
        model = ProviderRegistryService(db).create_model(
            {"model_id": "gpt-4o", "provider_id": "openai", "name": "GPT-4o"})
        assert model.model_id == "gpt-4o"

    def test_create_model_via_session_factory(self, no_db_service):
        no_db_service.create_provider({"provider_id": "cohere", "name": "Cohere"})
        model = no_db_service.create_model(
            {"model_id": "command-r", "provider_id": "cohere", "name": "Command R"})
        assert model.model_id == "command-r"

    def test_get_models_by_provider(self, db):
        _seed_provider(db, "p1")
        _seed_provider(db, "p2")
        _seed_model(db, "a", provider_id="p1")
        _seed_model(db, "b", provider_id="p1")
        _seed_model(db, "c", provider_id="p2")
        models = ProviderRegistryService(db).get_models_by_provider("p1")
        assert {m.model_id for m in models} == {"a", "b"}

    def test_get_models_by_provider_via_session_factory(self, no_db_service):
        no_db_service.create_provider({"provider_id": "cohere", "name": "Cohere"})
        no_db_service.create_model({"model_id": "x", "provider_id": "cohere", "name": "X"})
        assert len(no_db_service.get_models_by_provider("cohere")) == 1


class TestSearchModels:
    def _seed(self, db):
        p_vision = _seed_provider(db, "pv", vision=True, tools=True, cache=True, quality=95.0)
        p_plain = _seed_provider(db, "pp", quality=40.0)
        _seed_model(db, "m-vision", provider_id="pv", input_cost=0.005)
        _seed_model(db, "m-plain", provider_id="pp", input_cost=0.5)
        db.add(ModelCatalog(model_id="m-null-cost", provider_id="pp", name="Null cost",
                            input_cost_per_token=None, output_cost_per_token=None))
        db.commit()
        return p_vision, p_plain

    def test_no_filters(self, db):
        self._seed(db)
        assert len(ProviderRegistryService(db).search_models({})) == 3

    def test_filter_vision(self, db):
        self._seed(db)
        results = ProviderRegistryService(db).search_models({"supports_vision": True})
        assert {m.model_id for m in results} == {"m-vision"}

    def test_filter_tools_and_cache(self, db):
        self._seed(db)
        tools = ProviderRegistryService(db).search_models({"supports_tools": True})
        assert {m.model_id for m in tools} == {"m-vision"}
        cache = ProviderRegistryService(db).search_models({"supports_cache": True})
        assert {m.model_id for m in cache} == {"m-vision"}

    def test_filter_min_quality(self, db):
        self._seed(db)
        results = ProviderRegistryService(db).search_models({"min_quality": 90.0})
        assert {m.model_id for m in results} == {"m-vision"}

    def test_filter_max_cost_includes_null_cost(self, db):
        self._seed(db)
        results = ProviderRegistryService(db).search_models({"max_cost": 0.01})
        ids = {m.model_id for m in results}
        assert "m-vision" in ids
        assert "m-null-cost" in ids  # NULL cost rows pass the cap filter

    def test_search_via_session_factory(self, no_db_service):
        no_db_service.create_provider({"provider_id": "cohere", "name": "Cohere",
                                       "supports_tools": True, "quality_score": 80.0})
        no_db_service.create_model({"model_id": "x", "provider_id": "cohere", "name": "X",
                                    "input_cost_per_token": 0.001})
        assert len(no_db_service.search_models({"supports_tools": True})) == 1
        assert len(no_db_service.search_models({"min_quality": 90.0})) == 0


class TestProviderStats:
    def test_stats_found(self, db):
        _seed_provider(db, quality=88.0)
        _seed_model(db, "m1", input_cost=0.001, output_cost=0.002)
        _seed_model(db, "m2", input_cost=0.003, output_cost=0.004)
        stats = ProviderRegistryService(db).get_provider_stats("openai")
        assert stats["provider_id"] == "openai"
        assert stats["model_count"] == 2
        assert stats["avg_input_cost_per_token"] == 0.002
        assert stats["avg_output_cost_per_token"] == 0.003
        assert stats["quality_score"] == 88.0

    def test_stats_not_found(self, db):
        assert ProviderRegistryService(db).get_provider_stats("nope") == {}

    def test_stats_via_session_factory(self, no_db_service):
        no_db_service.create_provider({"provider_id": "cohere", "name": "Cohere"})
        stats = no_db_service.get_provider_stats("cohere")
        assert stats["model_count"] == 0
        assert stats["name"] == "Cohere"


class TestUpsert:
    def test_upsert_provider_requires_id(self, db):
        with pytest.raises(ValueError, match="provider_id is required"):
            ProviderRegistryService(db).upsert_provider({"name": "x"})

    def test_upsert_provider_creates(self, db):
        provider = ProviderRegistryService(db).upsert_provider(
            {"provider_id": "new", "name": "New"})
        assert provider.provider_id == "new"
        assert db.query(ProviderRegistry).count() == 1

    def test_upsert_provider_updates(self, db):
        _seed_provider(db, name="Old")
        updated = ProviderRegistryService(db).upsert_provider(
            {"provider_id": "openai", "name": "New", "quality_score": 77.0})
        assert updated.name == "New"
        assert updated.quality_score == 77.0
        assert db.query(ProviderRegistry).count() == 1

    def test_upsert_provider_via_session_factory(self, no_db_service):
        assert no_db_service.upsert_provider({"provider_id": "c", "name": "C"}).provider_id == "c"
        assert no_db_service.upsert_provider({"provider_id": "c", "name": "C2"}).name == "C2"

    def test_upsert_model_requires_id(self, db):
        with pytest.raises(ValueError, match="model_id is required"):
            ProviderRegistryService(db).upsert_model({"provider_id": "openai"})

    def test_upsert_model_creates(self, db):
        _seed_provider(db)
        model = ProviderRegistryService(db).upsert_model(
            {"model_id": "m1", "provider_id": "openai", "name": "M1"})
        assert model.model_id == "m1"

    def test_upsert_model_updates(self, db):
        _seed_provider(db)
        _seed_model(db, "m1")
        updated = ProviderRegistryService(db).upsert_model(
            {"model_id": "m1", "provider_id": "openai", "name": "Renamed"})
        assert updated.name == "Renamed"
        assert db.query(ModelCatalog).count() == 1

    def test_upsert_model_via_session_factory(self, no_db_service):
        no_db_service.create_provider({"provider_id": "cohere", "name": "Cohere"})
        no_db_service.upsert_model({"model_id": "x", "provider_id": "cohere", "name": "X"})
        assert no_db_service.upsert_model(
            {"model_id": "x", "provider_id": "cohere", "name": "X2"}).name == "X2"


class TestSingleton:
    def test_singleton_no_session(self):
        a = get_provider_registry()
        b = get_provider_registry()
        assert a is b
        assert a.db is None

    def test_passthrough_with_session(self, db):
        svc = get_provider_registry(db)
        assert svc.db is db

    def test_new_instance_with_session(self, db):
        first = get_provider_registry()
        with_session = get_provider_registry(db)
        assert with_session is not first
        assert with_session.db is db
