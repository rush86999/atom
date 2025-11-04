# Real Jira service implementation using jira package
# This provides real implementations for Jira API functionality

from typing import Dict, Any, Optional, List
import os
import logging
from jira import JIRA
from jira.exceptions import JIRAError

from mcp_base import MCPBase

logger = logging.getLogger(__name__)


class RealJiraService(MCPBase):
    def __init__(self, client: JIRA, cloud_id: Optional[str] = None):
        """Initialize real Jira client"""
        self.client = client
        self.cloud_id = cloud_id
        self.is_mock = False

    def list_files(
        self,
        project_id: str,
        query: Optional[str] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Get issues from a Jira project with optional search filtering"""
        try:
            # Build JQL query
            jql = f'project = "{project_id}"'
            if query:
                jql += f' AND text ~ "{query}"'

            # Handle pagination
            start_at = int(page_token) if page_token else 0

            # Search for issues
            issues = self.client.search_issues(
                jql_str=jql, startAt=start_at, maxResults=page_size
            )

            # Convert issues to dictionary format
            files = []
            for issue in issues:
                files.append(
                    {
                        "id": issue.id,
                        "key": issue.key,
                        "summary": issue.fields.summary,
                        "description": getattr(issue.fields, "description", None),
                        "status": getattr(issue.fields.status, "name", None)
                        if issue.fields.status
                        else None,
                        "assignee": getattr(issue.fields.assignee, "displayName", None)
                        if issue.fields.assignee
                        else None,
                        "reporter": getattr(issue.fields.reporter, "displayName", None)
                        if issue.fields.reporter
                        else None,
                        "created": issue.fields.created,
                        "updated": issue.fields.updated,
                        "priority": getattr(issue.fields.priority, "name", None)
                        if issue.fields.priority
                        else None,
                        "issuetype": getattr(issue.fields.issuetype, "name", None)
                        if issue.fields.issuetype
                        else None,
                        "url": issue.self,
                    }
                )

            # Calculate next page token
            next_page_token = (
                str(start_at + len(issues)) if len(issues) == page_size else None
            )

            return {
                "status": "success",
                "data": {"files": files, "nextPageToken": next_page_token},
            }

        except JIRAError as e:
            logger.error(f"JIRA API error: {e}")
            return {"status": "error", "message": f"JIRA API error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error listing Jira issues: {e}")
            return {"status": "error", "message": str(e)}

    def get_file_metadata(self, file_id: str, **kwargs) -> Dict[str, Any]:
        """Get metadata for a specific Jira issue"""
        try:
            issue = self.client.issue(file_id)

            metadata = {
                "id": issue.id,
                "key": issue.key,
                "summary": issue.fields.summary,
                "description": getattr(issue.fields, "description", None),
                "status": getattr(issue.fields.status, "name", None)
                if issue.fields.status
                else None,
                "assignee": getattr(issue.fields.assignee, "displayName", None)
                if issue.fields.assignee
                else None,
                "reporter": getattr(issue.fields.reporter, "displayName", None)
                if issue.fields.reporter
                else None,
                "created": issue.fields.created,
                "updated": issue.fields.updated,
                "priority": getattr(issue.fields.priority, "name", None)
                if issue.fields.priority
                else None,
                "issuetype": getattr(issue.fields.issuetype, "name", None)
                if issue.fields.issuetype
                else None,
                "labels": getattr(issue.fields, "labels", []),
                "components": [
                    comp.name for comp in getattr(issue.fields, "components", [])
                ],
                "url": issue.self,
            }

            return {"status": "success", "data": metadata}

        except JIRAError as e:
            logger.error(f"JIRA API error getting issue {file_id}: {e}")
            return {"status": "error", "message": f"JIRA API error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error getting Jira issue metadata: {e}")
            return {"status": "error", "message": str(e)}

    def download_file(self, file_id: str, **kwargs) -> Dict[str, Any]:
        """Download is not directly supported for Jira issues"""
        return {
            "status": "error",
            "message": "Download not directly supported for Jira issues. Use get_file_metadata to retrieve issue details.",
        }

    def create_issue(
        self,
        project_id: str,
        summary: str,
        description: str = "",
        issue_type: str = "Task",
        priority: str = "Medium",
        **kwargs,
    ) -> Dict[str, Any]:
        """Create a new Jira issue"""
        try:
            issue_dict = {
                "project": {"key": project_id},
                "summary": summary,
                "description": description,
                "issuetype": {"name": issue_type},
                "priority": {"name": priority},
            }

            new_issue = self.client.create_issue(fields=issue_dict)

            return {
                "status": "success",
                "data": {
                    "id": new_issue.id,
                    "key": new_issue.key,
                    "url": new_issue.self,
                },
            }

        except JIRAError as e:
            logger.error(f"JIRA API error creating issue: {e}")
            return {"status": "error", "message": f"JIRA API error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error creating Jira issue: {e}")
            return {"status": "error", "message": str(e)}

    def update_issue(
        self,
        issue_id: str,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Update an existing Jira issue"""
        try:
            issue = self.client.issue(issue_id)

            update_fields = {}
            if summary:
                update_fields["summary"] = summary
            if description:
                update_fields["description"] = description

            if update_fields:
                issue.update(fields=update_fields)

            if status:
                # Transition issue to new status
                transitions = self.client.transitions(issue)
                for transition in transitions:
                    if transition["name"].lower() == status.lower():
                        self.client.transition_issue(issue, transition["id"])
                        break

            return {
                "status": "success",
                "data": {"message": "Issue updated successfully"},
            }

        except JIRAError as e:
            logger.error(f"JIRA API error updating issue {issue_id}: {e}")
            return {"status": "error", "message": f"JIRA API error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error updating Jira issue: {e}")
            return {"status": "error", "message": str(e)}


# Function to get real Jira client
def get_real_jira_client(
    server: str, username: str = None, password: str = None, token: str = None
) -> JIRA:
    """Get real Jira client with authentication"""
    try:
        if token:
            # API token authentication
            client = JIRA(server=server, token_auth=token)
        elif username and password:
            # Basic authentication
            client = JIRA(server=server, basic_auth=(username, password))
        else:
            raise ValueError("Either token or username/password must be provided")

        return client

    except JIRAError as e:
        logger.error(f"Failed to create Jira client: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating Jira client: {e}")
        raise


# Function to get real Jira client with cloud ID
def get_real_jira_client_with_cloud_id(cloud_id: str, access_token: str) -> JIRA:
    """Get Jira client using cloud ID and OAuth token for Atlassian Cloud"""
    try:
        # Jira Cloud API base URL with cloud ID
        server_url = f"https://api.atlassian.com/ex/jira/{cloud_id}"
        client = JIRA(server=server_url, token_auth=access_token)
        logger.info(f"Created Jira client for cloud ID: {cloud_id}")
        return client
    except JIRAError as e:
        logger.error(f"Failed to create Jira client with cloud ID {cloud_id}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating Jira client with cloud ID: {e}")
        raise
