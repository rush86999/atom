# Phase 130: Frontend Module Coverage Consistency - Research

**Researched:** 2026-03-03
**Domain:** Frontend Testing, Jest Coverage, React Testing Library
**Confidence:** HIGH

## Summary

Phase 130 aims to achieve consistent 80%+ test coverage across all frontend modules in the Atom codebase. Current baseline shows 4.87% overall coverage (severe gap from claimed 89.84% in ROADMAP), with most integration components at 0% coverage. The frontend uses Jest 30.0.5 with React Testing Library, supporting per-module coverage reporting through Istanbul's built-in reporters.

**Primary recommendation:** Use Jest's native coverage reporters with directory-specific thresholds and develop a Node.js script for per-module aggregation and gap analysis. Leverage existing CI/CD infrastructure (frontend-tests.yml, coverage-report.yml, quality-gates.yml) for enforcement and trending.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **Jest** | 30.0.5 | Test runner, coverage collection | Industry standard for React testing, built-in Istanbul coverage, zero-config |
| **@testing-library/react** | 16.3.0 | Component testing | Official React testing approach, user-centric queries, maintained by core team |
| **@testing-library/jest-dom** | 6.6.3 | Custom DOM matchers | Enhances Jest with semantic assertions (toBeInTheDocument, etc.) |
| **@testing-library/user-event** | 14.6.1 | User interaction simulation | Realistic user input simulation (clicking, typing), replaces fireEvent |
| **Istanbul** | (bundled with Jest) | Coverage instrumentation | Jest's default coverage engine, supports 8+ reporter formats |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **fast-check** | 4.5.3 | Property-based testing | Already in use (Phase 108), continue for invariant validation |
| **msw** | 1.3.5 | API mocking | Already configured for integration tests (tests/mocks/handlers.ts) |
| **ts-jest** | 29.4.0 | TypeScript support | TypeScript compilation in Jest, already configured |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **Vitest** | Jest + Vitest migration | Vitest faster but ecosystem less mature, Jest 30 is production-ready with meaningful improvements |
| **istanbul-merge** | Native Jest aggregation | External tool adds complexity, Jest's json-summary sufficient for programmatic access |
| **codecov** | Custom GitHub Actions | Codecov external dependency, existing coverage-report.yml provides trending already |

**Installation:**
```bash
# All dependencies already installed
npm install --save-dev jest @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

## Architecture Patterns

### Recommended Project Structure
```
frontend-nextjs/
├── components/           # Component modules (36 subdirs, 34 root files)
│   ├── __tests__/       # Component tests co-located
│   ├── canvas/          # Canvas components (20+ tests, already good coverage)
│   ├── integrations/    # Integration components (mostly 0% coverage - GAP)
│   ├── Agents/          # Agent-related components
│   └── [module dirs]/   # Other feature modules
├── hooks/               # Custom React hooks
│   └── __tests__/       # Hook tests (useCanvasState tested)
├── lib/                 # Utility functions
│   └── __tests__/       # Utility tests
├── pages/               # Next.js pages (API routes tested)
├── tests/               # Integration and property tests
│   ├── integration/     # Cross-component integration tests
│   ├── property/        # FastCheck property tests
│   └── mocks/           # MSW handlers for API mocking
├── coverage/            # Jest coverage output (gitignored)
│   ├── coverage-final.json      # Full Istanbul coverage data
│   ├── coverage-summary.json    # Aggregated summary (programmatic access)
│   └── lcov-report/            # HTML interactive report
└── jest.config.js       # Jest configuration
```

### Pattern 1: Per-Module Coverage Reporting with JSON Summary
**What:** Generate machine-readable coverage reports with module-level breakdown using Jest's built-in reporters.

**When to use:** CI/CD pipelines, coverage trend tracking, gap analysis automation.

**Example:**
```javascript
// Source: jest.nodejs.cn/docs/configuration/
module.exports = {
  coverageReporters: ['json', 'json-summary', 'text', 'lcov'],
  coverageDirectory: 'coverage',
  collectCoverageFrom: [
    'components/**/*.{ts,tsx}',
    'pages/**/*.{ts,tsx}',
    'lib/**/*.{ts,tsx}',
    'hooks/**/*.{ts,tsx}',
    '!**/*.d.ts',
    '!**/node_modules/**',
    '!**/.next/**',
  ],
};
```

**Programmatic access:**
```javascript
// Parse coverage-summary.json for module-level metrics
const coverage = require('./coverage/coverage-summary.json');

