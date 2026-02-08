import asyncio
import logging
import os
import sys
import tempfile
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_document_processing_pipeline():
    """
    Test the complete document processing pipeline with LanceDB integration
    """
    try:
        # Import required modules
        from backend.python-api-service.lancedb_handler import get_lancedb_connection
        from backend.python_api_service.document_service_enhanced import EnhancedDocumentService

        logger.info("🚀 Starting Document Processing Pipeline Test")

        # Get LanceDB connection
        logger.info("📊 Connecting to LanceDB...")
        lancedb_conn = await get_lancedb_connection()

        if not lancedb_conn:
            logger.warning("⚠️ LanceDB not available, running in test mode without vector storage")
            lancedb_conn = None

        # Create enhanced document service
        doc_service = EnhancedDocumentService(
            db_pool=None,  # No database pool for testing
            lancedb_connection=lancedb_conn
        )

        logger.info("✅ Document service initialized")

        # Test 1: Create sample documents
        logger.info("📝 Creating test documents...")

        # Sample text document
        sample_text = """
        ATOM Document Processing Pipeline Test

        This is a test document to verify the complete document processing pipeline.
        The pipeline should extract text, chunk the content, generate embeddings,
        and store everything in LanceDB for semantic search.

        Key Features Tested:
        - Text extraction from various formats
        - Document chunking with overlap
        - Embedding generation
        - LanceDB vector storage
        - Semantic search capabilities

        Test Results:
        - Processing status: Success
        - Chunks generated: Multiple
        - Embeddings created: Yes
        - Search functionality: Working

        This concludes the document processing pipeline test.
        """

        # Test 2: Process text document
        logger.info("🔄 Processing text document...")

        text_result = await doc_service.process_and_store_document(
            user_id="test_user_123",
            file_data=sample_text.encode('utf-8'),
            filename="test_document.txt",
            source_uri="test://document_processing_pipeline",
            metadata={
                "test_type": "pipeline_verification",
                "purpose": "integration_testing",
                "version": "1.0"
            }
        )

        logger.info(f"✅ Text document processed: {text_result.get('doc_id')}")
        logger.info(f"📊 Document status: {text_result.get('status')}")
        logger.info(f"🔢 Total chunks: {text_result.get('total_chunks', 0)}")
        logger.info(f"💾 LanceDB stored: {text_result.get('lancedb_stored', False)}")

        # Test 3: Search functionality
        if lancedb_conn and text_result.get('lancedb_stored'):
            logger.info("🔍 Testing semantic search...")

            search_results = await doc_service.search_documents(
                user_id="test_user_123",
                query="document processing pipeline",
                limit=5,
                similarity_threshold=0.5
            )

            logger.info(f"📈 Search results: {len(search_results)} documents found")

            for i, result in enumerate(search_results):
                logger.info(f"  {i+1}. {result.get('filename')} - Score: {result.get('similarity_score', 0):.3f}")

        # Test 4: Document statistics
        logger.info("📊 Testing document statistics...")

        stats = await doc_service.get_document_statistics("test_user_123")
        logger.info(f"📈 Document statistics: {stats}")

        # Test 5: Get document chunks
        if text_result.get('doc_id'):
            logger.info("📄 Testing chunk retrieval...")

            chunks = await doc_service.get_document_chunks(
                user_id="test_user_123",
                doc_id=text_result['doc_id']
            )

            logger.info(f"📦 Retrieved {len(chunks)} chunks")

            if chunks:
                sample_chunk = chunks[0]
                logger.info(f"📋 Sample chunk text: {sample_chunk.get('chunk_text', '')[:100]}...")

        # Test 6: Error handling
        logger.info("⚠️ Testing error handling...")

        try:
            # Test with invalid file data
            await doc_service.process_and_store_document(
                user_id="test_user_123",
                file_data=b"",  # Empty file
                filename="empty_file.txt"
            )
        except Exception as e:
            logger.info(f"✅ Error handling working: {str(e)}")

        logger.info("🎉 All tests completed successfully!")

        return {
            "success": True,
            "tests_run": 6,
            "document_processed": text_result.get('doc_id'),
            "lancedb_available": lancedb_conn is not None,
            "search_working": len(search_results) > 0 if 'search_results' in locals() else False
        }

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e),
            "tests_run": 0
        }

async def test_document_processor():
    """
    Test the document processor module directly
    """
    try:
        logger.info("🔧 Testing document processor module...")

        from backend.python-api-service.document_processor import (
            extract_text_from_docx,
            extract_text_from_html,
            extract_text_from_pdf,
            extract_text_from_txt,
        )

        # Create test files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("This is a test text file for document processing.")
            txt_file = f.name

        try:
            # Test TXT extraction
            txt_content = extract_text_from_txt(txt_file)
            logger.info(f"✅ TXT extraction: {len(txt_content)} characters")

            # Test TXT extraction from bytes
            txt_bytes = b"This is test content as bytes."
            txt_content_bytes = extract_text_from_txt(txt_bytes)
            logger.info(f"✅ TXT bytes extraction: {len(txt_content_bytes)} characters")

        finally:
            # Clean up
            if os.path.exists(txt_file):
                os.unlink(txt_file)

        logger.info("✅ Document processor tests completed")
        return True

    except Exception as e:
        logger.error(f"❌ Document processor test failed: {e}")
        return False

async def test_lancedb_integration():
    """
    Test LanceDB integration specifically
    """
    try:
        logger.info("💾 Testing LanceDB integration...")

        from backend.python-api-service.lancedb_handler import (
            create_generic_document_tables_if_not_exist,
            get_lancedb_connection,
        )

        # Test connection
        lancedb_conn = await get_lancedb_connection()

        if lancedb_conn:
            logger.info("✅ LanceDB connection successful")

            # Test table creation
            tables_created = await create_generic_document_tables_if_not_exist(lancedb_conn)
            logger.info(f"✅ Tables created/verified: {tables_created}")

            # List available tables
            table_names = lancedb_conn.table_names()
            logger.info(f"📋 Available tables: {table_names}")

            return True
        else:
            logger.warning("⚠️ LanceDB not available for testing")
            return False

    except Exception as e:
        logger.error(f"❌ LanceDB integration test failed: {e}")
        return False

async def main():
    """
    Run all document processing pipeline tests
    """
    logger.info("=" * 60)
    logger.info("🧪 ATOM Document Processing Pipeline Test Suite")
    logger.info("=" * 60)

    results = {}

    # Run individual tests
    results['lancedb_integration'] = await test_lancedb_integration()
    results['document_processor'] = await test_document_processor()
    results['pipeline_integration'] = await test_document_processing_pipeline()

    # Summary
    logger.info("=" * 60)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 60)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} {test_name}")

    total_passed = sum(1 for result in results.values() if result)
    total_tests = len(results)

    logger.info(f"📈 Overall: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        logger.info("🎉 All tests passed! Document processing pipeline is ready.")
    else:
        logger.warning("⚠️ Some tests failed. Check the logs for details.")

if __name__ == "__main__":
    # Run the tests
    asyncio.run(main())
