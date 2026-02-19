"""
NPM Script Analyzer - Malicious postinstall/preinstall script detection.

Analyzes npm package.json scripts for security threats:
- Network exfiltration (fetch, axios, http requests)
- Credential theft (process.env access, filesystem reads)
- Command execution (child_process, exec, spawn)
- Dynamic code execution (eval, Function constructor)
- Obfuscation (Base64 encoding/decoding)

Reference: Phase 36 RESEARCH.md Pattern 4 "NPM Postinstall Script Threat Detection"
Shai-Hulud/Sha1-Hulud attacks (Sept/Nov 2025) - 700+ packages with credential stealers
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger(__name__)


class NpmScriptAnalyzer:
    """
    Analyzes npm packages for malicious postinstall/preinstall scripts.

    Detects:
    - Network requests (data exfiltration)
    - Credential theft (env vars, file reads)
    - Command execution (child_process)
    - Dynamic code (eval, Function)
    - Obfuscation (atob, btoa)

    Returns:
        {
            "malicious": bool,  # True if CRITICAL patterns found
            "warnings": List[str],  # All detected threats
            "details": List[Dict],  # Detailed threat info
            "scripts_found": List[Dict]  # Scripts discovered
        }
    """

    # Malicious patterns (regex + keyword matching)
    MALICIOUS_PATTERNS = [
        # Network exfiltration
        r'\bfetch\s*\(',
        r'\baxios\s*\.',
        r'\bhttps?\.',
        r'\brequest\s*\(',

        # Credential theft
        r'\bprocess\.env\.',
        r'\bfs\.readFileSync\s*\(',
        r'\bfs\.readFile\s*\(',

        # Command execution
        r'\brequire\s*\(\s*["\']child_process["\']\s*\)',
        r'\bexec\s*\(',
        r'\bspawn\s*\(',

        # Dynamic code execution
        r'\beval\s*\(',
        r'\bFunction\s*\(',

        # Obfuscation
        r'\batob\s*\(',  # Base64 decode
        r'\bbtoa\s*\(',  # Base64 encode
    ]

    # Suspicious package combinations
    SUSPICIOUS_COMBINATIONS = [
        {"packages": ["trufflehog", "axios"], "reason": "Credential exfiltration"},
        {"packages": ["dotenv", "axios"], "reason": "API key theft"},
        {"packages": ["node-fetch", "fs"], "reason": "Data exfiltration"},
    ]

    def analyze_package_scripts(
        self,
        packages: List[str]
    ) -> Dict[str, Any]:
        """
        Analyze packages for malicious postinstall/preinstall scripts.

        Args:
            packages: List of package specifiers

        Returns:
            {
                "malicious": bool,
                "warnings": List[str],
                "details": List[Dict],
                "scripts_found": List[Dict]
            }
        """
        warnings = []
        details = []
        scripts_found = []

        for pkg in packages:
            # Extract package name (handle scoped packages @scope/name)
            pkg_name = self._parse_package_name(pkg)

            # Get package metadata from npm registry
            package_info = self._fetch_package_info(pkg_name)

            if not package_info:
                logger.warning(f"Could not fetch package info for {pkg_name}")
                continue

            # Check scripts section
            scripts = package_info.get("scripts", {})
            postinstall = scripts.get("postinstall", "")
            preinstall = scripts.get("preinstall", "")
            install = scripts.get("install", "")

            if postinstall or preinstall or install:
                scripts_found.append({
                    "package": pkg_name,
                    "postinstall": bool(postinstall),
                    "preinstall": bool(preinstall),
                    "install": bool(install),
                    "content": postinstall or preinstall or install
                })

                # Analyze script content for malicious patterns
                script_content = postinstall or preinstall or install

                for pattern in self.MALICIOUS_PATTERNS:
                    if re.search(pattern, script_content, re.IGNORECASE):
                        warnings.append(
                            f"{pkg_name}: Malicious pattern detected: {pattern}"
                        )
                        details.append({
                            "package": pkg_name,
                            "pattern": pattern,
                            "severity": "CRITICAL",
                            "script_type": "postinstall" if postinstall else ("preinstall" if preinstall else "install"),
                            "content": script_content[:200]  # First 200 chars
                        })

        # Check for suspicious package combinations
        pkg_names = [self._parse_package_name(pkg) for pkg in packages]

        for combo in self.SUSPICIOUS_COMBINATIONS:
            if all(p in pkg_names for p in combo["packages"]):
                warnings.append(
                    f"Suspicious combination: {', '.join(combo['packages'])} "
                    f"- {combo['reason']}"
                )
                details.append({
                    "severity": "HIGH",
                    "type": "suspicious_combination",
                    "packages": combo["packages"],
                    "reason": combo["reason"]
                })

        return {
            "malicious": any(d.get("severity") == "CRITICAL" for d in details),
            "warnings": warnings,
            "details": details,
            "scripts_found": scripts_found
        }

    def _parse_package_name(self, pkg: str) -> str:
        """
        Parse package name from specifier.

        Args:
            pkg: Package specifier (e.g., "lodash@4.17.21", "express@^4.18.0")

        Returns:
            Package name only
        """
        # Handle scoped packages (@scope/name@version)
        if pkg.startswith('@'):
            # Find the version delimiter after the scope
            parts = pkg.split('@')
            if len(parts) >= 3:  # @scope/name@version
                return f"@{parts[1]}"  # Return @scope/name
            else:  # @scope/name without version
                return pkg

        # Handle regular packages (name@version)
        if '@' in pkg:
            return pkg.split('@')[0]

        return pkg

    def _fetch_package_info(self, package_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetch package metadata from npm registry.

        Args:
            package_name: Package name (e.g., "lodash", "@angular/core")

        Returns:
            Package metadata dict or None
        """
        try:
            url = f"https://registry.npmjs.org/{package_name}"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()

                # Get latest version info
                latest_version = data.get("dist-tags", {}).get("latest")
                if latest_version:
                    version_info = data.get("versions", {}).get(latest_version, {})
                    return version_info

                # Fallback to first version if no dist-tags
                versions = data.get("versions", {})
                if versions:
                    first_version = next(iter(versions.values()))
                    return first_version

                return None
            else:
                logger.error(f"npm registry returned {response.status_code} for {package_name}")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"npm registry request timed out for {package_name}")
            return None
        except Exception as e:
            logger.error(f"Error fetching package info for {package_name}: {e}")
            return None

    def analyze_scripts_from_content(
        self,
        package_json_content: str
    ) -> Dict[str, Any]:
        """
        Analyze scripts from package.json content directly.

        Args:
            package_json_content: Raw package.json content as string

        Returns:
            Analysis results
        """
        try:
            package_data = json.loads(package_json_content)
            scripts = package_data.get("scripts", {})

            warnings = []
            details = []
            scripts_found = []

            for script_type, script_content in scripts.items():
                # Focus on lifecycle scripts
                if script_type in ["postinstall", "preinstall", "install", "prepack", "postpack"]:
                    scripts_found.append({
                        "type": script_type,
                        "content": script_content
                    })

                    # Analyze for malicious patterns
                    for pattern in self.MALICIOUS_PATTERNS:
                        if re.search(pattern, script_content, re.IGNORECASE):
                            warnings.append(
                                f"Malicious pattern in {script_type}: {pattern}"
                            )
                            details.append({
                                "script_type": script_type,
                                "pattern": pattern,
                                "severity": "CRITICAL",
                                "content": script_content[:200]
                            })

            return {
                "malicious": any(d.get("severity") == "CRITICAL" for d in details),
                "warnings": warnings,
                "details": details,
                "scripts_found": scripts_found
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse package.json: {e}")
            return {
                "malicious": False,
                "warnings": ["Failed to parse package.json"],
                "details": [],
                "scripts_found": []
            }
