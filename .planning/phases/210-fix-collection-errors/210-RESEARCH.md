# Phase 210: Fix Test Collection Errors - Research

**Researched:** 2026-03-19
**Domain:** Test Infrastructure Quality
**Confidence:** HIGH

## Summary

Phase 210 addresses pytest collection errors caused by duplicate test file names in different directories. Currently, 3 collection errors block pytest from properly measuring code coverage. The root cause is Python's import system treating files with identical basenames (e.g., `test_agent_graduation_service_coverage.py`) as the same module, regardless of directory location. This research documents the conflicts, recommends a systematic renaming approach, and establishes naming conventions to prevent future occurrences.

**Primary recommendation:** Rename the newer, smaller test files in `tests/core/memory/` with unique suffixes (e.g., `_v2.py`) to resolve import conflicts while preserving test functionality. This follows the pattern established in Phases 199 and 200 for resolving collection errors.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 9.0.2 | Test framework | Industry standard, Python 3.14 compatible, module-based discovery |
| **Python import system** | 3.11+ | Module resolution | Basename-based module identification causes conflicts |
| **pytest-cov** | 7.0.0 | Coverage measurement | Coverage tracking requires all tests to be collected |

### Test Collection Behavior

| Aspect | Behavior | Impact |
|--------|----------|--------|
| **Module resolution** | Basename-based (ignores directory) | `tests/core/memory/test_foo.py` and `tests/core/agents/test_foo.py` conflict |
| **First import wins** | First file discovered becomes the module | Second file with same name triggers "import file mismatch" error |
| **Error visibility** | Collection fails but other tests still run | Easy to miss collection errors without explicit checks |
| **Fix requirement** | Unique basenames across entire test suite | Directory structure alone insufficient |

**Installation:**
```bash
# All dependencies already installed
pip install pytest==9.0.2 pytest-cov==7.0.0
```

---

## Architecture Patterns

### Current Collection Error State (March 19, 2026)

**Error Count:** 3 collection errors

**Error Type 1: AgentGraduationService Test Duplication**
```python
# Conflict:
tests/core/agents/test_agent_graduation_service_coverage.py
  → 1,378 lines, 14 test classes, 15 test methods
  → Created: Phase 193 (commit bc2a145ea)

tests/core/memory/test_agent_graduation_service_coverage.py
  → 556 lines, 9 test classes, 15 test methods
  → Created: Phase 206-05 (commit 86d07e53a)

# Error Message:
ERROR collecting tests/core/agents/test_agent_graduation_service_coverage.py
import file mismatch:
imported module 'test_agent_graduation_service_coverage' has this __file__ attribute:
  /Users/rushiparikh/projects/atom/backend/tests/core/memory/test_agent_graduation_service_coverage.py
```

**Error Type 2: EpisodeRetrievalService Test Duplication**
```python
# Conflict:
tests/core/episodes/test_episode_retrieval_service_coverage.py
  → 70 KB, 16 test methods
  → Created: Phase 14x (episode system implementation)

tests/core/memory/test_episode_retrieval_service_coverage.py
  → 26 KB, 7 test methods
  → Created: Phase 206-xx (memory module refactoring)

# Error Message:
ERROR collecting tests/core/episodes/test_episode_retrieval_service_coverage.py
import file mismatch:
imported module 'test_episode_retrieval_service_coverage' has this __file__ attribute:
  /Users/rushiparikh/projects/atom/backend/tests/core/memory/test_episode_retrieval_service_coverage.py
```

**Error Type 3: EpisodeSegmentationService Test Duplication**
```python
# Conflict:
tests/core/episodes/test_episode_segmentation_service_coverage.py
  → 49 KB, 56 test methods
  → Created: Phase 14x (episode system implementation)

tests/core/memory/test_episode_segmentation_service_coverage.py
  → 18 KB, 37 test methods
  → Created: Phase 206-xx (memory module refactoring)

# Error Message:
ERROR collecting tests/core/episodes/test_episode_segmentation_service_coverage.py
import file mismatch:
imported module 'test_episode_segmentation_service_coverage' has this __file__ attribute:
  /Users/rushiparikh/projects/atom/backend/tests/core/memory/test_episode_segmentation_service_coverage.py
```

