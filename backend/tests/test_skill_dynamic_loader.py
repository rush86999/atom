"""
Tests for SkillDynamicLoader - Runtime skill loading with hot-reload.

Tests cover:
- Dynamic skill loading using importlib
- Hot-reload on file changes
- sys.modules cache management
- Version tracking with file hashes
- Optional watchdog file monitoring
"""

import hashlib
import importlib
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock

import pytest

from core.skill_dynamic_loader import SkillDynamicLoader, get_global_loader


@pytest.fixture
def temp_skill_dir():
    """Create temporary directory for skill files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_skill_file(temp_skill_dir):
    """Create a sample skill Python file."""
    skill_path = Path(temp_skill_dir) / "test_skill.py"
    skill_content = """
def run(inputs):
    return {"result": "Hello from skill"}

def metadata():
    return {"name": "test_skill", "version": "1.0.0"}
"""
    skill_path.write_text(skill_content)
    return str(skill_path)


class TestSkillDynamicLoaderInitialization:
    """Test SkillDynamicLoader initialization and configuration."""

    def test_initialization_default(self):
        """Test loader initialization with defaults."""
        loader = SkillDynamicLoader()

        assert loader.skills_dir is None
        assert loader.loaded_skills == {}
        assert loader.skill_versions == {}
        assert loader._observer is None

    def test_initialization_with_skills_dir(self, temp_skill_dir):
        """Test loader initialization with skills directory."""
        loader = SkillDynamicLoader(skills_dir=temp_skill_dir)

        assert loader.skills_dir == Path(temp_skill_dir)
        assert loader.loaded_skills == {}
        assert loader._observer is None  # Monitoring disabled by default

    def test_initialization_with_monitoring(self, temp_skill_dir):
        """Test loader initialization with file monitoring enabled."""
        # Mock watchdog module to avoid actual file monitoring
        with patch.dict('sys.modules', {'watchdog.observers': Mock(), 'watchdog.events': Mock()}):
            from watchdog.observers import Observer
            mock_observer = Mock()
            Observer.return_value = mock_observer

            loader = SkillDynamicLoader(skills_dir=temp_skill_dir, enable_monitoring=True)

            assert loader.skills_dir == Path(temp_skill_dir)

    def test_initialization_monitoring_without_dir(self):
        """Test that monitoring is ignored when no skills_dir provided."""
        loader = SkillDynamicLoader(enable_monitoring=True)

        assert loader.skills_dir is None
        assert loader._observer is None


class TestSkillLoading:
    """Test dynamic skill loading functionality."""

    def test_load_skill_from_file(self, sample_skill_file):
        """Test loading a skill from file path."""
        loader = SkillDynamicLoader()
        module = loader.load_skill("test_skill", sample_skill_file)

        assert module is not None
        assert hasattr(module, 'run')
        assert hasattr(module, 'metadata')

    def test_load_skill_adds_to_sys_modules(self, sample_skill_file):
        """Test that loaded skill is added to sys.modules."""
        loader = SkillDynamicLoader()

        # Clean up if already exists
        if "test_skill_sys" in sys.modules:
            del sys.modules["test_skill_sys"]

        module = loader.load_skill("test_skill_sys", sample_skill_file)

        assert "test_skill_sys" in sys.modules
        assert sys.modules["test_skill_sys"] is module

        # Cleanup
        del sys.modules["test_skill_sys"]

    def test_load_skill_returns_cached_module(self, sample_skill_file):
        """Test that subsequent loads return cached module."""
        loader = SkillDynamicLoader()

        module1 = loader.load_skill("cached_skill", sample_skill_file)
        module2 = loader.load_skill("cached_skill", sample_skill_file)

        assert module1 is module2  # Same object reference

    def test_load_skill_force_reload(self, sample_skill_file):
        """Test force_reload parameter bypasses cache."""
        loader = SkillDynamicLoader()

        module1 = loader.load_skill("reload_skill", sample_skill_file, force_reload=False)
        module2 = loader.load_skill("reload_skill", sample_skill_file, force_reload=True)

        # Should be different objects after force reload
        assert module1 is not module2

    def test_load_skill_file_not_found(self, temp_skill_dir):
        """Test loading non-existent file returns None."""
        loader = SkillDynamicLoader()

        result = loader.load_skill("missing_skill", "/nonexistent/path/skill.py")

        assert result is None

    def test_load_skill_syntax_error(self, temp_skill_dir):
        """Test loading skill with syntax error returns None."""
        loader = SkillDynamicLoader()

        # Create skill file with syntax error
        bad_skill_path = Path(temp_skill_dir) / "bad_skill.py"
        bad_skill_path.write_text("def run(\n")  # Incomplete syntax

        result = loader.load_skill("bad_skill", str(bad_skill_path))

        assert result is None
        # Should clean up sys.modules on error
        assert "bad_skill" not in sys.modules

    def test_load_skill_stores_metadata(self, sample_skill_file):
        """Test that skill metadata is stored after loading."""
        loader = SkillDynamicLoader()

        module = loader.load_skill("metadata_skill", sample_skill_file)

        assert "metadata_skill" in loader.loaded_skills
        skill_info = loader.loaded_skills["metadata_skill"]
        assert skill_info["module"] is module
        assert skill_info["path"] == sample_skill_file
        assert "loaded_at" in skill_info
        assert "hash" in skill_info

    def test_load_skill_calculates_file_hash(self, sample_skill_file):
        """Test that file hash is calculated and stored."""
        loader = SkillDynamicLoader()

        loader.load_skill("hash_skill", sample_skill_file)

        assert "hash_skill" in loader.skill_versions
        file_hash = loader.skill_versions["hash_skill"]
        assert len(file_hash) == 64  # SHA256 hex digest length
        assert file_hash.isalnum()


class TestSkillReloading:
    """Test hot-reload functionality."""

    def test_reload_skill_success(self, sample_skill_file):
        """Test successful skill reload."""
        loader = SkillDynamicLoader()

        # Load initial version
        module1 = loader.load_skill("reload_test", sample_skill_file)

        # Modify the file
        Path(sample_skill_file).write_text("""
