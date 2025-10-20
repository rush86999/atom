"""
Enhanced Demo Script for Backend Location Detection

This script demonstrates the LanceDB sync system with enhanced backend location
detection and frontend-specific storage configurations.

Key Features:
- Backend location detection (cloud vs local)
- Frontend-specific storage modes (web vs desktop)
- Automatic configuration based on environment
- Performance comparison across different setups
"""

import os
import asyncio
import logging
import json
import time
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


async def demo_backend_location_detection():
    """Demonstrate automatic backend location detection"""
    logger.info("🔍 Starting Backend Location Detection Demo")

    # Test different environment scenarios
    test_scenarios = [
        {
            "name": "Cloud Environment (AWS Lambda)",
            "env_vars": {
                "AWS_LAMBDA_FUNCTION_NAME": "test-function",
                "FRONTEND_TYPE": "web",
                "S3_STORAGE_ENABLED": "true",
            },
        },
        {
            "name": "Cloud Environment (Google Cloud Functions)",
            "env_vars": {
                "FUNCTION_NAME": "test-function",
                "FRONTEND_TYPE": "web",
                "S3_STORAGE_ENABLED": "true",
            },
        },
        {
            "name": "Local Development (Desktop App)",
            "env_vars": {
                "FRONTEND_TYPE": "desktop",
                "S3_STORAGE_ENABLED": "false",
                "S3_BACKUP_ENABLED": "true",
            },
        },
        {
            "name": "Local Development (Web App)",
            "env_vars": {
                "FRONTEND_TYPE": "web",
                "BACKEND_LOCATION": "local",
                "S3_STORAGE_ENABLED": "false",
            },
        },
        {
            "name": "Explicit Cloud Backend",
            "env_vars": {
                "BACKEND_LOCATION": "cloud",
                "FRONTEND_TYPE": "web",
                "S3_STORAGE_ENABLED": "true",
            },
        },
    ]

    for scenario in test_scenarios:
        logger.info(f"\n🧪 Testing Scenario: {scenario['name']}")

        # Set environment variables
        original_env = {}
        for key, value in scenario["env_vars"].items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            from sync import get_config

            # Get configuration with auto-detection
            config = get_config()

            print(f"\n📊 Configuration Analysis:")
            print(f"  Frontend Type: {config.frontend_type}")
            print(f"  Backend Location: {config.backend_location}")
            print(f"  S3 Storage Enabled: {config.s3_storage_enabled}")
            print(f"  Use S3 as Primary: {config.use_s3_as_primary}")
            print(f"  Local Cache Enabled: {config.local_cache_enabled}")
            print(f"  Recommended Mode: {config.get_recommended_storage_mode()}")
            print(f"  Cloud Backend: {config.is_cloud_backend()}")
            print(f"  Local Backend: {config.is_local_backend()}")

            # Validate configuration
            is_valid = config.validate()
            print(f"  Configuration Valid: {is_valid}")

        except Exception as e:
            logger.error(f"❌ Scenario failed: {e}")
        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


