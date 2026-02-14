---
phase: 09-1-api-route-governance-resolution
plan: 37
type: execute
wave: 1
depends_on: []
files_modified:
  - api/data_ingestion_routes.py
  - api/marketing_routes.py
  - api/operational_routes.py
autonomous: true
user_setup: []
must_haves:
  truths:
    - "data_ingestion_routes.py tested with 50%+ coverage (102 lines → ~51 lines covered)"
    - "marketing_routes.py tested with 50%+ coverage (64 lines → ~32 lines covered)"
    - "operational_routes.py tested with 50%+ coverage (71 lines → ~36 lines covered)"
    - "All tests passing (no blockers)"
    - "Coverage report generated with overall metrics"
  artifacts:
    - path: "tests/api/test_data_ingestion_routes.py"
      provides: "Data ingestion route tests"
      min_lines: 150
    - path: "tests/api/test_marketing_routes.py"
      provides: "Marketing route tests"
      min_lines: 150
    - path: "tests/api/test_operational_routes.py"
      provides: "Operational route tests"
      min_lines: 150
  key_links:
    - from: "test_data_ingestion_routes.py"
      to: "api/data_ingestion_routes.py"
      via: "Data ingestion coverage"
      pattern: "50%+"
    - from: "test_marketing_routes.py"
      to: "api/marketing_routes.py"
      via: "Marketing endpoint coverage"
      pattern: "50%+"
    - from: "test_operational_routes.py"
      to: "api/operational_routes.py"
      via: "Operational endpoint coverage"
      pattern: "50%+"
status: complete
created: 2026-02-14
completed: 2026-02-14
gap_closure: false
---

# Plan 37: Data Ingestion, Marketing & Operations Routes

**Status:** ✅ Complete
**Wave:** 1
**Dependencies:** None

## Objective

Create comprehensive tests for data ingestion, marketing, and operational API routes to achieve 50%+ coverage across all three files.

## Context

Phase 9.1 targets 27-29% overall coverage (+5-7% from 22.15% baseline) by testing zero-coverage API routes.

**Files in this plan:**

1. **api/data_ingestion_routes.py** (102 lines, 0% coverage)
   - Document upload and processing endpoints
   - Data validation and transformation
   - Batch ingestion operations

2. **api/marketing_routes.py** (64 lines, 0% coverage)
   - Marketing campaign management
   - Campaign analytics and reporting
   - Audience targeting and segmentation

3. **api/operational_routes.py** (71 lines, 0% coverage)
   - System operations and maintenance endpoints
   - Health checks and diagnostics
   - Operational metrics and monitoring

**Total Production Lines:** 237
**Expected Coverage at 50%:** ~119 lines
**Target Coverage Contribution:** +1.0-1.5% overall

## Success Criteria

**Must Have (truths that become verifiable):**
1. data_ingestion_routes.py tested with 50%+ coverage (102 lines → ~51 lines covered)
2. marketing_routes.py tested with 50%+ coverage (64 lines → ~32 lines covered)
3. operational_routes.py tested with 50%+ coverage (71 lines → ~36 lines covered)
4. All tests passing (no blockers)
5. Coverage report generated with overall metrics

**Should Have:**
- Data validation tests (file type, size, format)
- Campaign management tests (create, update, delete)
- Health check tests (system status, dependency checks)

**Could Have:**
- Batch processing tests (large file uploads)
- Campaign performance tests (open rates, click-through)
- Operational alerting tests (threshold violations)

**Won't Have:**
- Integration tests with real storage systems (S3, etc.)
- End-to-end data pipeline tests
- Real-time campaign execution tests

## Tasks

### Task 1: Create test_data_ingestion_routes.py

**File:** CREATE: `tests/api/test_data_ingestion_routes.py` (150+ lines)

**Action:**
Create comprehensive tests for data ingestion routes:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock
from api.data_ingestion_routes import router
from core.data_ingestion_service import DataIngestionService

# Tests to implement:
# 1. Test POST /ingestion/upload - 200 status, file uploaded
# 2. Test POST /ingestion/upload - 400 for invalid file type
# 3. Test POST /ingestion/upload - 400 for file size exceeded
# 4. Test POST /ingestion/batch - 200 status, batch processed
# 5. Test POST /ingestion/batch - 400 for invalid batch format
# 6. Test GET /ingestion/status/{job_id} - 200 status, job status
# 7. Test GET /ingestion/status/{job_id} - 404 for job not found
# 8. Test GET /ingestion/history - 200 status, ingestion history
# 9. Test DELETE /ingestion/job/{job_id} - 200 status, job cancelled
# 10. Test DELETE /ingestion/job/{job_id} - 404 for job not found
```

**Coverage Targets:**
- File upload (POST /ingestion/upload)
- Batch processing (POST /ingestion/batch)
- Job status (GET /ingestion/status/{job_id})
- Ingestion history (GET /ingestion/history)
- Job cancellation (DELETE /ingestion/job/{job_id})
- Error handling (400, 404, 500)

**Verify:**
```bash
source venv/bin/activate && python -m pytest tests/api/test_data_ingestion_routes.py -v --cov=api/data_ingestion_routes --cov-report=term-missing
# Expected: 50%+ coverage
```

**Done:**
- 150+ lines of tests created
- 50%+ coverage achieved
- All tests passing

### Task 2: Create test_marketing_routes.py

**File:** CREATE: `tests/api/test_marketing_routes.py` (150+ lines)

**Action:**
Create comprehensive tests for marketing routes:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock
from api.marketing_routes import router
from core.marketing_service import MarketingService

# Tests to implement:
# 1. Test POST /marketing/campaign - 201 status, campaign created
# 2. Test POST /marketing/campaign - 400 for invalid campaign data
# 3. Test PUT /marketing/campaign/{campaign_id} - 200 status, campaign updated
# 4. Test PUT /marketing/campaign/{campaign_id} - 404 for campaign not found
# 5. Test GET /marketing/campaign/{campaign_id} - 200 status, campaign details
# 6. Test GET /marketing/campaign/{campaign_id} - 404 for campaign not found
# 7. Test GET /marketing/campaigns - 200 status, list of campaigns
# 8. Test DELETE /marketing/campaign/{campaign_id} - 200 status, campaign deleted
# 9. Test GET /marketing/analytics/{campaign_id} - 200 status, analytics data
# 10. Test GET /marketing/analytics/{campaign_id} - 404 for campaign not found
```

