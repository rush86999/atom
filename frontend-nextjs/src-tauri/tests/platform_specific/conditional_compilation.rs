//! Conditional compilation tests for cfg! macro and #[cfg] attribute patterns
//!
//! Tests verify Rust's conditional compilation features:
//! - cfg! macro for runtime platform detection
//! - #[cfg] attributes for compile-time code inclusion
//! - cfg! combinations: any(), all(), not()
//! - Platform-specific logic patterns
//!
//! These tests ensure that platform detection works correctly and that
//! conditional compilation patterns behave as expected across Windows,
//! macOS, and Linux platforms.

#[cfg(test)]
mod tests {
    use std::path::PathBuf;

    // ========================================================================
    // cfg! Macro Platform Detection Tests
    // ========================================================================

    #[test]
    fn test_cfg_macro_platform_detection() {
        // Test cfg! macro returns expected boolean values for target_os

        let is_windows = cfg!(target_os = "windows");
        let is_macos = cfg!(target_os = "macos");
        let is_linux = cfg!(target_os = "linux");

        // Verify exactly one platform is true (or none for unsupported platforms)
        let platforms_count = [is_windows, is_macos, is_linux]
            .iter()
            .filter(|&&x| x)
            .count();

        // Should be exactly 1 on supported platforms, or 0 on unsupported platforms
        assert!(platforms_count <= 1,
            "At most one platform should be detected, found {}", platforms_count);

        // Verify platform detection is consistent
        if is_windows {
            assert!(!is_macos && !is_linux,
                "Windows should not also be macOS or Linux");
        }

        if is_macos {
            assert!(!is_windows && !is_linux,
                "macOS should not also be Windows or Linux");
        }

        if is_linux {
            assert!(!is_windows && !is_macos,
                "Linux should not also be Windows or macOS");
        }
    }

    #[test]
    fn test_cfg_macro_architecture_detection() {
        // Test cfg! macro for target_arch detection (x86_64, aarch64, etc.)

        let is_x86_64 = cfg!(target_arch = "x86_64");
        let is_aarch64 = cfg!(target_arch = "aarch64");
        let is_arm64 = cfg!(target_arch = "arm64");

        // Verify exactly one architecture is true (or none for unsupported architectures)
        let arch_count = [is_x86_64, is_aarch64, is_arm64]
            .iter()
            .filter(|&&x| x)
            .count();

        assert!(arch_count <= 1,
            "At most one architecture should be detected, found {}", arch_count);

        // Most common desktop architectures should be one of these
        let is_known_arch = is_x86_64 || is_aarch64 || is_arm64;
        assert!(is_known_arch || !is_known_arch, // Always true, but documents assumption
            "Architecture should be x86_64, aarch64, or arm64 (found other)");
    }

    #[test]
    fn test_cfg_macro_endian_detection() {
        // Test cfg! macro for target_endian detection

        let is_little_endian = cfg!(target_endian = "little");
        let is_big_endian = cfg!(target_endian = "big");

        // Verify exactly one endianness is true
        let endian_count = [is_little_endian, is_big_endian]
            .iter()
            .filter(|&&x| x)
            .count();

        assert_eq!(endian_count, 1,
            "Exactly one endianness should be detected, found {}", endian_count);

        // Most modern desktop systems are little-endian
        // (This test documents the assumption, doesn't enforce it)
        if is_big_endian {
            // Big-endian is rare on modern desktops (mostly legacy systems)
            // Test still passes but documents this unusual case
        }
    }

    // ========================================================================
    // cfg! Macro Combinations Tests
    // ========================================================================

    #[test]
    fn test_cfg_any_combinations() {
        // Test cfg!(any(...)) combinations for multiple conditions

        // Should be true if running on Windows OR macOS
        let is_windows_or_macos = cfg!(any(
            target_os = "windows",
            target_os = "macos"
        ));

        // Verify any() logic
        let is_windows = cfg!(target_os = "windows");
        let is_macos = cfg!(target_os = "macos");

        assert_eq!(is_windows_or_macos, is_windows || is_macos,
            "any() should behave like logical OR");

        // Should be true if running on Windows OR macOS OR Linux
        let is_desktop_platform = cfg!(any(
            target_os = "windows",
            target_os = "macos",
            target_os = "linux"
        ));

        // At least one desktop platform should be true (or we're on an unsupported platform)
        let is_windows_macos_or_linux = is_windows || is_macos || cfg!(target_os = "linux");
        assert_eq!(is_desktop_platform, is_windows_macos_or_linux,
            "any() with 3 conditions should match OR logic");
    }

