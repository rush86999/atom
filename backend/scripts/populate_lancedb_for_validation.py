#!/usr/bin/env python3
"""
Populate LanceDB for Hybrid Search Validation
Ensures rich data exists for Docs, Meetings, and Tasks with proper embeddings.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend.core.lancedb_handler import LanceDBHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def populate_db():
    logger.info("Initializing LanceDB Handler...")
    # Force local embeddings to ensure consistency without API keys if possible
    handler = LanceDBHandler(embedding_provider="local")
    
    if not handler.db:
        logger.error("Failed to connect to LanceDB")
        return False

    # Test Data Categories
    documents = [
        # DOCUMENTS
        {
            "text": "The Q4 Marketing Strategy focuses on organic growth through content marketing and SEO optimization. Key targets include a 20% increase in inbound leads.",
            "source": "doc",
            "metadata": {"title": "Q4 Marketing Plan", "type": "document", "author": "Sarah J."}
        },
        {
            "text": "API Documentation v2.0: All endpoints now require Bearer token authentication. Rate limits are set to 100 requests per minute.",
            "source": "doc",
            "metadata": {"title": "API Docs v2.0", "type": "document", "author": "Dev Team"}
        },
        
        # MEETINGS
        {
            "text": "Meeting Transcript: Team discussed the new frontend architecture. decided to migrate to Next.js 14 for better server-side rendering performance. Action items: JIRA-123, JIRA-124.",
            "source": "meeting",
            "metadata": {"title": "Frontend Architecture Review", "type": "meeting", "attendees": ["Alice", "Bob"]}
        },
        {
            "text": "Client Call Notes: Client requested a new feature for exporting reports to PDF. Timeline agreed for delivery is next Friday.",
            "source": "meeting",
            "metadata": {"title": "Weekly Client Sync", "type": "meeting", "attendees": ["Client", "PM"]}
        },
        
        # TASKS
        {
            "text": "Task: Fix the login page layout issue on mobile devices. The submit button is overlapping with the footer.",
            "source": "task",
            "metadata": {"title": "Fix Mobile Login", "type": "task", "priority": "high"}
        },
        {
            "text": "Task: Update the database schema to support multi-tenant architecture. Migration script needed.",
            "source": "task",
            "metadata": {"title": "DB Schema Migration", "type": "task", "priority": "critical"}
        }
    ]

    logger.info(f"Seeding {len(documents)} items into 'document_chunks' table...")
    
    # Use the batch add method
    count = handler.add_documents_batch("document_chunks", documents)
    
    if count > 0:
        logger.info(f"✅ Successfully added {count} documents.")
        return True
    else:
        logger.error("❌ Failed to add documents.")
        return False

def verify_search():
    logger.info("Verifying Search Functionality...")
    handler = LanceDBHandler(embedding_provider="local")
    
    # Test Query 1: "marketing plan" (Should find Doc)
    results = handler.search("document_chunks", "marketing strategy", limit=1)
    if results and "Marketing" in results[0]['text']:
        logger.info("✅ Search Verification 1 (Doc): PASS")
    else:
        logger.warning(f"❌ Search Verification 1 (Doc): FAIL - {results}")

    # Test Query 2: "next.js" (Should find Meeting)
    results = handler.search("document_chunks", "frontend framework", limit=1)
    if results and "Next.js" in results[0]['text']:
        logger.info("✅ Search Verification 2 (Meeting): PASS")
    else:
        logger.warning(f"❌ Search Verification 2 (Meeting): FAIL - {results}")

if __name__ == "__main__":
    if populate_db():
        verify_search()
    else:
        sys.exit(1)