### Resolution Strategy: Selective Renaming

**Principle:** Preserve the larger, more comprehensive test file and rename the smaller, newer file with a unique suffix.

**Rationale:**
- Larger files typically have more comprehensive test coverage
- Older files are more likely to be referenced in CI/CD pipelines
- Newer files in `tests/core/memory/` are recent additions (Phase 206)
- Memory module reorganization created these duplicates

**Renaming Pattern:**
```python
# Pattern 1: Add module-specific suffix
tests/core/memory/test_agent_graduation_service_coverage.py
  → tests/core/memory/test_agent_graduation_service_memory.py

tests/core/memory/test_episode_retrieval_service_coverage.py
  → tests/core/memory/test_episode_retrieval_memory.py

tests/core/memory/test_episode_segmentation_service_coverage.py
  → tests/core/memory/test_episode_segmentation_memory.py

# Pattern 2: Add version suffix (alternative)
  → tests/core/memory/test_agent_graduation_service_coverage_v2.py
```

### Renaming Implementation Pattern

**Step 1: Verify Test Functionality**
```bash
# Ensure tests pass before renaming
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest \
  tests/core/memory/test_agent_graduation_service_coverage.py -v

# Expected: All tests pass (no collection errors when run individually)
```

**Step 2: Rename File**
```bash
# Use git mv to preserve history
git mv tests/core/memory/test_agent_graduation_service_coverage.py \
        tests/core/memory/test_agent_graduation_service_memory.py

# Verify rename completed
ls -la tests/core/memory/test_agent_graduation_service_memory.py
```

**Step 3: Verify Collection**
```bash
# Check for collection errors
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest \
  tests/core/memory/ tests/core/agents/ --collect-only 2>&1 | grep "ERROR collecting"

# Expected: No errors (or reduced from 3 to 2)
```

**Step 4: Verify Test Execution**
```bash
# Run renamed tests
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest \
  tests/core/memory/test_agent_graduation_service_memory.py -v

# Expected: All tests still pass (same behavior as before rename)
```

### Naming Convention to Prevent Future Conflicts

**Rule:** Test filenames must be unique across the entire test suite, regardless of directory.

**Convention Options:**

**Option 1: Module-Specific Suffix (RECOMMENDED)**
```python
# Pattern: test_<service>_<module>.py

tests/core/agents/test_agent_graduation_service_coverage.py
tests/core/memory/test_agent_graduation_service_memory.py
tests/core/episodes/test_episode_retrieval_service_coverage.py
tests/core/memory/test_episode_retrieval_memory.py
tests/core/episodes/test_episode_segmentation_service_coverage.py
tests/core/memory/test_episode_segmentation_memory.py

# Benefits:
# - Descriptive (indicates module being tested)
# - Follows existing test directory structure
# - Easy to identify test scope
```

**Option 2: Version Suffix**
```python
# Pattern: test_<service>_coverage_v<version>.py

tests/core/agents/test_agent_graduation_service_coverage.py
tests/core/memory/test_agent_graduation_service_coverage_v2.py

# Benefits:
# - Clear iteration history
# - Easy to track test evolution
```

**Option 3: Directory-Encoded Name**
```python
# Pattern: test_<module>_<service>_coverage.py

tests/core/agents/test_agents_agent_graduation_service_coverage.py
tests/core/memory/test_memory_agent_graduation_service_coverage.py

# Benefits:
# - Guaranteed uniqueness
# - Clear module ownership

# Drawbacks:
# - Verbose
# - Redundant with directory structure
```

**Recommended:** Option 1 (Module-Specific Suffix) for balance of clarity and brevity.

### Anti-Patterns to Avoid

