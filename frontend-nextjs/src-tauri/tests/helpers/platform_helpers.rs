//! Platform helper utilities for desktop testing
//!
//! Provides convenience functions for platform detection, platform-specific
//! assertions, and cross-platform test utilities. Mirrors Phase 139 mobile
//! testing helpers (testUtils.ts with mockPlatform/restorePlatform).
//!
//! # Desktop vs Mobile Platform Helpers
//!
//! Unlike mobile (React Native with Platform.OS mocking), desktop platforms
//! are determined at compile time using Rust's cfg! macro. Desktop helpers
//! focus on runtime detection convenience and assertion utilities rather than
//! platform switching (which is not possible or needed for desktop tests).
//!
//! # Usage
//!
//! ```rust
//! use crate::helpers::platform_helpers::*;
//!
//! // Get current platform
//! let platform = get_current_platform();
//! assert!(is_platform("windows") || is_platform("macos") || is_platform("linux"));
//!
//! // Platform-specific assertions
//! cfg_assert("macos"); // Panics if not on macOS
//!
//! // Platform-specific paths
//! let temp_dir = get_temp_dir();
//! let separator = get_platform_separator(); // "\\" on Windows, "/" on Unix
//! ```
//!
//! # Pattern Reference (Phase 139 Mobile)
//!
//! Mirrors these mobile helpers:
//! - `mockPlatform()` → Not needed (desktop uses compile-time cfg!)
//! - `restorePlatform()` → Not needed (no mock restoration needed)
//! - `getiOSInsets()` → `get_platform_separator()` (platform-specific values)
//! - `getAndroidInsets()` → `get_temp_dir()` (platform-specific paths)

use std::path::PathBuf;

/// Get the current platform as a string
///
/// Returns "windows", "macos", "linux", or "unknown" based on compile-time
/// platform detection using cfg! macro.
///
/// # Returns
///
/// - `"windows"` - Windows platform
/// - `"macos"` - macOS platform
/// - `"linux"` - Linux platform
/// - `"unknown"` - Unsupported platform
///
/// # Examples
///
/// ```rust
/// let platform = get_current_platform();
/// match platform {
///     "windows" => println!("Running on Windows"),
///     "macos" => println!("Running on macOS"),
///     "linux" => println!("Running on Linux"),
///     _ => println!("Unknown platform"),
/// }
/// ```
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

/// Check if the current platform matches the expected platform
///
/// Compares the current platform (from get_current_platform()) to the
/// expected platform string.
///
/// # Arguments
///
/// * `expected` - Expected platform string ("windows", "macos", "linux")
///
/// # Returns
///
/// `true` if platform matches, `false` otherwise
///
/// # Examples
///
/// ```rust
/// assert!(is_platform("windows") || is_platform("macos") || is_platform("linux"));
/// ```
pub fn is_platform(expected: &str) -> bool {
    get_current_platform() == expected
}

/// Assert that the current platform matches the expected platform
///
/// Panics with a descriptive message if the current platform does not
/// match the expected platform. Useful for platform-specific test assertions.
///
/// # Arguments
///
/// * `platform` - Expected platform string ("windows", "macos", "linux")
///
/// # Panics
///
/// Panics if current platform does not match expected platform
///
/// # Examples
///
/// ```rust
/// #[cfg(target_os = "macos")]
/// #[test]
/// fn test_macos_feature() {
///     cfg_assert("macos"); // Ensures test only runs on macOS
///     // Test macOS-specific feature
/// }
/// ```
pub fn cfg_assert(platform: &str) {
    let current = get_current_platform();
    assert!(
        current == platform,
        "Platform assertion failed: expected '{}', got '{}'",
        platform,
        current
    );
}

/// Get the platform-specific temporary directory
///
/// Returns the temporary directory path for the current platform:
/// - Windows: `%TEMP%` environment variable or fallback
/// - macOS: `/var/folders/...` or `/tmp`
/// - Linux: `/tmp` or `$XDG_RUNTIME_DIR`
///
/// # Returns
///
/// PathBuf pointing to the platform-specific temp directory
///
/// # Examples
///
/// ```rust
/// let temp_dir = get_temp_dir();
/// assert!(temp_dir.exists());
/// assert!(temp_dir.is_dir());
/// ```
pub fn get_temp_dir() -> PathBuf {
    std::env::temp_dir()
}

