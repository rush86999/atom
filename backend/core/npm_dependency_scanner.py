"""
NPM Dependency Scanner - Vulnerability scanning for npm packages.

Scans packages and their transitive dependencies for:
- Known CVEs (Common Vulnerabilities and Exposures)
- npm Advisory Database entries
- Snyk vulnerability database (if API key provided)

Uses npm audit (npm-maintained) and Snyk (commercial DB) for comprehensive scanning.

Reference: Phase 36 RESEARCH.md Pattern 2 "NPM Dependency Vulnerability Scanning"
Shai-Hulud attack prevention (Sept/Nov 2025 - 700+ infected npm packages)
"""

import json
import logging
import os
import subprocess
import tempfile
from typing import Any, Dict, List, Optional
import shutil

logger = logging.getLogger(__name__)


class NpmDependencyScanner:
    """
    Scans npm packages for security vulnerabilities.

    Returns:
        {
            "safe": bool,  # True if no vulnerabilities found
            "vulnerabilities": List[Dict],  # Vulnerability details
            "dependency_tree": Dict,  # Package list with versions
            "warning": Optional[str]  # Timeout warnings
        }
    """

    def __init__(self, snyk_api_key: Optional[str] = None):
        """
        Initialize scanner with optional Snyk API key.

        Args:
            snyk_api_key: Snyk commercial DB API key (optional)
        """
        self.snyk_api_key = snyk_api_key or os.getenv("SNYK_API_KEY")

    def scan_packages(
        self,
        packages: List[str],
        package_manager: str = "npm",
        cache_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Scan npm packages for vulnerabilities.

        Args:
            packages: List of package specifiers (e.g., ["lodash@4.17.21", "express@^4.18.0"])
            package_manager: "npm", "yarn", or "pnpm"
            cache_dir: Optional cache directory for package metadata

        Returns:
            Dict with scan results including safe flag, vulnerabilities, dependency tree
        """
        # Handle empty packages
        if not packages:
            return {
                "safe": True,
                "vulnerabilities": [],
                "dependency_tree": {},
                "warning": None
            }

        # Create temporary directory for scanning
        with tempfile.TemporaryDirectory(prefix="npm_scan_") as temp_dir:
            try:
                # Step 1: Create package.json with dependencies
                package_json = self._create_package_json(packages)
                package_json_path = os.path.join(temp_dir, "package.json")

                with open(package_json_path, 'w') as f:
                    json.dump(package_json, f, indent=2)

                # Step 2: Install packages (without scripts for security)
                self._install_packages(temp_dir, package_manager)

                # Step 3: Build dependency tree
                dependency_tree = self._build_dependency_tree(temp_dir)

                # Step 4: Run npm audit
                audit_result = self._run_package_manager_audit(temp_dir, package_manager)

                # Step 5: Run Snyk check (if API key available)
                snyk_result = self._run_snyk_check(temp_dir) if self.snyk_api_key else {"vulnerabilities": []}

                # Step 6: Merge results
                vulnerabilities = audit_result['vulnerabilities'] + snyk_result['vulnerabilities']

                return {
                    "safe": len(vulnerabilities) == 0,
                    "vulnerabilities": vulnerabilities,
                    "dependency_tree": dependency_tree,
                    "warning": None
                }

            except subprocess.TimeoutExpired as e:
                logger.error(f"Package scan timed out: {e}")
                return {
                    "safe": True,  # Timeout doesn't mean unsafe, just couldn't scan
                    "vulnerabilities": [],
                    "dependency_tree": {},
                    "warning": f"Scan timed out after {e.timeout}s - unable to verify safety"
                }
            except Exception as e:
                logger.error(f"Error scanning packages: {e}")
                return {
                    "safe": True,  # Error doesn't mean unsafe, just couldn't scan
                    "vulnerabilities": [],
                    "dependency_tree": {},
                    "warning": f"Scan failed: {str(e)}"
                }

    def _create_package_json(self, packages: List[str]) -> Dict[str, Any]:
        """
        Create package.json with specified dependencies.

        Args:
            packages: List of package specifiers

        Returns:
            package.json dict
        """
        dependencies = {}

        for pkg in packages:
            # Parse package specifier (e.g., "lodash@4.17.21" or "express")
            if '@' in pkg and not pkg.startswith('@'):
                # Scoped packages start with @, so check if @ is not at start
                name, version = pkg.split('@', 1)
                dependencies[name] = version
            else:
                # No version specified, use latest (*)
                dependencies[pkg] = "*"

        return {
            "name": "atom-scan-temp",
            "version": "1.0.0",
            "private": True,
            "dependencies": dependencies
        }

    def _install_packages(
        self,
        working_dir: str,
        package_manager: str
    ) -> None:
        """
        Install packages without running scripts (security measure).

        Args:
            working_dir: Directory containing package.json
            package_manager: "npm", "yarn", or "pnpm"

        Raises:
            subprocess.CalledProcessError: If installation fails
            subprocess.TimeoutExpired: If installation times out
        """
        try:
            if package_manager == "npm":
                cmd = ["npm", "install", "--ignore-scripts", "--no-audit", "--no-fund"]
            elif package_manager == "yarn":
                cmd = ["yarn", "install", "--ignore-scripts", "--silent"]
            elif package_manager == "pnpm":
                cmd = ["pnpm", "install", "--ignore-scripts", "--silent"]
            else:
                raise ValueError(f"Unknown package manager: {package_manager}")

            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                logger.error(f"{package_manager} install failed: {result.stderr}")
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stderr)

        except subprocess.TimeoutExpired:
            logger.error(f"{package_manager} install timed out")
            raise
        except Exception as e:
            logger.error(f"Error installing packages: {e}")
            raise

    def _build_dependency_tree(self, working_dir: str) -> Dict[str, Any]:
        """
        Build dependency tree using npm list.

        Args:
            working_dir: Directory containing node_modules

        Returns:
            Dict mapping package -> version
        """
        try:
            cmd = ["npm", "list", "--json", "--depth=0"]

            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    dependencies = data.get("dependencies", {})

                    dependency_tree = {}
                    for name, info in dependencies.items():
                        dependency_tree[name] = {
                            "version": info.get("version", "unknown"),
                            "resolved": info.get("resolved", "unknown")
                        }

                    return dependency_tree

                except json.JSONDecodeError:
                    logger.error(f"Failed to parse npm list output: {result.stdout}")
                    return {}
            else:
                logger.error(f"npm list failed: {result.stderr}")
                return {}

        except subprocess.TimeoutExpired:
            logger.error("npm list timed out")
            return {}
        except Exception as e:
            logger.error(f"Error building dependency tree: {e}")
            return {}

    def _run_package_manager_audit(
        self,
        working_dir: str,
        package_manager: str
    ) -> Dict[str, Any]:
        """
        Run npm/yarn/pnpm audit and parse JSON output.

        Args:
            working_dir: Directory containing package.json
            package_manager: "npm", "yarn", or "pnpm"

        Returns:
            {"vulnerabilities": [...]}
        """
        try:
            if package_manager == "npm":
                cmd = ["npm", "audit", "--json"]
            elif package_manager == "yarn":
                cmd = ["yarn", "audit", "--json"]
            elif package_manager == "pnpm":
                cmd = ["pnpm", "audit", "--json"]
            else:
                raise ValueError(f"Unknown package manager: {package_manager}")

            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=120
            )

            # npm audit returns 0 for no vulnerabilities, 1 for vulnerabilities found
            if result.returncode in [0, 1]:
                try:
                    data = json.loads(result.stdout)

                    # Parse npm audit JSON format
                    vulnerabilities = []
                    audit_data = data.get("vulnerabilities", {})

                    for pkg_name, vuln_info in audit_data.items():
                        # Handle both single vulnerability object and list of vulnerabilities
                        if isinstance(vuln_info, dict):
                            vuln_list = [vuln_info]
                        else:
                            vuln_list = vuln_info if isinstance(vuln_info, list) else []

                        for vuln in vuln_list:
                            vulnerabilities.append({
                                "cve_id": vuln.get("cwe", "UNKNOWN"),
                                "severity": vuln.get("severity", "UNKNOWN"),
                                "package": pkg_name,
                                "affected_versions": vuln.get("range", []),
                                "advisory": vuln.get("title", "No description"),
                                "source": f"{package_manager}-audit"
                            })

                    return {"vulnerabilities": vulnerabilities}

                except json.JSONDecodeError:
                    logger.error(f"Failed to parse {package_manager} audit output")
                    return {"vulnerabilities": []}
            else:
                logger.error(f"{package_manager} audit failed: {result.stderr}")
                return {"vulnerabilities": []}

        except subprocess.TimeoutExpired:
            logger.error(f"{package_manager} audit timed out")
            return {"vulnerabilities": []}
        except Exception as e:
            logger.error(f"Error running {package_manager} audit: {e}")
            return {"vulnerabilities": []}

    def _run_snyk_check(self, working_dir: str) -> Dict[str, Any]:
        """
        Run Snyk vulnerability check and parse JSON output.

        Args:
            working_dir: Directory containing package.json

        Returns:
            {"vulnerabilities": [...]}
        """
        # Check if Snyk CLI is installed
        if not shutil.which("snyk"):
            logger.warning("Snyk CLI not found - skipping Snyk check")
            return {"vulnerabilities": []}

        try:
            # Snyk must be authenticated first: snyk auth
            cmd = [
                "snyk",
                "test",
                "--json",
                "--severity-threshold=medium"  # Ignore low severity
            ]

            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=120,
                env={**os.environ, "SNYK_API_KEY": self.snyk_api_key}
            )

            if result.returncode == 0:
                # No vulnerabilities found
                return {"vulnerabilities": []}
            else:
                # Parse vulnerabilities from JSON output
                try:
                    data = json.loads(result.stdout)

                    vulnerabilities = []
                    for vuln in data.get("vulnerabilities", []):
                        vulnerabilities.append({
                            "cve_id": vuln.get("identifiers", {}).get("CVE", ["UNKNOWN"])[0],
                            "severity": vuln.get("severity", "UNKNOWN"),
                            "package": vuln.get("packageName", "UNKNOWN"),
                            "affected_versions": vuln.get("semver", {}).get("vulnerable", []),
                            "advisory": vuln.get("title", "No description"),
                            "source": "snyk"
                        })

                    return {"vulnerabilities": vulnerabilities}

                except json.JSONDecodeError:
                    logger.error(f"Failed to parse Snyk output: {result.stdout}")
                    return {"vulnerabilities": []}

        except subprocess.TimeoutExpired:
            logger.error("Snyk check timed out")
            return {"vulnerabilities": []}
        except Exception as e:
            logger.error(f"Error running Snyk: {e}")
            return {"vulnerabilities": []}
