from .gdrive_service import list_gdrive_files, get_gdrive_file_metadata, download_gdrive_file
from .dropbox_service import DropboxService
from .auth_handler import get_mcp_provider

def list_mcp_files(creds, folder_id, query, page_size, page_token):
    provider = get_mcp_provider(creds)
    if provider == 'dropbox':
        dropbox_service = DropboxService(creds.token)
        return dropbox_service.list_files(folder_id=folder_id, query=query, page_size=page_size, page_token=page_token)
    else:
        return list_gdrive_files(creds.token, folder_id, query, page_size, page_token)

def get_mcp_file_metadata(creds, file_id):
    provider = get_mcp_provider(creds)
    if provider == 'dropbox':
        dropbox_service = DropboxService(creds.token)
        return dropbox_service.get_file_metadata(file_id)
    else:
        return get_gdrive_file_metadata(creds.token, file_id)

def download_mcp_file(creds, file_id, target_mime_type):
    provider = get_mcp_provider(creds)
    if provider == 'dropbox':
        dropbox_service = DropboxService(creds.token)
        return dropbox_service.download_file(file_id, target_mime_type)
    else:
        return download_gdrive_file(creds.token, file_id, target_mime_type)
