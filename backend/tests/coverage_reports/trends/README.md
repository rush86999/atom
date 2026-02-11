# Coverage Trend Data

This directory stores historical coverage data for tracking coverage trends over time.

## Format

### coverage_trend.json

Aggregated trend data with domain-level coverage percentages.

```json
{
  "coverage_history": [
    {
      "date": "2026-02-11",
      "commit": "abc123",
      "overall_percent": 15.57,
      "governance_percent": 13.37,
      "security_percent": 22.40,
      "episodes_percent": 15.52,
      "test_count": 100
    }
  ],
  "targets": {
    "overall": 80,
    "governance": 80,
    "security": 80,
    "episodes": 80
  }
}
```

### Fields

- `date`: ISO date (YYYY-MM-DD) of coverage measurement
- `commit`: Git commit SHA (short or long)
- `overall_percent`: Overall backend coverage percentage
- `governance_percent`: Governance domain coverage percentage
- `security_percent`: Security domain coverage percentage
- `episodes_percent`: Episodic memory domain coverage percentage
- `test_count`: Total number of tests at time of measurement
- `targets`: Coverage percentage targets for each domain

### Dated Snapshots

Individual coverage snapshots: `YYYY-MM-DD_coverage.json`

Format: Standard pytest-cov JSON output (see metrics/coverage.json)

**Purpose**: Detailed coverage data for specific dates (file-by-file breakdown)

## Usage

### View Trend

```bash
# View entire trend
jq '.' coverage_trend.json

# View latest coverage
jq '.coverage_history[0]' coverage_trend.json

# Plot trend (requires gnuplot)
jq -r '.coverage_history[] | [.date, .overall_percent] | @tsv' coverage_trend.json \
  | gnuplot -p -e 'plot "/dev/stdin"'
```

### Detect Regression

```bash
# Compare latest with previous
LATEST=$(jq '.coverage_history[0].overall_percent' coverage_trend.json)
PREVIOUS=$(jq '.coverage_history[1].overall_percent' coverage_trend.json)

if (( $(echo "$LATEST < $PREVIOUS" | bc -l) )); then
    echo "Coverage regression: $PREVIOUS% → $LATEST%"
fi
```

### Calculate Progress to Target

```bash
# Calculate remaining coverage needed
TARGET=$(jq '.targets.overall' coverage_trend.json)
CURRENT=$(jq '.coverage_history[0].overall_percent' coverage_trend.json)
REMAINING=$(echo "$TARGET - $CURRENT" | bc)

echo "Current: $CURRENT%, Target: $TARGET%, Remaining: $REMAINING%"
```

## Update Process

### Manual Update

```bash
# Run tests with coverage
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=json

# Extract coverage metrics
OVERALL=$(jq '.totals.percent_covered' tests/coverage_reports/metrics/coverage.json)
DATE=$(date +%Y-%m-%d)
COMMIT=$(git rev-parse --short HEAD)

# Update coverage_trend.json
jq --arg date "$DATE" \
   --arg commit "$COMMIT" \
   --argjson overall "$OVERALL" \
   '.coverage_history += [{date: $date, commit: $commit, overall_percent: $overall}]' \
   tests/coverage_reports/trends/coverage_trend.json > tmp.json
mv tmp.json tests/coverage_reports/trends/coverage_trend.json
```

### CI/CD Update

GitHub Actions workflow (`.github/workflows/coverage-report.yml`) automatically updates this file:
- Runs on push to main and PR to main
- Extracts coverage metrics from coverage.json
- Appends new entry to coverage_history
- Commits updated file back to repository

## Interpretation

### Trend Direction

- **Increasing**: Coverage improving (good)
- **Flat**: Coverage stable (monitor)
- **Decreasing**: Coverage regressing (investigate)

### Target Progress

Calculate percentage of target achieved:

```bash
CURRENT=$(jq '.coverage_history[0].overall_percent' coverage_trend.json)
TARGET=$(jq '.targets.overall' coverage_trend.json)
PROGRESS=$(echo "scale=1; $CURRENT * 100 / $TARGET" | bc)

echo "Progress: $PROGRESS% of target"
```

### Domain Comparison

Compare coverage across domains:

```bash
jq '.coverage_history[0] | {
  governance: .governance_percent,
  security: .security_percent,
  episodes: .episodes_percent
}' coverage_trend.json
```

Identify domains needing attention (below target).

## Data Retention

- **coverage_trend.json**: Track indefinitely (Git history)
- **Dated snapshots**: Keep last 30 days (CI/CD cleanup)
- **Artifacts**: Keep last 30 runs (GitHub Actions retention)

## Privacy Note

Coverage reports may contain:
- File paths (internal structure, not sensitive)
- Line numbers (implementation details, not sensitive)
- Coverage percentages (aggregate metrics, safe to share)

**Do NOT commit**:
- Source code snippets from coverage reports
- Variable names or implementation details
- Any sensitive data in test fixtures

## See Also

- **[../COVERAGE_GUIDE.md](../../docs/COVERAGE_GUIDE.md)** - Coverage interpretation guide
- **[../metrics/coverage.json](../metrics/coverage.json)** - Current detailed coverage
- **[../html/index.html](../html/index.html)** - HTML coverage report

---

*Last Updated: 2026-02-11*