// Get per-module coverage
for (const [filepath, metrics] of Object.entries(coverage)) {
  if (filepath !== 'total') {
    console.log(`${filepath}: ${metrics.lines.pct}% lines covered`);
  }
}
```

### Pattern 2: Directory-Specific Coverage Thresholds
**What:** Enforce different coverage requirements for different module categories using glob patterns in `coverageThreshold`.

**When to use:** Quality gates, critical module enforcement, graduated rollout strategy.

**Example:**
```javascript
// Source: jest.nodejs.cn/docs/configuration/
module.exports = {
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 75,
    },
    // Higher threshold for utilities (critical infrastructure)
    './lib/**/*.{ts,tsx}': {
      branches: 90,
      functions: 90,
      lines: 90,
      statements: 90,
    },
    // Lower threshold for integration components (complex, external deps)
    './components/integrations/**/*.{ts,tsx}': {
      branches: 70,
      functions: 70,
      lines: 70,
      statements: 70,
    },
    // Canvas components (already good coverage, maintain)
    './components/canvas/**/*.{ts,tsx}': {
      branches: 85,
      functions: 85,
      lines: 85,
      statements: 85,
    },
  },
};
```

### Pattern 3: Coverage Gap Analysis Script
**What:** Node.js script to identify modules below threshold and prioritize testing efforts.

**When to use:** Pre-PR checks, coverage triage, sprint planning input.

**Example:**
```javascript
#!/usr/bin/env node
/**
 * Identify modules below 80% coverage threshold
 * Usage: node scripts/coverage-gaps.js
 */
const fs = require('fs');
const coverage = JSON.parse(fs.readFileSync('coverage/coverage-summary.json', 'utf8'));

const THRESHOLD = 80;
const gaps = [];

for (const [filepath, metrics] of Object.entries(coverage)) {
  if (filepath === 'total') continue;

  const linePct = metrics.lines.pct;
  if (linePct < THRESHOLD) {
    gaps.push({
      file: filepath.replace(process.cwd(), ''),
      coverage: linePct,
      uncovered: metrics.lines.total - metrics.lines.covered,
      priority: linePct < 50 ? 'CRITICAL' : linePct < 70 ? 'HIGH' : 'MEDIUM'
    });
  }
}

// Sort by coverage ascending (worst first)
gaps.sort((a, b) => a.coverage - b.coverage);

console.log(`\n=== COVERAGE GAPS (${gaps.length} modules < ${THRESHOLD}%) ===\n`);
gaps.forEach(gap => {
  console.log(`${gap.priority} | ${gap.coverage}% | ${gap.uncovered} uncovered | ${gap.file}`);
});
```

### Pattern 4: Component Testing with React Testing Library
**What:** Test user behavior and interactions, not implementation details.

**When to use:** All component testing, integration testing, user flow validation.

**Example:**
```javascript
// Source: React Testing Library best practices
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

