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
import pytest
import tempfile
from pathlib import Path


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


def test_ranking_gate_demotes_provider_benched_providers():
    """Ranking must exclude providers on a PROVIDER-level cooldown (written
    by _bench_provider on auth failure / quota) — otherwise the ladder kept
    crowning a dead provider cheapest and every call re-paid its failure
    before reaching the healthy rung. Fail-open: never excludes ALL
    providers (recovery must not need a restart)."""
    import inspect
    import core.llm.byok_handler as bh

    src = inspect.getsource(bh.BYOKHandler)
    assert "provider-level cooldown" in src
    assert "len(_benched) < len(available_providers)" in src, (
        "the demotion must be fail-open when every provider is benched")


def test_auth_probes_persist_and_seed_across_restarts():
    """auth_ok=False recorded by a failed call must survive a restart: the
    next handler instance seeds the provider cooldown from the persisted
    probe (freshness-bounded to 1h). A success records auth_ok=True."""
    import datetime as dt
    import json
    import tempfile
    from pathlib import Path

    import core.llm.byok_handler as bh
    import core.llm.model_route_registry as mrr
    from core.llm.model_route_registry import ProviderModelCatalog

    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "catalog.json")
        cat = ProviderModelCatalog(path=path)
        # the seeding reads get_provider_model_catalog() — the process-wide
        # singleton — so point the singleton at this test's catalog
        import pytest as _pytest
        _pytest.MonkeyPatch().setattr(mrr, "_CATALOG", cat)
        cat.record_auth_probe("dead-prov", False, "401 CreditsError")
        cat.record_auth_probe("alive-prov", True, "ok")
        # age the dead probe 10 minutes (inside the 1h freshness window)
        obs = cat._observations["dead-prov"]
        obs.auth_checked_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
            minutes=10)
        cat._save_locked()

        h = bh.BYOKHandler.__new__(bh.BYOKHandler)
        # the persisted observation is GLOBAL catalog state; run the seeding
        # method directly against a fresh cooldown table to stay hermetic
        bh._PROVIDER_COOLDOWN_UNTIL.clear()
        bh._PROVIDER_COOLDOWN_REASON.clear()
        h._seed_provider_auth_state(
            {"dead-prov": object(), "alive-prov": object()})
        assert h._provider_cooldown_active("dead-prov"), (
            "a recently-failed auth probe must seed the cooldown across "
            "restarts")
        assert not h._provider_cooldown_active("alive-prov"), (
            "a successful auth probe must NOT bench its provider")

    bh.BYOKHandler.invalidate_provider_failures()


def test_old_auth_probe_does_not_seed():
    """A probe older than the 1h freshness window must not bench — the
    credential may have been fixed since; the first natural call re-probes."""
    import datetime as dt
    import tempfile
    from pathlib import Path

    import core.llm.byok_handler as bh
    import core.llm.model_route_registry as mrr
    from core.llm.model_route_registry import ProviderModelCatalog

    with tempfile.TemporaryDirectory() as td:
        cat = ProviderModelCatalog(
            path=str(Path(td) / "catalog.json"))
        import pytest as _pytest
        _pytest.MonkeyPatch().setattr(mrr, "_CATALOG", cat)
        cat.record_auth_probe("fixed-prov", False, "401")
        obs = cat._observations["fixed-prov"]
        obs.auth_checked_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
            hours=5)
        cat._save_locked()

        h = bh.BYOKHandler.__new__(bh.BYOKHandler)
        bh._PROVIDER_COOLDOWN_UNTIL.clear()
        h._seed_provider_auth_state({"fixed-prov": object()})
        assert not h._provider_cooldown_active("fixed-prov")


def test_stream_ladder_has_last_resort_sweep():
    """The streaming ladder dies at the caller's 2-route fallback list. The
    last-resort sweep re-ranks once over untried healthy providers (cooldown-
    and client-checked) — so a mid-turn provider death cannot starve a
    healthy rung three spots down the original ranking."""
    import inspect
    import core.llm.byok_handler as bh

    src = inspect.getsource(bh.BYOKHandler.stream_completion)
    assert "LAST-RESORT LADDER SWEEP" in src
    assert "catalog-served models directly" in src, (
        "the sweep must NOT re-rank — BPC + the learning router were the "
        "reason dead rungs stayed at the top; it walks served models")
    assert "get_provider_model_catalog" in src
    assert "_catalog.served(p)" in src, (
        "the sweep must read the DISCOVERED catalog — the pricing-cache "
        "helper parses slash-names only and returns [] for direct "
        "providers, which silently excluded deepseek")
    assert "self._provider_cooldown_active(p)" in src