def run(inputs):
    return {"result": "Updated version"}

def metadata():
    return {"name": "test_skill", "version": "2.0.0"}
""")

        # Reload
        module2 = loader.reload_skill("reload_test")

        assert module2 is not None
        assert module2 is not module1  # Different object after reload

    def test_reload_skill_not_loaded(self, sample_skill_file):
        """Test reloading skill that was never loaded."""
        loader = SkillDynamicLoader()

        result = loader.reload_skill("never_loaded")

        assert result is None

    def test_reload_skill_unchanged_skips_reload(self, sample_skill_file):
        """Test that reload is skipped if file hasn't changed."""
        loader = SkillDynamicLoader()

        module1 = loader.load_skill("unchanged_skill", sample_skill_file)
        module2 = loader.reload_skill("unchanged_skill")

        # Should return same module (no reload)
        assert module1 is module2

    def test_reload_clears_sys_modules(self, sample_skill_file):
        """Test that reload clears sys.modules to prevent stale code."""
        loader = SkillDynamicLoader()

        # Load skill
        loader.load_skill("clear_test", sample_skill_file)
        assert "clear_test" in sys.modules

        # Modify and reload
        Path(sample_skill_file).write_text("# Modified content\n")
        loader.reload_skill("clear_test")

        # Should still be in sys.modules but with updated code
        assert "clear_test" in sys.modules


class TestSkillRetrieval:
    """Test skill retrieval and querying."""

    def test_get_skill_loaded(self, sample_skill_file):
        """Test getting a loaded skill."""
        loader = SkillDynamicLoader()
        loaded_module = loader.load_skill("get_test", sample_skill_file)

        retrieved_module = loader.get_skill("get_test")

        assert retrieved_module is loaded_module

    def test_get_skill_not_loaded(self):
        """Test getting a skill that was never loaded."""
        loader = SkillDynamicLoader()

        result = loader.get_skill("nonexistent")

        assert result is None


