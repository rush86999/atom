# Phase 121 Health Monitoring Coverage - Baseline Snapshot

**Plan:** 121-01
**Date:** 2026-03-02
**Purpose:** Establish baseline coverage measurement for health check endpoints and monitoring infrastructure

## Executive Summary

| File | Statements | Covered | Coverage | Missing Lines | Status |
|------|-----------|---------|----------|---------------|---------|
| `api/health_routes.py` | 114 | 48 | **42.11%** | 66 lines | ⚠️ Below target |
| `core/monitoring.py` | 106 | 94 | **88.68%** | 12 lines | ✅ Exceeds target |
| **Combined** | **220** | **142** | **64.55%** | **78 lines** | ✅ **Above 60% target** |

**Overall Assessment:** Combined coverage of 64.55% exceeds the 60% target. The `core/monitoring.py` file is well-tested at 88.68%, while `api/health_routes.py` requires additional tests to reach 60% individually.

---

## Current Coverage Baseline

### api/health_routes.py: 42.11% (48 of 114 lines)

**Coverage Status:** ⚠️ 17.89 percentage points below 60% target

**Missing Lines (66 total):**
```
197-198, 200-201, 206, 208, 214-216, 221-223, 228-230, 239, 241-246,
317, 319, 321, 324-325, 327, 330, 338, 349-351, 353, 355-357, 370-371,
383-388, 394-395, 400-402, 536-540, 542-548, 553, 556, 600-601, 604, 607, 609
```

**Functions with Missing Coverage:**
- **Lines 188-246:** `_check_database()` - Database connectivity check with timeout handling
- **Lines 304-371:** `check_database_connectivity()` - DB health endpoint with connection pool metrics
- **Lines 374-406:** `_check_disk_space()` - Disk space check with psutil
- **Lines 517-556:** `sync_health_probe()` - Atom SaaS sync subsystem health check
- **Lines 586-609:** `sync_prometheus_metrics()` - Sync-specific Prometheus metrics endpoint

### core/monitoring.py: 88.68% (94 of 106 lines)

**Coverage Status:** ✅ 28.68 percentage points above 60% target

**Missing Lines (12 total):**
```
174-175, 182-183, 489-496
```

**Functions with Missing Coverage:**
- **Lines 170-175:** `add_log_level()` - Custom log level processor (not actively used)
- **Lines 178-183:** `add_logger_name()` - Custom logger name processor (not actively used)
- **Lines 483-496:** `initialize_metrics()` - Prometheus HTTP server startup (side effect, hard to test)

**Note:** Most missing lines in `monitoring.py` are for optional/custom processors and side-effect initialization (Prometheus HTTP server). The core metrics infrastructure is well-tested.

---

## Test Inventory

### test_health_routes.py (13 tests - 100% passing)

**Coverage:** 42.11% of `api/health_routes.py`

**Test Classes:**
1. `TestLivenessProbe` (2 tests)
   - `test_live_returns_200` - Verifies 200 response with alive status
   - `test_live_always_succeeds` - Confirms lightweight check behavior

2. `TestReadinessProbe` (4 tests)
   - `test_ready_returns_200_when_dependencies_healthy` - All checks passing
   - `test_ready_returns_503_when_database_unavailable` - DB failure handling
   - `test_ready_returns_503_when_disk_insufficient` - Low disk space handling
   - `test_ready_returns_503_when_both_dependencies_fail` - Multiple failures

3. `TestMetricsEndpoint` (4 tests)
   - `test_metrics_exposes_prometheus_format` - Prometheus text format
   - `test_metrics_includes_http_metrics` - HTTP metrics presence
   - `test_metrics_includes_agent_metrics` - Agent metrics presence
   - `test_metrics_includes_skill_metrics` - Skill metrics presence

4. `TestPerformance` (3 tests)
   - `test_liveness_probe_latency` - <10ms target (test allows 100ms)
   - `test_readiness_probe_latency` - <100ms target (test allows 500ms)
   - `test_metrics_endpoint_latency` - <50ms target (test allows 200ms)

### test_monitoring.py (30 tests - 100% passing)

**Coverage:** 88.68% of `core/monitoring.py`

**Test Classes:**
1. `TestPrometheusMetricsInitialization` (4 tests)
   - HTTP metrics (Counter, Histogram)
   - Agent metrics (Counter, Histogram, Gauge)
   - Skill metrics (Counter, Histogram)
   - DB metrics (Histogram, Gauge)

2. `TestDeploymentMetricsInitialization` (4 tests)
   - Deployment metrics (Counter, Histogram, Counter)
   - Canary metrics (Gauge)
   - Smoke test metrics (Counter, Histogram)
   - Prometheus query metrics (Counter, Histogram)

3. `TestStructlogConfiguration` (2 tests)
   - `test_configure_structlog` - Configuration succeeds
   - `test_get_logger_returns_bound_logger` - Logger creation

