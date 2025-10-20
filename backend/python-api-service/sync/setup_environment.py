"""
Environment Setup Script for LanceDB Sync System

This script sets up the required environment variables and configuration
for the LanceDB sync system, ensuring all dependencies are properly configured.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class EnvironmentSetup:
    """Handles environment setup for the LanceDB sync system"""

    # Default configuration values
    DEFAULT_CONFIG = {
        # Frontend Configuration
        "FRONTEND_TYPE": "desktop",  # "web" or "desktop"
        # Local Storage
        "LANCEDB_URI": "data/lancedb",
        "LANCEDB_TABLE_NAME": "processed_documents",
        "LANCEDB_CHUNKS_TABLE_NAME": "document_chunks",
        # S3 Storage Configuration
        "S3_STORAGE_ENABLED": "false",
        "S3_BUCKET": "",
        "S3_PREFIX": "lancedb-primary",
        "S3_REGION": "us-east-1",
        "S3_ENDPOINT": "",
        # S3 Backup Configuration
        "S3_BACKUP_ENABLED": "false",
        "S3_BACKUP_BUCKET": "",
        "S3_BACKUP_PREFIX": "lancedb-backup",
        # Storage Behavior (auto-configured based on frontend type)
        "USE_S3_AS_PRIMARY": "false",
        "LOCAL_CACHE_ENABLED": "true",
        "SYNC_ON_STARTUP": "true",
        # Sync Behavior
        "SYNC_INTERVAL": "300",
        "MAX_CONCURRENT_PROCESSING": "5",
        "CHUNK_SIZE_MB": "50",
        "MAX_RETRIES": "3",
        # Source Monitoring
        "ENABLE_SOURCE_MONITORING": "true",
        "SYNC_STATE_DIR": "data/sync_state",
        "HEALTH_CHECK_INTERVAL": "60",
        "DEFAULT_POLL_INTERVAL": "300",
        "CHECKSUM_ENABLED": "true",
        # API Configuration
        "API_HOST": "0.0.0.0",
        "API_PORT": "8000",
        # Integration Settings
        "ENABLE_LEGACY_FALLBACK": "true",
        "MIGRATE_EXISTING_DATA": "false",
        "SYNC_ENABLED_BY_DEFAULT": "true",
    }

    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self.current_config = {}

    def setup_environment(self, override_existing: bool = False) -> bool:
        """
        Set up the environment for the sync system

        Args:
            override_existing: Whether to override existing environment variables

        Returns:
            bool: True if setup successful
        """
        try:
            logger.info("Setting up LanceDB sync system environment...")

            # Load configuration from file if provided
            if self.config_file and os.path.exists(self.config_file):
                self._load_config_from_file()
            else:
                self.current_config = self.DEFAULT_CONFIG.copy()

            # Set environment variables
            self._set_environment_variables(override_existing)

            # Create required directories
            self._create_required_directories()

            # Verify dependencies
            self._verify_dependencies()

            logger.info("Environment setup completed successfully")
            return True

        except Exception as e:
            logger.error(f"Environment setup failed: {e}")
            return False

    def _load_config_from_file(self) -> None:
        """Load configuration from file"""
        try:
            import json

            with open(self.config_file, "r") as f:
                file_config = json.load(f)

            # Merge with defaults
            self.current_config = {**self.DEFAULT_CONFIG, **file_config}
            logger.info(f"Loaded configuration from {self.config_file}")

        except Exception as e:
            logger.error(f"Failed to load config file {self.config_file}: {e}")
            self.current_config = self.DEFAULT_CONFIG.copy()

    def _set_environment_variables(self, override_existing: bool) -> None:
        """Set environment variables"""
        for key, value in self.current_config.items():
            if override_existing or key not in os.environ:
                os.environ[key] = str(value)
                logger.debug(f"Set environment variable: {key}={value}")

    def _create_required_directories(self) -> None:
        """Create required directories for the sync system"""
        directories = [
            os.path.dirname(os.environ.get("LANCEDB_URI", "data/lancedb")),
            os.environ.get("SYNC_STATE_DIR", "data/sync_state"),
            "logs",
            "tmp",
        ]

        for directory in directories:
            try:
                Path(directory).mkdir(parents=True, exist_ok=True)
                logger.debug(f"Created directory: {directory}")
            except Exception as e:
                logger.warning(f"Failed to create directory {directory}: {e}")

    def _verify_dependencies(self) -> None:
        """Verify that required dependencies are available"""
        dependencies = [
            ("lancedb", "lancedb"),
            ("pyarrow", "pyarrow"),
            ("boto3", "boto3"),
            ("fastapi", "fastapi"),
            ("uvicorn", "uvicorn"),
            ("aiohttp", "aiohttp"),
            ("aiofiles", "aiofiles"),
        ]

        missing_deps = []

        for package_name, import_name in dependencies:
            try:
                __import__(import_name)
                logger.debug(f"Dependency available: {package_name}")
            except ImportError:
                missing_deps.append(package_name)
                logger.warning(f"Dependency missing: {package_name}")

        if missing_deps:
            logger.warning(f"Missing dependencies: {', '.join(missing_deps)}")
            logger.info(
                "Install missing dependencies with: pip install "
                + " ".join(missing_deps)
            )

    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of the current configuration"""
        return {
            "frontend_type": os.environ.get("FRONTEND_TYPE", "desktop"),
            "local_db_path": os.environ.get("LANCEDB_URI"),
            "s3_storage_enabled": os.environ.get("S3_STORAGE_ENABLED", "").lower()
            == "true",
            "s3_backup_enabled": os.environ.get("S3_BACKUP_ENABLED", "").lower()
            == "true",
            "use_s3_as_primary": os.environ.get("USE_S3_AS_PRIMARY", "").lower()
            == "true",
            "local_cache_enabled": os.environ.get("LOCAL_CACHE_ENABLED", "").lower()
            == "true",
            "source_monitoring_enabled": os.environ.get(
                "ENABLE_SOURCE_MONITORING", ""
            ).lower()
            == "true",
            "sync_interval": int(os.environ.get("SYNC_INTERVAL", 300)),
            "health_check_interval": int(os.environ.get("HEALTH_CHECK_INTERVAL", 60)),
        }

    def generate_config_file(self, output_path: str) -> bool:
        """
        Generate a configuration file with current settings

        Args:
            output_path: Path to save the configuration file

        Returns:
            bool: True if generation successful
        """
        try:
            import json

            config_data = {}
            for key in self.DEFAULT_CONFIG.keys():
                config_data[key] = os.environ.get(key, self.DEFAULT_CONFIG[key])

            with open(output_path, "w") as f:
                json.dump(config_data, f, indent=2)

            logger.info(f"Configuration file generated: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to generate config file: {e}")
            return False


