# Desktop Coverage Guide

## Overview

Atom Desktop is a Tauri-based desktop application built with Rust that brings AI-powered automation to Windows, macOS, and Linux. This guide covers desktop testing infrastructure, coverage tracking, and platform-specific testing patterns.

**Phase 140-143:** Desktop coverage baseline and expansion targeting 80% code coverage across desktop-specific code paths.

## Current Baseline

**Baseline Status:** Phase 140 infrastructure complete, baseline measurement pending

- **Coverage Infrastructure:** ✅ Complete (tarpaulin.toml, coverage.sh, baseline tracking)
- **Platform-Specific Tests:** ✅ Complete (21 tests for conditional compilation and helpers)
- **Documentation:** 🔄 In progress (this guide)
- **CI/CD Integration:** 🔄 Pending (desktop-coverage.yml workflow)

**Expected Baseline:** TBD (will be measured in CI/CD on x86_64 runner)

**Target:** 80% coverage by Phase 142

## Coverage Gaps

Based on initial code analysis of `src/main.rs` (1757 lines), identified coverage gaps include:

### File Dialog Operations
- **Lines:** 24-165 (open_file_dialog, open_folder_dialog, save_file_dialog)
- **Gaps:** Error handling paths, filter edge cases, cancellation scenarios
- **Platform Differences:** Windows vs macOS vs Linux file picker dialogs

### Device Capabilities
- **Lines:** 200-450 (camera, screen recording, location services)
- **Gaps:** Platform-specific ffmpeg backends, permission handling, device enumeration
- **Windows:** DirectShow/Vidéo for Windows APIs
- **macOS:** AVFoundation framework
- **Linux:** V4L2 (Video4Linux2) APIs

### System Tray Implementation
- **Lines:** 500-650 (tray icon, menu items, click handlers)
- **Gaps:** Tray icon rendering, menu state management, click event routing
- **Platform Differences:** Taskbar vs Dock vs panel applets

### IPC Command Handlers
- **Lines:** 700-1200 (Tauri commands, event emission, state management)
- **Gaps:** Async command handling, error propagation, state synchronization
- **Critical Paths:** File operations, shell commands, system info queries

### Error Handling
- **Lines:** Throughout main.rs
- **Gaps:** Panic recovery, Result error variants, user-friendly error messages
- **Priority:** High (desktop stability depends on robust error handling)

## Quick Start

### Local Coverage Generation

```bash
cd frontend-nextjs/src-tauri

# Generate HTML coverage report (default)
./coverage.sh

# Explicit HTML generation
./coverage.sh --html

# Terminal output only
./coverage.sh --stdout

# Baseline measurement (Phase 140)
./coverage.sh --baseline
```

### Viewing Coverage Reports

After running `./coverage.sh`, open the HTML report:

```bash
# Default report location
open coverage-report/index.html  # macOS
xdg-open coverage-report/index.html  # Linux
start coverage-report/index.html  # Windows
```

**HTML Report Features:**
- Click on files to see line-by-line coverage
- Red highlighting: uncovered lines
- Green highlighting: covered lines
- Yellow highlighting: partially covered branches

### CI/CD Coverage Reports

Coverage reports are automatically generated on push to `main` or `develop` branches:

1. Navigate to the Actions tab in GitHub
2. Click on the "Desktop Coverage" workflow run
3. Scroll to "Artifacts" section
4. Download `desktop-coverage` artifact
5. Extract and open `index.html` in your browser

## Configuration

### tarpaulin.toml Configuration

The `tarpaulin.toml` file provides centralized coverage configuration:

```toml
[exclude-files]
# Exclude test files from coverage calculations
patterns = ["tests/*", "*/tests/*"]

[report]
# Output formats: HTML for visual inspection, JSON for baseline tracking
out = ["Html", "Json"]
output-dir = "coverage-report"

[features]
# Coverage threshold for future enforcement (Phase 142)
# Phase 140: informational only (baseline measurement)
coverage_threshold = 80

[engine]
# Use ptrace for compatibility across platforms
default = "ptrace"
```

**Configuration Options:**

| Option | Value | Purpose |
|--------|-------|---------|
| `exclude-files` | `tests/*`, `*/tests/*` | Exclude test code from coverage calculations |
| `out` | `Html`, `Json` | Generate visual HTML reports and machine-readable JSON |
| `output-dir` | `coverage-report` | Directory for coverage reports |
| `coverage_threshold` | `80` | Target percentage (informational in Phase 140, enforced in Phase 142) |
| `default` | `ptrace` | Tarpaulin engine for cross-platform compatibility |