- **Duplicate basenames across directories:** Don't rely on directory structure for uniqueness
- **Generic test names:** Avoid `test_service_coverage.py` without module qualifier
- **Ignoring collection errors:** Collection errors mask missing tests and inflate coverage gaps
- **Inconsistent naming:** Don't mix `test_foo_memory.py` and `test_bar_coverage_v2.py`
- **Manual file moves without git:** Always use `git mv` to preserve file history

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Collection error detection | Manual pytest runs with grep | pytest --collect-only with error counting | Systematic verification, metrics on progress |
| Duplicate detection | Manual file name comparison | Automated script: `find tests/ -name "test_*.py" -type f | xargs -n1 basename | sort \| uniq -d` | Catches all duplicates, prevents future errors |
| Renaming safety | Manual `mv` commands | `git mv` to preserve history | Preserves git blame, revert capability |
| Import reference updates | Manual grep and edit | Automated refactoring tools or comprehensive grep search | Ensures all references updated, no broken imports |
| Naming convention enforcement | Manual code review | Pre-commit hook or CI check for duplicate basenames | Prevents future conflicts automatically |

**Key insight:** Python's import system is basename-based, not path-based. Directory structure does NOT prevent module conflicts. Unique basenames are required across the entire test suite.

---

## Common Pitfalls

### Pitfall 1: Ignoring Collection Errors

**What goes wrong:** pytest collection errors don't fail the test run, they just skip those files. This leads to artificially low coverage and missing test coverage.

**Why it happens:** pytest continues collecting and running other tests after encountering collection errors, masking the problem.

**How to avoid:**
```bash
# GOOD: Explicitly check for collection errors
pytest --collect-only -q 2>&1 | grep -c "ERROR collecting"
# Expected: 0

# Verify in CI/CD pipeline
# .github/workflows/test.yml
- name: Check test collection
  run: |
    ERRORS=$(pytest --collect-only -q 2>&1 | grep -c "ERROR collecting" || true)
    if [ $ERRORS -ne 0 ]; then
      echo "Found $ERRORS collection errors"
      exit 1
    fi

# BAD: Assume pytest ran all tests
# Collection errors don't fail pytest, so test passes but coverage is incomplete
```

**Warning signs:** Coverage drops unexpectedly, test count decreases, new tests don't appear in coverage reports

### Pitfall 2: Relying on Directory Structure for Uniqueness

**What goes wrong:** Assuming `tests/core/agents/test_foo.py` and `tests/core/memory/test_foo.py` are distinct modules.

**Why it happens:** Intuition says path matters, but Python imports are basename-based.

**How to avoid:**
```python
# GOOD: Unique basenames across entire test suite
tests/core/agents/test_agent_graduation_service_coverage.py
tests/core/memory/test_agent_graduation_service_memory.py

# BAD: Same basename in different directories
tests/core/agents/test_agent_graduation_service_coverage.py
tests/core/memory/test_agent_graduation_service_coverage.py
# ERROR: import file mismatch
```

**Warning signs:** Collection errors with "import file mismatch" message

### Pitfall 3: Renaming Without Checking for References

**What goes wrong:** Renaming a test file breaks imports in other test files or CI configuration.

**Why it happens:** Test files may import fixtures or classes from other test files (anti-pattern but happens).

**How to avoid:**
```bash
# GOOD: Search for imports before renaming
grep -r "from test_agent_graduation_service_coverage import" tests/
grep -r "import test_agent_graduation_service_coverage" tests/

# If found, update those references after renaming
# OLD: from test_agent_graduation_service_coverage import TestGraduationCriteria
# NEW: from test_agent_graduation_service_memory import TestGraduationCriteria

# Verify all references updated
grep -r "test_agent_graduation_service_coverage" tests/
# Expected: No results (all updated to new name)
```

**Warning signs:** Import errors after renaming, tests failing with `ModuleNotFoundError`

### Pitfall 4: Not Preserving Git History

**What goes wrong:** Using `mv` instead of `git mv` loses file history, making it harder to debug or revert.

**Why it happens:** Habitual use of Unix commands without considering git tracking.

**How to avoid:**
```bash
# GOOD: Use git mv to preserve history
git mv old_file.py new_file.py

# Verify history preserved
git log --follow -- new_file.py

# BAD: Use regular mv (breaks git history)
mv old_file.py new_file.py
git add new_file.py
git rm old_file.py
# History lost, git blame shows rename as origin
```

**Warning signs:** `git blame` shows rename operation instead of original commits

### Pitfall 5: Inconsistent Naming Conventions

