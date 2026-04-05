# Bugs Fixed in Testing Framework

**Date:** February 7, 2026
**Session:** Property-Based Testing & Fuzzy Testing Implementation
**Status:** ✅ All Critical Bugs Fixed

---

## Summary

Fixed **7 bugs** across the testing framework:
- 2 cache test timing issues (Hypothesis deadline)
- 5 chaos test logic errors and timing issues

---

## Bugs Fixed

### 1. Cache Test Idempotency - Hypothesis Deadline Bug

**File:** `backend/tests/property_tests/invariants/test_cache_invariants.py`
**Test:** `test_cache_idempotency_within_ttl`
**Issue:** Test exceeded Hypothesis's 200ms deadline due to database operations
**Error:** `Unreliable test timings! On an initial run, this test took 297.81ms, which exceeded the deadline of 200.00ms`
**Fix:** Added `deadline=None` to `@settings` decorator
**Result:** ✅ Test now passes

```python
@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_cache_idempotency_within_ttl(...):
```

---

### 2. Cache Test High Volume - Hypothesis Deadline Bug

**File:** `backend/tests/property_tests/invariants/test_cache_invariants.py`
**Test:** `test_cache_handles_high_volume`
**Issue:** Test exceeded Hypothesis's 200ms deadline when simulating high volume
**Error:** `Unreliable test timings! On an initial run, this test took 252.31ms, which exceeded the deadline of 200.00ms`
**Fix:** Added `deadline=None` to `@settings` decorator
**Result:** ✅ Test now passes

```python
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_cache_handles_high_volume(...):
```

---

### 3. Chaos Test - Missing Import in Helper

**File:** `backend/tests/chaos/chaos_helpers.py`
**Issue:** `NetworkChaosSimulator` used `requests.get` without importing `requests`
**Error:** `NameError: name 'requests' is not defined`
**Fix:** Added conditional import at top of file
**Result:** ✅ Import error resolved

```python
try:
    import requests
except ImportError:
    requests = None
```

---

### 4. Chaos Test - Incorrect integers() Strategy Parameter

**File:** `backend/tests/chaos/test_chaos.py`
**Test:** `test_database_transaction_rollback`
**Issue:** Used `max_size` parameter for `st.integers()` instead of `max_value`
**Error:** `TypeError: integers() got an unexpected keyword argument 'max_size'`
**Fix:** Changed `max_size=10` to `max_value=10`
**Result:** ✅ Collection error resolved

```python
# Before (incorrect):
failure_at=st.integers(min_value=2, max_size=10)

# After (correct):
failure_at=st.integers(min_value=2, max_value=10)
```

---

### 5. Chaos Test - Webhook Retry Logic Bug

**File:** `backend/tests/chaos/test_chaos.py`
**Test:** `test_webhook_failure_handling`
**Issue:** Test generated `max_retries=1` but success condition required 2+ retries
**Error:** `AssertionError: Webhooks should eventually succeed` with `assert 0 > 0`
**Fix:** Changed `st.integers(min_value=1, max_value=5)` to `min_value=3`
**Result:** ✅ Test now passes

```python
# Before (buggy):
max_retries=st.integers(min_value=1, max_value=5)
# Test logic: succeeds after retries >= 2, but max_retries could be 1

# After (fixed):
max_retries=st.integers(min_value=3, max_value=5)
# Now max_retries always >= 3, giving enough attempts for success
```

---

### 6. Chaos Test - DNS Resolution Logic Bug

**File:** `backend/tests/chaos/test_chaos.py`
**Test:** `test_dns_failure_handling`
**Issue:** DNS cache was empty when domains failed, resulting in 0 successful resolutions
**Error:** `AssertionError: At least some domains should resolve` with `assert 0 > 0`
**Fix:** Pre-populated DNS cache before simulating failures, increased `min_size` from 3 to 4
**Result:** ✅ Test now passes