class TestSkillUnloading:
    """Test skill unloading and cleanup."""

    def test_unload_skill_success(self, sample_skill_file):
        """Test successful skill unloading."""
        loader = SkillDynamicLoader()

        # Load skill
        loader.load_skill("unload_test", sample_skill_file)
        assert "unload_test" in loader.loaded_skills

        # Unload
        result = loader.unload_skill("unload_test")

        assert result is True
        assert "unload_test" not in loader.loaded_skills
        assert "unload_test" not in loader.skill_versions

    def test_unload_skill_not_loaded(self):
        """Test unloading skill that was never loaded."""
        loader = SkillDynamicLoader()

        result = loader.unload_skill("never_loaded")

        assert result is False

    def test_unload_clears_sys_modules(self, sample_skill_file):
        """Test that unloading clears sys.modules."""
        loader = SkillDynamicLoader()

        loader.load_skill("sys_clear_test", sample_skill_file)
        assert "sys_clear_test" in sys.modules

        loader.unload_skill("sys_clear_test")

        assert "sys_clear_test" not in sys.modules


class TestSkillListing:
    """Test listing loaded skills."""

    def test_list_loaded_skills_empty(self):
        """Test listing when no skills are loaded."""
        loader = SkillDynamicLoader()

        result = loader.list_loaded_skills()

        assert result == {}

    def test_list_loaded_skills_single(self, sample_skill_file):
        """Test listing with one loaded skill."""
        loader = SkillDynamicLoader()
        loader.load_skill("list_test", sample_skill_file)

        result = loader.list_loaded_skills()

        assert "list_test" in result
        assert result["list_test"]["path"] == sample_skill_file
        assert "loaded_at" in result["list_test"]
        assert "hash" in result["list_test"]
        assert len(result["list_test"]["hash"]) == 8  # First 8 chars

    def test_list_loaded_skills_multiple(self, temp_skill_dir):
        """Test listing with multiple loaded skills."""
        loader = SkillDynamicLoader()

        # Create multiple skill files
        skill1_path = Path(temp_skill_dir) / "skill1.py"
        skill2_path = Path(temp_skill_dir) / "skill2.py"
        skill1_path.write_text("def run(): pass")
        skill2_path.write_text("def run(): pass")

        loader.load_skill("skill1", str(skill1_path))
        loader.load_skill("skill2", str(skill2_path))

        result = loader.list_loaded_skills()

        assert len(result) == 2
        assert "skill1" in result
        assert "skill2" in result


class TestUpdateChecking:
    """Test checking for skill updates."""

    def test_check_for_updates_empty(self):
        """Test update check with no loaded skills."""
        loader = SkillDynamicLoader()

        result = loader.check_for_updates()

        assert result == {}

    def test_check_for_updates_unchanged(self, sample_skill_file):
        """Test update check when skills haven't changed."""
        loader = SkillDynamicLoader()
        loader.load_skill("update_test", sample_skill_file)

        result = loader.check_for_updates()

        assert "update_test" in result
        assert result["update_test"] is False  # No update

    def test_check_for_updates_modified(self, sample_skill_file):
        """Test update check when skill file was modified."""
        loader = SkillDynamicLoader()
        loader.load_skill("modified_test", sample_skill_file)

        # Modify the file
        Path(sample_skill_file).write_text("# Modified content")

        result = loader.check_for_updates()

        assert "modified_test" in result
        assert result["modified_test"] is True  # Update available


class TestFileHashCalculation:
    """Test file hash calculation."""

    def test_calculate_file_hash(self, sample_skill_file):
        """Test SHA256 hash calculation."""
        loader = SkillDynamicLoader()

        hash1 = loader._calculate_file_hash(Path(sample_skill_file))
        hash2 = loader._calculate_file_hash(Path(sample_skill_file))

        # Same file should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64

    def test_calculate_file_hash_different_content(self, temp_skill_dir):
        """Test hash calculation for different content."""
        loader = SkillDynamicLoader()

        file1 = Path(temp_skill_dir) / "file1.py"
        file2 = Path(temp_skill_dir) / "file2.py"
        file1.write_text("content1")
        file2.write_text("content2")

        hash1 = loader._calculate_file_hash(file1)
        hash2 = loader._calculate_file_hash(file2)

        # Different content should produce different hashes
        assert hash1 != hash2

    def test_calculate_file_hash_not_found(self):
        """Test hash calculation for non-existent file."""
        loader = SkillDynamicLoader()

        result = loader._calculate_file_hash(Path("/nonexistent/file.py"))

        assert result == ""


