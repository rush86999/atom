import os
import io
import logging
from typing import Optional, Tuple, Dict, Any, List, TYPE_CHECKING

# This is the standard way to handle imports for type checking vs. runtime.
# The 'if TYPE_CHECKING:' block is read by type checkers, but not executed at runtime.
# This prevents ImportError if the libraries are not installed, while still allowing type hints.
if TYPE_CHECKING:
    from google.oauth2.credentials import Credentials
    from googleapiclient.errors import HttpError
    from google.auth.transport.requests import Request
    from googleapiclient.http import MediaIoUploader


# --- Runtime Imports and Mock Fallbacks ---
# We attempt to import the actual libraries. If they aren't installed,
# we define mock classes with the same names to ensure the application can run.
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from google.auth.transport.requests import Request
    from googleapiclient.http import MediaIoUploader
    logging.info("Successfully imported Google API libraries.")
except ImportError:
    logging.warning("Google API libraries not found. Using mock implementation.")

    # --- MOCK IMPLEMENTATIONS ---
    # These classes simulate the behavior of the Google libraries for local development.

    class MockHttpError(Exception):
        """Mocks googleapiclient.errors.HttpError."""
        def __init__(self, resp, content, uri=None):
            self.resp = resp
            self.content = content
            self.uri = uri
            super().__init__(f"HttpError {resp.get('status', 'unknown')}")

    class MockRequest:
        """Mocks google.auth.transport.requests.Request."""
        pass

    class MockMediaIoUploader:
        """Mocks googleapiclient.http.MediaIoUploader."""
        def __init__(self, fd, mimetype, chunksize, resumable):
            pass

    class MockCredentials:
        """Mocks google.oauth2.credentials.Credentials."""
        def __init__(self, token=None, refresh_token=None, token_uri=None, client_id=None, client_secret=None, scopes=None, expiry=None):
            self.token = token or 'mock_access_token'
            self.refresh_token = refresh_token or 'mock_refresh_token'
            self.expired = False
            self.expiry = expiry

        def refresh(self, request: "MockRequest"):
            from datetime import datetime, timedelta
            self.token = 'mock_refreshed_token'
            self.expiry = datetime.utcnow() + timedelta(hours=1)
            self.expired = False

    # --- Mock Service and Resource Objects ---
    class _MockExecute:
        def execute(self) -> Any:
            raise NotImplementedError

    class _MockFileListRequest(_MockExecute):
        def execute(self) -> Dict[str, List[Dict[str, Any]]]:
            return {'files': [{'id': 'mock_id_1', 'name': 'MockFile1.pdf'}]}

    class _MockFileGetRequest(_MockExecute):
        def __init__(self, fileId: str, fields: str):
            self._fileId = fileId
        def execute(self) -> Dict[str, Any]:
            return {'id': self._fileId, 'name': 'Mock File', 'mimeType': 'application/pdf', 'exportLinks': {'application/pdf': 'http://mock'}}

    class _MockFileMediaRequest(_MockExecute):
        def execute(self) -> bytes:
            return b"mock file content"

    class _MockFileCreateRequest(_MockExecute):
        def __init__(self, body: Dict, media_body: Any):
            self._body = body
        def execute(self) -> Dict[str, Any]:
            return {'id': 'mock-created-file-id', 'name': self._body.get('name', 'Untitled')}

    class _MockFilesResource:
        def list(self, **kwargs) -> _MockFileListRequest: return _MockFileListRequest()
        def get(self, fileId: str, fields: str) -> _MockFileGetRequest: return _MockFileGetRequest(fileId, fields)
        def get_media(self, fileId: str) -> _MockFileMediaRequest: return _MockFileMediaRequest()
        def export_media(self, fileId: str, mimeType: str) -> _MockFileMediaRequest: return _MockFileMediaRequest()
        def create(self, **kwargs) -> _MockFileCreateRequest: return _MockFileCreateRequest(kwargs.get('body'), kwargs.get('media_body'))

    class _MockDriveService:
        def files(self) -> _MockFilesResource: return _MockFilesResource()

    # --- Assign mocks to the names expected by the application ---
    # This ensures that the rest of the file can use these names without knowing if they are real or mocks.
    Credentials = MockCredentials
    HttpError = MockHttpError
    Request = MockRequest
    MediaIoUploader = MockMediaIoUploader
    def build(service_name: str, version: str, credentials: Any) -> _MockDriveService:
        return _MockDriveService()


# --- Application Service Code ---
from .db_oauth_gdrive import get_token, update_gdrive_access_token
from .crypto_utils import decrypt_data, encrypt_data

logger = logging.getLogger(__name__)
SCOPES = ['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/drive.file']

