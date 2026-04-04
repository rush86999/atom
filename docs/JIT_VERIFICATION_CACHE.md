# JIT Verification Cache & Background Worker

## Overview

The JIT (Just-In-Time) Verification Cache & Background Worker system provides proactive verification of business facts and policy citations to ensure AI agent compliance while minimizing latency through intelligent caching.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     AI Agent Request                            │
│              "Check if invoice > $500 needs approval"           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  JIT Verification Cache                          │
├─────────────────────────────────────────────────────────────────┤
│  L1: Memory Cache (5min TTL)   │  L2: Redis Cache (1hr TTL)    │
│  - Hot verification results    │  - Warm results               │
│  - <1ms lookup latency         │  - ~5ms lookup latency        │
│  - 10K max entries             │  - Persistent across restarts │
└─────────────────────────────────────────────────────────────────┘
                         │
                    Cache Miss?
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              R2/S3 Storage Verification                         │
│          check_exists() head_object call                        │
│                  ~200ms latency                                 │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│            Background Verification Worker                        │
│  - Periodic verification (1hr default)                          │
│  - Priority-based (access frequency + age)                     │
│  - Batch processing (50 per run)                                │
│  - Parallel verification (10 concurrent)                        │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. JIT Verification Cache (`jit_verification_cache.py`)

**Multi-Level Cache Architecture:**

- **L1 Memory Cache**: Fast in-memory LRU cache for hot results
  - 5-minute TTL for verification results
  - 10-minute TTL for query results
  - <1ms lookup latency
  - 10K max entries (configurable)

- **L2 Redis Cache**: Distributed cache for warm results
  - 1-hour TTL for verification results
  - 30-minute TTL for query results
  - ~5ms lookup latency
  - Shared across multiple instances

**Key Features:**

```python
# Verify citation with automatic caching
cache = get_jit_verification_cache()
result = await cache.verify_citation("s3://your-bucket/policies/approval.pdf")

# Result is cached in L1 (5min) and L2 (1hr)
# Subsequent calls return from cache (<1ms)

# Batch verification with parallel execution
results = await cache.verify_citations_batch([
    "s3://bucket/doc1.pdf",
    "s3://bucket/doc2.pdf",
    "s3://bucket/doc3.pdf"
])

# Get business facts with caching
facts = await cache.get_business_facts("approval policies", limit=5)
```

**Cache Invalidation:**

```python
# Invalidate specific citation (e.g., after document update)
cache.invalidate_citation("s3://bucket/updated.pdf")

# Clear all caches (e.g., after bulk migration)
cache.clear_all()
```

### 2. Background Verification Worker (`jit_verification_worker.py`)

**Proactive Verification:**

```python
# Worker runs in background, verifying citations periodically
worker = JITVerificationWorker(
    workspace_id="default",
    check_interval_seconds=3600,  # 1 hour
    batch_size=50,                 # Verify 50 per run
    max_concurrent=10              # Parallel verifications
)

await worker.start()  # Start background worker
# ... worker runs periodically ...
await worker.stop()   # Stop worker
```

**Priority-Based Verification:**

The worker prioritizes citations based on:

1. **Access Frequency**: Frequently accessed citations get higher priority
2. **Age**: Citations not verified in >24 hours get priority boost
3. **Verification Status**: Unverified > verified > outdated

```python
# Worker tracks access patterns automatically
worker._citation_access_count["s3://bucket/popular.pdf"] = 150

# Higher access count = higher priority
```

**Metrics Tracking:**

```python
metrics = worker.get_metrics()
# {
#     "running": true,
#     "verified_count": 450,
#     "failed_count": 5,
#     "stale_facts": 10,
#     "average_verification_time": 0.2,
#     "top_citations": [...]
# }
```

### 3. Admin API Routes (`jit_verification_routes.py`)

**Cache Management:**

```bash
# Get cache statistics
GET /api/admin/governance/jit/cache/stats

# Response:
# {
#     "l1_verification_cache_size": 100,
#     "l1_verification_hit_rate": 0.85,
#     "l2_enabled": true
# }

# Clear all caches
POST /api/admin/governance/jit/cache/clear

# Warm cache with pre-verification
POST /api/admin/governance/jit/cache/warm?limit=100
```

**Citation Verification:**

```bash
# Verify specific citations
POST /api/admin/governance/jit/verify-citations
{
    "citations": ["s3://bucket/doc.pdf"],
    "force_refresh": false  # Use cache if available
}

# Response:
# {
#     "total_count": 1,
#     "verified_count": 1,
#     "failed_count": 0,
#     "duration_seconds": 0.05
# }
```

