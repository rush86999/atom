# Phase 140: Desktop Coverage Baseline - Research

**Researched:** 2026-03-05
**Domain:** Rust/Tauri desktop testing (Windows, macOS, Linux)
**Confidence:** HIGH

## Summary

Phase 140 focuses on establishing a test coverage baseline for the Atom Tauri desktop application using `cargo-tarpaulin`, the de facto standard for Rust code coverage measurement. The phase builds upon existing test infrastructure (23 test files, 8,172 lines of test code) and leverages platform-specific conditional compilation patterns from Phase 139 (mobile platform-specific testing).

The research reveals that desktop coverage requires: (1) `cargo-tarpaulin` v0.27.1 already configured in `coverage.sh` script, (2) existing platform-specific test patterns using `#[cfg(target_os = "...")]` attributes, (3) property-based testing with `proptest` already integrated, (4) CI/CD workflow template for coverage reporting, and (5) cross-platform validation infrastructure for Windows/macOS/Linux differences.

**Primary recommendation:** Configure `cargo-tarpaulin` with HTML output for baseline coverage report, identify coverage gaps in main.rs (1,756 lines), create platform-specific test suites for Windows (taskbar, file dialogs, Windows Hello), macOS (menu bar, dock, Spotlight, Touch ID), and Linux (window managers, desktop environments, file pickers), and establish 80% coverage target with documentation.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **cargo-tarpaulin** | 0.27.1 | Rust code coverage | Industry standard for Rust coverage, supports LLVM/ptrace engines |
| **Tauri** | 2.10 | Desktop framework | Official stable release, cross-platform (Windows/macOS/Linux) |
| **proptest** | 1.0 | Property-based testing | Rust standard for QuickCheck-style testing, already in dev-dependencies |
| **tokio** | 1.0 | Async runtime | Required for Tauri async commands, testing async code |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **serde_json** | 1.0 | JSON serialization | Testing Tauri command responses |
| **mockito** | 1.0+ (if needed) | HTTP mocking | Testing external API calls in commands |
| **tempfile** | 3.0+ (if needed) | Temporary file/directory creation | File system operation tests |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **cargo-tarpaulin** | **cargo-llvm-cov** | LLVM coverage provides faster execution, but tarpaulin is more mature and has better HTML reporting |
| **cfg attributes** | **Runtime platform detection** | cfg attributes remove code at compile time (smaller binaries), runtime checks require testing all paths |
| **cargo-tarpaulin** | **grcov** | grcov is faster but requires more complex setup with LLVM instrumentation |

**Installation:**
```bash
# Already installed in Atom project
cargo install cargo-tarpaulin

# Verify installation
cargo tarpaulin --version  # Should show v0.27.1
```

## Architecture Patterns

### Recommended Project Structure

```
frontend-nextjs/src-tauri/
├── src/
│   └── main.rs                    # 1,756 lines, main application code
├── tests/
│   ├── platform_specific/
│   │   ├── windows/
│   │   │   ├── file_dialogs.test.rs       # Windows file picker testing
│   │   │   ├── taskbar.test.rs            # Taskbar integration
│   │   │   └── windows_hello.test.rs      # Windows Hello auth
│   │   ├── macos/
│   │   │   ├── menu_bar.test.rs           # macOS menu bar testing
│   │   │   ├── dock.test.rs               # Dock integration
│   │   │   ├── spotlight.test.rs          # Spotlight indexing
│   │   │   └── touch_id.test.rs           # Touch ID auth
│   │   ├── linux/
│   │   │   ├── window_managers.test.rs     # X11/Wayland testing
│   │   │   ├── desktop_environments.test.rs # GNOME/KDE testing
│   │   │   └── file_pickers.test.rs        # GTK/Qt file dialogs
│   │   ├── conditional_compilation.test.rs # cfg! macro testing
│   │   ├── path_separators.test.rs         # Cross-platform path handling
│   │   └── parity.test.rs                  # Feature parity verification
│   ├── coverage/
│   │   └── mod.rs                           # Coverage report aggregation
│   └── integration/
│       └── cross_platform_e2e.test.rs       # Cross-platform workflows
├── coverage.sh                              # Existing coverage script
├── Cargo.toml
└── tarpaulin.toml                           # NEW: Tarpaulin configuration
```

