from jira import JIRA
from typing import Dict, Any, Optional

from .mcp_base import MCPBase

class JiraService(MCPBase):
    def __init__(self, server_url: str, username: str, api_token: str):
        self.client = JIRA(server=server_url, basic_auth=(username, api_token))

    def list_files(
        self,
        project_id: str,
        query: Optional[str] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            if query:
                jql = f'project = "{project_id}" AND text ~ "{query}"'
            else:
                jql = f'project = "{project_id}"'

            start_at = int(page_token) if page_token else 0
            issues = self.client.search_issues(jql, startAt=start_at, maxResults=page_size)

            next_page_token = str(start_at + len(issues)) if len(issues) == page_size else None

            return {"status": "success", "data": {"files": [issue.raw for issue in issues], "nextPageToken": next_page_token}}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_file_metadata(
        self,
        file_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            issue = self.client.issue(file_id)
            return {"status": "success", "data": issue.raw}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def download_file(
        self,
        file_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        return {"status": "error", "message": "Download not directly supported for Jira issues."}
