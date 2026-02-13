---
phase: 08-80-percent-coverage-push
plan: 22
type: execute
wave: 3
depends_on: ["21"]
files_modified: ["backend/tests/coverage_reports/PHASE_8_7_PLAN.md"]
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "Phase 8.7 plan created with top 10-15 zero-coverage files identified"
    - "Realistic +2-3% coverage target calculated based on actual velocity"
    - "File-by-file breakdown with line counts and coverage estimates provided"
    - "Testing strategy documented based on Phase 8.6 learnings"
  artifacts:
    - path: "backend/tests/coverage_reports/PHASE_8_7_PLAN.md"
      provides: "Detailed Phase 8.7 testing plan with file list and targets"
      min_lines: 400
  key_links:
    - from: "backend/tests/coverage_reports/PHASE_8_7_PLAN.md"
      to: "backend/tests/coverage_reports/metrics/coverage_summary.json"
      via: "Velocity-based target calculation"
      pattern: "velocity.*1.42.*percent.*plan"
---

<objective>
Create detailed Phase 8.7 plan with top 10-15 zero-coverage files by size, realistic +2-3% coverage target, and testing strategy based on Phase 8.6 learnings.

Purpose: Bridge the gap between Phase 8 completion (15.87% coverage) and the next phase of work with concrete file list, coverage targets, and execution strategy.

Output: PHASE_8_7_PLAN.md with file breakdown, coverage estimates, and testing approach.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-21-PLAN.md
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-20-SUMMARY.md
@backend/tests/coverage_reports/metrics/coverage_summary.json

# Phase 8.6 Learnings to Apply:
1. High-impact files (>150 lines) provide 3.38x velocity
2. Target 50% average coverage per file (sustainable)
3. 4 plans per wave with 4 files each = optimal flow
4. Focus on workflow, governance, and API files for maximum impact

# Current State:
- Coverage: 15.87% overall
- Zero-coverage files: 99 remaining
- Velocity: +1.42% per plan (Phase 8.6)
- Target: 17-18% (+2-3%)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Identify top 10-15 zero-coverage files by size</name>
  <files>backend/tests/coverage_reports/PHASE_8_7_PLAN.md</files>
  <action>
    Create PHASE_8_7_PLAN.md with file inventory. First, analyze coverage.json to identify zero-coverage files sorted by line count. Use this command:

    ```bash
    python3 << 'EOF'
    import json
    import os

    coverage_file = "/Users/rushiparikh/projects/atom/backend/tests/coverage_reports/metrics/coverage.json"
    backend_dir = "/Users/rushiparikh/projects/atom/backend"

    with open(coverage_file, 'r') as f:
        data = json.load(f)

    zero_coverage = []
    for file_path, file_data in data.get('files', {}).items():
        pct = file_data['summary']['percent_covered']
        if pct == 0.0:
            # Get actual line count from source file
            full_path = os.path.join(backend_dir, file_path)
            if os.path.exists(full_path):
                with open(full_path, 'r') as src:
                    lines = len(src.readlines())
                zero_coverage.append((file_path, lines))

    # Sort by line count descending
    zero_coverage.sort(key=lambda x: x[1], reverse=True)

    print("# Top Zero-Coverage Files by Size")
    print("| File | Lines | Module |")
    print("|------|-------|--------|")
    for path, lines in zero_coverage[:20]:
        module = path.split('/')[0] if '/' in path else 'unknown'
        print(f"| {path} | {lines} | {module} |")
    EOF
    ```

    Then create PHASE_8_7_PLAN.md with:
    1. Top 10-15 zero-coverage files table
    2. Group by module (core, api, tools)
    3. Calculate total lines to be covered
    4. Estimate coverage impact at 50% average per file
  </action>
  <verify>test -f backend/tests/coverage_reports/PHASE_8_7_PLAN.md && grep -c "Top Zero-Coverage Files" backend/tests/coverage_reports/PHASE_8_7_PLAN.md</verify>
  <done>PHASE_8_7_PLAN.md created with top 10-15 zero-coverage files inventory</done>
</task>

<task type="auto">
  <name>Task 2: Calculate coverage impact and targets</name>
  <files>backend/tests/coverage_reports/PHASE_8_7_PLAN.md</files>
  <action>
    Add coverage calculation section to PHASE_8_7_PLAN.md:

    **Coverage Impact Calculation:**
    - Current coverage: 15.87%
    - Target: 17-18% (+2-3 percentage points)
    - Total codebase lines: 112,125
    - Lines needed for +2%: 2,243 lines
    - Lines needed for +3%: 3,364 lines
    - At 50% average coverage per file: Need to test 4,500-6,700 lines of production code

    **File Selection Strategy:**
    - Priority 1: Core workflow files (highest ROI)
    - Priority 2: Governance services (critical path)
    - Priority 3: API routes (integration points)

    **Per-File Targets:**
    - For 200-line files: Target 100 lines covered (50%)
    - For 150-line files: Target 75 lines covered (50%)
    - Tests per file: ~30-40 tests for 200-line files

    Include table:
    | File | Lines | Target Coverage | Lines to Cover | Est. Tests |
    |------|-------|-----------------|----------------|------------|
  </action>
  <verify>grep -A 20 "Coverage Impact Calculation" backend/tests/coverage_reports/PHASE_8_7_PLAN.md</verify>
  <done>PHASE_8_7_PLAN.md contains coverage impact calculations with target lines and test estimates</done>