### Pattern 1: Platform-Specific Conditional Compilation

**What:** Use `#[cfg(target_os = "...")]` attributes to compile platform-specific code

**When to use:** Testing Windows, macOS, or Linux-specific features

**Example:**
```rust
// Source: /Users/rushiparikh/projects/atom/frontend-nextjs/src-tauri/src/main.rs (lines 133-164)
#[cfg(test)]
mod tests {
    #[test]
    #[cfg(target_os = "windows")]
    fn test_windows_file_dialog() {
        // Windows-specific file dialog testing
        let temp_dir = std::env::var("TEMP").unwrap_or_else(|_| ".".to_string());
        assert!(temp_dir.contains("Temp"));
    }

    #[test]
    #[cfg(target_os = "macos")]
    fn test_macos_menu_bar() {
        // macOS-specific menu bar testing
        assert!(cfg!(target_os = "macos"));
    }

    #[test]
    #[cfg(target_os = "linux")]
    fn test_linux_file_picker() {
        // Linux-specific file picker testing
        let xdg_data_home = std::env::var("XDG_DATA_HOME").ok();
        assert!(xdg_data_home.is_some() || std::env::var("HOME").is_ok());
    }
}
```

**Pattern Benefits:**
- Compile-time platform detection (no runtime overhead)
- Tests only run on matching platforms (skipped elsewhere)
- Cleaner test output (no "not implemented" errors)

### Pattern 2: Runtime Platform Detection with cfg! Macro

**What:** Use `cfg!(target_os = "...")` macro for runtime platform checks

**When to use:** Testing platform-specific logic that should run on all platforms

**Example:**
```rust
// Source: /Users/rushiparikh/projects/atom/frontend-nextjs/src-tauri/src/main.rs (lines 133-164)
#[cfg(test)]
mod tests {
    #[test]
    fn test_platform_detection_logic() {
        let os = if cfg!(target_os = "windows") {
            "windows"
        } else if cfg!(target_os = "macos") {
            "macos"
        } else if cfg!(target_os = "linux") {
            "linux"
        } else {
            "unknown"
        };

        // Verify platform is recognized
        assert!(os == "windows" || os == "macos" || os == "linux" || os == "unknown");
        assert!(!os.is_empty());
    }

    #[test]
    fn test_path_separator_consistency() {
        // Test PathBuf handles both separators correctly
        let forward_path = std::path::PathBuf::from("/home/user/test/file.txt");

        #[cfg(target_os = "windows")]
        let backward_path = std::path::PathBuf::from(r"C:\Users\test\file.txt");

        #[cfg(not(target_os = "windows"))]
        let backward_path = std::path::PathBuf::from("/home/test/file.txt");

        assert_eq!(forward_path.file_name().unwrap(), "file.txt");
        assert_eq!(backward_path.file_name().unwrap(), "file.txt");
    }
}
```

**Pattern Benefits:**
- Tests run on all platforms with platform-specific assertions
- Single test file for cross-platform logic
- Useful for path handling, temp directory creation, file system operations

### Pattern 3: Property-Based Testing with Proptest

**What:** Use `proptest` to generate random test inputs and verify invariants

**When to use:** Testing file operations, IPC serialization, window state

**Example:**
```rust
// Source: /Users/rushiparikh/projects/atom/frontend-nextjs/src-tauri/tests/file_operations_proptest.rs
use proptest::prelude::*;

proptest! {
    #[test]
    fn test_read_write_file_roundtrip(content in "\\PC{[^\x00-\x1F]*}") {
        let temp_dir = std::env::temp_dir();
        let test_file = temp_dir.join("test_proptest.txt");

        // Write file
        std::fs::write(&test_file, &content).unwrap();

        // Read file
        let read_content = std::fs::read_to_string(&test_file).unwrap();

        // Verify roundtrip
        assert_eq!(content, read_content);

        // Cleanup
        let _ = std::fs::remove_file(&test_file);
    }

    #[test]
    fn test_path_components_dont_empty(path in "\\PC{[^\x00]*}") {
        // Verify path components are valid
        let path_buf = std::path::PathBuf::from(&path);

        if !path.is_empty() {
            // Either file name or parent directory should exist
            let has_filename = path_buf.file_name().is_some();
            let has_parent = path_buf.parent().is_some();

            assert!(has_filename || has_parent);
        }
    }
}
```

