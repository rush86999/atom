import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict

# Dropbox SDK
try:
    import dropbox
    from dropbox.exceptions import AuthError
    DROPBOX_SDK_AVAILABLE = True
except ImportError:
    DROPBOX_SDK_AVAILABLE = False
    dropbox = None
    AuthError = None

# Internal imports for DB access and crypto
try:
    from . import db_oauth_dropbox
    from . import crypto_utils
except ImportError:
    # Fallback for different execution contexts
    import db_oauth_dropbox
    import crypto_utils

logger = logging.getLogger(__name__)

# Load Dropbox App credentials from environment
DROPBOX_APP_KEY = os.getenv("DROPBOX_APP_KEY")
DROPBOX_APP_SECRET = os.getenv("DROPBOX_APP_SECRET")

async def get_dropbox_client(user_id: str, db_conn_pool: Optional[Any]) -> Optional[dropbox.Dropbox]:
    """
    Constructs and returns an authenticated Dropbox client for a user.
    Handles token retrieval, decryption, and refreshing if necessary.
    """
    if not DROPBOX_SDK_AVAILABLE:
        logger.error("Dropbox SDK is not installed.")
        return None
    if not DROPBOX_APP_KEY or not DROPBOX_APP_SECRET:
        logger.error("Dropbox App Key/Secret are not configured in the environment.")
        return None

    try:
        token_info = await db_oauth_dropbox.get_tokens(db_conn_pool, user_id)
        if not token_info:
            logger.warning(f"No Dropbox tokens found for user_id: {user_id}")
            return None

        access_token = crypto_utils.decrypt_message(token_info['encrypted_access_token'])
        refresh_token = crypto_utils.decrypt_message(token_info.get('encrypted_refresh_token')) if token_info.get('encrypted_refresh_token') else None
        expires_at = token_info.get('expires_at')

        # Check if the token is expired or close to expiring (e.g., within 5 minutes)
        if expires_at and datetime.now(timezone.utc) >= (expires_at - timedelta(minutes=5)):
            if not refresh_token:
                logger.error(f"Dropbox token for user {user_id} is expired, but no refresh token is available.")
                return None

            logger.info(f"Dropbox access token for user {user_id} is expired. Refreshing...")

            # The Dropbox SDK can handle the refresh flow automatically if instantiated with the refresh token
            dbx_for_refresh = dropbox.Dropbox(
                oauth2_refresh_token=refresh_token,
                app_key=DROPBOX_APP_KEY,
                app_secret=DROPBOX_APP_SECRET
            )

            try:
                dbx_for_refresh.check_and_refresh_access_token()

                # Get the new token details
                new_access_token = dbx_for_refresh._oauth2_access_token
                new_expires_at = datetime.now(timezone.utc) + timedelta(seconds=dbx_for_refresh._oauth2_access_token_expiration)

                # Encrypt and save the new access token
                encrypted_new_access_token = crypto_utils.encrypt_message(new_access_token)
                await db_oauth_dropbox.update_tokens(
                    db_conn_pool=db_conn_pool,
                    user_id=user_id,
                    encrypted_access_token=encrypted_new_access_token,
                    expires_at=new_expires_at
                )
                logger.info(f"Successfully refreshed and updated Dropbox token for user {user_id}.")
                # Update local variables for client instantiation
                access_token = new_access_token

            except AuthError as e:
                logger.error(f"Dropbox AuthError while refreshing token for user {user_id}: {e}", exc_info=True)
                # This could mean the refresh token was revoked. We should probably delete the invalid tokens.
                await db_oauth_dropbox.delete_tokens(db_conn_pool, user_id)
                logger.warning(f"Deleted invalid Dropbox tokens for user {user_id} after refresh failure.")
                return None

        # Instantiate the client with the valid (or newly refreshed) access token
        dbx = dropbox.Dropbox(oauth2_access_token=access_token)
        return dbx

    except Exception as e:
        logger.error(f"An unexpected error occurred in get_dropbox_client for user {user_id}: {e}", exc_info=True)
        return None


