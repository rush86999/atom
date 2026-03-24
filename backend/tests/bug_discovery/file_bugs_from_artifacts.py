#!/usr/bin/env python3
"""
Bug Filing Script for Test Failures

This script scans the artifacts directory for test failure reports,
parses them, and files GitHub Issues using the BugFilingService.

Usage:
    python file_bugs_from_artifacts.py

Environment Variables:
    GITHUB_TOKEN: GitHub Personal Access Token (automatic in CI/CD)
    GITHUB_REPOSITORY: Repository in format "owner/repo"
    WORKFLOW_RUN_URL: URL of the workflow run (optional)
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.bug_discovery.bug_filing_service import BugFilingService


def find_failure_reports(artifacts_dir: Path) -> List[Path]:
    """
    Find all failure report JSON files in artifacts directory.

    Args:
        artifacts_dir: Path to artifacts directory

    Returns:
        List of paths to failure report files
    """
    failure_reports = []

    # Search for JSON files that might be failure reports
    for json_file in artifacts_dir.rglob("*.json"):
        # Check if it's a failure report (has test_name and error_message)
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                if "test_name" in data and "error_message" in data:
                    failure_reports.append(json_file)
        except (json.JSONDecodeError, IOError):
            continue

    return failure_reports


def parse_failure_report(report_path: Path) -> Dict[str, Any]:
    """
    Parse a failure report JSON file.

    Args:
        report_path: Path to failure report file

    Returns:
        Dict with failure metadata
    """
    with open(report_path, 'r') as f:
        return json.load(f)


def determine_test_type(metadata: Dict[str, Any]) -> str:
    """
    Determine test type from metadata.

    Args:
        metadata: Failure metadata dict

    Returns:
        Test type string (load, network, memory, mobile, desktop, visual, a11y)
    """
    # Check for explicit test_type
    if "test_type" in metadata:
        return metadata["test_type"]

    # Infer from file path
    test_file = metadata.get("test_file", "")
    if "load" in test_file:
        return "load"
    elif "network" in test_file or "offline" in test_file:
        return "network"
    elif "memory" in test_file or "leak" in test_file:
        return "memory"
    elif "mobile" in test_file:
        return "mobile"
    elif "desktop" in test_file or "window" in test_file:
        return "desktop"
    elif "visual" in test_file or "percy" in test_file:
        return "visual"
    elif "a11y" in test_file or "wcag" in test_file or "accessibility" in test_file:
        return "a11y"

    # Default to generic
    return "unknown"


def enrich_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich metadata with additional context.

    Args:
        metadata: Original metadata dict

    Returns:
        Enriched metadata dict
    """
    # Add CI/CD context
    metadata["ci_run_url"] = os.getenv("WORKFLOW_RUN_URL", "")
    metadata["commit_sha"] = os.getenv("GITHUB_SHA", "unknown")
    metadata["branch_name"] = os.getenv("GITHUB_REF_NAME", "unknown")

    # Determine test type if not set
    if "test_type" not in metadata:
        metadata["test_type"] = determine_test_type(metadata)

    # Add platform if not set
    if "platform" not in metadata:
        metadata["platform"] = "web"  # Default

    return metadata


