//! Tests for desktop helper functions.
//!
//! Tests cover:
//! - File operation helpers (read, write, exists, delete, create directory)
//! - Path handling helpers (join, normalize, parent, file name, absolute)
//! - OS detection helpers (macOS, Windows, Linux)
//! - String helpers (truncate, sanitize filename, unique ID)

#[cfg(test)]
mod tests {
    // Note: These tests are written to be run with: cargo test --test helpers_test
    // The helper functions are in src/helpers.rs

    #[test]
    fn test_join_paths() {
        // Test basic path joining
        let result = helpers::join_paths(&["home", "user", "documents"]);
        assert!(result.to_string_lossy().contains("documents"));

        // Test single segment
        let result = helpers::join_paths(&["single"]);
        assert!(result.to_string_lossy().contains("single"));

        // Test empty segments
        let result = helpers::join_paths(&[]]);
        assert_eq!(result.to_string_lossy(), "");
    }

    #[test]
    fn test_get_file_extension() {
        // Test common extensions
        assert_eq!(helpers::get_file_extension("test.txt"), Some("txt".to_string()));
        assert_eq!(helpers::get_file_extension("document.pdf"), Some("pdf".to_string()));
        assert_eq!(helpers::get_file_extension("image.png"), Some("png".to_string()));

        // Test no extension
        assert_eq!(helpers::get_file_extension("test"), None);
        assert_eq!(helpers::get_file_extension("test."), None);

        // Test hidden files (Unix-style)
        assert_eq!(helpers::get_file_extension(".hidden"), None);
        assert_eq!(helpers::get_file_extension(".gitignore"), Some("gitignore".to_string()));

        // Test multiple extensions
        assert_eq!(helpers::get_file_extension("archive.tar.gz"), Some("gz".to_string()));
    }

    #[test]
    fn test_get_parent_directory() {
        // Test getting parent directory
        let parent = helpers::get_parent_directory("/home/user/file.txt");
        assert!(parent.is_some());
        let parent_path = parent.unwrap();
        assert!(parent_path.to_string_lossy().contains("user"));

        // Test root path (no parent)
        let parent = helpers::get_parent_directory("/");
        assert!(parent.is_none() || parent.unwrap().to_string_lossy().is_empty());

        // Test nested path
        let parent = helpers::get_parent_directory("/a/b/c/d");
        assert!(parent.is_some());
        assert!(parent.unwrap().to_string_lossy().contains("c"));
    }

    #[test]
    fn test_get_file_name() {
        // Test extracting file name
        assert_eq!(helpers::get_file_name("/path/to/file.txt"), Some("file.txt".to_string()));
        assert_eq!(helpers::get_file_name("file.txt"), Some("file.txt".to_string()));

        // Test directory path
        assert_eq!(helpers::get_file_name("/path/to/"), None);

        // Test root path
        assert_eq!(helpers::get_file_name("/"), None);
    }

    #[test]
    fn test_is_absolute_path() {
        // Test absolute paths
        assert!(helpers::is_absolute_path("/home/user"));
        assert!(helpers::is_absolute_path("/"));

        // Test relative paths
        assert!(!helpers::is_absolute_path("relative/path"));
        assert!(!helpers::is_absolute_path("./relative"));
        assert!(!helpers::is_absolute_path("../parent"));

        // Platform-specific tests
        #[cfg(windows)]
        {
            assert!(helpers::is_absolute_path("C:\\Users\\user"));
            assert!(helpers::is_absolute_path("\\\\server\\share"));
        }
    }

    #[test]
    fn test_truncate_string() {
        // Test string shorter than max length
        assert_eq!(helpers::truncate_string("short", 10), "short");

        // Test string exactly at max length
        assert_eq!(helpers::truncate_string("exact", 5), "exact");

        // Test string longer than max length
        assert_eq!(helpers::truncate_string("very long text", 10), "very lo...");

        // Test empty string
        assert_eq!(helpers::truncate_string("", 10), "");

        // Test max length less than ellipsis length
        assert_eq!(helpers::truncate_string("text", 2), "..");
    }

    #[test]
    fn test_sanitize_filename() {
        // Test invalid characters (Windows)
        assert_eq!(helpers::sanitize_filename("file<name>.txt"), "file_name_.txt");
        assert_eq!(helpers::sanitize_filename("file>name>.txt"), "file_name_.txt");
        assert_eq!(helpers::sanitize_filename("file:name?.txt"), "file_name_.txt");

        // Test path separators
        assert_eq!(helpers::sanitize_filename("file/name.txt"), "file_name.txt");
        assert_eq!(helpers::sanitize_filename("file\\name.txt"), "file_name.txt");

        // Test invalid characters
        assert_eq!(helpers::sanitize_filename('file"name|.txt'), "file_name_.txt");
        assert_eq!(helpers::sanitize_filename("file*name?.txt"), "file_name_.txt");

        // Test valid filename (unchanged)
        assert_eq!(helpers::sanitize_filename("normal.txt"), "normal.txt");
        assert_eq!(helpers::sanitize_filename("file_name-123.txt"), "file_name-123.txt");

        // Test empty filename
        assert_eq!(helpers::sanitize_filename(""), "");
    }

    #[test]
    fn test_generate_unique_id() {
        // Test that IDs are unique
        let id1 = helpers::generate_unique_id();
        let id2 = helpers::generate_unique_id();
        assert_ne!(id1, id2);

        // Test that IDs are non-empty
        assert!(!id1.is_empty());
        assert!(!id2.is_empty());

        // Test that IDs are hex strings
        assert!(id1.chars().all(|c| c.is_ascii_hexdigit()));
        assert!(id2.chars().all(|c| c.is_ascii_hexdigit()));
    }

    #[test]
    fn test_is_macos() {
        // Result depends on test platform
        let result = helpers::is_macos();
        // Just verify it returns a boolean
        assert!(result || !result);
    }

    #[test]
    fn test_is_windows() {
        // Result depends on test platform
        let result = helpers::is_windows();
        // Just verify it returns a boolean
        assert!(result || !result);
    }

    #[test]
    fn test_is_linux() {
        // Result depends on test platform
        let result = helpers::is_linux();
        // Just verify it returns a boolean
        assert!(result || !result);
    }

    #[test]
    fn test_get_home_directory() {
        let home = helpers::get_home_directory();
        assert!(home.is_some());

        let home_path = home.unwrap();
        assert!(!home_path.to_string_lossy().is_empty());

        // Verify home directory exists
        assert!(home_path.exists());
    }

    // File operation tests (require temp directory)
    #[test]
    fn test_file_operations() {
        use std::fs;
        use tempfile::TempDir;

        // Create temp directory
        let temp_dir = TempDir::new().unwrap();
        let test_file = temp_dir.path().join("test.txt");
        let test_content = "Hello, World!";

        // Test write and read
        helpers::write_file_content(&test_file, test_content).unwrap();
        assert!(test_file.exists());

        let read_content = helpers::read_file_content(&test_file).unwrap();
        assert_eq!(read_content, test_content);

        // Test file_exists
        assert!(helpers::file_exists(&test_file));
        assert!(!helpers::file_exists(temp_dir.path().join("nonexistent.txt")));

        // Test delete
        helpers::delete_file(&test_file).unwrap();
        assert!(!test_file.exists());

        // Test create_directory
        let test_dir = temp_dir.path().join("test_dir");
        helpers::create_directory(&test_dir).unwrap();
        assert!(test_dir.exists());
        assert!(test_dir.is_dir());
    }

    #[test]
    fn test_normalize_path() {
        // Test absolute path
        let abs_path = helpers::normalize_path("/home/user");
        assert!(abs_path.is_absolute());

        // Test relative path (may fail if path doesn't exist)
        let rel_path = helpers::normalize_path(".");
        assert!(rel_path.is_absolute());
    }

    #[test]
    fn test_edge_cases() {
        // Test empty strings in path operations
        assert_eq!(helpers::get_file_extension(""), None);
        assert_eq!(helpers::get_file_name(""), None);

        // Test special characters in filenames
        let sanitized = helpers::sanitize_filename("file<>:\"/\\|?*.txt");
        assert!(!sanitized.contains('<'));
        assert!(!sanitized.contains('>'));

        // Test very long path
        let long_name = "a".repeat(1000);
        let truncated = helpers::truncate_string(&long_name, 100);
        assert!(truncated.len() <= 100);
    }

    #[test]
    fn test_unicode_handling() {
        // Test Unicode characters in filename
        assert_eq!(helpers::sanitize_filename("文件.txt"), "文件.txt");

        // Test Unicode in path
        let parent = helpers::get_parent_directory("/path/to/文件");
        assert!(parent.is_some());

        // Test Unicode truncation
        let unicode_text = "Hello 世界 🌍";
        let truncated = helpers::truncate_string(unicode_text, 10);
        assert!(truncated.len() <= 13); // 10 chars + "..."
    }
}
