"""
Auto Installer Service - Batch package installation with rollback.

Automatically installs Python and npm dependencies with:
- Dependency resolution
- Conflict detection
- Distributed locking (Redis)
- Rollback on failure
- Image reuse

Reference: Phase 60 RESEARCH.md Pattern 4 "Auto-Installation with Dependency Resolution"
"""

import logging
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.dependency_resolver import DependencyResolver
from core.package_installer import PackageInstaller
from core.npm_package_installer import NpmPackageInstaller

logger = logging.getLogger(__name__)


class AutoInstallerService:
    """
    Automatic package installation with rollback.

    Workflow:
    1. Resolve dependencies
    2. Check for conflicts
    3. Acquire distributed lock
    4. Install packages in batch
    5. Release lock on success
    6. Rollback on failure
    """

    def __init__(self, db: Session):
        """
        Initialize auto installer.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.resolver = DependencyResolver()
        self._python_installer = None
        self._npm_installer = None
        self._locks = {}  # In-memory locks (use Redis in production)

    @property
    def python_installer(self) -> PackageInstaller:
        """Lazy load Python installer."""
        if self._python_installer is None:
            self._python_installer = PackageInstaller()
        return self._python_installer

    @property
    def npm_installer(self) -> NpmPackageInstaller:
        """Lazy load npm installer."""
        if self._npm_installer is None:
            self._npm_installer = NpmPackageInstaller()
        return self._npm_installer

    async def install_dependencies(
        self,
        skill_id: str,
        packages: List[str],
        package_type: str,
        agent_id: str,
        scan_for_vulnerabilities: bool = True
    ) -> Dict[str, Any]:
        """
        Install dependencies with conflict detection and rollback.

        Args:
            skill_id: Unique skill identifier
            packages: List of package specifiers
            package_type: "python" or "npm"
            agent_id: Agent ID requesting installation
            scan_for_vulnerabilities: Run security scan

        Returns:
            Dict with installation result
        """
        lock_key = f"package_install_lock:{skill_id}:{package_type}"

        try:
            # Step 1: Acquire lock
            if not self._acquire_lock(lock_key):
                return {
                    "success": False,
                    "error": "Installation already in progress"
                }

            # Step 2: Resolve dependencies
            if package_type == "python":
                resolution = self.resolver.resolve_python_dependencies(packages)
            else:
                resolution = self.resolver.resolve_npm_dependencies(packages)

            if not resolution["success"]:
                return {
                    "success": False,
                    "error": resolution["error"],
                    "conflicts": resolution.get("conflicts", [])
                }

            # Step 3: Check if image already exists
            image_tag = self._get_image_tag(skill_id, package_type)
            if self._image_exists(image_tag, package_type):
                logger.info(f"Image {image_tag} already exists, skipping build")
                return {
                    "success": True,
                    "image_tag": image_tag,
                    "cached": True
                }

            # Step 4: Install packages
            install_result = await self._install_packages(
                skill_id=skill_id,
                packages=resolution["dependencies"],
                package_type=package_type,
                scan_for_vulnerabilities=scan_for_vulnerabilities
            )

            if not install_result["success"]:
                # Rollback
                await self._rollback_installation(skill_id, package_type)
                return install_result

            return {
                "success": True,
                "installed_packages": resolution["dependencies"],
                "image_tag": install_result.get("image_tag"),
                "total_count": resolution["total_count"]
            }

        except Exception as e:
            logger.error(f"Auto-installation failed: {e}")
            await self._rollback_installation(skill_id, package_type)
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            # Release lock
            self._release_lock(lock_key)

    async def _install_packages(
        self,
        skill_id: str,
        packages: List[str],
        package_type: str,
        scan_for_vulnerabilities: bool
    ) -> Dict[str, Any]:
        """Install packages using appropriate installer."""
        if package_type == "python":
            result = self.python_installer.install_packages(
                skill_id=skill_id,
                requirements=packages,
                scan_for_vulnerabilities=scan_for_vulnerabilities
            )
        else:  # npm
            result = self.npm_installer.install_packages(
                skill_id=skill_id,
                packages=packages,
                scan_for_vulnerabilities=scan_for_vulnerabilities
            )

        return result

    async def _rollback_installation(self, skill_id: str, package_type: str):
        """Rollback failed installation (cleanup images)."""
        logger.warning(f"Rolling back installation for {skill_id} ({package_type})")

        try:
            if package_type == "python":
                self.python_installer.cleanup_skill_image(skill_id)
            else:
                self.npm_installer.cleanup_skill_image(skill_id)
        except Exception as e:
            logger.error(f"Rollback failed: {e}")

    def _get_image_tag(self, skill_id: str, package_type: str) -> str:
        """Get Docker image tag for skill."""
        if package_type == "python":
            return f"atom-skill:{skill_id.replace('/', '-')}-v1"
        else:
            return f"atom-npm-skill:{skill_id.replace('/', '-')}-v1"

    def _image_exists(self, image_tag: str, package_type: str) -> bool:
        """Check if Docker image already exists."""
        try:
            if package_type == "python":
                self.python_installer.client.images.get(image_tag)
            else:
                self.npm_installer.client.images.get(image_tag)
            return True
        except Exception:
            return False

    def _acquire_lock(self, lock_key: str, timeout: int = 30) -> bool:
        """Acquire distributed lock (simplified in-memory)."""
        if lock_key in self._locks:
            # Check if lock expired
            if time.time() - self._locks[lock_key] > 300:  # 5 min timeout
                del self._locks[lock_key]
            else:
                return False

        self._locks[lock_key] = time.time()
        return True

    def _release_lock(self, lock_key: str):
        """Release distributed lock."""
        if lock_key in self._locks:
            del self._locks[lock_key]

    async def batch_install(
        self,
        installations: List[Dict[str, Any]],
        agent_id: str
    ) -> Dict[str, Any]:
        """
        Install multiple skill dependencies in batch.

        Args:
            installations: List of {skill_id, packages, package_type}
            agent_id: Agent ID requesting installations

        Returns:
            Dict with batch installation result
        """
        results = []
        successes = 0
        failures = 0

        for install_spec in installations:
            skill_id = install_spec["skill_id"]
            packages = install_spec["packages"]
            package_type = install_spec.get("package_type", "python")

            result = await self.install_dependencies(
                skill_id=skill_id,
                packages=packages,
                package_type=package_type,
                agent_id=agent_id
            )

            results.append({
                "skill_id": skill_id,
                "result": result
            })

            if result["success"]:
                successes += 1
            else:
                failures += 1

        return {
            "success": failures == 0,
            "total": len(installations),
            "successes": successes,
            "failures": failures,
            "results": results
        }
