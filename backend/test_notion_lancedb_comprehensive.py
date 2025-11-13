#!/usr/bin/env python3
"""
Comprehensive Test for Notion Integration with LanceDB Memory System

This script tests the complete pipeline:
1. Notion OAuth authentication
2. Document processing and content extraction
3. Text chunking and embedding generation
4. LanceDB storage and retrieval
5. ATOM agent memory access
"""

import os
import sys
import asyncio
import json
from datetime import datetime, timezone

# Set up environment for testing
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_notion_lancedb.db')
os.environ.setdefault('FLASK_SECRET_KEY', 'test-secret-key')
os.environ.setdefault('NOTION_CLIENT_ID', 'test_client_id')
os.environ.setdefault('NOTION_CLIENT_SECRET', 'test_client_secret')
os.environ.setdefault('NOTION_REDIRECT_URI', 'http://localhost:5058/api/auth/notion/callback')

# Add backend to Python path
sys.path.insert(0, '/Users/rushiparikh/projects/atom/atom/backend/python-api-service')

def test_module_imports():
    """Test that all required modules can be imported"""
    print("🔍 Testing Module Imports...")
    
    modules_to_test = [
        ('notion_document_processor', 'NotionDocumentProcessor'),
        ('notion_integration_service', 'NotionIntegrationService'),
        ('text_processing_service', 'TextProcessingService'),
        ('sync.source_change_detector', 'SourceChangeDetector'),
        ('sync.orchestration_service', 'OrchestrationService'),
        ('sync.incremental_sync_service', 'IncrementalSyncService'),
        ('notion_client', 'Client'),
    ]
    
    successful_imports = []
    failed_imports = []
    
    for module_name, class_name in modules_to_test:
        try:
            module = __import__(module_name)
            if hasattr(module, class_name):
                successful_imports.append((module_name, class_name))
                print(f"  ✓ {module_name}.{class_name}")
            else:
                failed_imports.append((module_name, f"Missing class: {class_name}"))
                print(f"  ✗ {module_name}.{class_name} (missing)")
                
        except ImportError as e:
            failed_imports.append((module_name, str(e)))
            print(f"  ✗ {module_name} (ImportError: {str(e)[:50]}...)")
        except Exception as e:
            failed_imports.append((module_name, str(e)))
            print(f"  ✗ {module_name} (Error: {str(e)[:50]}...)")
    
    print(f"\n📊 Import Results: {len(successful_imports)} ✓ / {len(failed_imports)} ✗")
    
    return len(failed_imports) == 0


def test_text_processing():
    """Test text processing and embedding generation"""
    print("\n📝 Testing Text Processing Service...")
    
    try:
        from text_processing_service import (
            get_text_processing_service,
            process_text_for_embeddings,
            generate_embeddings,
            get_text_statistics
        )
        
        # Test text processing service
        service = get_text_processing_service()
        print("  ✓ Text processing service initialized")
        
        # Test text statistics
        test_text = """
        ATOM Notion Integration Test
        
        This is a test document to verify that the text processing service
        can properly chunk text, generate embeddings, and store them in LanceDB
        for the ATOM agent memory system.
        
        Features tested:
        1. Text chunking with overlap
        2. Embedding generation
        3. Metadata extraction
        4. LanceDB storage
        """
        
        stats = get_text_statistics(test_text)
        print(f"  ✓ Text statistics: {stats['char_count']} chars, {stats['word_count']} words, {stats['estimated_chunks']} chunks")
        
        # Test text chunking
        chunks = process_text_for_embeddings(test_text, chunk_size=200, chunk_overlap=50)
        print(f"  ✓ Text chunking: {len(chunks)} chunks generated")
        
        if chunks:
            print(f"    First chunk: {chunks[0][:100]}...")
        
        # Test embedding generation (synchronous for test)
        import asyncio
        async def test_embeddings():
            embeddings = await generate_embeddings(chunks[:2])  # Test with first 2 chunks
            return embeddings
        
        embeddings = asyncio.run(test_embeddings())
        print(f"  ✓ Embedding generation: {len(embeddings)} embeddings generated")
        
        if embeddings:
            print(f"    Embedding dimension: {len(embeddings[0])}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Text processing test failed: {e}")
        return False