/// Get the platform-specific path separator
///
/// Returns the path separator character for the current platform:
/// - Windows: `"\"` (backslash)
/// - macOS/Linux: `"/"` (forward slash)
///
/// # Returns
///
/// String slice containing the platform-specific path separator
///
/// # Examples
///
/// ```rust
/// let separator = get_platform_separator();
/// if separator == "/" {
///     println!("Unix-style paths");
/// } else {
///     println!("Windows-style paths");
/// }
/// ```
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

    // ========================================================================
    // get_current_platform() Tests
    // ========================================================================

    #[test]
    fn test_get_current_platform_returns_valid_value() {
        let platform = get_current_platform();

        // Should be one of the known platforms or "unknown"
        assert!(
            platform == "windows" || platform == "macos" || platform == "linux" || platform == "unknown",
            "Platform should be windows, macos, linux, or unknown, got: {}",
            platform
        );

        // Should not be empty
        assert!(!platform.is_empty(), "Platform should not be empty");

        // Should be reasonable length
        assert!(platform.len() >= 3 && platform.len() <= 10,
            "Platform length should be 3-10 characters, got: {}",
            platform.len()
        );
    }

    #[test]
    fn test_get_current_platform_matches_cfg_macro() {
        let platform = get_current_platform();

        // Verify platform matches cfg! macro
        if cfg!(target_os = "windows") {
            assert_eq!(platform, "windows", "cfg! should match get_current_platform()");
        } else if cfg!(target_os = "macos") {
            assert_eq!(platform, "macos", "cfg! should match get_current_platform()");
        } else if cfg!(target_os = "linux") {
            assert_eq!(platform, "linux", "cfg! should match get_current_platform()");
        } else {
            assert_eq!(platform, "unknown", "Unsupported platform should be 'unknown'");
        }
    }

    // ========================================================================
    // is_platform() Tests
    // ========================================================================

    #[test]
    fn test_is_platform_matches_current_platform() {
        let platform = get_current_platform();

        // is_platform() should match get_current_platform()
        assert!(
            is_platform(platform),
            "is_platform should return true for current platform '{}'",
            platform
        );

        // is_platform() should return false for other platforms
        let other_platforms = vec!["windows", "macos", "linux"]
            .into_iter()
            .filter(|&p| p != platform)
            .collect::<Vec<_>>();

        for other in other_platforms {
            assert!(
                !is_platform(other),
                "is_platform should return false for non-current platform '{}' (current: '{}')",
                other,
                platform
            );
        }
    }

    #[test]
    fn test_is_platform_handles_unknown_platform() {
        // is_platform should return false for unknown platform string
        assert!(!is_platform("freebsd"), "Should return false for freebsd");
        assert!(!is_platform("android"), "Should return false for android");
        assert!(!is_platform("ios"), "Should return false for ios");
        assert!(!is_platform(""), "Should return false for empty string");
    }

    // ========================================================================
    // cfg_assert() Tests
    // ========================================================================

    #[test]
    fn test_cfg_assert_passes_for_correct_platform() {
        let platform = get_current_platform();

        // Should not panic for correct platform
        cfg_assert(platform);
    }

    #[test]
    #[should_panic(expected = "Platform assertion failed")]
    fn test_cfg_assert_panics_for_incorrect_platform() {
        let platform = get_current_platform();

        // Pick a different platform
        let wrong_platform = if platform == "windows" {
            "macos"
        } else if platform == "macos" {
            "linux"
        } else if platform == "linux" {
            "windows"
        } else {
            "windows" // Fallback for unknown platform
        };

        // Should panic for wrong platform
        cfg_assert(wrong_platform);
    }

    // ========================================================================
    // get_temp_dir() Tests
    // ========================================================================

    #[test]
    fn test_get_temp_dir_returns_valid_path() {
        let temp_dir = get_temp_dir();

        // Should exist
        assert!(temp_dir.exists(), "Temp directory should exist");

        // Should be a directory
        assert!(temp_dir.is_dir(), "Temp should be a directory");

        // Should be absolute path
        assert!(temp_dir.is_absolute(), "Temp directory should be absolute path");
    }

    #[test]
    fn test_get_temp_dir_is_writable() {
        use std::fs;

        let temp_dir = get_temp_dir();
        let test_file = temp_dir.join("platform_helpers_writable_test.txt");

        // Should be able to write file
        fs::write(&test_file, "test content")
            .expect("Should be able to write to temp directory");

        // Verify file exists
        assert!(test_file.exists(), "Test file should exist");

        // Cleanup
        let _ = fs::remove_file(&test_file);
        assert!(!test_file.exists(), "Test file should be cleaned up");
    }

    // ========================================================================
    // get_platform_separator() Tests
    // ========================================================================

    #[test]
    fn test_get_platform_separator_is_consistent() {
        let separator = get_platform_separator();

        // Should be single character
        assert_eq!(separator.len(), 1, "Separator should be single character");

        // Should match platform expectations
        if cfg!(target_os = "windows") {
            assert_eq!(separator, "\\", "Windows should use backslash");
        } else {
            assert_eq!(separator, "/", "Unix should use forward slash");
        }
    }

    #[test]
    fn test_get_platform_separator_matches_cfg_macro() {
        let separator = get_platform_separator();

        // Verify separator matches cfg! macro detection
        let is_windows = cfg!(target_os = "windows");

        assert_eq!(separator == "\\", is_windows,
            "Separator should match cfg!(target_os = \"windows\")");
    }

    #[test]
    fn test_get_platform_separator_in_path_construction() {
        use std::path::PathBuf;

        let separator = get_platform_separator();
        let path = if separator == "\\" {
            PathBuf::from(r"C:\Users\test\file.txt")
        } else {
            PathBuf::from("/home/test/file.txt")
        };

        // Path should be absolute
        assert!(path.is_absolute(), "Constructed path should be absolute");

        // Path should extract file name correctly
        assert_eq!(path.file_name().unwrap().to_string_lossy(), "file.txt",
            "File name should be extracted correctly");
    }
}
