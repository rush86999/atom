"""
Demo Script for LanceDB Hybrid Storage with S3

This script demonstrates the LanceDB hybrid storage system with:
- Local storage for fast desktop access
- S3 as primary storage backend
- Automatic sync between local and S3
- Multi-user isolation
"""

import os
import asyncio
import logging
import tempfile
import json
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


async def demo_hybrid_storage_basic():
    """Demonstrate basic hybrid storage functionality"""
    logger.info("🚀 Starting LanceDB Hybrid Storage Demo")

    try:
        # Set up environment for demo
        os.environ.update(
            {
                "LANCEDB_URI": "data/demo_lancedb",
                "S3_STORAGE_ENABLED": "false",  # Disable S3 for basic demo
                "LOCAL_CACHE_ENABLED": "true",
                "S3_BACKUP_ENABLED": "false",
            }
        )

        from sync.lancedb_storage_service import create_lancedb_storage_service

        # Create storage service
        storage_service = create_lancedb_storage_service()

        # Test user data
        user_id = "demo_user_1"

        # Prepare demo document
        document_data = {
            "doc_id": "demo_doc_001",
            "doc_type": "demo",
            "title": "Demo Document",
            "source_uri": "demo://test/document1",
            "metadata": {
                "author": "demo_script",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "demo_purpose": "hybrid_storage_test",
            },
        }

        # Prepare demo chunks with embeddings
        chunks_with_embeddings = [
            {
                "text_content": "This is the first chunk of the demo document for hybrid storage testing.",
                "embedding": [0.1] * 1536,  # Mock embedding
                "metadata": {"chunk_index": 0, "type": "introduction"},
            },
            {
                "text_content": "This is the second chunk demonstrating the hybrid storage capabilities.",
                "embedding": [0.2] * 1536,  # Mock embedding
                "metadata": {"chunk_index": 1, "type": "content"},
            },
            {
                "text_content": "This is the third chunk showing how local and S3 storage work together.",
                "embedding": [0.3] * 1536,  # Mock embedding
                "metadata": {"chunk_index": 2, "type": "conclusion"},
            },
        ]

        # Store document
        logger.info("💾 Storing document with hybrid storage...")
        storage_result = await storage_service.store_document(
            user_id=user_id,
            document_data=document_data,
            chunks_with_embeddings=chunks_with_embeddings,
        )

        print(f"Storage Result: {json.dumps(storage_result, indent=2)}")

        # Search documents
        logger.info("🔍 Searching documents...")
        search_result = await storage_service.search_documents(
            user_id=user_id,
            query_vector=[0.1] * 1536,  # Mock query vector
            limit=5,
        )

        print(f"Search Result: {json.dumps(search_result, indent=2)}")

        # Get storage status
        logger.info("📊 Getting storage status...")
        status_result = await storage_service.get_storage_status(user_id)

        print(f"Storage Status: {json.dumps(status_result, indent=2)}")

        logger.info("✅ Basic hybrid storage demo completed!")

    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
        import traceback

        traceback.print_exc()


