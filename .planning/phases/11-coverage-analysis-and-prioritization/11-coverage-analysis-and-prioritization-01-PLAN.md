---
phase: 11-coverage-analysis-and-prioritization
plan: 01
type: execute
wave: 1
depends_on: [10-fix-tests]
files_modified:
  - tests/coverage_reports/metrics/coverage_summary.json
  - tests/coverage_reports/priority_files_for_phases_12_13.json
  - tests/coverage_reports/PHASE_11_COVERAGE_ANALYSIS_REPORT.md
  - tests/scripts/analyze_coverage_gaps.py
autonomous: true

must_haves:
  truths:
    - Coverage report generated with detailed file-by-file breakdown showing lines, coverage percentage, and coverage gap
    - All files >200 lines identified and ranked by coverage gap (largest untested files first)
    - High-impact testing opportunities prioritized for Phases 12-13 (files with highest uncovered line counts)
    - Testing strategy document created with file priorities and recommended test types
  artifacts:
    - path: "tests/coverage_reports/metrics/coverage_summary.json"
      provides: "Aggregated coverage metrics by module and file size tier"
      contains: "files_by_size, high_priority_files, zero_coverage_files"
    - path: "tests/coverage_reports/priority_files_for_phases_12_13.json"
      provides: "Prioritized file list for Phases 12-13 execution"
      contains: "priority_ranking, estimated_coverage_gain, recommended_test_type"
    - path: "tests/coverage_reports/PHASE_11_COVERAGE_ANALYSIS_REPORT.md"
      provides: "Comprehensive coverage analysis report"
      min_lines: 200
    - path: "tests/scripts/analyze_coverage_gaps.py"
      provides: "Reusable coverage gap analysis script"
      min_lines: 100
  key_links:
    - from: "tests/scripts/analyze_coverage_gaps.py"
      to: "tests/coverage_reports/metrics/coverage.json"
      via: "JSON parsing and analysis"
      pattern: "json.load.*coverage.json"
    - from: "tests/coverage_reports/priority_files_for_phases_12_13.json"
      to: ".planning/phases/12-*/"
      via: "File priority list consumed by Phase 12 planning"
      pattern: "priority_files_for_phases_12_13"
---

<objective>
Generate comprehensive coverage analysis with file-by-file breakdown and create prioritized testing strategy for Phases 12-13.

Purpose: Current coverage is 22.8% (15,578 of 55,465 lines). This analysis identifies the highest-impact files for maximum coverage gain, enabling data-driven test planning for Phases 12-13. Focus on files >200 lines with lowest coverage percentages to maximize ROI.

Output: Coverage analysis report, prioritized file list, reusable analysis script, testing strategy document.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md

# Current Coverage Baseline (from Phase 10 completion)
- Overall coverage: 22.8% (15,578 of 55,465 lines)
- Total files analyzed: 405
- Target: 80% overall coverage (multi-phase journey)

# Key Finding from Coverage Data Analysis
Top 30 files >200 lines with highest coverage gaps (from preliminary analysis):
1. core/workflow_engine.py: 1163 lines, 4.8% coverage, 1107 lines uncovered
2. core/atom_agent_endpoints.py: 736 lines, 8.2% coverage, 675 lines uncovered
3. core/workflow_analytics_engine.py: 593 lines, 27.8% coverage, 428 lines uncovered
4. core/llm/byok_handler.py: 549 lines, 8.5% coverage, 502 lines uncovered
5. core/workflow_debugger.py: 527 lines, 9.7% coverage, 476 lines uncovered
6. core/byok_endpoints.py: 498 lines, 36.1% coverage, 318 lines uncovered
7. core/lancedb_handler.py: 494 lines, 18.0% coverage, 405 lines uncovered
8. core/auto_document_ingestion.py: 479 lines, 13.9% coverage, 412 lines uncovered
9. core/workflow_versioning_system.py: 476 lines, 16.6% coverage, 397 lines uncovered
10. core/advanced_workflow_system.py: 473 lines, 18.1% coverage, 387 lines uncovered

Zero coverage files >100 lines (22 files identified):
- core/enterprise_user_management.py: 213 lines, 0.0% coverage
- core/embedding_service.py: 190 lines, 0.0% coverage
- core/byok_cost_optimizer.py: 188 lines, 0.0% coverage
- core/reconciliation_engine.py: 181 lines, 0.0% coverage

