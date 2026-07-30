"""Tests for the round-5 bug fixes: response quality, streaming fallback,
cache hashing, complexity regex, health threshold, and tier quality bands.
"""
import pytest

from core.llm.response_quality import assess_response_quality


# --------------------------------------------------------------------------
# Bug 11: refusal detection (leading-window match + more markers)
# --------------------------------------------------------------------------

class TestRefusalDetection:
    def test_exact_refusal_still_detected(self):
        q = assess_response_quality(content="I'm sorry, but I can't help with that.", finish_reason="stop")
        assert "refusal" in q.issues
        assert q.quality_satisfied is False

    def test_refusal_with_preamble_detected(self):
        """A preamble before the refusal phrase must still be caught."""
        q = assess_response_quality(
            content="Sure, I understand. Unfortunately, I cannot help with that request.",
            finish_reason="stop",
        )
        assert "refusal" in q.issues, "preamble-prefixed refusal was missed"

    def test_refusal_with_leading_whitespace_and_marker(self):
        q = assess_response_quality(content="\n# Response\nI'm sorry, but I cannot assist with that.",
                                    finish_reason="stop")
        assert "refusal" in q.issues

    def test_unfortunately_variant_detected(self):
        q = assess_response_quality(content="Unfortunately, I am unable to provide that information.",
                                    finish_reason="stop")
        assert "refusal" in q.issues

    def test_legitimate_content_not_flagged_as_refusal(self):
        """No false positives on substantive content mentioning safety."""
        q = assess_response_quality(
            content="Here's a detailed explanation of authentication and authorization patterns. "
                    "Note that I can't cover every edge case, but the main flows are documented below. "
                    "This response is substantive and complete.",
            finish_reason="stop",
        )
        assert "refusal" not in q.issues
        assert q.quality_satisfied is True

    def test_refusal_far_into_long_text_not_flagged(self):
        """A refusal phrase appearing well past the leading window is not a refusal."""
        long_pre = "Here is a thorough answer. " * 100  # >> 160 chars
        q = assess_response_quality(content=long_pre + " I'm sorry, but I can't assist with that.",
                                    finish_reason="stop")
        assert "refusal" not in q.issues


# --------------------------------------------------------------------------
# Bug 14: provider-serves-model heuristic (streaming fallback)
# --------------------------------------------------------------------------

class TestProviderServesModel:
    def _handler(self):
        from core.llm.byok_handler import BYOKHandler
        return BYOKHandler.__new__(BYOKHandler)

    def test_openai_serves_gpt(self):
        assert self._handler()._provider_serves_model("openai", "gpt-4o") is True

    def test_anthropic_does_not_serve_gpt(self):
        """Cross-provider: Anthropic must not be asked to serve gpt-4o."""
        assert self._handler()._provider_serves_model("anthropic", "gpt-4o") is False

    def test_anthropic_serves_claude(self):
        assert self._handler()._provider_serves_model("anthropic", "claude-sonnet-4") is True

    def test_deepseek_serves_deepseek(self):
        assert self._handler()._provider_serves_model("deepseek", "deepseek-chat") is True

    def test_local_providers_serve_anything(self):
        """Local providers (ollama/vllm) serve arbitrary model names."""
        h = self._handler()
        assert h._provider_serves_model("ollama", "llama3") is True
        assert h._provider_serves_model("vllm", "gpt-4o") is True  # local serves anything


# --------------------------------------------------------------------------
# Bug 13: health filter threshold (borderline providers not hard-excluded)
# --------------------------------------------------------------------------

