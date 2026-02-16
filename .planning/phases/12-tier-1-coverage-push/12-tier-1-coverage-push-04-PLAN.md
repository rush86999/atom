---
phase: 12-tier-1-coverage-push
plan: 04
type: execute
wave: 3
depends_on: ["12-tier-1-coverage-push-01", "12-tier-1-coverage-push-03"]
files_modified:
  - backend/tests/property_tests/debugger/test_workflow_debugger_invariants.py
  - backend/tests/coverage_reports/metrics/coverage.json
  - .planning/phases/12-tier-1-coverage-push/12-tier-1-coverage-push-04-SUMMARY.md
autonomous: true
gap_closure: false

must_haves:
  truths:
    - "workflow_debugger.py has 50% coverage (breakpoint and state inspection tested)"
    - "Phase 12 overall coverage target of 28% achieved (+5.2% from 22.8% baseline)"
    - "All 6 Tier 1 files tested at 50% coverage (sustainable target proven in Phase 8.6)"
    - "Property tests for debugger state machine and breakpoint logic"
  artifacts:
    - path: "backend/tests/property_tests/debugger/test_workflow_debugger_invariants.py"
      provides: "Property tests for workflow breakpoints, state inspection, and step execution"
      min_lines: 350
    - path: ".planning/phases/12-tier-1-coverage-push/12-tier-1-coverage-push-04-SUMMARY.md"
      provides: "Phase 12 completion summary with coverage metrics"
      min_lines: 200
  key_links:
    - from: "backend/tests/property_tests/debugger/test_workflow_debugger_invariants.py"
      to: "backend/core/workflow_debugger.py"
      via: "import WorkflowDebugger and test breakpoint management"
      pattern: "from core.workflow_debugger import WorkflowDebugger"
    - from: ".planning/phases/12-tier-1-coverage-push/12-tier-1-coverage-push-04-SUMMARY.md"
      to: ".planning/phases/13-tier-2-3-coverage-push"
      via: "recommend Tier 2-3 files for Phase 13"
      pattern: "priority_files_for_phase_13"
---

<objective>
Achieve 50% coverage on workflow_debugger.py (527 lines) using property tests for breakpoint management and state inspection, and complete Phase 12 Tier 1 coverage push with overall coverage target of 28% (+5.2 percentage points).

**Purpose:** Complete the Tier 1 file testing by covering workflow_debugger.py, which enables workflow debugging with breakpoints, state inspection, and step-by-step execution. This is the last remaining Tier 1 file from the Phase 11 analysis. Upon completion, validate that Phase 12 achieved its 28% overall coverage target.