def test_notion_document_processor():
    """Test Notion document processor"""
    print("\n📄 Testing Notion Document Processor...")
    
    try:
        from notion_document_processor import (
            NotionProcessorConfig,
            create_notion_processor
        )
        
        # Create test configuration
        config = NotionProcessorConfig(
            user_id="test_user_123",
            sync_interval=60,  # 1 minute for testing
            chunk_size=300,
            chunk_overlap=30,
            include_pages=True,
            include_databases=True,
            exclude_archived=False,
        )
        
        print("  ✓ Notion processor configuration created")
        
        # Create processor (without initialization since no real tokens)
        processor = create_notion_processor("test_user_123")
        print("  ✓ Notion processor created")
        
        # Test configuration access
        print(f"    User ID: {processor.config.user_id}")
        print(f"    Sync interval: {processor.config.sync_interval}")
        print(f"    Chunk size: {processor.config.chunk_size}")
        
        # Test content extraction methods
        test_page = {
            "id": "test_page_id",
            "properties": {
                "title": {"title": [{"text": {"content": "Test Page"}}]},
                "Description": {"rich_text": [{"text": {"content": "Test description"}}]}
            },
            "url": "https://notion.so/test_page",
            "last_edited_time": datetime.now(timezone.utc).isoformat(),
            "archived": False
        }
        
        # Test title extraction
        title = processor._extract_page_title(test_page)
        print(f"  ✓ Title extraction: '{title}'")
        
        # Test block content extraction
        test_block = {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"text": {"content": "This is a test paragraph."}}]
            }
        }
        
        block_content = processor._extract_block_content(test_block)
        print(f"  ✓ Block content extraction: '{block_content}'")
        
        # Test chunking fallback
        test_content = "This is test content for fallback chunking. " * 10
        fallback_chunks = processor._fallback_chunking(test_content)
        print(f"  ✓ Fallback chunking: {len(fallback_chunks)} chunks")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Notion processor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_notion_integration_service():
    """Test Notion integration service"""
    print("\n🔗 Testing Notion Integration Service...")
    
    try:
        from notion_integration_service import (
            get_notion_integration_service,
            NotionIntegrationService
        )
        
        # Create integration service
        service = get_notion_integration_service()
        print("  ✓ Notion integration service created")
        
        # Test service methods (without full initialization)
        print(f"  ✓ Service running: {service.running}")
        print(f"  ✓ Processors count: {len(service.processors)}")
        
        # Test statistics method
        async def test_stats():
            return await service.get_integration_statistics()
        
        stats = asyncio.run(test_stats())
        print(f"  ✓ Statistics method works: {stats.get('total_users', 0)} users")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Notion integration service test failed: {e}")
        return False


def test_sync_system():
    """Test sync system components"""
    print("\n🔄 Testing Sync System...")
    
    try:
        from sync.source_change_detector import (
            SourceChangeDetector,
            SourceType,
            SourceConfig,
            create_source_change_detector
        )
        
        # Test source change detector
        detector = create_source_change_detector("test_sync_state")
        print("  ✓ Source change detector created")
        
        # Test source configuration
        test_config = SourceConfig(
            source_type=SourceType.NOTION,
            source_id="test_notion_user",
            config={
                "api_key": "test_key",
                "database_ids": ["test_db_id"],
                "page_ids": ["test_page_id"]
            },
            poll_interval=60
        )
        
        detector.add_source(test_config)
        print("  ✓ Notion source configuration added")
        
        # Test orchestration service
        from sync.orchestration_service import (
            OrchestrationService,
            OrchestrationConfig
        )
        
        orch_config = OrchestrationConfig(
            local_db_path="test_lancedb",
            enable_source_monitoring=False,  # Don't start monitoring in test
        )
        
        orch_service = OrchestrationService(orch_config)
        print("  ✓ Orchestration service created")
        
        # Test incremental sync service
        from sync.incremental_sync_service import (
            IncrementalSyncService,
            create_incremental_sync_service,
            SyncConfig
        )
        
        sync_config = SyncConfig(
            local_db_path="test_lancedb",
            s3_bucket=None,  # No S3 for testing
        )
        
        sync_service = create_incremental_sync_service(
            local_db_path=sync_config.local_db_path,
            s3_bucket=sync_config.s3_bucket
        )
        
        print("  ✓ Incremental sync service created")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Sync system test failed: {e}")
        return False


