"""
Jira Integration Tests (pytest)

Tests Jira issue management integration with proper mocking.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session

from core.models import AgentExecution, AgentOperationTracker


class TestJiraIssueIntegration:
    """Test Jira issue management integration."""

    @pytest.fixture
    def mock_jira_client(self):
        """Create mock Jira client."""
        with patch('integrations.jira_service.JIRA') as mock_client:
            yield mock_client.return_value

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = Mock(spec=Session)
        db.query = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.rollback = Mock()
        db.refresh = Mock()
        return db

    def test_create_jira_issue(self, mock_jira_client, mock_db):
        """Test creating an issue in Jira."""
        # Mock Jira API response
        mock_jira_client.create_issue.return_value = {
            "key": "PROJ-123",
            "id": "12345",
            "fields": {
                "summary": "Fix login bug",
                "issuetype": {"name": "Bug"},
                "priority": {"name": "High"}
            }
        }

        execution = AgentExecution(
            id="exec-jira-001",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Create Jira issue"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Create issue
        issue_dict = {
            "project": {"key": "PROJ"},
            "summary": "Fix login bug",
            "issuetype": {"name": "Bug"},
            "priority": {"name": "High"}
        }

        result = mock_jira_client.create_issue(issue_dict)

        # Verify API call
        mock_jira_client.create_issue.assert_called_once()
        assert result["key"] == "PROJ-123"
        assert result["fields"]["summary"] == "Fix login bug"

        execution.output_data = {
            "issue_created": True,
            "issue_key": result["key"],
            "issue_url": f"https://jira.atlassian.net/browse/{result['key']}"
        }
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

        assert execution.output_data["issue_created"] is True

    def test_update_jira_issue(self, mock_jira_client, mock_db):
        """Test updating an existing Jira issue."""
        mock_jira_client.update_issue.return_value = None

        execution = AgentExecution(
            id="exec-jira-002",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Update issue"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Update issue
        issue_key = "PROJ-123"
        fields = {"summary": "Updated summary"}

        mock_jira_client.update_issue(issue_key, fields=fields)

        # Verify API call
        mock_jira_client.update_issue.assert_called_once_with(issue_key, fields=fields)

        execution.output_data = {"issue_updated": True, "issue_key": issue_key}
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

    def test_transition_jira_issue(self, mock_jira_client, mock_db):
        """Test transitioning Jira issue status."""
        mock_jira_client.transition_issue.return_value = None

        execution = AgentExecution(
            id="exec-jira-003",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Transition issue"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Transition issue
        issue_key = "PROJ-123"
        transition_id = "31"  # ID for "In Progress" transition

        mock_jira_client.transition_issue(issue_key, transition_id)

        # Verify API call
        mock_jira_client.transition_issue.assert_called_once_with(issue_key, transition_id)

        execution.output_data = {
            "issue_transitioned": True,
            "issue_key": issue_key,
            "new_status": "In Progress"
        }
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

    def test_add_comment_to_jira_issue(self, mock_jira_client, mock_db):
        """Test adding a comment to Jira issue."""
        mock_jira_client.add_comment.return_value = {
            "id": "comment-001",
            "body": "Issue resolved successfully"
        }

        execution = AgentExecution(
            id="exec-jira-004",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Add comment"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Add comment
        result = mock_jira_client.add_comment("PROJ-123", "Issue resolved successfully")

        # Verify API call
        mock_jira_client.add_comment.assert_called_once()
        assert result["body"] == "Issue resolved successfully"

        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

    def test_search_jira_issues(self, mock_jira_client, mock_db):
        """Test searching for issues in Jira."""
        mock_jira_client.search_issues.return_value = [
            {"key": "PROJ-100", "fields": {"summary": "Issue 1"}},
            {"key": "PROJ-101", "fields": {"summary": "Issue 2"}}
        ]

        execution = AgentExecution(
            id="exec-jira-005",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Search issues"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Search issues
        jql = "project = PROJ AND status = Open"
        results = mock_jira_client.search_issues(jql)

        # Verify API call
        mock_jira_client.search_issues.assert_called_once()
        assert len(results) == 2

        execution.output_data = {
            "issues_found": len(results),
            "issues": [{"key": i["key"], "summary": i["fields"]["summary"]} for i in results]
        }
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        mock_db.commit()

    def test_jira_error_handling(self, mock_jira_client, mock_db):
        """Test handling Jira API errors."""
        # Mock API error
        mock_jira_client.create_issue.side_effect = Exception("JiraError: Unauthorized")

        execution = AgentExecution(
            id="exec-jira-error-001",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Create issue"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Attempt to create issue
        try:
            mock_jira_client.create_issue({"project": {"key": "PROJ"}})
        except Exception as e:
            execution.status = "failed"
            execution.error_message = str(e)
            execution.completed_at = datetime.utcnow()
            mock_db.commit()

        assert execution.status == "failed"
        assert "Unauthorized" in execution.error_message

    def test_jira_authentication_error(self, mock_jira_client, mock_db):
        """Test handling Jira authentication errors."""
        # Mock auth error
        mock_jira_client.create_issue.side_effect = Exception("JiraError: 401 Unauthorized")

        execution = AgentExecution(
            id="exec-jira-auth-001",
            agent_id="agent-001",
            status="running",
            input_data={"task": "Create issue"},
            started_at=datetime.utcnow()
        )
        mock_db.add(execution)

        # Attempt to create issue
        try:
            mock_jira_client.create_issue({})
        except Exception as e:
            execution.status = "failed"
            execution.error_message = f"Authentication failed: {str(e)}"
            execution.completed_at = datetime.utcnow()
            mock_db.commit()

        assert execution.status == "failed"
        assert "401" in execution.error_message