**Output:** Property tests for breakpoint invariants, state management, and debugger controls. Phase 12 summary document with coverage metrics and Phase 13 recommendations.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@backend/tests/coverage_reports/metrics/priority_files_for_phases_12_13.json
@backend/tests/coverage_reports/metrics/PHASE_11_COVERAGE_ANALYSIS_REPORT.md
@backend/core/workflow_debugger.py
@backend/tests/property_tests/workflows/test_workflow_engine_invariants.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create property tests for workflow debugger breakpoint and state invariants</name>
  <files>backend/tests/property_tests/debugger/test_workflow_debugger_invariants.py</files>
  <action>
    Create backend/tests/property_tests/debugger/test_workflow_debugger_invariants.py with property tests for debugging functionality:

    **Target workflow_debugger.py (527 lines, 0% coverage) - test these invariants:**

    1. **Breakpoint Management Invariants** (using st.text for step IDs):
       ```python
       @given(
           step_id=st.text(min_size=1, max_size=50, alphabet='abc123_-'),
           is_enabled=st.booleans()
       )
       def test_breakpoint_creation(self, step_id, is_enabled):
           """INVARIANT: Breakpoint created with correct state."""
       debugger = WorkflowDebugger()
           debugger.set_breakpoint(step_id, enabled=is_enabled)
           assert debugger.has_breakpoint(step_id) == is_enabled

       @given(
           step_ids=st.lists(
               st.text(min_size=1, max_size=30, alphabet='abc123_'),
               min_size=1,
               max_size=10,
               unique=True
           )
       )
       def test_multiple_breakpoints(self, step_ids):
           """INVARIANT: Multiple breakpoints can be set."""
       debugger = WorkflowDebugger()
           for step_id in step_ids:
               debugger.set_breakpoint(step_id)
           assert debugger.breakpoint_count() == len(step_ids)

       @given(
           step_id=st.text(min_size=1, max_size=50, alphabet='abc123_-')
       )
       def test_breakpoint_removal(self, step_id):
           """INVARIANT: Breakpoint can be removed."""
       debugger = WorkflowDebugger()
           debugger.set_breakpoint(step_id)
           debugger.clear_breakpoint(step_id)
           assert not debugger.has_breakpoint(step_id)
       ```

    2. **State Inspection Invariants**:
       ```python
       @given(
           variables=st.dictionaries(
               st.text(min_size=1, max_size=20, alphabet='abc'),
               st.one_of(st.integers(), st.text(), st.booleans(), st.none()),
               min_size=0,
               max_size=10
           )
       )
       def test_state_capture(self, variables):
           """INVARIANT: State captures all variables."""
       debugger = WorkflowDebugger()
           state = debugger.capture_state(variables)
           assert len(state) == len(variables)
           for key, value in variables.items():
               assert state.get(key) == value

       @given(
           variables=st.dictionaries(
               st.text(min_size=1, max_size=20, alphabet='abc'),
               st.integers(min_value=0, max_value=1000),
               min_size=1,
               max_size=5
           ),
           key=st.text(min_size=1, max_size=20, alphabet='abc')
       )
       def test_state_variable_access(self, variables, key):
           """INVARIANT: State variables can be accessed."""
       debugger = WorkflowDebugger()
           state = debugger.capture_state(variables)
           if key in variables:
               assert debugger.get_variable(state, key) == variables[key]
           else:
               assert debugger.get_variable(state, key) is None
       ```

    3. **Step Execution Invariants**:
       ```python
       @given(
           current_step=st.integers(min_value=0, max_value=10),
           total_steps=st.integers(min_value=5, max_value=15)
       )
       def test_step_within_bounds(self, current_step, total_steps):
           """INVARIANT: Current step is within valid range."""
       debugger = WorkflowDebugger()
           if current_step < total_steps:
               debugger.set_current_step(current_step, total_steps)
               assert debugger.current_step == current_step
               assert debugger.total_steps == total_steps

       @given(
           step_mode=st.sampled_from(["step_over", "step_into", "step_out", "continue"])
       )
       def test_step_mode_setting(self, step_mode):
           """INVARIANT: Step mode is preserved."""
       debugger = WorkflowDebugger()
           debugger.set_step_mode(step_mode)
           assert debugger.step_mode == step_mode
       ```

    4. **Breakpoint Triggering Invariants**:
       ```python
       @given(
           execution_step=st.integers(min_value=0, max_value=10),
           breakpoint_steps=st.lists(
               st.integers(min_value=0, max_value=10),
               min_size=0,
               max_size=5,
               unique=True
           )
       )
       def test_breakpoint_triggers(self, execution_step, breakpoint_steps):
           """INVARIANT: Execution pauses at breakpoint steps."""
       debugger = WorkflowDebugger()
           for bp_step in breakpoint_steps:
               debugger.set_breakpoint(f"step_{bp_step}")
           should_pause = execution_step in breakpoint_steps
           assert debugger.should_pause(f"step_{execution_step}") == should_pause
       ```

    5. **State Snapshot Invariants**:
       ```python
       @given(
           snapshots=st.lists(
               st.integers(min_value=0, max_value=100),
               min_size=0,
               max_size=10
           )
       )
       def test_snapshot_sequence(self, snapshots):
           """INVARIANT: Snapshots are in chronological order."""
       debugger = WorkflowDebugger()
           for i, value in enumerate(snapshots):
               debugger.take_snapshot({"value": value, "index": i})
           saved_snapshots = debugger.get_snapshots()
           assert len(saved_snapshots) == len(snapshots)
           for i, snapshot in enumerate(saved_snapshots):
               assert snapshot["index"] == i

       @given(
           max_snapshots=st.integers(min_value=1, max_value=20),
           snapshot_count=st.integers(min_value=1, max_value=50)
       )
       def test_snapshot_limit(self, max_snapshots, snapshot_count):
           """INVARIANT: Snapshot count respects limit."""
       debugger = WorkflowDebugger(max_snapshots=max_snapshots)
           for i in range(snapshot_count):
               debugger.take_snapshot({"index": i})
           assert debugger.snapshot_count() <= max_snapshots
       ```

    6. **Variable Watch Invariants**:
       ```python
       @given(
           watch_variables=st.lists(
               st.text(min_size=1, max_size=20, alphabet='abc'),
               min_size=1,
               max_size=5,
               unique=True
           ),
           current_state=st.dictionaries(
               st.text(min_size=1, max_size=20, alphabet='abc'),
               st.integers(),
               min_size=0,
               max_size=10
           )
       )
       def test_watch_variables(self, watch_variables, current_state):
           """INVARIANT: Watch variables are tracked in state."""
       debugger = WorkflowDebugger()
           for var in watch_variables:
               debugger.add_watch(var)
           watched = debugger.get_watched_values(current_state)
           for var in watch_variables:
               if var in current_state:
                   assert var in watched
                   assert watched[var] == current_state[var]
       ```

    **Test structure:**
    ```python
    import pytest
    from hypothesis import given, strategies as st, settings
    from core.workflow_debugger import WorkflowDebugger

    class TestWorkflowDebuggerBreakpointInvariants:
        @pytest.fixture
        def debugger(self):
            return WorkflowDebugger()

        @given(step_id=st.text(min_size=1, max_size=30, alphabet='abc123_-'))
        @settings(max_examples=50)
        def test_breakpoint_id_is_valid(self, debugger, step_id):
            """INVARIANT: Breakpoint ID is stored correctly."""
            debugger.set_breakpoint(step_id)
            assert debugger.has_breakpoint(step_id)

    class TestWorkflowDebuggerStateInvariants:
        @pytest.fixture
        def debugger(self):
            return WorkflowDebugger()

        @given(variables=st.dictionaries(st.text(), st.integers(), min_size=0, max_size=10))
        @settings(max_examples=50)
        def test_state_preserves_values(self, debugger, variables):
            """INVARIANT: State preserves all variable values."""
            state = debugger.capture_state(variables)
            for key, value in variables.items():
                assert state.get(key) == value
    ```

    **Coverage target:** 50% of workflow_debugger.py (264 lines covered)

    **Use existing patterns from:**
    - backend/tests/property_tests/workflows/test_workflow_engine_invariants.py (for workflow testing patterns)
  </action>
  <verify>
    PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/property_tests/debugger/test_workflow_debugger_invariants.py -v --cov=backend/core/workflow_debugger --cov-report=term-missing | tail -30
    Expected: 50%+ coverage on workflow_debugger.py, all property tests pass
  </verify>
  <done>
    workflow_debugger.py coverage >= 50%, at least 10 property tests covering breakpoints, state inspection, and execution
  </done>
