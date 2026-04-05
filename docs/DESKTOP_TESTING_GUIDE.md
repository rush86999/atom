# Desktop Testing Guide

**Platform:** Tauri (Rust)
**Frameworks:** cargo test, proptest, tarpaulin
**Target:** 40%+ coverage
**Last Updated:** March 7, 2026

---

## Overview

Atom Desktop is a Tauri-based desktop application built with Rust that brings AI-powered automation to Windows, macOS, and Linux. This guide covers testing infrastructure, framework patterns, platform-specific testing, and coverage measurement.

**Key Points:**
- **Test Framework:** Rust's built-in `cargo test` with proptest for property-based testing
- **Coverage Tool:** tarpaulin for code coverage measurement
- **Platform Support:** Windows, macOS, Linux with conditional compilation
- **Test Organization:** Platform-specific modules, helper utilities, integration tests
- **Current Coverage:** 65-70% estimated (Phase 142 complete)

---

## Quick Start (5 min)

### Run All Tests

```bash
cd frontend-nextjs/src-tauri
cargo test
# Expected: 122+ tests compile and pass
```

### Run Platform-Specific Tests

```bash
# Run all tests (platform-specific tests automatically filtered by #[cfg])
cargo test

# Run specific test
cargo test test_windows_file_dialog_open

# Run tests in specific module
cargo test --test platform_specific

# Run with output
cargo test -- --nocapture

# Run with logging
cargo test -- --test-threads=1 -- -t
```

### Generate Coverage Report

```bash
# HTML report (visual inspection)
cargo tarpaulin --out Html --output-dir coverage-report

# JSON report (CI/CD integration)
cargo tarpaulin --out Json --output-dir coverage

# View HTML report
open coverage-report/index.html  # macOS
xdg-open coverage-report/index.html  # Linux
start coverage-report/index.html  # Windows
```

### Quick Verification

```bash
# Verify test setup (compile only)
cargo test --no-run

# Count tests
cargo test -- --list | wc -l

# Run tests with coverage
./coverage.sh
```

---

## Test Structure

### Directory Layout

```
frontend-nextjs/src-tauri/
├── tests/
│   ├── main.rs                          # Integration tests
│   ├── platform_specific/
│   │   ├── mod.rs                       # Platform module exports
│   │   ├── windows.rs                   # Windows-specific tests
│   │   ├── macos.rs                     # macOS-specific tests
│   │   ├── linux.rs                     # Linux-specific tests
│   │   └── conditional_compilation.rs   # cfg! macro tests
│   ├── helpers/
│   │   ├── mod.rs                       # Helper module exports
│   │   └── platform_helpers.rs          # Platform detection utilities
│   ├── coverage/
│   │   ├── mod.rs                       # Baseline tracking module
│   │   └── coverage_baseline_test.rs    # Baseline tests
│   └── integration/
│       ├── tauri_commands_test.rs       # IPC command tests
│       ├── system_tray_test.rs          # System tray tests
│       └── device_capabilities_test.rs  # Device capability tests
└── src/
    └── main.rs                          # Production code (1756 lines)
```

### Module Organization

**platform_specific/mod.rs** - Platform gate declarations:
```rust
#[cfg(target_os = "windows")]
pub mod windows;

#[cfg(target_os = "macos")]
pub mod macos;

#[cfg(target_os = "linux")]
pub mod linux;

// Cross-platform modules (run on all platforms)
pub mod conditional_compilation;
```

**helpers/mod.rs** - Test utility exports:
```rust
pub mod platform_helpers;

pub use platform_helpers::{
    get_current_platform,
    is_platform,
    cfg_assert,
    get_temp_dir,
    get_platform_separator
};
```

---

## cargo test Patterns

### Unit Tests

Unit tests test individual functions and modules in isolation.

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_platform_detection() {
        let platform = get_current_platform();
        assert!(!platform.is_empty());
        assert!(["windows", "macos", "linux"].contains(&platform));
    }

    #[test]
    fn test_path_separator() {
        let separator = get_platform_separator();
        if cfg!(target_os = "windows") {
            assert_eq!(separator, "\\");
        } else {
            assert_eq!(separator, "/");
        }
    }
}
```

**Key Points:**
- Place unit tests in the same module as production code (#[cfg(test)] mod tests)
- Test public API, not implementation details
- Use descriptive test names (test_<function>_<scenario>)

### Async Tests (tokio)

Async tests use tokio::test for async/await operations.

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use tokio::test;

    #[tokio::test]
    async fn test_async_device_capability() {
        let result = get_device_capability("camera").await;
        assert!(result.is_ok());

        let capability = result.unwrap();
        assert_eq!(capability.name, "camera");
        assert!(capability.available);
    }

    #[tokio::test]
    async fn test_async_file_operation() {
        let temp_dir = get_temp_dir();
        let test_file = temp_dir.join("test_async.txt");

        // Async file write
        let write_result = write_file_async(&test_file, b"test content").await;
        assert!(write_result.is_ok());

        // Async file read
        let read_result = read_file_async(&test_file).await;
        assert!(read_result.is_ok());
        assert_eq!(read_result.unwrap(), b"test content");

        // Cleanup
        let _ = std::fs::remove_file(&test_file);
    }
}
```

