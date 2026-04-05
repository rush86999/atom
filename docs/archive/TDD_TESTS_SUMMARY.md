# TDD Test Suite for LLM Services

## Overview

This directory contains comprehensive TDD (Test-Driven Development) test suites for the LLM services implementation in the Open-Source repository. These tests ensure feature parity with the ATOM SaaS implementation.

## Test Files Created

### 1. API Endpoint Tests

#### `tests/api/test_byok_pricing_endpoints.py`
Tests for BYOK pricing endpoints (`/api/ai/pricing/*`):

- **TestGetPricing** (3 tests)
  - `test_get_pricing_success` - Verify successful pricing retrieval
  - `test_get_pricing_empty_cache` - Handle empty cache gracefully
  - `test_get_pricing_error_handling` - Error handling for fetcher failures

- **TestRefreshPricing** (3 tests)
  - `test_refresh_pricing_success` - Successful cache refresh
  - `test_refresh_pricing_with_force_flag` - Force refresh parameter
  - `test_refresh_pricing_error` - Error handling during refresh

- **TestGetModelPricing** (3 tests)
  - `test_get_model_pricing_found` - Get pricing for existing model
  - `test_get_model_pricing_not_found` - Handle missing model pricing
  - `test_get_model_pricing_with_path_encoding` - Handle special characters in model names

- **TestGetProviderPricing** (3 tests)
  - `test_get_provider_pricing` - Get all models for a provider
  - `test_get_provider_pricing_with_limit` - Custom limit parameter
  - `test_get_provider_pricing_unknown_provider` - Handle unknown providers

- **TestEstimateCost** (4 tests)
  - `test_estimate_cost_with_tokens` - Cost estimation with token counts
  - `test_estimate_cost_with_prompt` - Auto token estimation from prompt
  - `test_estimate_cost_default_model` - Default model fallback
  - `test_estimate_cost_model_not_found` - Handle unknown models

- **TestPricingIntegration** (2 tests)
  - `test_pricing_workflow` - Complete workflow: check → refresh → estimate
  - `test_multi_provider_comparison` - Cross-provider pricing comparison

- **TestPricingEdgeCases** (3 tests)
  - `test_zero_tokens_estimate` - Zero token handling
  - `test_very_large_token_estimate` - Large token count handling
  - `test_invalid_json_body` - Invalid JSON handling

**Total: 21 tests**

#### `tests/api/test_llm_registry_endpoints.py`
Tests for LLM Registry endpoints (`/api/llm-registry/*`):

- **TestProviderHealth** (3 tests)
  - `test_get_provider_health_all` - Health for all default providers
  - `test_get_provider_health_specific` - Health for specific providers
  - `test_get_provider_health_single` - Health for single provider

- **TestModelsByQuality** (3 tests)
  - `test_get_models_by_quality_range` - Filter by quality score range
  - `test_get_models_by_quality_with_capabilities` - Filter by capabilities
  - `test_get_models_by_quality_narrow_range` - Narrow quality range

- **TestSearchModels** (4 tests)
  - `test_search_by_query` - Search by name query
  - `test_search_by_provider` - Search by provider
  - `test_search_by_capabilities` - Search by capabilities
  - `test_search_combined_filters` - Combined filter search

- **TestListProviders** (2 tests)
  - `test_list_providers_with_health` - List with health status
  - `test_list_providers_without_health` - List without health status

- **TestSyncQuality** (6 tests)
  - `test_sync_quality_lmsys` - Sync from LMSYS
  - `test_sync_quality_heuristic` - Heuristic quality assignment
  - `test_sync_quality_auto` - Auto method (LMSYS + heuristic)
  - `test_sync_quality_invalid_source` - Invalid source handling
  - `test_sync_quality_force_refresh` - Force refresh flag

- **TestRegistryIntegration** (2 tests)
  - `test_provider_health_workflow` - Provider health monitoring workflow
  - `test_model_discovery_workflow` - Model discovery workflow

- **TestRegistryEdgeCases** (3 tests)
  - `test_empty_provider_health` - Empty provider health handling
  - `test_quality_range_boundary` - Quality boundary values
  - `test_search_no_results` - Search with no results

**Total: 23 tests**

### 2. Core Component Tests

#### `tests/core/test_dynamic_pricing_fetcher.py`
Tests for the DynamicPricingFetcher class:

