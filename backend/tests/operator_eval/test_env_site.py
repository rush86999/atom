"""Tests for the operator_eval site hardening, adapter, and canary suite.

Covers ENV_HARNESS_ADOPTION_PLAN rev 2 §Phase 1b (world/evidence split,
strengthened verifiers), §Phase 2 (token control API, ephemeral instances,
rollout classification), §Phase 3 (hand-authored mutations + mechanical
canaries).

Stdlib-only site logic is exercised in-process via EvalSite.request(); one
test spins the real HTTP server to pin the token gate. No model keys, no
playwright, no DB.
"""

import asyncio
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from adapter import EnvInstance, run_rollout                       # noqa: E402
from core.env_curriculum.outcomes import RolloutOutcome, RolloutStatus  # noqa: E402
from core.env_curriculum.mutations import SetupMutation            # noqa: E402
from mutations import build_library, run_canary, run_canary_suite  # noqa: E402
from test_site import (                                            # noqa: E402
    EvalSite,
    WORLD_SCHEMA,
    default_world,
    fresh_evidence,
    start_site,
)
from tasks import BASE_TASKS, get_task                             # noqa: E402


@pytest.fixture
def site() -> EvalSite:
    return EvalSite()


def _get(site: EvalSite, path: str, query: str = ""):
    return site.request("GET", path, query=query)


def _post(site: EvalSite, path: str, form: dict):
    return site.request("POST", path, form=form)


def _verify(task_id: str, result, site: EvalSite) -> bool:
    return bool(get_task(task_id)["verify"](result, site))


# ---------------------------------------------------------------------------
# Phase 1b: world/evidence split
# ---------------------------------------------------------------------------

def test_world_and_evidence_are_separate_namespaces(site):
    assert set(site.world) == WORLD_SCHEMA
    assert site.evidence == fresh_evidence()
    assert set(site.evidence).isdisjoint(set(site.world))


def test_load_world_rejects_evidence_keys(site):
    with pytest.raises(ValueError, match="non-world keys"):
        site.load_world_updates({"form_submissions": 99})
    with pytest.raises(ValueError, match="non-world keys"):
        site.load_world_updates({"visited": ["/docs/1"]})
    assert site.evidence["form_submissions"] == 0  # untouched


def test_load_world_deep_merges_and_copies(site):
    site.load_world_updates({"docs": {"3": {"api_code": "ATOM-9"}}})
    assert site.world["docs"]["3"]["api_code"] == "ATOM-9"
    assert site.world["docs"]["2"]["secret_word"] == \
        default_world()["docs"]["2"]["secret_word"]  # sibling keys survive
    assert site.world["docs"]["3"] is not \
        site.base_world["docs"]["3"]  # no aliasing into the base snapshot


def test_reset_restores_base_world_and_clears_evidence(site):
    site.load_world_updates({"headline": "MUTATED"})
    _post(site, "/submit", {"name": "x", "email": "y", "company": "z"})
    site.control_reset()
    assert site.world["headline"] == default_world()["headline"]
    assert site.evidence == fresh_evidence()


def test_visited_tracks_order_excluding_state_and_control(site):
    _get(site, "/docs/1")
    _get(site, "/state")
    _get(site, "/docs/2")
    assert site.evidence["visited"] == ["/docs/1", "/docs/2"]


# ---------------------------------------------------------------------------
# Phase 1b: strengthened verifiers
# ---------------------------------------------------------------------------

def test_form_fill_requires_all_three_fields(site):
    task = get_task("form_fill")
    # email missing → the rev 1 verifier accepted this; rev 2 must not.
    _post(site, "/submit", {"name": "Ada Lovelace",
                            "email": "", "company": "Analytical Engines"})
    assert site.evidence["form_errors"] == 1  # site rejected the incomplete submit
    _post(site, "/submit", {"name": "Ada Lovelace",
                            "email": "ada@example.com",
                            "company": "Analytical Engines"})
    assert _verify("form_fill", {"summary": "done"}, site)