### Customizing Coverage Thresholds

To adjust coverage thresholds for specific modules:

```toml
[coverage-thresholds]
# Per-module thresholds (future enhancement)
main.rs = 80
platform_specific/windows.rs = 70
platform_specific/macos.rs = 70
platform_specific/linux.rs = 70
```

## Test Organization

### Directory Structure

```
frontend-nextjs/src-tauri/tests/
├── platform_specific/
│   ├── mod.rs                 # Module declarations with #[cfg] gates
│   ├── windows.rs             # Windows-specific tests (Phase 141)
│   ├── macos.rs               # macOS-specific tests (Phase 141)
│   ├── linux.rs               # Linux-specific tests (Phase 141)
│   ├── cross_platform.rs      # Cross-platform validation tests
│   └── conditional_compilation.rs  # cfg! macro tests (✅ complete)
├── helpers/
│   ├── mod.rs                 # Helper module declarations
│   └── platform_helpers.rs    # Platform detection utilities (✅ complete)
├── coverage/
│   ├── mod.rs                 # Baseline tracking module (✅ complete)
│   └── coverage_baseline_test.rs  # Baseline tests (✅ complete)
└── cross_platform_validation_test.rs  # Existing cross-platform tests
```

### Platform-Specific Module Pattern

Use `#[cfg(target_os = "...")]` attributes for compile-time platform filtering:

```rust
// platform_specific/mod.rs

#[cfg(target_os = "windows")]
pub mod windows;

#[cfg(target_os = "macos")]
pub mod macos;

#[cfg(target_os = "linux")]
pub mod linux;

// Cross-platform modules (run on all platforms)
pub mod cross_platform;
pub mod conditional_compilation;
```

**Benefits:**
- Compile-time platform detection (no runtime overhead)
- Tests only run on matching platforms (skipped elsewhere)
- Clean test output (no "not implemented" errors)

### Test Naming Conventions

- **Windows-specific:** `test_windows_file_dialog_open()`, `test_windows_taskbar_visibility()`
- **macOS-specific:** `test_macos_menu_bar_creation()`, `test_macos_dock_integration()`
- **Linux-specific:** `test_linux_file_picker_xdg()`, `test_linux_window_manager_detect()`
- **Cross-platform:** `test_file_dialog_basic()`, `test_tray_icon_click()`

## Platform-Specific Patterns

### Conditional Compilation with #[cfg]

Use `#[cfg]` attributes for compile-time platform filtering:

```rust
#[cfg(target_os = "windows")]
#[test]
fn test_windows_file_dialog_open() {
    // Windows-specific test code
    assert_eq!(get_platform_separator(), "\\");
}

#[cfg(target_os = "macos")]
#[test]
fn test_macos_menu_bar_creation() {
    // macOS-specific test code
    assert_eq!(get_platform_separator(), "/");
}

#[cfg(target_os = "linux")]
#[test]
fn test_linux_file_picker_xdg() {
    // Linux-specific test code
    assert_eq!(get_platform_separator(), "/");
}
```

### Runtime Platform Detection with cfg!

Use `cfg!` macro for runtime platform checks in cross-platform tests:

```rust
#[test]
fn test_platform_detection_logic() {
    let platform = if cfg!(target_os = "windows") {
        "windows"
    } else if cfg!(target_os = "macos") {
        "macos"
    } else if cfg!(target_os = "linux") {
        "linux"
    } else {
        "unknown"
    };

    // Platform-specific assertions
    if cfg!(target_os = "windows") {
        assert_eq!(get_platform_separator(), "\\");
    } else {
        assert_eq!(get_platform_separator(), "/");
    }
}
```

### Combining Conditions with any/all/not

```rust
#[cfg(any(target_os = "windows", target_os = "macos"))]
#[test]
fn test_native_dialogs() {
    // Test Windows and macOS native dialogs
}

#[cfg(all(target_os = "linux", target_arch = "x86_64"))]
#[test]
fn test_linux_x86_64_specific() {
    // Test Linux x86_64-specific behavior
}

#[cfg(not(target_os = "windows"))]
#[test]
fn test_unix_path_handling() {
    // Test Unix path handling (macOS + Linux)
}
```

## Helper Utilities

### Platform Helpers Module

