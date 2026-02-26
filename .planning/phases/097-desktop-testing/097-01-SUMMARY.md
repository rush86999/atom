---
phase: 097-desktop-testing
plan: 01
title: "Desktop Coverage Aggregation"
oneLiner: "Extended unified coverage aggregation to include Rust tarpaulin coverage from desktop, enabling 4-platform coverage tracking"
subsystem: Testing Infrastructure
tags: [coverage, tarpaulin, rust, desktop, aggregation, python]
---

## Phase 097 Plan 01: Desktop Coverage Aggregation Summary

**Completed:** 2026-02-26
**Duration:** 2 minutes
**Commits:** 2

---

### Overview

Extended the unified coverage aggregation script (`backend/tests/scripts/aggregate_coverage.py`) to support Rust tarpaulin coverage from the desktop platform. The script now aggregates coverage from all 4 platforms (backend pytest, frontend Jest, mobile jest-expo, desktop tarpaulin) into a single unified report with per-platform breakdown.

**Key Achievement:** 4-platform coverage aggregation with graceful degradation for missing desktop coverage (warning, not error).

---

### Implementation Details

#### 1. Added `load_tarpaulin_coverage` Function

**Location:** `backend/tests/scripts/aggregate_coverage.py` (lines 255-318)

**Implementation:**
```python
def load_tarpaulin_coverage(path: Path) -> Dict[str, Any]:
    """Load cargo-tarpaulin coverage.json from desktop tests."""
    result = {
        "platform": "rust",
        "coverage_pct": 0.0,
        "covered": 0,
        "total": 0,
        "branches_covered": 0,
        "branches_total": 0,
        "branch_coverage_pct": 0.0,
        "file": str(path),
    }

    if not path.exists():
        result["error"] = "file not found"
        return result

    try:
        with open(path, 'r') as f:
            coverage_data = json.load(f)

        # Tarpaulin coverage.json format:
        # {
        #   "files": {
        #     "path/to/file.rs": {
        #       "stats": {
        #         "covered": 50,
        #         "coverable": 100,
        #         "percent": 50.0
        #       }
        #     }
        #   }
        # }

        total_covered = 0
        total_lines = 0

        files = coverage_data.get("files", {})
        for file_path, file_data in files.items():
            stats = file_data.get("stats", {})
            total_covered += stats.get("covered", 0)
            total_lines += stats.get("coverable", 0)

        result["covered"] = total_covered
        result["total"] = total_lines

        # Calculate line coverage percentage
        if result["total"] > 0:
            result["coverage_pct"] = (result["covered"] / result["total"] * 100)
        else:
            result["coverage_pct"] = 0.0

        # Note: tarpaulin doesn't provide branch coverage
        result["branches_covered"] = 0
        result["branches_total"] = 0
        result["branch_coverage_pct"] = 0.0

    except (json.JSONDecodeError, IOError) as e:
        result["error"] = str(e)

    return result
```

