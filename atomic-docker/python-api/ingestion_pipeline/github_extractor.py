import os
import logging
import requests
from typing import Dict, Any, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from .lancedb_handler import add_processed_document, get_lancedb_connection
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64

# Configure logging
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

GITHUB_API_BASE_URL = 'https://api.github.com'
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:secretpgpassword@postgres:5432/postgres")
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "a_default_encryption_key_32_chars")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def decrypt(text: str) -> str:
    text_parts = text.split(':')
    iv = bytes.fromhex(text_parts[0])
    encrypted_text = bytes.fromhex(text_parts[1])
    backend = default_backend()
    key = ENCRYPTION_KEY.encode()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=backend)
    decryptor = cipher.decryptor()
    decrypted = decryptor.update(encrypted_text) + decryptor.finalize()
    # Unpad
    unpadder = lambda s: s[:-ord(s[len(s)-1:])]
    return unpadder(decrypted).decode('utf-8')

async def get_github_access_token(user_id: str) -> Optional[str]:
    db = SessionLocal()
    try:
        query = text("SELECT encrypted_access_token FROM user_tokens WHERE user_id = :user_id AND service = 'github'")
        result = db.execute(query, {"user_id": user_id}).fetchone()
        if result and result[0]:
            return decrypt(result[0])
        return None
    finally:
        db.close()

async def ingest_github_issue(repo: str, issue_number: int, user_id: str) -> Dict[str, Any]:
    """
    Fetches a GitHub issue and ingests it into LanceDB.
    """
    access_token = await get_github_access_token(user_id)
    if not access_token:
        return {"status": "error", "message": "GitHub access token not found."}

    headers = {'Authorization': f'token {access_token}'}
    url = f'{GITHUB_API_BASE_URL}/repos/{repo}/issues/{issue_number}'

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        issue_data = response.json()

        doc_id = f"github-issue-{issue_data['id']}"
        doc_meta = {
            "doc_id": doc_id,
            "user_id": user_id,
            "source_uri": issue_data['html_url'],
            "doc_type": "github_issue",
            "title": issue_data['title'],
            "metadata_json": "{}",
            "created_at_source": issue_data['created_at'],
            "last_modified_source": issue_data['updated_at'],
            "ingested_at": "NOW()",
            "processing_status": "SUCCESS",
        }

        chunks_data = [{
            "doc_id": doc_id,
            "user_id": user_id,
            "chunk_sequence": 0,
            "text_content": issue_data['body'],
            "parent_doc_type": "github_issue",
        }]

        db_conn = await get_lancedb_connection()
        if not db_conn:
            return {"status": "error", "message": "Failed to connect to LanceDB."}

        result = await add_processed_document(db_conn, doc_meta, chunks_data)
        return result

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching GitHub issue: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to fetch GitHub issue: {str(e)}"}

if __name__ == '__main__':
    import asyncio

    async def main_test():
        repo = "owner/repo"
        issue_number = 1
        user_id = "test_user_123"

        result = await ingest_github_issue(repo, issue_number, user_id)
        print(result)

    # asyncio.run(main_test())
    pass
