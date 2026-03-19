# Load Testing with Locust

This directory contains Locust load tests for validating Atom API performance under concurrent user load.

## Overview

Load testing simulates multiple concurrent users interacting with the API to identify performance bottlenecks, establish capacity limits, and validate that Phase 208 performance benchmarks hold under load.

**Key Differences from Phase 208 Benchmarks:**
- **Phase 208**: Single-user benchmarks establishing targets (<1ms cache, <100ms API)
- **Phase 209**: Multi-user load testing validating targets under concurrent load (100-1000 users)

## Prerequisites

1. **Locust installed** (already in requirements-testing.txt):
   ```bash
   pip install locust>=2.15.0
   ```

2. **Application running**:
   ```bash
   cd backend
   python -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```

3. **Test database** (optional but recommended):
   ```bash
   export DATABASE_URL=sqlite:///./atom_load_test.db
   ```

## Running Locust

### Interactive Mode (Web UI)

Start Locust with web UI for real-time monitoring:

```bash
cd backend
locust -f tests/load/locustfile.py
```

Then open http://localhost:8089 in your browser.

**Web UI Features:**
- Real-time request rate (RPS) monitoring
- Response time percentiles (P50, P95, P99)
- Failure rate tracking
- User count adjustment during test
- Stop/start test control

**Default Settings:**
- Host: http://localhost:8000
- Web UI Port: 8089
- Default Users: Start with 100 users
- Spawn Rate: 10 users/second

### Headless Mode (CI/CD)

Run load tests without web UI for automation:

```bash
cd backend
locust -f tests/load/locustfile.py --headless \
  -u 100 \              # 100 concurrent users
  -r 10 \               # Spawn 10 users/second
  -t 5m \               # Run for 5 minutes
  --html tests/load/reports/load-test-report.html \
  --json tests/load/reports/load-test-results.json
```

**Recommended Load Test Profiles:**

| Profile | Users | Duration | Purpose |
|---------|-------|----------|---------|
| Smoke Test | 50 | 2m | Quick validation, CI/CD |
| Standard Load | 100 | 5m | Normal traffic simulation |
| Peak Load | 500 | 10m | Peak traffic validation |
| Stress Test | 1000 | 15m | Identify breaking point |

### Custom Port (Avoid Conflicts)

If port 8089 is in use:

```bash
locust -f tests/load/locustfile.py --web-port=8090
```

## User Scenarios

### 1. AtomAPIUser (Base User)

**Purpose**: Basic API interactions with health checks

**Tasks:**
- Health check (weight: 1) - GET /health/live

**Wait Time**: 1-3 seconds between tasks

**When to Use**: Baseline health check performance

### 2. AgentAPIUser

**Purpose**: Simulate agent management operations

**Tasks:**
- List agents (weight: 5) - GET /api/v1/agents
- Get agent (weight: 3) - GET /api/v1/agents/{id}
- Create agent (weight: 1) - POST /api/v1/agents

**Wait Time**: 1-3 seconds between tasks

**Phase 208 Targets:**
- List agents: <50ms
- Get agent: <50ms
- Create agent: <100ms

**When to Use**: Testing agent CRUD performance

### 3. WorkflowExecutionUser

**Purpose**: Simulate workflow execution operations

**Tasks:**
- Execute workflow (weight: 2) - POST /api/v1/workflows/{id}/execute
- List workflows (weight: 1) - GET /api/v1/workflows

**Wait Time**: 2-5 seconds (longer for workflow execution)

**Phase 208 Targets:**
- Execute workflow: <100ms
- List workflows: <50ms

**When to Use**: Testing workflow performance under load

### 4. GovernanceCheckUser

**Purpose**: Simulate governance permission checks

**Tasks:**
- Check permission (weight: 4) - POST /api/agent-governance/check-permission
- Get cache stats (weight: 2) - GET /api/agent-governance/cache-stats

**Wait Time**: 1-3 seconds between tasks

**Phase 208 Targets:**
- Cached permission check: <1ms
- Cache stats: <50ms

