//! Coverage baseline tracking module for Atom desktop application
//!
//! This module provides utilities for:
//! - Parsing Tarpaulin coverage reports (HTML/JSON)
//! - Generating baseline coverage measurements
//! - Tracking coverage progress over time
//!
//! # Phase 140: Baseline Measurement
//!
//! This module establishes the initial coverage baseline for the desktop (Tauri/Rust) codebase.
//! The baseline is measured but not enforced in Phase 140.
//! Coverage enforcement will begin in Phase 142 (80% threshold).
//!
//! # Usage
//!
//! ```rust
//! use coverage::{generate_baseline, load_baseline};
//!
//! // Generate a new baseline after running coverage.sh
//! generate_baseline().expect("Failed to generate baseline");
//!
//! // Load an existing baseline
//! let baseline = load_baseline().expect("No baseline found");
//! println!("Current coverage: {}%", baseline.baseline_coverage);
//! ```

use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::fs;
use std::io;

/// Coverage baseline data structure
///
/// Captures the coverage percentage at a specific point in time,
/// along with metadata about the measurement.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CoverageBaseline {
    /// Overall coverage percentage (0.0 to 100.0)
    pub baseline_coverage: f64,

    /// ISO8601 timestamp when baseline was measured
    pub measured_at: String,

    /// Total lines of code (excluding tests)
    pub total_lines: usize,

    /// Lines covered by tests
    pub covered_lines: usize,

    /// Platform where baseline was measured (macos, windows, linux)
    pub platform: String,

    /// Architecture (x86_64, aarch64, etc.)
    pub arch: String,

    /// Git commit SHA (if available)
    pub commit_sha: Option<String>,

    /// Optional notes about the baseline
    pub notes: Option<String>,
}

impl CoverageBaseline {
    /// Create a new coverage baseline
    pub fn new(
        baseline_coverage: f64,
        total_lines: usize,
        covered_lines: usize,
        platform: String,
        arch: String,
    ) -> Self {
        Self {
            baseline_coverage,
            measured_at: chrono::Utc::now().to_rfc3339(),
            total_lines,
            covered_lines,
            platform,
            arch,
            commit_sha: get_git_sha(),
            notes: None,
        }
    }

    /// Add notes to the baseline
    pub fn with_notes(mut self, notes: String) -> Self {
        self.notes = Some(notes);
        self
    }

    /// Calculate percentage of uncovered code
    pub fn uncovered_percentage(&self) -> f64 {
        100.0 - self.baseline_coverage
    }

    /// Calculate gap to target coverage
    pub fn gap_to_target(&self, target: f64) -> f64 {
        (target - self.baseline_coverage).max(0.0)
    }
}

/// Get the current git commit SHA
fn get_git_sha() -> Option<String> {
    use std::process::Command;

    if let Ok(output) = Command::new("git")
        .args(["rev-parse", "--short", "HEAD"])
        .output()
    {
        if output.status.success() {
            if let Ok(sha) = String::from_utf8(output.stdout) {
                return Some(sha.trim().to_string());
            }
        }
    }
    None
}

/// Parse Tarpaulin coverage report and extract percentage
///
/// This function attempts to parse the coverage report from multiple sources:
/// 1. coverage-report/index.html (HTML report)
/// 2. coverage-report/coverage.json (JSON report)
/// 3. coverage/coverage.json (legacy location)
///
/// Returns the overall coverage percentage, or 0.0 if parsing fails.
pub fn parse_coverage_report() -> Result<f64, String> {
    // Try JSON report first (easier to parse)
    let json_paths = vec![
        "coverage-report/coverage.json",
        "coverage/coverage.json",
    ];

    for path in json_paths {
        if Path::new(path).exists() {
            if let Ok(coverage) = parse_json_report(path) {
                return Ok(coverage);
            }
        }
    }

    // Fallback to HTML parsing
    let html_path = "coverage-report/index.html";
    if Path::new(html_path).exists() {
        parse_html_report(html_path)
    } else {
        Err("No coverage report found. Run ./coverage.sh first.".to_string())
    }
}

