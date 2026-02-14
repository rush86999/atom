
import sys
import os
import logging
from datetime import datetime

# Add backend to path
sys.path.append(os.getcwd())

from core.lancedb_handler import LanceDBHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("populate_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def populate_documents():
    logger.info("Initializing LanceDB Handler...")
    
    # Debug connection directly to see error
    try:
        import lancedb
        # Use same path as Handler default or env
        db_path = os.getenv("LANCEDB_URI", "./data/atom_memory")
        if not db_path.startswith("s3://"):
             db_path = os.path.abspath(db_path)
        logger.info(f"DEBUG: Attempting to connect to {db_path}...")
        db = lancedb.connect(db_path)
        logger.info("DEBUG: Direct connection successful.")
    except Exception as e:
        logger.error(f"DEBUG: Direct connection failed: {e}")

    handler = LanceDBHandler(embedding_provider="local")
    
    logger.info(f"DEBUG: handler.db type: {type(handler.db)}")
    logger.info(f"DEBUG: handler.db value: {handler.db}")

    if handler.db is None:
        logger.error("Failed to connect to LanceDB")
        return False

    # Seed data with user_id="user-123" to match frontend mock
    documents = [
        {
            "text": "The Q4 Marketing Strategy focuses on organic growth through content marketing and SEO optimization.",
            "source": "doc",
            "user_id": "user-123",
            "metadata": {"title": "Q4 Marketing Plan", "doc_type": "document", "author": "Sarah J."}
        },
        {
            "text": "Meeting Transcript: Team discussed the new frontend architecture. Decide to migrate to Next.js 14.",
            "source": "meeting",
            "user_id": "user-123",
            "metadata": {"title": "Frontend Arch Review", "doc_type": "meeting", "attendees": ["Alice", "Bob"]}
        },
        {
            "text": "Project Requirements: The new search feature must support hybrid search and be resilient to database failures.",
            "source": "doc",
            "user_id": "user-123", # Crucial for frontend search
            "metadata": {"title": "Search Requirements", "doc_type": "document", "author": "Product Owner"}
        }
    ]

    logger.info(f"Seeding {len(documents)} items into 'documents' table with user_id='user-123'...")
    
    count = handler.add_documents_batch("documents", documents)
    
    if count > 0:
        logger.info(f"✅ Successfully added {count} documents to 'documents' table.")
        return True
    else:
        logger.error("❌ Failed to add documents.")
        return False

def verify_search():
    logger.info("Verifying Search Functionality...")
    handler = LanceDBHandler(embedding_provider="local")
    
    # Simulate frontend request with user_id="user-123"
    results = handler.search("documents", "marketing", user_id="user-123", limit=1)
    
    if results:
        logger.info(f"✅ Search Verification PASS. Found: {results[0]['metadata'].get('title')}")
    else:
        logger.warning(f"❌ Search Verification FAIL. No results found.")

if __name__ == "__main__":
    if populate_documents():
        verify_search()
