import os
import logging
from typing import Optional, Tuple, List, Dict, Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request

from .db_oauth_gdrive import get_token, save_token
from .crypto_utils import decrypt_token

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

async def get_gdrive_credentials(user_id: str, db_conn_pool) -> Optional[Credentials]:
    """
    Retrieves and refreshes Google Drive credentials for a user.
    """
    encrypted_token_data = await get_token(db_conn_pool, user_id)
    if not encrypted_token_data:
        return None

    try:
        decrypted_token_json = decrypt_token(encrypted_token_data)
        creds = Credentials.from_authorized_user_info(decrypted_token_json, SCOPES)

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save the potentially refreshed token back to the DB
            await save_token(db_conn_pool, user_id, creds.to_json())

        return creds
    except Exception as e:
        logger.error(f"Failed to load or refresh Google credentials for user {user_id}: {e}", exc_info=True)
        return None

async def is_user_connected(user_id: str, db_conn_pool) -> bool:
    """
    Checks if a user has a valid, non-expired token.
    """
    creds = await get_gdrive_credentials(user_id, db_conn_pool)
    return creds is not None and creds.valid


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
        if 'google-apps' in mime_type:
            export_links = metadata.get('exportLinks')
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
