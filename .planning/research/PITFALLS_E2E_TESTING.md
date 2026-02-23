# Domain Pitfalls: E2E UI Testing with Playwright

**Domain:** E2E UI Testing with Playwright (adding to existing production platform)
**Researched:** February 23, 2026
**Confidence:** MEDIUM

## Critical Pitfalls

### Pitfall 1: Brittle WebSocket/Stream Assertions

**What goes wrong:**
Tests fail intermittently when asserting on streaming LLM responses or WebSocket messages because they check UI state before async data arrives, or assume message ordering that isn't guaranteed. Tests pass 90% of the time but fail randomly in CI, eroding team trust in the test suite.

**Why it happens:**
Developers treat streaming/WebSocket communication like HTTP request-response pairs. They don't account for:
- Network latency variations in CI vs. local
- Message fragmentation (WebSocket frames can arrive in chunks)
- Race conditions between UI rendering and message handling
- Missing unique message identifiers for ordering verification

**How to avoid:**
1. **Never use fixed timeouts** (`page.waitForTimeout(5000)`) — use condition-based waits
2. **Add unique IDs to WebSocket messages** for precise tracking
3. **Buffer messages and assert on sets**, not sequences (unless order is critical)
4. **Use Playwright's auto-wait assertions** with proper selectors
5. **Create WebSocket helper utilities** for connection lifecycle management

```javascript
// ❌ BAD: Brittle timing-based assertion
await page.waitForTimeout(3000);
expect(await page.locator('.response').textContent()).toContain('AI response');

// ✅ GOOD: Condition-based assertion
await expect(page.locator('.response')).toContainText('AI response', { timeout: 10000 });
```

**Warning signs:**
- Tests failing with "element not found" or "timeout" errors intermittently
- Need to increase timeouts to make tests pass
- Tests pass locally but fail in CI
- `page.waitForTimeout()` appearing in test code

**Phase to address:**
Phase 1 (Foundation) — Build WebSocket testing utilities and assertion patterns from the start. Fixing brittle tests later requires rewriting entire suites.

---

### Pitfall 2: Test Data Pollution in Parallel Execution

**What goes wrong:**
When tests run in parallel (using pytest-xdist or Playwright workers), they modify shared database records, causing intermittent failures. Test A creates user "test@example.com", Test B tries to create the same user, one fails with "unique constraint violation". Tests that pass in serial execution fail randomly in parallel.

**Why it happens:**
Existing backend test data management works for serial tests but doesn't account for concurrent access. Developers assume database transactions isolate tests, but:
- Unique constraints violations occur before transaction commit
- Shared fixtures (seed data) aren't worker-isolated
- Cleanup hooks run at wrong times (after all tests, not per-worker)

**How to avoid:**
1. **Generate unique test data per worker** using timestamps/UUIDs
2. **Use database rollback in afterEach hooks** for complete isolation
3. **Create separate schemas per worker** if using PostgreSQL
4. **Run E2E tests against dedicated test database**, never production
5. **Implement proper test data lifecycle** in `beforeEach`/`afterEach`

```javascript
// ✅ GOOD: Unique test data per test
test('user registration', async ({ page }) => {
  const uniqueEmail = `test-${Date.now()}-${Math.random()}@example.com`;
  await page.fill('#email', uniqueEmail);
  // ... rest of test
});
```

**Warning signs:**
- Tests pass when run singly but fail in full suite
- "Unique constraint" or "duplicate key" errors in test logs
- Need to run tests with `--workers=1` to make them pass
- Tests interfering with each other's state

**Phase to address:**
Phase 1 (Foundation) — Establish test data isolation strategy before writing tests. Phase 3 (Critical Flows) — Verify parallel execution doesn't cause pollution.

---

### Pitfall 3: Over-Specified Selectors Breaking on UI Changes

**What goes wrong:**
Tests use CSS selectors like `#main-content > div.container > button:nth-child(3)` that break when frontend team refactors DOM structure. Tests fail even though functionality is correct, creating false positives that waste development time.

