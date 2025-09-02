import dropbox
from .mcp_base import MCPBase
from typing import Dict, Any, Optional

class DropboxService(MCPBase):
    def __init__(self, access_token: str):
        self.dbx = dropbox.Dropbox(access_token)

    def list_files(
        self,
        folder_id: Optional[str] = None,
        query: Optional[str] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            if query:
                result = self.dbx.files_search_v2(query, options=dropbox.files.SearchOptions(path=folder_id, max_results=page_size), start=page_token)
                files = [entry.metadata.get_metadata() for entry in result.matches]
                next_page_token = result.start + len(result.matches) if result.has_more else None
            else:
                path = folder_id if folder_id else ''
                result = self.dbx.files_list_folder(path, limit=page_size)
                files = [entry for entry in result.entries]
                next_page_token = result.cursor if result.has_more else None

            return {"status": "success", "data": {"files": files, "nextPageToken": next_page_token}}
        except dropbox.exceptions.ApiError as e:
            return {"status": "error", "message": str(e)}

    def get_file_metadata(
        self,
        file_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            metadata = self.dbx.files_get_metadata(file_id)
            return {"status": "success", "data": metadata}
        except dropbox.exceptions.ApiError as e:
            return {"status": "error", "message": str(e)}

    def download_file(
        self,
        file_id: str,
        target_mime_type: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            metadata, res = self.dbx.files_download(file_id)
            return {"status": "success", "data": {"file_name": metadata.name, "content_bytes": res.content, "mime_type": metadata.media_info}}
        except dropbox.exceptions.ApiError as e:
            return {"status": "error", "message": str(e)}