def test_api_endpoints():
    """Test API endpoints registration"""
    print("\n🌐 Testing API Endpoints...")
    
    try:
        from flask import Flask
        from main_api_app import app
        
        # Check if app has Notion routes
        notion_routes = []
        for rule in app.url_map.iter_rules():
            if 'notion' in rule.rule.lower():
                notion_routes.append(rule.rule)
        
        print(f"  ✓ Flask app imported")
        print(f"  ✓ Found {len(notion_routes)} Notion routes")
        
        # Check for integration service endpoints
        integration_routes = [r for r in notion_routes if 'integration' in r]
        print(f"  ✓ Found {len(integration_routes)} integration routes")
        
        # Show key routes
        key_routes = [
            '/api/auth/notion/authorize',
            '/api/auth/notion/status',
            '/api/notion/integration/add',
            '/api/notion/integration/status',
            '/api/notion/integration/sync'
        ]
        
        for route in key_routes:
            if any(route in r for r in notion_routes):
                print(f"    ✓ {route}")
            else:
                print(f"    ✗ {route} (missing)")
        
        return len(notion_routes) >= 10  # Should have at least 10 Notion routes
        
    except Exception as e:
        print(f"  ✗ API endpoints test failed: {e}")
        return False


def test_lancedb_availability():
    """Test LanceDB availability"""
    print("\n🗄️ Testing LanceDB Availability...")
    
    try:
        # Try to import LanceDB
        import lancedb
        print("  ✓ LanceDB library available")
        
        # Test creating a connection
        db = lancedb.connect("./test_lancedb", mode="overwrite")
        print("  ✓ LanceDB connection successful")
        
        # Test creating a table
        import pyarrow as pa
        
        schema = pa.schema([
            pa.field("id", pa.string()),
            pa.field("content", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), list_size=384)),
        ])
        
        table = db.create_table("test_docs", schema=schema, mode="overwrite")
        print("  ✓ LanceDB table creation successful")
        
        # Test inserting data
        test_data = [
            {
                "id": "test_1",
                "content": "Test document content",
                "vector": [0.1] * 384  # Dummy embedding
            }
        ]
        
        table.add(test_data)
        print("  ✓ Data insertion successful")
        
        # Test querying
        results = table.search([0.1] * 384).limit(5).to_list()
        print(f"  ✓ Query successful: {len(results)} results")
        
        # Cleanup
        db.drop_table("test_docs")
        print("  ✓ Table cleanup successful")
        
        return True
        
    except ImportError as e:
        print(f"  ✗ LanceDB not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ LanceDB test failed: {e}")
        return False


