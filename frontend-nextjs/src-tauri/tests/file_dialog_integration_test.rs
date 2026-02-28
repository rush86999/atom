//! Integration tests for Tauri file dialog workflows
//!
//! Tests for file read/write workflows, directory listing, and file metadata.
//! These tests verify end-to-end file operations using temp directories
//! with proper cleanup.

#[cfg(test)]
mod tests {
    use std::fs;

    // ========================================================================
    // File Read/Write Workflow Tests
    // ========================================================================

    #[test]
    fn test_file_read_workflow_with_temp_file() {
        let temp_dir = std::env::temp_dir();
        let test_file = temp_dir.join("atom_integration_read_test.txt");
        let test_content = "Hello from Atom file dialog integration test!";

        // Setup: Create test file
        fs::write(&test_file, test_content)
            .expect("Failed to write test file");

        // Verify file exists
        assert!(test_file.exists(), "Test file should exist");

        // Read file content
        let read_content = fs::read_to_string(&test_file)
            .expect("Failed to read test file");

        // Verify content matches
        assert_eq!(read_content, test_content, "Read content should match written content");

        // Cleanup
        let _ = fs::remove_file(&test_file);
        assert!(!test_file.exists(), "Test file should be cleaned up");
    }

    #[test]
    fn test_file_write_workflow_to_temp_directory() {
        let temp_dir = std::env::temp_dir();
        let test_file = temp_dir.join("atom_integration_write_test.txt");
        let test_content = "Integration test content for file write workflow";

        // Write file
        fs::write(&test_file, test_content)
            .expect("Failed to write test file");

        // Verify file was written
        assert!(test_file.exists(), "Written file should exist");

        // Verify content
        let written_content = fs::read_to_string(&test_file)
            .expect("Failed to verify written content");

        assert_eq!(written_content, test_content, "Written content should match original");

        // Verify file size
        let metadata = fs::metadata(&test_file)
            .expect("Failed to get file metadata");

        assert_eq!(metadata.len(), test_content.len() as u64, "File size should match content length");

        // Cleanup
        let _ = fs::remove_file(&test_file);
    }

    #[test]
    fn test_nested_directory_creation_and_file_write() {
        let temp_dir = std::env::temp_dir();
        let nested_dir = temp_dir.join("atom_integration").join("level1").join("level2");
        let test_file = nested_dir.join("nested_test.txt");
        let test_content = "Content in nested directory";

        // Create parent directories
        if let Some(parent) = test_file.parent() {
            fs::create_dir_all(parent)
                .expect("Failed to create parent directories");
        }

        // Verify nested directories exist
        assert!(nested_dir.exists(), "Nested directory should exist");
        assert!(nested_dir.is_dir(), "Nested path should be a directory");

        // Write file to nested directory
        fs::write(&test_file, test_content)
            .expect("Failed to write to nested directory");

        // Verify file exists in nested location
        assert!(test_file.exists(), "File should exist in nested directory");

        // Verify content
        let read_content = fs::read_to_string(&test_file)
            .expect("Failed to read from nested directory");

        assert_eq!(read_content, test_content, "Nested file content should match");

        // Cleanup: Remove entire nested directory tree
        let _ = fs::remove_file(&test_file);
        let _ = fs::remove_dir_all(nested_dir.parent().unwrap());

        // Verify cleanup
        assert!(!test_file.exists(), "Nested file should be cleaned up");
        assert!(!nested_dir.exists(), "Nested directory should be cleaned up");
    }

    // ========================================================================
    // Directory Listing Workflow Tests
    // ========================================================================

    #[test]
    fn test_directory_listing_with_files_and_subdirectories() {
        let temp_dir = std::env::temp_dir();
        let test_dir = temp_dir.join("atom_integration_list_test");

        // Setup: Create directory with mixed content
        fs::create_dir_all(&test_dir)
            .expect("Failed to create test directory");

        // Create files
        fs::write(test_dir.join("file1.txt"), "content1")
            .expect("Failed to create file1");
        fs::write(test_dir.join("file2.md"), "content2")
            .expect("Failed to create file2");
        fs::write(test_dir.join("file3.json"), "{\"key\": \"value\"}")
            .expect("Failed to create file3");

        // Create subdirectories
        fs::create_dir(test_dir.join("subdir1"))
            .expect("Failed to create subdir1");
        fs::create_dir(test_dir.join("subdir2"))
            .expect("Failed to create subdir2");

        // List directory
        let entries = fs::read_dir(&test_dir)
            .expect("Failed to list directory");

        let entry_names: Vec<String> = entries
            .flatten()
            .map(|e| e.file_name().to_string_lossy().to_string())
            .collect();

        // Verify all entries present
        assert!(entry_names.len() >= 5, "Should have at least 5 entries (3 files + 2 dirs)");
        assert!(entry_names.contains(&"file1.txt".to_string()), "Should contain file1.txt");
        assert!(entry_names.contains(&"file2.md".to_string()), "Should contain file2.md");
        assert!(entry_names.contains(&"file3.json".to_string()), "Should contain file3.json");
        assert!(entry_names.contains(&"subdir1".to_string()), "Should contain subdir1");
        assert!(entry_names.contains(&"subdir2".to_string()), "Should contain subdir2");

        // Cleanup
        let _ = fs::remove_file(test_dir.join("file1.txt"));
        let _ = fs::remove_file(test_dir.join("file2.md"));
        let _ = fs::remove_file(test_dir.join("file3.json"));
        let _ = fs::remove_dir(test_dir.join("subdir1"));
        let _ = fs::remove_dir(test_dir.join("subdir2"));
        let _ = fs::remove_dir(&test_dir);
    }

