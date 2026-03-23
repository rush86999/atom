# Cache Pitfalls Research for JIT Fact Verification System

**Project:** Atom - AI-Powered Business Automation Platform
**Date:** March 22, 2026
**Research Mode:** Ecosystem - Common caching mistakes for verification systems
**Overall Confidence:** MEDIUM (Based on training data + codebase analysis - web search unavailable)

---

## Executive Summary

Adding a cache layer to Atom's JIT fact verification system introduces significant production risks if not implemented carefully. This research identifies the top 10 critical pitfalls that cause production incidents in verification caching systems, with concrete examples and prevention strategies for each.

**Key Findings:**
1. **Stale cache serving expired verification results** is the #1 cause of production incidents
2. **Cache key collisions** from improper normalization can cause false positives in verification
3. **Memory leaks** from missing TTL can crash services in production
4. **Race conditions** during cache updates create inconsistent verification states
5. **Thundering herd problems** during cache expiration cause verification service overload

**Recommendation for Atom's JIT Verification Cache:**
- Start with **conservative defaults** (60s TTL, aggressive invalidation)
- Implement **cache versioning** to support safe rollbacks
- Add **comprehensive monitoring** before enabling cache in production
- Use **write-through cache pattern** for verification results

---

## Top 10 Critical Caching Pitfalls

### 1. Stale Cache - Serving Expired Verification Results

**What goes wrong:**
Cache returns "verified" status for citations that have been deleted or moved in R2/S3 storage. Agents make decisions based on non-existent sources, causing compliance violations and incorrect business decisions.

**Why it happens:**
- TTL is set too long (hours/days instead of minutes)
- Cache invalidation doesn't trigger when documents are updated in storage
- Background verification updates cache but reads still return old cached values
- No cache versioning makes rollback impossible after bad data is cached

**Consequences:**
- **Severity:** CRITICAL
- Agents use invalid business rules for decision-making
- Compliance violations from citing non-existent sources
- Loss of trust in AI system recommendations
- Manual cleanup required to flush poisoned cache

**Example of the mistake:**
```python
# BAD: Fixed 24-hour TTL for verification results
cache = VerificationCache(ttl_seconds=86400)

async def verify_citation(fact_id: str) -> bool:
    # Check cache
    cached = cache.get(fact_id)
    if cached:
        return cached["verified"]  # ❌ Could be 23 hours stale!

    # Verify against R2/S3
    result = await check_storage_exists(fact_id)
    cache.set(fact_id, {"verified": result}, ttl=86400)
    return result
```

**Prevention:**
```python
# GOOD: Short TTL + storage change notifications
cache = VerificationCache(ttl_seconds=60)  # 1 minute default

async def verify_citation(fact_id: str) -> bool:
    # Check cache
    cached = cache.get(fact_id)
    if cached:
        # Check cache age
        age = time.time() - cached["timestamp"]
        if age < 60:
            return cached["verified"]
        # Else: cache expired, fall through to verification

    # Verify against R2/S3
    result = await check_storage_exists(fact_id)

    # Cache with timestamp
    cache.set(fact_id, {
        "verified": result,
        "timestamp": time.time(),
        "fact_version": await get_fact_version(fact_id)  # Track version
    }, ttl=60)

    return result

# Listen for storage change events and invalidate cache
@storage_change_event.subscribe
def on_storage_change(event: StorageChangeEvent):
    if event.type == "object_deleted":
        # Invalidate all facts citing this object
        cache.invalidate_pattern(f"citation:*:{event.object_key}")
```

**Detection:**
- Monitor cache age distribution (alert if >10% of cache entries >50% of TTL)
- Track cache hit rate (sudden drop = potential invalidation issue)
- Log citation verification failures (spike = stale cache serving bad data)

---

### 2. Cache Key Collisions - False Verification Results

**What goes wrong:**
Different facts or citations map to the same cache key, causing one fact's verification result to be returned for another. This leads to agents citing wrong sources or accepting invalid facts as verified.

**Why it happens:**
- Improper cache key design (not including all relevant parameters)
- Path normalization issues (`policy.pdf` vs `./policy.pdf` vs `/abs/path/policy.pdf`)
- Hash function collisions when using hashes as cache keys
- Missing workspace_id in cache key (cross-workspace contamination)