**When to Use**: Testing governance cache performance

### 5. EpisodeAPIUser

**Purpose**: Simulate episodic memory retrieval

**Tasks:**
- List episodes (weight: 3) - GET /api/v1/episodes
- Get episode (weight: 2) - GET /api/v1/episodes/{id}

**Wait Time**: 1-3 seconds between tasks

**Phase 208 Targets:**
- List episodes: <50ms
- Get episode: <50ms

**When to Use**: Testing episode retrieval performance

## Critical Endpoints

| Endpoint | Method | Purpose | Weight | Phase 208 Target |
|----------|--------|---------|--------|------------------|
| /health/live | GET | Health check | 1 | <10ms |
| /api/v1/agents | GET | List agents | 5 | <50ms |
| /api/v1/agents/{id} | GET | Get agent | 3 | <50ms |
| /api/v1/agents | POST | Create agent | 1 | <100ms |
| /api/v1/workflows/{id}/execute | POST | Execute workflow | 2 | <100ms |
| /api/v1/workflows | GET | List workflows | 1 | <50ms |
| /api/agent-governance/check-permission | POST | Check permission | 4 | <1ms (cached) |
| /api/agent-governance/cache-stats | GET | Cache stats | 2 | <50ms |
| /api/v1/episodes | GET | List episodes | 3 | <50ms |
| /api/v1/episodes/{id} | GET | Get episode | 2 | <50ms |

## Interpreting Results

### Key Metrics

**Requests Per Second (RPS):**
- Measure of throughput
- Higher is better (indicates capacity)
- Target: Maintain RPS as user count increases

**Response Time Percentiles:**
- **P50 (Median)**: 50% of requests complete faster than this
- **P95**: 95% of requests complete faster than this (SLA target)
- **P99**: 99% of requests complete faster than this (tail latency)

**Failure Rate:**
- Percentage of failed requests (non-2xx status codes)
- Target: <1% failure rate
- Common failures: 500 (server error), 503 (service unavailable)

### Example Output

```
Name                                                          # reqs      # fails |    Avg     Min     Max    Med |   req/s  failures/s
---------------------------------------------------------------------------------------------------------------------------------------
GET /health/live                                                  150     0(0.00%) |      8       5      15       8 |   10.00        0.00
GET /api/v1/agents                                                 75     0(0.00%) |     45      20      80      42 |    5.00        0.00
POST /api/v1/agents                                                 5     0(0.00%) |     95      70     120      90 |    0.33        0.00
---------------------------------------------------------------------------------------------------------------------------------------
Aggregate                                                          230     0(0.00%) |     32       5     120      20 |   15.33        0.00

Response time percentiles (approximate)
  50%      20ms
  66%      25ms
  75%      30ms
  80%      35ms
  90%      50ms
  95%      70ms
  98%      90ms
  99%     110ms
 100%     120ms (longest request)
```

### Performance Indicators

**Good Performance:**
- P95 response time < Phase 208 targets (e.g., <50ms for agents)
- Failure rate <1%
- RPS scales linearly with user count
- No response time spikes as user count increases

**Performance Issues:**
- P95 response time increases with user count (bottleneck)
- Failure rate >5% (capacity limit)
- RPS plateaus or decreases (system overload)
- Response time spikes during test (resource exhaustion)

## Troubleshooting

### Server Not Running

**Symptom:** Connection refused errors

**Solution:**
```bash
# Check if server is running
curl http://localhost:8000/health/live

# Start server if not running
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### Authentication Failures

**Symptom:** 401 Unauthorized errors

**Solution:**
- Load tests use hardcoded credentials (`load_test@example.com`)
- Ensure test user exists in database
- Check authentication endpoint is working:
  ```bash
  curl -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "load_test@example.com", "password": "test_password_123"}'
  ```

### Port Conflicts

**Symptom:** "Address already in use" error

**Solution:**
```bash
# Use different port for Locust web UI
locust -f tests/load/locustfile.py --web-port=8090
```

### Database Connection Pool Exhaustion

**Symptom:** "Connection pool exhausted" errors, timeouts

**Solution:**
```bash
# Increase connection pool size
export SQLALCHEMY_POOL_SIZE=20
export SQLALCHEMY_MAX_OVERFLOW=40
export SQLALCHEMY_POOL_TIMEOUT=30

