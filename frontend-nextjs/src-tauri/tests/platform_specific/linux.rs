//! Linux-specific tests for XDG directories, temp operations, and path handling
//!
//! This module contains tests that only compile and run on Linux using
//! `#[cfg(target_os = "linux")]` conditional compilation. Tests focus on
//! Linux-specific code paths in main.rs:
//!
//! - **XDG Directories**: XDG_DATA_HOME, XDG_CONFIG_HOME, XDG_RUNTIME_DIR
//! - **Temp Operations**: /tmp directory, XDG_RUNTIME_DIR fallback
//! - **Path Handling**: Linux path separators (forward slashes), /home paths
//! - **System Info**: Linux-specific platform detection and desktop environment
//!
//! # Platform Guard
//!
//! All tests in this module use `#[cfg(target_os = "linux")]` to ensure they only
//! compile and run on Linux. On non-Linux platforms, this entire module is skipped
//! during compilation.
//!
//! # Test Organization
//!
//! 1. **Helper Functions**: XDG directory access with fallbacks
//! 2. **Platform Detection**: `test_linux_platform_detection()`
//! 3. **XDG Directories**: DATA_HOME, CONFIG_HOME, RUNTIME_DIR with fallbacks
//! 4. **Path Handling**: Separators, home directory, Linux path format
//! 5. **Temp Operations**: Format, writability, /tmp access
//! 6. **System Info**: `cfg!` macro detection, desktop environment, file operations
//!
//! # XDG Base Directory Specification
//!
//! Linux uses the XDG Base Directory Specification for config and data directories:
//! - **XDG_DATA_HOME**: User data files (default: `$HOME/.local/share`)
//! - **XDG_CONFIG_HOME**: User config files (default: `$HOME/.config`)
//! - **XDG_RUNTIME_DIR**: Runtime files (default: `/tmp` if not set)
//!
//! # Pattern Reference
//!
//! Mirrors Phase 139 mobile platform-specific testing:
//! - `mobile/src/__tests__/platform-specific/ios/` → `tests/platform_specific/linux/`
//! - SafeAreaContext mock → XDG directory verification
//! - Platform.OS mocking → cfg!(target_os = "linux") compile-time detection
//!
//! # Usage
//!
//! ```bash
//! # Run Linux-specific tests (only works on Linux)
//! cargo test platform_specific::linux
//!
//! # List all tests (only shows tests on Linux)
//! cargo test --list | grep linux
//! ```

// Only compile this module on Linux
#![cfg(target_os = "linux")]

use std::fs;
use std::path::PathBuf;
use std::env;
use crate::helpers::platform_helpers::*;

// ========================================================================
// Helper Functions
// ========================================================================

/// Get the XDG Data Home directory
///
/// Returns the path for user data files according to XDG Base Directory Specification.
/// Checks XDG_DATA_HOME environment variable first, falls back to `$HOME/.local/share`.
///
/// # Returns
///
/// PathBuf pointing to XDG data directory
///
/// # XDG Specification
///
/// - **Default**: `$HOME/.local/share`
/// - **Environment Variable**: `XDG_DATA_HOME`
///
/// # Examples
///
/// ```rust
/// let data_home = get_xdg_data_home();
/// assert!(data_home.ends_with(".local/share") || env::var("XDG_DATA_HOME").is_ok());
/// ```
fn get_xdg_data_home() -> PathBuf {
    // Check XDG_DATA_HOME environment variable first
    if let Ok(data_home) = env::var("XDG_DATA_HOME") {
        return PathBuf::from(data_home);
    }

    // Fallback to $HOME/.local/share
    if let Ok(home) = env::var("HOME") {
        let default_path = PathBuf::from(home).join(".local/share");

        // Create directory if it doesn't exist (for testing)
        if !default_path.exists() {
            let _ = fs::create_dir_all(&default_path);
        }

        return default_path;
    }

    // Last resort: use current directory
    PathBuf::from(".").join(".local/share")
}

/// Get the XDG Config Home directory
///
/// Returns the path for user config files according to XDG Base Directory Specification.
/// Checks XDG_CONFIG_HOME environment variable first, falls back to `$HOME/.config`.
///
/// # Returns
///
/// PathBuf pointing to XDG config directory
///
/// # XDG Specification
///
/// - **Default**: `$HOME/.config`
/// - **Environment Variable**: `XDG_CONFIG_HOME`
///
/// # Examples
///
/// ```rust
/// let config_home = get_xdg_config_home();
/// assert!(config_home.ends_with(".config") || env::var("XDG_CONFIG_HOME").is_ok());
/// ```
fn get_xdg_config_home() -> PathBuf {
    // Check XDG_CONFIG_HOME environment variable first
    if let Ok(config_home) = env::var("XDG_CONFIG_HOME") {
        return PathBuf::from(config_home);
    }

    // Fallback to $HOME/.config
    if let Ok(home) = env::var("HOME") {
        let default_path = PathBuf::from(home).join(".config");

        // Create directory if it doesn't exist (for testing)
        if !default_path.exists() {
            let _ = fs::create_dir_all(&default_path);
        }

        return default_path;
    }

    // Last resort: use current directory
    PathBuf::from(".").join(".config")
}

/// Get the XDG Runtime Directory
///
/// Returns the path for runtime files according to XDG Base Directory Specification.
/// Checks XDG_RUNTIME_DIR environment variable first, falls back to `/tmp`.
///
/// # Returns
///
/// PathBuf pointing to XDG runtime directory
///
/// # XDG Specification
///
/// - **Default**: `/tmp` (fallback, not spec-compliant)
/// - **Environment Variable**: `XDG_RUNTIME_DIR`
///
/// # Note
///
/// XDG_RUNTIME_DIR is required to be created by the user session manager with
/// proper permissions (0700). If not set, we fall back to `/tmp` for testing purposes.
///
/// # Examples
///
/// ```rust
/// let runtime_dir = get_xdg_runtime_dir();
/// assert!(runtime_dir.starts_with("/tmp") || env::var("XDG_RUNTIME_DIR").is_ok());
/// ```
fn get_xdg_runtime_dir() -> PathBuf {
    // Check XDG_RUNTIME_DIR environment variable first
    if let Ok(runtime_dir) = env::var("XDG_RUNTIME_DIR") {
        return PathBuf::from(runtime_dir);
    }

    // Fallback to /tmp
    PathBuf::from("/tmp")
}

// ========================================================================
// Platform Detection Tests
// ========================================================================

#[test]
#[cfg(target_os = "linux")]
fn test_linux_platform_detection() {
    // Test get_current_platform() returns "linux"
    let platform = get_current_platform();
    assert_eq!(platform, "linux", "get_current_platform() should return 'linux'");

    // Test is_platform() returns true for "linux"
    assert!(is_platform("linux"), "is_platform('linux') should return true");

    // Test is_platform() returns false for other platforms
    assert!(!is_platform("windows"), "is_platform('windows') should return false");
    assert!(!is_platform("macos"), "is_platform('macos') should return false");

    // Test cfg_assert() passes for "linux"
    cfg_assert("linux"); // Should not panic

    // Test cfg!(target_os) macro matches platform detection
    assert!(cfg!(target_os = "linux"), "cfg!(target_os = \"linux\") should be true");
    assert!(!cfg!(target_os = "windows"), "cfg!(target_os = \"windows\") should be false");
    assert!(!cfg!(target_os = "macos"), "cfg!(target_os = \"macos\") should be false");
}

// ========================================================================
// Placeholder for Task 2 tests (XDG directory tests)
// Placeholder for Task 3 tests (temp and system info tests)
// ========================================================================
