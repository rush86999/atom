//! Platform-specific utilities for macOS, Windows, and Linux.
//!
//! This module provides platform-specific path resolution and system integration.

use std::path::PathBuf;

/// Get macOS Application Support directory.
///
/// # Arguments
/// * `app_name` - Name of the application
///
/// # Returns
/// Application Support path
#[cfg(target_os = "macos")]
pub fn get_macos_app_support_path(app_name: &str) -> PathBuf {
    let mut path = PathBuf::from(std::env::var("HOME").unwrap_or_else(|_| ".".to_string()));
    path.push("Library");
    path.push("Application Support");
    path.push(app_name);
    path
}

/// Get Windows AppData (Roaming) directory.
///
/// # Arguments
/// * `app_name` - Name of the application
///
/// # Returns
/// AppData path
#[cfg(target_os = "windows")]
pub fn get_windows_app_data_path(app_name: &str) -> PathBuf {
    let mut path = PathBuf::from(std::env::var("APPDATA").unwrap_or_else(|_| ".".to_string()));
    path.push(app_name);
    path
}

/// Get Windows temp directory.
///
/// # Returns
/// Temp directory path
#[cfg(target_os = "windows")]
pub fn get_windows_temp_path() -> PathBuf {
    PathBuf::from(std::env::var("TEMP").unwrap_or_else(|_| ".".to_string()))
}

/// Get Linux config directory.
///
/// # Arguments
/// * `app_name` - Name of the application (lowercase)
///
/// # Returns
/// Config path (~/.config/app_name)
#[cfg(target_os = "linux")]
pub fn get_linux_config_path(app_name: &str) -> PathBuf {
    let mut path = PathBuf::from(std::env::var("HOME").unwrap_or_else(|_| ".".to_string()));
    path.push(".config");
    path.push(app_name);
    path
}

/// Get Linux data directory.
///
/// # Arguments
/// * `app_name` - Name of the application (lowercase)
///
/// # Returns
/// Data path (~/.local/share/app_name)
#[cfg(target_os = "linux")]
pub fn get_linux_data_path(app_name: &str) -> PathBuf {
    let mut path = PathBuf::from(std::env::var("HOME").unwrap_or_else(|_| ".".to_string()));
    path.push(".local");
    path.push("share");
    path.push(app_name);
    path
}

/// Get cache directory for current platform.
///
/// # Arguments
/// * `app_name` - Name of the application
///
/// # Returns
/// Cache directory path
pub fn get_cache_path(app_name: &str) -> PathBuf {
    #[cfg(target_os = "macos")]
    {
        let mut path = PathBuf::from(std::env::var("HOME").unwrap_or_else(|_| ".".to_string()));
        path.push("Library");
        path.push("Caches");
        path.push(app_name);
        path
    }

    #[cfg(target_os = "windows")]
    {
        let mut path = PathBuf::from(std::env::var("LOCALAPPDATA").unwrap_or_else(|_| ".".to_string()));
        path.push(app_name);
        path.push("Cache");
        path
    }

    #[cfg(target_os = "linux")]
    {
        let mut path = PathBuf::from(std::env::var("HOME").unwrap_or_else(|_| ".".to_string()));
        path.push(".cache");
        path.push(app_name);
        path
    }
}

/// Get log directory for current platform.
///
/// # Arguments
/// * `app_name` - Name of the application
///
/// # Returns
/// Log directory path
pub fn get_log_path(app_name: &str) -> PathBuf {
    #[cfg(target_os = "macos")]
    {
        let mut path = PathBuf::from(std::env::var("HOME").unwrap_or_else(|_| ".".to_string()));
        path.push("Library");
        path.push("Logs");
        path.push(app_name);
        path
    }

    #[cfg(target_os = "windows")]
    {
        let mut path = PathBuf::from(std::env::var("LOCALAPPDATA").unwrap_or_else(|_| ".".to_string()));
        path.push(app_name);
        path.push("Logs");
        path
    }

    #[cfg(target_os = "linux")]
    {
        let mut path = PathBuf::from(std::env::var("HOME").unwrap_or_else(|_| ".".to_string()));
        path.push(".local");
        path.push("state");
        path.push(app_name);
        path
    }
}

/// Open URL in default browser (platform-specific).
///
/// # Arguments
/// * `url` - URL to open
///
/// # Returns
/// * `Ok(())` - Success
/// * `Err(io::Error)` - Failed to open URL
pub fn open_url(url: &str) -> Result<(), std::io::Error> {
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg(url)
            .spawn()?;
    }

    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("cmd")
            .args(&["/C", "start", "", url])
            .spawn()?;
    }

    #[cfg(target_os = "linux")]
    {
        std::process::Command::new("xdg-open")
            .arg(url)
            .spawn()?;
    }

    Ok(())
}

/// Show file in file manager (platform-specific).
///
/// # Arguments
/// * `path` - Path to file/folder
///
/// # Returns
/// * `Ok(())` - Success
/// * `Err(io::Error)` - Failed to show in file manager
pub fn show_in_folder(path: &PathBuf) -> Result<(), std::io::Error> {
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg("-R")
            .arg(path)
            .spawn()?;
    }

    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("explorer")
            .arg("/select,")
            .arg(path)
            .spawn()?;
    }

    #[cfg(target_os = "linux")]
    {
        std::process::Command::new("dbus-send")
            .args(&[
                "--session",
                "--dest=org.freedesktop.FileManager1",
                "--type=method_call",
                "/org/freedesktop/FileManager1",
                "org.freedesktop.FileManager1.ShowItems",
                format!("array:string:file://{}", path.to_string_lossy()).as_str(),
            ])
            .spawn()?;
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[cfg(target_os = "macos")]
    #[test]
    fn test_get_macos_app_support_path() {
        let path = get_macos_app_support_path("Atom");
        assert!(path.to_string_lossy().contains("Library"));
        assert!(path.to_string_lossy().contains("Application Support"));
        assert!(path.to_string_lossy().contains("Atom"));
    }

    #[cfg(target_os = "windows")]
    #[test]
    fn test_get_windows_app_data_path() {
        let path = get_windows_app_data_path("Atom");
        assert!(path.to_string_lossy().contains("Atom"));
    }

    #[cfg(target_os = "windows")]
    #[test]
    fn test_get_windows_temp_path() {
        let path = get_windows_temp_path();
        assert!(!path.to_string_lossy().is_empty());
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn test_get_linux_config_path() {
        let path = get_linux_config_path("atom");
        assert!(path.to_string_lossy().contains(".config"));
        assert!(path.to_string_lossy().contains("atom"));
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn test_get_linux_data_path() {
        let path = get_linux_data_path("atom");
        assert!(path.to_string_lossy().contains(".local"));
        assert!(path.to_string_lossy().contains("share"));
    }

    #[test]
    fn test_get_cache_path() {
        let path = get_cache_path("Atom");
        assert!(!path.to_string_lossy().is_empty());
        // Path content depends on platform
    }

    #[test]
    fn test_get_log_path() {
        let path = get_log_path("Atom");
        assert!(!path.to_string_lossy().is_empty());
        // Path content depends on platform
    }
}
