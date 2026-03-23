# Architecture Patterns

**Domain:** Verification Result Caching
**Researched:** March 22, 2026

## Recommended Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Verification Cache Layer                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌────────────────┐     ┌────────────────┐     ┌────────────────┐ │
│  │  API Request   │────▶│  @cached_      │────▶│  Storage       │ │
│  │  verify_       │     │  verification  │     │  .check_       │ │
│  │  citation()    │     │  decorator     │     │  exists()      │ │
│  └────────────────┘     └────────────────┘     └────────────────┘ │
│                                 │                       │          │
│                                 ▼                       ▼          │
│                    ┌────────────────┐     ┌────────────────┐      │
│                    │  Hot Cache     │     │  R2/S3         │      │
│                    │  (Memory)      │     │  (200-500ms)   │      │
│                    │  <1ms          │     └────────────────┘      │
│                    └───────┬────────┘              │              │
│                            │                       │              │
│                            │ Miss                  │ Result       │
│                            ▼                       ▼              │
│                    ┌────────────────┐     ┌────────────────┐      │
│                    │  Cold Cache    │◀────┤  Cache Result  │      │
│                    │  (PostgreSQL)  │     │  Storage       │      │
│                    │  <50ms         │     └────────────────┘      │
│                    └────────────────┘                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **@cached_verification** | Decorator that intercepts verification calls | VerificationCacheService, storage.check_exists() |
| **VerificationCacheService** | Manages cache lookups, TTL, statistics | PostgreSQL, in-memory cache, Redis (optional) |
| **Hot Cache** | In-memory LRU cache for ultra-fast lookups | VerificationCacheService only |
| **Cold Cache** | PostgreSQL table for persistent cache storage | VerificationCacheService only |
| **Background Worker** | Pre-warms cache on application startup | VerificationCacheService, WorldModelService |

### Data Flow

**Current Flow (No Cache):**
```
verify_citation(fact_id)
  └─▶ Get fact from LanceDB
  └─▶ For each citation:
      └─▶ storage.check_exists(key)  ← 200-500ms per citation
      └─▶ Update verification_status
  └─▶ Return results
```

**Proposed Flow (With Cache):**
```
verify_citation(fact_id)  [decorated]
  └─▶ Get fact from LanceDB
  └─▶ For each citation:
      ├─▶ Check hot cache (memory)
      │   └─▶ HIT → Return cached result (<1ms)
      │   └─▶ MISS → Check cold cache (PostgreSQL)
      │       └─▶ HIT → Return cached result (<50ms), populate hot cache
      │       └─▶ MISS → storage.check_exists(key) (200-500ms)
      │           └─▶ Store in cold cache
      │           └─▶ Store in hot cache
  └─▶ Return results
```

## Patterns to Follow

### Pattern 1: Decorator Wrapper (Recommended)
**What:** Non-invasive caching via decorator pattern
**When:** Adding caching to existing verify_citation() function
**Example:**
```python
from functools import wraps
from core.verification_cache_service import get_verification_cache

def cached_verification(ttl_seconds: int = 900):
    """
    Decorator to cache citation verification results.

    Args:
        ttl_seconds: Time-to-live for cache entries (default: 15 minutes)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_verification_cache()

            # Extract citation from kwargs
            fact_id = kwargs.get('fact_id')
            fact = await wm.get_fact_by_id(fact_id)

            if not fact or not fact.citations:
                return await func(*args, **kwargs)

            # Check cache for each citation
            cached_results = []
            all_cached = True

            for citation in fact.citations:
                cache_key = _make_cache_key(citation)

                # Try hot cache first
                result = await cache.get_hot(cache_key)
                if result is not None:
                    cached_results.append(result)
                    continue

                # Try cold cache
                result = await cache.get_cold(cache_key)
                if result is not None:
                    await cache.set_hot(cache_key, result)  # Warm hot cache
                    cached_results.append(result)
                    continue

                # Cache miss - fall through to original function
                all_cached = False
                break

            if all_cached:
                # All citations were cached
                return _build_cached_response(cached_results)

            # Fall back to original verification
            result = await func(*args, **kwargs)

            # Store in cache
            for citation_result in result['citations']:
                cache_key = _make_cache_key(citation_result['citation'])
                await cache.set_hot(cache_key, citation_result)
                await cache.set_cold(cache_key, citation_result, ttl=ttl_seconds)

            return result

        return wrapper
    return decorator
```

### Pattern 2: LRU Cache with TTL (GovernanceCache Pattern)
**What:** Thread-safe in-memory cache with expiration
**When:** Implementing hot cache layer
**Example:**
```python
from collections import OrderedDict
import threading
import time

class VerificationHotCache:
    """
    Thread-safe LRU cache for verification results.

    Follows GovernanceCache pattern from core/governance_cache.py
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 900):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

        # OrderedDict for LRU eviction (thread-safe operations)
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached verification result."""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]
            cached_at = entry.get("cached_at", 0)
            age_seconds = time.time() - cached_at

            # Check if expired
            if age_seconds > self.ttl_seconds:
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (mark as recently used)
            self._cache.move_to_end(key)
            self._hits += 1

            return entry["data"]

    async def set(self, key: str, value: Dict[str, Any]):
        """Set cached verification result."""
        with self._lock:
            # Evict oldest if at capacity
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
                self._evictions += 1

            self._cache[key] = {
                "data": value,
                "cached_at": time.time()
            }
```

