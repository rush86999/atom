"""Provider-contract freeze for the final composed rehearsal runner.

The gate must match the DECLARED policy and the user's authorization:

* ``automatic`` — every configured provider is eligible;
* ``selected`` — only the declared subset, which must be non-empty and a
  subset of the configured providers;
* an invalid policy authorizes nothing (fail closed);
* historical intended routes are observations, not pass/fail criteria.

The route checks still reject any POST outside the authorized set, so this
does not remove a real restriction to manufacture a pass.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

RUNNER = (
    Path(__file__).resolve().parents[1]
    / "scripts/orchestration_acceptance/journey_matrix"
    / "l1_l2_l3_integrated_served_20261020"
    / "run_composed_served_live_rehearsal_final.py")


def _runner():
    spec = importlib.util.spec_from_file_location(
        "final_rehearsal_runner_policy", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROVIDERS = ["deepseek", "ollama", "opencode-go", "openrouter"]


def test_automatic_authorizes_every_configured_provider():
    runner = _runner()
    contract = runner._authorized_provider_contract({
        "mode": "automatic",
        "allowed_providers": [],
        "approved_providers": PROVIDERS,
    })
    assert contract["valid"] is True
    assert contract["authorized"] == PROVIDERS
    assert "openrouter/" in contract["route_prefixes"]
    assert "https://openrouter.ai/api/v1" in contract["post_prefixes"]


def test_selected_authorizes_only_the_declared_subset():
    runner = _runner()
    contract = runner._authorized_provider_contract({
        "mode": "selected",
        "allowed_providers": ["deepseek", "ollama"],
        "approved_providers": PROVIDERS,
    })
    assert contract["valid"] is True
    assert contract["authorized"] == ["deepseek", "ollama"]
    assert "openrouter/" not in contract["route_prefixes"]


def test_invalid_policy_authorizes_nothing():
    runner = _runner()
    empty = runner._authorized_provider_contract({
        "mode": "selected",
        "allowed_providers": [],
        "approved_providers": PROVIDERS,
    })
    assert empty["valid"] is False
    assert empty["authorized"] == []
    outside = runner._authorized_provider_contract({
        "mode": "selected",
        "allowed_providers": ["anthropic"],
        "approved_providers": PROVIDERS,
    })
    assert outside["valid"] is False
    assert outside["authorized"] == []
    unknown_mode = runner._authorized_provider_contract({
        "mode": "anything",
        "allowed_providers": [],
        "approved_providers": PROVIDERS,
    })
    assert unknown_mode["valid"] is False


def test_policy_violations_fail_closed():
    runner = _runner()
    contract = runner._authorized_provider_contract({
        "mode": "selected",
        "allowed_providers": ["deepseek", "ollama"],
        "approved_providers": PROVIDERS,
    })
    posts = [
        "https://api.deepseek.com/v1/chat/completions",
        "http://localhost:11434/v1/chat/completions",
        "https://opencode.ai/zen/go/v1/chat/completions",
        "https://unknown.example/v1/chat/completions",
    ]
    violations = runner._provider_policy_violations(
        posts, contract["post_prefixes"])
    assert violations == [
        "https://opencode.ai/zen/go/v1/chat/completions",
        "https://unknown.example/v1/chat/completions",
    ]
    assert runner._provider_policy_violations(posts, ()) == posts, (
        "an empty authorization set must reject every POST")


def test_deterministic_continuation_is_authorized_without_a_model():
    runner = _runner()
    prefixes = ("deepseek/", "opencode-go/", "openrouter/")
    assert runner._interpretation_route_authorized(
        "deterministic:continuation", {"dispatch_models": []}, prefixes)
    assert runner._interpretation_route_authorized(
        "llm:glm-5.3-flash",
        {"dispatch_models": ["openrouter/z-ai/glm-5.3-flash"]},
        prefixes)
    assert not runner._interpretation_route_authorized(
        "llm:glm-5.3-flash",
        {"dispatch_models": ["openrouter/z-ai/glm-5.3-flash"]},
        ("deepseek/", "ollama/")), (
        "a route outside the declared policy is never authorized")
    assert not runner._interpretation_route_authorized(
        "llm:glm-5.3-flash", {"dispatch_models": []}, prefixes), (
        "a model origin with no captured dispatch is not evidence that an "
        "authorized provider served it")
    assert not runner._interpretation_route_authorized(
        "deterministic:continuation",
        {"dispatch_models": ["unknown/model"]}, prefixes), (
        "a bounded refinement attempt must still be authorized")


def test_historical_intended_routes_are_observations_not_gates():
    source = RUNNER.read_text()
    checks_block = source.split("checks = {", 1)[1].split(
        "# Guards, captured before", 1)[0]
    assert "provider_allowlist_clean" not in checks_block
    assert "provider_reply_parity" not in checks_block
    assert "provider_policy_respected" in checks_block
    assert "provider_reply_authorized" in checks_block
    # The historical values remain recorded for evidence.
    assert "historical_intended_route_checks" in source
