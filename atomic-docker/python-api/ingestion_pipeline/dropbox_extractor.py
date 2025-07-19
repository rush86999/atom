import os
import logging
from typing import List, Dict, Any
import dropbox
import io
import docx
import PyPDF2
from datetime import datetime, timezone

# Configure logging
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def extract_text_from_docx(content: bytes) -> str:
    doc = docx.Document(io.BytesIO(content))
    return "\n".join([paragraph.text for paragraph in doc.paragraphs])

def extract_text_from_pdf(content: bytes) -> str:
    reader = PyPDF2.PdfReader(io.BytesIO(content))
    text = []
    for page in reader.pages:
        text.append(page.extract_text())
    return "\n".join(text)

async def extract_data_from_dropbox(user_id: str, access_token: str) -> List[Dict[str, Any]]:
    logger.info(f"Extracting data from Dropbox for user {user_id}")
    dbx = dropbox.Dropbox(access_token)
    extracted_data = []

    try:
        for entry in dbx.files_list_folder('').entries:
            if isinstance(entry, dropbox.files.FileMetadata):
                file_path = entry.path_display
                file_ext = os.path.splitext(file_path)[1].lower()
                text = ""

                try:
                    _, res = dbx.files_download(path=file_path)
                    content = res.content

                    if file_ext == '.docx':
                        text = extract_text_from_docx(content)
                    elif file_ext == '.pdf':
                        text = extract_text_from_pdf(content)
                    elif file_ext == '.txt':
                        text = content.decode('utf-8')
                    else:
                        logger.warning(f"Unsupported file type: {file_ext}. Skipping file: {file_path}")
                        continue

                    extracted_data.append({
                        "source": "dropbox",
                        "document_id": f"dropbox_{entry.id}",
                        "document_title": entry.name,
                        "full_text": text,
                        "user_id": user_id,
                        "created_at": entry.client_modified.replace(tzinfo=timezone.utc).isoformat(),
                        "last_edited_at": entry.server_modified.replace(tzinfo=timezone.utc).isoformat(),
                        "url": dbx.sharing_create_shared_link(path=file_path).url
                    })
                except Exception as e:
                    logger.error(f"Error processing file {file_path} from Dropbox: {e}")
    except Exception as e:
        logger.error(f"Error listing files from Dropbox: {e}")

    return extracted_data
