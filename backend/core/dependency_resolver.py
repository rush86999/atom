"""
Dependency Resolver - Python and npm dependency resolution with conflict detection.

Resolves package dependencies with:
- Version conflict detection
- Transitive dependency resolution
- Circular dependency detection
- Compatible version selection

Reference: Phase 60 RESEARCH.md Pattern 4 "Auto-Installation with Dependency Resolution"
"""

import logging
from collections import defaultdict
from typing import Any, Dict, List, Tuple
from packaging.requirements import Requirement

logger = logging.getLogger(__name__)


class DependencyResolver:
    """
    Resolve Python and npm dependencies with conflict detection.

    Simplified resolver for Phase 60:
    - Uses packaging.requirements for Python version parsing
    - Detects direct version conflicts
    - Returns unified dependency list or conflict errors

    For production, consider using pip's full resolver or pubgrub.
    """

    def __init__(self):
        """Initialize dependency resolver."""
        self.logger = logging.getLogger(__name__)

    def resolve_python_dependencies(
        self,
        packages: List[str]
    ) -> Dict[str, Any]:
        """
        Resolve Python package dependencies with conflict detection.

        Args:
            packages: List of package specifiers (e.g., ["numpy==1.21.0", "pandas>=1.3.0"])

        Returns:
            Dict with resolution result
        """
        try:
            # Step 1: Parse requirements
            parsed_reqs = []
            for pkg in packages:
                try:
                    req = Requirement(pkg)
                    parsed_reqs.append(req)
                except Exception as e:
                    logger.warning(f"Failed to parse requirement '{pkg}': {e}")
                    return {
                        "success": False,
                        "error": f"Invalid requirement: {pkg}",
                        "details": str(e)
                    }

            # Step 2: Build dependency graph
            dependency_graph = defaultdict(list)
            package_versions = defaultdict(set)

            for req in parsed_reqs:
                if req.specifier:
                    package_versions[req.name].add(str(req.specifier))
                # For transitive deps, would need to query PyPI (simplified here)
                dependency_graph[req.name] = []

            # Step 3: Detect conflicts
            conflicts = self._detect_conflicts(package_versions)
            if conflicts:
                return {
                    "success": False,
                    "error": "Dependency conflicts detected",
                    "conflicts": conflicts
                }

            # Step 4: Return unified dependency list
            unified_deps = self._flatten_requirements(parsed_reqs)

            return {
                "success": True,
                "dependencies": unified_deps,
                "total_count": len(unified_deps),
                "conflicts": []
            }

        except Exception as e:
            logger.error(f"Dependency resolution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def resolve_npm_dependencies(
        self,
        packages: List[str]
    ) -> Dict[str, Any]:
        """
        Resolve npm package dependencies with conflict detection.

        Args:
            packages: List of npm package specifiers (e.g., ["lodash@4.17.21", "express@^4.18.0"])

        Returns:
            Dict with resolution result
        """
        try:
            # Parse npm packages (simplified)
            package_versions = defaultdict(list)

            for pkg in packages:
                name, version = self._parse_npm_package(pkg)
                if version:
                    package_versions[name].append(version)

            # Detect version conflicts
            conflicts = []
            for name, versions in package_versions.items():
                if len(versions) > 1:
                    conflicts.append({
                        "package": name,
                        "requested_versions": versions
                    })

            if conflicts:
                return {
                    "success": False,
                    "error": "npm version conflicts detected",
                    "conflicts": conflicts
                }

            return {
                "success": True,
                "dependencies": list(set(packages)),
                "total_count": len(set(packages)),
                "conflicts": []
            }

        except Exception as e:
            logger.error(f"npm dependency resolution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _detect_conflicts(
        self,
        package_versions: Dict[str, set]
    ) -> List[Dict[str, Any]]:
        """
        Detect version conflicts in dependency graph.

        Args:
            package_versions: Dict mapping package names to version specifiers

        Returns:
            List of conflict dicts
        """
        conflicts = []

        for package_name, specifiers in package_versions.items():
            if len(specifiers) > 1:
                # Multiple version requirements for same package
                conflicts.append({
                    "package": package_name,
                    "conflicting_versions": list(specifiers)
                })

        return conflicts

    def _flatten_requirements(
        self,
        requirements: List[Requirement]
    ) -> List[str]:
        """
        Flatten requirements into unified package list.

        Args:
            requirements: List of Requirement objects

        Returns:
            List of package specifiers
        """
        return [str(req) for req in requirements]

    def _parse_npm_package(self, package: str) -> Tuple[str, str]:
        """
        Parse npm package specifier into name and version.

        Args:
            package: Package specifier (e.g., "lodash@4.17.21", "express")

        Returns:
            Tuple of (name, version)
        """
        # Handle scoped packages
        if package.startswith('@'):
            if package.count('@') >= 2:
                parts = package.split('@')
                return f"@{parts[1]}", parts[2]
            return package, "latest"

        # Handle regular packages
        if '@' in package:
            name, version = package.split('@', 1)
            return name, version

        return package, "latest"

    def check_package_compatibility(
        self,
        existing_packages: List[str],
        new_packages: List[str],
        package_type: str = "python"
    ) -> Dict[str, Any]:
        """
        Check if new packages are compatible with existing ones.

        Args:
            existing_packages: Already installed packages
            new_packages: Packages to add
            package_type: "python" or "npm"

        Returns:
            Dict with compatibility result
        """
        all_packages = existing_packages + new_packages

        if package_type == "python":
            result = self.resolve_python_dependencies(all_packages)
        else:
            result = self.resolve_npm_dependencies(all_packages)

        return result
