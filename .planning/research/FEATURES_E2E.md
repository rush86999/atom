# Feature Research: E2E UI Testing for Atom Platform

**Domain:** End-to-End Testing - Playwright-based UI Testing
**Researched:** February 23, 2026
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

E2E testing capabilities that teams assume exist. Missing these = E2E framework feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Happy Path Tests** | Foundation of E2E testing - verify critical user flows work end-to-end | LOW | Standard Playwright patterns, test ID locators required |
| **Authentication Flows** | Login/logout, session management - most apps require auth to test features | MEDIUM | storageState fixtures for fast login, MFA support adds complexity |
| **Form Submission & Validation** | Canvas forms, skill config - core interaction pattern | LOW | Test validation errors, required fields, successful submission |
| **Navigation & Routing** | Multi-page apps require flow between pages | LOW | Verify URL changes, breadcrumb navigation, back/forward browser actions |
| **Dynamic Content Rendering** | Wait for async data, charts, canvas to load | MEDIUM | Playwright auto-waiting + explicit signals (network, element visibility) |
| **Error Handling Tests** | Verify UI shows appropriate errors when things fail | MEDIUM | Network failures, API errors, validation messages |
| **Responsive Design Testing** | Modern apps work on mobile/tablet/desktop | MEDIUM | Viewport configuration, mobile emulation in Playwright |
| **Screenshot on Failure** | Essential for debugging CI failures | LOW | Built-in Playwright feature: `screenshot: 'only-on-failure'` |
| **Test Reports** | CI/CD requires readable test results | LOW | HTML reporter configured, JSON for CI integration |
| **Flaky Test Retries** | Network/browser issues cause intermittent failures | LOW | Configured in playwright.config.ts: `retries: process.env.CI ? 2 : 1` |
| **Parallel Test Execution** | Reduce test run time for large suites | MEDIUM | `fullyParallel: false` (current) - enable for speed when stable |
| **Browser Selection** | Test on Chrome (primary) + cross-browser when needed | LOW | Projects configured for Chromium in config |

### Differentiators (Competitive Advantage)

E2E testing features that set Atom's testing apart. Not required, but highly valuable for real-time AI platform.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **WebSocket Message Capture** | Test streaming LLM responses - unique to AI platforms | HIGH | Playwright WebSocket monitoring via `page.on('websocket')` (HIGH confidence) |
| **Real-Time Canvas State Testing** | Verify AI accessibility tree exposes correct state | MEDIUM | Use `window.atom.canvas.getState()` API for assertions |
| **Agent Governance Flow Testing** | Test STUDENT→INTERN→SUPERVISED→AUTONOMOUS transitions | HIGH | Multi-step tests with approval workflows, confidence thresholds |
| **Episode Integration Verification** | Test canvas presentations + feedback capture | MEDIUM | Verify episode creation after interactions, state persistence |
| **Multi-Agent Orchestration Testing** | Test concurrent agent execution with governance | HIGH | Complex - requires multiple WebSocket connections, state coordination |
| **Streaming Response Validation** | Verify token-by-token streaming works correctly | HIGH | Capture WebSocket frames, assert streaming format, completion |
| **Canvas Component Testing** | Test charts, forms, trackers render correctly | MEDIUM | Visual regression + programmatic state checks |
| **Skill Installation E2E** | Test marketplace → install → config → use workflow | MEDIUM | Complex flow, requires governance checks, vulnerability scanning |
| **Browser Automation Testing** | Test CDP-based browser tool integration | HIGH | Requires Playwright CDP connection, very meta (testing with itself) |
| **Device Capabilities Testing** | Test camera, screen recording, notifications | HIGH | Requires real devices or emulators, permissions handling |
| **Maturity-Based Access Control** | Test actions blocked/approved based on agent maturity | HIGH | Core to Atom's value prop - verify governance enforcement |
| **Graduation Criteria Testing** | Test agent levels up after meeting thresholds | MEDIUM | Episode count, intervention rate, constitutional score |
| **Real-Time Error Guidance** | Test error resolution workflows, smart error categorization | MEDIUM | Verify 7 error categories, guidance canvas presentation |
| **Wave-Based Parallel Execution** | Test autonomous coding agent parallel task execution | HIGH | Verify DAG validation, checkpoint/rollback system |
| **AI Accessibility Testing** | Verify hidden trees expose state for screen readers | MEDIUM | Check `role='log'`, `aria-live` attributes, JSON state |

