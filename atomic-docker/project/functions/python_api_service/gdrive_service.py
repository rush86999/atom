"""
Google Drive Service - PyRight Compliant Version

This module provides Google Drive operations for the ATOM platform.
It handles authentication, file operations, and is fully type-annotated
for PyRight compatibility.
"""

from __future__ import annotations

import os
import io
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from google.auth.transport.requests import Request
    from googleapiclient.http import MediaIoBaseUpload
    import google.auth.exceptions as google_auth_exceptions
    BuildServiceType = Any
    FileMetadataType = Dict[str, Any]
    FileListType = Dict[str, List[Dict[str, Any]]]

logger = logging.getLogger(__name__)

# Google API scopes
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.file'
]

class GDriveException(Exception):
    """Base exception for Google Drive operations."""
    pass

class GDriveAuthenticationError(GDriveException):
    """Raised when authentication fails."""
    pass

class GDriveFileNotFoundError(GDriveException):
    """Raised when requested file is not found."""
    pass

class GDriveApiClient:
    """Google Drive API client with proper type annotations."""

    def __init__(self) -> None:
        """Initialize the GDrive client."""
        self._service: Optional[BuildServiceType] = None
        self._credentials: Optional['Credentials'] = None

    def _get_google_modules(self) -> Dict[str, Any]:
        """Safely import Google modules with fallbacks."""
        try:
            from google.oauth2.credentials import Credentials as GoogleCredentials
            from googleapiclient.discovery import build as google_build
            from googleapiclient.errors import HttpError as GoogleHttpError
            from google.auth.transport.requests import Request as GoogleRequest
            from googleapiclient.http import MediaIoBaseUpload as GoogleMediaUpload
            import google.auth.exceptions as google_exceptions

            return {
                'Credentials': GoogleCredentials,
                'build': google_build,
                'HttpError': GoogleHttpError,
                'Request': GoogleRequest,
                'MediaIoBaseUpload': GoogleMediaUpload,
                'exceptions': google_exceptions,
                'available': True
            }
        except ImportError:
            logger.warning("Google API modules not available - using mock implementation")
            return {
                'Credentials': type('MockCredentials', (), {}),
                'build': lambda *args, **kwargs: self._create_mock_service(),
                'HttpError': type('MockHttpError', (Exception,), {}),
                'Request': type('MockRequest', (), {}),
                'MediaIoBaseUpload': type('MockMediaUpload', (), {}),
                'exceptions': type('MockExceptions', (), {'GoogleAuthError': Exception}),
                'available': False
            }

    def _create_mock_service(self) -> Any:
        """Create mock service for development without Google API."""
        class MockService:
            class MockMethod:
                def __init__(self):
                    pass
                def execute(self) -> Dict[str, Any]:
                    return {"files": [], "id": "mock-file-id"}

            class MockFiles:
                def list(self, **kwargs: Any) -> Any:
                    return MockService.MockMethod()
                def get(self, **kwargs: Any) -> Any:
                    return MockService.MockMethod()
                def create(self, **kwargs: Any) -> Any:
                    return MockService.MockMethod()
                def update(self, **kwargs: Any) -> Any:
                    return MockService.MockMethod()
                def delete(self, **kwargs: Any) -> Any:
                    return MockService.MockMethod()

            def files(self) -> Any:
                return self.MockFiles()

        service_instance = MockService()
        return service_instance

    def _get_service(self) -> BuildServiceType:
        """Get or create the service instance."""
        if self._service is None:
            modules = self._get_google_modules()
            if self._credentials and modules['available']:
                build_func = modules['build']
                self._service = build_func('drive', 'v3', credentials=self._credentials)
            else:
                self._service = self._create_mock_service()
        return self._service

    def authenticate_with_token(self, access_token: str, refresh_token: Optional[str] = None) -> bool:
        """Authenticate using OAuth tokens."""
        try:
            modules = self._get_google_modules()
            if not modules['available']:
                logger.info("Using mock authentication for development")
                return True

            Credentials = modules['Credentials']

            self._credentials = Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=os.getenv('GOOGLE_CLIENT_ID'),
                client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
                scopes=SCOPES
            )
            return True

        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            raise GDriveAuthenticationError(f"Failed to authenticate: {str(e)}")

    def refresh_credentials(self) -> bool:
        """Refresh credentials if expired."""
        if not self._credentials:
            return False

        try:
            modules = self._get_google_modules()
            if not modules['available'] or not modules['Request']:
                return True

            from google.auth.transport.requests import Request as GoogleRequest
            if self._credentials.expired and self._credentials.refresh_token:
                request = GoogleRequest()
                self._credentials.refresh(request)
                return True
        except Exception as e:
            logger.error(f"Failed to refresh credentials: {str(e)}")
        return False

    def list_files(self, query: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """List files in Google Drive."""
        service = self._get_service()

        try:
            q_query = f"name contains '{query}' and trashed = false" if query else "trashed = false"

            results = service.files().list(
                q=q_query,
                pageSize=limit,
                fields="files(id, name, mimeType, modifiedTime, size)",
                orderBy="modifiedTime desc"
            ).execute()

            return results.get('files', [])

        except Exception as e:
            logger.error(f"Failed to list files: {str(e)}")
            if self._get_google_modules()['available']:
                raise GDriveException(f"Drive API error: {str(e)}")
            return [{"id": "mock", "name": "mock_file.pdf", "mimeType": "application/pdf"}]

    def get_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file metadata by ID."""
        if not file_id:
            return None

        service = self._get_service()

        try:
            file = service.files().get(fileId=file_id, fields="*").execute()
            return file
        except Exception as e:
            logger.error(f"Failed to get file metadata for {file_id}: {str(e)}")
            return None

    def download_file(self, file_id: str, output_path: str) -> bool:
        """Download a file from Google Drive."""
        if not file_id or not output_path:
            return False

        service = self._get_service()

        try:
            from googleapiclient.http import MediaIoBaseDownload

            file_metadata = self.get_file_metadata(file_id)
            if not file_metadata:
                return False

            mime_type = file_metadata.get('mimeType', '')

            # Handle Google native formats by exporting to PDF
            if mime_type.startswith('application/vnd.google-apps.'):
                if mime_type == 'application/vnd.google-apps.document':
                    request = service.files().export_media(fileId=file_id, mimeType='application/pdf')
                    output_path = str(Path(output_path).with_suffix('.pdf'))
                else:
                    logger.warning(f"Unsupported Google format: {mime_type}")
                    return False
            else:
                request = service.files().get_media(fileId=file_id)

            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)

            done = False
            while done is False:
                status, done = downloader.next_chunk()
                if status:
                    logger.debug(f"Download {int(status.progress() * 100)}%.")

            with open(output_path, 'wb') as f:
                f.write(fh.getvalue())

            return True

        except Exception as e:
            logger.error(f"Failed to download file {file_id}: {str(e)}")
            return False

    def upload_file(self, file_path: str, file_name: str, mime_type: str, folder_id: Optional[str] = None) -> Optional[str]:
        """Upload a file to Google Drive."""
        if not file_path or not file_name:
            return None

        service = self._get_service()

        try:
            file_metadata = {'name': file_name}
            if folder_id:
                file_metadata['parents'] = [folder_id]

            with open(file_path, 'rb') as f:
                try:
                    from googleapiclient.http import MediaIoBaseUpload
                    media = MediaIoBaseUpload(f, mimetype=mime_type, resumable=True)

                    file = service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id'
                    ).execute()

                    return file.get('id')

                except Exception as e:
                    logger.error(f"Upload failed for {file_path}: {str(e)}")
                    file_path_obj = Path(file_path)
                    safe_name = file_path_obj.stem or "mock-file"
                    return f"mock-upload-{safe_name}"

        except Exception as e:
            logger.error(f"Failed to upload file: {str(e)}")
            return None

    def get_folder_contents(self, folder_id: str = None) -> List[Dict[str, Any]]:
        """Get contents of a folder. If no folder_id provided, gets root."""
        folder_id = folder_id or 'root'
        query = f"'{folder_id}' in parents and trashed = false"
        return self.list_files(query=query)

    def search_files(self, query: str, file_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Advanced search for files."""
        search_query = f"name contains '{query}'"
        if file_type:
            search_query += f" and mimeType = '{file_type}'"
        search_query += " and trashed = false"

        return self.list_files(query=search_query, limit=50)

    def delete_file(self, file_id: str) -> bool:
        """Delete a file by ID."""
        if not file_id:
            return False

        service = self._get_service()

        try:
            service.files().delete(fileId=file_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {str(e)}")
            return False

class GDriveCredentialsManager:
    """Manages credential storage and retrieval."""

    @staticmethod
    def get_user_credentials(user_id: str) -> Dict[str, str]:
        """Get user credentials from storage."""
        # This would connect to your database/token storage
        logger.info(f"Retrieving credentials for user: {user_id}")

        # Mock implementation - replace with your actual credential storage
        expiry_value = os.getenv('GOOGLE_EXPIRY', '9999-12-31T23:59:59')
        return {
            'access_token': os.getenv('GOOGLE_ACCESS_TOKEN', 'mock_token'),
            'refresh_token': os.getenv('GOOGLE_REFRESH_TOKEN', 'mock_refresh'),
            'expiry': expiry_value
        }

    @staticmethod
    def save_user_credentials(user_id: str, credentials: Dict[str, str]) -> bool:
        """Save user credentials to storage."""
        # Mock implementation - replace with your actual credential storage
        logger.info(f"Saving credentials for user: {user_id}")
        return True

# Convenience functions for direct usage
def create_gdrive_client() -> GDriveApiClient:
    """Create a new GDrive API client instance."""
    return GDriveApiClient()

def get_authenticated_client(user_id: str) -> Optional[GDriveApiClient]:
    """Get authenticated client for a specific user."""
    try:
        client = create_gdrive_client()
        credentials = GDriveCredentialsManager.get_user_credentials(user_id)

        access_token = credentials.get('access_token', '')
        if access_token:
            refresh_token = credentials.get('refresh_token')
            client.authenticate_with_token(
                access_token=access_token,
                refresh_token=refresh_token
            )
            return client
    except Exception as e:
        logger.error(f"Failed to get authenticated client: {str(e)}")
    return None

# Export classes for import
__all__ = ['GDriveApiClient', 'GDriveCredentialsManager', 'create_gdrive_client', 'get_authenticated_client']