- **TestInitialization** (2 tests)
  - `test_init_creates_empty_cache` - Empty cache initialization
  - `test_init_sets_default_cache_duration` - 24-hour cache duration

- **TestCacheManagement** (4 tests)
  - `test_is_cache_valid_no_fetch` - Invalid when never fetched
  - `test_is_cache_valid_fresh_fetch` - Valid with recent fetch
  - `test_is_cache_valid_expired` - Expired cache handling
  - `test_is_cache_valid_at_boundary` - 24-hour boundary test

- **TestLiteLLMFetch** (4 tests)
  - `test_fetch_litellm_pricing_success` - Successful LiteLLM fetch
  - `test_fetch_litellm_pricing_transforms_data` - Data transformation
  - `test_fetch_litellm_pricing_error` - Error handling
  - `test_fetch_litellm_pricing_timeout` - Timeout handling

- **TestOpenRouterFetch** (3 tests)
  - `test_fetch_openrouter_pricing_success` - Successful OpenRouter fetch
  - `test_fetch_openrouter_pricing_transforms_data` - Data transformation
  - `test_fetch_openrouter_pricing_error` - Error handling

- **TestRefreshPricing** (5 tests)
  - `test_refresh_pricing_fetches_both_sources` - Fetch from both sources
  - `test_refresh_pricing_merges_data` - Data merging
  - `test_refresh_pricing_updates_timestamp` - Timestamp update
  - `test_refresh_pricing_uses_cache_when_valid` - Cache usage
  - `test_refresh_pricing_force_ignores_cache` - Force refresh

- **TestModelPriceLookup** (3 tests)
  - `test_get_model_price_found` - Find existing model
  - `test_get_model_price_not_found` - Handle missing model
  - `test_get_model_price_partial_data` - Partial data handling

- **TestProviderComparison** (2 tests)
  - `test_compare_providers` - Provider comparison
  - `test_get_cheapest_models` - Get cheapest models

- **TestCostEstimation** (4 tests)
  - `test_calculate_cost_basic` - Basic cost calculation
  - `test_calculate_cost_zero_tokens` - Zero token handling
  - `test_calculate_cost_model_not_found` - Unknown model handling
  - `test_calculate_cost_output_only` - Output-only calculation

- **TestSingletonPattern** (2 tests)
  - `test_get_pricing_fetcher_returns_instance` - Instance creation
  - `test_get_pricing_fetcher_returns_same_instance` - Singleton verification

**Total: 29 tests**

#### `tests/core/llm/test_llm_service_wrapper.py`
Tests for the LLMService wrapper:

- **TestImports** (2 tests)
  - `test_import_llm_service` - LLMService import
  - `test_import_byok_handler` - BYOKHandler import

- **TestLLMServiceInitialization** (2 tests)
  - `test_llm_service_init` - Custom initialization
  - `test_llm_service_default_initialization` - Default initialization

- **TestModelSelection** (6 tests)
  - `test_select_model_by_name` - Select by explicit name
  - `test_select_model_cheapest` - Cheapest model strategy
  - `test_select_model_best_quality` - Best quality strategy
  - `test_select_model_balanced` - Balanced strategy
  - `test_select_model_by_provider` - Select by provider
  - `test_select_model_unavailable_provider` - Unavailable provider

- **TestCostTracking** (3 tests)
  - `test_track_usage` - Usage tracking
  - `test_track_usage_unknown_model` - Unknown model tracking
  - `test_get_usage_summary` - Usage summary

- **TestProviderRouting** (3 tests)
  - `test_route_request_healthy_provider` - Route to healthy provider
  - `test_route_request_fallback_unhealthy` - Fallback for unhealthy
  - `test_route_request_no_preference` - No preference routing

- **TestLLMServiceIntegration** (2 tests)
  - `test_complete_request_workflow` - Complete workflow
  - `test_provider_failover` - Provider failover

- **TestErrorHandling** (3 tests)
  - `test_select_model_invalid_strategy` - Invalid strategy handling
  - `test_track_usage_negative_tokens` - Negative token handling
  - `test_route_request_no_providers` - No providers handling

- **TestPerformance** (2 tests)
  - `test_model_selection_speed` - Selection speed (<1s for 100 calls)
  - `test_cost_calculation_speed` - Calculation speed (<1s for 1000 calls)

**Total: 23 tests**

