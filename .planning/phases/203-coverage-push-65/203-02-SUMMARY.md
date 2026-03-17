---
phase: 203-coverage-push-65
plan: 02
subsystem: debug-system-models
tags: [debug-system, models, database, test-coverage, architectural-debt]

# Dependency graph
requires:
  - phase: 202-coverage-push-60
    plan: 10
    provides: Debug alerting test file (blocked by missing models)
provides:
  - DebugEvent database model (11 fields)
  - DebugInsight database model (13 fields)
  - DebugEventType enum (5 event types)
  - DebugInsightType enum (5 insight types)
  - DebugInsightSeverity enum (3 severity levels)
  - Fixed debug_alerting.py imports
affects: [debug-system, test-coverage, debug-alerting, debug-collector]

# Tech tracking
tech-stack:
  added: [DebugEvent, DebugInsight, debug system enums]
  patterns:
    - "String primary keys with UUID-based defaults"
    - "JSON metadata fields for flexible event/insight data"
    - "Timezone-aware datetime fields using datetime.now(timezone.utc)"
    - "Index fields for query performance (event_type, component_type, severity, resolved, timestamp)"

key-files:
  created: []
  modified:
    - backend/core/models.py (added 3 enums + 2 models, 79 lines)
    - backend/core/debug_alerting.py (fixed imports)

key-decisions:
  - "Add DebugEventType, DebugInsightType, DebugInsightSeverity enums to match debug_alerting.py usage"
  - "DebugEvent uses 11 fields based on debug_collector.py usage patterns"
  - "DebugInsight uses 13 fields based on debug_alerting.py constructor patterns"
  - "Removed unused DebugAlert import from debug_alerting.py (Rule 1 - bug fix)"
  - "Added missing DebugInsightType import to debug_alerting.py (Rule 1 - bug fix)"
  - "No foreign key relationship needed - DebugInsight stands alone (no event_id field required)"

patterns-established:
  - "Pattern: UUID-based string primary keys with prefixed defaults"
  - "Pattern: JSON columns for flexible metadata storage (data, event_metadata, evidence, suggestions, affected_components)"
  - "Pattern: Timezone-aware datetime defaults using datetime.now(timezone.utc)"
  - "Pattern: Index fields frequently used in WHERE/ORDER BY clauses"

# Metrics
duration: ~3 minutes (229 seconds)
completed: 2026-03-17
---

# Phase 203: Coverage Push to 65% - Plan 02 Summary

**DebugEvent and DebugInsight models added to unblock debug_alerting test coverage**

## Performance

- **Duration:** ~3 minutes (229 seconds)
- **Started:** 2026-03-17T18:26:04Z
- **Completed:** 2026-03-17T18:29:13Z
- **Tasks:** 3
- **Files created:** 0
- **Files modified:** 2

## Accomplishments

- **3 enums added** (DebugEventType, DebugInsightType, DebugInsightSeverity)
- **2 database models added** (DebugEvent with 11 fields, DebugInsight with 13 fields)
- **Fixed import errors** in debug_alerting.py (removed unused DebugAlert, added missing DebugInsightType)
- **Models import successfully** without AttributeError
- **debug_alerting tests unblocked** - can now import and use models
- **79 lines added** to core/models.py
- **Architectural debt resolved** from Phase 202 Plan 10

## Task Commits

1 task was committed:

1. **Task 2: Add models** - `b6eed52c2` (feat)

**Plan metadata:** 3 tasks, 1 commit, 229 seconds execution time

## Models Created

### DebugEvent Model (11 fields)

**Table:** `debug_events`

**Fields:**
- `id` (String, primary key) - UUID-based identifier
- `event_type` (String(50), indexed) - log, state_snapshot, metric, error, system
- `component_type` (String(50), indexed) - agent, browser, workflow, system
- `component_id` (String, indexed, optional) - Component identifier
- `correlation_id` (String, indexed) - Links related events
- `parent_event_id` (String, indexed, optional) - For event chains
- `level` (String(20), optional) - DEBUG, INFO, WARNING, ERROR, CRITICAL
- `message` (Text, optional) - Log message
- `data` (JSON, optional) - Full event data
- `event_metadata` (JSON, optional) - Tags, labels, additional context
- `timestamp` (DateTime, indexed, timezone-aware) - Event timestamp

**Indexes:** event_type, component_type, component_id, correlation_id, parent_event_id, timestamp

**Usage Pattern:**
```python
event = DebugEvent(
    id=str(uuid.uuid4()),
    event_type="log",
    component_type="agent",
    component_id="agent-123",
    correlation_id="corr-456",
    parent_event_id="parent-789",
    level="INFO",
    message="Agent started",
    data={"timestamp": "2026-03-17T18:00:00Z"},
    event_metadata={"source": "api"},
    timestamp=datetime.utcnow()
)
```

### DebugInsight Model (13 fields)

**Table:** `debug_insights`