async def get_current_account(client: dropbox.Dropbox) -> Optional[Dict[str, Any]]:
    """
    Gets the current user's account information.
    Returns a dictionary of account info or None on failure.
    """
    try:
        account_info = client.users_get_current_account()
        # The result is a Dropbox user object, we can convert it to a dict if needed
        # For now, returning the object itself might be more useful.
        return {
            "name": account_info.name.display_name,
            "email": account_info.email,
            "account_id": account_info.account_id,
            "profile_photo_url": account_info.profile_photo_url,
        }
    except AuthError as e:
        logger.error(f"Dropbox API authentication error: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Error calling users_get_current_account: {e}", exc_info=True)
        return None


async def list_folder(client: dropbox.Dropbox, path: str = "") -> Optional[Dict[str, Any]]:
    """
    Lists the contents of a folder.
    Returns a dictionary containing files and folders or None on failure.
    """
    try:
        logger.info(f"Listing folder for path: '{path or 'root'}'")
        result = client.files_list_folder(path)

        files = []
        for entry in result.entries:
            item = {
                "type": "folder" if isinstance(entry, dropbox.files.FolderMetadata) else "file",
                "name": entry.name,
                "id": entry.id,
                "path_lower": entry.path_lower,
            }
            if isinstance(entry, dropbox.files.FileMetadata):
                item["size"] = entry.size
                item["server_modified"] = entry.server_modified.isoformat()
            files.append(item)

        return {
            "entries": files,
            "cursor": result.cursor,
            "has_more": result.has_more,
        }
    except AuthError as e:
        logger.error(f"Dropbox API authentication error: {e}", exc_info=True)
        return None
    except dropbox.exceptions.ApiError as e:
        logger.error(f"Dropbox API error listing folder '{path}': {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error listing folder '{path}': {e}", exc_info=True)
        return None

async def is_user_connected(user_id: str, db_conn_pool: Optional[Any]) -> bool:
    """
    Checks if a user has a valid, active Dropbox token.
    """
    try:
        token_info = await db_oauth_dropbox.get_tokens(db_conn_pool, user_id)
        if not token_info:
            return False

        # Optionally, you could try a lightweight API call to confirm the token is still valid
        # For now, just checking existence is sufficient.
        return True
    except Exception as e:
        logger.error(f"Error checking if user {user_id} is connected to Dropbox: {e}", exc_info=True)
        return False

async def search_files(client: dropbox.Dropbox, query: str) -> Optional[Dict[str, Any]]:
    """
    Searches for files and folders matching the query.
    """
    try:
        logger.info(f"Searching for query: '{query}'")
        result = client.files_search_v2(query)

        matches = []
        for match in result.matches:
            entry = match.metadata.get_metadata()
            item = {
                "type": "folder" if isinstance(entry, dropbox.files.FolderMetadata) else "file",
                "name": entry.name,
                "id": entry.id,
                "path_lower": entry.path_lower,
            }
            if isinstance(entry, dropbox.files.FileMetadata):
                item["size"] = entry.size
                item["server_modified"] = entry.server_modified.isoformat()
            matches.append(item)

        return {
            "matches": matches,
            "has_more": result.has_more,
            "cursor": result.cursor,
        }
    except AuthError as e:
        logger.error(f"Dropbox API authentication error during search: {e}", exc_info=True)
        return None
    except dropbox.exceptions.ApiError as e:
        logger.error(f"Dropbox API error searching for '{query}': {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error searching for '{query}': {e}", exc_info=True)
        return None

async def download_file(client: dropbox.Dropbox, file_path: str) -> Optional[tuple]:
    """
    Downloads a file from Dropbox.
    Returns a tuple of (FileMetadata, FileContentBytes) or None on failure.
    """
    try:
        logger.info(f"Downloading file from path: {file_path}")
        metadata, res = client.files_download(path=file_path)
        return metadata, res.content
    except AuthError as e:
        logger.error(f"Dropbox API authentication error downloading file '{file_path}': {e}", exc_info=True)
        return None
    except dropbox.exceptions.ApiError as e:
        logger.error(f"Dropbox API error downloading file '{file_path}': {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error downloading file '{file_path}': {e}", exc_info=True)
        return None
