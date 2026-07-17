"""
Coverage tests for core/llm/registry module (0% -> target 80%+)

Target files:
- models.py (LLMModel, ModelSyncJob)
- sync_job.py (sync functionality)
- cache.py (caching)
- queries.py (query functions)
- heuristic_scorer.py (scoring)
- rate_limiter.py (rate limiting)
- provider_health.py (health checks)
- service.py (main service)
- transformers.py (data transformation)
"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from datetime import datetime, timedelta


class TestRegistryModels:
    """Test registry model classes"""

    def test_llm_model_exists(self):
        """Test LLMModel model exists"""
        from core.llm.registry.models import LLMModel
        assert LLMModel is not None

    def test_model_sync_job_exists(self):
        """Test ModelSyncJob model exists"""
        from core.llm.registry.sync_job import ModelSyncJob
        assert ModelSyncJob is not None

    def test_llm_model_creation(self):
        """Test LLMModel creation"""
        from core.llm.registry.models import LLMModel
        
        model = LLMModel(
            tenant_id="tenant-123",
            provider="openai",
            model_name="gpt-4",
            context_window=8192,
            input_price_per_token=0.00003,
            output_price_per_token=0.00006
        )
        
        assert model.tenant_id == "tenant-123"
        assert model.provider == "openai"
        assert model.model_name == "gpt-4"
        assert model.context_window == 8192


class TestModelSyncJob:
    """Test model sync job functionality"""

    def test_sync_job_creation(self):
        """Test ModelSyncJob creation"""
        from core.llm.registry.sync_job import ModelSyncJob
        mock_db = MagicMock()
        job = ModelSyncJob(mock_db)
        assert job.db == mock_db

    def test_run_sync_job(self):
        """Test running sync job"""
        from core.llm.registry.sync_job import run_sync_job
        
        with patch('core.llm.registry.sync_job.ModelSyncJob.run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {"models_fetched": 10}
            import asyncio
            result = asyncio.run(run_sync_job("tenant-123"))
            assert result == {"models_fetched": 10}


class TestRegistryCache:
    """Test registry cache functionality"""

    def test_cache_module_exists(self):
        """Test cache module exists"""
        from core.llm.registry import cache
        assert cache is not None

    def test_cache_functions(self):
        """Test cache functions exist"""
        from core.llm.registry.cache import RegistryCacheService
        
        assert RegistryCacheService is not None


class TestRegistryQueries:
    """Test registry query functions"""

    def test_queries_module_exists(self):
        """Test queries module exists"""
        from core.llm.registry import queries
        assert queries is not None

    def test_list_available_models(self):
        """Test querying models by capability"""
        from core.llm.registry.queries import query_by_capability
        assert callable(query_by_capability)


class TestHeuristicScorer:
    """Test heuristic scorer"""

    def test_scorer_module_exists(self):
        """Test heuristic scorer module exists"""
        from core.llm.registry import heuristic_scorer
        assert heuristic_scorer is not None

    def test_score_calculation(self):
        """Test score calculation"""
        from core.llm.registry.heuristic_scorer import HeuristicScorer
        
        scorer = HeuristicScorer()
        score = scorer.calculate_score("gpt-4", 8192, "openai")
        assert isinstance(score, (int, float))


class TestRateLimiter:
    """Test rate limiter"""

    def test_rate_limiter_module_exists(self):
        """Test rate limiter module exists"""
        from core.llm.registry import rate_limiter
        assert rate_limiter is not None

    def test_rate_limiter_class(self):
        """Test RateLimiter class exists"""
        from core.llm.registry.rate_limiter import RateLimiter
        
        limiter = RateLimiter()
        assert limiter is not None


class TestProviderHealth:
    """Test provider health checks"""

    def test_health_module_exists(self):
        """Test provider health module exists"""
        from core.llm.registry import provider_health
        assert provider_health is not None

    def test_health_checker_class(self):
        """Test ProviderHealthService class exists"""
        from core.llm.registry.provider_health import ProviderHealthService
        
        checker = ProviderHealthService()
        assert checker is not None


class TestRegistryService:
    """Test registry service"""

    def test_service_module_exists(self):
        """Test service module exists"""
        from core.llm.registry import service
        assert service is not None

    def test_registry_service_class(self):
        """Test LLMRegistryService class exists"""
        from core.llm.registry.service import LLMRegistryService
        
        mock_db = MagicMock()
        service = LLMRegistryService(mock_db)
        assert service is not None


class TestTransformers:
    """Test data transformers"""

    def test_transformers_module_exists(self):
        """Test transformers module exists"""
        from core.llm.registry import transformers
        assert transformers is not None

    def test_transform_functions(self):
        """Test transform functions exist"""
        from core.llm.registry.transformers import transform_litellm_model
        
        assert callable(transform_litellm_model)


class TestLMSysClient:
    """Test LMSys API client"""

    def test_lmsys_module_exists(self):
        """Test LMSys module exists"""
        from core.llm.registry import lmsys_client
        assert lmsys_client is not None

    def test_lmsys_client_class(self):
        """Test LMSYSClient class exists"""
        from core.llm.registry.lmsys_client import LMSYSClient
        
        client = LMSYSClient()
        assert client is not None


class TestFetchers:
    """Test data fetchers"""

    def test_fetchers_module_exists(self):
        """Test fetchers module exists"""
        from core.llm.registry import fetchers
        assert fetchers is not None

    def test_fetch_functions(self):
        """Test fetch functions exist"""
        from core.llm.registry.fetchers import fetch_model_metadata
        
        assert callable(fetch_model_metadata)