</task>

<task type="auto">
  <name>Task 2: Generate Phase 12 coverage summary and validate 28% overall target</name>
  <files>backend/tests/coverage_reports/metrics/coverage.json</files>
  <action>
    Run complete Phase 12 coverage analysis and validate 28% overall coverage target:

    1. Run coverage for all 6 Tier 1 files tested in Plans 01-04:
       ```bash
       PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest \
         backend/tests/unit/test_models_orm.py \
         backend/tests/property_tests/workflows/test_workflow_engine_state_invariants.py \
         backend/tests/integration/test_atom_agent_endpoints.py \
         backend/tests/property_tests/llm/test_byok_handler_invariants.py \
         backend/tests/property_tests/analytics/test_workflow_analytics_invariants.py \
         backend/tests/property_tests/debugger/test_workflow_debugger_invariants.py \
         --cov=backend/core/models \
         --cov=backend/core/workflow_engine \
         --cov=backend/core/atom_agent_endpoints \
         --cov=backend/core/llm/byok_handler \
         --cov=backend/core/workflow_analytics_engine \
         --cov=backend/core/workflow_debugger \
         --cov-report=json \
         --cov-report=term \
         -v
       ```

    2. Calculate Phase 12 coverage achievement:
       ```python
       import json
       with open('backend/tests/coverage_reports/metrics/coverage.json') as f:
           data = json.load(f)

       # Coverage for each Tier 1 file (target: 50% each)
       tier1_files = {
           "models.py": "backend/core/models.py",
           "workflow_engine.py": "backend/core/workflow_engine.py",
           "atom_agent_endpoints.py": "backend/core/atom_agent_endpoints.py",
           "byok_handler.py": "backend/core/llm/byok_handler.py",
           "workflow_analytics_engine.py": "backend/core/workflow_analytics_engine.py",
           "workflow_debugger.py": "backend/core/workflow_debugger.py"
       }

       total_covered = 0
       total_lines = 0
       for name, path in tier1_files.items():
           file_data = data['files'].get(path, {})
           summary = file_data.get('summary', {})
           covered = summary.get('covered_lines', 0)
           num_statements = summary.get('num_statements', 0)
           percent = summary.get('percent_covered', 0)
           print(f"{name}: {covered}/{num_statements} = {percent:.1f}%")
           total_covered += covered
           total_lines += num_statements

       overall_percent = (total_covered / total_lines * 100) if total_lines > 0 else 0
       print(f"\nTier 1 Overall: {total_covered}/{total_lines} = {overall_percent:.1f}%")
       print(f"Target: 50%, Achieved: {overall_percent:.1f}%")
       ```

    3. Validate Phase 12 goal of 28% overall coverage (+5.2% from 22.8% baseline):
       - Baseline: 22.8% (from Phase 11 completion)
       - Target: 28.0% (+5.2 percentage points)
       - Required lines: 5.2% of 25,768 total = 1,340 lines covered
       - Achieved lines from Tier 1 files at 50%:
         * models.py: 1,176 lines
         * workflow_engine.py: 582 lines
         * atom_agent_endpoints.py: 368 lines
         * byok_handler.py: 275 lines
         * workflow_analytics_engine.py: 297 lines
         * workflow_debugger.py: 264 lines
         * Total: 2,962 lines (exceeds 1,340 target)

    4. Generate Phase 12 summary:
       ```python
       phase12_summary = {
           "phase": "12-tier-1-coverage-push",
           "baseline_coverage": 22.8,
           "target_coverage": 28.0,
           "tier1_files_tested": 6,
           "coverage_per_file": {
               "models.py": {"target": 50, "achieved": 50, "lines": 1176},
               "workflow_engine.py": {"target": 50, "achieved": 50, "lines": 582},
               "atom_agent_endpoints.py": {"target": 50, "achieved": 50, "lines": 368},
               "byok_handler.py": {"target": 50, "achieved": 50, "lines": 275},
               "workflow_analytics_engine.py": {"target": 50, "achieved": 50, "lines": 297},
               "workflow_debugger.py": {"target": 50, "achieved": 50, "lines": 264}
           },
           "total_lines_covered": 2962,
           "estimated_overall_increase": 5.2,
           "estimated_final_coverage": 28.0,
           "plans_completed": 4,
           "tests_created": {
               "unit": 1,
               "integration": 1,
               "property": 4
           }
       }
       ```

    5. If target not met, identify gaps:
       - Check which files are below 50% coverage
       - Add targeted tests for uncovered branches
       - Re-run coverage to validate improvement
  </action>
  <verify>
    python3 -c "
    import json
    with open('backend/tests/coverage_reports/metrics/coverage.json') as f:
        data = json.load(f)
        tier1_files = ['backend/core/models.py', 'backend/core/workflow_engine.py',
                       'backend/core/atom_agent_endpoints.py', 'backend/core/llm/byok_handler.py',
                       'backend/core/workflow_analytics_engine.py', 'backend/core/workflow_debugger.py']
        total_covered = 0
        total_statements = 0
        for path in tier1_files:
            file_data = data['files'].get(path, {})
            summary = file_data.get('summary', {})
            covered = summary.get('covered_lines', 0)
            statements = summary.get('num_statements', 0)
            percent = summary.get('percent_covered', 0)
            print(f'{path.split(\"/\")[-1]}: {percent:.1f}%')
            total_covered += covered
            total_statements += statements
        overall = (total_covered / total_statements * 100) if total_statements > 0 else 0
        print(f'Tier 1 Overall: {overall:.1f}%')
        assert overall >= 50.0, f'Tier 1 coverage {overall:.1f}% < 50%'
    "
    Expected: All Tier 1 files at 50%+ coverage, overall Tier 1 >= 50%
  </verify>
  <done>
    All 6 Tier 1 files at 50%+ coverage, Phase 12 target of 28% overall coverage achieved, summary document generated
  </done>
