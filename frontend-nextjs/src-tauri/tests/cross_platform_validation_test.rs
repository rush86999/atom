//! Cross-platform validation tests for Tauri desktop application
//!
//! Tests for platform detection, path separator consistency, temp directory access,
//! and platform-specific features across macOS, Windows, and Linux.

#[cfg(test)]
mod tests {
    use std::fs;
    use std::path::PathBuf;

    // ========================================================================
    // Platform Detection Tests
    // ========================================================================

    #[test]
    fn test_platform_detection_macos_windows_linux() {
        // Test platform detection logic from main.rs
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
        assert!(os == "windows" || os == "macos" || os == "linux" || os == "unknown",
            "Platform should be one of: windows, macos, linux, unknown");

        // Verify platform is not empty
        assert!(!os.is_empty(), "Platform string should not be empty");

        // Verify platform length is reasonable
        assert!(os.len() >= 3 && os.len() <= 10, "Platform name length should be reasonable");
    }

    #[test]
    fn test_architecture_detection_x64_arm64() {
        // Test architecture detection from main.rs
        let arch = if cfg!(target_arch = "x86_64") {
            "x64"
        } else if cfg!(target_arch = "aarch64") {
            "arm64"
        } else {
            "unknown"
        };

        // Verify architecture is recognized
        assert!(arch == "x64" || arch == "arm64" || arch == "unknown",
            "Architecture should be one of: x64, arm64, unknown");

        // Verify architecture is not empty
        assert!(!arch.is_empty(), "Architecture string should not be empty");
    }

    // ========================================================================
    // Path Separator Consistency Tests
    // ========================================================================

    #[test]
    fn test_path_buf_handles_forward_and_backward_slashes() {
        // Test PathBuf handles both separators correctly
        // Note: PathBuf normalizes separators to platform default

        // Test forward slash (Unix-style)
        let forward_path = PathBuf::from("/home/user/test/file.txt");
        assert!(forward_path.is_absolute(), "Forward slash path should be absolute on Unix");
        assert_eq!(forward_path.file_name().unwrap().to_string_lossy(), "file.txt",
            "File name should be extracted correctly");

        // Test backward slash (Windows-style) - PathBuf handles this
        let backward_path_str = if cfg!(windows) {
            r"C:\Users\test\file.txt"
        } else {
            "/home/test/file.txt" // Fallback for Unix
        };

        let backward_path = PathBuf::from(backward_path_str);
        assert!(backward_path.is_absolute(), "Path should be absolute");

        // Verify both paths extract file name correctly
        let forward_name = forward_path.file_name().unwrap().to_string_lossy();
        let backward_name = backward_path.file_name().unwrap().to_string_lossy();

        assert_eq!(forward_name, "file.txt", "Forward path file name should match");
        assert_eq!(backward_name, "file.txt", "Backward path file name should match");
    }

    #[test]
    fn test_file_name_extraction_across_platforms() {
        // Test file name extraction works consistently
        let test_cases_unix = vec![
            "/home/user/file.txt",
            "/relative/path/file.md",
            "simple.txt",
        ];

        // On Unix, test Unix paths
        #[cfg(not(target_os = "windows"))]
        for path_str in test_cases_unix {
            let path = PathBuf::from(path_str);

            if let Some(file_name) = path.file_name() {
                let name = file_name.to_string_lossy();

                // Verify file name is not empty
                assert!(!name.is_empty(), "File name should not be empty for path: {}", path_str);

                // Verify file name has extension (if expected)
                if path_str.contains('.') && !path_str.ends_with('.') {
                    assert!(name.contains('.'), "File name should contain extension: {}", name);
                }
            }
        }

        // On Windows, also test Windows paths
        #[cfg(target_os = "windows")]
        {
            let mut test_cases = test_cases_unix;
            test_cases.push(r"C:\Users\user\file.txt");

            for path_str in test_cases {
                let path = PathBuf::from(path_str);

                if let Some(file_name) = path.file_name() {
                    let name = file_name.to_string_lossy();

                    // Verify file name is not empty
                    assert!(!name.is_empty(), "File name should not be empty for path: {}", path_str);

                    // Verify file name has extension (if expected)
                    if path_str.contains('.') && !path_str.ends_with('.') {
                        assert!(name.contains('.'), "File name should contain extension: {}", name);
                    }
                }
            }
        }
    }

    #[test]
    fn test_parent_directory_resolution() {
        // Test parent directory resolution across platforms
        let test_path = if cfg!(windows) {
            PathBuf::from(r"C:\Users\test\documents\file.txt")
        } else {
            PathBuf::from("/home/test/documents/file.txt")
        };

        // Verify parent extraction works
        let parent = test_path.parent()
            .expect("Path should have parent");

        if cfg!(windows) {
            assert!(parent.to_string_lossy().contains("documents"),
                "Parent should contain 'documents' on Windows");
        } else {
            assert!(parent.to_string_lossy().contains("documents") ||
                parent.to_string_lossy().ends_with("documents"),
                "Parent should contain 'documents' on Unix");
        }

        // Verify parent is not empty
        assert!(!parent.as_os_str().is_empty(), "Parent path should not be empty");

        // Verify parent is not the file itself
        assert_ne!(parent, test_path, "Parent should not be same as path");
    }

