---
phase: 212-80pct-coverage-clean-slate
plan: WAVE2B
type: execute
wave: 2
depends_on: ["212-WAVE1A", "212-WAVE1B"]
files_modified:
  - backend/tests/test_skill_adapter.py
  - backend/tests/test_skill_composition_engine.py
  - backend/tests/test_skill_dynamic_loader.py
autonomous: true

must_haves:
  truths:
    - "skill_adapter.py achieves 80%+ line coverage"
    - "skill_composition_engine.py achieves 80%+ line coverage"
    - "skill_dynamic_loader.py achieves 80%+ line coverage"
  artifacts:
    - path: "backend/tests/test_skill_adapter.py"
      provides: "Unit tests for SkillAdapter"
      min_lines: 400
      exports: ["TestSkillAdapter", "TestSkillExecution"]
    - path: "backend/tests/test_skill_composition_engine.py"
      provides: "Unit tests for SkillCompositionEngine"
      min_lines: 350
      exports: ["TestSkillComposition", "TestDAGValidation"]
    - path: "backend/tests/test_skill_dynamic_loader.py"
      provides: "Unit tests for SkillDynamicLoader"
      min_lines: 300
      exports: ["TestSkillLoading", "TestHotReload"]
  key_links:
    - from: "backend/tests/test_skill_adapter.py"
      to: "backend/core/skill_adapter.py"
      via: "Direct imports and mocking"
    - from: "backend/tests/test_skill_composition_engine.py"
      to: "backend/core/skill_composition_engine.py"
      via: "Direct imports and mocking"
    - from: "backend/tests/test_skill_dynamic_loader.py"
      to: "backend/core/skill_dynamic_loader.py"
      via: "Direct imports and mocking"
---

<objective>
Increase backend coverage from 25% to 40% by testing skill system services (adapter, composition, loader).

Purpose: Skill system enables agents to use community skills and compose workflows. These are core to agent extensibility. High coverage ensures reliable skill loading and execution.

Output: 3 test files with 1,050+ total lines, achieving backend 40%+ coverage.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/216-fix-business-facts-test-failures/216-PATTERN-DOC.md
@backend/core/skill_adapter.py
@backend/core/skill_composition_engine.py
@backend/core/skill_dynamic_loader.py

# Test Pattern Reference
From Phase 216: Use AsyncMock for async methods, patch services at import location, mock database sessions with SessionLocal fixtures.

# Target Files Analysis

## 1. skill_adapter.py (~400 lines)
Key methods:
- load_skill(): Load OpenClaw/ClawHub skill
- validate_skill(): Validate SKILL.md
- execute_skill(): Execute skill function
- sandbox_execution(): Hazard sandbox
- parse_skill_metadata(): Extract metadata

## 2. skill_composition_engine.py (~350 lines)
Key methods:
- create_dag(): Create workflow DAG
- validate_dag(): Detect cycles
- execute_dag(): Execute workflow
- resolve_dependencies(): Resolve skill dependencies
- parallel_execution(): Execute independent skills

NetworkX-based DAG validation

## 3. skill_dynamic_loader.py (~300 lines)
Key methods:
- hot_reload(): Watch for file changes
- load_skill_module(): Dynamic importlib loading
- unload_skill(): Unload skill module
- list_loaded_skills(): List active skills

Watchdog file monitoring
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create tests for skill_adapter</name>
  <files>backend/tests/test_skill_adapter.py</files>
  <action>
Create backend/tests/test_skill_adapter.py with comprehensive tests:

1. Imports: pytest, AsyncMock, from core.skill_adapter import SkillAdapter

2. Fixtures:
   - mock_adapter(): Returns SkillAdapter
   - mock_skill_metadata(): Returns test SKILL.md parsed data

3. Class TestSkillLoading:
   - test_load_skill_success(): Loads valid skill
   - test_load_skill_invalid_path(): Handles invalid path
   - test_load_skill_missing_metadata(): Handles missing SKILL.md
   - test_load_skill_parse_error(): Handles parse errors

4. Class TestSkillValidation:
   - test_validate_skill_valid(): Validates valid skill
   - test_validate_skill_missing_name(): Requires name
   - test_validate_skill_missing_description(): Requires description
   - test_validate_skill_missing_python(): Requires Python for backend skills

5. Class TestSkillExecution:
   - test_execute_skill_success(): Executes skill function
   - test_execute_skill_with_args(): Passes arguments
   - test_execute_skill_handles_error(): Handles skill errors
   - test_execute_skill_timeout(): Handles timeout

6. Class TestSandboxExecution:
   - test_sandbox_python(): Sandboxes Python execution
   - test_sandbox_network_disabled(): Network disabled in sandbox
   - test_sandbox_resource_limits(): Enforces resource limits
   - test_sandbox_readonly_fs(): Read-only filesystem

