---
phase: 08-80-percent-coverage-push
plan: 41
type: execute
wave: 2
depends_on: []
files_modified:
  - api/workflow_template_routes.py
  - api/workflow_collaboration.py
autonomous: true
user_setup: []
must_haves:
  truths:
    - "workflow_template_routes.py tested with 50%+ coverage (298 lines → ~149 lines covered)"
    - "workflow_collaboration.py tested with 50%+ coverage (253 lines → ~127 lines covered)"
    - "All tests passing (no blockers)"
    - "Test execution statistics documented"
  artifacts:
    - path: "tests/api/test_workflow_template_routes.py"
      provides: "Workflow template route tests"
      min_lines: 200
    - path: "tests/api/test_workflow_collaboration.py"
      provides: "Workflow collaboration tests"
      min_lines: 200
  key_links:
    - from: "test_workflow_template_routes.py"
      to: "api/workflow_template_routes.py"
      via: "Workflow template endpoint coverage"
      pattern: "50%+"
    - from: "test_workflow_collaboration.py"
      to: "api/workflow_collaboration.py"
      via: "Workflow collaboration endpoint coverage"
      pattern: "50%+"
status: pending
created: 2026-02-14
gap_closure: false
---

# Plan 41: Workflow Templates & Collaboration

**Status:** Pending
**Wave:** 2
**Dependencies:** None

## Objective

Create comprehensive tests for workflow template and collaboration API routes to achieve 50%+ coverage across both files.

## Context

Phase 9.2 targets 32-35% overall coverage (+28.12% from 3.9% current) by testing zero-coverage API routes.

**Files in this plan:**

1. **api/workflow_template_routes.py** (298 lines, 0% coverage)
   - Workflow template CRUD operations
   - Template versioning and management
   - Template instantiation and execution
   - Template validation and governance

2. **api/workflow_collaboration.py** (253 lines, 0% coverage)
   - Shared workflow collaboration
   - Real-time collaborative editing
   - Permission management and access control
   - Activity tracking and notifications

**Total Production Lines:** 551
**Expected Coverage at 50%:** ~276 lines
**Target Coverage Contribution:** +0.5-0.7% overall

## Success Criteria

**Must Have (truths that become verifiable):**
1. workflow_template_routes.py tested with 50%+ coverage (298 lines → ~149 lines covered)
2. workflow_collaboration.py tested with 50%+ coverage (253 lines → ~127 lines covered)
3. All tests passing (no blockers)
4. Test execution statistics documented

**Should Have:**
- Error handling tests (400, 404, 500 status codes)
- Governance integration tests (permission checks, access control)
- Collaboration workflow tests (share, unshare, transfer ownership)

**Could Have:**
- Performance tests (concurrent template editing)
- Real-time collaboration streaming tests
- Version control and conflict resolution tests

**Won't Have:**
- Integration tests with real workflow execution engine
- End-to-end workflow lifecycle tests (create → edit → execute → monitor)

## Tasks

### Task 1: Create test_workflow_template_routes.py

**File:** CREATE: `tests/api/test_workflow_template_routes.py` (200+ lines)

**Action:**
Create comprehensive tests for workflow template routes:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock
from api.workflow_template_routes import router
from core.workflow_template_service import WorkflowTemplateService