### Anti-Features (Commonly Requested, Often Problematic)

E2E testing approaches that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Fixed Timeout Waits** (`page.waitForTimeout`) | Simple to write, "wait for things to load" | Increases flakiness, tests fail when network is slow, creates false negatives | Use Playwright auto-waiting + explicit signals: `waitForResponse()`, `waitForSelector()`, `waitForURL()` |
| **Visual Regression for Everything** | "Catch any UI change automatically" | High maintenance burden, false positives from minor layout shifts, slow execution | Use for critical branding elements only; rely on state-based assertions for functional testing |
| **Testing Every User Journey** | "Comprehensive coverage" | Diminishing returns, slow test suite, brittle tests | Focus on **critical paths** (login → agent chat → canvas → skill install) and **high-risk scenarios** |
| **Cross-Browser Testing for Every Test** | "Support all browsers equally" | 3x test execution time, most bugs found on primary browser (Chromium) | Test cross-browser for regression or pre-release only; focus on Chromium for PR gate |
| **Testing Third-Party Integrations** | "Verify Gmail/QuickBooks/etc. works" | Flaky due to external API rate limits, auth changes, not our responsibility | Mock integration APIs in E2E, rely on integration tests for real API validation |
| **Complex Page Object Model (POM)** | "Organized, maintainable tests" | Over-engineering for simple tests, POM becomes outdated, creates abstraction leakage | Use lightweight page objects (fixture functions) for reusable operations; keep tests readable |
| **Testing Backend Logic via UI** | "True end-to-end" | Slow feedback loop, hard to debug, backend logic should have unit/integration tests | Use E2E for **user journeys**, not business logic validation |
| **Randomized Test Data** | "Catch edge cases" | Non-deterministic failures, hard to reproduce bugs | Use fixed test data for E2E; use property-based tests for edge cases |
| **Testing Analytics/Metrics** | "Verify tracking works" | Brittle selectors, changes frequently, not core to user value | Spot-check analytics integration; don't build comprehensive E2E suite around it |
| **Testing Deprecated Features** | "Ensure nothing breaks" | Wastes maintenance time, delays deletion | Delete tests when features are deprecated; E2E should test current functionality |

## Feature Dependencies

```
[Authentication State Management]
    └──requires──> [User Accounts Database]
                   └──requires──> [API Auth Endpoints]

[Agent Chat E2E Tests]
    └──requires──> [WebSocket Infrastructure]
                   └──requires──> [LLM Provider Integration]
    └──enhances──> [Streaming Response Validation]

[Canvas Presentation Tests]
    └──requires──> [Canvas State API] (window.atom.canvas)
    └──requires──> [Dynamic Component Rendering]
    └──enhances──> [AI Accessibility Testing]

[Agent Governance Tests]
    └──requires──> [Agent Maturity System]
                   └──requires──> [Governance Cache]
    └──enhances──> [Graduation Criteria Testing]

[Skill Installation E2E]
    └──requires──> [Marketplace API]
    └──requires──> [Package Governance Service]
    └──requires──> [Vulnerability Scanner]

[Browser Automation E2E]
    └──requires──> [Playwright CDP Integration]
    └──conflicts──> [Headless Mode] (some CDP features require headed)

[Device Capabilities Testing]
    └──requires──> [Real Devices/Emulators]
    └──enhances──> [Permission Flow Testing]

[Episode Integration Tests]
    └──requires──> [Episode Segmentation Service]
    └──requires──> [Episode Lifecycle Service]
    └──enhances──> [Agent Graduation Testing]

[Autonomous Coding Agent E2E]
    └──requires──> [All Core Services]
    └──requires──> [Git Repository]
    └──requires──> [WebSocket Streaming]
```

### Dependency Notes

- **Authentication State Management requires User Accounts:** E2E tests need existing users or ability to create them. Use `storageState` fixtures to save login session and skip login flow in every test.
- **Agent Chat Tests enhance Streaming Response Validation:** Chat tests naturally verify streaming works; streaming tests can be more focused on WebSocket frame format, timing, and error recovery.
- **Canvas State API required for Canvas Tests:** Tests use `window.atom.canvas.getState()` to verify AI accessibility tree; this is the primary assertion mechanism for canvas components.
- **Browser Automation E2E conflicts with Headless Mode:** Some CDP-based features (screen sharing, certain device capabilities) require headed browser; mark these tests with `@headed` marker.
- **Episode Integration enhances Agent Graduation:** Episode tests validate capture/storage, graduation tests verify agents level up correctly based on episode data.