def setup_sync_environment(
    config_file: Optional[str] = None,
    override_existing: bool = False,
    generate_config: bool = False,
) -> bool:
    """
    Convenience function to set up the sync system environment

    Args:
        config_file: Path to configuration file
        override_existing: Whether to override existing environment variables
        generate_config: Whether to generate a configuration file

    Returns:
        bool: True if setup successful
    """
    setup = EnvironmentSetup(config_file)

    if not setup.setup_environment(override_existing):
        return False

    if generate_config:
        config_path = config_file or "sync_config.json"
        setup.generate_config_file(config_path)

    # Print configuration summary
    summary = setup.get_config_summary()
    print("\n" + "=" * 50)
    print("LanceDB Sync System - Environment Summary")
    print("=" * 50)
    print(f"Frontend Type: {summary['frontend_type'].upper()}")
    print(f"Local Database: {summary['local_db_path']}")
    print(
        f"S3 Primary Storage: {'Enabled' if summary['s3_storage_enabled'] else 'Disabled'}"
    )
    print(f"S3 Backup: {'Enabled' if summary['s3_backup_enabled'] else 'Disabled'}")
    print(f"Use S3 as Primary: {'Yes' if summary['use_s3_as_primary'] else 'No'}")
    print(f"Local Cache: {'Enabled' if summary['local_cache_enabled'] else 'Disabled'}")
    print(
        f"Source Monitoring: {'Enabled' if summary['source_monitoring_enabled'] else 'Disabled'}"
    )
    print(f"Sync Interval: {summary['sync_interval']} seconds")
    print(f"Health Check: {summary['health_check_interval']} seconds")

    # Frontend-specific recommendations
    if summary["frontend_type"] == "web":
        print("\n📱 Web App Configuration:")
        print("  • S3 Primary Storage: ✅ Recommended")
        print("  • Local Cache: ✅ Optional for performance")
        print("  • S3 Backup: ⚠️ Usually not needed")
    else:
        print("\n💻 Desktop App Configuration:")
        print("  • Local Storage: ✅ Primary")
        print("  • S3 Backup: ✅ Recommended for data safety")
        print("  • S3 Primary: ⚠️ Not recommended for performance")

    print("=" * 50 + "\n")

    return True


