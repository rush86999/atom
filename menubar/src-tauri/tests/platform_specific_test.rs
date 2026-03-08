//! Tests for platform-specific utilities.
//!
//! Tests cover:
//! - macOS-specific utilities (app support path, version, notifications)
//! - Windows-specific utilities (app data path, temp path, version)
//! - Linux-specific utilities (config path, data path, desktop environment)
//! - Cross-platform compatibility (cache, logs, open URL, show in folder)

#[cfg(test)]
mod tests {
    // Note: These tests are written to be run with: cargo test --test platform_specific_test
    // The platform-specific functions are in src/platform_specific.rs

    #[cfg(target_os = "macos")]
    #[test]
    fn test_get_macos_app_support_path() {
        let path = platform_specific::get_macos_app_support_path("Atom");
        assert!(path.to_string_lossy().contains("Library"));
        assert!(path.to_string_lossy().contains("Application Support"));
        assert!(path.to_string_lossy().contains("Atom"));
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn test_macos_paths_exist() {
        // Verify that macOS paths are absolute
        let app_support = platform_specific::get_macos_app_support_path("Atom");
        assert!(app_support.is_absolute());

        // Verify HOME directory is used
        assert!(app_support.to_string_lossy().starts_with('/'));
    }

    #[cfg(target_os = "windows")]
    #[test]
    fn test_get_windows_app_data_path() {
        let path = platform_specific::get_windows_app_data_path("Atom");
        assert!(path.to_string_lossy().contains("Atom"));
        assert!(path.is_absolute());

        // Verify APPDATA is used
        #[cfg(target_os = "windows")]
        assert!(path.to_string_lossy().contains("AppData") || path.to_string_lossy().starts_with("C:\\"));
    }

    #[cfg(target_os = "windows")]
    #[test]
    fn test_get_windows_temp_path() {
        let path = platform_specific::get_windows_temp_path();
        assert!(!path.to_string_lossy().is_empty());
        assert!(path.is_absolute());
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn test_get_linux_config_path() {
        let path = platform_specific::get_linux_config_path("atom");
        assert!(path.to_string_lossy().contains(".config"));
        assert!(path.to_string_lossy().contains("atom"));
        assert!(path.is_absolute());
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn test_get_linux_data_path() {
        let path = platform_specific::get_linux_data_path("atom");
        assert!(path.to_string_lossy().contains(".local"));
        assert!(path.to_string_lossy().contains("share"));
        assert!(path.to_string_lossy().contains("atom"));
        assert!(path.is_absolute());
    }

    #[test]
    fn test_get_cache_path() {
        let path = platform_specific::get_cache_path("Atom");
        assert!(!path.to_string_lossy().is_empty());
        assert!(path.is_absolute());

        // Platform-specific checks
        #[cfg(target_os = "macos")]
        assert!(path.to_string_lossy().contains("Caches"));

        #[cfg(target_os = "windows")]
        assert!(path.to_string_lossy().contains("Cache"));

        #[cfg(target_os = "linux")]
        assert!(path.to_string_lossy().contains(".cache"));
    }

    #[test]
    fn test_get_log_path() {
        let path = platform_specific::get_log_path("Atom");
        assert!(!path.to_string_lossy().is_empty());
        assert!(path.is_absolute());

        // Platform-specific checks
        #[cfg(target_os = "macos")]
        assert!(path.to_string_lossy().contains("Logs"));

        #[cfg(target_os = "windows")]
        assert!(path.to_string_lossy().contains("Logs"));

        #[cfg(target_os = "linux")]
        assert!(path.to_string_lossy().contains("state"));
    }

    #[test]
    fn test_cross_platform_compatibility() {
        // Test that functions return absolute paths
        let cache = platform_specific::get_cache_path("TestApp");
        let logs = platform_specific::get_log_path("TestApp");

        assert!(cache.is_absolute());
        assert!(logs.is_absolute());

        // Test that app name is included in path
        assert!(cache.to_string_lossy().contains("TestApp"));
        assert!(logs.to_string_lossy().contains("TestApp"));
    }

    #[test]
    fn test_edge_cases() {
        // Test with empty app name
        let cache = platform_specific::get_cache_path("");
        assert!(cache.is_absolute());

        // Test with special characters in app name
        let cache = platform_specific::get_cache_path("Test App (2024)");
        assert!(cache.is_absolute());
    }

    #[test]
    fn test_open_url() {
        // Note: This test may fail in CI environments without a display
        // We're just checking that the function doesn't crash
        let result = platform_specific::open_url("https://example.com");

        // Result depends on whether we have a display/browser
        // Just verify it returns Result type
        match result {
            Ok(()) => {}, // Success
            Err(e) => {
                // Expected in headless environments
                assert!(e.kind() == std::io::ErrorKind::NotFound ||
                       e.kind() == std::io::ErrorKind::PermissionDenied);
            }
        }
    }

    #[test]
    fn test_show_in_folder() {
        use std::path::PathBuf;

        // Note: This test may fail in CI environments without a file manager
        // We're just checking that the function doesn't crash
        let test_path = PathBuf::from("/tmp/test_file.txt");
        let result = platform_specific::show_in_folder(&test_path);

        // Result depends on whether we have a file manager
        // Just verify it returns Result type
        match result {
            Ok(()) => {}, // Success
            Err(e) => {
                // Expected in headless environments
                assert!(e.kind() == std::io::ErrorKind::NotFound ||
                       e.kind() == std::io::ErrorKind::PermissionDenied);
            }
        }
    }

    #[test]
    fn test_platform_detection() {
        // Test that platform-specific functions are compiled correctly
        #[cfg(target_os = "macos")]
        {
            let _ = platform_specific::get_macos_app_support_path("Test");
        }

        #[cfg(target_os = "windows")]
        {
            let _ = platform_specific::get_windows_app_data_path("Test");
            let _ = platform_specific::get_windows_temp_path();
        }

        #[cfg(target_os = "linux")]
        {
            let _ = platform_specific::get_linux_config_path("test");
            let _ = platform_specific::get_linux_data_path("test");
        }
    }

    #[test]
    fn test_path_separators() {
        // Test that paths use correct separators for platform
        let cache = platform_specific::get_cache_path("Test");
        let path_str = cache.to_string_lossy();

        #[cfg(target_os = "windows")]
        assert!(path_str.contains("\\"));

        #[cfg(any(target_os = "macos", target_os = "linux"))]
        assert!(path_str.contains("/"));
    }

    #[test]
    fn test_unicode_app_names() {
        // Test with Unicode app names
        let cache = platform_specific::get_cache_path("应用");
        assert!(cache.is_absolute());
        assert!(cache.to_string_lossy().contains("应用"));
    }

    #[test]
    fn test_relative_vs_absolute_paths() {
        // All platform-specific paths should be absolute
        let cache = platform_specific::get_cache_path("Test");
        let logs = platform_specific::get_log_path("Test");

        #[cfg(target_os = "macos")]
        {
            let app_support = platform_specific::get_macos_app_support_path("Test");
            assert!(app_support.is_absolute());
        }

        #[cfg(target_os = "windows")]
        {
            let app_data = platform_specific::get_windows_app_data_path("Test");
            let temp = platform_specific::get_windows_temp_path();
            assert!(app_data.is_absolute());
            assert!(temp.is_absolute());
        }

        #[cfg(target_os = "linux")]
        {
            let config = platform_specific::get_linux_config_path("test");
            let data = platform_specific::get_linux_data_path("test");
            assert!(config.is_absolute());
            assert!(data.is_absolute());
        }

        assert!(cache.is_absolute());
        assert!(logs.is_absolute());
    }

    #[test]
    fn test_path_uniqueness() {
        // Test that different app names produce different paths
        let cache1 = platform_specific::get_cache_path("App1");
        let cache2 = platform_specific::get_cache_path("App2");

        assert_ne!(cache1, cache2);

        // Test that same app name produces same path
        let cache1a = platform_specific::get_cache_path("App1");
        assert_eq!(cache1, cache1a);
    }
}