### Pattern 3: FastAPI Lifespan Background Worker
**What:** Async cache warming on application startup
**When:** Pre-populating cache with "verified" facts
**Example:**
```python
from contextlib import asynccontextmanager
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    logger.info("Starting verification cache warming...")

    # Start background cache warming (non-blocking)
    cache_warming_task = asyncio.create_task(warm_verification_cache())

    # Continue with other startup tasks
    yield

    # --- SHUTDOWN ---
    # Cancel cache warming if still running
    cache_warming_task.cancel()
    try:
        await cache_warming_task
    except asyncio.CancelledError:
        pass

async def warm_verification_cache():
    """
    Background worker to pre-warm verification cache.

    Loads all "verified" facts and caches their citations.
    Runs asynchronously without blocking startup.
    """
    try:
        from core.agent_world_model import WorldModelService
        from core.verification_cache_service import get_verification_cache

        wm = WorldModelService(workspace_id="default")
        cache = get_verification_cache()

        # Get all verified facts
        facts = await wm.list_all_facts(status="verified", limit=1000)

        logger.info(f"Pre-warming cache with {len(facts)} verified facts...")

        for fact in facts:
            for citation in fact.citations:
                # Pre-populate cache with "verified" status
                cache_key = _make_cache_key(citation)
                await cache.set_hot(cache_key, {
                    "citation": citation,
                    "exists": True,
                    "source": "R2"
                })

        logger.info(f"Cache warming complete: {len(facts)} facts cached")

    except Exception as e:
        logger.error(f"Cache warming failed: {e}")
        # Graceful degradation - application continues without cache warming
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Blocking Startup with Cache Warming
**What:** Synchronous cache loading in lifespan blocks application startup
**Why bad:** Prevents application from serving requests until cache is loaded
**Instead:** Use async background worker with `asyncio.create_task()`

### Anti-Pattern 2: Cache-Only Verification
**What:** Skipping storage.check_exists() if cache exists
**Why bad:** Stale cache data causes false positives
**Instead:** Always allow fallback to storage.check_exists() on miss or suspicion

### Anti-Pattern 3: Global Cache without Workspace Isolation
**What:** Single cache key without workspace_id
**Why bad:** Cross-workspace data leakage, security violation
**Instead:** Include workspace_id in cache key: `f"{workspace_id}:{citation}"`

## Scalability Considerations

| Concern | At 100 users | At 10K users | At 1M users |
|---------|--------------|--------------|-------------|
| **Hot cache size** | 1,000 entries (~100KB) | 10,000 entries (~1MB) | Redis cluster (distributed) |
| **Cold cache DB** | PostgreSQL table <1GB | Partition by workspace_id | Shard by workspace_id |
| **Cache warming time** | <5 seconds | <30 seconds | Batch loading with pagination |
| **Hit rate target** | >80% | >90% | >95% |

## Database Schema

**Table: `fact_verification_cache`**

```sql
CREATE TABLE fact_verification_cache (
    id SERIAL PRIMARY KEY,
    workspace_id VARCHAR(255) NOT NULL,
    citation_key TEXT NOT NULL,
    is_valid BOOLEAN NOT NULL,
    source VARCHAR(50),  -- 'R2', 'Local', 'Legacy'
    cached_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT unique_citation_per_workspace UNIQUE (workspace_id, citation_key)
);

CREATE INDEX idx_fact_verification_cache_workspace ON fact_verification_cache(workspace_id);
CREATE INDEX idx_fact_verification_cache_expires ON fact_verification_cache(expires_at);

-- Partitioning strategy for 1M+ users (future)
-- CREATE TABLE fact_verification_cache_2026_03 PARTITION OF fact_verification_cache
-- FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
```

**Fields:**
- `citation_key`: Hash or normalized citation string (e.g., `sha256(citation)`)
- `expires_at`: TTL-based expiration (NOW() + INTERVAL '15 minutes')
- `is_valid`: Result of storage.check_exists()
- `source`: Storage backend (for debugging)

## Integration Points

### 1. API Layer Integration
**File:** `backend/api/admin/business_facts_routes.py:336`

```python
@router.post("/{fact_id}/verify-citation")
@cached_verification(ttl_seconds=900)  # Add decorator
async def verify_citation(
    fact_id: str,
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))
):
    # Existing implementation unchanged
    # Decorator handles caching transparently
```

### 2. Invalidation Triggers
**File:** `backend/api/admin/business_facts_routes.py:231` (upload endpoint)
**File:** `backend/api/admin/business_facts_routes.py:212` (delete endpoint)

```python
@router.post("/upload")
async def upload_and_extract(...):
    # ... existing upload logic ...
    # After successful upload, invalidate related cache entries
    await cache.invalidate_by_document(s3_uri)
```

```python
@router.delete("/{fact_id}")
async def delete_fact(fact_id: str, ...):
    # ... existing delete logic ...
    # Invalidate cache for this fact's citations
    fact = await wm.get_fact_by_id(fact_id)
    for citation in fact.citations:
        await cache.invalidate(citation)
```

### 3. Monitoring Integration
**File:** `backend/core/monitoring.py`

```python
from prometheus_client import Counter, Histogram

cache_hits = Counter('verification_cache_hits_total', 'Total cache hits', ['layer'])
cache_misses = Counter('verification_cache_misses_total', 'Total cache misses', ['layer'])
cache_latency = Histogram('verification_cache_latency_seconds', 'Cache lookup latency', ['layer'])
```

## Sources

- HIGH confidence: Existing codebase patterns
  - `backend/core/governance_cache.py` (LRU cache with TTL)
  - `backend/core/cache.py` (Redis + in-memory fallback)
  - `backend/main_api_app.py` (lifespan events)
  - `backend/api/admin/business_facts_routes.py` (verification flow)
- MEDIUM confidence: Standard async patterns (asyncio.create_task for background workers)
- LOW confidence: Scalability estimates (no production load data available)