</task>

<task type="auto">
  <name>Task 3: Create Phase 12 completion summary and Phase 13 recommendations</name>
  <files>.planning/phases/12-tier-1-coverage-push/12-tier-1-coverage-push-04-SUMMARY.md</files>
  <action>
    Create Phase 12 completion summary document with metrics and Phase 13 recommendations:

    **Document structure:**
    ```markdown
    # Phase 12: Tier 1 Coverage Push - Completion Summary

    ## Executive Summary

    Phase 12 achieved its target of 28% overall coverage (+5.2 percentage points from 22.8% baseline) by testing all 6 Tier 1 files (>500 lines, <20% coverage) to 50% coverage each.

    ## Coverage Achieved

    ### File-by-File Results

    | File | Lines | Baseline | Target | Achieved | Status |
    |------|-------|----------|--------|----------|--------|
    | models.py | 2,351 | 0% | 50% | XX% | ✓/✗ |
    | workflow_engine.py | 1,163 | 0% | 50% | XX% | ✓/✗ |
    | atom_agent_endpoints.py | 736 | 0% | 50% | XX% | ✓/✗ |
    | workflow_analytics_engine.py | 593 | 0% | 50% | XX% | ✓/✗ |
    | byok_handler.py | 549 | 0% | 50% | XX% | ✓/✗ |
    | workflow_debugger.py | 527 | 0% | 50% | XX% | ✓/✗ |

    ### Overall Impact

    - **Baseline Coverage:** 22.8%
    - **Target Coverage:** 28.0%
    - **Achieved Coverage:** XX%
    - **Percentage Point Increase:** +XX%
    - **Total Lines Covered:** X,XXX lines

    ## Tests Created

    ### Plan 01: Foundation (Models + Workflow Engine)
    - Unit tests for ORM relationships (test_models_orm.py)
    - Property tests for state machine (test_workflow_engine_state_invariants.py)

    ### Plan 02: Agent Endpoints
    - Integration tests for API contracts (test_atom_agent_endpoints.py)
    - WebSocket streaming tests

    ### Plan 03: LLM + Analytics
    - Property tests for provider routing (test_byok_handler_invariants.py)
    - Property tests for aggregation (test_workflow_analytics_invariants.py)

    ### Plan 04: Debugger + Summary
    - Property tests for debugging (test_workflow_debugger_invariants.py)
    - Phase 12 summary document

    ## Test Type Distribution

    - **Unit Tests:** X tests for ORM models
    - **Integration Tests:** X tests for API endpoints
    - **Property Tests:** X tests for stateful logic
    - **Total:** XX tests created

    ## Velocity Analysis

    - **Plans Completed:** 4
    - **Average Velocity:** +X.X% per plan
    - **Efficiency:** 3.38x acceleration (Tier 1 focus vs. unfocused testing)

    ## Phase 13 Recommendations

    Based on Phase 11 analysis, Phase 13 should target:

    ### Tier 2 Files (300-500 lines)
    - byok_endpoints.py (498 lines) - integration tests
    - lancedb_handler.py (494 lines) - property tests
    - auto_document_ingestion.py (479 lines) - unit tests
    - workflow_versioning_system.py (476 lines) - property tests

    ### Zero Coverage Quick Wins
    - 212 files with 0% coverage and >100 lines
    - Estimated potential: +7.0 percentage points

    ### Target
    - **Goal:** 35% overall coverage (+7.0 percentage points)
    - **Estimated Plans:** 5-6
    - **Estimated Velocity:** +1.2-1.4% per plan

    ## Lessons Learned

    1. **50% coverage target is sustainable** - Proven from Phase 8.6, avoids diminishing returns
    2. **Property tests for stateful logic** - More effective than unit tests for state machines
    3. **Integration tests for APIs** - Essential for endpoint contract validation
    4. **Tier-based prioritization** - 3.38x velocity acceleration by focusing on largest files

    ## Files for Next Phase

    See backend/tests/coverage_reports/metrics/priority_files_for_phases_12_13.json for Phase 13 file rankings.
    ```

    **Include Phase 13 file priorities:**
    - Load priority_files_for_phases_12_13.json
    - Extract Phase 13 files (ranks 1-30)
    - Group by test type (property, integration, unit)
    - Estimate coverage potential

    **Coverage validation:**
    - Re-run full test suite with coverage
    - Generate updated coverage.json
    - Calculate final Phase 12 metrics
    - Confirm 28% target achieved
  </action>
  <verify>
    cat .planning/phases/12-tier-1-coverage-push/12-tier-1-coverage-push-04-SUMMARY.md
    Expected: Summary document with all 6 file results, overall coverage metrics, and Phase 13 recommendations
  </verify>
  <done>
    Phase 12 summary document created with coverage metrics, test statistics, and Phase 13 recommendations
  </done>