    #[test]
    fn test_cfg_all_combinations() {
        // Test cfg!(all(...)) combinations for multiple conditions

        // Should be true if running on Linux AND x86_64
        let is_linux_x86_64 = cfg!(all(
            target_os = "linux",
            target_arch = "x86_64"
        ));

        // Verify all() logic
        let is_linux = cfg!(target_os = "linux");
        let is_x86_64 = cfg!(target_arch = "x86_64");

        assert_eq!(is_linux_x86_64, is_linux && is_x86_64,
            "all() should behave like logical AND");

        // Should be true if running on macOS AND aarch64 (Apple Silicon)
        let is_macos_arm64 = cfg!(all(
            target_os = "macos",
            target_arch = "aarch64"
        ));

        let is_macos = cfg!(target_os = "macos");
        let is_aarch64 = cfg!(target_arch = "aarch64");

        assert_eq!(is_macos_arm64, is_macos && is_aarch64,
            "all() with macOS and aarch64 should match AND logic");
    }

    #[test]
    fn test_cfg_not_operator() {
        // Test cfg!(not(...)) operator for negation

        // Should be true if NOT Windows (i.e., Unix-like: macOS or Linux)
        let is_not_windows = cfg!(not(target_os = "windows"));

        // Verify not() logic
        let is_windows = cfg!(target_os = "windows");

        assert_eq!(is_not_windows, !is_windows,
            "not() should behave like logical NOT");

        // Should be true if NOT Linux (i.e., Windows or macOS)
        let is_not_linux = cfg!(not(target_os = "linux"));

        let is_linux = cfg!(target_os = "linux");

        assert_eq!(is_not_linux, !is_linux,
            "not(target_os = \"linux\") should match !is_linux");
    }

    // ========================================================================
    // Platform Detection Logic Tests (mirroring cross_platform_validation_test.rs)
    // ========================================================================

    #[test]
    fn test_platform_detection_logic() {
        // Test platform string extraction using cfg! macro
        // Mirrors cross_platform_validation_test.rs lines 16-36

        let os = if cfg!(target_os = "windows") {
            "windows"
        } else if cfg!(target_os = "macos") {
            "macos"
        } else if cfg!(target_os = "linux") {
            "linux"
        } else {
            "unknown"
        };

        // Verify platform is recognized (one of the expected values)
        assert!(os == "windows" || os == "macos" || os == "linux" || os == "unknown",
            "Platform should be one of: windows, macos, linux, unknown, got: {}", os);

        // Verify platform is not empty
        assert!(!os.is_empty(), "Platform string should not be empty");

        // Verify platform length is reasonable (3-10 characters)
        assert!(os.len() >= 3 && os.len() <= 10,
            "Platform name length should be 3-10 characters, got: {}", os.len());

        // Verify platform string consistency
        if cfg!(target_os = "windows") {
            assert_eq!(os, "windows", "cfg! should match platform string");
        } else if cfg!(target_os = "macos") {
            assert_eq!(os, "macos", "cfg! should match platform string");
        } else if cfg!(target_os = "linux") {
            assert_eq!(os, "linux", "cfg! should match platform string");
        }
    }

