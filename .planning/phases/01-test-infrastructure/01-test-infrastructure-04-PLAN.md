---
phase: 01-test-infrastructure
plan: 04
type: execute
wave: 2
depends_on: ["01-test-infrastructure-01"]
files_modified:
  - .github/workflows/ci.yml
  - backend/tests/README.md
autonomous: true

must_haves:
  truths:
    - "CI pipeline runs tests automatically on every push and PR with coverage enforcement"
    - "CI runs pytest with -n auto for parallel execution"
    - "CI enforces 80% coverage threshold"
    - "CI publishes coverage reports as artifacts"
  artifacts:
    - path: ".github/workflows/ci.yml"
      contains: "pytest"
      contains: "coverage"
    - path: "backend/tests/README.md"
      contains: "CI/CD"
      min_lines: 50
  key_links:
    - from: "push to main"
      to: "pytest -n auto"
      via: "GitHub Actions workflow"
      pattern: "on:\\s*push:"
    - from: "coverage.json"
      to: "PR comments"
      via: "Coverage artifact"
      pattern: "upload-artifact"
---

<objective>
Enhance GitHub Actions CI pipeline to run full test suite with parallel execution and coverage enforcement on every push and PR.

Purpose: Automate test execution and quality gate enforcement, preventing regression and ensuring coverage standards are maintained.
Output: Updated CI workflow with pytest -n auto, coverage reporting, and 80% threshold enforcement
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/01-test-infrastructure/01-RESEARCH.md
@.github/workflows/ci.yml
@backend/tests/TESTING_GUIDE.md
</context>

<tasks>

<task type="auto">
  <name>Add full test suite job to CI workflow</name>
  <files>.github/workflows/ci.yml</files>
  <action>
    Update .github/workflows/ci.yml to add a comprehensive test job:

    1. After the existing `backend-test` job, add a new `backend-test-full` job:

    ```yaml
  backend-test-full:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: atom_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - name: Free Disk Space (Ubuntu)
        run: |
          sudo rm -rf /usr/local/lib/android
          sudo rm -rf /opt/hostedtoolcache/CodeQL

      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Cache pip packages
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('backend/requirements*.txt') }}
          restore-keys: |
            ${{ runner.os }}-pip-

      - name: Install dependencies
        working-directory: ./backend
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r requirements-testing.txt

      - name: Run tests with coverage (parallel)
        working-directory: ./backend
        env:
          DATABASE_URL: "sqlite:///:memory:"
          BYOV_ENCRYPTION_KEY: test_key_for_ci_only
          ENVIRONMENT: test
          ATOM_DISABLE_LANCEDB: true
          ATOM_MOCK_DATABASE: true
        run: |
          pytest tests/ -v -n auto \
            --cov=core \
            --cov=api \
            --cov=tools \
            --cov-report=html:tests/coverage_reports/html \
            --cov-report=json:tests/coverage_reports/metrics/coverage.json \
            --cov-report=term-missing:skip-covered \
            --cov-fail-under=80 \
            --maxfail=5

      - name: Upload coverage reports
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: coverage-reports
          path: |
            backend/tests/coverage_reports/html/
            backend/tests/coverage_reports/metrics/coverage.json
          retention-days: 30

      - name: Coverage summary
        working-directory: ./backend
        if: always()
        run: |
          if [ -f tests/coverage_reports/metrics/coverage.json ]; then
            python -c "import json; d=json.load(open('tests/coverage_reports/metrics/coverage.json')); p=d['totals']['percent_covered']; print(f'Coverage: {p:.1f}%')"
          fi
    ```

    2. Add dependency so `docker-build` waits for tests:
       Update `needs: [backend-test, frontend-build]` to include `backend-test-full`

    DO NOT modify existing `backend-test` job (quick sanity check).
  </action>
  <verify>grep -A5 "backend-test-full:" .github/workflows/ci.yml</verify>
  <done>New backend-test-full job runs full test suite with parallel execution and coverage</done>
</task>

