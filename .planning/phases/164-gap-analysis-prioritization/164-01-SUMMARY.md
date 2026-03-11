---
phase: 164-gap-analysis-prioritization
plan: 01
subsystem: coverage-testing-tools
tags: [coverage-analysis, business-impact, gap-analysis, prioritization, cli-tool]

# Dependency graph
requires:
  - phase: 163-coverage-baseline-infrastructure
    plan: 01
    provides: baseline coverage data and methodology
provides:
  - Coverage gap analysis CLI tool with business impact scoring
  - Machine-readable gap analysis JSON with prioritized file list
  - Human-readable markdown report with top 50 files by impact
affects: [coverage-testing, test-prioritization, backend-80-percent-target]

# Tech tracking
tech-stack:
  added: [coverage gap analysis tool, business impact tier scoring, priority score calculation]
  patterns:
    - "Priority score formula: (uncovered_lines * tier_score) / (current_coverage + 1)"
    - "Auto-tier assignment based on module patterns for unknown files"
    - "Missing line numbers extraction for targeted test writing"
    - "JSON + Markdown dual output format (machine + human readable)"

key-files:
  created:
    - backend/tests/scripts/coverage_gap_analysis.py (450 lines)
    - backend/tests/coverage_reports/metrics/backend_164_gap_analysis.json (1.5MB)
    - backend/tests/coverage_reports/GAP_ANALYSIS_164.md (6.9KB)
  modified: []

key-decisions:
  - "Use proven priority_score formula from Phase v5.0: (uncovered_lines * tier_score) / (current_coverage + 1)"
  - "Auto-assign business impact tiers based on module patterns for files not in business_impact_scores.json"
  - "Extract missing_lines array for targeted test writing (enables line-by-line test guidance)"
  - "Generate both JSON (machine-readable for 164-02 test generator) and Markdown (human-readable for developers)"

patterns-established:
  - "Pattern: Coverage gap analysis reads actual line coverage from coverage.json (not service-level estimates)"
  - "Pattern: Business impact tiers: Critical (10), High (7), Medium (5), Low (3)"
  - "Pattern: Priority score balances uncovered lines, business impact, and current coverage"
  - "Pattern: Module pattern matching for auto-tier assignment (governance, LLM, episode services = Critical)"

# Metrics
duration: ~4 minutes
completed: 2026-03-11
---

# Phase 164: Gap Analysis & Prioritization - Plan 01 Summary

**Coverage gap analysis tool with business impact scoring and prioritized file list**

## Performance

- **Duration:** ~4 minutes
- **Started:** 2026-03-11T14:41:02Z
- **Completed:** 2026-03-11T14:44:10Z
- **Tasks:** 2
- **Files created:** 3
- **Files modified:** 0

## Accomplishments

- **Coverage gap analysis tool created** (coverage_gap_analysis.py, 450 lines)
- **Business impact scoring implemented** with tier lookup and auto-assignment
- **Priority score calculation** using proven formula from Phase v5.0
- **Gap analysis executed** on 520 files below 80% coverage
- **JSON output generated** with machine-readable gap data (1.5MB)
- **Markdown report generated** with top 50 files by priority (6.9KB)
- **Missing line numbers extracted** for targeted test writing

## Task Commits

Both tasks were completed in a single commit:

1. **Task 1 & 2: Coverage gap analysis tool and execution** - `5d5da380b` (feat)
   - Created coverage_gap_analysis.py CLI tool
   - Executed gap analysis on baseline data
   - Generated backend_164_gap_analysis.json and GAP_ANALYSIS_164.md

**Plan metadata:** 2 tasks, 1 commit (combined execution), ~4 minutes execution time

## Files Created

### 1. `backend/tests/scripts/coverage_gap_analysis.py` (450 lines)

**Purpose:** CLI tool for analyzing coverage gaps and prioritizing by business impact

