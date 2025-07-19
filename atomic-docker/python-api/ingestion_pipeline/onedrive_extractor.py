import os
import logging
from typing import List, Dict, Any
import io
import docx
import PyPDF2
from msgraph import GraphServiceClient
from msgraph.generated.models.drive_item import DriveItem
from azure.identity import InteractiveBrowserCredential

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

async def extract_data_from_onedrive(user_id: str, access_token: str) -> List[Dict[str, Any]]:
    logger.info(f"Extracting data from OneDrive for user {user_id}")

    credential = InteractiveBrowserCredential(client_id=os.environ["MS_CLIENT_ID"])
    client = GraphServiceClient(credentials=credential)

    extracted_data = []

    try:
        drive_items = await client.me.drive.root.children.get()
        for item in drive_items.value:
            if item.file:
                file_name = item.name
                file_ext = os.path.splitext(file_name)[1].lower()
                text = ""

                try:
                    content = await client.me.drive.items.by_drive_item_id(item.id).content.get()

                    if file_ext == '.docx':
                        text = extract_text_from_docx(content)
                    elif file_ext == '.pdf':
                        text = extract_text_from_pdf(content)
                    elif file_ext == '.txt':
                        text = content.decode('utf-8')
                    else:
                        logger.warning(f"Unsupported file type: {file_ext}. Skipping file: {file_name}")
                        continue

                    extracted_data.append({
                        "source": "onedrive",
                        "document_id": f"onedrive_{item.id}",
                        "document_title": file_name,
                        "full_text": text,
                        "user_id": user_id,
                        "created_at": item.created_date_time.isoformat(),
                        "last_edited_at": item.last_modified_date_time.isoformat(),
                        "url": item.web_url
                    })
                except Exception as e:
                    logger.error(f"Error processing file {file_name} from OneDrive: {e}")
    except Exception as e:
        logger.error(f"Error listing files from OneDrive: {e}")

    return extracted_data
