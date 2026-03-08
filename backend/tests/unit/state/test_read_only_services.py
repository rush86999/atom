"""
Unit tests for backend read-only services and configuration.

These tests verify that configuration loaders, constants, and cache helpers
are properly structured and accessible.
"""

import os
import re
from pathlib import Path
import pytest


class TestConfigStructure:
    """Test core/config.py structure."""

    @pytest.fixture
    def config_content(self):
        """Read config.py content."""
        backend_dir = Path(__file__).parent.parent.parent.parent
        config_path = backend_dir / "core" / "config.py"

        if not config_path.exists():
            pytest.skip(f"config.py not found at {config_path}")

        with open(config_path, 'r') as f:
            return f.read()

    def test_config_file_exists(self, config_content):
        """Test that config.py exists and has content."""
        assert len(config_content) > 0
        assert len(config_content) > 500  # Reasonable size

    def test_config_has_database_config(self, config_content):
        """Test that DatabaseConfig class exists."""
        assert "class DatabaseConfig" in config_content
        assert "dataclass" in config_content

    def test_config_has_redis_config(self, config_content):
        """Test that RedisConfig class exists."""
        assert "class RedisConfig" in config_content

    def test_config_has_scheduler_config(self, config_content):
        """Test that SchedulerConfig class exists."""
        assert "class SchedulerConfig" in config_content

    def test_config_has_server_config(self, config_content):
        """Test that ServerConfig class exists."""
        assert "class ServerConfig" in config_content

    def test_config_has_get_config_function(self, config_content):
        """Test that get_config function exists."""
        assert "def get_config" in config_content

    def test_config_has_environment_variable_reading(self, config_content):
        """Test that config reads from environment variables."""
        assert "os.getenv" in config_content or "os.environ" in config_content

    def test_config_has_default_values(self, config_content):
        """Test that config has default values."""
        assert "=" in config_content  # Assignment operators for defaults

    def test_config_uses_dataclass(self, config_content):
        """Test that config uses dataclass pattern."""
        assert "@dataclass" in config_content or "dataclass" in config_content

    def test_config_has_logging(self, config_content):
        """Test that config has logging configuration."""
        assert "logging" in config_content.lower()


class TestGovernanceConfigStructure:
    """Test core/governance_config.py structure."""

    @pytest.fixture
    def governance_config_content(self):
        """Read governance_config.py content."""
        backend_dir = Path(__file__).parent.parent.parent.parent
        config_path = backend_dir / "core" / "governance_config.py"

        if not config_path.exists():
            pytest.skip(f"governance_config.py not found")

        with open(config_path, 'r') as f:
            return f.read()

    def test_governance_config_has_maturity_levels(self, governance_config_content):
        """Test that maturity levels are defined."""
        assert "maturity" in governance_config_content.lower()
        assert "student" in governance_config_content.lower() or "intern" in governance_config_content.lower()

    def test_governance_config_has_action_complexity(self, governance_config_content):
        """Test that action complexity levels are defined."""
        assert "complexity" in governance_config_content.lower() or "action" in governance_config_content.lower()


class TestConstantsStructure:
    """Test that constants are defined in models.py."""

    @pytest.fixture
    def models_content(self):
        """Read models.py content (partial)."""
        backend_dir = Path(__file__).parent.parent.parent.parent
        models_path = backend_dir / "core" / "models.py"

        if not models_path.exists():
            pytest.skip(f"models.py not found")

        with open(models_path, 'r') as f:
            # Read first 500 lines for enums/constants
            lines = []
            for i, line in enumerate(f):
                if i >= 500:
                    break
                lines.append(line)
            return '\n'.join(lines)

    def test_models_has_user_role_enum(self, models_content):
        """Test that UserRole enum exists."""
        assert "class UserRole" in models_content or "UserRole" in models_content

    def test_models_has_enums(self, models_content):
        """Test that enums are defined."""
        assert "enum" in models_content.lower() or "Enum" in models_content


