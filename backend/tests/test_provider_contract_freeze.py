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
    assert "https://openrouter.ai/api/v1/" in contract["post_prefixes"]


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
    automatic = runner._authorized_provider_contract({
        "mode": "automatic",
        "allowed_providers": [],
        "approved_providers": PROVIDERS,
    })
    assert runner._provider_policy_violations(
        ["https://api.deepseek.com/v1.evil/chat/completions"],
        automatic["post_prefixes"]), (
        "a host-suffix trick must not pass a startswith check")


def test_deterministic_continuation_is_authorized_without_a_model():
    runner = _runner()
    prefixes = ("deepseek/", "opencode-go/", "openrouter/")
    assert runner._interpretation_route_authorized(
        "deterministic:continuation",
        {"dispatch_models": [], "refinement": {"status": "skipped"}},
        prefixes)
    assert runner._interpretation_route_authorized(
        "deterministic:continuation",
        {"dispatch_models": ["deepseek/deepseek-v4-pro"],
         "refinement": {"status": "completed", "outcome": "unresolved"}},
        prefixes)
    assert not runner._interpretation_route_authorized(
        "deterministic:continuation",
        {"dispatch_models": [], "refinement": {"status": "completed"}},
        prefixes), (
        "a completed refinement with no captured dispatch is UNKNOWN, "
        "not no-dispatch")
    assert not runner._interpretation_route_authorized(
        "deterministic:continuation",
        {"dispatch_models": [], "refinement": {"status": "unknown"}},
        prefixes)
    assert not runner._interpretation_route_authorized(
        "deterministic:continuation",
        {"dispatch_models": ["openrouter/z-ai/glm-5.3-flash"],
         "refinement": {"status": "cancelled"}},
        ("deepseek/", "ollama/")), (
        "an attempted refinement outside the declared policy is never "
        "authorized")
    assert runner._interpretation_route_authorized(
        "llm:glm-5.3-flash",
        {"dispatch_models": ["openrouter/z-ai/glm-5.3-flash"]},
        prefixes)
    assert not runner._interpretation_route_authorized(
        "llm:glm-5.3-flash", {"dispatch_models": []}, prefixes), (
        "a model origin with no captured dispatch is not evidence that an "
        "authorized provider served it")


def test_step_interpretation_prefers_the_accepted_deterministic_record():
    runner = _runner()
    step = {"observation": {
        "interpretation": {"interpretation": {
            "origin": "unresolved", "scope_change": "unresolved"}},
        "apply": {"interpretation": {
            "origin": "deterministic:continuation",
            "refinement": {
                "status": "completed", "outcome": "unresolved"}}},
    }}
    accepted = runner._step_interpretation(step)
    assert accepted["origin"] == "deterministic:continuation", accepted
    assert runner.stage_summary(step, "")["refinement"]["status"] == (
        "completed")
    # Without a deterministic/refinement apply record, the model event
    # remains authoritative.
    model_only = {"observation": {
        "interpretation": {"interpretation": {
            "origin": "llm:test", "scope_change": "continue"}},
        "apply": {"interpretation": {
            "origin": "llm:test", "scope_change": "continue"}},
    }}
    assert runner._step_interpretation(model_only)["origin"] == "llm:test"


def test_stage_summary_carries_refinement_or_unknown():
    runner = _runner()
    step = {"observation": {"apply": {"interpretation": {
        "origin": "deterministic:continuation",
        "refinement": {
            "status": "cancelled", "reason": "wait_timeout"}}}}}
    assert runner.stage_summary(step, "")["refinement"]["status"] == (
        "cancelled")
    bare = {"observation": {"apply": {"interpretation": {
        "origin": "deterministic:continuation"}}}}
    assert runner.stage_summary(bare, "")["refinement"]["status"] == (
        "unknown"), "missing capture must be unknown, not no-dispatch"


def test_l3_answer_contract_remains_strict_on_any_decoy():
    """The original predeclared gate is unchanged. The captured attempt-16
    answer is semantically correct per the independent manual assessment,
    but this automated gate still fails it because it mentions the decoy.
    Do not replace this with a nearby-word disclaimer heuristic."""
    runner = _runner()
    clean = "The launch code for project Zephyr-9 is QUARTZ-77."
    assert runner.l3_answer_contract(clean) is True
    captured_explanatory = (
        "The launch code for project Zephyr-9 is **QUARTZ-77**.\n\n"
        "Source: your uploaded document `l3_zephyr9_fixture.txt`, which "
        "lists the launch code for project Zephyr-9 as QUARTZ-77. "
        "(Note: the same document also mentions BASALT-13, but that's the "
        "archive key for a different project, Halcyon-2 — not relevant "
        "here.)")
    assert runner.l3_answer_contract(captured_explanatory) is False, (
        "the original gate remains strict; the manual assessment is "
        "separate")
    cases = (
        # Swapped attribution.
        "QUARTZ-77 is the archive key; the launch code for Zephyr-9 is "
        "BASALT-13.",
        # Decoy presented as Zephyr-9's code, followed by an unrelated
        # disclaimer on another sentence.
        "The launch code is QUARTZ-77. The launch code for Zephyr-9 is "
        "BASALT-13. This note is not relevant.",
        # Decoy served as the answer.
        "The launch code for project Zephyr-9 is BASALT-13.",
    )
    for text in cases:
        assert runner.l3_answer_contract(text) is False, text


def test_pilot_preflight_requires_a_listening_pilot_by_default():
    runner = _runner()
    absent = {"backend_8001_listening": False,
              "frontend_3000_listening": False}
    listening = {"backend_8001_listening": True,
                 "frontend_3000_listening": True}
    assert runner.pilot_preflight(absent)["ok"] is False
    assert runner.pilot_preflight(absent)["reason"] == "pilot_not_listening"
    assert runner.pilot_preflight(listening)["ok"] is True


def test_pilot_preflight_absent_mode_needs_an_explicit_assertion():
    runner = _runner()
    absent = {"backend_8001_listening": False,
              "frontend_3000_listening": False}
    listening = {"backend_8001_listening": True,
                 "frontend_3000_listening": True}
    assert runner.pilot_preflight(
        absent, "absent", "")["ok"] is False
    assert runner.pilot_preflight(
        absent, "absent", "pilot intentionally stopped; candidate on :8121"
    )["ok"] is True
    assert runner.pilot_preflight(
        listening, "absent", "pilot intentionally stopped")["ok"] is False
    assert runner.pilot_preflight(
        absent, "unknown-mode", "asserted")["ok"] is False


def test_pilot_preflight_stops_before_the_candidate_launch():
    source = RUNNER.read_text()
    preflight = source.index(
        'if not cfg["pilot_preflight"]["ok"]:')
    launch = source.index('launch("pre")')
    assert preflight < launch, (
        "an absent required pilot must stop before creating the world or "
        "launching the candidate")


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