# Phase 8.6 Strategy Validation
Phase 8.6 proved high-impact file testing yields 3.38x velocity acceleration:
- High-impact files (>150 lines): +1.42% per plan
- Early Phase 8 (unfocused): +0.42% per plan
- Target: 50% average coverage per file (not 100% - diminishing returns)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create coverage gap analysis script</name>
  <files>tests/scripts/analyze_coverage_gaps.py</files>
  <action>
Create reusable Python script at tests/scripts/analyze_coverage_gaps.py that:

1. Parses tests/coverage_reports/metrics/coverage.json
2. Categorizes files into tiers:
   - Tier 1: >500 lines (highest impact)
   - Tier 2: 300-500 lines (high impact)
   - Tier 3: 200-300 lines (medium impact)
   - Tier 4: 100-200 lines (low impact)
   - Tier 5: <100 lines (minimal impact)

3. For each file, calculates:
   - coverage_gap = total_lines * (1 - coverage_percentage/100)
   - potential_gain = coverage_gap * 0.5 (assuming 50% achievable coverage)
   - priority_score = coverage_gap / total_lines (uncovered ratio)

4. Outputs three JSON files:
   - coverage_summary.json: Module-level aggregations
   - priority_files_for_phases_12_13.json: Ranked by coverage_gap
   - zero_coverage_analysis.json: Files with 0% coverage >100 lines

5. Generates markdown report with sections:
   - Executive Summary (overall coverage, total gap)
   - High-Impact Files (Tier 1-3 by coverage_gap)
   - Zero Coverage Files (priority for quick wins)
   - Module Breakdown (core/, api/, tools/)
   - Recommendations for Phases 12-13

Script requirements:
- Use argparse for CLI options (--output-dir, --format json|markdown|all)
- Error handling for missing coverage.json
- Type hints for all functions
- Docstrings with usage examples

DO NOT modify coverage.json - it's the source of truth generated by pytest-cov.
</action>
  <verify>python3 tests/scripts/analyze_coverage_gaps.py --format all --output-dir tests/coverage_reports/metrics/</verify>
  <done>Script executes successfully and generates coverage_summary.json, priority_files_for_phases_12_13.json, and PHASE_11_COVERAGE_ANALYSIS_REPORT.md</done>
</task>

<task type="auto">
  <name>Task 2: Generate coverage analysis report</name>
  <files>tests/coverage_reports/PHASE_11_COVERAGE_ANALYSIS_REPORT.md</files>
  <action>
Run the analysis script and create comprehensive markdown report at tests/coverage_reports/PHASE_11_COVERAGE_ANALYSIS_REPORT.md with:

1. Executive Summary:
   - Current coverage: 22.8% (55,465 total lines, 15,578 covered)
   - Remaining gap: 39,887 lines to reach 80%
   - High-impact files (>200 lines): ~90 files
   - Zero-coverage files (>100 lines): 22 files

2. Top 20 High-Impact Files table:
   Columns: File, Total Lines, Current %, Uncovered Lines, Priority Score, Recommended Tests

3. Zero Coverage Quick Wins section:
   - List all 22 files with 0% coverage >100 lines
   - Estimated coverage gain if tested to 50%
   - Recommended test type (unit, integration, property)

4. Module Breakdown:
   - core/: Current coverage %, total lines, top 5 gaps
   - api/: Current coverage %, total lines, top 5 gaps
   - tools/: Current coverage %, total lines, top 5 gaps

5. Phase 12-13 Strategy:
   - Wave 1 (Phase 12): Tier 1 files (>500 lines) - estimated +3-4% coverage
   - Wave 2 (Phase 12): Tier 2 files (300-500 lines) - estimated +2-3% coverage
   - Wave 3 (Phase 13): Zero coverage files - estimated +1-2% coverage

6. Test Type Recommendations:
   - Property tests: workflow_engine, byok_handler (stateful logic)
   - Integration tests: atom_agent_endpoints, workflow_endpoints (API contracts)
   - Unit tests: lancedb_handler, auto_document_ingestion (isolated logic)

7. Execution Plan:
   - Files per plan: 3-4 high-impact files
   - Target coverage per file: 50% (proven sustainable from Phase 8.6)
   - Estimated velocity: +1.5% per plan (maintaining Phase 8.6 acceleration)

