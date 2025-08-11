from .gdrive_service import GDriveApiClient
from .dropbox_service import DropboxService
from .auth_handler import get_mcp_provider

from .onedrive_service import OneDriveService

def list_mcp_files(creds, folder_id, query, page_size, page_token):
    provider = get_mcp_provider(creds)
    if provider == 'dropbox':
        dropbox_service = DropboxService(creds.token)
        return dropbox_service.list_files(folder_id=folder_id, query=query, page_size=page_size, page_token=page_token)
    elif provider == 'onedrive':
        onedrive_service = OneDriveService(creds.token)
        return onedrive_service.list_files(folder_id=folder_id, query=query, page_size=page_size, page_token=page_token)
    else:
        gdrive_client = GDriveApiClient()
        gdrive_client.authenticate_with_token(creds.token, creds.refresh_token)
        return gdrive_client.list_files(query=query, limit=page_size)

def get_mcp_file_metadata(creds, file_id):
    provider = get_mcp_provider(creds)
    if provider == 'dropbox':
        dropbox_service = DropboxService(creds.token)
        return dropbox_service.get_file_metadata(file_id)
    elif provider == 'onedrive':
        onedrive_service = OneDriveService(creds.token)
        return onedrive_service.get_file_metadata(file_id)
    else:
        gdrive_client = GDriveApiClient()
        gdrive_client.authenticate_with_token(creds.token, creds.refresh_token)
        return gdrive_client.get_file_metadata(file_id)

import base64

def download_mcp_file(creds, file_id, target_mime_type):
    provider = get_mcp_provider(creds)
    if provider == 'dropbox':
        dropbox_service = DropboxService(creds.token)
        return dropbox_service.download_file(file_id, target_mime_type)
    elif provider == 'onedrive':
        onedrive_service = OneDriveService(creds.token)
        return onedrive_service.download_file(file_id, target_mime_type)
    else:
        gdrive_client = GDriveApiClient()
        gdrive_client.authenticate_with_token(creds.token, creds.refresh_token)
        file_path = f"/tmp/{file_id}"
        if gdrive_client.download_file(file_id, file_path):
            with open(file_path, 'rb') as f:
                content = f.read()
            return {"status": "success", "data": {"file_name": file_id, "content": base64.b64encode(content).decode('utf-8'), "mime_type": target_mime_type}}
        else:
            return {"status": "error", "message": "File download failed"}