class TestFileMonitoring:
    """Test optional file monitoring functionality."""

    def test_start_monitoring_without_watchdog(self, temp_skill_dir):
        """Test that monitoring is skipped gracefully if watchdog not installed."""
        loader = SkillDynamicLoader(skills_dir=temp_skill_dir)

        # Mock importlib to fail importing watchdog
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith('watchdog'):
                raise ImportError("watchdog not installed")
            return real_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            loader._start_file_monitor()

            # Observer should remain None
            assert loader._observer is None

    def test_start_monitoring_exception_handling(self, temp_skill_dir):
        """Test exception handling in monitoring start."""
        loader = SkillDynamicLoader(skills_dir=temp_skill_dir)

        # Mock importlib to raise exception
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith('watchdog'):
                raise Exception("Test error")
            return real_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            loader._start_file_monitor()

            # Should handle exception gracefully
            assert loader._observer is None

    def test_stop_monitoring_when_not_started(self):
        """Test stopping monitoring when it was never started."""
        loader = SkillDynamicLoader()

        # Should not raise exception
        loader.stop_monitoring()


class TestGlobalLoader:
    """Test global loader instance."""

    def test_get_global_loader_creates_instance(self):
        """Test that get_global_loader creates instance on first call."""
        # Reset global loader
        import core.skill_dynamic_loader
        core.skill_dynamic_loader._global_loader = None

        loader = get_global_loader()

        assert loader is not None
        assert isinstance(loader, SkillDynamicLoader)

    def test_get_global_loader_returns_same_instance(self):
        """Test that get_global_loader returns same instance on subsequent calls."""
        loader1 = get_global_loader()
        loader2 = get_global_loader()

        assert loader1 is loader2

    def test_get_global_loader_with_skills_dir(self, temp_skill_dir):
        """Test get_global_loader with skills_dir parameter."""
        # Reset global loader
        import core.skill_dynamic_loader
        core.skill_dynamic_loader._global_loader = None

        loader = get_global_loader(skills_dir=temp_skill_dir)

        assert loader.skills_dir == Path(temp_skill_dir)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_load_skill_with_import_error(self, temp_skill_dir):
        """Test loading skill that has import errors."""
        loader = SkillDynamicLoader()

        # Create skill with non-existent import
        bad_import_path = Path(temp_skill_dir) / "bad_import.py"
        bad_import_path.write_text("from nonexistent_module import something")

        result = loader.load_skill("bad_import", str(bad_import_path))

        assert result is None

    def test_load_skill_with_runtime_error(self, temp_skill_dir):
        """Test loading skill that executes code with runtime error on import."""
        loader = SkillDynamicLoader()

        # Create skill with runtime error at module level
        runtime_error_path = Path(temp_skill_dir) / "runtime_error.py"
        runtime_error_path.write_text("1 / 0")  # Division by zero

        result = loader.load_skill("runtime_error", str(runtime_error_path))

        assert result is None

    def test_concurrent_reload_handling(self, sample_skill_file):
        """Test that concurrent reloads are handled gracefully."""
        loader = SkillDynamicLoader()

        loader.load_skill("concurrent_test", sample_skill_file)

        # Multiple reloads should work
        result1 = loader.reload_skill("concurrent_test")
        result2 = loader.reload_skill("concurrent_test")

        assert result1 is not None
        assert result2 is not None

    def test_unicode_in_skill_file(self, temp_skill_dir):
        """Test loading skill file with Unicode characters."""
        loader = SkillDynamicLoader()

        unicode_path = Path(temp_skill_dir) / "unicode.py"
        unicode_path.write_text("# -*- coding: utf-8 -*-\ndef run():\n    return {'message': 'Hello 世界'}")

        result = loader.load_skill("unicode_skill", str(unicode_path))

        assert result is not None