    #[test]
    fn test_directory_listing_nonexistent_error_handling() {
        let temp_dir = std::env::temp_dir();
        let nonexistent_dir = temp_dir.join("atom_nonexistent_test_dir_12345");

        // Ensure directory doesn't exist
        if nonexistent_dir.exists() {
            let _ = fs::remove_dir_all(&nonexistent_dir);
        }

        // Attempt to list non-existent directory
        let result = fs::read_dir(&nonexistent_dir);

        // Verify error returned
        assert!(result.is_err(), "Should return error for non-existent directory");

        let error_msg = result.unwrap_err().to_string();
        assert!(error_msg.contains("No such file") || error_msg.contains("not found") || error_msg.contains("os error 2"),
            "Error should indicate directory not found");
    }

    #[test]
    fn test_directory_listing_file_as_directory_error() {
        let temp_dir = std::env::temp_dir();
        let test_file = temp_dir.join("atom_not_a_dir_test.txt");

        // Create file
        fs::write(&test_file, "test content")
            .expect("Failed to create test file");

        // Attempt to list file as directory
        let result = fs::read_dir(&test_file);

        // Verify error returned
        assert!(result.is_err(), "Should return error when listing file as directory");

        // Cleanup
        let _ = fs::remove_file(&test_file);
    }

    // ========================================================================
    // File Metadata Workflow Tests
    // ========================================================================

    #[test]
    fn test_file_metadata_size_and_modified_time() {
        let temp_dir = std::env::temp_dir();
        let test_file = temp_dir.join("atom_metadata_test.txt");
        let test_content = "Content for metadata test";

        // Write file
        fs::write(&test_file, test_content)
            .expect("Failed to write test file");

        // Get metadata
        let metadata = fs::metadata(&test_file)
            .expect("Failed to get file metadata");

        // Verify size
        assert_eq!(metadata.len(), test_content.len() as u64, "File size should match content length");

        // Verify it's a file (not directory)
        assert!(metadata.is_file(), "Should be a file");
        assert!(!metadata.is_dir(), "Should not be a directory");

        // Verify modified time exists
        let modified = metadata.modified()
            .expect("Failed to get modified time");

        let now = std::time::SystemTime::now();
        let duration = now.duration_since(modified)
            .expect("Modified time should be in the past");

        // Verify file was modified recently (within last 10 seconds)
        assert!(duration.as_secs() < 10, "File should have been modified recently");

        // Cleanup
        let _ = fs::remove_file(&test_file);
    }

    #[test]
    fn test_entry_iteration_and_metadata_extraction() {
        let temp_dir = std::env::temp_dir();
        let test_dir = temp_dir.join("atom_entry_iteration_test");

        // Setup: Create directory with files of different sizes
        fs::create_dir_all(&test_dir)
            .expect("Failed to create test directory");

        fs::write(test_dir.join("small.txt"), "x")
            .expect("Failed to create small file");
        fs::write(test_dir.join("medium.txt"), "x".repeat(100))
            .expect("Failed to create medium file");
        fs::write(test_dir.join("large.txt"), "x".repeat(1000))
            .expect("Failed to create large file");

        // Iterate entries and extract metadata
        let entries = fs::read_dir(&test_dir)
            .expect("Failed to list directory");

        let mut file_count = 0;
        let mut total_size = 0u64;

        for entry in entries.flatten() {
            let metadata = entry.metadata()
                .expect("Failed to get entry metadata");

            if metadata.is_file() {
                file_count += 1;
                total_size += metadata.len();

                // Verify all files have readable metadata
                assert!(metadata.modified().is_ok(), "Should have modified time");
                assert!(metadata.created().is_ok() || cfg!(target_os = "linux"),
                    "Should have creation time (not guaranteed on Linux)");
            }
        }

        // Verify we found all 3 files
        assert_eq!(file_count, 3, "Should find 3 files");

        // Verify total size (1 + 100 + 1000 = 1101 bytes)
        assert_eq!(total_size, 1101, "Total size should match sum of file sizes");

        // Cleanup
        let _ = fs::remove_file(test_dir.join("small.txt"));
        let _ = fs::remove_file(test_dir.join("medium.txt"));
        let _ = fs::remove_file(test_dir.join("large.txt"));
        let _ = fs::remove_dir(&test_dir);
    }

    // ========================================================================
    // Cross-Platform Path Handling Tests
    // ========================================================================

    #[test]
    fn test_path_separator_handling() {
        let temp_dir = std::env::temp_dir();

        // Create path with multiple components
        let test_path = temp_dir.join("level1").join("level2").join("test.txt");

        // Verify path is properly constructed
        assert!(test_path.is_absolute(), "Path should be absolute");

        // Verify file name extraction works
        let file_name = test_path.file_name()
            .expect("Should have file name");

        assert_eq!(file_name.to_string_lossy(), "test.txt", "File name should be extracted correctly");

        // Verify extension extraction works
        let extension = test_path.extension()
            .expect("Should have extension");

        assert_eq!(extension.to_string_lossy(), "txt", "Extension should be extracted correctly");

        // Verify parent directory works
        let parent = test_path.parent()
            .expect("Should have parent");

        assert!(parent.ends_with("level2"), "Parent should end with level2");
    }

    #[test]
    fn test_temp_directory_cross_platform() {
        let temp_dir = std::env::temp_dir();

        // Verify temp directory exists and is accessible
        assert!(temp_dir.exists(), "Temp directory should exist");
        assert!(temp_dir.is_dir(), "Temp should be a directory");

        // Verify temp directory is writable
        let test_file = temp_dir.join("cross_platform_write_test.txt");
        fs::write(&test_file, "test")
            .expect("Should be able to write to temp directory");

        assert!(test_file.exists(), "Written file should exist in temp directory");

        // Cleanup
        let _ = fs::remove_file(&test_file);
    }
}
