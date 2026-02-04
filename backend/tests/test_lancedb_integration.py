#!/usr/bin/env python3
"""
Test script for LanceDB integration in Atom personal assistant.
This script tests the complete LanceDB functionality including document storage and retrieval.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend', 'python-api-service'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_lancedb_integration():
    """Test the complete LanceDB integration"""
    print("🧪 Testing LanceDB Integration...")

    try:
        # Import the LanceDB handler
        from lancedb_handler import (
            add_processed_document,
            create_generic_document_tables_if_not_exist,
            delete_document,
            get_document_stats,
            get_lancedb_connection,
            search_documents,
        )

        # Set test environment
        os.environ["LANCEDB_URI"] = "/tmp/test_lancedb"

        # Get LanceDB connection
        print("🔗 Connecting to LanceDB...")
        db_conn = await get_lancedb_connection()
        print(f"🔗 Connection object: {db_conn}")
        print(f"🔗 Connection type: {type(db_conn)}")
        if db_conn is None:
            print("❌ Failed to connect to LanceDB")
            return False

        # Create tables
        print("📊 Creating tables...")
        tables_created = await create_generic_document_tables_if_not_exist(db_conn)
        print(f"📊 Tables created: {tables_created}")
        if tables_created is False:
            print("❌ Failed to create tables")
            return False

        # Test document 1
        print("📝 Adding test document 1...")
        doc_meta_1 = {
            "doc_id": "test_doc_1",
            "user_id": "test_user",
            "source_uri": "file:///test/document1.txt",
            "doc_type": "text",
            "title": "Test Document 1",
            "metadata_json": '{"author": "Test User", "category": "test"}',
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "processing_status": "completed"
        }

        chunks_1 = [
            {
                "chunk_sequence": 0,
                "text_content": "This is the first chunk of test document 1 about artificial intelligence and machine learning.",
                "embedding": [0.1] * 1536,  # Mock embedding
                "metadata_json": '{"section": "introduction"}'
            },
            {
                "chunk_sequence": 1,
                "text_content": "The second chunk discusses neural networks and deep learning applications in natural language processing.",
                "embedding": [0.2] * 1536,  # Mock embedding
                "metadata_json": '{"section": "body"}'
            }
        ]

        result_1 = await add_processed_document(db_conn, doc_meta_1, chunks_1)
        print(f"📝 Document 1 result: {result_1}")
        if result_1["status"] != "success":
            print(f"❌ Failed to add document 1: {result_1['message']}")
            return False

        # Test document 2
        print("📝 Adding test document 2...")
        doc_meta_2 = {
            "doc_id": "test_doc_2",
            "user_id": "test_user",
            "source_uri": "file:///test/document2.pdf",
            "doc_type": "pdf",
            "title": "Test Document 2",
            "metadata_json": '{"author": "Another User", "category": "research"}',
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "processing_status": "completed"
        }

        chunks_2 = [
            {
                "chunk_sequence": 0,
                "text_content": "This document covers data science topics including statistics and machine learning algorithms.",
                "embedding": [0.15] * 1536,  # Mock embedding
                "metadata_json": '{"section": "abstract"}'
            },
            {
                "chunk_sequence": 1,
                "text_content": "Detailed analysis of regression models and classification techniques for predictive analytics.",
                "embedding": [0.25] * 1536,  # Mock embedding
                "metadata_json": '{"section": "methodology"}'
            }
        ]

        result_2 = await add_processed_document(db_conn, doc_meta_2, chunks_2)
        print(f"📝 Document 2 result: {result_2}")
        if result_2["status"] != "success":
            print(f"❌ Failed to add document 2: {result_2['message']}")
            return False

        # Test search functionality
        print("🔍 Testing search functionality...")
        query_vector = [0.12] * 1536  # Mock query vector similar to our documents
        search_result = await search_documents(db_conn, query_vector, "test_user", limit=5)

        if search_result["status"] != "success":
            print(f"❌ Search failed: {search_result['message']}")
            return False

        print(f"✅ Search found {search_result['count']} documents")
        for i, result in enumerate(search_result["results"]):
            print(f"  {i+1}. {result['title']} ({len(result['chunks'])} chunks)")

        # Test document statistics
        print("📈 Testing document statistics...")
        stats_result = await get_document_stats(db_conn, "test_user")

        if stats_result["status"] != "success":
            print(f"❌ Stats failed: {stats_result['message']}")
            return False

        print(f"✅ Statistics: {stats_result['total_documents']} documents, {stats_result['total_chunks']} chunks")
        for doc_type, count in stats_result["documents_by_type"].items():
            print(f"  - {doc_type}: {count}")

        # Test document deletion
        print("🗑️ Testing document deletion...")
        delete_result = await delete_document(db_conn, "test_doc_1", "test_user")

        if delete_result["status"] != "success":
            print(f"❌ Deletion failed: {delete_result['message']}")
            return False

        print("✅ Document deleted successfully")

        # Verify deletion
        stats_after_delete = await get_document_stats(db_conn, "test_user")
        if stats_after_delete["status"] == "success":
            print(f"✅ After deletion: {stats_after_delete['total_documents']} documents remaining")

        print("🎉 All LanceDB tests passed!")
        return True

    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_document_processor_integration():
    """Test the document processor integration with LanceDB"""
    print("\n🧪 Testing Document Processor Integration...")

    try:
        import os
        import tempfile
        from document_processor import process_document_and_store

        # Create a test document in a temporary file
        test_content = """
        This is a test document for the document processor integration.
        It contains multiple paragraphs to test chunking functionality.

        The document discusses various topics including artificial intelligence,
        machine learning, and natural language processing.

        Each paragraph should be processed as a separate chunk and stored in LanceDB.
        The embeddings should be generated and the document should be searchable.
        """

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp_file:
            tmp_file.write(test_content)
            tmp_file_path = tmp_file.name

        try:
            # Test processing
            result = await process_document_and_store(
                user_id="test_user",
                file_path_or_bytes=tmp_file_path,
                document_id="processor_test_doc",
                source_uri="file:///test/processor_test.txt",
                original_doc_type="text",
                processing_mime_type="text/plain",
                title="Processor Test Document"
            )

        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

        if result["status"] == "success":
            print(f"✅ Document processor integration successful: {result['data']['num_chunks_stored']} chunks stored")
            return True
        else:
            print(f"❌ Document processor failed: {result['message']}")
            return False

    except Exception as e:
        print(f"❌ Document processor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests"""
    print("🚀 Starting LanceDB Integration Tests")
    print("=" * 50)

    # Test basic LanceDB functionality
    lancedb_success = await test_lancedb_integration()

    # Test document processor integration
    processor_success = await test_document_processor_integration()

    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"LanceDB Integration: {'✅ PASS' if lancedb_success else '❌ FAIL'}")
    print(f"Document Processor: {'✅ PASS' if processor_success else '❌ FAIL'}")

    if lancedb_success and processor_success:
        print("\n🎉 All tests passed! LanceDB integration is working correctly.")
        return 0
    else:
        print("\n💥 Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