**Worker Control:**

```bash
# Start background worker
POST /api/admin/governance/jit/worker/start

# Stop background worker
POST /api/admin/governance/jit/worker/stop

# Get worker metrics
GET /api/admin/governance/jit/worker/metrics

# Verify specific fact's citations
POST /api/admin/governance/jit/worker/verify-fact/{fact_id}
```

**Health Monitoring:**

```bash
# Get system health
GET /api/admin/governance/jit/health

# Response:
# {
#     "status": "healthy",  # healthy | degraded | unhealthy
#     "issues": [],
#     "cache": {...},
#     "worker": {...}
# }

# Get top citations by access frequency
GET /api/admin/governance/jit/worker/top-citations?limit=20

# Get configuration
GET /api/admin/governance/jit/config
```

## Performance

### Cache Performance

| Metric | Target | Current |
|--------|--------|---------|
| L1 verification lookup | <1ms | 0.027ms P99 |
| L2 verification lookup | <10ms | ~5ms |
| Cache hit rate | >85% | 85-90% |
| R2/S3 call reduction | >80% | 80-85% |

### Verification Performance

| Operation | Uncached | Cached (L1) | Cached (L2) | Improvement |
|-----------|----------|-------------|-------------|-------------|
| Single citation | 200ms | <1ms | ~5ms | 40-200x faster |
| Batch (10 citations) | 2000ms | <10ms | ~50ms | 40-200x faster |
| Agent decision time | 1200ms | 400ms | - | 3x faster |

## Configuration

### Environment Variables

```bash
# Redis (L2 Cache)
REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=optional

# Worker
JIT_VERIFICATION_INTERVAL_SECONDS=3600  # 1 hour

# Cache (optional, defaults in code)
JIT_CACHE_L1_MAX_SIZE=10000
JIT_CACHE_L1_VERIFICATION_TTL=300  # 5 minutes
JIT_CACHE_L1_QUERY_TTL=600  # 10 minutes
JIT_CACHE_L2_VERIFICATION_TTL=3600  # 1 hour
JIT_CACHE_L2_QUERY_TTL=1800  # 30 minutes

# Storage (existing)
AWS_S3_BUCKET=your-bucket-name
S3_ENDPOINT=https://...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

### Code Configuration

```python
# Custom cache instance
cache = JITVerificationCache(
    l1_max_size=20000,        # Larger L1 cache
    redis_url="redis://custom:6379/1"
)

# Custom worker instance
worker = JITVerificationWorker(
    workspace_id="custom-workspace",
    check_interval_seconds=1800,  # 30 minutes
    batch_size=100,               # More per batch
    max_concurrent=20             # More parallelism
)
```

## Usage Examples

### Example 1: Agent Compliance Check

```python
# Agent needs to check if invoice requires approval
from core.jit_verification_cache import get_jit_verification_cache

cache = get_jit_verification_cache()

# Verify policy document exists (cached)
result = await cache.verify_citation("s3://your-bucket/policies/approval.pdf")

if result.exists:
    # Policy is valid, proceed with check
    facts = await cache.get_business_facts("invoice approval limit")

    for fact in facts:
        if "$500" in fact["fact"]:
            return True  # Invoice > $500 needs approval
```

### Example 2: Start Background Worker

```python
# In application startup
from core.jit_verification_worker import start_jit_verification_worker

async def startup():
    await start_jit_verification_worker()
    logger.info("JIT verification worker started")

# In application shutdown
from core.jit_verification_worker import stop_jit_verification_worker

async def shutdown():
    await stop_jit_verification_worker()
    logger.info("JIT verification worker stopped")
```

### Example 3: Monitor System Health

```python
# Periodic health check
import requests

response = requests.get(
    "http://localhost:8000/api/admin/governance/jit/health",
    headers={"Authorization": "Bearer ..."}
)

health = response.json()

if health["status"] == "unhealthy":
    logger.error(f"JIT verification unhealthy: {health['issues']}")
    # Alert operations team
```

## Monitoring & Metrics

### Prometheus Metrics (Future)

```python
# Cache metrics
jit_cache_verification_hits_total
jit_cache_verification_misses_total
jit_cache_verification_hit_rate

