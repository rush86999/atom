# Phase 121 Plan 02: Coverage Gap Analysis

**Date**: 2026-03-02
**Wave**: 2
**Purpose**: Analyze coverage gaps and create prioritized test list for health monitoring system

---

## Executive Summary

**Combined Coverage**: 65.39% (exceeds 60% target)
- **api/health_routes.py**: 42.11% (48/114 lines covered, 66 missing)
- **core/monitoring.py**: 88.68% (94/106 lines covered, 12 missing)

**Target**: 60% coverage per file
**Status**: Combined target met, but health_routes.py needs improvement

---

## Coverage by File

### api/health_routes.py
- **Current Coverage**: 42.11%
- **Target Coverage**: 60%
- **Gap**: 17.89 percentage points
- **Missing Lines**: 66
- **Tests Estimated**: ~26 tests to reach 60%

### core/monitoring.py
- **Current Coverage**: 88.68%
- **Target Coverage**: 60%
- **Status**: ✅ Already exceeds target by 28.68 points
- **Missing Lines**: 12 (low impact functions)

---

## Coverage Gaps: api/health_routes.py

### Gap 1: _execute_db_query() - 30.0% coverage
- **Lines**: 237-246 (10 lines total, 7 missing)
- **Impact**: MEDIUM
- **Missing Lines**: [239, 241, 242, 243, 244, 245, 246]
- **Tests Needed**:
  1. Test successful database query execution
  2. Test database exception handling
  3. Test session cleanup on error
- **Estimated Coverage Gain**: +5-7%

### Gap 2: _check_database() - 68.1% coverage
- **Lines**: 188-234 (47 lines total, 15 missing)
- **Impact**: HIGH
- **Missing Lines**: [197, 198, 200, 201, 206, 208, 214, 215, 216, 221, 222, 223, 228, 229, 230]
- **Tests Needed**:
  1. Test successful database connectivity check
  2. Test asyncio.TimeoutError path
  3. Test SQLAlchemyError exception path
  4. Test generic exception path
- **Estimated Coverage Gain**: +8-10%

### Gap 3: _check_disk_space() - 69.7% coverage
- **Lines**: 374-406 (33 lines total, 10 missing)
- **Impact**: MEDIUM
- **Missing Lines**: [383, 384, 385, 387, 388, 394, 395, 400, 401, 402]
- **Tests Needed**:
  1. Test sufficient disk space path
  2. Test low disk space warning path
  3. Test psutil exception handling
- **Estimated Coverage Gain**: +5-7%

### Gap 4: check_database_connectivity() - 75.0% coverage
- **Lines**: 304-371 (68 lines total, 17 missing)
- **Impact**: HIGH
- **Missing Lines**: [317, 319, 321, 324, 325, 327, 330, 338, 349, 350, 351, 353, 355, 356, 357, 370, 371]
- **Tests Needed**:
  1. Test successful database pool status retrieval
  2. Test slow query warning path (>100ms)
  3. Test exception handling with HTTPException 503
  4. Test session cleanup in finally block
- **Estimated Coverage Gain**: +6-8%

### Gap 5: sync_health_probe() - 70.0% coverage
- **Lines**: 517-556 (40 lines total, 12 missing)
- **Impact**: HIGH
- **Missing Lines**: [536, 538, 539, 540, 542, 543, 544, 546, 547, 548, 553, 556]
- **Tests Needed**:
  1. Test sync health monitor integration
  2. Test healthy status (200 response)
  3. Test unhealthy status (503 response)
  4. Test JSONResponse for non-200 status
  5. Test database session cleanup
- **Estimated Coverage Gain**: +6-8%

### Gap 6: sync_prometheus_metrics() - 79.2% coverage
- **Lines**: 586-609 (24 lines total, 5 missing)
- **Impact**: LOW
- **Missing Lines**: [600, 601, 604, 607, 609]
- **Tests Needed**:
  1. Test sync metrics import and generation
  2. Test Prometheus REGISTRY usage
  3. Test Response content-type
- **Estimated Coverage Gain**: +3-4%

---

## Coverage Gaps: core/monitoring.py

**Note**: core/monitoring.py already exceeds 60% target at 88.68%. These gaps are low priority.

### Gap 7: initialize_metrics() - 42.9% coverage
- **Lines**: 483-496 (14 lines total, 8 missing)
- **Impact**: MEDIUM (but low priority since target met)
- **Missing Lines**: [489, 490, 491, 492, 493, 494, 495, 496]
- **Tests Needed**:
  1. Test successful Prometheus server startup
  2. Test OSError handling (server already running)
  3. Test logging on startup
- **Estimated Coverage Gain**: +4-5%

### Gap 8: add_log_level() - 66.7% coverage
- **Lines**: 170-175 (6 lines total, 2 missing)
- **Impact**: LOW
- **Missing Lines**: [174, 175]
- **Tests Needed**:
  1. Test log level addition to event dict
