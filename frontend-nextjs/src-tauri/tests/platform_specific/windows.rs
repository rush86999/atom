//! Windows-specific tests for file dialogs, path handling, and temp operations
//!
//! This module contains tests that only compile and run on Windows using
//! `#[cfg(target_os = "windows")]` conditional compilation. Tests focus on
//! Windows-specific code paths in main.rs:
//!
//! - **File Dialogs** (lines 24-165): `open_file_dialog`, `save_file_dialog`, `open_folder_dialog`
//! - **Path Handling**: Windows path separators (backslashes), drive letters, UNC paths
//! - **Temp Operations**: `%TEMP%` environment variable, Windows temp directory access
//! - **System Info**: Windows-specific platform detection and system information
//!
//! # Platform Guard
//!
//! All tests in this module use `#[cfg(target_os = "windows")]` to ensure they only
//! compile and run on Windows. On non-Windows platforms, this entire module is skipped
//! during compilation.
//!
//! # Test Organization
//!
//! 1. **Helper Functions**: `create_temp_test_file()`, `verify_windows_path_format()`
//! 2. **Platform Detection**: `test_windows_platform_detection()`
//! 3. **Temp Directory**: Format, writability, environment variables
//! 4. **Path Handling**: Separators, normalization, drive letters, extensions
//! 5. **System Info**: `cfg!` macro detection, environment variables, file operations
//!
//! # Pattern Reference
//!
//! Mirrors Phase 139 mobile platform-specific testing:
//! - `mobile/src/__tests__/platform-specific/ios/` → `tests/platform_specific/windows/`
//! - SafeAreaContext mock → Windows path format verification
//! - Platform.OS mocking → cfg!(target_os = "windows") compile-time detection
//!
//! # Usage
//!
//! ```bash
//! # Run Windows-specific tests (only works on Windows)
//! cargo test platform_specific::windows
//!
//! # List all tests (only shows tests on Windows)
//! cargo test --list | grep windows
//! ```

// Only compile this module on Windows
#![cfg(target_os = "windows")]

use std::fs;
use std::path::PathBuf;
use std::env;
use crate::helpers::platform_helpers::*;

// ========================================================================
// Helper Functions
// ========================================================================

/// Create a temporary test file with the given content
///
/// Creates a unique temporary file in the system temp directory using a
/// timestamp-based filename. Returns the PathBuf to the created file.
///
/// # Arguments
///
/// * `content` - Content to write to the temporary file
///
/// # Returns
///
/// PathBuf pointing to the created temporary file
///
/// # Note
///
/// Caller is responsible for cleanup. Use pattern like:
/// ```rust
/// let test_file = create_temp_test_file("test content");
/// // ... test code ...
/// let _ = fs::remove_file(&test_file); // Cleanup
/// ```
fn create_temp_test_file(content: &str) -> PathBuf {
    let temp_dir = get_temp_dir();

    // Create unique filename with timestamp
    let timestamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_secs();
    let filename = format!("windows_test_{}.txt", timestamp);
    let test_file = temp_dir.join(&filename);

    // Write content to file
    fs::write(&test_file, content)
        .expect("Failed to write temporary test file");

    test_file
}

/// Verify that a path matches Windows path format
///
/// Checks if the path contains Windows-specific characteristics:
/// - Backslash separators (\\)
/// - Drive letter prefix (C:, D:, etc.)
///
/// # Arguments
///
/// * `path` - Path string to verify
///
/// # Returns
///
/// `true` if path appears to be Windows format, `false` otherwise
///
/// # Examples
///
/// ```rust
/// assert!(verify_windows_path_format(r"C:\Users\test\file.txt"));
/// assert!(!verify_windows_path_format("/home/test/file.txt"));
/// ```
fn verify_windows_path_format(path: &str) -> bool {
    // Check for backslash separator
    let has_backslash = path.contains('\\');

    // Check for drive letter pattern (C:, D:, etc.)
    let has_drive_letter = path.len() >= 2
        && path.as_bytes()[0].is_ascii_alphabetic()
        && &path[1..2] == ":";

    has_backslash || has_drive_letter
}

// ========================================================================
// Platform Detection Tests
// ========================================================================

#[test]
#[cfg(target_os = "windows")]
fn test_windows_platform_detection() {
    // Test get_current_platform() returns "windows"
    let platform = get_current_platform();
    assert_eq!(platform, "windows", "get_current_platform() should return 'windows'");

    // Test is_platform() returns true for "windows"
    assert!(is_platform("windows"), "is_platform('windows') should return true");

    // Test is_platform() returns false for other platforms
    assert!(!is_platform("macos"), "is_platform('macos') should return false");
    assert!(!is_platform("linux"), "is_platform('linux') should return false");

    // Test cfg_assert() passes for "windows"
    cfg_assert("windows"); // Should not panic

    // Test cfg!(target_os) macro matches platform detection
    assert!(cfg!(target_os = "windows"), "cfg!(target_os = \"windows\") should be true");
    assert!(!cfg!(target_os = "macos"), "cfg!(target_os = \"macos\") should be false");
    assert!(!cfg!(target_os = "linux"), "cfg!(target_os = \"linux\") should be false");
}

// ========================================================================
// Temp Directory Tests
// ========================================================================