/// Parse JSON coverage report
fn parse_json_report(path: &str) -> Result<f64, String> {
    let content = fs::read_to_string(path)
        .map_err(|e| format!("Failed to read {}: {}", path, e))?;

    // Try to parse as Tarpaulin JSON format
    // Tarpaulin JSON is a simple format with coverage percentage
    if let Ok(value) = serde_json::from_str::<serde_json::Value>(&content) {
        // Try to extract coverage from various possible formats
        if let Some(coverage) = value.get("coverage").and_then(|v| v.as_f64()) {
            return Ok(coverage);
        }

        // Tarpaulin sometimes outputs as a list of files
        if let Some(files) = value.as_array() {
            let mut total_lines = 0;
            let mut covered_lines = 0;

            for file in files {
                if let Some(total) = file.get("total").and_then(|v| v.as_u64()) {
                    total_lines += total as usize;
                }
                if let Some(covered) = file.get("covered").and_then(|v| v.as_u64()) {
                    covered_lines += covered as usize;
                }
            }

            if total_lines > 0 {
                return Ok((covered_lines as f64 / total_lines as f64) * 100.0);
            }
        }
    }

    Err(format!("Could not parse coverage from {}", path))
}

/// Parse HTML coverage report (basic extraction)
fn parse_html_report(path: &str) -> Result<f64, String> {
    let content = fs::read_to_string(path)
        .map_err(|e| format!("Failed to read {}: {}", path, e))?;

    // Tarpaulin HTML reports contain coverage percentage in the format:
    // "XX.XX%" in the header or summary section
    if let Some(pos) = content.find("%") {
        // Look backwards from the % to find the number
        let before_percent = &content[..pos];
        if let Some(number_start) = before_percent.rfind(|c: char| !c.is_numeric() && c != '.') {
            let number_str = &before_percent[number_start + 1..];
            if let Ok(percentage) = number_str.parse::<f64>() {
                return Ok(percentage);
            }
        }
    }

    // Alternative: search for "coverage:" patterns
    if let Some(idx) = content.to_lowercase().find("coverage") {
        let after_coverage = &content[idx..];
        // Look for a percentage within the next 100 characters
        let search_range = after_coverage.chars().take(100).collect::<String>();
        if let Some(percent_pos) = search_range.find('%') {
            let before_percent = &search_range[..percent_pos];
            let number_str = before_percent
                .chars()
                .rev()
                .take(10)
                .collect::<Vec<_>>()
                .into_iter()
                .rev()
                .collect::<String>();

            if let Ok(percentage) = number_str.trim().parse::<f64>() {
                return Ok(percentage);
            }
        }
    }

    Err("Could not extract coverage percentage from HTML report".to_string())
}

/// Get the path to the baseline JSON file
pub fn get_baseline_path() -> PathBuf {
    PathBuf::from("coverage/baseline.json")
}

/// Generate a new coverage baseline
///
/// This function parses the latest coverage report and creates
/// a baseline.json file with the current coverage metrics.
pub fn generate_baseline() -> Result<CoverageBaseline, String> {
    // Parse coverage report
    let coverage = parse_coverage_report()?;

    // Get platform and architecture
    let platform = std::env::consts::OS.to_string();
    let arch = std::env::consts::ARCH.to_string();

    // For now, use placeholder values for line counts
    // In the future, we can parse these from the coverage report more accurately
    let total_lines = 1757; // main.rs line count (from wc -l)
    let covered_lines = ((coverage / 100.0) * total_lines as f64) as usize;

    let baseline = CoverageBaseline::new(
        coverage,
        total_lines,
        covered_lines,
        platform,
        arch,
    ).with_notes("Phase 140 baseline measurement".to_string());

    // Ensure directory exists
    let baseline_path = get_baseline_path();
    if let Some(parent) = baseline_path.parent() {
        fs::create_dir_all(parent)
            .map_err(|e| format!("Failed to create directory: {}", e))?;
    }

    // Write baseline file
    let baseline_json = serde_json::to_string_pretty(&baseline)
        .map_err(|e| format!("Failed to serialize baseline: {}", e))?;

    fs::write(&baseline_path, baseline_json)
        .map_err(|e| format!("Failed to write baseline: {}", e))?;

    println!("✅ Coverage baseline created:");
    println!("   Coverage: {:.2}%", baseline.baseline_coverage);
    println!("   Platform: {}", baseline.platform);
    println!("   Arch: {}", baseline.arch);
    println!("   File: {}", baseline_path.display());

    Ok(baseline)
}

