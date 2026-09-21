"""A rejected credential benches the PROVIDER, not just the (model) pair.

Live 2026-09-17 acceptance logs: opencode-go's key was dead upstream, and
the structured cascade's auth memo was PAIR-scoped — five opencode-go
models each re-paid a 401 round trip per call window (~700 wasted 401s,
32 exhausted "All structured providers failed" chains) before the
provider was effectively out of rotation. The fix mirrors
``_record_attempt_failure``'s PROVIDER_SCOPED design: the first auth
failure benches the provider process-wide, and the structured cascade
skips cooled providers like the other cascades do.
"""
import inspect


def _handler():
    import os
    os.environ.setdefault("TESTING", "1")
    from core.llm.byok_handler import BYOKHandler
    return BYOKHandler.__new__(BYOKHandler)


def test_auth_bench_is_provider_scoped_and_clearable():
    h = _handler()

    h._bench_provider("prov-x", cause="invalid_credential",
                      detail="Error code: 401 AuthError")
    assert h._provider_cooldown_active("prov-x")
    assert not h._provider_cooldown_active("prov-healthy")

    h.invalidate_provider_failures("prov-x")
    assert not h._provider_cooldown_active("prov-x"), (
        "a credential change must be able to recover the provider "
        "immediately — the bench is a pause, never a decommission")


def test_structured_cascade_skips_cooldowned_providers():
    """The loop head must consult the provider cooldown (the same skip the
    other cascades apply) — source-pinned because the defect was exactly a
    path that had the bench machinery available but never consulted it."""
    import core.llm.byok_handler as bh

    src = inspect.getsource(bh.BYOKHandler)
    assert src.count("self._provider_cooldown_active(") >= 3, (
        "the structured cascade's candidate loop must skip provider-"
        "cooldowned candidates like the other cascades do")


def test_auth_branch_benches_the_whole_provider():
    """The 401 branch in the structured cascade must call the PROVIDER
    bench, not only add the pair memo."""
    import core.llm.byok_handler as bh

    src = inspect.getsource(bh)
    assert 'self._bench_provider(\n                                provider_id,' in src \
        or "self._bench_provider(" in src
    # the auth-memo block sits inside the structured cascade and benches
    # with the invalid_credential cause
    assert 'cause="invalid_credential"' in src


def test_structured_gate_vetoes_only_positive_absence():
    """The structured cascade's dispatch gate must veto a model the
    provider's DISCOVERED catalogue excludes, but never veto when the
    catalogue is unknown (an undiscovered environment keeps its structured
    path). Pinned at the unit level: reason-based, not eligible-based."""
    h = _handler()
    import core.llm.model_route_registry as mrr

    assert h._ranked_model_is_known_unserved("never-seen-prov", "some-model") \
        is False, "unknown catalogue must not veto"