The `tests/helpers/platform_helpers.rs` module provides utility functions:

```rust
use helpers::platform_helpers::*;

// Get current platform string
let platform = get_current_platform(); // "windows", "macos", "linux", "unknown"

// Platform-specific assertions
cfg_assert("macos"); // Panics if not on macOS

// Platform-specific paths
let temp_dir = get_temp_dir();
let separator = get_platform_separator(); // "\\" on Windows, "/" on Unix
```

### Helper Functions Reference

| Function | Return Type | Purpose |
|----------|-------------|---------|
| `get_current_platform()` | `&'static str` | Returns "windows", "macos", "linux", or "unknown" |
| `is_platform(expected: &str)` | `bool` | Compares current platform to expected string |
| `cfg_assert(platform: &str)` | `()` | Panics if not on specified platform |
| `get_temp_dir()` | `PathBuf` | Returns platform-specific temp directory |
| `get_platform_separator()` | `&'static str` | Returns path separator ("\\" or "/") |

### Usage Example

```rust
#[test]
fn test_temp_directory_writable() {
    let temp_dir = get_temp_dir();

    // Create a test file
    let test_file = temp_dir.join("atom_test.txt");
    fs::write(&test_file, b"test content").unwrap();

    // Verify file exists
    assert!(test_file.exists());

    // Cleanup
    fs::remove_file(&test_file).unwrap();
}
```

## Coverage Targets

### Phase Goals

| Phase | Target | Focus Areas |
|-------|--------|-------------|
| **Phase 140** | Baseline | Infrastructure, measurement, documentation |
| **Phase 141** | +20-30% | Platform-specific tests (Windows, macOS, Linux) |
| **Phase 142** | +30-40% | IPC commands, error handling, state management |
| **Phase 143** | 80% overall | Edge cases, integration tests, final verification |

### Baseline vs Target

**Current Baseline:** TBD (will be measured in CI/CD)

**Target:** 80% coverage by Phase 142

**Gap Analysis:**
- If baseline is 20%: need +60 percentage points
- If baseline is 30%: need +50 percentage points
- If baseline is 40%: need +40 percentage points

### Priority Files for Coverage

**High Priority (Business Critical):**
1. `src/main.rs` - Core application logic, IPC handlers
2. Platform-specific file dialogs
3. Device capabilities (camera, screen recording, location)
4. System tray implementation

**Medium Priority (Frequently Used):**
1. Window management (minimize, maximize, close)
2. File system operations (read, write, watch)
3. Shell command execution
4. System information queries

**Lower Priority (Edge Cases):**
1. Error recovery paths
2. Performance optimization branches
3. Deprecated feature compatibility

## CI/CD Integration

### GitHub Actions Workflow

The `.github/workflows/desktop-coverage.yml` workflow generates coverage reports on every push:

```yaml
name: Desktop Coverage

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  coverage:
    runs-on: ubuntu-latest  # x86_64 for tarpaulin compatibility
    timeout-minutes: 15

    steps:
      - uses: actions/checkout@v4

      - uses: actions-rust-lang/setup-rust-toolchain@v1

      - name: Install tarpaulin
        run: cargo install cargo-tarpaulin

      - name: Generate coverage
        run: |
          cd frontend-nextjs/src-tauri
          cargo tarpaulin --config tarpaulin.toml --out Html --output-dir coverage-report

      - name: Upload coverage artifact
        uses: actions/upload-artifact@v4
        with:
          name: desktop-coverage
          path: frontend-nextjs/src-tauri/coverage-report/
          retention-days: 30
```

### Coverage Report Artifacts

Coverage reports are stored as GitHub Actions artifacts:

- **Artifact Name:** `desktop-coverage`
- **Retention:** 30 days
- **Contents:** `index.html`, `coverage.json`, `cobertura.xml`
- **Download:** Actions tab → Workflow run → Artifacts section

### Baseline Tracking

Baseline data is tracked in `coverage/baseline.json`:

```json
{
  "baseline_coverage": 0.0,
  "measured_at": "2026-03-05T18:25:30Z",
  "total_lines": 1757,
  "covered_lines": 0,
  "platform": "macos",
  "arch": "x86_64",
  "commit_sha": "d4db874f8",
  "notes": "Phase 140 baseline measurement"
}
```

## Troubleshooting

### ARM Mac Limitations

**Problem:** cargo-tarpaulin requires x86_64 architecture

