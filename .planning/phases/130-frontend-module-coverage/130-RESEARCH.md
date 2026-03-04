# Phase 130: Frontend Module Coverage Consistency - Research

**Date:** 2026-03-03
**Status:** CRITICAL FINDING - Coverage discrepancy identified
**Actual Baseline:** 4.87% (not 89.84% as claimed in ROADMAP.md)

---

## Executive Summary

Phase 130 investigates the massive discrepancy between claimed frontend coverage (89.84% in ROADMAP.md) and actual coverage (4.87% measured). The research reveals:

1. **Coverage discrepancy**: ROADMAP claims 89.84% but actual is 4.87% - a 75+ percentage point gap
2. **595 modules** have 0% coverage out of ~660 total modules
3. **Directory-level coverage**: lib/ 44.46%, hooks/ 14.56%, components/ 4.25%, pages/ 0.33%
4. **Test infrastructure exists**: Jest 30.0.5, React Testing Library 16.3.0, proper configuration
5. **Existing tests** are focused on specific areas (canvas, lib utilities) with good quality

The discrepancy likely stems from ROADMAP measuring only tested files while claiming overall coverage, or using a different measurement scope.

---

## Current Coverage Analysis

### Overall Coverage (measured 2026-03-03)

| Metric | Percentage | Covered/Total |
|--------|------------|---------------|
| Lines | 4.87% | 1,052/21,592 |
| Statements | 4.75% | 1,086/22,837 |
| Functions | 4.72% | 256/5,421 |
| Branches | 4.46% | 712/15,936 |

### Directory-Level Coverage

| Directory | Coverage | Files | Lines Covered/Total |
|-----------|----------|-------|---------------------|
| lib/ | 44.46% | 18 | 321/722 |
| hooks/ | 14.56% | 25 | 144/989 |
| components/ | 4.25% | 232 | 565/13,303 |
| pages/ | 0.33% | 386 | 22/6,578 |

### Top 20 Modules by Coverage

| Module | Coverage | Lines | Notes |
|--------|----------|-------|-------|
| components/layout/Layout.tsx | 100% | 2/2 | Minimal file |
| hooks/useWebSocket.ts | 100% | 54/54 | Excellent coverage |
| lib/validation.ts | 100% | 50/50 | Comprehensive tests |
| lib/integrations-catalog.ts | 100% | 39/39 | Good test coverage |
| lib/crypto.ts | 100% | 18/18 | Crypto utilities tested |
| components/canvas/OperationErrorGuide.tsx | 97.72% | 43/44 | Near perfect |
| lib/password-validator.ts | 96.36% | 53/55 | Well tested |
| lib/tokenEncryption.ts | 96% | 48/50 | Encryption tested |
| hooks/useUndoRedo.ts | 94.59% | 35/37 | Good hook testing |
| components/ui/card.tsx | 94.44% | 17/18 | UI component tested |
| components/canvas/InteractiveForm.tsx | 92% | 69/75 | Form component tested |
| lib/websocket-client.ts | 91.66% | 11/12 | WebSocket client |
| hooks/useCanvasState.ts | 90.9% | 30/33 | Canvas state hook |
| components/ui/select.tsx | 88.88% | 16/18 | Select component |
| components/canvas/ViewOrchestrator.tsx | 87.65% | 71/81 | Canvas orchestration |
| components/ui/slider.tsx | 80% | 4/5 | Slider component |
| components/canvas/AgentRequestPrompt.tsx | 76.38% | 55/72 | Agent prompts |
| components/canvas/test utilities | 70.96% | 22/31 | Test infrastructure |
| lib/db.ts | 70.58% | 12/17 | Database utilities |
| components/ui/dialog.tsx | 70% | 14/20 | Dialog component |

### Bottom Modules (0% Coverage)

**36 Integration Components at 0%:**
- AsanaIntegration.tsx (142 lines)
- AzureIntegration.tsx (178 lines)
- BoxIntegration.tsx (260 lines)
- DiscordIntegration.tsx (54 lines)
- FreshdeskIntegration.tsx (130 lines)
- GitHubIntegration.tsx (112 lines)
- IntercomIntegration.tsx (115 lines)
- JiraIntegration.tsx (158 lines)
- JiraOAuthFlow.tsx (120 lines)
- LinearIntegration.tsx (137 lines)
- MailchimpIntegration.tsx (136 lines)
- NotionIntegration.tsx (161 lines)
- OutlookIntegration.tsx (148 lines)
- QuickBooksIntegration.tsx (246 lines)
- SlackIntegration.tsx (147 lines)
- StripeIntegration.tsx (130 lines)
- TableauIntegration.tsx (89 lines)
- TeamsIntegration.tsx (142 lines)
- ZendeskIntegration.tsx (137 lines)
- And 17 more integration components...

