# Feature Landscape

**Domain:** Verification Result Caching for World Model
**Researched:** March 22, 2026

## Table Stakes

Features users expect. Missing = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Cached verification lookups** | Current 200ms+ latency per citation is painful | Low | Standard caching pattern, reduce to <5ms |
| **Cache expiration** | Prevents stale data from deleted documents | Low | TTL-based expiration (15 minutes recommended) |
| **Graceful fallback** | System must work if cache fails | Medium | Fallback to direct storage.check_exists() |
| **Cache statistics** | Monitor hit rate, validate effectiveness | Low | Track hits/misses/evictions |
| **Invalidation on change** | Documents uploaded/deleted must invalidate cache | Medium | Trigger on POST /upload and DELETE /{fact_id} |

## Differentiators

Features that set product apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Background cache warming** | Pre-populate cache on startup, eliminate cold start | Medium | Use FastAPI lifespan events |
| **Hybrid storage (hot + cold)** | Balance speed (memory) with persistence (database) | High | Hot cache: <1ms, Cold cache: <50ms |
| **Batch pre-verification** | Verify all "verified" facts in background on startup | High | Leverage CitationVerificationBatch model |
| **Distributed cache support** | Redis support for multi-instance deployments | Medium | Optional, uses existing RedisCacheService |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Infinite cache TTL** | Stale data when documents deleted | Use 15-minute TTL with manual invalidation |
| **Synchronous cache warming** | Blocks application startup | Async background worker with graceful degradation |
| **Cache-only verification** | Breaks if cache is wrong | Always fallback to storage.check_exists() on miss |
| **Complex cache eviction** | LRU is sufficient | Don't implement LFU, ARC, or other complex algorithms |

## Feature Dependencies

```
Database Schema → Core Service → Integration → Background Worker → Monitoring
```

1. **Database Schema** (Foundation)
   - PostgreSQL table: `fact_verification_cache`
   - Columns: citation_key, is_valid, expires_at, workspace_id

2. **Core Service** (Depends on: Database)
   - VerificationCacheService class
   - Methods: get(), set(), invalidate(), get_stats()

3. **Integration** (Depends on: Core Service)
   - Decorator: @cached_verification
   - Applied to: verify_citation() in business_facts_routes.py

4. **Background Worker** (Depends on: Integration)
   - Cache warming in FastAPI lifespan
   - Load all "verified" facts into cache on startup

5. **Monitoring** (Depends on: All above)
   - Prometheus metrics: cache_hits, cache_misses, cache_hit_rate
   - Health check: /health/cache-verification

## MVP Recommendation

**Phase 1 (MVP):** In-memory cache with simple decorator

Prioritize:
1. In-memory cache (Python dict + LRU)
2. Decorator wrapper on verify_citation()
3. 15-minute TTL
4. Graceful fallback to storage.check_exists()
5. Basic hit/miss statistics

Defer:
- Background cache warming (Phase 3)
- PostgreSQL cold cache (Phase 2+)
- Redis distributed cache (Phase 4)
- Batch pre-verification (Phase 3)

**Rationale:**
- In-memory cache provides 90% of value with 10% of complexity
- Existing `GovernanceCache` pattern can be copied
- Reduces latency from 200ms to <5ms immediately
- No database schema changes required

## Sources

- HIGH confidence: Existing codebase patterns (GovernanceCache, RedisCacheService)
- MEDIUM confidence: Standard caching best practices (TTL, LRU, graceful fallback)
- docs/JIT_FACT_PROVISION_SYSTEM.md (verification flow documentation)
- docs/CITATION_SYSTEM_GUIDE.md (citation verification API)