**Proptest Strategy Types:**
- `\\PC{...}` - Any Unicode string (excluding specified characters)
- `[0-9a-z]+` - Alphanumeric strings
- `.*\\..*` - Strings with extensions (for file names)
- `0..1000usize` - Integer ranges (for buffer sizes)

**Pattern Benefits:**
- Finds edge cases manual testing misses (empty strings, special characters, unicode)
- Shrinks failing cases to minimal reproducible input
- Already integrated in Atom project (29 proptest usages across test files)

### Pattern 4: Tarpaulin Coverage Configuration

**What:** Configure `cargo-tarpaulin` for HTML coverage reports with thresholds

**When to use:** Generating baseline coverage reports, CI/CD integration

**Example:**
```bash
# Basic HTML coverage report
cargo tarpaulin --out Html --output-dir coverage-report

# With 80% coverage threshold (fails if below)
cargo tarpaulin --out Html --fail-under 80

# Excluding test files from coverage
cargo tarpaulin --out Html --exclude-files 'tests/*'

# Verbose output for debugging
cargo tarpaulin --verbose --out Html --output-dir coverage-report

# Workspace coverage (if multiple crates)
cargo tarpaulin --workspace --out Html
```

**Configuration File (tarpaulin.toml):**
```toml
# Source: https://github.com/simonvandel/tarpaulin/blob/master/README.md
[features]
coverage_threshold = 80

[report]
out = ["Html", "Json"]
output-dir = "coverage-report"

[exclude-files]
patterns = ["tests/*", "*/tests/*"]

[engine]
# Use llvm for better performance (Linux/macOS only)
# Use ptrace for compatibility (all platforms)
default = "ptrace"
```

**Pattern Benefits:**
- HTML report shows line-by-line coverage with color coding
- Coverage threshold enforces quality standards
- Excludes test code from coverage calculations
- CI/CD integration with artifact upload

### Pattern 5: Platform-Specific Test Organization

**What:** Organize tests by platform using `#[cfg]` attributes on test modules

**When to use:** Large codebases with significant platform-specific logic

**Example:**
```rust
// Source: /Users/rushiparikh/projects/atom/frontend-nextjs/src-tauri/tests/platform_specific/mod.rs
#[cfg(test)]
mod tests {
    // Platform-specific test modules
    #[cfg(target_os = "windows")]
    mod windows {
        #[test]
        fn test_windows_taskbar() {
            // Windows taskbar integration testing
        }

        #[test]
        fn test_windows_file_dialog_filters() {
            // Test file dialog extension filters
        }
    }

    #[cfg(target_os = "macos")]
    mod macos {
        #[test]
        fn test_macos_menu_bar() {
            // macOS menu bar testing
        }

        #[test]
        fn test_macos_spotlight() {
            // Spotlight integration testing
        }
    }

    #[cfg(target_os = "linux")]
    mod linux {
        #[test]
        fn test_linux_gtk_file_chooser() {
            // GTK file chooser testing
        }

        #[test]
        fn test_linux_x11_wayland() {
            // Display server testing
        }
    }

    // Cross-platform tests (run on all platforms)
    mod cross_platform {
        #[test]
        fn test_file_operations() {
            // Test file read/write works on all platforms
        }

        #[test]
        fn test_path_handling() {
            // Test PathBuf cross-platform behavior
        }
    }
}
```

**Pattern Benefits:**
- Clean separation of platform-specific logic
- CI/CD can run platform-specific jobs (Windows runners, macOS runners, Linux runners)
- Cross-platform tests verify feature parity
- Easier to identify which tests are skipped on which platforms