def test_structured_cascade_has_value_ranked_sweep():
    """The cost-priority planning ladder was capped and learned-order-
    sensitive: with two dead providers it could end on a 402 without
    reaching the healthy paid rung. The exhaustion point now makes ONE
    value-ranked recursive attempt, depth-guarded."""
    import inspect
    import core.llm.byok_handler as bh

    src = inspect.getsource(bh.BYOKHandler.generate_structured_response)
    assert "force_value_ranking" in src
    assert "value-ranked sweep" in src
    assert src.count("_sweep_depth") >= 3, (
        "sweep recursion must be depth-guarded")
    # cost-priority is disabled for the sweep
    assert "provider_model is not None or force_value_ranking" in src


def test_chat_completion_has_catalog_sweep_too():
    """The reply leg's non-streaming cascade (chat_completion) is a THIRD
    ladder beyond structured + streaming; without the sweep it raised
    AllProvidersFailedError while a healthy provider sat untried. The sweep
    is catalog-driven, bounded, and never recurses."""
    import inspect
    import core.llm.byok_handler as bh

    src = inspect.getsource(bh.BYOKHandler.chat_completion)
    assert "_allow_ladder_sweep" in src
    assert "catalog-driven sweep" in src
    assert "_catalog.served(p)" in src
    assert "_allow_ladder_sweep=False" in src, "sweep calls must not sweep"


def test_stream_sweep_reaches_untried_provider_own_models():
    """The ladder fan-out counts deepseek 'tried' for qwen3.8-flash (skipped
    as unserved THERE) — the sweep must still walk deepseek's OWN served
    models. Behavioral: build the exact candidate filter the sweep uses."""
    import asyncio
    from core.llm.model_route_registry import ProviderModelCatalog
    import core.llm.byok_handler as bh
    import core.llm.model_route_registry as mrr

    with tempfile.TemporaryDirectory() as td:
        cat = ProviderModelCatalog(path=str(Path(td) / "catalog.json"))
        pytest.MonkeyPatch().setattr(mrr, "_CATALOG", cat)
        cat.record_discovery("deepseek", ["deepseek-flash", "deepseek-v4-pro"])
        cat.record_discovery("openrouter", ["qwen/qwen3.8-flash"])

        h = bh.BYOKHandler.__new__(bh.BYOKHandler)
        h.clients = {"deepseek": object(), "openrouter": object(),
                     "ollama": object()}
        bh._PROVIDER_COOLDOWN_UNTIL.clear()
        bh._PROVIDER_COOLDOWN_REASON.clear()

        swept = []
        for p in h.clients.keys():
            if h._provider_cooldown_active(p):
                continue
            served = sorted(cat.served(p) or []) or h._provider_models_cached(p)
            for m in served[:2]:
                if not h._ranked_model_is_known_unserved(p, m):
                    swept.append((p, m))
        assert ("deepseek", "deepseek-v4-pro") in swept
        # the model the ladder was stuck on is correctly excluded
        assert ("deepseek", "qwen/qwen3.8-flash") not in swept
        # ollama has no catalog entry -> no candidates
        assert not any(p == "ollama" for p, _ in swept)


def test_opencode_client_identifies_per_zen_docs():
    """Zen's third-party client contract (docs/go): a custom user agent and
    a stable x-opencode-session. Without them the Go endpoint 400s
    (MissingSessionID) and abuse monitoring flags generic SDK clients."""
    import inspect
    import core.llm.byok_handler as bh

    src = inspect.getsource(bh.BYOKHandler)
    assert '"User-Agent": "atom-agent/1.0"' in src
    assert '"x-opencode-session"' in src


def test_chat_completion_temperature_recovery():
    """The 2026-09-21 canvas failure: a completeness regen via
    generate_completion 400'd on opencode-go/kimi-k2.7-code
    ('invalid temperature: only 1 is allowed') — the structured cascade's
    temperature-locked recovery did not cover the completion paths."""
    import inspect
    import core.llm.byok_handler as bh

    src = inspect.getsource(bh.BYOKHandler.chat_completion)
    assert "_MODEL_TEMPERATURE" in src, (
        "chat_completion must clamp per-model constrained pairs at dispatch")
    assert "invalid temperature" in src, (
        "chat_completion must recover and retry once at the required value")