**What goes wrong:** Mix of `test_foo_memory.py`, `test_bar_coverage_v2.py`, `test_baz_service.py` makes it unclear which tests to run.

**Why it happens:** Incremental renames without a plan, different developers using different patterns.

**How to avoid:**
```python
# GOOD: Consistent naming convention
# Pattern: test_<service>_<module>.py for duplicates
tests/core/agents/test_agent_graduation_service_coverage.py
tests/core/memory/test_agent_graduation_service_memory.py

# Pattern: test_<service>_coverage.py for unique names
tests/core/agents/test_agent_governance_service_coverage.py

# Consistency rules:
# 1. Use module suffix when duplicates exist
# 2. Use _coverage suffix for comprehensive test files
# 3. Avoid version suffixes unless tracking iterations
# 4. Document convention in CODE_QUALITY_STANDARDS.md

# BAD: Inconsistent patterns
tests/core/agents/test_agent_graduation_service_coverage.py
tests/core/memory/test_agent_graduation_service_coverage_v2.py
tests/core/memory/test_episode_retrieval_test.py
tests/core/episodes/test_segmentation.py
# Unclear which tests to run, hard to discover
```

**Warning signs:** Team confusion about which test files to run, grep difficulty finding tests

---

## Code Examples

Verified patterns from Phase 199/200 implementations and pytest documentation:

### Collection Error Detection Pattern

```bash
# Source: Phase 199-01 PLAN (pytest collection fixes)
# Problem: 3 collection errors blocking coverage measurement

# Step 1: Run collection and capture errors
pytest --collect-only -q 2>&1 | tee /tmp/pytest_collection.log

# Step 2: Count collection errors
ERROR_COUNT=$(grep -c "ERROR collecting" /tmp/pytest_collection.log || echo "0")
echo "Found $ERROR_COUNT collection errors"

# Step 3: Verify specific errors
grep "ERROR collecting" /tmp/pytest_collection.log
# Expected output:
# ERROR collecting tests/core/agents/test_agent_graduation_service_coverage.py
# ERROR collecting tests/core/episodes/test_episode_retrieval_service_coverage.py
# ERROR collecting tests/core/episodes/test_episode_segmentation_service_coverage.py

# Step 4: Verify no errors (after fix)
pytest --collect-only -q 2>&1 | grep "ERROR collecting"
# Expected: No output (0 errors)
```

### File Renaming Pattern

```bash
# Source: Phase 199 systematic fix approach
# Problem: Duplicate test basenames causing import conflicts

# Step 1: Identify larger file (preserve) vs smaller file (rename)
wc -l tests/core/agents/test_agent_graduation_service_coverage.py
# 1378 tests/core/agents/test_agent_graduation_service_coverage.py

wc -l tests/core/memory/test_agent_graduation_service_coverage.py
# 556 tests/core/memory/test_agent_graduation_service_coverage.py

# Decision: Rename smaller file in tests/core/memory/

# Step 2: Check for import references (safety check)
grep -r "from test_agent_graduation_service_coverage import" tests/
# Expected: No results (test files don't import each other)

# Step 3: Rename with git mv (preserves history)
git mv tests/core/memory/test_agent_graduation_service_coverage.py \
        tests/core/memory/test_agent_graduation_service_memory.py

# Step 4: Verify rename completed
ls -la tests/core/memory/test_agent_graduation_service_memory.py
# -rw-r--r--  1 rushiparikh  staff  19707 Mar 17 22:42 ..._memory.py

# Step 5: Verify collection error resolved
pytest tests/core/memory/ tests/core/agents/ --collect-only 2>&1 | grep "ERROR collecting"
# Expected: No error for agent_graduation_service (reduced from 3 to 2 errors)
```

### Verification Pattern