**Key Points:**
- Use `#[tokio::test]` for async test functions (not #[test])
- Test error paths explicitly (Result types, error propagation)
- Clean up resources in test body (no tearDown in Rust)

### Platform-Specific Tests

Platform-specific tests use conditional compilation to run only on matching platforms.

```rust
#[cfg(test)]
#[cfg(target_os = "windows")]
mod windows_tests {
    use super::*;

    #[test]
    fn test_windows_temp_directory() {
        let temp = get_temp_dir();
        let temp_str = temp.to_string_lossy();

        // Windows temp paths contain backslashes
        assert!(temp_str.contains('\\'));

        // Verify directory exists
        assert!(temp.exists());
        assert!(temp.is_dir());
    }

    #[test]
    fn test_windows_path_format() {
        let path = PathBuf::from("C:\\Users\\Test\\file.txt");

        assert!(path.is_absolute());
        assert!(path.starts_with("C:\\"));
        assert_eq!(path.extension().unwrap(), "txt");
    }

    #[test]
    fn test_windows_file_extensions() {
        let test_cases = vec![
            ("file.txt", "txt"),
            ("document.pdf", "pdf"),
            ("archive.tar.gz", "gz"),
            ("script.rs", "rs"),
            ("image.png", "png"),
        ];

        for (filename, expected_ext) in test_cases {
            let path = PathBuf::from(filename);
            assert_eq!(path.extension().unwrap(), expected_ext);
        }
    }
}

#[cfg(test)]
#[cfg(target_os = "macos")]
mod macos_tests {
    use super::*;

    #[test]
    fn test_macos_app_support_dir() {
        let support_dir = dirs_next::config_dir();
        assert!(support_dir.is_some());

        let dir = support_dir.unwrap();
        let dir_str = dir.to_string_lossy();

        // macOS Application Support directory
        assert!(dir_str.contains("Application Support") || dir_str.contains(".config"));

        // Verify directory exists
        assert!(dir.exists());
        assert!(dir.is_dir());
    }

    #[test]
    fn test_macos_path_separator() {
        let separator = get_platform_separator();
        assert_eq!(separator, "/");

        let path = PathBuf::from("/Users/test/file.txt");
        assert!(path.is_absolute());
        assert!(path.starts_with("/"));
    }
}

#[cfg(test)]
#[cfg(target_os = "linux")]
mod linux_tests {
    use super::*;

    #[test]
    fn test_linux_xdg_config() {
        let config = std::env::var("XDG_CONFIG_HOME").ok();
        let home = std::env::var("HOME").ok();

        // Either XDG_CONFIG_HOME or HOME should be set
        assert!(config.is_some() || home.is_some());

        if let Some(home_dir) = home {
            let expected_config = format!("{}/.config", home_dir);
            assert_eq!(config.unwrap_or(expected_config), expected_config);
        }
    }

    #[test]
    fn test_linux_temp_dir() {
        let temp = get_temp_dir();
        let temp_str = temp.to_string_lossy();

        // Linux temp paths use forward slashes
        assert!(temp_str.contains('/'));
        assert!(!temp_str.contains('\\'));

        // Common temp directories
        let is_tmp_or_tmpdir = temp_str.contains("/tmp") || temp_str.contains("/tmpdir");
        assert!(is_tmp_or_tmpdir);
    }
}
```

**Key Points:**
- Use `#[cfg(target_os = "...")]` for compile-time platform filtering
- Tests only compile and run on matching platforms
- No runtime overhead from conditionally compiled tests
- Use `cargo test` to run all tests (platform-specific tests are automatically filtered)

---

## Property Testing (proptest)

Property-based testing validates invariants across hundreds of randomly generated inputs, finding edge cases that example-based testing misses.

### Invariant Testing

Test that a property holds for all possible inputs.

```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn test_path_normalization_doesnt_change_valid_paths(path in "[a-zA-Z0-9_/]+") {
        let normalized = normalize_path(&path);

        // Invariant: Normalized paths contain forward slashes
        assert!(normalized.contains('/'), "Normalized path should contain /");

        // Invariant: No backslashes in normalized paths
        assert!(!normalized.contains('\\'), "Normalized path should not contain \\");
    }

    #[test]
    fn test_temp_dir_always_exists(_dummy in prop::collection::vec(any::<u8>(), 0..100)) {
        let temp_dir = get_temp_dir();

        // Invariant: Temp directory always exists
        assert!(temp_dir.exists(), "Temp directory should exist");

        // Invariant: Temp directory is a directory
        assert!(temp_dir.is_dir(), "Temp should be a directory");
    }
}
```

### Error Handling Properties

Test that error handling is robust across invalid inputs.

```rust
proptest! {
    #[test]
    fn test_device_capability_fails_gracefully_on_invalid_input(input in "[^\u{0}-\u{7F}]*") {
        let result = validate_device_capability(&input);

        // Invariant: Invalid input returns error or empty input is allowed
        assert!(result.is_err() || input.is_empty(),
                "Invalid input should fail or empty input should be allowed");
    }

    #[test]
    fn test_file_operations_handle_large_paths(path in prop::string::string_regex("[a-z]{0,1000}/[a-z]{0,1000}").unwrap()) {
        let temp_dir = get_temp_dir();
        let full_path = temp_dir.join(&path);

        // Invariant: Operations should not panic on long paths
        let result = std::fs::create_dir_all(&full_path);

        // Cleanup
        let _ = std::fs::remove_dir_all(&full_path);

        // Result is Ok (success) or Err (path too long) but never panic
        match result {
            Ok(_) => assert!(true),
            Err(e) => assert!(e.to_string().contains("name too long") ||
                            e.to_string().contains("file name too long") ||
                            e.to_string().contains("invalid")),
        }
    }
}
```

### Round-Trip Invariants

Test that serialization/deserialization preserves data.

```rust
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ICommand {
    pub cmd: String,
    pub args: serde_json::Value,
}

proptest! {
    #[test]
    fn prop_ipc_roundtrip(cmd in any::<ICommand>()) {
        /// INVARIANT: IPC serialization round-trip preserves data
        let serialized = serde_json::to_string(&cmd).unwrap();
        let deserialized: ICommand = serde_json::from_str(&serialized).unwrap();
        prop_assert_eq!(cmd, deserialized);
    }

    #[test]
    fn prop_json_value_roundtrip(value in any::<serde_json::Value>()) {
        /// INVARIANT: JSON serialization round-trip preserves data
        let serialized = serde_json::to_string(&value).unwrap();
        let deserialized: serde_json::Value = serde_json::from_str(&serialized).unwrap();
        prop_assert_eq!(value, deserialized);
    }
}
```

### Numeric Boundary Testing

Test behavior at numeric boundaries.

```rust
proptest! {
    #[test]
    fn prop_window_size_constraints(width in prop::num::i32::ANY, height in prop::num::i32::ANY) {
        /// INVARIANT: Window size respects min/max constraints
        let mut window = WindowState::new();
        window.set_size(width, height);

        let (actual_width, actual_height) = window.size();

        // Invariant: Width constrained to [400, 4096]
        prop_assert!(actual_width >= 400 && actual_width <= 4096,
                     "Width {} should be in range [400, 4096]", actual_width);

        // Invariant: Height constrained to [300, 4096]
        prop_assert!(actual_height >= 300 && actual_height <= 4096,
                     "Height {} should be in range [300, 4096]", actual_height);
    }

    #[test]
    fn prop_volume_constraints(volume in prop::num::u32::ANY) {
        /// INVARIANT: Volume level constrained to [0, 100]
        let clamped = volume.clamp(0, 100);

        prop_assert!(clamped <= 100, "Volume {} should not exceed 100", clamped);
        prop_assert!(clamped >= 0, "Volume {} should not be negative", clamped);
    }
}
```

### Idempotency Testing

Test that operations can be called multiple times safely.

```rust
proptest! {
    #[test]
    fn prop_fullscreen_toggle_idempotence(initial_state in prop::sample::select(vec![true, false])) {
        /// INVARIANT: Fullscreen toggle is idempotent (even toggles = original state)
        let mut window = WindowState::new();
        window.set_fullscreen(initial_state);

        // Toggle twice
        window.toggle_fullscreen();
        window.toggle_fullscreen();

        // Invariant: State should be unchanged after even number of toggles
        prop_assert_eq!(window.is_fullscreen(), initial_state);
    }

    #[test]
    fn prop_mute_toggle_idempotence(initial_volume in prop::num::u32::ANY) {
        /// INVARIANT: Mute toggle is idempotent
        let mut audio = AudioState::new();
        audio.set_volume(initial_volume);

        // Mute
        audio.toggle_mute();
        assert!(audio.is_muted());

        // Unmute
        audio.toggle_mute();
        assert!(!audio.is_muted());

        // Invariant: Volume unchanged after mute/unmute cycle
        prop_assert_eq!(audio.volume(), initial_volume.clamp(0, 100));
    }
}
```

**Key Points:**
- Use `proptest! { ... }` macro for property tests
- Test invariants (properties that must always hold true)
- Document invariants in docstrings with `/// INVARIANT:`
- Use `prop_assert_eq!` and `prop_assert!` for better failure messages
- Set `#[proptest_config]` for custom test counts (default: 256 cases)

**See also:** `docs/PROPERTY_TESTING_PATTERNS.md` (proptest section)

---

## Tauri Integration Testing

### IPC Command Tests

Test Tauri IPC commands that bridge frontend and backend.

```rust
#[cfg(test)]
#[cfg_attr(mobile, tauri::mobile_entry_point)]
mod tests {
    use tauri::Manager;
    use serde_json::json;

    #[test]
    fn test_invoke_handler() {
        let app = tauri::test::mock_app();
        let result = app.emit_all("test-event", json!({"test": "payload"}));
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_file_open_command() {
        let app = tauri::test::mock_app();

        // Invoke open_file command
        let result = app.emit_all("open_file", json!({
            "path": "/path/to/file.txt"
        }));

        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_system_info_command() {
        let app = tauri::test::mock_app();

        // Invoke get_system_info command
        let info = get_system_info(&app).await;

        assert_eq!(info.platform, std::env::consts::OS);
        assert_eq!(info.arch, std::env::consts::ARCH);
        assert!(!info.version.is_empty());
    }
}
```

### Window Operations

Test window management (minimize, maximize, close).

```rust
#[test]
fn test_window_creation() {
    let app = tauri::test::mock_app();
    let window = app.get_window("main").unwrap();

    assert_eq!(window.label(), "main");
}

#[test]
fn test_window_minimize() {
    let mut window = WindowState::new();

    // Initially not minimized
    assert!(!window.is_minimized());

    // Minimize
    window.minimize();
    assert!(window.is_minimized());

    // Unminimize
    window.unminimize();
    assert!(!window.is_minimized());
}

#[test]
fn test_window_fullscreen_toggle() {
    let mut window = WindowState::new();

    // Initially not fullscreen
    assert!(!window.is_fullscreen());

    // Toggle fullscreen
    window.toggle_fullscreen();
    assert!(window.is_fullscreen());

    // Toggle again
    window.toggle_fullscreen();
    assert!(!window.is_fullscreen());
}
```

### System Tray Tests

Test system tray icon and menu interactions.

```rust
#[cfg(test)]
mod tray_tests {
    use super::*;

    #[test]
    fn test_tray_icon_creation() {
        let tray = SystemTray::new();

        assert!(tray.is_visible());
        assert_eq!(tray.tooltip(), "Atom");
    }

    #[test]
    fn test_tray_menu_structure() {
        let tray = SystemTray::new();
        let menu = tray.get_menu();

        // Verify menu items exist
        assert!(menu.has_item("show"));
        assert!(menu.has_item("hide"));
        assert!(menu.has_item("quit"));
    }

    #[test]
    fn test_tray_click_handler() {
        let mut tray = SystemTray::new();

        // Simulate tray icon click
        tray.on_click();
        assert!(tray.is_window_visible());

        // Click again to hide
        tray.on_click();
        assert!(!tray.is_window_visible());
    }

    #[test]
    fn test_tray_menu_item_click() {
        let mut tray = SystemTray::new();

        // Click "Quit" menu item
        tray.on_menu_item_click("quit");
        assert!(tray.should_quit());
    }
}
```

**Key Points:**
- Use `tauri::test::mock_app()` for integration tests
- Test IPC command invocation and response handling
- Test window operations (minimize, maximize, fullscreen, close)
- Test system tray interactions (icon clicks, menu items)

---

## Platform-Specific Patterns

### Windows

Windows-specific tests for file dialogs, taskbar, and registry access.

```rust
#[cfg(target_os = "windows")]
#[test]
fn test_windows_file_dialog() {
    let path = PathBuf::from("C:\\Users\\Test\\file.txt");

    assert!(path.is_absolute());
    assert!(path.starts_with("C:\\"));
    assert_eq!(path.extension().unwrap(), "txt");
}

#[cfg(target_os = "windows")]
#[test]
fn test_windows_drive_letter_parsing() {
    let test_cases = vec![
        ("C:", "C"),
        ("D:\\", "D"),
        ("E:\\path\\to\\file", "E"),
    ];

    for (path, expected_drive) in test_cases {
        let parsed = extract_drive_letter(path);
        assert_eq!(parsed, expected_drive);
    }
}

#[cfg(target_os = "windows")]
#[test]
fn test_windows_temp_directory_format() {
    let temp = std::env::var("TEMP").unwrap();
    let temp_path = PathBuf::from(&temp);

    // Windows temp paths contain backslashes
    assert!(temp.to_string_lossy().contains('\\'));

    // Verify directory exists
    assert!(temp_path.exists());
    assert!(temp_path.is_dir());
}

#[cfg(target_os = "windows")]
#[test]
fn test_windows_environment_variables() {
    let appdata = std::env::var("APPDATA").ok();
    let userprofile = std::env::var("USERPROFILE").ok();

    assert!(appdata.is_some() || userprofile.is_some());

    if let Some(appdata_path) = appdata {
        assert!(appdata_path.contains('\\'));
    }
}
```

### macOS

macOS-specific tests for menu bar, dock, and file system.

```rust
#[cfg(target_os = "macos")]
#[test]
fn test_macos_app_support_dir() {
    let support_dir = dirs_next::config_dir();
    assert!(support_dir.is_some());

    let dir = support_dir.unwrap();
    let dir_str = dir.to_string_lossy();

    // macOS Application Support directory
    assert!(dir_str.contains("Application Support") || dir_str.contains(".config"));

    // Verify directory exists
    assert!(dir.exists());
    assert!(dir.is_dir());
}

#[cfg(target_os = "macos")]
#[test]
fn test_macos_path_separator() {
    let separator = get_platform_separator();
    assert_eq!(separator, "/");

    let path = PathBuf::from("/Users/test/file.txt");
    assert!(path.is_absolute());
    assert!(path.starts_with("/"));
    assert!(!path.to_string_lossy().contains('\\'));
}

#[cfg(target_os = "macos")]
#[test]
fn test_macos_home_directory() {
    let home = dirs_next::home_dir();
    assert!(home.is_some());

    let home_dir = home.unwrap();
    let home_str = home_dir.to_string_lossy();

    // Home directory starts with /Users
    assert!(home_str.starts_with("/Users"));

    // Verify directory exists
    assert!(home_dir.exists());
    assert!(home_dir.is_dir());
}

#[cfg(target_os = "macos")]
#[test]
fn test_macos_bundle_identifier() {
    let bundle_id = get_bundle_identifier();

    // Bundle identifier format: com.company.app
    assert!(bundle_id.contains('.'));
    assert_eq!(bundle_id.split('.').count(), 3);
}
```

### Linux

Linux-specific tests for XDG paths, window managers, and file pickers.

```rust
#[cfg(target_os = "linux")]
#[test]
fn test_linux_xdg_config() {
    let config = std::env::var("XDG_CONFIG_HOME").ok();
    let home = std::env::var("HOME").ok();

    // Either XDG_CONFIG_HOME or HOME should be set
    assert!(config.is_some() || home.is_some());

    if let Some(home_dir) = home {
        let expected_config = format!("{}/.config", home_dir);
        assert_eq!(config.unwrap_or(expected_config), expected_config);
    }
}

#[cfg(target_os = "linux")]
#[test]
fn test_linux_path_separator() {
    let separator = get_platform_separator();
    assert_eq!(separator, "/");

    let path = PathBuf::from("/home/user/file.txt");
    assert!(path.is_absolute());
    assert!(path.starts_with("/"));
    assert!(!path.to_string_lossy().contains('\\'));
}

#[cfg(target_os = "linux")]
#[test]
fn test_linux_temp_directory() {
    let temp = get_temp_dir();
    let temp_str = temp.to_string_lossy();

    // Linux temp paths use forward slashes
    assert!(temp_str.contains('/'));
    assert!(!temp_str.contains('\\'));

    // Common temp directories
    let is_tmp_or_tmpdir = temp_str.contains("/tmp") || temp_str.contains("/tmpdir");
    assert!(is_tmp_or_tmpdir);

    // Verify directory exists
    assert!(temp.exists());
    assert!(temp.is_dir());
}

#[cfg(target_os = "linux")]
#[test]
fn test_linux_desktop_file() {
    let desktop_file = PathBuf::from("/usr/share/applications/atom.desktop");

    // Desktop file may or may not exist (depends on installation)
    if desktop_file.exists() {
        let contents = std::fs::read_to_string(&desktop_file).unwrap();
        assert!(contents.contains("[Desktop Entry]"));
        assert!(contents.contains("Exec="));
    }
}
```

**Key Points:**
- Use `#[cfg(target_os = "...")]` for compile-time platform filtering
- Test platform-specific paths (C:\ on Windows, /Users on macOS, /home on Linux)
- Test environment variables (APPDATA on Windows, XDG_CONFIG_HOME on Linux)
- Test file system differences (path separators, case sensitivity)

---

## Coverage (tarpaulin)

### Coverage Baseline

**Current Status:** 65-70% estimated (Phase 142 complete)

| Module | Target | Current | Gap |
|--------|--------|---------|-----|
| IPC Commands | 80% | 65% | 15% |
| Device Capabilities | 50% | 15% | 35% |
| System Tray | 60% | 45% | 15% |
| File Dialogs | 80% | 40% | 40% |
| Window Operations | 70% | 55% | 15% |

### Generate Coverage Report

```bash
# HTML report (visual inspection)
cargo tarpaulin --out Html --output-dir coverage-report

# JSON report (CI/CD integration)
cargo tarpaulin --out Json --output-dir coverage

# XML report (Cobertura format)
cargo tarpaulin --out Xml --output-dir coverage

# Combine multiple formats
cargo tarpaulin --out Html --out Json --output-dir coverage-report
```

### View Coverage Report

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

### Coverage Thresholds

```bash
# Enforce coverage threshold (fails if below 40%)
cargo tarpaulin --fail-under 40 --out Html --output-dir coverage-report

# Local development (informational, no enforcement)
cargo tarpaulin --fail-under 0 --out Html --output-dir coverage-report

# CI/CD enforcement (fails build if below threshold)
cargo tarpaulin --fail-under 40 --out Json --output-dir coverage
```

### tarpaulin Configuration

Create `tarpaulin.toml` for consistent configuration:

```toml
[exclude-files]
# Exclude test files from coverage calculations
patterns = ["tests/*", "*/tests/*"]

[report]
# Output formats: HTML for visual inspection, JSON for CI/CD
out = ["Html", "Json"]
output-dir = "coverage-report"

[features]
# Coverage threshold for desktop (40% target)
coverage_threshold = 40

[enforcement]
# Coverage enforcement settings
ci_threshold = 40
pr_threshold = 35  # Allow 5% gap during PR review
main_threshold = 40  # Strict enforcement on main branch

[engine]
# Use ptrace for compatibility across platforms
default = "ptrace"
```

### Coverage Workflow

1. **Generate coverage report:**
   ```bash
   cargo tarpaulin --out Html --output-dir coverage-report
   ```

2. **Open HTML report:**
   ```bash
   open coverage-report/index.html
   ```

3. **Identify uncovered lines:**
   - Red lines in HTML report
   - Focus on high-priority modules (IPC Commands, Device Capabilities)

4. **Add tests for uncovered lines:**
   - Write unit tests for uncovered functions
   - Write integration tests for uncovered code paths

5. **Verify coverage increase:**
   ```bash
   cargo tarpaulin --fail-under 40 --out Html --output-dir coverage-report
   ```

**See also:** `docs/DESKTOP_COVERAGE.md` (detailed coverage tracking and trending)

---

## CI/CD

### GitHub Actions Workflow

The `.github/workflows/desktop-coverage.yml` workflow generates coverage reports on every push.

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

      - name: Run desktop tests
        working-directory: ./frontend-nextjs/src-tauri
        run: cargo test --verbose

      - name: Generate coverage
        working-directory: ./frontend-nextjs/src-tauri
        run: |
          cargo tarpaulin --out Json --output-dir coverage -- --test-threads=1

      - name: Enforce 40% threshold
        working-directory: ./frontend-nextjs/src-tauri
        run: |
          COVERAGE=$(node -p "JSON.parse(require('fs').readFileSync('coverage/coverage.json')).coverage")
          if (( $(echo "$COVERAGE < 40" | bc -l) )); then
            echo "Coverage $COVERAGE% below 40% threshold"
            exit 1
          fi

      - name: Upload coverage artifact
        uses: actions/upload-artifact@v4
        with:
          name: desktop-coverage
          path: frontend-nextjs/src-tauri/coverage/
          retention-days: 30
```

### Coverage Enforcement

Coverage is automatically enforced on all pull requests and pushes to main:

- **PRs:** 35% threshold (allows 5% gap during development)
- **Main branch:** 40% threshold (strict enforcement)
- **Failure:** Build fails and PR cannot merge

**How it works:**
1. Tarpaulin runs with `--fail-under` flag during CI/CD
2. If coverage below threshold, tarpaulin exits with error code
3. GitHub Actions workflow fails, blocking PR merge
4. PR comment shows coverage gap to target with actionable next steps

### Local Development

Run coverage locally without enforcement:

```bash
cd frontend-nextjs/src-tauri
cargo tarpaulin --fail-under 0 --out Html --output-dir coverage-report
```

Run with enforcement to verify before pushing:

```bash
cargo tarpaulin --fail-under 40 --out Html --output-dir coverage-report
```

**Enforcement workflow:**
1. Add tests for uncovered lines (see HTML report)
2. Run `cargo tarpaulin --fail-under 40` locally to verify
3. If coverage meets threshold, push to PR
4. CI/CD verifies and allows merge

---

## Test Helpers

### Platform Helpers Module

The `tests/helpers/platform_helpers.rs` module provides utility functions for platform-specific testing.

```rust
use std::path::PathBuf;

/// Get current platform string
pub fn get_current_platform() -> &'static str {
    if cfg!(target_os = "windows") {
        "windows"
    } else if cfg!(target_os = "macos") {
        "macos"
    } else if cfg!(target_os = "linux") {
        "linux"
    } else {
        "unknown"
    }
}

