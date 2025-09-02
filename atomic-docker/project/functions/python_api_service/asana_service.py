import asana
from typing import Dict, Any, Optional
from . import db_oauth_asana, crypto_utils

from .mcp_base import MCPBase

class AsanaService(MCPBase):
    def __init__(self, client: asana.Client):
        self.client = client

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
                # Asana's search is across a workspace, not a single project.
                # This is a simplified example.
                results = self.client.tasks.search_tasks_for_workspace(
                    self.client.workspaces.find_all()[0]['gid'],
                    {'text': query, 'projects.any': project_id}
                )
                files = [task for task in results]
                next_page_token = None # Simplified
            else:
                tasks = self.client.tasks.get_tasks_for_project(project_id, limit=page_size, offset=page_token)
                files = [task for task in tasks]
                next_page_token = tasks.next_page['offset'] if tasks.next_page else None

            return {"status": "success", "data": {"files": files, "nextPageToken": next_page_token}}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_file_metadata(
        self,
        file_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            task = self.client.tasks.get_task(file_id)
            return {"status": "success", "data": task}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def download_file(
        self,
        file_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        # Asana tasks don't have a direct "download" in the same way as file storage services.
        # This is a placeholder for what might be a more complex operation,
        # like getting attachments from a task.
        return {"status": "error", "message": "Download not directly supported for Asana tasks."}