def test_form_fill_rejects_wrong_email(site):
    _post(site, "/submit", {"name": "Ada Lovelace", "email": "wrong@x.com",
                            "company": "Analytical Engines"})
    assert not _verify("form_fill", {"summary": ""}, site)


def test_form_validation_requires_reported_error_message(site):
    site.load_world_updates(
        {"form_error_message": "Please complete every field."})
    _post(site, "/submit", {"name": "Grace"})
    msg = site.evidence["last_form_error"]
    assert _verify("form_validation",
                   {"summary": f"The page says: {msg}"}, site)
    # error count hit, but the summary doesn't report the message → fail
    assert not _verify("form_validation",
                       {"summary": "I submitted the form."}, site)


def test_all_verifiers_fail_on_empty_result(site):
    for task in BASE_TASKS:
        assert not _verify(task["id"], {"summary": ""}, site), task["id"]


def test_base_verifiers_pass_on_mechanical_solutions(site):
    """Every base task must be solvable: mechanical solver → frozen verifier."""
    from mutations import MECHANICAL_SOLUTIONS

    class _Shim:
        def __init__(self, s):
            self.site = s

    shim = _Shim(site)
    for task in BASE_TASKS:
        site.control_reset()
        result = MECHANICAL_SOLUTIONS[task["id"]](shim, task)
        assert _verify(task["id"], result, site), task["id"]


# ---------------------------------------------------------------------------
# Rules engine
# ---------------------------------------------------------------------------

def test_hide_link_removes_only_matching_anchor(site):
    site.set_rules(observe=[{"kind": "hide_link", "href": "/docs/3"}])
    _status, _ctype, body = _get(site, "/")
    html = body.decode()
    assert "href='/docs/3'" not in html
    assert "href='/docs/2'" in html


def test_redact_text_filters_rendered_pages(site):
    site.set_rules(observe=[{"kind": "redact_text", "text": "quokka"}])
    _status, _ctype, body = _get(site, "/docs/2")
    assert "quokka" not in body.decode()
    assert "[redacted]" in body.decode()


def test_block_path_intercepts(site):
    site.set_rules(action=[{"kind": "block_path", "path": "/search",
                            "status": 404}])
    status, _ctype, _body = _get(site, "/search", query="q=pricing")
    assert status == 404


def test_fail_first_n_fails_then_recovers(site):
    site.set_rules(action=[{"kind": "fail_first_n", "method": "POST",
                            "path": "/submit", "n": 1, "status": 500}])
    form = {"name": "a", "email": "b", "company": "c"}
    status1, _ctype, _b1 = _post(site, "/submit", form)
    status2, _ctype, _b2 = _post(site, "/submit", form)
    assert status1 == 500 and status2 == 200
    assert site.evidence["form_submissions"] == 1  # blocked attempt not counted


def test_rules_reject_unknown_kind_and_missing_params(site):
    with pytest.raises(ValueError, match="Unknown rule kind"):
        site.set_rules(observe=[{"kind": "explode"}])
    with pytest.raises(ValueError, match="missing params"):
        site.set_rules(action=[{"kind": "fail_first_n", "method": "POST"}])


def test_rules_reset_with_control_reset(site):
    site.set_rules(action=[{"kind": "block_path", "path": "/long"}])
    site.control_reset()
    status, _ctype, _body = _get(site, "/long")
    assert status == 200


# ---------------------------------------------------------------------------
# Phase 2: token gate + instance isolation
# ---------------------------------------------------------------------------

def test_control_api_rejects_missing_token():
    site, stop = start_site()  # real HTTP server, ephemeral port
    try:
        url = f"{site.base_url}/control/reset"
        req = urllib.request.Request(url, data=b"{}", method="POST")
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(req)
        assert excinfo.value.code == 403

        good = urllib.request.Request(
            url, data=b"{}", method="POST",
            headers={"X-Run-Token": site.run_token})
        with urllib.request.urlopen(good) as resp:
            assert json.loads(resp.read())["ok"] is True
    finally:
        stop()