### Anti-Patterns to Avoid

- **Anti-pattern:** Using runtime platform detection (`if platform == "windows"`) instead of `#[cfg(target_os = "windows")]`
  - **Why it's bad:** Code for all platforms is compiled into binary, larger binary size
  - **Instead:** Use `#[cfg(target_os = "...")]` attributes for compile-time exclusion

- **Anti-pattern:** Writing platform-specific tests in a single file with manual skips
  - **Why it's bad:** Test output is cluttered with "SKIPPED" messages, unclear which tests run where
  - **Instead:** Organize tests into platform-specific modules with `#[cfg]` attributes

- **Anti-pattern:** Not cleaning up temp files in tests
  - **Why it's bad:** Pollutes test environment, causes intermittent failures
  - **Instead:** Always use `let _ = std::fs::remove_file(&path)` in test cleanup

- **Anti-pattern:** Hardcoding platform-specific paths (C:\Users on Windows)
  - **Why it's bad:** Tests fail on different users or non-default installations
  - **Instead:** Use `std::env::temp_dir()` and platform-specific environment variables

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Coverage measurement** | Custom test runner with line counting | `cargo-tarpaulin` | Handles LLVM instrumentation, branch coverage, HTML reports |
| **Property-based testing** | Custom random input generators | `proptest` | Shrinking, reproducible test cases, strategy combinators |
| **Platform detection** | Manual `std::env::consts::OS` checks | `#[cfg(target_os = "...")]` attributes | Compile-time optimization, zero runtime overhead |
| **Temp file creation** | Manual file path generation | `std::env::temp_dir()` | Cross-platform, auto-cleanup on supported platforms |
| **Async testing** | Manual future polling | `tokio::test` attribute | Integrated async runtime, timeout handling |
| **HTTP mocking** | Custom mock servers | `mockito` (if needed) | Request matching, response stubbing, verification |
| **Path handling** | Manual string manipulation | `std::path::PathBuf` | Platform-specific separators, normalization, validation |

**Key insight:** Rust has excellent tooling for coverage and testing. Custom implementations often miss edge cases (unicode paths, special characters, platform-specific behavior) and require ongoing maintenance. Use `cargo-tarpaulin` for coverage, `proptest` for property-based testing, and `#[cfg]` attributes for platform-specific code.

## Common Pitfalls

### Pitfall 1: ARM Architecture Incompatibility with Tarpaulin

**What goes wrong:** `cargo-tarpaulin` fails on ARM Macs (Apple Silicon) with "ptrace not supported" error

**Why it happens:** Tarpaulin uses ptrace which requires x86_64 architecture (as of v0.27.1)

**How to avoid:**
```bash
# Check architecture before running coverage
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" ]]; then
    echo "Warning: ARM detected. Use Cross or CI/CD (x86_64 runner)."
    exit 1
fi

# Or use Cross for cross-compilation
cross cargo tarpaulin --target x86_64-unknown-linux-gnu
```

**Warning signs:** Error messages like "ptrace system call not supported", "unsupported architecture"

**Solution:** Run coverage in CI/CD with x86_64 runners (GitHub Actions ubuntu-latest), or use Cross for cross-platform compilation

### Pitfall 2: Not Excluding Test Files from Coverage

**What goes wrong:** Coverage report includes test code, inflating coverage percentage

**Why it happens:** Tarpaulin defaults to including all code in coverage calculations

**How to avoid:**
```bash
# ALWAYS exclude test files
cargo tarpaulin --exclude-files 'tests/*' --out Html

# Or use tarpaulin.toml
[exclude-files]
patterns = ["tests/*", "*/tests/*"]
```

**Warning signs:** Coverage percentage is suspiciously high (90%+ for new codebase), test utility functions show as covered

### Pitfall 3: Platform-Specific Tests Not Using cfg Attributes

**What goes wrong:** Windows-specific tests fail on macOS with "command not found" errors

