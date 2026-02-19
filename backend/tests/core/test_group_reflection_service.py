"""
Unit tests for GroupReflectionService — domain-agnostic GEA Reflection Module.

Covers:
  - DomainProfileRegistry resolution (all built-ins, fallback, aliases)
  - Domain-adaptive quality gate (quality_weight per domain)
  - Domain-specific log signal extraction per profile
  - LLM prompt structure per domain
  - gather_group_experience_pool() with domain auto-detection
  - reflect_and_generate_directives() per domain
  - Runtime domain registration
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from core.group_reflection_service import (
    GroupReflectionService,
    DomainProfile,
    DomainProfileRegistry,
    DOMAIN_PROFILES,
    MIN_QUALITY_SCORE,
    _extract_traceback,
    _extract_email_signal,
    _extract_conflict_signal,
    _extract_financial_signal,
    _extract_support_signal,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def make_trace(
    benchmark_score=0.7,
    benchmark_passed=True,
    is_high_quality=True,
    model_patch="+ some fix",
    task_log="some log",
    tool_use_log=None,
    evolving_requirements="Add retry logic",
):
    t = MagicMock()
    t.benchmark_score = benchmark_score
    t.benchmark_passed = benchmark_passed
    t.is_high_quality = is_high_quality
    t.model_patch = model_patch
    t.task_log = task_log
    t.tool_use_log = tool_use_log or [{"tool_name": "bash", "success": True}]
    t.evolving_requirements = evolving_requirements
    return t


def make_db(traces):
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.order_by.return_value = q
    q.limit.return_value = q
    q.all.return_value = traces
    q.first.return_value = None
    db.query.return_value = q
    return db


# ─── DomainProfileRegistry ────────────────────────────────────────────────────

class TestDomainProfileRegistry:
    def test_resolves_engineering_profile(self):
        p = DomainProfileRegistry.resolve("engineering")
        assert "Software" in p.name

    def test_resolves_crm_profile(self):
        p = DomainProfileRegistry.resolve("crm")
        assert "CRM" in p.name or "Sales" in p.name

    def test_resolves_finance_profile(self):
        p = DomainProfileRegistry.resolve("finance")
        assert "Financial" in p.name or "Finance" in p.name

    def test_resolves_scheduling_profile(self):
        p = DomainProfileRegistry.resolve("scheduling")
        assert "Schedule" in p.name or "Calendar" in p.name

    def test_resolves_support_profile(self):
        p = DomainProfileRegistry.resolve("support")
        assert "Support" in p.name

    def test_resolves_alias_coding(self):
        p = DomainProfileRegistry.resolve("coding")
        assert p is DOMAIN_PROFILES["engineering"]

    def test_resolves_alias_calendar(self):
        p = DomainProfileRegistry.resolve("calendar")
        assert p is DOMAIN_PROFILES["scheduling"]

    def test_resolves_alias_financial(self):
        p = DomainProfileRegistry.resolve("financial")
        assert p is DOMAIN_PROFILES["finance"]

    def test_unknown_category_returns_generic(self):
        p = DomainProfileRegistry.resolve("alien_category_xyz")
        assert "General" in p.name

    def test_none_category_returns_generic(self):
        p = DomainProfileRegistry.resolve(None)
        assert "General" in p.name

    def test_case_insensitive_resolution(self):
        p = DomainProfileRegistry.resolve("CRM")
        assert p.name == DomainProfileRegistry.resolve("crm").name

    def test_space_normalized_resolution(self):
        p = DomainProfileRegistry.resolve("customer support")
        assert p.name == DomainProfileRegistry.resolve("customer_support").name

    def test_list_domains_returns_all(self):
        domains = DomainProfileRegistry.list_domains()
        assert "engineering" in domains
        assert "crm" in domains
        assert "finance" in domains


# ─── Quality Gate (domain-adjusted) ───────────────────────────────────────────

class TestDomainAdaptedQualityGate:
    def test_strict_domain_blocks_borderline_trace(self):
        """Marketing quality_weight=1.3 → effective threshold = 0.3 * 1.3 = 0.39"""
        trace = make_trace(benchmark_score=0.35, is_high_quality=True)
        db = make_db([trace])
        svc = GroupReflectionService(db)
        pool = svc.gather_group_experience_pool(["a1"], category="marketing")
        # Score 0.35 < 0.39 → filtered out
        assert pool["trace_count"] == 0
        assert pool["filtered_count"] == 1

    def test_permissive_domain_passes_borderline_trace(self):
        """Engineering quality_weight=0.8 → effective threshold = 0.3 * 0.8 = 0.24"""
        trace = make_trace(benchmark_score=0.28, is_high_quality=True)
        db = make_db([trace])
        svc = GroupReflectionService(db)
        pool = svc.gather_group_experience_pool(["a1"], category="engineering")
        # Score 0.28 > 0.24 → passes
        assert pool["trace_count"] == 1
        assert pool["filtered_count"] == 0

    def test_low_quality_flag_always_blocks(self):
        """is_high_quality=False always blocks regardless of domain or score."""
        trace = make_trace(benchmark_score=0.99, is_high_quality=False)
        db = make_db([trace])
        svc = GroupReflectionService(db)
        pool = svc.gather_group_experience_pool(["a1"], category="finance")
        assert pool["trace_count"] == 0


# ─── Domain-specific log signal extraction ────────────────────────────────────

class TestSignalExtraction:
    def test_engineering_finds_traceback(self):
        log = "Starting...\nTraceback (most recent call last):\n  File x.py\nValueError: bad"
        result = _extract_traceback(log)
        assert result and "Traceback" in result

    def test_engineering_falls_back_to_error_lines(self):
        log = "step 1 ok\nerror: division by zero\nstep 3"
        result = _extract_traceback(log)
        assert result and "error" in result.lower()

    def test_crm_finds_bounce(self):
        log = "send ok\nbounce received from user@domain.com\nretrying..."
        result = _extract_email_signal(log)
        assert result and "bounce" in result.lower()

    def test_crm_finds_converted(self):
        log = "prospecting\ndeal converted to closed-won\nstage updated"
        result = _extract_email_signal(log)
        assert result and "converted" in result.lower()

    def test_scheduling_finds_conflict(self):
        log = "booking slot\nconflict detected: slot already taken\nretrying"
        result = _extract_conflict_signal(log)
        assert result and "conflict" in result.lower()

    def test_finance_finds_mismatch(self):
        log = "reconciling ledger\nmismatch: $0.03 off\nescalating"
        result = _extract_financial_signal(log)
        assert result and "mismatch" in result.lower()

    def test_support_finds_escalation(self):
        log = "processing ticket\nescalating to tier-2\nticket updated"
        result = _extract_support_signal(log)
        assert result and "escalat" in result.lower()

    def test_signal_returns_none_for_very_short_log(self):
        """Logs under ~80 chars with no keyword should return None, not garbage."""
        result = _extract_traceback("ok")
        assert result is None


# ─── LLM Prompt Domain Injection ──────────────────────────────────────────────

class TestReflectionPromptContent:
    def test_crm_prompt_contains_domain_vocabulary(self):
        db = make_db([])
        svc = GroupReflectionService(db)
        profile = DomainProfileRegistry.resolve("crm")
        pool = {
            "agent_count": 3, "trace_count": 2,
            "tool_patterns": [{"tool_name": "send_email", "success": True}],
            "task_log_excerpts": ["bounce received"],
            "successful_patches": ["change follow-up cadence"],
            "evolving_requirements": ["Reduce follow-up to 3 days"],
            "_domain_profile": profile, "_category": "crm",
        }
        prompt = svc._build_reflection_prompt(pool, profile, max_directives=3)
        assert "CRM" in prompt or "Sales" in prompt
        assert "bounce" in prompt
        assert "email template" in prompt.lower() or "outreach" in prompt.lower()

    def test_finance_prompt_contains_domain_vocabulary(self):
        db = make_db([])
        svc = GroupReflectionService(db)
        profile = DomainProfileRegistry.resolve("finance")
        pool = {
            "agent_count": 2, "trace_count": 1,
            "tool_patterns": [{"tool_name": "reconcile", "success": False}],
            "task_log_excerpts": ["mismatch: $0.02 off"],
            "successful_patches": [],
            "evolving_requirements": [],
            "_domain_profile": profile, "_category": "finance",
        }
        prompt = svc._build_reflection_prompt(pool, profile, max_directives=3)
        assert "Financial" in prompt or "finance" in prompt.lower()
        assert "reconciliation" in prompt.lower() or "mismatch" in prompt.lower()

    def test_tool_vocab_star_marking(self):
        """Domain tools should get a ★ marker in the summary."""
        db = make_db([])
        svc = GroupReflectionService(db)
        profile = DomainProfileRegistry.resolve("crm")  # tool_vocab includes "hubspot"
        patterns = [
            {"tool_name": "hubspot", "success": True},
            {"tool_name": "unknown_tool", "success": True},
        ]
        summary = svc._summarize_tool_patterns(patterns, profile)
        assert "hubspot ★" in summary or "hubspot★" in summary.replace(" ★", "★")
        assert "★" not in summary.replace("hubspot ★", "")  # other tools no star


# ─── End-to-end reflect_and_generate_directives ───────────────────────────────

class TestReflectGenerateDirectivesDomainAware:
    @pytest.mark.asyncio
    async def test_system_prompt_references_domain_name(self):
        """LLM should receive a system prompt mentioning the domain."""
        db = make_db([])
        svc = GroupReflectionService(db)
        svc.llm = MagicMock()

        captured_system_prompt = {}

        async def fake_generate(**kwargs):
            captured_system_prompt["value"] = kwargs.get("system_prompt", "")
            return "1. Increase personalization\n2. Reduce cadence"

        svc.llm.generate = fake_generate

        pool = {
            "agent_count": 2, "trace_count": 2,
            "tool_patterns": [], "task_log_excerpts": [],
            "successful_patches": [], "evolving_requirements": [],
            "_domain_profile": DomainProfileRegistry.resolve("crm"),
            "_category": "crm",
        }
        directives = await svc.reflect_and_generate_directives(pool, category="crm")
        assert "CRM" in captured_system_prompt["value"] or "Sales" in captured_system_prompt["value"]
        assert len(directives) == 2

    @pytest.mark.asyncio
    async def test_empty_pool_fallback_mentions_domain_success(self):
        """Empty pool falls back to a bootstrap directive using the domain's success label."""
        db = make_db([])
        svc = GroupReflectionService(db)
        pool = {
            "agent_count": 0, "trace_count": 0,
            "tool_patterns": [], "task_log_excerpts": [],
            "successful_patches": [], "evolving_requirements": [],
            "_domain_profile": DomainProfileRegistry.resolve("scheduling"),
            "_category": "scheduling",
        }
        directives = await svc.reflect_and_generate_directives(pool, category="scheduling")
        assert len(directives) == 1
        # Bootstrap message should reference the domain's success concept
        assert any(
            kw in directives[0].lower()
            for kw in ["booking", "conflict", "schedule", "meeting", "slot", "refining"]
        )

    @pytest.mark.asyncio
    async def test_llm_failure_fallback_mentions_domain_failure(self):
        """LLM error returns a fallback directive using the domain's failure label."""
        db = make_db([])
        svc = GroupReflectionService(db)
        svc.llm = MagicMock()
        svc.llm.generate = AsyncMock(side_effect=RuntimeError("timeout"))

        pool = {
            "agent_count": 3, "trace_count": 2,
            "tool_patterns": [], "task_log_excerpts": [],
            "successful_patches": [], "evolving_requirements": [],
            "_domain_profile": DomainProfileRegistry.resolve("finance"),
            "_category": "finance",
        }
        directives = await svc.reflect_and_generate_directives(pool, category="finance")
        assert len(directives) == 1
        assert any(
            kw in directives[0].lower()
            for kw in ["reconciliation", "mismatch", "rounding", "current behavior"]
        )


