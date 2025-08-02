import os
import io
import logging
from typing import Optional, Tuple, Dict, Any, List, Union

# Standard import handling for optional dependencies
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from google.auth.transport.requests import Request
    from googleapiclient.http import MediaIoUpload
    import google.auth.exceptions as google_auth_exceptions
    HAS_GOOGLE_API = True

    CredentialsType = Credentials
    HttpErrorType = HttpError
    RequestType = Request
    MediaIoUploadType = MediaIoUpload
    GoogleAuthErrorType = google_auth_exceptions.GoogleAuthError

except ImportError:
    HAS_GOOGLE_API = False

    class CredentialsType:
        """Mock Credentials type"""
        def __init__(self, **kwargs):
            self.token = kwargs.get('token', 'mock_token')
            self.expired = kwargs.get('expired', False)
            self.refresh_token = kwargs.get('refresh_token', 'mock_refresh_token')
            self.client_id = kwargs.get('client_id', 'mock_client_id')
            self.client_secret = kwargs.get('client_secret', 'mock_client_secret')
            self.scopes = kwargs.get('scopes', [])
            self.token_uri = "https://oauth2.googleapis.com/token"

    class HttpErrorType(Exception):
        """Mock HttpError type"""
        def __init__(self, resp, content, uri=None):
            super().__init__(str(resp))
            self.resp = resp
            self.content = content

    class RequestType:
        """Mock Request type"""
        pass

    class MediaIoUploadType:
        """Mock MediaIoUpload type"""
        def __init__(self, fd, mimetype, chunksize, resumable):
            pass

    class GoogleAuthErrorType(Exception):
        """Mock GoogleAuthError type"""
        pass

from db_oauth_gdrive import get_token, update_gdrive_access_token
from crypto_utils import decrypt_data, encrypt_data

logger = logging.getLogger(__name__)
SCOPES = ['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/drive.file']

async def get_gdrive_credentials(user_id: str, db_conn_pool: Any) -> Optional[CredentialsType]:
    """Retrieve and prepare Google Drive credentials for a specific user."""
    from db_oauth_gdrive import get_user_by_id

    logger.info(f"Retrieving Google Drive credentials for user_id: {user_id}")

    try:
        user_row = await get_user_by_id(user_id, db_conn_pool)
        if not user_row or not user_row.get('google_token_encrypted'):
            logger.warning("No encrypted Google token found for user")
            return None

        raw_token_json_str = decrypt_data(user_row['google_token_encrypted'])
        if not raw_token_json_str:
            logger.error("Failed to decrypt Google token")
            return None

        token_dict = json.loads(raw_token_json_str)

        credentials = CredentialsType(
            token=token_dict.get('access_token'),
            refresh_token=token_dict.get('refresh_token'),
            client_id=os.environ.get('GOOGLE_CLIENT_ID'),
            client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
            scopes=SCOPES,
            token_uri="https://oauth2.googleapis.com/token"
        )

        logger.info("Successfully retrieved Google Drive credentials")
        return credentials

    except Exception as e:
        logger.error(f"Error getting Google Drive credentials: {str(e)}")
        return None

async def refresh_and_update_gdrive_token(
    db_conn_pool: Any,
    user_id: str,
    credentials: CredentialsType
) -> CredentialsType:
    """Refresh Google token and update database."""
    try:
        if not credentials.expired:
            return credentials

        request = RequestType()
        credentials.refresh(request)

        updated_token = {
            'access_token': credentials.token,
            'refresh_token': credentials.refresh_token or await get_refresh_token(user_id, db_conn_pool),
            'token_type': 'Bearer'
        }

        encrypted_token = encrypt_data(json.dumps(updated_token))
        await update_gdrive_access_token(user_id, encrypted_token, db_conn_pool)

        logger.info("Successfully refreshed and updated Google Drive token")
        return credentials

    except Exception as e:
        logger.error(f"Error refreshing Google Drive token: {str(e)}")
        await update_gdrive_access_token(user_id, None, db_conn_pool)
        raise e

async def extract_text_from_pdf(user_id: str, file_id: str, db_conn_pool: Any) -> str:
    """Extract text content from a PDF file in Google Drive."""
    try:
        credentials = await get_gdrive_credentials(user_id, db_conn_pool)
        if not credentials:
            return ""

        credentials = await refresh_and_update_gdrive_token(db_conn_pool, user_id, credentials)

        if not HAS_GOOGLE_API:
            logger.warning("Google API not available, returning placeholder")
            return "[Google Drive API not available - output below is placeholder]"

        service = build('drive', 'v3', credentials=credentials)

        request = service.files().get_media(fileId=file_id)
        file_content = request.execute()

        from PyPDF2 import PdfReader

        with io.BytesIO(file_content) as pdf_file:
            reader = PdfReader(pdf_file)
            text_content = ""

            for page_num, page in enumerate(reader.pages):
                text_content += f"\n--- Page {page_num + 1} ---\n"
                text_content += page.extract_text() or "[No text detected on this page]"

        return text_content

    except HttpErrorType as e:
        logger.error(f"HttpError extracting text from PDF: {str(e)}")
        if e.resp.status == 403:
            return "[Permission denied when accessing Google Drive file]"
        elif e.resp.status == 404:
            return "[File not found in Google Drive]"
        return f"[Error accessing Google Drive file: {str(e)}]"
    except Exception as e:
        logger.error(f"Unexpected error extracting text from PDF: {str(e)}")
        return f"[Error processing PDF: {str(e)}]"