def test_instances_are_isolated_from_each_other():
    with EnvInstance() as a, EnvInstance() as b:
        assert a.base_url != b.base_url
        a.site.load_world_updates({"headline": "ONLY-A"})
        _post(a.site, "/submit", {"name": "n", "email": "e", "company": "c"})
        assert b.site.world["headline"] != "ONLY-A"
        assert b.site.evidence["form_submissions"] == 0


# ---------------------------------------------------------------------------
# Phase 2: rollout classification (fake loop — deterministic, no Chromium)
# ---------------------------------------------------------------------------

class FakeSession:
    def __init__(self):
        self.started = False

    async def start(self, start_url=None):
        self.started = True

    async def close(self):
        pass


def _fake_loop(summary, done=True, steps=2, exc=None):
    class FakeLoop:
        def __init__(self, backend, max_steps):
            pass

        async def run(self, goal):
            if exc:
                raise exc
            return {"done": done, "steps": steps, "summary": summary}
    return FakeLoop


def _run(instance, task, loop_factory):
    return asyncio.run(run_rollout(
        instance, task, loop_factory=loop_factory,
        session_factory=FakeSession))


def test_rollout_pass_classification():
    with EnvInstance() as instance:
        outcome = _run(instance, get_task("find_code"),
                       _fake_loop("The API secret code is ATOM-7741."))
    assert outcome.status == RolloutStatus.PASS
    assert outcome.steps == 2


def test_rollout_agent_fail_classification():
    with EnvInstance() as instance:
        outcome = _run(instance, get_task("find_code"),
                       _fake_loop("I could not find any code."))
    assert outcome.status == RolloutStatus.AGENT_FAIL


def test_rollout_harness_error_on_loop_crash():
    with EnvInstance() as instance:
        outcome = _run(instance, get_task("find_code"),
                       _fake_loop("", exc=RuntimeError("401 CreditsError")))
    assert outcome.status == RolloutStatus.HARNESS_ERROR
    assert "CreditsError" in outcome.error
    assert not outcome.counts_for_rate


def test_rollout_harness_error_on_error_bearing_result():
    """OperatorLoop never raises machinery failures — it returns them in
    result['error'] (caught exceptions, governance blocks, observation
    failures, undecidable first steps). Those must classify as
    HARNESS_ERROR, never reach the verifier as agent_fail/pass."""
    def loop_with_error(backend, max_steps):
        class FakeLoop:
            async def run(self, goal):
                return {"done": False, "steps": 0, "summary": "",
                        "actions": [], "error": "observation failed: "
                        "browser died"}
        return FakeLoop()

    with EnvInstance() as instance:
        outcome = _run(instance, get_task("find_code"), loop_with_error)
    assert outcome.status == RolloutStatus.HARNESS_ERROR
    assert "browser died" in outcome.error
    assert not outcome.counts_for_rate


def test_rollout_error_free_result_still_scores_via_verifier():
    # A clean result (no error field) must keep the normal path: verifier
    # decides pass/agent_fail.
    with EnvInstance() as instance:
        outcome = _run(instance, get_task("find_code"),
                       _fake_loop("I could not find any code."))
    assert outcome.status == RolloutStatus.AGENT_FAIL


