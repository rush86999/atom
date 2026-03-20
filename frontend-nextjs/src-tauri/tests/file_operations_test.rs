// File Operations Tests
//
// Tests for file system operations including:
// - File reading
// - File writing
// - File existence checks
// - Directory operations
// - File permissions
// - Error handling
// - Path handling (relative, absolute)
//
// Author: Phase 212 Wave 4B
// Date: 2026-03-20

use std::fs;
use std::io::{Read, Write, Seek};
use std::path::PathBuf;
use tempfile::TempDir;

#[test]
fn test_file_read() {
    // Test file reading
    let temp_dir = TempDir::new().expect("Failed to create temp dir");
    let file_path = temp_dir.path().join("test_read.txt");

    // Write test content
    let content = "Hello, World!";
    fs::write(&file_path, content).expect("Failed to write file");

    // Read file
    let read_content = fs::read_to_string(&file_path).expect("Failed to read file");

    assert_eq!(read_content, content);
    assert!(file_path.exists());
}

#[test]
fn test_file_write() {
    // Test file writing
    let temp_dir = TempDir::new().expect("Failed to create temp dir");
    let file_path = temp_dir.path().join("test_write.txt");

    // Write content
    let content = "Test content for writing";
    let mut file = fs::File::create(&file_path).expect("Failed to create file");
    file.write_all(content.as_bytes()).expect("Failed to write to file");

    // Verify content
    let read_content = fs::read_to_string(&file_path).expect("Failed to read file");
    assert_eq!(read_content, content);
}

#[test]
fn test_file_exists() {
    // Test file existence check
    let temp_dir = TempDir::new().expect("Failed to create temp dir");
    let existing_file = temp_dir.path().join("existing.txt");
    let non_existing_file = temp_dir.path().join("non_existing.txt");

    // Create existing file
    fs::write(&existing_file, "content").expect("Failed to write file");

    // Check existence
    assert!(existing_file.exists());
    assert!(!non_existing_file.exists());
}

#[test]
fn test_directory_operations() {
    // Test directory create/list/delete
    let temp_dir = TempDir::new().expect("Failed to create temp dir");

    // Create directory
    let dir_path = temp_dir.path().join("test_dir");
    fs::create_dir(&dir_path).expect("Failed to create directory");
    assert!(dir_path.exists());
    assert!(dir_path.is_dir());

    // Create nested directories
    let nested_dir = dir_path.join("nested").join("deeply");
    fs::create_dir_all(&nested_dir).expect("Failed to create nested directories");
    assert!(nested_dir.exists());

    // List directory contents
    let entries = fs::read_dir(&dir_path).expect("Failed to read directory");
    let entry_count = entries.count();
    assert!(entry_count >= 1);

    // Delete directory
    fs::remove_dir_all(&dir_path).expect("Failed to remove directory");
    assert!(!dir_path.exists());
}

#[test]
fn test_file_permissions() {
    // Test permission checks
    let temp_dir = TempDir::new().expect("Failed to create temp dir");
    let file_path = temp_dir.path().join("test_permissions.txt");

    // Create file
    fs::write(&file_path, "content").expect("Failed to write file");

    // Check if file is readable
    let metadata = fs::metadata(&file_path).expect("Failed to get metadata");
    assert!(metadata.is_file());

    // Check if file is readable (try to read it)
    let can_read = fs::read_to_string(&file_path).is_ok();
    assert!(can_read);

    // Check permissions (Unix-specific)
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let permissions = metadata.permissions();
        let mode = permissions.mode();
        // File should have read permission for owner
        assert!(mode & 0o400 != 0);
    }
}

#[test]
fn test_error_handling() {
    // Test error cases (not found, permission denied)
    let non_existing_file = PathBuf::from("/tmp/non_existing_file_12345.txt");

    // Test file not found
    let result = fs::read_to_string(&non_existing_file);
    assert!(result.is_err());

    // Test writing to read-only location (if applicable)
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let temp_dir = TempDir::new().expect("Failed to create temp dir");
        let readonly_file = temp_dir.path().join("readonly.txt");

        // Create file
        fs::write(&readonly_file, "content").expect("Failed to write file");

        // Make it read-only
        let metadata = fs::metadata(&readonly_file).expect("Failed to get metadata");
        let mut permissions = metadata.permissions();
        permissions.set_mode(0o400); // Read-only
        fs::set_permissions(&readonly_file, permissions).expect("Failed to set permissions");

        // Try to write to read-only file
        let result = fs::write(&readonly_file, "new content");
        assert!(result.is_err());
    }
}

#[test]
fn test_file_paths() {
    // Test path handling (relative, absolute)
    let temp_dir = TempDir::new().expect("Failed to create temp dir");

    // Absolute path
    let absolute_path = temp_dir.path().join("absolute.txt");
    assert!(absolute_path.is_absolute());

    // Relative path
    let relative_path = PathBuf::from("relative.txt");
    assert!(!relative_path.is_absolute());

    // Path components
    let path = temp_dir.path().join("parent").join("child.txt");
    let parent = path.parent().unwrap();
    assert!(parent.ends_with("parent"));

    let file_name = path.file_name().unwrap();
    assert_eq!(file_name, "child.txt");

    // Path extension
    let ext = path.extension().unwrap();
    assert_eq!(ext, "txt");
}