7. Class TestSecurityValidation:
   - test_detect_typosquatting(): Detects typosquat packages
   - test_detect_dependency_confusion(): Detects dependency confusion
   - test_scan_vulnerabilities(): Scans with pip-audit
   - test_block_unsafe_skills(): Blocks unsafe skills

8. Mock file system, subprocess, pip-audit
  </action>
  <verify>
pytest backend/tests/test_skill_adapter.py -v
pytest backend/tests/test_skill_adapter.py --cov=core.skill_adapter --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All skill_adapter tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 2: Create tests for skill_composition_engine</name>
  <files>backend/tests/test_skill_composition_engine.py</files>
  <action>
Create backend/tests/test_skill_composition_engine.py with comprehensive tests:

1. Imports: pytest, from core.skill_composition_engine import SkillCompositionEngine

2. Fixtures:
   - mock_engine(): Returns SkillCompositionEngine
   - mock_dag(): Returns NetworkX DAG

3. Class TestDAGCreation:
   - test_create_simple_dag(): Creates simple workflow
   - test_create_parallel_dag(): Creates parallel branches
   - test_create_sequential_dag(): Creates sequential flow
   - test_create_conditional_dag(): Creates conditional branches

4. Class TestDAGValidation:
   - test_validate_valid_dag(): Passes valid DAG
   - test_detect_cycle(): Detects circular dependency
   - test_detect_orphan(): Detects orphan nodes
   - test_validate_missing_dependencies(): Detects missing deps

5. Class TestDAGExecution:
   - test_execute_sequential(): Executes sequentially
   - test_execute_parallel(): Executes in parallel
   - test_execute_with_failure(): Continues on failure
   - test_execute_timeout(): Handles timeout

6. Class TestDependencyResolution:
   - test_resolve_dependencies(): Resolves skill deps
   - test_detect_version_conflict(): Detects version conflicts
   - test_detect_cycle_dependencies(): Detects cycles
   - test_install_missing_deps(): Installs missing deps

7. Use NetworkX for DAG operations
  </action>
  <verify>
pytest backend/tests/test_skill_composition_engine.py -v
pytest backend/tests/test_skill_composition_engine.py --cov=core.skill_composition_engine --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All skill_composition_engine tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 3: Create tests for skill_dynamic_loader</name>
  <files>backend/tests/test_skill_dynamic_loader.py</files>
  <action>
Create backend/tests/test_skill_dynamic_loader.py with comprehensive tests:

1. Imports: pytest, from core.skill_dynamic_loader import SkillDynamicLoader

2. Fixtures:
   - mock_loader(): Returns SkillDynamicLoader
   - mock_skill_module(): Returns test skill module

3. Class TestSkillLoading:
   - test_load_skill_module(): Loads skill with importlib
   - test_load_skill_reload(): Reloads existing skill
   - test_load_skill_import_error(): Handles import errors
   - test_load_skill_syntax_error(): Handles syntax errors

4. Class TestSkillUnloading:
   - test_unload_skill(): Unloads skill module
   - test_unload_nonexistent(): Handles nonexistent skill
   - test_unload_cleanup(): Cleans up resources

5. Class TestHotReload:
   - test_watch_file_changes(): Uses watchdog to watch files
   - test_reload_on_change(): Reloads on file change
   - test_reload_debounce(): Debounces rapid changes
   - test_reload_preserves_state(): Preserves state during reload

6. Class TestSkillListing:
   - test_list_loaded_skills(): Lists all loaded skills
   - test_list_skills_by_category(): Groups by category
   - test_list_skill_metadata(): Returns metadata

7. Mock importlib, watchdog, file system
  </action>
  <verify>
pytest backend/tests/test_skill_dynamic_loader.py -v
pytest backend/tests/test_skill_dynamic_loader.py --cov=core.skill_dynamic_loader --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All skill_dynamic_loader tests passing, 80%+ coverage achieved
  </done>
</task>

</tasks>

<verification>
After completing all tasks:

1. Run all tests:
   pytest backend/tests/test_skill_adapter.py \
          backend/tests/test_skill_composition_engine.py \
          backend/tests/test_skill_dynamic_loader.py -v

2. Verify coverage per module (all should be 80%+):
   pytest backend/tests/ --cov=core.skill_adapter \
                         --cov=core.skill_composition_engine \
                         --cov=core.skill_dynamic_loader \
                         --cov-report=term-missing

3. Verify overall backend coverage increase:
   pytest backend/tests/ --cov=core --cov-report=json
   # Backend should be 40%+ (from 25% baseline)

4. Verify no regression in existing tests:
   pytest backend/tests/ -v
</verification>

<success_criteria>
1. All 3 test files pass (100% pass rate)
2. Each of 3 modules achieves 80%+ coverage
3. Backend overall coverage >= 40%
4. No regression in existing test coverage
5. All tests execute in <30 seconds
</success_criteria>

<output>
After completion, create `.planning/phases/212-80pct-coverage-clean-slate/212-WAVE2B-SUMMARY.md`
</output>
