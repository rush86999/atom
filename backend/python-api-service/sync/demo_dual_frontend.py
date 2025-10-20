"""
Demo Script for Dual Frontend Storage Configurations

This script demonstrates the LanceDB storage system with different configurations
for web app (cloud-native) and desktop app (local-first) frontends.
"""

import os
import asyncio
import logging
import json
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


async def demo_web_app_configuration():
    """Demonstrate web app (cloud-native) storage configuration"""
    logger.info("🌐 Starting Web App (Cloud-Native) Demo")

    try:
        # Set up environment for web app
        os.environ.update(
            {
                "FRONTEND_TYPE": "web",
                "S3_STORAGE_ENABLED": "true",
                "USE_S3_AS_PRIMARY": "true",
                "LOCAL_CACHE_ENABLED": "true",
                "S3_BUCKET": "atom-web-primary",  # Would be real bucket in production
                "S3_BACKUP_ENABLED": "false",  # Usually not needed for web app
            }
        )

        from sync.lancedb_storage_service import create_lancedb_storage_service
        from sync import get_config

        # Get configuration
        config = get_config()

        print(f"\n📱 Web App Configuration:")
        print(f"  Frontend Type: {config.frontend_type}")
        print(f"  S3 Storage: {config.s3_storage_enabled}")
        print(f"  S3 Primary: {config.use_s3_as_primary}")
        print(f"  Local Cache: {config.local_cache_enabled}")
        print(f"  S3 Backup: {config.s3_backup_enabled}")
        print(f"  Recommended Mode: {config.get_recommended_storage_mode()}")

        # Create storage service
        storage_service = create_lancedb_storage_service()

        # Test user data
        user_id = "web_user_1"

        # Prepare demo document
        document_data = {
            "doc_id": "web_doc_001",
            "doc_type": "web_demo",
            "title": "Web App Document",
            "source_uri": "web://cloud/document1",
            "metadata": {
                "frontend": "web",
                "storage_backend": "s3_primary",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        chunks_with_embeddings = [
            {
                "text_content": "This document is stored using S3 primary storage for web app.",
                "embedding": [0.1] * 1536,
                "metadata": {"chunk_index": 0, "frontend": "web"},
            }
        ]

        # Store document
        logger.info("💾 Storing document with web app configuration...")
        result = await storage_service.store_document(
            user_id=user_id,
            document_data=document_data,
            chunks_with_embeddings=chunks_with_embeddings,
        )

        print(f"Web App Storage Result: {json.dumps(result, indent=2)}")

        # Get storage status
        status = await storage_service.get_storage_status(user_id)
        print(f"Web App Storage Status: {json.dumps(status, indent=2)}")

        logger.info("✅ Web app demo completed!")

    except Exception as e:
        logger.error(f"❌ Web app demo failed: {e}")
        import traceback

        traceback.print_exc()


async def demo_desktop_app_configuration():
    """Demonstrate desktop app (local-first) storage configuration"""
    logger.info("💻 Starting Desktop App (Local-First) Demo")

    try:
        # Set up environment for desktop app
        os.environ.update(
            {
                "FRONTEND_TYPE": "desktop",
                "S3_STORAGE_ENABLED": "false",  # Local primary
                "USE_S3_AS_PRIMARY": "false",
                "LOCAL_CACHE_ENABLED": "true",
                "S3_BACKUP_ENABLED": "true",  # Backup to S3 for data safety
                "S3_BACKUP_BUCKET": "atom-desktop-backup",  # Would be real bucket in production
            }
        )

        from sync.lancedb_storage_service import create_lancedb_storage_service
        from sync import get_config

        # Get configuration
        config = get_config()

        print(f"\n💻 Desktop App Configuration:")
        print(f"  Frontend Type: {config.frontend_type}")
        print(f"  S3 Storage: {config.s3_storage_enabled}")
        print(f"  S3 Primary: {config.use_s3_as_primary}")
        print(f"  Local Cache: {config.local_cache_enabled}")
        print(f"  S3 Backup: {config.s3_backup_enabled}")
        print(f"  Recommended Mode: {config.get_recommended_storage_mode()}")

        # Create storage service
        storage_service = create_lancedb_storage_service()

        # Test user data
        user_id = "desktop_user_1"

        # Prepare demo document
        document_data = {
            "doc_id": "desktop_doc_001",
            "doc_type": "desktop_demo",
            "title": "Desktop App Document",
            "source_uri": "desktop://local/document1",
            "metadata": {
                "frontend": "desktop",
                "storage_backend": "local_primary",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        chunks_with_embeddings = [
            {
                "text_content": "This document is stored locally with S3 backup for desktop app.",
                "embedding": [0.2] * 1536,
                "metadata": {"chunk_index": 0, "frontend": "desktop"},
            }
        ]

        # Store document
        logger.info("💾 Storing document with desktop app configuration...")
        result = await storage_service.store_document(
            user_id=user_id,
            document_data=document_data,
            chunks_with_embeddings=chunks_with_embeddings,
        )

        print(f"Desktop App Storage Result: {json.dumps(result, indent=2)}")

        # Sync to S3 backup
        logger.info("🔄 Syncing to S3 backup...")
        sync_result = await storage_service.sync_user_data(user_id)
        print(f"Desktop App Sync Result: {json.dumps(sync_result, indent=2)}")

        # Get storage status
        status = await storage_service.get_storage_status(user_id)
        print(f"Desktop App Storage Status: {json.dumps(status, indent=2)}")

        logger.info("✅ Desktop app demo completed!")

    except Exception as e:
        logger.error(f"❌ Desktop app demo failed: {e}")
        import traceback

        traceback.print_exc()


async def demo_mixed_frontend_users():
    """Demonstrate handling users from both frontend types"""
    logger.info("👥 Starting Mixed Frontend Users Demo")

    try:
        from sync.lancedb_storage_service import create_lancedb_storage_service

        # Test users from different frontends
        users = [
            {
                "user_id": "web_user_alice",
                "frontend": "web",
                "config": {
                    "FRONTEND_TYPE": "web",
                    "S3_STORAGE_ENABLED": "true",
                    "USE_S3_AS_PRIMARY": "true",
                },
            },
            {
                "user_id": "desktop_user_bob",
                "frontend": "desktop",
                "config": {
                    "FRONTEND_TYPE": "desktop",
                    "S3_STORAGE_ENABLED": "false",
                    "USE_S3_AS_PRIMARY": "false",
                },
            },
            {
                "user_id": "web_user_charlie",
                "frontend": "web",
                "config": {
                    "FRONTEND_TYPE": "web",
                    "S3_STORAGE_ENABLED": "true",
                    "USE_S3_AS_PRIMARY": "true",
                },
            },
        ]

        for user in users:
            # Set environment for this user's frontend type
            os.environ.update(user["config"])

            # Create storage service with current configuration
            storage_service = create_lancedb_storage_service()

            # Prepare user-specific document
            document_data = {
                "doc_id": f"{user['frontend']}_doc_{user['user_id']}",
                "doc_type": "mixed_demo",
                "title": f"Document for {user['user_id']} ({user['frontend']})",
                "source_uri": f"{user['frontend']}://user/document1",
                "metadata": {
                    "frontend": user["frontend"],
                    "user_id": user["user_id"],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            }

            chunks_with_embeddings = [
                {
                    "text_content": f"This document belongs to {user['user_id']} using {user['frontend']} frontend.",
                    "embedding": [0.3] * 1536,
                    "metadata": {"chunk_index": 0, "frontend": user["frontend"]},
                }
            ]

            # Store document
            logger.info(
                f"💾 Storing document for {user['user_id']} ({user['frontend']})..."
            )
            result = await storage_service.store_document(
                user_id=user["user_id"],
                document_data=document_data,
                chunks_with_embeddings=chunks_with_embeddings,
            )

            print(f"Storage for {user['user_id']}: {json.dumps(result, indent=2)}")

            # Get storage status
            status = await storage_service.get_storage_status(user["user_id"])
            print(f"Status for {user['user_id']}: {json.dumps(status, indent=2)}")

        logger.info("✅ Mixed frontend users demo completed!")

    except Exception as e:
        logger.error(f"❌ Mixed frontend demo failed: {e}")
        import traceback

        traceback.print_exc()


async def demo_frontend_migration():
    """Demonstrate migrating users between frontend types"""
    logger.info("🔄 Starting Frontend Migration Demo")

    try:
        from sync.lancedb_storage_service import create_lancedb_storage_service
        from sync import get_config, update_config

        # Start with desktop configuration
        os.environ.update(
            {
                "FRONTEND_TYPE": "desktop",
                "S3_STORAGE_ENABLED": "false",
                "USE_S3_AS_PRIMARY": "false",
                "S3_BACKUP_ENABLED": "true",
            }
        )

        user_id = "migrating_user"

        print(f"\n🔄 Migration Scenario: Desktop → Web")

        # Phase 1: Desktop user
        logger.info("📝 Phase 1: Desktop user with local storage")
        desktop_config = get_config()
        print(f"  Initial Config: {desktop_config.frontend_type}")
        print(f"  Storage Backend: {desktop_config.get_recommended_storage_mode()}")

        storage_service = create_lancedb_storage_service()

        # Store document as desktop user
        document_data = {
            "doc_id": "migration_doc_001",
            "doc_type": "migration_demo",
            "title": "Migration Test Document",
            "source_uri": "desktop://migration/document1",
            "metadata": {
                "phase": "desktop",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        chunks_with_embeddings = [
            {
                "text_content": "This document was created as a desktop user.",
                "embedding": [0.4] * 1536,
                "metadata": {"chunk_index": 0, "phase": "desktop"},
            }
        ]

        desktop_result = await storage_service.store_document(
            user_id=user_id,
            document_data=document_data,
            chunks_with_embeddings=chunks_with_embeddings,
        )
        print(f"  Desktop Storage: {desktop_result['storage_backend']}")

        # Phase 2: Migrate to web configuration
        logger.info("📝 Phase 2: Migrating to web configuration")
        os.environ.update(
            {
                "FRONTEND_TYPE": "web",
                "S3_STORAGE_ENABLED": "true",
                "USE_S3_AS_PRIMARY": "true",
                "S3_BACKUP_ENABLED": "false",
            }
        )

        web_config = get_config()
        print(f"  Migrated Config: {web_config.frontend_type}")
        print(f"  Storage Backend: {web_config.get_recommended_storage_mode()}")

        # Create new storage service with web configuration
        web_storage_service = create_lancedb_storage_service()

        # Store new document as web user
        document_data["doc_id"] = "migration_doc_002"
        document_data["metadata"]["phase"] = "web"
        chunks_with_embeddings[0]["text_content"] = (
            "This document was created after migrating to web configuration."
        )
        chunks_with_embeddings[0]["metadata"]["phase"] = "web"

        web_result = await web_storage_service.store_document(
            user_id=user_id,
            document_data=document_data,
            chunks_with_embeddings=chunks_with_embeddings,
        )
        print(f"  Web Storage: {web_result['storage_backend']}")

        # Compare storage backends
        desktop_status = await storage_service.get_storage_status(user_id)
        web_status = await web_storage_service.get_storage_status(user_id)

        print(f"\n📊 Migration Summary:")
        print(f"  Desktop Backend: {desktop_status.get('storage_backend')}")
        print(f"  Web Backend: {web_status.get('storage_backend')}")
        print(f"  Documents (Desktop): {desktop_status.get('documents_count')}")
        print(f"  Documents (Web): {web_status.get('documents_count')}")

        logger.info("✅ Frontend migration demo completed!")

    except Exception as e:
        logger.error(f"❌ Migration demo failed: {e}")
        import traceback

        traceback.print_exc()


async def demo_performance_comparison():
    """Demonstrate performance characteristics for each frontend type"""
    logger.info("⚡ Starting Performance Comparison Demo")

    try:
        import time
        from sync.lancedb_storage_service import create_lancedb_storage_service

        frontend_configs = [
            {
                "name": "Web App (S3 Primary)",
                "config": {
                    "FRONTEND_TYPE": "web",
                    "S3_STORAGE_ENABLED": "true",
                    "USE_S3_AS_PRIMARY": "true",
                    "LOCAL_CACHE_ENABLED": "true",
                },
            },
            {
                "name": "Desktop App (Local Primary)",
                "config": {
                    "FRONTEND_TYPE": "desktop",
                    "S3_STORAGE_ENABLED": "false",
                    "USE_S3_AS_PRIMARY": "false",
                    "LOCAL_CACHE_ENABLED": "true",
                },
            },
        ]

        performance_results = {}

        for config in frontend_configs:
            logger.info(f"⚡ Testing performance for: {config['name']}")

            # Set configuration
            os.environ.update(config["config"])

            storage_service = create_lancedb_storage_service()
            user_id = f"perf_test_{config['name'].lower().replace(' ', '_')}"

            # Prepare test document
            document_data = {
                "doc_id": f"perf_doc_{user_id}",
                "doc_type": "performance_test",
                "title": f"Performance Test - {config['name']}",
                "source_uri": f"perf://test/document1",
                "metadata": {
                    "test_type": "performance",
                    "frontend_config": config["name"],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            }

            chunks_with_embeddings = [
                {
                    "text_content": f"Performance test document for {config['name']} configuration.",
                    "embedding": [0.5] * 1536,
                    "metadata": {"chunk_index": 0, "test": "performance"},
                }
            ]

            # Measure storage performance
            start_time = time.time()
            result = await storage_service.store_document(
                user_id=user_id,
                document_data=document_data,
                chunks_with_embeddings=chunks_with_embeddings,
            )
            storage_time = time.time() - start_time

            # Measure search performance
            start_time = time.time()
            search_result = await storage_service.search_documents(
                user_id=user_id,
                query_vector=[0.5] * 1536,
                limit=5,
            )
            search_time = time.time() - start_time

            # Get status
            status = await storage_service.get_storage_status(user_id)

            performance_results[config["name"]] = {
                "storage_time_ms": round(storage_time * 1000, 2),
                "search_time_ms": round(search_time * 1000, 2),
                "storage_backend": status.get("storage_backend"),
                "documents_count": status.get("documents_count"),
                "chunks_count": status.get("chunks_count"),
            }

            print(f"  {config['name']}:")
            print(
                f"    Storage: {performance_results[config['name']]['storage_time_ms']}ms"
            )
            print(
                f"    Search: {performance_results[config['name']]['search_time_ms']}ms"
            )
            print(
                f"    Backend: {performance_results[config['name']]['storage_backend']}"
            )

        print(f"\n📊 Performance Summary:")
        for config_name, results in performance_results.items():
            print(f"  {config_name}:")
            print(f"    Storage: {results['storage_time_ms']}ms")
            print(f"    Search: {results['search_time_ms']}ms")
            print(f"    Backend: {results['storage_backend']}")

        logger.info("✅ Performance comparison demo completed!")

    except Exception as e:
        logger.error(f"❌ Performance comparison demo failed: {e}")
        import traceback

        traceback.print_exc()


async def main():
    """Run all dual frontend demos"""
    print("🎯 LanceDB Dual Frontend Storage - Complete Demo")
    print("=" * 60)

    # Create necessary directories
    os.makedirs("data", exist_ok=True)

    # Run demos
    await demo_web_app_configuration()
    print("\n" + "=" * 60 + "\n")

    await demo_desktop_app_configuration()
    print("\n" + "=" * 60 + "\n")

    await demo_mixed_frontend_users()
    print("\n" + "=" * 60 + "\n")

    await demo_frontend_migration()
    print("\n" + "=" * 60 + "\n")

    await demo_performance_comparison()

    print("\n" + "=" * 60)
    print("🎉 All dual frontend demos completed!")
    print("=" * 60)


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())