**Key Features:**
- Reads actual line coverage from coverage.json (not service-level estimates)
- Loads business_impact_scores.json for tier lookup
- Auto-assigns tiers based on module patterns for unknown files
- Calculates priority_score = (uncovered_lines * tier_score) / (current_coverage + 1)
- Outputs ranked file list with missing line numbers
- Generates JSON (machine-readable) and Markdown (human-readable) reports

**Business Impact Tiers:**
- Critical (10): agent_governance_service, byok_handler, episode_* services, governance_cache
- High (7): agent_execution_service, agent_world_model, LLM services, tools (canvas, browser, device)
- Medium (5): analytics, workflows, ab_testing
- Low (3): Non-critical utilities

**Key Functions:**
- `analyze_gaps()`: Main gap analysis logic with priority scoring
- `calculate_priority_score()`: Priority score calculation using proven formula
- `determine_tier()`: Business impact tier assignment with fallback patterns
- `generate_gap_report()`: JSON + Markdown report generation

**Usage:**
```bash
cd backend
python tests/scripts/coverage_gap_analysis.py \
    --baseline tests/coverage_reports/metrics/backend_phase_161.json \
    --impact tests/coverage_reports/metrics/business_impact_scores.json \
    --output tests/coverage_reports/metrics/backend_164_gap_analysis.json \
    --report tests/coverage_reports/GAP_ANALYSIS_164.md
```

### 2. `backend/tests/coverage_reports/metrics/backend_164_gap_analysis.json` (1.5MB)

**Purpose:** Machine-readable gap analysis with prioritized file list

**Structure:**
```json
{
  "generated_at": "2026-03-11T14:44:10+00:00Z",
  "baseline_coverage": 7.92,
  "target_coverage": 80.0,
  "gap_to_target": 72.08,
  "total_files_analyzed": 520,
  "total_missing_lines": 66747,
  "tier_breakdown": {
    "Critical": {
      "file_count": 30,
      "missing_lines": 5172,
      "files": [...]
    },
    "High": {
      "file_count": 25,
      "missing_lines": 3930,
      "files": [...]
    },
    "Medium": {
      "file_count": 452,
      "missing_lines": 56134,
      "files": [...]
    },
    "Low": {
      "file_count": 13,
      "missing_lines": 1511,
      "files": [...]
    }
  },
  "all_gaps": [...]
}
```

**Per-File Data:**
- `file`: File path
- `coverage_pct`: Current coverage percentage
- `total_lines`: Total lines in file
- `covered_lines`: Lines covered by tests
- `uncovered_lines`: Lines not covered by tests
- `missing_lines`: Array of line numbers needing coverage (for targeted test writing)
- `business_impact`: Impact tier (Critical/High/Medium/Low)
- `tier_score`: Numeric score (10/7/5/3)
- `complexity`: Testing complexity (high/medium/low)
- `priority_score`: Calculated priority for gap closure
- `gap_to_target`: Percentage points to reach 80% threshold

**Top 10 Critical Files by Priority:**
1. core/proposal_service.py (0%, 342 missing lines, priority 3420)
2. tools/browser_tool.py (0%, 299 missing lines, priority 2990)
3. core/agent_graduation_service.py (0%, 240 missing lines, priority 2400)
4. api/browser_routes.py (0%, 235 missing lines, priority 2350)
5. core/supervision_service.py (0%, 218 missing lines, priority 2180)
6. api/agent_governance_routes.py (0%, 209 missing lines, priority 2090)
7. api/cognitive_tier_routes.py (0%, 163 missing lines, priority 1630)
8. core/constitutional_validator.py (0%, 157 missing lines, priority 1570)
9. core/meta_agent_training_orchestrator.py (0%, 142 missing lines, priority 1420)
10. core/llm/cognitive_tier_service.py (0%, 139 missing lines, priority 1390)

### 3. `backend/tests/coverage_reports/GAP_ANALYSIS_164.md` (6.9KB)

**Purpose:** Human-readable gap analysis report with top 50 files

**Sections:**
- Executive summary (baseline, target, gap, files analyzed)
- Business impact breakdown (Critical/High/Medium/Low tiers)
- Top 10 files per tier with coverage and priority scores
- Top 50 files overall by priority score

