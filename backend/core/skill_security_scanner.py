"""
Skill Security Scanner - LLM-based security scanning for community skills.

Provides defense-in-depth security for imported OpenClaw skills using:
- Static pattern matching for known malicious patterns
- GPT-4 semantic analysis for detecting obfuscated threats
- Result caching by SHA hash to avoid re-scanning
- Fail-open behavior to allow imports even if scanning fails

Reference: Phase 14 Plan 03 - Skills Registry & Security
"""

import hashlib
import logging
import os
from typing import Any, Dict, List

from openai import OpenAI

logger = logging.getLogger(__name__)


class SkillSecurityScanner:
    """
    LLM-based malicious pattern detection for community skills.

    Combines fast static analysis (blacklist patterns) with GPT-4
    semantic analysis to detect security risks before import.

    Security patterns:
    - CRITICAL: System commands, container escape attempts
    - HIGH: Data exfiltration, network access, file operations
    - MEDIUM: Suspicious imports, encoded content
    - LOW: No concerning patterns detected
    - UNKNOWN: Scan failed (fail-open behavior)

    Example:
        scanner = SkillSecurityScanner()
        result = scanner.scan_skill(
            skill_name="my_skill",
            skill_content="print('hello')"
        )
        # Returns: {"safe": True, "risk_level": "LOW", "findings": []}
    """

    # Known malicious patterns (static analysis)
    MALICIOUS_PATTERNS = [
        "subprocess.call",
        "os.system",
        "eval(",
        "exec(",
        "pickle.loads",
        "marshal.loads",
        "__import__",
        "socket.socket",
        "urllib.request",
        "requests.post",
        "requests.get",
        "open(",
        "file.write",
        "os.remove",
        "shutil.rmtree",
        "os.unlink",
        "pathlib.Path.unlink",
        "base64.b64decode",
        "getattr(os,",
        "getattr(__import__",
        "compile(",
    ]

    def __init__(self, api_key: str | None = None):
        """
        Initialize security scanner with OpenAI client.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("OpenAI API key not provided - security scanning limited to static analysis")

        # In-memory cache for scan results
        self._scan_cache: Dict[str, Dict[str, Any]] = {}

    def scan_skill(self, skill_name: str, skill_content: str) -> Dict[str, Any]:
        """
        Scan skill for malicious patterns using static + LLM analysis.

        Args:
            skill_name: Name of the skill being scanned
            skill_content: Skill code or prompt content

        Returns:
            Dict with:
                - safe: bool - True if skill passes security checks
                - risk_level: str - "LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"
                - findings: List[str] - List of security concerns found

        Example:
            result = scanner.scan_skill("calculator", "print(2+2)")
            # {"safe": True, "risk_level": "LOW", "findings": []}
        """
        # Check cache first
        cache_key = hashlib.sha256(skill_content.encode()).hexdigest()
        if cache_key in self._scan_cache:
            logger.debug(f"Cache hit for skill '{skill_name}' (SHA: {cache_key[:8]}...)")
            return self._scan_cache[cache_key]

        logger.info(f"Scanning skill '{skill_name}' (SHA: {cache_key[:8]}...)")

        # Step 1: Static pattern matching (fast)
        static_findings = self._static_scan(skill_content)
        if static_findings:
            # Critical patterns found - no need for LLM scan
            result = {
                "safe": False,
                "risk_level": "CRITICAL",
                "findings": static_findings
            }
            self._scan_cache[cache_key] = result
            return result

        # Step 2: LLM semantic analysis (if OpenAI available)
        if self.client:
            llm_result = self._llm_scan(skill_name, skill_content)
            self._scan_cache[cache_key] = llm_result
            return llm_result
        else:
            # No OpenAI client - return safe result with warning
            logger.warning(f"LLM scan skipped for '{skill_name}' (no API key)")
            result = {
                "safe": True,
                "risk_level": "UNKNOWN",
                "findings": ["Static scan passed, LLM scan unavailable (no OPENAI_API_KEY)"]
            }
            self._scan_cache[cache_key] = result
            return result

    def _static_scan(self, code: str) -> List[str]:
        """
        Fast pattern matching for known malicious patterns.

        Args:
            code: Skill code to scan

        Returns:
            List of findings (empty if safe)
        """
        findings = []

        for pattern in self.MALICIOUS_PATTERNS:
            if pattern in code:
                findings.append(f"Detected suspicious pattern: {pattern}")

        if findings:
            logger.warning(f"Static scan found {len(findings)} malicious patterns")

        return findings

    def _llm_scan(self, skill_name: str, skill_content: str) -> Dict[str, Any]:
        """
        Use GPT-4 for semantic analysis of skill code.

        Args:
            skill_name: Name of the skill
            skill_content: Skill code or prompt

        Returns:
            Dict with safe, risk_level, findings
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a security analyst. Analyze this code for malicious intent: "
                            "data exfiltration, unauthorized access, crypto mining, container escape "
                            "attempts, or any suspicious behavior. Respond with a brief analysis."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Skill: {skill_name}\n\nCode:\n```\n{skill_content}\n```\n\n"
                                  f"Analyze for security risks. Start with RISK LEVEL: "
                          f"[LOW/MEDIUM/HIGH/CRITICAL], then explain."
                    }
                ],
                max_tokens=500,
                temperature=0
            )

            analysis = response.choices[0].message.content
            logger.info(f"LLM scan completed for '{skill_name}'")

            # Parse LLM response for risk assessment
            risk_level = self._assess_risk_level(analysis)

            # Determine safety based on risk level
            safe = risk_level in ["LOW", "UNKNOWN"]

            return {
                "safe": safe,
                "risk_level": risk_level,
                "findings": [analysis]
            }

        except Exception as e:
            # Fail-open: Log error but allow import to continue
            logger.error(f"LLM scan failed for '{skill_name}': {e}")
            return {
                "safe": True,
                "risk_level": "UNKNOWN",
                "findings": [f"Scan failed: {str(e)}"]
            }

    def _assess_risk_level(self, analysis: str) -> str:
        """
        Extract risk level from LLM analysis text.

        Args:
            analysis: LLM response text

        Returns:
            "LOW", "MEDIUM", "HIGH", "CRITICAL", or "UNKNOWN"
        """
        analysis_lower = analysis.lower()

        # Check for explicit risk level mentions
        if any(word in analysis_lower for word in ["risk level: critical", "critical risk", "malicious"]):
            return "CRITICAL"
        elif any(word in analysis_lower for word in ["risk level: high", "high risk"]):
            return "HIGH"
        elif any(word in analysis_lower for word in ["risk level: medium", "moderate risk", "suspicious"]):
            return "MEDIUM"
        elif any(word in analysis_lower for word in ["risk level: low", "low risk", "no concerns"]):
            return "LOW"
        else:
            # Default to UNKNOWN if no clear risk level found
            return "UNKNOWN"

    def clear_cache(self) -> None:
        """
        Clear the in-memory scan cache.

        Use this if you want to force re-scanning of skills.
        """
        self._scan_cache.clear()
        logger.info("Security scanner cache cleared")

    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get statistics about the scan cache.

        Returns:
            Dict with cache_size key
        """
        return {"cache_size": len(self._scan_cache)}