- **Estimated Coverage Gain**: +1-2%

### Gap 9: add_logger_name() - 66.7% coverage
- **Lines**: 178-183 (6 lines total, 2 missing)
- **Impact**: LOW
- **Missing Lines**: [182, 183]
- **Tests Needed**:
  1. Test logger name addition to event dict
- **Estimated Coverage Gain**: +1-2%

---

## Prioritized Test List (Highest ROI)

### Priority 1: HIGH Impact Gaps (health_routes.py)

1. **_check_database() - Timeout & Error Paths**
   - Test asyncio.TimeoutError (line 214-220)
   - Test SQLAlchemyError (line 221-227)
   - Test generic Exception (line 228-234)
   - **Coverage Gain**: +8-10%

2. **check_database_connectivity() - Pool Status & Errors**
   - Test connection pool status retrieval (line 330-336)
   - Test slow query warning (line 349-351)
   - Test HTTPException 503 on error (line 357-367)
   - **Coverage Gain**: +6-8%

3. **sync_health_probe() - Integration Tests**
   - Test sync health monitor call (line 536-543)
   - Test JSONResponse for non-200 status (line 546-551)
   - Test database session cleanup (line 555-556)
   - **Coverage Gain**: +6-8%

### Priority 2: MEDIUM Impact Gaps

4. **_execute_db_query() - Query Execution**
   - Test successful query execution (line 241-243)
   - Test exception handling (line 244-246)
   - **Coverage Gain**: +5-7%

5. **_check_disk_space() - Disk Space Checks**
   - Test sufficient disk space (line 387-392)
   - Test low disk space warning (line 394-399)
   - Test psutil exception (line 400-406)
   - **Coverage Gain**: +5-7%

### Priority 3: LOW Priority (Optional)

6. **sync_prometheus_metrics() - Metrics Export**
   - Test metrics generation (line 604-609)
   - **Coverage Gain**: +3-4%

7. **initialize_metrics() - Server Startup**
   - Test Prometheus server startup (line 489-496)
   - **Coverage Gain**: +4-5%

---

## Test Count Estimate

### Formula
```
current_coverage = 42.11%
target_coverage = 60%
gap = 60 - 42.11 = 17.89 percentage points
estimated_tests_per_pct = 1.5 tests (based on existing test density)
tests_needed = 17.89 * 1.5 ≈ 26 tests
```

### By File

| File | Current | Target | Gap | Tests Needed |
|------|---------|--------|-----|--------------|
| api/health_routes.py | 42.11% | 60% | +17.89% | ~26 tests |
| core/monitoring.py | 88.68% | 60% | (exceeds) | 0 tests |
| **Total** | **65.39%** | **60%** | **combined met** | **~26 tests** |

### Test Allocation by Plan

- **Plan 01** (baseline): 30 tests created
- **Plan 02** (gap analysis): 0 new tests (analysis only)
- **Plan 03** (add tests): ~26 tests to reach 60% target

---

## Detailed Function Coverage Analysis

### api/health_routes.py Functions

| Function | Lines | Coverage | Missing | Impact |
|----------|-------|----------|---------|--------|
| liveness_probe | 65-81 | 100% | 0 | NONE |
| readiness_probe | 142-185 | 86.5% | 9 | LOW |
| _check_database | 188-234 | 68.1% | 15 | HIGH |
| _execute_db_query | 237-246 | 30.0% | 7 | MEDIUM |
| check_database_connectivity | 304-371 | 75.0% | 17 | HIGH |
| _check_disk_space | 374-406 | 69.7% | 10 | MEDIUM |
| prometheus_metrics | 435-447 | 100% | 0 | NONE |
| sync_health_probe | 517-556 | 70.0% | 12 | HIGH |
| sync_prometheus_metrics | 586-609 | 79.2% | 5 | LOW |

### core/monitoring.py Functions

| Function | Lines | Coverage | Missing | Impact |
|----------|-------|----------|---------|--------|
| add_log_level | 170-175 | 66.7% | 2 | LOW |
| add_logger_name | 178-183 | 66.7% | 2 | LOW |
| configure_structlog | 186-240 | 100% | 0 | NONE |
| get_logger | 243-257 | 100% | 0 | NONE |
| RequestContext.__init__ | 270-273 | 100% | 0 | NONE |
| RequestContext.__enter__ | 275-280 | 100% | 0 | NONE |
| RequestContext.__exit__ | 282-285 | 100% | 0 | NONE |
| track_http_request | 293-312 | 100% | 0 | NONE |
| track_agent_execution | 315-331 | 100% | 0 | NONE |
| track_skill_execution | 334-350 | 100% | 0 | NONE |
| track_db_query | 353-363 | 100% | 0 | NONE |
| set_active_agents | 366-373 | 100% | 0 | NONE |
| set_db_connections | 376-385 | 100% | 0 | NONE |
| track_deployment | 393-415 | 100% | 0 | NONE |
| track_smoke_test | 418-440 | 100% | 0 | NONE |
| record_rollback | 443-451 | 100% | 0 | NONE |
| update_canary_traffic | 454-466 | 100% | 0 | NONE |
| record_prometheus_query | 469-480 | 100% | 0 | NONE |
| initialize_metrics | 483-496 | 42.9% | 8 | MEDIUM |