## MVP Definition (v3.1 E2E Testing)

### Launch With (v3.1)

Minimum viable E2E testing for production readiness validation.

- [ ] **Critical Path: Login → Agent Chat → Canvas Response** — Verify core user journey (STUDENT agent with streaming response)
- [ ] **Critical Path: Skill Installation** — Test marketplace search → install → configure → use (INTERN agent approval)
- [ ] **Canvas Form Submission** — Test InteractiveForm component (validation, submission, canvas state)
- [ ] **Agent Governance Enforcement** — Verify STUDENT blocked from actions, INTERN requires approval
- [ ] **Episode Creation** — Verify episodes created after canvas interactions
- [ ] **WebSocket Streaming** — Capture and validate streaming LLM responses
- [ ] **Error Handling** — Test API errors, network failures, validation messages
- [ ] **Authentication Flows** — Login, logout, session persistence, re-auth
- [ ] **Screenshot/Video on Failure** — Debugging support for CI failures
- [ ] **HTML Test Reports** — Readable results for team review

### Add After Validation (v3.2)

Features to add once core E2E is stable.

- [ ] **Multi-Agent Orchestration** — Test concurrent agent execution with governance
- [ ] **Graduation Criteria** — Full agent level-up testing (episode counts, intervention rates)
- [ ] **Browser Automation E2E** — Test CDP-based tool with real browser control
- [ ] **Device Capabilities** — Camera, notifications, location permissions
- [ ] **Visual Regression** — Critical branding elements (logo, key canvas components)
- [ ] **Cross-Browser Testing** — Firefox, Safari for regression
- [ ] **Performance Regression** — Page load times, streaming latency thresholds
- [ ] **Parallel Execution** — Speed up test suite once flakiness is resolved

### Future Consideration (v4+)

Deferred until E2E practice is mature and stable.

- [ ] **Mobile App Testing** — React Native E2E with Detox/Appium (different skillset)
- [ ] **Chaos Engineering** — Inject failures (network, database) during E2E runs
- [ ] **Load Testing for WebSockets** — Concurrent connection limits (K6 or Artillery)
- [ ] **AI-Generated Tests** — Use LLM to generate E2E tests from user stories
- [ ] **Self-Healing Tests** — Auto-fix selectors when UI changes (experimental)

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| **Critical Path: Login → Chat → Canvas** | HIGH | MEDIUM | P1 |
| **WebSocket Streaming Validation** | HIGH | HIGH | P1 |
| **Agent Governance Enforcement** | HIGH | MEDIUM | P1 |
| **Canvas Form Testing** | HIGH | LOW | P1 |
| **Skill Installation Flow** | HIGH | MEDIUM | P1 |
| **Episode Integration** | MEDIUM | MEDIUM | P1 |
| **Authentication Flows** | HIGH | LOW | P1 |
| **Error Handling Tests** | HIGH | MEDIUM | P1 |
| **Screenshot/Video on Failure** | MEDIUM | LOW | P1 |
| **Multi-Agent Orchestration** | MEDIUM | HIGH | P2 |
| **Graduation Criteria Testing** | MEDIUM | HIGH | P2 |
| **Browser Automation E2E** | MEDIUM | HIGH | P2 |
| **Device Capabilities Testing** | LOW | HIGH | P3 |
| **Visual Regression** | LOW | MEDIUM | P3 |
| **Cross-Browser Testing** | LOW | MEDIUM | P3 |
| **Performance Regression** | MEDIUM | MEDIUM | P2 |
| **Parallel Execution** | MEDIUM | LOW | P2 |
| **Mobile App Testing** | LOW | HIGH | P3 |
| **Chaos Engineering** | LOW | HIGH | P3 |
| **Load Testing** | LOW | MEDIUM | P3 |

**Priority key:**
- **P1**: Must have for v3.1 launch (critical paths, governance)
- **P2**: Should have for v3.2 (advanced features, performance)
- **P3**: Nice to have for v4+ (specialized, future consideration)

## Workflow-Specific Testing Patterns

### 1. Agent Chat & Streaming (HIGH Complexity)

**What to Test:**
- User sends message → Agent responds with streaming
- WebSocket connection established → Message frames captured
- Streaming token-by-token display in UI
- Agent governance blocks/actions based on maturity level
- Session persists across page refreshes
- Chat history loads from previous sessions

