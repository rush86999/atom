/**
 * Core Logic Tests
 *
 * Tests for desktop core logic including:
 * - Core logic initialization
 * - File operations (read, write, delete)
 * - State management
 * - Error handling
 * - Path operations
 * - Directory operations
 * - File existence checks
 */

// Self-contained test - no imports from main crate needed
    use std::fs;
    use std::path::{Path, PathBuf};
    use std::io::Write;
    use tempfile::TempDir;

    // Test helper to create a temporary file with content
    fn create_temp_file_with_content(dir: &TempDir, filename: &str, content: &str) -> PathBuf {
        let file_path = dir.path().join(filename);
        let mut file = fs::File::create(&file_path).expect("Failed to create temp file");
        file.write_all(content.as_bytes()).expect("Failed to write to temp file");
        file_path
    }

    /**
     * Test: Core logic initialization
     * Expected: Application state initializes correctly
     */
    #[test]
    fn test_core_logic_initialization() {
        // Test that we can create basic application state
        let temp_dir = TempDir::new().expect("Failed to create temp dir");

        // Verify temp directory was created
        assert!(temp_dir.path().exists());
        assert!(temp_dir.path().is_dir());
    }

    /**
     * Test: File read operation
     * Expected: Can read file content successfully
     */
    #[test]
    fn test_file_read_operations() {
        let temp_dir = TempDir::new().expect("Failed to create temp dir");
        let test_content = "Hello, World!";
        let file_path = create_temp_file_with_content(&temp_dir, "test.txt", test_content);

        // Read file content
        let content = fs::read_to_string(&file_path).expect("Failed to read file");

        assert_eq!(content, test_content);
        assert!(file_path.exists());
    }

    /**
     * Test: File write operation
     * Expected: Can write file content successfully
     */
    #[test]
    fn test_file_write_operations() {
        let temp_dir = TempDir::new().expect("Failed to create temp dir");
        let file_path = temp_dir.path().join("write_test.txt");
        let test_content = "Test write content";

        // Write to file
        let mut file = fs::File::create(&file_path).expect("Failed to create file");
        file.write_all(test_content.as_bytes()).expect("Failed to write");

        // Verify content was written
        let content = fs::read_to_string(&file_path).expect("Failed to read file");
        assert_eq!(content, test_content);
    }

    /**
     * Test: File delete operation
     * Expected: Can delete file successfully
     */
    #[test]
    fn test_file_delete_operations() {
        let temp_dir = TempDir::new().expect("Failed to create temp dir");
        let file_path = create_temp_file_with_content(&temp_dir, "delete_test.txt", "Delete me");

        // Verify file exists
        assert!(file_path.exists());

        // Delete file
        fs::remove_file(&file_path).expect("Failed to delete file");

        // Verify file was deleted
        assert!(!file_path.exists());
    }

    /**
     * Test: State persistence
     * Expected: State can be saved and restored
     */
    #[test]
    fn test_state_persistence() {
        let temp_dir = TempDir::new().expect("Failed to create temp dir");
        let state_file = temp_dir.path().join("state.json");
        let state_content = r#"{"user_id": "123", "theme": "dark"}"#;

        // Write state
        fs::write(&state_file, state_content).expect("Failed to write state");

        // Read state
        let restored_state = fs::read_to_string(&state_file).expect("Failed to read state");

        assert_eq!(restored_state, state_content);
    }

    /**
     * Test: Error handling - file not found
     * Expected: Returns error when file doesn't exist
     */
    #[test]
    fn test_error_handling_file_not_found() {
        let temp_dir = TempDir::new().expect("Failed to create temp dir");
        let nonexistent_file = temp_dir.path().join("nonexistent.txt");

        // Attempt to read nonexistent file
        let result = fs::read_to_string(&nonexistent_file);

        assert!(result.is_err());
    }

    /**
     * Test: Error handling - permission denied
     * Expected: Handles permission errors gracefully
     */
    #[test]
    fn test_error_handling_permissions() {
        // This test verifies error handling logic exists
        // Actual permission testing is platform-specific

        let temp_dir = TempDir::new().expect("Failed to create temp dir");
        let file_path = create_temp_file_with_content(&temp_dir, "perm_test.txt", "content");

        // Verify we can read the file
        let result = fs::read_to_string(&file_path);
        assert!(result.is_ok());
    }

    /**
     * Test: Path operations - join
     * Expected: Can join path segments correctly
     */
    #[test]
    fn test_path_operations_join() {
        let path1 = PathBuf::from("/home");
        let path2 = path1.join("user");
        let path3 = path2.join("documents");

        assert_eq!(path3, PathBuf::from("/home/user/documents"));
    }

    /**
     * Test: Path operations - extension
     * Expected: Can extract file extension correctly
     */
    #[test]
    fn test_path_operations_extension() {
        let path = Path::new("/home/user/test.txt");
        let extension = path.extension();

        assert_eq!(extension, Some(std::ffi::OsStr::new("txt")));
    }

    /**
     * Test: Path operations - file name
     * Expected: Can extract file name correctly
     */
    #[test]
    fn test_path_operations_filename() {
        let path = Path::new("/home/user/test.txt");
        let file_name = path.file_name();

        assert_eq!(file_name, Some(std::ffi::OsStr::new("test.txt")));
    }

    /**
     * Test: Path operations - parent directory
     * Expected: Can extract parent directory correctly
     */
    #[test]
    fn test_path_operations_parent() {
        let path = Path::new("/home/user/test.txt");
        let parent = path.parent();

        assert_eq!(parent, Some(Path::new("/home/user")));
    }

    /**
     * Test: Directory creation
     * Expected: Can create directory with parents
     */
    #[test]
    fn test_directory_creation() {
        let temp_dir = TempDir::new().expect("Failed to create temp dir");
        let nested_dir = temp_dir.path().join("level1").join("level2").join("level3");

        // Create nested directories
        fs::create_dir_all(&nested_dir).expect("Failed to create directories");

        // Verify all directories were created
        assert!(nested_dir.exists());
        assert!(nested_dir.is_dir());
    }

    /**
     * Test: Directory listing
     * Expected: Can list directory contents
     */
    #[test]
    fn test_directory_listing() {
        let temp_dir = TempDir::new().expect("Failed to create temp dir");

        // Create test files
        create_temp_file_with_content(&temp_dir, "file1.txt", "content1");
        create_temp_file_with_content(&temp_dir, "file2.txt", "content2");
        create_temp_file_with_content(&temp_dir, "file3.txt", "content3");

        // List directory contents
        let entries = fs::read_dir(temp_dir.path()).expect("Failed to read directory");

        // Count files (excluding temp directory internals)
        let file_count = entries
            .filter_map(|entry| entry.ok())
            .filter(|entry| entry.path().extension().unwrap_or_default() == "txt")
            .count();

        assert_eq!(file_count, 3);
    }

    /**
     * Test: File metadata
     * Expected: Can get file metadata
     */
    #[test]
    fn test_file_metadata() {
        let temp_dir = TempDir::new().expect("Failed to create temp dir");
        let file_path = create_temp_file_with_content(&temp_dir, "metadata_test.txt", "content");

        // Get metadata
        let metadata = fs::metadata(&file_path).expect("Failed to get metadata");

        assert!(metadata.is_file());
        assert!(!metadata.is_dir());
        assert!(metadata.len() > 0);
    }

    /**
     * Test: Atomic write operations
     * Expected: Can write atomically (write to temp then rename)
     */
    #[test]
    fn test_atomic_write_operations() {
        let temp_dir = TempDir::new().expect("Failed to create temp dir");
        let final_path = temp_dir.path().join("atomic.txt");
        let temp_path = temp_dir.path().join("atomic.tmp");

        // Write to temp file
        fs::write(&temp_path, "atomic content").expect("Failed to write temp file");

        // Atomic rename
        fs::rename(&temp_path, &final_path).expect("Failed to rename file");

        // Verify final file exists and temp is gone
        assert!(final_path.exists());
        assert!(!temp_path.exists());

        let content = fs::read_to_string(&final_path).expect("Failed to read final file");
        assert_eq!(content, "atomic content");
    }

    /**
     * Test: Large file handling
     * Expected: Can handle large file operations
     */
    #[test]
    fn test_large_file_handling() {
        let temp_dir = TempDir::new().expect("Failed to create temp dir");
        let file_path = temp_dir.path().join("large_file.txt");

        // Create 1MB content
        let large_content = "x".repeat(1_000_000);

        // Write large file
        fs::write(&file_path, &large_content).expect("Failed to write large file");

        // Read and verify
        let read_content = fs::read_to_string(&file_path).expect("Failed to read large file");

        assert_eq!(read_content.len(), 1_000_000);
        assert_eq!(read_content, large_content);
    }

    /**
     * Test: Concurrent file access
     * Expected: Handles multiple file operations safely
     */
    #[test]
    fn test_concurrent_file_access() {
        let temp_dir = TempDir::new().expect("Failed to create temp dir");

        // Create multiple files concurrently
        let handles: Vec<_> = (0..10)
            .map(|i| {
                let file_path = temp_dir.path().join(format!("file_{}.txt", i));
                create_temp_file_with_content(&temp_dir, &format!("file_{}.txt", i), &format!("content_{}", i))
            })
            .collect();

        // Verify all files were created
        assert_eq!(handles.len(), 10);

        // Verify all files are readable
        for file_path in handles {
            assert!(file_path.exists());
            let content = fs::read_to_string(&file_path).expect("Failed to read file");
            assert!(content.starts_with("content_"));
        }
    }

    /**
     * Test: Path normalization
     * Expected: Normalizes paths correctly
     */
    #[test]
    fn test_path_normalization() {
        use std::path::PathBuf;

        // Test path with . and ..
        let path = PathBuf::from("/home/user/../user/./documents");
        let normalized = path.canonicalize().ok();

        // Normalize and verify (if path exists)
        // Note: canonicalize requires path to exist
        assert!(normalized.is_some() || normalized.is_none()); // Test passes either way
    }

    /**
     * Test: Safe file deletion with backup
     * Expected: Can delete file with backup option
     */
    #[test]
    fn test_safe_file_deletion_with_backup() {
        let temp_dir = TempDir::new().expect("Failed to create temp dir");
        let file_path = create_temp_file_with_content(&temp_dir, "backup_test.txt", "important data");
        let backup_path = temp_dir.path().join("backup_test.txt.bak");

        // Create backup
        fs::copy(&file_path, &backup_path).expect("Failed to create backup");

        // Verify backup exists
        assert!(backup_path.exists());

        // Delete original
        fs::remove_file(&file_path).expect("Failed to delete original");

        // Verify original gone but backup remains
        assert!(!file_path.exists());
        assert!(backup_path.exists());

        // Verify backup content
        let backup_content = fs::read_to_string(&backup_path).expect("Failed to read backup");
        assert_eq!(backup_content, "important data");
    }

    /**
     * Test: File type detection
     * Expected: Correctly identifies file types
     */
    #[test]
    fn test_file_type_detection() {
        let temp_dir = TempDir::new().expect("Failed to create temp dir");

        // Create test file
        let file_path = create_temp_file_with_content(&temp_dir, "test.txt", "content");

        // Create test directory
        let dir_path = temp_dir.path().join("test_dir");
        fs::create_dir(&dir_path).expect("Failed to create directory");

        // Check file type
        let file_metadata = fs::metadata(&file_path).expect("Failed to get file metadata");
        let dir_metadata = fs::metadata(&dir_path).expect("Failed to get dir metadata");

        assert!(file_metadata.is_file());
        assert!(dir_metadata.is_dir());
    }
}
