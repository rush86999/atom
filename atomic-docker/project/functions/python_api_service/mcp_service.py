import io
import logging
import json
import os # For path.splitext in download_mcp_file
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
DEFAULT_FILE_FIELDS_FOR_LIST = "nextPageToken, files(id, name, mimeType, modifiedTime, webViewLink, parents, capabilities(canDownload, canExport))"
DEFAULT_FILE_FIELDS_FOR_GET = "id, name, mimeType, modifiedTime, webViewLink, parents, capabilities(canDownload, canExport), exportLinks, shortcutDetails"


def _get_drive_service(access_token: str) -> Optional[Any]:
    """Initializes and returns a Google Drive service client."""
    try:
        creds = Credentials(token=access_token)
        service = build('drive', DRIVE_API_VERSION, credentials=creds, static_discovery=False)
        return service
    except Exception as e:
        logger.error(f"Failed to initialize Google Drive service: {e}", exc_info=True)
        return None

def list_mcp_files(
    access_token: str, folder_id: Optional[str] = None, query: Optional[str] = None,
    page_size: int = DEFAULT_PAGE_SIZE, page_token: Optional[str] = None,
    fields: str = DEFAULT_FILE_FIELDS_FOR_LIST, corpora: str = "user"
) -> Dict[str, Any]:
    service = _get_drive_service(access_token)
    if not service: return {"status": "error", "message": "Failed to initialize Google Drive service.", "code": "MCP_SERVICE_INIT_FAILED"}
    q_parts = ["trashed = false"]
    if query: q_parts.append(f"name contains '{query}'")
    if folder_id: q_parts.append(f"'{folder_id}' in parents")
    final_query = " and ".join(q_parts) if len(q_parts) > 1 else q_parts[0] if q_parts else None
    try:
        logger.info(f"Listing MCP files: query='{final_query}', folder_id='{folder_id}', page_token='{page_token}', corpora='{corpora}'")
        results = service.files().list(
            q=final_query, pageSize=page_size, pageToken=page_token, fields=fields,
            supportsAllDrives=(corpora == "allDrives"), includeItemsFromAllDrives=(corpora == "allDrives"), corpora=corpora
        ).execute()
        files = results.get('files', [])
        next_page = results.get('nextPageToken')
        logger.info(f"MCP list_files returned {len(files)} items. Next page token: {bool(next_page)}")
        return {"status": "success", "data": {"files": files, "nextPageToken": next_page}}
    except HttpError as e:
        error_content = e.resp.reason if hasattr(e.resp, 'reason') else str(e); error_message = error_content; error_code_detail = "MCP_API_ERROR"
        try: error_details_json = json.loads(e.content.decode()); error_message = error_details_json.get("error", {}).get("message", error_content); error_code_detail = error_details_json.get("error", {}).get("errors", [{}])[0].get("reason", "MCP_API_ERROR")
        except: pass
        logger.error(f"Google Drive API error during list_files: {error_message} (Status: {e.resp.status}, Code: {error_code_detail})", exc_info=True)
        return {"status": "error", "message": error_message, "code": f"MCP_API_{error_code_detail.upper()}", "details": str(e.content.decode() if e.content else str(e))}
    except Exception as e:
        logger.error(f"Unexpected error listing Google Drive files: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error listing files: {str(e)}", "code": "MCP_LIST_UNEXPECTED_ERROR"}