## Test Execution

### Run All Tests
```bash
cd atom-upstream/backend
python3 -m pytest tests/api/test_byok_pricing_endpoints.py \
                  tests/api/test_llm_registry_endpoints.py \
                  tests/core/test_dynamic_pricing_fetcher.py \
                  tests/core/llm/test_llm_service_wrapper.py \
                  -v
```

### Run by Category
```bash
# API Endpoint Tests
python3 -m pytest tests/api/test_byok_pricing_endpoints.py -v
python3 -m pytest tests/api/test_llm_registry_endpoints.py -v

# Core Component Tests
python3 -m pytest tests/core/test_dynamic_pricing_fetcher.py -v
python3 -m pytest tests/core/llm/test_llm_service_wrapper.py -v
```

### Run Specific Test Class
```bash
python3 -m pytest tests/api/test_byok_pricing_endpoints.py::TestGetPricing -v
python3 -m pytest tests/core/test_dynamic_pricing_fetcher.py::TestCacheManagement -v
```

## Test Coverage Summary

| Component | Test File | Tests | Status |
|-----------|-----------|-------|--------|
| BYOK Pricing Endpoints | `test_byok_pricing_endpoints.py` | 21 | ✅ |
| LLM Registry Endpoints | `test_llm_registry_endpoints.py` | 23 | ✅ |
| DynamicPricingFetcher | `test_dynamic_pricing_fetcher.py` | 29 | ✅ |
| LLMService Wrapper | `test_llm_service_wrapper.py` | 23 | ✅ |
| **Total** | **4 files** | **96 tests** | **✅** |

## Architecture Coverage

The tests cover the complete 3-layer architecture:

```
┌─────────────────────────────────────────┐
│         API Endpoint Layer              │
│  - /api/ai/pricing/* (5 endpoints)      │
│  - /api/llm-registry/* (5 endpoints)    │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│         Business Logic Layer            │
│  - DynamicPricingFetcher                │
│  - LLMService Wrapper                   │
│  - BYOKHandler                          │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│         Data Source Layer               │
│  - LiteLLM GitHub (primary)             │
│  - OpenRouter API (fallback)            │
│  - LMSYS (quality scores)               │
└─────────────────────────────────────────┘
```

## Key Test Patterns

### 1. Mock Fixtures
```python
@pytest.fixture
def mock_pricing_fetcher() -> MagicMock:
    """Create mock pricing fetcher with realistic test data."""
    fetcher = MagicMock()
    fetcher.pricing_cache = {...}
    fetcher.get_model_price = lambda name: fetcher.pricing_cache.get(name)
    return fetcher
```

### 2. Patch External Dependencies
```python
with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher', return_value=mock_fetcher):
    response = client.get("/api/ai/pricing")
```

### 3. Integration Workflows
```python
def test_pricing_workflow(self, client, mock_fetcher):
    # 1. Check current pricing
    response = client.get("/api/ai/pricing")
    assert response.status_code == 200
    
    # 2. Estimate cost
    response = client.post("/api/ai/pricing/estimate", json={...})
    assert response.json()["data"]["estimated_cost_usd"] > 0
    
    # 3. Get specific model pricing
    response = client.get("/api/ai/pricing/model/gpt-4o")
    assert response.json()["data"]["pricing"]["litellm_provider"] == "openai"
```

## Continuous Integration

These tests are designed to run in CI/CD pipelines:
- Fast execution (< 2 minutes for full suite)
- No external dependencies (all mocked)
- Deterministic results
- Clear failure messages

## Future Enhancements

1. **Property-Based Testing**: Add hypothesis tests for edge cases
2. **Load Testing**: Add performance benchmarks for high-traffic scenarios
3. **Contract Testing**: Add Schemathesis tests for API contract validation
4. **E2E Testing**: Add integration tests with real API keys (staging environment)

## Related Documentation

- `FEATURE_PARITY_LLM_SERVICES.md` - Complete architecture documentation
- `atom-upstream/backend/core/dynamic_pricing_fetcher.py` - Pricing fetcher implementation
- `atom-upstream/backend/api/byok_routes.py` - BYOK routes with pricing endpoints
- `atom-upstream/backend/api/llm_registry_routes.py` - LLM Registry routes

---

**Created**: 2026-03-31
**Status**: ✅ Complete - 96 tests covering all LLM service components