</task>

<task type="auto">
  <name>Task 3: Document testing strategy based on Phase 8.6 learnings</name>
  <files>backend/tests/coverage_reports/PHASE_8_7_PLAN.md</files>
  <action>
    Add testing strategy section to PHASE_8_7_PLAN.md:

    **Phase 8.6 Learnings Applied:**

    1. **High-Impact File Selection:**
       - Only files >150 lines (optimal ROI)
       - Prioritize workflow and governance (business-critical)
       - Group related files for efficient context switching

    2. **Test Structure (from Plan 15-18):**
       - Use pytest with fixtures for database models
       - Mock external services (LLM, WebSocket, HTTP clients)
       - Test both success and error paths
       - Include edge cases and boundary conditions

    3. **Coverage Targets:**
       - 50% average coverage per file (proven sustainable)
       - Stretch to 60% for critical governance files
       - Accept 40% for complex orchestration files

    4. **Execution Pattern:**
       - 4 plans, 3-4 files per plan
       - ~30-40 tests per file
       - 1.5-2 hours per plan execution

    **Test Template:**
    ```python
    # Test structure from Phase 8.6
    def test_{function}_success():
        # Arrange
        # Act
        # Assert

    def test_{function}_error():
        # Arrange error condition
        # Act & Assert exception

    def test_{function}_edge_case():
        # Boundary condition
    ```
  </action>
  <verify>grep -A 30 "Testing Strategy" backend/tests/coverage_reports/PHASE_8_7_PLAN.md</verify>
  <done>PHASE_8_7_PLAN.md contains documented testing strategy with Phase 8.6 learnings</done>
</task>

<task type="auto">
  <name>Task 4: Create plan-by-plan breakdown</name>
  <files>backend/tests/coverage_reports/PHASE_8_7_PLAN.md</files>
  <action>
    Add plan breakdown section to PHASE_8_7_PLAN.md:

    **Phase 8.7 Plan Breakdown (4 plans):**

    **Plan 23: Core Workflow Infrastructure**
    - Files: workflow_engine.py, workflow_scheduler.py, workflow_templates.py, workflow_executor.py
    - Total lines: ~850
    - Target coverage: 50% average (~425 lines)
    - Estimated tests: 120-150
    - Duration: 2-3 hours
    - Expected impact: +0.7-0.8% overall coverage

    **Plan 24: Workflow Orchestration**
    - Files: workflow_coordinator.py, workflow_parallel_executor.py, workflow_validation.py, workflow_retrieval.py
    - Total lines: ~700
    - Target coverage: 50% average (~350 lines)
    - Estimated tests: 100-120
    - Duration: 2 hours
    - Expected impact: +0.6-0.7% overall coverage

    **Plan 25: Agent Governance**
    - Files: agent_governance_service.py, agent_context_resolver.py, trigger_interceptor.py
    - Total lines: ~600
    - Target coverage: 60% average (~360 lines, higher for critical path)
    - Estimated tests: 100-120
    - Duration: 2 hours
    - Expected impact: +0.6-0.7% overall coverage

    **Plan 26: API Integration & Summary**
    - Files: Top 2 zero-coverage API routes + Phase 8.7 summary
    - Total lines: ~400
    - Target coverage: 50% average (~200 lines)
    - Estimated tests: 60-80
    - Duration: 1.5-2 hours
    - Expected impact: +0.3-0.4% overall coverage

    **Total Phase 8.7:**
    - Files: 15-16
    - Production lines: ~2,550
    - Lines to cover: ~1,335 (52.5% average)
    - Tests: 380-470
    - Overall impact: +2.2-2.6% coverage
    - Target coverage: 18.0-18.5%
  </action>
  <verify>grep -A 40 "Phase 8.7 Plan Breakdown" backend/tests/coverage_reports/PHASE_8_7_PLAN.md</verify>
  <done>PHASE_8_7_PLAN.md contains 4-plan breakdown with files, targets, and impact estimates</done>
</task>

</tasks>

<verification>
After completion:
1. PHASE_8_7_PLAN.md exists in backend/tests/coverage_reports/
2. File contains top 10-15 zero-coverage files inventory
3. Coverage calculations show +2-3% target is realistic
4. Testing strategy references Phase 8.6 learnings
5. Plan breakdown shows 4 plans with specific files and targets
</verification>

<success_criteria>
1. PHASE_8_7_PLAN.md created with 400+ lines
2. File inventory includes top zero-coverage files with line counts
3. Coverage impact calculation shows realistic +2-3% target
4. Testing strategy documented with Phase 8.6 learnings
5. 4-plan breakdown with specific files, tests, and impact estimates
</success_criteria>

<output>
After completion, create `.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-22-SUMMARY.md`
</output>