```bash
# Source: Phase 199-02 verification steps
# Problem: Ensure renamed tests still work correctly

# Step 1: Verify tests collect successfully
pytest tests/core/memory/test_agent_graduation_service_memory.py --collect-only -q
# Expected: "15 tests collected, 0 errors"

# Step 2: Verify tests execute successfully
pytest tests/core/memory/test_agent_graduation_service_memory.py -v
# Expected: All 15 tests pass

# Step 3: Verify no import errors
pytest tests/core/memory/test_agent_graduation_service_memory.py -v 2>&1 | grep -i "import"
# Expected: No import errors

# Step 4: Verify coverage measurement works
pytest tests/core/memory/test_agent_graduation_service_memory.py \
  --cov=core.agent_graduation_service --cov-report=term-missing
# Expected: Coverage report generated successfully

# Step 5: Full collection verification
pytest --collect-only -q 2>&1 | tail -5
# Expected: "XXXX tests collected, 0 errors in X.XXs"
```

### Naming Convention Enforcement Pattern

```bash
# Source: Phase 210 naming convention design
# Problem: Prevent future duplicate basenames

# Step 1: Detect duplicates (pre-commit hook)
#!/bin/bash
# .git/hooks/pre-commit

# Find duplicate test basenames
DUPLICATES=$(find tests/ -name "test_*.py" -type f | xargs -n1 basename | sort | uniq -d)

if [ -n "$DUPLICATES" ]; then
  echo "ERROR: Duplicate test file basenames found:"
  echo "$DUPLICATES"
  echo ""
  echo "Rename files to ensure unique basenames across entire test suite."
  echo "Pattern: tests/core/memory/test_service_memory.py"
  exit 1
fi

# Step 2: List all test basenames (for review)
find tests/ -name "test_*.py" -type f | xargs -n1 basename | sort | uniq -c | sort -rn
# Shows count of each basename (duplicates have count > 1)

# Step 3: Verify naming convention
# Check for _memory suffix in tests/core/memory/
find tests/core/memory/ -name "test_*_memory.py" -type f
# Expected: List of memory module tests with unique names

# Check for _coverage suffix (general pattern)
find tests/ -name "test_*_coverage.py" -type f | xargs -n1 basename | sort | uniq -d
# Expected: No duplicates (if found, need module-specific suffix)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Duplicate basenames allowed | Unique basenames required | Phase 210 (planned) | 0 collection errors, accurate coverage |
| Manual conflict detection | Automated duplicate detection | Phase 210 (planned) | Pre-commit hook prevents future errors |
| Inconsistent naming | Consistent naming convention | Phase 210 (planned) | Clear test ownership, easier discovery |
| Directory-based uniqueness | Basename-based uniqueness | Phase 210 (planned) | Matches Python import system behavior |

**Deprecated/outdated:**
- **Duplicate test basenames:** **ANTI-PATTERN** regardless of directory structure
- **Ignoring collection errors:** **MASKS** missing tests and coverage gaps
- **Manual `mv` for test files:** **LOSES** git history, use `git mv`
- **Generic test names:** **CAUSES** conflicts, use module-specific suffixes

---

## Open Questions

1. **Naming convention preference**
   - What we know: Module-specific suffix (`_memory.py`) is clear and descriptive
   - What's unclear: Team preference for `_memory.py` vs `_v2.py` suffix
   - Recommendation: Use `_memory.py` for clarity, document in CODE_QUALITY_STANDARDS.md

2. **Import reference safety**
   - What we know: Test files typically don't import other test files
   - What's unclear: Whether any CI/CD configs or scripts reference these files
   - Recommendation: Search for references before renaming, update if found

3. **Coverage measurement impact**
   - What we know: Collection errors prevent accurate coverage measurement
   - What's unclear: Current coverage percentage (artificially low due to errors)
   - Recommendation: Measure coverage after fixes to quantify improvement

4. **Future prevention mechanism**
   - What we know: Pre-commit hooks can detect duplicates
   - What's unclear: Whether to enforce in CI/CD pipeline or developer workflow only
   - Recommendation: Both - pre-commit hook for developer feedback, CI check for gatekeeping

---

## Duplicate Test File Analysis

### File Comparison Summary

| Test File | Location | Size | Test Classes | Test Methods | Created | Decision |
|-----------|----------|------|--------------|--------------|---------|----------|
| **test_agent_graduation_service_coverage.py** | agents/ | 1,378 lines | 14 | 15 | Phase 193 | **PRESERVE** (larger) |
| **test_agent_graduation_service_coverage.py** | memory/ | 556 lines | 9 | 15 | Phase 206-05 | **RENAME** → `_memory.py` |
| **test_episode_retrieval_service_coverage.py** | episodes/ | 70 KB | N/A | 16 | Phase 14x | **PRESERVE** (larger) |
| **test_episode_retrieval_service_coverage.py** | memory/ | 26 KB | N/A | 7 | Phase 206 | **RENAME** → `_memory.py` |
| **test_episode_segmentation_service_coverage.py** | episodes/ | 49 KB | N/A | 56 | Phase 14x | **PRESERVE** (larger) |
| **test_episode_segmentation_service_coverage.py** | memory/ | 18 KB | N/A | 37 | Phase 206 | **RENAME** → `_memory.py` |

### Renaming Strategy

**Files to Rename (3 total):**
1. `tests/core/memory/test_agent_graduation_service_coverage.py` → `test_agent_graduation_service_memory.py`
2. `tests/core/memory/test_episode_retrieval_service_coverage.py` → `test_episode_retrieval_memory.py`
3. `tests/core/memory/test_episode_segmentation_service_coverage.py` → `test_episode_segmentation_memory.py`

**Rationale:**
- Smaller files (newer, less comprehensive)
- Memory module reorganization in Phase 206 created duplicates
- Preserves larger, more established test files
- Clear naming indicates module scope

**Expected Outcome:**
- Collection errors reduced from 3 to 0
- All tests remain functional (rename only, no logic changes)
- Coverage measurement unblocked
- Naming convention established for future test files

---

## Sources

### Primary (HIGH confidence)

- pytest 9.0.2 Documentation - https://docs.pytest.org/en/stable/
  - Test discovery: `python_files = test_*.py`
  - Collection behavior: `pytest --collect-only`
  - Import system: Basename-based module resolution

- Phase 199-01 PLAN - `.planning/phases/199-fix-test-collection-errors/199-01-PLAN.md`
  - Systematic pytest configuration fixes
  - Collection error detection patterns
  - pytest.ini --ignore patterns

- Phase 200-01 PLAN - `.planning/phases/200-fix-collection-errors/200-01-PLAN.md`
  - Similar collection error resolution approach
  - File exclusion via pytest configuration

- pytest.ini - `/Users/rushiparikh/projects/atom/backend/pytest.ini`
  - Current test configuration
  - Existing ignore patterns for duplicate files (lines 114-120)

### Secondary (MEDIUM confidence)

- Python Import System Documentation - https://docs.python.org/3/reference/import.html
  - Module resolution rules
  - Basename-based module identification

- Git Documentation - https://git-scm.com/docs/git-mv
  - `git mv` preserves file history
  - Renaming files in version control

### Tertiary (LOW confidence)

- None - All findings verified against codebase, official documentation, or phase artifacts

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest 9.0.2 verified in codebase
- Architecture: HIGH - Collection errors confirmed via pytest --collect-only
- Resolution strategy: HIGH - Based on Phase 199/200 precedents
- Naming convention: MEDIUM - Multiple valid options, team preference unknown
- Pitfalls: HIGH - All pitfalls verified against actual pytest behavior

**Research date:** 2026-03-19
**Valid until:** 2026-04-18 (30 days - stable testing stack, pytest 9.x LTS)

---

## Appendices

### Appendix A: Collection Error Log

**Command:** `PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/core/memory/ tests/core/agents/ tests/core/episodes/ --collect-only 2>&1 | grep -A 3 "ERROR collecting"`

**Output (March 19, 2026):**
```
ERROR collecting tests/core/agents/test_agent_graduation_service_coverage.py
import file mismatch:
imported module 'test_agent_graduation_service_coverage' has this __file__ attribute:
  /Users/rushiparikh/projects/atom/backend/tests/core/memory/test_agent_graduation_service_coverage.py