<task type="auto">
  <name>Create CI/CD integration documentation</name>
  <files>backend/tests/README.md</files>
  <action>
    Create comprehensive backend/tests/README.md:

    ```markdown
    # Atom Test Suite

    Comprehensive test suite for the Atom AI-powered business automation platform.

    Quick Start
    -----------

    Run all tests:
    \`\`\`bash
    cd backend
    pytest tests/ -v
    \`\`\`

    Run with coverage:
    \`\`\`bash
    pytest tests/ --cov=core --cov=api --cov=tools --cov-report=html
    open tests/coverage_reports/html/index.html
    \`\`\`

    Run in parallel:
    \`\`\`bash
    pytest tests/ -n auto
    \`\`\`

    Test Organization
    ------------------

    \`\`\`
    tests/
    ├── conftest.py                    # Root fixtures
    ├── factories/                     # Test data factories
    │   ├── __init__.py               # BaseFactory
    │   ├── agent_factory.py          # AgentRegistry
    │   ├── user_factory.py           # User
    │   ├── episode_factory.py        # Episode/EpisodeSegment
    │   ├── execution_factory.py      # AgentExecution
    │   └── canvas_factory.py         # CanvasAudit
    ├── property_tests/               # Hypothesis property tests
    ├── integration/                  # Integration tests
    ├── unit/                         # Isolated unit tests
    └── coverage_reports/             # Coverage reports
    \`\`\`

    Using Test Factories
    --------------------

    Factories provide dynamic, isolated test data:

    \`\`\`python
    from tests.factories import AgentFactory, UserFactory

    # Create an agent with dynamic data
    agent = AgentFactory.create(
        status="STUDENT",
        confidence=0.4
    )
    # agent.id is a unique UUID (not hardcoded)

    # Create a user
    user = UserFactory.create(
        role="member",
        status="active"
    )
    # user.email is unique (Faker-generated)
    \`\`\`

    Markers
    -------

    Tests are categorized by markers:

    \`\`\`bash
    pytest -m unit              # Unit tests only
    pytest -m integration       # Integration tests only
    pytest -m "not slow"        # Exclude slow tests
    pytest -m P0               # Critical priority tests
    \`\`\`

    CI/CD Integration
    -----------------

    GitHub Actions runs tests automatically:

    1. **Push to main/develop**: Full test suite with coverage
    2. **Pull Request**: Full test suite with coverage enforcement
    3. **Coverage Threshold**: 80% minimum (configurable)

    Coverage reports are uploaded as artifacts and retained for 30 days.

    Local Development
    -----------------

    For fast feedback during development:

    \`\`\`bash
    # Run only modified tests
    pytest tests/ -v --lf  # "last failed" - rerun failed tests

    # Run with pdb on failure
    pytest tests/ -v --pdb

    # Stop on first failure
    pytest tests/ -v -x

    # Run specific file
    pytest tests/property_tests/database/test_database_invariants.py -v
    \`\`\`

    Coverage Targets
    ----------------

    | Domain | Target | Priority |
    |--------|--------|----------|
    | Governance | 80% | P0 |
    | Security | 80% | P0 |
    | Episodes | 80% | P1 |
    | Core backend | 80% | P1 |

    See [TESTING_GUIDE.md](./TESTING_GUIDE.md) for comprehensive testing documentation.
    ```

    Ensure the file is at backend/tests/README.md (not in a subdirectory).
  </action>
  <verify>cat backend/tests/README.md | head -50</verify>
  <done>backend/tests/README.md exists with test suite documentation and CI/CD integration guide</done>
</task>

</tasks>

<verification>
1. Verify CI workflow YAML is valid: `yamllint .github/workflows/ci.yml` (if yamllint available)
2. Check that backend-test-full job has correct dependency ordering
3. Verify coverage artifact upload paths match actual directory structure
4. Confirm README is readable and covers all key topics
</verification>

<success_criteria>
- CI workflow includes backend-test-full job with parallel execution
- Coverage threshold of 80% is enforced in CI
- Coverage reports are uploaded as artifacts
- README.md documents CI/CD integration clearly
- All existing CI functionality is preserved
</success_criteria>

<output>
After completion, create `.planning/phases/01-test-infrastructure/01-test-infrastructure-04-SUMMARY.md`
</output>