**Fields:**
- `id` (String, primary key) - UUID-based identifier
- `insight_type` (String(50), indexed) - error, performance, anomaly, consistency, flow
- `severity` (String(20), indexed) - critical, warning, info
- `title` (String(200), optional) - Insight title
- `description` (Text, optional) - Full description
- `summary` (Text, optional) - One-line summary
- `evidence` (JSON, optional) - Evidence data
- `confidence_score` (Float, default: 0.5) - 0.0 to 1.0
- `suggestions` (JSON, optional) - List of suggestion strings
- `scope` (String(50), optional) - component, system, distributed
- `affected_components` (JSON, optional) - List of affected components
- `resolved` (Boolean, default: False, indexed) - Whether insight is resolved
- `generated_at` (DateTime, indexed, timezone-aware) - When insight was generated

**Indexes:** insight_type, severity, resolved, generated_at

**Usage Pattern:**
```python
insight = DebugInsight(
    insight_type="error",
    severity="critical",
    title="High error rate alert: agent/agent_123",
    description="Error rate 60.0% exceeds threshold 50%",
    summary="Error rate 60.0% requires attention",
    evidence={"component_type": "agent", "component_id": "agent_123", "error_rate": 0.6},
    confidence_score=0.95,
    suggestions=["Investigate immediately", "Check error logs"],
    scope="component",
    affected_components=[{"type": "agent", "id": "agent_123"}],
    resolved=False,
    generated_at=datetime.utcnow()
)
```

### Enums Added

**DebugEventType (5 values):**
- LOG - Log events
- STATE_SNAPSHOT - State capture events
- METRIC - Metric events
- ERROR - Error events
- SYSTEM - System events

**DebugInsightType (5 values):**
- ERROR - Error insights
- PERFORMANCE - Performance insights
- ANOMALY - Anomaly insights
- CONSISTENCY - Consistency insights
- FLOW - Flow insights

**DebugInsightSeverity (3 values):**
- CRITICAL - Critical severity
- WARNING - Warning severity
- INFO - Info severity

## Files Modified

### backend/core/models.py (+79 lines)

**Added:**
- Line 112-120: DebugEventType enum (5 values)
- Line 121-127: DebugInsightType enum (5 values)
- Line 128-133: DebugInsightSeverity enum (3 values)
- Line 4730-4763: DebugEvent model (11 fields, 34 lines)
- Line 4765-4795: DebugInsight model (13 fields, 31 lines)

**Location:** After SES models (line 4727), before UNIVERSAL COMMUNICATION BRIDGE MODELS (line 4730)

### backend/core/debug_alerting.py (fixed imports)

**Before:**
```python
from core.models import (
    DebugEvent,
    DebugInsight,
    DebugAlert,  # ❌ Does not exist
    DebugEventType,
    DebugInsightSeverity,
)
```

**After:**
```python
from core.models import (
    DebugEvent,
    DebugInsight,
    DebugEventType,
    DebugInsightType,  # ✅ Added
    DebugInsightSeverity,
)
```