ERROR collecting tests/core/episodes/test_episode_retrieval_service_coverage.py
import file mismatch:
imported module 'test_episode_retrieval_service_coverage' has this __file__ attribute:
  /Users/rushiparikh/projects/atom/backend/tests/core/memory/test_episode_retrieval_service_coverage.py

ERROR collecting tests/core/episodes/test_episode_segmentation_service_coverage.py
import file mismatch:
imported module 'test_episode_segmentation_service_coverage' has this __file__ attribute:
  /Users/rushiparikh/projects/atom/backend/tests/core/memory/test_episode_segmentation_service_coverage.py

=========================== summary ==========================
949 tests collected, 3 errors in 91.54s (0:01:31)
```

**Summary:** 3 collection errors, all due to duplicate basenames between `tests/core/memory/` and other directories.

### Appendix B: File Size Analysis

**Command:** `ls -lh tests/core/memory/test_*.py tests/core/agents/test_agent_graduation_service_coverage.py tests/core/episodes/test_episode_*.py | grep -E "graduation|retrieval|segmentation" | sort`

**Output:**
```
-rw-r--r--  1 rushiparikh  staff    18K Mar 17 22:23 tests/core/memory/test_episode_segmentation_service_coverage.py
-rw-r--r--  1 rushiparikh  staff    26K Mar 17 22:35 tests/core/memory/test_episode_retrieval_service_coverage.py
-rw-r--r--  1 rushiparikh  staff    20K Mar 17 22:42 tests/core/memory/test_agent_graduation_service_coverage.py
-rw-r--r--  1 rushiparikh  staff    49K Mar 14 15:04 tests/core/episodes/test_episode_segmentation_service_coverage.py
-rw-r--r--  1 rushiparikh  staff    70K Mar 14 15:13 tests/core/episodes/test_episode_retrieval_service_coverage.py
-rw-r--r--  1 rushiparikh  staff    46K Mar 14 20:17 tests/core/agents/test_agent_graduation_service_coverage.py
```

**Pattern:** Memory module files are consistently smaller (18-26K) vs episode/agents files (46-70K), supporting decision to rename memory files.

### Appendix C: Test Count Verification

**Agent Graduation Service Tests:**
```bash
$ grep -c "^    def test_" tests/core/agents/test_agent_graduation_service_coverage.py
15

