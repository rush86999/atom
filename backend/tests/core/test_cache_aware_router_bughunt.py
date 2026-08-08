"""
Bug-hunt tests for CacheAwareRouter (cache-aware request routing).

Targets net-new bugs (absent from HEAD) in:
- cache-key history lifecycle (clear_cache_history)
- analytics accessor aliasing (get_cache_hit_history)

Each test is annotated `BUG: <desc>` and was confirmed RED against HEAD before
the fix was applied.
"""

import pytest

from core.llm.cache_aware_router import CacheAwareRouter


class _StubPricingFetcher:
    """Minimal pricing fetcher stand-in (no DB / network)."""

    def get_model_price(self, model):
        return {
            "input_cost_per_token": 1.0e-6,
            "output_cost_per_token": 2.0e-6,
        }


@pytest.fixture
def router():
    """Fresh CacheAwareRouter with stub pricing fetcher."""
    return CacheAwareRouter(_StubPricingFetcher())


# ---------------------------------------------------------------------------
# BUG 1: clear_cache_history leaks _cache_key_order -> FIFO invariant breaks
# ---------------------------------------------------------------------------

class TestClearCacheHistoryLeaksOrder:
    """BUG: clear_cache_history() clears cache_hit_history but not
    _cache_key_order, leaving stale keys. The FIFO eviction invariant
    (`_cache_key_order` mirrors live history keys) is broken, and the
    `_MAX_CACHE_KEYS` bound is defeated because the order list keeps
    growing across clear cycles."""

    def test_clear_all_empties_order_list(self, router):
        """BUG: clear_cache_history() must also reset _cache_key_order."""
        # Populate several distinct keys.
        for i in range(5):
            router.record_cache_outcome(f"hash_{i}_padding", "ws", was_cached=True)

        assert len(router._cache_key_order) == 5
        assert len(router.cache_hit_history) == 5

        router.clear_cache_history()  # clear ALL

        # History is gone...
        assert router.cache_hit_history == {}
        # ...and the insertion-order tracker MUST be gone too, otherwise
        # subsequent record_cache_outcome evictions operate on stale keys.
        assert router._cache_key_order == [], (
            "clear_cache_history leaked stale keys into _cache_key_order"
        )

    def test_clear_workspace_empties_only_that_workspaces_order_entries(self, router):
        """BUG: workspace-scoped clear must drop those keys from
        _cache_key_order as well, not just from cache_hit_history."""
        router.record_cache_outcome("alpha_padding_xx", "wsA", was_cached=True)
        router.record_cache_outcome("beta_padding_xxx", "wsB", was_cached=True)

        router.clear_cache_history(workspace_id="wsA")

        # wsA key removed from history...
        assert all(
            not k.startswith("wsA:") for k in router.cache_hit_history
        )
        # ...and from the order tracker.
        assert all(
            not k.startswith("wsA:") for k in router._cache_key_order
        ), "workspace-scoped clear left stale keys in _cache_key_order"
        # wsB untouched.
        assert any(k.startswith("wsB:") for k in router.cache_hit_history)

    def test_order_list_does_not_grow_unbounded_across_clear_cycles(self, router):
        """BUG: without clearing _cache_key_order, each clear+record cycle
        leaves the order list larger than the number of LIVE keys, so the
        `_MAX_CACHE_KEYS` ceiling no longer bounds live memory."""
        cap = router._MAX_CACHE_KEYS
        # Fill to the cap, clear, repeat several times.
        for cycle in range(4):
            for i in range(cap):
                router.record_cache_outcome(f"cycle{cycle}_key{i}_pad", "ws", True)
            router.clear_cache_history()

        # After clearing, NO live keys should remain.
        assert router.cache_hit_history == {}
        # The order list must NOT retain thousands of stale entries.
        assert len(router._cache_key_order) == 0, (
            f"_cache_key_order grew to {len(router._cache_key_order)} "
            f"despite empty history (memory leak / broken FIFO bound)"
        )


# ---------------------------------------------------------------------------
# BUG 2: get_cache_hit_history returns shared inner list references
# ---------------------------------------------------------------------------

class TestGetCacheHitHistoryAliasing:
    """BUG: get_cache_hit_history() returns the actual [hits, total] list
    objects from the internal dict (shallow copy only). A caller mutating a
    returned list corrupts the router's internal state, and subsequent
    predict_cache_hit_probability() reads the corrupted counts."""

    def test_caller_cannot_mutate_internal_state_via_returned_list(self, router):
        """BUG: mutating a returned history list must not affect the router."""
        router.record_cache_outcome("seed_padding_xxxx", "ws", was_cached=True)
        router.record_cache_outcome("seed_padding_xxxx", "ws", was_cached=False)

        snapshot_before = {k: list(v) for k, v in router.cache_hit_history.items()}

        hist = router.get_cache_hit_history("ws")
        key = next(iter(hist))
        # Caller maliciously / accidentally rewrites the counts.
        hist[key][0] = 99999
        hist[key][1] = 1

        # Internal state must be unchanged.
        assert dict(router.cache_hit_history) == snapshot_before, (
            "get_cache_hit_history leaked mutable references into internal state"
        )

    def test_predict_unaffected_by_caller_mutation(self, router):
        """BUG: predict_cache_hit_probability must reflect recorded outcomes,
        not whatever a prior analytics caller wrote into the returned list."""
        router.record_cache_outcome("pred_padding_xxx", "ws", was_cached=True)
        router.record_cache_outcome("pred_padding_xxx", "ws", was_cached=True)
        # 2/2 = 1.0 hit rate expected.
        expected = 1.0

        # Analytics consumer grabs history and trashes it.
        hist = router.get_cache_hit_history()
        for v in hist.values():
            v[0] = 0
            v[1] = 9999

        prob = router.predict_cache_hit_probability("pred_padding_xxx", "ws")
        assert prob == expected, (
            f"predict returned {prob} after caller mutated analytics view; "
            f"expected {expected} (aliasing bug)"
        )

    def test_full_history_view_also_defensive(self, router):
        """BUG: the no-arg path (`.copy()`) must also not share list refs."""
        router.record_cache_outcome("full_padding_xxxx", "ws", was_cached=True)

        hist_all = router.get_cache_hit_history()  # no workspace filter
        key = next(iter(hist_all))
        original = list(router.cache_hit_history[key])
        hist_all[key][0] = -5

        assert router.cache_hit_history[key] == original
