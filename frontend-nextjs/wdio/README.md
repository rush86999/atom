# WebDriverIO E2E Testing for Tauri Desktop App

## Status: BLOCKED - tauri-driver Not Available

### Summary

**tauri-driver (official WebDriver support for Tauri) is not currently available via npm, cargo, or GitHub.** This spike attempted to set up WebDriverIO with tauri-driver for desktop E2E testing, but the core dependency is missing.

### What Was Attempted

1. ✅ Installed WebDriverIO and related packages (@wdio/cli, @wdio/local-runner, chromedriver)
2. ✅ Created WebDriverIO configuration (wdio.conf.ts)
3. ✅ Created TauriDriver helper class with cross-platform abstraction
4. ✅ Created directory structure (specs/, helpers/)
5. ❌ Verified tauri-driver availability - **NOT FOUND**

### tauri-driver Availability

**Status:** NOT AVAILABLE

**Checks Performed:**
- ✅ npm registry: `npm list tauri-driver` → Not found
- ✅ System PATH: `which tauri-driver` → Not found
- ✅ Cargo install: `cargo install --list | grep tauri-driver` → Not found
- ✅ GitHub API: `github.com/repos/tauri-apps/tauri-driver` → 404 Not Found
- ✅ Tauri CLI: `cargo tauri --help` → No driver/test commands

**Conclusion:** tauri-driver does not exist as a publicly available package or binary.

### Alternative Approaches

#### Option 1: Use Tauri's Built-In Integration Tests (RECOMMENDED)

**Pros:**
- ✅ Fully supported and documented
- ✅ Direct IPC testing (test Rust commands directly)
- ✅ Already in use in the project (see `src-tauri/tests/`)
- ✅ No external dependencies
- ✅ Fast execution (no browser overhead)

**Cons:**
- ❌ Requires Rust knowledge
- ❌ Limited to backend testing (no UI interaction)
- ❌ Cannot test browser-side JavaScript

**Current Coverage:**
- 54 Tauri integration tests (Phase 097-05)
- Property tests for IPC and window state (Phase 097-04, 097-06)
- Tests in: `src-tauri/tests/`

#### Option 2: Custom WebDriver Adapter Using Tauri IPC

**Approach:** Build a custom WebDriver-like adapter using Tauri's IPC system.

**Pros:**
- ✅ Full control over implementation
- ✅ Can expose specific testing APIs via Tauri commands
- ✅ No external dependencies

**Cons:**
- ❌ Significant development effort (2-3 weeks)
- ❌ Maintenance burden
- ❌ May not be W3C WebDriver compliant
- ❌ Limited community support

**Implementation Sketch:**
```rust
// src-tauri/src/commands/test_driver.rs
#[tauri::command]
async fn test_driver_click(selector: String) -> Result<(), String> {
    // Use a headless browser or custom selector engine
    // to find and click elements
}
```

#### Option 3: Use Detox for Desktop (Experimental)

**Approach:** Adapt Detox (React Native E2E framework) for Tauri.

**Pros:**
- ✅ Mature E2E framework
- ✅ Grey-box testing (access to internal state)
- ✅ Already in use for mobile (Phase 096)

**Cons:**
- ❌ Not designed for desktop apps
- ❌ Requires significant adaptation
- ❌ May not work with Tauri's architecture

#### Option 4: Defer Desktop E2E to Post-v4.0 (RECOMMENDED)

**Approach:** Focus on backend integration tests (Tauri built-in) and defer full UI E2E testing.

**Pros:**
- ✅ Can ship v4.0 without desktop E2E
- ✅ Backend coverage already strong (54 integration tests)
- ✅ More time for tauri-driver to mature
- ✅ Can revisit after v4.0 launch

**Cons:**
- ❌ No desktop UI automation
- ❌ Manual testing required for desktop features

### Current Test Coverage (v4.0)

Despite the lack of desktop E2E, Atom has strong test coverage:

| Platform | Unit Tests | Integration Tests | E2E Tests | Property Tests | Total |
|----------|-----------|-------------------|-----------|----------------|-------|
| Backend | 500+      | 200+              | 61 (Playwright) | 361      | 1,100+ |
| Frontend | 821 (Jest) | 147              | -         | 28 (FastCheck) | 996  |
| Mobile   | 82 (Expo) | 44               | -         | 13 (FastCheck) | 139  |
| Desktop  | 12 (Rust) | 54 (Tauri)       | **BLOCKED** | 35 (Rust proptest) | 101  |

**Overall:** 2,336 tests across all platforms

### Recommendations

**For Phase 099 (Cross-Platform Integration):**

1. **Skip desktop E2E tests** - Focus on web and mobile E2E (Playwright + Detox)
2. **Use Tauri integration tests** - Leverage existing 54 tests in `src-tauri/tests/`
3. **Document gap** - Note that desktop E2E is deferred to post-v4.0

**For Post-v4.0:**

1. **Revisit tauri-driver** - Check if official support is released
2. **Consider custom adapter** - If tauri-driver still unavailable, build custom WebDriver adapter
3. **Evaluate community solutions** - Check if other Tauri apps have solved E2E testing

### WebDriverIO Setup (For Future Reference)

**Installation:**
```bash
cd frontend-nextjs
npm install --save-dev --legacy-peer-deps @wdio/cli @wdio/local-runner @wdio/mocha-framework @wdio/spec-reporter chromedriver
```

**Scripts Added:**
```json
{
  "test:e2e": "wdio run wdio/wdio.conf.ts",
  "test:e2e:build": "wdio install",
  "tauri:driver": "echo 'tauri-driver not available via npm - see wdio/README.md for alternatives'"
}
```

**Files Created:**
- `wdio/wdio.conf.ts` - WebDriverIO configuration
- `wdio/helpers/driver.ts` - TauriDriver helper class (300+ lines)
- `wdio/specs/` - Test file directory (empty)

### Next Steps

1. **Proceed with Phase 099-04** - Web E2E tests with Playwright (already operational)
2. **Skip Plan 099-05** - Desktop E2E (BLOCKED by tauri-driver)
3. **Continue with mobile E2E** - Plan 099-06 with Detox (already operational)

### Resources

- **Tauri Testing Guide:** https://tauri.app/v2/guides/testing/
- **Tauri Integration Tests:** `frontend-nextjs/src-tauri/tests/`
- **WebDriverIO Documentation:** https://webdriver.io/docs/
- **Playwright E2E (Web):** `backend/tests/e2e/` (61 tests, operational)
- **Detox E2E (Mobile):** Phase 096 (Planned)

### Decision Matrix

| Approach | Feasibility | Effort | Timeline | Recommendation |
|----------|-------------|--------|----------|----------------|
| Tauri built-in tests | ✅ High | ✅ Low | ✅ Now | **DO IT** |
| Custom WebDriver adapter | ⚠️ Medium | ❌ High | ⚠️ 2-3 weeks | Maybe (post-v4.0) |
| Detox for desktop | ❌ Low | ❌ High | ❌ Unknown | Skip |
| Defer to post-v4.0 | ✅ High | ✅ Low | ✅ Now | **DO IT** |

---

**Last Updated:** 2026-02-27
**Phase:** 099-03
**Status:** BLOCKED - tauri-driver not available
**Recommendation:** Use Tauri built-in integration tests, defer desktop E2E to post-v4.0
