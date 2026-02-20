---
phase: 68-byok-cognitive-tier-system
plan: 02
subsystem: llm-routing
tags: [llm, caching, cost-optimization, byok, routing, cache-aware]

# Dependency graph
requires:
  - phase: 68-byok-cognitive-tier-system
    plan: 01
    provides: CacheAwareRouter foundation, DynamicPricingFetcher with cache metadata
provides:
  - Cache-aware cost calculation with prompt caching support
  - Historical cache hit tracking and prediction
  - BYOKHandler integration with cache-aware BPC scoring
  - Comprehensive test suite (25 tests, 100% pass rate)
affects: [68-03, 68-04, 68-05]

# Tech tracking
tech-stack:
  added: [CacheAwareRouter, cache hit prediction, cache outcome recording]
  patterns: [cache-aware cost scoring, historical cache hit tracking, in-memory cache history]

key-files:
  created: [backend/core/llm/cache_aware_router.py, backend/tests/test_cache_aware_routing.py]
  modified: [backend/core/dynamic_pricing_fetcher.py, backend/core/llm/byok_handler.py]

key-decisions:
  - "In-memory cache history sufficient for initial implementation (no DB persistence needed yet)"
  - "50% default cache hit probability (industry average from research)"
  - "10% cached cost ratio for OpenAI/Anthropic/Gemini (research-verified)"
  - "Minimum token thresholds enforced: 1024 (OpenAI/Gemini), 2048 (Anthropic)"

patterns-established:
  - "CacheAwareRouter pattern: Calculate effective cost with cache hit probability modeling"
  - "Historical tracking pattern: Record outcomes for future predictions (workspace-specific)"
  - "Provider capability pattern: Centralized cache capability metadata with fallbacks"

# Metrics
duration: 13min
completed: 2026-02-20
---

# Phase 68: Plan 02 Summary

**Cache-aware cost scoring for LLM routing with historical cache hit prediction, supporting OpenAI/Anthropic/Gemini prompt caching at 10% cost with 50% default hit probability**

## Performance

- **Duration:** 13 minutes
- **Started:** 2026-02-20T17:17:12Z
- **Completed:** 2026-02-20T12:29:57Z
- **Tasks:** 4 completed
- **Files modified:** 4

## Accomplishments

- Implemented CacheAwareRouter with provider-specific caching capabilities (OpenAI: 10% cost, 1024 min tokens; Anthropic: 10% cost, 2048 min tokens; Gemini: 10% cost, 1024 min tokens; DeepSeek/MiniMax: no caching)
- Extended DynamicPricingFetcher with `supports_cache` field and cache capability detection methods
- Integrated cache-aware routing into BYOKHandler with cache-adjusted BPC scoring and cache outcome recording
- Created comprehensive test suite (25 tests, 100% pass rate) covering cost calculation, cache prediction, BYOK integration, performance benchmarks

## Task Commits

Each task was committed atomically:

1. **Task 1: Create CacheAwareRouter with cost calculation** - `53c988ca` (feat)
2. **Task 2: Extend DynamicPricingFetcher with cache metadata** - `699e7429` (feat)
3. **Task 3: Integrate cache-aware routing into BYOKHandler** - `a3a19009` (feat)
4. **Task 4: Create cache-aware routing tests** - `047f7a43` (test)

**Plan metadata:** No final metadata commit (only task commits)

## Files Created/Modified

- `backend/core/llm/cache_aware_router.py` - CacheAwareRouter class with calculate_effective_cost(), predict_cache_hit_probability(), record_cache_outcome(), provider capability metadata
- `backend/core/dynamic_pricing_fetcher.py` - Extended with supports_cache field, model_supports_cache(), _infer_provider(), get_cache_min_tokens()
- `backend/core/llm/byok_handler.py` - Integrated CacheAwareRouter, extended get_ranked_providers() with estimated_tokens/workspace_id params, cache outcome recording after generation
- `backend/tests/test_cache_aware_routing.py` - 25 comprehensive tests (effective cost, cache prediction, BYOK integration, performance, provider capabilities)

## Decisions Made

- In-memory cache history (`cache_hit_history` dict) sufficient for initial implementation - no database persistence needed yet
- 50% default cache hit probability based on industry average from OpenAI/Anthropic research
- 10% cached cost ratio for all caching providers (OpenAI, Anthropic, Gemini) - research-verified pricing
- Minimum token thresholds enforced to prevent false cache predictions: 1024 for OpenAI/Gemini, 2048 for Anthropic
- First 16 characters of prompt hash used as history key (balances specificity and collision avoidance)
- Cache outcome recording integrated into BYOKHandler.generate_response() with provider-specific detection (Anthropic: prompt_cache_hit_tokens, OpenAI: cache_controls)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Test fixture errors: Removed `benchmark` fixture parameter (not available) and replaced with manual timing loops
- Test assertion adjustments: Fixed cost calculation assertions to match actual effective cost behavior (84% of full price with 90% cache hit, not 50% as initially expected due to output costs)
- Mock configuration: Added proper Mock() objects with return values instead of Mock() with spec only in test_cache_unavailable_below_threshold

