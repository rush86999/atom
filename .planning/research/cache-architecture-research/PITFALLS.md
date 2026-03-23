# Domain Pitfalls

**Domain:** Verification Result Caching
**Researched:** March 22, 2026

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: Stale Cache Data from Deleted Documents
**What goes wrong:** Document deleted from R2/S3, but cache still shows "verified" → agents use invalid facts
**Why it happens:** Cache TTL is too long or no invalidation on document delete
**Consequences:** Compliance violations, incorrect decisions, data integrity issues
**Prevention:**
  - Use aggressive TTL (15 minutes recommended)
  - Invalidate cache entries on document upload/delete
  - Add manual invalidation API endpoint for admins
**Detection:** Monitor cache hit rate vs. verification failure rate (correlation indicates staleness)

### Pitfall 2: Blocking Application Startup
**What goes wrong:** Synchronous cache warming blocks lifespan, preventing health checks from passing
**Why it happens:** Cache warming runs in main thread instead of background task
**Consequences:** Kubernetes/ECS health probes fail → pod restart loop → downtime
**Prevention:**
  - Always use `asyncio.create_task()` for cache warming
  - Implement graceful degradation (startup continues if warming fails)
  - Add startup timeout (e.g., 30 seconds) before giving up
**Detection:** Monitor application startup time, check for startup timeouts in logs

### Pitfall 3: Cross-Workspace Data Leakage
**What goes wrong:** Cache key doesn't include workspace_id → User A sees User B's verification results
**Why it happens:** Global cache keys, insufficient isolation
**Consequences:** SECURITY BREACH, data privacy violation
**Prevention:**
  - Always include workspace_id in cache key: `f"{workspace_id}:{citation}"`
  - Use separate cache instances per workspace (optional, more isolation)
  - Validate workspace_id in cache.get() operations
**Detection:** Security audit, test with multiple workspaces

### Pitfall 4: Cache Stampede on Startup
**What goes wrong:** All application instances start simultaneously, miss cache, hammer R2/S3 API
**Why it happens:** No cache warming or all instances cold-start at same time (deployment)
**Consequences:** R2/S3 rate limits, throttling, slow deployment
**Prevention:**
  - Implement staggered cache warming (random delay per instance)
  - Use "cache warming" flag to enable only on one instance (leader election)
  - Consider pre-warming from database cold cache instead of R2/S3
**Detection:** Monitor R2/S3 API request rate during deployments

## Moderate Pitfalls

### Pitfall 1: Cache Eviction During High Load
**What goes wrong:** LRU eviction thrashing, low hit rate during peak traffic
**Why it happens:** Cache size too small for workload
**Consequences:** Degraded performance, increased latency
**Prevention:**
  - Size cache appropriately (1000 entries for <100 users, 10,000 for scale)
  - Monitor cache hit rate, alert if <80%
  - Implement hybrid hot/cold cache (unlimited cold cache)
**Detection:** Prometheus metrics on cache_hits / cache_misses ratio

### Pitfall 2: Memory Leak in Hot Cache
**What goes wrong:** Cache entries never expire, memory usage grows unbounded
**Why it happens:** Bug in TTL expiration logic or background cleanup task crashes
**Consequences:** OOM (Out of Memory), process killed
**Prevention:**
  - Use max_size parameter in LRU cache (hard limit)
  - Implement background cleanup task (follow GovernanceCache pattern)
  - Monitor memory usage, set alerts
**Detection:** Memory metrics, process monitoring

### Pitfall 3: Database Connection Pool Exhaustion
**What goes wrong:** Cold cache lookups exhaust PostgreSQL connection pool
**Why it happens:** Every cache miss opens new DB connection, not released properly
**Consequences:** Database slowdown, connection timeouts
**Prevention:**
  - Use SQLAlchemy session context manager (`with get_db_session() as db:`)
  - Increase pool size if needed (default: 20 connections)
  - Implement connection pooling for cache queries
**Detection:** Database metrics, monitor active connections

