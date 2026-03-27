# Bug Discovery Infrastructure Verification Checklist

**Phase:** 237 - Bug Discovery Infrastructure Foundation
**Purpose:** Verify all INFRA-01 through INFRA-05 requirements are met
**Last Updated:** 2026-03-24

## Overview

This checklist verifies that bug discovery infrastructure is production-ready and meets all requirements defined in REQUIREMENTS.md and researched in 237-RESEARCH.md.

## INFRA-01: Integration into Existing pytest Infrastructure

**Requirement:** Bug discovery integrates into existing pytest infrastructure (tests/ directory, not separate /bug-discovery/)

**Verification Steps:**
- [ ] Fuzzing tests exist in `backend/tests/fuzzing/` (NOT separate /bug-discovery/)
- [ ] Browser discovery tests exist in `backend/tests/browser_discovery/` (NOT separate /bug-discovery/)
- [ ] `pytest tests/` discovers all bug discovery tests
- [ ] `pytest.ini` testpaths includes new directories
- [ ] No separate /bug-discovery/ directory exists in codebase

**Commands:**
```bash
# Verify directory structure
ls -la backend/tests/fuzzing/
ls -la backend/tests/browser_discovery/

# Verify pytest discovery
pytest backend/tests/ --collect-only | grep -E "fuzzing|browser_discovery"

# Verify no separate /bug-discovery/ directory
ls -la backend/tests/ | grep bug-discovery || echo "PASS: No separate directory"
```

**Expected Output:**
- `backend/tests/fuzzing/` directory exists
- `backend/tests/browser_discovery/` directory exists
- Pytest discovers tests from both directories
- No `/bug-discovery/` directory at project root

**Evidence:**
- Created: `backend/tests/fuzzing/conftest.py`
- Created: `backend/tests/browser_discovery/conftest.py`

---

## INFRA-02: Separate CI Pipelines

**Requirement:** Separate CI pipelines (fast PR tests <10min vs weekly bug discovery 2 hours)

**Verification Steps:**
- [ ] `.github/workflows/pr-tests.yml` exists
- [ ] PR workflow uses `-m "fast or property"` marker selection
- [ ] PR workflow timeout is 10 minutes
- [ ] `.github/workflows/bug-discovery-weekly.yml` exists
- [ ] Bug discovery workflow uses `-m "fuzzing or chaos or browser"` marker selection
- [ ] Bug discovery workflow timeout is 2 hours
- [ ] Bug discovery workflow triggers weekly (Sunday 3 AM UTC)

**Commands:**
```bash
# Verify workflows exist
ls -la .github/workflows/pr-tests.yml
ls -la .github/workflows/bug-discovery-weekly.yml

# Verify marker selection
grep 'pytest.*-m "fast or property"' .github/workflows/pr-tests.yml
grep 'pytest.*-m "fuzzing or chaos or browser"' .github/workflows/bug-discovery-weekly.yml
```

**Expected Output:**
- PR workflow: `-m "fast or property"` marker selection
- Bug discovery workflow: `-m "fuzzing or chaos or browser"` marker selection
- Timeouts: PR = 10min, Bug discovery = 2 hours

**Evidence:**
- Created: `.github/workflows/pr-tests.yml`
- Created: `.github/workflows/bug-discovery-weekly.yml`

---

## INFRA-03: Documentation Templates

**Requirement:** Documentation templates for all bug discovery categories (fuzzing, chaos, property tests, browser)

**Verification Steps:**
- [ ] `FUZZING_TEMPLATE.md` exists with all required sections
- [ ] `CHAOS_TEMPLATE.md` exists with all required sections
- [ ] `PROPERTY_TEMPLATE.md` exists with all required sections
- [ ] `BROWSER_TEMPLATE.md` exists with all required sections
- [ ] `README.md` explains template usage
- [ ] All templates include TQ-01 through TQ-05 compliance section

**Commands:**
```bash
# Verify templates exist
ls -la backend/tests/bug_discovery/TEMPLATES/*.md

# Verify required sections
for template in FUZZING CHAOS PROPERTY BROWSER; do
  echo "Checking $template template..."
  grep -q "Purpose:" backend/tests/bug_discovery/TEMPLATES/${template}_TEMPLATE.md
  grep -q "Dependencies:" backend/tests/bug_discovery/TEMPLATES/${template}_TEMPLATE.md
  grep -q "Setup:" backend/tests/bug_discovery/TEMPLATES/${template}_TEMPLATE.md
  grep -q "Test Procedure:" backend/tests/bug_discovery/TEMPLATES/${template}_TEMPLATE.md
  grep -q "Expected Behavior:" backend/tests/bug_discovery/TEMPLATES/${template}_TEMPLATE.md
  grep -q "Bug Filing:" backend/tests/bug_discovery/TEMPLATES/${template}_TEMPLATE.md
  grep -q "TQ Compliance:" backend/tests/bug_discovery/TEMPLATES/${template}_TEMPLATE.md
done
```

**Expected Output:**
- 4 templates + README exist
- All templates contain 7 required sections
- All templates reference TQ-01 through TQ-05

**Evidence:**
- Created: `backend/tests/bug_discovery/TEMPLATES/FUZZING_TEMPLATE.md`
- Created: `backend/tests/bug_discovery/TEMPLATES/CHAOS_TEMPLATE.md`
- Created: `backend/tests/bug_discovery/TEMPLATES/PROPERTY_TEMPLATE.md`
- Created: `backend/tests/bug_discovery/TEMPLATES/BROWSER_TEMPLATE.md`
- Created: `backend/tests/bug_discovery/TEMPLATES/README.md`

