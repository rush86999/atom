"""
Integration Demo for LanceDB Sync System

This script demonstrates the complete LanceDB sync system with:
1. Source monitoring setup
2. Document processing
3. Local + S3 storage
4. Status monitoring
"""

import os
import asyncio
import logging
import tempfile
import json
from datetime import datetime, timezone
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


async def demo_basic_sync():
    """Demonstrate basic sync system functionality"""
    logger.info("🚀 Starting LanceDB Sync System Demo")

    try:
        from sync.startup import create_sync_system

        # Create sync system with test configuration
        startup = create_sync_system(
            {
                "local_db_path": "data/demo_lancedb",
                "s3_bucket": None,  # Disable S3 for demo
                "enable_source_monitoring": True,
                "sync_state_dir": "data/demo_sync_state",
            }
        )

        # Initialize the system
        logger.info("📦 Initializing sync system...")
        if not await startup.initialize():
            logger.error("❌ Failed to initialize sync system")
            return

        # Start the system
        logger.info("▶️ Starting sync system...")
        if not await startup.start():
            logger.error("❌ Failed to start sync system")
            return

        # Add default sources
        logger.info("➕ Adding default sources...")
        await startup.add_default_sources()

        # Show system status
        logger.info("📊 Getting system status...")
        status = await startup.get_status()
        print("\n" + "=" * 50)
        print("SYSTEM STATUS")
        print("=" * 50)
        print(json.dumps(status, indent=2))
        print("=" * 50 + "\n")

        # Keep system running for a bit
        logger.info("⏰ System running for 30 seconds...")
        await asyncio.sleep(30)

        # Stop the system
        logger.info("🛑 Stopping sync system...")
        await startup.stop()

        logger.info("✅ Demo completed successfully!")

    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
        import traceback

        traceback.print_exc()