def check_environment() -> Dict[str, Any]:
    """
    Check the current environment status

    Returns:
        Dict with environment status information
    """
    status = {
        "environment_ready": True,
        "missing_dependencies": [],
        "configuration_issues": [],
        "directory_issues": [],
    }

    # Check dependencies
    dependencies = [
        "lancedb",
        "pyarrow",
        "boto3",
        "fastapi",
        "uvicorn",
        "aiohttp",
        "aiofiles",
    ]
    for dep in dependencies:
        try:
            __import__(dep)
        except ImportError:
            status["missing_dependencies"].append(dep)
            status["environment_ready"] = False

    # Check required environment variables
    required_vars = ["LANCEDB_URI", "SYNC_STATE_DIR", "FRONTEND_TYPE"]
    for var in required_vars:
        if var not in os.environ:
            status["configuration_issues"].append(
                f"Missing environment variable: {var}"
            )
            status["environment_ready"] = False

    # Validate frontend type
    frontend_type = os.environ.get("FRONTEND_TYPE", "desktop")
    if frontend_type not in ["web", "desktop"]:
        status["configuration_issues"].append(
            f"Invalid FRONTEND_TYPE: {frontend_type}. Must be 'web' or 'desktop'"
        )
        status["environment_ready"] = False

    # Check S3 configuration consistency based on frontend type
    frontend_type = os.environ.get("FRONTEND_TYPE", "desktop")

    if frontend_type == "web":
        # Web app should have S3 storage enabled
        if os.environ.get("S3_STORAGE_ENABLED", "").lower() != "true":
            status["configuration_issues"].append(
                "Web app frontend requires S3 storage to be enabled"
            )
            status["environment_ready"] = False
    else:
        # Desktop app should have local cache enabled
        if os.environ.get("LOCAL_CACHE_ENABLED", "").lower() != "true":
            status["configuration_issues"].append(
                "Desktop app frontend requires local cache to be enabled"
            )
            status["environment_ready"] = False

    if os.environ.get("USE_S3_AS_PRIMARY", "").lower() == "true":
        if os.environ.get("S3_STORAGE_ENABLED", "").lower() != "true":
            status["configuration_issues"].append(
                "Cannot use S3 as primary storage when S3 storage is disabled"
            )
            status["environment_ready"] = False

    if (
        os.environ.get("LOCAL_CACHE_ENABLED", "").lower() != "true"
        and os.environ.get("S3_STORAGE_ENABLED", "").lower() != "true"
    ):
        status["configuration_issues"].append(
            "At least one storage backend must be enabled"
        )
        status["environment_ready"] = False

    # Check directory accessibility
    directories_to_check = [
        os.path.dirname(os.environ.get("LANCEDB_URI", "data/lancedb")),
        os.environ.get("SYNC_STATE_DIR", "data/sync_state"),
    ]

    for directory in directories_to_check:
        try:
            Path(directory).mkdir(parents=True, exist_ok=True)
            # Test write access
            test_file = Path(directory) / ".write_test"
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            status["directory_issues"].append(f"Directory issue with {directory}: {e}")
            status["environment_ready"] = False

    return status


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    import argparse

    parser = argparse.ArgumentParser(
        description="Set up LanceDB sync system environment"
    )
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument(
        "--override",
        action="store_true",
        help="Override existing environment variables",
    )
    parser.add_argument(
        "--generate-config", action="store_true", help="Generate configuration file"
    )
    parser.add_argument(
        "--check", action="store_true", help="Check environment status only"
    )

    args = parser.parse_args()

    if args.check:
        # Check environment status
        status = check_environment()
        print("\nEnvironment Status:")
        print(f"Ready: {'✅' if status['environment_ready'] else '❌'}")

        if status["missing_dependencies"]:
            print(f"Missing Dependencies: {', '.join(status['missing_dependencies'])}")

        if status["configuration_issues"]:
            print(f"Configuration Issues: {', '.join(status['configuration_issues'])}")

        if status["directory_issues"]:
            print(f"Directory Issues: {', '.join(status['directory_issues'])}")

        sys.exit(0 if status["environment_ready"] else 1)

    else:
        # Set up environment
        success = setup_sync_environment(
            config_file=args.config,
            override_existing=args.override,
            generate_config=args.generate_config,
        )

        sys.exit(0 if success else 1)