async def get_gdrive_credentials(user_id: str, db_conn_pool: Any) -> Optional["Credentials"]:
    """
    Retrieves and refreshes Google Drive credentials for a user from the database.
    """
    encrypted_token_data = get_token(db_conn_pool, user_id)
    if not encrypted_token_data:
        logger.warning(f"No GDrive token found in DB for user {user_id}")
        return None

    try:
        client_id = os.environ.get("GOOGLE_CLIENT_ID")
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
        if not client_id or not client_secret:
            logger.error("GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not configured.")
            return None

        decrypted_access_token = decrypt_data(encrypted_token_data['access_token_encrypted'])
        if not decrypted_access_token:
            logger.error(f"Failed to decrypt access token for user {user_id}")
            return None

        decrypted_refresh_token = decrypt_data(encrypted_token_data['refresh_token_encrypted']) if encrypted_token_data.get('refresh_token_encrypted') else None

        creds = Credentials(
            token=decrypted_access_token,
            refresh_token=decrypted_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES)

        if creds.expired and creds.refresh_token:
            logger.info(f"GDrive token for user {user_id} expired. Refreshing...")
            creds.refresh(Request())
            if creds.token and hasattr(creds, 'expiry') and creds.expiry:
                new_encrypted_access_token = encrypt_data(creds.token)
                new_expiry_ms = int(creds.expiry.timestamp() * 1000)
                if new_encrypted_access_token:
                    update_gdrive_access_token(db_conn_pool, user_id, new_encrypted_access_token, new_expiry_ms)
                    logger.info(f"Refreshed and updated GDrive token for user {user_id}")
        return creds
    except Exception as e:
        logger.error(f"Failed to process Google credentials for user {user_id}: {e}", exc_info=True)
        return None

async def list_files(creds: "Credentials", query: Optional[str] = None, page_size: int = 50, page_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Lists files in Google Drive, optionally filtered by a query."""
    try:
        service = build('drive', 'v3', credentials=creds)
        q_filter = f"name contains '{query}' and trashed = false" if query else "trashed = false"
        results = service.files().list(
            q=q_filter,
            pageSize=page_size,
            pageToken=page_token,
            fields="nextPageToken, files(id, name, mimeType, webViewLink, modifiedTime)"
        ).execute()
        return results
    except HttpError as e:
        logger.error(f"Google Drive API error during list_files: {e}", exc_info=True)
        return None

async def get_file_metadata(creds: "Credentials", file_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves metadata for a single file."""
    try:
        service = build('drive', 'v3', credentials=creds)
        file_metadata = service.files().get(fileId=file_id, fields="*").execute()
        return file_metadata
    except HttpError as e:
        logger.error(f"Google Drive API error getting metadata for {file_id}: {e}", exc_info=True)
        return None

async def download_file(creds: "Credentials", file_id: str) -> Optional[Tuple[bytes, Dict[str, Any]]]:
    """Downloads a file, exporting Google Docs to PDF if necessary."""
    try:
        service = build('drive', 'v3', credentials=creds)
        metadata = await get_file_metadata(creds, file_id)
        if not metadata:
            return None

        mime_type = metadata.get('mimeType', '')
        request = None
        if 'google-apps' in mime_type:
            export_links = metadata.get('exportLinks', {})
            if 'application/pdf' in export_links:
                request = service.files().export_media(fileId=file_id, mimeType='application/pdf')
                metadata['name'] = f"{metadata.get('name', 'Untitled')}.pdf"
                metadata['mimeType'] = 'application/pdf'
            else:
                logger.warning(f"No suitable PDF export format for GDrive file {file_id} of type {mime_type}")
                return None
        else:
            request = service.files().get_media(fileId=file_id)

        if request:
            file_content = request.execute()
            return (file_content, metadata)
        return None
    except HttpError as e:
        logger.error(f"Google Drive API error downloading file {file_id}: {e}", exc_info=True)
        return None

async def create_file(creds: "Credentials", file_metadata: Dict[str, Any], file_content: Optional[bytes] = None) -> Optional[Dict[str, Any]]:
    """Creates a file or folder in Google Drive."""
    try:
        service = build('drive', 'v3', credentials=creds)
        media_body = None
        if file_content:
            fh = io.BytesIO(file_content)
            mimetype = file_metadata.get('mimeType', 'application/octet-stream')
            media_body = MediaIoUploader(fh, mimetype=mimetype, resumable=True, chunksize=1024 * 1024)

        file_resource = service.files().create(
            body=file_metadata,
            media_body=media_body,
            fields='id, name, webViewLink'
        ).execute()
        return file_resource
    except HttpError as e:
        logger.error(f"Google Drive API error creating file: {e}", exc_info=True)
        return None