## Minor Pitfalls

### Pitfall 1: Cache Key Collisions
**What goes wrong:** Two different citations hash to same cache key
**Why it happens:** Using simple hash (CRC32) instead of cryptographic hash
**Consequences:** Wrong verification result returned, false negatives
**Prevention:**
  - Use SHA-256 for cache keys: `sha256(citation).hexdigest()`
  - Include workspace_id in key to prevent cross-workspace collisions
**Detection:** Log warnings on cache key collisions (should never happen with SHA-256)

### Pitfall 2: Missing Cache Statistics
**What goes wrong:** No visibility into cache performance
**Why it happens:** Forgot to implement metrics tracking
**Consequences:** Can't debug performance issues, can't prove cache value
**Prevention:**
  - Track hits, misses, evictions (follow GovernanceCache pattern)
  - Expose metrics via Prometheus
  - Add admin endpoint for cache stats: GET /admin/cache/stats
**Detection:** Pre-commit checklist includes cache metrics

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| **Phase 1: Database Schema** | Missing indexes on cache table | Add composite index on (workspace_id, citation_key, expires_at) |
| **Phase 1: Database Schema** | Partitioning too early | Don't partition until >1M rows, use standard table first |
| **Phase 2: Integration** | Breaking existing verification flow | Use decorator pattern (additive, not replacing) |
| **Phase 2: Integration** | Forgetting workspace_id in cache key | Code review checklist item, unit test for isolation |
| **Phase 3: Background Worker** | Blocking startup with sync warming | Always use asyncio.create_task(), test startup time |
| **Phase 3: Background Worker** | Cache warming crashes, takes down app | Try/except with graceful degradation, log error |
| **Phase 4: Monitoring** | Forgetting cache metrics | Add to monitoring checklist, expose Prometheus endpoints |
| **Phase 4: Monitoring** | No alerting on low hit rate | Set alert if cache_hit_rate < 80% for 5 minutes |

## Migration Path

### Phase 1: Database Schema (Zero Downtime)
```sql
-- 1. Create new table (non-blocking)
CREATE TABLE fact_verification_cache (...);

-- 2. Add indexes (non-blocking for empty table)
CREATE INDEX idx_fact_verification_cache_workspace ON fact_verification_cache(workspace_id);

-- 3. Deploy new code that reads from cache but doesn't write (safe)
-- 4. Verify cache lookups work (monitor logs)
-- 5. Enable cache writes (no rollback needed, cache is optional)
```

### Phase 2: Integration (Non-Breaking)
```python
# 1. Add decorator with feature flag
@cached_verification(enabled=getenv("CACHE_ENABLED", "false"))
async def verify_citation(...):
    # Existing code unchanged

# 2. Deploy with flag=false (no change)
# 3. Test in staging with flag=true
# 4. Enable in production with flag=true
# 5. Monitor for 1 week, remove flag if stable
```

### Phase 3: Background Worker (Gradual Rollout)
```python
# 1. Add lifespan with toggle
enable_cache_warming = getenv("CACHE_WARMING_ENABLED", "false")

if enable_cache_warming:
    asyncio.create_task(warm_verification_cache())

# 2. Deploy with toggle=false
# 3. Enable on single instance (canary)
# 4. Monitor startup time, cache hit rate
# 5. Rollout to all instances
```

### Rollback Strategy
- **Phase 1**: Database schema is additive, no rollback needed (cache is optional)
- **Phase 2**: Set CACHE_ENABLED=false to disable decorator
- **Phase 3**: Set CACHE_WARMING_ENABLED=false to disable background worker
- **Phase 4**: Disable Prometheus metrics (no impact on functionality)

## Sources

- HIGH confidence: Existing codebase patterns (GovernanceCache pitfalls learned)
- MEDIUM confidence: Standard caching challenges (TTL, eviction, memory leaks)
- MEDIUM confidence: FastAPI lifespan best practices (non-blocking startup)
- LOW confidence: Production load patterns (no real-world data, estimated)