def test_pinned_decider_raises_on_provider_failure_instead_of_done():
    """A provider exhaustion must surface as an exception (which the loop
    records as error → adapter HARNESS_ERROR), never as a synthetic
    done=True that the verifier could score as an agent outcome."""
    import asyncio as _asyncio
    from pinned_decider import PinnedVisionDecider

    class ExplodingClient:
        class chat:  # noqa: N801 — mirrors openai SDK shape
            class completions:  # noqa: N801
                @staticmethod
                async def create(**kw):
                    raise RuntimeError("401 CreditsError")

    decider = PinnedVisionDecider(ExplodingClient(), "glm-5.3-flash",
                                  attempts=2)

    class Obs:
        url = "http://x/"; title = "t"; page_text = "p"
        screenshot_b64 = None
        viewport = (1280, 720)

    with pytest.raises(RuntimeError, match="model call failed"):
        _asyncio.run(decider.decide("goal", Obs(), history=[]))


def test_rollout_harness_error_on_verifier_crash():
    def bad_verify(result, site):
        raise KeyError("boom")

    with EnvInstance() as instance:
        task = dict(get_task("find_code"))
        task["verify"] = bad_verify
        outcome = _run(instance, task, _fake_loop("anything"))
    assert outcome.status == RolloutStatus.HARNESS_ERROR
    assert "verifier crashed" in outcome.error


def test_rollout_error_bearing_result_with_agent_reason_is_scored():
    """no_valid_action / unparseable_step / repeated_action_failure /
    action_blocked / budget_exhausted are AGENT-attributable terminations:
    they must reach the verifier (-> agent_fail here), never be excluded
    and rerun as harness errors - that would bias success rates upward."""
    seen = []

    def loop_reason(termination_reason, error=None):
        def factory(backend, max_steps):
            seen.append(termination_reason)

            class FakeLoop:
                async def run(self, goal):
                    return {"done": False, "steps": 2, "summary": "",
                            "actions": [{"step": 1, "action": "click",
                                         "action_type": "click",
                                         "success": False}],
                            "termination_reason": termination_reason,
                            "error": error}
            return FakeLoop()
        return factory

    with EnvInstance() as instance:
        for reason in ("no_valid_action", "unparseable_step",
                       "repeated_action_failure", "action_blocked",
                       "budget_exhausted"):
            err = ("no action could be decided for the task"
                   if reason == "no_valid_action" else None)
            outcome = _run(instance, get_task("find_code"),
                           loop_reason(reason, error=err))
            assert outcome.status == RolloutStatus.AGENT_FAIL, reason
    assert seen == ["no_valid_action", "unparseable_step",
                    "repeated_action_failure", "action_blocked",
                    "budget_exhausted"]


def test_rollout_infrastructure_terminations_are_harness_errors():
    def loop_reason(termination_reason, error):
        def factory(backend, max_steps):
            class FakeLoop:
                async def run(self, goal):
                    return {"done": False, "steps": 0, "summary": "",
                            "actions": [],
                            "termination_reason": termination_reason,
                            "error": error}
            return FakeLoop()
    with EnvInstance() as instance:
        for reason, err in (("exception", "playwright exploded"),
                            ("observation_failed", "browser died"),
                            ("stopped", None)):
            outcome = _run(instance, get_task("find_code"),
                           loop_reason(reason, err))
            assert outcome.status == RolloutStatus.HARNESS_ERROR, reason
            assert not outcome.counts_for_rate, reason


def test_rollout_legacy_error_without_reason_stays_conservative():
    """A foreign/legacy producer returning an error with NO termination
    reason is treated as harness (conservative), not as agent failure."""
    def factory(backend, max_steps):
        class FakeLoop:
            async def run(self, goal):
                return {"done": False, "steps": 0, "summary": "",
                        "actions": [], "error": "unknown producer error"}
        return FakeLoop()
    with EnvInstance() as instance:
        outcome = _run(instance, get_task("find_code"), factory)
    assert outcome.status == RolloutStatus.HARNESS_ERROR
    assert "unknown producer error" in outcome.error