**Changes:**
- Removed: `DebugAlert` (unused, doesn't exist)
- Added: `DebugInsightType` (used in lines 155, 270, 345, 417)

## Decisions Made

### Decision 1: No Foreign Key Relationship

**Question:** Should DebugInsight have a foreign key to DebugEvent?

**Answer:** No. Analyzing debug_alerting.py and debug_insight_engine.py, DebugInsight objects are created independently without linking to a specific event. The alerting system generates insights based on aggregate queries (error rates, performance metrics, anomalies), not individual events.

**Evidence:**
- debug_alerting.py line 154-178: Creates DebugInsight from aggregated error rate statistics
- debug_alerting.py line 268-292: Creates DebugInsight from component-level error analysis
- debug_alerting.py line 343-367: Creates DebugInsight from performance percentile analysis

### Decision 2: Field Mapping from Usage Analysis

**DebugEvent fields mapped from debug_collector.py:**
- `id` (str uuid) - line 190
- `event_type` - line 191
- `component_type` - line 192
- `component_id` - line 193
- `correlation_id` - line 194
- `parent_event_id` - line 195
- `level` - line 196
- `message` - line 197
- `data` - line 198
- `event_metadata` - line 199
- `timestamp` - line 200

**DebugInsight fields mapped from debug_alerting.py:**
- `insight_type` - line 155, 270, 345, 417
- `severity` - line 156, 271, 346, 418
- `title` - line 157, 272, 347, 419
- `description` - line 158, 273, 348, 420-421
- `summary` - line 159, 274, 349, 422
- `evidence` - line 160-167, 275-280, 350-355, 423-426
- `confidence_score` - line 168, 282, 357, 428
- `suggestions` - line 169-173, 283-286, 358-361, 429-432
- `scope` - line 175, 288, 363, 435
- `affected_components` - line 176, 289, 364, 436
- `generated_at` - line 177, 290, 365, 437
- `resolved` - line 215 (query filter)

### Decision 3: Import Fix (Rule 1 - Bug Fix)

**Issue:** debug_alerting.py imports `DebugAlert` which doesn't exist, and is missing `DebugInsightType` which is used.

**Fix:** Removed unused `DebugAlert` import, added missing `DebugInsightType` import.

**Justification:** Rule 1 (auto-fix bugs) - broken imports prevent module from loading.

## Deviations from Plan

### Rule 1 - Bug Fix: Import Errors in debug_alerting.py

**Found during:** Task 3 (verification)

**Issue:** debug_alerting.py had import errors:
- Imported `DebugAlert` which doesn't exist in models.py
- Missing `DebugInsightType` which is used in lines 155, 270, 345, 417

**Fix:**
- Removed `DebugAlert` from imports (unused)
- Added `DebugInsightType` to imports

**Files modified:** backend/core/debug_alerting.py

**Impact:** Fixed ImportError that prevented debug_alerting module from loading with the new models.

## Verification Results

All verification steps passed:

1. ✅ **DebugEvent model exists** - core/models.py line 4737-4763
2. ✅ **DebugInsight model exists** - core/models.py line 4765-4795
3. ✅ **Enums added** - DebugEventType (line 112), DebugInsightType (line 121), DebugInsightSeverity (line 128)
4. ✅ **DebugEvent has 11 fields** - id, event_type, component_type, component_id, correlation_id, parent_event_id, level, message, data, event_metadata, timestamp
5. ✅ **DebugInsight has 13 fields** - id, insight_type, severity, title, description, summary, evidence, confidence_score, suggestions, scope, affected_components, resolved, generated_at
6. ✅ **Models import successfully** - `from core.models import DebugEvent, DebugInsight`
7. ✅ **debug_alerting imports work** - `from core.debug_alerting import DebugAlertingEngine`
8. ✅ **pytest collection passes** - test_debug_alerting_coverage.py collects 21 tests without AttributeError
9. ✅ **All critical fields present** - Verified with SQLAlchemy inspection

## Test Results

### Model Import Verification

```bash
$ python3 -c "from core.models import DebugEvent, DebugInsight; print('SUCCESS')"
SUCCESS

$ python3 -c "from core.debug_alerting import DebugAlertingEngine; print('SUCCESS')"
SUCCESS
```

### Field Verification

```bash
DebugEvent columns: ['id', 'event_type', 'component_type', 'component_id',
                     'correlation_id', 'parent_event_id', 'level', 'message',
                     'data', 'event_metadata', 'timestamp']

DebugInsight columns: ['id', 'insight_type', 'severity', 'title', 'description',
                       'summary', 'evidence', 'confidence_score', 'suggestions',
                       'scope', 'affected_components', 'resolved', 'generated_at']
```

### Pytest Collection

```bash
$ pytest tests/core/test_debug_alerting_coverage.py --collect-only -q
tests/core/test_debug_alerting_coverage.py: 21

======================== 21 tests collected ========================
```

No AttributeError or ImportError - models are available for testing.

## Coverage Impact

### Before (Phase 202 Plan 10)

- **Debug alerting tests:** Skipped due to missing models
- **Estimated coverage:** 0% (tests couldn't run)
- **Error:** `AttributeError: cannot import name 'DebugEvent' from 'core.models'`

### After (Phase 203 Plan 02)

- **Debug alerting tests:** Can run (21 tests collected)
- **Estimated coverage:** TBD (tests can now execute in Phase 203 Plan 03+)
- **Error:** None - models import successfully

**Next Steps:**
- Phase 203 Plan 03: Run debug_alerting tests and measure actual coverage
- Phase 203 Plan 04-11: Continue coverage push to 65%

## Issues Encountered

**Issue 1: Import Error in debug_alerting.py**

**Symptom:** ImportError when importing DebugAlertingEngine after adding models

**Root Cause:** debug_alerting.py imports `DebugAlert` which doesn't exist, and is missing `DebugInsightType` which is used

**Fix:** Removed unused `DebugAlert` import, added missing `DebugInsightType` import

**Impact:** Fixed by Rule 1 (auto-fix bugs) - import errors prevented module loading

## Self-Check: PASSED

All files modified:
- ✅ backend/core/models.py (79 lines added: 3 enums + 2 models)
- ✅ backend/core/debug_alerting.py (imports fixed)

All commits exist:
- ✅ b6eed52c2 - feat(203-02): add DebugEvent and DebugInsight models

All verification passed:
- ✅ DebugEvent model with 11 fields exists
- ✅ DebugInsight model with 13 fields exists
- ✅ All enums added (DebugEventType, DebugInsightType, DebugInsightSeverity)
- ✅ Models import without AttributeError
- ✅ debug_alerting.py imports work correctly
- ✅ pytest collection passes for test_debug_alerting_coverage.py

## Next Phase Readiness

✅ **Debug system models complete** - DebugEvent and DebugInsight ready for use

**Ready for:**
- Phase 203 Plan 03: Run debug_alerting tests and measure coverage
- Phase 203 Plan 04-11: Continue coverage push to 65% target

**Unblocked Tests:**
- backend/tests/core/test_debug_alerting_coverage.py (21 tests, 353 lines)
- Can now execute without AttributeError
- Coverage measurement can proceed accurately

---

*Phase: 203-coverage-push-65*
*Plan: 02*
*Completed: 2026-03-17*