</task>

</tasks>

<verification>
1. Run all Phase 12 tests: `pytest backend/tests/unit/test_models_orm.py backend/tests/property_tests/workflows/test_workflow_engine_state_invariants.py backend/tests/integration/test_atom_agent_endpoints.py backend/tests/property_tests/llm/test_byok_handler_invariants.py backend/tests/property_tests/analytics/test_workflow_analytics_invariants.py backend/tests/property_tests/debugger/test_workflow_debugger_invariants.py -v`
2. Check overall coverage: `pytest --cov=backend --cov-report=term | grep TOTAL`
3. Verify 28% overall coverage target achieved
4. Validate all 6 Tier 1 files at 50%+ coverage
5. Confirm Phase 12 summary document is complete
</verification>

<success_criteria>
- workflow_debugger.py coverage >= 50% (264 lines covered from 527 total)
- All 6 Tier 1 files at 50%+ coverage
- Overall coverage >= 28% (+5.2 percentage points from baseline)
- At least 10 property tests for debugger
- Phase 12 summary document completed
- Phase 13 recommendations documented
- No test failures or regressions
</success_criteria>

<output>
After completion, create `.planning/phases/12-tier-1-coverage-push/12-tier-1-coverage-push-04-SUMMARY.md` with:
- Coverage achieved for all 6 Tier 1 files
- Overall coverage percentage increase (baseline to final)
- Total tests created by type (unit, integration, property)
- Velocity analysis and efficiency metrics
- Phase 13 file priorities and recommendations
- Lessons learned and best practices
</output>
