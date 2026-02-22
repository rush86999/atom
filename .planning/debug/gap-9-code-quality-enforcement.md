---
status: diagnosed
trigger: "Investigate Gap #9: Code Quality Enforcement"
created: 2026-02-21T10:00:00Z
updated: 2026-02-21T10:20:00Z
---

## Current Focus
hypothesis: Quality checks exist at 5 decision points but are advisory rather than enforced due to: (1) graceful degradation returns passed=True when tools unavailable, (2) quality gates don't block workflow progression, (3) no validation before commits, (4) no flaky test detection, (5) no type hint gate
test: Formed comprehensive hypothesis mapping all 5 enforcement gaps
expecting: To identify exact insertion points for quality gate validation
next_action: Document root cause and provide implementation recommendations

## Symptoms
expected: All AI-generated code must pass mypy, black, isort, flake8 checks before commits. Flaky tests auto-detected. Type hints required.
actual: Quality checks are advisory - commits proceed even when checks fail. No flaky test detection. No type hint enforcement.
errors: None (functional gap, not a bug)
reproduction: Run autonomous coding workflow with code that fails mypy/black - observe that commit still succeeds
started: Gap identified during Phase 62 verification (test coverage 80%)

## Eliminated

## Evidence
- timestamp: 2026-02-21T10:05:00Z
  checked: CodeQualityService.check_mypy() (line 64-148)
  found: Returns {"passed": True} when mypy not found (line 136) - graceful degradation bypasses enforcement
  implication: Quality checks pass even when tools are unavailable

- timestamp: 2026-02-21T10:06:00Z
  checked: CodeQualityService.enforce_all_quality_gates() (line 382-453)
  found: Returns quality_report with mypy_passed, black_formatted, isort_sorted, flake8_passed
  implication: Quality report is generated but calling code must enforce it

- timestamp: 2026-02-21T10:07:00Z
  checked: CommitterAgent.create_commit() (line 965-1026)
  found: No validation of quality_checks or test_results before creating commit (line 1009)
  implication: Commits proceed regardless of quality check failures

- timestamp: 2026-02-21T10:08:00Z
  checked: TestRunnerService.run_tests() (line 77-153)
  found: No flaky test detection or retry logic for intermittent failures
  implication: Flaky tests not identified or handled

- timestamp: 2026-02-21T10:09:00Z
  checked: AgentOrchestrator._run_fix_tests() (line 1174-1211)
  found: Orchestrator calls test_runner.fix_test_failures() but no quality gate validation
  implication: Workflow proceeds from code_generation to test_generation without quality checks

- timestamp: 2026-02-21T10:10:00Z
  checked: CodeGeneratorOrchestrator._generate_feature_code() (line 140-172)
  found: Calls _enforce_quality_gates() and stores quality_report in files array (line 163)
  implication: Quality checks run during code generation but failures don't block file creation

- timestamp: 2026-02-21T10:11:00Z
  checked: CodeGeneratorOrchestrator._enforce_quality_gates() (line 250-303)
  found: Returns "best effort" code after max_iterations even if quality gates don't pass (line 298-303)
  implication: Quality gates are advisory - code generation continues even with failures

- timestamp: 2026-02-21T10:12:00Z
  checked: CodeQualityService for type hint validation
  found: No AST-based type hint validation function exists (only validate_docstrings at line 563)
  implication: No dedicated type hint enforcement gate

- timestamp: 2026-02-21T10:13:00Z
  checked: TestRunnerService for flaky test detection
  found: No retry logic or flaky test detection in run_tests() or parse_pytest_output()
  implication: Flaky tests not identified or handled differently from real failures