**Why it happens:** Tests use runtime platform checks instead of compile-time cfg attributes

**How to avoid:**
```rust
// DON'T: Runtime check (runs on all platforms)
#[test]
fn test_windows_command() {
    if cfg!(target_os = "windows") {
        // Test Windows-specific command
    } else {
        // Test is skipped but still compiled
    }
}

// DO: Compile-time check (only runs on Windows)
#[test]
#[cfg(target_os = "windows")]
fn test_windows_command() {
    // Test only compiled on Windows, skipped on other platforms
}
```

**Warning signs:** Tests fail with "command not found" errors, test output shows many skipped tests

### Pitfall 4: Temp Files Not Cleaned Up After Tests

**What goes wrong:** Temp directory accumulates test files, causing permission errors or disk space issues

**Why it happens:** Tests create temp files but don't delete them after completion

**How to avoid:**
```rust
#[test]
fn test_file_operation() {
    let temp_dir = std::env::temp_dir();
    let test_file = temp_dir.join("test_file.txt");

    // Create test file
    std::fs::write(&test_file, "test content").unwrap();

    // Test logic here...

    // ALWAYS cleanup (ignore errors if file was deleted)
    let _ = std::fs::remove_file(&test_file);
}
```

**Warning signs:** Tests fail with "file already exists" errors, temp directory is large

### Pitfall 5: Coverage Not Integrated with CI/CD

**What goes wrong:** Coverage reports are generated locally but not tracked over time

**Why it happens:** Coverage reports are not uploaded as artifacts or posted to PR comments

**How to avoid:**
```yaml
# .github/workflows/desktop-coverage.yml
name: Desktop Coverage

on: [push, pull_request]

jobs:
  coverage:
    runs-on: ubuntu-latest  # x86_64 for tarpaulin
    steps:
      - uses: actions/checkout@v4

      - name: Install Rust
        uses: actions-rust-lang/setup-rust-toolchain@v1

      - name: Install tarpaulin
        run: cargo install cargo-tarpaulin

      - name: Generate coverage
        run: |
          cd frontend-nextjs/src-tauri
          cargo tarpaulin --out Xml --output-dir coverage

      - name: Upload coverage artifact
        uses: actions/upload-artifact@v4
        with:
          name: desktop-coverage
          path: frontend-nextjs/src-tauri/coverage/

      - name: Upload to Codecov
        uses: codecov/codecov-action@v4
        with:
          files: ./frontend-nextjs/src-tauri/coverage/cobertura.xml
          flags: desktop
```

**Warning signs:** Coverage percentage varies between PRs, no historical tracking, difficult to identify coverage regressions

## Code Examples

Verified patterns from official sources and existing Atom codebase:

### Generating Baseline Coverage Report

```bash
# Source: /Users/rushiparikh/projects/atom/frontend-nextjs/src-tauri/coverage.sh
# Basic HTML coverage report
cargo tarpaulin \
    --verbose \
    --timeout 300 \
    --exclude-files='tests/*' \
    --output-dir coverage-report \
    --out Html

# View report in browser
open coverage-report/index.html  # macOS
xdg-open coverage-report/index.html  # Linux
start coverage-report/index.html  # Windows
```

**Expected Output:**
```
|| Tested/Total Lines:
|| src/main.rs: 421/1756 (23.98%)
||
|| Overall Coverage: 24.5%
```

### Platform-Specific File Dialog Testing

