//! Desktop helper functions for file operations, path handling, and OS detection.
//!
//! This module provides cross-platform utility functions for common desktop operations.

use std::path::{Path, PathBuf};
use std::fs;
use std::env;

/// Read file content as string.
///
/// # Arguments
/// * `path` - Path to the file
///
/// # Returns
/// * `Ok(String)` - File content
/// * `Err(io::Error)` - I/O error if file cannot be read
///
/// # Example
/// ```
/// let content = read_file_content("test.txt")?;
/// ```
pub fn read_file_content<P: AsRef<Path>>(path: P) -> Result<String, std::io::Error> {
    fs::read_to_string(path)
}

/// Write content to file.
///
/// # Arguments
/// * `path` - Path to the file
/// * `content` - Content to write
///
/// # Returns
/// * `Ok(())` - Success
/// * `Err(io::Error)` - I/O error if file cannot be written
pub fn write_file_content<P: AsRef<Path>>(path: P, content: &str) -> Result<(), std::io::Error> {
    fs::write(path, content)
}

/// Check if file exists.
///
/// # Arguments
/// * `path` - Path to check
///
/// # Returns
/// * `true` if file exists, `false` otherwise
pub fn file_exists<P: AsRef<Path>>(path: P) -> bool {
    path.as_ref().exists()
}

/// Delete file safely.
///
/// # Arguments
/// * `path` - Path to the file to delete
///
/// # Returns
/// * `Ok(())` - Success
/// * `Err(io::Error)` - I/O error if file cannot be deleted
pub fn delete_file<P: AsRef<Path>>(path: P) -> Result<(), std::io::Error> {
    fs::remove_file(path)
}

/// Create directory with parents if needed.
///
/// # Arguments
/// * `path` - Path to the directory to create
///
/// # Returns
/// * `Ok(())` - Success
/// * `Err(io::Error)` - I/O error if directory cannot be created
pub fn create_directory<P: AsRef<Path>>(path: P) -> Result<(), std::io::Error> {
    fs::create_dir_all(path)
}

/// Get file extension from path.
///
/// # Arguments
/// * `path` - Path to the file
///
/// # Returns
/// * `Some(String)` - File extension (without dot)
/// * `None` - No extension
pub fn get_file_extension<P: AsRef<Path>>(path: P) -> Option<String> {
    path.as_ref()
        .extension()
        .map(|ext| ext.to_string_lossy().to_string())
}

/// Join path segments.
///
/// # Arguments
/// * `segments` - Path segments to join
///
/// # Returns
/// Joined path as PathBuf
pub fn join_paths(segments: &[&str]) -> PathBuf {
    segments.iter().fold(PathBuf::new(), |acc, segment| acc.join(segment))
}

/// Normalize path (convert to absolute path).
///
/// # Arguments
/// * `path` - Path to normalize
///
/// # Returns
/// Normalized path as PathBuf
pub fn normalize_path<P: AsRef<Path>>(path: P) -> PathBuf {
    fs::canonicalize(path.as_ref()).unwrap_or_else(|_| path.as_ref().to_path_buf())
}

/// Get parent directory of path.
///
/// # Arguments
/// * `path` - Path to get parent of
///
/// # Returns
/// * `Some(PathBuf)` - Parent directory
/// * `None` - No parent (root path)
pub fn get_parent_directory<P: AsRef<Path>>(path: P) -> Option<PathBuf> {
    path.as_ref().parent().map(|p| p.to_path_buf())
}

/// Get file name from path.
///
/// # Arguments
/// * `path` - Path to get file name from
///
/// # Returns
/// * `Some(String)` - File name
/// * `None` - No file name
pub fn get_file_name<P: AsRef<Path>>(path: P) -> Option<String> {
    path.as_ref()
        .file_name()
        .map(|name| name.to_string_lossy().to_string())
}

/// Check if path is absolute.
///
/// # Arguments
/// * `path` - Path to check
///
/// # Returns
/// * `true` if path is absolute, `false` otherwise
pub fn is_absolute_path<P: AsRef<Path>>(path: P) -> bool {
    path.as_ref().is_absolute()
}

/// Check if current platform is macOS.
///
/// # Returns
/// * `true` if macOS, `false` otherwise
pub fn is_macos() -> bool {
    cfg!(target_os = "macos")
}

/// Check if current platform is Windows.
///
/// # Returns
/// * `true` if Windows, `false` otherwise
pub fn is_windows() -> bool {
    cfg!(target_os = "windows")
}

/// Check if current platform is Linux.
///
/// # Returns
/// * `true` if Linux, `false` otherwise
pub fn is_linux() -> bool {
    cfg!(target_os = "linux")
}

/// Get home directory for current platform.
///
/// # Returns
/// * `Some(PathBuf)` - Home directory path
/// * `None` - Home directory not found
pub fn get_home_directory() -> Option<PathBuf> {
    env::var("HOME")
        .or_else(|_| env::var("USERPROFILE"))
        .ok()
        .map(PathBuf::from)
}

/// Truncate string with ellipsis.
///
/// # Arguments
/// * `text` - Text to truncate
/// * `max_length` - Maximum length (including ellipsis)
///
/// # Returns
/// Truncated string with ellipsis if needed
pub fn truncate_string(text: &str, max_length: usize) -> String {
    if text.len() <= max_length {
        text.to_string()
    } else {
        format!("{}...", &text[..max_length.saturating_sub(3)])
    }
}

/// Sanitize filename by removing invalid characters.
///
/// # Arguments
/// * `filename` - Filename to sanitize
///
/// # Returns
/// Sanitized filename
pub fn sanitize_filename(filename: &str) -> String {
    filename
        .chars()
        .map(|c| match c {
            '<' | '>' | ':' | '"' | '/' | '\\' | '|' | '?' | '*' => '_',
            _ => c,
        })
        .collect()
}

/// Generate unique ID (simple UUID v4-like).
///
/// # Returns
/// Unique ID string
pub fn generate_unique_id() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    format!("{:x}", timestamp)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_join_paths() {
        let result = join_paths(&["home", "user", "documents"]);
        assert!(result.to_string_lossy().contains("documents"));
    }

    #[test]
    fn test_get_file_extension() {
        assert_eq!(get_file_extension("test.txt"), Some("txt".to_string()));
        assert_eq!(get_file_extension("test"), None);
        assert_eq!(get_file_extension(".hidden"), None);
    }

    #[test]
    fn test_get_parent_directory() {
        let parent = get_parent_directory("/home/user/file.txt");
        assert!(parent.is_some());
        assert!(parent.unwrap().to_string_lossy().contains("user"));
    }

    #[test]
    fn test_get_file_name() {
        assert_eq!(get_file_name("/path/to/file.txt"), Some("file.txt".to_string()));
        assert_eq!(get_file_name("/path/to/"), None);
    }

    #[test]
    fn test_is_absolute_path() {
        assert!(is_absolute_path("/home/user"));
        assert!(!is_absolute_path("relative/path"));
    }

    #[test]
    fn test_truncate_string() {
        assert_eq!(truncate_string("short", 10), "short");
        assert_eq!(truncate_string("very long text", 10), "very lo...");
    }

    #[test]
    fn test_sanitize_filename() {
        assert_eq!(sanitize_filename("file<name>.txt"), "file_name_.txt");
        assert_eq!(sanitize_filename("normal.txt"), "normal.txt");
    }

    #[test]
    fn test_generate_unique_id() {
        let id1 = generate_unique_id();
        let id2 = generate_unique_id();
        assert_ne!(id1, id2);
    }
}