/// Check if current platform matches expected platform
pub fn is_platform(expected: &str) -> bool {
    get_current_platform() == expected
}

/// Panic if not on specified platform
pub fn cfg_assert(platform: &str) {
    assert!(is_platform(platform),
            "Not on {} platform (current: {})", platform, get_current_platform());
}

/// Get platform-specific temp directory
pub fn get_temp_dir() -> PathBuf {
    std::env::temp_dir()
}

/// Get platform-specific path separator
pub fn get_platform_separator() -> &'static str {
    if cfg!(target_os = "windows") {
        "\\"
    } else {
        "/"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_current_platform() {
        let platform = get_current_platform();
        assert!(!platform.is_empty());
        assert!(["windows", "macos", "linux", "unknown"].contains(&platform));
    }

    #[test]
    fn test_is_platform() {
        let current = get_current_platform();
        assert!(is_platform(current));
        assert!(!is_platform("fake_platform"));
    }

    #[test]
    fn test_cfg_assert() {
        cfg_assert(get_current_platform()); // Should not panic
    }

    #[test]
    fn test_get_temp_dir() {
        let temp = get_temp_dir();
        assert!(temp.exists());
        assert!(temp.is_dir());
    }

    #[test]
    fn test_get_platform_separator() {
        let separator = get_platform_separator();
        if cfg!(target_os = "windows") {
            assert_eq!(separator, "\\");
        } else {
            assert_eq!(separator, "/");
        }
    }
}
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
use helpers::platform_helpers::*;

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

