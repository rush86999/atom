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
/// * `None` - No extension (including a trailing dot, e.g. `"test."`)
pub fn get_file_extension<P: AsRef<Path>>(path: P) -> Option<String> {
    path.as_ref()
        .extension()
        // `Path::extension` yields `Some("")` for a name that ends in a dot;
        // an empty extension is not an extension.
        .filter(|ext| !ext.is_empty())
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
/// * `None` - No file name (empty path, root, or a path with a trailing
///   separator such as `"/path/to/"`, which names a directory)
pub fn get_file_name<P: AsRef<Path>>(path: P) -> Option<String> {
    let path = path.as_ref();
    let raw = path.as_os_str().to_string_lossy();
    if raw.is_empty() || raw.chars().last().map(std::path::is_separator).unwrap_or(false) {
        return None;
    }
    path.file_name()
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
/// Lengths are measured in bytes (UTF-8), matching `str::len`. Truncation
/// never splits a multi-byte character; the cut is moved back to the nearest
/// character boundary.
///
/// # Arguments
/// * `text` - Text to truncate
/// * `max_length` - Maximum length (including ellipsis)
///
/// # Returns
/// Truncated string with ellipsis if needed. When `max_length` is smaller
/// than the ellipsis, the result is just `.` repeated `max_length` times so
/// the documented maximum is never exceeded.
pub fn truncate_string(text: &str, max_length: usize) -> String {
    if text.len() <= max_length {
        return text.to_string();
    }
    if max_length <= 3 {
        return ".".repeat(max_length);
    }
    let mut end = max_length - 3;
    while end > 0 && !text.is_char_boundary(end) {
        end -= 1;
    }
    format!("{}...", &text[..end])
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
/// Uniqueness is guaranteed within a process by a monotonic counter and
/// widened across processes by the process id; the wall-clock timestamp keeps
/// the values spread over time. The result is a lowercase hex string, so it is
/// safe for filenames, DOM ids, and IPC payload keys.
///
/// # Returns
/// Unique hex ID string
pub fn generate_unique_id() -> String {
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::time::{SystemTime, UNIX_EPOCH};

    static COUNTER: AtomicU64 = AtomicU64::new(0);

    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_nanos())
        .unwrap_or(0);
    let pid = u64::from(std::process::id());
    let counter = COUNTER.fetch_add(1, Ordering::Relaxed);

    format!("{:032x}{:08x}{:016x}", timestamp, pid, counter)
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
        assert_eq!(get_file_extension("test."), None);
        assert_eq!(get_file_extension(".hidden"), None);
        assert_eq!(get_file_extension("archive.tar.gz"), Some("gz".to_string()));
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
        assert_eq!(get_file_name("file.txt"), Some("file.txt".to_string()));
        assert_eq!(get_file_name("/path/to/"), None);
        assert_eq!(get_file_name("/"), None);
        assert_eq!(get_file_name(""), None);
    }

    #[test]
    fn test_is_absolute_path() {
        assert!(is_absolute_path("/home/user"));
        assert!(!is_absolute_path("relative/path"));
    }

    #[test]
    fn test_truncate_string() {
        assert_eq!(truncate_string("short", 10), "short");
        assert_eq!(truncate_string("exact", 5), "exact");
        assert_eq!(truncate_string("very long text", 10), "very lo...");
        assert_eq!(truncate_string("text", 2), "..");
        // Multi-byte characters must not be split (this used to panic).
        // 10-byte budget leaves 7 for text; 7 falls inside '世' (bytes 6..9),
        // so the cut moves back to the previous boundary at byte 6.
        let unicode = truncate_string("Hello 世界 🌍", 10);
        assert_eq!(unicode, "Hello ...");
        assert!(unicode.len() <= 13);
        assert!(unicode.is_char_boundary(unicode.len()));
    }

    #[test]
    fn test_sanitize_filename() {
        assert_eq!(sanitize_filename("file<name>.txt"), "file_name_.txt");
        assert_eq!(sanitize_filename("normal.txt"), "normal.txt");
        assert_eq!(sanitize_filename("文件.txt"), "文件.txt");
    }

    #[test]
    fn test_generate_unique_id() {
        let ids: Vec<String> = (0..1_000).map(|_| generate_unique_id()).collect();
        for id in &ids {
            assert!(!id.is_empty());
            assert!(id.chars().all(|c| c.is_ascii_hexdigit()));
        }
        let mut unique = ids.clone();
        unique.sort();
        unique.dedup();
        assert_eq!(unique.len(), ids.len());
    }
}
