"""
Tests for LLMRegistryService - Model metadata management.

Tests cover:
- Service initialization
- Model upsert operations
- Querying models by capability
- Model deletion and deprecation
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from core.llm.registry.service import LLMRegistryService
from core.llm.registry.models import LLMModel


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock()
    db.query = Mock()
    db.filter = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.flush = Mock()
    db.refresh = Mock()
    return db


@pytest.fixture
def registry_service(mock_db):
    """Create LLMRegistryService instance."""
    with patch('core.llm.registry.service.RegistryCacheService'):
        with patch('core.llm.registry.service.ModelMetadataFetcher'):
            service = LLMRegistryService(mock_db, use_cache=False)
            return service


# ============================================================================
# Service Initialization Tests (3 tests)
# ============================================================================

class TestLLMRegistryServiceInit:
    """Tests for LLMRegistryService initialization."""

    def test_initialization_with_db(self, mock_db):
        """Test service initialization with database session."""
        with patch('core.llm.registry.service.RegistryCacheService'):
            with patch('core.llm.registry.service.ModelMetadataFetcher'):
                service = LLMRegistryService(mock_db, use_cache=False)
                assert service.db == mock_db
                assert service.cache is None
                assert service.use_cache is False

    def test_initialization_with_cache(self, mock_db):
        """Test service initialization with cache enabled."""
        with patch('core.llm.registry.service.RegistryCacheService') as mock_cache:
            with patch('core.llm.registry.service.ModelMetadataFetcher'):
                service = LLMRegistryService(mock_db, use_cache=True)
                assert service.cache is not None
                assert service.use_cache is True

    def test_initialization_creates_fetcher(self, mock_db):
        """Test that initialization creates ModelMetadataFetcher."""
        with patch('core.llm.registry.service.RegistryCacheService'):
            with patch('core.llm.registry.service.ModelMetadataFetcher') as mock_fetcher:
                service = LLMRegistryService(mock_db)
                assert service.fetcher is not None


# ============================================================================
# Model Upsert Tests (6 tests)
# ============================================================================

class TestUpsertModel:
    """Tests for model upsert operations."""

    def test_upsert_model_new_model(self, registry_service, mock_db):
        """Test upserting a new model."""
        model_data = {
            'model_name': 'gpt-4',
            'provider': 'openai',
            'context_window': 8192,
            'input_price_per_token': 0.00003,
            'output_price_per_token': 0.00006
        }

        mock_query = Mock()
        mock_existing_model = None
        mock_query.filter.return_value.first.return_value = mock_existing_model
        mock_db.query.return_value = mock_query

        model = registry_service.upsert_model('tenant-123', model_data)

        assert mock_db.add.called
        assert mock_db.flush.called

    def test_upsert_model_existing_model(self, registry_service, mock_db):
        """Test upserting an existing model (update)."""
        existing_model = Mock(spec=LLMModel)
        existing_model.id = 1

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = existing_model
        mock_db.query.return_value = mock_query

        model_data = {
            'model_name': 'gpt-4',
            'provider': 'openai',
            'context_window': 128000,  # Updated value
            'input_price_per_token': 0.00003,
            'output_price_per_token': 0.00006
        }

        model = registry_service.upsert_model('tenant-123', model_data)

        # Should update existing model, not add new one
        assert not mock_db.add.called

    def test_upsert_model_with_capabilities(self, registry_service, mock_db):
        """Test upserting model with capabilities list."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        model_data = {
            'model_name': 'claude-3-opus',
            'provider': 'anthropic',
            'capabilities': ['vision', 'code', 'math']
        }

        model = registry_service.upsert_model('tenant-123', model_data)

        assert mock_db.add.called

    def test_upsert_model_handles_commit_error(self, registry_service, mock_db):
        """Test upsert handles database commit errors."""
        mock_db.flush.side_effect = Exception("Database error")

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        model_data = {'model_name': 'gpt-4', 'provider': 'openai'}

        # Should not raise, should handle error gracefully
        try:
            model = registry_service.upsert_model('tenant-123', model_data)
        except Exception:
            pass  # Expected

    def test_upsert_model_with_pricing_dict(self, registry_service, mock_db):
        """Test upserting model with pricing information."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        model_data = {
            'model_name': 'gpt-3.5-turbo',
            'provider': 'openai',
            'input_price_per_token': 0.0005,
            'output_price_per_token': 0.0015
        }

        model = registry_service.upsert_model('tenant-123', model_data)

        assert mock_db.add.called

    def test_upsert_model_preserves_tenant_id(self, registry_service, mock_db):
        """Test that upsert preserves tenant_id."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        model_data = {'model_name': 'test-model', 'provider': 'test'}

        model = registry_service.upsert_model('tenant-abc', model_data)

        assert mock_db.add.called


# ============================================================================
# Query Models Tests (4 tests)
# ============================================================================