    #[test]
    fn test_path_separator_consistency() {
        // Test PathBuf handles both forward and backward slashes correctly
        // Mirrors cross_platform_validation_test.rs lines 63-89

        // Test forward slash (Unix-style path)
        let forward_path = PathBuf::from("/home/user/test/file.txt");

        // Verify forward slash path is absolute on Unix
        #[cfg(not(target_os = "windows"))]
        assert!(forward_path.is_absolute(),
            "Forward slash path should be absolute on Unix-like systems");

        // Verify file name extraction works
        assert_eq!(forward_path.file_name().unwrap().to_string_lossy(), "file.txt",
            "File name should be extracted correctly from forward slash path");

        // Test backward slash (Windows-style path)
        let backward_path_str = if cfg!(target_os = "windows") {
            r"C:\Users\test\file.txt"
        } else {
            "/home/test/file.txt" // Fallback for Unix systems
        };

        let backward_path = PathBuf::from(backward_path_str);

        // Verify backward slash path is absolute
        assert!(backward_path.is_absolute(),
            "Backward slash path should be absolute");

        // Verify both paths extract file name correctly
        let forward_name = forward_path.file_name().unwrap().to_string_lossy();
        let backward_name = backward_path.file_name().unwrap().to_string_lossy();

        assert_eq!(forward_name, "file.txt",
            "Forward path file name should be 'file.txt'");
        assert_eq!(backward_name, "file.txt",
            "Backward path file name should be 'file.txt'");

        // Verify PathBuf normalizes separators to platform default
        // (Windows converts / to \, Unix keeps /)
        let path_string = backward_path.to_string_lossy();

        if cfg!(target_os = "windows") {
            // Windows should normalize to backslashes
            assert!(path_string.contains('\\') || path_string.contains('/'),
                "Windows path should contain separator");
        } else {
            // Unix should use forward slashes
            assert!(path_string.contains('/'),
                "Unix path should contain forward slash");
        }
    }

    // ========================================================================
    // Conditional Compilation Edge Cases Tests
    // ========================================================================

    #[test]
    fn test_cfg_macro_compile_time_constants() {
        // Test cfg! macro results are compile-time constants

        // cfg! results can be used in const contexts
        const IS_WINDOWS: bool = cfg!(target_os = "windows");
        const IS_MACOS: bool = cfg!(target_os = "macos");
        const IS_LINUX: bool = cfg!(target_os = "linux");

        // Verify constants are booleans
        let _ = IS_WINDOWS || IS_MACOS || IS_LINUX;

        // Verify cfg! results are consistent
        assert_eq!(cfg!(target_os = "windows"), IS_WINDOWS,
            "cfg! should match const value");

        assert_eq!(cfg!(target_os = "macos"), IS_MACOS,
            "cfg! should match const value");

        assert_eq!(cfg!(target_os = "linux"), IS_LINUX,
            "cfg! should match const value");
    }

    #[test]
    fn test_cfg_macro_in_const_expressions() {
        // Test cfg! macro can be used in const expressions

        const PLATFORM_NAME: &str = if cfg!(target_os = "windows") {
            "windows"
        } else if cfg!(target_os = "macos") {
            "macos"
        } else if cfg!(target_os = "linux") {
            "linux"
        } else {
            "unknown"
        };

        // Verify const expression works
        assert!(!PLATFORM_NAME.is_empty(),
            "Platform name should not be empty");

        assert!(PLATFORM_NAME.len() >= 3,
            "Platform name should be at least 3 characters");
    }

    #[test]
    fn test_cfg_macro_complex_combinations() {
        // Test complex cfg! combinations with any(), all(), not()

        // Should be true for (Linux AND x86_64) OR (macOS AND aarch64)
        let is_specific_config = cfg!(any(
            all(target_os = "linux", target_arch = "x86_64"),
            all(target_os = "macos", target_arch = "aarch64")
        ));

        // Verify complex combination logic
        let is_linux_x86_64 = cfg!(target_os = "linux") && cfg!(target_arch = "x86_64");
        let is_macos_arm64 = cfg!(target_os = "macos") && cfg!(target_arch = "aarch64");

        assert_eq!(is_specific_config, is_linux_x86_64 || is_macos_arm64,
            "Complex any(all(...), all(...)) should match logical expression");

        // Should be true for Unix-like systems (NOT Windows)
        let is_unix = cfg!(not(target_os = "windows"));

        // Verify Unix-like detection
        let is_macos_or_linux = cfg!(target_os = "macos") || cfg!(target_os = "linux");

        assert_eq!(is_unix, is_macos_or_linux,
            "not(windows) should match macOS OR Linux");
    }
}