**Key Design Decisions:**
- Tarpaulin JSON format parsed from `files.{path}.stats` structure
- Branch coverage set to 0 (tarpaulin doesn't provide branch metrics)
- Graceful degradation with `error` field for missing/invalid files
- Consistent with existing `load_jest_coverage` and `load_jest_expo_coverage` patterns

#### 2. Updated `aggregate_coverage` Function

**Changes:**
- Added `tarpaulin_path: Optional[Path] = None` parameter
- Load rust coverage: `rust_coverage = load_tarpaulin_coverage(tarpaulin_path) if tarpaulin_path else None`
- Include rust in platforms dict if available
- Update overall coverage calculation:

```python
# Add rust/desktop coverage if available
if rust_coverage:
    total_covered += rust_coverage["covered"]
    total_lines += rust_coverage["total"]
    total_branches_covered += rust_coverage["branches_covered"]
    total_branches += rust_coverage["branches_total"]
```

**Overall Coverage Formula (4 platforms):**
```
(covered_backend + covered_frontend + covered_mobile + covered_rust) /
(total_backend + total_frontend + total_mobile + total_rust)
```

#### 3. Updated CLI Arguments

**New Argument:**
```python
parser.add_argument(
    "--desktop-coverage",
    type=Path,
    default=Path(__file__).parent.parent.parent.parent / "frontend-nextjs" / "src-tauri" / "coverage" / "coverage.json",
    help="Path to tarpaulin coverage.json (default: frontend-nextjs/src-tauri/coverage/coverage.json)"
)
```

**Usage:**
```bash
python3 backend/tests/scripts/aggregate_coverage.py --help | grep desktop
  --desktop-coverage DESKTOP_COVERAGE
                        Path to tarpaulin coverage.json (default: frontend-
                        nextjs/src-tauri/coverage/coverage.json)
```

#### 4. Updated Report Generation

**Text Format:**
```
RUST:
  File: /Users/rushiparikh/projects/atom/frontend-nextjs/src-tauri/coverage/coverage.json
  Line Coverage:    38.00%  (     57 /     150 lines)
  Branch Coverage:   0.00%  (      0 /       0 branches)
```

**Markdown Format:**
```markdown
| **rust** | 38.00% | 0.00% | ✅ OK |
```

**JSON Format:**
```json
"rust": {
  "platform": "rust",
  "coverage_pct": 38.0,
  "covered": 57,
  "total": 150,
  "branches_covered": 0,
  "branches_total": 0,
  "branch_coverage_pct": 0.0,
  "file": "/Users/rushiparikh/projects/atom/frontend-nextjs/src-tauri/coverage/coverage.json"
}
```

---

### Test Results

#### Mock Tarpaulin Coverage File

Created mock coverage file for testing:
```json
{
  "files": {
    "src/lib.rs": {
      "stats": {
        "covered": 42,
        "coverable": 100,
        "percent": 42.0
      }
    },
    "src/main.rs": {
      "stats": {
        "covered": 15,
        "coverable": 50,
        "percent": 30.0
      }
    }
  }
}
```

**Calculations:**
- Total covered: 42 + 15 = 57 lines
- Total coverable: 100 + 50 = 150 lines
- Coverage percentage: 57 / 150 = 38.0%

#### Verification Tests

**Test 1: All 4 Platforms in Unified Report**
```bash
python3 backend/tests/scripts/aggregate_coverage.py --format text
```
Result: ✅ All platforms (python, javascript, mobile, rust) appear in output

**Test 2: JSON Structure Verification**
```bash
cat backend/tests/scripts/coverage_reports/unified/coverage.json | python3 -c "import json, sys; data = json.load(sys.stdin); print('Platforms:', list(data['platforms'].keys()))"
```
Result: ✅ `Platforms: ['python', 'javascript', 'mobile', 'rust']`

**Test 3: Overall Coverage Calculation**
```
Without desktop: 20294 / 97517 = 20.81%
With desktop: (20294 + 57) / (97517 + 150) = 20351 / 97667 = 20.84%
```
Result: ✅ Overall coverage correctly includes desktop in weighted average

**Test 4: Graceful Handling of Missing Desktop Coverage**
```bash
rm frontend-nextjs/src-tauri/coverage/coverage.json
python3 backend/tests/scripts/aggregate_coverage.py --format text
```
Result: ✅ Warning message (not error), script exits successfully:
```
⚠️  WARNING: rust coverage file not found or invalid: frontend-nextjs/src-tauri/coverage/coverage.json
```

---

### Current Coverage Metrics (Without Desktop)

**Overall Coverage:** 20.81% (20,294 / 97,517 lines)
- Backend (Python): 21.67% (18,552 / 69,417 lines)
- Frontend (JavaScript): 3.45% (761 / 22,031 lines)
- Mobile (jest-expo): 16.16% (981 / 6,069 lines)
- Desktop (Rust): 0.00% (0 / 0 lines) - file not found

**Branch Coverage:** 2.62% (939 / 35,802 branches)
- Backend: 1.14% (194 / 17,080 branches)
- Frontend: 2.48% (382 / 15,374 branches)
- Mobile: 10.84% (363 / 3,348 branches)
- Desktop: 0.00% (0 / 0 branches) - tarpaulin doesn't provide branch coverage

**Note:** Desktop coverage file doesn't exist yet (requires x86_64 architecture and cargo-tarpaulin execution). The infrastructure is ready to aggregate desktop coverage once generated.

---

### Files Modified

**Created:**
- `frontend-nextjs/src-tauri/coverage/coverage.json` (mock file, not committed - ignored by .gitignore)

**Modified:**
- `backend/tests/scripts/aggregate_coverage.py` (+102 lines, -5 lines)
  - Added `load_tarpaulin_coverage` function (64 lines)
  - Updated `aggregate_coverage` function signature and implementation
  - Updated `main` function with `--desktop-coverage` argument
  - Updated docstring to reflect 4-platform support

**Generated:**
- `backend/tests/scripts/coverage_reports/unified/coverage.json` (unified coverage report with 4 platforms)

---

### Success Criteria Validation

| Criterion | Status | Evidence |
|-----------|--------|----------|
| 1. load_tarpaulin_coverage function exists and parses desktop coverage | ✅ | Function at lines 255-318, tested with mock data |
| 2. Rust/desktop platform appears in all report formats (text, json, markdown) | ✅ | Verified in all 3 formats |
| 3. Overall coverage percentage includes desktop in weighted average | ✅ | 20.84% with desktop vs 20.81% without |
| 4. Script handles missing desktop coverage gracefully (warning, not error) | ✅ | Warning message, exits with 0 |
| 5. CLI accepts --desktop-coverage argument | ✅ | `--help` shows argument with default path |

**All success criteria met.**

---

### Deviations from Plan

**None** - Plan executed exactly as written.

---

### Next Steps

**Phase 097-02:** Desktop Test Infrastructure Setup
- Configure Jest for Tauri desktop application testing
- Set up tauri-driver for WebDriver-based E2E testing
- Create desktop test directory structure and configuration files

**Expected Outcome:** Desktop test infrastructure ready for integration tests (window management, file system, IPC).

---

### Integration Points

**Upstream Dependencies:**
- None (standalone coverage aggregation enhancement)

**Downstream Dependencies:**
- Phase 097-02 (Desktop Test Infrastructure) - Will generate real tarpaulin coverage
- Phase 097-07 (Phase Verification) - Will use unified coverage metrics

**External Integrations:**
- `frontend-nextjs/src-tauri/coverage.sh` - Generates tarpaulin coverage.json
- `.github/workflows/unified-tests.yml` - CI workflow that aggregates coverage

---

### Lessons Learned

1. **Consistent Patterns Matter:** Following the same structure as `load_jest_coverage` and `load_jest_expo_coverage` made the implementation straightforward and maintainable.

2. **Graceful Degradation:** Handling missing desktop coverage with a warning (not error) allows the script to run successfully even when desktop coverage isn't available (ARM Macs, CI environments).

3. **Tarpaulin Limitations:** Tarpaulin doesn't provide branch coverage, so we set branches to 0. This is acceptable for line coverage tracking but may affect overall branch coverage metrics.

4. **Default Path Convention:** Using `frontend-nextjs/src-tauri/coverage/coverage.json` as the default path aligns with the existing coverage.sh script and maintains consistency with frontend/mobile coverage locations.

---

### References

**Plan:** `.planning/phases/097-desktop-testing/097-01-PLAN.md`
**Research:** `.planning/phases/097-desktop-testing/097-RESEARCH.md`
**Coverage Script:** `backend/tests/scripts/aggregate_coverage.py`
**Desktop Coverage Script:** `frontend-nextjs/src-tauri/coverage.sh`

---

*Summary generated: 2026-02-26*
*Phase: 097 (Desktop Testing)*
*Plan: 01 (Desktop Coverage Aggregation)*
*Status: ✅ COMPLETE*

---

## Self-Check: PASSED

**Files Created/Modified:**
- ✅ `backend/tests/scripts/aggregate_coverage.py` - Extended with tarpaulin support
- ✅ `.planning/phases/097-desktop-testing/097-01-SUMMARY.md` - Plan summary

**Commits:**
- ✅ `1c6c425b6` - feat(097-01): add tarpaulin coverage loader to aggregation script
- ✅ `fd29318d2` - test(097-01): test desktop coverage aggregation with mock data

**Functions Added:**
- ✅ `load_tarpaulin_coverage` - Parses tarpaulin JSON format

**CLI Arguments:**
- ✅ `--desktop-coverage` - Path to tarpaulin coverage.json

**Success Criteria:**
- ✅ All 5 success criteria met (function exists, all report formats, overall calculation, graceful handling, CLI argument)

**Tests:**
- ✅ Verified with mock tarpaulin coverage (150 lines, 38%)
- ✅ Verified graceful handling with missing file
- ✅ Verified all 4 platforms in unified report