---

## Test Specifications for Plan 03

### Specification 1: _check_database() Timeout Path
```python
async def test_check_database_timeout():
    """Test database health check timeout handling."""
    # Mock asyncio.wait_for to raise TimeoutError
    # Verify returns {"healthy": False, "message": "Database timeout after 5.0s"}
    # Verify latency_ms = 5000.0
```

### Specification 2: _check_database() SQLAlchemy Error Path
```python
async def test_check_database_sqlalchemy_error():
    """Test database health check SQLAlchemy exception handling."""
    # Mock db.execute to raise SQLAlchemyError
    # Verify returns {"healthy": False, "message": "Database error: ..."}
    # Verify latency_ms = 0
```

### Specification 3: _check_database() Generic Exception Path
```python
async def test_check_database_generic_exception():
    """Test database health check generic exception handling."""
    # Mock db.execute to raise generic Exception
    # Verify returns {"healthy": False, "message": "Unexpected error: ..."}
```

### Specification 4: check_database_connectivity() Pool Status
```python
async def test_check_database_connectivity_pool_status():
    """Test database connectivity with pool status."""
    # Verify pool status keys: size, checked_in, checked_out, overflow, max_overflow
    # Verify query_time_ms is rounded to 2 decimals
```

### Specification 5: check_database_connectivity() Slow Query Warning
```python
async def test_check_database_connectivity_slow_query_warning():
    """Test slow query warning (>100ms)."""
    # Mock query execution to take >100ms
    # Verify warning field added to response
    # Verify logger.warning called
```

### Specification 6: check_database_connectivity() Exception Handling
```python
async def test_check_database_connectivity_exception():
    """Test database connectivity exception handling."""
    # Mock db.execute to raise Exception
    # Verify raises HTTPException 503
    # Verify response contains status="unhealthy"
```

### Specification 7: sync_health_probe() Healthy Status
```python
async def test_sync_health_probe_healthy():
    """Test sync health probe returns healthy status."""
    # Mock get_sync_health_monitor().check_health to return healthy status
    # Verify returns 200 with health_status dict
```

### Specification 8: sync_health_probe() Unhealthy Status
```python
async def test_sync_health_probe_unhealthy():
    """Test sync health probe returns unhealthy status."""
    # Mock get_sync_health_monitor().check_health to return unhealthy status
    # Mock get_http_status to return 503
    # Verify returns JSONResponse with status_code=503
```

### Specification 9: _execute_db_query() Success Path
```python
async def test_execute_db_query_success():
    """Test successful database query execution."""
    # Mock db_session.execute to return result
    # Verify returns True
```

### Specification 10: _execute_db_query() Exception Path
```python
async def test_execute_db_query_exception():
    """Test database query exception handling."""
    # Mock db_session.execute to raise Exception
    # Verify raises Exception
    # Verify logger.error called
```

### Specification 11: _check_disk_space() Sufficient Space
```python
async def test_check_disk_space_sufficient():
    """Test disk space check with sufficient space."""
    # Mock psutil.disk_usage to return >1GB free
    # Verify returns {"healthy": True, "message": "{X:.2f}GB free"}
```

### Specification 12: _check_disk_space() Low Space
```python
async def test_check_disk_space_low():
    """Test disk space check with low space."""
    # Mock psutil.disk_usage to return <1GB free
    # Verify returns {"healthy": False}
    # Verify message includes "Low disk space"
    # Verify logger.warning called
```

### Specification 13: _check_disk_space() Exception Handling
```python
async def test_check_disk_space_exception():
    """Test disk space check exception handling."""
    # Mock psutil.disk_usage to raise Exception
    # Verify returns {"healthy": False, "message": "Disk check error: ..."}
    # Verify logger.error called
```

---

## Success Criteria for Plan 03

After implementing tests in Plan 03:

1. ✅ api/health_routes.py coverage ≥ 60%
2. ✅ All HIGH impact gaps have tests
3. ✅ All MEDIUM impact gaps have tests
4. ✅ Combined coverage remains ≥ 60%
5. ✅ Zero regression in existing tests

---

## Next Steps

**Plan 03**: Add gap-filling tests
- Implement 13 test specifications above
- Target: 60%+ coverage for api/health_routes.py
- Validate combined coverage ≥ 60%
- Update baseline metrics

**Link**: 121-03-PLAN.md will use this gap analysis to implement tests