describe('Integration Component', () => {
  it('handles OAuth flow correctly', async () => {
    render(<JiraOAuthFlow />);

    // User action
    const connectButton = screen.getByRole('button', { name: /connect to jira/i });
    await userEvent.click(connectButton);

    // Verify outcome
    await waitFor(() => {
      expect(screen.getByText(/authorization successful/i)).toBeInTheDocument();
    });
  });
});
```

### Anti-Patterns to Avoid

- **Testing implementation details:** Don't test state, methods, or internal logic. Test user-observable behavior.
  ```javascript
  // BAD
  expect(component.state.isLoading).toBe(false);

  // GOOD
  expect(screen.queryByTestId('spinner')).not.toBeInTheDocument();
  ```

- **Coverage for coverage's sake:** Don't write meaningless tests to hit 80%. Focus on critical paths and edge cases.

- **Ignoring test reliability:** Flaky tests undermine coverage goals. Use proper waitFor, cleanup, and mock isolation.

- **Monolithic test files:** Organize tests by feature/user story, not by file structure. Use `describe` blocks for clarity.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Coverage collection | Custom instrumentation | Jest built-in `--coverage` flag | Istanbul handles edge cases, branch detection, source maps |
| Coverage aggregation | Custom JSON parsing | `coverage-summary.json` reporter | Jest generates aggregated metrics, no manual calculation |
| HTML reports | Custom HTML generation | `lcov` reporter + `lcov-reporter` action | Interactive drill-down, highlighted uncovered lines |
| Test discovery | Custom file finder | Jest `testMatch` glob patterns | Jest handles watch mode, selective runs, incremental compilation |
| Mock generation | Manual mock writing | MSW (Mock Service Worker) | Already configured (tests/mocks/handlers.ts), network-level mocking |
| Coverage trending | Custom database | GitHub Actions artifacts + existing `coverage-report.yml` | Backend trend tracker pattern proven, 90-day retention |

**Key insight:** Jest 30 + Istanbul provide production-ready coverage infrastructure. Custom scripts should only aggregate/analyze existing data, not replace collection mechanisms.

## Common Pitfalls

### Pitfall 1: Coverage Inflation from Test Files
**What goes wrong:** Including test files in coverage calculations inflates metrics (tests cover tests, not production code).

**Why it happens:** `collectCoverageFrom` includes `**/__tests__/**` patterns by accident.

**How to avoid:** Explicitly exclude test directories and files:
```javascript
collectCoverageFrom: [
  'components/**/*.{ts,tsx}',
  '!**/__tests__/**',
  '!**/*.test.{ts,tsx}',
  '!**/*.spec.{ts,tsx}',
],
```

**Warning signs:** Coverage >90% but integration components at 0%, or sudden coverage jumps after adding test files.

### Pitfall 2: False Coverage from Type Definitions
**What goes wrong:** `.d.ts` files counted as coverable code but don't require testing.

**Why it happens:** TypeScript declaration files matched by `{ts,tsx}` glob patterns.

**How to avoid:** Always exclude type definitions:
```javascript
collectCoverageFrom: [
  'components/**/*.{ts,tsx}',
  '!**/*.d.ts',
],
```

**Warning signs:** 100% coverage for type-only files, "covered" lines with no executable code.

### Pitfall 3: CI/CD Coverage Drift
**What goes wrong:** Local coverage reports differ from CI due to environment differences (Node version, OS, file paths).

**Why it happens:** Local Jest cache conflicts, OS-specific path separators, different Node versions.

**How to avoid:**
1. Run `jest --clearCache` before CI
2. Use consistent Node version in CI and local (`package.json` engines field)
3. Commit `coverage/coverage-summary.json` for PR comparison baseline
```bash
# .github/workflows/frontend-tests.yml
- name: Clear Jest cache
  run: cd frontend-nextjs && npx jest --clearCache

- name: Run tests with coverage
  run: cd frontend-nextjs && npm run test:ci -- --maxWorkers=2
```

**Warning signs:** CI passes coverage gate but local shows regression, or vice versa.

### Pitfall 4: Threshold Paralysis
**What goes wrong:** Per-module thresholds set too strict (100%) or too lax, blocking deployment or allowing gaps.

**Why it happens:** Global thresholds applied uniformly without considering module complexity, business criticality, or external dependencies.

**How to avoid:** Use graduated thresholds based on module characteristics:
```javascript
coverageThreshold: {
  global: { lines: 80 },  // Baseline for all code
  './lib/**/*.{ts,tsx}': { lines: 90 },  // Utils are testable, critical
  './components/integrations/**/*.{ts,tsx}': { lines: 70 },  // External deps, complex
}
```

**Warning signs:** PRs blocked on trivial utility functions, or critical integration components pass with 5% coverage.

### Pitfall 5: Ignoring Coverage Reports
**What goes wrong:** Coverage reports generated but never reviewed, gaps accumulate over time.

**Why it happens:** No automated enforcement, reports buried in artifacts, developer feedback loop broken.

**How to avoid:**
1. Post coverage summary as PR comment (use existing `coverage-report.yml` pattern)
2. Fail CI on coverage regression below threshold (use existing `quality-gates.yml`)
3. Generate coverage trend dashboard (backend has pattern at `tests/coverage_reports/dashboards/`)

**Warning signs:** Consistent coverage decline over months, no PR comments on coverage impact.

## Code Examples

Verified patterns from official sources:

### Generate Per-Module Coverage Report
```javascript
// Source: https://jest.nodejs.cn/docs/configuration/
// jest.config.js
module.exports = {
  collectCoverage: true,
  coverageDirectory: 'coverage',
  coverageReporters: ['json-summary', 'text', 'lcov'],  // json-summary for programmatic access
  collectCoverageFrom: [
    'components/**/*.{ts,tsx}',
    'pages/**/*.{ts,tsx}',
    'lib/**/*.{ts,tsx}',
    'hooks/**/*.{ts,tsx}',
    '!**/*.d.ts',
    '!**/node_modules/**',
    '!**/.next/**',
  ],
};

// Run: npm run test:coverage
// Output: coverage/coverage-summary.json with per-file metrics
```

### Extract Module Coverage Metrics
```javascript
// Source: Jest coverage-summary.json structure (Istanbul format)
const fs = require('fs');

