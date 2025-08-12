import os
import logging
from typing import List, Dict, Any
import io
from boxsdk import Client, OAuth2
from boxsdk.object.file import File as BoxFile
import docx
import PyPDF2
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

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

async def extract_data_from_box(user_id: str, access_token: str) -> List[Dict[str, Any]]:
    """
    Extracts text content and metadata from files in a user's Box account.
    """
    logger.info(f"Starting Box data extraction for user '{user_id}'")

    if not access_token:
        logger.error("Box access token was not provided. Aborting Box extraction.")
        return []

    try:
        oauth = OAuth2(client_id=None, client_secret=None, access_token=access_token)
        client = Client(oauth)
        # Verify that the client is authenticated
        client.users.get(user_id='me')
    except Exception as e:
        logger.error(f"Failed to authenticate with Box using the provided access token: {e}", exc_info=True)
        return []

    extracted_data = []

    try:
        # Get items from the root folder
        root_folder = client.folder(folder_id='0').get()
        items = root_folder.get_items()

        for item in items:
            if not isinstance(item, BoxFile):
                continue

            file_name = item.name
            file_ext = os.path.splitext(file_name)[1].lower()
            text = ""

            try:
                logger.info(f"Processing file: '{file_name}' (ID: {item.id}) from Box.")

                # Download file content
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

                # Box API provides RFC 3339 datetime strings, which are ISO 8601 compatible.
                created_at_iso = datetime.fromisoformat(item.created_at).isoformat()
                modified_at_iso = datetime.fromisoformat(item.modified_at).isoformat()

                # Get a shared link to the file for the URL
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
