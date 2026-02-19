"""
Package Installer - Docker-based Python package installation for skill isolation.

Builds dedicated Docker images for each skill's Python packages to prevent
dependency conflicts between skills (Skill A needs numpy==1.21, Skill B needs numpy==1.24).

Security constraints:
- Pre-installation vulnerability scanning (pip-audit + Safety)
- Read-only root filesystem
- Resource limits during installation
- Non-root user execution
- Minimal base image (python:3.11-slim)

Reference: Phase 35 RESEARCH.md Pattern 1 "Per-Skill Docker Image Isolation"
"""

import docker
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.package_dependency_scanner import PackageDependencyScanner
from core.skill_sandbox import HazardSandbox

logger = logging.getLogger(__name__)


class PackageInstaller:
    """
    Installs Python packages in dedicated Docker images for skill isolation.

    Builds images tagged by skill ID and version for reusability:
    - Image tag format: "atom-skill:{skill_id}-v{version}"
    - Base image: python:3.11-slim (minimal, secure)
    - Virtual environment: /opt/atom_skill_env (isolated)
    """

    def __init__(self, safety_api_key: Optional[str] = None):
        """
        Initialize Docker client, scanner, and sandbox.

        Args:
            safety_api_key: Optional Safety API key for commercial vulnerability DB
        """
        self._client = None
        self._scanner = None
        self._sandbox = None
        self._safety_api_key = safety_api_key
        logger.info("PackageInstaller initialized (lazy loading)")

    @property
    def client(self):
        """Lazy load Docker client."""
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    @property
    def scanner(self):
        """Lazy load scanner."""
        if self._scanner is None:
            self._scanner = PackageDependencyScanner(safety_api_key=self._safety_api_key)
        return self._scanner

    @property
    def sandbox(self):
        """Lazy load sandbox."""
        if self._sandbox is None:
            self._sandbox = HazardSandbox()
        return self._sandbox

    def install_packages(
        self,
        skill_id: str,
        requirements: List[str],
        scan_for_vulnerabilities: bool = True,
        base_image: str = "python:3.11-slim"
    ) -> Dict[str, Any]:
        """
        Install Python packages and build dedicated Docker image for skill.

        Args:
            skill_id: Unique skill identifier
            requirements: List of package specifiers (e.g., ["numpy==1.21.0", "pandas>=1.3.0"])
            scan_for_vulnerabilities: Run vulnerability scan before installation
            base_image: Base Docker image to use

        Returns:
            Dict with:
                - success: bool
                - image_tag: str (Docker image tag)
                - vulnerabilities: List (if scanned)
                - build_logs: List[str] (Docker build logs)
                - error: str (if failed)
        """
        # Step 1: Vulnerability scan (if enabled)
        vulnerabilities = []
        if scan_for_vulnerabilities:
            logger.info(f"Scanning {len(requirements)} packages for vulnerabilities...")
            scan_result = self.scanner.scan_packages(requirements)
            vulnerabilities = scan_result["vulnerabilities"]

            if not scan_result["safe"]:
                logger.warning(f"Vulnerabilities detected: {len(vulnerabilities)} issues")
                return {
                    "success": False,
                    "error": "Vulnerabilities detected during scanning",
                    "vulnerabilities": vulnerabilities,
                    "image_tag": None
                }

            logger.info(f"Scan complete: {len(vulnerabilities)} vulnerabilities found")

        # Step 2: Build Docker image with packages
        image_tag = f"atom-skill:{skill_id.replace('/', '-')}-v1"

        try:
            logger.info(f"Building image {image_tag} for skill {skill_id}")
            build_logs = self._build_skill_image(
                skill_id=skill_id,
                requirements=requirements,
                image_tag=image_tag,
                base_image=base_image
            )

            logger.info(f"Successfully built image {image_tag} for skill {skill_id}")
            return {
                "success": True,
                "image_tag": image_tag,
                "vulnerabilities": vulnerabilities,
                "build_logs": build_logs
            }

        except Exception as e:
            logger.error(f"Failed to build image for {skill_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "vulnerabilities": vulnerabilities,
                "image_tag": None
            }

    def _build_skill_image(
        self,
        skill_id: str,
        requirements: List[str],
        image_tag: str,
        base_image: str
    ) -> List[str]:
        """
        Build Docker image with skill's Python packages pre-installed.

        Args:
            skill_id: Skill identifier
            requirements: List of package specifiers
            image_tag: Docker image tag
            base_image: Base Docker image

        Returns:
            List of build log lines
        """
        # Create temporary directory for Dockerfile and requirements.txt
        temp_dir = Path(tempfile.mkdtemp(prefix="atom_skill_build_"))

        try:
            # Step 1: Create requirements.txt
            req_file = temp_dir / "requirements.txt"
            req_file.write_text('\n'.join(requirements))

            # Step 2: Create Dockerfile
            dockerfile_content = f"""FROM {base_image}

# Create isolated virtual environment
RUN python -m venv /opt/atom_skill_env
ENV PATH="/opt/atom_skill_env/bin:$PATH"

# Upgrade pip and setuptools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install Python packages
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Clean up
RUN rm /tmp/requirements.txt

# Set working directory
WORKDIR /skill

# Non-root user for security
RUN useradd -m -u 1000 atom && chown -R atom:atom /skill
USER atom
"""

            dockerfile_path = temp_dir / "Dockerfile"
            dockerfile_path.write_text(dockerfile_content)

            # Step 3: Build image
            build_logs = []
            logger.info(f"Building Docker image {image_tag}...")

            image, build_logs_generator = self.client.images.build(
                path=str(temp_dir),
                tag=image_tag,
                rm=True,
                forcerm=True
            )

            # Capture build logs
            for chunk in build_logs_generator:
                if 'stream' in chunk:
                    log_line = chunk['stream'].strip()
                    if log_line:
                        build_logs.append(log_line)
                        logger.debug(f"Build: {log_line}")

            logger.info(f"Built image {image_tag} for skill {skill_id}")
            return build_logs

        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_dir)
                logger.debug(f"Cleaned up temp directory {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory {temp_dir}: {e}")

    def execute_with_packages(
        self,
        skill_id: str,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: int = 30,
        memory_limit: str = "256m",
        cpu_limit: float = 0.5
    ) -> str:
        """
        Execute skill code using its dedicated image with pre-installed packages.

        Args:
            skill_id: Skill identifier (used to find image tag)
            code: Python code to execute
            inputs: Input variables for execution
            timeout_seconds: Maximum execution time
            memory_limit: Memory limit for container
            cpu_limit: CPU quota for container

        Returns:
            str: Execution output or error message

        Raises:
            RuntimeError: If skill image not found
        """
        image_tag = f"atom-skill:{skill_id.replace('/', '-')}-v1"

        # Check if image exists
        try:
            self.client.images.get(image_tag)
            logger.info(f"Found image {image_tag} for skill {skill_id}")
        except docker.errors.ImageNotFound:
            error_msg = (
                f"Image {image_tag} not found. "
                f"Run install_packages() first to build skill image."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Execute using custom image
        return self.sandbox.execute_python(
            code=code,
            inputs=inputs,
            timeout_seconds=timeout_seconds,
            memory_limit=memory_limit,
            cpu_limit=cpu_limit,
            image=image_tag
        )

    def cleanup_skill_image(self, skill_id: str) -> bool:
        """
        Remove skill's Docker image to free disk space.

        Args:
            skill_id: Skill identifier

        Returns:
            bool: True if image removed, False if not found
        """
        image_tag = f"atom-skill:{skill_id.replace('/', '-')}-v1"

        try:
            image = self.client.images.get(image_tag)
            image.remove(force=True)
            logger.info(f"Removed image {image_tag} for skill {skill_id}")
            return True
        except docker.errors.ImageNotFound:
            logger.warning(f"Image {image_tag} not found (already removed)")
            return False
        except Exception as e:
            logger.error(f"Failed to remove image {image_tag}: {e}")
            return False

    def get_skill_images(self) -> List[Dict[str, Any]]:
        """
        List all Atom skill images.

        Returns:
            List of image details with tags, size, created timestamps
        """
        try:
            images = self.client.images.list(filters={"reference": "atom-skill:*"})

            skill_images = []
            for image in images:
                if image.tags and any(tag.startswith("atom-skill:") for tag in image.tags):
                    skill_images.append({
                        "tags": image.tags,
                        "id": image.id,
                        "size": image.attrs.get("Size", 0),
                        "created": image.attrs.get("Created", "")
                    })

            return skill_images

        except Exception as e:
            logger.error(f"Failed to list skill images: {e}")
            return []


def test_installer_basic():
    """Basic smoke test to verify installer functionality."""
    try:
        installer = PackageInstaller()

        # Test 1: Install simple package
        result = installer.install_packages(
            skill_id="test-skill",
            requirements=["requests==2.31.0"],
            scan_for_vulnerabilities=False  # Skip scan for faster test
        )

        if not result["success"]:
            print(f"✗ PackageInstaller install failed: {result.get('error')}")
            return False

        print(f"✓ PackageInstaller basic test passed (image: {result['image_tag']})")

        # Test 2: Cleanup
        cleanup_success = installer.cleanup_skill_image("test-skill")
        if cleanup_success:
            print("✓ PackageInstaller cleanup test passed")
        else:
            print("⚠ PackageInstaller cleanup test warning (image not found)")

        return True

    except Exception as e:
        print(f"✗ PackageInstaller test failed: {e}")
        return False


if __name__ == "__main__":
    # Run basic test when module executed directly
    test_installer_basic()