**Error:**
```
Error: failed to run custom build command for `tarpaulin`
```

**Solutions:**
1. **Use Cross** (recommended):
   ```bash
   cargo install cross
   cross test --target x86_64-unknown-linux-gnu
   ```

2. **Run in CI/CD**:
   - Push to GitHub and let the workflow run on x86_64 runner
   - Download coverage artifact from Actions tab

3. **Use Rosetta 2** (macOS ARM):
   ```bash
   arch -x86_64 cargo tarpaulin --config tarpaulin.toml
   ```

### Tarpaulin Compilation Errors

**Problem:** Tarpaulin fails to compile on certain Rust versions

**Solution:**
```bash
# Use latest stable Rust
rustup update stable
cargo +stable install cargo-tarpaulin
```

### Coverage Report Not Generated

**Problem:** No coverage report in `coverage-report/` directory

**Checks:**
1. Verify tarpaulin.toml exists in `frontend-nextjs/src-tauri/`
2. Check for compilation errors (must compile successfully first)
3. Verify output directory permissions
4. Check tarpaulin output for errors

```bash
# Run with verbose output
cargo tarpaulin --verbose --config tarpaulin.toml
```

### Missing Platform-Specific Tests

**Problem:** Tests for specific platform are not running

**Check:**
1. Verify target OS matches platform:
   ```bash
   rustc --print cfg | grep target_os
   ```

2. Check module declarations have correct `#[cfg]` attributes:
   ```rust
   #[cfg(target_os = "windows")]
   pub mod windows;
   ```

3. Use `cargo test --list` to see compiled tests:
   ```bash
   cargo test --list | grep platform
   ```

### Coverage Percentage Not Increasing

**Problem:** Adding tests but coverage percentage stays the same

**Possible Causes:**
1. Tests hitting already-covered code paths
2. Test file exclusion patterns too broad
3. Conditional compilation excluding new code
4. Coverage cached from previous run

**Solutions:**
1. Use `cargo clean` before running coverage
2. Verify test file exclusions: `grep exclude-files tarpaulin.toml`
3. Check platform-specific code is compiled for target platform
4. Use HTML report to identify actual uncovered lines

## References

### Internal Documentation
- [Phase 140 Plan 01 Summary](../.planning/phases/140-desktop-coverage-baseline/140-01-SUMMARY.md) - Coverage infrastructure
- [Phase 140 Plan 02 Summary](../.planning/phases/140-desktop-coverage-baseline/140-02-SUMMARY.md) - Platform-specific testing
- [Phase 139 Mobile Platform-Specific Testing](../.planning/phases/139-mobile-platform-specific-testing/) - Mobile testing patterns

### External Resources
- [Tarpaulin Documentation](https://github.com/rsimonv/tarpaulin)
- [Tauri Testing Guide](https://tauri.app/v1/guides/testing/)
- [Rust Conditional Compilation](https://doc.rust-lang.org/reference/conditional-compilation.html)
- [Cross Compilation Guide](https://github.com/rust-embedded/cross)

### Test Patterns Reference
- Phase 139: `mobile/src/__tests__/platform-specific/` (mobile platform-specific tests)
- Phase 140: `frontend-nextjs/src-tauri/tests/platform_specific/` (desktop platform-specific tests)

## Next Steps

### Phase 141: Platform-Specific Testing

1. **Windows Tests:**
   - File dialog operations (open, save, folder picker)
   - Taskbar integration (progress, notifications)
   - Windows Hello biometric authentication
   - Registry access and system settings

2. **macOS Tests:**
   - Menu bar customization and menus
   - Dock integration and bounce notifications
   - Touch ID biometric authentication
   - Spotlight integration and file indexing

3. **Linux Tests:**
   - Window manager detection (GNOME, KDE, Xfce)
   - XDG desktop file integration
   - File picker dialogs (GTK, Qt)
   - System tray (appindicator) integration

### Phase 142: Coverage Enforcement

1. Add `--fail-under 80` to tarpaulin command
2. Enforce per-module coverage thresholds
3. Add PR comments with coverage trends
4. Integrate with CI/CD quality gates

### Phase 143: Final Verification

1. Achieve 80% overall coverage
2. Verify all critical paths covered
3. Document remaining gaps
4. Handoff to production deployment

---

**Last Updated:** 2026-03-05
**Phase:** 140 Desktop Coverage Baseline
**Status:** Infrastructure Complete, Baseline Pending
