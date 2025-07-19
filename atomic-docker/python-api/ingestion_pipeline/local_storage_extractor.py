import os
import logging
from typing import List, Dict, Any
import docx
import PyPDF2
from datetime import datetime, timezone

# Configure logging
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def extract_text_from_docx(file_path: str) -> str:
    doc = docx.Document(file_path)
    return "\n".join([paragraph.text for paragraph in doc.paragraphs])

def extract_text_from_pdf(file_path: str) -> str:
    with open(file_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        text = []
        for page in reader.pages:
            text.append(page.extract_text())
        return "\n".join(text)

def extract_text_from_txt(file_path: str) -> str:
    with open(file_path, 'r') as f:
        return f.read()

async def extract_data_from_local_storage(user_id: str, path: str) -> List[Dict[str, Any]]:
    logger.info(f"Extracting data from local storage for user {user_id} at path {path}")
    extracted_data = []
    for root, _, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            text = ""
            try:
                if file_ext == '.docx':
                    text = extract_text_from_docx(file_path)
                elif file_ext == '.pdf':
                    text = extract_text_from_pdf(file_path)
                elif file_ext == '.txt':
                    text = extract_text_from_txt(file_path)
                else:
                    logger.warning(f"Unsupported file type: {file_ext}. Skipping file: {file_path}")
                    continue

                stat = os.stat(file_path)
                created_at = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat()
                last_edited_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

                extracted_data.append({
                    "source": "local_storage",
                    "document_id": f"local_{stat.st_ino}",
                    "document_title": file,
                    "full_text": text,
                    "user_id": user_id,
                    "created_at": created_at,
                    "last_edited_at": last_edited_at,
                    "url": f"file://{file_path}"
                })
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
    return extracted_data
