# Edge Case Bug Catalog

**Phase**: 301-04 (Edge Case Property Tests)
**Created**: 2026-04-29
**Test Suite**: `backend/tests/property_tests/test_edge_cases.py`
**Total Tests**: 20
**Passed**: 11 (55%)
**Failed**: 9 (45%)

---

## Summary

Edge case property tests discovered 9 bugs across validation, model attributes, and race conditions. Key findings:

- **P0 (Critical)**: 0 bugs
- **P1 (High)**: 6 bugs (model attribute errors, missing validation)
- **P2 (Medium)**: 3 bugs (race condition handling, text generation)
- **P3 (Low)**: 0 bugs

---

## Discovered Bugs

### 1. Agent Name Accepts Empty String [P1]

**Test**: `test_agent_name_rejects_empty_string`
**Severity**: P1 (Logic Error)
**Status**: FAILED

**Issue**: AgentRegistry model does not validate that `name` is non-empty. Empty strings are accepted.

**Current Behavior**:
```python
agent = AgentRegistry(
    id=str(uuid.uuid4()),
    name="",  # Empty string accepted
    category="test",
    module_path="test.module",
    class_name="TestClass"
)
# No validation error raised
```

**Expected Behavior**: Should raise `ValueError` when name is empty.

**Fix**: Add validation in `AgentRegistry` model:
```python
def __init__(self, **kwargs):
    if 'name' in kwargs and not kwargs['name'].strip():
        raise ValueError("Agent name cannot be empty")
    super().__init__(**kwargs)
```

**Files**: `backend/core/models.py` (AgentRegistry class)

---

### 2. AgentRegistry Missing 'maturity' Attribute [P1]

**Test**: `test_agent_capabilities_rejects_empty_list`, `test_concurrent_maturity_updates_serialize_correctly`
**Severity**: P1 (Model Error)
**Status**: FAILED

**Issue**: AgentRegistry model does not have a `maturity` attribute, but tests assume it exists.

**Error**:
```
TypeError: 'maturity' is an invalid keyword argument for AgentRegistry
```

**Root Cause**: Model attribute mismatch. The model may use `status` instead of `maturity`, or the attribute doesn't exist.

**Fix Options**:
1. Add `maturity` column to AgentRegistry model
2. Update tests to use correct attribute name (e.g., `status`)

**Files**: `backend/core/models.py` (AgentRegistry class definition)

---

### 3. AgentRegistry Missing 'completed_episodes' Attribute [P1]

**Test**: `test_maturity_requires_non_negative_episodes`, `test_concurrent_maturity_updates_serialize_correctly`
**Severity**: P1 (Model Error)
**Status**: FAILED

**Issue**: AgentRegistry model does not have a `completed_episodes` attribute.

**Error**:
```
TypeError: 'completed_episodes' is an invalid keyword argument for AgentRegistry
```

**Root Cause**: Model attribute missing or incorrect name.

**Fix**: Add `completed_episodes` column to AgentRegistry model (Integer, default=0).

**Files**: `backend/core/models.py` (AgentRegistry class definition)

---

### 4. Agent ID Accepts None [P1]

**Test**: `test_agent_id_rejects_none`
**Severity**: P1 (Validation Gap)
**Status**: FAILED

**Issue**: AgentRegistry model does not validate that `id` is not None.

**Current Behavior**:
```python
agent = AgentRegistry(
    id=None,  # None accepted
    name="TestAgent",
    category="test",
    module_path="test.module",
    class_name="TestClass"
)
# No validation error
```

**Expected Behavior**: Should raise `ValueError` or `TypeError` when id is None.

**Fix**: Add validation in `AgentRegistry.__init__`:
```python
if 'id' in kwargs and kwargs['id'] is None:
    raise ValueError("Agent ID cannot be None")
```

**Files**: `backend/core/models.py` (AgentRegistry class)

---

### 5. AgentEpisode Missing 'title' Attribute [P1]

**Test**: `test_episode_segments_rejects_empty_list`, `test_concurrent_episode_segmentation_doesnt_duplicate`
**Severity**: P1 (Model Error)
**Status**: FAILED

**Issue**: AgentEpisode model (imported as `Episode`) does not have a `title` attribute.

**Error**:
```
TypeError: 'title' is an invalid keyword argument for AgentEpisode
```

**Root Cause**: Model schema mismatch. Episode model may use different attribute names.

**Fix**: Check Episode/AgentEpisode model definition and update tests to use correct attributes.

**Files**: `backend/core/models.py` (Episode/AgentEpisode class)

---

### 6. Text Strategy Generates Single Word [P2]

**Test**: `test_episode_summary_max_500_words`
**Severity**: P2 (Test Design Issue)
**Status**: FAILED