async def demo_s3_primary_storage():
    """Demonstrate S3 as primary storage backend"""
    logger.info("☁️ Starting S3 Primary Storage Demo")

    try:
        # Check if S3 is configured
        s3_bucket = os.environ.get("S3_BUCKET")
        if not s3_bucket:
            logger.info("S3 not configured - skipping S3 primary demo")
            return

        # Set up environment for S3 primary
        os.environ.update(
            {
                "S3_STORAGE_ENABLED": "true",
                "USE_S3_AS_PRIMARY": "true",
                "LOCAL_CACHE_ENABLED": "true",  # Keep local cache for performance
            }
        )

        from sync.lancedb_storage_service import create_lancedb_storage_service

        # Create storage service
        storage_service = create_lancedb_storage_service()

        # Test user data
        user_id = "s3_user_1"

        # Prepare demo document
        document_data = {
            "doc_id": "s3_doc_001",
            "doc_type": "s3_demo",
            "title": "S3 Primary Storage Document",
            "source_uri": "s3://demo/document1",
            "metadata": {
                "storage_backend": "s3_primary",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        chunks_with_embeddings = [
            {
                "text_content": "This document is stored using S3 as the primary storage backend.",
                "embedding": [0.4] * 1536,
                "metadata": {"chunk_index": 0},
            }
        ]

        # Store document in S3 primary
        logger.info("💾 Storing document in S3 primary...")
        result = await storage_service.store_document(
            user_id=user_id,
            document_data=document_data,
            chunks_with_embeddings=chunks_with_embeddings,
        )

        print(f"S3 Primary Storage Result: {json.dumps(result, indent=2)}")

        # Verify storage backend
        status = await storage_service.get_storage_status(user_id)
        print(f"S3 Storage Status: {json.dumps(status, indent=2)}")

        logger.info("✅ S3 primary storage demo completed!")

    except Exception as e:
        logger.error(f"❌ S3 primary demo failed: {e}")
        import traceback

        traceback.print_exc()


async def demo_local_with_s3_backup():
    """Demonstrate local storage with S3 backup"""
    logger.info("🔄 Starting Local + S3 Backup Demo")

    try:
        # Check if S3 backup is configured
        s3_backup_bucket = os.environ.get("S3_BACKUP_BUCKET")
        if not s3_backup_bucket:
            logger.info("S3 backup not configured - skipping backup demo")
            return

        # Set up environment for local + S3 backup
        os.environ.update(
            {
                "S3_STORAGE_ENABLED": "false",  # Use local as primary
                "S3_BACKUP_ENABLED": "true",  # Enable S3 backup
                "LOCAL_CACHE_ENABLED": "true",
            }
        )

        from sync.lancedb_storage_service import create_lancedb_storage_service
        from sync.incremental_sync_service import create_incremental_sync_service

        # Create services
        storage_service = create_lancedb_storage_service()
        sync_service = create_incremental_sync_service()

        # Test user data
        user_id = "backup_user_1"

        # Prepare demo document
        document_data = {
            "doc_id": "backup_doc_001",
            "doc_type": "backup_demo",
            "title": "Local Storage with S3 Backup",
            "source_uri": "local://backup/document1",
            "metadata": {
                "storage_mode": "local_primary_s3_backup",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        chunks_with_embeddings = [
            {
                "text_content": "This document is stored locally with automatic S3 backup.",
                "embedding": [0.5] * 1536,
                "metadata": {"chunk_index": 0},
            }
        ]

        # Store document locally
        logger.info("💾 Storing document locally...")
        storage_result = await storage_service.store_document(
            user_id=user_id,
            document_data=document_data,
            chunks_with_embeddings=chunks_with_embeddings,
        )

        print(f"Local Storage Result: {json.dumps(storage_result, indent=2)}")

        # Sync to S3 backup
        logger.info("🔄 Syncing to S3 backup...")
        sync_result = await storage_service.sync_user_data(user_id)

        print(f"Sync Result: {json.dumps(sync_result, indent=2)}")

        # Get sync status
        sync_status = await sync_service.get_sync_status(user_id)
        print(f"Sync Status: {json.dumps(sync_status, indent=2)}")

        logger.info("✅ Local + S3 backup demo completed!")

    except Exception as e:
        logger.error(f"❌ Backup demo failed: {e}")
        import traceback

        traceback.print_exc()


async def demo_multi_user_isolation():
    """Demonstrate multi-user data isolation"""
    logger.info("👥 Starting Multi-User Isolation Demo")

    try:
        from sync.lancedb_storage_service import create_lancedb_storage_service

        # Create storage service
        storage_service = create_lancedb_storage_service()

        # Multiple test users
        users = [
            {"id": "user_alice", "name": "Alice"},
            {"id": "user_bob", "name": "Bob"},
            {"id": "user_charlie", "name": "Charlie"},
        ]

        for user in users:
            user_id = user["id"]

            # Prepare user-specific document
            document_data = {
                "doc_id": f"user_doc_{user_id}",
                "doc_type": "user_demo",
                "title": f"Document for {user['name']}",
                "source_uri": f"user://{user_id}/document1",
                "metadata": {
                    "user_name": user["name"],
                    "user_id": user_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            }

            chunks_with_embeddings = [
                {
                    "text_content": f"This is a private document for {user['name']} only.",
                    "embedding": [0.6] * 1536,
                    "metadata": {"chunk_index": 0, "user_specific": True},
                }
            ]

            # Store document for each user
            logger.info(f"💾 Storing document for {user['name']}...")
            result = await storage_service.store_document(
                user_id=user_id,
                document_data=document_data,
                chunks_with_embeddings=chunks_with_embeddings,
            )

            print(f"Storage for {user['name']}: {json.dumps(result, indent=2)}")

            # Get individual user status
            status = await storage_service.get_storage_status(user_id)
            print(f"Status for {user['name']}: {json.dumps(status, indent=2)}")

        logger.info("✅ Multi-user isolation demo completed!")

    except Exception as e:
        logger.error(f"❌ Multi-user demo failed: {e}")
        import traceback

        traceback.print_exc()


async def demo_storage_modes():
    """Demonstrate different storage modes"""
    logger.info("🎛️ Starting Storage Modes Demo")

    try:
        from sync import get_config, update_config

        # Get current configuration
        config = get_config()

        storage_modes = [
            {
                "name": "Local Only",
                "config": {
                    "s3_storage_enabled": False,
                    "s3_backup_enabled": False,
                    "local_cache_enabled": True,
                },
            },
            {
                "name": "S3 Primary + Local Cache",
                "config": {
                    "s3_storage_enabled": True,
                    "use_s3_as_primary": True,
                    "local_cache_enabled": True,
                    "s3_backup_enabled": False,
                },
            },
            {
                "name": "Local Primary + S3 Backup",
                "config": {
                    "s3_storage_enabled": False,
                    "s3_backup_enabled": True,
                    "local_cache_enabled": True,
                },
            },
            {
                "name": "S3 Only (No Local Cache)",
                "config": {
                    "s3_storage_enabled": True,
                    "use_s3_as_primary": True,
                    "local_cache_enabled": False,
                    "s3_backup_enabled": False,
                },
            },
        ]

        for mode in storage_modes:
            logger.info(f"🔄 Testing storage mode: {mode['name']}")

            # Update configuration
            updated_config = update_config(**mode["config"])

            print(f"\n{mode['name']} Configuration:")
            print(f"  S3 Storage: {updated_config.s3_storage_enabled}")
            print(f"  S3 Primary: {updated_config.use_s3_as_primary}")
            print(f"  Local Cache: {updated_config.local_cache_enabled}")
            print(f"  S3 Backup: {updated_config.s3_backup_enabled}")

            # Test basic functionality
            from sync.lancedb_storage_service import create_lancedb_storage_service

            storage_service = create_lancedb_storage_service()
            user_id = f"mode_test_{mode['name'].lower().replace(' ', '_')}"

            try:
                status = await storage_service.get_storage_status(user_id)
                print(f"  Status: ✅ Operational")
                print(f"  Backend: {status.get('storage_backend', 'unknown')}")
            except Exception as e:
                print(f"  Status: ❌ Failed - {e}")

        logger.info("✅ Storage modes demo completed!")

    except Exception as e:
        logger.error(f"❌ Storage modes demo failed: {e}")
        import traceback

        traceback.print_exc()


async def main():
    """Run all hybrid storage demos"""
    print("🎯 LanceDB Hybrid Storage - Complete Demo")
    print("=" * 60)

    # Create necessary directories
    os.makedirs("data", exist_ok=True)

    # Run demos
    await demo_hybrid_storage_basic()
    print("\n" + "=" * 60 + "\n")

    await demo_s3_primary_storage()
    print("\n" + "=" * 60 + "\n")

    await demo_local_with_s3_backup()
    print("\n" + "=" * 60 + "\n")

    await demo_multi_user_isolation()
    print("\n" + "=" * 60 + "\n")

    await demo_storage_modes()

    print("\n" + "=" * 60)
    print("🎉 All hybrid storage demos completed!")
    print("=" * 60)


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())