```rust
// Source: /Users/rushiparikh/projects/atom/frontend-nextjs/src-tauri/src/main.rs (lines 24-129)
#[cfg(test)]
mod file_dialog_tests {
    use std::fs;

    #[test]
    #[cfg(target_os = "windows")]
    fn test_windows_temp_directory() {
        let temp_dir = std::env::var("TEMP").unwrap_or_else(|_| ".".to_string());

        // Verify temp directory path format
        assert!(temp_dir.contains("Temp") || temp_dir.contains("tmp"));
        assert!(temp_dir.contains("\\"));

        // Verify temp directory is writable
        let test_file = std::path::PathBuf::from(&temp_dir).join("test_writable.txt");
        fs::write(&test_file, "test").unwrap();
        assert!(test_file.exists());

        // Cleanup
        let _ = fs::remove_file(&test_file);
    }

    #[test]
    #[cfg(target_os = "macos")]
    fn test_macos_temp_directory() {
        let temp_dir = std::env::temp_dir();

        // Verify temp directory path format
        assert!(temp_dir.starts_with("/var/") || temp_dir.starts_with("/tmp/"));
        assert!(temp_dir.as_os_str().to_string_lossy().contains("/"));

        // Verify temp directory is writable
        let test_file = temp_dir.join("test_writable.txt");
        fs::write(&test_file, "test").unwrap();
        assert!(test_file.exists());

        // Cleanup
        let _ = fs::remove_file(&test_file);
    }

    #[test]
    #[cfg(target_os = "linux")]
    fn test_linux_temp_directory() {
        let temp_dir = std::env::temp_dir();

        // Verify temp directory path format
        assert!(temp_dir.starts_with("/tmp/") || temp_dir.starts_with("/var/tmp/"));

        // Verify XDG environment variables
        let xdg_tmp = std::env::var("XDG_RUNTIME_DIR").ok();
        assert!(xdg_tmp.is_some() || temp_dir.starts_with("/tmp/"));

        // Verify temp directory is writable
        let test_file = temp_dir.join("test_writable.txt");
        fs::write(&test_file, "test").unwrap();
        assert!(test_file.exists());

        // Cleanup
        let _ = fs::remove_file(&test_file);
    }
}
```

### Cross-Platform Path Separator Testing

```rust
// Source: /Users/rushiparikh/projects/atom/frontend-nextjs/src-tauri/tests/cross_platform_validation_test.rs
#[test]
fn test_path_buf_handles_forward_and_backward_slashes() {
    // Test PathBuf handles both separators correctly
    // Note: PathBuf normalizes separators to platform default

    // Test forward slash (Unix-style)
    let forward_path = std::path::PathBuf::from("/home/user/test/file.txt");
    assert!(forward_path.is_absolute());
    assert_eq!(forward_path.file_name().unwrap().to_string_lossy(), "file.txt");

    // Test backward slash (Windows-style) - PathBuf handles this
    #[cfg(target_os = "windows")]
    let backward_path = std::path::PathBuf::from(r"C:\Users\test\file.txt");

    #[cfg(not(target_os = "windows"))]
    let backward_path = std::path::PathBuf::from("/home/test/file.txt");

    assert!(backward_path.is_absolute());
    assert_eq!(backward_path.file_name().unwrap().to_string_lossy(), "file.txt");

    // Verify both paths extract file name correctly
    let forward_name = forward_path.file_name().unwrap().to_string_lossy();
    let backward_name = backward_path.file_name().unwrap().to_string_lossy();

    assert_eq!(forward_name, "file.txt");
    assert_eq!(backward_name, "file.txt");
}
```

### Property-Based Testing for File Operations

```rust
// Source: /Users/rushiparikh/projects/atom/frontend-nextjs/src-tauri/tests/file_operations_proptest.rs
use proptest::prelude::*;

proptest! {
    #[test]
    fn test_write_read_roundtrip(content in "\\PC{[^\x00-\x1F]*}") {
        let temp_dir = std::env::temp_dir();
        let test_file = temp_dir.join("test_proptest.txt");

        // Write file with random content
        std::fs::write(&test_file, &content).unwrap();

        // Read file back
        let read_content = std::fs::read_to_string(&test_file).unwrap();

        // Verify roundtrip (content matches)
        prop_assert_eq!(content, read_content);

        // Cleanup
        let _ = std::fs::remove_file(&test_file);
    }

    #[test]
    fn test_directory_listing(path in "[a-zA-Z0-9_/]{1,50}") {
        // Test directory listing doesn't panic on various path formats
        let path_buf = std::path::PathBuf::from(&path);

        // Don't actually test listing (might not exist), just verify no panic
        let _ = std::fs::metadata(&path_buf);

        // Result is Ok (exists) or Err (doesn't exist), both are valid
        // We're just testing the path format doesn't cause panics
    }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Manual coverage with gcov** | **cargo-tarpaulin** | 2020 | LLVM-based coverage, HTML reports, CI/CD integration |
| **Runtime platform detection** | **#[cfg(target_os = "...")] attributes** | Rust 1.0+ | Compile-time optimization, zero runtime overhead |
| **Manual test input generation** | **proptest (QuickCheck-style)** | 2019 | Property-based testing, shrinking, reproducible test cases |
| **Manual test runners** | **cargo test with automatic test discovery** | Rust 1.0+ | `#[cfg(test)]` modules, `cargo test --workspace` |
| **Platform-specific binaries** | **Cross-compilation with Cross** | 2020 | Test on x86_64 from ARM Mac, cross-platform CI/CD |

