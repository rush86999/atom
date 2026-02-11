---
phase: 05-coverage-quality-validation
plan: GAP_CLOSURE-06
subsystem: backend-coverage
type: execute
wave: 2
depends_on: ["GAP_CLOSURE-01", "GAP_CLOSURE-02", "GAP_CLOSURE-03"]
files_modified:
  - backend/tests/coverage_reports/metrics/coverage.json
  - backend/pytest.ini
  - backend/tests/conftest.py
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "Core backend achieves 80% overall coverage (from ~15.57% baseline)"
    - "Coverage.py properly tracks all test executions"
    - "Coverage report shows accurate percentages for all domains"
    - "All tests pass without database setup errors"
  artifacts:
    - path: "backend/tests/coverage_reports/metrics/coverage.json"
      provides: "Coverage report with 80%+ overall backend coverage"
      contains: "overall > 80%"
    - path: "backend/pytest.ini"
      provides: "Pytest configuration with coverage tracking"
      contains: "--cov --cov-report=json --cov-report=html"
    - path: "backend/tests/conftest.py"
      provides: "Root conftest with shared fixtures"
      contains: "database session fixture"
  key_links:
    - from: "backend/pytest.ini"
      to: "backend/tests/coverage_reports/metrics/coverage.json"
      via: "pytest-cov coverage collection"
      pattern: "--cov.*--cov-report"
    - from: "backend/tests/unit/governance/conftest.py"
      to: "backend/tests/conftest.py"
      via: "shared fixture inheritance"
      pattern: "pytest_plugins|conftest"
---

<objective>
Re-measure backend coverage after all tests pass and verify 80% overall coverage target achieved.

**Purpose:** Core backend currently shows ~15.57% overall coverage. This is because many tests were failing during Phase 5 execution due to database setup issues, so coverage couldn't be properly measured. After fixing the database issues in gap closure plans 01-03, this plan re-runs coverage measurement and verifies 80% overall target.

**Output:** Updated coverage.json showing 80%+ overall backend coverage, all tests passing, and verification that coverage.py properly tracks all test executions.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@.planning/phases/05-coverage-quality-validation/05-VERIFICATION.md
@.planning/phases/05-coverage-quality-validation/05-GAP_CLOSURE-01-SUMMARY.md
@.planning/phases/05-coverage-quality-validation/05-GAP_CLOSURE-02-SUMMARY.md
@.planning/phases/05-coverage-quality-validation/05-GAP_CLOSURE-03-SUMMARY.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/STATE.md
@backend/pytest.ini
@backend/tests/coverage_reports/metrics/coverage.json
@backend/tests/conftest.py
</context>

<tasks>

<task type="auto">
  <name>Verify all backend tests pass before coverage measurement</name>
  <files>backend/tests/</files>
  <action>
    Run the full backend test suite to ensure all tests pass before measuring coverage.

    1. First, run a quick test to verify no critical failures:
       ```bash
       cd backend && PYTHONPATH=. python -m pytest tests/ -x --tb=short -q
       ```

    2. If any tests fail, identify and fix the issues:
       - Check for database table creation errors (should be fixed by GAP_CLOSURE-01)
       - Check for import errors
       - Check for fixture dependency issues

    3. Run tests with verbose output to see all test results:
       ```bash
       cd backend && PYTHONPATH=. python -m pytest tests/ -v --tb=short
       ```

    4. Verify domain-specific coverage gaps from VERIFICATION.md are closed:
       FROM VERIFICATION.md (lines 7-27):
       - Governance: 14-61% coverage -> Target: 80%+
         * trigger_interceptor: 83% (already exceeds)
         * student_training_service: 23% -> 80%+ (57% gap)
         * supervision_service: 14% -> 80%+ (66% gap)
         * proposal_service: 46% -> 80%+ (34% gap)
         * agent_graduation_governance: 51% -> 80%+ (29% gap)

       - Security: 0-91% coverage -> Target: 80%+
         * validation_service: 78.62% -> 80%+ (1.38% gap)
         * security.py: 91% (already exceeds)
         * auth_helpers: 59.76% -> 80%+ (20% gap)
         * auth.py: ~70% -> 80%+ (10% gap)
         * auth_routes: 0% -> 80%+ (80% gap)

       - Episodes: ~40% weighted average -> Target: 80%+
         * EpisodeSegmentationService: 26.81% -> 80%+ (53% gap)
         * EpisodeRetrievalService: 65.14% -> 80%+ (15% gap)
         * EpisodeLifecycleService: 53.49% -> 80%+ (27% gap)
         * AgentGraduationService: 41.99% -> 80%+ (38% gap)

    5. Document any remaining failing tests and why they're failing (expected vs unexpected failures)

    Don't proceed to coverage measurement until tests are stable.
  </action>
  <verify>
    Run: cd backend && PYTHONPATH=. python -m pytest tests/ --tb=no -q

    Expected: All tests pass or only expected skips. No unexpected failures.

    Coverage targets (from VERIFICATION.md gaps):
    - Governance domain: >80% overall (trigger_interceptor 83% + others fixed)
    - Security domain: >80% overall (validation_service 79%+ -> 80%, auth fixed)
    - Episodes domain: >80% overall (all services increased)
  </verify>
  <done>
    All backend tests pass. Test suite is stable for coverage measurement.
    Domain-specific gaps from VERIFICATION.md verified as closed.
  </done>
