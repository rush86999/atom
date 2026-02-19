"""
Test Auto-Installation Service - Dependency resolution, batch installation, rollback.

Coverage:
- Python dependency resolution
- npm dependency resolution
- Version conflict detection
- Image caching
- Lock acquisition
- Rollback on failure
- Batch installation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.dependency_resolver import DependencyResolver
from core.auto_installer_service import AutoInstallerService


@pytest.fixture
def resolver():
    """Create dependency resolver fixture."""
    return DependencyResolver()


@pytest.fixture
def auto_installer(db_session):
    """Create auto installer fixture."""
    return AutoInstallerService(db_session)


class TestDependencyResolution:
    """Test dependency resolution functionality."""

    def test_resolve_python_packages(self, resolver):
        """Test resolving Python package dependencies."""
        result = resolver.resolve_python_dependencies([
            "requests==2.28.0",
            "numpy>=1.21.0"
        ])

        assert result["success"] is True
        assert result["total_count"] == 2
        assert len(result["dependencies"]) == 2

    def test_detect_python_conflicts(self, resolver):
        """Test detection of Python version conflicts."""
        result = resolver.resolve_python_dependencies([
            "numpy==1.21.0",
            "numpy==1.24.0"  # Conflict!
        ])

        assert result["success"] is False
        assert "conflicts" in result
        assert len(result["conflicts"]) > 0

    def test_resolve_npm_packages(self, resolver):
        """Test resolving npm package dependencies."""
        result = resolver.resolve_npm_dependencies([
            "lodash@4.17.21",
            "express@^4.18.0"
        ])

        assert result["success"] is True
        assert result["total_count"] == 2

    def test_detect_npm_conflicts(self, resolver):
        """Test detection of npm version conflicts."""
        result = resolver.resolve_npm_dependencies([
            "lodash@4.17.21",
            "lodash@5.0.0"  # Conflict!
        ])

        assert result["success"] is False
        assert "conflicts" in result

    def test_check_package_compatibility(self, resolver):
        """Test checking new packages against existing."""
        existing = ["requests==2.28.0"]
        new = ["beautifulsoup4==4.11.0"]

        result = resolver.check_package_compatibility(existing, new, "python")

        assert result["success"] is True

    def test_incompatible_packages(self, resolver):
        """Test incompatible package combinations."""
        existing = ["numpy==1.21.0"]
        new = ["numpy==1.24.0"]

        result = resolver.check_package_compatibility(existing, new, "python")

        assert result["success"] is False

    def test_parse_npm_scoped_package(self, resolver):
        """Test parsing scoped npm packages."""
        name, version = resolver._parse_npm_package("@types/node@20.0.0")

        assert name == "@types/node"
        assert version == "20.0.0"

    def test_parse_npm_regular_package(self, resolver):
        """Test parsing regular npm packages."""
        name, version = resolver._parse_npm_package("lodash@4.17.21")

        assert name == "lodash"
        assert version == "4.17.21"

    def test_parse_npm_package_no_version(self, resolver):
        """Test parsing npm package without version."""
        name, version = resolver._parse_npm_package("express")

        assert name == "express"
        assert version == "latest"


class TestLockAcquisition:
    """Test distributed lock functionality."""

    def test_acquire_lock(self, auto_installer):
        """Test acquiring a lock."""
        lock_key = "test_lock"
        assert auto_installer._acquire_lock(lock_key) is True
        assert auto_installer._acquire_lock(lock_key) is False  # Already held

    def test_release_lock(self, auto_installer):
        """Test releasing a lock."""
        lock_key = "test_lock"
        auto_installer._acquire_lock(lock_key)
        auto_installer._release_lock(lock_key)

        # Should be available again
        assert auto_installer._acquire_lock(lock_key) is True

    def test_lock_expiry(self, auto_installer):
        """Test lock expiration after timeout."""
        import time

        lock_key = "test_lock_expiry"
        auto_installer._locks[lock_key] = time.time() - 400  # Expired

        # Should acquire despite being in map
        assert auto_installer._acquire_lock(lock_key) is True


class TestAutoInstallation:
    """Test auto-installation workflows."""

    @pytest.mark.asyncio
    async def test_install_python_packages(self, auto_installer):
        """Test installing Python packages."""
        with patch.object(auto_installer.python_installer, 'install_packages') as mock_install:
            mock_install.return_value = {
                "success": True,
                "image_tag": "atom-skill:test-skill-v1"
            }

            result = await auto_installer.install_dependencies(
                skill_id="test-skill",
                packages=["requests==2.28.0"],
                package_type="python",
                agent_id="test-agent"
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_install_with_conflicts(self, auto_installer):
        """Test installation fails with conflicts."""
        result = await auto_installer.install_dependencies(
            skill_id="test-skill",
            packages=["numpy==1.21.0", "numpy==1.24.0"],
            package_type="python",
            agent_id="test-agent"
        )

        assert result["success"] is False
        assert "conflicts" in result

    @pytest.mark.asyncio
    async def test_install_with_cached_image(self, auto_installer):
        """Test installation skips if image exists."""
        with patch.object(auto_installer, '_image_exists', return_value=True):
            result = await auto_installer.install_dependencies(
                skill_id="test-skill",
                packages=["requests==2.28.0"],
                package_type="python",
                agent_id="test-agent"
            )

            assert result["success"] is True
            assert result.get("cached") is True

    @pytest.mark.asyncio
    async def test_install_npm_packages(self, auto_installer):
        """Test installing npm packages."""
        with patch.object(auto_installer.npm_installer, 'install_packages') as mock_install:
            mock_install.return_value = {
                "success": True,
                "image_tag": "atom-npm-skill:test-skill-v1"
            }

            result = await auto_installer.install_dependencies(
                skill_id="test-skill",
                packages=["lodash@4.17.21"],
                package_type="npm",
                agent_id="test-agent"
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_install_fails_with_lock_timeout(self, auto_installer):
        """Test installation fails when lock is held."""
        lock_key = f"package_install_lock:test-skill:python"
        auto_installer._locks[lock_key] = __import__('time').time()

        result = await auto_installer.install_dependencies(
            skill_id="test-skill",
            packages=["requests==2.28.0"],
            package_type="python",
            agent_id="test-agent"
        )

        assert result["success"] is False
        assert "already in progress" in result["error"]


class TestBatchInstallation:
    """Test batch installation."""

    @pytest.mark.asyncio
    async def test_batch_install_multiple(self, auto_installer):
        """Test installing multiple skills."""
        async def mock_install(*args, **kwargs):
            return {"success": True}

        with patch.object(auto_installer, 'install_dependencies', side_effect=mock_install):
            result = await auto_installer.batch_install(
                installations=[
                    {"skill_id": "skill1", "packages": ["requests"], "package_type": "python"},
                    {"skill_id": "skill2", "packages": ["numpy"], "package_type": "python"}
                ],
                agent_id="test-agent"
            )

            assert result["success"] is True
            assert result["total"] == 2
            assert result["successes"] == 2
            assert result["failures"] == 0

    @pytest.mark.asyncio
    async def test_batch_with_failures(self, auto_installer):
        """Test batch installation with partial failures."""
        call_count = 0

        async def mock_install(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return {"success": call_count > 1}  # First fails, rest succeed

        with patch.object(auto_installer, 'install_dependencies', side_effect=mock_install):
            result = await auto_installer.batch_install(
                installations=[
                    {"skill_id": "skill1", "packages": ["pkg1"], "package_type": "python"},
                    {"skill_id": "skill2", "packages": ["pkg2"], "package_type": "python"}
                ],
                agent_id="test-agent"
            )

            assert result["success"] is False  # Not all succeeded
            assert result["failures"] == 1

    @pytest.mark.asyncio
    async def test_batch_with_mixed_package_types(self, auto_installer):
        """Test batch installation with both Python and npm packages."""
        async def mock_install(*args, **kwargs):
            return {"success": True, "image_tag": "test-image"}

        with patch.object(auto_installer, 'install_dependencies', side_effect=mock_install):
            result = await auto_installer.batch_install(
                installations=[
                    {"skill_id": "skill1", "packages": ["requests"], "package_type": "python"},
                    {"skill_id": "skill2", "packages": ["lodash"], "package_type": "npm"}
                ],
                agent_id="test-agent"
            )

            assert result["success"] is True
            assert result["total"] == 2


class TestImageManagement:
    """Test Docker image management."""

    def test_get_python_image_tag(self, auto_installer):
        """Test Python image tag generation."""
        tag = auto_installer._get_image_tag("test-skill", "python")

        assert tag == "atom-skill:test-skill-v1"

    def test_get_npm_image_tag(self, auto_installer):
        """Test npm image tag generation."""
        tag = auto_installer._get_image_tag("test-skill", "npm")

        assert tag == "atom-npm-skill:test-skill-v1"

    def test_get_image_tag_with_slash(self, auto_installer):
        """Test image tag generation with slash in skill ID."""
        tag = auto_installer._get_image_tag("user/skill", "python")

        assert tag == "atom-skill:user-skill-v1"

    def test_image_exists_when_found(self, auto_installer):
        """Test image exists check when image is found."""
        # Mock the client property to avoid Docker connection
        mock_client = MagicMock()
        mock_client.images.get.return_value = MagicMock()

        with patch.object(auto_installer.python_installer, '_client', mock_client):
            exists = auto_installer._image_exists("atom-skill:test-v1", "python")

            assert exists is True

    def test_image_exists_when_not_found(self, auto_installer):
        """Test image exists check when image is not found."""
        # Mock the client property to avoid Docker connection
        mock_client = MagicMock()
        mock_client.images.get.side_effect = Exception("Image not found")

        with patch.object(auto_installer.python_installer, '_client', mock_client):
            exists = auto_installer._image_exists("atom-skill:test-v1", "python")

            assert exists is False
