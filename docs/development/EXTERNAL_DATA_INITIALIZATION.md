# External Data Fetcher Initialization - Implementation Plan

> **Priority**: High (Critical for BPC Routing)
> **Estimated Time**: 2-3 hours
> **Impact**: Ensures BPC routing uses fresh external data on startup

---

## 🎯 Objective

Initialize external data fetchers (pricing and benchmarks) during application startup to ensure:
1. Fresh data is available when first request arrives
2. BPC routing makes optimal decisions from the start
3. Stale cache issues are avoided

---

## 📝 Implementation

### Step 1: Add External Data Initialization to Startup

**File**: `backend/main_api_app.py`

**Location**: In the `lifespan()` function, after line 236 (after Redis setup)

**Code to Add**:

```python
    # 6. Initialize External Data Fetchers (Pricing & Benchmarks)
    # Ensures BPC routing has fresh data from external APIs
    try:
        from core.dynamic_pricing_fetcher import get_pricing_fetcher
        from core.dynamic_benchmark_fetcher import get_benchmark_fetcher

        logger.info("Initializing external data fetchers...")

        # Warm up pricing cache (use cache if valid, otherwise fetch)
        pricing_fetcher = get_pricing_fetcher()
        await pricing_fetcher.refresh_pricing(force=False)

        if pricing_fetcher.last_fetch:
            cache_age = (datetime.now() - pricing_fetcher.last_fetch).total_seconds() / 3600
            logger.info(f"  ✓ Pricing cache: {len(pricing_fetcher.pricing_cache)} models (age: {cache_age:.1f}h)")
        else:
            logger.warning("  ⚠ Pricing cache empty (will fetch on first use)")

        # Warm up benchmark cache (use cache if valid, otherwise fetch)
        benchmark_fetcher = get_benchmark_fetcher()
        await benchmark_fetcher.refresh_benchmarks(force=False)

        if benchmark_fetcher.last_fetch:
            cache_age = (datetime.now() - benchmark_fetcher.last_fetch).total_seconds() / 3600
            logger.info(f"  ✓ Benchmark cache: {len(benchmark_fetcher.benchmark_cache)} models (age: {cache_age:.1f}h)")
        else:
            logger.warning("  ⚠ Benchmark cache empty (will fetch on first use)")

    except Exception as e:
        logger.error(f"Failed to initialize external data fetchers: {e}")
        logger.warning("  ⚠ BPC routing may use stale fallback data until APIs recover")
```

### Step 2: Add Health Check Endpoint