async def demo_document_processing():
    """Demonstrate document processing with the sync system"""
    logger.info("📄 Starting Document Processing Demo")

    try:
        from sync.orchestration_service import create_orchestration_service
        from sync.source_change_detector import SourceType, ChangeType

        # Create orchestration service
        service = create_orchestration_service(
            local_db_path="data/demo_lancedb_processing",
            s3_bucket=None,
            enable_source_monitoring=False,  # Disable for focused demo
        )

        # Start the service
        await service.start()

        # Create a test document
        document_data = {
            "doc_id": "demo_document_1",
            "doc_type": "demo",
            "title": "Demo Document",
            "metadata": {
                "created_by": "demo_script",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

        chunks_with_embeddings = [
            {
                "text_content": "This is the first chunk of the demo document.",
                "embedding": [0.1] * 1536,  # Mock embedding
                "metadata": {"chunk_index": 0, "type": "text"},
            },
            {
                "text_content": "This is the second chunk with different content.",
                "embedding": [0.2] * 1536,  # Mock embedding
                "metadata": {"chunk_index": 1, "type": "text"},
            },
        ]

        # Simulate a source change
        from sync.source_change_detector import SourceChange

        demo_change = SourceChange(
            source_type=SourceType.LOCAL_FILESYSTEM,
            source_id="demo_source",
            item_id="demo_document_1",
            item_path="/demo/path/document1.pdf",
            change_type=ChangeType.CREATED,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={"user_id": "demo_user", "file_size": 1024, "file_type": "pdf"},
        )

        # Process the change (this would normally be handled automatically)
        logger.info("🔄 Processing demo document...")
        await service._process_source_change(demo_change)

        # Get system status
        status = await service.get_system_status()
        print("\n" + "=" * 50)
        print("PROCESSING STATUS")
        print("=" * 50)
        print(f"Service Running: {status['service_running']}")
        if "sync_service" in status:
            sync_status = status["sync_service"]
            print(f"Local DB Available: {sync_status.get('local_db_available', False)}")
            print(f"Pending Syncs: {sync_status.get('pending_syncs', 0)}")
            print(f"Failed Syncs: {sync_status.get('failed_syncs', 0)}")
        print("=" * 50 + "\n")

        # Clean up
        await service.stop()

        logger.info("✅ Document processing demo completed!")

    except Exception as e:
        logger.error(f"❌ Document processing demo failed: {e}")
        import traceback

        traceback.print_exc()


async def demo_api_service():
    """Demonstrate the API service functionality"""
    logger.info("🌐 Starting API Service Demo")

    try:
        from sync.api_service import create_api_service
        import uvicorn
        from fastapi.testclient import TestClient

        # Create API service
        api_service = create_api_service()
        app = api_service.get_app()

        # Use test client for demo
        client = TestClient(app)

        # Test health endpoint
        logger.info("🩺 Testing health endpoint...")
        response = client.get("/health")
        print(f"Health Status: {response.status_code}")
        if response.status_code == 200:
            health_data = response.json()
            print(f"Service Status: {health_data.get('status')}")

        # Test root endpoint
        logger.info("🏠 Testing root endpoint...")
        response = client.get("/")
        if response.status_code == 200:
            root_data = response.json()
            print(f"API Message: {root_data.get('message')}")
            print(f"API Version: {root_data.get('version')}")

        # Test status endpoint
        logger.info("📊 Testing status endpoint...")
        response = client.get("/api/v1/status")
        if response.status_code == 200:
            status_data = response.json()
            print(f"Service Running: {status_data.get('service_running')}")
            print(f"Sync Service Available: {'sync_service' in status_data}")

        logger.info("✅ API service demo completed!")

    except Exception as e:
        logger.error(f"❌ API service demo failed: {e}")
        import traceback

        traceback.print_exc()


async def demo_local_filesystem_monitoring():
    """Demonstrate local filesystem monitoring"""
    logger.info("📁 Starting Local Filesystem Monitoring Demo")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            test_files = ["document1.pdf", "notes.txt", "presentation.pptx"]

            for filename in test_files:
                file_path = Path(temp_dir) / filename
                file_path.write_text(f"Content of {filename}")
                logger.info(f"📄 Created test file: {file_path}")

            from sync.orchestration_service import create_orchestration_service
            from sync.source_change_detector import SourceConfig, SourceType

            # Create service with filesystem monitoring
            service = create_orchestration_service(
                local_db_path="data/demo_lancedb_monitoring",
                s3_bucket=None,
                enable_source_monitoring=True,
            )

            await service.start()

            # Add the temporary directory as a monitored source
            local_source = SourceConfig(
                source_type=SourceType.LOCAL_FILESYSTEM,
                source_id="demo_monitoring",
                config={
                    "watch_paths": [temp_dir],
                    "file_patterns": ["*.pdf", "*.txt", "*.pptx"],
                },
                poll_interval=10,  # Short interval for demo
                enabled=True,
            )

            await service.add_source(local_source)

            # Force a scan to detect the files
            logger.info("🔍 Forcing source scan...")
            scan_result = await service.force_source_scan(
                SourceType.LOCAL_FILESYSTEM, "demo_monitoring"
            )

            print(f"Scan completed: {scan_result.get('message')}")
            print(f"Changes found: {scan_result.get('changes_found', 0)}")

            # Wait a bit to show monitoring
            logger.info("👀 Monitoring for 15 seconds...")
            await asyncio.sleep(15)

            # Get final status
            status = await service.get_system_status()
            print(f"\nFinal monitoring status:")
            print(
                f"Sources monitored: {status.get('change_detector', {}).get('sources_monitored', 0)}"
            )

            await service.stop()

            logger.info("✅ Filesystem monitoring demo completed!")

    except Exception as e:
        logger.error(f"❌ Filesystem monitoring demo failed: {e}")
        import traceback

        traceback.print_exc()


async def main():
    """Run all demos"""
    print("🎯 LanceDB Sync System - Complete Integration Demo")
    print("=" * 60)

    # Create necessary directories
    os.makedirs("data", exist_ok=True)

    # Run demos
    await demo_basic_sync()
    print("\n" + "=" * 60 + "\n")

    await demo_document_processing()
    print("\n" + "=" * 60 + "\n")

    await demo_api_service()
    print("\n" + "=" * 60 + "\n")

    await demo_local_filesystem_monitoring()

    print("\n" + "=" * 60)
    print("🎉 All demos completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())