$ grep -c "^    def test_" tests/core/memory/test_agent_graduation_service_coverage.py
15

# Both have 15 test methods, but agents/ version has more test classes (14 vs 9)
# and more comprehensive coverage (1,378 vs 556 lines)
```

**Episode Retrieval Service Tests:**
```bash
$ grep -c "^    def test_" tests/core/episodes/test_episode_retrieval_service_coverage.py
16

$ grep -c "^    def test_" tests/core/memory/test_episode_retrieval_service_coverage.py
7

# Episodes/ version has 2.3x more tests (16 vs 7)
```

**Episode Segmentation Service Tests:**
```bash
$ grep -c "^    def test_" tests/core/episodes/test_episode_segmentation_service_coverage.py
56

$ grep -c "^    def test_" tests/core/memory/test_episode_segmentation_service_coverage.py
37

# Episodes/ version has 1.5x more tests (56 vs 37)
```

### Appendix D: Naming Convention Examples

**Current State (with conflicts):**
```
tests/core/agents/test_agent_graduation_service_coverage.py
tests/core/memory/test_agent_graduation_service_coverage.py  ← CONFLICT

tests/core/episodes/test_episode_retrieval_service_coverage.py
tests/core/memory/test_episode_retrieval_service_coverage.py  ← CONFLICT

tests/core/episodes/test_episode_segmentation_service_coverage.py
tests/core/memory/test_episode_segmentation_service_coverage.py  ← CONFLICT
```

**Proposed State (unique basenames):**
```
tests/core/agents/test_agent_graduation_service_coverage.py
tests/core/memory/test_agent_graduation_service_memory.py  ← RENAMED

tests/core/episodes/test_episode_retrieval_service_coverage.py
tests/core/memory/test_episode_retrieval_memory.py  ← RENAMED

tests/core/episodes/test_episode_segmentation_service_coverage.py
tests/core/memory/test_episode_segmentation_memory.py  ← RENAMED
```

**Benefits:**
- ✅ No collection errors
- ✅ Clear module ownership
- ✅ Consistent naming convention
- ✅ Easy to discover and run specific module tests

---

*Phase: 210-fix-collection-errors*
*Research Date: 2026-03-19*
*Next Step: Create PLAN.md files based on research findings*
