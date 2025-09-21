"""
Mock Box Service for Development

This module provides a mock implementation of the Box service for development
and testing when the real boxsdk is not available or has compatibility issues.
"""

from typing import Dict, Any, Optional, List
import datetime

class MockOAuth2:
    """Mock OAuth2 class for Box authentication"""
    def __init__(self, access_token: str = "mock_access_token"):
        self.access_token = access_token

class MockClient:
    """Mock Box Client class"""
    def __init__(self, oauth: MockOAuth2):
        self.oauth = oauth
        self.files = MockFilesManager()
        self.folders = MockFoldersManager()

class MockFilesManager:
    """Mock Files Manager"""
    def get(self, file_id: str) -> Dict[str, Any]:
        return {
            "id": file_id,
            "name": f"Mock File {file_id}",
            "size": 1024,
            "modified_at": datetime.datetime.now().isoformat(),
            "type": "file"
        }

class MockFoldersManager:
    """Mock Folders Manager"""
    def get(self, folder_id: str, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        return {
            "id": folder_id,
            "name": f"Mock Folder {folder_id}",
            "item_collection": {
                "entries": [
                    {
                        "id": "file_1",
                        "name": "document.pdf",
                        "type": "file",
                        "size": 2048,
                        "modified_at": datetime.datetime.now().isoformat()
                    },
                    {
                        "id": "file_2",
                        "name": "spreadsheet.xlsx",
                        "type": "file",
                        "size": 4096,
                        "modified_at": datetime.datetime.now().isoformat()
                    }
                ],
                "total_count": 2
            }
        }

class BoxService:
    """Mock Box Service implementation"""
    def __init__(self, oauth: MockOAuth2):
        self.client = MockClient(oauth)

    def list_files(
        self,
        folder_id: str = '0',
        query: Optional[str] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Mock list files implementation"""

        # Simulate some delay for realism
        import time
        time.sleep(0.1)

        # Generate mock files based on query
        files = []
        if query and "document" in query.lower():
            files = [
                {
                    "id": "doc_1",
                    "name": "Important Document.pdf",
                    "size": 1536,
                    "modified_at": "2025-09-15T10:30:00Z",
                    "type": "file"
                }
            ]
        elif query and "spreadsheet" in query.lower():
            files = [
                {
                    "id": "sheet_1",
                    "name": "Financial Report.xlsx",
                    "size": 3072,
                    "modified_at": "2025-09-14T14:45:00Z",
                    "type": "file"
                }
            ]
        else:
            files = [
                {
                    "id": "file_001",
                    "name": "Project Plan.docx",
                    "size": 2048,
                    "modified_at": "2025-09-13T09:15:00Z",
                    "type": "file"
                },
                {
                    "id": "file_002",
                    "name": "Budget Spreadsheet.xlsx",
                    "size": 4096,
                    "modified_at": "2025-09-12T16:20:00Z",
                    "type": "file"
                },
                {
                    "id": "file_003",
                    "name": "Meeting Notes.pdf",
                    "size": 1024,
                    "modified_at": "2025-09-11T11:30:00Z",
                    "type": "file"
                }
            ]

        # Apply pagination
        if page_token:
            # Simulate pagination token
            files = files[1:] if len(files) > 1 else files

        return {
            "entries": files[:page_size],
            "total_count": len(files),
            "limit": page_size,
            "offset": 0
        }

    def get_file_content(self, file_id: str) -> Dict[str, Any]:
        """Mock get file content implementation"""
        return {
            "id": file_id,
            "name": f"File_{file_id}.txt",
            "content": f"This is mock content for file {file_id}. In a real implementation, this would be the actual file content.",
            "size": len(f"This is mock content for file {file_id}. In a real implementation, this would be the actual file content."),
            "download_url": f"https://mock.box.com/files/{file_id}/content"
        }

    def upload_file(self, folder_id: str, file_name: str, file_content: bytes) -> Dict[str, Any]:
        """Mock upload file implementation"""
        return {
            "id": f"uploaded_{hash(file_name)}",
            "name": file_name,
            "size": len(file_content),
            "modified_at": datetime.datetime.now().isoformat(),
            "parent": {"id": folder_id},
            "type": "file"
        }

    def get_service_status(self) -> Dict[str, Any]:
        """Get mock service status"""
        return {
            "status": "mock_mode",
            "message": "Box service running in mock mode for development",
            "available": True,
            "mock_data": True
        }

# Create mock instances for easy import
mock_oauth = MockOAuth2()
mock_client = MockClient(mock_oauth)
mock_service = BoxService(mock_oauth)
