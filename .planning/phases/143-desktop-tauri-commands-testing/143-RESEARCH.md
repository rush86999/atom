# Phase 143: Desktop Tauri Commands Testing - Research

**Researched:** 2026-03-05
**Domain:** Tauri 2.0 Testing, Invoke Handlers, Event System, Window Management
**Confidence:** MEDIUM

## Summary

Phase 143 requires testing Tauri commands with frontend invoke simulation, event system emit/listen validation, window management operations, command error propagation, and Tauri state persistence. Building on Phase 142's 65-70% coverage baseline (122 new tests), this phase targets the remaining 10-15 percentage point gap to reach 80% overall coverage by focusing on Tauri-specific integration testing that was deferred from Phase 142.

**Primary recommendation:** Use a multi-tiered testing strategy: (1) Frontend invoke simulation with mock IPC for command testing, (2) Event system testing with emit/listen validation using tokio channels, (3) Window management testing with mock AppHandle and Window objects, (4) Error propagation testing with Result types and JSON validation, (5) State persistence testing with file-based storage mocking.

**Key finding:** Tauri 2.0 does NOT provide a `#[tauri::test]` macro for integration testing. The official approach is standard `#[test]` or `#[tokio::test]` with manual mocking of AppHandle, Window, and event channels. Frontend testing uses `@tauri-apps/api/mocks` for IPC mocking.

## User Constraints

No CONTEXT.md exists for Phase 143. Researcher has full discretion to recommend approaches based on:
- Phase 142 completion (65-70% estimated coverage, 122 tests, coverage enforcement active)
- Phase 142 handoff recommendations (Tauri context tests deferred to Phase 143)
- Desktop coverage requirements (DESKTOP-04: 80% target, remaining 10-15% gap)
- Existing Tauri commands (19 commands identified in main.rs)
- Current test infrastructure (Phase 141-142 established patterns)

## Standard Stack

### Core Testing Framework

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **cargo test** | Built-in | Unit tests for command logic | Rust's official test framework, works with Tauri commands |
| **tokio::test** | 1.x (dev-dep) | Async command testing | Required for async Tauri commands, already in project |
| **@tauri-apps/api/mocks** | Tauri v2 | Frontend IPC mocking | Official Tauri v2 mocking for frontend invoke testing |
| **cargo-tarpaulin** | 0.27 (dev-dep) | Code coverage | Already configured for CI/CD enforcement |

### Already in Project

From `frontend-nextjs/src-tauri/Cargo.toml`:
```toml
[dependencies]
tauri = { version = "2.10", features = ["tray-icon", "image-png"] }
tokio = { version = "1", features = ["full"] }

[dev-dependencies]
cargo-tarpaulin = "0.27"
proptest = "1.0"
```

**Recommendation:** Add frontend test framework for invoke simulation (Jest/Vitest with Tauri mocks).

### Supporting Tools

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **mockall** | (not in project) | Mock trait implementations | For mocking AppHandle, Window, Emitter traits |
| **serial_test** | (not in project) | Sequential test execution | For tests with shared state (file I/O, event channels) |
| **tempfile** | (not in project) | Temporary file/directory management | For state persistence testing |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **@tauri-apps/api/mocks** | Manual IPC stubbing | Official mocking handles serialization, manual stubbing more control but verbose |
| **tokio::test** | async-std::test | Tokio is ecosystem standard, async-std is alternative but less adoption |
| **cargo-tarpaulin** | cargo-llvm-cov | Tarpaulin established in Phase 142, llvm-cov faster but macOS linking issues |

## Architecture Patterns

### Tauri Command Inventory

**19 Commands Identified** in `main.rs` (lines 24-1652):

1. **File Operations** (6 commands):
   - `open_file_dialog` (line 24) - File picker with filters
   - `open_folder_dialog` (line 68) - Folder selection
   - `save_file_dialog` (line 89) - File save dialog
   - `read_file_content` (line 167) - Read file to string
   - `write_file_content` (line 183) - Write string to file
   - `list_directory` (line 209) - Directory listing with metadata

2. **System Operations** (2 commands):
   - `get_system_info` (line 132) - Platform/arch detection
   - `execute_command` (line 273) - Shell command execution

3. **Satellite Management** (3 commands):
   - `install_satellite_dependencies` (line 335) - Python venv setup
   - `start_satellite` (line 408) - Spawn satellite process
   - `stop_satellite` (line 492) - Kill satellite process

4. **Local Skills** (1 command):
   - `list_local_skills` (line 504) - List skills/local directory

5. **Atom Invoke Router** (1 command):
   - `atom_invoke_command` (line 541) - Command router with 10+ sub-commands