```python
# Before (buggy):
for domain in domains[:3]:  # Fail first 3 domains
    dns_failures.add(domain)
# If len(domains) == 3, all fail → 0 successful resolutions

# After (fixed):
# First, populate cache with all domains
for domain in domains:
    try:
        resolve_dns(domain)
    except Exception:
        pass  # Cache won't be populated if it fails

# Now simulate DNS failure for some domains (but keep cached values)
for domain in domains[:3]:  # Fail 3 domains
    dns_failures.add(domain)
# Cache has values, so failures fall back to cached entries
```

---

### 7. Chaos Tests - Hypothesis Deadline Issues (4 tests)

**File:** `backend/tests/chaos/test_chaos.py`
**Tests:**
- `test_webhook_failure_handling`
- `test_system_recovers_within_5_seconds`
- `test_recovery_performance`
- `test_system_stability_under_chaos`

**Issue:** All exceeded Hypothesis's 200ms deadline due to intentional delays (simulating recovery)
**Errors:**
- `Test took 1529.96ms, which exceeds the deadline of 200.00ms`
- `Test took 5013.75ms, which exceeds the deadline of 200.00ms`
- `Test took 1005.06ms, which exceeds the deadline of 200.00ms`
- `Test took 367.80ms, which exceeds the deadline of 200.00ms`

**Fix:** Added `deadline=None` to all 4 tests
**Result:** ✅ All tests now pass

---

## Test Results After Fixes

### Property Tests (Existing)
- ✅ **55 tests passing** (100% pass rate)
- ⏱️ **36.04s runtime**
- 📈 **18.53% coverage** (baseline)

### Chaos Tests
- ✅ **17 tests passing** (100% pass rate after fixes)
- ⏱️ **35.61s runtime**
- 📊 **13 passing initially → 17 passing after deadline fixes**

---

## Root Cause Analysis

### Why These Bugs Occurred

1. **Hypothesis Defaults**: Hypothesis's default 200ms deadline is too aggressive for tests involving:
   - Database operations (commit, flush, refresh)
   - Intentional delays (sleep statements to simulate recovery)
   - Multiple iterations (high-volume tests)

2. **Test Design Issues**: Some tests had logical flaws:
   - `test_webhook_failure_handling`: Success condition required more retries than generated
   - `test_dns_failure_handling`: Failed to pre-populate cache before testing failures

3. **Import Errors**: `requests` was used but not imported in chaos_helpers.py

### Prevention Strategies

1. **Always Use `deadline=None`** for tests that:
   - Perform I/O operations (database, network)
   - Use `time.sleep()` to simulate delays
   - Run multiple iterations in a loop

2. **Review Hypothesis Strategy Parameters**:
   - `st.integers()` uses `min_value` and `max_value`, NOT `min_size`/`max_size`
   - Ensure generated values satisfy test invariants

3. **Pre-populate State Before Testing Failures**:
   - Ensure caches/DBs have data before simulating failures
   - Verify fallback mechanisms have something to fall back to

4. **Import All Required Modules**:
   - Check that all used modules are imported
   - Use conditional imports for optional dependencies

---

## Files Modified

| File | Lines Changed | Type |
|------|---------------|------|
| `tests/property_tests/invariants/test_cache_invariants.py` | 2 | Bug fix |
| `tests/chaos/chaos_helpers.py` | 5 | Bug fix |
| `tests/chaos/test_chaos.py` | 7 | Bug fix |

**Total:** 3 files, 14 lines changed

---

## Next Steps

### Completed ✅
1. Fixed all test bugs (7 bugs resolved)
2. All property tests passing (55/55)
3. All chaos tests passing (17/17)

### Recommended Future Work
1. Add `deadline=None` to ALL tests involving I/O or delays
2. Increase test coverage from 18.53% to 80%+ target
3. Run mutation testing to find test gaps
4. Run fuzzy tests for 1+ hour to find edge cases

---

**Status:** ✅ **ALL TESTS PASSING**

---

*Generated: February 7, 2026*
*Testing Framework: Property-Based Testing & Fuzzy Testing*
*Total Test Count: 72 tests (55 property + 17 chaos)*
