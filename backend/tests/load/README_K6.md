# Load Testing with k6

This directory contains k6 load tests for validating Atom API performance under concurrent user load.

## Overview

Load testing simulates multiple concurrent users interacting with the API to identify performance bottlenecks, establish capacity limits, and validate that performance benchmarks hold under load.

**Why k6?**
- Modern, developer-friendly load testing tool
- JavaScript-based test scripts (easy to extend)
- Great CI/CD integration
- Built-in metrics and thresholds
- Cloud-based execution available (k6 Cloud)

**Why Add k6 Alongside Locust?**
- **k6**: Better for CI/CD automation, simpler syntax, built-in thresholds
- **Locust**: Better for interactive testing, web UI, distributed load testing

## Prerequisites

### 1. Install k6

**macOS (Homebrew):**
```bash
brew install k6
```

**Linux:**
```bash
curl https://github.com/grafana/k6/releases/download/v0.51.0/k6-v0.51.0-linux-amd64.tar.gz -L | tar xvz
sudo mv k6-v0.51.0-linux-amd64/k6 /usr/local/bin/
```

**Windows:**
```bash
chocolatey install k6
```

**Verify installation:**
```bash
k6 version
```

### 2. Start Application

Ensure the Atom backend is running:

```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### 3. Create Test User (Optional)

Load tests use `load_test@example.com` with password `test_password_123`. Create this user via:

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "load_test@example.com", "password": "test_password_123"}'
```

## Running Tests

### Quick Test (Development)

Run a quick test for fast feedback:

```bash
cd backend/tests/load
k6 run test_api_load_baseline.js --duration 30s --vus 5
```

### Full Baseline Test (10 Users)

Establish baseline performance:

```bash
cd backend/tests/load
k6 run test_api_load_baseline.js
```

**Duration:** 6 minutes (2m ramp-up, 3m sustained, 1m ramp-down)
**Users:** 10 concurrent
**Thresholds:** p(95)<500ms, error rate <5%

### Moderate Load Test (50 Users)

Test under moderate concurrent load:

```bash
cd backend/tests/load
k6 run test_api_load_moderate.js
```

**Duration:** 17 minutes (5m ramp-up, 10m sustained, 2m ramp-down)
**Users:** 50 concurrent
**Thresholds:** p(95)<800ms, error rate <10%

### High Load Test (100 Users)

Test under high concurrent load:

```bash
cd backend/tests/load
k6 run test_api_load_high.js
```

**Duration:** 28 minutes (10m ramp-up, 15m sustained, 3m ramp-down)
**Users:** 100 concurrent
**Thresholds:** p(95)<1200ms, error rate <15%

### Web UI Load Test (20 Users)

Test realistic web UI user flows:

```bash
cd backend/tests/load
k6 run test_web_ui_load.js
```

**Duration:** 9 minutes (3m ramp-up, 5m sustained, 1m ramp-down)
**Users:** 20 concurrent
**Thresholds:** p(95)<1000ms, error rate <10%

## Environment Variables

Configure the API URL:

```bash
# Default: http://localhost:8000
export API_URL="http://localhost:8000"

# Run with custom API URL
API_URL="http://staging.example.com" k6 run test_api_load_baseline.js
```

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
- Target: <5% for baseline, <15% for high load
- Common failures: 500 (server error), 503 (service unavailable)

**Checks:**
- Custom validation checks (e.g., "login successful", "agent execution started")
- Pass rate indicates percentage of checks that passed
- Target: >90% for baseline, >85% for high load

### Example Output

```
Baseline Load Test Summary
========================

Total Requests: 1234
Failed Requests: 45
Failure Rate: 3.65%

Response Times:
  P50: 180ms
  P95: 420ms
  P99: 780ms

Checks:
  Passed: 1150
  Failed: 84
  Pass Rate: 93.19%

running (06.0s), 000/10 VUs, 1234 complete and 0 interrupted iterations
✓ /api/auth/login [ 96% ]
  ✓ has status 200
  ✓ received token
✓ /api/v1/agents/execute [ 91% ]
  ✓ agent execution started
```

### Performance Indicators

**Good Performance:**
- P95 response time meets thresholds
- Failure rate below target
- RPS scales linearly with user count
- No response time spikes as user count increases

**Performance Issues:**
- P95 response time increases with user count (bottleneck)
- Failure rate exceeds target (capacity limit)
- RPS plateaus or decreases (system overload)
- Response time spikes during test (resource exhaustion)

## CI/CD Integration

### GitHub Actions Workflow

