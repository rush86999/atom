# Frontend Test Coverage Guide

## Overview

This guide covers frontend testing practices, coverage requirements, and CI/CD integration for the Atom platform.

**Current Coverage:** 1.41% (as of 2026-03-03)
**Target Coverage:** 80%+ per module

**Note:** The 89.84% coverage figure previously documented in ROADMAP.md referred to backend coverage, not frontend. This documentation error has been corrected in Phase 130.

## Coverage Requirements

### Module Thresholds

| Module | Threshold | Rationale |
|--------|-----------|-----------|
| Utility Libraries (`lib/**`) | 90% | Critical infrastructure, highly testable |
| React Hooks (`hooks/**`) | 85% | Testable with renderHook pattern |
| Canvas Components (`components/canvas/**`) | 85% | Maintain existing good coverage |
| UI Components (`components/ui/**`) | 80% | Standard component testing |
| Integration Components (`components/integrations/**`) | 80% | External dependencies, complex |
| Next.js Pages (`pages/**`) | 80% | Page-level testing |
| **Global Floor** | **80%** | Minimum for all code |

### Threshold Evolution

- **Phase 130-05 (2026-03-03):** Integrations threshold raised from 70% to 80% (graduated rollout complete)
- **Phase 130-05 (2026-03-03):** Global coverage floor raised from 75% to 80% lines

## Running Tests Locally

### Basic Commands

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Check module thresholds
npm run test:check-coverage

# Run CI mode (max 2 workers, no watch)
npm run test:ci
```

### Coverage Trend Tracking

```bash
# Update trend data (after running tests)
npm run coverage:trend:update

# View trend report
npm run coverage:trend:report

# Generate HTML visualization
npm run coverage:trend:html
```

### Coverage Analysis Scripts

```bash
# Generate per-module audit report
node scripts/coverage-audit.js

# Generate coverage gaps report
node scripts/coverage-gaps.js

# Check module thresholds with GitHub Actions annotations
node scripts/check-module-coverage.js --reporter=github-actions
```

## Testing Patterns

### Component Testing

Use React Testing Library for user-centric testing:

```typescript
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MyComponent } from './MyComponent';

describe('MyComponent', () => {
  it('handles user interaction', async () => {
    const user = userEvent.setup();
    render(<MyComponent />);

    const button = screen.getByRole('button', { name: /submit/i });
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByText(/success/i)).toBeInTheDocument();
    });
  });
});
```

### Integration Testing

Use MSW (Mock Service Worker) for API mocking:

```typescript
import { server } from '../../tests/mocks/handlers';
import { rest } from 'msw';

describe('API Integration', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('handles API response', async () => {
    server.use(
      rest.get('/api/data', (req, res, ctx) => {
        return res(ctx.json({ items: [] }));
      })
    );

    // Test component with mocked API
  });
});
```

**MSW Handler Organization:**
- Handlers organized by service (Jira, Slack, Microsoft365, etc.)
- Located in `tests/mocks/handlers.ts`
- Makes handler overrides easier for specific test scenarios

### Property-Based Testing

Use fast-check for invariant validation:

```typescript
import fc from 'fast-check';

describe('State Machine', () => {
  it('preserves state data during transitions', () => {
    fc.assert(
      fc.property(fc.record({ id: fc.string() }), (data) => {
        const result = stateMachine({ status: 'idle', data }, { type: 'START' });
        expect(result.data).toEqual(data);
      })
    );
  });
});
```

### Canvas Component Testing

Canvas components have established testing patterns (73% coverage - use as reference):

```typescript
import { render, screen } from '@testing-library/react';
import { CanvasGuidance } from './CanvasGuidance';

