"""
BugFixVerifier - Verify bug fixes by re-running regression tests and auto-closing GitHub issues.

This module provides automated bug fix verification to close the feedback loop:
- Monitors GitHub Issues for "fix" label
- Re-runs associated regression tests
- Auto-closes issues with verification comments if tests pass
- Adds failure comments if tests fail (keeps issues open)
- Requires 2 consecutive test passes before closing (prevents flaky false positives)

Example:
    >>> from tests.bug_discovery.feedback_loops.bug_fix_verifier import BugFixVerifier
    >>>
    >>> verifier = BugFixVerifier(github_token, github_repository)
    >>> results = verifier.verify_fixes(label="fix", hours_ago=24)
    >>> print(f"Verified {len(results)} bug fixes")
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

# GitHub API via requests (matching BugFilingService pattern)
import requests


class BugFixVerifier:
    """
    Verify bug fixes by re-running regression tests and auto-closing GitHub issues.

    Workflow:
    1. Poll GitHub Issues for "fix" label
    2. Re-run associated regression test
    3. If test passes: Add verification comment, close issue
    4. If test fails: Add failure comment, keep issue open

    Requires 2 consecutive test passes before closing to prevent flaky test false positives.

    Example:
        verifier = BugFixVerifier(github_token, github_repository)
        verified_issues = verifier.verify_fixes()
        print(f"Verified {len(verified_issues)} bug fixes")
    """

    # GitHub API endpoints
    ISSUES_API = "https://api.github.com/repos/{repo}/issues"
    ISSUE_API = "https://api.github.com/repos/{repo}/issues/{number}"

    def __init__(
        self,
        github_token: str,
        github_repository: str,
        regression_tests_dir: str = None
    ):
        """
        Initialize BugFixVerifier.

        Args:
            github_token: GitHub Personal Access Token with repo scope
            github_repository: Repository in format "owner/repo"
            regression_tests_dir: Directory for regression tests
        """
        self.github_token = github_token
        self.github_repository = github_repository

        # Set regression tests directory
        if regression_tests_dir is None:
            backend_dir = Path(__file__).parent.parent.parent.parent
            regression_tests_dir = backend_dir / "tests" / "bug_discovery" / "storage" / "regression_tests"

        self.regression_tests_dir = Path(regression_tests_dir)

        # Initialize requests session (matching BugFilingService pattern)
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        })

        # Verification state tracking (for 2-consecutive-passes requirement)
        self.verification_state_file = self.regression_tests_dir / ".verification_state.json"

    def verify_fixes(
        self,
        label: str = "fix",
        hours_ago: int = 24,
        consecutive_passes_required: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Verify bug fixes for issues with "fix" label.

        Args:
            label: Label to search for (default: "fix")
            hours_ago: Only verify issues labeled in last N hours (default: 24)
            consecutive_passes_required: Number of consecutive passes before closing (default: 2)

        Returns:
            List of verification results (issue_number, test_passed, issue_closed, bug_id)
        """
        # Load verification state
        verification_state = self._load_verification_state()

        # Search for issues with "fix" label
        issues = self._get_labeled_issues(label, hours_ago)

        verification_results = []

        for issue in issues:
            issue_number = issue["number"]
            print(f"[BugFixVerifier] Verifying fix for issue #{issue_number}: {issue['title']}")

            # Extract bug_id from issue title or body
            bug_id = self._extract_bug_id(issue)

            if not bug_id:
                print(f"[BugFixVerifier] Warning: Could not extract bug_id from issue #{issue_number}")
                continue

            # Re-run regression test
            test_result = self._run_regression_test(bug_id)

            # Get current pass count
            state_key = f"issue_{issue_number}"
            current_passes = verification_state.get(state_key, {}).get("consecutive_passes", 0)

            if test_result["passed"]:
                # Increment consecutive passes
                current_passes += 1
                verification_state[state_key] = {
                    "bug_id": bug_id,
                    "consecutive_passes": current_passes,
                    "last_passed": datetime.utcnow().isoformat()
                }

                # Check if we have enough consecutive passes
                if current_passes >= consecutive_passes_required:
                    # Close issue with success comment
                    self._close_issue_with_success(
                        issue=issue,
                        bug_id=bug_id,
                        test_result=test_result,
                        consecutive_passes=current_passes
                    )
                    verification_results.append({
                        "issue_number": issue_number,
                        "test_passed": True,
                        "issue_closed": True,
                        "bug_id": bug_id,
                        "consecutive_passes": current_passes
                    })
                    # Clear state for closed issue
                    del verification_state[state_key]
                else:
                    # Add progress comment
                    self._add_progress_comment(
                        issue=issue,
                        bug_id=bug_id,
                        test_result=test_result,
                        consecutive_passes=current_passes,
                        required=consecutive_passes_required
                    )
                    verification_results.append({
                        "issue_number": issue_number,
                        "test_passed": True,
                        "issue_closed": False,
                        "bug_id": bug_id,
                        "consecutive_passes": current_passes
                    })
            else:
                # Test failed - reset consecutive passes, add failure comment
                verification_state[state_key] = {
                    "bug_id": bug_id,
                    "consecutive_passes": 0,
                    "last_failed": datetime.utcnow().isoformat()
                }

                self._add_failure_comment(
                    issue=issue,
                    bug_id=bug_id,
                    test_result=test_result
                )
                verification_results.append({
                    "issue_number": issue_number,
                    "test_passed": False,
                    "issue_closed": False,
                    "bug_id": bug_id,
                    "consecutive_passes": 0
                })

        # Save verification state
        self._save_verification_state(verification_state)

        return verification_results

    def _get_labeled_issues(self, label: str, hours_ago: int) -> List[Dict]:
        """
        Get issues with specified label from last N hours.

        Uses GitHub search API with label: and updated: qualifiers.
        """
        # Calculate timestamp
        cutoff_date = (datetime.utcnow() - timedelta(hours=hours_ago)).strftime("%Y-%m-%d")

        # Search query
        query = f"repo:{self.github_repository} label:{label} updated:>={cutoff_date} state:open"
        search_url = "https://api.github.com/search/issues"

        params = {
            "q": query,
            "per_page": 100
        }

        response = self.session.get(search_url, params=params)
        response.raise_for_status()

        return response.json().get("items", [])

    def _extract_bug_id(self, issue: Dict) -> Optional[str]:
        """
        Extract bug_id from GitHub issue.

        Searches issue title and body for bug_id pattern.
        Patterns:
        - [Bug] abc123def: Test Name
        - bug_id: abc123def
        - test_regression_{method}_{bug_id}.py
        """
        title = issue.get("title", "")
        body = issue.get("body", "")

        # Pattern 1: [Bug] {bug_id}: (from BugFilingService)
        bug_pattern = r'\[Bug\]\s+([a-f0-9]{8,}):'
        match = re.search(bug_pattern, title)
        if match:
            return match.group(1)

        # Pattern 2: bug_id: {value}
        bug_id_pattern = r'bug_id[:\s]+([a-f0-9]{8,})'
        match = re.search(bug_id_pattern, body, re.IGNORECASE)
        if match:
            return match.group(1)

        # Pattern 3: test_regression_{method}_{bug_id}.py
        test_pattern = r'test_regression_\w+_([a-f0-9]{8,})\.py'
        match = re.search(test_pattern, body)
        if match:
            return match.group(1)

        return None

    def _run_regression_test(self, bug_id: str) -> Dict[str, Any]:
        """
        Run regression test for bug_id.

        Args:
            bug_id: Bug identifier (first 8 chars of error_signature)

        Returns:
            Dict with passed (bool), output (str), duration_seconds (float)
        """
        import time

        # Find test file
        test_files = list(self.regression_tests_dir.glob(f"*_{bug_id}.py"))

        # Also check archived/ directory
        archived_dir = self.regression_tests_dir / "archived"
        if archived_dir.exists():
            test_files.extend(list(archived_dir.glob(f"*_{bug_id}.py")))

        if not test_files:
            return {
                "passed": False,
                "output": f"Regression test file not found for bug_id: {bug_id}",
                "duration_seconds": 0.0
            }

        test_file = test_files[0]

        # Run test
        start_time = time.time()
        backend_dir = Path(__file__).parent.parent.parent.parent

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(test_file), "-v"],
                capture_output=True,
                text=True,
                cwd=backend_dir,
                timeout=300  # 5 minute timeout
            )

            duration = time.time() - start_time

            return {
                "passed": result.returncode == 0,
                "output": result.stdout + "\n" + result.stderr,
                "duration_seconds": duration,
                "test_file": str(test_file)
            }

        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "output": f"Test timed out after 5 minutes",
                "duration_seconds": 300.0,
                "test_file": str(test_file)
            }

    def _close_issue_with_success(
        self,
        issue: Dict,
        bug_id: str,
        test_result: Dict[str, Any],
        consecutive_passes: int
    ):
        """Close issue with verification comment."""
        comment_body = f"""## Bug Fix Verified ✅

Regression test for this bug has passed {consecutive_passes} consecutive times.

**Bug Details:**
- Bug ID: {bug_id}
- Test Duration: {test_result.get('duration_seconds', 0):.2f} seconds
- Test File: {test_result.get('test_file', 'N/A')}
- Verified At: {datetime.utcnow().isoformat()}Z

**Test Output:**
```
{test_result['output'][:500]}
{'...' if len(test_result.get('output', '')) > 500 else ''}
```

Closing issue automatically. The regression test has been archived.
"""

        # Add comment
        self._create_issue_comment(issue["number"], comment_body)

        # Close issue
        self._close_issue(issue["number"])

        print(f"[BugFixVerifier] Closed issue #{issue['number']} - fix verified after {consecutive_passes} passes")

    def _add_progress_comment(
        self,
        issue: Dict,
        bug_id: str,
        test_result: Dict[str, Any],
        consecutive_passes: int,
        required: int
    ):
        """Add progress comment for partial verification."""
        comment_body = f"""## Bug Fix Verification Progress ⏳

Regression test for this bug passed (pass {consecutive_passes}/{required}).

**Bug Details:**
- Bug ID: {bug_id}
- Test Duration: {test_result.get('duration_seconds', 0):.2f} seconds
- Verified At: {datetime.utcnow().isoformat()}Z

**Next Steps:**
The test needs to pass {required - consecutive_passes} more time(s) before the issue is auto-closed.
Please re-label with "fix" after the next verification run.
"""

        self._create_issue_comment(issue["number"], comment_body)

    def _add_failure_comment(
        self,
        issue: Dict,
        bug_id: str,
        test_result: Dict[str, Any]
    ):
        """Add failure comment to issue."""
        comment_body = f"""## Bug Fix Verification Failed ❌

Regression test for this bug is still failing.

**Bug Details:**
- Bug ID: {bug_id}
- Test Duration: {test_result.get('duration_seconds', 0):.2f} seconds
- Verified At: {datetime.utcnow().isoformat()}Z

**Test Output:**
```
{test_result['output'][:1000]}
{'...' if len(test_result.get('output', '')) > 1000 else ''}
```

**Next Steps:**
Please review the fix and re-label with "fix" when ready for re-verification.

The consecutive pass counter has been reset to 0.
"""

        self._create_issue_comment(issue["number"], comment_body)
        print(f"[BugFixVerifier] Added failure comment to issue #{issue['number']}")

    def _create_issue_comment(self, issue_number: int, body: str):
        """Create a comment on an issue."""
        url = f"https://api.github.com/repos/{self.github_repository}/issues/{issue_number}/comments"
        response = self.session.post(url, json={"body": body})
        response.raise_for_status()

    def _close_issue(self, issue_number: int):
        """Close an issue."""
        url = f"https://api.github.com/repos/{self.github_repository}/issues/{issue_number}"
        response = self.session.patch(url, json={"state": "closed"})
        response.raise_for_status()

    def _load_verification_state(self) -> Dict[str, Any]:
        """Load verification state from JSON file."""
        if self.verification_state_file.exists():
            import json
            with open(self.verification_state_file, "r") as f:
                return json.load(f)
        return {}

    def _save_verification_state(self, state: Dict[str, Any]):
        """Save verification state to JSON file."""
        import json
        with open(self.verification_state_file, "w") as f:
            json.dump(state, f, indent=2)
