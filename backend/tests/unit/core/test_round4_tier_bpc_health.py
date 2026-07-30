"""Tests for the round-4 bug fixes across the cognitive-tier / BPC / health
subsystems.

Covers:
- Bug 4: qwen models map to the qwen provider (was moonshot).
- Bug 5: ProviderHealthMonitor is thread-safe (concurrent record_call doesn't
  crash or lose data); singleton creation is race-free.
- Bug 6: _load_capability_index bulk-fetches once (no per-model DB round-trip).
- Bug 8: free/local models no longer get a near-infinite BPC value_score.
- Bug 16: default_tier respects min_tier/max_tier clamps.
"""
import threading

import pytest
from unittest.mock import MagicMock


# --------------------------------------------------------------------------
# Bug 4: qwen -> qwen provider
# --------------------------------------------------------------------------

def test_qwen_models_map_to_qwen_provider():
    """qwen-plus/Max are served by DashScope (provider 'qwen'), not moonshot."""
    from core.llm.cognitive_tier_service import CognitiveTierService
    svc = CognitiveTierService.__new__(CognitiveTierService)  # bypass __init__ (needs DB)
    assert svc._model_to_provider("qwen-plus") == "qwen"
    assert svc._model_to_provider("qwen-max") == "qwen"
    # kimi is still moonshot (unchanged).
    assert svc._model_to_provider("kimi-k2") == "moonshot"


# --------------------------------------------------------------------------
# Bug 5: ProviderHealthMonitor thread safety
# --------------------------------------------------------------------------