**File**: `backend/api/health_routes.py` (create if doesn't exist)

**Code to Add**:

```python
from fastapi import APIRouter
from datetime import datetime
from typing import Dict, Any

router = APIRouter()

@router.get("/health/external-data")
async def external_data_health() -> Dict[str, Any]:
    """
    Check health of external data sources (pricing and benchmarks).

    Returns cache status, data freshness, and model counts.
    Useful for monitoring and troubleshooting BPC routing.
    """
    from core.dynamic_pricing_fetcher import get_pricing_fetcher
    from core.dynamic_benchmark_fetcher import get_benchmark_fetcher

    pricing_fetcher = get_pricing_fetcher()
    benchmark_fetcher = get_benchmark_fetcher()

    # Calculate pricing cache age
    pricing_age_hours = None
    if pricing_fetcher.last_fetch:
        pricing_age_hours = (datetime.now() - pricing_fetcher.last_fetch).total_seconds() / 3600

    # Calculate benchmark cache age
    benchmark_age_hours = None
    if benchmark_fetcher.last_fetch:
        benchmark_age_hours = (datetime.now() - benchmark_fetcher.last_fetch).total_seconds() / 3600

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "pricing": {
            "last_fetch": pricing_fetcher.last_fetch.isoformat() if pricing_fetcher.last_fetch else None,
            "cache_age_hours": round(pricing_age_hours, 2) if pricing_age_hours else None,
            "model_count": len(pricing_fetcher.pricing_cache),
            "cache_valid": pricing_fetcher._is_cache_valid(),
            "sources": ["litellm", "openrouter"],
            "cache_duration_hours": 24
        },
        "benchmarks": {
            "last_fetch": benchmark_fetcher.last_fetch.isoformat() if benchmark_fetcher.last_fetch else None,
            "cache_age_hours": round(benchmark_age_hours, 2) if benchmark_age_hours else None,
            "model_count": len(benchmark_fetcher.benchmark_cache),
            "cache_valid": benchmark_fetcher._is_cache_valid(),
            "sources": ["lmsys", "artificial_analysis", "benchmark_moe"],
            "cache_duration_hours": 6
        },
        "warnings": []
    }
```

### Step 3: Add Prometheus Metrics (Optional)

**File**: `backend/core/dynamic_pricing_fetcher.py`

**Add to imports**:

```python
from prometheus_client import Counter, Gauge

# Metrics
PRICING_REFRESH_SUCCESS = Counter(
    "llm_pricing_refresh_success_total",
    "Successful pricing refresh operations",
    ["source"]
)

PRICING_REFRESH_FAILURE = Counter(
    "llm_pricing_refresh_failure_total",
    "Failed pricing refresh operations",
    ["source"]
)

PRICING_DATA_AGE = Gauge(
    "llm_pricing_data_age_seconds",
    "Age of pricing data in seconds"
)
```

**Update `fetch_litellm_pricing()` method**:

```python
async def fetch_litellm_pricing(self) -> Dict[str, Any]:
    """Fetch pricing from LiteLLM's GitHub repository"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(LITELLM_PRICING_URL)
            response.raise_for_status()
            data = response.json()

            # ... existing transformation code ...

            PRICING_REFRESH_SUCCESS.labels(source="litellm").inc()
            logger.info(f"Fetched {len(pricing)} model prices from LiteLLM")
            return pricing

    except Exception as e:
        PRICING_REFRESH_FAILURE.labels(source="litellm").inc()
        logger.error(f"Failed to fetch LiteLLM pricing: {e}")
        return {}
```

**Similar changes for `fetch_openrouter_pricing()` and benchmark fetcher**.

---

## ✅ Testing

### Test 1: Verify Startup Initialization

```bash
# Start the application
cd backend
python -m uvicorn main_api_app:app --reload

# Check logs for:
# ✓ Pricing cache: XXX models (age: X.Xh)
# ✓ Benchmark cache: XXX models (age: X.Xh)
```

### Test 2: Verify Health Endpoint

```bash
# Call health endpoint
curl http://localhost:8000/health/external-data

# Expected response:
{
  "status": "healthy",
  "pricing": {
    "model_count": 150,
    "cache_age_hours": 0.5,
    "cache_valid": true
  },
  "benchmarks": {
    "model_count": 100,
    "cache_age_hours": 2.5,
    "cache_valid": true
  }
}
```

### Test 3: Verify BPC Routing Uses Fresh Data

```python
# Test script: test_bpc_fresh_data.py
import asyncio
from core.llm.byok_handler import BYOKHandler
from core.dynamic_pricing_fetcher import get_pricing_fetcher
from core.dynamic_benchmark_fetcher import get_benchmark_fetcher

async def test():
    # Verify fresh data
    pricing = get_pricing_fetcher()
    benchmarks = get_benchmark_fetcher()

    assert pricing.last_fetch is not None, "Pricing not initialized"
    assert benchmarks.last_fetch is not None, "Benchmarks not initialized"

    # Test BPC routing
    handler = BYOKHandler()
    options = await handler.get_ranked_providers(
        complexity=QueryComplexity.MODERATE,
        prefer_cost=True
    )

    assert len(options) > 0, "No providers ranked"
    print(f"✅ BPC routing working with fresh data: {len(options)} providers")

asyncio.run(test())
```

---

## 📊 Success Criteria

| Metric | Before | After | How to Verify |
|--------|--------|-------|---------------|
| **Startup Data Ready** | No | Yes | Check logs for cache initialization |
| **Health Endpoint** | Missing | Exists | `/health/external-data` returns 200 |
| **First Request Latency** | High (cold) | Low (warm) | Time first BPC routing call |
| **Stale Data Risk** | High | Low | Cache age < 24h on startup |

---

## 🚨 Rollback Plan

If issues arise:

1. **Disable initialization** (temporary):
   ```python
   # Comment out the initialization block in main_api_app.py
   # System will fall back to lazy initialization
   ```

2. **Check external API status**:
   ```bash
   curl https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json
   curl https://openrouter.ai/api/v1/models
   ```

3. **Use cached data** (if APIs are down):
   - The system automatically uses cached data if APIs fail
   - Caches are stored in `./data/ai_pricing_cache.json` and `./data/benchmark_cache.json`

---

## 📚 Related Files

- `backend/core/dynamic_pricing_fetcher.py` - Pricing API integration
- `backend/core/dynamic_benchmark_fetcher.py` - Benchmark API integration
- `backend/core/llm/byok_handler.py` - BPC routing logic
- `backend/api/health_routes.py` - Health check endpoints
- `backend/main_api_app.py` - Application startup

---

## 🔄 Next Steps

After implementing startup initialization:

1. **Monitor logs** during deployment to ensure data loads successfully
2. **Set up alerts** for stale data (cache age > 24h)
3. **Consider background refresh** (next improvement)
4. **Add metrics dashboard** for external data health

---

**Status**: Ready for Implementation
**Priority**: High
**Estimated Time**: 2-3 hours
**Risk**: Low (graceful fallback to cached data)