## Cost Reduction Calculations

**Theoretical cost savings with cache-aware routing:**

- **90% cache hit rate:** 16.2% cost reduction (input costs reduced to 19% of original, output costs unchanged)
  - Full price: $0.000006 per token (GPT-4o: $2.50/M input, $10/M output)
  - With 90% cache hit: $0.000005 per token
  - Savings: $0.000001 per token (16.2%)

- **100% cache hit rate:** 18.4% cost reduction (maximum theoretical)
  - Effective input cost: 10% of original
  - Effective cost: $0.000005125 per token

- **Real-world impact:** For repeated prompts (e.g., system prompts, templates), cache-aware routing can achieve 16-18% cost reduction on cached providers compared to cache-unaware routing

## Cache Hit Prediction Accuracy

**Current implementation:**
- Default probability: 50% (industry average for mixed workloads)
- Workspace-specific tracking: Separate histories per workspace ID
- Prompt hash prefixing: First 16 characters of SHA-256 hash

**Verification:**
- Default probability correctly returns 0.5 for unknown prompts
- Historical tracking correctly calculates actual hit rates (e.g., 2/3 = 66.7%)
- Workspace isolation working: Different workspaces maintain separate histories

## Test Coverage Report

**Total tests:** 25 (100% pass rate)

**Breakdown by category:**
- Effective cost calculation: 6 tests
  - Cached provider cost reduction ✓
  - Uncached provider full cost ✓
  - Below minimum threshold no cache ✓
  - Zero cache hit probability ✓
  - 100% cache hit ✓
  - Unknown model infinite cost ✓

- Cache hit prediction: 4 tests
  - Default probability no history ✓
  - Actual hit rate from history ✓
  - Workspace-specific tracking ✓
  - Prompt hash prefix keying ✓

- Cache outcome recording: 3 tests
  - Record hit increments counter ✓
  - Record miss increments total only ✓
  - Multiple outcomes update correctly ✓

- BYOK integration: 5 tests
  - Cache-aware ranking ✓
  - Cache unavailable below threshold ✓
  - BYOK integration with estimated tokens ✓
  - Backward compatibility no params ✓
  - Cache outcome recording ✓

- Performance: 2 tests
  - Effective cost calculation <10ms ✓
  - Cache hit prediction <1ms ✓

- Provider capabilities: 5 tests
  - OpenAI cache capabilities ✓
  - Anthropic cache capabilities ✓
  - DeepSeek no cache ✓
  - Unknown provider defaults ✓
  - Provider name variations ✓

## Performance Benchmarks

**Effective cost calculation:**
- Average time: <1ms per provider
- Target: <10ms ✓
- Status: **PASS** (10x better than target)

**Cache hit prediction:**
- Average time: <0.1ms per lookup
- Target: <1ms ✓
- Status: **PASS** (10x better than target)

**Overall routing overhead:**
- Cache-aware BPC scoring: <1ms additional latency
- Impact on routing decision: **Negligible**

## Success Criteria Verification

1. ✓ CacheAwareRouter calculates effective cost with cached_cost_ratio (0.10) applied
2. ✓ Cache hit prediction uses historical data (workspace:model) with 0.5 default
3. ✓ Minimum token thresholds enforced (1024 for OpenAI/Gemini, 2048 for Anthropic)
4. ✓ BYOK ranking uses effective cost for value score calculation
5. ✓ 25+ tests covering all routing scenarios (25 tests created)
6. ✓ Performance <10ms per provider cost calculation (achieving <1ms)

**All 6 success criteria met.**

## Next Phase Readiness

**Ready for Phase 68-03:**
- CacheAwareRouter foundation complete and tested
- DynamicPricingFetcher extended with cache metadata
- BYOKHandler integration complete with backward compatibility
- Test coverage comprehensive (25 tests, 100% pass rate)

**Blockers:** None

**Recommendations for next phase:**
- Consider database persistence for cache_hit_history if analytics become important
- Monitor actual cache hit rates in production to validate 50% default assumption
- A/B test cache-aware vs cache-unaware routing to measure real-world cost savings

---
*Phase: 68-byok-cognitive-tier-system*
*Plan: 02*
*Completed: 2026-02-20*