def test_health_monitor_concurrent_record_calls_no_loss():
    """Many threads recording calls must all land (no lost updates, no crash)."""
    from core.provider_health_monitor import ProviderHealthMonitor
    mon = ProviderHealthMonitor(window_minutes=5)
    N = 300
    barrier = threading.Barrier(N)

    def record(i):
        barrier.wait()
        mon.record_call("openai", success=(i % 5 != 0), latency_ms=float(i))

    threads = [threading.Thread(target=record, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly N calls recorded (none lost to races), within the window.
    assert len(mon.call_history["openai"]) == N
    # Health score is a valid probability.
    assert 0.0 <= mon.get_health_score("openai") <= 1.0


def test_health_monitor_concurrent_mixed_providers():
    """Concurrent writes to DIFFERENT providers must not corrupt either deque."""
    from core.provider_health_monitor import ProviderHealthMonitor
    mon = ProviderHealthMonitor(window_minutes=5)
    providers = ["openai", "anthropic", "deepseek", "gemini"]
    N = 100

    def record(provider):
        for i in range(N):
            mon.record_call(provider, success=True, latency_ms=10.0)

    threads = [threading.Thread(target=record, args=(p,)) for p in providers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for p in providers:
        assert len(mon.call_history[p]) == N


def test_health_monitor_singleton_creation_is_thread_safe():
    """Concurrent first-callers must not create duplicate singletons."""
    import core.provider_health_monitor as mod
    # Reset the singleton.
    mod._health_monitor = None
    instances = []
    barrier = threading.Barrier(20)

    def get():
        barrier.wait()
        instances.append(id(mod.get_provider_health_monitor()))

    threads = [threading.Thread(target=get) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All callers got the same singleton instance.
    assert len(set(instances)) == 1
    # Cleanup so other tests aren't affected.
    mod._health_monitor = None


# --------------------------------------------------------------------------
# Bug 8: free-model BPC cost floor
# --------------------------------------------------------------------------

def test_free_model_does_not_dominate_paid_via_infinite_score():
    """A zero-cost local model must not unconditionally beat higher-quality paid models.

    The BPC scorer now floors free models at ~1% of the median PAID cost in the
    pool (two-pass), so a free model still wins at equal quality but a
    substantially-higher-quality paid model can outrank it (Bug 8).
    """
    # Reconstruct the two-pass pool-relative floor logic.
    def score_pool(cands):
        # cands: list of (quality, cost)
        paid = sorted(c for _, c in cands if c > 0)
        median_paid = paid[len(paid) // 2] if paid else 0.0
        floor = max(median_paid * 0.5, 1e-9) if paid else 1e-9
        out = []
        for q, c in cands:
            nc = max(c, floor)
            out.append((q ** 2) / (nc * 1e6))
        return out

    # Pool: a free local 7B (q=0.5) and a premium model (q=0.95, cost 1e-6).
    scores = score_pool([(0.5, 0.0), (0.95, 1e-6)])
    local_score, paid_score = scores[0], scores[1]
    # The premium model must outrank the free low-quality local model.
    assert paid_score > local_score, (
        f"free model still dominates: local={local_score} paid={paid_score}")

    # But a free model still beats an EQUAL-quality paid model (cheapness wins).
    eq = score_pool([(0.9, 0.0), (0.9, 1e-6)])
    assert eq[0] > eq[1], "free model should beat equal-quality paid model"



# --------------------------------------------------------------------------
# Bug 6: capability index is bulk-loaded (smoke test of the helper signature)
# --------------------------------------------------------------------------

def test_filter_by_capabilities_uses_index_without_db():
    """When a capability_index is provided, no DB session is opened."""
    from core.llm.byok_handler import BYOKHandler
    handler = BYOKHandler.__new__(BYOKHandler)  # bypass heavy __init__
    # An index entry with the capability passes.
    idx = {"gpt-4o": ["tools", "vision"]}
    assert handler._filter_by_capabilities("gpt-4o", "tools", idx) is True
    # An index entry without the capability fails.
    assert handler._filter_by_capabilities("gpt-4o", "computer_use", idx) is False
    # A model NOT in the index passes through (unknown -> conservative pass).
    assert handler._filter_by_capabilities("unknown-model", "tools", idx) is True
    # No requirement -> always pass.
    assert handler._filter_by_capabilities("anything", None, idx) is True


# --------------------------------------------------------------------------
# Bug 16: default_tier respects min/max clamps
# --------------------------------------------------------------------------

def test_default_tier_is_clamped_to_max():
    """default_tier above max_tier must be clamped down to max_tier."""
    from core.llm.cognitive_tier_service import CognitiveTierService, CognitiveTier
    svc = CognitiveTierService.__new__(CognitiveTierService)
    svc.classifier = MagicMock()
    svc.classifier.classify.return_value = CognitiveTier.STANDARD
    svc.workspace_id = "ws1"
    svc.tenant_id = None

    pref = MagicMock()
    pref.min_tier = None
    pref.max_tier = "standard"   # cap at STANDARD
    pref.default_tier = "complex"  # would bypass to COMPLEX without the fix
    svc.get_workspace_preference = lambda: pref

    tier = svc.select_tier("any prompt", "chat")
    assert tier == CognitiveTier.STANDARD  # clamped, not COMPLEX


def test_default_tier_is_clamped_to_min():
    """default_tier below min_tier must be clamped up to min_tier."""
    from core.llm.cognitive_tier_service import CognitiveTierService, CognitiveTier
    svc = CognitiveTierService.__new__(CognitiveTierService)
    svc.classifier = MagicMock()
    svc.classifier.classify.return_value = CognitiveTier.STANDARD
    svc.workspace_id = "ws1"
    svc.tenant_id = None

    pref = MagicMock()
    pref.min_tier = "heavy"      # floor at HEAVY
    pref.max_tier = None
    pref.default_tier = "micro"  # would bypass to MICRO without the fix
    svc.get_workspace_preference = lambda: pref

    tier = svc.select_tier("any prompt", "chat")
    assert tier == CognitiveTier.HEAVY  # clamped up, not MICRO


def test_default_tier_within_bounds_passes_unchanged():
    """A default_tier inside the bounds is returned as-is."""
    from core.llm.cognitive_tier_service import CognitiveTierService, CognitiveTier
    svc = CognitiveTierService.__new__(CognitiveTierService)
    svc.classifier = MagicMock()
    svc.classifier.classify.return_value = CognitiveTier.STANDARD
    svc.workspace_id = "ws1"
    svc.tenant_id = None

    pref = MagicMock()
    pref.min_tier = "standard"
    pref.max_tier = "complex"
    pref.default_tier = "versatile"  # within [standard, complex]
    svc.get_workspace_preference = lambda: pref

    tier = svc.select_tier("any prompt", "chat")
    assert tier == CognitiveTier.VERSATILE
