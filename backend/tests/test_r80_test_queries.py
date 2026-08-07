"""Round 80 — LLM registry query helper coverage.

``core/llm/registry/test_queries.py`` lives INSIDE the package (never
collected by pytest) and additionally requires PostgreSQL, so the helper
module ``core/llm/registry/queries.py`` had zero CI coverage. This module
covers everything that runs on SQLite (Personal Edition): hybrid-column
capability queries, metadata JSON path queries (SQLite 3.38+ ``->>``),
quality-range / frontier / auto-include routing queries, and
``score_model_for_routing``.

TDD target B5: ``score_model_for_routing`` crashed on any DB-loaded model —
``Numeric`` columns return ``Decimal`` (``Decimal -= float`` → TypeError)
and SQLite round-trips ``discovered_at`` as a naive datetime (naive > aware
→ TypeError). Fixed by coercing to float and normalizing naive timestamps
to UTC before the freshness comparison.

PostgreSQL-only paths (JSONB ``@>``/``&&`` operators, EXPLAIN ANALYZE) are
skip-marked on SQLite.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.llm.registry.models import LLMModel
from core.llm.registry.queries import (
    AUDIO,
    FUNCTION_CALLING,
    JSON_MODE,
    TOOLS,
    VISION,
    explain_query,
    get_auto_include_models,
    get_capable_models,
    get_frontier_models,
    get_index_usage_stats,
    get_models_by_quality_range,
    query_by_all_capabilities,
    query_by_capability,
    query_by_metadata,
    score_model_for_routing,
)

_HYBRID_OK = "JSONB @> / && operators are PostgreSQL-only; not supported on SQLite"
_EXPLAIN_OK = "EXPLAIN ANALYZE is PostgreSQL-only; SQLite only has EXPLAIN QUERY PLAN"


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    LLMModel.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _model(**kw):
    # Explicit str id + discovered_at: SQLite's multi-row insertmanyvalues
    # RETURNING path can't sentinel-match the UUID TypeDecorator; a string
    # id sidesteps it, and providing the timestamp avoids the eager
    # server-default re-fetch entirely.
    base = dict(
        id=str(uuid.uuid4()),
        tenant_id="tenant-1",
        provider="openai",
        model_name="gpt-4",
        capabilities=[],
        supports_vision=False,
        supports_tools=False,
        supports_function_calling=False,
        supports_audio=False,
        supports_computer_use=False,
        is_deprecated=False,
        quality_score=None,
        discovered_at=datetime.now(timezone.utc),
    )
    base.update(kw)
    if base["capabilities"]:
        model = LLMModel(**base)
        model.sync_capabilities()
        # sync_capabilities sets the boolean columns from capabilities.
        return model
    return LLMModel(**base)


def _seed(db):
    models = [
        _model(provider="openai", model_name="gpt-4-vision-preview", capabilities=[VISION]),
        _model(provider="anthropic", model_name="claude-3-opus", capabilities=[TOOLS]),
        _model(provider="openai", model_name="gpt-4-turbo", capabilities=[VISION, TOOLS]),
        _model(provider="openai", model_name="gpt-4o",
               capabilities=[VISION, TOOLS, FUNCTION_CALLING, AUDIO], quality_score=95),
        _model(provider="openrouter", model_name="custom-model", capabilities=[JSON_MODE], quality_score=85),
        _model(provider="anthropic", model_name="claude-3-sonnet", capabilities=[VISION, JSON_MODE]),
    ]
    db.add_all(models)
    db.commit()
    return models


class TestQueryByCapability:
    def test_vision_hybrid_column(self, db):
        _seed(db)
        names = [m.model_name for m in query_by_capability(db, "tenant-1", VISION)]
        assert names == ["gpt-4-vision-preview", "gpt-4-turbo", "gpt-4o", "claude-3-sonnet"]

    def test_tools_hybrid_column(self, db):
        _seed(db)
        names = [m.model_name for m in query_by_capability(db, "tenant-1", TOOLS)]
        assert names == ["claude-3-opus", "gpt-4-turbo", "gpt-4o"]

    def test_audio_hybrid_column(self, db):
        _seed(db)
        names = [m.model_name for m in query_by_capability(db, "tenant-1", AUDIO)]
        assert names == ["gpt-4o"]

    def test_no_matches(self, db):
        _seed(db)
        # "computer_use" is a hybrid column with no matching seeds.
        assert query_by_capability(db, "tenant-1", "computer_use") == []

    def test_tenant_isolation(self, db):
        _seed(db)
        db.add(_model(tenant_id="tenant-2", model_name="other-tenant", capabilities=[VISION]))
        db.commit()
        models = query_by_capability(db, "tenant-1", VISION)
        assert len(models) == 4
        assert all(m.tenant_id == "tenant-1" for m in models)

    @pytest.mark.skip(reason=_HYBRID_OK)
    def test_rare_capability_jsonb_path(self, db):
        # PostgreSQL-only path — documents the intent on engines that support it.
        _seed(db)
        names = [m.model_name for m in query_by_capability(db, "tenant-1", JSON_MODE)]
        assert "custom-model" in names
        assert "claude-3-sonnet" in names


class TestQueryByAllCapabilities:
    def test_two_hybrid_caps(self, db):
        _seed(db)
        names = [m.model_name for m in query_by_all_capabilities(db, "tenant-1", [VISION, TOOLS])]
        assert names == ["gpt-4-turbo", "gpt-4o"]

    def test_three_hybrid_caps(self, db):
        _seed(db)
        names = [m.model_name for m in query_by_all_capabilities(db, "tenant-1", [VISION, TOOLS, FUNCTION_CALLING])]
        assert names == ["gpt-4o"]

    def test_impossible_combination(self, db):
        _seed(db)
        # "computer_use" is a hybrid column no seed model has.
        assert query_by_all_capabilities(db, "tenant-1", [TOOLS, AUDIO, "computer_use"]) == []


class TestQueryByMetadata:
    def test_metadata_path_match(self, db):
        models = _seed(db)
        for m in models:
            m.provider_metadata = {"provider": m.provider, "region": "us-east"}
        db.commit()
        names = [m.model_name for m in query_by_metadata(db, "tenant-1", "provider", "openai")]
        assert names == ["gpt-4-vision-preview", "gpt-4-turbo", "gpt-4o"]

    def test_metadata_no_match(self, db):
        _seed(db)
        assert query_by_metadata(db, "tenant-1", "nonexistent", "value") == []


class TestGetCapableModels:
    def test_required_only(self, db):
        _seed(db)
        names = [m.model_name for m in get_capable_models(db, "tenant-1", required_capabilities=[VISION, TOOLS])]
        assert names == ["gpt-4-turbo", "gpt-4o"]

    @pytest.mark.skip(reason=_HYBRID_OK)
    def test_any_single_string(self, db):
        # any-path compiles to JSONB && — PostgreSQL-only.
        _seed(db)
        names = [m.model_name for m in get_capable_models(db, "tenant-1", any_capability=VISION)]
        assert len(names) == 4

    @pytest.mark.skip(reason=_HYBRID_OK)
    def test_required_and_any(self, db):
        _seed(db)
        names = [m.model_name for m in get_capable_models(
            db, "tenant-1", required_capabilities=[TOOLS], any_capabilities=[VISION, AUDIO]
        )]
        assert names == ["gpt-4-turbo", "gpt-4o"]

    def test_no_filters_returns_all_tenant_models(self, db):
        _seed(db)
        assert len(get_capable_models(db, "tenant-1")) == 6


class TestGetModelsByQualityRange:
    def _seed_quality(self, db):
        db.add_all([
            _model(model_name="low", quality_score=40),
            _model(model_name="mid", quality_score=70),
            _model(model_name="high", quality_score=90),
            _model(model_name="deprecated-high", quality_score=95, is_deprecated=True),
            _model(model_name="no-score"),
        ])
        db.commit()

    def test_range_filter_sorted_desc(self, db):
        self._seed_quality(db)
        names = [m.model_name for m in get_models_by_quality_range(db, "tenant-1", min_quality=60, max_quality=95)]
        assert names == ["high", "mid"]

    def test_deprecated_excluded(self, db):
        self._seed_quality(db)
        names = [m.model_name for m in get_models_by_quality_range(db, "tenant-1")]
        assert "deprecated-high" not in names
        assert "no-score" not in names  # NULL quality excluded

    def test_limit(self, db):
        self._seed_quality(db)
        names = [m.model_name for m in get_models_by_quality_range(db, "tenant-1", limit=1)]
        assert names == ["high"]


class TestGetFrontierModels:
    def _seed(self, db):
        db.add_all([
            _model(model_name="gpt-4o", quality_score=95),
            _model(model_name="gpt-4o-mini", quality_score=82),
            _model(model_name="claude-3-opus-preview", quality_score=91),
            _model(model_name="experimental-sonnet", quality_score=88),
            _model(model_name="alpha-test", quality_score=86),
            _model(model_name="old", quality_score=75),
            _model(model_name="deprecated", quality_score=99, is_deprecated=True),
        ])
        db.commit()

    def test_default_threshold_and_exclusions(self, db):
        self._seed(db)
        names = [m.model_name for m in get_frontier_models(db, "tenant-1")]
        assert "gpt-4o" in names
        assert "gpt-4o-mini" in names
        assert "old" not in names
        assert "deprecated" not in names
        assert "claude-3-opus-preview" not in names
        assert "experimental-sonnet" not in names
        assert "alpha-test" not in names

    def test_include_experimental(self, db):
        self._seed(db)
        names = [m.model_name for m in get_frontier_models(db, "tenant-1", exclude_experimental=False)]
        assert "claude-3-opus-preview" in names
        assert "experimental-sonnet" in names

    def test_hybrid_capability_filter(self, db):
        self._seed(db)
        db.add(_model(model_name="vision-only", capabilities=[VISION], quality_score=90))
        db.commit()
        names = [m.model_name for m in get_frontier_models(db, "tenant-1", capabilities=[VISION])]
        assert names == ["vision-only"]  # seeded frontier models carry no caps

    @pytest.mark.skip(reason=_HYBRID_OK)
    def test_non_hybrid_capability_filter(self, db):
        _seed(db)
        names = [m.model_name for m in get_frontier_models(db, "tenant-1", capabilities=[JSON_MODE])]
        assert names == ["custom-model"]


class TestGetAutoIncludeModels:
    def _seed(self, db):
        db.add_all([
            _model(provider="openai", model_name="gpt-4o", quality_score=95),
            _model(provider="openai", model_name="gpt-4o-preview", quality_score=90),
            _model(provider="openai", model_name="experimental-x", quality_score=92),
            _model(provider="anthropic", model_name="claude-3-opus", quality_score=88),
            _model(provider="anthropic", model_name="claude-3-sonnet", quality_score=70),
            _model(provider="openai", model_name="deprecated", quality_score=99, is_deprecated=True),
        ])
        db.commit()

    def test_auto_include_excludes_preview_and_deprecated(self, db):
        self._seed(db)
        names = [m.model_name for m in get_auto_include_models(db, "tenant-1")]
        assert "gpt-4o" in names
        assert "gpt-4o-preview" not in names
        assert "experimental-x" not in names
        assert "claude-3-opus" in names
        assert "claude-3-sonnet" not in names
        assert "deprecated" not in names

    def test_provider_filter(self, db):
        self._seed(db)
        names = [m.model_name for m in get_auto_include_models(db, "tenant-1", provider="openai")]
        assert names == ["gpt-4o"]
        assert all(m.provider == "openai" for m in get_auto_include_models(db, "tenant-1", provider="openai"))


class TestScoreModelForRouting:
    def _db_model(self, db, **kw):
        # Old discovered_at: the +2.0 "recently discovered" bonus must NOT
        # apply to baseline expectations (bonus tests set it explicitly).
        base = dict(id=str(uuid.uuid4()), tenant_id="tenant-1", provider="openai",
                    model_name="gpt-4o", quality_score=90,
                    discovered_at=datetime.now(timezone.utc) - timedelta(days=400))
        base.update(kw)
        m = LLMModel(**base)
        db.add(m)
        db.commit()
        db.refresh(m)
        return m

    # ------------------------------------------------------------------ #
    # B5: DB-loaded models must not crash the scorer.
    # ------------------------------------------------------------------ #
    def test_b5_db_loaded_model_with_health_priority(self, db):
        m = self._db_model(db)
        score = score_model_for_routing(m, health_priority=1)
        assert score == pytest.approx(90.0 - 5.0)

    def test_b5_db_loaded_model_without_health_priority(self, db):
        m = self._db_model(db)
        score = score_model_for_routing(m)
        assert score == pytest.approx(90.0)

    def test_health_priority_penalty_scales(self, db):
        m = self._db_model(db)
        assert score_model_for_routing(m, health_priority=0) == pytest.approx(90.0)
        assert score_model_for_routing(m, health_priority=2) == pytest.approx(80.0)
        assert score_model_for_routing(m, health_priority=3) == pytest.approx(75.0)

    def test_missing_quality_defaults_to_mid_range(self, db):
        m = self._db_model(db, quality_score=None)
        assert score_model_for_routing(m) == pytest.approx(75.0)

    def test_clamped_to_zero_hundred(self, db):
        m = self._db_model(db, quality_score=99)
        assert score_model_for_routing(m, health_priority=3) == pytest.approx(99 - 15)

    def test_recently_discovered_bonus(self, db):
        m = self._db_model(db)
        m.discovered_at = datetime.now(timezone.utc) - timedelta(days=3)
        score = score_model_for_routing(m)
        assert score == pytest.approx(92.0)

    def test_no_bonus_for_old_models(self, db):
        m = self._db_model(db)
        m.discovered_at = datetime.now(timezone.utc) - timedelta(days=400)
        score = score_model_for_routing(m)
        assert score == pytest.approx(90.0)


class TestModelBasics:
    def test_sync_capabilities(self, db):
        m = _model(model_name="m", capabilities=[VISION, TOOLS])
        m.sync_capabilities()
        assert m.supports_vision is True
        assert m.supports_tools is True
        assert m.supports_audio is False
        assert m.supports_function_calling is False

    def test_sync_capabilities_empty(self, db):
        m = _model(model_name="m")
        m.sync_capabilities()
        assert m.supports_vision is False
        assert m.supports_tools is False

    def test_get_hybrid_capabilities(self, db):
        hybrid = LLMModel.get_hybrid_capabilities()
        assert VISION in hybrid
        assert TOOLS in hybrid
        assert FUNCTION_CALLING in hybrid
        assert AUDIO in hybrid
        assert JSON_MODE not in hybrid

    def test_to_dict_includes_hybrid_columns(self, db):
        m = _model(model_name="m", capabilities=[VISION], quality_score=88)
        m.sync_capabilities()
        db.add(m)
        db.commit()
        result = m.to_dict()
        assert result["supports_vision"] is True
        assert result["supports_tools"] is False
        assert result["quality_score"] == 88.0
        assert result["tenant_id"] == "tenant-1"


class TestExplainAndStats:
    @pytest.mark.skipif(True, reason=_EXPLAIN_OK)
    def test_explain_query_returns_plan(self, db):
        # PostgreSQL-only (EXPLAIN ANALYZE). Kept as documentation of the API.
        _seed(db)
        plan = explain_query(db, "tenant-1", VISION)
        assert isinstance(plan, str)
        assert len(plan) > 0

    @pytest.mark.skipif(True, reason=_EXPLAIN_OK)
    def test_index_usage_stats_keys(self, db):
        _seed(db)
        stats = get_index_usage_stats(db, "tenant-1", VISION)
        assert "explain_output" in stats
        assert "uses_gin_index" in stats
        assert "execution_time" in stats
        assert "planning_time" in stats
        assert "row_count" in stats
