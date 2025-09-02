from boxsdk import Client, OAuth2
from typing import Dict, Any, Optional
from . import db_oauth_box, crypto_utils

from .mcp_base import MCPBase

class BoxService(MCPBase):
    def __init__(self, oauth: OAuth2):
        self.client = Client(oauth)

    def list_files(
        self,
        folder_id: str = '0',
        query: Optional[str] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            if query:
                # Box API search is a bit different, it's a global search.
                # We can't limit it to a folder_id in the same way.
                results = self.client.search().query(query=query, limit=page_size, offset=int(page_token) if page_token else 0)
                files = [item for item in results]
                next_page_token = str(int(page_token or '0') + len(files)) if len(files) == page_size else None
            else:
                items = self.client.folder(folder_id=folder_id).get_items(limit=page_size, offset=int(page_token) if page_token else 0)
                files = [item for item in items]
                next_page_token = str(int(page_token or '0') + len(files)) if len(files) == page_size else None

            return {"status": "success", "data": {"files": files, "nextPageToken": next_page_token}}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_file_metadata(
        self,
        file_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            file_info = self.client.file(file_id).get()
            return {"status": "success", "data": file_info}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def download_file(
        self,
        file_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            file_info = self.client.file(file_id).get()
            file_content = self.client.file(file_id).content()
            return {"status": "success", "data": {"file_name": file_info.name, "content_bytes": file_content, "mime_type": file_info.extension}}
        except Exception as e:
            return {"status": "error", "message": str(e)}
