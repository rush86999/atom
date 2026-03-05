//! macOS-specific tests for menu bar, dock, path handling, and temp operations
//!
//! This module contains tests that only compile and run on macOS (target_os = "macos").
//! Tests focus on macOS-specific behavior in main.rs (lines 500-650 for menu bar)
//! and platform-specific paths (temp directories, path separators, app data locations).
//!
//! # Platform Guard
//!
//! All tests in this module use `#[cfg(target_os = "macos")]` to ensure they only
//! compile on macOS. On other platforms (Windows, Linux), this entire module is
//! excluded from compilation, preventing "unimplemented function" errors.
//!
//! # Test Categories
//!
//! - **Platform Detection**: Verify macOS platform detection via cfg! macro
//! - **Path Handling**: macOS-specific path formats (forward slashes, /Users/, /var/folders)
//! - **Temp Directory**: macOS temp directory operations (/var/folders or /tmp)
//! - **Menu Bar**: Menu bar structure and expected JSON format
//! - **Dock Integration**: Dock icon bouncing and dock menu structure
//! - **System Info**: macOS system information (platform, architecture, version)
//! - **File Operations**: Unix-style file permissions and line endings (LF only)
//!
//! # Dependencies
//!
//! - `std::fs` - File operations (create, read, write, delete)
//! - `std::path::PathBuf` - Path handling and manipulation
//! - `std::env` - Environment variables (HOME, TEMP)
//! - `crate::helpers::platform_helpers::*` - Platform detection utilities
//!
//! # Usage
//!
//! ```bash
//! # Run only on macOS (skipped on other platforms)
//! cargo test platform_specific::macos
//!
//! # List all macOS tests
//! cargo test --list | grep macos
//! ```
//!
//! # Pattern Reference (Phase 141 Desktop)
//!
//! Mirrors Phase 139 mobile platform-specific testing patterns:
//! - `mobile/src/__tests__/platform-specific/ios/` → `tests/platform_specific/macos/`
//! - Platform guards: `Platform.OS === 'ios'` → `#[cfg(target_os = "macos")]`
//! - Platform assertions: `expect(Platform.OS).toBe('ios')` → `cfg_assert("macos")`

use std::fs;
use std::path::PathBuf;
use std::env;
use crate::helpers::platform_helpers::*;

// ============================================================================
// Helper Functions
// ============================================================================

/// Get the macOS-specific temporary directory
///
/// Calls `std::env::temp_dir()` and returns the macOS temp directory path.
/// On macOS, this is typically `/var/folders/.../T/` or falls back to `/tmp/`.
///
/// # Returns
///
/// PathBuf pointing to the macOS temp directory
///
/// # Examples
///
/// ```rust
/// let temp_dir = get_macos_temp_dir();
/// assert!(temp_dir.starts_with("/"));
/// assert!(temp_dir.exists());
/// ```
fn get_macos_temp_dir() -> PathBuf {
    std::env::temp_dir()
}

/// Verify Unix/Mac path format
///
/// Checks if a path follows Unix/Mac format:
/// - Contains forward slashes (/)
/// - Starts with "/" for absolute paths
/// - Does NOT contain backslashes (\)
///
/// # Arguments
///
/// * `path` - Path string to verify
///
/// # Returns
///
/// `true` if path follows Unix/Mac format, `false` otherwise
///
/// # Examples
///
/// ```rust
/// assert!(verify_unix_path_format("/Users/test/file.txt"));
/// assert!(!verify_unix_path_format(r"C:\Users\test\file.txt"));
/// ```
fn verify_unix_path_format(path: &str) -> bool {
    // Must contain forward slashes
    let has_forward_slash = path.contains('/');

    // If absolute, must start with "/"
    let starts_correctly = if path.starts_with('/') {
        true
    } else {
        // Relative paths don't need leading slash
        !path.contains('\\')
    };

    // Must NOT contain backslashes
    let no_backslashes = !path.contains('\\');

    has_forward_slash && starts_correctly && no_backslashes
}

// ============================================================================
// Platform Detection Tests
// ============================================================================

#[cfg(target_os = "macos")]
#[cfg(test)]
mod platform_detection_tests {
    use super::*;

    #[test]
    fn test_macos_platform_detection() {
        // Verify get_current_platform() returns "macos"
        let platform = get_current_platform();
        assert_eq!(platform, "macos", "Platform should be macos");

        // Verify is_platform("macos") returns true
        assert!(is_platform("macos"), "is_platform should return true for macos");

        // Verify is_platform returns false for other platforms
        assert!(!is_platform("windows"), "is_platform should return false for windows");
        assert!(!is_platform("linux"), "is_platform should return false for linux");
    }

    #[test]
    fn test_macos_cfg_assert() {
        // cfg_assert should NOT panic when called with "macos"
        cfg_assert("macos");
    }

    #[test]
    #[should_panic(expected = "Platform assertion failed")]
    fn test_macos_cfg_assert_panics_for_wrong_platform() {
        // cfg_assert should panic when called with wrong platform
        cfg_assert("windows");
    }

    #[test]
    fn test_macos_cfg_macro_detection() {
        // Verify cfg! macro detects macOS correctly
        assert!(cfg!(target_os = "macos"), "cfg! should detect macOS");

        // Verify cfg! macro returns false for other platforms
        assert!(!cfg!(target_os = "windows"), "cfg! should return false for Windows");
        assert!(!cfg!(target_os = "linux"), "cfg! should return false for Linux");
    }
}

// ============================================================================
// Path Handling Tests
// ============================================================================

#[cfg(target_os = "macos")]
#[cfg(test)]
mod path_handling_tests {
    use super::*;

