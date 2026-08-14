"""
Tests for the LLM Registry services.

The former /api/llm-registry/* router (api/llm_registry_routes.py) was deleted
as dead code (no frontend consumer, no backend importer), so these tests were
ported onto the surviving service layer with the same intent:

- Provider health monitoring -> core.llm.registry.provider_health.ProviderHealthService
- Model quality filtering  -> core.llm.registry.queries.get_models_by_quality_range

The pre-existing permanently-skipped endpoint tests (search/sync/providers
list) were removed together with the module they targeted; they asserted
nothing while skipped.
"""

import json
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import core.llm.registry.models  # noqa: F401  (registers LLMModel on Base)
from core.database import Base
from core.llm.registry.models import LLMModel
from core.llm.registry.provider_health import ProviderHealthService
from core.llm.registry.queries import get_models_by_quality_range


# ============================================================================
# Fixtures
# ============================================================================

class FakeCache:
    """In-memory stand-in for UniversalCacheService."""

    def __init__(self):
        self.store = {}

    async def get_async(self, key):
        return self.store.get(key)

    async def set_async(self, key, value, ttl=None):
        self.store[key] = value


@pytest.fixture
def fake_cache():
    return FakeCache()


@pytest.fixture
def provider_health_service(fake_cache):
    return ProviderHealthService(cache_service=fake_cache)


def _seed_health(cache, provider, **metrics):
    cache.store[f"llm_registry:provider_health:{provider}"] = json.dumps({
        "current_state": metrics.get("state", "healthy"),
        "success_count": metrics.get("success_count", 0),
        "error_count": metrics.get("error_count", 0),
        "consecutive_failures": metrics.get("consecutive_failures", 0),
        "consecutive_successes": metrics.get("consecutive_successes", 0),
        "last_success_ts": metrics.get("last_success_ts"),
        "last_error_ts": metrics.get("last_error_ts"),
        "avg_latency_ms": metrics.get("avg_latency_ms"),
    })


@pytest.fixture
def registry_db():
    """Dedicated in-memory session with the llm_models table created."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[LLMModel.__table__])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def seed_models(registry_db):
    """Seed a small model catalog spanning quality tiers."""
    catalog = [
        ("gpt-4o", "openai", 95.5, ["tools", "vision", "json_mode"]),
        ("gpt-4o-mini", "openai", 82.0, ["tools", "json_mode"]),
        ("claude-3-5-sonnet", "anthropic", 94.0, ["tools", "vision", "json_mode"]),
        ("deepseek-chat", "deepseek", 88.5, ["tools", "json_mode"]),
        ("gemini-1-5-pro", "google", 91.0, ["tools", "vision", "video"]),
        ("legacy-model", "openai", 99.0, ["tools"]),  # deprecated -> excluded
    ]
    for model_name, provider, quality, caps in catalog:
        registry_db.add(LLMModel(
            id=str(uuid.uuid4()),  # str: UUID column round-trips as CHAR on SQLite
            tenant_id="default",
            provider=provider,
            model_name=model_name,
            quality_score=quality,
            capabilities=caps,
            is_deprecated=(model_name == "legacy-model"),
        ))
    registry_db.commit()
    return catalog


# ============================================================================
# Provider Health
# ============================================================================

class TestProviderHealth:
    """Tests for ProviderHealthService.get_all_health (provider health)."""

    @pytest.mark.asyncio
    async def test_get_provider_health_all(self, provider_health_service, fake_cache):
        """Test getting health for all default providers."""
        _seed_health(fake_cache, "openai", success_count=1234, error_count=12,
                     avg_latency_ms=245.5)
        _seed_health(fake_cache, "anthropic", success_count=890, error_count=5,
                     avg_latency_ms=312.3)
        _seed_health(fake_cache, "google", state="degraded", success_count=500,
                     error_count=50, consecutive_failures=2, avg_latency_ms=450.0)
        _seed_health(fake_cache, "deepseek", success_count=2000, error_count=10,
                     avg_latency_ms=180.2)

        default_providers = ['openai', 'anthropic', 'google', 'meta',
                             'mistral', 'cohere', 'deepseek']
        health = await provider_health_service.get_all_health(default_providers)

        assert len(health) >= 4  # At least the seeded providers

        openai_health = health["openai"]
        assert openai_health["state"] == "healthy"
        assert openai_health["success_count"] == 1234
        assert "avg_latency_ms" in openai_health

        # Degraded provider is surfaced with its state
        assert health["google"]["state"] == "degraded"

    @pytest.mark.asyncio
    async def test_get_provider_health_specific(self, provider_health_service, fake_cache):
        """Test getting health for specific providers only."""
        _seed_health(fake_cache, "openai", success_count=100, error_count=12,
                     avg_latency_ms=245.5)
        _seed_health(fake_cache, "anthropic", success_count=200, error_count=5,
                     avg_latency_ms=312.3)

        health = await provider_health_service.get_all_health(["openai", "anthropic"])

        assert len(health) == 2
        assert "openai" in health
        assert "anthropic" in health

    @pytest.mark.asyncio
    async def test_get_provider_health_single(self, provider_health_service, fake_cache):
        """Test getting health for a single provider."""
        _seed_health(fake_cache, "deepseek", success_count=150, error_count=10,
                     avg_latency_ms=180.2)

        health = await provider_health_service.get_all_health(["deepseek"])

        assert len(health) == 1
        assert "deepseek" in health
        assert health["deepseek"]["state"] == "healthy"


# ============================================================================
# Model quality filtering
# ============================================================================

class TestModelsByQuality:
    """Tests for get_models_by_quality_range (model quality filtering)."""

    def test_get_models_by_quality_range(self, registry_db, seed_models):
        """Test filtering models by quality score range."""
        models = get_models_by_quality_range(
            registry_db, tenant_id="default",
            min_quality=80.0, max_quality=100.0, limit=10
        )

        assert 1 <= len(models) <= 10
        assert all(80.0 <= float(m.quality_score) <= 100.0 for m in models)
        # Sorted by quality_score DESC
        scores = [float(m.quality_score) for m in models]
        assert scores == sorted(scores, reverse=True)
        # Deprecated models are excluded
        assert all(m.model_name != "legacy-model" for m in models)

    def test_get_models_by_quality_with_capabilities(self, registry_db, seed_models):
        """Test filtering by quality then narrowing by capabilities."""
        models = get_models_by_quality_range(
            registry_db, tenant_id="default",
            min_quality=80, max_quality=100
        )

        # Capability narrowing (the deleted route performed this client-side)
        required = ["tools", "vision"]
        filtered = [m for m in models if all(c in (m.capabilities or []) for c in required)]

        assert len(filtered) >= 1
        for m in filtered:
            assert "tools" in m.capabilities
            assert "vision" in m.capabilities

    def test_get_models_by_quality_narrow_range(self, registry_db, seed_models):
        """Test filtering with a narrow quality range."""
        models = get_models_by_quality_range(
            registry_db, tenant_id="default",
            min_quality=93, max_quality=96
        )

        assert len(models) >= 1
        assert all(93 <= float(m.quality_score) <= 96 for m in models)
        # gpt-4o (95.5) and claude-3-5-sonnet (94.0) fall in range; the
        # deprecated 99.0 model must not leak in even though it is high.
        names = {m.model_name for m in models}
        assert "gpt-4o" in names
        assert "legacy-model" not in names
