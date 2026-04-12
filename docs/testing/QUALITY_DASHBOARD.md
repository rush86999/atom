# Quality Metrics Dashboard

**Last Updated:** 2026-04-12
**Data Source:** `tests/coverage_reports/metrics/quality_metrics.json`

---

## Executive Summary

| Metric | Backend | Frontend | Target | Status |
|--------|---------|----------|--------|--------|
| **Coverage** | 4.60% | 14.12% | 80% | ⚠️ / ⚠️ |
| **Lines Covered** | 5,070 | 3,838 | - | - |
| **Total Lines** | 89,320 | 26,273 | - | - |
| **Gap to Target** | 75.40% | 65.88% | 0% | - |
| **Test Pass Rate** | 100% | 100% | 100% | ✅ |
| **Trend** | → 0.00% | → 0.00% | - | - |

---

## Coverage Trends

### Backend Coverage

- **Latest:** 4.60%
- **Target:** 80%
- **Baseline:** 4.60% (Phase 251)
- **Gap:** 75.40%

**Trend:** → 0.00%

### Frontend Coverage

- **Latest:** 14.12%
- **Target:** 80%
- **Baseline:** 14.12% (Phase 254)
- **Gap:** 65.88%

**Trend:** → 0.00%

---

## Historical Data

| Date | Backend Cov | Frontend Cov | Pass Rate | Notes |
|------|-------------|--------------|-----------|-------|
| 2026-04-12 | 4.60% | 14.12% | 100% | Baseline established |

---

## Coverage by Component

### Backend Components

| Component | Coverage | Lines | Status |
|-----------|----------|-------|--------|
| core/ | 4.60% | 5,070/89,320 | ⚠️ |
| api/ | TBD | TBD | ⚠️ |
| tools/ | TBD | TBD | ⚠️ |

### Frontend Components

| Component | Coverage | Lines | Status |
|-----------|----------|-------|--------|
| src/components/ | TBD | TBD | ⚠️ |
| src/services/ | TBD | TBD | ⚠️ |
| src/lib/ | TBD | TBD | ⚠️ |

---

## Test Statistics

| Metric | Backend | Frontend |
|--------|---------|----------|
| **Total Tests** | TBD | TBD |
| **Unit Tests** | TBD | TBD |
| **Integration Tests** | TBD | TBD |
| **E2E Tests** | TBD | TBD |
| **Property Tests** | TBD | - |

---

## Quality Gates

| Gate | Status | Details |
|------|--------|---------|
| **Coverage Threshold (70%)** | ❌ Fail | Backend: 4.60%, Frontend: 14.12% |
| **Test Pass Rate (100%)** | ✅ Pass | All tests passing |
| **Build Success** | ✅ Pass | Latest build: success |

---

## Recommendations

### Immediate Actions

1. **Backend coverage is 4.60% (below target)**
   - Action: Add tests for core business logic
   - Priority: High
   - Estimated Impact: +10-20%

2. **Frontend coverage is 14.12% (below target)**
   - Action: Add tests for components and services
   - Priority: High
   - Estimated Impact: +10-15%

### Medium-Term Goals

1. **Reach 70% coverage** (Phase 2 target)
   - Current: 4.60% (backend), 14.12% (frontend)
   - Gap: 65.40% (backend), 55.88% (frontend)
   - Estimated effort: 4-6 weeks

2. **Reach 80% coverage** (Final target)
   - Current: 4.60% (backend), 14.12% (frontend)
   - Gap: 75.40% (backend), 65.88% (frontend)
   - Estimated effort: 6-8 weeks

---

## How to Update This Dashboard

This dashboard is automatically updated by the Quality Metrics workflow (`.github/workflows/quality-metrics.yml`).

**Manual Update:**
```bash
# Run tests and collect metrics
cd backend
python3 -m pytest --cov=core --cov=api --cov=tools --cov-report=json:tests/coverage_reports/metrics/coverage_latest.json -q

# Calculate quality metrics
python3 .github/scripts/calculate-quality-metrics.py

# Update dashboard (regenerate from metrics)
python3 .github/scripts/generate-dashboard.py
```

**Scheduled Updates:**
- Automatic: Daily at 00:00 UTC
- On Push: Every commit to main branch
- On PR: Every pull request

---

## Data Sources

- **Metrics Data:** `tests/coverage_reports/metrics/quality_metrics.json`
- **Backend Coverage:** `tests/coverage_reports/metrics/coverage_latest.json`
- **Frontend Coverage:** `frontend-nextjs/coverage/coverage-summary.json`
- **Historical Data:** Embedded in `quality_metrics.json`

---

## Export Options

### JSON Export
```bash
cat backend/tests/coverage_reports/metrics/quality_metrics.json
```

### CSV Export
```bash
python3 .github/scripts/export-metrics-csv.py > quality_metrics.csv
```

### PDF Export
```bash
pandoc backend/docs/QUALITY_DASHBOARD.md -o quality_dashboard.pdf
```

---

**Dashboard Version:** 1.0
**Automation:** GitHub Actions
**Retention:** 90 days
