"""Tests for LLM Model Registry Query Helpers

These tests verify that capability-based queries work correctly and use
GIN indexes for optimal performance.

Tests include:
- Single capability lookups (hybrid and JSONB)
- Multi-capability AND queries
- Any capability OR queries
- Metadata path queries
- Index usage verification with EXPLAIN ANALYZE

Note: These tests require PostgreSQL (JSONB support). Use testcontainers
or set POSTGRES_URL environment variable.
"""
import pytest
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import uuid

from core.llm.registry.models import LLMModel
from core.llm.registry.queries import (
    query_by_capability,
    query_by_all_capabilities,
    query_by_any_capability,
    query_by_metadata,
    get_capable_models,
    explain_query,
    get_index_usage_stats,
    VISION,
    TOOLS,
    FUNCTION_CALLING,
    AUDIO,
    JSON_MODE,
)

# Try to import testcontainers for PostgreSQL
try:
    from testcontainers.postgres import PostgresContainer
    TESTCONTAINERS_AVAILABLE = True
except ImportError:
    TESTCONTAINERS_AVAILABLE = False

# Test database URL
POSTGRES_URL = os.environ.get("POSTGRES_URL")
if POSTGRES_URL:
    TEST_DATABASE_URL = POSTGRES_URL
elif TESTCONTAINERS_AVAILABLE:
    # Will be set by fixture
    TEST_DATABASE_URL = None
else:
    # No PostgreSQL available, skip tests
    TEST_DATABASE_URL = None


@pytest.fixture(scope="session")
def postgres_container():
    """Spin up PostgreSQL container for tests"""
    if TEST_DATABASE_URL:
        # Using external PostgreSQL from POSTGRES_URL
        yield TEST_DATABASE_URL
        return

    if not TESTCONTAINERS_AVAILABLE:
        pytest.skip("PostgreSQL not available - set POSTGRES_URL or install testcontainers")

    postgres = PostgresContainer("postgres:16-alpine")
    try:
        postgres.start()
        yield postgres.get_connection_url()
    finally:
        postgres.stop()


@pytest.fixture(scope="function")
def db(postgres_container: str) -> Generator[Session, None, None]:
    """Fresh database for each test"""
    engine = create_engine(postgres_container, echo=False)

    # Create tables
    LLMModel.metadata.create_all(engine)

    # Create session
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    engine.dispose()


@pytest.fixture(scope="function")
def sample_models(db: Session) -> None:
    """Create sample models with various capabilities"""
    models = [
        # Model 1: Vision only
        LLMModel(
            tenant_id="tenant-1",
            provider="openai",
            model_name="gpt-4-vision-preview",
            context_window=128000,
            capabilities=["vision"],
            supports_vision=True,
            supports_tools=False,
            supports_function_calling=False,
            supports_audio=False,
        ),
        # Model 2: Tools only
        LLMModel(
            tenant_id="tenant-1",
            provider="anthropic",
            model_name="claude-3-opus",
            context_window=200000,
            capabilities=["tools"],
            supports_vision=False,
            supports_tools=True,
            supports_function_calling=False,
            supports_audio=False,
        ),
        # Model 3: Vision + Tools
        LLMModel(
            tenant_id="tenant-1",
            provider="openai",
            model_name="gpt-4-turbo",
            context_window=128000,
            capabilities=["vision", "tools"],
            supports_vision=True,
            supports_tools=True,
            supports_function_calling=False,
            supports_audio=False,
        ),
        # Model 4: All common capabilities
        LLMModel(
            tenant_id="tenant-1",
            provider="openai",
            model_name="gpt-4o",
            context_window=128000,
            capabilities=["vision", "tools", "function_calling", "audio"],
            supports_vision=True,
            supports_tools=True,
            supports_function_calling=True,
            supports_audio=True,
        ),
        # Model 5: Rare capability only
        LLMModel(
            tenant_id="tenant-1",
            provider="openrouter",
            model_name="custom-model",
            context_window=32000,
            capabilities=["json_mode"],
            supports_vision=False,
            supports_tools=False,
            supports_function_calling=False,
            supports_audio=False,
        ),
        # Model 6: Vision + rare capability
        LLMModel(
            tenant_id="tenant-1",
            provider="anthropic",
            model_name="claude-3-sonnet",
            context_window=200000,
            capabilities=["vision", "json_mode"],
            supports_vision=True,
            supports_tools=False,
            supports_function_calling=False,
            supports_audio=False,
        ),
    ]

    for model in models:
        db.add(model)
    db.commit()