#[test]
fn test_platform_detection() {
    let platform = get_current_platform();
    assert!(!platform.is_empty());

    if is_platform("windows") {
        assert_eq!(get_platform_separator(), "\\");
    } else {
        assert_eq!(get_platform_separator(), "/");
    }
}
```

---

## Troubleshooting

### Issue 1: tarpaulin Linking Errors on macOS

**Problem:** cargo-tarpaulin fails to compile on macOS with linking errors.

**Error:**
```
Error: failed to run custom build command for `tarpaulin`
cc failed with exit code 1
```

**Cause:** tarpaulin has known compatibility issues on macOS x86_64 and ARM architectures.

**Solutions:**

1. **Use CI/CD (Recommended):**
   - Push to GitHub and let the workflow run on ubuntu-latest runner
   - Download coverage artifact from Actions tab
   - CI/CD uses ubuntu-latest which avoids linking issues

2. **Use Cross-Compilation:**
   ```bash
   cargo install cross
   cross test --target x86_64-unknown-linux-gnu
   ```

3. **Use Rosetta 2 (macOS ARM only):**
   ```bash
   arch -x86_64 cargo tarpaulin --config tarpaulin.toml
   ```

**See also:** `docs/DESKTOP_COVERAGE.md` (ARM Mac Limitations section)

---

### Issue 2: cfg! Tests Not Running on Other Platforms

**Problem:** Platform-specific tests with `#[cfg(target_os = "windows")]` don't run on macOS or Linux.