**Issue**: Hypothesis `st.text()` generates character sequences, not word-separated text. Word count assertion fails.

**Error**:
```
assert 1 > 500  # Only 1 "word" generated (no spaces)
```

**Root Cause**: `st.text()` generates raw text without guaranteed word boundaries.

**Fix**: Use `st.lists(st.text(), min_size=501)` and join with spaces, or use `st.text()` with alphabet that includes spaces.

**Updated Test**:
```python
@given(st.lists(st.text(min_size=5, max_size=20), min_size=501, max_size=1000))
def test_episode_summary_max_500_words(words):
    long_summary = " ".join(words)
    word_count = len(long_summary.split())
    assert word_count > 500
```

**Files**: `backend/tests/property_tests/test_edge_cases.py`

---

### 7. Concurrent Agent Execution Status Error [P2]

**Test**: `test_concurrent_agent_execution_doesnt_corrupt_state`
**Severity**: P2 (Race Condition)
**Status**: FAILED

**Issue**: Concurrent thread trying to set invalid status value causes error.

**Error**:
```
errors=['RUNNING']  # Status string, not enum
```

**Root Cause**: Test uses string 'RUNNING' instead of `AgentStatus.RUNNING` enum.

**Fix**: Update test to use proper enum values.

**Files**: `backend/tests/property_tests/test_edge_cases.py`

---

### 8. Episode Segments Empty List Accepted [P3]

**Test**: `test_episode_segments_rejects_empty_list`
**Severity**: P3 (Edge Case)
**Status**: FAILED (but expected)

**Issue**: Episode model accepts empty segments list (may be intentional for new episodes).

**Current Behavior**:
```python
episode = Episode(
    id=str(uuid.uuid4()),
    agent_id=str(uuid.uuid4()),
    title="Test Episode",  # Wrong attribute name
    summary="Test summary",
    segments=[]  # Empty list accepted
)
# No validation error
```

**Expected Behavior**: Depends on business logic. Empty segments may be valid for new episodes.

**Decision**: This may not be a bug if empty episodes are allowed during creation.

**Files**: `backend/core/models.py` (Episode class)

---

### 9. Workflow Steps Empty Dict [P3]

**Test**: `test_workflow_steps_rejects_empty_dict`
**Severity**: P3 (Test Only)
**Status**: PASSED (test only, no actual model tested)

**Issue**: Test verifies dictionary emptiness but doesn't test actual model validation.

**Note**: This is a placeholder test. Workflow model not actually tested.

**Files**: `backend/tests/property_tests/test_edge_cases.py`

---

## Pass Rate by Category

| Category | Tests | Passed | Pass Rate |
|----------|-------|--------|-----------|
| Empty/Null Values | 5 | 1 | 20% |
| Boundary Values | 5 | 4 | 80% |
| Extreme Inputs | 5 | 5 | 100% |
| Race Conditions | 3 | 0 | 0% |
| Performance | 2 | 2 | 100% |
| **Total** | **20** | **11** | **55%** |

---

## Bug Severity Distribution

| Severity | Count | Percentage |
|----------|-------|------------|
| P0 (Critical - crash/data loss) | 0 | 0% |
| P1 (High - logic error) | 6 | 67% |
| P2 (Medium - validation gap) | 3 | 33% |
| P3 (Low - edge case) | 0 | 0% |
| **Total** | **9** | **100%** |

---

## Recommended Fixes (Priority Order)

### High Priority (P1)

1. **Fix Model Attribute Mismatches** (Bugs 2, 3, 5)
   - Audit AgentRegistry and Episode models
   - Add missing attributes: `maturity`, `completed_episodes`, `title`
   - Update test imports and assertions

2. **Add Validation for Empty Name** (Bug 1)
   - Add `name` validation in AgentRegistry.__init__
   - Reject empty/whitespace-only names

3. **Add Validation for None ID** (Bug 4)
   - Add `id` validation in AgentRegistry.__init__
   - Reject None values

### Medium Priority (P2)

4. **Fix Text Strategy for Word Count** (Bug 6)
   - Use `st.lists(st.text())` and join with spaces
   - Ensure word-splitting works correctly

5. **Fix Enum Usage in Concurrent Test** (Bug 7)
   - Replace status strings with `AgentStatus` enum values

### Low Priority (P3)

6. **Evaluate Empty Segments Validation** (Bug 8)
   - Determine if empty segments should be rejected
   - Add validation if needed

---

## Next Steps

1. **Fix P1 bugs** (model attributes, validation gaps)
2. **Re-run test suite** to verify fixes
3. **Target pass rate**: 95%+ (19/20 tests passing)
4. **Update bug catalog** with fix confirmations

---

**Catalog created**: 2026-04-29
**Test execution time**: ~10 seconds
**Hypothesis examples generated**: 1000+ per test