---

## INFRA-04: Enforced TEST_QUALITY_STANDARDS.md

**Requirement:** Enforced TEST_QUALITY_STANDARDS.md (TQ-01 through TQ-05) for all bug discovery tests

**Verification Steps:**
- [ ] All templates include TQ-01 through TQ-05 compliance section
- [ ] `TEST_QUALITY_GATE.md` exists with quality enforcement
- [ ] Conftest.py files include quality hooks (timeout, rerunfailures)
- [ ] pytest.ini enforces test quality (strict markers, maxfail)

**Commands:**
```bash
# Verify TQ compliance in templates
grep -r "TQ-01" backend/tests/bug_discovery/TEMPLATES/
grep -r "TQ-02" backend/tests/bug_discovery/TEMPLATES/
grep -r "TQ-03" backend/tests/bug_discovery/TEMPLATES/
grep -r "TQ-04" backend/tests/bug_discovery/TEMPLATES/
grep -r "TQ-05" backend/tests/bug_discovery/TEMPLATES/

# Verify quality gate exists
ls -la backend/tests/bug_discovery/TEST_QUALITY_GATE.md

# Verify pytest.ini quality settings
grep "strict-markers" backend/pytest.ini
grep "maxfail" backend/pytest.ini
```

**Expected Output:**
- All templates reference TQ-01 through TQ-05
- TEST_QUALITY_GATE.md exists with enforcement
- pytest.ini has strict-markers and maxfail

**Evidence:**
- All 4 templates include TQ compliance sections
- Created: `backend/tests/bug_discovery/TEST_QUALITY_GATE.md`

---

## INFRA-05: Fixture Reuse

**Requirement:** Bug discovery fixtures reuse existing auth_fixtures, database_fixtures, page_objects

**Verification Steps:**
- [ ] `FIXTURE_REUSE_GUIDE.md` documents all existing fixtures
- [ ] `e2e_ui/README.md` updated with bug discovery section
- [ ] Fuzzing conftest.py imports from e2e_ui/fixtures
- [ ] Browser discovery conftest.py imports from e2e_ui/fixtures
- [ ] No duplicate fixture definitions in bug discovery tests

**Commands:**
```bash
# Verify fixture reuse guide exists
ls -la backend/tests/bug_discovery/FIXTURE_REUSE_GUIDE.md

# Verify fixture imports
grep "from tests.e2e_ui.fixtures import" backend/tests/fuzzing/conftest.py
grep "from tests.e2e_ui.fixtures import" backend/tests/browser_discovery/conftest.py

# Verify no duplicate fixtures (should not define db_session, authenticated_page, etc.)
grep -n "def db_session" backend/tests/fuzzing/conftest.py && echo "FAIL: Duplicate fixture" || echo "PASS: No duplicate"
grep -n "def authenticated_page" backend/tests/browser_discovery/conftest.py && echo "FAIL: Duplicate fixture" || echo "PASS: No duplicate"
```

**Expected Output:**
- FIXTURE_REUSE_GUIDE.md exists with all fixtures documented
- Bug discovery conftest.py files import existing fixtures
- No duplicate fixture definitions

**Evidence:**
- Created: `backend/tests/bug_discovery/FIXTURE_REUSE_GUIDE.md`
- Updated: `backend/tests/e2e_ui/README.md` with bug discovery section
- Created: `backend/tests/fuzzing/conftest.py` with imports
- Created: `backend/tests/browser_discovery/conftest.py` with imports

---

## Phase 237 Success Criteria

**From ROADMAP.md:**
1. Bug discovery tests run in `pytest tests/` alongside existing tests
2. Fast PR tests complete in <10 minutes
3. Weekly bug discovery pipeline runs in ~2 hours
4. All bug discovery tests follow TEST_QUALITY_STANDARDS.md
5. Bug discovery fixtures reuse existing fixtures

**Verification Commands:**
```bash
# Success Criterion 1: pytest discovery
pytest backend/tests/ --collect-only | grep -E "fuzzing|browser_discovery|bug_discovery"

# Success Criterion 2: Fast PR tests
grep "timeout-minutes: 10" .github/workflows/pr-tests.yml

# Success Criterion 3: Weekly bug discovery
grep "timeout-minutes: 120" .github/workflows/bug-discovery-weekly.yml

# Success Criterion 4: TQ compliance
grep -r "TQ Compliance" backend/tests/bug_discovery/TEMPLATES/

# Success Criterion 5: Fixture reuse
grep "from tests.e2e_ui.fixtures import" backend/tests/fuzzing/conftest.py
grep "from tests.e2e_ui.fixtures import" backend/tests/browser_discovery/conftest.py
```

## Final Verification

Run all verification commands and confirm:
- [ ] All INFRA-01 through INFRA-05 checks pass
- [ ] All 5 success criteria are met
- [ ] No duplicate fixtures exist
- [ ] No separate /bug-discovery/ directory exists
- [ ] Pytest discovers all bug discovery tests
- [ ] CI workflows are correctly configured

**Verification Status:** [ ] PASS / [ ] FAIL

**Date Verified:** _______________

**Verified By:** _______________