function getModuleCoverage(coverageFile, modulePath) {
  const coverage = JSON.parse(fs.readFileSync(coverageFile, 'utf8'));

  // Find matching modules (supports partial paths)
  const modules = Object.entries(coverage)
    .filter(([filepath]) => filepath.includes(modulePath))
    .map(([filepath, metrics]) => ({
      file: filepath,
      lines: metrics.lines.pct,
      functions: metrics.functions.pct,
      branches: metrics.branches.pct,
      statements: metrics.statements.pct,
    }));

  return modules;
}

// Example: Get all integration component coverage
const integrations = getModuleCoverage('./coverage/coverage-summary.json', 'components/integrations');
console.log(`Average integration coverage: ${avg(integrations.map(m => m.lines))}%`);
```

### Enforce Module-Level Thresholds in CI
```yaml
# Source: Existing .github/workflows/quality-gates.yml pattern
# .github/workflows/frontend-module-coverage.yml
name: Frontend Module Coverage Gates

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main]

jobs:
  module-coverage:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend-nextjs/package-lock.json

      - name: Install dependencies
        working-directory: ./frontend-nextjs
        run: npm ci --legacy-peer-deps

      - name: Run tests with coverage
        working-directory: ./frontend-nextjs
        run: npm run test:coverage -- --maxWorkers=2

      - name: Check module thresholds
        working-directory: ./frontend-nextjs
        run: |
          node scripts/check-module-coverage.js \
            --threshold 80 \
            --reporter github-actions
```

### Test Uncovered Integration Component
```javascript
// Source: React Testing Library patterns
// components/integrations/__tests__/JiraIntegration.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { JiraIntegration } from '../JiraIntegration';

describe('Jira Integration Component', () => {
  it('renders connection form when not authenticated', () => {
    render(<JiraIntegration />);
    expect(screen.getByLabelText(/jira instance url/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /connect/i })).toBeInTheDocument();
  });

  it('handles OAuth connection flow', async () => {
    const mockOnConnect = jest.fn();
    render(<JiraIntegration onConnect={mockOnConnect} />);

    const urlInput = screen.getByLabelText(/jira instance url/i);
    await userEvent.type(urlInput, 'https://example.atlassian.net');

    const connectButton = screen.getByRole('button', { name: /connect/i });
    await userEvent.click(connectButton);

    await waitFor(() => {
      expect(mockOnConnect).toHaveBeenCalledWith('https://example.atlassian.net');
    });
  });

  it('displays error message on connection failure', async () => {
    const mockOnError = jest.fn();
    render(<JiraIntegration onError={mockOnError} />);

    // MSW mock to return 401
    server.use(
      rest.post('/api/integrations/jira/connect', (req, res, ctx) => {
        return res(ctx.status(401), ctx.json({ error: 'Invalid credentials' }));
      })
    );

    const connectButton = screen.getByRole('button', { name: /connect/i });
    await userEvent.click(connectButton);

    await waitFor(() => {
      expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
    });
  });
});
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Jest 29** | **Jest 30** (2024-10) | Oct 2024 | Performance improvements, better TypeScript support |
| **Enzyme** | **React Testing Library** | 2020+ | User-centric testing, official React recommendation |
| **Custom coverage scripts** | **Istanbul built-in** | Jest 17+ (2018) | Zero-config coverage, 8+ reporter formats |
| **Manual threshold enforcement** | **coverageThreshold in config** | Jest 20+ (2017) | Declarative quality gates, CI-integrated |
| **Coverage HTML only** | **JSON summary + trend tracking** | 2019+ | Programmatic access, automated trending, PR comments |

**Deprecated/outdated:**
- **Enzyme** (shallow rendering): Deprecated in favor of React Testing Library (full DOM rendering)
- **jest-cli** separate package: Now bundled with Jest as `jest` command
- **istanbul CLI**: Use `jest --coverage` instead (Istanbul integrated)

## Open Questions

1. **89.84% vs 4.87% Coverage Discrepancy**
   - What we know: ROADMAP.md claims 89.84% overall frontend coverage, but actual coverage-summary.json shows 4.87% (1052/21592 lines)
   - What's unclear: Source of 89.84% metric (possibly from different measurement, selective reporting, or outdated data)
   - Recommendation: Use current 4.87% as baseline, investigate discrepancy in Plan 01 (coverage audit), trust coverage-summary.json as source of truth

2. **Per-Module Threshold Rollout Strategy**
   - What we know: 36 integration components at 0% coverage, canvas components have better coverage
   - What's unclear: Whether to set 80% threshold immediately for all modules (may block development) or graduated rollout (critical modules first)
   - Recommendation: Use graduated thresholds in Plan 02 (thresholds configuration):
     - Utils/lib: 90% (already critical infrastructure, testable)
     - Canvas components: 85% (maintain current good coverage)
     - Integration components: 70% initially, ramp to 80% in Phase 131+
     - Global floor: 80% by end of Phase 130