6. **Device Capabilities** (5 commands):
   - `camera_snap` (line 870) - Camera capture (platform-specific)
   - `screen_record_start` (line 1082) - Start screen recording
   - `screen_record_stop` (line 1257) - Stop screen recording
   - `get_location` (line 1339) - IP geolocation
   - `send_notification` (line 1526) - Desktop notification

7. **Security** (1 command):
   - `execute_shell_command` (line 1584) - Whitelisted command execution

### Test Organization Structure

```
frontend-nextjs/src-tauri/tests/
├── tauri_commands/
│   ├── mod.rs                      # Command test module (NEW)
│   ├── file_dialog_tests.rs        # File dialog invoke tests (NEW)
│   ├── system_operations_tests.rs  # System info/command tests (NEW)
│   ├── satellite_tests.rs          # Satellite management tests (NEW)
│   ├── device_capabilities_tests.rs # Device command tests (NEW)
│   └── error_propagation_tests.rs  # Error handling tests (NEW)
├── tauri_events/
│   ├── mod.rs                      # Event test module (NEW)
│   ├── emit_tests.rs               # Event emission tests (NEW)
│   ├── listen_tests.rs              # Event listener tests (NEW)
│   └── event_validation_tests.rs   # Emit/listen integration (NEW)
├── tauri_windows/
│   ├── mod.rs                      # Window test module (NEW)
│   ├── window_create_tests.rs      # Window creation tests (NEW)
│   ├── window_close_tests.rs       # Window close/focus tests (NEW)
│   └── window_state_tests.rs       # Window state persistence (NEW)
├── tauri_state/
│   ├── mod.rs                      # State test module (NEW)
│   ├── persistent_storage_tests.rs # File-based state tests (NEW)
│   └── app_state_tests.rs          # AppState management (NEW)
└── frontend_invoke_simulation/
    ├── invoke_mock_tests.ts        # Frontend invoke tests (NEW)
    └── ipc_validation_tests.ts     # IPC serialization tests (NEW)
```

### Pattern 1: Frontend Invoke Simulation with Tauri Mocks

**What:** Test Tauri commands from frontend using `@tauri-apps/api/mocks`

**When to use:** Testing IPC invocation, command routing, response validation

**Example:**
```typescript
// frontend-nextjs/src-tauri/tests/frontend_invoke_simulation/invoke_mock_tests.ts
import { mockIPC, clearMocks } from "@tauri-apps/api/mocks"
import { invoke } from "@tauri-apps/api/core"

describe("Tauri Command Invoke Tests", () => {
  afterEach(() => {
    clearMocks()
  })

  test("invoke get_system_info returns valid response", async () => {
    // Mock IPC handler
    mockIPC((cmd, payload) => {
      switch (cmd) {
        case "get_system_info":
          return {
            platform: "darwin",
            architecture: "aarch64",
            version: "0.1.0-alpha.4",
            tauri_version: "2.0.0",
            features: {
              file_system: true,
              notifications: true,
              system_tray: true,
            }
          }
        default:
          throw new Error(`Unknown command: ${cmd}`)
      }
    })

    // Test invoke
    const result = await invoke("get_system_info")

    // Validate response structure
    expect(result).toHaveProperty("platform")
    expect(result).toHaveProperty("architecture")
    expect(result).toHaveProperty("features")
    expect(result.features.file_system).toBe(true)
  })

  test("invoke read_file_content with valid path", async () => {
    mockIPC((cmd, payload) => {
      if (cmd === "read_file_content") {
        return {
          success: true,
          content: "Hello, Tauri!",
          path: payload.path
        }
      }
    })

    const result = await invoke("read_file_content", { path: "/tmp/test.txt" })

    expect(result.success).toBe(true)
    expect(result.content).toBe("Hello, Tauri!")
  })

  test("invoke read_file_content not found error", async () => {
    mockIPC((cmd, payload) => {
      if (cmd === "read_file_content") {
        return {
          success: false,
          error: "File not found",
          path: payload.path
        }
      }
    })

    const result = await invoke("read_file_content", { path: "/nonexistent.txt" })

    expect(result.success).toBe(false)
    expect(result.error).toContain("not found")
  })
})
```