4. `TestRequestContext` (2 tests)
   - `test_request_context_binds_attributes` - Context binding
   - `test_request_context_restores_after_exit` - Context restoration

5. `TestMetricsHelpers` (6 tests)
   - `test_track_http_request` - HTTP metrics tracking
   - `test_track_agent_execution` - Agent metrics tracking
   - `test_track_skill_execution` - Skill metrics tracking
   - `test_track_db_query` - DB metrics tracking
   - `test_set_active_agents` - Active agents gauge
   - `test_set_db_connections` - DB connection metrics

6. `TestDeploymentMetricsHelpers` (6 tests)
   - `test_track_deployment_success` - Successful deployment tracking
   - `test_track_deployment_failure` - Failed deployment tracking
   - `test_track_smoke_test_success` - Successful smoke test tracking
   - `test_track_smoke_test_failure` - Failed smoke test tracking
   - `test_record_rollback` - Rollback event recording
   - `test_update_canary_traffic` - Canary traffic percentage update
   - `test_record_prometheus_query` - Prometheus query recording

### test_health_monitoring.py (9 tests - 5 passing, 4 failing)

**Note:** Tests for `HealthMonitoringService` (agent/integration health monitoring), NOT for health routes or monitoring infrastructure. The 4 failures are in a different service and do not block coverage measurement.

**Passing Tests (5/9):**
- `test_get_system_metrics` - System-wide metrics
- `test_get_active_alerts` - Active alerts retrieval
- `test_acknowledge_alert` - Alert acknowledgment
- Plus 2 other system/alert tests

**Failing Tests (4/9):**
- `test_get_agent_health_idle` - KeyError: 'agent_name'
- `test_get_agent_health_with_executions` - TypeError: 'user_id' invalid for AgentExecution
- `test_get_health_history` - IntegrityError: NOT NULL constraint failed
- `test_get_integration_health` - IntegrityError: NOT NULL constraint failed

**Note:** These failures relate to `HealthMonitoringService` (a different service) and do not affect coverage of `api/health_routes.py` or `core/monitoring.py`.

---

## Gap Summary

### High Priority Gaps (Zero Coverage)

**api/health_routes.py:**
1. **`check_database_connectivity()` endpoint** (Lines 304-371, 68 lines)
   - Purpose: Database connectivity health check with connection pool metrics
   - Status: 0% coverage (not tested at all)
   - Impact: HIGH - Critical for deployment smoke tests
   - Tests needed: 4-6 tests (success, timeout, slow query warning, exception handling)

2. **`sync_health_probe()` endpoint** (Lines 517-556, 40 lines)
   - Purpose: Atom SaaS sync subsystem health check
   - Status: 0% coverage (not tested at all)
   - Impact: HIGH - Monitoring for sync subsystem
   - Tests needed: 5-7 tests (healthy, degraded, unhealthy, error handling)

3. **`sync_prometheus_metrics()` endpoint** (Lines 586-609, 24 lines)
   - Purpose: Sync-specific Prometheus metrics endpoint
   - Status: 0% coverage (not tested at all)
   - Impact: MEDIUM - Metrics scraping endpoint
   - Tests needed: 2-3 tests (metrics format, metric types)

4. **`_check_database()` helper** (Lines 188-246, 59 lines)
   - Purpose: Database connectivity check with timeout (used by readiness probe)
   - Status: Partial coverage (called via readiness probe, but not fully tested)
   - Impact: MEDIUM - Error paths not tested
   - Tests needed: 3-4 tests (timeout, SQLAlchemy error, unexpected error)

5. **`_check_disk_space()` helper** (Lines 374-406, 33 lines)
   - Purpose: Disk space check with psutil (used by readiness probe)
   - Status: Partial coverage (called via readiness probe, but not fully tested)
   - Impact: MEDIUM - Error paths not tested
   - Tests needed: 2-3 tests (psutil exception handling)

**core/monitoring.py:**
1. **`initialize_metrics()` function** (Lines 483-496, 14 lines)
   - Purpose: Start Prometheus HTTP server on port 8001
   - Status: 0% coverage (side effect, hard to test)
   - Impact: LOW - Initialization function called at startup
   - Tests needed: 0-1 tests (optional - side effect testing)

### Medium Priority Gaps (Partial Coverage)

**api/health_routes.py:**
1. **Readiness probe error paths** (Lines 214-230, 17 lines missing)
   - Purpose: Database timeout and error handling
   - Status: Mocked in tests, but real error paths not exercised
   - Impact: MEDIUM - Error handling verification
   - Tests needed: 2-3 tests (timeout exception, SQLAlchemy error, generic exception)

2. **Database pool status checking** (Lines 330-336, 7 lines missing)
   - Purpose: Connection pool metrics in `check_database_connectivity()`
   - Status: Not tested (entire endpoint untested)
   - Impact: MEDIUM - Pool monitoring
   - Part of `check_database_connectivity()` tests needed