**Other Notable 0% Coverage:**
- Dashboard.tsx (64 lines) - Main dashboard
- PerformanceDashboard.tsx (61 lines)
- SystemStatusDashboard.tsx (58 lines)
- CommunicationHub.tsx (6 lines)
- TaskManagement.tsx (80 lines)
- CalendarManagement.tsx (49 lines)
- SmartSearch.tsx (11 lines)
- GlobalChatWidget.tsx (126 lines)
- All pages/ directory (0.33% = 22/6,578 lines)

---

## Root Cause Analysis

### Why the Discrepancy?

**Hypothesis 1: Different Measurement Scope**
- ROADMAP 89.84% likely measured only files that HAVE tests
- Actual 4.87% measures ALL source files
- 89.84% of ~1,000 tested lines vs 4.87% of ~21,600 total lines

**Hypothesis 2: Test Directory Inclusion**
- Some measurements may include test/ directory in coverage
- This inflates numbers artificially

**Hypothesis 3: Coverage Collection Configuration**
- Jest collectCoverageFrom may have been configured differently
- Previous measurements may have excluded large directories

### Verification

The jest.config.js shows proper configuration:
```javascript
collectCoverageFrom: [
  "components/**/*.{ts,tsx}",
  "pages/**/*.{ts,tsx}",
  "lib/**/*.{ts,tsx}",
  "hooks/**/*.{ts,tsx}",
  "!**/*.d.ts",
  "!**/node_modules/**",
  "!**/.next/**",
],
```

This configuration is correct and includes all major source directories.

---

## Existing Test Infrastructure

### Jest Configuration (jest.config.js)

- **Test Environment:** jsdom
- **Setup Files:** polyfills.ts, setup.ts
- **Transform:** babel-jest for TS/TSX/JS/JSX
- **Test Match:** Standard patterns
- **Coverage Reporters:** json, json-summary, text, lcov
- **Coverage Thresholds:** 80% across all metrics (NOT being met)

### Testing Libraries

- **Jest:** 30.0.5 (latest)
- **React Testing Library:** 16.3.0 (latest)
- **Testing Library DOM:** 10.4.1
- **Testing Library user-event:** 14.6.1
- **MSW:** 1.3.5 (for API mocking)

### Existing Test Files

**Component Tests (20+ files):**
- components/canvas/__tests__/ (11 test files)
- components/integrations/__tests__/ (1 test file)
- components/Agents/__tests__/ (1 test file)
- components/Voice/__tests__/ (1 test file)
- components/layout/__tests__/ (1 test file)
- components/__tests__/ (2 test files)

**Library Tests (25+ files):**
- lib/__tests__/ (25 test files)
- lib/__tests__/api/ (5 test files)

**Test Utilities:**
- tests/setup.ts
- tests/polyfills.ts
- tests/mocks/ (data.ts, errors.ts, handlers.ts, server.ts)

### Test Quality

From Phase 105 canvas component coverage summary:
- 370+ component tests created
- 94.4% test pass rate
- User-centric queries (getByRole, getByLabelText)
- Accessibility tree testing
- WebSocket integration tests with mocks

---

## Gap Analysis

### What's Missing

1. **Integration Components (36 files, ~5,000 lines)**
   - 0% coverage across all third-party integrations
   - Asana, Azure, Box, GitHub, Jira, Linear, Notion, Slack, etc.

2. **Pages Directory (386 files, ~6,578 lines)**
   - 0.33% coverage (only 22 lines covered)
   - API routes, page components, server-side rendering

3. **Core Components (100+ files)**
   - Dashboard, Calendar, Communication, Task Management
   - Settings components (15+ files)
   - Debugging components (10+ files)
   - Collaboration components (5+ files)

4. **Hooks (25 files, 989 lines)**
   - Only 14.56% coverage
   - useChatMemory, useAgentExecution, useAudioControl need testing

5. **UI Components (30+ files)**
   - Some have good coverage (button, input, card)
   - Many need coverage (accordion, dropdown, resizable, scroll-area, sheet, separator)

### Coverage Gap to 80% Target

| Metric | Current | Target | Gap |
|--------|---------|--------|-----|
| Lines | 1,052 | 17,274 | 16,222 lines |
| Statements | 1,086 | 18,270 | 17,184 statements |
| Functions | 256 | 4,337 | 4,081 functions |
| Branches | 712 | 12,749 | 12,037 branches |

---

## Technical Stack

### Current Versions

```json
{
  "jest": "^30.0.5",
  "@testing-library/react": "^16.3.0",
  "@testing-library/jest-dom": "^6.6.3",
  "@testing-library/user-event": "^14.6.1",
  "jest-environment-jsdom": "^30.0.5",
  "babel-jest": "^30.2.0",
  "ts-jest": "^29.4.0"
}
```

### Testing Patterns Used