async def demo_storage_modes_by_backend():
    """Demonstrate different storage modes based on backend location"""
    logger.info("💾 Starting Storage Modes by Backend Demo")

    storage_modes = [
        {
            "name": "Web App + Cloud Backend",
            "env_vars": {
                "FRONTEND_TYPE": "web",
                "BACKEND_LOCATION": "cloud",
                "S3_STORAGE_ENABLED": "true",
                "USE_S3_AS_PRIMARY": "true",
                "LOCAL_CACHE_ENABLED": "true",
            },
        },
        {
            "name": "Web App + Local Backend",
            "env_vars": {
                "FRONTEND_TYPE": "web",
                "BACKEND_LOCATION": "local",
                "S3_STORAGE_ENABLED": "false",
                "USE_S3_AS_PRIMARY": "false",
                "LOCAL_CACHE_ENABLED": "true",
            },
        },
        {
            "name": "Desktop App + Cloud Backend",
            "env_vars": {
                "FRONTEND_TYPE": "desktop",
                "BACKEND_LOCATION": "cloud",
                "S3_STORAGE_ENABLED": "false",
                "USE_S3_AS_PRIMARY": "false",
                "LOCAL_CACHE_ENABLED": "true",
                "S3_BACKUP_ENABLED": "true",
            },
        },
        {
            "name": "Desktop App + Local Backend",
            "env_vars": {
                "FRONTEND_TYPE": "desktop",
                "BACKEND_LOCATION": "local",
                "S3_STORAGE_ENABLED": "false",
                "USE_S3_AS_PRIMARY": "false",
                "LOCAL_CACHE_ENABLED": "true",
                "S3_BACKUP_ENABLED": "true",
            },
        },
    ]

    for mode in storage_modes:
        logger.info(f"\n🏗️  Testing Storage Mode: {mode['name']}")

        # Set environment variables
        original_env = {}
        for key, value in mode["env_vars"].items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            from sync import get_config
            from sync.lancedb_storage_service import create_lancedb_storage_service

            # Get configuration
            config = get_config()

            print(f"\n📋 Storage Mode Configuration:")
            print(f"  Frontend: {config.frontend_type}")
            print(f"  Backend: {config.backend_location}")
            print(f"  S3 Storage: {config.s3_storage_enabled}")
            print(f"  S3 Primary: {config.use_s3_as_primary}")
            print(f"  Local Cache: {config.local_cache_enabled}")
            print(f"  S3 Backup: {config.s3_backup_enabled}")
            print(f"  Recommended Mode: {config.get_recommended_storage_mode()}")

            # Create storage service
            storage_service = create_lancedb_storage_service()

            # Test basic functionality
            user_id = f"test_user_{mode['name'].replace(' ', '_').lower()}"

            document_data = {
                "doc_id": f"doc_{int(time.time())}",
                "doc_type": "demo",
                "title": f"Test Document - {mode['name']}",
                "source_uri": f"demo://{mode['name'].replace(' ', '_').lower()}",
                "metadata": {
                    "mode": mode["name"],
                    "frontend": config.frontend_type,
                    "backend": config.backend_location,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            }

            chunks_with_embeddings = [
                {
                    "text_content": f"This is a test document for {mode['name']} configuration.",
                    "embedding": [0.1] * 1536,
                    "metadata": {"chunk_index": 0},
                }
            ]

            # Store document
            logger.info("💾 Testing document storage...")
            result = await storage_service.store_document(
                user_id=user_id,
                document_data=document_data,
                chunks_with_embeddings=chunks_with_embeddings,
            )

            print(f"  Storage Result: {result.get('status', 'unknown')}")
            print(f"  Document ID: {result.get('doc_id', 'N/A')}")
            print(f"  Local Stored: {result.get('local_stored', False)}")
            print(f"  Queued for Sync: {result.get('queued_for_sync', False)}")

            # Get storage status
            status = await storage_service.get_storage_status(user_id)
            print(f"  Storage Status: {status.get('status', 'unknown')}")

            logger.info("✅ Storage mode test completed!")

        except Exception as e:
            logger.error(f"❌ Storage mode test failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


async def demo_performance_comparison():
    """Compare performance across different backend configurations"""
    logger.info("⚡ Starting Performance Comparison Demo")

    performance_scenarios = [
        {
            "name": "Web App - Cloud Backend (S3 Primary)",
            "env_vars": {
                "FRONTEND_TYPE": "web",
                "BACKEND_LOCATION": "cloud",
                "S3_STORAGE_ENABLED": "true",
                "USE_S3_AS_PRIMARY": "true",
            },
        },
        {
            "name": "Web App - Local Backend (Local Primary)",
            "env_vars": {
                "FRONTEND_TYPE": "web",
                "BACKEND_LOCATION": "local",
                "S3_STORAGE_ENABLED": "false",
                "USE_S3_AS_PRIMARY": "false",
            },
        },
        {
            "name": "Desktop App - Local Backend (Local Primary)",
            "env_vars": {
                "FRONTEND_TYPE": "desktop",
                "BACKEND_LOCATION": "local",
                "S3_STORAGE_ENABLED": "false",
                "USE_S3_AS_PRIMARY": "false",
            },
        },
    ]

    performance_results = []

    for scenario in performance_scenarios:
        logger.info(f"\n🏃‍♂️ Testing Performance: {scenario['name']}")

        # Set environment variables
        original_env = {}
        for key, value in scenario["env_vars"].items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            from sync import get_config
            from sync.lancedb_storage_service import create_lancedb_storage_service

            # Get configuration
            config = get_config()

            # Create storage service
            storage_service = create_lancedb_storage_service()

            # Test user
            user_id = f"perf_user_{scenario['name'].replace(' ', '_').lower()}"

            # Performance test: Store multiple documents
            num_documents = 5
            store_times = []

            for i in range(num_documents):
                document_data = {
                    "doc_id": f"perf_doc_{i}_{int(time.time())}",
                    "doc_type": "performance",
                    "title": f"Performance Test Doc {i} - {scenario['name']}",
                    "source_uri": f"perf://{scenario['name'].replace(' ', '_').lower()}/{i}",
                    "metadata": {
                        "test_type": "performance",
                        "scenario": scenario["name"],
                        "iteration": i,
                    },
                }

                chunks_with_embeddings = [
                    {
                        "text_content": f"Performance test document content for iteration {i}.",
                        "embedding": [float(i % 100) / 100.0] * 1536,
                        "metadata": {"chunk_index": 0},
                    }
                ]

                # Measure storage time
                start_time = time.time()
                result = await storage_service.store_document(
                    user_id=user_id,
                    document_data=document_data,
                    chunks_with_embeddings=chunks_with_embeddings,
                )
                end_time = time.time()

                store_times.append(end_time - start_time)

                if result.get("status") != "success":
                    logger.warning(f"  Document {i} storage failed: {result}")

            # Calculate performance metrics
            avg_store_time = sum(store_times) / len(store_times) if store_times else 0
            total_store_time = sum(store_times)

            performance_results.append({
                "scenario": scenario["name"],
                "frontend": config.frontend_type,
                "backend": config.backend_location,
                "storage_mode": config.get_recommended_storage_mode(),
                "documents_stored": len(store_times),
                "average_store_time_ms": round(avg_store_time * 1000, 2),
                "total_store_time_ms": round(total_store_time * 1000, 2),
                "documents_per_second": round(len(store_times) / total_store_time, 2) if total_store_time > 0 else 0,
            })

            print(f"  Documents Stored: {len(store_times)}")
            print(f"  Average Store Time: {avg_store_time * 1000:.2f} ms")
            print(f"  Total Store Time: {total_store_time * 1000:.2f} ms")
            print(f"  Documents/Second: {len(store_times) / total_store_time:.2f}" if total_store_time > 0 else "N/A")

            logger.info("✅ Performance test completed!")

        except Exception as e:
            logger.error(f"❌ Performance test failed: {e}")
        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    # Print performance summary
    logger.info("\n📈 Performance Comparison Summary:")
    print("\n" + "="*80)
    print("PERFORMANCE COMPARISON ACROSS BACKEND CONFIGURATIONS")
    print("="*80)

    for result in performance_results:
        print(f"\n🏷️  {result['scenario']}")
        print(f"   Frontend: {result['frontend']}")
        print(f"   Backend: {result['backend']}")
        print(f"   Storage Mode: {result['storage_mode']}")
        print(f"   Documents: {result['documents_stored']}")
        print(f"   Avg Store Time: {result['average_store_time_ms']} ms")
        print(f"   Total Time: {result['total_store_time_ms']} ms")
        print(f"   Docs/Second: {result['documents_per_second']}")


async def demo_migration_scenarios():
    """Demonstrate migration scenarios between backend locations"""
    logger.info("🔄 Starting Migration Scenarios Demo")

    migration_scenarios = [
        {
            "name": "Local Development → Cloud Production",
            "from_env": {
                "FRONTEND_TYPE": "web",
                "BACKEND_LOCATION": "local",
                "S3_STORAGE_ENABLED": "false",
            },
            "to_env": {
                "FRONTEND_TYPE": "web",
                "BACKEND_LOCATION": "cloud",
                "S3_STORAGE_ENABLED": "true",
                "USE_S3_AS_PRIMARY": "true",
            },
        },
        {
            "name": "Desktop App → Web App Migration",
            "from_env": {
                "FRONTEND_TYPE": "desktop",
                "BACKEND_LOCATION": "local",
                "S3_STORAGE_ENABLED": "false",
            },
            "to_env": {
                "FRONTEND_TYPE": "web",
                "BACKEND_LOCATION": "cloud",
                "S3_STORAGE_ENABLED": "true",
                "USE_S3_AS_PRIMARY": "true",
            },
        },
    ]

    for scenario in migration_scenarios:
        logger.info(f"\n🚚 Testing Migration: {scenario['name']}")

        print(f"\n📦 Migration Analysis:")
        print(f"  From: {scenario['from_env']}")
        print(f"  To: {scenario['to_env']}")

        # Analyze configuration changes
        from sync import get_config, update_config

        # Test "from" configuration
        original_env = {}
        for key, value in scenario["from_env"].items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        from_config = get_config()
        print(f"  From Config - Frontend: {from_config.frontend_type}")
        print(f"  From Config - Backend: {from_config.backend_location}")
        print(f"  From Config - Storage Mode: {from_config.get_recommended_storage_mode()}")

        # Test "to" configuration
        for key, value in scenario["to_env"].items():
            os.environ[key] = value

        to_config = get_config()
        print(f"  To Config - Frontend: {to_config.frontend_type}")
        print(f"  To Config - Backend: {to_config.backend_location}")
        print(f"  To Config - Storage Mode: {to_config.get_recommended_storage_mode()}")

        # Migration recommendations
        print(f"\n💡 Migration Recommendations:")
        if from_config.is_desktop_frontend() and to_config.is_web_frontend():
            print("  - Desktop → Web: Data sync required from local to cloud")
            print("  - Enable S3 storage and configure as primary")
            print("  - Consider data migration strategy")
        elif from_config.is_local_backend() and to_config.is_cloud_backend():
            print("  - Local → Cloud: Backend infrastructure changes")
            print("  - Update S3 configuration and credentials")
            print("  - Test cloud connectivity and permissions")
        else:
            print("  - Configuration change only, no data migration needed")

        # Restore original environment
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

        logger.info("✅ Migration analysis completed!")


async def main():
    """Run all demo scenarios"""
    logger.info("🚀 Starting Enhanced Backend
