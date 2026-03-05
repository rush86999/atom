//! Integration tests for Tauri desktop application
//!
//! Tests for native API integration, system tray, notifications,
//! and cross-platform consistency.
//!
//! Note: Integration test files are at the root tests/ level:
//! - file_dialog_integration_test.rs
//! - menu_bar_integration_test.rs
//! - notification_integration_test.rs
//! - device_capabilities_integration_test.rs (Phase 142)

mod file_dialog_integration;
mod menu_bar_integration;
mod notification_integration;
mod cross_platform_validation;