async def extract_metadata_from_files(user_id: str, file_ids: List[str], db_conn_pool: Any) -> List[Dict[str, Any]]:
    """Extract metadata for multiple files from Google Drive."""
    try:
        credentials = await get_gdrive_credentials(user_id, db_conn_pool)
        if not credentials:
            return []

        credentials = await refresh_and_update_gdrive_token(db_conn_pool, user_id, credentials)

        if not HAS_GOOGLE_API:
            logger.warning("Google API not available, returning mock metadata")
            return [{'id': file_id, 'name': f'file_{file_id[-8:]}', 'mimeType': 'application/octet-stream'} for file_id in file_ids]

        service = build('drive', 'v3', credentials=credentials)

        files = []
        for file_id in file_ids:
            try:
                file = service.files().get(fileId=file_id, fields="id, name, mimeType, modifiedTime, size").execute()
                files.append(file)
            except HttpErrorType as e:
                logger.error(f"Error getting metadata for file {file_id}: {str(e)}")
                files.append({'id': file_id, 'name': 'Unknown File', 'mimeType': 'application/octet-stream', 'error': str(e)})

        return files

    except Exception as e:
        logger.error(f"Error extracting metadata from files: {str(e)}")
        return []

async def upload_file(user_id: str, file_path: str, file_name: str, mime_type: str, db_conn_pool: Any) -> Optional[str]:
    """Upload a file to Google Drive."""
    try:
        credentials = await get_gdrive_credentials(user_id, db_conn_pool)
        if not credentials:
            return None

        credentials = await refresh_and_update_gdrive_token(db_conn_pool, user_id, credentials)

        if not HAS_GOOGLE_API:
            logger.warning("Google API not available, returning mock file ID")
            return f"mock-file-id-{file_name}"

        service = build('drive', 'v3', credentials=credentials)

        file_metadata = {'name': file_name}

        with io.FileIO(file_path, 'rb') as file_data:
            media = MediaIoUploadType(file_data, mimetype=mime_type, resumable=True)
            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()

        return file.get('id')

    except Exception as e:
        logger.error(f"Error uploading file to Google Drive: {str(e)}")
        return None

async def list_files(user_id: str, query: str = None, limit: int = 100, db_conn_pool: Any) -> List[Dict[str, Any]]:
    """List files from Google Drive with optional query."""
    try:
        credentials = await get_gdrive_credentials(user_id, db_conn_pool)
        if not credentials:
            return []

        credentials = await refresh_and_update_gdrive_token(db_conn_pool, user_id, credentials)

        if not HAS_GOOGLE_API:
            logger.warning("Google API not available, returning mock file list")
            return [
                {'id': 'mock-file-1', 'name': 'document1.pdf', 'mimeType': 'application/pdf', 'modifiedTime': '2023-01-01'},
                {'id': 'mock-file-2', 'name': 'spreadsheet.xlsx', 'mimeType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'modifiedTime': '2023-01-02'}
            ]

        service = build('drive', 'v3', credentials=credentials)

        query_str = query or "mimeType!='application/vnd.google-apps.folder'"
        results = service.files().list(q=query_str, pageSize=limit, fields="files(id, name, mimeType, modifiedTime, size)").execute()

        return results.get('files', [])

    except Exception as e:
        logger.error(f"Error listing Google Drive files: {str(e)}")
        return []

async def download_file(user_id: str, file_id: str, output_path: str, db_conn_pool: Any) -> bool:
    """Download a file from Google Drive to local path."""
    try:
        credentials = await get_gdrive_credentials(user_id, db_conn_pool)
        if not credentials:
            return False

        credentials = await refresh_and_update_gdrive_token(db_conn_pool, user_id, credentials)

        if not HAS_GOOGLE_API:
            logger.warning("Google API not available, creating placeholder file")
            with open(output_path, 'w') as f:
                f.write("# Placeholder - Google API not available")
            return True

        service = build('drive', 'v3', credentials=credentials)

        request = service.files().get_media(fileId=file_id)
        file_content = request.execute()

        with open(output_path, 'wb') as f:
            f.write(file_content)

        return True

    except Exception as e:
        logger.error(f"Error downloading file from Google Drive: {str(e)}")
        return False

async def get_refresh_token(user_id: str, db_conn_pool: Any) -> Optional[str]:
    """Extract refresh token from user's saved credentials."""
    try:
        from db_oauth_gdrive import get_user_by_id

        user_row = await get_user_by_id(user_id, db_conn_pool)
        if not user_row or not user_row.get('google_token_encrypted'):
            return None

        raw_token_json_str = decrypt_data(user_row['google_token_encrypted'])
        if not raw_token_json_str:
            return None

        token_dict = json.loads(raw_token_json_str)
        return token_dict.get('refresh_token')

    except Exception as e:
        logger.error(f"Error getting refresh token: {str(e)}")
        return None

# Import required modules at the end to avoid circular imports
import json