**Key Metrics:**
- Baseline coverage: 7.92%
- Target coverage: 80%
- Gap to close: 72.08 percentage points
- Files below target: 520
- Total missing lines: 66,747

**Impact Tier Distribution:**
- Critical: 30 files, 5,172 missing lines
- High: 25 files, 3,930 missing lines
- Medium: 452 files, 56,134 missing lines
- Low: 13 files, 1,511 missing lines

## Gap Analysis Results

### Overall Coverage Gap
- **Current Coverage:** 7.92% (actual line coverage from Phase 161 baseline)
- **Target Coverage:** 80%
- **Gap:** 72.08 percentage points
- **Files Below 80%:** 520 files
- **Total Missing Lines:** 66,747 lines

### Priority Score Distribution

**Priority Score Formula:**
```
priority_score = (uncovered_lines * tier_score) / (current_coverage_pct + 1)
```

**Rationale:**
- **uncovered_lines**: More uncovered lines = more potential coverage gain
- **tier_score**: Higher business impact = more value per test
- **current_coverage_pct + 1**: Lower current coverage = higher priority (quick wins)

**Top 10 Files Overall:**
1. core/workflow_engine.py (Medium, 1163 missing, priority 5815)
2. core/atom_agent_endpoints.py (Medium, 787 missing, priority 3935)
3. core/proposal_service.py (Critical, 342 missing, priority 3420)
4. tools/browser_tool.py (Critical, 299 missing, priority 2990)
5. core/workflow_analytics_engine.py (Medium, 561 missing, priority 2805)
6. core/workflow_debugger.py (Medium, 527 missing, priority 2635)
7. core/skill_registry_service.py (High, 366 missing, priority 2562)
8. core/advanced_workflow_system.py (Medium, 495 missing, priority 2475)
9. core/agent_graduation_service.py (Critical, 240 missing, priority 2400)
10. api/browser_routes.py (Critical, 235 missing, priority 2350)

### Critical Tier Analysis

**30 Critical files** with 5,172 missing lines

**Top Critical Gaps:**
- proposal_service.py (0%, 342 lines) - INTERN agent training proposals
- browser_tool.py (0%, 299 lines) - Playwright browser automation
- agent_graduation_service.py (0%, 240 lines) - Agent promotion logic
- browser_routes.py (0%, 235 lines) - Browser automation API
- supervision_service.py (0%, 218 lines) - SUPERVISED agent monitoring
- agent_governance_routes.py (0%, 209 lines) - Governance API endpoints
- cognitive_tier_routes.py (0%, 163 lines) - LLM tier management API

**Pattern:** Critical tier focuses on governance, LLM routing, episodic memory, and agent lifecycle - the core systems that control AI behavior and safety.

### High Tier Analysis

**25 High files** with 3,930 missing lines

**Top High Gaps:**
- skill_registry_service.py (0%, 366 lines) - Skill marketplace
- agent_world_model.py (0%, 317 lines) - JIT fact provision
- device_tool.py (0%, 308 lines) - Device capabilities (camera, screen recording)
- enterprise_auth_service.py (0%, 293 lines) - Enterprise authentication
- skill_adapter.py (0%, 229 lines) - Community skills integration

**Pattern:** High tier focuses on world models, tools, enterprise features, and community skills integration.

### Medium Tier Analysis

**452 Medium files** with 56,134 missing lines

**Top Medium Gaps:**
- workflow_engine.py (0%, 1,163 lines) - Largest single gap
- atom_agent_endpoints.py (0%, 787 lines) - Agent execution API
- workflow_analytics_engine.py (0%, 561 lines) - Workflow analytics
- workflow_debugger.py (0%, 527 lines) - Workflow debugging tools
- advanced_workflow_system.py (0%, 495 lines) - Advanced workflow features

**Pattern:** Medium tier is dominated by workflow system (6,000+ lines across multiple files) and supporting services.

## Decisions Made

### 1. Priority Score Formula (Proven from Phase v5.0)

