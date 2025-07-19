import os
import logging
from typing import List, Dict, Any
import io
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import docx
import PyPDF2

# Configure logging
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def get_gdrive_service(credentials: Credentials):
    return build('drive', 'v3', credentials=credentials)

def extract_text_from_docx(content: bytes) -> str:
    doc = docx.Document(io.BytesIO(content))
    return "\n".join([paragraph.text for paragraph in doc.paragraphs])

def extract_text_from_pdf(content: bytes) -> str:
    reader = PyPDF2.PdfReader(io.BytesIO(content))
    text = []
    for page in reader.pages:
        text.append(page.extract_text())
    return "\n".join(text)

async def extract_data_from_gdrive(user_id: str, credentials_json: str) -> List[Dict[str, Any]]:
    logger.info(f"Extracting data from Google Drive for user {user_id}")
    credentials = Credentials.from_authorized_user_info(info=json.loads(credentials_json))
    service = get_gdrive_service(credentials)

    extracted_data = []

    results = service.files().list(pageSize=10, fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, webViewLink)").execute()
    items = results.get('files', [])

    for item in items:
        file_id = item['id']
        file_name = item['name']
        mime_type = item['mimeType']
        text = ""
        try:
            if mime_type == 'application/vnd.google-apps.document':
                request = service.files().export_media(fileId=file_id, mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
                content = request.execute()
                text = extract_text_from_docx(content)
            elif mime_type == 'application/pdf':
                request = service.files().get_media(fileId=file_id)
                content = request.execute()
                text = extract_text_from_pdf(content)
            elif mime_type == 'text/plain':
                request = service.files().get_media(fileId=file_id)
                content = request.execute()
                text = content.decode('utf-8')
            else:
                logger.warning(f"Unsupported MIME type: {mime_type}. Skipping file: {file_name}")
                continue

            extracted_data.append({
                "source": "gdrive",
                "document_id": f"gdrive_{file_id}",
                "document_title": file_name,
                "full_text": text,
                "user_id": user_id,
                "created_at": item['createdTime'],
                "last_edited_at": item['modifiedTime'],
                "url": item['webViewLink']
            })
        except Exception as e:
            logger.error(f"Error processing file {file_name} from Google Drive: {e}")

    return extracted_data
