---
phase: 05-coverage-quality-validation
plan: GAP_CLOSURE-05
subsystem: desktop-testing
type: execute
wave: 2
depends_on: []
files_modified:
  - frontend-nextjs/src-tauri/src/websocket.rs
  - frontend-nextjs/src-tauri/src/commands.rs
  - frontend-nextjs/src-tauri/src/main.rs
  - frontend-nextjs/src-tauri/src/auth.rs
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "Desktop app achieves 80% coverage (from 74% baseline)"
    - "WebSocket reconnection tests added (currently 60% coverage)"
    - "Error path tests for main.rs setup added"
    - "Network timeout tests for commands added"
    - "Invalid token refresh scenarios tested"
  artifacts:
    - path: "frontend-nextjs/src-tauri/src/websocket.rs"
      provides: "WebSocket module with 80%+ coverage"
      contains: "reconnection logic tests"
    - path: "frontend-nextjs/src-tauri/src/commands.rs"
      provides: "Commands module with 80%+ coverage"
      contains: "network timeout tests"
    - path: "frontend-nextjs/src-tauri/src/main.rs"
      provides: "Main setup with error path tests"
      contains: "setup error handling tests"
    - path: "frontend-nextjs/src-tauri/src/auth.rs"
      provides: "Auth module with token refresh tests"
      contains: "invalid token refresh scenarios"
  key_links:
    - from: "frontend-nextjs/src-tauri/Cargo.toml"
      to: "cargo-tarpaulin coverage"
      via: "tarpaulin with 80% threshold"
      pattern: "cargo-tarpaulin.*0\\.27\\.1"
    - from: "frontend-nextjs/src-tauri/tests/websocket_test.rs"
      to: "frontend-nextjs/src-tauri/src/websocket.rs"
      via: "WebSocket reconnection test coverage"
      pattern: "test_reconnect|test_connection_lost"
---

<objective>
Add desktop Rust tests to increase coverage from 74% to 80%.

**Purpose:** Desktop app currently has 74% coverage, 6% gap to 80% target. Key gaps: WebSocket reconnection at 60% coverage, error paths in main.rs, network timeout handling in commands, and invalid token refresh scenarios. Tauri linking issues prevent local tarpaulin execution on macOS ARM, but tests can still be written and run via CI/CD.

**Output:** Added Rust tests for WebSocket reconnection, main.rs error paths, command network timeouts, and auth token refresh edge cases. Coverage increases from 74% to 80%+.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@.planning/phases/05-coverage-quality-validation/05-07-SUMMARY.md
@.planning/phases/05-coverage-quality-validation/05-VERIFICATION.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/STATE.md
@frontend-nextjs/src-tauri/src/websocket.rs
@frontend-nextjs/src-tauri/src/commands.rs
@frontend-nextjs/src-tauri/src/main.rs
@frontend-nextjs/src-tauri/src/auth.rs
@frontend-nextjs/src-tauri/Cargo.toml
@frontend-nextjs/.github/workflows/desktop-coverage.yml
</context>

<tasks>

<task type="auto">
  <name>Add WebSocket reconnection tests</name>
  <files>frontend-nextjs/src-tauri/tests/websocket_test.rs</files>
  <action>
    Create or enhance WebSocket tests to cover reconnection logic, increasing websocket.rs coverage from 60% to 80%+.

    Add tests for:
    1. Connection loss detection
    2. Automatic reconnection with exponential backoff
    3. Reconnection failure handling (max retries exceeded)
    4. Reconnection success after temporary failure
    5. WebSocket state transitions during reconnection
    6. Message queuing during disconnection
    7. Heartbeat/keepalive timeout handling

    Use the existing test structure in frontend-nextjs/src-tauri/tests/ directory.

    Pattern for WebSocket tests:
    ```rust
    #[cfg(test)]
    mod tests {
        use super::*;
        // ... test implementations
    }
    ```

    Target 100+ lines of new tests for websocket reconnection scenarios.
  </action>
  <verify>
    Run: cd frontend-nextjs/src-tauri && cargo test --test websocket_test --lib

    Expected: New tests pass, websocket.rs coverage increases from 60% to 80%+
  </verify>
  <done>
    WebSocket reconnection tests added. websocket.rs coverage increases by 20+ percentage points.
  </done>