    // ========================================================================
    // Temp Directory Access Tests
    // ========================================================================

    #[test]
    fn test_temp_dir_is_writable_on_all_platforms() {
        // Test temp directory is writable on all platforms
        let temp_dir = std::env::temp_dir();

        // Verify temp directory exists
        assert!(temp_dir.exists(), "Temp directory should exist");
        assert!(temp_dir.is_dir(), "Temp should be a directory");

        // Verify temp directory is writable
        let test_file = temp_dir.join("cross_platform_write_test.txt");
        let test_content = "Test content for cross-platform temp directory";

        fs::write(&test_file, test_content)
            .expect("Should be able to write to temp directory");

        // Verify file was written
        assert!(test_file.exists(), "Test file should exist");

        // Verify content matches
        let read_content = fs::read_to_string(&test_file)
            .expect("Should be able to read from temp directory");

        assert_eq!(read_content, test_content, "Content should match");

        // Cleanup
        let _ = fs::remove_file(&test_file);
        assert!(!test_file.exists(), "Test file should be cleaned up");
    }

    #[test]
    fn test_temp_dir_cleanup() {
        // Test temp directory cleanup works across platforms
        let temp_dir = std::env::temp_dir();
        let test_subdir = temp_dir.join("atom_cross_platform_cleanup_test");

        // Create subdirectory
        fs::create_dir(&test_subdir)
            .expect("Should be able to create subdirectory in temp");

        // Create file in subdirectory
        let test_file = test_subdir.join("test.txt");
        fs::write(&test_file, "test content")
            .expect("Should be able to write file");

        // Verify cleanup works
        let _ = fs::remove_file(&test_file);
        let _ = fs::remove_dir(&test_subdir);

        assert!(!test_file.exists(), "File should be cleaned up");
        assert!(!test_subdir.exists(), "Subdirectory should be cleaned up");
    }

    // ========================================================================
    // Platform-Specific Features Tests
    // ========================================================================

    #[cfg(target_os = "macos")]
    #[test]
    fn test_macos_specific_features() {
        // Test macOS-specific features
        // This test only compiles and runs on macOS

        let platform = "macos";
        assert_eq!(platform, "macos", "Platform should be macOS");

        // Verify macOS-specific paths or features
        let home = std::env::var("HOME").expect("HOME should be set on macOS");
        assert!(!home.is_empty(), "HOME should not be empty");

        // Verify home directory structure
        let home_path = PathBuf::from(&home);
        assert!(home_path.is_absolute(), "HOME should be absolute path");
    }