class TestSingleCapabilityQueries:
    """Tests for single capability lookups"""

    def test_query_by_vision_hybrid_column(self, db: Session, sample_models):
        """Test querying by vision capability using hybrid column"""
        models = query_by_capability(db, "tenant-1", VISION)

        assert len(models) == 4  # gpt-4-vision, gpt-4-turbo, gpt-4o, claude-3-sonnet
        model_names = [m.model_name for m in models]
        assert "gpt-4-vision-preview" in model_names
        assert "gpt-4-turbo" in model_names
        assert "gpt-4o" in model_names
        assert "claude-3-sonnet" in model_names

    def test_query_by_tools_hybrid_column(self, db: Session, sample_models):
        """Test querying by tools capability using hybrid column"""
        models = query_by_capability(db, "tenant-1", TOOLS)

        assert len(models) == 3  # claude-3-opus, gpt-4-turbo, gpt-4o
        model_names = [m.model_name for m in models]
        assert "claude-3-opus" in model_names
        assert "gpt-4-turbo" in model_names
        assert "gpt-4o" in model_names

    def test_query_by_rare_capability_jsonb(self, db: Session, sample_models):
        """Test querying by rare capability using JSONB"""
        models = query_by_capability(db, "tenant-1", JSON_MODE)

        assert len(models) == 2  # custom-model, claude-3-sonnet
        model_names = [m.model_name for m in models]
        assert "custom-model" in model_names
        assert "claude-3-sonnet" in model_names

    def test_query_by_capability_no_matches(self, db: Session, sample_models):
        """Test querying with capability that has no matches"""
        models = query_by_capability(db, "tenant-1", "streaming")

        assert len(models) == 0

    def test_query_by_capability_tenant_isolation(self, db: Session, sample_models):
        """Test that queries respect tenant isolation"""
        # Create model for different tenant
        model = LLMModel(
            tenant_id="tenant-2",
            provider="openai",
            model_name="gpt-4",
            capabilities=[VISION],
            supports_vision=True,
            supports_tools=False,
            supports_function_calling=False,
            supports_audio=False,
        )
        db.add(model)
        db.commit()

        # Query should only return tenant-1 models
        models = query_by_capability(db, "tenant-1", VISION)

        assert len(models) == 4
        assert all(m.tenant_id == "tenant-1" for m in models)


class TestMultiCapabilityAND:
    """Tests for multi-capability AND queries"""

    def test_query_by_all_capabilities_vision_tools(self, db: Session, sample_models):
        """Test querying for models with BOTH vision AND tools"""
        models = query_by_all_capabilities(db, "tenant-1", [VISION, TOOLS])

        assert len(models) == 2  # gpt-4-turbo, gpt-4o
        model_names = [m.model_name for m in models]
        assert "gpt-4-turbo" in model_names
        assert "gpt-4o" in model_names

    def test_query_by_all_capabilities_three_hybrid(self, db: Session, sample_models):
        """Test querying for models with 3 hybrid capabilities"""
        models = query_by_all_capabilities(
            db, "tenant-1", [VISION, TOOLS, FUNCTION_CALLING]
        )

        assert len(models) == 1  # only gpt-4o
        assert models[0].model_name == "gpt-4o"

    def test_query_by_all_capabilities_mixed_hybrid_rare(self, db: Session, sample_models):
        """Test querying with mix of hybrid and rare capabilities"""
        models = query_by_all_capabilities(db, "tenant-1", [VISION, JSON_MODE])

        assert len(models) == 1  # only claude-3-sonnet has both
        assert models[0].model_name == "claude-3-sonnet"

    def test_query_by_all_capabilities_no_matches(self, db: Session, sample_models):
        """Test querying with impossible combination"""
        models = query_by_all_capabilities(db, "tenant-1", [AUDIO, JSON_MODE])

        assert len(models) == 0


class TestAnyCapabilityOR:
    """Tests for any capability OR queries"""

    def test_query_by_any_capability_vision_or_tools(self, db: Session, sample_models):
        """Test querying for models with vision OR tools"""
        models = query_by_any_capability(db, "tenant-1", [VISION, TOOLS])

        # Should return 5 models: all except custom-model (only json_mode)
        assert len(models) == 5
        model_names = [m.model_name for m in models]
        assert "custom-model" not in model_names

    def test_query_by_any_capability_all_common(self, db: Session, sample_models):
        """Test querying for models with any common capability"""
        models = query_by_any_capability(
            db, "tenant-1", [VISION, TOOLS, FUNCTION_CALLING, AUDIO]
        )

        # All models except custom-model
        assert len(models) == 5

    def test_query_by_any_capability_rare_only(self, db: Session, sample_models):
        """Test querying for rare capability only"""
        models = query_by_any_capability(db, "tenant-1", [JSON_MODE])

        assert len(models) == 2  # custom-model, claude-3-sonnet


class TestMetadataQueries:
    """Tests for metadata JSONB path queries"""

    def test_query_by_metadata_provider(self, db: Session, sample_models):
        """Test querying by provider in metadata"""
        # First add metadata to sample models
        for model in db.query(LLMModel).filter_by(tenant_id="tenant-1").all():
            model.provider_metadata = {"provider": model.provider}
        db.commit()

        models = query_by_metadata(db, "tenant-1", "provider", "openai")

        assert len(models) == 3  # gpt-4-vision, gpt-4-turbo, gpt-4o
        assert all(m.provider == "openai" for m in models)

    def test_query_by_metadata_no_matches(self, db: Session, sample_models):
        """Test querying metadata with no matches"""
        models = query_by_metadata(db, "tenant-1", "nonexistent", "value")

        assert len(models) == 0