def get_mcp_file_metadata(access_token: str, file_id: str, fields: Optional[str] = None) -> Dict[str, Any]:
    service = _get_drive_service(access_token)
    if not service: return {"status": "error", "message": "Failed to initialize Google Drive service.", "code": "MCP_SERVICE_INIT_FAILED"}
    fields_to_request = fields or DEFAULT_FILE_FIELDS_FOR_GET
    try:
        logger.info(f"Fetching MCP file metadata for ID: {file_id}, Fields: {fields_to_request}")
        file_metadata = service.files().get(fileId=file_id, fields=fields_to_request, supportsAllDrives=True).execute()
        if file_metadata.get("mimeType") == "application/vnd.google-apps.shortcut" and file_metadata.get("shortcutDetails", {}).get("targetId"):
            target_id = file_metadata["shortcutDetails"]["targetId"]
            logger.info(f"File ID {file_id} is a shortcut to target ID {target_id}. Fetching target metadata.")
            shortcut_info = {"shortcutId": file_id, "shortcutName": file_metadata.get("name"), "shortcutWebViewLink": file_metadata.get("webViewLink")}
            target_metadata_response = get_mcp_file_metadata(access_token, target_id, fields)
            if target_metadata_response["status"] == "success" and target_metadata_response.get("data"):
                target_metadata_response["data"]["is_shortcut_to"] = shortcut_info
                target_metadata_response["data"]["original_shortcut_id_if_applicable"] = file_id
                return target_metadata_response
            else: logger.warning(f"Could not resolve shortcut target {target_id} for {file_id}. Returning shortcut metadata.")
        logger.info(f"Successfully fetched metadata for MCP file ID: {file_id}, Name: {file_metadata.get('name')}")
        return {"status": "success", "data": file_metadata}
    except HttpError as e:
        error_content = e.resp.reason if hasattr(e.resp, 'reason') else str(e); error_message = error_content; error_code_detail = "MCP_API_ERROR"
        try: error_details_json = json.loads(e.content.decode()); error_message = error_details_json.get("error", {}).get("message", error_content); error_code_detail = error_details_json.get("error", {}).get("errors", [{}])[0].get("reason", "MCP_API_ERROR_UNPARSED")
        except: pass
        logger.error(f"Google Drive API error fetching metadata for file {file_id}: {error_message} (Status: {e.resp.status}, Code: {error_code_detail})", exc_info=True)
        return {"status": "error", "message": error_message, "code": f"MCP_API_{error_code_detail.upper()}", "details": str(e.content.decode() if e.content else str(e))}
    except Exception as e:
        logger.error(f"Unexpected error fetching MCP file metadata for {file_id}: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error fetching metadata for file {file_id}: {str(e)}", "code": "MCP_GET_METADATA_UNEXPECTED_ERROR"}

