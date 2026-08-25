"""R83 evidence-based default flags.

Locks the default-ON / default-OFF decisions (docs/agents/R83_RELIABILITY_PLAN.md
"Default posture" table) so nobody flips a default without touching this file
and its rationale.

Default ON (practical + evidence-based):
- ATOM_SC_USC_FALLBACK — peer-reviewed (ICML 2024), fires only on otherwise-
  wasted all-distinct votes, any judge failure degrades to exact old behavior.
- ATOM_SC_FANOUT — zero added LLM cost, schema-normalized samples stay
  comparable, silent degradation everywhere.
- ATOM_SC_SOFT — shadow-only (hard winner always followed); defaulting ON is
  pure observability that collects the promotion-gate data. Safe because a
  logprobs-rejecting gateway gets one retry without logprobs.

Default OFF (evidence against / precondition unmet):
- ATOM_DATAMARKING — touches every untrusted prompt; promotion precondition
  (shadow task-success A/B canary) not yet built.

(R83 #4 fusion arms were REMOVED 2026-08-24 after the hard-suite experiment
showed them inert by construction — legs LIMIT 5+5 vs a 15-entity context
window; see R83_RELIABILITY_PLAN.md #4.)
"""
import pytest


@pytest.fixture(autouse=True)
def _clean_r83_env(monkeypatch):
    for var in (
        "ATOM_SC_USC_FALLBACK", "ATOM_SC_FANOUT", "ATOM_SC_SOFT",
        "ATOM_RETRIEVAL_FUSION", "ATOM_DATAMARKING",
    ):
        monkeypatch.delenv(var, raising=False)


class TestDefaultsOn:
    def test_usc_fallback_default_on(self):
        from core.hallucination_config import is_usc_fallback_enabled
        assert is_usc_fallback_enabled() is True

    def test_fanout_default_on(self):
        from core.hallucination_config import is_sc_fanout_enabled
        assert is_sc_fanout_enabled() is True

    def test_soft_sc_default_on(self):
        from core.hallucination_config import is_sc_soft_enabled
        assert is_sc_soft_enabled() is True

    def test_kill_switches_still_work(self, monkeypatch):
        import core.hallucination_config as hc
        monkeypatch.setenv("ATOM_SC_USC_FALLBACK", "false")
        monkeypatch.setenv("ATOM_SC_FANOUT", "0")
        monkeypatch.setenv("ATOM_SC_SOFT", "off")
        assert hc.is_usc_fallback_enabled() is False
        assert hc.is_sc_fanout_enabled() is False
        assert hc.is_sc_soft_enabled() is False


class TestDefaultsOff:
    def test_datamarking_default_off(self):
        from core.prompt_datamarking import get_datamarking_mode
        assert get_datamarking_mode() == "off"

    def test_fusion_arms_removed(self):
        """R83 #4 closure: the inert fusion arms must stay deleted."""
        import importlib

        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("core.hybrid_search.leg_fusion")


class TestSoftSCGatewayRejection:
    def test_logprobs_rejection_retries_without_logprobs(self, monkeypatch):
        """A gateway rejecting the logprobs kwarg must not fail the call —
        one retry without logprobs, sample comes back unstamped."""
        from types import SimpleNamespace as NS
        from tests.test_covpush_byok_gen import make_handler, patch_session, pro_tenant_db

        calls = []

        class _FakeInstructorClient:
            def __init__(self, client):
                pass

            class chat:
                class completions:
                    @staticmethod
                    def create(**kwargs):
                        calls.append(dict(kwargs))
                        if kwargs.get("logprobs"):
                            raise TypeError("unexpected keyword 'logprobs'")
                        return NS(plan="ok")

        import core.llm.byok_handler as mod

        monkeypatch.setattr(mod.instructor, "from_openai", lambda c: _FakeInstructorClient(c))
        handler = make_handler()
        handler.clients = {"p1": object()}
        handler.get_ranked_providers = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            return_value=[("p1", "m1")]
        )

        from unittest.mock import AsyncMock

        monkeypatch.setenv("ATOM_SC_SOFT", "true")
        with patch_session(pro_tenant_db()):
            result = __import__("asyncio").run(handler.generate_structured_response(
                prompt="p", system_instruction="s", response_model=dict,
            ))
        assert result.plan == "ok"
        assert len(calls) == 2
        assert calls[0]["logprobs"] is True
        assert "logprobs" not in calls[1]