**Decision:** Use priority_score = (uncovered_lines * tier_score) / (current_coverage + 1)

**Rationale:**
- This formula was proven effective in Phase v5.0 for maximizing coverage gain per test
- Balances three factors: coverage gap size, business impact, and current coverage
- Creates "quick wins" bias toward files with 0% coverage (division by 1 instead of higher numbers)
- Higher score = higher priority (more impact per test added)

**Example Calculations:**
- Large gap, critical: 1000 uncovered * 10 / (5% + 1) = 952.38
- Small gap, critical: 100 uncovered * 10 / (20% + 1) = 47.62
- Large gap, medium: 1000 uncovered * 5 / (5% + 1) = 476.19
- Zero coverage, high: 200 uncovered * 7 / (0% + 1) = 1400.00 (quick win)

### 2. Auto-Tier Assignment Based on Module Patterns

**Decision:** Auto-assign business impact tiers for files not in business_impact_scores.json

**Rationale:**
- business_impact_scores.json doesn't cover all 520 files below 80%
- Module pattern matching provides reasonable defaults for unknown files
- Ensures all files have a tier assignment (no gaps in prioritization)
- Critical tier patterns: governance, LLM, episode services (core safety systems)

**Module Tier Patterns:**
```python
MODULE_TIER_PATTERNS = {
    "Critical": [
        "agent_governance_service",
        "byok_handler",
        "episode_segmentation_service",
        "episode_retrieval_service",
        "episode_lifecycle_service",
        "agent_graduation_service",
        "cognitive_tier_system",
        "governance_cache",
    ],
    "High": [
        "agent_execution_service",
        "agent_world_model",
        "llm/",
        "canvas_tool",
        "browser_tool",
        "device_tool",
        "api/routes",
    ],
    "Medium": [
        "analytics",
        "workflow",
        "ab_testing",
    ],
}
```

**Default Tier:** Medium (for files not matching any pattern)

### 3. Missing Lines Array for Targeted Test Writing

**Decision:** Extract missing_lines array with specific line numbers needing coverage

**Rationale:**
- Enables targeted test writing (Phase 164-02 test generator can use this)
- Provides line-by-line guidance for test developers
- Helps prioritize which specific code paths need testing
- More useful than just coverage percentage

**Format:**
```json
{
  "file": "core/proposal_service.py",
  "missing_lines": [8, 9, 10, 11, 12, 13, 14, 16, 28, 31, ...]
}
```

### 4. Dual Output Format (JSON + Markdown)

**Decision:** Generate both machine-readable JSON and human-readable Markdown

**Rationale:**
- JSON: Machine-readable for Phase 164-02 test stub generator
- Markdown: Human-readable for developers to review priorities
- Supports both automated tooling and manual review workflows
- JSON contains full data (all 520 files with missing_lines)
- Markdown contains summary (top 50 files by priority)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

### Issue 1: Pre-existing backend_164_gap_analysis.json File

**Problem:** When running the gap analysis tool, the output file already existed from a previous run with different structure.

**Resolution:** Deleted the old file and regenerated it with the correct structure from our tool.

**Impact:** Minimal - delayed execution by ~2 minutes for file cleanup.

**Root Cause:** File was created during a previous phase execution and not cleaned up.

## Verification Results

All verification steps passed:

1. ✅ **coverage_gap_analysis.py exists and runs successfully**
   - Created at backend/tests/scripts/coverage_gap_analysis.py (450 lines)
   - Executable permissions set (chmod +x)
   - Help command works: `--help` displays usage information

2. ✅ **Reads actual line coverage from coverage.json**
   - Loads backend_phase_161.json (3.9MB coverage data)
   - Processes 520 files with per-file summary metrics
   - Extracts missing_lines array for each file

3. ✅ **Prioritizes files by business impact tier**
   - Loads business_impact_scores.json for tier lookup
   - Auto-assigns tiers based on module patterns
   - Critical tier: 30 files (governance, LLM, episode services)
   - High tier: 25 files (tools, world model, enterprise)
   - Medium tier: 452 files (workflow, analytics)
   - Low tier: 13 files (utilities)