def download_mcp_file(access_token: str, file_id: str, target_mime_type: Optional[str] = None) -> Dict[str, Any]:
    service = _get_drive_service(access_token)
    if not service: return {"status": "error", "message": "Failed to initialize Google Drive service.", "code": "MCP_SERVICE_INIT_FAILED"}
    try:
        file_metadata = service.files().get(fileId=file_id, fields="id, name, mimeType, capabilities(canExport), exportLinks").execute()
        original_mime_type = file_metadata.get('mimeType', '')
        file_name = file_metadata.get('name', file_id)
        logger.info(f"Attempting to download MCP file: ID='{file_id}', Name='{file_name}', OriginalMIME='{original_mime_type}'")

        request_obj = None
        effective_mime_type = original_mime_type
        base_name, original_ext = os.path.splitext(file_name)

        is_gsuite = original_mime_type.startswith('application/vnd.google-apps')
        if is_gsuite:
            export_links = file_metadata.get('exportLinks', {})
            can_export = file_metadata.get('capabilities', {}).get('canExport', False)
            if not can_export and not export_links : return {"status": "error", "message": f"File '{file_name}' is GSuite type but cannot be exported.", "code": "MCP_EXPORT_NOT_ALLOWED"}

            # Determine the effective_mime_type for export
            if original_mime_type == 'application/vnd.google-apps.document':
                if target_mime_type == 'text/plain' and 'text/plain' in export_links: effective_mime_type = 'text/plain'; file_name = f"{base_name}.txt"
                elif target_mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' and 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' in export_links: effective_mime_type = target_mime_type; file_name = f"{base_name}.docx"
                elif (not target_mime_type or target_mime_type == 'application/pdf') and 'application/pdf' in export_links: effective_mime_type = 'application/pdf'; file_name = f"{base_name}.pdf"
                else: effective_mime_type = next(iter(export_links.keys()), None); file_name = f"{base_name}.unknown_export" # Fallback
            elif original_mime_type == 'application/vnd.google-apps.spreadsheet':
                if target_mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' and 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in export_links: effective_mime_type = target_mime_type; file_name = f"{base_name}.xlsx"
                elif target_mime_type == 'text/csv' and 'text/csv' in export_links: effective_mime_type = 'text/csv'; file_name = f"{base_name}.csv"
                elif (not target_mime_type or target_mime_type == 'application/pdf') and 'application/pdf' in export_links: effective_mime_type = 'application/pdf'; file_name = f"{base_name}.pdf"
                else: effective_mime_type = next(iter(export_links.keys()), None); file_name = f"{base_name}.unknown_export"
            elif original_mime_type == 'application/vnd.google-apps.presentation':
                if (not target_mime_type or target_mime_type == 'application/pdf') and 'application/pdf' in export_links: effective_mime_type = 'application/pdf'; file_name = f"{base_name}.pdf"
                elif target_mime_type == 'application/vnd.openxmlformats-officedocument.presentationml.presentation' and 'application/vnd.openxmlformats-officedocument.presentationml.presentation' in export_links: effective_mime_type = target_mime_type; file_name = f"{base_name}.pptx"
                else: effective_mime_type = next(iter(export_links.keys()), None); file_name = f"{base_name}.unknown_export"
            else: # Other GSuite types
                effective_mime_type = target_mime_type if target_mime_type and target_mime_type in export_links else 'application/pdf'
                if effective_mime_type not in export_links: effective_mime_type = next(iter(export_links.keys()), None)
                if effective_mime_type == 'application/pdf': file_name = f"{base_name}.pdf"
                elif effective_mime_type == 'text/plain': file_name = f"{base_name}.txt"

            if not effective_mime_type: return {"status": "error", "message": f"No suitable export format found for GSuite file '{file_metadata.get('name')}' (ID: {file_id}). Requested: {target_mime_type}", "code": "MCP_NO_EXPORT_FORMATS"}
            logger.info(f"Exporting GSuite file ID {file_id} (Original Name: {file_metadata.get('name')}) as MIME: {effective_mime_type}. New Filename: {file_name}")
            request_obj = service.files().export_media(fileId=file_id, mimeType=effective_mime_type)
        else: # Native file
            if target_mime_type and target_mime_type != original_mime_type:
                logger.warning(f"Target MIME type {target_mime_type} requested for native file {file_id} ({original_mime_type}), but direct download will be used. Conversion not supported here.")
            logger.info(f"Downloading native file '{file_name}' (ID: {file_id}) directly.")
            request_obj = service.files().get_media(fileId=file_id)

        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request_obj)
        done = False
        while not done: status, done = downloader.next_chunk(); # logger.debug(f"Download progress: {int(status.progress() * 100)}%") if status else None

        file_content_bytes = fh.getvalue()
        logger.info(f"Successfully downloaded/exported file '{file_name}' (ID: {file_id}). Size: {len(file_content_bytes)} bytes. Effective MIME: {effective_mime_type}")
        return {"status": "success", "data": {"file_name": file_name, "content_bytes": file_content_bytes, "mime_type": effective_mime_type}}
    except HttpError as e:
        error_content = e.resp.reason if hasattr(e.resp, 'reason') else str(e); error_message = error_content; error_code_detail = "MCP_API_ERROR"
        try: error_details_json = json.loads(e.content.decode()); error_message = error_details_json.get("error", {}).get("message", error_content); error_code_detail = error_details_json.get("error", {}).get("errors", [{}])[0].get("reason", "MCP_API_ERROR_UNPARSED")
        except: pass
        logger.error(f"Google Drive API error during download/export of file {file_id}: {error_message} (Status: {e.resp.status}, Code: {error_code_detail})", exc_info=True)
        return {"status": "error", "message": error_message, "code": f"MCP_API_{error_code_detail.upper()}", "details": str(e.content.decode() if e.content else str(e))}
    except Exception as e:
        logger.error(f"Unexpected error downloading/exporting MCP file {file_id}: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error downloading file: {str(e)}", "code": "MCP_DOWNLOAD_UNEXPECTED_ERROR"}