## Resolution
root_cause: |
  Quality checks exist in CodeQualityService and are called by CodeGeneratorOrchestrator, but enforcement is bypassed at 5 critical points:

  1. **Graceful Degradation Bypass** (code_quality_service.py:136)
     - Returns passed=True when mypy/black/isort/flake8 tools not found
     - File: Line 136: return {"passed": True, ...} # Don't block if tool unavailable
     - Impact: Commits proceed even if quality tools unavailable

  2. **Best Effort Code Generation** (autonomous_coder_agent.py:298-303)
     - Returns code after max_iterations even if quality gates fail
     - File: Lines 298-303: "Max iterations reached, return best effort"
     - Impact: Files created with failing quality checks

  3. **No Commit Gate Validation** (autonomous_committer_agent.py:965-1026)
     - create_commit() doesn't validate quality_checks before committing
     - File: Line 1009: commit_sha = self.git_ops.create_commit(commit_message)
     - Missing: No if not quality_report["mypy_passed"]: raise QualityGateError
     - Impact: Low-quality code committed to repository

  4. **No Orchestrator Phase Gates** (autonomous_coding_orchestrator.py:1117-1146)
     - _run_generate_code() doesn't check quality results before phase transition
     - File: Line 1145: return {"phase": "generate_code", "artifacts": {...}}
     - Missing: No validation that quality_checks["passed"] == True
     - Impact: Workflow proceeds from code_generation to test_generation with failing checks

  5. **No Flaky Test Detection** (test_runner_service.py:77-153)
     - run_tests() has no retry logic or flaky detection
     - File: Line 77-153: Single test run, no re-runs for intermittent failures
     - Missing: No "rerun 3x, mark as flaky if passes intermittently" logic
     - Impact: Flaky tests waste auto-fix attempts on non-issues

  6. **No Type Hint Validation Gate** (code_quality_service.py:563-648)
     - validate_docstrings() exists but no validate_type_hints() function
     - File: AST parsing exists for docstrings but not for type hint coverage
     - Missing: No AST check for functions without type hints
     - Impact: Functions without type hints pass quality gates

fix: |
  Implement 6 enforcement fixes:

  1. **Add ENFORCE_QUALITY_GATES config** (backend/core/config.py or .env)
     - Environment variable: ENFORCE_QUALITY_GATES=true (default: false for backward compat)
     - Modify CodeQualityService to check flag before graceful degradation

  2. **Add quality gate validation in CodeGeneratorOrchestrator**
     - File: autonomous_coder_agent.py:298
     - Change: Raise QualityGateError if max_iterations reached and not passed
     - Add: Optional strict_mode parameter (default: false)

  3. **Add quality gate validation in CommitterAgent**
     - File: autonomous_committer_agent.py:1005 (before line 1009)
     - Add: Check all files have quality_checks["passed"] == True
     - Add: Block commit if ENFORCE_QUALITY_GATES=true and checks fail

  4. **Add quality gate validation in Orchestrator**
     - File: autonomous_coding_orchestrator.py:1144 (before return)
     - Add: Validate all files have quality_checks["passed"] == True
     - Add: Raise exception if ENFORCE_QUALITY_GATES=true and checks fail
     - Add: Block transition to GENERATE_TESTS phase

  5. **Implement flaky test detection**
     - File: test_runner_service.py (new method: detect_flaky_tests)
     - Add: Re-run failed tests 3x with delay
     - Add: Mark as flaky if passes intermittently
     - Add: Return flaky_tests list separate from hard failures

  6. **Add type hint validation gate**
     - File: code_quality_service.py (new method: validate_type_hints)
     - Add: AST parsing to find functions without type hints
     - Add: Check FunctionDef.returns, arg.annotation for all args
     - Add: Return {"has_type_hints": bool, "missing_hints": [str]}

verification: |
  Test with code that fails quality checks:
  1. Generate code without type hints
  2. Set ENFORCE_QUALITY_GATES=true
  3. Verify workflow blocks at code_generation phase
  4. Verify create_commit() raises QualityGateError
  5. Generate flaky test, verify detection
  6. Generate code with mypy errors, verify blocked commit

files_changed:
  - backend/core/code_quality_service.py (add validate_type_hints, check ENFORCE_QUALITY_GATES)
  - backend/core/autonomous_coder_agent.py (raise on failed quality gates)
  - backend/core/autonomous_committer_agent.py (validate quality_checks before commit)
  - backend/core/autonomous_coding_orchestrator.py (validate quality at phase transitions)
  - backend/core/test_runner_service.py (add detect_flaky_tests with retry logic)