# Tests to implement:
# 1. Test POST /templates - 201 status, template created
# 2. Test POST /templates - 400 for invalid template data
# 3. Test GET /templates/{template_id} - 200 status, template details
# 4. Test GET /templates/{template_id} - 404 for template not found
# 5. Test PUT /templates/{template_id} - 200 status, template updated
# 6. Test PUT /templates/{template_id} - 404 for template not found
# 7. Test DELETE /templates/{template_id} - 200 status, template deleted
# 8. Test DELETE /templates/{template_id} - 404 for template not found
# 9. Test POST /templates/{template_id}/instantiate - 200 status, workflow instantiated
# 10. Test POST /templates/{template_id}/instantiate - 400 for invalid template
# 11. Test POST /templates/{template_id}/instantiate - 404 for template not found
# 12. Test GET /templates - 200 status, list of templates
# 13. Test GET /templates/category/{category} - 200 status, templates by category
# 14. Test GET /templates/version/{version_id} - 200 status, version details
# 15. Test PUT /templates/{template_id}/version/{version_id} - 200 status, version updated
```

**Coverage Targets:**
- Template CRUD (POST /templates, GET /templates/{template_id}, PUT /templates/{template_id}, DELETE /templates/{template_id})
- Template instantiation (POST /templates/{template_id}/instantiate)
- Template versioning (GET /templates/version/{version_id}, PUT /templates/{template_id}/version/{version_id})
- Template listing and filtering (GET /templates, GET /templates/category/{category})
- Error handling (400, 404, 500)

**Verify:**
```bash
source venv/bin/activate && python -m pytest tests/api/test_workflow_template_routes.py -v --cov=api/workflow_template_routes --cov-report=term-missing
# Expected: 50%+ coverage
```

**Done:**
- 200+ lines of tests created
- 50%+ coverage achieved
- All tests passing

### Task 2: Create test_workflow_collaboration.py

**File:** CREATE: `tests/api/test_workflow_collaboration.py` (200+ lines)

**Action:**
Create comprehensive tests for workflow collaboration routes:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock
from api.workflow_collaboration import router
from core.workflow_collaboration_service import WorkflowCollaborationService

# Tests to implement:
# 1. Test POST /collaboration/share - 200 status, workflow shared
# 2. Test POST /collaboration/share - 400 for invalid workflow ID
# 3. Test POST /collaboration/share - 404 for workflow not found
# 4. Test POST /collaboration/unshare - 200 status, workflow unshared
# 5. Test POST /collaboration/unshare - 400 for invalid workflow ID
# 6. Test POST /collaboration/unshare - 404 for workflow not found
# 7. Test POST /collaboration/join - 200 status, joined workflow
# 8. Test POST /collaboration/join - 400 for invalid request
# 9. Test POST /collaboration/join - 404 for workflow not found
# 10. Test DELETE /collaboration/workflow/{workflow_id} - 200 status, removed from workflow
# 11. Test DELETE /collaboration/workflow/{workflow_id} - 404 for workflow not found
# 12. Test GET /collaboration/workflows - 200 status, list of shared workflows
# 13. Test GET /collaboration/workflow/{workflow_id}/activity - 200 status, activity log
# 14. Test GET /collaboration/workflow/{workflow_id}/permissions - 200 status, permissions
# 15. Test PUT /collaboration/workflow/{workflow_id}/permissions - 200 status, permissions updated
```

**Coverage Targets:**
- Sharing operations (POST /collaboration/share, POST /collaboration/unshare)
- Join workflow (POST /collaboration/join)
- Workflow removal (DELETE /collaboration/workflow/{workflow_id})
- Shared workflow listing (GET /collaboration/workflows)
- Activity tracking (GET /collaboration/workflow/{workflow_id}/activity)
- Permission management (GET /collaboration/workflow/{workflow_id}/permissions, PUT /collaboration/workflow/{workflow_id}/permissions)
- Error handling (400, 404, 500)

**Verify:**
```bash
source venv/bin/activate && python -m pytest tests/api/test_workflow_collaboration.py -v --cov=api/workflow_collaboration --cov-report=term-missing
# Expected: 50%+ coverage
```

**Done:**
- 200+ lines of tests created
- 50%+ coverage achieved
- All tests passing

### Task 3: Run test suite and document coverage

**Action:**
Run both test files and document coverage statistics:

```bash
source venv/bin/activate && python -m pytest \
  tests/api/test_workflow_template_routes.py \
  tests/api/test_workflow_collaboration.py \
  -v \
  --cov=api/workflow_template_routes \
  --cov=api/workflow_collaboration \
  --cov-report=term-missing \
  --cov-report=html:tests/coverage_reports/html
```

**Verify:**
```bash
# Check coverage output:
# workflow_template_routes.py: 50%+
# workflow_collaboration.py: 50%+
```

**Done:**
- All tests passing
- Coverage targets met (50%+ each file)
- Test execution statistics documented

## Key Links

| From | To | Via | Artifact |
|------|-----|-----|----------|
| test_workflow_template_routes.py | workflow_template_routes.py | Workflow template endpoint coverage | 50%+ |
| test_workflow_collaboration.py | workflow_collaboration.py | Workflow collaboration endpoint coverage | 50%+ |

## Progress Tracking

**Starting Coverage:** 3.9%
**Target Coverage (Plan 41):** 4.4-4.6% (+0.5-0.7%)
**Actual Coverage:** Documented in summary after execution

## Notes

- Wave 2 plan (no dependencies)
- Focus on workflow template management and collaboration features
- Template CRUD operations (create, read, update, delete)
- Template instantiation and versioning
- Real-time collaborative editing with permission management
- Error handling tests (400, 404, 500) essential

**Estimated Duration:** 90 minutes