```yaml
name: Load Tests (k6)

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

      - name: Install k6
        run: |
          curl https://github.com/grafana/k6/releases/download/v0.51.0/k6-v0.51.0-linux-amd64.tar.gz -L | tar xvz
          sudo mv k6-v0.51.0-linux-amd64/k6 /usr/local/bin/

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt

      - name: Start application
        run: |
          cd backend
          python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
          sleep 10

      - name: Run baseline load test
        run: |
          cd backend/tests/load
          k6 run test_api_load_baseline.js --duration 2m --vus 10

      - name: Upload load test results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: k6-load-test-results
          path: backend/tests/load/reports/
```

### Quick Smoke Test for CI

For faster CI feedback, run a 1-minute smoke test:

```bash
k6 run test_api_load_baseline.js --duration 1m --vus 5
```

## Test Scenarios

### test_api_load_baseline.js (10 Users)

**Scenarios:**
- 60% Authentication flow (login)
- 40% Agent execution (list + execute)

**Purpose:** Establish baseline performance metrics

### test_api_load_moderate.js (50 Users)

**Scenarios:**
- 50% Authentication (login, logout)
- 30% Agent execution (GET agents, POST execute)
- 20% Canvas operations (GET canvas, POST present)

**Purpose:** Validate system performance under moderate load

### test_api_load_high.js (100 Users)

**Scenarios:**
- 40% Authentication
- 35% Agent execution
- 15% Canvas operations
- 10% Workflow execution

**Purpose:** Identify system breaking point and capacity limits

### test_web_ui_load.js (20 Users)

**User Flow:**
1. GET / (load homepage)
2. POST /api/auth/login (authenticate)
3. GET /dashboard (load dashboard)
4. GET /api/v1/agents (list agents)
5. POST /api/v1/agents/execute (execute agent)
6. GET /api/v1/canvas/{id} (view canvas)
7. POST /api/v1/canvas/present (present canvas)
8. GET /api/v1/workflows (list workflows, optional)
9. POST /api/auth/logout (logout, optional)

**Purpose:** Simulate realistic web UI user behavior

## Troubleshooting

### k6 Not Found

**Symptom:** `k6: command not found`

**Solution:**
```bash
# macOS
brew install k6

# Linux
curl https://github.com/grafana/k6/releases/download/v0.51.0/k6-v0.51.0-linux-amd64.tar.gz -L | tar xvz
sudo mv k6-v0.51.0-linux-amd64/k6 /usr/local/bin/
```

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
- Load tests use `load_test@example.com` with password `test_password_123`
- Ensure test user exists in database
- Check authentication endpoint is working:
  ```bash
  curl -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "load_test@example.com", "password": "test_password_123"}'
  ```

### High Failure Rate

**Symptom:** >15% failure rate with 500 errors

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

**Symptom:** P95 > 2x target thresholds

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

## Best Practices

1. **Warm up the cache**: Run for 1-2 minutes before collecting metrics
2. **Start small**: Begin with 10 users, scale up gradually
3. **Monitor resources**: Watch CPU, memory, database connections during test
4. **Use realistic data**: Test with production-like data volumes
5. **Run multiple times**: Performance can vary due to system load
6. **Compare to baseline**: Track performance over time to detect regressions
7. **Test in staging**: Never run load tests in production without limits
8. **Automate in CI**: Run smoke tests on every PR, full tests nightly

## Next Steps

After running load tests:
1. Review HTML report for detailed metrics (if using Locust)
2. Compare P95 times to target thresholds
3. Identify bottlenecks (database, cache, network)
4. Optimize slow endpoints
5. Re-run load tests to validate improvements
6. Update baseline metrics if performance improved

## References

- **k6 Documentation**: https://k6.io/docs/
- **k6 Examples**: https://k6.io/docs/examples/
- **Locust Load Tests**: `README.md` (Locust-based tests)
- **Phase 208 Benchmarks**: `.planning/phases/208-integration-performance-testing/208-07-PERFORMANCE-METRICS.md`
- **Monitoring Setup**: `backend/docs/MONITORING_SETUP.md`

## Comparison: k6 vs Locust

| Feature | k6 | Locust |
|---------|----|----|
| Language | JavaScript | Python |
| Learning Curve | Low (JS familiarity) | Low (Python familiarity) |
| CI/CD Integration | Excellent (native CLI) | Good (requires web UI or headless mode) |
| Interactive Web UI | No | Yes (built-in) |
| Distributed Load | k6 Cloud (paid) | Built-in (master/worker) |
| Thresholds | Built-in | Manual checks |
| Best For | CI/CD, automation | Interactive testing, distributed load |

**Recommendation:** Use k6 for CI/CD automation and Locust for interactive testing/distributed load.