def file_bugs_from_reports(
    service: BugFilingService,
    failure_reports: List[Path]
) -> List[Dict[str, Any]]:
    """
    File bugs for all failure reports.

    Args:
        service: BugFilingService instance
        failure_reports: List of failure report paths

    Returns:
        List of filing results
    """
    results = []

    for report_path in failure_reports:
        try:
            # Parse failure report
            failure_data = parse_failure_report(report_path)

            # Extract required fields
            test_name = failure_data.get("test_name", "unknown_test")
            error_message = failure_data.get("error_message", "Test failed")
            metadata = failure_data.get("metadata", {})

            # Enrich metadata
            metadata = enrich_metadata(metadata)

            # Add test_name if not in metadata
            if "test_file" not in metadata:
                metadata["test_file"] = test_name

            # Add stack_trace if available
            if "stack_trace" in failure_data:
                metadata["stack_trace"] = failure_data["stack_trace"]

            # Add screenshot/log paths if available
            if "screenshot_path" in failure_data:
                metadata["screenshot_path"] = failure_data["screenshot_path"]
            if "log_path" in failure_data:
                metadata["log_path"] = failure_data["log_path"]

            # File bug
            result = service.file_bug(
                test_name=test_name,
                error_message=error_message,
                metadata=metadata
            )

            # Add report path to result
            result["report_path"] = str(report_path)
            results.append(result)

            # Log result
            if result["status"] == "created":
                print(f"✓ Filed bug: {result['issue_url']} - {test_name}")
            elif result["status"] == "duplicate":
                print(f"⊘ Duplicate bug: {result['issue_url']} - {test_name}")
            else:
                print(f"✗ Failed to file bug: {test_name}")

        except Exception as e:
            print(f"✗ Error processing {report_path}: {e}")
            results.append({
                "status": "error",
                "error": str(e),
                "report_path": str(report_path)
            })

    return results


def save_bug_links(results: List[Dict[str, Any]], artifacts_dir: Path) -> None:
    """
    Save bug links to a text file for PR commenting.

    Args:
        results: List of filing results
        artifacts_dir: Path to artifacts directory
    """
    bug_links_path = artifacts_dir / "bug_links.txt"

    with open(bug_links_path, 'w') as f:
        f.write("# Bugs Filed from Test Failures\n\n")
        f.write(f"Generated at: {datetime.utcnow().isoformat()}Z\n\n")

        for result in results:
            if result["status"] == "created":
                f.write(f"- [{result['issue_number']}] {result['issue_url']}\n")

    print(f"\nBug links saved to: {bug_links_path}")


def save_filing_results(results: List[Dict[str, Any]], artifacts_dir: Path) -> None:
    """
    Save filing results to JSON file.

    Args:
        results: List of filing results
        artifacts_dir: Path to artifacts directory
    """
    filed_bugs_path = artifacts_dir / "filed_bugs.json"

    with open(filed_bugs_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"Filing results saved to: {filed_bugs_path}")


def main():
    """Main entry point."""
    # Get environment variables
    github_token = os.getenv("GITHUB_TOKEN")
    github_repository = os.getenv("GITHUB_REPOSITORY")

    if not github_token:
        print("Error: GITHUB_TOKEN environment variable not set")
        sys.exit(1)

    if not github_repository:
        print("Error: GITHUB_REPOSITORY environment variable not set")
        sys.exit(1)

    # Initialize bug filing service
    print(f"Initializing bug filing service for {github_repository}...")
    service = BugFilingService(github_token, github_repository)

    # Find artifacts directory
    artifacts_dir = Path(__file__).parent.parent / "artifacts"
    if not artifacts_dir.exists():
        print(f"Warning: Artifacts directory not found: {artifacts_dir}")
        # Create it for output files
        artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Find failure reports
    print(f"\nScanning for failure reports in: {artifacts_dir}")
    failure_reports = find_failure_reports(artifacts_dir)

    if not failure_reports:
        print("No failure reports found.")
        print("Bug filing requires test failure reports in artifacts directory.")
        print("\nTo create failure reports, run tests with failure capture enabled.")
        return

    print(f"Found {len(failure_reports)} failure report(s)")

    # File bugs
    print("\nFiling bugs...")
    results = file_bugs_from_reports(service, failure_reports)

    # Save results
    save_bug_links(results, artifacts_dir)
    save_filing_results(results, artifacts_dir)

    # Print summary
    created = sum(1 for r in results if r["status"] == "created")
    duplicates = sum(1 for r in results if r["status"] == "duplicate")
    errors = sum(1 for r in results if r["status"] == "error")

    print(f"\n{'='*60}")
    print("Bug Filing Summary")
    print(f"{'='*60}")
    print(f"Total reports: {len(results)}")
    print(f"Bugs created:  {created}")
    print(f"Duplicates:    {duplicates}")
    print(f"Errors:        {errors}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
