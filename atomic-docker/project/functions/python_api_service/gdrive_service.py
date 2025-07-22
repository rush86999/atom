import os
import logging
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime, timezone

# Mock Google API imports for local testing
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from google.auth.transport.requests import Request
except ImportError:
    # Mock Google credentials
    class Credentials:
        def __init__(self, token=None, refresh_token=None, token_uri=None, client_id=None, client_secret=None, scopes=None):
            self.token = token or 'mock_access_token'
            self.refresh_token = refresh_token or 'mock_refresh_token'
            self.token_uri = token_uri
            self.client_id = client_id
            self.client_secret = client_secret
            self.scopes = scopes or []
            self.expired = False
            self.expiry = None

        @classmethod
        def from_authorized_user_info(cls, info, scopes):
            return cls(
                token=info.get('token'),
                refresh_token=info.get('refresh_token'),
                token_uri=info.get('token_uri'),
                client_id=info.get('client_id'),
                client_secret=info.get('client_secret'),
                scopes=scopes
            )

        def refresh(self, request):
            # Mock refresh - just set expired to False
            self.expired = False
            self.token = 'mock_refreshed_token'

        def to_json(self):
            import json
            return json.dumps({
                'token': self.token,
                'refresh_token': self.refresh_token,
                'token_uri': self.token_uri,
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'scopes': self.scopes
            })

    # Mock Google API builder
    def build(service_name, version, credentials=None):
        if service_name == 'drive':
            return MockDriveService()
        return MockService()

    # Mock HttpError
    class HttpError(Exception):
        def __init__(self, resp, content, uri=None):
            self.resp = resp
            self.content = content
            self.uri = uri
            super().__init__(f"HttpError {resp.get('status', 'unknown')}")

    # Mock Request
    class Request:
        pass

    class MockCreateRequest:
        def __init__(self, body=None, media_body=None):
            self._body = body or {}
            self._media_body = media_body

        def execute(self):
            return {
                "id": "mock-created-file-id",
                "name": self._body.get("name", "Untitled"),
                "webViewLink": "https://docs.google.com/mock",
                "parents": self._body.get("parents", []),
            }

    # Mock Drive service
    class MockDriveService:
        def __init__(self):
            self.files_resource = MockFilesResource()

        def files(self):
            return self.files_resource

    class MockFilesResource:
        def list(self, **kwargs):
            return MockListRequest()

        def get(self, **kwargs):
            return MockGetRequest()

        def get_media(self, **kwargs):
            return MockMediaRequest()

        def export_media(self, fileId, mimeType):
            return MockMediaRequest()

        def create(self, body=None, media_body=None, fields='*'):
            return MockCreateRequest(body=body, media_body=media_body)

    class MockListRequest:
        def execute(self):
            return {
                'files': [
                    {
                        'id': 'mock_file_1',
                        'name': 'Mock Document 1.pdf',
                        'mimeType': 'application/pdf',
                        'modifiedTime': '2024-01-01T00:00:00Z'
                    },
                    {
                        'id': 'mock_file_2',
                        'name': 'Mock Spreadsheet.xlsx',
                        'mimeType': 'application/vnd.google-apps.spreadsheet',
                        'modifiedTime': '2024-01-02T00:00:00Z'
                    }
                ],
                'nextPageToken': None
            }

    class MockGetRequest:
        def execute(self):
            return {
                'id': 'mock_file_id',
                'name': 'Mock File',
                'mimeType': 'application/pdf',
                'modifiedTime': '2024-01-01T00:00:00Z'
            }

    class MockMediaRequest:
        def execute(self):
            return b'Mock file content'

    class MockService:
        def files(self):
            return MockFilesResource()

from .db_oauth_gdrive import get_token
from .crypto_utils import decrypt_data as decrypt_token, encrypt_data as encrypt_token

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

async def get_gdrive_credentials(user_id: str, db_conn_pool) -> Optional[Credentials]:
    """
    Retrieves and refreshes Google Drive credentials for a user.
    """
    encrypted_token_data = get_token(db_conn_pool, user_id)
    if not encrypted_token_data:
        return None

    try:
        # To refresh, the Credentials object needs client_id and client_secret.
        # These should be loaded from the environment, not stored in the DB.
        client_id = os.environ.get("GOOGLE_CLIENT_ID")
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
        token_uri = "https://oauth2.googleapis.com/token"

        access_token_encrypted = encrypted_token_data.get('access_token_encrypted')
        if not access_token_encrypted:
            logger.error(f"Encrypted access token not found for user {user_id}")
            return None
        decrypted_access_token = decrypt_token(access_token_encrypted)

        refresh_token_encrypted = encrypted_token_data.get('refresh_token_encrypted')
        decrypted_refresh_token = decrypt_token(refresh_token_encrypted) if refresh_token_encrypted else None

        creds = Credentials(
            token=decrypted_access_token,
            refresh_token=decrypted_refresh_token,
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret,
            scopes=encrypted_token_data.get('scopes_granted', '').split(','))

        # The `creds.expired` property checks the token expiry against current time.
        if creds.expired and creds.refresh_token:
            from .db_oauth_gdrive import update_gdrive_access_token

            creds.refresh(Request())

            if creds.token:
                new_encrypted_access_token = encrypt_token(creds.token)
                new_expiry_timestamp_ms = int(creds.expiry.timestamp() * 1000) if creds.expiry else None

                if new_encrypted_access_token and new_expiry_timestamp_ms:
                    update_gdrive_access_token(
                        db_conn_pool=db_conn_pool,
                        user_id=user_id,
                        new_encrypted_access_token=new_encrypted_access_token,
                        new_expiry_timestamp_ms=new_expiry_timestamp_ms
                    )

        return creds
    except Exception as e:
        logger.error(f"Failed to load or refresh Google credentials for user {user_id}: {e}", exc_info=True)
        return None

