---
wave: 1
depends_on: []
files_modified:
  - backend/tests/core/services/test_canvas_collaboration_service.py
  - backend/tests/core/services/test_embedding_service.py
  - backend/tests/core/services/test_agent_promotion_service.py
  - backend/tests/core/services/test_canvas_docs_service.py
  - backend/tests/core/services/test_docling_processor.py
  - backend/tests/core/services/test_debug_query.py
  - backend/tests/api/services/test_industry_workflow_endpoints.py
  - backend/tests/core/services/test_budget_enforcement_service.py
  - backend/tests/core/services/test_financial_audit_service.py
  - backend/tests/core/services/test_agent_communication.py
autonomous: false
---

# Phase 219: Coverage Push - Zero-Coverage Files (Option 1)

**Goal:** Add basic tests to top 10 zero-coverage files to push coverage from 74.6% → 78-79%

**Target Files** (1,652 statements total):
1. `canvas_collaboration_service.py` - 194 statements, 0% coverage
2. `embedding_service.py` - 321 statements, 0% coverage
3. `agent_promotion_service.py` - 128 statements, 0% coverage
4. `canvas_docs_service.py` - 169 statements, 0% coverage
5. `docling_processor.py` - 167 statements, 0% coverage
6. `debug_query.py` - 163 statements, 0% coverage
7. `industry_workflow_endpoints.py` - 181 statements, 0% coverage
8. `budget_enforcement_service.py` - 151 statements, 0% coverage
9. `financial_audit_service.py` - 154 statements, 0% coverage
10. `agent_communication.py` - 136 statements, 0% coverage

**Strategy:**
- For each file, create a basic test suite covering:
  - Class initialization
  - Public method signatures
  - Error handling paths
  - Edge cases
- Target: 50-70% coverage per file (achievable with basic tests)
- Estimated total gain: +800-1,200 covered lines (~3-4 percentage points)

## Task 1: Read and Analyze Target Files

For each target file:
1. Read the file to understand its structure
2. Identify public classes and methods
3. Note dependencies and imports
4. Create test file skeleton

## Task 2: Create Basic Test Suites

Create test file for each target:

**File: `backend/tests/core/services/test_canvas_collaboration_service.py`**
- Test CanvasCollaborationService initialization
- Test session creation
- Test real-time collaboration features
- Test permission checks
- Target: 50% coverage (~97 lines)

**File: `backend/tests/core/services/test_embedding_service.py`**
- Test embedding generation
- Test vector operations
- Test embedding retrieval
- Test error handling
- Target: 50% coverage (~160 lines)

**File: `backend/tests/core/services/test_agent_promotion_service.py`**
- Test promotion criteria checks
- Test promotion workflow
- Test rejection scenarios
- Target: 50% coverage (~64 lines)

**File: `backend/tests/core/services/test_canvas_docs_service.py`**
- Test document rendering
- Test document collaboration
- Test document access control
- Target: 50% coverage (~84 lines)

**File: `backend/tests/core/services/test_docling_processor.py`**
- Test document parsing
- Test OCR processing
- Test text extraction
- Target: 50% coverage (~83 lines)

**File: `backend/tests/core/services/test_debug_query.py`**
- Test query execution
- Test debug output
- Test error scenarios
- Target: 50% coverage (~81 lines)

**File: `backend/tests/api/services/test_industry_workflow_endpoints.py`**
- Test workflow CRUD operations
- Test industry-specific templates
- Test workflow execution
- Target: 50% coverage (~90 lines)

**File: `backend/tests/core/services/test_budget_enforcement_service.py`**
- Test budget validation
- Test enforcement checks
- Test violation detection
- Target: 50% coverage (~75 lines)

**File: `backend/tests/core/services/test_financial_audit_service.py`**
- Test audit log creation
- Test transaction tracking
- Test compliance checks
- Target: 50% coverage (~77 lines)

**File: `backend/tests/core/services/test_agent_communication.py`**
- Test message routing
- Test agent chat
- Test communication protocols
- Target: 50% coverage (~68 lines)

## Task 3: Run Tests and Measure Coverage

For each test file:
1. Run the tests to verify they pass
2. Generate coverage report for the specific file
3. Verify coverage increased from 0% to 50%+
4. Commit the test file

**Command:**
```bash
PYTHONPATH=. pytest tests/core/services/test_canvas_collaboration_service.py --cov=core.services.canvas_collaboration_service --cov-report=term-missing -v
```

## Task 4: Aggregate Results and Verify

**Command:**
```bash
PYTHONPATH=. pytest tests/ --ignore=tests/integration --ignore=tests/e2e --ignore=tests/scenarios --ignore=tests/security --ignore=tests/unit --ignore=tests/property_tests --cov=backend --cov-branch --cov-report=term --tb=no -q
```

**Expected Output:**
- Coverage: 78-79% (up from 74.6%)
- Gain: +3.4 percentage points
- Files tested: 10 new test files created

## Verification

- [ ] All 10 test files created
- [ ] All tests passing
- [ ] Coverage increased to 78-79%
- [ ] Each target file now has 50%+ coverage
- [ ] No regressions in existing tests

## Success Criteria

**Complete:** Coverage increased from 74.6% to 78-79%
**Tests Created:** ~500-600 tests across 10 test files
**Time Estimate:** 2-3 hours
**Next Step:** Remaining 1-2 percentage points to reach 80% (can be achieved with 2-3 more files or extending existing tests)