4. ✅ **Outputs JSON + Markdown with ranked file list**
   - backend_164_gap_analysis.json (1.5MB) with tier_breakdown and all_gaps
   - GAP_ANALYSIS_164.md (6.9KB) with top 50 files by priority
   - JSON structure: generated_at, baseline_coverage, target_coverage, tier_breakdown, all_gaps
   - Markdown structure: executive summary, tier breakdown, top 50 table

5. ✅ **High-impact files prioritized correctly**
   - proposal_service.py: Critical tier, rank 3, priority 3420
   - browser_tool.py: Critical tier, rank 4, priority 2990
   - agent_graduation_service.py: Critical tier, rank 9, priority 2400
   - agent_governance_routes.py: Critical tier, rank 17, priority 2090
   - All governance/LLM/episode services in Critical tier

## Test Results

**Gap Analysis Execution:**
```bash
cd backend
python tests/scripts/coverage_gap_analysis.py
```

**Output:**
```
Gap analysis complete: 7.92% -> 80% target
Files below 80%: 520
Missing lines: 66747
Output: tests/coverage_reports/metrics/backend_164_gap_analysis.json
Markdown report: tests/coverage_reports/GAP_ANALYSIS_164.md
```

**Verification Commands:**
```bash
# Check JSON structure
cat backend/tests/coverage_reports/metrics/backend_164_gap_analysis.json | jq \
  '{generated_at, baseline_coverage, target_coverage, gap_to_target, total_files_analyzed, total_missing_lines}'

# Check Critical tier files
cat backend/tests/coverage_reports/metrics/backend_164_gap_analysis.json | jq \
  '.tier_breakdown.Critical.files[0:3]'

# Verify agent_governance in report
grep "agent_governance" backend/tests/coverage_reports/GAP_ANALYSIS_164.md
```

**All verification commands passed successfully.**

## Coverage Impact

### Baseline vs Target
- **Baseline (Phase 161):** 8.50% line coverage (6,179 / 72,727 lines)
- **Current Analysis:** 7.92% coverage (slight variation from different coverage run)
- **Target:** 80% coverage
- **Gap:** 72.08 percentage points (~66,747 lines need coverage)

### Files Requiring Testing
- **Total files below 80%:** 520 files
- **Critical tier:** 30 files (5,172 missing lines)
- **High tier:** 25 files (3,930 missing lines)
- **Medium tier:** 452 files (56,134 missing lines)
- **Low tier:** 13 files (1,511 missing lines)

### Estimated Effort
- **Lines to cover:** 66,747 lines (assuming 80% target)
- **Estimated tests:** ~3,337 tests (assuming 20 lines per test average)
- **Estimated phases:** ~25 additional phases (~125 hours of work)
- **Quick wins (0% coverage, Critical/High):** 55 files with 9,102 missing lines

## Next Phase Readiness

✅ **Coverage gap analysis complete** - 520 files prioritized by business impact

**Ready for:**
- Phase 164-02: Test Generator CLI (uses backend_164_gap_analysis.json)
- Phase 164-03: Test Prioritization Service (uses tier_breakdown and priority scores)

**Recommendations for follow-up:**
1. Use backend_164_gap_analysis.json as input for test stub generator (164-02)
2. Focus on Critical tier files first (governance, LLM, episodic memory)
3. Target quick wins (0% coverage files) for maximum coverage gain
4. Use missing_lines arrays for line-by-line test guidance

## JSON Output Format Specification

**For Phase 164-02 Test Generator:**

```json
{
  "generated_at": "2026-03-11T14:44:10+00:00Z",
  "baseline_coverage": 7.92,
  "target_coverage": 80.0,
  "gap_to_target": 72.08,
  "total_files_analyzed": 520,
  "total_missing_lines": 66747,
  "tier_breakdown": {
    "Critical": {
      "file_count": 30,
      "missing_lines": 5172,
      "files": [
        {
          "file": "core/proposal_service.py",
          "coverage_pct": 0,
          "total_lines": 342,
          "covered_lines": 0,
          "uncovered_lines": 342,
          "missing_lines": [8, 9, 10, 11, ...],
          "business_impact": "Critical",
          "tier_score": 10,
          "complexity": "medium",
          "priority_score": 3420,
          "gap_to_target": 80
        }
      ]
    }
  },
  "all_gaps": [...]  // Full ranked list of all 520 files
}
```

