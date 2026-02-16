"""
Tests for SkillSecurityScanner

Unit tests for LLM-based security scanning with static pattern matching.
Tests malicious pattern detection, risk assessment, caching, and fail-open behavior.

Reference: Phase 14 Plan 03 - Skills Registry & Security
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from core.skill_security_scanner import SkillSecurityScanner


class TestStaticScan:
    """Test static pattern matching for malicious code."""

    def test_static_scan_detects_malicious_patterns(self):
        """Verify blacklist patterns are detected."""
        scanner = SkillSecurityScanner()

        malicious_code = """
import os
os.system("rm -rf /")
eval(user_input)
subprocess.call(["malicious"])
"""

        findings = scanner._static_scan(malicious_code)

        assert len(findings) >= 3
        assert any("os.system" in f for f in findings)
        assert any("eval(" in f for f in findings)
        assert any("subprocess.call" in f for f in findings)

    def test_static_scan_passes_safe_code(self):
        """Safe code should pass static scan."""
        scanner = SkillSecurityScanner()

        safe_code = """
def add_numbers(a, b):
    return a + b

result = add_numbers(2, 3)
print(result)
"""

        findings = scanner._static_scan(safe_code)

        assert len(findings) == 0

    def test_static_scan_detects_all_blacklist_patterns(self):
        """Test all patterns in MALICIOUS_PATTERNS list."""
        scanner = SkillSecurityScanner()

        for pattern in scanner.MALICIOUS_PATTERNS:
            # Create code with pattern
            code = f"def test():\n    {pattern}\n"
            findings = scanner._static_scan(code)

            assert len(findings) >= 1
            assert any(pattern in f for f in findings)


class TestLLMScan:
    """Test LLM-based semantic analysis."""

    @patch('core.skill_security_scanner.OpenAI')
    def test_llm_scan_returns_risk_assessment(self, mock_openai):
        """Mock GPT-4 call returns risk assessment."""
        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "RISK LEVEL: LOW\nNo security concerns found."
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        scanner = SkillSecurityScanner()
        scanner.client = mock_client

        result = scanner._llm_scan("test_skill", "print('hello')")

        assert "safe" in result
        assert "risk_level" in result
        assert "findings" in result
        assert result["risk_level"] == "LOW"

    @patch('core.skill_security_scanner.OpenAI')
    def test_llm_scan_detects_high_risk(self, mock_openai):
        """LLM detects high risk code."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            "RISK LEVEL: HIGH\n"
            "This code attempts data exfiltration and unauthorized access."
        )
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        scanner = SkillSecurityScanner()
        scanner.client = mock_client

        result = scanner._llm_scan("malicious", "suspicious_code")

        assert result["risk_level"] == "HIGH"
        assert result["safe"] == False

    @patch('core.skill_security_scanner.OpenAI')
    def test_llm_scan_fails_gracefully(self, mock_openai):
        """LLM scan failure returns safe result (fail-open)."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_openai.return_value = mock_client

        scanner = SkillSecurityScanner()
        scanner.client = mock_client

        result = scanner._llm_scan("test", "code")

        # Fail-open behavior
        assert result["safe"] == True
        assert result["risk_level"] == "UNKNOWN"
        assert "Scan failed" in result["findings"][0]


class TestRiskAssessment:
    """Test risk level classification."""

    def test_risk_level_critical(self):
        """Critical risk assessment."""
        scanner = SkillSecurityScanner()

        analysis = "This code is CRITICAL with malicious intent"
        risk = scanner._assess_risk_level(analysis)

        assert risk == "CRITICAL"

    def test_risk_level_high(self):
        """High risk assessment."""
        scanner = SkillSecurityScanner()

        analysis = "RISK LEVEL: high - dangerous patterns detected"
        risk = scanner._assess_risk_level(analysis)

        assert risk == "HIGH"

    def test_risk_level_medium(self):
        """Medium risk assessment."""
        scanner = SkillSecurityScanner()

        analysis = "Moderate risk - suspicious behavior found"
        risk = scanner._assess_risk_level(analysis)

        assert risk == "MEDIUM"

    def test_risk_level_low(self):
        """Low risk assessment."""
        scanner = SkillSecurityScanner()

        analysis = "RISK LEVEL: low - no concerns"
        risk = scanner._assess_risk_level(analysis)

        assert risk == "LOW"

    def test_risk_level_unknown(self):
        """Unknown risk when no clear indicators."""
        scanner = SkillSecurityScanner()

        analysis = "This is just some analysis text"
        risk = scanner._assess_risk_level(analysis)

        assert risk == "UNKNOWN"


class TestCaching:
    """Test scan result caching."""

    def test_scan_caches_results_by_sha(self):
        """Verify cache behavior with same content."""
        scanner = SkillSecurityScanner()

        # Mock LLM to avoid API call
        with patch.object(scanner, '_llm_scan') as mock_llm:
            mock_llm.return_value = {
                "safe": True,
                "risk_level": "LOW",
                "findings": []
            }

            # First scan
            result1 = scanner.scan_skill("test", "code_content")
            assert mock_llm.call_count == 1

            # Second scan with same content
            result2 = scanner.scan_skill("test", "code_content")
            assert mock_llm.call_count == 1  # Should not increase

            # Results should be identical
            assert result1 == result2

    def test_cache_can_be_cleared(self):
        """Cache can be cleared to force re-scanning."""
        scanner = SkillSecurityScanner()

        with patch.object(scanner, '_llm_scan') as mock_llm:
            mock_llm.return_value = {
                "safe": True,
                "risk_level": "LOW",
                "findings": []
            }

            # First scan
            scanner.scan_skill("test", "code")
            assert scanner.get_cache_stats()["cache_size"] == 1

            # Clear cache
            scanner.clear_cache()
            assert scanner.get_cache_stats()["cache_size"] == 0

            # Second scan should call LLM again
            scanner.scan_skill("test", "code")
            assert mock_llm.call_count == 2


class TestFullScanWorkflow:
    """Test complete scan workflow."""

    def test_scan_skill_critical_pattern_returns_immediately(self):
        """Critical patterns return CRITICAL without LLM scan."""
        scanner = SkillSecurityScanner()

        with patch.object(scanner, '_llm_scan') as mock_llm:
            malicious_code = "os.system('rm -rf /')"

            result = scanner.scan_skill("malicious", malicious_code)

            # Should NOT call LLM for critical patterns
            assert mock_llm.call_count == 0
            assert result["risk_level"] == "CRITICAL"
            assert result["safe"] == False

    def test_scan_skill_without_openai_key(self):
        """Scanner works without OpenAI API key (static only)."""
        # Create scanner without API key
        scanner = SkillSecurityScanner(api_key=None)

        safe_code = "print('hello world')"
        result = scanner.scan_skill("test", safe_code)

        # Should return safe but with UNKNOWN risk (no LLM)
        assert result["safe"] == True
        assert result["risk_level"] == "UNKNOWN"
        assert "LLM scan unavailable" in result["findings"][0]

    def test_scan_skill_integration(self):
        """Full integration test with static + LLM."""
        scanner = SkillSecurityScanner()

        with patch.object(scanner, '_llm_scan') as mock_llm:
            mock_llm.return_value = {
                "safe": True,
                "risk_level": "LOW",
                "findings": ["No security concerns"]
            }

            safe_code = "def calculate(x, y): return x + y"
            result = scanner.scan_skill("calculator", safe_code)

            assert result["safe"] == True
            assert result["risk_level"] == "LOW"
            assert len(result["findings"]) > 0


class TestCacheStats:
    """Test cache statistics."""

    def test_get_cache_stats(self):
        """Get cache statistics."""
        scanner = SkillSecurityScanner()

        stats = scanner.get_cache_stats()
        assert "cache_size" in stats
        assert stats["cache_size"] == 0

        # Add item to cache
        scanner._scan_cache["test_key"] = {"safe": True}

        stats = scanner.get_cache_stats()
        assert stats["cache_size"] == 1
