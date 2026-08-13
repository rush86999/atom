# -*- coding: utf-8 -*-
"""Coverage wave 79 — core/skill_security_scanner.py 94% → 100% (gaps left by
tests/test_skill_security.py).

Covers the fail-open no-LLM path (client_available=False → UNKNOWN, cached),
cache-hit behavior across both branches, cache clear/stats, static-scan
short-circuit caching, LLM scan failure → UNKNOWN (fail-open), risk-level
assessment edge phrases, constructor legacy api_key + workspace_id passthrough
to LLMService, and _assess_risk_level full phrase matrix.

Zero LLM spend (LLMService fully mocked), no network.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.skill_security_scanner import SkillSecurityScanner


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def scanner():
    with patch("core.skill_security_scanner.LLMService") as mock_llm:
        s = SkillSecurityScanner(api_key="legacy", workspace_id="ws-77")
        mock_llm.assert_called_once_with(workspace_id="ws-77")
        yield s


# ============================================================================
# No-LLM fail-open path (previously uncovered lines 131-138)
# ============================================================================

class TestNoLLMFailOpen:
    def test_scan_without_llm_returns_unknown(self, scanner):
        scanner.client_available = False
        result = _run(scanner.scan_skill("safe_skill", "print('hello')"))
        assert result["safe"] is True
        assert result["risk_level"] == "UNKNOWN"
        assert "Static scan passed" in result["findings"][0]

    async def test_async_scan_without_llm(self, scanner):
        scanner.client_available = False
        result = await scanner.scan_skill("safe_skill", "print('hi')")
        assert result["risk_level"] == "UNKNOWN"

    def test_no_llm_result_is_cached(self, scanner):
        scanner.client_available = False
        first = _run(scanner.scan_skill("s1", "code-1"))
        with patch.object(scanner, "_static_scan", side_effect=AssertionError("cached")):
            second = _run(scanner.scan_skill("s2", "code-1"))  # same content → cache hit
        assert second == first
        assert scanner.get_cache_stats()["cache_size"] == 1

    def test_client_available_is_true_by_default(self):
        with patch("core.skill_security_scanner.LLMService"):
            assert SkillSecurityScanner().client_available is True

    def test_llm_scan_never_called_when_unavailable(self, scanner):
        scanner.client_available = False
        with patch.object(scanner, "_llm_scan", new=AsyncMock()) as llm:
            _run(scanner.scan_skill("s", "code"))
        llm.assert_not_awaited()


# ============================================================================
# Cache behavior across branches
# ============================================================================

class TestCacheBehavior:
    def test_cache_hit_skips_static_scan(self, scanner):
        with patch.object(scanner, "_static_scan", return_value=[]) as static, \
                patch.object(scanner, "_llm_scan", new=AsyncMock(return_value={
                    "safe": True, "risk_level": "LOW", "findings": []})):
            _run(scanner.scan_skill("a", "content-1"))
            assert static.call_count == 1
            _run(scanner.scan_skill("b", "content-1"))
            assert static.call_count == 1  # cached

    def test_cache_hit_after_static_critical(self, scanner):
        with patch.object(scanner, "_static_scan", return_value=["eval("]):
            r1 = _run(scanner.scan_skill("a", "bad-content"))
            assert r1["risk_level"] == "CRITICAL"
        with patch.object(scanner, "_static_scan", side_effect=AssertionError("cached")):
            r2 = _run(scanner.scan_skill("b", "bad-content"))
        assert r2 == r1

    def test_clear_cache(self, scanner):
        with patch.object(scanner, "_static_scan", return_value=[]), \
                patch.object(scanner, "_llm_scan", new=AsyncMock(return_value={
                    "safe": True, "risk_level": "LOW", "findings": []})):
            _run(scanner.scan_skill("a", "content"))
        assert scanner.get_cache_stats()["cache_size"] == 1
        scanner.clear_cache()
        assert scanner.get_cache_stats()["cache_size"] == 0

    def test_cache_stats_empty(self, scanner):
        assert scanner.get_cache_stats() == {"cache_size": 0}


# ============================================================================
# LLM scan branch + fail-open on LLM errors
# ============================================================================

class TestLLMScanBranch:
    async def test_llm_path_returns_low_safe(self, scanner):
        scanner.llm_service.generate_completion = AsyncMock(
            return_value={"content": "Risk level: low — no concerns."})
        result = await scanner.scan_skill("ok", "print(1)")
        assert result["safe"] is True
        assert result["risk_level"] == "LOW"
        assert result["findings"] == ["Risk level: low — no concerns."]

    async def test_llm_error_fails_open_to_unknown(self, scanner):
        scanner.llm_service.generate_completion = AsyncMock(
            side_effect=RuntimeError("llm down"))
        result = await scanner._llm_scan("x", "code")
        assert result["safe"] is True
        assert result["risk_level"] == "UNKNOWN"
        assert "Scan failed" in result["findings"][0]

    async def test_llm_scan_empty_content_response(self, scanner):
        scanner.llm_service.generate_completion = AsyncMock(return_value={"content": ""})
        result = await scanner._llm_scan("x", "code")
        assert result["risk_level"] == "UNKNOWN"

    def test_scan_skill_with_llm_available(self, scanner):
        with patch.object(scanner, "_llm_scan", new=AsyncMock(return_value={
                "safe": True, "risk_level": "LOW", "findings": []})):
            result = _run(scanner.scan_skill("s", "clean"))
        assert result["risk_level"] == "LOW"


# ============================================================================
# Risk phrase matrix (all branches of _assess_risk_level)
# ============================================================================

class TestRiskPhrases:
    @pytest.mark.parametrize("phrase,expected", [
        ("RISK LEVEL: CRITICAL", "CRITICAL"),
        ("critical risk detected", "CRITICAL"),
        ("this code is malicious", "CRITICAL"),
        ("Risk level: high", "HIGH"),
        ("high risk of exfiltration", "HIGH"),
        ("risk level: medium", "MEDIUM"),
        ("moderate risk observed", "MEDIUM"),
        ("suspicious behavior", "MEDIUM"),
        ("risk level: low", "LOW"),
        ("low risk, no concerns", "LOW"),
        ("no concerns found", "LOW"),
        ("unknown output", "UNKNOWN"),
    ])
    def test_phrase_matrix(self, scanner, phrase, expected):
        assert scanner._assess_risk_level(phrase) == expected

    def test_case_insensitive(self, scanner):
        assert scanner._assess_risk_level("RISK LEVEL: HIGH") == "HIGH"
        assert scanner._assess_risk_level("Risk Level: Low") == "LOW"


# ============================================================================
# Static scan edge (safe code, pattern list sanity)
# ============================================================================

class TestStaticEdge:
    def test_safe_code_no_findings(self, scanner):
        assert scanner._static_scan("def f():\n    return 1 + 2") == []

    def test_malicious_pattern_detected(self, scanner):
        findings = scanner._static_scan("import os\nos.system('id')")
        assert any("os.system" in f for f in findings)

    def test_all_blacklist_patterns(self, scanner):
        for pattern in scanner.MALICIOUS_PATTERNS:
            assert scanner._static_scan(f"x = {pattern}") != []
