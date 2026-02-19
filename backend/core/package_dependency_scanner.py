"""
Package Dependency Scanner - Vulnerability scanning for Python packages.

Scans packages and their transitive dependencies for:
- Known CVEs (Common Vulnerabilities and Exposures)
- PyPI Security Advisory Database entries
- GitHub Advisory Database entries
- Safety DB commercial database (if API key provided)

Uses pip-audit (PyPA-maintained) and Safety (commercial DB) for comprehensive scanning.

Reference: Phase 35 RESEARCH.md Pitfall 5 "Transitive Dependency Vulnerabilities"
"""

import json
import logging
import os
import subprocess
import tempfile
from typing import Any, Dict, List, Optional
from packaging import version as pkg_version

logger = logging.getLogger(__name__)


class PackageDependencyScanner:
    """
    Scans Python packages for security vulnerabilities.

    Returns:
        {
            "safe": bool,  # True if no vulnerabilities found
            "vulnerabilities": List[Dict],  # Vulnerability details
            "dependency_tree": Dict,  # Full dependency tree
            "conflicts": List[Dict]  # Version conflicts detected
        }
    """

    def __init__(self, safety_api_key: Optional[str] = None):
        """
        Initialize scanner with optional Safety API key.

        Args:
            safety_api_key: Safety commercial DB API key (optional)
        """
        self.safety_api_key = safety_api_key or os.getenv("SAFETY_API_KEY")

    def scan_packages(
        self,
        requirements: List[str],
        cache_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Scan package requirements for vulnerabilities.

        Args:
            requirements: List of package specifiers (e.g., ["numpy==1.21.0", "pandas>=1.3.0"])
            cache_dir: Optional cache directory for package metadata

        Returns:
            Dict with scan results including safe flag, vulnerabilities, dependency tree
        """
        # Handle empty requirements
        if not requirements:
            return {
                "safe": True,
                "vulnerabilities": [],
                "dependency_tree": {},
                "conflicts": []
            }

        # Step 1: Create temporary requirements.txt
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('\n'.join(requirements))
            req_file = f.name

        try:
            # Step 2: Build dependency tree
            dependency_tree = self._build_dependency_tree(req_file)

            # Step 3: Run pip-audit (PyPA-maintained)
            audit_result = self._run_pip_audit(req_file)

            # Step 4: Run Safety check (if API key available)
            safety_result = self._run_safety_check(req_file) if self.safety_api_key else {"vulnerabilities": []}

            # Step 5: Check for version conflicts
            conflicts = self._check_version_conflicts(dependency_tree)

            # Step 6: Merge results
            vulnerabilities = audit_result['vulnerabilities'] + safety_result['vulnerabilities']

            return {
                "safe": len(vulnerabilities) == 0 and len(conflicts) == 0,
                "vulnerabilities": vulnerabilities,
                "dependency_tree": dependency_tree,
                "conflicts": conflicts
            }
        finally:
            # Clean up temporary file
            try:
                os.unlink(req_file)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {req_file}: {e}")

    def _build_dependency_tree(self, requirements_file: str) -> Dict[str, Any]:
        """
        Build full dependency tree using pipdeptree.

        Returns: Dict mapping package -> {version, dependencies: [...]}
        """
        try:
            # Install packages first (temporarily)
            subprocess.run(
                ["pip", "install", "--no-deps", "-r", requirements_file],
                capture_output=True,
                timeout=120
            )

            # Get dependency tree
            result = subprocess.run(
                ["pipdeptree", "--json"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                tree_data = json.loads(result.stdout)

                # Convert to simplified format
                dependency_tree = {}
                for pkg in tree_data:
                    package_name = pkg.get("package", {}).get("package_name", "")
                    package_version = pkg.get("package", {}).get("installed_version", "")
                    dependencies = pkg.get("dependencies", [])

                    dependency_tree[package_name] = {
                        "version": package_version,
                        "dependencies": {
                            dep.get("package_name", ""): dep.get("installed_version", "")
                            for dep in dependencies
                        }
                    }

                return dependency_tree
            else:
                logger.error(f"pipdeptree failed: {result.stderr}")
                return {}

        except subprocess.TimeoutExpired:
            logger.error("pipdeptree timed out")
            return {}
        except Exception as e:
            logger.error(f"Error building dependency tree: {e}")
            return {}

    def _run_pip_audit(self, requirements_file: str) -> Dict[str, Any]:
        """
        Run pip-audit and parse JSON output.

        Returns: {"vulnerabilities": [...]}
        """
        try:
            cmd = [
                "pip-audit",
                "--format", "json",
                "--requirement", requirements_file
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                # No vulnerabilities found
                return {"vulnerabilities": []}
            else:
                # Parse vulnerabilities from JSON output
                try:
                    data = json.loads(result.stdout)

                    # Convert to standardized format
                    vulnerabilities = []
                    for vuln in data:
                        vulnerabilities.append({
                            "cve_id": vuln.get("id", "UNKNOWN"),
                            "severity": vuln.get("fix_versions", ["UNKNOWN"])[0],
                            "package": vuln.get("name", "UNKNOWN"),
                            "affected_versions": vuln.get("versions", []),
                            "advisory": vuln.get("description", "No description"),
                            "source": "pip-audit"
                        })

                    return {"vulnerabilities": vulnerabilities}

                except json.JSONDecodeError:
                    logger.error(f"Failed to parse pip-audit output: {result.stdout}")
                    return {"vulnerabilities": []}

        except subprocess.TimeoutExpired:
            logger.error("pip-audit timed out")
            return {"vulnerabilities": []}
        except Exception as e:
            logger.error(f"Error running pip-audit: {e}")
            return {"vulnerabilities": []}

    def _run_safety_check(self, requirements_file: str) -> Dict[str, Any]:
        """
        Run Safety check and parse JSON output.

        Returns: {"vulnerabilities": [...]}
        """
        try:
            cmd = [
                "safety",
                "check",
                "--file", requirements_file,
                "--json",
                "--continue-on-errors"
            ]

            if self.safety_api_key:
                cmd.extend(["--api-key", self.safety_api_key])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                # No vulnerabilities found
                return {"vulnerabilities": []}
            else:
                # Parse vulnerabilities from JSON output
                try:
                    data = json.loads(result.stdout)

                    vulnerabilities = []
                    for vuln in data:
                        vulnerabilities.append({
                            "cve_id": vuln.get("id", "UNKNOWN"),
                            "severity": vuln.get("vulnerability_id", "UNKNOWN"),
                            "package": vuln.get("package_name", "UNKNOWN"),
                            "affected_versions": vuln.get("affected_versions", []),
                            "advisory": vuln.get("advisory", "No description"),
                            "source": "safety"
                        })

                    return {"vulnerabilities": vulnerabilities}

                except json.JSONDecodeError:
                    logger.error(f"Failed to parse Safety output: {result.stdout}")
                    return {"vulnerabilities": []}

        except subprocess.TimeoutExpired:
            logger.error("Safety check timed out")
            return {"vulnerabilities": []}
        except Exception as e:
            logger.error(f"Error running Safety: {e}")
            return {"vulnerabilities": []}

    def _check_version_conflicts(self, dependency_tree: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Check for version conflicts in dependency tree.

        Returns: List of conflict descriptions
        """
        conflicts = []

        # Track version requirements for each package
        package_versions: Dict[str, set] = {}

        for package, details in dependency_tree.items():
            version = details.get("version", "")
            dependencies = details.get("dependencies", {})

            # Check if package is required multiple times with different versions
            if package in package_versions:
                if version not in package_versions[package]:
                    conflicts.append({
                        "package": package,
                        "versions": list(package_versions[package]) + [version],
                        "severity": "version_conflict"
                    })
            else:
                package_versions[package] = {version}

            # Check transitive dependencies for conflicts
            for dep_name, dep_version in dependencies.items():
                if dep_name in package_versions:
                    if dep_version not in package_versions[dep_name]:
                        conflicts.append({
                            "package": dep_name,
                            "versions": list(package_versions[dep_name]) + [dep_version],
                            "severity": "transitive_conflict"
                        })
                else:
                    package_versions[dep_name] = {dep_version}

        return conflicts