**Why it happens:**
Developers use Playwright's code generator or browser DevTools to copy selectors, which capture implementation details. When UI changes (CSS classes, DOM nesting), tests fail despite no functional regression. This is the #1 cause of E2E test maintenance burden.

**How to avoid:**
1. **Prefer user-visible attributes** — `getByRole()`, `getByText()`, `getByLabel()`, `getByTestId()`
2. **Never use structural selectors** — `nth-child()`, CSS classes as selectors
3. **Add `data-testid` attributes** to critical UI elements (not every element)
4. **Test user outcomes, not implementation** — "can user submit form?" not "button has class .btn-primary"
5. **Review selector brittleness** in code review

```javascript
// ❌ BAD: Brittle structural selector
await page.click('#main-content > div > button:nth-child(3)');

// ❌ BAD: CSS class selector
await page.click('.btn-primary.submit-btn');

// ✅ GOOD: User-visible attribute
await page.click('button', { name: 'Submit' });

// ✅ GOOD: Test ID (stable, intentional)
await page.click('[data-testid="submit-button"]');
```

**Warning signs:**
- Tests breaking after frontend refactors with no functional changes
- Selector chains longer than 3 levels deep
- `nth-child()`, CSS classes in test selectors
- Frequent test updates due to UI changes

**Phase to address:**
Phase 1 (Foundation) — Establish selector guidelines and add test IDs to core components. Phase 2 (Component Tests) — Review all selectors for brittleness.

---

### Pitfall 4: Memory Leaks and Resource Exhaustion in Docker

**What goes wrong:**
Playwright tests crash in CI/Docker with "Chromium exited with code 139 (SIGSEGV)" or "JavaScript heap out of memory". Tests run fine locally but fail in GitHub Actions/Docker, especially when running many tests in parallel. CI runners become unresponsive or OOM kill.

**Why it happens:**
Each browser instance consumes 150-250MB RAM. Running 20+ tests in parallel exhausts 8GB CI machines. Chromium requires:
- Shared memory (`/dev/shm`) — crashes without sufficient allocation
- IPC host mode — zombie processes accumulate without `--init`
- Proper context/page cleanup — unclosed pages leak memory

**How to avoid:**
1. **Always use Docker flags:** `--ipc=host --shm-size=2gb --init`
2. **Explicitly close pages in afterEach hooks:** `await page.close()`
3. **Limit workers based on memory:** 1 worker per 512MB RAM minimum
4. **Set Node.js memory limit:** `NODE_OPTIONS=--max-old-space-size=4096`
5. **Use Playwright's isolated mode** for automatic cleanup

```yaml
# docker-compose.yml for E2E tests
services:
  playwright-tests:
    image: mcr.microsoft.com/playwright:v1.56.1-noble
    ipc: host  # CRITICAL: Prevents Chromium crashes
    shm_size: '2gb'  # CRITICAL: Shared memory for browser
    init: true  # Prevents zombie processes
    environment:
      - NODE_OPTIONS=--max-old-space-size=4096
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2.0'
```

**Warning signs:**
- Random Chromium crashes in CI but not locally
- "JavaScript heap out of memory" errors
- CI runners becoming slow or unresponsive after test runs
- Need to restart CI runners between builds

**Phase to address:**
Phase 4 (CI Integration) — Configure Docker and CI resources correctly. This is purely infrastructure, not test code.

---

### Pitfall 5: False Negatives from Testing Implementation Details

**What goes wrong:**
Tests verify internal implementation (function calls, state updates) rather than user-facing outcomes. When developers refactor code (no behavior change), tests fail. Team loses trust in tests, starts ignoring failures, or removes tests entirely.

**Why it happens:**
Developers write tests that are too granular, checking implementation details like:
- Specific CSS classes instead of visual state
- Internal component state instead of rendered output
- Function/method calls instead of user interactions
- API response structure instead of UI feedback

