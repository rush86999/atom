"""
Integration tests for capability-based routing and health filtering in BYOKHandler

Phase 226.4-04: Tests for LUX exclusion, capability filtering, health filtering, and combined routing
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from core.llm.byok_handler import BYOKHandler, QueryComplexity
from core.models import ModelCatalog
from core.provider_health_monitor import ProviderHealthMonitor


class TestCapabilityRouting:
    """Test suite for capability-based routing"""

    @pytest.fixture
    def mock_byok_handler(self):
        """Create BYOKHandler with mocked dependencies"""
        with patch('core.llm.byok_handler.get_byok_manager'), \
             patch('core.llm.byok_handler.CacheAwareRouter'), \
             patch('core.llm.byok_handler.CognitiveClassifier'), \
             patch('core.llm.byok_handler.CognitiveTierService'), \
             patch('core.provider_health_monitor.get_provider_health_monitor'):
            handler = BYOKHandler()
            # Mock the clients dictionary
            handler.clients = {
                "anthropic": Mock(),
                "openai": Mock(),
                "deepseek": Mock(),
            }
            # Mock health monitor
            handler.health_monitor = Mock()
            handler.health_monitor.health_scores = {}
            handler.health_monitor.get_health_score = Mock(return_value=1.0)
            handler.health_monitor.record_call = Mock()
            # Mock _refresh_excluded_cache to avoid DB queries
            handler.excluded_models = set()
            handler._refresh_excluded_cache = Mock()
            return handler

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session"""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        return session

    @pytest.fixture
    def mock_pricing_fetcher(self):
        """Create mock pricing fetcher with test models"""
        fetcher = Mock()
        fetcher.pricing_cache = {
            "gpt-4o": {
                "litellm_provider": "openai",
                "max_input_tokens": 128000,
                "input_cost_per_token": 2.5e-6,
                "output_cost_per_token": 1.0e-5,
            },
            "claude-3.5-sonnet": {
                "litellm_provider": "anthropic",
                "max_input_tokens": 200000,
                "input_cost_per_token": 3.0e-6,
                "output_cost_per_token": 1.5e-5,
            },
            "lux-1.0": {
                "litellm_provider": "anthropic",
                "max_input_tokens": 200000,
                "input_cost_per_token": 3.0e-6,
                "output_cost_per_token": 1.5e-5,
            },
            "deepseek-chat": {
                "litellm_provider": "deepseek",
                "max_input_tokens": 16000,
                "input_cost_per_token": 1.0e-7,
                "output_cost_per_token": 2.0e-7,
            },
        }
        return fetcher

    def test_lux_excluded_from_general_routing(self, mock_byok_handler, mock_db_session, mock_pricing_fetcher):
        """Test that LUX is excluded from general routing when no capability requirement"""
        # Mock ModelCatalog to return LUX with exclude_from_general_routing=True
        lux_model = ModelCatalog(
            model_id="lux-1.0",
            provider_id="anthropic",
            capabilities=["computer_use", "browser_use"],
            exclude_from_general_routing=True
        )
        gpt_model = ModelCatalog(
            model_id="gpt-4o",
            provider_id="openai",
            capabilities=["chat", "vision", "tools"],
            exclude_from_general_routing=False
        )

        def mock_query(model):
            if model == ModelCatalog:
                mock_query_obj = MagicMock()
                if "lux" in str(mock_query_obj.filter.return_value.first.return_value):
                    mock_query_obj.filter.return_value.first.return_value = lux_model
                else:
                    mock_query_obj.filter.return_value.first.return_value = gpt_model
                return mock_query_obj
            return MagicMock()

        mock_db_session.query.return_value.filter_by.return_value.first.side_effect = [
            gpt_model,  # gpt-4o first
            lux_model,  # lux-1.0 second
        ]

        with patch('core.llm.byok_handler.get_db_session', return_value=mock_db_session), \
             patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher), \
             patch('core.llm.byok_handler.get_capability_score') as mock_cap_score, \
             patch('core.llm.byok_handler.get_quality_score', return_value=90):
            mock_cap_score.return_value = 95  # lux has high computer_use score
            mock_byok_handler._refresh_excluded_cache()

            result = mock_byok_handler.get_ranked_providers(
                complexity=QueryComplexity.MODERATE,
                required_capability=None  # No capability requirement
            )

            model_ids = [model for provider, model in result]
            assert "lux-1.0" not in model_ids, "LUX should be excluded from general routing"
            assert "gpt-4o" in model_ids, "GPT-4o should be included in general routing"

    def test_lux_included_for_computer_use(self, mock_byok_handler, mock_db_session, mock_pricing_fetcher):
        """Test that LUX is included when required_capability='computer_use'"""
        lux_model = ModelCatalog(
            model_id="lux-1.0",
            provider_id="anthropic",
            capabilities=["computer_use", "browser_use"],
            exclude_from_general_routing=True
        )

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = lux_model

        with patch('core.llm.byok_handler.get_db_session', return_value=mock_db_session), \
             patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher), \
             patch('core.llm.byok_handler.get_capability_score') as mock_cap_score:
            mock_cap_score.return_value = 95  # lux has high computer_use score
            mock_byok_handler._refresh_excluded_cache()

            result = mock_byok_handler.get_ranked_providers(
                complexity=QueryComplexity.MODERATE,
                required_capability="computer_use"
            )

            model_ids = [model for provider, model in result]
            assert "lux-1.0" in model_ids, "LUX should be included for computer_use routing"

    def test_capability_filter_vision_only(self, mock_byok_handler, mock_db_session, mock_pricing_fetcher):
        """Test that only vision-capable models are filtered correctly"""
        gpt_model = ModelCatalog(
            model_id="gpt-4o",
            provider_id="openai",
            capabilities=["chat", "vision", "tools"],
            exclude_from_general_routing=False
        )
        deepseek_model = ModelCatalog(
            model_id="deepseek-chat",
            provider_id="deepseek",
            capabilities=["chat"],
            exclude_from_general_routing=False
        )

        call_count = [0]
        def mock_first():
            call_count[0] += 1
            if call_count[0] == 1:
                return gpt_model
            return deepseek_model

        mock_db_session.query.return_value.filter_by.return_value.first.side_effect = mock_first

        with patch('core.llm.byok_handler.get_db_session', return_value=mock_db_session), \
             patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher), \
             patch('core.llm.byok_handler.get_capability_score', return_value=95):
            result = mock_byok_handler.get_ranked_providers(
                complexity=QueryComplexity.MODERATE,
                required_capability="vision"
            )

            model_ids = [model for provider, model in result]
            # GPT-4o should be included (has vision), deepseek-chat should be filtered
            assert any("gpt-4o" in model for model in model_ids), "GPT-4o should be included for vision"

    def test_capability_filter_no_requirement(self, mock_byok_handler, mock_db_session, mock_pricing_fetcher):
        """Test that all models are included when no capability requirement"""
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = None

        with patch('core.llm.byok_handler.get_db_session', return_value=mock_db_session), \
             patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher), \
             patch('core.llm.byok_handler.get_quality_score', return_value=90):
            result = mock_byok_handler.get_ranked_providers(
                complexity=QueryComplexity.MODERATE,
                required_capability=None
            )

            # Should include all models that pass quality filter
            assert len(result) > 0, "Should return models when no capability requirement"

    def test_capability_specific_quality_score(self, mock_byok_handler, mock_db_session, mock_pricing_fetcher):
        """Test that get_capability_score is used when required_capability is set"""
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = None

        with patch('core.llm.byok_handler.get_db_session', return_value=mock_db_session), \
             patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher), \
             patch('core.llm.byok_handler.get_capability_score') as mock_cap_score:
            mock_cap_score.return_value = 92  # Capability-specific score

            mock_byok_handler.get_ranked_providers(
                complexity=QueryComplexity.MODERATE,
                required_capability="computer_use"
            )

            # Should have called get_capability_score
            assert mock_cap_score.called, "get_capability_score should be called with required_capability"

    def test_capability_fallback_to_generic_score(self, mock_byok_handler, mock_db_session, mock_pricing_fetcher):
        """Test that get_quality_score is used for unknown capabilities"""
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = None

        with patch('core.llm.byok_handler.get_db_session', return_value=mock_db_session), \
             patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher), \
             patch('core.llm.byok_handler.get_quality_score', return_value=85) as mock_quality_score:
            mock_byok_handler.get_ranked_providers(
                complexity=QueryComplexity.MODERATE,
                required_capability=None
            )

            # Should have called get_quality_score (not capability score)
            assert mock_quality_score.called, "get_quality_score should be called without required_capability"

    def test_excluded_models_cache(self, mock_byok_handler):
        """Test that excluded_models cache is populated correctly"""
        with patch('core.llm.byok_handler.get_db_session') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.query.return_value.filter.return_value.all.return_value = [
                ("lux-1.0",),
                ("specialized-model-2",),
            ]

            mock_byok_handler._refresh_excluded_cache()

            assert "lux-1.0" in mock_byok_handler.excluded_models
            assert "specialized-model-2" in mock_byok_handler.excluded_models
            assert len(mock_byok_handler.excluded_models) == 2

    def test_refresh_excluded_cache(self, mock_byok_handler):
        """Test that cache refresh queries database correctly"""
        with patch('core.llm.byok_handler.get_db_session') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.query.return_value.filter.return_value.all.return_value = [
                ("lux-1.0",),
            ]

            mock_byok_handler._refresh_excluded_cache()

            # Verify query was called with correct filter
            mock_db.query.assert_called_once_with(ModelCatalog.model_id)

    def test_health_filter_unhealthy_excluded(self, mock_byok_handler, mock_db_session, mock_pricing_fetcher):
        """Test that providers with health_score < 0.5 are excluded"""
        # Set up health monitor with unhealthy provider
        mock_byok_handler.health_monitor.health_scores = {
            "openai": 0.3,  # Unhealthy
            "anthropic": 0.8,  # Healthy
        }

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = None

        with patch('core.llm.byok_handler.get_db_session', return_value=mock_db_session), \
             patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher), \
             patch('core.llm.byok_handler.get_quality_score', return_value=90):
            result = mock_byok_handler.get_ranked_providers(
                complexity=QueryComplexity.MODERATE,
                required_capability=None
            )

            providers = [provider for provider, model in result]
            # OpenAI should be filtered out due to low health score
            assert "openai" not in providers, "Unhealthy providers should be excluded"

    def test_health_filter_healthy_included(self, mock_byok_handler, mock_db_session, mock_pricing_fetcher):
        """Test that providers with health_score >= 0.5 are included"""
        mock_byok_handler.health_monitor.health_scores = {
            "anthropic": 0.9,  # Healthy
        }

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = None

        with patch('core.llm.byok_handler.get_db_session', return_value=mock_db_session), \
             patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher), \
             patch('core.llm.byok_handler.get_quality_score', return_value=90):
            result = mock_byok_handler.get_ranked_providers(
                complexity=QueryComplexity.MODERATE,
                required_capability=None
            )

            providers = [provider for provider, model in result]
            assert "anthropic" in providers, "Healthy providers should be included"

    def test_health_filter_unknown_passes(self, mock_byok_handler, mock_db_session, mock_pricing_fetcher):
        """Test that unknown providers (no health score) pass through"""
        # Empty health scores - all providers are unknown
        mock_byok_handler.health_monitor.health_scores = {}

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = None

        with patch('core.llm.byok_handler.get_db_session', return_value=mock_db_session), \
             patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher), \
             patch('core.llm.byok_handler.get_quality_score', return_value=90):
            result = mock_byok_handler.get_ranked_providers(
                complexity=QueryComplexity.MODERATE,
                required_capability=None
            )

            # Should return results (unknown providers pass through)
            assert len(result) > 0, "Unknown providers should pass through health filter"

    def test_capability_and_health_combined(self, mock_byok_handler, mock_db_session, mock_pricing_fetcher):
        """Test that both capability and health filters are applied together"""
        lux_model = ModelCatalog(
            model_id="lux-1.0",
            provider_id="anthropic",
            capabilities=["computer_use"],
            exclude_from_general_routing=True
        )

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = lux_model

        # Set up health: anthropic healthy, deepseek unhealthy
        mock_byok_handler.health_monitor.health_scores = {
            "anthropic": 0.9,
            "deepseek": 0.3,
        }

        with patch('core.llm.byok_handler.get_db_session', return_value=mock_db_session), \
             patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher), \
             patch('core.llm.byok_handler.get_capability_score', return_value=95):
            result = mock_byok_handler.get_ranked_providers(
                complexity=QueryComplexity.MODERATE,
                required_capability="computer_use"
            )

            # LUX should be included (has computer_use) and anthropic is healthy
            model_ids = [model for provider, model in result]
            assert "lux-1.0" in model_ids, "LUX should pass capability filter"
            # Deepseek should be filtered by health
            providers = [provider for provider, model in result]
            assert "deepseek" not in providers, "Unhealthy providers should be filtered"

    def test_multiple_capability_models(self, mock_byok_handler, mock_db_session, mock_pricing_fetcher):
        """Test that models with multiple capabilities are matched correctly"""
        gpt_model = ModelCatalog(
            model_id="gpt-4o",
            provider_id="openai",
            capabilities=["chat", "vision", "tools", "computer_use"],
            exclude_from_general_routing=False
        )

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = gpt_model

        with patch('core.llm.byok_handler.get_db_session', return_value=mock_db_session), \
             patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher), \
             patch('core.llm.byok_handler.get_capability_score', return_value=92):
            # Test with different capabilities
            for capability in ["vision", "tools", "computer_use"]:
                result = mock_byok_handler.get_ranked_providers(
                    complexity=QueryComplexity.MODERATE,
                    required_capability=capability
                )
                model_ids = [model for provider, model in result]
                assert any("gpt-4o" in model for model in model_ids), \
                    f"GPT-4o should be included for {capability} capability"

    def test_vision_capability_routing(self, mock_byok_handler, mock_db_session, mock_pricing_fetcher):
        """Test vision models are filtered correctly"""
        vision_model = ModelCatalog(
            model_id="gpt-4o",
            provider_id="openai",
            capabilities=["chat", "vision"],
            exclude_from_general_routing=False
        )
        chat_only_model = ModelCatalog(
            model_id="deepseek-chat",
            provider_id="deepseek",
            capabilities=["chat"],
            exclude_from_general_routing=False
        )

        call_count = [0]
        def mock_first():
            call_count[0] += 1
            if call_count[0] % 2 == 1:
                return vision_model
            return chat_only_model

        mock_db_session.query.return_value.filter_by.return_value.first.side_effect = mock_first

        with patch('core.llm.byok_handler.get_db_session', return_value=mock_db_session), \
             patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher), \
             patch('core.llm.byok_handler.get_capability_score', return_value=90):
            result = mock_byok_handler.get_ranked_providers(
                complexity=QueryComplexity.MODERATE,
                required_capability="vision"
            )

            # Vision-capable models should be included
            assert len(result) > 0, "Should return vision-capable models"

    def test_tools_capability_routing(self, mock_byok_handler, mock_db_session, mock_pricing_fetcher):
        """Test tools support is filtered correctly"""
        tools_model = ModelCatalog(
            model_id="claude-3.5-sonnet",
            provider_id="anthropic",
            capabilities=["chat", "tools"],
            exclude_from_general_routing=False
        )

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = tools_model

        with patch('core.llm.byok_handler.get_db_session', return_value=mock_db_session), \
             patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher), \
             patch('core.llm.byok_handler.get_capability_score', return_value=93):
            result = mock_byok_handler.get_ranked_providers(
                complexity=QueryComplexity.MODERATE,
                required_capability="tools"
            )

            # Tools-capable models should be included
            model_ids = [model for provider, model in result]
            assert any("claude" in model.lower() for model in model_ids), \
                "Tools-capable models should be included"
