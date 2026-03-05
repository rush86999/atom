//! Platform-specific test module organization for desktop (Windows/macOS/Linux)
//!
//! This module organizes tests by target platform using Rust's conditional compilation
//! features. Platform-specific tests are compiled only on their target platforms, while
//! cross-platform tests run on all platforms.
//!
//! # Module Organization
//!
//! - **windows**: Windows-specific tests (file dialogs, taskbar, Windows Hello)
//! - **macos**: macOS-specific tests (menu bar, dock, Spotlight, Touch ID)
//! - **linux**: Linux-specific tests (window managers, desktop environments, file pickers)
//! - **cross_platform**: Tests that run on all platforms (path handling, temp directories)
//! - **conditional_compilation**: Tests for cfg! macro and #[cfg] attribute patterns
//!
//! # Conditional Compilation Pattern
//!
//! Platform-specific modules use `#[cfg(target_os = "...")]` attributes:
//!
//! ```rust
//! #[cfg(target_os = "windows")]
//! pub mod windows;
//!
//! #[cfg(target_os = "macos")]
//! pub mod macos;
//!
//! #[cfg(target_os = "linux")]
//! pub mod linux;
//! ```
//!
//! This pattern ensures that:
//! - Platform-specific code is only compiled on the target platform
//! - Tests only run on platforms where they are relevant
//! - No runtime platform detection overhead
//! - Clean test output (no "skipped" messages for unsupported platforms)
//!
//! # Cross-Platform Tests
//!
//! Cross-platform tests use `cfg!` macro for runtime platform checks:
//!
//! ```rust
//! let os = if cfg!(target_os = "windows") {
//!     "windows"
//! } else if cfg!(target_os = "macos") {
//!     "macos"
//! } else if cfg!(target_os = "linux") {
//!     "linux"
//! } else {
//!     "unknown"
//! };
//! ```
//!
//! This allows single test files to verify platform-specific logic across all platforms.
//!
//! # Pattern Reference (Phase 139 Mobile)
//!
//! This structure mirrors the mobile platform-specific testing infrastructure from Phase 139:
//! - `mobile/src/__tests__/platform-specific/ios/` → `tests/platform_specific/windows/`
//! - `mobile/src/__tests__/platform-specific/android/` → `tests/platform_specific/macos/`
//! - `mobile/src/__tests__/platform-specific/conditionalRendering.test.tsx` → `tests/platform_specific/conditional_compilation.rs`
//!
//! # Usage
//!
//! ```rust
//! use crate::platform_specific::*;
//!
//! // Cross-platform tests run everywhere
//! #[test]
//! fn test_path_handling() {
//!     // Test implementation
//! }
//!
//! // Platform-specific tests run only on target platform
//! #[cfg(target_os = "windows")]
//! #[test]
//! fn test_windows_file_dialog() {
//!     // Test implementation
//! }
//! ```
//!
//! # Module Visibility
//!
//! IMPORTANT: Do NOT use `cfg!` macro for module visibility. Use `#[cfg]` attributes
//! on module declarations themselves. This ensures platform-specific modules are not
//! compiled on unsupported platforms.
//!
//! ```rust
//! // CORRECT: Use #[cfg] attribute on module declaration
//! #[cfg(target_os = "windows")]
//! pub mod windows;
//!
//! // INCORRECT: Do NOT use cfg! for module visibility
//! // if cfg!(target_os = "windows") {
//! //     pub mod windows;
//! // }
//! ```

// Platform-specific test modules (only compiled on target platforms)
#[cfg(target_os = "windows")]
pub mod windows;

#[cfg(target_os = "macos")]
pub mod macos;

#[cfg(target_os = "linux")]
pub mod linux;

// Cross-platform test modules (compiled and run on all platforms)
pub mod cross_platform;

// Conditional compilation tests (verify cfg! macro and #[cfg] patterns)
pub mod conditional_compilation;

// Re-exports for common types used across platform-specific tests
pub use cross_platform::*;