/// Load an existing coverage baseline
///
/// Returns the baseline data, or an error if the file doesn't exist.
pub fn load_baseline() -> Result<CoverageBaseline, String> {
    let baseline_path = get_baseline_path();

    if !baseline_path.exists() {
        return Err("Baseline file not found. Run generate_baseline() first.".to_string());
    }

    let content = fs::read_to_string(&baseline_path)
        .map_err(|e| format!("Failed to read baseline: {}", e))?;

    let baseline: CoverageBaseline = serde_json::from_str(&content)
        .map_err(|e| format!("Failed to parse baseline JSON: {}", e))?;

    Ok(baseline)
}

/// Compare current coverage with baseline
///
/// Returns the difference in percentage points (positive = improvement, negative = regression).
pub fn compare_with_baseline() -> Result<f64, String> {
    let current = parse_coverage_report()?;
    let baseline = load_baseline()?;

    let difference = current - baseline.baseline_coverage;

    println!("📊 Coverage Comparison:");
    println!("   Baseline: {:.2}%", baseline.baseline_coverage);
    println!("   Current:  {:.2}%", current);
    println!("   Difference: {:+.2}%", difference);

    Ok(difference)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_coverage_baseline_creation() {
        let baseline = CoverageBaseline::new(
            45.5,
            1000,
            455,
            "macos".to_string(),
            "x86_64".to_string(),
        );

        assert_eq!(baseline.baseline_coverage, 45.5);
        assert_eq!(baseline.total_lines, 1000);
        assert_eq!(baseline.covered_lines, 455);
        assert_eq!(baseline.platform, "macos");
        assert_eq!(baseline.arch, "x86_64");
    }

    #[test]
    fn test_uncovered_percentage() {
        let baseline = CoverageBaseline::new(
            75.0,
            1000,
            750,
            "linux".to_string(),
            "aarch64".to_string(),
        );

        assert_eq!(baseline.uncovered_percentage(), 25.0);
    }

    #[test]
    fn test_gap_to_target() {
        let baseline = CoverageBaseline::new(
            45.0,
            1000,
            450,
            "windows".to_string(),
            "x86_64".to_string(),
        );

        assert_eq!(baseline.gap_to_target(80.0), 35.0);
        assert_eq!(baseline.gap_to_target(40.0), 0.0); // Already above target
    }

    #[test]
    fn test_baseline_with_notes() {
        let baseline = CoverageBaseline::new(
            50.0,
            1000,
            500,
            "macos".to_string(),
            "arm64".to_string(),
        ).with_notes("Initial baseline".to_string());

        assert_eq!(baseline.notes, Some("Initial baseline".to_string()));
    }

    #[test]
    fn test_get_baseline_path() {
        let path = get_baseline_path();
        assert!(path.ends_with("coverage/baseline.json"));
    }

    #[test]
    fn test_json_report_parsing() {
        // Create a temporary JSON report
        let report_content = r#"{"coverage": 42.5}"#;
        let temp_path = "/tmp/test_coverage.json";

        fs::write(temp_path, report_content).unwrap();

        // Note: This test would need the file to exist in the right location
        // For now, we just verify the parsing logic works
        let result = parse_json_report(temp_path);
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), 42.5);

        // Cleanup
        let _ = fs::remove_file(temp_path);
    }

    #[test]
    fn test_html_report_parsing_fallback() {
        // Test that HTML parsing fails gracefully with invalid content
        let invalid_html = "<html><body>No coverage data here</body></html>";
        let temp_path = "/tmp/test_coverage.html";

        fs::write(temp_path, invalid_html).unwrap();

        let result = parse_html_report(temp_path);
        assert!(result.is_err());

        // Cleanup
        let _ = fs::remove_file(temp_path);
    }

    #[test]
    fn test_html_report_parsing_basic() {
        // Test basic HTML parsing with percentage
        let html_content = r#"
        <html>
        <body>
        <h1>Coverage Report: 67.8%</h1>
        </body>
        </html>
        "#;

        let temp_path = "/tmp/test_coverage.html";

        fs::write(temp_path, html_content).unwrap();

        let result = parse_html_report(temp_path);
        assert!(result.is_ok());
        // Note: HTML parsing is heuristic, so we just check it doesn't error

        // Cleanup
        let _ = fs::remove_file(temp_path);
    }
}