**Expected Behaviors:**
- WebSocket connection established within 2 seconds
- First token appears within 5 seconds (LLM latency)
- Streaming completes without interruption
- STUDENT agents can present but not execute actions
- INTERN agents show approval prompts for actions
- SUPERVISED agents execute with real-time monitoring
- AUTONOMOUS agents execute without prompts

**Test Patterns:**
```typescript
// Capture WebSocket messages
test('agent chat streams response', async ({ page }) => {
  const messages: string[] = [];
  page.on('websocket', ws => {
    ws.on('framereceived', (data) => {
      const msg = JSON.parse(data.toString());
      messages.push(msg.content);
    });
  });

  await page.fill('[data-testid="chat-input"]', 'Create a chart');
  await page.click('[data-testid="send-button"]');

  // Assert streaming response
  await expect.poll(() => messages.length).toBeGreaterThan(0);
  expect(messages[messages.length - 1]).toContain('chart');
});
```

**Complexity:** HIGH (WebSocket monitoring, async timing, governance state)

### 2. Canvas Presentations & Forms (MEDIUM Complexity)

**What to Test:**
- Canvas renders with correct component (chart, form, markdown)
- InteractiveForm validates fields correctly
- Form submission triggers agent action
- Canvas state accessible via `window.atom.canvas.getState()`
- AI accessibility tree exposes state (role='log', aria-live)
- Canvas closes/disposes properly

**Expected Behaviors:**
- Canvas appears within 1 second of agent response
- Form fields show validation errors for invalid input
- Submit button disabled when form invalid
- Canvas state JSON includes all fields, validation errors
- Hidden tree includes screen reader attributes

**Test Patterns:**
```typescript
test('canvas form validates and submits', async ({ page }) => {
  // Trigger canvas presentation
  await page.fill('[data-testid="chat-input"]', 'Show me a form');
  await page.click('[data-testid="send-button"]');

  // Wait for canvas
  await page.waitForSelector('[data-testid="canvas-container"]');

  // Check canvas state
  const canvasState = await page.evaluate(() =>
    window.atom.canvas.getState('canvas-id')
  );
  expect(canvasState.component).toBe('form');
  expect(canvasState.form_data).toBeDefined();

  // Fill form with invalid data
  await page.fill('[data-testid="field-email"]', 'invalid-email');
  await page.click('[data-testid="submit-button"]');

  // Assert validation error
  await expect(page.locator('[data-testid="error-email"]')).toBeVisible();

  // Fill valid data and submit
  await page.fill('[data-testid="field-email"]', 'test@example.com');
  await page.click('[data-testid="submit-button"]');

  // Assert submission
  await expect(page.locator('[data-testid="submit-success"]')).toBeVisible();
});
```

**Complexity:** MEDIUM (dynamic components, state assertions)

### 3. Skills & Workflows (MEDIUM Complexity)

**What to Test:**
- Marketplace search returns relevant skills
- Skill installation triggers governance check (INTERN+)
- Skill configuration form saves settings
- Workflow execution uses installed skill
- Vulnerability scanning blocks unsafe skills

**Expected Behaviors:**
- Marketplace loads within 3 seconds
- Search filters by name, category, rating
- Install button disabled for STUDENT agents
- INTERN agents require approval for skill install
- Configuration persists across sessions
- Unsafe skills (vulnerabilities) blocked with clear message

**Test Patterns:**
```typescript
test('skill installation with governance', async ({ page }) => {
  // Navigate to marketplace
  await page.click('[data-testid="nav-marketplace"]');
  await expect(page).toHaveURL('/marketplace');

  // Search for skill
  await page.fill('[data-testid="search-input"]', 'gmail');
  await page.click('[data-testid="search-button"]');

  // Assert results
  await expect(page.locator('[data-testid="skill-card"]')).toHaveCount(3);

  // Click install
  await page.click('[data-testid="skill-gmail"] >> [data-testid="install-button"]');

  // Assert governance approval required (INTERN agent)
  await expect(page.locator('[data-testid="approval-prompt"]')).toBeVisible();
  await expect(page.locator('[data-testid="approval-prompt"]'))
    .toContainText('INTERN agent requires approval');

  // Approve
  await page.click('[data-testid="approve-button"]');

  // Assert installation success
  await expect(page.locator('[data-testid="install-success"]')).toBeVisible();
});
```