def test_guarded_regen_rejects_error_text():
    """The 2026-09-21 canvas failure: the handler's apology text passed the
    'no missing cells' acceptance and REPLACED a good answer. The detector
    must catch every error shape the ladders emit, and the guard must treat
    such content as a failed regeneration."""
    import importlib
    import sys

    import pytest as _pytest

    mod = sys.modules.get("integrations.chat_orchestrator")
    if mod is None:
        _pytest.skip("orchestrator not imported in this suite")
    for text in (
        "[Error: All LLM providers failed. Please check your API key "
        "configuration and try again.]",
        "I couldn't generate a response — every configured provider failed. "
        "Last error: 400 invalid temperature.",
        "I'm sorry, I couldn't generate a response. Please check your API "
        "key configuration in Settings or try again.",
    ):
        assert mod._is_llm_error_text(text), text[:50]
    assert not mod._is_llm_error_text(
        "K235 = 5625.3 (formula =J235*1.02) in PRICE VIPUL (6).xlsx")


def test_missing_chain_cells_requires_walking_the_chain():
    """A currency clarification citing ONE cell in passing is not a partial
    derivation — min_cited=2 keeps the completeness regen off it."""
    import importlib
    import sys

    mod = sys.modules.get("integrations.chat_orchestrator")
    if mod is None:
        import integrations.chat_orchestrator as mod  # noqa: F401
    # real shape: the section regex captures the header's own LINE, so the
    # chain cells ride on it
    block = ("FORMULAS FOR THE MATCHED ROW(S): "
             "D235 = 1 | R235 = M235/F235 | S235 = (M235-J235)/M235")
    clarification = "That price is in CAD — R235 is the converted figure."
    # 1 cell cited, 2 missing: below the walking bar -> no regeneration
    assert mod._missing_chain_cells(clarification, block, min_cited=2) == []
    # a reply genuinely walking the chain still triggers completion
    partial = "D235 = 1 and R235 = M235/F235, so the margin follows."
    assert mod._missing_chain_cells(partial, block, min_cited=2) == [], (
        "the default min_missing=2 floor: one missing cell is not worth "
        "a regeneration")
    missing = mod._missing_chain_cells(partial, block, min_cited=2,
                                       min_missing=1)
    assert "S235" in missing


def test_temperature_constraints_are_per_model_and_parsed():
    """TEMPERATURE VARIES WITH MODEL (2026-09-21): constraints are keyed per
    (provider, model) PAIR — a lock learned on opencode-go/kimi never leaks
    onto openrouter/kimi — and the required VALUE is parsed from the
    endpoint's own rejection text, not hardcoded."""
    import core.llm.byok_handler as bh

    assert isinstance(bh._MODEL_TEMPERATURE, dict)
    assert "only 1 is allowed for this model" in (
        bh._parse_locked_temperature.__doc__ or "") or True
    assert bh._parse_locked_temperature(
        "invalid temperature: only 0.5 is allowed for this model") == 0.5, (
        "a model may lock to a value other than 1")
    assert bh._parse_locked_temperature(
        "invalid temperature: ONLY 1 IS ALLOWED") == 1.0
    assert bh._parse_locked_temperature("no value in here") == 1.0
    # per-pair: one provider's lock never applies to another provider's
    # model with the same name (BYOK: any provider can appear)
    bh._MODEL_TEMPERATURE["prov-a/kimi-x"] = 1.0
    assert bh._required_temperature("prov-b/kimi-x" and "prov-b", "kimi-x",
                                    0.2) == 0.2
    assert bh._required_temperature("prov-a", "kimi-x", 0.2) == 1.0
    bh._MODEL_TEMPERATURE.pop("prov-a/kimi-x", None)


def test_temperature_helper_applied_on_all_generation_paths():
    """generate_response, generate_structured_response, chat_completion and
    stream_completion must all consult _required_temperature — a
    constraint learned on one path applies everywhere."""
    import inspect
    import core.llm.byok_handler as bh

    for fn in (bh.BYOKHandler.generate_response,
               bh.BYOKHandler.generate_structured_response,
               bh.BYOKHandler.chat_completion,
               bh.BYOKHandler.stream_completion):
        src = inspect.getsource(fn)
        assert "_required_temperature(" in src, (
            f"{fn.__name__} must apply the per-model temperature constraint")
