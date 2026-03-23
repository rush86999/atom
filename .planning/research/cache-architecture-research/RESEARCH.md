# Research Summary: Verification Result Caching for World Model JIT Fact Provision

**Domain:** AI Business Automation Platform - Fact Verification System
**Researched:** March 22, 2026
**Overall confidence:** HIGH (based on codebase analysis, no external search available)

## Executive Summary

Atom's World Model system currently performs real-time R2/S3 storage checks for every citation verification, resulting in 200-500ms latency per citation. This research analyzes the existing JIT fact provision architecture and recommends introducing a **Verification Cache Service** using a hybrid storage approach (in-memory hot cache + PostgreSQL cold cache) with background cache warming via FastAPI lifespan events.

The existing system has well-defined integration points:
- **Verification flow**: `verify_citation()` in `business_facts_routes.py` (lines 336-407)
- **Storage checks**: `storage.check_exists()` in `storage.py` (lines 56-63)
- **World Model**: `agent_world_model.py` manages facts in LanceDB with metadata
- **Existing cache patterns**: `GovernanceCache` (LRU with TTL, 60s default) and `RedisCacheService`

Key findings:
1. **Current bottleneck**: Each verification makes synchronous S3/R2 API calls via `storage.check_exists()`
2. **No caching layer**: Verification results are not persisted, forcing repeated checks for same citations
3. **Batch operations**: `CitationVerificationBatch` model exists but is not yet utilized for caching
4. **Clean integration point**: Decorator pattern on `verify_citation()` or new service wrapper
5. **Infrastructure ready**: FastAPI lifespan events available, PostgreSQL connection pooling configured, Redis optional

## Key Findings

**Stack:**
- Python 3.11+ with FastAPI (async/await throughout)
- SQLAlchemy 2.0 with PostgreSQL (production) or SQLite (development)
- LanceDB for vector storage (business_facts table)
- R2/S3 via boto3 for document storage
- Existing `GovernanceCache` class provides LRU cache pattern to follow

**Architecture:**
- Current flow: Fact → Citation → storage.check_exists() → 200ms+ latency
- Recommended: Fact → Citation → VerificationCacheService → <5ms hit, 200ms miss
- Background worker: Async cache warming on startup via FastAPI lifespan

**Critical pitfall:**
- **Cache invalidation**: Documents can be deleted from R2/S3, causing stale "verified" status
- **Solution**: Short TTL (15 minutes) + manual invalidation on document upload/delete

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Phase 1: Database Schema & Core Service** - Foundation for cache storage
   - Addresses: Create `fact_verification_cache` table in PostgreSQL
   - Addresses: Implement `VerificationCacheService` with get/set/invalidate methods
   - Avoids: Breaking existing verification flow (add cache alongside, not replace)

2. **Phase 2: Integration & Decorator Pattern** - Non-invasive integration
   - Addresses: Create `@cached_verification` decorator for `verify_citation()`
   - Addresses: Fallback to direct storage check if cache fails
   - Avoids: Modifying LanceDB or WorldModel core logic

3. **Phase 3: Background Cache Warming** - Performance optimization
   - Addresses: Add cache pre-warming to FastAPI lifespan (startup event)
   - Addresses: Async worker for loading "verified" facts without blocking startup
   - Avoids: Blocking application startup if pre-warming fails (graceful degradation)

4. **Phase 4: Monitoring & Invalidation** - Production readiness
   - Addresses: Cache hit/miss metrics via Prometheus
   - Addresses: Invalidation triggers on document upload/delete
   - Avoids: Stale data from deleted documents

**Phase ordering rationale:**
- Database schema first (foundational, cannot be changed easily)
- Service integration second (adds value without background complexity)
- Background worker third (optimization, not required for correctness)
- Monitoring fourth (production hardening)

**Research flags for phases:**
- Phase 1: Standard database patterns, unlikely to need research
- Phase 2: Review existing `GovernanceCache` implementation for consistency
- Phase 3: LOW confidence - FastAPI lifespan patterns vary, may need testing for async worker startup
- Phase 4: Standard observability, unlikely to need research

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Analyzed actual codebase (Python 3.11, FastAPI, SQLAlchemy 2.0) |
| Features | HIGH | Existing code shows clear verification flow and cache patterns |
| Architecture | HIGH | Mapped actual integration points (files, line numbers, class methods) |
| Pitfalls | MEDIUM | Cache invalidation is standard challenge, TTL strategy is proven |

## Gaps to Address

- **External search unavailable**: Web search quota exhausted, relied on codebase analysis
- **No benchmark data**: Current verification performance documented but not measured in test environment
- **Background worker patterns**: FastAPI lifespan async worker startup may need empirical testing
- **Cache size estimation**: Unknown number of unique citations in production (affects table sizing)
