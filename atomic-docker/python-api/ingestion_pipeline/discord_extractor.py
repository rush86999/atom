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

DISCORD_API_BASE_URL = 'https://discord.com/api'
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

async def get_discord_access_token(user_id: str) -> Optional[str]:
    db = SessionLocal()
    try:
        query = text("SELECT encrypted_access_token FROM user_tokens WHERE user_id = :user_id AND service = 'discord'")
        result = db.execute(query, {"user_id": user_id}).fetchone()
        if result and result[0]:
            return decrypt(result[0])
        return None
    finally:
        db.close()

async def ingest_discord_messages(channel_id: str, user_id: str) -> Dict[str, Any]:
    """
    Fetches messages from a Discord channel and ingests them into LanceDB.
    """
    access_token = await get_discord_access_token(user_id)
    if not access_token:
        return {"status": "error", "message": "Discord access token not found."}

    headers = {'Authorization': f'Bearer {access_token}'}
    url = f'{DISCORD_API_BASE_URL}/channels/{channel_id}/messages'

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        messages = response.json()

        db_conn = await get_lancedb_connection()
        if not db_conn:
            return {"status": "error", "message": "Failed to connect to LanceDB."}

        for message in messages:
            doc_id = f"discord-message-{message['id']}"
            doc_meta = {
                "doc_id": doc_id,
                "user_id": user_id,
                "source_uri": f"https://discord.com/channels/@me/{channel_id}/{message['id']}",
                "doc_type": "discord_message",
                "title": f"Message from {message['author']['username']}",
                "metadata_json": "{}",
                "created_at_source": message['timestamp'],
                "last_modified_source": message['edited_timestamp'],
                "ingested_at": "NOW()",
                "processing_status": "SUCCESS",
            }

            chunks_data = [{
                "doc_id": doc_id,
                "user_id": user_id,
                "chunk_sequence": 0,
                "text_content": message['content'],
                "parent_doc_type": "discord_message",
            }]

            await add_processed_document(db_conn, doc_meta, chunks_data)

        return {"status": "success", "messages_ingested": len(messages)}

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Discord messages: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to fetch Discord messages: {str(e)}"}

if __name__ == '__main__':
    import asyncio

    async def main_test():
        channel_id = "your_channel_id"
        user_id = "test_user_123"

        result = await ingest_discord_messages(channel_id, user_id)
        print(result)

    # asyncio.run(main_test())
    pass
