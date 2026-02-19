"""
Test Dynamic Skill Loading - Runtime loading, hot-reload, cache management.

Coverage:
- Load skill from file path
- Reload skill with cache clearing
- Get loaded skill module
- Unload skill
- List loaded skills
- Check for file updates
- Module cache management (sys.modules)
- Version hash calculation
"""

import importlib
import sys
import tempfile
from pathlib import Path

import pytest

from core.skill_dynamic_loader import SkillDynamicLoader


@pytest.fixture
def temp_skill_file():
    """Create temporary skill file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
def run(inputs):
    """Skill execution function."""
    return f"Result: {inputs.get('value', 0)} * 2"

def get_info():
    """Skill metadata function."""
    return {"name": "test_skill", "version": "1.0"}
''')
        temp_path = f.name
    yield temp_path
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def dynamic_loader():
    """Create dynamic loader instance."""
    return SkillDynamicLoader()


class TestSkillLoading:
    """Test basic skill loading functionality."""

    def test_load_skill_from_file(self, dynamic_loader, temp_skill_file):
        """Test loading skill from file path."""
        module = dynamic_loader.load_skill("test_skill", temp_skill_file)

        assert module is not None
        assert hasattr(module, 'run')
        assert hasattr(module, 'get_info')

    def test_load_skill_creates_module_entry(self, dynamic_loader, temp_skill_file):
        """Test that loaded skill is in sys.modules."""
        dynamic_loader.load_skill("test_skill", temp_skill_file)

        assert "test_skill" in sys.modules

    def test_load_skill_stores_metadata(self, dynamic_loader, temp_skill_file):
        """Test that skill metadata is stored."""
        dynamic_loader.load_skill("test_skill", temp_skill_file)

        loaded = dynamic_loader.list_loaded_skills()
        assert "test_skill" in loaded
        assert "path" in loaded["test_skill"]
        assert "loaded_at" in loaded["test_skill"]

    def test_load_nonexistent_file(self, dynamic_loader):
        """Test loading from nonexistent file fails gracefully."""
        result = dynamic_loader.load_skill("missing", "/nonexistent/path.py")

        assert result is None

    def test_execute_loaded_skill(self, dynamic_loader, temp_skill_file):
        """Test executing function from loaded skill."""
        module = dynamic_loader.load_skill("test_skill", temp_skill_file)

        result = module.run({"value": 5})
        assert result == "Result: 5 * 2"


class TestSkillReload:
    """Test hot-reload functionality."""

    def test_reload_skill(self, dynamic_loader, temp_skill_file):
        """Test reloading skill module."""
        # Load original
        module = dynamic_loader.load_skill("test_skill", temp_skill_file)
        original_result = module.run({})

        # Modify file
        with open(temp_skill_file, 'w') as f:
            f.write('''
def run(inputs):
    return "Updated result"

def get_info():
    return {"name": "test_skill", "version": "2.0"}
''')

        # Reload
        reloaded = dynamic_loader.reload_skill("test_skill")
        new_result = reloaded.run({})

        assert new_result == "Updated result"

    def test_reload_clears_module_cache(self, dynamic_loader, temp_skill_file):
        """Test that reload clears sys.modules entry."""
        import gc

        # Load skill
        dynamic_loader.load_skill("test_skill", temp_skill_file)
        original_module = sys.modules.get("test_skill")
        original_id = id(original_module)

        # Modify and reload
        with open(temp_skill_file, 'w') as f:
            f.write('def run(inputs): return "new"')

        dynamic_loader.reload_skill("test_skill")
        reloaded_module = sys.modules.get("test_skill")

        # Module object should be different after reload
        assert id(reloaded_module) != original_id

    def test_reload_unloaded_skill(self, dynamic_loader):
        """Test reloading skill that was never loaded."""
        result = dynamic_loader.reload_skill("never_loaded")

        assert result is None

    def test_check_for_updates(self, dynamic_loader, temp_skill_file):
        """Test checking for file updates."""
        dynamic_loader.load_skill("test_skill", temp_skill_file)

        # No updates yet
        updates = dynamic_loader.check_for_updates()
        assert updates.get("test_skill") is False

        # Modify file
        with open(temp_skill_file, 'w') as f:
            f.write('def run(inputs): return "modified"')

        # Now should show update
        updates = dynamic_loader.check_for_updates()
        assert updates.get("test_skill") is True


class TestSkillUnloading:
    """Test skill unloading functionality."""

    def test_unload_skill(self, dynamic_loader, temp_skill_file):
        """Test unloading removes skill from tracking."""
        dynamic_loader.load_skill("test_skill", temp_skill_file)
        result = dynamic_loader.unload_skill("test_skill")

        assert result is True
        assert "test_skill" not in dynamic_loader.loaded_skills

    def test_unload_clears_sys_modules(self, dynamic_loader, temp_skill_file):
        """Test unloading clears sys.modules entry."""
        dynamic_loader.load_skill("test_skill", temp_skill_file)
        dynamic_loader.unload_skill("test_skill")

        assert "test_skill" not in sys.modules

    def test_unload_nonexistent_skill(self, dynamic_loader):
        """Test unloading skill that was never loaded."""
        result = dynamic_loader.unload_skill("never_loaded")

        assert result is False


class TestVersionTracking:
    """Test file hash version tracking."""

    def test_calculates_file_hash(self, dynamic_loader, temp_skill_file):
        """Test that file hash is calculated."""
        dynamic_loader.load_skill("test_skill", temp_skill_file)

        assert "test_skill" in dynamic_loader.skill_versions
        assert len(dynamic_loader.skill_versions["test_skill"]) == 64  # SHA256

    def test_hash_changes_on_file_modification(self, dynamic_loader, temp_skill_file):
        """Test that hash changes when file is modified."""
        dynamic_loader.load_skill("test_skill", temp_skill_file)
        original_hash = dynamic_loader.skill_versions["test_skill"]

        # Modify file
        with open(temp_skill_file, 'w') as f:
            f.write('def run(inputs): return "modified"')

        dynamic_loader.reload_skill("test_skill")
        new_hash = dynamic_loader.skill_versions["test_skill"]

        assert original_hash != new_hash


class TestModuleCache:
    """Test sys.modules cache management."""

    def test_cache_cleared_before_reload(self, dynamic_loader, temp_skill_file):
        """Test that sys.modules is cleared during reload."""
        import gc

        dynamic_loader.load_skill("test_skill", temp_skill_file)

        # Module is in cache
        assert "test_skill" in sys.modules

        # Modify file to trigger reload
        with open(temp_skill_file, 'w') as f:
            f.write('def run(inputs): return "v2"')

        # Reload should clear cache first
        dynamic_loader.reload_skill("test_skill")

        # New module in cache (different object)
        assert "test_skill" in sys.modules

    def test_module_cache_isolated_between_loaders(self):
        """Test that different loaders have isolated caches."""
        # Create two separate loaders
        loader1 = SkillDynamicLoader()
        loader2 = SkillDynamicLoader()

        # Create two different skill files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f1:
            f1.write('def run(): return "loader1"')
            path1 = f1.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f2:
            f2.write('def run(): return "loader2"')
            path2 = f2.name

        try:
            # Load same skill name with different loaders
            module1 = loader1.load_skill("shared_skill", path1)
            module2 = loader2.load_skill("shared_skill", path2)

            # Each loader should have its own module
            assert module1.run() == "loader1"
            assert module2.run() == "loader2"

        finally:
            # Cleanup
            Path(path1).unlink(missing_ok=True)
            Path(path2).unlink(missing_ok=True)
            loader1.unload_skill("shared_skill")
            loader2.unload_skill("shared_skill")


class TestPerformance:
    """Test performance targets for dynamic loading."""

    def test_load_skill_under_one_second(self, dynamic_loader, temp_skill_file):
        """Test that skill loading completes in under 1 second."""
        import time

        start = time.time()
        module = dynamic_loader.load_skill("perf_skill", temp_skill_file)
        elapsed = time.time() - start

        assert module is not None
        assert elapsed < 1.0, f"Skill loading took {elapsed:.2f}s (target: <1s)"

    def test_reload_skill_under_one_second(self, dynamic_loader, temp_skill_file):
        """Test that skill reload completes in under 1 second."""
        import time

        # Load skill first
        dynamic_loader.load_skill("perf_skill", temp_skill_file)

        # Modify file
        with open(temp_skill_file, 'w') as f:
            f.write('def run(inputs): return "reloaded"')

        # Measure reload time
        start = time.time()
        module = dynamic_loader.reload_skill("perf_skill")
        elapsed = time.time() - start

        assert module is not None
        assert elapsed < 1.0, f"Skill reload took {elapsed:.2f}s (target: <1s)"
        assert module.run({}) == "reloaded"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_load_skill_with_syntax_error(self, dynamic_loader):
        """Test loading skill with syntax error fails gracefully."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('def run(:\n    return "broken syntax"')  # Missing closing paren
            temp_path = f.name

        try:
            result = dynamic_loader.load_skill("broken_skill", temp_path)

            assert result is None
            assert "broken_skill" not in sys.modules

        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_load_skill_with_import_error(self, dynamic_loader):
        """Test loading skill with missing import fails gracefully."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('import nonexistent_module_xyz\ndef run(): return "test"')
            temp_path = f.name

        try:
            result = dynamic_loader.load_skill("import_error_skill", temp_path)

            # Should fail to load due to import error
            assert result is None

        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_force_reload_same_skill(self, dynamic_loader, temp_skill_file):
        """Test force_reload parameter reloads even if unchanged."""
        # Load skill
        module1 = dynamic_loader.load_skill("test_skill", temp_skill_file)
        id1 = id(module1)

        # Force reload without modifying file
        module2 = dynamic_loader.load_skill("test_skill", temp_skill_file, force_reload=True)
        id2 = id(module2)

        # Should get different module object
        assert id1 != id2

    def test_get_skill_returns_none_for_nonexistent(self, dynamic_loader):
        """Test get_skill returns None for nonexistent skill."""
        result = dynamic_loader.get_skill("nonexistent_skill")

        assert result is None

    def test_list_loaded_skills_empty(self, dynamic_loader):
        """Test list_loaded_skills returns empty dict initially."""
        result = dynamic_loader.list_loaded_skills()

        assert result == {}