Use the following format for file rankings:
```
| Rank | File | Lines | Current % | Uncovered | Priority |
|------|------|-------|-----------|-----------|----------|
| 1 | core/workflow_engine.py | 1163 | 4.8% | 1107 | 0.95 |
```
</action>
  <verify>grep -q "Executive Summary" tests/coverage_reports/PHASE_11_COVERAGE_ANALYSIS_REPORT.md && grep -q "Top 20 High-Impact Files" tests/coverage_reports/PHASE_11_COVERAGE_ANALYSIS_REPORT.md && grep -q "Phase 12-13 Strategy" tests/coverage_reports/PHASE_11_COVERAGE_ANALYSIS_REPORT.md</verify>
  <done>Report contains all required sections with accurate data from coverage.json</done>
</task>

<task type="auto">
  <name>Task 3: Create prioritized file list for Phases 12-13</name>
  <files>tests/coverage_reports/priority_files_for_phases_12_13.json</files>
  <action>
Generate JSON file at tests/coverage_reports/priority_files_for_phases_12_13.json with structure:

```json
{
  "generated_at": "2026-02-15T...",
  "current_coverage": {
    "percent": 22.8,
    "covered_lines": 15578,
    "total_lines": 55465
  },
  "target_coverage": {
    "percent": 80,
    "required_lines": 44372,
    "gap_lines": 28794
  },
  "phases": {
    "12": {
      "target_percent": 28,
      "target_gain": 5.2,
      "files": [
        {
          "rank": 1,
          "file": "core/workflow_engine.py",
          "lines": 1163,
          "current_percent": 4.8,
          "uncovered_lines": 1107,
          "estimated_tests_needed": 40,
          "recommended_test_type": "property",
          "coverage_complexity": "high",
          "dependencies": ["workflow_analytics_engine", "workflow_debugger"]
        }
      ]
    },
    "13": {
      "target_percent": 35,
      "target_gain": 7.0,
      "files": [...]
    }
  },
  "zero_coverage_quick_wins": [
    {
      "file": "core/enterprise_user_management.py",
      "lines": 213,
      "estimated_gain_lines": 107,
      "recommended_test_type": "unit"
    }
  ]
}
```

Group files by:
- Phase 12: Tier 1 files (>500 lines, <20% coverage) - highest ROI
- Phase 13: Tier 2 files (300-500 lines, <30% coverage) + zero coverage files

Include test complexity estimates:
- low: <30 tests needed (simple CRUD, utilities)
- medium: 30-60 tests (business logic, some async)
- high: >60 tests (stateful, complex workflows, async heavy)

DO NOT include files already >70% coverage (diminishing returns).
</action>
  <verify>python3 -c "import json; data = json.load(open('tests/coverage_reports/priority_files_for_phases_12_13.json')); assert 'phases' in data; assert '12' in data['phases']; assert '13' in data['phases']; assert len(data['phases']['12']['files']) > 0"</verify>
  <done>JSON file contains valid structure with Phase 12 and 13 file rankings, test type recommendations, and complexity estimates</done>
</task>

</tasks>

<verification>
1. Coverage analysis script executes without errors
2. All output files generated: coverage_summary.json, priority_files_for_phases_12_13.json, PHASE_11_COVERAGE_ANALYSIS_REPORT.md
3. Report contains accurate coverage data matching coverage.json source
4. Prioritized file list contains only high-impact files (>200 lines, <50% coverage)
5. Test type recommendations align with file complexity and dependencies
</verification>

<success_criteria>
1. Coverage analysis report (PHASE_11_COVERAGE_ANALYSIS_REPORT.md) exists with all required sections
2. Prioritized file list (priority_files_for_phases_12_13.json) contains ~30-40 high-impact files across Phases 12-13
3. Reusable analysis script (analyze_coverage_gaps.py) can be run for future coverage snapshots
4. Report identifies clear testing strategy: Tier 1 files first, targeting 50% coverage per file
5. Estimated coverage gain quantified: Phase 12 (+5-6%), Phase 13 (+7-8%)
</success_criteria>

<output>
After completion, create `.planning/phases/11-coverage-analysis-and-prioritization/11-coverage-analysis-and-prioritization-01-SUMMARY.md` with:
- Coverage analysis results (total gap, high-impact files identified)
- Files generated and their locations
- Key findings (top uncovered files, zero coverage quick wins)
- Recommendations for Phase 12 planning (specific files, estimated coverage gain)
- Execution time and task completion summary
</output>