**Coverage Targets:**
- Campaign creation (POST /marketing/campaign)
- Campaign updates (PUT /marketing/campaign/{campaign_id})
- Campaign retrieval (GET /marketing/campaign/{campaign_id})
- Campaign listing (GET /marketing/campaigns)
- Campaign deletion (DELETE /marketing/campaign/{campaign_id})
- Campaign analytics (GET /marketing/analytics/{campaign_id})
- Error handling (400, 404, 500)

**Verify:**
```bash
source venv/bin/activate && python -m pytest tests/api/test_marketing_routes.py -v --cov=api/marketing_routes --cov-report=term-missing
# Expected: 50%+ coverage
```

**Done:**
- 150+ lines of tests created
- 50%+ coverage achieved
- All tests passing

### Task 3: Create test_operational_routes.py

**File:** CREATE: `tests/api/test_operational_routes.py` (150+ lines)

**Action:**
Create comprehensive tests for operational routes:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock
from api.operational_routes import router
from core.operational_service import OperationalService

# Tests to implement:
# 1. Test GET /ops/health - 200 status, system healthy
# 2. Test GET /ops/health - 503 status, system unhealthy
# 3. Test GET /ops/metrics - 200 status, metrics returned
# 4. Test GET /ops/diagnostics - 200 status, diagnostics data
# 5. Test POST /ops/maintenance/start - 200 status, maintenance mode started
# 6. Test POST /ops/maintenance/stop - 200 status, maintenance mode stopped
# 7. Test GET /ops/status - 200 status, operational status
# 8. Test GET /ops/dependencies - 200 status, dependency status
# 9. Test GET /ops/alerts - 200 status, active alerts
# 10. Test DELETE /ops/alerts/{alert_id} - 200 status, alert dismissed
```

**Coverage Targets:**
- Health checks (GET /ops/health)
- System metrics (GET /ops/metrics)
- Diagnostics (GET /ops/diagnostics)
- Maintenance mode (POST /ops/maintenance/start, POST /ops/maintenance/stop)
- Operational status (GET /ops/status)
- Dependency checks (GET /ops/dependencies)
- Alerting (GET /ops/alerts, DELETE /ops/alerts/{alert_id})
- Error handling (400, 404, 500)

**Verify:**
```bash
source venv/bin/activate && python -m pytest tests/api/test_operational_routes.py -v --cov=api/operational_routes --cov-report=term-missing
# Expected: 50%+ coverage
```

**Done:**
- 150+ lines of tests created
- 50%+ coverage achieved
- All tests passing

### Task 4: Run test suite and document coverage

**Action:**
Run all three test files and document coverage statistics:

```bash
source venv/bin/activate && python -m pytest \
  tests/api/test_data_ingestion_routes.py \
  tests/api/test_marketing_routes.py \
  tests/api/test_operational_routes.py \
  -v \
  --cov=api/data_ingestion_routes \
  --cov=api/marketing_routes \
  --cov=api/operational_routes \
  --cov-report=term-missing \
  --cov-report=html:tests/coverage_reports/html
```

**Verify:**
```bash
# Check coverage output:
# data_ingestion_routes.py: 50%+
# marketing_routes.py: 50%+
# operational_routes.py: 50%+
```

**Done:**
- All tests passing
- Coverage targets met (50%+ each file)
- Coverage report generated with overall metrics

## Key Links

| From | To | Via | Artifact |
|------|-----|-----|----------|
| test_data_ingestion_routes.py | data_ingestion_routes.py | Data ingestion coverage | 50%+ |
| test_marketing_routes.py | marketing_routes.py | Marketing endpoint coverage | 50%+ |
| test_operational_routes.py | operational_routes.py | Operational endpoint coverage | 50%+ |

## Progress Tracking

**Starting Coverage:** 22.15%
**Target Coverage (Plan 37):** 24.15-25.65% (+2.0-3.5% cumulative)
**Actual Coverage:** Documented in summary after execution

## Notes

- Wave 1 plan (no dependencies)
- Focus on data ingestion, marketing campaigns, and operational monitoring
- File upload validation tests (type, size) critical for data ingestion
- Campaign lifecycle tests (create, update, delete, analytics)
- Health check and dependency monitoring tests
- Error handling tests (400, 404, 500, 503) essential

**Estimated Duration:** 90 minutes