**How to avoid:**
1. **Test user journeys, not code paths** — "Can user log in?" not "login() called with correct args"
2. **Use black-box testing** — interact only via UI, not internal APIs
3. **Focus on critical paths** — login, checkout, core workflows
4. **Avoid comprehensive coverage** — 2025 research shows removing E2E tests improved outcomes by 16.7%
5. **Use component tests** for implementation details, E2E for integration

**Warning signs:**
- Tests failing after code refactors with no behavior changes
- Tests mocking internal functions or checking state directly
- More E2E tests than unit/integration tests
- Test suite taking >30 minutes to run

**Phase to address:**
Phase 2 (Component Tests) — Use component tests for detailed validation. Phase 3 (Critical Flows) — Keep E2E focused on user journeys only.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| **Hardcoded timeouts** (`waitForTimeout`) | Tests pass quickly | Flaky tests, random failures, lost trust | NEVER — use condition-based waits |
| **Copying selectors from DevTools** | Fast test authoring | Tests break on UI changes, high maintenance | NEVER — use role/text/testId selectors |
| **Running tests serially** (`--workers=1`) | Avoids data pollution issues | Slow feedback loops (hours vs minutes) | Only in Phase 1 for debugging |
| **Using production database for E2E** | No test data setup needed | Risk of data corruption, privacy violations, slow tests | NEVER — use dedicated test DB |
| **Skipping cleanup hooks** | Faster test development | Test pollution, flaky failures, hard to debug | NEVER — always cleanup in afterEach |
| **Testing edge cases in E2E** | High coverage numbers | Slow test suite, better tested at unit level | Only for critical user-facing edge cases |
| **Shared test fixtures across files** | Less setup code | Test interdependence, hard to parallelize | Only for read-only fixtures (e.g., static data) |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **PostgreSQL** | Using production database or shared test DB without isolation | Use transaction rollback per test or separate schemas per worker |
| **Redis/WebSocket** | Assuming immediate message delivery, not testing reconnection | Test connection lifecycle, message buffering, reconnection logic |
| **Docker Compose** | Insufficient shared memory (`shm_size`), missing `--ipc=host` | Always use `--ipc=host --shm-size=2gb --init` flags |
| **GitHub Actions** | Running all browsers in parallel without resource limits | Limit workers to 4, set memory limits, use caching for dependencies |
| **FastAPI Backend** | Starting backend before migrations complete | Add health check endpoint, wait for `/health/ready` before starting tests |
| **Next.js Dev Server** | Not waiting for build to complete, race conditions | Use `wait-on` or health checks, ensure port is listening |
| **Playwright Docker Image** | Using `:latest` tag, version drift | Pin to specific version: `mcr.microsoft.com/playwright:v1.56.1-noble` |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| **Sequential test execution** | Test suite takes 2+ hours, blocks deployments | Run tests in parallel (workers = CPU cores / 2) | At 50+ tests |
| **No test data cleanup** | Database grows to GBs, tests slow down over time | Transaction rollback or truncation in afterEach | After 100+ test runs |
| **Browser instances per test** | Memory exhaustion in CI, OOM kills | Reuse browser context, limit concurrent pages | At 20+ parallel tests |
| **Screenshot/video on every test** | Disk space exhausted, slow uploads | Only on failure, or critical tests only | At 100+ tests |
| **Waiting for full page loads** | Tests unnecessarily slow (30s+ per test) | Use network idle detection or specific element waits | With SPAs always |
| **Not using test retries** | Flaky infrastructure failures block CI | Use `retries: 2` in CI, `retries: 0` locally | In CI environments |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| **Hardcoded API keys in test files** | Credentials leaked in git history | Use environment variables, `.env.test` file in `.gitignore` |
| **Testing against production URLs** | Accidental data deletion, privacy violations | Fail fast if `NODE_ENV=production` in test runs, use `BASE_URL` env var |
| **Real user credentials in tests** | Account lockouts, compliance violations | Use test-only accounts, auto-create test users via API |
| **Disabling security headers for tests** | False sense of security, production vulnerable | Test with security headers enabled, use test-specific auth tokens |
| **Exposing test reports publicly** | Internal URLs, user data leaked | Store test reports as CI artifacts (authenticated), not public S3 |
| **Not cleaning up test users** | Database clutter, potential access via forgotten accounts | Auto-delete test users in afterEach, mark with `is_test=True` flag |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| **Tests blocking deploys for minor UI issues** | Slow feature delivery, team ignores tests | Separate smoke tests (block deploy) from full suite (non-blocking) |
| **Poor test failure messages** | Hours spent debugging what failed | Use custom matchers, include screenshots/videos on failure |
| **Tests running during peak dev hours** | Slow development machines | Run full E2E only in CI, use targeted tests locally |
| **No test results visualization** | Team doesn't know test health | Publish HTML reports, track flakiness metrics over time |
| **Silent test failures (try/catch swallowing errors)** | False sense of confidence | Never catch test errors without re-throwing, use `test.fail()` for expected failures |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **WebSocket Connection Testing:** Often missing reconnection logic, message ordering verification — verify tests cover connection lifecycle (connect, disconnect, reconnect)
- [ ] **Streaming Response Validation:** Often missing partial message handling, buffer overflow checks — verify tests handle incomplete chunks, large payloads
- [ ] **Parallel Test Execution:** Often missing data pollution detection, worker isolation — verify `pytest -n auto` doesn't cause random failures
- [ ] **CI/CD Integration:** Often missing Docker memory limits, timeout configurations — verify tests pass in GitHub Actions with same reliability as local
- [ ] **Test Data Cleanup:** Often missing cleanup in error paths (test fails before afterEach) — verify database is clean even after test failures
- [ ] **Browser Cleanup:** Often missing page.close() in tests — verify no zombie Chrome processes after test run
- [ ] **Accessibility Testing:** Often missing from E2E entirely — verify `getByRole()` works, add basic a11y checks
- [ ] **Network Failure Simulation:** Often missing happy-path-only tests — verify app handles WebSocket disconnects, API failures gracefully
- [ ] **Mobile/Viewport Testing:** Often missing responsive design verification — verify tests work on mobile viewport (375x667)
- [ ] **Test Report Artifacts:** Often missing screenshots/videos on failure — verify CI uploads artifacts for debugging

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| **Brittle selectors causing failures** | MEDIUM | 1. Run Trace Viewer on failed test (`npx playwright show-trace`) <br> 2. Identify broken selectors <br> 3. Replace with `getByRole()`/`getByText()` <br> 4. Add missing `data-testid` attributes to frontend |
| **Test data pollution** | HIGH | 1. Identify conflicting tests (run with `--workers=1`) <br> 2. Add unique data generation to all tests <br> 3. Implement transaction rollback cleanup <br> 4. Re-enable parallel execution |
| **Docker memory exhaustion** | LOW | 1. Add Docker resource limits (memory, shm_size) <br> 2. Reduce worker count <br> 3. Add explicit page.close() in tests <br> 4. Monitor with `docker stats` |
| **WebSocket test flakiness** | HIGH | 1. Add unique message IDs <br> 2. Replace timeouts with condition-based waits <br> 3. Add connection retry logic in tests <br> 4. Use mock WebSocket server for deterministic testing |
| **CI timeout failures** | MEDIUM | 1. Increase timeout in playwright.config <br> 2. Split test suite into smaller jobs <br> 3. Use `--shard` to distribute across runners <br> 4. Optimize slow tests (parallelize, reduce waits) |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| **Brittle WebSocket assertions** | Phase 1 (Foundation) — Build WebSocket helper utilities | Phase 2 — Run tests 100 times, verify 0% flakiness |
| **Test data pollution** | Phase 1 (Foundation) — Establish data isolation strategy | Phase 3 — Run full suite with `--workers=4`, verify no conflicts |
| **Over-specified selectors** | Phase 1 (Foundation) — Define selector guidelines + add test IDs | Phase 2 — Refactor frontend, verify tests still pass |
| **Docker memory leaks** | Phase 4 (CI Integration) — Configure Docker resources correctly | Phase 4 — Run full suite 10x in CI, verify no OOM |
| **False negatives (testing implementation)** | Phase 2 (Component Tests) — Use component tests for details | Phase 3 — Review E2E tests, remove implementation checks |
| **Slow test execution** | Phase 3 (Critical Flows) — Limit E2E to user journeys only | Phase 4 — Measure suite duration, target <15 minutes |
| **Poor failure reporting** | Phase 2 (Component Tests) — Add screenshots/videos on fail | Phase 3 — Trigger intentional failure, review artifacts |
| **CI integration issues** | Phase 4 (CI Integration) — Set up GitHub Actions properly | Phase 4 — Run 20 consecutive builds, verify all pass |

