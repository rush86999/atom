---
phase: 08-80-percent-coverage-push
plan: 13
type: execute
wave: 3
depends_on:
  - 08-80-percent-coverage-push-12
files_modified:
  - .github/workflows/test-coverage.yml
  - .gitignore
  - pytest.ini
  - pyproject.toml
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "CI/CD pipeline enforces coverage thresholds on every pull request"
    - "Coverage regression detection prevents merging if coverage drops"
    - "Coverage reports are generated and posted as PR comments"
    - "Coverage diff reports show new code coverage"
  artifacts:
    - path: ".github/workflows/test-coverage.yml"
      provides: "CI/CD workflow with coverage quality gates"
      contains: "coverage thresholds, regression detection, PR reporting"
    - path: "pyproject.toml"
      provides: "Coverage configuration with thresholds"
      contains: "[tool.coverage.run], [tool.coverage.report]"
  key_links:
    - from: ".github/workflows/test-coverage.yml"
      to: "pytest"
      via: "coverage run"
      pattern: "pytest --cov"
    - from: ".github/workflows/test-coverage.yml"
      to: "pull request"
      via: "github actions"
      pattern: "pull_request:"
---

<objective>
Implement CI/CD coverage quality gates to prevent coverage regression and enforce coverage thresholds. This addresses the "Coverage quality gates prevent regression in CI/CD" gap which failed during verification.

Purpose: Ensure coverage improvements are protected and future changes don't regress coverage. Automated gates provide immediate feedback on pull requests.

Output: CI/CD workflow with coverage thresholds, regression detection, and automated PR reporting.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-VERIFICATION.md
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-01-SUMMARY.md
@.github/workflows/test-coverage.yml

Gap context from VERIFICATION.md:
- "Coverage quality gates prevent regression in CI/CD" - status: failed
- "No CI/CD quality gates were implemented during Phase 8"
- "Coverage thresholds not configured"
- "No automated coverage regression detection"
- "No pull request coverage reporting"

Missing artifacts:
- "CI/CD pipeline configuration for coverage thresholds"
- "Coverage regression detection"
- "Automated coverage reporting on pull requests"
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create or enhance CI/CD workflow with coverage quality gates</name>
  <files>.github/workflows/test-coverage.yml</files>
  <action>
    Create or enhance .github/workflows/test-coverage.yml with coverage quality gates:

    1. Check if the file exists: cat .github/workflows/test-coverage.yml
    2. If it exists, read it and enhance with missing features
    3. If it doesn't exist, create it with the following structure:

    ```yaml
    name: Test Coverage

    on:
      push:
        branches: [main, develop]
      pull_request:
        branches: [main, develop]

    jobs:
      coverage:
        runs-on: ubuntu-latest
        timeout-minutes: 10

        steps:
        - uses: actions/checkout@v4
          with:
            fetch-depth: 0  # Full history for diff

        - name: Set up Python
          uses: actions/setup-python@v5
          with:
            python-version: '3.11'
            cache: 'pip'

        - name: Install dependencies
          run: |
            pip install -e backend/[test]
            pip install pytest-cov

        - name: Run tests with coverage
          run: |
            cd backend
            pytest tests/ -v \
              --cov=. \
              --cov-report=xml \
              --cov-report=html \
              --cov-report=term-missing \
              --cov-fail-under=25

        - name: Check coverage diff
          run: |
            pip install diff-cover
            diff-cover coverage.xml --compare-branch=origin/main --fail-under=5

        - name: Upload coverage reports
          uses: actions/upload-artifact@v4
          with:
            name: coverage-reports
            path: |
              backend/htmlcov/
              backend/coverage.xml

        - name: Report coverage to PR
          if: github.event_name == 'pull_request'
          uses: py-cov-action/python-coverage-comment-action@v3
          with:
            GITHUB_TOKEN: ${{ github.token }}
            MINIMUM_GREEN: 80
            MINIMUM_ORANGE: 60
```

    Key features to include:
    - Triggers on push and PR
    - Coverage threshold check (--cov-fail-under=25, gradually increase)
    - Coverage diff check (fail if PR drops coverage by >5%)
    - Upload coverage artifacts
    - PR comment with coverage report
    - Color-coded coverage (green 80%+, orange 60-79%, red <60%)
  </action>
  <verify>cat .github/workflows/test-coverage.yml | grep -E "cov-fail-under|diff-cover|coverage-comment"</verify>
  <done>CI/CD workflow exists with coverage thresholds, diff check, and PR reporting</done>
</task>