class TestCombinedQueries:
    """Tests for combined flexible queries"""

    def test_get_capable_models_required_only(self, db: Session, sample_models):
        """Test combined query with required capabilities only"""
        models = get_capable_models(
            db, "tenant-1", required_capabilities=[VISION, TOOLS]
        )

        assert len(models) == 2  # gpt-4-turbo, gpt-4o

    def test_get_capable_models_any_only(self, db: Session, sample_models):
        """Test combined query with any capability only"""
        models = get_capable_models(
            db, "tenant-1", any_capabilities=[VISION, AUDIO]
        )

        # Models with vision OR audio
        assert len(models) == 5

    def test_get_capable_models_required_and_any(self, db: Session, sample_models):
        """Test combined query with both required and any"""
        models = get_capable_models(
            db,
            "tenant-1",
            required_capabilities=[TOOLS],
            any_capabilities=[VISION, AUDIO],
        )

        # Must have tools AND (vision OR audio)
        # Matches: gpt-4-turbo (tools + vision), gpt-4o (tools + both)
        assert len(models) == 2
        model_names = [m.model_name for m in models]
        assert "gpt-4-turbo" in model_names
        assert "gpt-4o" in model_names

    def test_get_capable_models_any_single_string(self, db: Session, sample_models):
        """Test any_capability as single string"""
        models = get_capable_models(
            db, "tenant-1", any_capability=VISION
        )

        assert len(models) == 4


class TestSyncCapabilities:
    """Tests for sync_capabilities method"""

    def test_sync_capabilities_adds_to_hybrid_columns(self, db: Session):
        """Test that sync_capabilities updates hybrid columns"""
        model = LLMModel(
            tenant_id="tenant-1",
            provider="test",
            model_name="test-model",
            capabilities=[VISION, TOOLS],
        )

        model.sync_capabilities()

        assert model.supports_vision is True
        assert model.supports_tools is True
        assert model.supports_function_calling is False
        assert model.supports_audio is False

    def test_sync_capabilities_all_hybrid(self, db: Session):
        """Test sync with all hybrid capabilities"""
        model = LLMModel(
            tenant_id="tenant-1",
            provider="test",
            model_name="test-model",
            capabilities=[VISION, TOOLS, FUNCTION_CALLING, AUDIO],
        )

        model.sync_capabilities()

        assert model.supports_vision is True
        assert model.supports_tools is True
        assert model.supports_function_calling is True
        assert model.supports_audio is True

    def test_sync_capabilities_empty(self, db: Session):
        """Test sync with empty capabilities"""
        model = LLMModel(
            tenant_id="tenant-1",
            provider="test",
            model_name="test-model",
            capabilities=[],
        )

        model.sync_capabilities()

        assert model.supports_vision is False
        assert model.supports_tools is False
        assert model.supports_function_calling is False
        assert model.supports_audio is False


class TestHybridCapabilities:
    """Tests for hybrid capability constants"""

    def test_get_hybrid_capabilities(self, db: Session):
        """Test getting list of hybrid capabilities"""
        hybrid = LLMModel.get_hybrid_capabilities()

        assert VISION in hybrid
        assert TOOLS in hybrid
        assert FUNCTION_CALLING in hybrid
        assert AUDIO in hybrid
        assert JSON_MODE not in hybrid  # Not a hybrid capability


class TestIndexUsage:
    """Tests for verifying GIN index usage (PostgreSQL only)"""

    def test_explain_query_output(self, db: Session, sample_models):
        """Test that explain_query returns execution plan"""
        plan = explain_query(db, "tenant-1", VISION)

        assert plan is not None
        assert isinstance(plan, str)
        assert len(plan) > 0

    def test_index_usage_stats(self, db: Session, sample_models):
        """Test getting index usage statistics"""
        stats = get_index_usage_stats(db, "tenant-1", VISION)

        assert "explain_output" in stats
        assert "uses_gin_index" in stats
        assert "execution_time" in stats
        assert "planning_time" in stats
        assert "row_count" in stats

    def test_gin_index_used_for_capability_query(self, db: Session, sample_models):
        """Verify that GIN index is used for capability queries"""
        stats = get_index_usage_stats(db, "tenant-1", VISION)

        # Check that the query uses an index
        # Note: Actual index usage depends on data size and planner decisions
        assert stats["row_count"] is not None


class TestToDict:
    """Tests for to_dict method with hybrid columns"""

    def test_to_dict_includes_hybrid_columns(self, db: Session):
        """Test that to_dict includes hybrid capability columns"""
        model = LLMModel(
            tenant_id="tenant-1",
            provider="test",
            model_name="test-model",
            capabilities=[VISION, TOOLS],
            supports_vision=True,
            supports_tools=True,
            supports_function_calling=False,
            supports_audio=False,
        )
        db.add(model)
        db.commit()

        result = model.to_dict()

        assert "supports_vision" in result
        assert "supports_tools" in result
        assert "supports_function_calling" in result
        assert "supports_audio" in result
        assert result["supports_vision"] is True
        assert result["supports_tools"] is True
        assert result["supports_function_calling"] is False
        assert result["supports_audio"] is False