## Sources

### WebSocket & Streaming Testing
- [Playwright处理WebSocket的测试方法](https://www.cnblogs.com/hogwarts/p/19564781) (Feb 2026) — MEDIUM confidence, comprehensive WebSocket testing patterns
- [WebSocket 测试要点：实时应用的策略与代码](https://m.blog.csdn.net/hacker_laoyi/article/details/154990729) (Nov 2025) — MEDIUM confidence, message ordering and lifecycle testing
- [5步掌握WebSocket流式处理](https://m.blog.csdn.net/gitblog_00668/article/details/155090347) (Dec 2025) — LOW confidence, not verified with official docs

### Test Reliability & False Positives/Negatives
- [app.build: Production Framework for Agentic Prompt-to-Code](https://arxiv.org/html/2509.03310v2) (Sept 2025) — HIGH confidence, peer-reviewed research showing E2E tests can harm outcomes
- [7 End-to-End Testing Best Practices in 2025](https://research.aimultiple.com/end-to-end-end-to-end-testing-best-practices/) (Jan 2025) — MEDIUM confidence, industry survey
- [How to reduce false failure in Test Automation](https://www.browserstack.com/guide/automate-failure-detection-in-qa-workflow) (2024) — MEDIUM confidence, practical strategies

### Parallel Execution & Test Isolation
- [Playwright Test Execution Strategies](https://www.cnblogs.com/hogwarts/p/19457056) (2025) — MEDIUM confidence, parallel testing configuration
- [Playwright并行测试配置与优化技巧](https://juejin.cn/post/7589093939656081460) (Aug 2025) — LOW confidence, needs verification
- [Using Persistent Context in Playwright](https://www.browserstack.com/guide/playwright-persistent-context) (2024) — HIGH confidence, official documentation

### Docker & CI Integration
- [Official Playwright Docker Documentation](https://playwright.dev/docs/docker) — HIGH confidence, authoritative source
- [Playwright Performance Optimization Guide](https://blog.csdn.net/weixin_46281581/article/details/145792224) (March 2025) — MEDIUM confidence, memory leak patterns
- [CI/CD Test Data Cleanup Techniques](https://blog.itpub.net/70034708/viewspace-3078561/) (March 2025) — MEDIUM confidence, cleanup strategies

### Test Data Management
- [实战技巧：CI/CD 中有效清理测试数据](https://m.blog.csdn.net/deerxiaolua/article/details/146006139) (March 2025) — MEDIUM confidence, practical cleanup patterns
- [5种方法清理接口测试后的测试数据](https://m.blog.csdn.net/okcross0/article/details/141467298) (Aug 2024) — LOW confidence, needs verification
- [4种处理端到端测试数据的方法](https://www.163.com/dy/article/HFL32OOH0553SRCA.html) (2024) — LOW confidence, aggregation source

### Best Practices & Selector Strategies
- [The Complete Playwright End-to-End Story](https://developer.microsoft.com/blog/the-complete-playwright-end-to-end-story-tools-ai-and-real-world-workflows) (2025) — HIGH confidence, official Microsoft guidance
- [Playwright Testing Best Practices](https://www.cnblogs.com/longmo666/articles/18594972.html) (2025) — LOW confidence, community article

---

*Pitfalls research for: E2E UI Testing with Playwright (v3.1)*
*Researched: February 23, 2026*