**Error:**
```
test result: ok. 0 passed, 0 failed, 0 ignored, 0 measured
```

**Cause:** This is **expected behavior**, not a bug. `#[cfg]` attributes perform compile-time filtering, so tests only compile and run on matching platforms.

**Verification:**

```bash
# Check which tests are compiled
cargo test --list | grep platform

# Expected output:
# test_windows_file_dialog_open (only on Windows)
# test_macos_app_support_dir (only on macOS)
# test_linux_xdg_config (only on Linux)
```

**How to test cross-platform code:**

1. **Use cfg! macro for runtime checks:**
   ```rust
   #[test]
   fn test_platform_detection_logic() {
       let platform = if cfg!(target_os = "windows") {
           "windows"
       } else if cfg!(target_os = "macos") {
           "macos"
       } else {
           "linux"
       };

       assert!(!platform.is_empty());
   }
   ```

2. **Test on actual target platforms:**
   - Use GitHub Actions matrix strategy (runs tests on Windows, macOS, Linux)
   - Use virtual machines for local testing

3. **Accept platform-specific test gaps:**
   - Document which tests run on which platforms
   - Use CI/CD to verify all platform-specific tests pass

---

### Issue 3: Async Test Panics

**Problem:** Async tests fail with "panic in async function" or "runtime not found" errors.