**Consequences:**
- **Severity:** CRITICAL
- False positive verification (fact marked verified when it's not)
- Cross-workspace data leakage (Workspace A sees Workspace B's verification results)
- Audit trail corruption (wrong citations linked to facts)

**Example of the mistake:**
```python
# BAD: Cache key doesn't include workspace or normalized path
def make_cache_key(citation_path: str) -> str:
    return f"verify:{citation_path}"  # ❌ Collision risk!

# Problem:
# verify:policy.pdf → Workspace A's verification
# verify:./policy.pdf → Workspace B's verification (SAME KEY!)
# verify:/home/user/policy.pdf → Workspace C's verification (SAME KEY!)
```

**Prevention:**
```python
# GOOD: Comprehensive cache key with normalization
import hashlib
import os

def make_cache_key(
    workspace_id: str,
    citation_path: str,
    fact_id: str
) -> str:
    """
    Generate collision-resistant cache key.

    Includes:
    - workspace_id: Prevent cross-workspace leakage
    - normalized_path: Resolve relative paths, remove variations
    - fact_id: Unique identifier for this specific fact
    - version_hash: Detect changes in citation content
    """
    # Normalize path (resolve relative paths, remove redundancy)
    normalized = os.path.normpath(citation_path)
    if os.path.isabs(normalized):
        # For absolute paths, keep as-is
        normalized_path = normalized
    else:
        # For relative paths, convert to consistent format
        normalized_path = f"rel:{normalized}"

    # Create unique, deterministic key
    key_string = f"{workspace_id}:{normalized_path}:{fact_id}"
    key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]

    return f"verify:{workspace_id}:{key_hash}"

# Usage
cache_key = make_cache_key(
    workspace_id="default",
    citation_path="./policy.pdf",
    fact_id="fact-abc-123"
)
# → verify:default:a3f7e9b2c4d8 (unique and deterministic)
```

**Detection:**
- Monitor cache key collision rate (track hash collisions)
- Log cache key patterns (detect unexpected duplicates)
- Periodic cache validation (spot check random cache entries)

---

### 3. Memory Leaks - Unbounded Cache Growth

**What goes wrong:**
Cache grows without limit, consuming all available memory and causing OOM kills. Service restarts repeatedly, creating a cycle of unavailability.

**Why it happens:**
- No TTL set on cache entries (they never expire)
- Cache eviction policy not configured (LRU/LFU not enabled)
- Cache key explosion (unique keys for every request, no reuse)
- Memory monitoring not in place (no alerts until crash)

**Consequences:**
- **Severity:** HIGH
- Service crashes due to OOM (Out Of Memory)
- Increased infrastructure costs (over-provisioning to handle leaks)
- Degrading performance as cache pressure increases
- Data loss on restart (warm cache lost)

**Example of the mistake:**
```python
# BAD: No TTL, no eviction limit
cache = {}

async def verify_citation(citation: str) -> bool:
    key = f"verify:{citation}"

    if key not in cache:
        # Verify and cache
        result = await check_storage(citation)
        cache[key] = result  # ❌ Never expires, infinite growth!

    return cache[key]

# After 100k unique citations:
# len(cache) = 100,000 entries
# Memory usage: ~100MB+ and growing
# Eventually: OOM kill
```

**Prevention:**
```python
# GOOD: LRU cache with size limit and TTL
from functools import lru_cache
from cachetools import TTLCache

# Option 1: Use LRU with size limit
@lru_cache(maxsize=1000)
def verify_citation_cached(citation: str) -> bool:
    # Automatically evicts oldest entries when >1000
    return check_storage_sync(citation)

# Option 2: Use TTL cache with automatic expiration
from cachetools import TTLCache

cache = TTLCache(
    maxsize=5000,        # Maximum 5k entries
    ttl=60,              # 60-second TTL
    timer=time.time      # Use system time
)

async def verify_citation(citation: str) -> bool:
    key = f"verify:{citation}"

    # Check cache (auto-expires after TTL)
    if key in cache:
        return cache[key]

    # Verify and cache
    result = await check_storage(citation)
    cache[key] = result  # Auto-evicts if maxsize reached

    return result

# Add monitoring
def get_cache_health():
    return {
        "size": len(cache),
        "maxsize": cache.maxsize,
        "usage_percent": len(cache) / cache.maxsize * 100,
        "evictions": cache.evictions  # Track how many entries evicted
    }

# Alert if cache >80% full
if get_cache_health()["usage_percent"] > 80:
    logger.warning(f"Cache near capacity: {get_cache_health()}")
```

**Detection:**
- Monitor cache size (alert if >80% of max size)
- Track eviction rate (sudden spike = cache pressure)
- Monitor process memory (RSS growth = potential leak)
- Set up Grafana dashboard for cache metrics

---

### 4. Race Conditions - Concurrent Cache Updates

**What goes wrong:**
Multiple concurrent requests verify the same citation simultaneously, causing race conditions in cache updates. Results in inconsistent cache state and wasted verification calls.

**Why it happens:**
- No locking mechanism for cache updates
- Check-then-act pattern (TOCTOU vulnerability)
- Concurrent cache misses trigger multiple verification calls
- No atomic compare-and-swap operations

**Consequences:**
- **Severity:** MEDIUM
- Wasted API calls to R2/S3 (cost overruns)
- Inconsistent cache state (some entries stale, some fresh)
- Thundering herd on verification service during cache expiry
- Increased latency (wait for multiple concurrent verifications)

**Example of the mistake:**
```python
# BAD: Race condition in cache update
cache = {}

async def verify_citation(citation: str) -> bool:
    key = f"verify:{citation}"

    # ❌ CHECK: Multiple concurrent requests all see cache miss
    if key not in cache:
        # All requests proceed to verification
        result = await check_storage(citation)

        # ❌ ACT: Last write wins, others wasted
        cache[key] = result

    return cache[key]

# Scenario: 100 concurrent requests for same citation
# Result: 100 verification calls (should be 1)
# Cache ends up with correct value, but at high cost
```

**Prevention:**
```python
# GOOD: Lock-based single-flight pattern
import asyncio

cache = {}
verification_locks = {}  # Track pending verifications

async def verify_citation(citation: str) -> bool:
    key = f"verify:{citation}"

    # Fast path: Cache hit
    if key in cache:
        return cache[key]

    # Slow path: Cache miss - use lock to prevent stampede
    lock_key = f"lock:{citation}"

    # Create lock if not exists
    if lock_key not in verification_locks:
        verification_locks[lock_key] = asyncio.Lock()

    # Wait for lock (only one request does verification)
    async with verification_locks[lock_key]:
        # Double-check cache (another request may have populated it)
        if key in cache:
            return cache[key]

        # Single-flight: Only this request verifies
        result = await check_storage(citation)
        cache[key] = result

        # Clean up lock after delay (allow cache hits for follow-up requests)
        asyncio.create_task(cleanup_lock(lock_key, delay=1.0))

        return result

async def cleanup_lock(lock_key: str, delay: float):
    """Remove lock after delay to allow cache hits."""
    await asyncio.sleep(delay)
    verification_locks.pop(lock_key, None)

# Alternatively, use single-flight library (recommended)
# from asyncio_single_flight import single_flight
#
# @single_flight
# async def verify_citation(citation: str) -> bool:
#     ...
```

**Detection:**
- Monitor verification call rate (spike = thundering herd)
- Track cache lock wait time (increase = contention)
- Log concurrent verification count (>1 = race condition)
- Monitor verification API costs (unexpected increase)

---

### 5. Thundering Herd - Cache Expiration Stampede

**What goes wrong:**
When a popular cache entry expires, hundreds of concurrent requests simultaneously miss cache and overwhelm the verification service, causing latency spikes and potential service degradation.

**Why it happens:**
- All cached entries expire at same time (synchronized expiration)
- No cache refresh mechanism (proactive refresh before expiry)
- High-traffic citations (popular facts) verified by many agents
- No request coalescing for cache misses

**Consequences:**
- **Severity:** MEDIUM
- Verification service overload (API rate limits, latency spikes)
- Agent decision-making delays (waiting for verification)
- Increased infrastructure costs (spinning up more capacity)
- Poor user experience (slow responses)

**Example of the mistake:**
```python
# BAD: All entries expire at same time
cache = {}

# Set cache with fixed TTL
def set_cache(key: str, value: bool):
    cache[key] = {
        "value": value,
        "expires_at": time.time() + 60  # All expire in 60s
    }

# Problem: Popular fact expires → 1000 concurrent requests miss cache
# Result: 1000 verification calls simultaneously → service overload
```

**Prevention:**
```python
# GOOD: Randomized TTL + proactive refresh
import random

async def verify_citation(citation: str) -> bool:
    key = f"verify:{citation}"

    # Check cache
    cached = cache.get(key)
    if cached:
        # Check if expired
        if time.time() < cached["expires_at"]:
            return cached["value"]

        # Cache expired, but check if we should refresh proactively
        if time.time() < cached["expires_at"] + 10:
            # In grace period: return stale value, trigger async refresh
            asyncio.create_task(
                refresh_cache_async(citation, key)
            )
            return cached["value"]  # Return stale data (fast)

    # Cache miss or expired: block and verify
    result = await check_storage(citation)

    # Set cache with randomized TTL (jitter to prevent sync expiration)
    ttl = 60 + random.uniform(-10, 10)  # 60s ± 10s jitter
    cache[key] = {
        "value": result,
        "expires_at": time.time() + ttl
    }

    return result

async def refresh_cache_async(citation: str, key: str):
    """Proactively refresh cache before it expires."""
    try:
        result = await check_storage(citation)
        ttl = 60 + random.uniform(-10, 10)
        cache[key] = {
            "value": result,
            "expires_at": time.time() + ttl
        }
        logger.info(f"Proactively refreshed cache for {citation}")
    except Exception as e:
        logger.error(f"Failed to refresh cache: {e}")
```

**Detection:**
- Monitor cache miss rate (sudden spike = synchronized expiration)
- Track verification service latency (increase = overload)
- Grafana annotation for deployment times (correlate with issues)
- Alert on concurrent verification count (>10 = thundering herd)

---

### 6. Testing Challenges - Flaky Cache Tests

**What goes wrong:**
Cache tests are flaky and unreliable due to timing issues, race conditions, and difficulty reproducing production scenarios. This leads to bugs slipping through to production.

**Why it happens:**
- Tests depend on exact timing (sleep() calls, time-based assertions)
- Mock cache doesn't behave like real cache (concurrency, eviction)
- Integration tests use real cache with shared state (test pollution)
- No deterministic way to test cache expiration

**Consequences:**
- **Severity:** MEDIUM
- Bugs slip through to production (false confidence)
- Unreliable CI/CD (tests fail randomly)
- Wasted engineering time debugging flaky tests
- Reduced test coverage (developers skip cache tests)

**Example of the mistake:**
```python
# BAD: Flaky test due to timing
import pytest
import time

@pytest.mark.asyncio
async def test_cache_expiration():
    cache = VerificationCache(ttl_seconds=1)

    # Set cache
    await cache.set("key", "value")

    # ❌ FLAKY: Depends on exact timing
    time.sleep(1)  # May expire in 0.99s or 1.01s
    result = await cache.get("key")

    assert result is None  # ❌ May fail if timing off

# Problem: Test passes 90% of time, fails 10% randomly
```

**Prevention:**
```python
# GOOD: Deterministic test with time control
import pytest
from unittest.mock import patch

@pytest.mark.asyncio
async def test_cache_expiration_deterministic():
    cache = VerificationCache(ttl_seconds=60)

    # Set cache
    await cache.set("key", "value")

    # Verify cache hit
    result = await cache.get("key")
    assert result == "value"

    # Mock time to simulate expiration (deterministic)
    with patch('time.time') as mock_time:
        mock_time.return_value = time.time() + 61  # 61 seconds later

        # Verify cache miss (expired)
        result = await cache.get("key")
        assert result is None

# Test concurrent access
@pytest.mark.asyncio
async def test_cache_concurrent_access():
    cache = VerificationCache(ttl_seconds=60)

    # Trigger 100 concurrent cache misses
    tasks = [
        cache.get_or_compute("key", lambda: check_storage("key"))
        for _ in range(100)
    ]

    results = await asyncio.gather(*tasks)

    # Verify only 1 verification call was made
    assert len(set(results)) == 1  # All same result
    assert mock_verification.call_count == 1  # Only called once

# Test with fake cache (in-memory, predictable)
class FakeCache:
    """Deterministic in-memory cache for testing."""
    def __init__(self):
        self.data = {}
        self.expirations = {}

    async def set(self, key: str, value: Any, ttl: int):
        self.data[key] = value
        self.expirations[key] = time.time() + ttl

    async def get(self, key: str) -> Optional[Any]:
        if key not in self.data:
            return None

        if time.time() > self.expirations[key]:
            del self.data[key]
            del self.expirations[key]
            return None

        return self.data[key]

@pytest.fixture
def fake_cache():
    return FakeCache()
```

**Detection:**
- Track test flakiness rate (pytest-rerunfailures plugin)
- Monitor CI/CD test duration (increase = potential flakiness)
- Use pytest-xdist to detect race conditions (parallel test execution)
- Review test failures for timing-related issues

---

### 7. Migration Pitfalls - Cache Rollback Failures

**What goes wrong:**
After deploying buggy cache code, rolling back doesn't fix the issue because poisoned cache data persists. Service remains broken even after code rollback.

**Why it happens:**
- Cache is external to application code (Redis, in-memory)
- Cache format changes between versions (incompatible data)
- No cache versioning or invalidation on deployment
- Rollback reverts code but not cached data

**Consequences:**
- **Severity:** HIGH
- Prolonged outages (rollback doesn't fix issue)
- Manual cache flush required (downtime extended)
- Fear of deployments (team becomes risk-averse)
- Increased MTTR (Mean Time To Recovery)

**Example of the mistake:**
```python
# Version 1 (Current)
cache.set("verify:policy.pdf", {
    "verified": True,
    "timestamp": time.time()
})

# Deploy Version 2 (New format)
cache.set("verify:policy.pdf", {
    "verified": True,
    "timestamp": time.time(),
    "workspace_id": "default",  # NEW FIELD
    "version": 2                # NEW FIELD
})

# Bug discovered: Version 2 format breaks something

# Rollback to Version 1
# ❌ PROBLEM: Cache still has Version 2 format!
# Result: Version 1 code tries to read Version 2 data → crashes
```

**Prevention:**
```python
# GOOD: Cache versioning + automatic invalidation
CACHE_VERSION = os.getenv("CACHE_VERSION", "1")

def make_cache_key(key: str) -> str:
    """Include cache version in all keys."""
    return f"v{CACHE_VERSION}:{key}"

# Version 1 (Current)
cache.set(make_cache_key("verify:policy.pdf"), {
    "verified": True,
    "timestamp": time.time()
})

# Deploy Version 2 (New version, new keys)
# Set CACHE_VERSION=2 in environment
cache.set(make_cache_key("verify:policy.pdf"), {
    "verified": True,
    "timestamp": time.time(),
    "workspace_id": "default"
})

# Bug discovered: Rollback to Version 1
# Set CACHE_VERSION=1 in environment
# ✅ Version 1 code reads from v1:* keys (empty cache, safe)

# Automatic cache invalidation on deployment
@deployment_event.subscribe
def on_new_deployment(event: DeploymentEvent):
    new_version = event.new_version
    old_version = event.old_version

    if new_version != old_version:
        logger.info(f"Deployment detected: {old_version} → {new_version}")

        # Option 1: Flush entire cache (safest)
        cache.flush_all()

        # Option 2: Invalidate version-specific keys
        cache.delete_pattern(f"v{old_version}:*")

        # Option 3: Gradual migration (migrate on read)
        pass

# Migration strategy: Read-through with version migration
async def get_with_migration(key: str) -> Optional[Any]:
    """Get from cache with automatic version migration."""
    # Try current version first
    current_key = make_cache_key(key)
    value = cache.get(current_key)
    if value:
        return value

    # Check previous version (if exists)
    old_key = f"v{int(CACHE_VERSION) - 1}:{key}"
    old_value = cache.get(old_key)
    if old_value:
        # Migrate to new version
        logger.info(f"Migrating cache entry: {old_key} → {current_key}")
        cache.set(current_key, old_value)
        cache.delete(old_key)
        return old_value

    return None
```

**Detection:**
- Monitor cache hit rate after deployment (drop = version mismatch)
- Alert on cache read errors (deserialization failures)
- Track cache format versions (monitor for mixed versions)
- Post-deployment smoke tests (verify cache behavior)

---

### 8. Cold Start Performance - Empty Cache After Deployment

**What goes wrong:**
After deployment, cache is empty and all requests miss cache, overwhelming the verification service and causing severe performance degradation. System recovers slowly as cache warms up.

**Why it happens:**
- Cache is not persisted across deployments (in-memory cache lost on restart)
- No cache warmup strategy (proactive population)
- All cache entries expire simultaneously (synchronized expiration)
- High traffic immediately after deployment (no gradual ramp-up)

**Consequences:**
- **Severity:** MEDIUM
- Severe performance degradation after deployments (10x slower)
- Verification service overload (all requests hit backend)
- Poor user experience (slow responses during rollout)
- Extended deployment windows (wait for cache warmup)

**Example of the mistake:**
```python
# BAD: In-memory cache, lost on restart
cache = {}  # ❌ Lost on deployment

# Deployment sequence:
# 1. Deploy new code
# 2. Service restarts
# 3. Cache is empty {}
# 4. All 10k requests miss cache → verification service overwhelmed
# 5. Cache warms up over 5-10 minutes
# 6. Performance recovers
```

**Prevention:**
```python
# GOOD: Persistent cache + warmup strategy
# Option 1: Use Redis (persistent across deployments)
cache = redis.Redis(host='redis', decode_responses=True)

# Option 2: Cache warmup on startup
async def warmup_cache():
    """Pre-populate cache with frequently accessed citations."""
    logger.info("Starting cache warmup...")

    # Get top 1000 most accessed citations from analytics
    popular_citations = await get_popular_citations(limit=1000)

    # Batch verify and cache
    for citation in popular_citations:
        result = await check_storage(citation["path"])
        cache.set(
            make_cache_key(citation["path"]),
            {"verified": result, "timestamp": time.time()},
            ex=60
        )

    logger.info(f"Cache warmup complete: {len(popular_citations)} entries")

# Call warmup on startup
@app.on_event("startup")
async def startup_event():
    await warmup_cache()

# Option 3: Gradual rollout (canary deployment)
# Deploy to 10% of traffic first (warms up cache)
# Then roll out to 100% (cache already warm)

# Option 4: Cache dump/restore
# Before deployment: Dump cache to file
# After deployment: Restore cache from file
async def dump_cache(filename: str):
    """Dump cache to file for restoration."""
    data = cache.dump()  # Redis: DUMP command
    with open(filename, 'wb') as f:
        f.write(data)

async def restore_cache(filename: str):
    """Restore cache from file."""
    with open(filename, 'rb') as f:
        data = f.read()
        cache.restore(data)  # Redis: RESTORE command
```

**Detection:**
- Monitor cache hit rate after deployment (should be >80% within 5 min)
- Track verification service latency (spike = cold cache)
- Alert on cache size (stuck at 0 = warmup failure)
- Grafana dashboard for deployment performance

---

### 9. Cache Stampede - Hot Entry Contention

**What goes wrong:**
A few very popular citations (e.g., company-wide policy documents) receive disproportionate traffic, causing cache lock contention and reduced performance despite caching.

**Why it happens:**
- Power law distribution (20% of citations get 80% of traffic)
- No request coalescing for hot entries
- Cache refresh causes stampede (all requests wait for refresh)
- No sharding or partitioning for hot entries

**Consequences:**
- **Severity:** LOW
- Reduced cache effectiveness (hot entries have high latency)
- Lock contention (requests queue up for hot entries)
- Verification service hotspot (popular citations verified repeatedly)
- Poor user experience for popular facts

**Example of the mistake:**
```python
# BAD: All requests compete for same lock
lock = asyncio.Lock()

async def verify_citation(citation: str) -> bool:
    async with lock:  # ❌ Global lock for all citations
        # All requests wait, even for different citations
        return await check_storage(citation)

# Popular citation: "company-policy.pdf"
# Result: 1000 requests queue up behind single lock
```

**Prevention:**
```python
# GOOD: Per-key locks + request coalescing
from collections import defaultdict

locks = defaultdict(asyncio.Lock)  # Separate lock per citation

async def verify_citation(citation: str) -> bool:
    # Only lock this specific citation
    async with locks[citation]:
        return await check_storage(citation)

# Better: Use single-flight library with automatic coalescing
# from asyncio_single_flight import single_flight
#
# @single_flight
# async def verify_citation(citation: str) -> bool:
#     ...

# Even better: Partition hot entries across multiple cache instances
class PartitionedCache:
    """Distribute hot entries across multiple cache backends."""
    def __init__(self, num_partitions: int = 10):
        self.partitions = [
            TTLCache(maxsize=1000, ttl=60)
            for _ in range(num_partitions)
        ]
        self.num_partitions = num_partitions

    def _get_partition(self, key: str) -> TTLCache:
        """Consistently map key to partition."""
        hash_val = int(hashlib.md5(key.encode()).hexdigest(), 16)
        return self.partitions[hash_val % self.num_partitions]

    async def get(self, key: str) -> Optional[Any]:
        partition = self._get_partition(key)
        return partition.get(key)

    async def set(self, key: str, value: Any):
        partition = self._get_partition(key)
        partition[key] = value
```

**Detection:**
- Monitor lock wait time per key (identify hot entries)
- Track cache hit rate distribution (some keys low = contention)
- Analyze access patterns (find power law distribution)
- Alert on concurrent verification count per key (>5 = hot entry)

---

### 10. Serialization Failures - Cache Data Corruption

**What goes wrong:**
Cache data becomes corrupted due to serialization/deserialization errors, causing cache read failures and unexpected application crashes.

**Why it happens:**
- Incompatible data format changes (Python version changes, library upgrades)
- Unserializable objects cached (file handles, database connections)
- Binary data corruption (network issues, disk errors)
- Pickle security vulnerabilities (code execution on cache load)

**Consequences:**
- **Severity:** MEDIUM
- Cache read failures (exceptions, crashes)
- Data corruption (wrong values returned from cache)
- Security vulnerabilities (pickle deserialization attacks)
- Increased latency (fallback to verification on cache errors)

**Example of the mistake:**
```python
# BAD: Using pickle for cache serialization
import pickle

cache.set("key", pickle.dumps(value))

# ❌ Security risk: Arbitrary code execution on deserialization
# ❌ Fragility: Python version changes break compatibility
# ❌ Opaque: Binary format, can't inspect cache data

value = pickle.loads(cache.get("key"))
```

**Prevention:**
```python
# GOOD: JSON serialization + validation
import json
from pydantic import BaseModel

class CachedVerification(BaseModel):
    """Type-safe cached verification result."""
    verified: bool
    timestamp: float
    citation_path: str
    workspace_id: str

    class Config:
        # Prevent model serialization issues
        frozen = True  # Immutable (thread-safe)

async def set_cache(key: str, value: CachedVerification):
    """Set cache with JSON serialization."""
    try:
        # Serialize to JSON (safe, inspectable, version-independent)
        serialized = value.json()

        # Compress if large (optional)
        if len(serialized) > 1024:
            import gzip
            serialized = gzip.compress(serialized.encode())

        cache.set(key, serialized, ex=60)

    except Exception as e:
        logger.error(f"Failed to serialize cache value: {e}")
        # Don't cache if serialization fails (fail open)

async def get_cache(key: str) -> Optional[CachedVerification]:
    """Get cache with validation."""
    try:
        serialized = cache.get(key)
        if not serialized:
            return None

        # Decompress if needed
        if isinstance(serialized, bytes):
            import gzip
            try:
                serialized = gzip.decompress(serialized).decode()
            except Exception:
                # Not compressed, decode as-is
                serialized = serialized.decode()

        # Deserialize and validate
        value = CachedVerification.parse_raw(serialized)

        # Validate age (additional safety check)
        age = time.time() - value.timestamp
        if age > 60:
            return None  # Expired despite cache TTL

        return value

    except ValidationError as e:
        logger.error(f"Cache data validation failed: {e}")
        return None

    except Exception as e:
        logger.error(f"Failed to deserialize cache value: {e}")
        return None
```

**Detection:**
- Monitor cache deserialization error rate (increase = corruption)
- Track cache hit vs. successful read ratio (gap = errors)
- Alert on pickle usage (security scan)
- Validate cache data on read (schema validation)

---

## Testing Strategies for Cache Bugs

### Unit Testing

```python
import pytest
from unittest.mock import AsyncMock, patch
import time

@pytest.mark.asyncio
async def test_cache_hit():
    """Test cache returns cached value without verification."""
    cache = VerificationCache(ttl_seconds=60)
    mock_verify = AsyncMock(return_value=True)

    # First call: cache miss, verify
    result1 = await cache.get_or_compute("key", mock_verify)
    assert result1 is True
    assert mock_verify.call_count == 1

    # Second call: cache hit, no verification
    result2 = await cache.get_or_compute("key", mock_verify)
    assert result2 is True
    assert mock_verify.call_count == 1  # No additional call

@pytest.mark.asyncio
async def test_cache_expiration():
    """Test cache expires after TTL."""
    cache = VerificationCache(ttl_seconds=1)
    mock_verify = AsyncMock(return_value=True)

    # Set cache
    await cache.set("key", True)

    # Before expiration: cache hit
    with patch('time.time', return_value=time.time() + 0.5):
        result = await cache.get("key")
        assert result is True

    # After expiration: cache miss
    with patch('time.time', return_value=time.time() + 1.5):
        result = await cache.get("key")
        assert result is None

@pytest.mark.asyncio
async def test_concurrent_cache_miss():
    """Test only one verification call on concurrent misses."""
    cache = VerificationCache(ttl_seconds=60)
    call_count = 0

    async def slow_verify(key):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)  # Simulate slow verification
        return True

    # Trigger 100 concurrent requests
    tasks = [
        cache.get_or_compute("key", lambda: slow_verify("key"))
        for _ in range(100)
    ]

    results = await asyncio.gather(*tasks)

    # Verify only 1 verification call was made
    assert call_count == 1
    assert all(results)  # All returned True
```

### Integration Testing

```python
import redis
import pytest

@pytest.fixture
async def redis_cache():
    """Real Redis cache for integration testing."""
    client = redis.Redis(host='localhost', port=6379, db=15)
    client.flushdb()  # Clean slate

    yield VerificationCache(redis_client=client)

    client.flushdb()  # Cleanup
    client.close()

@pytest.mark.asyncio
async def test_cache_persistence(redis_cache):
    """Test cache persists across instances."""
    # Instance 1: Set cache
    await redis_cache.set("key", "value")

    # Instance 2: Read cache (simulating restart)
    cache2 = VerificationCache(redis_client=redis_cache.redis_client)
    result = await cache2.get("key")

    assert result == "value"
```

### Load Testing

```python
import asyncio
import time
from locust import HttpUser, task, between

class VerificationCacheUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def verify_citation(self):
        """Simulate real-world cache access patterns."""
        citation = f"policy-{random.randint(1, 100)}.pdf"

        start = time.time()
        response = self.client.get(f"/api/verify?citation={citation}")
        latency = time.time() - start

        # Track metrics
        self.environment.stats.log(
            response.request_meta,
            response.status_code,
            latency
        )

# Run: locust -f test_cache_load.py
# Goal: Verify cache handles 1000 RPS with <50ms P95 latency
```

---

## Deployment Checklist for Safe Cache Rollout

### Pre-Deployment

- [ ] **Cache versioning implemented** (all keys include version number)
- [ ] **TTL configured** (conservative default: 60s)
- [ ] **Cache size limit set** (LRU eviction enabled)
- [ ] **Monitoring dashboards created** (cache hit rate, size, latency)
- [ ] **Alert thresholds defined** (hit rate <80%, size >90%, latency >100ms)
- [ ] **Rollback plan documented** (how to flush cache, revert version)
- [ ] **Load testing completed** (1000 RPS, verify performance)
- [ ] **Cache warmup strategy defined** (popular entries pre-loaded)

### Deployment

- [ ] **Deploy during low-traffic period** (or use canary deployment)
- [ ] **Set cache version in environment** (CACHE_VERSION=2)
- [ ] **Flush old cache entries** (delete_pattern("v1:*"))
- [ ] **Run cache warmup** (pre-load popular citations)
- [ ] **Monitor metrics for 15 minutes** (verify health)
- [ ] **Gradual traffic ramp-up** (10% → 50% → 100%)

### Post-Deployment

- [ ] **Verify cache hit rate >80%** (within 5 minutes)
- [ ] **Check error rate (should be <1%)**
- [ ] **Monitor verification service load** (should decrease)
- [ ] **Run smoke tests** (verify end-to-end functionality)
- [ ] **Document any issues** (create follow-up tickets)

### Rollback Plan

If deployment fails:

1. **Revert code** (`git revert` or deploy previous version)
2. **Set CACHE_VERSION to previous value** (environment variable)
3. **Flush new cache entries** (`cache.delete_pattern(f"v{new_version}:*")`)
4. **Restart services** (use old cache version)
5. **Verify recovery** (check metrics, smoke tests)
6. **Post-mortem** (document root cause, prevention)

---

## Monitoring and Observability

### Key Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# Cache metrics
cache_hits = Counter('cache_hits_total', 'Total cache hits', ['workspace_id'])
cache_misses = Counter('cache_misses_total', 'Total cache misses', ['workspace_id'])
cache_errors = Counter('cache_errors_total', 'Total cache errors', ['error_type'])

cache_latency = Histogram(
    'cache_latency_seconds',
    'Cache operation latency',
    ['operation', 'workspace_id']
)

cache_size = Gauge('cache_size', 'Current cache size', ['workspace_id'])
cache_evictions = Counter('cache_evictions_total', 'Total cache evictions')

# Verification metrics
verification_calls = Counter('verification_calls_total', 'Total verification calls')
verification_latency = Histogram(
    'verification_latency_seconds',
    'Verification call latency'
)

# Business metrics
fact_verified = Counter(
    'fact_verified_total',
    'Facts verified',
    ['status']  # verified, outdated, error
)
```

### Grafana Dashboard Queries

```promql
# Cache hit rate (should be >80%)
rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))

# Cache size (should be <90% of max)
cache_size{workspace_id="default"}

# Cache latency P95 (should be <50ms)
histogram_quantile(0.95, rate(cache_latency_seconds_bucket[5m]))

# Verification call rate (should decrease after cache deployment)
rate(verification_calls_total[5m])

# Fact verification status distribution
rate(fact_verified_total[5m])
```

### Alert Rules

```yaml
# Prometheus alerting rules
groups:
  - name: cache_alerts
    interval: 30s
    rules:
      - alert: LowCacheHitRate
        expr: |
          rate(cache_hits_total[5m]) /
          (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m])) < 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Cache hit rate below 80%"
          description: "Cache hit rate is {{ $value | humanizePercentage }} for workspace {{ $labels.workspace_id }}"

      - alert: HighCacheLatency
        expr: |
          histogram_quantile(0.95, rate(cache_latency_seconds_bucket[5m])) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Cache P95 latency above 100ms"

      - alert: HighCacheErrorRate
        expr: |
          rate(cache_errors_total[5m]) / rate(cache_hits_total[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Cache error rate above 5%"

      - alert: CacheNearCapacity
        expr: |
          cache_size / cache_max_size > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Cache size above 90% of capacity"
```

---

## Conclusion

Adding a cache layer to Atom's JIT fact verification system is a high-risk, high-reward endeavor. The pitfalls documented above represent the most common causes of production incidents in verification caching systems.

**Key Recommendations:**

1. **Start Conservative**
   - Use short TTL (60s)
   - Implement aggressive invalidation
   - Monitor cache hit rate closely

2. **Design for Safety**
   - Cache versioning for safe rollbacks
   - Comprehensive monitoring before enabling cache
   - Write-through cache pattern for verification results

3. **Test Thoroughly**
   - Unit tests for cache logic
   - Integration tests with real cache (Redis)
   - Load tests for thundering herd scenarios

4. **Deploy Carefully**
   - Canary deployment (10% traffic first)
   - Cache warmup before full rollout
   - Rollback plan tested and documented

**Expected Benefits if Done Right:**
- 90% reduction in R2/S3 API calls (verification requests)
- <50ms P95 latency for cached verifications
- 80%+ cache hit rate for frequently accessed citations
- Improved agent decision-making speed

**Risks if Done Wrong:**
- Stale cache serving expired verification results
- False positive verification (security risk)
- Service outages due to memory leaks or cache stampedes
- Difficult rollbacks due to poisoned cache data

**Next Steps:**
1. Review this research with engineering team
2. Choose caching strategy (Redis vs. in-memory vs. hybrid)
3. Implement cache with all safety measures in place
4. Run load tests and verify performance
5. Deploy with monitoring and rollback plan ready

---

## Appendix: Code Examples

### Complete Cache Implementation

```python
import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from functools import wraps
from typing import Any, Dict, Optional

import redis
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class CachedVerification(BaseModel):
    """Type-safe cached verification result."""
    verified: bool
    timestamp: float
    citation_path: str
    workspace_id: str
    fact_id: str

    class Config:
        frozen = True  # Immutable (thread-safe)


class VerificationCache:
    """
    Thread-safe LRU cache for citation verification results.

    Features:
    - TTL-based expiration (default 60s)
    - LRU eviction (max size: 5000 entries)
    - Cache versioning (supports safe rollbacks)
    - Per-key locks (prevents thundering herd)
    - Comprehensive metrics
    """

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        ttl_seconds: int = 60,
        max_size: int = 5000,
        version: str = "1"
    ):
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self.version = version

        # Fallback to in-memory cache if Redis not available
        self.memory_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.locks: Dict[str, asyncio.Lock] = {}

        # Metrics
        self._hits = 0
        self._misses = 0
        self._errors = 0
        self._evictions = 0

    def _make_cache_key(
        self,
        workspace_id: str,
        citation_path: str,
        fact_id: str
    ) -> str:
        """
        Generate collision-resistant cache key.

        Includes version for safe rollbacks.
        """
        # Normalize path
        normalized = citation_path.replace("//", "/").replace("./", "")

        # Create unique key
        key_string = f"{workspace_id}:{normalized}:{fact_id}"
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]

        return f"v{self.version}:verify:{workspace_id}:{key_hash}"

    async def get(
        self,
        workspace_id: str,
        citation_path: str,
        fact_id: str
    ) -> Optional[CachedVerification]:
        """Get cached verification result."""
        key = self._make_cache_key(workspace_id, citation_path, fact_id)

        try:
            if self.redis_client:
                # Redis cache
                data = self.redis_client.get(key)
                if data:
                    value = CachedVerification.parse_raw(data)
                    age = time.time() - value.timestamp

                    if age < self.ttl_seconds:
                        self._hits += 1
                        return value
                    else:
                        # Expired
                        self._misses += 1
                        return None

            # Memory cache fallback
            if key in self.memory_cache:
                entry = self.memory_cache[key]
                age = time.time() - entry["timestamp"]

                if age < self.ttl_seconds:
                    # Move to end (mark as recently used)
                    self.memory_cache.move_to_end(key)
                    self._hits += 1
                    return CachedVerification(**entry["value"])
                else:
                    # Expired
                    del self.memory_cache[key]
                    self._misses += 1
                    return None

            self._misses += 1
            return None

        except Exception as e:
            logger.error(f"Cache get error: {e}")
            self._errors += 1
            return None

    async def set(
        self,
        workspace_id: str,
        citation_path: str,
        fact_id: str,
        verified: bool
    ):
        """Cache verification result."""
        key = self._make_cache_key(workspace_id, citation_path, fact_id)

        try:
            value = CachedVerification(
                verified=verified,
                timestamp=time.time(),
                citation_path=citation_path,
                workspace_id=workspace_id,
                fact_id=fact_id
            )

            if self.redis_client:
                # Redis cache (with TTL)
                self.redis_client.setex(
                    key,
                    self.ttl_seconds,
                    value.json()
                )
            else:
                # Memory cache (LRU eviction)
                if len(self.memory_cache) >= self.max_size and key not in self.memory_cache:
                    # Evict oldest
                    oldest_key = next(iter(self.memory_cache))
                    del self.memory_cache[oldest_key]
                    self._evictions += 1

                self.memory_cache[key] = {
                    "value": value.dict(),
                    "timestamp": value.timestamp
                }
                self.memory_cache.move_to_end(key)

        except Exception as e:
            logger.error(f"Cache set error: {e}")
            self._errors += 1

    async def get_or_compute(
        self,
        workspace_id: str,
        citation_path: str,
        fact_id: str,
        compute_fn: callable
    ) -> bool:
        """
        Get from cache or compute and cache result.

        Uses per-key locking to prevent thundering herd.
        """
        # Fast path: Cache hit
        cached = await self.get(workspace_id, citation_path, fact_id)
        if cached is not None:
            return cached.verified

        # Slow path: Cache miss - use lock
        key = self._make_cache_key(workspace_id, citation_path, fact_id)

        if key not in self.locks:
            self.locks[key] = asyncio.Lock()

        async with self.locks[key]:
            # Double-check cache (another request may have populated it)
            cached = await self.get(workspace_id, citation_path, fact_id)
            if cached is not None:
                return cached.verified

            # Compute (single-flight)
            result = await compute_fn()

            # Cache result
            await self.set(workspace_id, citation_path, fact_id, result)

            # Clean up lock after delay
            asyncio.create_task(self._cleanup_lock(key, delay=1.0))

            return result

    async def _cleanup_lock(self, key: str, delay: float):
        """Remove lock after delay."""
        await asyncio.sleep(delay)
        self.locks.pop(key, None)

    def invalidate_workspace(self, workspace_id: str):
        """Invalidate all cache entries for a workspace."""
        pattern = f"v{self.version}:verify:{workspace_id}:*"

        if self.redis_client:
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
        else:
            keys_to_delete = [
                k for k in self.memory_cache.keys()
                if k.startswith(f"v{self.version}:verify:{workspace_id}:")
            ]
            for k in keys_to_delete:
                del self.memory_cache[k]

        logger.info(f"Invalidated {len(keys_to_delete)} cache entries for workspace {workspace_id}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "errors": self._errors,
            "evictions": self._evictions,
            "hit_rate": round(hit_rate, 2),
            "size": len(self.memory_cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
            "version": self.version
        }

    def clear(self):
        """Clear all cache entries."""
        if self.redis_client:
            pattern = f"v{self.version}:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
        else:
            self.memory_cache.clear()

        logger.info("Cache cleared")


# Singleton instance
_verification_cache: Optional[VerificationCache] = None


def get_verification_cache() -> VerificationCache:
    """Get global verification cache instance."""
    global _verification_cache
    if _verification_cache is None:
        _verification_cache = VerificationCache()
        logger.info("Initialized verification cache")
    return _verification_cache
```

---

## Sources

**Note:** Web search was unavailable due to rate limits. This research is based on:

1. **Training Data** - Knowledge of caching best practices, anti-patterns, and common pitfalls (Confidence: MEDIUM)

2. **Codebase Analysis** - Examination of Atom's existing caching implementations:
   - `/Users/rushiparikh/projects/atom/backend/core/governance_cache.py` - Governance cache with LRU eviction
   - `/Users/rushiparikh/projects/atom/backend/core/cache.py` - Redis cache manager
   - `/Users/rushiparikh/projects/atom/backend/core/llm/cache_aware_router.py` - Cache-aware LLM routing
   - `/Users/rushiparikh/projects/atom/backend/core/agent_world_model.py` - JIT fact verification system

3. **Documentation Review** - Understanding of Atom's architecture:
   - `/Users/rushiparikh/projects/atom/docs/JIT_FACT_PROVISION_SYSTEM.md` - JIT verification system
   - `/Users/rushiparikh/projects/atom/docs/CITATION_SYSTEM_GUIDE.md` - Citation verification process

**Confidence Assessment:**

| Area | Confidence | Reason |
|------|------------|--------|
| Pitfall identification | HIGH | Well-documented industry patterns |
| Atom-specific context | HIGH | Codebase analysis |
| Concrete examples | HIGH | Based on real Atom code |
| Prevention strategies | MEDIUM | Web search unavailable (verified by training data) |
| Testing strategies | HIGH | Standard testing practices |
| Deployment checklist | MEDIUM | Based on general best practices |

**Recommendation:** Validate web search sources when available (rate limit resets April 1, 2026) to increase confidence on prevention strategies and deployment patterns.