<task type="auto">
  <name>Task 2: Configure coverage thresholds in pyproject.toml or pytest.ini</name>
  <files>pyproject.toml pytest.ini</files>
  <action>
    Add or enhance coverage configuration in pyproject.toml or pytest.ini:

    1. Check which file exists: ls pyproject.toml pytest.ini
    2. If pyproject.toml exists, add/modify [tool.coverage.*] sections
    3. If pytest.ini exists, add/modify [coverage:*] sections

    Add configuration with:

    For pyproject.toml:
    ```toml
    [tool.coverage.run]
    source = ["backend"]
    omit = [
        "*/tests/*",
        "*/test_*.py",
        "*/__pycache__/*",
        "*/migrations/*",
        "*/venv/*",
        "*/virtualenv/*",
    ]
    branch = true

    [tool.coverage.report]
    precision = 2
    show_missing = true
    skip_covered = false
    exclude_lines = [
        "pragma: no cover",
        "def __repr__",
        "raise AssertionError",
        "raise NotImplementedError",
        "if __name__ == .__main__.:",
        "if TYPE_CHECKING:",
        "class .*\\bProtocol\\):",
        "@(abc\\.)?abstractmethod",
    ]

    [tool.coverage.html]
    directory = "htmlcov"

    [tool.coverage.xml]
    output = "coverage.xml"
    ```

    For pytest.ini:
    ```ini
    [coverage:run]
    source = backend
    omit =
        */tests/*
        */test_*.py
        */__pycache__/*
        */migrations/*

    [coverage:report]
    precision = 2
    show_missing = True
    exclude_lines =
        pragma: no cover
        def __repr__
        raise AssertionError
        raise NotImplementedError
        if __name__ == .__main__.:
        if TYPE_CHECKING:

    [coverage:html]
    directory = htmlcov

    [coverage:xml]
    output = coverage.xml
    ```

    Configure appropriate omission patterns for the project
  </action>
  <verify>grep -A 20 "\[tool.coverage\]" pyproject.toml 2>/dev/null || grep -A 20 "\[coverage:" pytest.ini 2>/dev/null</verify>
  <done>Coverage configuration exists with source, omit, and report settings</done>
</task>

<task type="auto">
  <name>Task 3: Add coverage trending configuration</name>
  <files>backend/tests/coverage_reports/.gitkeep backend/tests/coverage_reports/trending.json</files>
  <action>
    Set up coverage trending to track coverage over time:

    1. Create backend/tests/coverage_reports/trending.json with structure:
       ```json
       {
         "history": [],
         "baseline": {
           "date": "2026-02-12",
           "overall_coverage": 25.0,
           "core_coverage": 16.6,
           "api_coverage": 30.3,
           "tools_coverage": 7.6
         },
         "target": {
           "overall_coverage": 80.0,
           "date": "2026-02-28"
         }
       }
       ```

    2. Create a script backend/tests/scripts/update_coverage_trending.py:
       ```python
       #!/usr/bin/env python3
       """Update coverage trending data from coverage.json."""

       import json
       from datetime import datetime
       from pathlib import Path

       def update_trending():
           coverage_file = Path("tests/coverage_reports/metrics/coverage.json")
           trending_file = Path("tests/coverage_reports/trending.json")

           if not coverage_file.exists():
               print("No coverage.json found")
               return

           with open(coverage_file) as f:
               coverage_data = json.load(f)

           trending = {"history": [], "baseline": {}, "target": {
               "overall_coverage": 80.0,
               "date": "2026-02-28"
           }}

           if trending_file.exists():
               with open(trending_file) as f:
                   trending = json.load(f)

           # Add current snapshot
           trending["history"].append({
               "date": datetime.now().isoformat(),
               "overall_coverage": coverage_data.get("percent_covered", 0),
               "lines_covered": coverage_data.get("covered_lines", 0),
               "lines_total": coverage_data.get("num_statements", 0)
           })

           # Keep only last 30 entries
           trending["history"] = trending["history"][-30:]

           with open(trending_file, "w") as f:
               json.dump(trending, f, indent=2)

           print(f"Coverage trending updated: {coverage_data.get('percent_covered', 0)}%")

       if __name__ == "__main__":
           update_trending()
       ```

    3. Make the script executable: chmod +x backend/tests/scripts/update_coverage_trending.py
  </action>
  <verify>ls -la backend/tests/coverage_reports/trending.json backend/tests/scripts/update_coverage_trending.py</verify>
  <done>Coverage trending infrastructure created with JSON storage and update script</done>
</task>

</tasks>

<verification>
After all tasks complete:

1. Verify CI/CD workflow structure:
   ```bash
   cat .github/workflows/test-coverage.yml | grep -E "cov-fail-under|diff-cover|python-coverage-comment"
   ```

2. Verify coverage configuration:
   ```bash
   grep -A 20 "\[tool.coverage\]" pyproject.toml || grep -A 20 "\[coverage:" pytest.ini
   ```

3. Verify trending files exist:
   ```bash
   ls -la backend/tests/coverage_reports/trending.json
   ls -la backend/tests/scripts/update_coverage_trending.py
   ```

4. Test the coverage script:
   ```bash
   cd backend && python tests/scripts/update_coverage_trending.py
   cat tests/coverage_reports/trending.json
   ```

5. Verify workflow would catch coverage regression (manual check of logic):
   - cov-fail-under=25 (minimum threshold)
   - diff-cover --fail-under=5 (don't allow more than 5% drop)
   - PR comment coverage report enabled
</verification>

<success_criteria>
- .github/workflows/test-coverage.yml created/enhanced with quality gates
- Coverage threshold configured (cov-fail-under)
- Coverage diff check configured (diff-cover)
- PR coverage reporting enabled (python-coverage-comment-action)
- Coverage configuration in pyproject.toml or pytest.ini
- Coverage trending infrastructure created
- Update script for coverage trending exists
- All configurations follow project conventions
</success_criteria>

<output>
After completion, create `.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-13-SUMMARY.md`
</output>
