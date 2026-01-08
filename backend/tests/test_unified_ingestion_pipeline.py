import asyncio
import os
import sys
import logging
from datetime import datetime
from unittest.mock import MagicMock, patch

# Add the backend directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# MOCK BEFORE IMPORTS
import sentence_transformers
sentence_transformers.SentenceTransformer = MagicMock()

print("🔍 Importing pipeline components...")
from integrations.atom_ingestion_pipeline import atom_ingestion_pipeline, RecordType
from integrations.atom_communication_ingestion_pipeline import memory_manager

# Force mock on the instance as well
memory_manager.model = MagicMock()
memory_manager.model.encode.return_value = [0.1] * 768

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_unified_ingestion():
    print("🧪 Testing Unified Ingestion Pipeline...")
    
    # Set test environment
    test_db_path = "/tmp/test_atom_memory"
    
    # Clean up old DB
    import shutil
    if os.path.exists(test_db_path):
        print(f"🧹 Cleaning up existing test DB at {test_db_path}...")
        shutil.rmtree(test_db_path)
    
    os.environ["LANCEDB_URI"] = test_db_path
    
    # Initialize memory manager
    print(f"🔗 Initializing Memory Manager at {test_db_path}...")
    memory_manager.db_path = test_db_path
    
    # Mock the embedding generation to avoid any heavy lifting
    memory_manager.generate_embedding = MagicMock(return_value=[0.1] * 768)
    
    if not memory_manager.initialize():
        print("❌ Failed to initialize LanceDB")
        return False
    print("✅ Memory Manager initialized")

    # 1. Test HubSpot Ingestion
    print("📝 Testing HubSpot Contact Ingestion...")
    hubspot_contact = {
        "id": "hs_contact_123",
        "properties": {
            "firstname": "John",
            "lastname": "Doe",
            "email": "john.doe@example.com"
        }
    }
    success = atom_ingestion_pipeline.ingest_record("hubspot", RecordType.CONTACT.value, hubspot_contact)
    if not success:
        print("❌ HubSpot ingestion failed")
        return False
    print("✅ HubSpot Contact ingested")

    # 2. Test Zoom Ingestion
    print("📝 Testing Zoom Meeting Ingestion...")
    zoom_meeting = {
        "meeting_id": "8472947294",
        "topic": "Atom Ingestion Sync",
        "host_id": "zoom_user_1",
        "status": "started"
    }
    success = atom_ingestion_pipeline.ingest_record("zoom", RecordType.MEETING.value, zoom_meeting)
    if not success:
        print("❌ Zoom ingestion failed")
        return False
    print("✅ Zoom Meeting ingested")

    # 3. Test Salesforce Ingestion
    print("📝 Testing Salesforce Lead Ingestion...")
    sf_lead = {
        "Id": "sf_lead_456",
        "FirstName": "Jane",
        "LastName": "Smith",
        "Company": "Tech Corp"
    }
    success = atom_ingestion_pipeline.ingest_record("salesforce", RecordType.LEAD.value, sf_lead)
    if not success:
        print("❌ Salesforce ingestion failed")
        return False
    print("✅ Salesforce Lead ingested")

    # 4. Test Slack Ingestion
    print("📝 Testing Slack Message Ingestion...")
    slack_msg = {
        "id": "slack_msg_789",
        "text": "Hello team, let's discuss the new memory system.",
        "ts": "1672531200.000000",
        "user": "U12345"
    }
    success = atom_ingestion_pipeline.ingest_record("slack", RecordType.COMMUNICATION.value, slack_msg)
    if not success:
        print("❌ Slack ingestion failed")
        return False
    print("✅ Slack Message ingested")

    # 5. Verify Retrieval (Hybrid Search)
    print("🔍 Verifying Retrieval from LanceDB (Hybrid Search)...")
    
    # 5a. Vector/Semantic Focus
    print("🔍 Testing Semantic Retrieval...")
    results = memory_manager.search_communications("John Doe", limit=5)
    print(f"DEBUG: Found {len(results)} results for 'John Doe'")
    if not any("John Doe" in str(r) for r in results):
        print("❌ Failed to retrieve HubSpot contact by semantic content")
        return False
    print("✅ HubSpot contact found by semantic search")

    # 5b. Keyword/FTS Focus
    print("🔍 Testing Keyword Retrieval (FTS)...")
    results = memory_manager.search_communications("Tech Corp", limit=5)
    print(f"DEBUG: Found {len(results)} results for 'Tech Corp'")
    if not any("Tech Corp" in str(r) for r in results):
        print("❌ Failed to retrieve Salesforce lead by keyword (FTS)")
        return False
    print("✅ Salesforce lead found by keyword search")

    print("🎉 All Hybrid Ingestion & Search tests passed!")
    return True

if __name__ == "__main__":
    try:
        asyncio.run(test_unified_ingestion())
    except Exception as e:
        print(f"💥 Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