async def is_user_connected(user_id: str, db_conn_pool) -> bool:
    """
    Checks if a user has a valid, non-expired token.
    """
    creds = await get_gdrive_credentials(user_id, db_conn_pool)
    return creds is not None and not creds.expired


async def search_files(creds: Credentials, query: str) -> Optional[Dict[str, Any]]:
    """
    Searches for files in Google Drive.
    """
    try:
        service = build('drive', 'v3', credentials=creds)
        results = service.files().list(
            q=f"name contains '{query}'",
            pageSize=20,
            fields="nextPageToken, files(id, name, webViewLink, mimeType, modifiedTime)"
        ).execute()
        return results
    except HttpError as e:
        logger.error(f"Google Drive API error during search: {e}", exc_info=True)
        return None


async def list_files(creds: Credentials, folder_id: Optional[str] = None, query: Optional[str] = None, page_size: int = 50, page_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Lists files in a specific folder or matching a query.
    """
    try:
        service = build('drive', 'v3', credentials=creds)
        q_parts = []
        if folder_id:
            q_parts.append(f"'{folder_id}' in parents")
        if query:
            q_parts.append(query)

        q_string = " and ".join(q_parts)

        results = service.files().list(
            q=q_string,
            pageSize=page_size,
            pageToken=page_token,
            fields="nextPageToken, files(id, name, mimeType, modifiedTime, webViewLink, parents, capabilities, exportLinks, shortcutDetails)"
        ).execute()
        return results
    except HttpError as e:
        logger.error(f"Google Drive API error during list_files: {e}", exc_info=True)
        return None

async def get_file_metadata(creds: Credentials, file_id: str, fields: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieves metadata for a single file.
    """
    try:
        service = build('drive', 'v3', credentials=creds)
        file_metadata = service.files().get(fileId=file_id, fields=fields or "*").execute()
        return file_metadata
    except HttpError as e:
        logger.error(f"Google Drive API error getting metadata for file {file_id}: {e}", exc_info=True)
        return None

async def download_file(creds: Credentials, file_id: str) -> Optional[Tuple[bytes, Dict[str, Any]]]:
    """
    Downloads a file from Google Drive, handling Google Docs/Sheets/Slides by exporting.
    """
    try:
        service = build('drive', 'v3', credentials=creds)

        # First, get file metadata to check its type
        metadata = await get_file_metadata(creds, file_id, "mimeType, name, exportLinks")
        if not metadata:
            return None

        mime_type = metadata.get('mimeType')
        request = None

        # If it's a Google Doc, Sheet, or Slide, we need to export it
        if mime_type and 'google-apps' in mime_type:
            export_links = metadata.get('exportLinks') or {}
            # Prefer PDF for export, but fall back to other types if necessary
            if 'application/pdf' in export_links:
                request = service.files().export_media(fileId=file_id, mimeType='application/pdf')
                metadata['mimeType'] = 'application/pdf' # Update mimeType to reflect the downloaded content
            elif 'text/plain' in export_links:
                 request = service.files().export_media(fileId=file_id, mimeType='text/plain')
                 metadata['mimeType'] = 'text/plain'
            else: # Add other fallbacks if needed e.g., for sheets
                logger.warning(f"Could not find a suitable export format for GDrive file {file_id} of type {mime_type}")
                return None
        else: # For binary files, use the standard download method
            request = service.files().get_media(fileId=file_id)

        if request:
            file_content = request.execute()
            return file_content, metadata

        return None

    except HttpError as e:
        logger.error(f"Google Drive API error downloading file {file_id}: {e}", exc_info=True)
        return None

async def create_file(creds: Credentials, file_metadata: Dict[str, Any], file_content: Optional[bytes] = None) -> Optional[Dict[str, Any]]:
    """
    Creates a file or folder in Google Drive.
    """
    try:
        service = build('drive', 'v3', credentials=creds)

        if file_content:
            # Mock MediaIoUploader for local testing
            try:
                from googleapiclient.http import MediaIoUploader
            except ImportError:
                class MediaIoUploader:
                    def __init__(self, *args, **kwargs):
                        pass
            import io

            fh = io.BytesIO(file_content)
            media = MediaIoUploader(fh, chunksize=1024*1024, resumable=True)
            file = service.files().create(body=file_metadata, media_body=media, fields='id, name, webViewLink, parents').execute()
        else:
            file = service.files().create(body=file_metadata, fields='id, name, webViewLink, parents').execute()

        return file
    except HttpError as e:
        logger.error(f"Google Drive API error creating file: {e}", exc_info=True)
        return None

async def get_file(creds: Credentials, file_id: str) -> Optional[Dict[str, Any]]:
    """
    Gets a file's metadata.
    """
    try:
        service = build('drive', 'v3', credentials=creds)
        file = service.files().get(fileId=file_id, fields='id, name, webViewLink, parents').execute()
        return file
    except HttpError as e:
        logger.error(f"Google Drive API error getting file: {e}", exc_info=True)
        return None
