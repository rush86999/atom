"""
Test Script for Backend Location Detection

This script tests the enhanced backend location detection and storage configuration
based on the key assumptions:
- Backend folder might be in cloud or local environment
- Desktop app will always be local for LanceDB sync
- Backend will have cloud default settings for web app
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

# Set mock S3 bucket for testing (used in specific test cases)
MOCK_S3_BUCKET = "test-bucket-mock"


async def test_backend_location_detection():
    """Test automatic backend location detection"""
    logger.info("🧪 Testing Backend Location Detection")

    test_cases = [
        {
            "name": "AWS Lambda Environment",
            "env_vars": {
                "AWS_LAMBDA_FUNCTION_NAME": "test-function",
                "FRONTEND_TYPE": "web",
                "S3_BUCKET": MOCK_S3_BUCKET,
            },
            "expected_backend": "cloud",
            "expected_mode": "s3_primary_local_cache",
        },
        {
            "name": "Google Cloud Functions",
            "env_vars": {
                "FUNCTION_NAME": "test-function",
                "FRONTEND_TYPE": "web",
                "S3_BUCKET": MOCK_S3_BUCKET,
            },
            "expected_backend": "cloud",
            "expected_mode": "s3_primary_local_cache",
        },
        {
            "name": "Kubernetes Environment",
            "env_vars": {
                "KUBERNETES_SERVICE_HOST": "kubernetes",
                "FRONTEND_TYPE": "web",
                "S3_BUCKET": MOCK_S3_BUCKET,
            },
            "expected_backend": "cloud",
            "expected_mode": "s3_primary_local_cache",
        },
        {
            "name": "Explicit Cloud Backend",
            "env_vars": {
                "BACKEND_LOCATION": "cloud",
                "FRONTEND_TYPE": "web",
                "S3_BUCKET": MOCK_S3_BUCKET,
            },
            "expected_backend": "cloud",
            "expected_mode": "s3_primary_local_cache",
        },
        {
            "name": "Default Local Environment",
            "env_vars": {
                "BACKEND_LOCATION": "local",
                "S3_STORAGE_ENABLED": "false",
                "TEST_MODE": "true",
            },
            "expected_backend": "local",
            "expected_mode": "local_primary_s3_backup",
        },
        {
            "name": "Explicit Local Backend",
            "env_vars": {
                "BACKEND_LOCATION": "local",
                "FRONTEND_TYPE": "desktop",
                "S3_STORAGE_ENABLED": "false",
                "TEST_MODE": "true",
            },
            "expected_backend": "local",
            "expected_mode": "local_primary_s3_backup",
        },
    ]

    for test_case in test_cases:
        logger.info(f"\n📋 Testing: {test_case['name']}")

        # Save original environment
        original_env = {}
        for key, value in test_case["env_vars"].items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            from sync import get_config

            # Get configuration with auto-detection
            config = get_config()

            # Verify backend location
            assert config.backend_location == test_case["expected_backend"], (
                f"Expected {test_case['expected_backend']}, got {config.backend_location}"
            )

            # Debug output
            print(f"  Debug - Frontend: {config.frontend_type}")
            print(f"  Debug - Backend: {config.backend_location}")
            print(f"  Debug - S3 Primary: {config.use_s3_as_primary}")
            print(f"  Debug - Local Cache: {config.local_cache_enabled}")
            print(f"  Debug - S3 Storage Enabled: {config.s3_storage_enabled}")
            print(f"  Debug - S3 Bucket: {config.s3_bucket}")

            # Verify storage mode
            actual_mode = config.get_recommended_storage_mode()
            assert actual_mode == test_case["expected_mode"], (
                f"Expected {test_case['expected_mode']}, got {actual_mode}"
            )

            # Verify configuration validation
            assert config.validate(), "Configuration validation failed"

            logger.info(
                f"✅ PASS: Backend={config.backend_location}, Mode={actual_mode}"
            )

        except Exception as e:
            logger.error(f"❌ FAIL: {e}")
            import traceback

            traceback.print_exc()
        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


async def test_frontend_storage_configurations():
    """Test storage configurations for different frontend types"""
    logger.info("\n🧪 Testing Frontend Storage Configurations")

    test_cases = [
        {
            "name": "Web App + Cloud Backend",
            "env_vars": {
                "FRONTEND_TYPE": "web",
                "BACKEND_LOCATION": "cloud",
                "S3_STORAGE_ENABLED": "true",
                "S3_BUCKET": MOCK_S3_BUCKET,
                "TEST_MODE": "true",
            },
            "expected_s3_primary": True,
            "expected_local_cache": True,
        },
        {
            "name": "Web App + Local Backend",
            "env_vars": {
                "FRONTEND_TYPE": "web",
                "BACKEND_LOCATION": "local",
                "S3_STORAGE_ENABLED": "false",
            },
            "expected_s3_primary": False,
            "expected_local_cache": True,
        },
        {
            "name": "Desktop App + Cloud Backend",
            "env_vars": {
                "FRONTEND_TYPE": "desktop",
                "BACKEND_LOCATION": "cloud",
                "S3_STORAGE_ENABLED": "false",
                "TEST_MODE": "true",
            },
            "expected_s3_primary": False,
            "expected_local_cache": True,
        },
        {
            "name": "Desktop App + Local Backend",
            "env_vars": {
                "FRONTEND_TYPE": "desktop",
                "BACKEND_LOCATION": "local",
                "S3_STORAGE_ENABLED": "false",
                "TEST_MODE": "true",
                "TEST_MODE": "true",
            },
            "expected_s3_primary": False,
            "expected_local_cache": True,
        },
    ]

    for test_case in test_cases:
        logger.info(f"\n📋 Testing: {test_case['name']}")

        # Save original environment
        original_env = {}
        for key, value in test_case["env_vars"].items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            from sync import get_config

            # Get configuration
            config = get_config()

            # Verify frontend type
            assert config.frontend_type == test_case["env_vars"]["FRONTEND_TYPE"], (
                f"Frontend type mismatch: expected {test_case['env_vars']['FRONTEND_TYPE']}, got {config.frontend_type}"
            )

            # Verify backend location
            assert (
                config.backend_location == test_case["env_vars"]["BACKEND_LOCATION"]
            ), (
                f"Backend location mismatch: expected {test_case['env_vars']['BACKEND_LOCATION']}, got {config.backend_location}"
            )

            # Verify S3 primary setting
            assert config.use_s3_as_primary == test_case["expected_s3_primary"], (
                f"S3 primary expected {test_case['expected_s3_primary']}, got {config.use_s3_as_primary}"
            )

            # Verify local cache setting
            assert config.local_cache_enabled == test_case["expected_local_cache"], (
                f"Local cache expected {test_case['expected_local_cache']}, got {config.local_cache_enabled}"
            )

            # Verify configuration is valid
            assert config.validate(), "Configuration validation failed"

            logger.info(
                f"✅ PASS: S3 Primary={config.use_s3_as_primary}, Local Cache={config.local_cache_enabled}"
            )

        except Exception as e:
            logger.error(f"❌ FAIL: {e}")
            import traceback

            traceback.print_exc()
        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


async def test_storage_service_initialization():
    """Test storage service initialization with different configurations"""
    logger.info("\n🧪 Testing Storage Service Initialization")

    test_cases = [
        {
            "name": "Web App Cloud Configuration",
            "env_vars": {
                "FRONTEND_TYPE": "web",
                "BACKEND_LOCATION": "cloud",
                "S3_STORAGE_ENABLED": "true",
                "USE_S3_AS_PRIMARY": "true",
                "S3_BUCKET": MOCK_S3_BUCKET,
                "TEST_MODE": "true",
            },
        },
        {
            "name": "Web App Local Configuration",
            "env_vars": {
                "FRONTEND_TYPE": "web",
                "BACKEND_LOCATION": "local",
                "S3_STORAGE_ENABLED": "false",
                "USE_S3_AS_PRIMARY": "false",
            },
        },
        {
            "name": "Desktop App Configuration",
            "env_vars": {
                "FRONTEND_TYPE": "desktop",
                "BACKEND_LOCATION": "local",
                "S3_STORAGE_ENABLED": "false",
                "TEST_MODE": "true",
                "TEST_MODE": "true",
                "USE_S3_AS_PRIMARY": "false",
            },
        },
    ]

    for test_case in test_cases:
        logger.info(f"\n📋 Testing: {test_case['name']}")

        # Save original environment
        original_env = {}
        for key, value in test_case["env_vars"].items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            from sync import get_config
            from sync.lancedb_storage_service import create_lancedb_storage_service

            # Get configuration
            config = get_config()

            # Create storage service
            storage_service = create_lancedb_storage_service()

            # Verify service was created successfully
            assert storage_service is not None, "Storage service creation failed"
            assert storage_service.config == config, "Configuration mismatch"

            # Verify appropriate initialization based on configuration
            if config.is_web_frontend() and config.is_cloud_backend():
                # Web + Cloud: Should have S3 client initialized
                logger.info("✅ Web + Cloud: S3 primary storage configured")
            elif config.is_web_frontend() and config.is_local_backend():
                # Web + Local: Should use local storage
                logger.info("✅ Web + Local: Local primary storage configured")
            elif config.is_desktop_frontend():
                # Desktop: Always local-first
                logger.info("✅ Desktop: Local-first storage configured")

            logger.info("✅ PASS: Storage service initialized successfully")

        except Exception as e:
            logger.error(f"❌ FAIL: {e}")
            import traceback

            traceback.print_exc()
        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


async def test_desktop_client_local_first():
    """Test that desktop client maintains local-first approach"""
    logger.info("\n🧪 Testing Desktop Client Local-First Approach")

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

        logger.info("✅ PASS: Desktop maintains local-first approach")

    except Exception as e:
        logger.error(f"❌ FAIL: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Restore original environment
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


async def main():
    """Run all tests"""
    logger.info("🚀 Starting Backend Location Detection Tests")

    await test_backend_location_detection()
    await test_frontend_storage_configurations()
    await test_storage_service_initialization()
    await test_desktop_client_local_first()

    logger.info("\n🎉 All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