</task>

<task type="auto">
  <name>Add error path tests for main.rs setup</name>
  <files>frontend-nextjs/src-tauri/tests/main_test.rs</files>
  <action>
    Create tests for main.rs setup error handling paths.

    Add tests for:
    1. App initialization failure scenarios
    2. Window creation error handling
    3. Plugin initialization failures
    4. Configuration file errors (missing/corrupted config)
    5. Resource loading failures
    6. Cleanup on error conditions

    Note: Some main.rs setup is difficult to test directly. Use integration tests where possible and document any non-testable paths.

    Target 80+ lines of tests for error paths.
  </action>
  <verify>
    Run: cd frontend-nextjs/src-tauri && cargo test --test main_test --lib

    Expected: New tests pass, main.rs coverage increases for error paths
  </verify>
  <done>
    Main.rs error path tests added. Coverage increases for setup error handling.
  </done>
</task>

<task type="auto">
  <name>Add network timeout tests for commands</name>
  <files>frontend-nextjs/src-tauri/tests/commands_test.rs</files>
  <action>
    Create tests for network timeout handling in Tauri commands.

    Add tests for:
    1. Backend API request timeout
    2. Slow response handling
    3. Request retry logic
    4. Cancellation during network request
    5. Partial response handling
    6. Network unavailable scenarios

    Mock the HTTP client to simulate timeout conditions.

    Target 100+ lines of tests for network timeout scenarios in commands.rs.
  </action>
  <verify>
    Run: cd frontend-nextjs/src-tauri && cargo test --test commands_test --lib

    Expected: New tests pass, commands.rs coverage increases from 70% to 80%+
  </verify>
  <done>
    Network timeout tests added. commands.rs coverage increases by 10+ percentage points.
  </done>
</task>

<task type="auto">
  <name>Add invalid token refresh scenarios for auth</name>
  <files>frontend-nextjs/src-tauri/tests/auth_test.rs</files>
  <action>
    Create tests for invalid token refresh scenarios in auth.rs.

    Add tests for:
    1. Expired refresh token handling
    2. Malformed access token refresh
    3. Revoked token refresh attempt
    4. Refresh endpoint error responses (401, 403, 500)
    5. Concurrent refresh requests
    6. Token refresh during logout

    Target 80+ lines of tests for auth edge cases.
  </action>
  <verify>
    Run: cd frontend-nextjs/src-tauri && cargo test --test auth_test --lib

    Expected: New tests pass, auth.rs coverage increases for token refresh paths
  </verify>
  <done>
    Invalid token refresh scenario tests added. auth.rs coverage increases for edge cases.
  </done>
</task>

</tasks>

<verification>
Overall verification steps:
1. Run desktop tests: cd frontend-nextjs/src-tauri && cargo test --lib
2. If on x86_64, run coverage: ./coverage.sh
3. If on ARM or with linking issues, push to GitHub and verify CI/CD workflow runs
4. Check .github/workflows/desktop-coverage.yml workflow results
5. Verify coverage exceeds 80% overall

Note: Local tarpaulin may fail on macOS ARM due to Tauri linking issues. CI/CD workflow uses x86_64 runners which work correctly.
</verification>

<success_criteria>
Desktop app achieves 80% coverage:
- websocket.rs: 80%+ coverage (from 60%)
- commands.rs: 80%+ coverage (from 70%)
- main.rs: Error paths tested
- auth.rs: Token refresh edge cases tested
- Overall desktop coverage: 80%+ (from 74%)
- CI/CD workflow passes with 80% threshold
</success_criteria>

<output>
After completion, create `.planning/phases/05-coverage-quality-validation/05-GAP_CLOSURE-05-SUMMARY.md`
</output>
