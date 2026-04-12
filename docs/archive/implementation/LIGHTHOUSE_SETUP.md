# Lighthouse CI Setup Guide

This guide explains how to set up and use Google Lighthouse for performance regression testing in Atom. Lighthouse is an automated tool for improving the quality of web pages, providing audits for performance, accessibility, progressive web apps, and more.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Local Development](#local-development)
4. [Performance Budgets](#performance-budgets)
5. [CI/CD Integration](#ci-cd-integration)
6. [Troubleshooting](#troubleshooting)
7. [Interpreting Results](#interpreting-results)

---

## Overview

### What is Lighthouse?

Google Lighthouse is an open-source, automated tool for improving the quality of web pages. It provides:

- **Performance Audits**: Measures metrics like First Contentful Paint (FCP), Largest Contentful Paint (LCP), Total Blocking Time (TBT), and Cumulative Layout Shift (CLS)
- **Accessibility Audits**: Checks for WCAG compliance and accessibility best practices
- **Best Practices**: Verifies modern web development standards (HTTPS, no mixed content, etc.)
- **SEO**: Analyzes meta tags, structured data, and mobile-friendliness

### Why Use Lighthouse CI?

Lighthouse CI integrates performance testing into your CI/CD pipeline to:

- **Catch Performance Regressions**: Detect significant slowdowns (>20% degradation) before they reach production
- **Enforce Performance Budgets**: Ensure all pages meet minimum performance thresholds
- **Automate Performance Monitoring**: Run tests on every PR and push to main
- **Provide Actionable Insights**: Get specific recommendations for optimization

### Integration with Atom

- **E2E Tests**: `test_performance_regression.py` runs Lighthouse via subprocess
- **GitHub Actions**: `.github/workflows/lighthouse-ci.yml` automates testing on PRs
- **Performance Budgets**: Configured thresholds for TTFB, FCP, LCP, TBT, CLS
- **Baseline Tracking**: JSON file stores baseline metrics for regression detection

---

## Prerequisites

### 1. Install Node.js (v18 or later)

Lighthouse CLI requires Node.js. Verify installation:

```bash
node --version  # Should be v18.x.x or later
```

If not installed, download from: https://nodejs.org/

### 2. Install Lighthouse CLI

Install Lighthouse globally via npm:

```bash
npm install -g lighthouse
```

Verify installation:

```bash
lighthouse --version
# Output: Lighthouse vX.X.X
```

### 3. Start Application Servers

Lighthouse needs running servers to test against.

**Backend Server (Port 8000):**
```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

**Frontend Server (Port 3001):**
```bash
cd frontend-nextjs
npm install
npm run build
npm start  # Runs on port 3001
```

**Verify Servers:**
```bash
curl http://localhost:8000/health/live  # Backend health check
curl http://localhost:3001              # Frontend homepage
```

---

## Local Development

### Run Lighthouse Manually

Run Lighthouse with HTML report:

```bash
lighthouse http://localhost:3001/dashboard --view
```

Run Lighthouse with JSON output:

```bash
lighthouse http://localhost:3001/dashboard \
  --output=json \
  --output-path=/tmp/lighthouse-report.json
```

Run Lighthouse with custom settings:

```bash
lighthouse http://localhost:3001/dashboard \
  --chrome-flags="--headless" \
  --quiet \
  --output=json \
  --output-path=/tmp/lighthouse-report.json
```

### Run Lighthouse E2E Tests

Run all Lighthouse tests:

```bash
cd backend
pytest tests/e2e_ui/tests/test_performance_regression.py -v -m lighthouse
```

Run specific test:

```bash
pytest tests/e2e_ui/tests/test_performance_regression.py::test_lighthouse_performance_scores -v
```

Run with verbose output:

```bash
pytest tests/e2e_ui/tests/test_performance_regression.py -v -s --tb=short
```

### Test Specific Pages

Test dashboard page:

```bash
lighthouse http://localhost:3001/dashboard \
  --output=json \
  --output-path=dashboard-report.json
```

Test agents page:

```bash
lighthouse http://localhost:3001/agents \
  --output=json \
  --output-path=agents-report.json
```

Test login page:

```bash
lighthouse http://localhost:3001/login \
  --output=json \
  --output-path=login-report.json
```

### View Lighthouse Reports

Open HTML report in browser:

```bash
lighthouse http://localhost:3001/dashboard --view
```

Or open JSON report in Lighthouse Viewer:

1. Go to: https://googlechrome.github.io/lighthouse/viewer/
2. Paste JSON report content
3. View interactive results

---

## Performance Budgets

### Budget Thresholds

| Metric | Budget | Description |
|--------|--------|-------------|
| **TTFB** | < 600ms | Time to First Byte - Server response time |
| **FCP** | < 1.5s | First Contentful Paint - First content rendered |
| **LCP** | < 2.5s | Largest Contentful Paint - Main content rendered |
| **TBT** | < 300ms | Total Blocking Time - Main thread blocking time |
| **CLS** | < 0.1 | Cumulative Layout Shift - Visual stability |

### Score Thresholds

| Category | Threshold | Description |
|----------|-----------|-------------|
| **Performance** | > 90 | Overall performance score (0-100) |
| **Accessibility** | > 90 | WCAG accessibility compliance |
| **Best Practices** | > 90 | Modern web standards compliance |
| **SEO** | > 80 | Search engine optimization |

### Adjust Budgets

Edit `.lighthouserc.json` to customize budgets:

```json
{
  "ci": {
    "assert": {
      "assertions": {
        "categories:performance": ["error", {"minScore": 0.9}],
        "categories:accessibility": ["error", {"minScore": 0.9}],
        "categories:best-practices": ["error", {"minScore": 0.9}],
        "categories:seo": ["warn", {"minScore": 0.8}]
      }
    }
  }
}
```

### Budget Severity Levels

- **error**: Fails the test (blocks PR merge)
- **warn**: Shows warning but doesn't fail
- **off**: Disabled assertion

Example: Relax SEO budget to warning only:

```json
"categories:seo": ["warn", {"minScore": 0.75}]
```

---

## CI/CD Integration

### GitHub Actions Workflow

The Lighthouse CI workflow (`.github/workflows/lighthouse-ci.yml`) runs on:

- **Pull Requests**: Tests changes before merge
- **Push to main**: Monitors production performance

### Workflow Steps

1. **Checkout repository**: Clone code
2. **Setup Node.js**: Install Node.js 18
3. **Install Lighthouse CLI**: `npm install -g lighthouse`
4. **Start servers**: Backend (port 8000) and frontend (port 3001)
5. **Run Lighthouse CI**: Test critical pages
6. **Comment on PR**: Post results as PR comment
7. **Upload artifacts**: Save reports for 7 days
8. **Stop servers**: Clean up background processes

### Critical Pages Tested

- `http://localhost:3001/` - Homepage
- `http://localhost:3001/dashboard` - Dashboard
- `http://localhost:3001/agents` - Agent list
- `http://localhost:3001/workflows` - Workflow list

### PR Comment Behavior

On pull requests, Lighthouse CI posts a comment with:

- **Performance scores**: Overall scores for each page
- **Budget status**: Pass/fail for each budget
- **Metrics breakdown**: TTFB, FCP, LCP, TBT, CLS values
- **Regression detection**: Comparison with baseline

Example comment:

```
## Lighthouse CI Results

| Page | Performance | Accessibility | Best Practices | SEO |
|------|-------------|---------------|----------------|-----|
| / | 95 | 100 | 100 | 85 |
| /dashboard | 92 | 98 | 100 | 82 |
| /agents | 88 | 95 | 95 | 80 |

All budgets passed! ✅
```

### Failing PR on Regression

If performance regresses by >20%, the PR comment shows:

```
## Performance Regression Detected ❌

| Metric | Current | Baseline | Change |
|--------|---------|----------|--------|
| FCP | 1800ms | 1500ms | +20% |
| LCP | 3200ms | 2500ms | +28% |

PR blocked: Fix performance issues before merging.
```

### CI/CD Configuration

Edit `.github/workflows/lighthouse-ci.yml` to customize:

```yaml
- name: Run Lighthouse CI
  uses: treosh/lighthouse-ci-action@v9
  with:
    urls: |
      http://localhost:3001/
      http://localhost:3001/dashboard
    uploadArtifacts: true
    temporaryPublicStorage: true
```

---

## Troubleshooting

### Common Issues

#### 1. Lighthouse Not Installed

**Error:** `lighthouse: command not found`

**Solution:**
```bash
npm install -g lighthouse
```

#### 2. Server Not Running

**Error:** `net::ERR_CONNECTION_REFUSED`

**Solution:**
```bash
# Start backend
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# Start frontend
cd frontend-nextjs
npm run build
npm start
```

#### 3. Port Already in Use

**Error:** `Address already in use`

**Solution:**
```bash
# Kill process using port 8000
lsof -ti:8000 | xargs kill -9

# Kill process using port 3001
lsof -ti:3001 | xargs kill -9
```

#### 4. Timeout Errors

**Error:** `Lighthouse timed out after 60 seconds`

**Solution:**
- Increase timeout in `test_performance_regression.py`:
  ```python
  timeout=120  # Increase from 60 to 120 seconds
  ```

- Check if server is responding slowly:
  ```bash
  curl -w "@-" -o /dev/null -s "http://localhost:3001/dashboard" <<EOF
  time_namelookup:  %{time_namelookup}\n
  time_connect:     %{time_connect}\n
  time_appconnect:  %{time_appconnect}\n
  time_pretransfer: %{time_pretransfer}\n
  time_starttransfer: %{time_starttransfer}\n
  time_total:       %{time_total}\n
  EOF
  ```

#### 5. False Positives

**Issue:** Test fails but actual performance is fine

**Causes:**
- Network congestion during test run
- Cold start (first load is slower)
- Background processes consuming resources

**Solutions:**
- Run test multiple times: `--numberOfRuns=3`
- Ignore outliers in results
- Warm up server before testing

#### 6. Baseline Missing

**Error:** `Baseline file not found`

**Solution:**
- Test automatically creates baseline on first run
- Or manually create baseline:
  ```bash
  # Run Lighthouse and save as baseline
  lighthouse http://localhost:3001/dashboard \
    --output=json \
    --output-path=baseline-dashboard.json
  ```

#### 7. Permissions Denied

**Error:** `EACCES: permission denied`

**Solution:**
```bash
# Install with sudo (if using system Node.js)
sudo npm install -g lighthouse

# Or fix npm permissions
mkdir ~/.npm-global
npm config set prefix '~/.npm-global'
export PATH=~/.npm-global/bin:$PATH
```

### Updating Baseline Metrics

If performance legitimately improves, update baseline:

```python
# Manually update baseline
baseline_path = "tests/data/lighthouse-baseline.json"
save_baseline(baseline_path, "dashboard", current_metrics)
```

Or delete baseline file and re-run test:

```bash
rm backend/tests/e2e_ui/tests/data/lighthouse-baseline.json
pytest tests/e2e_ui/tests/test_performance_regression.py::test_performance_regression_detection -v
```

---

## Interpreting Results

### Performance Scores (0-100)

| Score Range | Rating | Action |
|-------------|--------|--------|
| 90-100 | Good | No action needed |
| 50-89 | Needs Improvement | Consider optimization |
| 0-49 | Poor | Urgent optimization required |

### Core Web Vitals

#### LCP (Largest Contentful Paint)

- **Good**: < 2.5s
- **Needs Improvement**: 2.5s - 4s
- **Poor**: > 4s

**Optimization Tips:**
- Reduce server response time (TTFB)
- Optimize images and videos
- Remove render-blocking resources

#### TBT (Total Blocking Time)

- **Good**: < 300ms
- **Needs Improvement**: 300ms - 600ms
- **Poor**: > 600ms

**Optimization Tips:**
- Reduce JavaScript execution time
- Break up long tasks
- Use Web Workers for heavy computation

#### CLS (Cumulative Layout Shift)

- **Good**: < 0.1
- **Needs Improvement**: 0.1 - 0.25
- **Poor**: > 0.25

**Optimization Tips:**
- Reserve space for images and videos
- Avoid inserting content above existing content
- Use CSS transforms and animations

### Regression Thresholds

- **20% Degradation**: Fails test (blocks PR)
- **10% Improvement**: Updates baseline

Example:

```
FCP: 1500ms → 1800ms (+20%)  # FAIL - Regression detected
FCP: 1500ms → 1350ms (-10%)  # PASS - Baseline updated
```

### Example Lighthouse Report

```json
{
  "categories": {
    "performance": {"score": 0.92},
    "accessibility": {"score": 0.98},
    "best-practices": {"score": 1.0},
    "seo": {"score": 0.85}
  },
  "audits": {
    "time-to-first-byte": {"numericValue": 450},
    "first-contentful-paint": {"numericValue": 1200},
    "largest-contentful-paint": {"numericValue": 2100},
    "total-blocking-time": {"numericValue": 180},
    "cumulative-layout-shift": {"numericValue": 0.05}
  }
}
```

**Interpretation:**
- Performance: 92/100 (Good)
- Accessibility: 98/100 (Good)
- Best Practices: 100/100 (Excellent)
- SEO: 85/100 (Good)
- TTFB: 450ms (Good, <600ms budget)
- FCP: 1.2s (Good, <1.5s budget)
- LCP: 2.1s (Good, <2.5s budget)
- TBT: 180ms (Good, <300ms budget)
- CLS: 0.05 (Good, <0.1 budget)

---

## Additional Resources

- **Lighthouse Documentation**: https://github.com/GoogleChrome/lighthouse
- **Lighthouse CI Documentation**: https://github.com/GoogleChrome/lighthouse-ci
- **Core Web Vitals**: https://web.dev/vitals/
- **Performance Budgets**: https://web.dev/use-lighthouse-for-performance-budgets/

---

## Quick Reference

```bash
# Install Lighthouse
npm install -g lighthouse

# Run Lighthouse manually
lighthouse http://localhost:3001/dashboard --view

# Run E2E tests
pytest tests/e2e_ui/tests/test_performance_regression.py -v -m lighthouse

# Check Lighthouse version
lighthouse --version

# Verify servers
curl http://localhost:8000/health/live
curl http://localhost:3001
```

---

*Last Updated: 2026-03-24*
