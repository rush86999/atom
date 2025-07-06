import io
import logging
from typing import List, Dict, Any, Optional, Tuple

# Google API Client Library
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Constants ---
DRIVE_API_VERSION = 'v3'
DEFAULT_PAGE_SIZE = 100
# Common fields to retrieve for file listings. Add more as needed.
DEFAULT_FILE_FIELDS = "nextPageToken, files(id, name, mimeType, modifiedTime, webViewLink, parents, capabilities(canDownload, canExport))"


def _get_drive_service(access_token: str) -> Optional[Any]:
    """Initializes and returns a Google Drive service client."""
    try:
        creds = Credentials(token=access_token)
        # Check if token is expired; ideally, the calling layer (TS skill/AuthService) handles refresh.
        # If token is expired here, operations will fail.
        # if creds.expired and creds.refresh_token: # This service won't have refresh_token directly
        #     # Perform refresh logic (complex, better handled by an auth service)
        #     pass
        service = build('drive', DRIVE_API_VERSION, credentials=creds, static_discovery=False)
        return service
    except Exception as e:
        logger.error(f"Failed to initialize Google Drive service: {e}", exc_info=True)
        return None

def list_gdrive_files(
    access_token: str,
    folder_id: Optional[str] = None,
    query: Optional[str] = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    page_token: Optional[str] = None,
    fields: str = DEFAULT_FILE_FIELDS,
    shared_with_me: bool = False, # To list files shared with the user
    corpora: str = "user" # user, domain, allDrives (for shared drive support)
) -> Dict[str, Any]:
    """
    Lists files and folders from Google Drive.
    Returns a dictionary: {"status": "success/error", "data": {"files": [], "nextPageToken": ...}, "message": ..., "code": ...}
    """
    service = _get_drive_service(access_token)
    if not service:
        return {"status": "error", "message": "Failed to initialize Google Drive service.", "code": "GDRIVE_SERVICE_INIT_FAILED"}

    q_parts = []
    if query:
        q_parts.append(f"name contains '{query}'") # Basic name query, can be expanded

    if folder_id:
        q_parts.append(f"'{folder_id}' in parents")

    # Filter for non-trashed files
    q_parts.append("trashed = false")

    final_query = " and ".join(q_parts) if q_parts else None

    try:
        logger.info(f"Listing GDrive files: query='{final_query}', folder_id='{folder_id}', page_token='{page_token}', sharedWithMe='{shared_with_me}', corpora='{corpora}'")

        results = service.files().list(
            q=final_query,
            pageSize=page_size,
            pageToken=page_token,
            fields=fields,
            supportsAllDrives=True, # Required for sharedDriveItems and corpora=allDrives
            includeItemsFromAllDrives=True if corpora == "allDrives" else False,
            corpora=corpora, # 'user', 'drive', 'domain', 'allDrives'
            # sharedWithMe=shared_with_me # This parameter is not valid for files.list with q; use specific query terms for shared files
        ).execute()

        files = results.get('files', [])
        next_page = results.get('nextPageToken')

        logger.info(f"GDrive list_files returned {len(files)} items. Next page token: {bool(next_page)}")
        return {"status": "success", "data": {"files": files, "nextPageToken": next_page}}

    except HttpError as e:
        error_content = e.resp.reason if hasattr(e.resp, 'reason') else str(e)
        try: # Try to parse error details from Google's JSON response
            error_details_json = json.loads(e.content.decode())
            error_message = error_details_json.get("error", {}).get("message", error_content)
            error_code_detail = error_details_json.get("error", {}).get("errors", [{}])[0].get("reason", "GDRIVE_API_ERROR")
        except:
            error_message = error_content
            error_code_detail = "GDRIVE_API_ERROR"

        logger.error(f"Google Drive API error during list_files: {error_message} (Status: {e.resp.status}, Code: {error_code_detail})", exc_info=True)
        return {"status": "error", "message": error_message, "code": f"GDRIVE_API_{error_code_detail.upper()}", "details": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error listing Google Drive files: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error listing files: {str(e)}", "code": "GDRIVE_LIST_UNEXPECTED_ERROR"}


def download_gdrive_file(
    access_token: str,
    file_id: str,
    target_mime_type: Optional[str] = None # e.g., 'application/pdf' for GDocs
) -> Dict[str, Any]:
    """
    Downloads a file from Google Drive. If it's a Google Workspace document,
    it exports it to the target_mime_type (PDF if not specified for GDocs).
    Returns: {"status": "success/error", "data": {"file_name": str, "content_bytes": bytes, "mime_type": str}, ...}
    """
    service = _get_drive_service(access_token)
    if not service:
        return {"status": "error", "message": "Failed to initialize Google Drive service.", "code": "GDRIVE_SERVICE_INIT_FAILED"}

    try:
        # Get file metadata to determine its type and capabilities
        file_metadata = service.files().get(fileId=file_id, fields="id, name, mimeType, capabilities(canExport)").execute()
        original_mime_type = file_metadata.get('mimeType', '')
        file_name = file_metadata.get('name', file_id)

        logger.info(f"Attempting to download GDrive file: ID='{file_id}', Name='{file_name}', MIMEType='{original_mime_type}'")

        request = None
        effective_mime_type = original_mime_type

        # Check if it's a Google Workspace type that needs export
        is_google_doc = original_mime_type.startswith('application/vnd.google-apps')

        if is_google_doc:
            can_export = file_metadata.get('capabilities', {}).get('canExport', False)
            if not can_export: # Should not happen if file is accessible, but good check
                 return {"status": "error", "message": f"File '{file_name}' (ID: {file_id}) is a Google Workspace type but cannot be exported.", "code": "GDRIVE_EXPORT_NOT_ALLOWED"}

            if not target_mime_type:
                if original_mime_type == 'application/vnd.google-apps.document':
                    target_mime_type = 'application/pdf' # Default export for GDoc
                    file_name = f"{os.path.splitext(file_name)[0]}.pdf" if '.' in file_name else f"{file_name}.pdf"
                elif original_mime_type == 'application/vnd.google-apps.spreadsheet':
                    target_mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' # XLSX
                    file_name = f"{os.path.splitext(file_name)[0]}.xlsx" if '.' in file_name else f"{file_name}.xlsx"
                elif original_mime_type == 'application/vnd.google-apps.presentation':
                    target_mime_type = 'application/pdf' # Or pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                    file_name = f"{os.path.splitext(file_name)[0]}.pdf" if '.' in file_name else f"{file_name}.pdf"
                else: # Other GSuite types, attempt PDF or fail
                    target_mime_type = 'application/pdf'
                    file_name = f"{os.path.splitext(file_name)[0]}.pdf" if '.' in file_name else f"{file_name}.pdf"

            logger.info(f"Exporting Google Workspace file '{file_name}' (ID: {file_id}) as MIME type: {target_mime_type}")
            request = service.files().export_media(fileId=file_id, mimeType=target_mime_type)
            effective_mime_type = target_mime_type
        else:
            # For native files (PDF, DOCX already in Drive, etc.), use direct download
            logger.info(f"Downloading native file '{file_name}' (ID: {file_id}) directly.")
            request = service.files().get_media(fileId=file_id)

        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                logger.debug(f"Download/Export progress for {file_id}: {int(status.progress() * 100)}%")

        file_content_bytes = fh.getvalue()
        logger.info(f"Successfully downloaded/exported file '{file_name}' (ID: {file_id}). Size: {len(file_content_bytes)} bytes.")

        return {
            "status": "success",
            "data": {
                "file_name": file_name,
                "content_bytes": file_content_bytes,
                "mime_type": effective_mime_type
            }
        }

    except HttpError as e:
        error_content = e.resp.reason if hasattr(e.resp, 'reason') else str(e)
        try:
            error_details_json = json.loads(e.content.decode())
            error_message = error_details_json.get("error", {}).get("message", error_content)
            error_code_detail = error_details_json.get("error", {}).get("errors", [{}])[0].get("reason", "GDRIVE_API_ERROR")
        except:
            error_message = error_content
            error_code_detail = "GDRIVE_API_ERROR"

        logger.error(f"Google Drive API error during download/export of file {file_id}: {error_message} (Status: {e.resp.status}, Code: {error_code_detail})", exc_info=True)
        return {"status": "error", "message": error_message, "code": f"GDRIVE_API_{error_code_detail.upper()}", "details": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error downloading/exporting GDrive file {file_id}: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error downloading file: {str(e)}", "code": "GDRIVE_DOWNLOAD_UNEXPECTED_ERROR"}

# Example Usage (Conceptual - for testing this module directly)
# async def main():
#     # Requires a valid, user-authorized access_token with drive.readonly scope
#     # This token would typically be obtained via an OAuth flow managed by another service/frontend.
#     access_token = os.getenv("TEST_GDRIVE_ACCESS_TOKEN")
#     if not access_token:
#         print("Please set TEST_GDRIVE_ACCESS_TOKEN environment variable for testing.")
#         return

#     print("--- Listing Root Files ---")
#     list_result = list_gdrive_files(access_token, page_size=5)
#     if list_result["status"] == "success":
#         for f in list_result["data"]["files"]:
#             print(f"ID: {f['id']}, Name: {f['name']}, MIME: {f['mimeType']}")
#             # Example: Download the first PDF or GDoc found
#             if not hasattr(main, 'downloaded_once'):
#                 if f['mimeType'] == 'application/pdf' or f['mimeType'] == 'application/vnd.google-apps.document':
#                     print(f"\n--- Attempting to download: {f['name']} ---")
#                     download_result = download_gdrive_file(access_token, f['id'])
#                     if download_result["status"] == "success":
#                         print(f"Successfully downloaded '{download_result['data']['file_name']}' ({len(download_result['data']['content_bytes'])} bytes, type: {download_result['data']['mime_type']})")
#                         # with open(download_result['data']['file_name'], 'wb') as df:
#                         #     df.write(download_result['data']['content_bytes'])
#                         # print(f"Saved to {download_result['data']['file_name']}")
#                         main.downloaded_once = True # static variable on function
#                     else:
#                         print(f"Download failed: {download_result['message']} (Code: {download_result.get('code')})")
#                     # break # download only one for testing
#     else:
#         print(f"Listing failed: {list_result['message']}")

# if __name__ == "__main__":
#    asyncio.run(main())

```
