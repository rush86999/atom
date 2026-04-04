# JIT Verification System - Quick Start Guide

## 5-Minute Setup

### 1. Install Dependencies

```bash
cd backend
pip install redis
```

### 2. Start Redis (for L2 cache)

```bash
# Using Docker
docker run -d -p 6379:6379 redis:latest

# Or using Homebrew (macOS)
brew install redis
brew start redis
```

### 3. Configure Environment

Add to your `.env` file:

```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# JIT Verification Worker
JIT_VERIFICATION_INTERVAL_SECONDS=3600  # Verify every hour

# Storage (existing configuration)
AWS_S3_BUCKET=your-bucket-name
S3_ENDPOINT=https://...
```

### 4. Start the Application

```bash
cd backend
python -m uvicorn main_api_app:app --reload --port 8000
```

The JIT verification routes are now available at:
- `http://localhost:8000/api/admin/governance/jit/*`

## Basic Usage

### Verify Citations

```bash
curl -X POST "http://localhost:8000/api/admin/governance/jit/verify-citations" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "citations": ["s3://your-bucket/policies/approval.pdf"],
    "force_refresh": false
  }'
```

### Start Background Worker

```bash
curl -X POST "http://localhost:8000/api/admin/governance/jit/worker/start" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Check Health

```bash
curl "http://localhost:8000/api/admin/governance/jit/health" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### View Cache Statistics

```bash
curl "http://localhost:8000/api/admin/governance/jit/cache/stats" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Common Operations

### Warm the Cache

Pre-verify citations to populate cache:

```bash
curl -X POST "http://localhost:8000/api/admin/governance/jit/cache/warm?limit=100" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Clear the Cache

Force fresh verification:

```bash
curl -X POST "http://localhost:8000/api/admin/governance/jit/cache/clear" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### View Worker Metrics

```bash
curl "http://localhost:8000/api/admin/governance/jit/worker/metrics" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Verify Specific Fact

```bash
curl -X POST "http://localhost:8000/api/admin/governance/jit/worker/verify-fact/fact-123" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### View Top Citations

See most frequently accessed citations:

```bash
curl "http://localhost:8000/api/admin/governance/jit/worker/top-citations?limit=20" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Code Integration

### In Your Agent Code

```python
from core.jit_verification_cache import get_jit_verification_cache

async def check_compliance(agent_id: str, invoice_amount: float):
    cache = get_jit_verification_cache()

    # Get business facts (cached)
    facts = await cache.get_business_facts("invoice approval")

    # Check policy citations (cached)
    for fact in facts:
        for citation in fact["citations"]:
            result = await cache.verify_citation(citation)
            if not result.exists:
                # Policy outdated, flag for review
                return {"compliant": False, "reason": "Policy citation missing"}

    # Check business rule
    if invoice_amount > 500:
        return {"compliant": False, "reason": "Needs VP approval"}

    return {"compliant": True}
```

### In Application Startup

```python
# backend/main_api_app.py

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from core.jit_verification_worker import start_jit_verification_worker

    worker = await start_jit_verification_worker()
    logger.info("JIT verification worker started")

    yield

    # Shutdown
    from core.jit_verification_worker import stop_jit_verification_worker
    await stop_jit_verification_worker()
    logger.info("JIT verification worker stopped")


app = FastAPI(lifespan=lifespan)
```

## Monitoring

### Set Up Alerts

Monitor these metrics:

1. **Cache Hit Rate**: Should be > 85%
   ```bash
   # Check hit rate
   curl ".../cache/stats" | jq ".l1_verification_hit_rate"
   ```

2. **Worker Status**: Should be `running: true`
   ```bash
   # Check worker status
   curl ".../worker/metrics" | jq ".running"
   ```

3. **Stale Facts**: Should be minimal
   ```bash
   # Check stale facts
   curl ".../worker/metrics" | jq ".stale_facts"
   ```

### Health Check Script

```bash
#!/bin/bash
# check_jit_health.sh

HEALTH=$(curl -s "http://localhost:8000/api/admin/governance/jit/health" \
  -H "Authorization: Bearer $TOKEN")

STATUS=$(echo $HEALTH | jq -r ".status")

if [ "$STATUS" != "healthy" ]; then
  ISSUES=$(echo $HEALTH | jq -r ".issues[]")
  echo "JIT verification unhealthy: $ISSUES"
  exit 1
fi

echo "JIT verification healthy"
exit 0
```

## Troubleshooting

### Cache Not Working

**Problem**: All verifications hitting R2/S3

**Solution**:
1. Check Redis is running: `redis-cli ping`
2. Check cache stats: `curl ".../cache/stats"`
3. Verify `REDIS_URL` is set correctly

### Worker Not Running

**Problem**: Worker shows `running: false`

**Solution**:
1. Start worker: `curl -X POST ".../worker/start"`
2. Check logs: `tail -f logs/atom.log | grep -i jit`
3. Verify interval: `echo $JIT_VERIFICATION_INTERVAL_SECONDS`

### High Latency

**Problem**: Agent decisions taking > 1 second

**Solution**:
1. Warm cache: `curl -X POST ".../cache/warm?limit=200"`
2. Increase cache size: `JIT_CACHE_L1_MAX_SIZE=20000`
3. Decrease verification interval: `JIT_VERIFICATION_INTERVAL_SECONDS=1800`

## Performance Tuning

### High-Traffic Systems

```bash
# .env
JIT_VERIFICATION_INTERVAL_SECONDS=1800  # 30 minutes
JIT_CACHE_L1_MAX_SIZE=50000             # 50K entries
```

### Low-Traffic Systems

```bash
# .env
JIT_VERIFICATION_INTERVAL_SECONDS=7200  # 2 hours
JIT_CACHE_L1_MAX_SIZE=5000              # 5K entries
```

### Memory-Constrained Systems

```bash
# .env
JIT_CACHE_L1_MAX_SIZE=1000              # 1K entries
JIT_CACHE_L1_VERIFICATION_TTL=180       # 3 minutes
```

## Testing

```bash
# Run tests
pytest tests/test_jit_verification_cache.py -v
pytest tests/test_jit_verification_worker.py -v
pytest tests/test_jit_verification_routes.py -v

# Run with coverage
pytest tests/test_jit_verification_*.py \
  --cov=core.jit_verification_cache \
  --cov=core.jit_verification_worker \
  --cov-report=html
```

## Next Steps

1. **Read Full Documentation**: `docs/JIT_VERIFICATION_CACHE.md`
2. **Configure Monitoring**: Set up alerts for cache hit rate and worker status
3. **Tune Performance**: Adjust cache sizes and verification intervals
4. **Integrate with Agents**: Add compliance checks to your agent workflows

## Support

For issues or questions:
- Check logs: `tail -f logs/atom.log | grep -i jit`
- Review health: `curl ".../health"`
- See documentation: `docs/JIT_VERIFICATION_CACHE.md`
