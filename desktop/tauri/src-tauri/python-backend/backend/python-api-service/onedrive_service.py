import requests
from .mcp_base import MCPBase
from typing import Dict, Any, Optional

class OneDriveService(MCPBase):
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://graph.microsoft.com/v1.0/me/drive"

    def list_files(
        self,
        folder_id: Optional[str] = None,
        query: Optional[str] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.access_token}"}
        if query:
            url = f"{self.base_url}/root/search(q='{query}')"
        else:
            folder = folder_id or "root"
            url = f"{self.base_url}/items/{folder}/children"

        params = {"$top": page_size}
        if page_token:
            params["$skiptoken"] = page_token

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            files = data.get("value", [])
            next_page_token = data.get("@odata.nextLink")
            return {"status": "success", "data": {"files": files, "nextPageToken": next_page_token}}
        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": str(e)}

    def get_file_metadata(
        self,
        file_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.access_token}"}
        url = f"{self.base_url}/items/{file_id}"
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return {"status": "success", "data": response.json()}
        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": str(e)}

    def download_file(
        self,
        file_id: str,
        target_mime_type: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.access_token}"}
        url = f"{self.base_url}/items/{file_id}/content"
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            # The file name and mime type are not available in the response headers.
            # We need to make another request to get the metadata.
            metadata = self.get_file_metadata(file_id)
            if metadata["status"] == "error":
                return metadata
            file_name = metadata["data"]["name"]
            mime_type = metadata["data"]["file"]["mimeType"]
            return {"status": "success", "data": {"file_name": file_name, "content_bytes": response.content, "mime_type": mime_type}}
        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": str(e)}
