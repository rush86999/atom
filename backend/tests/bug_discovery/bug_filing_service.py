"""
Automated Bug Filing Service for Test Failures

This module provides a service for automatically filing GitHub Issues
when tests fail, with complete metadata including screenshots, logs,
traces, and reproducible test cases.
"""

import os
import platform
import re
import traceback
from typing import Dict, List, Optional
from datetime import datetime

import requests


class BugFilingService:
    """
    Service for automatically filing GitHub Issues for test failures.

    Features:
    - Idempotent bug filing (no duplicate issues)
    - Rich metadata collection (screenshots, logs, traces)
    - Automatic labeling (test type, severity, platform)
    - Integration with all test types (load, network, memory, mobile, desktop, visual, a11y)
    """

    def __init__(self, github_token: str, github_repository: str):
        """
        Initialize BugFilingService.

        Args:
            github_token: GitHub Personal Access Token (PAT) with repo scope
            github_repository: Repository in format "owner/repo"
        """
        self.github_token = github_token
        self.github_repository = github_repository
        self.github_api_url = f"https://api.github.com/repos/{github_repository}/issues"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        })

        # Cache existing issues for idempotency
        self._existing_issues_cache: Optional[List[Dict]] = None

    def file_bug(
        self,
        test_name: str,
        error_message: str,
        metadata: Dict,
        expected_behavior: Optional[str] = None,
        actual_behavior: Optional[str] = None
    ) -> Dict:
        """
        File a bug for test failure.

        Args:
            test_name: Name of the failed test
            error_message: Error message from test failure
            metadata: Dict containing test metadata (screenshots, logs, platform info, etc.)
            expected_behavior: Expected behavior (optional)
            actual_behavior: Actual behavior (optional)

        Returns:
            Dict with issue URL and number if created, or existing issue if duplicate
        """
        # Generate bug title
        title = self._generate_bug_title(test_name, metadata.get("error_type", "Test Failure"))

        # Check for duplicate bug
        existing_issue = self._check_duplicate_bug(title)
        if existing_issue:
            return {
                "status": "duplicate",
                "issue_url": existing_issue["html_url"],
                "issue_number": existing_issue["number"],
                "message": "Bug already filed"
            }

        # Generate bug body
        body = self._generate_bug_body(
            test_name=test_name,
            error_message=error_message,
            metadata=metadata,
            expected_behavior=expected_behavior,
            actual_behavior=actual_behavior
        )

        # Generate labels
        labels = self._generate_labels(metadata)

        # Create GitHub issue
        issue = self._create_github_issue(title, body, labels)

        # Attach screenshots and logs if available
        if issue.get("number"):
            issue_number = issue["number"]

            # Attach screenshot
            if metadata.get("screenshot_path"):
                self._attach_screenshot(issue_number, metadata["screenshot_path"])

            # Attach logs
            if metadata.get("log_path"):
                self._attach_logs(issue_number, metadata["log_path"])

        return {
            "status": "created",
            "issue_url": issue.get("html_url"),
            "issue_number": issue.get("number"),
            "message": "Bug filed successfully"
        }

    def _check_duplicate_bug(self, title: str) -> Optional[Dict]:
        """
        Check if a bug with the same title already exists.

        Args:
            title: Bug title to check

        Returns:
            Existing issue dict if found, None otherwise
        """
        # Lazy load existing issues
        if self._existing_issues_cache is None:
            try:
                response = self.session.get(self.github_api_url, params={"state": "open", "per_page": 100})
                response.raise_for_status()
                self._existing_issues_cache = response.json()
            except Exception as e:
                print(f"Warning: Failed to fetch existing issues: {e}")
                self._existing_issues_cache = []

        # Search for duplicate title
        for issue in self._existing_issues_cache:
            if issue["title"] == title:
                return issue

        return None

    def _create_github_issue(self, title: str, body: str, labels: List[str]) -> Dict:
        """
        Create a GitHub issue.

        Args:
            title: Issue title
            body: Issue body (markdown formatted)
            labels: List of labels to apply

        Returns:
            Created issue dict
        """
        payload = {
            "title": title,
            "body": body,
            "labels": labels
        }

        try:
            response = self.session.post(self.github_api_url, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error creating GitHub issue: {e}")
            raise

    def _generate_bug_title(self, test_name: str, error_type: str) -> str:
        """
        Generate bug title from test name and error type.

        The title includes both error type and test name to make bugs
        discoverable and searchable. Different error messages for the
        same test will create different bugs (this is intentional).

        Args:
            test_name: Name of the failed test
            error_type: Type of error

        Returns:
            Formatted bug title
        """
        # Extract test name from full path if needed
        clean_test_name = test_name.split("::")[-1] if "::" in test_name else test_name
        clean_test_name = clean_test_name.replace("_", " ").replace("-", " ").strip()
        clean_test_name = clean_test_name.title()

        # Create a short error identifier from error_type (first 50 chars)
        error_identifier = error_type[:50] if len(error_type) > 50 else error_type

        return f"[Bug] {error_identifier}: {clean_test_name}"

    def _generate_bug_body(
        self,
        test_name: str,
        error_message: str,
        metadata: Dict,
        expected_behavior: Optional[str] = None,
        actual_behavior: Optional[str] = None
    ) -> str:
        """
        Generate bug body with complete metadata.

        Args:
            test_name: Name of the failed test
            error_message: Error message from test failure
            metadata: Dict containing test metadata
            expected_behavior: Expected behavior
            actual_behavior: Actual behavior

        Returns:
            Markdown-formatted bug body
        """
        # Extract metadata
        test_file = metadata.get("test_file", "unknown")
        os_info = metadata.get("os_info", platform.platform())
        python_version = metadata.get("python_version", platform.python_version())
        stack_trace = metadata.get("stack_trace", "")
        screenshot_url = metadata.get("screenshot_url", "")
        log_content = metadata.get("log_content", "")
        performance_metrics = metadata.get("performance_metrics", {})
        ci_run_url = metadata.get("ci_run_url", "")
        commit_sha = metadata.get("commit_sha", os.getenv("GITHUB_SHA", "unknown"))
        branch_name = metadata.get("branch_name", os.getenv("GITHUB_REF_NAME", "unknown"))

        # Extract custom metadata fields for test-specific context
        # These will be displayed in a custom metadata section
        custom_metadata = {}
        custom_fields = [
            "network_condition", "memory_increase_mb", "iterations",
            "endpoint", "status_code", "action", "percy_diff_url",
            "pixel_diff_count", "violation_type", "violation_count", "wcag_level",
            "device"
        ]
        for field in custom_fields:
            if field in metadata:
                custom_metadata[field] = metadata[field]

        # Build bug body
        body = f"""## Bug Description

{error_message}

## Test Context

- **Test:** `{test_name}`
- **File:** `{test_file}`
- **Platform:** {os_info}
- **Python:** {python_version}

"""

        # Add stack trace if available
        if stack_trace:
            body += f"""## Stack Trace

```
{stack_trace}
```

"""

        # Add steps to reproduce
        body += f"""## Steps to Reproduce

1. Run test: `pytest {test_file}::{test_name}`
2. Observe failure

"""

        # Add expected and actual behavior
        if expected_behavior:
            body += f"""## Expected Behavior

{expected_behavior}

"""

        if actual_behavior:
            body += f"""## Actual Behavior

{actual_behavior}

"""

        # Add performance metrics if available
        if performance_metrics:
            body += f"""## Performance Metrics

"""
            for metric_name, metric_value in performance_metrics.items():
                body += f"- **{metric_name}:** {metric_value}\n"
            body += "\n"

        # Add custom metadata if available
        if custom_metadata:
            body += f"""## Test-Specific Metadata

"""
            for field_name, field_value in custom_metadata.items():
                body += f"- **{field_name}:** {field_value}\n"
            body += "\n"

        # Add screenshot if available
        if screenshot_url:
            body += f"""## Screenshots

![Screenshot]({screenshot_url})

"""

        # Add logs if available
        if log_content:
            body += f"""## Logs

```
{log_content}
```

"""

        # Add CI/CD metadata
        body += f"""## Metadata

- **Test run:** [{ci_run_url}]({ci_run_url}) if ci_run_url else "local"
- **Commit:** `{commit_sha}`
- **Branch:** `{branch_name}`
- **Filed by:** Automated bug filing service
- **Timestamp:** {datetime.utcnow().isoformat()}Z
"""

        return body

    def _generate_labels(self, metadata: Dict) -> List[str]:
        """
        Generate labels for bug issue.

        Args:
            metadata: Dict containing test metadata

        Returns:
            List of labels
        """
        labels = ["bug", "automated"]

        # Test type label
        test_type = metadata.get("test_type", "unknown")
        labels.append(f"test-type:{test_type}")

        # Severity label
        severity = self._determine_severity(test_type, metadata)
        labels.append(f"severity:{severity}")

        # Platform label
        platform = metadata.get("platform", "web")
        labels.append(f"platform:{platform}")

        return labels

    def _determine_severity(self, test_type: str, metadata: Dict) -> str:
        """
        Determine bug severity based on test type and metadata.

        Args:
            test_type: Type of test (load, network, memory, etc.)
            metadata: Test metadata

        Returns:
            Severity level (critical, high, medium, low)
        """
        # Critical severity: load tests, security issues
        if test_type == "load":
            performance_metrics = metadata.get("performance_metrics", {})
            if performance_metrics.get("error_rate", 0) > 10:
                return "critical"
            return "high"

        # High severity: memory leaks, network failures, accessibility
        if test_type in ["memory", "network", "a11y"]:
            return "high"

        # Medium severity: visual regression, mobile, desktop
        if test_type in ["visual", "mobile", "desktop"]:
            return "medium"

        # Low severity: other issues
        return "low"

    def _attach_screenshot(self, issue_number: int, screenshot_path: str) -> None:
        """
        Attach screenshot to GitHub issue.

        Args:
            issue_number: GitHub issue number
            screenshot_path: Path to screenshot file
        """
        try:
            # Check if screenshot file exists
            if not os.path.exists(screenshot_path):
                print(f"Warning: Screenshot file not found: {screenshot_path}")
                return

            # Upload screenshot as issue comment
            # Note: GitHub API doesn't support direct image upload in comments
            # Images must be uploaded first, then referenced by URL
            # For now, we'll add a comment with the local path
            comment_body = f"**Screenshot:** `{screenshot_path}`\n\n*(Note: Automated screenshot upload requires additional setup)*"

            comment_url = f"{self.github_api_url}/{issue_number}/comments"
            self.session.post(comment_url, json={"body": comment_body})

        except Exception as e:
            print(f"Warning: Failed to attach screenshot: {e}")

    def _attach_logs(self, issue_number: int, log_path: str) -> None:
        """
        Attach logs to GitHub issue.

        Args:
            issue_number: GitHub issue number
            log_path: Path to log file
        """
        try:
            # Check if log file exists
            if not os.path.exists(log_path):
                print(f"Warning: Log file not found: {log_path}")
                return

            # Read log content (limit to 10KB to avoid huge comments)
            with open(log_path, "r") as f:
                log_content = f.read(10240)  # 10KB limit
                if len(log_content) >= 10240:
                    log_content += "\n\n...(truncated)"

            # Add logs as issue comment
            comment_body = f"""**Test Logs:**

```
{log_content}
```
"""

            comment_url = f"{self.github_api_url}/{issue_number}/comments"
            self.session.post(comment_url, json={"body": comment_body})

        except Exception as e:
            print(f"Warning: Failed to attach logs: {e}")


def file_bug_from_test_failure(
    test_name: str,
    error_message: str,
    stack_trace: str,
    test_type: str,
    metadata: Optional[Dict] = None
) -> Dict:
    """
    Convenience function to file bug from test failure.

    Args:
        test_name: Name of the failed test
        error_message: Error message from test failure
        stack_trace: Stack trace from test failure
        test_type: Type of test (load, network, memory, mobile, desktop, visual, a11y)
        metadata: Additional metadata (optional)

    Returns:
        Dict with issue URL and number if created
    """
    # Get GitHub token and repository from environment
    github_token = os.getenv("GITHUB_TOKEN")
    github_repository = os.getenv("GITHUB_REPOSITORY")

    if not github_token:
        raise ValueError("GITHUB_TOKEN environment variable not set")

    if not github_repository:
        raise ValueError("GITHUB_REPOSITORY environment variable not set")

    # Create bug filing service
    service = BugFilingService(github_token, github_repository)

    # Prepare metadata
    if metadata is None:
        metadata = {}

    # Add default metadata
    metadata.update({
        "test_type": test_type,
        "stack_trace": stack_trace,
        "os_info": platform.platform(),
        "python_version": platform.python_version(),
        "test_file": metadata.get("test_file", "unknown"),
        "platform": metadata.get("platform", "web")
    })

    # File bug
    return service.file_bug(test_name, error_message, metadata)
