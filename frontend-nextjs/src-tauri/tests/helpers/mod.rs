//! Test helper utilities for desktop testing
//!
//! This module provides helper functions and utilities for testing
//! desktop-specific functionality across Windows, macOS, and Linux platforms.
//!
//! # Modules
//!
//! - **platform_helpers**: Platform detection and assertion utilities

pub mod platform_helpers;

// Re-exports for convenience
pub use platform_helpers::*;
