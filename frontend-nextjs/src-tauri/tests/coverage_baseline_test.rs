//! Coverage baseline tracking tests
//!
//! Tests for the coverage baseline tracking module.

mod coverage;

use coverage::*;

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

    std::fs::write(temp_path, report_content).unwrap();

    let result = parse_json_report(temp_path);
    assert!(result.is_ok());
    assert_eq!(result.unwrap(), 42.5);

    // Cleanup
    let _ = std::fs::remove_file(temp_path);
}

#[test]
fn test_html_report_parsing_fallback() {
    // Test that HTML parsing fails gracefully with invalid content
    let invalid_html = "<html><body>No coverage data here</body></html>";
    let temp_path = "/tmp/test_coverage.html";

    std::fs::write(temp_path, invalid_html).unwrap();

    let result = parse_html_report(temp_path);
    assert!(result.is_err());

    // Cleanup
    let _ = std::fs::remove_file(temp_path);
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

    let temp_path = "/tmp/test_coverage_coverage.html";

    std::fs::write(temp_path, html_content).unwrap();

    let result = parse_html_report(temp_path);
    assert!(result.is_ok());

    // Cleanup
    let _ = std::fs::remove_file(temp_path);
}