**Complexity:** MEDIUM (governance workflows, multi-step flows)

### 4. User Management & Authentication (LOW-MEDIUM Complexity)

**What to Test:**
- Login with email/password
- Logout clears session
- Session persistence across refreshes
- Re-authentication after session expiry
- MFA flow (if enabled)
- User profile updates

**Expected Behaviors:**
- Login completes within 3 seconds
- Invalid credentials show clear error
- Session persists via token/storageState
- Logout redirects to login
- Expired session prompts re-auth

**Test Patterns:**
```typescript
test('user login and session persistence', async ({ page }) => {
  // Navigate to login
  await page.goto('/login');
  await page.fill('[data-testid="email-input"]', 'test@example.com');
  await page.fill('[data-testid="password-input"]', 'password123');
  await page.click('[data-testid="login-button"]');

  // Assert redirect to dashboard
  await expect(page).toHaveURL('/dashboard', { timeout: 5000 });

  // Refresh page - session should persist
  await page.reload();
  await expect(page.locator('[data-testid="user-avatar"]')).toBeVisible();

  // Logout
  await page.click('[data-testid="user-menu"]');
  await page.click('[data-testid="logout-button"]');

  // Assert redirect to login
  await expect(page).toHaveURL('/login');
});
```

**Complexity:** LOW (standard auth flows, well-documented patterns)

### 5. Real-Time Error Guidance (MEDIUM Complexity)

**What to Test:**
- Errors trigger guidance canvas presentation
- 7 error categories correctly classified
- Guidance provides actionable resolution steps
- Error recovery works as expected

**Expected Behaviors:**
- Error canvas appears within 1 second of error
- Error category displayed (e.g., "Network Error", "Validation Error")
- Resolution steps are clear and actionable
- User can retry/fix and continue

**Test Patterns:**
```typescript
test('error guidance canvas presentation', async ({ page }) => {
  // Trigger network error (intercept and block request)
  await page.route('**/api/agents/**', route => route.abort());

  // Attempt agent action
  await page.fill('[data-testid="chat-input"]', 'Execute workflow');
  await page.click('[data-testid="send-button"]');

  // Assert error canvas appears
  await expect(page.locator('[data-testid="error-guidance-canvas"]')).toBeVisible();
  await expect(page.locator('[data-testid="error-category"]'))
    .toContainText('Network Error');

  // Assert resolution steps provided
  await expect(page.locator('[data-testid="resolution-steps"]')).toContainText('Check connection');
});
```

**Complexity:** MEDIUM (error injection, async conditions)

## Critical Paths & Edge Cases

### Happy Paths (Must Work)

1. **User Login → Agent Chat → Canvas Response**
   - User logs in → sends message → agent responds → canvas appears
   - Success criteria: Complete flow without errors in <30 seconds

2. **Skill Install → Configure → Use**
   - Browse marketplace → install skill → configure → execute workflow
   - Success criteria: Skill executes successfully with correct output

3. **Canvas Form → Submit → Agent Action**
   - Agent presents form → user fills → submits → action executes
   - Success criteria: Form validation works, action completes

4. **Agent Graduation**
   - Agent completes episodes → meets thresholds → levels up
   - Success criteria: Maturity level increases, capabilities unlock

### Edge Cases (Should Handle)

1. **WebSocket Connection Drops Mid-Stream**
   - Expected: Reconnect prompt or auto-reconnect
   - Test: Simulate network failure during streaming

2. **LLM Timeout**
   - Expected: Timeout error with retry option
   - Test: Mock slow LLM response (>30s)

3. **Concurrent Agent Execution**
   - Expected: Isolated execution, no state conflicts
   - Test: Launch multiple agents simultaneously

4. **Invalid Skill Installation**
   - Expected: Vulnerability scan blocks install
   - Test: Try to install skill with known vulnerability

5. **Session Expiry During Action**
   - Expected: Action pauses, prompt re-auth, resume after login
   - Test: Use expired token, trigger action

6. **Canvas State Corruption**
   - Expected: Graceful error, canvas reloads
   - Test: Inject invalid state into window.atom.canvas

7. **Agent Governance Bypass Attempt**
   - Expected: Blocked, logged, security alert
   - Test: STUDENT agent attempts action (should be blocked)

## Complexity Assessment