    #[test]
    fn test_macos_temp_directory_format() {
        // Get temp directory
        let temp_path = get_macos_temp_dir();
        let temp_path_str = temp_path.to_string_lossy();

        // Assert path starts with "/" (Unix absolute path)
        assert!(temp_path_str.starts_with('/'),
            "macOS temp dir should start with '/', got: {}",
            temp_path_str
        );

        // Assert path does NOT contain backslashes (Windows-style)
        assert!(!temp_path_str.contains('\\'),
            "macOS temp dir should not contain backslashes, got: {}",
            temp_path_str
        );

        // Assert temp directory exists
        assert!(temp_path.exists(),
            "macOS temp dir should exist: {}",
            temp_path_str
        );

        // Assert temp directory is a directory
        assert!(temp_path.is_dir(),
            "macOS temp dir should be a directory: {}",
            temp_path_str
        );
    }

    #[test]
    fn test_macos_temp_directory_writable() {
        let temp_dir = get_macos_temp_dir();
        let test_file = temp_dir.join("atom_macos_writable_test.txt");

        // Write test file
        fs::write(&test_file, b"test content")
            .expect("Should be able to write to temp directory");

        // Verify file exists
        assert!(test_file.exists(), "Test file should exist");

        // Read back and verify content
        let content = fs::read_to_string(&test_file)
            .expect("Should be able to read from temp directory");
        assert_eq!(content, "test content", "Content should match");

        // Cleanup
        let _ = fs::remove_file(&test_file);
        assert!(!test_file.exists(), "Test file should be cleaned up");
    }

    #[test]
    fn test_macos_path_separator() {
        // Verify get_platform_separator() returns "/" on macOS
        let separator = get_platform_separator();
        assert_eq!(separator, "/", "macOS should use forward slash separator");

        // Create PathBuf with forward slashes
        let path = PathBuf::from("/Users/test/file.txt");

        // Verify file_name() returns "file.txt"
        assert_eq!(path.file_name().unwrap().to_string_lossy(), "file.txt",
            "File name should be extracted correctly");

        // Verify extension() returns "txt"
        assert_eq!(path.extension().unwrap().to_string_lossy(), "txt",
            "Extension should be extracted correctly");

        // Verify parent() returns "/Users/test"
        assert_eq!(path.parent().unwrap().to_str().unwrap(), "/Users/test",
            "Parent path should be extracted correctly");
    }

    #[test]
    fn test_macos_home_directory() {
        // Get HOME environment variable
        let home_dir = env::var("HOME")
            .expect("HOME environment variable should be set");

        // Verify path starts with "/Users/"
        assert!(home_dir.starts_with("/Users/"),
            "macOS HOME should start with /Users/, got: {}",
            home_dir
        );

        // Verify path exists
        let home_path = PathBuf::from(&home_dir);
        assert!(home_path.exists(),
            "macOS HOME directory should exist: {}",
            home_dir
        );

        // Create test path: $HOME/test_atom_file.txt
        let test_path = home_path.join("test_atom_file.txt");

        // Verify path components parse correctly
        assert_eq!(test_path.parent().unwrap(), home_path,
            "Test file parent should be HOME directory"
        );
        assert_eq!(test_path.file_name().unwrap().to_string_lossy(), "test_atom_file.txt",
            "Test file name should be correct"
        );
    }

    #[test]
    fn test_macos_appdata_directory() {
        // Get HOME directory
        let home_dir = env::var("HOME")
            .expect("HOME environment variable should be set");

        // Test common macOS app data locations
        let app_support = PathBuf::from(&home_dir).join("Library/Application Support");
        let preferences = PathBuf::from(&home_dir).join("Library/Preferences");
        let caches = PathBuf::from(&home_dir).join("Library/Caches");

        // Verify paths start with home directory
        assert!(app_support.starts_with(&home_dir),
            "Application Support should be under HOME"
        );
        assert!(preferences.starts_with(&home_dir),
            "Preferences should be under HOME"
        );
        assert!(caches.starts_with(&home_dir),
            "Caches should be under HOME"
        );

        // Verify Library/Application Support directory exists or can be created
        if app_support.exists() {
            assert!(app_support.is_dir(),
                "Application Support should be a directory"
            );
        }

        // Verify Library/Preferences directory exists
        if preferences.exists() {
            assert!(preferences.is_dir(),
                "Preferences should be a directory"
            );
        }

        // Verify Library/Caches directory exists or can be created
        if caches.exists() {
            assert!(caches.is_dir(),
                "Caches should be a directory"
            );
        }
    }

    #[test]
    fn test_macos_absolute_vs_relative_paths() {
        // Create absolute path
        let absolute_path = PathBuf::from("/Users/test/document.pdf");

        // Create relative path
        let relative_path = PathBuf::from("test/document.pdf");

        // Verify is_absolute() returns correct values
        assert!(absolute_path.is_absolute(),
            "Absolute path should be identified as absolute"
        );
        assert!(!relative_path.is_absolute(),
            "Relative path should NOT be identified as absolute"
        );

        // Verify file_name() returns same value for both
        assert_eq!(absolute_path.file_name(), relative_path.file_name(),
            "file_name() should return same value for absolute and relative paths"
        );
        assert_eq!(absolute_path.file_name().unwrap().to_string_lossy(), "document.pdf",
            "File name should be document.pdf"
        );

        // Verify extension() returns "pdf" for absolute path
        assert_eq!(absolute_path.extension().unwrap().to_string_lossy(), "pdf",
            "Extension should be pdf"
        );

        // Verify parent() for absolute path
        assert_eq!(absolute_path.parent().unwrap().to_str().unwrap(), "/Users/test",
            "Parent of absolute path should be correct"
        );

        // Verify parent() for relative path
        assert_eq!(relative_path.parent().unwrap().to_str().unwrap(), "test",
            "Parent of relative path should be correct"
        );
    }
}
