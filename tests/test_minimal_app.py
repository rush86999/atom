#!/usr/bin/env python3
"""
Minimal test of the LanceDB integration functionality.
This test focuses on the core LanceDB functionality that has been successfully implemented.
"""

import os
import sys
import asyncio
import tempfile

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend', 'python-api-service'))

async def test_lancedb_integration():
    """Test the complete LanceDB integration"""
    print("🧪 Testing LanceDB Integration...")

    try:
        from lancedb_handler import (
            get_lancedb_connection,
            create_generic_document_tables_if_not_exist,
            add_processed_document,
            search_documents,
            get_document_stats,
            delete_document
        )

        # Set test environment
        os.environ["LANCEDB_URI"] = "/tmp/test_lancedb_minimal"

        # Get LanceDB connection
        print("🔗 Connecting to LanceDB...")
        db_conn = await get_lancedb_connection()
        if db_conn is None:
            print("❌ Failed to connect to LanceDB")
            return False

        # Create tables
        print("📊 Creating tables...")
        tables_created = await create_generic_document_tables_if_not_exist(db_conn)
        if not tables_created:
            print("❌ Failed to create tables")
            return False

        # Test document
        print("📝 Adding test document...")
        doc_meta = {
            "doc_id": "test_minimal_doc",
            "user_id": "test_user",
            "source_uri": "file:///test.txt",
            "doc_type": "text",
            "title": "Test Document",
            "metadata_json": '{"test": "data"}',
            "processing_status": "completed"
        }

        chunks = [{
            "chunk_sequence": 0,
            "text_content": "This is test content about artificial intelligence and machine learning.",
            "embedding": [0.1] * 1536,
            "metadata_json": '{"section": "test"}'
        }]

        result = await add_processed_document(db_conn, doc_meta, chunks)
        if result["status"] != "success":
            print(f"❌ Failed to add document: {result['message']}")
            return False

        # Test search functionality
        print("🔍 Testing search functionality...")
        query_vector = [0.1] * 1536
        search_result = await search_documents(db_conn, query_vector, "test_user", limit=5)

        if search_result["status"] != "success":
            print(f"❌ Search failed: {search_result['message']}")
            return False

        print(f"✅ Search found {search_result['count']} documents")

        # Test document statistics
        print("📈 Testing document statistics...")
        stats_result = await get_document_stats(db_conn, "test_user")

        if stats_result["status"] != "success":
            print(f"❌ Stats failed: {stats_result['message']}")
            return False

        print(f"✅ Statistics: {stats_result['total_documents']} documents, {stats_result['total_chunks']} chunks")

        # Test document deletion
        print("🗑️ Testing document deletion...")
        delete_result = await delete_document(db_conn, "test_minimal_doc", "test_user")

        if delete_result["status"] != "success":
            print(f"❌ Deletion failed: {delete_result['message']}")
            return False

        print("✅ Document deleted successfully")

        print("🎉 LanceDB integration test passed!")
        return True

    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_document_processor():
    """Test document processor integration"""
    print("🧪 Testing Document Processor Integration...")

    try:
        from document_processor import process_document_and_store
        import tempfile
        import os

        # Create test document in a temporary file
        test_content = "This is a test document for the document processor integration."

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

            if result["status"] == "success":
                print(f"✅ Document processor integration successful: {result['data']['num_chunks_stored']} chunks stored")
                return True
            else:
                print(f"❌ Document processor failed: {result['message']}")
                return False

        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    except Exception as e:
        print(f"❌ Document processor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests"""
    print("🚀 Running LanceDB Integration Tests")
    print("=" * 50)

    # Test LanceDB functionality
    lancedb_success = await test_lancedb_integration()

    # Test document processor integration
    processor_success = await test_document_processor()

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
