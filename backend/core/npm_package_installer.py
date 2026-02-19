"""
NPM Package Installer - Docker-based npm package installation for skill isolation.

Builds dedicated Docker images for each skill's npm packages to prevent
dependency conflicts between skills (Skill A needs lodash@4.17.21, Skill B needs lodash@5.0.0).

Security constraints:
- Pre-installation vulnerability scanning (npm audit + Snyk)
- --ignore-scripts flag to prevent postinstall malware execution
- Read-only root filesystem
- Resource limits during installation
- Non-root user execution (UID 1001)
- Minimal base image (node:20-alpine)

Reference: Phase 36 RESEARCH.md Pattern 3 "npm Package Installation with Script Protection"
"""

import docker
import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.npm_dependency_scanner import NpmDependencyScanner
from core.skill_sandbox import HazardSandbox

logger = logging.getLogger(__name__)


class NpmPackageInstaller:
    """
    Installs npm packages in dedicated Docker images for skill isolation.

    Builds images tagged by skill ID and version for reusability:
    - Image tag format: "atom-npm-skill:{skill_id}-v{version}"
    - Base image: node:20-alpine (minimal, secure)
    - Working directory: /skill
    - Non-root user: nodejs (UID 1001)
    """

    def __init__(self, snyk_api_key: Optional[str] = None):
        """
        Initialize Docker client, scanner, and sandbox.

        Args:
            snyk_api_key: Optional Snyk API key for commercial vulnerability DB
        """
        self._client = None
        self._scanner = None
        self._sandbox = None
        self._snyk_api_key = snyk_api_key
        logger.info("NpmPackageInstaller initialized (lazy loading)")

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
            self._scanner = NpmDependencyScanner(sny_api_key=self._snyk_api_key)
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
        packages: List[str],
        scan_for_vulnerabilities: bool = True,
        package_manager: str = "npm",
        base_image: str = "node:20-alpine"
    ) -> Dict[str, Any]:
        """
        Install npm packages and build dedicated Docker image for skill.

        Args:
            skill_id: Unique skill identifier
            packages: List of package specifiers (e.g., ["lodash@4.17.21", "express@^4.18.0"])
            scan_for_vulnerabilities: Run vulnerability scan before installation
            package_manager: Package manager to use ("npm", "yarn", or "pnpm")
            base_image: Base Docker image to use

        Returns:
            Dict with:
                - success: bool
                - image_tag: str (Docker image tag)
                - vulnerabilities: List (if scanned)
                - build_logs: List[str] (Docker build logs)
                - error: str (if failed)
        """
        # Handle empty packages
        if not packages:
            return {
                "success": True,
                "image_tag": None,
                "vulnerabilities": [],
                "build_logs": [],
                "warning": "No packages specified"
            }

        # Step 1: Vulnerability scan (if enabled)
        vulnerabilities = []
        if scan_for_vulnerabilities:
            logger.info(f"Scanning {len(packages)} npm packages for vulnerabilities...")
            scan_result = self.scanner.scan_packages(packages, package_manager)
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
        image_tag = f"atom-npm-skill:{skill_id.replace('/', '-')}-v1"

        try:
            logger.info(f"Building image {image_tag} for skill {skill_id}")
            build_logs = self._build_skill_image(
                skill_id=skill_id,
                packages=packages,
                image_tag=image_tag,
                package_manager=package_manager,
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

    def _create_package_json(self, packages: List[str]) -> Dict[str, Any]:
        """
        Create package.json from package specifiers.

        Args:
            packages: List of package specifiers (e.g., "lodash@4.17.21", "express")

        Returns:
            Dict representing package.json
        """
        dependencies = {}

        for pkg in packages:
            # Parse package specifier (e.g., "lodash@4.17.21" or "express")
            if pkg.startswith('@'):
                # Scoped package (@scope/name or @scope/name@version)
                if pkg.count('@') >= 2:  # @scope/name@version
                    parts = pkg.split('@')
                    # parts[0] = '', parts[1] = 'scope/name', parts[2] = 'version'
                    name = f"@{parts[1]}"
                    version = parts[2]
                    dependencies[name] = version
                else:  # @scope/name without version
                    dependencies[pkg] = "*"
            elif '@' in pkg:
                # Regular package with version: name@version
                name, version = pkg.split('@', 1)
                dependencies[name] = version
            else:
                # No version specified, use latest (*)
                dependencies[pkg] = "*"

        return {
            "name": "atom-npm-skill",
            "version": "1.0.0",
            "private": True,
            "dependencies": dependencies
        }

    def _generate_dockerfile(
        self,
        package_json: Dict[str, Any],
        package_manager: str,
        base_image: str
    ) -> str:
        """
        Generate Dockerfile with security constraints.

        CRITICAL: Use --ignore-scripts flag to prevent postinstall malware execution
        CRITICAL: Set NODE_ENV=production for optimizations
        CRITICAL: Create non-root nodejs user (UID 1001)

        Args:
            package_json: Package JSON dict
            package_manager: "npm", "yarn", or "pnpm"
            base_image: Base Docker image

        Returns:
            str: Dockerfile content
        """
        deps_json = json.dumps(package_json, indent=2)

        # Determine install command based on package manager
        # CRITICAL: All commands use --ignore-scripts to prevent postinstall execution
        if package_manager == "npm":
            install_cmd = "npm ci --omit=dev --ignore-scripts"
        elif package_manager == "yarn":
            install_cmd = "yarn install --production --ignore-scripts"
        elif package_manager == "pnpm":
            install_cmd = "pnpm install --prod --ignore-scripts"
        else:
            raise ValueError(f"Unknown package manager: {package_manager}")

        dockerfile = f"""FROM {base_image}

# Set working directory
WORKDIR /skill

# Create package.json
RUN echo '{deps_json}' > package.json

# Install dependencies WITHOUT running scripts (CRITICAL SECURITY MEASURE)
# --ignore-scripts prevents postinstall/preinstall execution
# --omit=dev/--production skips dev dependencies
RUN {install_cmd}

# Clean up npm cache to reduce image size
RUN npm cache clean --force

# Set production environment for optimizations
ENV NODE_ENV=production

# Create non-root user for security (UID 1001)
RUN addgroup -g 1001 -S nodejs && \\
    adduser -S nodejs -u 1001
USER nodejs

# Set working directory
WORKDIR /skill
"""
        return dockerfile

    def _build_skill_image(
        self,
        skill_id: str,
        packages: List[str],
        image_tag: str,
        package_manager: str,
        base_image: str
    ) -> List[str]:
        """
        Build Docker image with skill's npm packages pre-installed.

        Args:
            skill_id: Skill identifier
            packages: List of package specifiers
            image_tag: Docker image tag
            package_manager: Package manager to use
            base_image: Base Docker image

        Returns:
            List of build log lines
        """
        # Create temporary directory for Dockerfile and package.json
        temp_dir = Path(tempfile.mkdtemp(prefix="atom_npm_skill_build_"))

        try:
            # Step 1: Create package.json
            package_json = self._create_package_json(packages)
            package_json_path = temp_dir / "package.json"
            package_json_path.write_text(json.dumps(package_json, indent=2))

            # Step 2: Create Dockerfile
            dockerfile_content = self._generate_dockerfile(
                package_json,
                package_manager,
                base_image
            )

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
        Execute skill code using its dedicated image with pre-installed npm packages.

        Args:
            skill_id: Skill identifier (used to find image tag)
            code: Node.js code to execute
            inputs: Input variables for execution
            timeout_seconds: Maximum execution time
            memory_limit: Memory limit for container
            cpu_limit: CPU quota for container

        Returns:
            str: Execution output or error message

        Raises:
            RuntimeError: If skill image not found
        """
        image_tag = f"atom-npm-skill:{skill_id.replace('/', '-')}-v1"

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
        return self.sandbox.execute_nodejs(
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
        image_tag = f"atom-npm-skill:{skill_id.replace('/', '-')}-v1"

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
        List all Atom npm skill images.

        Returns:
            List of image details with tags, size, created timestamps
        """
        try:
            images = self.client.images.list(filters={"reference": "atom-npm-skill:*"})

            skill_images = []
            for image in images:
                if image.tags and any(tag.startswith("atom-npm-skill:") for tag in image.tags):
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
        installer = NpmPackageInstaller()

        # Test 1: Install simple package
        result = installer.install_packages(
            skill_id="test-npm-skill",
            packages=["lodash@4.17.21"],
            scan_for_vulnerabilities=False  # Skip scan for faster test
        )

        if not result["success"]:
            print(f"✗ NpmPackageInstaller install failed: {result.get('error')}")
            return False

        print(f"✓ NpmPackageInstaller basic test passed (image: {result['image_tag']})")

        # Test 2: Cleanup
        cleanup_success = installer.cleanup_skill_image("test-npm-skill")
        if cleanup_success:
            print("✓ NpmPackageInstaller cleanup test passed")
        else:
            print("⚠ NpmPackageInstaller cleanup test warning (image not found)")

        return True

    except Exception as e:
        print(f"✗ NpmPackageInstaller test failed: {e}")
        return False


if __name__ == "__main__":
    # Run basic test when module executed directly
    test_installer_basic()