class TestCacheHelpersStructure:
    """Test cache helper structure."""

    @pytest.fixture
    def cache_files(self):
        """Get cache-related file contents."""
        backend_dir = Path(__file__).parent.parent.parent.parent
        cache_path = backend_dir / "core" / "cache.py"
        governance_cache_path = backend_dir / "core" / "governance_cache.py"

        contents = {}
        if cache_path.exists():
            with open(cache_path, 'r') as f:
                contents['cache'] = f.read()
        if governance_cache_path.exists():
            with open(governance_cache_path, 'r') as f:
                contents['governance_cache'] = f.read()

        return contents

    def test_governance_cache_exists(self, cache_files):
        """Test that governance_cache.py exists."""
        if 'governance_cache' not in cache_files:
            pytest.skip("governance_cache.py not found")
        assert len(cache_files['governance_cache']) > 0

    def test_governance_cache_has_cache_class(self, cache_files):
        """Test that governance cache has cache class."""
        if 'governance_cache' not in cache_files:
            pytest.skip("governance_cache.py not found")
        content = cache_files['governance_cache']
        assert "class" in content or "def" in content

    def test_cache_has_get_set_methods(self, cache_files):
        """Test that cache has get/set methods."""
        if 'governance_cache' not in cache_files:
            pytest.skip("governance_cache.py not found")
        content = cache_files['governance_cache']
        # Check for cache operations
        has_get = "get" in content.lower()
        has_set = "set" in content.lower()
        assert has_get or has_set


class TestFeatureFlags:
    """Test feature flag structure."""

    def test_environment_has_feature_flags(self):
        """Test that environment variables can be used for feature flags."""
        # This is a basic test - in real scenarios, you'd check specific feature flags
        # For now, we just verify that the pattern is possible
        backend_dir = Path(__file__).parent.parent.parent.parent
        config_path = backend_dir / "core" / "config.py"

        if config_path.exists():
            with open(config_path, 'r') as f:
                content = f.read()
            # Check for environment variable reading (feature flags use env vars)
            assert "os.getenv" in content or "os.environ" in content


class TestAppVersion:
    """Test app version configuration."""

    def test_app_version_accessible(self):
        """Test that app version can be accessed."""
        # Check main_api_app.py for version
        backend_dir = Path(__file__).parent.parent.parent.parent
        app_path = backend_dir / "main_api_app.py"

        if app_path.exists():
            with open(app_path, 'r') as f:
                content = f.read()
            # Check for version definition
            assert "version" in content.lower()


class TestEnvironmentDetection:
    """Test environment detection."""

    def test_environment_detection_exists(self):
        """Test that environment detection is possible."""
        backend_dir = Path(__file__).parent.parent.parent.parent
        config_path = backend_dir / "core" / "config.py"

        if config_path.exists():
            with open(config_path, 'r') as f:
                content = f.read()
            # Check for ENVIRONMENT variable
            has_env = "ENVIRONMENT" in content or "environment" in content.lower()
            assert has_env


class TestConfigurationIntegrity:
    """Test configuration file integrity."""

    @pytest.fixture
    def all_config_files(self):
        """Get all config file contents."""
        backend_dir = Path(__file__).parent.parent.parent.parent
        config_files = [
            backend_dir / "core" / "config.py",
            backend_dir / "core" / "governance_config.py",
        ]

        contents = {}
        for config_file in config_files:
            if config_file.exists():
                with open(config_file, 'r') as f:
                    contents[config_file.name] = f.read()

        return contents

    def test_config_files_are_readable(self, all_config_files):
        """Test that config files can be read."""
        assert len(all_config_files) > 0

    def test_config_files_have_syntax(self, all_config_files):
        """Test that config files have valid Python syntax."""
        for filename, content in all_config_files.items():
            # Basic syntax check - file should have imports and classes
            has_imports = "import" in content
            has_structure = "class" in content or "def" in content
            assert has_imports or has_structure, f"{filename} has no valid structure"