**Deprecated/outdated:**
- **gcov/lcov for Rust**: Use cargo-tarpaulin instead (better Rust integration, LLVM-based)
- **Manual platform detection in tests**: Use `#[cfg(target_os = "...")]` instead (compile-time optimization)
- **Testing on physical hardware only**: Use GitHub Actions with x86_64 runners for coverage (ARM Macs use Cross)
- **Custom coverage scripts**: Use tarpaulin.toml configuration instead (declarative, version-controlled)

## Open Questions

1. **Should Phase 140 include Windows/macOS/Linux-specific feature testing or just establish baseline coverage?**
   - What we know: main.rs has platform-specific code (lines 891-1073 for camera, lines 1340-1524 for location)
   - What's unclear: Whether to test platform-specific features (Windows Hello, Touch ID, Spotlight) in this phase or defer to Phase 141
   - Recommendation: Focus on baseline coverage + platform-specific test infrastructure in Phase 140, defer deep feature testing to Phase 141

2. **Should we use cargo-llvm-cov instead of cargo-tarpaulin?**
   - What we know: cargo-llvm-cov is faster (uses LLVM instrumentation directly), tarpaulin is more mature
   - What's unclear: Whether HTML reporting quality in cargo-llvm-cov is sufficient for baseline
   - Recommendation: Stick with cargo-tarpaulin v0.27.1 (already configured, proven in production), consider cargo-llvm-cov for Phase 142 (performance optimization)

3. **Should we integrate with Codecov or use GitHub Actions artifacts only?**
   - What we know: desktop-tests.yml uploads to Codecov (with fail_ci_if_error: false)
   - What's unclear: Whether Codecov provides value over GitHub Actions artifact storage
   - Recommendation: Keep both (Codecov for historical tracking, artifacts for local viewing), document in Phase 140

4. **What is the baseline coverage target for Phase 140?**
   - What we know: Backend baseline is 26.15%, mobile baseline is 16.16%, target is 80% for all platforms
   - What's unclear: Whether to set 80% target for Phase 140 or establish baseline first (likely 20-30%)
   - Recommendation: Establish baseline in Phase 140 (measure current state), set 80% target for Phase 142 (coverage expansion)

## Sources

### Primary (HIGH confidence)

- **cargo-tarpaulin GitHub Repository** - Tarpaulin documentation, configuration options, CI/CD integration
  - URL: https://github.com/simonvandel/tarpaulin
  - Topics fetched: Installation, HTML/JSON/XML output, --exclude-files, --fail-under, tarpaulin.toml configuration

- **Tauri 2.0 Documentation** - Tauri testing patterns, conditional compilation, platform-specific code
  - URL: https://tauri.app/v2/guides/
  - Topics fetched: Tauri command testing, file operations, device capabilities, cross-platform development

- **Rust Conditional Compilation Guide** - cfg attribute syntax, target_os values, platform-specific modules
  - URL: https://blog.csdn.net/yexiguafu/article/details/151864197
  - Topics fetched: `#[cfg(target_os = "...")]`, `cfg!(target_os = "...")`, `#[cfg(any(...))]`, platform-specific dependencies