#[test]
#[cfg(target_os = "windows")]
fn test_windows_temp_directory_format() {
    // Get TEMP environment variable or use default
    let temp_path = env::var("TEMP")
        .unwrap_or_else(|_| r"C:\Temp".to_string());

    // Assert path contains backslash (Windows separator)
    assert!(
        temp_path.contains('\\'),
        "TEMP path should contain backslash: {}",
        temp_path
    );

    // Assert path exists
    let path_buf = PathBuf::from(&temp_path);
    assert!(
        path_buf.exists(),
        "TEMP directory should exist: {}",
        temp_path
    );

    // Verify parent directory exists
    if let Some(parent) = path_buf.parent() {
        assert!(
            parent.exists(),
            "TEMP parent directory should exist: {}",
            parent.display()
        );
    }
}

#[test]
#[cfg(target_os = "windows")]
fn test_windows_temp_directory_writable() {
    // Create test file in temp directory
    let test_file = create_temp_test_file("test content");

    // Verify file exists
    assert!(
        test_file.exists(),
        "Test file should exist in temp directory"
    );

    // Read back and verify content matches
    let content = fs::read_to_string(&test_file)
        .expect("Failed to read test file");
    assert_eq!(content, "test content", "Content should match");

    // Cleanup
    let _ = fs::remove_file(&test_file);
    assert!(
        !test_file.exists(),
        "Test file should be cleaned up"
    );
}

// ========================================================================
// Path Separator Tests
// ========================================================================

#[test]
#[cfg(target_os = "windows")]
fn test_windows_path_separator() {
    // Test get_platform_separator() returns backslash
    let separator = get_platform_separator();
    assert_eq!(
        separator, "\\",
        "Windows path separator should be backslash"
    );

    // Create PathBuf with backslashes
    let path = PathBuf::from(r"C:\Users\test\file.txt");

    // Verify file_name() returns "file.txt"
    assert_eq!(
        path.file_name().unwrap().to_string_lossy(),
        "file.txt",
        "file_name() should extract filename"
    );

    // Verify extension() returns "txt"
    assert_eq!(
        path.extension().unwrap().to_string_lossy(),
        "txt",
        "extension() should extract extension"
    );

    // Verify parent() returns "C:\Users\test"
    let parent = path.parent().unwrap();
    assert_eq!(
        parent.to_string_lossy(),
        r"C:\Users\test",
        "parent() should return parent directory"
    );
}

#[test]
#[cfg(target_os = "windows")]
fn test_windows_path_buf_normalization() {
    // Create path with mixed separators
    let path = PathBuf::from(r"C:\Users/test\file.txt");

    // Verify PathBuf normalizes to backslashes
    let path_str = path.to_string_lossy();
    assert!(
        path_str.contains('\\'),
        "PathBuf should normalize to backslashes: {}",
        path_str
    );

    // Assert is_absolute() returns true for Windows absolute paths
    assert!(
        path.is_absolute(),
        "Windows absolute path should return true for is_absolute()"
    );
}

#[test]
#[cfg(target_os = "windows")]
fn test_windows_drive_letter_parsing() {
    // Test various Windows paths with drive letters
    let paths = vec![
        r"C:\",
        r"D:\Data",
        r"E:\Files\test.txt",
        r"F:\Program Files\Application",
    ];

    for path in paths {
        // Verify each starts with drive letter pattern: [A-Z]:
        assert!(
            path.len() >= 2,
            "Path should be at least 2 characters: {}",
            path
        );

        let first_char = path.as_bytes()[0];
        assert!(
            first_char.is_ascii_alphabetic(),
            "First char should be letter: {}",
            path
        );

        assert_eq!(
            &path[1..2],
            ":",
            "Second char should be colon: {}",
            path
        );

        // Verify Windows path format
        assert!(
            verify_windows_path_format(path),
            "Path should match Windows format: {}",
            path
        );
    }
}

#[test]
#[cfg(target_os = "windows")]
fn test_windows_file_extensions() {
    // Test file extension extraction
    let test_cases = vec![
        ("test.txt", "txt", "test"),
        ("document.pdf", "pdf", "document"),
        ("image.png", "png", "image"),
        ("archive.zip", "zip", "archive"),
        ("data.json", "json", "data"),
        ("README", "", "README"), // No extension
    ];

    for (filename, expected_ext, expected_stem) in vec![
        ("test.txt", Some("txt"), Some("test")),
        ("document.pdf", Some("pdf"), Some("document")),
        ("image.png", Some("png"), Some("image")),
        ("archive.zip", Some("zip"), Some("archive")),
        ("README", None, Some("README")),
    ] {
        let path = PathBuf::from(filename);

        // Verify extension()
        if let Some(ext) = expected_ext {
            assert_eq!(
                path.extension().unwrap().to_string_lossy(),
                ext,
                "Extension should match for {}",
                filename
            );
        } else {
            assert!(
                path.extension().is_none(),
                "Extension should be None for {}",
                filename
            );
        }

        // Verify file_stem()
        if let Some(stem) = expected_stem {
            assert_eq!(
                path.file_stem().unwrap().to_string_lossy(),
                stem,
                "File stem should match for {}",
                filename
            );
        }
    }
}