| Workflow | Complexity | Why |
|----------|------------|-----|
| **Agent Chat + Streaming** | HIGH | WebSocket monitoring, async timing, token-by-token assertions, governance state |
| **Canvas Presentations** | MEDIUM | Dynamic components, state API, AI accessibility tree, form validation |
| **Skills & Workflows** | MEDIUM | Multi-step flow, governance approvals, configuration, async operations |
| **User Management** | LOW | Standard auth flows, well-documented patterns, no real-time complexity |
| **Real-Time Error Guidance** | MEDIUM | Error injection, canvas presentation, async conditions |
| **Agent Governance** | HIGH | Multi-tier system, approval workflows, maturity transitions, cache validation |
| **Episode Integration** | MEDIUM | Background processing, state persistence, lifecycle events |
| **Browser Automation E2E** | HIGH | Meta (Playwright testing Playwright), CDP complexity, permissions |
| **Device Capabilities** | HIGH | Real devices/emulators, permissions, platform-specific behavior |
| **Autonomous Coding** | HIGH | Git operations, checkpoint/rollback, wave-based parallel execution |

## Test Data Requirements

| Test Data Type | Purpose | Source |
|----------------|---------|--------|
| **Test Users** | Login, session management, permissions | Seed script or API fixtures |
| **Test Agents** | STUDENT/INTERN/SUPERVISED/AUTONOMOUS levels | Database seed with known agents |
| **Test Skills** | Marketplace, installation, workflows | Mock marketplace or curated skill list |
| **Test Episodes** | Graduation testing, recall verification | Pre-generated episodes with known outcomes |
| **Test Workflows** | Execution, DAG validation, composition | Simple workflows (no external deps) |
| **Test Projects** | Autonomous coding, git operations | Empty git repos for testing |
| **Error Scenarios** | Error guidance, resilience testing | Pre-configured error conditions |

## Sources

- **[Playwright WebSocket Testing Guide](https://www.cnblogs.com/hogwarts/p/19564781)** (Feb 2, 2026) - WebSocket frame capture patterns
- **[Playwright vs. Selenium: 2026 Architecture Review](https://dev.to/deepak_mishra_35863517037/playwright-vs-selenium-a-2026-architecture-review-347d)** (Jan 3, 2026) - WebSocket-based communication architecture
- **[Playwright Canvas Testing Guide](https://blog.csdn.net/qq_63708637/article/details/144345312)** (Sept 2025) - Canvas context acquisition, pixel verification
- **[E2E Testing Best Practices 2026](https://www.browserstack.com/guide/playwright-testing-best-practices)** (Nov 2025) - Risk-based testing, stable locators, explicit signals
- **[WebSocket Testing Best Practices](https://blog.csdn.net/weixin_41544125/article/details/157125620)** (Sept 2025) - Concurrent connections, security testing, load testing
- **[Continuous Testing Maturity Model](https://www.infoq.cn/article/testing-maturity-model)** (InfoQ/Alibaba Cloud) - UI automation at Level 2, API testing at Level 3
- **[Agent Browser with Playwright](https://claude.ai/best-practices)** (Feb 2026) - AI agent testing with semantic selectors
- **[n8n E2E Testing Guide](https://docs.n8n.io/e2e-testing)** (Dec 2025) - Cypress configuration, CI/CD integration
- **[Modern Authentication Platforms](https://github.com/agamm/awesome-developer-first)** (2026) - Auth0, Clerk, Kinde for testing auth
- **[React Native Skia Testing Strategy](https://blog.csdn.net/weixin_41544125/article/details/154321234)** (Oct 2025) - WebSocket bidirectional testing architecture
- **[NestJS WebSocket Testing](https://docs.nestjs.com/techniques/websocket)** (May 2025) - Official WebSocket module support
- **[Test Data Management Best Practices](https://www.browserstack.com/guide/test-data-management)** (2025) - Fixture patterns, data isolation
- **[Playwright Documentation](https://playwright.dev/docs/intro)** (Official) - API reference, best practices
- **[Atom Platform Documentation](/Users/rushiparikh/projects/atom/CLAUDE.md)** (Feb 20, 2026) - Agent governance, episodic memory, canvas system
- **[Atom Codebase](/Users/rushiparikh/projects/atom)** (Current) - Existing test patterns, playwright.config.ts

---

*Feature research for: E2E UI Testing with Playwright*
*Researched: February 23, 2026*
*Focus: Agent chat/streaming, canvas presentations, skills/workflows, user management*