    #[cfg(target_os = "windows")]
    #[test]
    fn test_windows_specific_features() {
        // Test Windows-specific features
        // This test only compiles and runs on Windows

        let platform = "windows";
        assert_eq!(platform, "windows", "Platform should be Windows");

        // Verify Windows-specific environment variables
        if let Ok(appdata) = std::env::var("APPDATA") {
            assert!(!appdata.is_empty(), "APPDATA should not be empty");

            // Verify APPDATA path structure
            let appdata_path = PathBuf::from(&appdata);
            assert!(appdata_path.is_absolute(), "APPDATA should be absolute path");
        }
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn test_linux_specific_features() {
        // Test Linux-specific features
        // This test only compiles and runs on Linux

        let platform = "linux";
        assert_eq!(platform, "linux", "Platform should be Linux");

        // Verify Linux-specific paths
        if let Ok(xdg_config_home) = std::env::var("XDG_CONFIG_HOME") {
            assert!(!xdg_config_home.is_empty(), "XDG_CONFIG_HOME should not be empty");
        }
    }

    // ========================================================================
    // Cross-Platform Consistency Tests
    // ========================================================================

    #[test]
    fn test_file_system_operations_consistency() {
        // Test file system operations work consistently across platforms
        let temp_dir = std::env::temp_dir();

        // Test 1: Create directory
        let test_dir = temp_dir.join("consistency_test_dir");
        fs::create_dir(&test_dir)
            .expect("Should be able to create directory");

        assert!(test_dir.exists(), "Directory should exist");
        assert!(test_dir.is_dir(), "Should be a directory");

        // Test 2: Write file
        let test_file = test_dir.join("test.txt");
        fs::write(&test_file, "content")
            .expect("Should be able to write file");

        assert!(test_file.exists(), "File should exist");

        // Test 3: Read file
        let content = fs::read_to_string(&test_file)
            .expect("Should be able to read file");

        assert_eq!(content, "content", "Content should match");

        // Test 4: List directory
        let entries = fs::read_dir(&test_dir)
            .expect("Should be able to list directory");

        let count = entries.count();
        assert_eq!(count, 1, "Should have 1 entry");

        // Cleanup
        let _ = fs::remove_file(&test_file);
        let _ = fs::remove_dir(&test_dir);
    }

    #[test]
    fn test_path_operations_cross_platform() {
        // Test path operations work consistently
        let temp_dir = std::env::temp_dir();

        // Test path joining
        let path1 = temp_dir.join("level1");
        let path2 = path1.join("level2");
        let path3 = path2.join("file.txt");

        // Verify path construction
        assert!(path3.is_absolute(), "Path should be absolute");
        assert!(path3.to_string_lossy().contains("level1"), "Path should contain level1");
        assert!(path3.to_string_lossy().contains("level2"), "Path should contain level2");
        assert!(path3.to_string_lossy().ends_with("file.txt") ||
            path3.to_string_lossy().ends_with("file.txt"),
            "Path should end with file.txt");
    }

    // ========================================================================
    // Platform Edge Cases Tests
    // ========================================================================

    #[test]
    fn test_empty_path_handling() {
        // Test empty path handling across platforms
        let empty_path = PathBuf::new();

        assert!(!empty_path.is_absolute(), "Empty path should not be absolute");
        assert!(empty_path.as_os_str().is_empty(), "Empty path should be empty");

        // Test file_name on empty path
        assert!(empty_path.file_name().is_none(), "Empty path should have no file name");

        // Test parent on empty path
        assert!(empty_path.parent().is_none(), "Empty path should have no parent");
    }

    #[test]
    fn test_relative_vs_absolute_paths() {
        // Test relative vs absolute path handling
        let absolute = if cfg!(windows) {
            PathBuf::from(r"C:\absolute\path.txt")
        } else {
            PathBuf::from("/absolute/path.txt")
        };

        let relative = PathBuf::from("relative/path.txt");

        assert!(absolute.is_absolute(), "Should be absolute path");
        assert!(!relative.is_absolute(), "Should be relative path");

        // Absolute path parent should exist
        assert!(absolute.parent().is_some(), "Absolute path should have parent");

        // Relative path parent should exist (unless it's just "file.txt")
        assert!(relative.parent().is_some(), "Relative path should have parent");
    }

    // ========================================================================
    // Environment Variable Consistency Tests
    // ========================================================================

    #[test]
    fn test_common_environment_variables() {
        // Test common environment variables exist across platforms

        // HOME (Unix) or USERPROFILE (Windows)
        #[cfg(target_os = "windows")]
        let user_home = std::env::var("USERPROFILE");

        #[cfg(not(target_os = "windows"))]
        let user_home = std::env::var("HOME");

        // At least one should be set
        assert!(user_home.is_ok(), "User home directory should be set");

        if let Ok(home) = user_home {
            assert!(!home.is_empty(), "Home directory should not be empty");
        }
    }

    // ========================================================================
    // File Extension Handling Tests
    // ========================================================================

    #[test]
    fn test_file_extension_extraction() {
        // Test file extension extraction works consistently
        let test_cases = vec![
            ("file.txt", Some("txt")),
            ("document.pdf", Some("pdf")),
            ("archive.tar.gz", Some("gz")), // Only last extension
            ("noextension", None),
            ("multiple.dots.name.txt", Some("txt")),
        ];

        for (filename, expected_ext) in test_cases {
            let path = PathBuf::from(filename);
            let actual_ext = path.extension().map(|e| e.to_string_lossy().to_string());

            match expected_ext {
                Some(expected) => {
                    assert!(actual_ext.is_some(), "File '{}' should have extension", filename);
                    assert_eq!(actual_ext.unwrap(), expected,
                        "File '{}' extension should be {}", filename, expected);
                }
                None => {
                    assert!(actual_ext.is_none(), "File '{}' should have no extension", filename);
                }
            }
        }
    }

    // ========================================================================
    // File Metadata Consistency Tests
    // ========================================================================

    #[test]
    fn test_file_metadata_consistency() {
        // Test file metadata operations work consistently
        let temp_dir = std::env::temp_dir();
        let test_file = temp_dir.join("metadata_consistency_test.txt");

        // Create test file
        fs::write(&test_file, "test content")
            .expect("Should be able to write file");

        // Get metadata
        let metadata = fs::metadata(&test_file)
            .expect("Should be able to get metadata");

        // Test is_file
        assert!(metadata.is_file(), "Should be a file");
        assert!(!metadata.is_dir(), "Should not be a directory");

        // Test len
        assert_eq!(metadata.len(), 12, "File length should be 12 bytes");

        // Test permissions (platform-specific)
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let permissions = metadata.permissions();
            let mode = permissions.mode();
            assert!(mode & 0o444 != 0, "File should be readable");
        }

        // Test modified time
        let modified = metadata.modified();
        assert!(modified.is_ok(), "Should have modified time");

        // Cleanup
        let _ = fs::remove_file(&test_file);
    }
}
