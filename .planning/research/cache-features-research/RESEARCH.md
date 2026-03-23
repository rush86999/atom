# Verification Result Caching: Research Report

**Project:** Atom - Business Policy Citation Verification Caching
**Date:** March 22, 2026
**Status:** MEDIUM Confidence (based on codebase analysis, limited web search due to rate limits)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Cache Key Design](#cache-key-design)
3. [Cache Invalidation Strategies](#cache-invalidation-strategies)
4. [Cache Pre-warming](#cache-pre-warming)
5. [Observability & Metrics](#observability--metrics)
6. [Implementation Examples](#implementation-examples)
7. [References](#references)

---

## Executive Summary

### Problem Statement

The Atom platform's JIT (Just-In-Time) fact verification system performs real-time citation validation by checking R2/S3 storage on every request. According to `docs/CITATION_SYSTEM_GUIDE.md`:

- **Current latency**: ~200ms per citation verification
- **Operation**: `storage.check_exists(key)` → S3 `head_object()` API call
- **Frequency**: Every time a fact is retrieved or verified

This creates unnecessary latency and cost, especially since:
1. Citations rarely change (policy documents are static)
2. Verification is binary (exists/doesn't exist)
3. Same citations are checked repeatedly across fact retrievals

### Research Findings

**Cache Key Design:**
- Use content-addressable keys: `sha256(citation_path)` for deduplication
- Include workspace ID for multi-tenancy: `citation:{workspace_id}:{hash}`
- Optional: Add document version for fine-grained invalidation

**TTL Recommendations:**
- **Standard facts**: 24 hours (policies change infrequently)
- **High-compliance domains** (finance, legal): 4 hours
- **System facts** (internal configs): 1 hour

**Cache Size:**
- Start with 10,000 entries (vs. 1,000 for governance cache)
- LRU eviction when full
- Estimated memory: ~2MB for 10K entries (200 bytes per entry)

**Expected Performance:**
- Cache hit latency: <5ms (vs. 200ms current)
- Target hit rate: >90% (based on governance cache patterns)
- Cost reduction: 80%+ fewer S3 API calls

---

## Cache Key Design

### Recommended Key Structure

Based on analysis of `backend/core/governance_cache.py` and content-addressable storage patterns:

```python
# Primary format (recommended)
cache_key = f"citation:{workspace_id}:{sha256(citation_path)}"

# Alternative with version tracking (for Phase 2)
cache_key = f"citation:{workspace_id}:{doc_version}:{sha256(citation_path)}"

# Bulk verification key (multiple citations for same fact)
cache_key = f"fact:{workspace_id}:{fact_id}"
```

### Key Component Breakdown

| Component | Purpose | Example |
|-----------|---------|---------|
| `citation` | Namespace prefix | Prevents collision with other caches |
| `workspace_id` | Tenant isolation | `default`, `acme-corp`, etc. |
| `doc_version` | Version tracking | `v1`, `v2` (optional, Phase 2) |
| `sha256(citation_path)` | Content addressing | `a1b2c3d4...` (deduplicates identical paths) |

### Handling Duplicate Citations

**Problem**: Same document can be cited by multiple facts with different citation formats:

```
- s3://atom-saas/business_facts/default/abc/policy.pdf
- policy.pdf:p4
- /app/uploads/policy.pdf
```

**Solution**: Normalize before hashing:

```python
def normalize_citation(citation: str) -> str:
    """
    Normalize citation to canonical form for hashing.
    """
    # 1. Extract S3 key if present
    if citation.startswith("s3://"):
        # s3://bucket/key → key
        parts = citation.replace("s3://", "").split("/", 1)
        if len(parts) == 2:
            return parts[1]  # Return just the key

    # 2. Remove page references
    citation = citation.split(":")[0]

    # 3. Remove common prefixes
    for prefix in ["/app/uploads/", "/tmp/", "./"]:
        if citation.startswith(prefix):
            citation = citation[len(prefix):]

    return citation

# Usage
normalized = normalize_citation("s3://atom-saas/business_facts/default/abc/policy.pdf")
# → "business_facts/default/abc/policy.pdf"

cache_key = f"citation:{workspace_id}:{sha256(normalized)}"
```

### Cache Value Structure

```python
{
    "exists": bool,              # Verification result
    "checked_at": datetime,      # When verification occurred
    "citation": str,             # Original citation (for debugging)
    "source": str,               # "R2" or "Local"
    "ttl_seconds": int,          # Configured TTL
    "doc_version": str|None      # Document version (Phase 2)
}
```

---

## Cache Invalidation Strategies

### 1. TTL-Based Expiration (Phase 1)

**Recommended TTLs by Fact Domain:**

| Domain | TTL | Rationale |
|--------|-----|-----------|
| `finance` | 4 hours | High compliance, frequent audits |
| `legal` | 4 hours | Regulatory requirements |
| `hr` | 24 hours | Policy changes infrequent |
| `operations` | 24 hours | SOPs relatively stable |
| `compliance` | 1 hour | May need rapid updates |
| `general` | 24 hours | Default |

**Implementation Pattern** (from `GovernanceCache`):

```python
class CitationVerificationCache:
    def __init__(self, max_size: int = 10000, ttl_seconds: int = 86400):
        self.ttl_seconds = ttl_seconds  # 24 hours default
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, citation_path: str, workspace_id: str) -> Optional[Dict[str, Any]]:
        key = self._make_key(citation_path, workspace_id)

        with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]
            age_seconds = time.time() - entry.get("cached_at", 0)

            # Check TTL
            if age_seconds > self.ttl_seconds:
                del self._cache[key]
                return None

            # LRU: Move to end
            self._cache.move_to_end(key)
            return entry["data"]
```

### 2. Manual Invalidation (Phase 2)

**Trigger Events**:

1. **Document Re-upload**:
   ```
   POST /api/admin/governance/facts/upload
   ```
   → Invalidate all citations pointing to old document version

2. **Fact Update**:
   ```
   PUT /api/admin/governance/facts/{fact_id}
   ```
   → Invalidate citations for modified fact

3. **Manual Admin Flush**:
   ```
   POST /api/admin/governance/facts/cache/flush
   ```
   → Clear entire cache (emergency use)

**Implementation Pattern**:

```python
def invalidate_document(self, document_key: str, workspace_id: str):
    """
    Invalidate all cache entries for a specific document.
    Called when document is re-uploaded or modified.
    """
    with self._lock:
        # Find all keys that reference this document
        normalized_key = normalize_citation(document_key)
        key_hash = sha256(normalized_key).hexdigest()

        # Delete matching entries
        keys_to_delete = [
            k for k in self._cache.keys()
            if f"citation:{workspace_id}:{key_hash}" in k
        ]

        for key in keys_to_delete:
            del self._cache[key]
            self._invalidations += 1

        logger.info(f"Invalidated {len(keys_to_delete)} cache entries for {document_key}")
```

### 3. Version-Based Invalidation (Phase 2+)

**Track Document Versions in Metadata**:

```python
# When storing verification result, include document version
cache_entry = {
    "exists": True,
    "doc_version": "v3",  # Track version
    "checked_at": datetime.now()
}

# When document is updated, increment version
# Then cache entries with old version auto-expire
```

**Required Changes**:

1. Add `doc_version` field to citation metadata (currently not tracked)
2. Modify upload endpoint to assign version numbers
3. Include version in cache key: `citation:{workspace_id}:{version}:{hash}`

### 4. Event-Driven Invalidation (Future)

**Webhook Integration** (R2/S3 event notifications):

```python
# Listen for S3 ObjectCreated events
async def on_s3_object_created(event: dict):
    bucket = event["bucket"]
    key = event["key"]

    # Invalidate old versions of this document
    cache.invalidate_document(key, workspace_id="*")
```

---

## Cache Pre-warming

### Pre-warming Criteria

**1. Most Frequently Accessed Facts**

Track citation check frequency:

```python
# Add frequency tracking to cache
class CitationVerificationCache:
    def __init__(self):
        self._access_count: Dict[str, int] = {}

    def get(self, citation_path: str, workspace_id: str):
        key = self._make_key(citation_path, workspace_id)

        # Track access frequency
        self._access_count[key] = self._access_count.get(key, 0) + 1

        # ... existing cache logic
```

**Pre-warm Top N**:

```python
async def prewarm_frequent_citations(self, workspace_id: str, top_n: int = 100):
    """
    Pre-load frequently accessed citations into cache.
    Call on application startup or periodically.
    """
    # Sort by access frequency
    frequent_keys = sorted(
        self._access_count.items(),
        key=lambda x: x[1],
        reverse=True
    )[:top_n]

    prewarmed = 0
    for key, count in frequent_keys:
        if key in self._cache:
            continue  # Already cached

        # Extract citation from key
        citation_path = key.split(":")[-1]

        # Verify and cache
        result = await self._verify_citation(citation_path, workspace_id)
        if result:
            prewarmed += 1

    logger.info(f"Prewarmed {prewarmed}/{top_n} frequent citations")
```

**2. Recent Facts (Last N Days)**

```python
async def prewarm_recent_facts(self, workspace_id: str, days: int = 7):
    """
    Pre-load citations from facts created in the last N days.
    """
    wm = WorldModelService(workspace_id)
    facts = await wm.list_all_facts(limit=1000)

    # Filter by creation date
    cutoff_date = datetime.now() - timedelta(days=days)
    recent_facts = [
        f for f in facts
        if f.created_at >= cutoff_date
    ]

    prewarmed = 0
    for fact in recent_facts:
        for citation in fact.citations:
            key = self._make_key(citation, workspace_id)
            if key not in self._cache:
                result = await self._verify_citation(citation, workspace_id)
                if result:
                    prewarmed += 1

    logger.info(f"Prewarmed {prewarmed} citations from {len(recent_facts)} recent facts")
```

**3. High-Priority Facts (Domain-Based)**

```python
async def prewarm_critical_domains(self, workspace_id: str):
    """
    Pre-load citations from critical business domains.
    """
    critical_domains = ["finance", "legal", "compliance"]

    for domain in critical_domains:
        facts = await wm.list_all_facts(domain=domain, limit=100)

        for fact in facts:
            for citation in fact.citations:
                await self._verify_citation(citation, workspace_id)
```

### Pre-warming Strategy

**Implementation Approach**:

1. **On Startup** (recommended):
   ```python
   # In main.py application startup
   @app.on_event("startup")
   async def startup_event():
       cache = get_citation_cache()
       await cache.prewarm_recent_facts(workspace_id="default", days=7)
       await cache.prewarm_critical_domains(workspace_id="default")
   ```

2. **Periodic Background Task**:
   ```python
   # Run every hour
   async def periodic_prewarm_task():
       while True:
           await asyncio.sleep(3600)
           cache = get_citation_cache()
           await cache.prewarm_frequent_citations(workspace_id="default", top_n=50)
   ```

3. **Lazy Pre-warming** (on first access):
   ```python
   async def get_or_verify(self, citation_path: str, workspace_id: str):
       # Check cache
       cached = self.get(citation_path, workspace_id)
       if cached:
           return cached

       # Cache miss - verify and cache
       result = await self._verify_citation(citation_path, workspace_id)

       # Also verify related citations (speculative pre-warming)
       await self._verify_related_citations(citation_path, workspace_id)

       return result
   ```

**Batch Processing**:

```python
async def batch_verify_and_cache(
    self,
    citations: List[str],
    workspace_id: str,
    batch_size: int = 10
):
    """
    Verify multiple citations in parallel batches.
    """
    results = []

    for i in range(0, len(citations), batch_size):
        batch = citations[i:i+batch_size]

        # Parallel verification
        tasks = [
            self._verify_citation(citation, workspace_id)
            for citation in batch
        ]
        batch_results = await asyncio.gather(*tasks)

        results.extend(batch_results)

    return results
```

---

## Observability & Metrics

### Metrics to Track

**1. Cache Performance Metrics**

```python
{
    "cache_hits": int,              # Number of cache hits
    "cache_misses": int,            # Number of cache misses
    "hit_rate": float,              # Percentage (target: >90%)
    "avg_hit_latency_ms": float,    # Target: <5ms
    "avg_miss_latency_ms": float,   # Target: <200ms
    "cache_size": int,              # Current entries
    "evictions": int,               # LRU evictions
    "invalidations": int            # Manual invalidations
}
```

**2. Citation-Specific Metrics**

```python
{
    "most_accessed_citations": [
        {"citation": str, "access_count": int}
    ],
    "domain_hit_rates": {
        "finance": 0.92,
        "legal": 0.88,
        "hr": 0.95
    },
    "stale Citations": int,         # Citations with outdated status
    "verified_ratio": float         # verified / (verified + outdated)
}
```

**3. Storage Cost Metrics**

```python
{
    "s3_api_calls_saved": int,      # vs. no cache
    "cost_reduction_percent": float,
    "monthly_savings_usd": float
}
```

### Monitoring Endpoints

Add to existing `/health/metrics` endpoint (`backend/api/health_routes.py`):

```python
@router.get("/metrics/citation-cache")
async def get_citation_cache_metrics():
    cache = get_citation_cache()
    stats = cache.get_stats()

    return {
        "citation_cache": {
            "hit_rate": stats["hit_rate"],
            "size": stats["size"],
            "hits": stats["hits"],
            "misses": stats["misses"],
            "evictions": stats["evictions"],
            "invalidations": stats["invalidations"]
        }
    }
```

### Logging Strategy

```python
# Log cache misses for analysis
logger.debug(f"Citation cache MISS: {citation_path} (workspace: {workspace_id})")

# Log pre-warming activity
logger.info(f"Prewarming citation cache: {count} entries loaded in {elapsed_ms:.2f}ms")

# Log invalidation events
logger.info(f"Invalidated {count} cache entries for document: {document_key}")

# Alert on low hit rate
if cache.get_hit_rate() < 0.70:
    logger.warning(f"Citation cache hit rate below 70%: {cache.get_hit_rate():.2f}%")
```

### Performance Targets

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Cache hit rate | >90% | <70% |
| Cache hit latency | <5ms | >10ms |
| Cache miss latency | <200ms | >500ms |
| Cache size | <10,000 entries | >9,500 entries |
| Pre-warm duration | <5s | >10s |

---

## Implementation Examples

### Example 1: Basic Cache Usage

```python
from core.citation_cache import get_citation_cache

# Get cache instance
cache = get_citation_cache()

# Check citation (transparent caching)
result = await cache.get_or_verify(
    citation_path="s3://atom-saas/business_facts/default/abc/policy.pdf",
    workspace_id="default"
)

# Result:
# {
#     "exists": True,
#     "source": "R2",
#     "cached": True,  # True if from cache, False if fresh verification
#     "checked_at": datetime
# }
```

### Example 2: Integration with Existing Verification

**Current Code** (`backend/api/admin/business_facts_routes.py:336-407`):

```python
@router.post("/{fact_id}/verify-citation")
async def verify_citation(fact_id: str, ...):
    # Current: Every call hits S3/R2
    for citation in fact.citations:
        if citation.startswith("s3://"):
            exists = storage.check_exists(key)  # 200ms latency
```

**With Cache**:

```python
@router.post("/{fact_id}/verify-citation")
async def verify_citation(fact_id: str, ...):
    cache = get_citation_cache()

    for citation in fact.citations:
        # Check cache first (<5ms)
        result = await cache.get_or_verify(citation, workspace_id)
        exists = result["exists"]

        # ... rest of logic
```

### Example 3: Decorator Pattern (Alternative)

```python
# Add decorator to storage.check_exists method
from core.citation_cache import cached_verification

class StorageService:
    @cached_verification(ttl_seconds=86400)
    def check_exists(self, key: str) -> bool:
        """Original method - caching handled transparently"""
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False
```

### Example 4: Cache Statistics

```python
from core.citation_cache import get_citation_cache

cache = get_citation_cache()
stats = cache.get_stats()

print(f"Cache hit rate: {stats['hit_rate']}%")
print(f"Cache size: {stats['size']} / {stats['max_size']}")
print(f"S3 API calls saved: {stats['hits']}")
print(f"Estimated cost savings: ${stats['hits'] * 0.0004:.2f}")
```

---

## References

### Internal Codebase References

1. **`backend/core/governance_cache.py`** (975 lines)
   - Production-grade LRU cache with TTL
   - Thread-safe implementation
   - Decorator pattern support
   - **Confidence**: HIGH (proven in production)

2. **`backend/core/cache.py`** (95 lines)
   - Redis + in-memory hybrid cache
   - JSON serialization
   - **Confidence**: HIGH (foundational infrastructure)

3. **`backend/core/storage.py`** (69 lines)
   - R2/S3 integration
   - `check_exists()` method (current bottleneck)
   - **Confidence**: HIGH (active usage)

4. **`backend/core/agent_world_model.py`** (930 lines)
   - Business fact storage in LanceDB
   - Citation verification workflow
   - **Confidence**: HIGH (core system)

5. **`docs/CITATION_SYSTEM_GUIDE.md`**
   - Citation system documentation
   - Verification flow diagrams
   - **Confidence**: HIGH (authoritative)

6. **`docs/JIT_FACT_PROVISION_SYSTEM.md`**
   - JIT fact retrieval architecture
   - Performance benchmarks
   - **Confidence**: HIGH (authoritative)

### External Patterns (Based on Training Data)

1. **Content-Addressable Storage**
   - Git uses SHA-1 for object deduplication
   - IPFS uses content addressing for distributed storage
   - **Confidence**: HIGH (well-established patterns)

2. **Cache Invalidation Patterns**
   - CDN cache invalidation (purge by URL, purge by tag)
   - Database query cache invalidation (write-through)
   - **Confidence**: MEDIUM (standard patterns)

3. **TTL Selection**
   - CDN TTLs: 1 hour to 1 year (varies by content type)
   - DNS TTL: 300 seconds to 24 hours
   - **Confidence**: MEDIUM (domain-specific)

### Known Gaps

1. **Usage Analytics**: No existing citation access frequency tracking in codebase
2. **Document Versioning**: Storage service doesn't track document versions
3. **Pre-warming Data**: No historical data on citation access patterns

---

## Appendices

### A: Cache Key Examples

```python
# Example citations and their cache keys
examples = [
    {
        "citation": "s3://atom-saas/business_facts/default/abc/policy.pdf",
        "normalized": "business_facts/default/abc/policy.pdf",
        "hash": "a1b2c3d4e5f6...",
        "cache_key": "citation:default:a1b2c3d4e5f6..."
    },
    {
        "citation": "policy.pdf:p4",
        "normalized": "policy.pdf",
        "hash": "f6e5d4c3b2a1...",
        "cache_key": "citation:default:f6e5d4c3b2a1..."
    }
]
```

### B: Cache Size Calculation

**Per-Entry Memory Estimate**:

```python
entry_size = {
    "key": 64,              # SHA-256 hash as hex string
    "exists": 1,            # Boolean
    "checked_at": 8,        # Timestamp
    "citation": 100,        # Average citation string
    "source": 10,           # "R2" or "Local"
    "overhead": 20          # Python dict overhead
}

# Total: ~200 bytes per entry

# 10,000 entries × 200 bytes = 2MB
# 50,000 entries × 200 bytes = 10MB
```

### C: S3 API Cost Calculation

**Current (no cache)**:
- 10,000 verifications/day × 30 days = 300,000 API calls/month
- Cost: 300,000 × $0.0004/1K requests = **$120/month**

**With 90% cache hit rate**:
- 300,000 × 10% = 30,000 API calls/month
- Cost: 30,000 × $0.0004/1K requests = **$12/month**
- **Savings: $108/month (90% reduction)**

---

*End of Research Report*