**Error:**
```
thread 'test_async_device_capability' panicked at 'no tokio runtime found'
```

**Cause:** Missing `#[tokio::test]` attribute on async test functions.

**Solution:**

**Wrong:**
```rust
#[test]
async fn test_async_device_capability() {  // Missing #[tokio::test]
    let result = get_device_capability("camera").await;
    assert!(result.is_ok());
}
```

**Correct:**
```rust
#[tokio::test]  // Use tokio::test attribute for async tests
async fn test_async_device_capability() {
    let result = get_device_capability("camera").await;
    assert!(result.is_ok());
}
```

**Key Points:**
- Use `#[tokio::test]` for async test functions (not `#[test]`)
- `#[tokio::test]` creates a tokio runtime for the test
- Do not use `#[test]` with async functions

---

### Issue 4: GUI Tests Failing

**Problem:** Tests that interact with GUI components (windows, dialogs, menus) fail with "GUI context not available" errors.

**Error:**
```
thread 'test_window_creation' panicked at 'failed to create window: no GUI context available'
```

**Cause:** GUI tests require actual GUI context (window system, display server) which is not available in headless CI/CD environments or when running tests without a display.

**Solutions:**

1. **Use unit tests instead (recommended):**
   - Test business logic without GUI dependencies
   - Test state management, IPC commands, data processing

   ```rust
   // GOOD: Test window state logic (no GUI required)
   #[test]
   fn test_window_minimize_logic() {
       let mut window = WindowState::new();
       assert!(!window.is_minimized());

       window.minimize();
       assert!(window.is_minimized());
   }
   ```