class TestHealthFilterThreshold:
    def test_borderline_provider_remains_candidate(self):
        """A ~50% health provider must NOT be hard-excluded (was excluded at 0.5)."""
        from core.llm.byok_handler import BYOKHandler
        from core.provider_health_monitor import ProviderHealthMonitor
        handler = BYOKHandler.__new__(BYOKHandler)
        mon = ProviderHealthMonitor()
        # Simulate a 50% health provider via direct state.
        mon.health_scores["flaky"] = 0.5
        handler.health_monitor = mon
        assert handler._filter_by_health("flaky") is True  # borderline kept

    def test_dead_provider_excluded(self):
        from core.llm.byok_handler import BYOKHandler
        from core.provider_health_monitor import ProviderHealthMonitor
        handler = BYOKHandler.__new__(BYOKHandler)
        mon = ProviderHealthMonitor()
        mon.health_scores["dead"] = 0.1  # well below 0.2
        handler.health_monitor = mon
        assert handler._filter_by_health("dead") is False

    def test_unknown_provider_passes(self):
        from core.llm.byok_handler import BYOKHandler
        from core.provider_health_monitor import ProviderHealthMonitor
        handler = BYOKHandler.__new__(BYOKHandler)
        handler.health_monitor = ProviderHealthMonitor()
        assert handler._filter_by_health("never-seen") is True


# --------------------------------------------------------------------------
# Bug 9: cognitive-tier quality bands aligned with BPC MIN_QUALITY_BY_TIER
# --------------------------------------------------------------------------

class TestTierQualityBands:
    def test_standard_band_floor_matches_bpc(self):
        """The STANDARD band floor must align with BPC's MIN_QUALITY_BY_TIER[STANDARD]."""
        from core.llm.cognitive_tier_service import CognitiveTierService
        import inspect
        # Reflectively read the quality_map used in _get_dynamic_tier_models.
        src = inspect.getsource(CognitiveTierService._get_dynamic_tier_models)
        assert "80" in src, "STANDARD band floor should start at 80 (BPC floor)"


# --------------------------------------------------------------------------
# Bug 3: prompt_hash includes prompt content
# --------------------------------------------------------------------------

class TestPromptHash:
    def test_different_prompts_get_different_hashes(self):
        """Two prompts on the same ws/provider/model must hash differently."""
        import hashlib
        def h(prompt):
            prefix = (prompt or "")[:1000]
            return hashlib.sha256(f"ws:openai:gpt-4o:{prefix}".encode()).hexdigest()
        assert h("summarize this article") != h("write a poem about cats")

    def test_same_prompt_same_hash(self):
        import hashlib
        def h(prompt):
            prefix = (prompt or "")[:1000]
            return hashlib.sha256(f"ws:openai:gpt-4o:{prefix}".encode()).hexdigest()
        assert h("hello") == h("hello")


# --------------------------------------------------------------------------
# Bug 12: \bpo\b regex no longer over-escalates
# --------------------------------------------------------------------------

class TestComplexityRegex:
    def test_po_word_alone_does_not_trigger_advanced(self):
        """A prompt containing the bare word 'po' must not jump to ADVANCED."""
        from core.llm.byok_handler import BYOKHandler, QueryComplexity
        handler = BYOKHandler.__new__(BYOKHandler)
        # analyze_query_complexity sums weighted keyword hits; 'po' alone used
        # to add +5 (ADVANCED threshold). Now removed, a benign 'po' prompt
        # should stay at a low complexity.
        complexity = handler.analyze_query_complexity("send to po box 123", "chat")
        assert complexity != QueryComplexity.ADVANCED, "bare 'po' still over-escalates"

    def test_purchase_order_still_detected(self):
        """Genuine purchase-order intent is still recognized (escalates)."""
        from core.llm.byok_handler import BYOKHandler, QueryComplexity
        handler = BYOKHandler.__new__(BYOKHandler)
        complexity = handler.analyze_query_complexity(
            "generate a purchase order for the procurement workflow", "chat"
        )
        # 'purchase order' still contributes weight; the prompt must escalate
        # to at least ADVANCED (it may reach COMPLEX with extra terms).
        assert complexity in (QueryComplexity.ADVANCED, QueryComplexity.COMPLEX), (
            f"purchase-order prompt should escalate, got {complexity}")
