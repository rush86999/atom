import os
import logging
from typing import List, Dict, Any, Callable, Awaitable
import io
from boxsdk import Client, OAuth2
from boxsdk.object.file import File as BoxFile
import docx
import PyPDF2
from datetime import datetime, timedelta, timezone

# Assuming the execution environment (like a Docker container) will have PYTHONPATH
# set up to include the path to the 'python_api_service' directory. This is a common
# pattern for sharing code between services in a monorepo without creating a formal package.
# We will need to ensure the Dockerfile for this service sets this up.
from python_api_service import db_oauth_box, crypto_utils

# Configure logging
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# These are needed for the OAuth2 flow to refresh tokens
BOX_CLIENT_ID = os.getenv("BOX_CLIENT_ID")
BOX_CLIENT_SECRET = os.getenv("BOX_CLIENT_SECRET")

def extract_text_from_docx(content: bytes) -> str:
    """Extracts text from a DOCX file's content."""
    try:
        doc = docx.Document(io.BytesIO(content))
        return "\n".join([paragraph.text for paragraph in doc.paragraphs])
    except Exception as e:
        logger.error(f"Error extracting text from DOCX content: {e}")
        return ""

def extract_text_from_pdf(content: bytes) -> str:
    """Extracts text from a PDF file's content."""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        text = []
        for page in reader.pages:
            extracted_text = page.extract_text()
            if extracted_text:
                text.append(extracted_text)
        return "\n".join(text)
    except Exception as e:
        logger.error(f"Error extracting text from PDF content: {e}")
        return ""

async def extract_data_from_box(user_id: str, db_conn_pool: Any) -> List[Dict[str, Any]]:
    """
    Extracts data from Box using OAuth tokens stored in the database.
    """
    logger.info(f"Starting Box data extraction for user '{user_id}' using OAuth tokens.")

    if not db_conn_pool:
        logger.error("Database connection pool not provided to Box extractor.")
        return []

    if not BOX_CLIENT_ID or not BOX_CLIENT_SECRET:
        logger.error("BOX_CLIENT_ID or BOX_CLIENT_SECRET is not configured. Cannot perform OAuth token refresh. Aborting.")
        return []

    tokens = await db_oauth_box.get_tokens(db_conn_pool, user_id)
    if not tokens:
        logger.info(f"No Box OAuth tokens found for user '{user_id}'. Skipping Box extraction.")
        return []

    access_token_enc, refresh_token_enc, _ = tokens

    try:
        access_token = crypto_utils.decrypt_message(access_token_enc)
        refresh_token = crypto_utils.decrypt_message(refresh_token_enc) if refresh_token_enc else None
    except Exception as e:
        logger.error(f"Failed to decrypt tokens for user '{user_id}': {e}", exc_info=True)
        return []

    # Define an async callback to store the refreshed tokens
    async def store_refreshed_tokens_async(new_access_token: str, new_refresh_token: str):
        logger.info(f"Storing refreshed Box tokens for user '{user_id}'.")
        # Box tokens typically last 1 hour.
        new_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        enc_access = crypto_utils.encrypt_message(new_access_token)
        enc_refresh = crypto_utils.encrypt_message(new_refresh_token) if new_refresh_token else None
        await db_oauth_box.save_tokens(
            db_conn_pool, user_id, enc_access, enc_refresh, new_expires_at, ""
        )

    # The boxsdk store_tokens callback is synchronous, so we need a wrapper.
    def store_tokens_sync_wrapper(new_access_token: str, new_refresh_token: str):
        import asyncio
        try:
            # Get or create an event loop to run the async function
            loop = asyncio.get_running_loop()
            loop.create_task(store_refreshed_tokens_async(new_access_token, new_refresh_token))
        except RuntimeError: # 'get_running_loop' fails if no loop is running
            asyncio.run(store_refreshed_tokens_async(new_access_token, new_refresh_token))

    oauth = OAuth2(
        client_id=BOX_CLIENT_ID,
        client_secret=BOX_CLIENT_SECRET,
        access_token=access_token,
        refresh_token=refresh_token,
        store_tokens=store_tokens_sync_wrapper,
    )

    try:
        client = Client(oauth)
        # The SDK will automatically refresh the token if needed when a call is made.
        # This call serves as a test to ensure the connection is valid.
        client.users.get(user_id='me')
    except Exception as e:
        logger.error(f"Failed to create or test Box client for user '{user_id}' after fetching tokens: {e}", exc_info=True)
        return []

    extracted_data = []
    try:
        root_folder = client.folder(folder_id='0').get()
        items = root_folder.get_items()

        for item in items:
            if not isinstance(item, BoxFile):
                continue

            # ... (The rest of the file processing logic is identical to the previous version)
            file_name = item.name
            file_ext = os.path.splitext(file_name)[1].lower()
            text = ""

            try:
                logger.info(f"Processing file: '{file_name}' (ID: {item.id}) from Box.")
                content = item.content()

                if file_ext == '.docx':
                    text = extract_text_from_docx(content)
                elif file_ext == '.pdf':
                    text = extract_text_from_pdf(content)
                elif file_ext == '.txt':
                    text = content.decode('utf-8')
                else:
                    logger.warning(f"Unsupported file type '{file_ext}' for file '{file_name}'. Skipping.")
                    continue

                if not text.strip():
                    logger.info(f"No text content could be extracted from file: '{file_name}'. Skipping.")
                    continue

                created_at_iso = datetime.fromisoformat(item.created_at).isoformat()
                modified_at_iso = datetime.fromisoformat(item.modified_at).isoformat()
                shared_link_url = item.get_shared_link()

                extracted_data.append({
                    "source": "box",
                    "document_id": f"box_{item.id}",
                    "document_title": file_name,
                    "full_text": text,
                    "user_id": user_id,
                    "created_at": created_at_iso,
                    "last_edited_at": modified_at_iso,
                    "url": shared_link_url
                })
            except Exception as e:
                logger.error(f"Error processing file '{file_name}' (ID: {item.id}) from Box: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Failed to list or process files from Box for user '{user_id}': {e}", exc_info=True)

    logger.info(f"Finished Box data extraction for user '{user_id}'. Extracted {len(extracted_data)} items.")
    return extracted_data