2. **Mock GUI dependencies:**
   - Create mock implementations of GUI components
   - Test interaction logic without actual GUI

   ```rust
   struct MockWindow {
       minimized: bool,
   }

   impl MockWindow {
       fn minimize(&mut self) {
           self.minimized = true;
       }
   }

   #[test]
   fn test_mock_window_minimize() {
       let mut window = MockWindow { minimized: false };
       window.minimize();
       assert!(window.minimized);
   }
   ```

3. **Use integration tests with manual QA:**
   - Run GUI tests locally with display available
   - Document manual QA steps for GUI interactions
   - Use CI/CD for unit/integration tests, manual QA for GUI

**Key Points:**
- GUI tests require display server (X11, Wayland, Windows Desktop Manager)
- Headless CI/CD environments don't have display servers
- Focus on unit tests for business logic, use manual QA for GUI interactions

---

## Best Practices

### 1. Use #[cfg(target_os)] for Platform-Specific Tests

Use compile-time platform filtering for platform-specific tests.

**Do:**
```rust
#[cfg(target_os = "windows")]
#[test]
fn test_windows_file_dialog() {
    // Windows-specific test code
}

#[cfg(target_os = "macos")]
#[test]
fn test_macos_app_support_dir() {
    // macOS-specific test code
}
```

**Don't:**
```rust
#[test]
fn test_platform_specific() {
    if cfg!(target_os = "windows") {
        // Windows test code
    } else if cfg!(target_os = "macos") {
        // macOS test code
    }
}
```

**Why:** Compile-time filtering has zero runtime overhead and produces cleaner test output.

---

### 2. Property Test Invariants with proptest

Test invariants (properties that must always hold) across hundreds of randomly generated inputs.

**Do:**
```rust
proptest! {
    #[test]
    fn prop_path_normalization(path in "[a-zA-Z0-9_/]+") {
        let normalized = normalize_path(&path);
        assert!(normalized.contains('/'));
        assert!(!normalized.contains('\\'));
    }
}
```

**Don't:**
```rust
#[test]
fn test_path_normalization_example() {
    let normalized = normalize_path("path/to/file");
    assert!(normalized.contains('/'));
}
```