**core/monitoring.py:**
1. **Custom processors** (Lines 170-183, 14 lines missing)
   - Purpose: `add_log_level()` and `add_logger_name()` custom processors
   - Status: Not used (built-in structlog processors used instead)
   - Impact: LOW - Dead code if not actively used
   - Tests needed: 0 tests (unless used in production)

### Estimated Tests for 60% Target

**To reach 60% coverage for `api/health_routes.py` (currently 42.11%):**

| Gap Area | Tests Needed | Priority | Coverage Impact |
|----------|-------------|----------|-----------------|
| `check_database_connectivity()` endpoint | 4-6 tests | HIGH | +15-20% |
| `sync_health_probe()` endpoint | 5-7 tests | HIGH | +12-15% |
| `sync_prometheus_metrics()` endpoint | 2-3 tests | MEDIUM | +3-5% |
| `_check_database()` error paths | 3-4 tests | MEDIUM | +5-8% |
| `_check_disk_space()` error paths | 2-3 tests | LOW | +2-4% |
| **Total** | **16-23 tests** | | **+37-52% coverage** |

**Estimated Coverage After Plan 02:**
- `api/health_routes.py`: 42.11% + 37-52% = **79-94%** (exceeds 60% target)
- `core/monitoring.py`: 88.68% (already exceeds target)
- **Combined:** 64.55% + 15-25% = **80-90%**

**Note:** Even with minimal testing (16 tests focused on HIGH priority gaps), we can reach ~60% coverage for `api/health_routes.py`. Full gap-filling (23 tests) would achieve ~80%+ coverage.

---

## Next Steps (Plan 02)

### Priority 1: Database Connectivity Endpoint (HIGH)
**File:** `api/health_routes.py`
**Function:** `check_database_connectivity()` (Lines 304-371)
**Tests:** 4-6 tests
- Success case: Database accessible with pool status
- Slow query warning: Query >100ms triggers warning
- Exception handling: Database connection failure returns 503
- Pool metrics: Verify all pool fields returned

### Priority 2: Sync Health Probe (HIGH)
**File:** `api/health_routes.py`
**Function:** `sync_health_probe()` (Lines 517-556)
**Tests:** 5-7 tests
- Healthy: All checks passing (200 response)
- Degraded: Sync stale but not critical (200 response)
- Unhealthy: Critical checks failed (503 response)
- Error handling: SyncHealthMonitor exceptions handled
- Response structure: Verify all health check fields

### Priority 3: Database Error Paths (MEDIUM)
**File:** `api/health_routes.py`
**Function:** `_check_database()` (Lines 188-246)
**Tests:** 3-4 tests
- Timeout error: asyncio.TimeoutError returns unhealthy
- SQLAlchemy error: Database connection error returns unhealthy
- Generic error: Unexpected exceptions caught and logged

### Priority 4: Sync Metrics Endpoint (MEDIUM)
**File:** `api/health_routes.py`
**Function:** `sync_prometheus_metrics()` (Lines 586-609)
**Tests:** 2-3 tests
- Metrics format: Returns Prometheus text format
- Metric types: Includes sync-specific metrics
- Content type: text/plain; version=0.0.4

### Priority 5: Disk Space Error Paths (LOW)
**File:** `api/health_routes.py`
**Function:** `_check_disk_space()` (Lines 374-406)
**Tests:** 2-3 tests
- psutil exception: OSError handling returns unhealthy
- Exception logging: Errors logged appropriately

---

## Test Execution Summary

**Test Run Results:**
- **Total tests run:** 45 tests
- **Passed:** 41 tests (91.1%)
- **Failed:** 4 tests (8.9%)
- **Execution time:** 69 seconds

**Test Breakdown:**
- `test_health_routes.py`: 13/13 passing (100%)
- `test_monitoring.py`: 30/30 passing (100%)
- `test_health_monitoring.py`: 5/9 passing (55.6%)

**Blocking Failures:** None
**Note:** The 4 failing tests in `test_health_monitoring.py` are for `HealthMonitoringService` (a different service) and do not affect coverage measurement for `api/health_routes.py` or `core/monitoring.py`.

**Coverage Measurement Status:** ✅ Success
- Coverage JSON generated successfully
- Both target files measured accurately
- No blocking test failures preventing coverage measurement

---

## Conclusions

1. **Combined coverage of 64.55% exceeds 60% target** for the two files together
2. **`core/monitoring.py` is well-tested at 88.68%** - exceeds target by 28.68 pp
3. **`api/health_routes.py` needs gap-filling tests** - currently at 42.11% (17.89 pp below target)
4. **16-23 tests estimated to reach 60%+ coverage** for `api/health_routes.py`
5. **No blocking test failures** - coverage measurement completed successfully

**Recommendation:** Proceed with Plan 02 to add gap-filling tests for `api/health_routes.py`, focusing on HIGH priority gaps (database connectivity endpoint, sync health probe) to reach 60%+ coverage.
