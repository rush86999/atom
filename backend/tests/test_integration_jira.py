"""
Jira Integration Tests (pytest)

Tests the real JiraService in integrations/jira_service.py by mocking its
HTTP seam (_make_request). Covers issue create/update/transition/comment,
JQL search, error handling, and the execute_operation dispatch.
"""

import pytest
from unittest.mock import Mock, patch

from integrations.jira_service import JiraService


class FakeResponse:
    """Minimal requests.Response stand-in."""

    def __init__(self, status_code: int = 200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


@pytest.fixture
def jira_service():
    """Create a JiraService instance with OAuth config (skips SSRF guard)."""
    return JiraService(
        tenant_id="tenant-001",
        config={
            "access_token": "test-oauth-token",
            "cloud_id": "cloud-123",
        },
    )


@pytest.fixture
def mock_request(jira_service):
    """Mock the HTTP seam used by all JiraService methods."""
    with patch.object(jira_service, "_make_request") as mock_make:
        mock_make.return_value = FakeResponse()
        yield mock_make


class TestJiraIssueIntegration:
    """Test Jira issue management integration."""

    def test_create_jira_issue(self, jira_service, mock_request):
        """Test creating an issue in Jira."""
        mock_request.return_value = FakeResponse(payload={
            "key": "PROJ-123",
            "id": "12345",
            "fields": {
                "summary": "Fix login bug",
                "issuetype": {"name": "Bug"},
                "priority": {"name": "High"},
            },
        })

        result = jira_service.create_issue(
            project_key="PROJ",
            summary="Fix login bug",
            issue_type="Bug",
            description="Login flow crashes",
            priority="High",
        )

        assert result["key"] == "PROJ-123"
        assert result["fields"]["summary"] == "Fix login bug"

        # Verify the API call shape
        method, endpoint = mock_request.call_args.args[:2]
        assert method == "POST"
        assert endpoint == "/rest/api/3/issue"
        sent_json = mock_request.call_args.kwargs["json"]
        assert sent_json["fields"]["project"]["key"] == "PROJ"
        assert sent_json["fields"]["summary"] == "Fix login bug"
        assert sent_json["fields"]["priority"]["name"] == "High"

    def test_update_jira_issue(self, jira_service, mock_request):
        """Test updating an existing Jira issue."""
        result = jira_service.update_issue(
            "PROJ-123", {"fields": {"summary": "Updated summary"}}
        )

        assert result is True
        method, endpoint = mock_request.call_args.args[:2]
        assert method == "PUT"
        assert endpoint == "/rest/api/3/issue/PROJ-123"

    def test_transition_jira_issue(self, jira_service, mock_request):
        """Test transitioning Jira issue status by name."""
        def side_effect(method, endpoint, **kwargs):
            if "transitions" in endpoint:
                return FakeResponse(payload={
                    "transitions": [
                        {"id": "31", "name": "In Progress"},
                        {"id": "41", "name": "Done"},
                    ]
                })
            return FakeResponse()

        mock_request.side_effect = side_effect

        result = jira_service.transition_issue("PROJ-123", "In Progress")

        assert result is True
        # Second request should POST the resolved transition id
        calls = mock_request.call_args_list
        assert len(calls) == 2
        assert calls[0].args[:2] == ("GET", "/rest/api/3/issue/PROJ-123/transitions")
        assert calls[1].args[:2] == ("POST", "/rest/api/3/issue/PROJ-123/transitions")
        assert calls[1].kwargs["json"] == {"transition": {"id": "31"}}

    def test_transition_unknown_status_returns_false(self, jira_service, mock_request):
        """Test transitioning to an unknown status fails gracefully."""
        mock_request.return_value = FakeResponse(payload={"transitions": []})

        result = jira_service.transition_issue("PROJ-123", "Nope")

        assert result is False

    def test_add_comment_to_jira_issue(self, jira_service, mock_request):
        """Test adding a comment to Jira issue."""
        mock_request.return_value = FakeResponse(payload={
            "id": "comment-001",
            "body": "Issue resolved successfully",
        })

        result = jira_service.add_comment("PROJ-123", "Issue resolved successfully")

        assert result["id"] == "comment-001"
        method, endpoint = mock_request.call_args.args[:2]
        assert method == "POST"
        assert endpoint == "/rest/api/3/issue/PROJ-123/comment"

    def test_search_jira_issues(self, jira_service, mock_request):
        """Test searching for issues using JQL."""
        mock_request.return_value = FakeResponse(payload={
            "issues": [
                {"key": "PROJ-100", "fields": {"summary": "Issue 1"}},
                {"key": "PROJ-101", "fields": {"summary": "Issue 2"}},
            ],
            "total": 2,
        })

        result = jira_service.search_issues("project = PROJ AND status = Open")

        assert result["total"] == 2
        assert len(result["issues"]) == 2
        assert result["issues"][0]["key"] == "PROJ-100"
        method, endpoint = mock_request.call_args.args[:2]
        assert method == "GET"
        assert endpoint == "/rest/api/3/search"
        assert "jql" in mock_request.call_args.kwargs["params"]

    def test_jira_error_handling(self, jira_service, mock_request):
        """Test handling Jira API errors."""
        mock_request.return_value = FakeResponse(status_code=401, payload={})

        # create_issue returns None on API failure
        result = jira_service.create_issue("PROJ", "Summary", "Bug")
        assert result is None

        # update_issue returns False on API failure
        update_result = jira_service.update_issue("PROJ-123", {})
        assert update_result is False

    def test_connection_test_failure(self, jira_service):
        """Test connection check returns error dict on API failure."""
        with patch.object(
            jira_service.session, "get", return_value=FakeResponse(status_code=401)
        ):
            result = jira_service.test_connection()

        assert result["status"] == "error"
        assert result["authenticated"] is False


class TestJiraExecuteOperation:
    """Test the execute_operation dispatch seam."""

    @pytest.mark.asyncio
    async def test_execute_operation_create_issue(self, jira_service, mock_request):
        """Test execute_operation dispatches to create_issue."""
        mock_request.return_value = FakeResponse(payload={"key": "PROJ-1"})

        result = await jira_service.execute_operation(
            "create_issue",
            {
                "project_key": "PROJ",
                "summary": "From gateway",
                "issue_type": "Task",
            },
            context={"tenant_id": "tenant-001"},
        )

        assert result["success"] is True
        assert result["result"]["key"] == "PROJ-1"
        assert result["operation"] == "create_issue"

    @pytest.mark.asyncio
    async def test_execute_operation_tenant_mismatch_denied(self, jira_service, mock_request):
        """Test execute_operation rejects cross-tenant context."""
        result = await jira_service.execute_operation(
            "create_issue",
            {"project_key": "PROJ", "summary": "x", "issue_type": "Task"},
            context={"tenant_id": "other-tenant"},
        )

        assert result["success"] is False
        assert result["error"] == "Tenant ID mismatch"
        mock_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_operation_unknown_operation(self, jira_service, mock_request):
        """Test execute_operation rejects unknown operations."""
        result = await jira_service.execute_operation("delete_everything", {})

        assert result["success"] is False
        assert "Unknown operation" in result["error"]