describe('CanvasGuidance', () => {
  it('displays operation steps', () => {
    const mockSteps = [
      { title: 'Step 1', status: 'complete', message: 'Done' }
    ];

    render(<CanvasGuidance steps={mockSteps} />);
    expect(screen.getByText('Step 1')).toBeInTheDocument();
  });
});
```

## CI/CD Integration

### GitHub Actions

Coverage checks run on:
- Pull requests to `main` or `develop`
- Pushes to `main` or `develop`
- Manual workflow dispatch

**Workflow:** `.github/workflows/frontend-tests.yml`

### PR Comments

Each PR receives a coverage comment with:
- Overall coverage percentage
- Module-level breakdown (passed/failed status)
- Files below threshold (with coverage %)
- Worst files per module (top 5)

**Comment Pattern:** Uses find/update pattern to avoid duplicates (searches for bot comments with '## Frontend Module Coverage Report')

### Artifact Retention

- Coverage artifacts: 30 days
- Coverage trend data: 90 days
- Test results: 7 days

### Coverage Trend Tracking

Coverage trends are tracked over time:
- Trend data stored in `coverage-trend.jsonl`
- HTML report available at `coverage/reports/trend.html`
- 90-day retention for trend artifacts
- Supports update, report, and html commands

**Integration Point:** Trend data uploaded as artifact on pushes to main branch

## Best Practices

### DO

- Test user behavior, not implementation details
- Use semantic queries (`getByRole`, `getByLabelText`)
- Wait for async operations with `waitFor`
- Mock external APIs with MSW
- Test error states and edge cases
- Test OAuth flows, data fetching, error handling (401, 429, network errors, timeouts)
- Test loading states and disconnection flows
- Use lean test strategy for large codebases (comprehensive on CRITICAL, basic on HIGH/MEDIUM)

### DON'T

- Don't test component state directly
- Don't use `querySelector` (use semantic queries)
- Don't ignore async operations
- Don't test implementation details (methods, internal state)
- Don't add tests without clear ROI (see Phase 130-03 test strategy)

## Troubleshooting

### Coverage Below Threshold

1. Run `npm run test:coverage` locally
2. Check `coverage/index.html` for detailed report
3. Identify uncovered lines in failing modules
4. Add tests for uncovered paths

### CI Failure

1. Check GitHub Actions logs for specific module failures
2. Run `npm run test:ci` locally with same Node version
3. Clear Jest cache: `npx jest --clearCache`
4. Verify coverage-summary.json generates correctly
5. Check GitHub Actions annotations for file-level warnings

### Flaky Tests

1. Increase waitFor timeout
2. Use `act()` wrapper for state updates
3. Ensure proper cleanup in `afterEach`
4. Mock timers if needed with `jest.useFakeTimers()`

### Module Threshold Errors

1. Run `npm run test:check-coverage` locally
2. Check which modules are below threshold
3. Review coverage gaps report: `node scripts/coverage-gaps.js`
4. Prioritize CRITICAL files first (see 130-02-GAPS.md for prioritization)

## Testing Infrastructure

### Test File Organization

```
frontend-nextjs/
├── components/
│   └── __tests__/
│       ├── canvas/
│       ├── integrations/
│       └── ui/
├── hooks/
│   └── __tests__/
├── lib/
│   └── __tests__/
├── pages/
│   └── __tests__/
└── tests/
    ├── mocks/
    │   └── handlers.ts
    └── setup.ts
```

### MSW API Handlers

30+ handlers organized by service:
- Jira (issues, projects, users)
- Slack (channels, messages, reactions)
- Microsoft365 (emails, calendar events)
- Google (calendar events, drive files)
- Asana (tasks, projects, teams)
- Notion (pages, databases, blocks)
- Zoom (meetings, recordings, webinars)

**Pattern:** Each service has dedicated handlers for OAuth flow, data fetching, error handling (401, 429, network errors, timeouts), loading states, and disconnection flows.

### Test Scripts

- `scripts/check-module-coverage.js` - Enforces per-module thresholds
- `scripts/coverage-audit.js` - Generates per-module audit report
- `scripts/coverage-gaps.js` - Identifies files below threshold
- `scripts/coverage-trend-tracker.js` - Tracks coverage trends over time

## Coverage Metrics History

### Baseline (Phase 130-01, 2026-03-03)

- **Overall Coverage:** 4.87% (documented error: ROADMAP claimed 89.84% for backend)
- **Files Analyzed:** 1,479 production files
- **Test Suites:** 124 existing tests
- **Modules Below Threshold:** All modules (as expected for baseline)

### Gap Analysis (Phase 130-02, 2026-03-03)

- **Files Below Threshold:** 613 files
- **CRITICAL Priority:** 603 files (core features)
- **HIGH Priority:** 6 files (integrations)
- **MEDIUM Priority:** 4 files (UI components)
- **Estimated Effort:** 1,201-2,403 test suites (100-150 days with 1 tester)

### Test Infrastructure (Phase 130-03, 2026-03-03)

- **Integration Test Suites:** 17 test suites created
- **MSW Handlers:** 30+ API handlers
- **Test Patterns:** OAuth flows, error handling, loading states, disconnection flows
- **Coverage Strategy:** Lean approach (comprehensive on CRITICAL, basic on HIGH/MEDIUM)

## Resources

- [Jest Documentation](https://jestjs.io/docs/getting-started)
- [React Testing Library](https://testing-library.com/react)
- [fast-check](https://github.com/dubzzc/fast-check)
- [MSW (Mock Service Worker)](https://mswjs.io/)
- [Phase 130 Research](.planning/phases/130-frontend-module-coverage-consistency/130-RESEARCH.md)
- [Phase 130 Gap Analysis](.planning/phases/130-frontend-module-coverage-consistency/130-02-GAPS.md)

## Related Documentation

- [Backend Coverage Guide](../../backend/tests/coverage_reports/README.md)
- [Testing Best Practices](../../backend/docs/CODE_QUALITY_STANDARDS.md#testing)
- [API Documentation](../../backend/docs/API_DOCUMENTATION.md)