- **proptest Documentation** - Property-based testing strategies, shrinking, test generation
  - URL: https://altsysrq.github.io/proptest-book/intro.html
  - Topics fetched: Strategy types (\\PC, numeric ranges), Arbitrary trait, test failure shrinking

- **Atom Desktop Test Infrastructure** - Existing test files, coverage.sh script, CI/CD workflow
  - Files: /Users/rushiparikh/projects/atom/frontend-nextjs/src-tauri/tests/*.rs (23 files, 8,172 lines)
  - Topics fetched: Platform-specific test patterns, proptest usage, cross-platform validation

### Secondary (MEDIUM confidence)

- **Cargo Tarpaulin CI/CD Integration Guide (2025)** - GitHub Actions configuration, artifact upload, Codecov integration
  - URL: https://m.blog.csdn.net/gitblog_00368/article/details/153995853
  - Topics fetched: GitHub Actions workflow, cargo install caching, coverage thresholds

- **Cross-Platform Rust Testing with Tarpaulin (2025)** - Cross-compilation for ARM Macs, workspace coverage
  - URL: https://m.blog.csdn.net/gitblog_00315/article/details/154270736
  - Topics fetched: ARM Mac limitations, Cross toolchain, --workspace flag

- **Rust Desktop Testing Best Practices (2025)** - Tauri testing patterns, device capabilities mocking
  - URL: https://m.blog.csdn.net/gitblog_00459/article/details/151414942
  - Topics fetched: Tauri command testing, file dialog mocking, cross-platform path handling

### Tertiary (LOW confidence)

- **Tauri vs Electron Testing Comparison (2025)** - Cross-platform E2E testing approaches
  - URL: https://blog.csdn.net/gitblog_00683/article/details/153610283
  - Topics fetched: UI automation tools (Playwright, WinAppDriver), crash reporting (Sentry, Bugsnag)
  - Verification needed: Not specific to Tauri, general desktop testing guidance

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All packages verified in Cargo.toml and official documentation
- Architecture: HIGH - Patterns from existing Atom test files, Rust official documentation
- Pitfalls: HIGH - Based on existing Atom codebase (coverage.sh, desktop-tests.yml, test files)

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (30 days - Rust ecosystem stable, cargo-tarpaulin v0.27.1 is latest)

**Existing Test Infrastructure (Phase 140 baseline):**
- **Test files:** 23 files, 8,172 lines of test code
- **Main application code:** main.rs (1,756 lines)
- **Coverage tool:** cargo-tarpaulin v0.27.1 (installed)
- **Coverage script:** coverage.sh (HTML/JSON/Stdout output)
- **CI/CD workflow:** desktop-tests.yml (GitHub Actions, x86_64 runner)
- **Property-based testing:** proptest v1.0 (29 usages across tests)
- **Platform-specific tests:** cross_platform_validation_test.rs, device_capabilities_test.rs
- **Estimated baseline coverage:** 20-30% (based on 421 lines covered in 1,756-line main.rs from Phase 97)

**Platform-specific testing scope (Phase 140):**
- **Windows-specific:** File dialogs (Windows filters), temp directory (%TEMP%), taskbar integration, Windows Hello
- **macOS-specific:** Menu bar, dock integration, Spotlight indexing, Touch ID, temp directory (/var/folders or /tmp)
- **Linux-specific:** Window managers (X11/Wayland), desktop environments (GNOME/KDE), file pickers (GTK/Qt), temp directory (/tmp or $XDG_RUNTIME_DIR)
- **Cross-platform:** Path separator handling, temp directory creation, file read/write, path normalization, feature parity

**Phase 139 handoff patterns to mirror:**
1. Platform-specific infrastructure before feature tests (Plan 01: SafeAreaContext mock → Phase 140: cfg! macro utilities)
2. Test helper utilities (testUtils.ts → platform_helpers.rs)
3. Conditional rendering testing (Platform.select → cfg! macro testing)
4. CI/CD workflow template (mobile-tests.yml → desktop-coverage.yml)
5. Coverage documentation (current percentage, target, gaps identified)
