# Coverage Reports

This directory contains code coverage reports for the Atom platform.

## HTML Report

Open `html/index.html` in a web browser for interactive coverage visualization:

```bash
open backend/tests/coverage_reports/html/index.html
```

Features:
- Click files to see line-by-line coverage
- Red lines = not covered, Green lines = covered
- Yellow lines = partially covered (branch conditions)

## Terminal Report

Run tests with terminal coverage:

```bash
pytest --cov=core --cov-report=term-missing
```

Legend:
- `85%` = Line coverage percentage
- `25` = Number of missing lines

## JSON Report

Machine-readable metrics for CI/CD:

```bash
pytest --cov=core --cov-report=json
cat tests/coverage_reports/metrics/coverage.json
```

## Coverage Targets

| Module | Target | Current |
|--------|--------|---------|
| Governance | 80% | TBD |
| Security | 80% | TBD |
| Episodes | 80% | TBD |
| Core | 80% | TBD |

## Improving Coverage

1. Identify low-coverage files in HTML report
2. Add tests for uncovered paths
3. Re-run coverage report
4. Verify improvement

## Quality Gates

- Minimum 80% coverage enforced by `--cov-fail-under=80`
- PRs with <80% coverage will fail CI