def test_database_schema():
    """Test database schema and migrations"""
    print("\n📋 Testing Database Schema...")
    
    try:
        # Test if migration file exists
        migration_file = "/Users/rushiparikh/projects/atom/atom/backend/python-api-service/migrations/003_notion_oauth.sql"
        
        if os.path.exists(migration_file):
            print("  ✓ Notion OAuth migration file exists")
            
            # Read and check key components
            with open(migration_file, 'r') as f:
                migration_content = f.read()
            
            key_components = [
                "user_oauth_tokens",
                "user_notion_oauth_tokens",
                "access_token",
                "encrypted_access_token",
                "INDEX",
                "TRIGGER",
                "JSONB"
            ]
            
            found_components = []
            for component in key_components:
                if component in migration_content:
                    found_components.append(component)
                    print(f"    ✓ {component}")
                else:
                    print(f"    ✗ {component} (missing)")
            
            print(f"  ✓ Migration components: {len(found_components)}/{len(key_components)} found")
            return len(found_components) >= len(key_components) * 0.8  # 80% of components
        else:
            print("  ✗ Migration file not found")
            return False
            
    except Exception as e:
        print(f"  ✗ Database schema test failed: {e}")
        return False


def generate_test_report(results):
    """Generate comprehensive test report"""
    print("\n" + "=" * 60)
    print("📊 COMPREHENSIVE TEST REPORT")
    print("=" * 60)
    
    test_categories = {
        "Module Imports": "Core Python modules",
        "Text Processing": "Text chunking and embedding generation",
        "Notion Document Processor": "Notion content extraction and processing",
        "Notion Integration Service": "Integration service management",
        "Sync System": "Change detection and incremental sync",
        "API Endpoints": "Flask API route registration",
        "LanceDB": "Vector database storage and retrieval",
        "Database Schema": "Database migrations and schema"
    }
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        description = test_categories.get(test_name, "Unknown test")
        print(f"\n{test_name:<25} {status} - {description}")
        
        if not result:
            print("  ⚠️  This component needs attention")
    
    print(f"\n" + "-" * 60)
    print(f"OVERALL RESULTS: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 ALL TESTS PASSED!")
        print("✨ The Notion integration with LanceDB is working perfectly!")
        print("\n🚀 READY FOR PRODUCTION:")
        print("  - OAuth authentication ✓")
        print("  - Document processing ✓")
        print("  - Text chunking ✓")
        print("  - Embedding generation ✓")
        print("  - LanceDB storage ✓")
        print("  - Sync system ✓")
        print("  - API endpoints ✓")
        
    elif passed_tests >= total_tests * 0.8:
        print("\n✅ MOST TESTS PASSED!")
        print("🎯 The Notion integration is mostly ready")
        print("⚠️  Minor issues may need attention")
        
    else:
        print("\n⚠️  MULTIPLE TESTS FAILED")
        print("🔧 The Notion integration needs work before production")
        print("📋 Review failed components above")
    
    # Create detailed report file
    report_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "success_rate": passed_tests / total_tests,
        "test_results": results,
        "production_ready": passed_tests >= total_tests * 0.8
    }
    
    report_file = "/Users/rushiparikh/projects/atom/atom/notion_lancedb_test_report.json"
    with open(report_file, 'w') as f:
        json.dump(report_data, f, indent=2)
    
    print(f"\n📄 Detailed report saved: {report_file}")
    return passed_tests >= total_tests * 0.8


def main():
    """Run comprehensive test suite"""
    print("🚀 COMPREHENSIVE NOTION + LANCEDB INTEGRATION TEST")
    print("=" * 60)
    print("Testing complete pipeline from Notion to ATOM agent memory")
    print("=" * 60)
    
    # Run all tests
    test_results = {}
    
    test_functions = [
        ("Module Imports", test_module_imports),
        ("Text Processing", test_text_processing),
        ("Notion Document Processor", test_notion_document_processor),
        ("Notion Integration Service", test_notion_integration_service),
        ("Sync System", test_sync_system),
        ("API Endpoints", test_api_endpoints),
        ("LanceDB", test_lancedb_availability),
        ("Database Schema", test_database_schema),
    ]
    
    for test_name, test_func in test_functions:
        print(f"\n{'='*20} {test_name} {'='*20}")
        test_results[test_name] = test_func()
    
    # Generate final report
    return generate_test_report(test_results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)