1. **Component Testing:** React Testing Library with user-centric queries
2. **Hook Testing:** Direct testing in component tests
3. **API Testing:** MSW for mocking, axios testing patterns
4. **Property Testing:** fast-check for invariants (lib/__tests__/*.property.test.ts)
5. **Accessibility Testing:** ARIA attributes, role queries

---

## Per-Module Coverage Enforcement

### Istanbul Coverage Support

Jest uses Istanbul for coverage collection. The json-summary report provides per-module coverage data:

```json
{
  "/path/to/module.tsx": {
    "lines": { "total": 100, "covered": 50, "pct": 50 },
    "functions": { "total": 10, "covered": 5, "pct": 50 },
    "statements": { "total": 120, "covered": 60, "pct": 50 },
    "branches": { "total": 20, "covered": 10, "pct": 50 }
  }
}
```

### Module-Level Threshold Options

**Option 1: Jest Coverage Thresholds per Path**

Jest supports per-path thresholds in jest.config.js:

```javascript
coverageThreshold: {
  global: {
    branches: 80,
    functions: 80,
    lines: 80,
    statements: 75
  },
  "./lib/**/*.{ts,tsx}": {
    branches: 80,
    functions: 80,
    lines: 80,
    statements: 80
  },
  "./components/canvas/**/*.{ts,tsx}": {
    branches: 80,
    lines: 80
  }
}
```

**Option 2: Custom Coverage Script**

A Node.js script can parse coverage-summary.json and enforce per-module thresholds:

```javascript
const coverage = JSON.parse(fs.readFileSync('coverage/coverage-summary.json', 'utf8'));
const violations = [];

Object.entries(coverage).forEach(([file, metrics]) => {
  if (metrics.lines.pct < 80) {
    violations.push({ file, coverage: metrics.lines.pct });
  }
});

if (violations.length > 0) {
  console.error('Modules below 80%:', violations);
  process.exit(1);
}
```

**Option 3: CI/CD Integration**

GitHub Actions can fail PRs if modules fall below threshold:

```yaml
- name: Check module coverage
  run: |
    node scripts/check-module-coverage.js --threshold 80
```

### Recommended Approach

**Phase 130 should:**

1. **Create baseline measurement** - Document current per-module coverage
2. **Create gap analysis script** - Identify modules below 80% by priority
3. **Add tests strategically** - Focus on high-impact, low-coverage modules
4. **Implement enforcement** - CI check for module-level thresholds

---

## Recommended Strategy

### Wave 1: Audit & Verification (Plan 01)

**Goal:** Verify coverage discrepancy and establish accurate baseline

- Re-run coverage with verified configuration
- Document measurement methodology
- Identify root cause of 89.84% vs 4.87% discrepancy
- Create per-module baseline report

### Wave 2: Gap Analysis (Plan 02)

**Goal:** Identify highest-impact modules for testing

- Group modules by: business value, line count, dependencies
- Prioritize: Integration components > Dashboard > Core features
- Create test plan with coverage targets
- Estimate effort for each module group

### Wave 3: High-Impact Tests (Plans 03-04)

**Goal:** Add tests for highest-value modules

- **Plan 03:** Integration component tests (Asana, Jira, Slack, Notion - top 4)
- **Plan 04:** Dashboard and core feature tests (Dashboard, Calendar, CommunicationHub)

### Wave 4: Infrastructure (Plan 05-06)

**Goal:** Establish coverage enforcement infrastructure

- **Plan 05:** Per-module coverage enforcement script
- **Plan 06:** CI integration and quality gate

---

## Success Criteria Validation

### From ROADMAP Phase 130:

1. **Per-module coverage report shows all modules ≥80%**
   - Status: NOT MET (595/660 modules < 80%)
   - Path: Create report, then work toward target

2. **Coverage gaps identified in underperforming modules**
   - Status: IN PROGRESS (this research document)
   - Path: Prioritize by business value

3. **Tests added for uncovered components and utilities**
   - Status: TODO (Plans 03-04)
   - Path: Strategic test creation

4. **Module-level coverage enforced in quality gates**
   - Status: TODO (Plan 05-06)
   - Path: CI integration

5. **Coverage trend shows consistent improvement across modules**
   - Status: TODO (Plan 06)
   - Path: Coverage tracking over time

---

## Open Questions

1. **ROADMAP Accuracy:** Where did 89.84% come from? Needs investigation.
2. **Test Strategy:** Should we aim for 80% across ALL modules or focus on critical paths?
3. **Integration Tests:** Are integration component tests valuable or are they mostly API wrapper code?
4. **Pages Directory:** Should 386 API routes be tested or focus on page components only?
5. **Property Tests:** Should fast-check be expanded beyond lib/?

---

## References

- jest.config.js - Test configuration
- coverage/coverage-summary.json - Coverage data source
- frontend-nextjs/components/canvas/__tests__/canvas-coverage-summary.md - Phase 105 results
- ROADMAP.md - Phase 130 definition
