# Percy Visual Regression Testing

## Overview

Percy provides automated visual regression testing by capturing screenshots of critical pages and comparing them against baselines. This catches unintended UI changes before they reach production.

## Setup

### 1. Create Percy Account

1. Sign up at https://percy.io
2. Create a new project (e.g., "Atom Web App")
3. Copy your PERCY_TOKEN from project settings

### 2. Configure GitHub Actions Secret

1. Go to your GitHub repository settings
2. Navigate to Secrets and Variables → Actions
3. Add a new secret named `PERCY_TOKEN`
4. Paste the token from Percy dashboard

### 3. Run Baseline Capture

```bash
# Build frontend
cd frontend-nextjs
npm run build

# Start services
docker-compose -f docker-compose-e2e-ui.yml up -d

# Run Percy tests (first run establishes baseline)
npx percy exec -- pytest ../backend/tests/e2e_ui/tests/visual/ -v

# Cleanup
docker-compose -f docker-compose-e2e-ui.yml down
```

## How It Works

### Test Execution

1. **On Pull Request**: Percy captures screenshots of all test pages
2. **Comparison**: Screenshots are compared against baseline images
3. **Diff Detection**: Percy highlights any pixel differences
4. **Review**: Team reviews diffs in Percy dashboard

### Snapshot Configuration

See `.percyrc.js` for configuration:

- **Widths**: [1280, 768, 375] - Desktop, tablet, mobile
- **percyCSS**: Hides dynamic content (timestamps, loading states)
- **Discovery**: Waits for network idle before capturing

### Critical Pages Tested

1. **Dashboard** - Main navigation and overview
2. **Agent Chat** - Chat interface and message bubbles
3. **Canvas Sheets** - Data grid layout
4. **Canvas Charts** - Chart rendering and legends
5. **Canvas Forms** - Form field layout and validation states

## Reviewing Percy Results

### After Each PR

1. Check the Percy dashboard for visual diffs
2. Review each change carefully:
   - **Green check**: No changes (passing)
   - **Yellow diff**: Visual difference detected (needs review)
   - **Red X**: Failed snapshot (critical issue)

### Approving Changes

**Approve** if:
- Intentional design change (e.g., new feature, rebrand)
- Expected styling update (e.g., CSS refactor)
- False positive (dynamic content not hidden)

**Reject** if:
- Unintended layout break (e.g., misaligned elements)
- Broken component (e.g., missing icon, overflow)
- Regression from previous state (e.g., color shift)

### Reducing False Positives

If Percy detects false positives (dynamic content changes):

1. Add CSS selectors to `.percyrc.js`:
   ```javascript
   percyCSS: `
     .timestamp, .relative-time { display: none; }
     .loading-spinner { opacity: 0; }
     .user-avatar { content: 'static-avatar.png'; }
   `
   ```

2. Use `data-percy="skip"` attribute on elements to exclude:
   ```html
   <div class="weather-widget" data-percy="skip">...</div>
   ```

3. Narrow snapshot scope to specific elements:
   ```python
   # Instead of full page snapshot
   percy_snapshot(page, name="Widget", scope="#widget-container")
   ```

## Troubleshooting

### PERCY_TOKEN Not Found

**Error**: `Error: PERCY_TOKEN is required`

**Fix**: Add PERCY_TOKEN to GitHub Actions secrets (see Setup step 2)

### Baseline Not Found

**Error**: `No baseline found for snapshot`

**Fix**: First run establishes baseline. Run tests locally or merge PR to create baseline.

### Timeouts During Capture

**Error**: `Timeout waiting for network idle`

**Fix**: Adjust `.percyrc.js` discovery settings:
```javascript
discovery: {
  networkIdle: true,
  timeout: 60000  // Increase timeout to 60s
}
```

### Large Diff Files

**Error**: Percy diff exceeds size limit

**Fix**: Break large page into multiple snapshots:
```python
percy_snapshot(page, name="Header", scope=".header")
percy_snapshot(page, name="Main Content", scope=".main-content")
```

## Best Practices

1. **Snapshot Only Critical Pages** - Don't snapshot every page (limits + cost)
2. **Hide Dynamic Content** - Use percyCSS to exclude timestamps, weather widgets
3. **Review Diffs Promptly** - Review within 24h while context is fresh
4. **Document Decisions** - Comment in PR why diffs were approved/rejected
5. **Update Baselines** - When major redesign happens, approve all and set new baseline

## Running Locally

```bash
# Set PERCY_TOKEN environment variable
export PERCY_TOKEN=your_token_here

# Run tests with Percy
cd frontend-nextjs
npx percy exec -- pytest ../backend/tests/e2e_ui/tests/visual/ -v
```

## Resources

- Percy Documentation: https://docs.percy.io
- Percy CLI: https://github.com/percy/cli
- Percy Playwright: https://github.com/percy/percy-playwright
- Atom Project: https://github.com/your-org/atom

## Integration with CI

Visual regression tests run automatically on every pull request via `.github/workflows/visual-regression.yml`.

**Workflow Triggers**:
- Pull requests to main branch
- Manual trigger via workflow_dispatch

**Artifacts**:
- Percy results uploaded to Percy dashboard (not GitHub artifacts)
- Summary comment added to PR with review link

**Failure Conditions**:
- Workflow fails if Percy token missing
- Workflow succeeds even if diffs detected (human review required)
- Block merge if needed by adding required check in branch protection