**Why:** Property tests find edge cases that example-based tests miss (empty strings, special characters, Unicode).

**See also:** `docs/PROPERTY_TESTING_PATTERNS.md` (proptest section)

---

### 3. Test Error Paths Explicitly

Test error handling with explicit error cases.

**Do:**
```rust
#[test]
fn test_file_not_found_error() {
    let result = read_file("nonexistent_file.txt");
    assert!(result.is_err());
    assert_eq!(result.unwrap_err().kind(), io::ErrorKind::NotFound);
}

#[test]
fn test_invalid_input_error() {
    let result = validate_device_capability("");
    assert!(result.is_err());
    assert_eq!(result.unwrap_err(), Error::InvalidInput);
}
```

**Don't:**
```rust
#[test]
fn test_file_read_success() {
    let result = read_file("test.txt");
    assert!(result.is_ok()); // Only tests happy path
}
```

**Why:** Error handling is critical for desktop stability. Test both success and error paths.

---

### 4. Use --test-threads=1 for tarpaulin

Run tarpaulin with single-threaded tests for accurate coverage.

**Do:**
```bash
cargo tarpaulin --out Json --output-dir coverage -- --test-threads=1
```

**Don't:**
```bash
cargo tarpaulin --out Json --output-dir coverage
```

**Why:** Multi-threaded test execution can cause race conditions in coverage tracking, leading to inaccurate results.

---

### 5. Mock External Dependencies

Mock external dependencies (file system, hardware, OS APIs) for reliable tests.

**Do:**
```rust
#[test]
fn test_file_operations_with_mock() {
    let temp_dir = get_temp_dir();
    let test_file = temp_dir.join("test.txt");

    // Create test file
    fs::write(&test_file, b"test content").unwrap();

    // Test file operations
    let result = read_file(&test_file);
    assert!(result.is_ok());

    // Cleanup
    fs::remove_file(&test_file).unwrap();
}
```

**Don't:**
```rust
#[test]
fn test_file_operations_with_real_files() {
    let result = read_file("C:\\Windows\\System32\\config\\system"); // Dangerous!
    assert!(result.is_ok());
}
```

**Why:** Tests should not depend on external state (system files, hardware devices, network). Use temp directories and mocks.

---

## Further Reading

### Internal Documentation

- **Property Testing:** `docs/PROPERTY_TESTING_PATTERNS.md` (proptest section for invariants, generators, strategies)
- **Desktop Coverage:** `docs/DESKTOP_COVERAGE.md` (detailed coverage tracking, trending, gap analysis)
- **Cross-Platform Coverage:** `docs/CROSS_PLATFORM_COVERAGE.md` (weighted coverage, platform minimums, quality gates)
- **Phase 141 Summary:** `.planning/phases/141-desktop-coverage-expansion/141-06-SUMMARY.md` (platform-specific testing infrastructure)
- **Phase 142 Summary:** `.planning/phases/142-desktop-rust-backend/142-07-SUMMARY.md` (coverage enforcement and integration tests)

### External Resources

- **Tauri Testing:** [Tauri Testing Guide](https://tauri.app/v1/guides/testing/) - Official Tauri testing documentation
- **Rust Testing:** [The Rust Testing Guide](https://doc.rust-lang.org/book/ch11-00-testing.html) - Official Rust book on testing
- **proptest:** [proptest Documentation](https://altsysrq.github.io/proptest-book/) - Property testing in Rust
- **tarpaulin:** [tarpaulin GitHub](https://github.com/rpsec/tarpaulin) - Code coverage for Rust projects

### Test Patterns Reference

- **Backend Testing:** `backend/tests/docs/COVERAGE_GUIDE.md` (pytest patterns, fixtures, coverage)
- **Frontend Testing:** `docs/FRONTEND_TESTING_GUIDE.md` (Jest, React Testing Library, MSW)
- **Mobile Testing:** `docs/MOBILE_TESTING_GUIDE.md` (jest-expo, React Native Testing Library)

---

## See Also

### Testing Documentation

- **[Testing Documentation Index](TESTING_INDEX.md)** - Central hub for all testing documentation
- **[Desktop Coverage](DESKTOP_COVERAGE.md)** - Detailed coverage analysis and gap tracking

### Platform Guides

- **[Frontend Testing Guide](FRONTEND_TESTING_GUIDE.md)** - Jest, React Testing Library, MSW, jest-axe
- **[Mobile Testing Guide](MOBILE_TESTING_GUIDE.md)** - jest-expo, React Native Testing Library
- **Backend:** [Backend Coverage Guide](TESTING_INDEX.md) - pytest, Hypothesis, Schemathesis

### Cross-Platform Testing

- **[Property Testing Patterns](PROPERTY_TESTING_PATTERNS.md)** - FastCheck, Hypothesis, proptest
- **[E2E Testing Guide](E2E_TESTING_GUIDE.md)** - Playwright, API-level tests, Tauri integration
- **[Cross-Platform Coverage](CROSS_PLATFORM_COVERAGE.md)** - Weighted coverage, platform minimums

---

**Document Version:** 1.0
**Last Updated:** March 7, 2026
**Maintainer:** Testing Team

**For questions or contributions, see:** `docs/TESTING_INDEX.md`