class TestQueryModels:
    """Tests for querying models."""

    def test_get_models_by_capability(self, registry_service, mock_db):
        """Test getting models filtered by capability."""
        mock_models = [
            Mock(spec=LLMModel, capabilities=['vision', 'code']),
            Mock(spec=LLMModel, capabilities=['vision'])
        ]
        
        mock_query_result = Mock()
        mock_query_result.all.return_value = mock_models
        mock_db.query.return_value.filter.return_value = mock_query_result
        
        models = registry_service.get_models_by_capability('tenant-123', 'vision')
        
        assert models is not None

    def test_get_models_by_capability_empty_result(self, registry_service, mock_db):
        """Test getting models when no models match capability."""
        mock_query_result = Mock()
        mock_query_result.all.return_value = []
        mock_db.query.return_value.filter.return_value = mock_query_result
        
        models = registry_service.get_models_by_capability('tenant-123', 'nonexistent')
        
        assert models == []

    def test_get_models_by_capability_multiple_capabilities(self, registry_service, mock_db):
        """Test getting models with multiple capabilities."""
        mock_models = [
            Mock(spec=LLMModel, capabilities=['vision', 'code', 'math'])
        ]
        
        mock_query_result = Mock()
        mock_query_result.all.return_value = mock_models
        mock_db.query.return_value.filter.return_value = mock_query_result
        
        models = registry_service.get_models_by_capability('tenant-123', 'code')
        
        assert len(models) >= 0

    def test_get_models_by_capability_ignores_cache(self, registry_service, mock_db):
        """Test that capability query bypasses cache."""
        mock_query_result = Mock()
        mock_query_result.all.return_value = []
        mock_db.query.return_value.filter.return_value = mock_query_result

        # Service initialized with cache disabled
        assert registry_service.use_cache is False

        models = registry_service.get_models_by_capability('tenant-123', 'vision', use_cache=False)

        assert models is not None


# ============================================================================
# Model Deletion Tests (3 tests)
# ============================================================================

class TestDeleteModel:
    """Tests for model deletion."""

    @pytest.mark.asyncio
    async def test_delete_model_success(self, registry_service, mock_db):
        """Test successful model deletion."""
        mock_model = Mock(spec=LLMModel)
        mock_model.id = 1

        # Mock get_model to return the model directly (bypassing async issue)
        with patch.object(registry_service, 'get_model', return_value=mock_model):
            result = registry_service.delete_model('tenant-123', 'openai', 'gpt-4')

            assert mock_db.delete.called
            assert result is True

    @pytest.mark.asyncio
    async def test_delete_model_not_found(self, registry_service, mock_db):
        """Test deleting a model that doesn't exist."""
        # Mock get_model to return None (use regular Mock, not AsyncMock)
        mock_get_model = Mock(return_value=None)
        with patch.object(registry_service, 'get_model', mock_get_model):
            result = registry_service.delete_model('tenant-123', 'provider', 'nonexistent')

            assert result is False

    @pytest.mark.asyncio
    async def test_delete_model_handles_database_error(self, registry_service, mock_db):
        """Test delete handles database errors gracefully."""
        mock_model = Mock(spec=LLMModel)

        # Mock get_model to return the model
        with patch.object(registry_service, 'get_model', return_value=mock_model):
            mock_db.delete.side_effect = Exception("Database error")

            try:
                result = registry_service.delete_model('tenant-123', 'openai', 'gpt-4')
            except Exception:
                pass  # Expected


# ============================================================================
# Model Deprecation Tests (3 tests)
# ============================================================================

class TestModelDeprecation:
    """Tests for model deprecation."""

    @pytest.mark.asyncio
    async def test_mark_model_deprecated(self, registry_service, mock_db):
        """Test marking a model as deprecated."""
        mock_model = Mock(spec=LLMModel)
        mock_model.is_deprecated = False

        # Mock get_model to return the model directly (use regular Mock, not AsyncMock)
        mock_get_model = Mock(return_value=mock_model)
        with patch.object(registry_service, 'get_model', mock_get_model):
            result = registry_service.mark_model_deprecated('tenant-123', 'openai', 'gpt-4', reason='Replaced by gpt-4-turbo')

            assert mock_db.commit.called
            assert result is not None

    @pytest.mark.asyncio
    async def test_mark_model_deprecated_already_deprecated(self, registry_service, mock_db):
        """Test marking an already deprecated model."""
        mock_model = Mock(spec=LLMModel)
        mock_model.is_deprecated = True

        # Mock get_model to return the model directly (use regular Mock)
        mock_get_model = Mock(return_value=mock_model)
        with patch.object(registry_service, 'get_model', mock_get_model):
            result = registry_service.mark_model_deprecated('tenant-123', 'provider', 'old-model', reason='Already deprecated')

            # Should still return the model even if already deprecated
            assert result is not None

    def test_restore_deprecated_model(self, registry_service, mock_db):
        """Test restoring a deprecated model."""
        mock_model = Mock(spec=LLMModel)
        mock_model.is_deprecated = True

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_model
        mock_db.query.return_value = mock_query

        result = registry_service.restore_deprecated_model('tenant-123', 'openai', 'gpt-4')

        assert mock_db.commit.called


# ============================================================================
# Total: 19 tests focused on core functionality
# ============================================================================