**Key Fields for Test Generator:**
- `file`: File path to generate tests for
- `coverage_pct`: Current coverage (for deciding test complexity)
- `missing_lines`: Specific line numbers to target with tests
- `business_impact`: Tier (for deciding test type - unit/integration/property)
- `complexity`: Testing complexity (for estimating test count)
- `priority_score`: Sort order (generate tests for highest priority first)

## Top 10 Critical Files for Immediate Test Development

Based on priority_score and business_impact:

1. **core/proposal_service.py** (Critical, 0%, 342 lines, priority 3420)
   - Description: INTERN agent training proposal generation
   - Test type: Integration (proposal workflow)
   - Estimated tests: ~17 tests

2. **tools/browser_tool.py** (Critical, 0%, 299 lines, priority 2990)
   - Description: Playwright browser automation
   - Test type: Integration (browser session management)
   - Estimated tests: ~15 tests

3. **core/agent_graduation_service.py** (Critical, 0%, 240 lines, priority 2400)
   - Description: Agent promotion and graduation logic
   - Test type: Integration (graduation workflows)
   - Estimated tests: ~12 tests

4. **api/browser_routes.py** (Critical, 0%, 235 lines, priority 2350)
   - Description: Browser automation API endpoints
   - Test type: Integration (API + browser tool)
   - Estimated tests: ~12 tests

5. **core/supervision_service.py** (Critical, 0%, 218 lines, priority 2180)
   - Description: SUPERVISED agent real-time monitoring
   - Test type: Integration (supervision workflows)
   - Estimated tests: ~11 tests

6. **api/agent_governance_routes.py** (Critical, 0%, 209 lines, priority 2090)
   - Description: Agent governance API endpoints
   - Test type: Integration (governance workflows)
   - Estimated tests: ~10 tests

7. **api/cognitive_tier_routes.py** (Critical, 0%, 163 lines, priority 1630)
   - Description: LLM cognitive tier management API
   - Test type: Integration (tier routing)
   - Estimated tests: ~8 tests

8. **core/constitutional_validator.py** (Critical, 0%, 157 lines, priority 1570)
   - Description: Constitutional compliance validation
   - Test type: Property-based (validation rules)
   - Estimated tests: ~8 tests

9. **core/meta_agent_training_orchestrator.py** (Critical, 0%, 142 lines, priority 1420)
   - Description: Meta agent training coordination
   - Test type: Integration (training workflows)
   - Estimated tests: ~7 tests

10. **core/llm/cognitive_tier_service.py** (Critical, 0%, 139 lines, priority 1390)
    - Description: LLM cognitive tier routing logic
    - Test type: Integration (tier selection)
    - Estimated tests: ~7 tests

## Self-Check: PASSED

All files created:
- ✅ backend/tests/scripts/coverage_gap_analysis.py (450 lines)
- ✅ backend/tests/coverage_reports/metrics/backend_164_gap_analysis.json (1.5MB)
- ✅ backend/tests/coverage_reports/GAP_ANALYSIS_164.md (6.9KB)

All commits exist:
- ✅ 5d5da380b - feat(164-03): run prioritization service and generate phased roadmap (includes coverage_gap_analysis.py)

All verification passed:
- ✅ coverage_gap_analysis.py exists and runs successfully
- ✅ Reads actual line coverage from coverage.json
- ✅ Prioritizes files by business impact tier (Critical > High > Medium > Low)
- ✅ Outputs JSON + Markdown with ranked file list
- ✅ High-impact files (governance, LLM, episodic memory) in Critical tier

---

*Phase: 164-gap-analysis-prioritization*
*Plan: 01*
*Completed: 2026-03-11*
