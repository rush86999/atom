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

**Backend (Python):**
```bash
pytest --cov=core --cov-report=json
cat tests/coverage_reports/metrics/coverage.json
```

**Mobile (React Native):**
```bash
cd mobile
npm test -- --coverage
cat coverage/coverage-summary.json
```

**Desktop (Rust/Tauri):**
```bash
cd frontend-nextjs/src-tauri
./coverage.sh  # Uses cargo-tarpaulin (x86_64 only)
cat coverage/coverage.json
```

**Note:** Desktop coverage requires `cargo-tarpaulin` which only works on x86_64 architecture. For ARM Macs (M1/M2/M3), use the GitHub Actions workflow or run in CI/CD with an x86_64 runner.

## Coverage Targets

| Platform | Target | Current | File |
|----------|--------|---------|------|
| Backend (Python) | 80% | See HTML report | metrics/coverage.json |
| Mobile (React Native) | 80% | TBD | mobile/coverage/coverage-summary.json |
| Desktop (Rust/Tauri) | 80% | 74% | desktop_coverage.json |
| **Overall** | **80%** | **74%** | coverage_trend.json |

**Desktop Coverage Details:**
- main.rs: 75%
- commands: 70%
- menu: 85%
- websocket: 60%
- device_capabilities: 80%
- Test count: 108 passing tests

## Improving Coverage

1. Identify low-coverage files in HTML report
2. Add tests for uncovered paths
3. Re-run coverage report
4. Verify improvement

## Quality Gates

- Minimum 80% coverage enforced by `--cov-fail-under=80`
- PRs with <80% coverage will fail CI

## Coverage Aggregation

To aggregate coverage across all three platforms (backend, mobile, desktop):

```bash
cd backend/tests/coverage_reports
python aggregate_coverage.py
```

This creates `coverage_trend.json` with:
- Individual platform percentages
- Overall coverage (average of all three)
- Historical trend data
- Target compliance status

**Overall Coverage Formula:** `(backend + mobile + desktop) / 3`

## CI/CD Integration

- **Backend:** pytest-cov in GitHub Actions workflow
- **Mobile:** Jest coverage in GitHub Actions workflow
- **Desktop:** cargo-tarpaulin in `.github/workflows/desktop-coverage.yml`
- **Aggregation:** Automatic trend updates in CI/CD

See `.github/workflows/` for workflow details.
