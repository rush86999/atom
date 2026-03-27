"""
Unit tests for BugFixVerifier.
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add backend to path
import sys
backend_dir = Path(__file__).parent.parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tests.bug_discovery.feedback_loops.bug_fix_verifier import BugFixVerifier


@pytest.fixture
def temp_regression_dir(tmp_path):
    """Temporary directory for regression tests."""
    tests_dir = tmp_path / "regression_tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    # Create a sample test file
    test_file = tests_dir / "test_regression_fuzzing_abc123de.py"
    test_file.write_text("""
import pytest

@pytest.mark.regression
def test_regression_abc123de():
    assert True
""")

    # Create archived subdirectory
    archived_dir = tests_dir / "archived"
    archived_dir.mkdir(parents=True, exist_ok=True)

    archived_test = archived_dir / "test_regression_chaos_def456ab.py"
    archived_test.write_text("""
import pytest

@pytest.mark.regression
def test_regression_def456ab():
    assert True
""")

    return str(tests_dir)


@pytest.fixture
def mock_github_response():
    """Mock GitHub API response."""
    return {
        "items": [
            {
                "number": 123,
                "title": "[Bug] abc123de: SQL injection in agent_id",
                "body": "Bug ID: abc123de\\n\\nThis bug causes SQL injection.",
                "labels": [{"name": "fix"}],
                "updated_at": (datetime.utcnow() - timedelta(hours=1)).isoformat()
            },
            {
                "number": 124,
                "title": "Different issue without bug_id",
                "body": "This issue has no bug_id in title or body.",
                "labels": [{"name": "fix"}],
                "updated_at": (datetime.utcnow()).isoformat()
            }
        ]
    }


class TestBugFixVerifier:
    """Test BugFixVerifier class."""

    def test_init_creates_session(self, temp_regression_dir):
        """Test that __init__ creates requests session with auth headers."""
        verifier = BugFixVerifier("test_token", "owner/repo", temp_regression_dir)

        assert verifier.github_token == "test_token"
        assert verifier.github_repository == "owner/repo"
        assert verifier.session is not None
        assert "Authorization" in verifier.session.headers
        assert "token test_token" in verifier.session.headers["Authorization"]

    @patch('requests.Session.get')
    def test_get_labeled_issues(self, mock_get, temp_regression_dir):
        """Test _get_labeled_issues queries GitHub search API."""
        mock_response = Mock()
        mock_response.json.return_value = {"items": [{"number": 123}]}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        verifier = BugFixVerifier("test_token", "owner/repo", temp_regression_dir)
        issues = verifier._get_labeled_issues("fix", hours_ago=24)

        assert len(issues) == 1
        assert issues[0]["number"] == 123

    def test_extract_bug_id_from_title(self, temp_regression_dir):
        """Test _extract_bug_id extracts bug_id from [Bug] abc123de: format."""
        verifier = BugFixVerifier("test_token", "owner/repo", temp_regression_dir)

        issue = {
            "title": "[Bug] abc123de: SQL injection",
            "body": "Some description"
        }

        bug_id = verifier._extract_bug_id(issue)
        assert bug_id == "abc123de"

    def test_extract_bug_id_from_body(self, temp_regression_dir):
        """Test _extract_bug_id extracts bug_id from body."""
        verifier = BugFixVerifier("test_token", "owner/repo", temp_regression_dir)

        issue = {
            "title": "SQL injection bug",
            "body": "bug_id: abc123de\nDetails here"
        }

        bug_id = verifier._extract_bug_id(issue)
        assert bug_id == "abc123de"

    def test_extract_bug_id_from_test_name(self, temp_regression_dir):
        """Test _extract_bug_id extracts bug_id from test filename pattern."""
        verifier = BugFixVerifier("test_token", "owner/repo", temp_regression_dir)

        issue = {
            "title": "Bug found",
            "body": "See test_regression_fuzzing_abc123de.py"
        }

        bug_id = verifier._extract_bug_id(issue)
        assert bug_id == "abc123de"

    def test_extract_bug_id_returns_none(self, temp_regression_dir):
        """Test _extract_bug_id returns None when no bug_id found."""
        verifier = BugFixVerifier("test_token", "owner/repo", temp_regression_dir)

        issue = {
            "title": "Random issue",
            "body": "No bug_id here"
        }

        bug_id = verifier._extract_bug_id(issue)
        assert bug_id is None

    @patch('subprocess.run')
    def test_run_regression_test_passes(self, mock_run, temp_regression_dir):
        """Test _run_regression_test returns passed=True when test passes."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "PASSED"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        verifier = BugFixVerifier("test_token", "owner/repo", temp_regression_dir)
        result = verifier._run_regression_test("abc123de")

        assert result["passed"] is True
        assert "duration_seconds" in result
        assert result["test_file"].endswith("test_regression_fuzzing_abc123de.py")

    @patch('subprocess.run')
    def test_run_regression_test_fails(self, mock_run, temp_regression_dir):
        """Test _run_regression_test returns passed=False when test fails."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "FAILED"
        mock_run.return_value = mock_result

        verifier = BugFixVerifier("test_token", "owner/repo", temp_regression_dir)
        result = verifier._run_regression_test("abc123de")

        assert result["passed"] is False
        assert "FAILED" in result["output"]

    def test_run_regression_test_not_found(self, temp_regression_dir):
        """Test _run_regression_test returns error when test file not found."""
        verifier = BugFixVerifier("test_token", "owner/repo", temp_regression_dir)
        result = verifier._run_regression_test("nonexistent")

        assert result["passed"] is False
        assert "not found" in result["output"]

    @patch('subprocess.run')
    def test_run_regression_test_finds_archived_test(self, mock_run, temp_regression_dir):
        """Test _run_regression_test finds tests in archived/ directory."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "PASSED"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        verifier = BugFixVerifier("test_token", "owner/repo", temp_regression_dir)
        result = verifier._run_regression_test("def456ab")

        assert result["passed"] is True
        assert "archived" in result["test_file"]

    def test_verification_state_persistence(self, temp_regression_dir):
        """Test verification state is saved and loaded correctly."""
        verifier = BugFixVerifier("test_token", "owner/repo", temp_regression_dir)

        # Save state
        state = {
            "issue_123": {
                "bug_id": "abc123de",
                "consecutive_passes": 1,
                "last_passed": datetime.utcnow().isoformat()
            }
        }
        verifier._save_verification_state(state)

        # Load state
        loaded_state = verifier._load_verification_state()

        assert loaded_state == state

    @patch.object(BugFixVerifier, '_create_issue_comment')
    @patch.object(BugFixVerifier, '_close_issue')
    def test_close_issue_with_success(self, mock_close, mock_comment, temp_regression_dir):
        """Test _close_issue_with_success creates comment and closes issue."""
        verifier = BugFixVerifier("test_token", "owner/repo", temp_regression_dir)

        issue = {"number": 123, "title": "Bug fixed"}
        test_result = {"passed": True, "output": "PASSED", "duration_seconds": 1.5}

        verifier._close_issue_with_success(issue, "abc123de", test_result, consecutive_passes=2)

        assert mock_comment.called
        assert mock_close.called


class TestIntegrationWithBugFilingService:
    """Test integration with BugFilingService patterns."""

    def test_uses_same_github_api_patterns(self):
        """Test that BugFixVerifier uses same GitHub API patterns as BugFilingService."""
        from tests.bug_discovery.bug_filing_service import BugFilingService

        # Both should use requests.Session
        verifier = BugFixVerifier("test_token", "owner/repo")
        filer = BugFilingService("test_token", "owner/repo")

        assert hasattr(verifier, 'session')
        assert hasattr(filer, 'session')

        # Both should have Authorization header
        assert "Authorization" in verifier.session.headers
        assert "Authorization" in filer.session.headers