# Restart server with new settings
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### High Failure Rate

**Symptom:** >5% failure rate with 500 errors

**Possible Causes:**
1. **Database overload**: Reduce concurrent users, increase pool size
2. **Memory pressure**: Check server memory usage, reduce user count
3. **Rate limiting**: Check if API has rate limits configured
4. **External service failures**: Check LLM provider, external APIs

**Debugging:**
```bash
# Check server logs
tail -f logs/atom.log | grep ERROR

# Monitor server resources
htop  # or top on macOS

# Check database connections
# For PostgreSQL:
psql -c "SELECT count(*) FROM pg_stat_activity;"
```

### Slow Response Times

**Symptom:** P95 > 2x Phase 208 targets

**Possible Causes:**
1. **Cache misses**: Cold cache, low hit rate
2. **Database queries**: Missing indexes, N+1 queries
3. **Network latency**: Local vs remote database
4. **Resource contention**: CPU, memory, disk I/O

**Debugging:**
```bash
# Check cache hit rate
curl http://localhost:8000/api/agent-governance/cache-stats

# Profile database queries
# Enable query logging in SQLAlchemy
export SQLALCHEMY_ECHO=true

# Run with profiling
python -m cProfile -o profile.stats -m uvicorn main:app
```

## CI Integration

### GitHub Actions Workflow

```yaml
name: Load Tests

on:
  schedule:
    # Run daily at 2 AM UTC
    - cron: '0 2 * * *'
  pull_request:
    paths:
      - 'backend/core/**'
      - 'backend/api/**'

jobs:
  load-test:
    name: Run Load Tests
    runs-on: ubuntu-large

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install -r requirements-testing.txt

      - name: Start application
        run: |
          cd backend
          python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
          sleep 10

      - name: Run load tests
        run: |
          cd backend
          locust -f tests/load/locustfile.py --headless \
            -u 100 \
            -r 10 \
            -t 5m \
            --html tests/load/reports/load-test-report.html \
            --json tests/load/reports/load-test-results.json

      - name: Upload load test report
        uses: actions/upload-artifact@v4
        with:
          name: load-test-report
          path: backend/tests/load/reports/load-test-report.html
```

### Quick Smoke Test for CI

For faster CI feedback, run a 2-minute smoke test:

```bash
locust -f tests/load/locustfile.py --headless \
  -u 50 \              # Fewer users for speed
  -r 5 \               # Slower spawn rate
  -t 2m \              # Shorter duration
  --exit-code-on-error  # Fail CI if load test fails
```

## Best Practices

1. **Warm up the cache**: Run for 1-2 minutes before collecting metrics
2. **Start small**: Begin with 50 users, scale up gradually
3. **Monitor resources**: Watch CPU, memory, database connections during test
4. **Use realistic data**: Test with production-like data volumes
5. **Run multiple times**: Performance can vary due to system load
6. **Compare to baseline**: Track performance over time to detect regressions
7. **Test in staging**: Never run load tests in production without limits

## Next Steps

After running load tests:
1. Review HTML report for detailed metrics
2. Compare P95 times to Phase 208 targets
3. Identify bottlenecks (database, cache, network)
4. Optimize slow endpoints
5. Re-run load tests to validate improvements
6. Update baseline metrics if performance improved

## References

- **Phase 208 Benchmarks**: `.planning/phases/208-integration-performance-testing/208-07-PERFORMANCE-METRICS.md`
- **Locust Documentation**: https://docs.locust.io/
- **Load Testing Research**: `.planning/phases/209-load-stress-testing/209-RESEARCH.md`
- **Monitoring Setup**: `backend/docs/MONITORING_SETUP.md`
