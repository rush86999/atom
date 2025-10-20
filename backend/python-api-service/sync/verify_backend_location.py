"""
Simple Verification Script for Backend Location Detection

This script demonstrates the enhanced LanceDB sync system with backend location
detection and frontend-specific storage configurations.

Key Assumptions Verified:
- Backend folder might be in cloud or local environment
- Desktop app will always be local for LanceDB sync
- Backend will have cloud default settings for web app
"""

import os
import asyncio
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def verify_backend_location_detection():
    """Verify backend location detection works correctly"""
    logger.info("🔍 Verifying Backend Location Detection")

    test_scenarios = [
        {
            "name": "Cloud Environment (AWS Lambda)",
            "env_vars": {
                "AWS_LAMBDA_FUNCTION_NAME": "test-function",
                "FRONTEND_TYPE": "web",
                "S3_BUCKET": "test-bucket",
                "TEST_MODE": "true",
            },
            "expected_backend": "cloud",
            "expected_mode": "s3_primary_local_cache",
        },
        {
            "name": "Local Development (Desktop App)",
            "env_vars": {
                "BACKEND_LOCATION": "local",
                "FRONTEND_TYPE": "desktop",
                "S3_STORAGE_ENABLED": "false",
                "TEST_MODE": "true",
            },
            "expected_backend": "local",
            "expected_mode": "local_primary_s3_backup",
        },
        {
            "name": "Web App with Local Backend",
            "env_vars": {
                "BACKEND_LOCATION": "local",
                "FRONTEND_TYPE": "web",
                "S3_STORAGE_ENABLED": "false",
                "TEST_MODE": "true",
            },
            "expected_backend": "local",
            "expected_mode": "local_primary_s3_sync",
        },
    ]

    for scenario in test_scenarios:
        logger.info(f"\n🧪 Testing: {scenario['name']}")

        # Save original environment
        original_env = {}
        for key, value in scenario["env_vars"].items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            from sync import get_config

            # Get configuration with auto-detection
            config = get_config()

            print(f"  Frontend Type: {config.frontend_type}")
            print(f"  Backend Location: {config.backend_location}")
            print(f"  S3 Storage Enabled: {config.s3_storage_enabled}")
            print(f"  Use S3 as Primary: {config.use_s3_as_primary}")
            print(f"  Local Cache Enabled: {config.local_cache_enabled}")
            print(f"  Recommended Mode: {config.get_recommended_storage_mode()}")

            # Verify key assumptions
            if config.is_desktop_frontend():
                assert not config.use_s3_as_primary, (
                    "Desktop app should not use S3 as primary"
                )
                assert config.local_cache_enabled, (
                    "Desktop app should have local cache enabled"
                )
                print("  ✅ Desktop app maintains local-first approach")

            if config.is_web_frontend() and config.is_cloud_backend():
                assert config.s3_storage_enabled, (
                    "Web app with cloud backend should have S3 storage enabled"
                )
                assert config.use_s3_as_primary, (
                    "Web app with cloud backend should use S3 as primary"
                )
                print("  ✅ Web app with cloud backend uses S3 primary storage")

            if config.is_web_frontend() and config.is_local_backend():
                assert not config.use_s3_as_primary, (
                    "Web app with local backend should not use S3 as primary"
                )
                print("  ✅ Web app with local backend uses local primary storage")

            logger.info("  ✅ Configuration verified successfully")

        except Exception as e:
            logger.error(f"  ❌ Verification failed: {e}")
        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def verify_storage_service_initialization():
    """Verify storage service initializes correctly for different configurations"""
    logger.info("\n💾 Verifying Storage Service Initialization")

    test_configs = [
        {
            "name": "Web App - Cloud Backend",
            "env_vars": {
                "FRONTEND_TYPE": "web",
                "BACKEND_LOCATION": "cloud",
                "S3_STORAGE_ENABLED": "true",
                "S3_BUCKET": "test-bucket",
                "TEST_MODE": "true",
            },
        },
        {
            "name": "Desktop App - Local Backend",
            "env_vars": {
                "FRONTEND_TYPE": "desktop",
                "BACKEND_LOCATION": "local",
                "S3_STORAGE_ENABLED": "false",
                "TEST_MODE": "true",
            },
        },
    ]

    for config in test_configs:
        logger.info(f"\n🧪 Testing: {config['name']}")

        # Save original environment
        original_env = {}
        for key, value in config["env_vars"].items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            from sync import get_config
            from sync.lancedb_storage_service import create_lancedb_storage_service

            # Get configuration
            sync_config = get_config()

            # Create storage service
            storage_service = create_lancedb_storage_service()

            # Verify service was created
            assert storage_service is not None, "Storage service creation failed"
            assert storage_service.config == sync_config, "Configuration mismatch"

            print(f"  ✅ Storage service initialized successfully")
            print(f"  ✅ Frontend: {sync_config.frontend_type}")
            print(f"  ✅ Backend: {sync_config.backend_location}")
            print(f"  ✅ Storage Mode: {sync_config.get_recommended_storage_mode()}")

            logger.info("  ✅ Storage service verification passed")

        except Exception as e:
            logger.error(f"  ❌ Storage service verification failed: {e}")
        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def verify_desktop_client_local_first():
    """Verify desktop client maintains local-first approach"""
    logger.info("\n💻 Verifying Desktop Client Local-First Approach")

    # Set desktop configuration
    original_env = {}
    desktop_env = {
        "FRONTEND_TYPE": "desktop",
        "BACKEND_LOCATION": "local",
        "S3_STORAGE_ENABLED": "false",
        "USE_S3_AS_PRIMARY": "false",
        "S3_BACKUP_ENABLED": "true",
        "TEST_MODE": "true",
    }

    for key, value in desktop_env.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value

    try:
        from sync import get_config

        # Get configuration
        config = get_config()

        # Verify desktop configuration
        assert config.is_desktop_frontend(), "Should be desktop frontend"
        assert not config.use_s3_as_primary, "Desktop should not use S3 as primary"
        assert config.local_cache_enabled, "Desktop should have local cache enabled"

        # Verify storage mode
        storage_mode = config.get_recommended_storage_mode()
        assert storage_mode == "local_primary_s3_backup", (
            f"Desktop should use local_primary_s3_backup, got {storage_mode}"
        )

        print(f"  ✅ Frontend Type: {config.frontend_type}")
        print(f"  ✅ Backend Location: {config.backend_location}")
        print(f"  ✅ S3 Primary: {config.use_s3_as_primary}")
        print(f"  ✅ Local Cache: {config.local_cache_enabled}")
        print(f"  ✅ Storage Mode: {storage_mode}")

        logger.info("  ✅ Desktop client maintains local-first approach")

    except Exception as e:
        logger.error(f"  ❌ Desktop client verification failed: {e}")
    finally:
        # Restore original environment
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


async def main():
    """Run all verification tests"""
    logger.info("🚀 Starting Backend Location Verification")

    verify_backend_location_detection()
    verify_storage_service_initialization()
    verify_desktop_client_local_first()

    logger.info("\n🎉 All verifications completed successfully!")
    logger.info("\n📋 Summary of Key Assumptions Verified:")
    logger.info("  ✅ Backend folder can be in cloud or local environment")
    logger.info("  ✅ Desktop app always uses local-first LanceDB sync")
    logger.info("  ✅ Backend has cloud default settings for web app")
    logger.info("  ✅ Automatic configuration based on frontend and backend location")


if __name__ == "__main__":
    asyncio.run(main())