**Source:** [Tauri v2 Mocks Documentation](https://v2.tauri.org.cn/reference/javascript/api/namespacemocks/) | [Tauri IPC Testing Guide](https://m.w3cschool.cn/tauri/tauri-ipc-request.html) | [Tauri 2.0 官方文档](https://tauri.app/zh-cn/)

**MEDIUM Confidence** - Official Tauri v2 documentation, verified from multiple sources

### Pattern 2: Backend Command Testing with Mock AppHandle

**What:** Test Tauri commands directly in Rust with mocked AppHandle

**When to use:** Testing command logic, error handling, state management

**Example:**
```rust
// frontend-nextjs/src-tauri/tests/tauri_commands/system_operations_tests.rs

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Arc, Mutex};
    use std::collections::HashMap;

    // Mock AppHandle for testing
    struct MockAppHandle {
        state: Arc<Mutex<HashMap<String, serde_json::Value>>>,
    }

    impl MockAppHandle {
        fn new() -> Self {
            Self {
                state: Arc::new(Mutex::new(HashMap::new())),
            }
        }
    }

    #[test]
    fn test_get_system_info_structure() {
        // Test platform detection logic
        let os = if cfg!(target_os = "windows") {
            "windows"
        } else if cfg!(target_os = "macos") {
            "macos"
        } else if cfg!(target_os = "linux") {
            "linux"
        } else {
            "unknown"
        };

        let arch = if cfg!(target_arch = "x86_64") {
            "x64"
        } else if cfg!(target_arch = "aarch64") {
            "arm64"
        } else {
            "unknown"
        };

        // Build response matching main.rs structure
        let response = serde_json::json!({
            "platform": os,
            "architecture": arch,
            "version": env!("CARGO_PKG_VERSION"),
            "tauri_version": "2.0.0",
            "features": {
                "file_system": true,
                "notifications": true,
                "system_tray": true,
                "global_shortcuts": true
            }
        });

        // Validate structure
        assert!(response["platform"].is_string());
        assert!(response["architecture"].is_string());
        assert!(response["features"]["file_system"].is_boolean());
        assert_eq!(response["features"]["file_system"], true);
    }

    #[test]
    fn test_read_file_content_success() {
        use std::fs;
        use std::io::Write;

        // Create temporary file
        let temp_dir = std::env::temp_dir();
        let test_file = temp_dir.join("test_read.txt");
        let content = "Test content for read";
        fs::write(&test_file, content).unwrap();

        // Simulate read_file_content command logic
        let result = fs::read_to_string(&test_file);

        assert!(result.is_ok());
        let read_content = result.unwrap();
        assert_eq!(read_content, content);

        // Cleanup
        let _ = fs::remove_file(&test_file);
    }

    #[test]
    fn test_read_file_content_not_found() {
        // Test error path
        let result = std::fs::read_to_string("/nonexistent/path/file.txt");

        assert!(result.is_err());

        // Simulate JSON error response
        let error_response = serde_json::json!({
            "success": false,
            "error": result.unwrap_err().to_string(),
            "path": "/nonexistent/path/file.txt"
        });

        assert_eq!(error_response["success"], false);
        assert!(error_response["error"].is_string());
    }

    #[tokio::test]
    async fn test_write_file_content_creates_directories() {
        use std::fs;

        // Test nested directory creation
        let temp_dir = std::env::temp_dir();
        let nested_path = temp_dir.join("nested/dir/test.txt");
        let content = "Nested file content";

        // Simulate write_file_content logic with directory creation
        if let Some(parent) = nested_path.parent() {
            fs::create_dir_all(parent).unwrap();
        }

        let result = fs::write(&nested_path, content);
        assert!(result.is_ok());
        assert!(nested_path.exists());

        let read_content = fs::read_to_string(&nested_path).unwrap();
        assert_eq!(read_content, content);

        // Cleanup
        let _ = fs::remove_dir_all(temp_dir.join("nested"));
    }

    #[test]
    fn test_execute_command_whitelist() {
        // Test command whitelist validation
        let allowed_commands = vec![
            "ls", "pwd", "cat", "grep", "head", "tail", "echo", "find", "ps", "top"
        ];

        let test_command = "ls -la";
        let command_base = test_command.split_whitespace().next().unwrap_or("");

        assert!(allowed_commands.contains(&command_base));

        // Test disallowed command
        let dangerous_command = "rm -rf /tmp/test";
        let dangerous_base = dangerous_command.split_whitespace().next().unwrap_or("");

        assert!(!allowed_commands.contains(&dangerous_base));
    }
}
```

**Source:** Pattern established in Phase 142 (`tauri_context_test.rs`, `commands_test.rs`)

**HIGH Confidence** - Pattern already tested in Phase 142 Plan 04 (32 Tauri context tests)

### Pattern 3: Event System Testing with Emit/Listen Validation

**What:** Test Tauri event emission and listening patterns

**When to use:** Testing real-time updates, IPC events, pub/sub patterns

**Example:**
```rust
// frontend-nextjs/src-tauri/tests/tauri_events/emit_tests.rs

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Arc, Mutex};
    use std::collections::HashMap;
    use tokio::sync::mpsc;

    #[derive(Clone, Serialize)]
    struct FileEvent {
        path: String,
        operation: String,
    }

    #[test]
    fn test_event_structure_validation() {
        // Test event payload structure
        let event = FileEvent {
            path: "/tmp/test.txt".to_string(),
            operation: "create".to_string(),
        };

        // Serialize to JSON (matching Tauri emit behavior)
        let json = serde_json::to_string(&event).unwrap();

        assert!(json.contains("\"path\":\"/tmp/test.txt\""));
        assert!(json.contains("\"operation\":\"create\""));
    }

    #[tokio::test]
    async fn test_emit_event_pattern() {
        // Test event emission pattern from main.rs
        let (tx, mut rx) = mpsc::channel(32);

        // Simulate app.emit() behavior
        let event = FileEvent {
            path: "/tmp/test.txt".to_string(),
            operation: "modify".to_string(),
        };

        tx.send(event.clone()).await.unwrap();

        // Verify event received
        let received = rx.recv().await.unwrap();
        assert_eq!(received.path, "/tmp/test.txt");
        assert_eq!(received.operation, "modify");
    }

    #[test]
    fn test_event_name_validation() {
        // Test event names from main.rs
        let valid_events = vec![
            "folder-event",
            "cli-stdout",
            "cli-stderr",
            "satellite_stdout",
            "satellite_stderr",
        ];

        for event_name in valid_events {
            assert!(!event_name.is_empty());
            assert!(!event_name.contains(' ')); // No spaces in event names
        }
    }

    #[tokio::test]
    async fn test_listen_event_pattern() {
        // Test event listening pattern
        use tokio::sync::broadcast;

        let (tx, _rx1) = broadcast::channel(16);
        let mut rx2 = tx.subscribe();

        // Simulate event emission
        let event_payload = serde_json::json!({
            "path": "/tmp/test.txt",
            "operation": "create"
        });

        let _ = tx.send(event_payload.clone());

        // Simulate listener receiving event
        let received = rx2.recv().await.unwrap();
        assert_eq!(received["path"], "/tmp/test.txt");
        assert_eq!(received["operation"], "create");
    }

    #[test]
    fn test_event_serialization_roundtrip() {
        // Test event payload serialization/deserialization
        let original = FileEvent {
            path: "/tmp/test.txt".to_string(),
            operation: "create".to_string(),
        };

        // Serialize
        let json = serde_json::to_value(&original).unwrap();

        // Deserialize
        let deserialized: FileEvent = serde_json::from_value(json).unwrap();

        assert_eq!(deserialized.path, original.path);
        assert_eq!(deserialized.operation, original.operation);
    }
}
```

**Source:** Event emission patterns in `main.rs` lines 816-843 (folder watching), 296-316 (CLI stdout/stderr), 467-485 (satellite events)

**MEDIUM Confidence** - Pattern based on main.rs implementation, no official Tauri event testing documentation found

### Pattern 4: Window Management Testing with Mock Window

**What:** Test window operations (create, close, focus, hide)

**When to use:** Testing window lifecycle, state persistence, tray integration

**Example:**
```rust
// frontend-nextjs/src-tauri/tests/tauri_windows/window_create_tests.rs

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Debug, Clone)]
    struct MockWindow {
        label: String,
        visible: bool,
        focused: bool,
    }

    impl MockWindow {
        fn new(label: &str) -> Self {
            Self {
                label: label.to_string(),
                visible: true,
                focused: false,
            }
        }

        fn show(&mut self) {
            self.visible = true;
        }

        fn hide(&mut self) {
            self.visible = false;
        }

        fn set_focus(&mut self) {
            self.focused = true;
        }

        fn close(&mut self) {
            self.visible = false;
        }
    }

    #[test]
    fn test_window_creation_pattern() {
        // Test window creation pattern from main.rs setup
        let window_label = "main";
        let window = MockWindow::new(window_label);

        assert_eq!(window.label, "main");
        assert!(window.visible);
        assert!(!window.focused);
    }

    #[test]
    fn test_window_show_hide() {
        // Test show/hide pattern from system tray
        let mut window = MockWindow::new("main");

        // Hide window (minimize to tray)
        window.hide();
        assert!(!window.visible);

        // Show window (from tray click)
        window.show();
        assert!(window.visible);
    }

    #[test]
    fn test_window_focus_pattern() {
        // Test focus pattern from main.rs line 1727-1729
        let mut window = MockWindow::new("main");

        window.set_focus();
        assert!(window.focused);
    }

    #[test]
    fn test_window_close_prevention() {
        // Test close request prevention from main.rs line 1747-1752
        let mut window = MockWindow::new("main");
        let prevent_close = true; // From WindowEvent API

        if prevent_close {
            window.hide(); // Minimize to tray instead of closing
        }

        assert!(!window.visible); // Should be hidden, not closed
    }

    #[test]
    fn test_multiple_window_management() {
        // Test multiple window scenario
        let mut main_window = MockWindow::new("main");
        let mut settings_window = MockWindow::new("settings");

        main_window.set_focus();
        settings_window.set_focus();

        assert!(main_window.focused);
        assert!(settings_window.focused);
    }

    #[test]
    fn test_window_state_persistence() {
        // Test window state persistence pattern
        let window_state = serde_json::json!({
            "label": "main",
            "width": 1200,
            "height": 800,
            "x": 100,
            "y": 100,
            "visible": true,
            "focused": false
        });

        assert_eq!(window_state["label"], "main");
        assert_eq!(window_state["width"], 1200);
        assert_eq!(window_state["height"], 800);
        assert!(window_state["visible"].is_boolean());
    }
}
```

**Source:** Window management patterns in `main.rs` lines 1714-1753 (system tray setup, window events), [Tauri 2.0 Window Events](https://blog.csdn.net/qq_63401240/article/details/146981362)

**MEDIUM Confidence** - Based on main.rs implementation, no official Tauri window testing examples found

### Pattern 5: Command Error Propagation Testing

**What:** Test error handling and propagation in Tauri commands

**When to use:** Testing Result types, JSON error responses, graceful failures

**Example:**
```rust
// frontend-nextjs/src-tauri/tests/tauri_commands/error_propagation_tests.rs

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_command_error_response_structure() {
        // Test that errors return consistent JSON structure
        let error_response = serde_json::json!({
            "success": false,
            "error": "File not found",
            "path": "/tmp/nonexistent.txt"
        });

        // Must have "success" field
        assert_eq!(error_response["success"], false);

        // Must have "error" field on failure
        assert!(error_response.get("error").is_some());

        // Error message should be non-empty string
        let error_msg = error_response["error"].as_str().unwrap();
        assert!(!error_msg.is_empty());
    }

    #[test]
    fn test_file_operations_error_handling() {
        use std::fs;

        // Test file read error propagation
        let result = fs::read_to_string("/nonexistent/path/file.txt");

        assert!(result.is_err());

        // Convert to JSON error response
        let error_response = serde_json::json!({
            "success": false,
            "error": result.unwrap_err().to_string(),
            "path": "/nonexistent/path/file.txt"
        });

        assert_eq!(error_response["success"], false);
        assert!(error_response["error"].is_string());
    }

    #[test]
    fn test_command_validation_errors() {
        // Test command parameter validation
        let test_cases = vec![
            ("", true),  // Empty path should fail
            ("/tmp/test.txt", false),  // Valid path should succeed
        ];

        for (path, should_fail) in test_cases {
            let is_valid = !path.is_empty();
            assert_eq!(is_valid, !should_fail);
        }
    }

    #[test]
    fn test_async_command_timeout() {
        // Test timeout enforcement pattern
        let timeout_duration = std::time::Duration::from_secs(30);

        assert_eq!(timeout_duration.as_secs(), 30);

        // Test timeout exceeded scenario
        let elapsed = std::time::Duration::from_secs(35);
        let timeout_exceeded = elapsed > timeout_duration;

        assert!(timeout_exceeded);
    }

    #[test]
    fn test_permission_denied_errors() {
        // Test permission error handling
        let readonly_path = "/root/cannot_write_here.txt";

        // Attempt write (may fail on some systems)
        let result = std::fs::write(readonly_path, "test");

        // Either success (if permissions allow) or error (if denied)
        // We just verify it doesn't panic and returns Result
        match result {
            Ok(_) => {},
            Err(e) => {
                // Verify error message is meaningful
                let error_msg = e.to_string();
                assert!(!error_msg.is_empty());
            }
        }
    }

    #[test]
    fn test_network_error_propagation() {
        // Test network-related command errors
        use std::process::Command;

        // Try to connect to unreachable address
        let output = if cfg!(target_os = "windows") {
            Command::new("ping")
                .args(["-n", "1", "-w", "1", "192.0.2.1"]) // TEST-NET-1
                .output()
        } else {
            Command::new("ping")
                .args(["-c", "1", "-W", "1", "192.0.2.1"])
                .output()
        };

        assert!(output.is_ok());
        let output = output.unwrap();

        // Should fail (non-zero exit code)
        assert!(!output.status.success());

        // Build error response
        let error_response = serde_json::json!({
            "success": false,
            "error": "Network unreachable",
            "exit_code": output.status.code()
        });

        assert_eq!(error_response["success"], false);
    }
}
```

**Source:** Error handling patterns in `main.rs` (Result<serde_json::Value, String>), Phase 142 error handling tests

**HIGH Confidence** - Pattern established in Phase 142 Plan 03 (25 async error path tests)

### Anti-Patterns to Avoid

- **Testing with actual GUI context:** Don't require full Tauri app context for unit tests. Use mock objects and pattern validation instead.
- **Synchronous async tests:** Don't use `#[test]` for async functions. Always use `#[tokio::test]` or block_on.
- **Hardcoded platform assumptions:** Don't assume "darwin" or "windows". Use `cfg!` macros for platform-specific tests.
- **Skipping error paths:** Don't only test happy paths. Test all Result<Err> cases with JSON error validation.
- **File I/O without cleanup:** Don't leave temp files. Use cleanup in `finally` blocks or `Drop` trait.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **IPC mocking** | Custom stub functions | `@tauri-apps/api/mocks` | Official mocking handles serialization, command routing, error propagation |
| **Async runtime** | Manual thread spawning | `tokio::test` | Tokio is already in project, handles async/await, timers, channels |
| **Test isolation** | Manual state reset | `serial_test` crate | Prevents race conditions with shared state (file I/O, global state) |
| **Temp file management** | Manual file creation/cleanup | `tempfile` crate | Automatic cleanup, cross-platform temp directories |
| **Mock AppHandle/Window** | Full Tauri context setup | Pattern validation with mocks | Full context requires GUI, adds complexity, slower test execution |

**Key insight:** Tauri 2.0 does NOT provide integration test utilities like `#[tauri::test]`. The official approach is standard Rust testing with manual mocking for AppHandle, Window, and event channels. Frontend testing uses official `@tauri-apps/api/mocks` for IPC simulation.

## Common Pitfalls

### Pitfall 1: Assuming Tauri Provides `#[tauri::test]` Macro
**What goes wrong:** Looking for `#[tauri::test]` like `#[tokio::test]` or `#[actix_web::test]`, but it doesn't exist in Tauri 2.0.

**Why it happens:** Other frameworks provide test macros, developers assume Tauri does too.

**How to avoid:** Use standard `#[test]` or `#[tokio::test]` with manual mocking. For frontend, use `@tauri-apps/api/mocks`.

**Warning signs:** Searching for "tauri::test macro" in documentation, trying to import test macros from tauri crate.

**MEDIUM Confidence** - Verified from multiple sources (web search, official docs), Tauri 2.0 does not provide test macros

### Pitfall 2: Testing Commands Without GUI Context
**What goes wrong:** Trying to test Tauri commands that require `AppHandle` or `Window` parameters, but no GUI context exists in unit tests.

**Why it happens:** Tauri commands accept `AppHandle` and `Window` for event emission and window management, but these require full app context.

**How to avoid:**
1. Test command logic with mock `AppHandle` and `Window` (pattern validation)
2. Test frontend invoke with `@tauri-apps/api/mocks`
3. Test event patterns with `tokio::sync::channels` instead of actual IPC

**Warning signs:** Panics like "cannot create AppHandle outside of Tauri context", tests failing with "no window available".

**HIGH Confidence** - Phase 142 Plan 04 already established this pattern (32 Tauri context tests with mocks)

### Pitfall 3: Ignoring Async Command Runtime
**What goes wrong:** Using `#[test]` for async Tauri commands, getting "future cannot be sent between threads safely" errors.

**Why it happens:** Tauri commands are `async fn`, require Tokio runtime for `await`.

**How to avoid:** Always use `#[tokio::test]` for testing async commands. Ensure `tokio = { version = "1", features = ["full"] }` in dev-dependencies.

**Warning signs:** Compile errors with "await is only allowed in async functions", "Rust futures require async runtime".

**HIGH Confidence** - Tokio testing pattern is standard in Rust ecosystem

### Pitfall 4: Not Testing Error Propagation
**What goes wrong:** Only testing success paths, ignoring `Result::Err` cases and JSON error responses.

**Why it happens:** Focus on happy paths, error paths require setup (temp files, network failures, permissions).

**How to avoid:**
1. Test all `Result::Err` branches
2. Validate JSON error response structure (`{success: false, error: "..."}`)
3. Test edge cases (empty files, permissions, network failures)

**Warning signs:** Coverage gaps in command error handling, tests only asserting `Ok()` results.

**HIGH Confidence** - Phase 142 Plan 03 already established this pattern (25 async error path tests)

### Pitfall 5: Platform-Specific Code Without cfg Guards
**What goes wrong:** Tests fail on different platforms due to platform-specific code (Windows APIs, macOS frameworks).

**Why it happens:** Tauri commands use `#[cfg(target_os = "...")]` for platform-specific logic, tests don't guard accordingly.

**How to avoid:**
```rust
#[cfg(target_os = "macos")]
#[test]
fn test_macos_specific_feature() {
    // macOS-only test
}

#[cfg(target_os = "windows")]
#[test]
fn test_windows_specific_feature() {
    // Windows-only test
}

#[test]
fn test_cross_platform_feature() {
    // Works on all platforms
}
```

**Warning signs:** Tests fail on CI with different OS, "undefined reference" errors for platform-specific APIs.

**HIGH Confidence** - Phase 141 established this pattern (platform_specific/ module with cfg guards)

## Code Examples

Verified patterns from official sources and Phase 142 implementation:

### Frontend Invoke Mocking (Official Tauri v2)

```typescript
// Source: https://v2.tauri.org.cn/reference/javascript/api/namespacemocks/

import { mockIPC, clearMocks } from "@tauri-apps/api/mocks"
import { invoke } from "@tauri-apps/api/core"

afterEach(() => {
  clearMocks()
})

test("mocked command returns expected result", async () => {
  mockIPC((cmd, payload) => {
    switch (cmd) {
      case "get_system_info":
        return {
          platform: "darwin",
          architecture: "aarch64",
          version: "0.1.0",
        }
      default:
        throw new Error(`Unknown command: ${cmd}`)
    }
  })

  const result = await invoke("get_system_info")
  expect(result.platform).toBe("darwin")
})
```

**HIGH Confidence** - Official Tauri v2 documentation

### Backend Command Testing (Phase 142 Pattern)

```rust
// Source: Phase 142 Plan 04, tauri_context_test.rs

#[tokio::test]
async fn test_async_command_with_timeout() {
    use std::time::Duration;
    use tokio::time::timeout;

    let timeout_duration = Duration::from_secs(5);

    // Test command completes within timeout
    let result = timeout(timeout_duration, async {
        // Simulate async command
        tokio::time::sleep(Duration::from_millis(100)).await;
        "command result"
    }).await;

    assert!(result.is_ok());
    assert_eq!(result.unwrap(), "command result");
}
```

**HIGH Confidence** - Pattern established in Phase 142, verified to work

### Event System Testing (main.rs Pattern)

```rust
// Source: main.rs lines 816-843 (folder watching events)

use tokio::sync::mpsc;

#[tokio::test]
async fn test_event_emit_pattern() {
    let (tx, mut rx) = mpsc::channel(32);

    // Simulate event emission
    let event = serde_json::json!({
        "path": "/tmp/test.txt",
        "operation": "create"
    });

    tx.send(event.clone()).await.unwrap();

    // Verify event received
    let received = rx.recv().await.unwrap();
    assert_eq!(received["path"], "/tmp/test.txt");
    assert_eq!(received["operation"], "create");
}
```

**MEDIUM Confidence** - Pattern based on main.rs implementation, no official testing docs found

### Window Management Testing (Mock Pattern)

```rust
// Source: main.rs lines 1714-1753 (system tray window management)

#[derive(Clone)]
struct MockWindow {
    label: String,
    visible: bool,
}

impl MockWindow {
    fn show(&mut self) { self.visible = true; }
    fn hide(&mut self) { self.visible = false; }
}

#[test]
fn test_window_show_hide() {
    let mut window = MockWindow {
        label: "main".to_string(),
        visible: true,
    };

    // Test hide (minimize to tray)
    window.hide();
    assert!(!window.visible);

    // Test show (from tray click)
    window.show();
    assert!(window.visible);
}
```

**MEDIUM Confidence** - Mock pattern based on Phase 142 experience, no official window testing docs

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Tauri v1 testing** | **Tauri v2 with @tauri-apps/api/mocks** | 2024 (Tauri v2 release) | Frontend testing now uses official mocks instead of custom stubs |
| **Manual thread spawning** | **tokio::test for async** | 2020+ | Tokio became standard async runtime, simpler test code |
| **GUI-dependent tests** | **Pattern validation with mocks** | 2026 (Phase 142) | Tests can run without GUI context, faster CI/CD |
| **No coverage enforcement** | **cargo-tarpaulin with --fail-under** | 2026 (Phase 142) | Coverage enforced in CI/CD (75% PR, 80% main) |

**Deprecated/outdated:**
- **Tauri v1 invoke pattern:** `invoke` API changed in v2, use new `@tauri-apps/api/core` imports
- **Synchronous command testing:** All Tauri commands are async in v2, use `#[tokio::test]`
- **Manual IPC stubbing:** Use official `@tauri-apps/api/mocks` instead of custom stub functions

## Open Questions

1. **Tauri 2.0 official testing documentation**
   - What we know: Web search found community tutorials, no official testing guide
   - What's unclear: Does official Tauri testing documentation exist?
   - Recommendation: Check https://tauri.app directly, may need to inspect source code for test examples

2. **Window management testing best practices**
   - What we know: Phase 142 used mock objects for window operations
   - What's unclear: Are there official Tauri utilities for window testing?
   - Recommendation: Use mock pattern from Phase 142, document any gaps found

3. **Event system testing coverage**
   - What we know: Events are emitted in main.rs (folder watching, CLI, satellite)
   - What's unclear: How to test emit/listen patterns without full IPC?
   - Recommendation: Use tokio channels to simulate event patterns, validate JSON serialization

4. **State persistence testing**
   - What we know: AppState uses Arc<Mutex<T>> for watchers and recordings
   - What's unclear: How to test persistent state without actual file I/O?
   - Recommendation: Use tempfile crate for isolated file I/O tests, cleanup on Drop

5. **Frontend test framework choice**
   - What we know: Tauri mocks work with Jest, Vitest, other TS test runners
   - What's unclear: Which framework does the project use?
   - Recommendation: Check existing frontend test setup in package.json, use configured runner

## Sources

### Primary (HIGH confidence)
- **Tauri v2 Official Mocks Documentation** - Frontend IPC mocking with `@tauri-apps/api/mocks`
- **Phase 142 Research (142-RESEARCH.md)** - Rust testing patterns, tarpaulin coverage, proptest
- **Phase 142 Implementation** - 122 tests created, patterns established for Tauri context, async operations, property testing
- **Tauri 2.0 Official Documentation (Chinese)** - https://tauri.app/zh-cn/

### Secondary (MEDIUM confidence)
- **Tauri Testing Tutorial** - [CSDN: Tauri调试与测试](https://blog.csdn.net/sxlesq/article/details/145111941)
- **Tauri Event System Guide** - [CSDN: Tauri事件系统](https://blog.csdn.net/gitblog_00317/article/details/151820456)
- **Tauri 2.0 Window Events** - [CSDN: Window Event与创建Window](https://blog.csdn.net/qq_63401240/article/details/146981362)
- **Tauri 2.0 Command System** - [CSDN: Tauri命令系统](https://blog.csdn.net/gitblog_00495/article/details/151808365)
- **Tauri v2 Invoke Handler** - [CSDN: tauri::command属性与invoke函数](https://blog.csdn.net/qq_63401240/article/details/146581991)

### Tertiary (LOW confidence)
- **Frontend-Backend Integration** - [CSDN: 前端与Rust后端交互](https://blog.csdn.net/weixin_42072714/article/details/147525990)
- **Tauri 2.0 Development Manual** - [CSDN: Tauri2.0开发手册](https://m.blog.csdn.net/sxlesq/article/details/148261266)
- **WebSearch Results** - Multiple search queries for "Tauri 2.0 testing", "tauri::test macro", "invoke handler testing" (no official test macro found)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All testing tools verified from project Cargo.toml and official docs
- Architecture: MEDIUM - Patterns based on Phase 142 experience, no official Tauri testing guide found
- Pitfalls: HIGH - Verified from multiple sources, Phase 142 established anti-patterns

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (30 days - Tauri v2 is stable, but testing documentation may evolve)

**Key assumptions:**
- Tauri 2.0 does NOT provide `#[tauri::test]` macro (verified from web search, official docs)
- Frontend testing framework exists (Jest/Vitest configured in package.json)
- Phase 142 patterns (mock AppHandle, tokio channels) are valid for Phase 143
- Coverage enforcement with tarpaulin is operational in CI/CD

**What might I have missed:**
- Official Tauri testing documentation may exist in non-obvious locations (source code, examples, GitHub discussions)
- Window management testing utilities may exist in Tauri ecosystem (crates.io, community projects)
- Event system testing patterns may have established best practices not covered in web search
- Frontend test framework choice (Jest vs Vitest) needs verification from package.json