3. **Coverage Trend Tracking for Frontend**
   - What we know: Backend has sophisticated trend tracking (`tests/coverage_reports/trend_tracker.py`, dashboards, PR comments)
   - What's unclear: Whether to reuse backend Python scripts or create Node.js equivalent for frontend
   - Recommendation: Plan 04 should create Node.js version of backend trend tracker (consistency within frontend ecosystem), use same JSON structure for cross-platform comparison in Phase 146 (CROSS-02)

## Sources

### Primary (HIGH confidence)
- **Jest Documentation (Chinese)** - https://jest.nodejs.cn/docs/configuration/
  - Verified: `coverageThreshold` configuration, `coverageReporters` options, per-directory glob patterns
  - Confirmed: JSON summary reporter format, collectCoverageFrom patterns

- **Jest Official GitHub** - https://github.com/jestjs/jest
  - Verified: Jest 30.0.5 release (2024-10), TypeScript improvements, performance gains

- **React Testing Library Docs** - https://testing-library.com/react
  - Verified: renderHook for hooks testing, userEvent API, waitFor patterns
  - Confirmed: Best practices (test behavior not implementation, avoid state testing)

- **Istanbul Coverage Format** - https://istanbul.js.org/
  - Verified: JSON-summary structure (lines, branches, functions, statements metrics)
  - Confirmed: 8 reporter formats (lcov, json, json-summary, text, clover, etc.)

### Secondary (MEDIUM confidence)
- **Jest Coverage Reports Tutorial** - https://m.blog.csdn.net/gitblog_01111/article/details/154851544 (2025-10-12)
  - Verified: HTML report generation, JSON-summary usage, CI integration patterns

- **React Component Testing Guide** - https://blog.csdn.net/gitblog_00570/article/details/151454089 (2024-04)
  - Verified: Component testing patterns, coverage gap identification strategies

- **Jest Monorepo Coverage** - https://dev.to/mbarzeev/aggregating-unit-test-coverage-for-all-monorepos-packages-20c6
  - Verified: Per-package coverage configuration, Jest projects pattern
  - Note: Atom is not a monorepo (single frontend app), but per-module patterns apply

- **Coverage Trend Tracking** - https://m.blog.csdn.net/gitblog_01109/article/details/153502599 (2025-10-08)
  - Verified: GitHub Actions integration, SVG chart generation, commit-based tracking
  - Pattern: Similar to backend's `coverage-report.yml` workflow

### Tertiary (LOW confidence)
- **VSCode Coverage Gutters** - Various CSDN articles (2024-2025)
  - Needs validation: Plugin setup for local coverage visualization
  - Note: Developer convenience, not required for Phase 130 success

- **jest-coverage-report-action** - GitCode mirror (2026-01)
  - Needs validation: Latest features, GitHub Actions compatibility
  - Note: Existing backend coverage PR comment bot may be sufficient

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All packages verified in package.json, official docs confirm capabilities
- Architecture: HIGH - Jest/Istanbul coverage mechanisms well-documented, patterns verified in codebase
- Pitfalls: HIGH - Common issues documented in Jest community, patterns observed in backend coverage work

**Research date:** 2026-03-03
**Valid until:** 2026-04-03 (30 days - stable testing ecosystem, no major releases expected)

**Key data sources:**
- `/Users/rushiparikh/projects/atom/frontend-nextjs/jest.config.js` (current configuration)
- `/Users/rushiparikh/projects/atom/frontend-nextjs/coverage/coverage-summary.json` (4.87% baseline)
- `/Users/rushiparikh/projects/atom/.github/workflows/frontend-tests.yml` (existing CI pattern)
- `/Users/rushiparikh/projects/atom/.github/workflows/quality-gates.yml` (threshold enforcement)
- `/Users/rushiparikh/projects/atom/.planning/REQUIREMENTS.md` (FRONTEND-01 requirement)

**Critical findings for planning:**
1. **Severe coverage gap:** 4.87% actual vs 89.84% reported = 75+ percentage point gap to 80% target
2. **Module structure:** 36 integration components at 0% coverage, canvas components have good foundation (20+ tests)
3. **Existing infrastructure:** CI workflows, backend trend tracking patterns, MSW mocking configured
4. **Tooling:** Jest 30.0.5 production-ready, no migration needed, json-summary enables per-module analysis