def test_scorer_exact_boundary_two_of_six_is_met():
    """The registered 4b-style bar: a 2-rollout gap out of 6 is exactly
    33⅓pp and must count as met at threshold 1/3 — the pre-fix scorer
    rounded each rate first (0.833-0.5=0.333) and mis-summed this case."""
    from experiment import Runner
    from unittest.mock import patch

    with patch("core.llm_service.LLMService"):
        runner = Runner.__new__(Runner)  # no heavy init: only scoring tested
    runner.record = {"rollouts": [], "briefs": {}}
    runner.families = ["f1"]
    runner.delta_threshold = 1 / 3
    runner.out_path = Path("/tmp") / "boundary-test.json"

    def add(stage, arm, status):
        runner.record["rollouts"].append({
            "stage": stage, "arm": arm, "task_id": "f1", "status": status})

    # Arm A: 3 passes of 6. Arm B: 5 passes of 6 → gap exactly 2/6 = 1/3.
    for status in ("pass", "pass", "pass", "agent_fail", "agent_fail",
                   "agent_fail"):
        add("test_A", "A", status)
    for status in ("pass", "pass", "pass", "pass", "pass", "agent_fail"):
        add("test_B", "B", status)
    runner._score()
    assert runner.record["score"]["delta_pp"] == pytest.approx(33.3, abs=0.1)
    assert "THRESHOLD MET" in runner.record["score"]["decision"]


def test_format_actions_includes_parameters_and_detail():
    from experiment import _format_actions
    actions = [
        {"action_type": "click", "success": True,
         "parameters": {"coordinates": [412, 230]},
         "detail": {"url": "http://x/docs/3", "title": "Reference"}},
        {"action_type": "type", "success": False,
         "parameters": {"text": "hunter2"}, "detail": {}},
    ]
    rendered = _format_actions(actions)
    assert "click" in rendered and "412" in rendered
    assert "docs/3" in rendered and "Reference" in rendered
    assert "hunter2" in rendered and "FAIL" in rendered
    assert _format_actions([]) == "(none)"


def test_rollout_starts_from_reset_env():
    with EnvInstance() as instance:
        instance.site.load_world_updates({"headline": "STALE"})
        outcome = _run(instance, get_task("extract_headline"),
                       _fake_loop("Headline: OPERATOR EVAL DAILY"))
    # the adapter reset cleared the stale world before the rollout
    assert outcome.status == RolloutStatus.PASS


def test_apply_stack_validates_before_applying():
    from core.env_curriculum.mutations import MutationStack
    with EnvInstance() as instance:
        bad = MutationStack(name="bad",
                            setup=SetupMutation({"form_submissions": 99}))
        with pytest.raises(ValueError, match="non-world keys"):
            instance.apply_stack(bad)
        assert instance.site.world == default_world()  # nothing applied


# ---------------------------------------------------------------------------
# Phase 3: canary suite (deterministic, no model)
# ---------------------------------------------------------------------------

def test_canary_suite_full_expectation_match():
    results = run_canary_suite()
    names = {r["mutation"] for r in results}
    assert len(results) >= 12
    assert all(r["passed"] for r in results), [
        (r["mutation"], r["reason"]) for r in results if not r["passed"]]
    assert all(r.get("firebreak_intact") for r in results)
    negatives = [r for r in results if not r["solved"]]
    assert {r["mutation"] for r in negatives} == {
        "rules.redact_password_hint",
        "rules.redact_pricing_secret",
        "rules.block_search",
    }


def test_canary_detects_unsolvable_mutation_directionally():
    spec = next(s for s in build_library()
                if s.stack.name == "rules.block_search")
    with EnvInstance() as instance:
        result = run_canary(spec, instance=instance)
    assert result["solved"] is False
    assert result["passed"] is True  # expected unsolvable
    assert "firebreak" not in result["reason"].lower()


def test_evidence_site_vs_base_env_label_on_outcomes():
    outcome = RolloutOutcome(task_id="t", status=RolloutStatus.PASS,
                             env_label="mut:x", arm="B")
    assert outcome.to_dict()["env_label"] == "mut:x"