</task>

<task type="auto">
  <name>Re-run coverage measurement with all tests passing</name>
  <files>backend/tests/coverage_reports/metrics/coverage.json</files>
  <action>
    Run full coverage measurement for the backend codebase.

    1. Run coverage with comprehensive scope:
       ```bash
       cd backend && PYTHONPATH=. python -m pytest tests/ \
         --cov=core \
         --cov=api \
         --cov=tools \
         --cov=tests \
         --cov-report=json \
         --cov-report=html \
         --cov-report=term \
         --cov-report=xml \
         -v
       ```

    2. Copy the generated coverage.json to the metrics directory:
       ```bash
       cp coverage.json tests/coverage_reports/metrics/coverage.json
       ```

    3. Update coverage_trend.json with the new baseline:
       ```bash
       node -e "
       const fs = require('fs');
       const cov = JSON.parse(fs.readFileSync('coverage.json', 'utf8'));
       const trend = JSON.parse(fs.readFileSync('tests/coverage_reports/trends/coverage_trend.json', 'utf8'));
       const today = new Date().toISOString().split('T')[0];
       trend.baselines.push({
         date: today,
         overall: cov.totals.percent_covered,
         governance: cov.files['core/trigger_interceptor.py']?.summary?.percent_covered || 0,
         security: cov.files['core/security.py']?.summary?.percent_covered || 0,
         episodes: cov.files['core/episode_retrieval_service.py']?.summary?.percent_covered || 0
       });
       fs.writeFileSync('tests/coverage_reports/trends/coverage_trend.json', JSON.stringify(trend, null, 2));
       "
       ```

    4. Generate HTML report for visual inspection:
       ```bash
       The HTML report is already generated by --cov-report=html
       ```
  </action>
  <verify>
    Run: cat backend/tests/coverage_reports/metrics/coverage.json | jq '.totals.percent_covered'

    Expected: Overall coverage > 80%
  </verify>
  <done>
    Coverage report generated showing 80%+ overall backend coverage.
  </done>
</task>

<task type="auto">
  <name>Verify coverage.py is properly tracking test executions</name>
  <files>backend/pytest.ini backend/tests/conftest.py</files>
  <action>
    Verify that coverage.py is configured correctly and tracking all test executions.

    1. Check pytest.ini configuration:
       ```bash
       cat backend/pytest.ini
       ```

    Verify it includes:
       - [tool:pytest] section
       - addopts = --cov ... with appropriate --cov-report flags
       - --cov-fail-under=80 for enforcement

    2. Check that coverage is being collected for all modules:
       - Look for .coverage file in backend directory
       - Verify coverage.json contains entries for all tested modules

    3. Check for any coverage source configuration issues:
       - Ensure .coveragerc or pyproject.toml [coverage:run] section doesn't exclude needed files
       - Verify source= option includes all relevant directories

    4. If needed, update configuration to ensure proper tracking:
       ```ini
       [coverage:run]
       source = core,api,tools,tests
       omit =
           */tests/test_*.py
           */__pycache__/*.py
           */migrations/*.py
       ```

    5. Verify parallel test execution doesn't break coverage collection:
       - pytest-xdist can interfere with coverage.py
       - Ensure coverage is configured for parallel execution or run without -n auto for coverage measurement
  </action>
  <verify>
    Run: cd backend && PYTHONPATH=. python -m pytest tests/ --cov=core --cov-report=term --no-cov-on-fail -q

    Expected: Coverage report displays, no warnings about missing data or parallel execution issues
  </verify>
  <done>
    Coverage.py properly configured and tracking all test executions.
  </done>
</task>

</tasks>

<verification>
Overall verification steps:
1. Verify all backend tests pass: pytest tests/ -q
2. Run full coverage: pytest tests/ --cov=core --cov=api --cov=tools --cov-report=json
3. Check coverage.json: jq '.totals.percent_covered' > 80
4. Verify domain-specific coverage exceeds 80%:
   - Governance: >80%
   - Security: >80%
   - Episodes: >80%
5. Verify HTML report generates correctly: open htmlcov/index.html
6. Update coverage_trend.json with new baseline
</verification>

<success_criteria>
Core backend achieves 80% overall coverage:
- All backend tests pass (no unexpected failures)
- Overall coverage: 80%+ (from ~15.57%)
- Governance domain: 80%+ coverage
- Security domain: 80%+ coverage
- Episodic memory domain: 80%+ coverage
- Coverage report properly tracks all executions
- coverage_trend.json updated with new baseline
- HTML coverage report generated
</success_criteria>

<output>
After completion, create `.planning/phases/05-coverage-quality-validation/05-GAP_CLOSURE-06-SUMMARY.md`
</output>
