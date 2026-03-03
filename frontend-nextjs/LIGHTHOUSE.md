# Lighthouse CI Performance Testing

## Overview

Lighthouse CI automates performance audits on every pull request, catching performance regressions before they merge to production. It enforces performance budgets for key metrics (FCP, TTI, CLS, performance score) and tracks bundle size changes.

## Configuration

### Files

- **lighthouserc.json** - Lighthouse CI configuration with performance budgets
- **.lighthouserc.baseline.json** - Baseline metrics from staging/production
- **.bundlesize.json** - Bundle size budgets
- **next.config.js** - Bundle analyzer integration

### Performance Budgets

| Metric | Budget | Rationale |
|--------|--------|-----------|
| Performance Score | >90 (A grade) | Prevents slow pages |
| First Contentful Paint | <2s | Fast initial render |
| Time to Interactive | <5s | Quick interactivity |
| Cumulative Layout Shift | <0.1 | Prevents layout shifts |
| Total Blocking Time | <300ms | Responsive main thread |
| Total Bundle Size | <500 kB | Prevents bloat |
| Individual Chunk | <200 kB | Lazy loading targets |

## Running Locally

### 1. Start the Frontend

```bash
cd frontend-nextjs
npm run build
npm start
# Frontend available at http://localhost:3001
```

### 2. Run Lighthouse Audits

```bash
# Collect metrics (3 runs for accuracy)
npm run lighthouse:collect

# Assert against budgets
npm run lighthouse:assert

# Full CI flow (collect + assert)
npm run lighthouse:ci
```

### 3. View Results

```bash
# HTML report
open .lighthouseci/lhci-report.html

# JSON results
cat .lighthouseci/lhci-report.json
```

## Bundle Analysis

### Analyze Bundle Size

```bash
# Build with analyzer enabled
ANALYZE=true npm run build

# Opens browser with bundle visualization
# Shows:
# - Largest modules
# - Duplicate dependencies
# - Tree-shaking opportunities
```

### Reducing Bundle Size

1. **Code Splitting** - Use dynamic imports for heavy components
2. **Tree Shaking** - Ensure libraries export ES modules
3. **Remove Unused** - Audit dependencies with `npx depcheck`
4. **Compression** - Enable gzip/brotli on CDN
5. **Lazy Loading** - Route-based chunking with Next.js

### Interpreting Analyzer Results

**Colors**:
- Red: >100 KB ( prioritize optimization)
- Yellow: 50-100 KB (monitor)
- Green: <50 KB (good)

**Key Metrics**:
- **Initial Load** - Critical path JavaScript
- **Duplicate** - Same library in multiple chunks
- **Parser/Compiled** - Before/after minification

## CI/CD Integration

### GitHub Actions Workflow

`.github/workflows/lighthouse-ci.yml` runs on every PR and push to main.

**Workflow Steps**:
1. Build frontend (`npm run build`)
2. Start production server (`npm start`)
3. Collect Lighthouse metrics (`lhci collect`)
4. Assert against budgets (`lhci assert`)
5. Upload results as artifacts
6. Comment on PR with summary

### GitHub App Integration

**Optional**: Install Lighthouse CI GitHub App for PR comments:

1. Install app from GitHub Marketplace
2. Add `LHCI_GITHUB_APP_TOKEN` to repository secrets
3. Lighthouse automatically comments on PRs with:
   - Performance score changes
   - Budget failures
   - Comparison to baseline

### Failing Checks

**When Lighthouse Fails**:

1. **Budget Exceeded** - Metric above threshold (e.g., FCP = 2.5s, budget = 2s)
   - **Fix**: Optimize images, reduce JS, defer non-critical resources

2. **Score Dropped** - Performance score decreased by >5 points
   - **Fix**: Revert PR or optimize changes before merging

3. **Bundle Too Large** - JS bundle exceeds 500 KB
   - **Fix**: Code split, remove unused dependencies, enable compression

### Handling False Positives

If Lighthouse fails due to environment (CI slower than local):

1. **Adjust Budgets** - Update `lighthouserc.json` if baseline unrealistic
2. **Throttling** - CI uses desktop preset (4G throttling)
3. **Network Variance** - Lighthouse runs 3 times, uses median

## Establishing Baselines

### Initial Baseline

Run Lighthouse on staging/production to establish realistic baselines:

