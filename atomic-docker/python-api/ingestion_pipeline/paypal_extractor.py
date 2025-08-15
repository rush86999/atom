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

PAYPAL_API_BASE_URL = 'https://api-m.sandbox.paypal.com'
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

async def get_paypal_access_token(user_id: str) -> Optional[str]:
    db = SessionLocal()
    try:
        query = text("SELECT encrypted_access_token FROM user_tokens WHERE user_id = :user_id AND service = 'paypal'")
        result = db.execute(query, {"user_id": user_id}).fetchone()
        if result and result[0]:
            return decrypt(result[0])
        return None
    finally:
        db.close()

async def ingest_paypal_transactions(user_id: str) -> Dict[str, Any]:
    """
    Fetches transactions from PayPal and ingests them into LanceDB.
    """
    access_token = await get_paypal_access_token(user_id)
    if not access_token:
        return {"status": "error", "message": "PayPal access token not found."}

    headers = {'Authorization': f'Bearer {access_token}'}
    url = f'{PAYPAL_API_BASE_URL}/v1/reporting/transactions'

    try:
        response = requests.get(url, headers=headers, params={
            'start_date': '2023-01-01T00:00:00-0700',
            'end_date': '2025-12-31T23:59:59-0700',
            'fields': 'all'
        })
        response.raise_for_status()
        transactions = response.json()['transaction_details']

        db_conn = await get_lancedb_connection()
        if not db_conn:
            return {"status": "error", "message": "Failed to connect to LanceDB."}

        for transaction in transactions:
            transaction_info = transaction['transaction_info']
            doc_id = f"paypal-transaction-{transaction_info['transaction_id']}"
            doc_meta = {
                "doc_id": doc_id,
                "user_id": user_id,
                "source_uri": f"https://www.paypal.com/activity/payment/{transaction_info['transaction_id']}",
                "doc_type": "paypal_transaction",
                "title": f"Transaction {transaction_info['transaction_id']}",
                "metadata_json": "{}",
                "created_at_source": transaction_info['transaction_initiation_date'],
                "last_modified_source": transaction_info['transaction_updated_date'],
                "ingested_at": "NOW()",
                "processing_status": "SUCCESS",
            }

            chunks_data = [{
                "doc_id": doc_id,
                "user_id": user_id,
                "chunk_sequence": 0,
                "text_content": str(transaction),
                "parent_doc_type": "paypal_transaction",
            }]

            await add_processed_document(db_conn, doc_meta, chunks_data)

        return {"status": "success", "transactions_ingested": len(transactions)}

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching PayPal transactions: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to fetch PayPal transactions: {str(e)}"}

if __name__ == '__main__':
    import asyncio

    async def main_test():
        user_id = "test_user_123"

        result = await ingest_paypal_transactions(user_id)
        print(result)

    # asyncio.run(main_test())
    pass