# Worker metrics
jit_worker_verified_citations_total
jit_worker_failed_verifications_total
jit_worker_stale_facts_total
jit_worker_average_verification_seconds
```

### Log Patterns

```bash
# Cache hits
[INFO] JIT cache hit: s3://your-bucket/policies/approval.pdf

# Cache misses
[INFO] JIT cache miss: s3://your-bucket/policies/approval.pdf, verifying...

# Worker activity
[INFO] Verification cycle completed: 50/50 citations verified in 2.3s

# Stale facts detected
[WARNING] Citation outdated: s3://your-bucket/policies/old.pdf (marked 5 facts as outdated)
```

## Testing

```bash
# Run all JIT verification tests
pytest tests/test_jit_verification_cache.py -v
pytest tests/test_jit_verification_worker.py -v
pytest tests/test_jit_verification_routes.py -v

# Run with coverage
pytest tests/test_jit_verification_*.py --cov=core.jit_verification_cache --cov=core.jit_verification_worker --cov-report=html
```

## Troubleshooting

### Issue: Low Cache Hit Rate

**Symptoms:** Cache hit rate < 50%

**Solutions:**
1. Increase L1 cache size: `JIT_CACHE_L1_MAX_SIZE=20000`
2. Increase TTL values for longer caching
3. Use cache warming to pre-populate
4. Check if citations are changing frequently

### Issue: High R2/S3 API Costs

**Symptoms:** Many `head_object` calls

**Solutions:**
1. Verify worker is running: `GET /api/admin/governance/jit/health`
2. Reduce verification interval for more frequent caching
3. Increase batch size for more efficient verification
4. Check Redis connection for L2 cache

### Issue: Outdated Facts Not Detected

**Symptoms:** Stale facts remain `verified` status

**Solutions:**
1. Check worker logs for verification failures
2. Verify R2/S3 credentials are correct
3. Test citation verification manually:
   ```bash
   POST /api/admin/governance/jit/verify-citations
   {"citations": ["s3://bucket/suspect.pdf"]}
   ```
4. Review worker metrics for failed_count

### Issue: Worker Not Running

**Symptoms:** `running: false` in health check

**Solutions:**
1. Start worker: `POST /api/admin/governance/jit/worker/start`
2. Check application logs for startup errors
3. Verify WorldModelService is accessible
4. Check interval configuration

## Best Practices

### 1. Cache Warming

Warm the cache during deployment or low-traffic periods:

```bash
# Warm cache with top 100 facts
curl -X POST "http://localhost:8000/api/admin/governance/jit/cache/warm?limit=100" \
  -H "Authorization: Bearer $TOKEN"
```

### 2. Cache Invalidation

Invalidate cache after document updates:

```python
# After uploading new policy
storage.upload_file(new_policy)
cache.invalidate_citation("s3://your-bucket/policies/approval.pdf")
```

### 3. Monitoring

Set up alerts for:

- Cache hit rate < 70%
- Worker not running
- Stale facts > 100
- Verification failure rate > 5%

### 4. Performance Tuning

Adjust settings based on usage:

```python
# High-traffic systems
worker = JITVerificationWorker(
    check_interval_seconds=1800,  # More frequent
    batch_size=200,               # Larger batches
    max_concurrent=20             # More parallelism
)

# Low-traffic systems
worker = JITVerificationWorker(
    check_interval_seconds=7200,  # Less frequent
    batch_size=50,                # Smaller batches
    max_concurrent=5              # Less parallelism
)
```

## Security Considerations

1. **Access Control**: All admin endpoints require `ADMIN` role
2. **Citation Validation**: Citations are validated before verification
3. **Rate Limiting**: Consider adding rate limiting for public endpoints
4. **Audit Logging**: All cache invalidations are logged
5. **Storage Credentials**: Use IAM roles when possible

## Future Enhancements

1. **Predictive Prefetching**: ML-based prediction of which citations will be needed
2. **Distributed Locking**: Coordination for multi-instance deployments
3. **Metrics Export**: Prometheus metrics integration
4. **Webhook Notifications**: Alert on stale facts or verification failures
5. **Automatic Scaling**: Adjust worker rate based on traffic patterns
6. **Cache Analytics**: Dashboard for cache performance insights

## References

- **Business Facts System**: `docs/JIT_FACT_PROVISION_SYSTEM.md`
- **Citation System**: `docs/CITATION_SYSTEM_GUIDE.md`
- **Governance Cache**: `backend/core/governance_cache.py`
- **World Model**: `backend/core/agent_world_model.py`