```bash
# 1. Deploy to staging
git push origin staging

# 2. Run Lighthouse (5 runs for accuracy)
npx lhci collect --numberOfRuns=5

# 3. Extract median values
cat .lighthouseci/lhci-report.json | jq '.[0].categories.performance.score'

# 4. Update baseline
# Edit .lighthouserc.baseline.json with actual values
```

### Updating Baselines

When performance improves (intentionally):

1. Update budgets in `lighthouserc.json`
2. Document rationale in commit message
3. Update `.lighthouserc.baseline.json`
4. Commit changes to git

### Example Baseline Entry

```json
{
  "baseline": {
    "performance": 0.92,
    "first-contentful-paint": 1850,
    "interactive": 4200,
    "cumulative-layout-shift": 0.05,
    "total-blocking-time": 250
  },
  "notes": "Baseline established 2026-02-27 from production. Budgets set at 10% above baseline."
}
```

## Troubleshooting

### Server Not Starting

**Error**: `ECONNREFUSED` during Lighthouse collect

**Fix**: Ensure server started and port 3001 accessible:
```bash
# Test manually
curl http://localhost:3001

# Increase timeout in lighthouserc.json
"collect": {
  "settings": {
    "maxWaitForLoad": 35000  // Default is 30000
  }
}
```

### Flaky Metrics

**Error**: Scores vary by >10 points between runs

**Fix**:
- Increase `numberOfRuns` to 5 (uses median)
- Use `--stable-timers` for consistent JS execution
- Run in CI with consistent resources (Ubuntu runner)

### Budget Too Strict

**Error**: All PRs failing on budget

**Fix**: Rebaseline from current production:
```bash
# Capture production metrics
npx lhci collect --url=https://atom.ai/dashboard

# Update budgets to 10% above production
# Edit lighthouserc.json assert section
```

### Bundle Analysis Not Working

**Error**: `ANALYZE=true npm run build` shows nothing

**Fix**:
1. Ensure `@next/bundle-analyzer` installed: `npm list @next/bundle-analyzer`
2. Check `next.config.js` has `withBundleAnalyzer` wrapper
3. Set `ANALYZE=true` environment variable (not `npm` config)

## Best Practices

1. **Test Realistic Scenarios** - Audit authenticated pages, not just landing
2. **Monitor Trends** - Track metrics over time, not just absolute values
3. **Prioritize Critical Path** - Optimize above-fold content first
4. **Budget for Growth** - Set budgets 10-20% above baseline
5. **Automate Reviews** - Enable GitHub App for PR comments
6. **Fix Regressions Promptly** - Don't merge failing PRs "just this once"
7. **Profile Before Optimizing** - Use Lighthouse timeline to find bottlenecks

## Resources

- Lighthouse CI Documentation: https://github.com/GoogleChrome/lighthouse-ci
- Next.js Bundle Analyzer: https://www.npmjs.com/package/@next/bundle-analyzer
- Web.dev Performance Guides: https://web.dev/performance/
- Lighthouse Scoring: https://web.dev/lighthouse-scoring/

## Integration with Percy

Lighthouse CI runs alongside Percy visual regression tests in CI:

- **Percy** - Catches visual regressions (layout shifts, broken UI)
- **Lighthouse** - Catches performance regressions (slow load, high CLS)
- **Combined** - Comprehensive quality assurance for every PR

Workflow:
1. Percy captures screenshots (visual correctness)
2. Lighthouse audits performance (speed + UX)
3. Both must pass before merge (branch protection)

## Example CI Output

```markdown
## Lighthouse CI Results

### Performance Metrics
| Metric | Budget | Actual | Status |
|--------|--------|--------|--------|
| Performance Score | >90 | 92 | :heavy_check_mark: |
| First Contentful Paint | <2s | 1.8s | :heavy_check_mark: |
| Time to Interactive | <5s | 4.2s | :heavy_check_mark: |
| Cumulative Layout Shift | <0.1 | 0.05 | :heavy_check_mark: |
| Total Blocking Time | <300ms | 250ms | :heavy_check_mark: |

### Bundle Size
| Chunk | Budget | Actual | Status |
|-------|--------|--------|--------|
| Total JS | <500 kB | 420 kB | :heavy_check_mark: |
| Main Chunk | <200 kB | 180 kB | :heavy_check_mark: |

### Artifacts
- Full Lighthouse report: lighthouse-results artifact
- Bundle analysis: Run `ANALYZE=true npm run build` locally
```