#[test]
fn test_file_append() {
    // Test appending to file
    let temp_dir = TempDir::new().expect("Failed to create temp dir");
    let file_path = temp_dir.path().join("test_append.txt");

    // Write initial content
    fs::write(&file_path, "Line 1\n").expect("Failed to write file");

    // Append content
    let mut file = fs::OpenOptions::new()
        .append(true)
        .open(&file_path)
        .expect("Failed to open file");

    file.write_all(b"Line 2\n").expect("Failed to append to file");

    // Verify appended content
    let content = fs::read_to_string(&file_path).expect("Failed to read file");
    assert_eq!(content, "Line 1\nLine 2\n");
}

#[test]
fn test_file_copy() {
    // Test file copying
    let temp_dir = TempDir::new().expect("Failed to create temp dir");
    let src_path = temp_dir.path().join("source.txt");
    let dst_path = temp_dir.path().join("destination.txt");

    // Create source file
    let content = "Content to copy";
    fs::write(&src_path, content).expect("Failed to write file");

    // Copy file
    fs::copy(&src_path, &dst_path).expect("Failed to copy file");

    // Verify copy
    assert!(dst_path.exists());
    let copied_content = fs::read_to_string(&dst_path).expect("Failed to read file");
    assert_eq!(copied_content, content);

    // Original should still exist
    assert!(src_path.exists());
}

#[test]
fn test_file_rename() {
    // Test file renaming
    let temp_dir = TempDir::new().expect("Failed to create temp dir");
    let old_path = temp_dir.path().join("old_name.txt");
    let new_path = temp_dir.path().join("new_name.txt");

    // Create file with old name
    let content = "Content to rename";
    fs::write(&old_path, content).expect("Failed to write file");

    // Rename file
    fs::rename(&old_path, &new_path).expect("Failed to rename file");

    // Verify rename
    assert!(!old_path.exists());
    assert!(new_path.exists());

    let renamed_content = fs::read_to_string(&new_path).expect("Failed to read file");
    assert_eq!(renamed_content, content);
}

#[test]
fn test_file_delete() {
    // Test file deletion
    let temp_dir = TempDir::new().expect("Failed to create temp dir");
    let file_path = temp_dir.path().join("to_delete.txt");

    // Create file
    fs::write(&file_path, "content").expect("Failed to write file");
    assert!(file_path.exists());

    // Delete file
    fs::remove_file(&file_path).expect("Failed to remove file");
    assert!(!file_path.exists());
}

#[test]
fn test_binary_file_operations() {
    // Test binary file operations
    let temp_dir = TempDir::new().expect("Failed to create temp dir");
    let file_path = temp_dir.path().join("binary.bin");

    // Write binary data
    let binary_data: Vec<u8> = vec![0x00, 0x01, 0x02, 0xFF, 0xFE, 0xFD];
    fs::write(&file_path, &binary_data).expect("Failed to write binary file");

    // Read binary data
    let read_data = fs::read(&file_path).expect("Failed to read binary file");
    assert_eq!(read_data, binary_data);
}

#[test]
fn test_file_metadata() {
    // Test file metadata
    let temp_dir = TempDir::new().expect("Failed to create temp dir");
    let file_path = temp_dir.path().join("metadata.txt");

    // Create file
    let content = "Metadata test";
    fs::write(&file_path, content).expect("Failed to write file");

    // Get metadata
    let metadata = fs::metadata(&file_path).expect("Failed to get metadata");
    assert!(metadata.is_file());
    assert!(!metadata.is_dir());
    assert!(metadata.len() > 0);

    // Check modified time
    let modified = metadata.modified().expect("Failed to get modified time");
    assert!(modified.elapsed().unwrap().as_secs() < 10); // Modified within last 10 seconds
}

#[test]
fn test_empty_file() {
    // Test empty file handling
    let temp_dir = TempDir::new().expect("Failed to create temp dir");
    let file_path = temp_dir.path().join("empty.txt");

    // Create empty file
    fs::File::create(&file_path).expect("Failed to create file");

    // Read empty file
    let content = fs::read_to_string(&file_path).expect("Failed to read file");
    assert_eq!(content, "");

    // Check file size
    let metadata = fs::metadata(&file_path).expect("Failed to get metadata");
    assert_eq!(metadata.len(), 0);
}

#[test]
fn test_large_file() {
    // Test large file handling
    let temp_dir = TempDir::new().expect("Failed to create temp dir");
    let file_path = temp_dir.path().join("large.txt");

    // Create large content (1 MB)
    let large_content = "x".repeat(1_000_000);
    fs::write(&file_path, &large_content).expect("Failed to write large file");

    // Read large file
    let read_content = fs::read_to_string(&file_path).expect("Failed to read large file");
    assert_eq!(read_content.len(), 1_000_000);

    // Check file size
    let metadata = fs::metadata(&file_path).expect("Failed to get metadata");
    assert_eq!(metadata.len(), 1_000_000);
}

#[test]
fn test_file_seek_and_read() {
    // Test file seeking and partial reading
    let temp_dir = TempDir::new().expect("Failed to create temp dir");
    let file_path = temp_dir.path().join("seek.txt");

    // Write content
    let content = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    fs::write(&file_path, content).expect("Failed to write file");

    // Open file and seek
    let mut file = fs::File::open(&file_path).expect("Failed to open file");
    use std::io::Seek;

    // Seek to position 10
    file.seek(std::io::SeekFrom::Start(10)).expect("Failed to seek");

    // Read 10 bytes
    let mut buffer = vec![0u8; 10];
    file.read_exact(&mut buffer).expect("Failed to read");

    // Verify content (position 10 starts with 'A')
    let partial_content = String::from_utf8(buffer).expect("Invalid UTF-8");
    assert_eq!(partial_content, "ABCDEFGHIJ");
}