# ─── Runtime domain registration ─────────────────────────────────────────────

class TestRuntimeDomainRegistration:
    def test_can_register_and_resolve_custom_domain(self):
        GroupReflectionService.register_domain("legal", DomainProfile(
            name="Legal Document Review",
            success_label="clause correctly extracted",
            failure_label="missed clause or false positive",
            patch_label="extraction rule change",
            prompt_preamble="These agents review legal contracts.",
            quality_weight=1.5,
        ))
        profile = DomainProfileRegistry.resolve("legal")
        assert profile.name == "Legal Document Review"
        assert profile.quality_weight == 1.5

    def test_custom_domain_quality_gate_is_strict(self):
        """Legal quality_weight=1.5 → threshold=0.45, so 0.4 score is filtered."""
        GroupReflectionService.register_domain("legal2", DomainProfile(
            name="Legal v2",
            success_label="clause extracted",
            failure_label="missed clause",
            patch_label="rule change",
            prompt_preamble="Legal agents.",
            quality_weight=1.5,
        ))
        trace = make_trace(benchmark_score=0.40, is_high_quality=True)
        db = make_db([trace])
        svc = GroupReflectionService(db)
        pool = svc.gather_group_experience_pool(["a1"], category="legal2")
        assert pool["trace_count"] == 0  # 0.40 < 0.45 → filtered
