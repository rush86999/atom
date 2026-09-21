"""Hand-authored declarative mutations + deterministic solvability canaries.

Phase 3 of docs/architecture/ENV_HARNESS_ADOPTION_PLAN.md. The library is
the seed vocabulary a Phase 5 designer would compose from; the canaries
prove the machinery end-to-end WITHOUT any LLM/Chromium:

  mutated env → mechanical solution (a scripted agent reading the same
  filtered HTML a browser would) → frozen verifier → expectation.

Canaries encode a direction, not just a pass/fail: positive stacks must stay
solvable under the mutation, negative stacks (rules that destroy a task's
solution) must be detected as unsolvable — a canary that "solves" a
redacted-away secret or fails to solve a retry-transient would mean the
rules engine, the evidence split, or the verifier is broken.

No model keys, no playwright, no DB — safe to run anywhere, anytime.
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.env_curriculum.mutations import (  # noqa: E402
    MutationStack,
    RuleSpec,
    RulesMutation,
    SetupMutation,
)
from test_site import EvalSite, default_world  # noqa: E402
from tasks import BASE_TASKS, get_task         # noqa: E402


# ---------------------------------------------------------------------------
# Mechanical solutions — one scripted solver per task, reading only what the
# (possibly rule-filtered) site serves. Raising = "agent could not solve it".
# ---------------------------------------------------------------------------

def _get(instance, path: str, query: str = ""):
    status, _ctype, body = instance.site.request("GET", path, query=query)
    return status, body.decode()


def _post(instance, path: str, form: dict):
    status, _ctype, body = instance.site.request("POST", path, form=form)
    return status, body.decode()


def _solve_form_fill(instance, task) -> dict:
    _status, html = _get(instance, "/form")
    names = re.findall(r"input name='(\w+)'", html)
    values = {"name": "Ada Lovelace", "email": "ada@example.com",
              "company": "Analytical Engines"}
    form = {n: values[n] for n in names}  # unknown contract names → KeyError
    for _attempt in range(3):             # retries absorb fail_first_n rules
        status, html = _post(instance, "/submit", form)
        if status == 200:
            return {"done": True, "steps": 2,
                    "summary": "Submitted the form with all fields."}
    raise RuntimeError(f"form submit kept failing (last status {status})")


def _solve_find_code(instance, task) -> dict:
    _status, html = _get(instance, "/docs/3")
    match = re.search(r"secret code is ([\w-]+)", html)
    if not match:
        raise RuntimeError("API secret code not findable on /docs/3")
    return {"done": True, "steps": 2,
            "summary": f"The API secret code is {match.group(1)}."}


def _solve_login_flow(instance, task) -> dict:
    _status, html = _get(instance, "/login")
    # capture to the closing </p>, not \S+ — passwords would otherwise
    # swallow trailing markup ('hunter2</p><form').
    match = re.search(r"credentials: (\S+) / ([^<]+)</p>", html)
    if not match:
        raise RuntimeError("credentials hint not readable on /login")
    _status, _html = _post(instance, "/do_login",
                           {"user": match.group(1), "pass": match.group(2)})
    status, _html = _get(instance, "/dashboard")
    if status != 200:
        raise RuntimeError("dashboard unreachable after login")
    return {"done": True, "steps": 3,
            "summary": "Logged in and reached the dashboard."}


def _solve_search_and_click(instance, task) -> dict:
    _status, html = _get(instance, "/search", query="q=pricing")
    match = re.search(r"<ol>.*?<a href='([^']+)'", html, re.S)
    if not match:
        raise RuntimeError("no search results rendered")
    _status, html = _get(instance, match.group(1))
    word = re.search(r"secret word is '(\w+)'", html)
    if not word:
        raise RuntimeError("pricing secret word not findable on the result page")
    return {"done": True, "steps": 3,
            "summary": f"The pricing secret word is {word.group(1)}."}


def _solve_ordered_navigation(instance, task) -> dict:
    for doc in ("1", "2", "3"):
        _status, _html = _get(instance, f"/docs/{doc}")
    return {"done": True, "steps": 3,
            "summary": "Visited docs 1, 2, 3 in order."}


def _solve_extract_headline(instance, task) -> dict:
    _status, html = _get(instance, "/")
    match = re.search(r"Top headline: ([^<]+)", html)
    if not match:
        raise RuntimeError("headline not findable on the index page")
    return {"done": True, "steps": 1, "summary": f"Headline: {match.group(1)}"}


def _solve_scroll_find(instance, task) -> dict:
    _status, html = _get(instance, "/long")
    match = re.search(r"Bottom code: ([\w-]+)", html)
    if not match:
        raise RuntimeError("bottom code not findable on /long")
    return {"done": True, "steps": 2,
            "summary": f"The bottom code is {match.group(1)}."}


def _solve_form_validation(instance, task) -> dict:
    _status, html = _get(instance, "/form")
    names = re.findall(r"input name='(\w+)'", html)
    form = {n: "" for n in names}
    if "name" not in form:
        raise RuntimeError("form lost its name field")
    form["name"] = "Grace"
    _status, html = _post(instance, "/submit", form)
    match = re.search(r"<p>([^<]+)</p>", html)
    if not match:
        raise RuntimeError("no error message shown for incomplete submit")
    return {"done": True, "steps": 2,
            "summary": f"The page says: {match.group(1)}"}


MECHANICAL_SOLUTIONS = {
    "form_fill": _solve_form_fill,
    "find_code": _solve_find_code,
    "login_flow": _solve_login_flow,
    "search_and_click": _solve_search_and_click,
    "ordered_navigation": _solve_ordered_navigation,
    "extract_headline": _solve_extract_headline,
    "scroll_find": _solve_scroll_find,
    "form_validation": _solve_form_validation,
}


# ---------------------------------------------------------------------------
# The seed mutation library (hand-authored, Phase 3)
# ---------------------------------------------------------------------------

def _stack(name: str, world: dict | None = None,
           observe: list[RuleSpec] | None = None,
           action: list[RuleSpec] | None = None, notes: str = "") -> MutationStack:
    return MutationStack(
        name=name,
        setup=SetupMutation(world) if world else None,
        rules=RulesMutation(observe=tuple(observe or ()),
                            action=tuple(action or())) if (observe or action) else None,
        notes=notes,
    )


# Start-state (Setup) mutations — every rotation doubles as the Phase 4
# family-parameterization mechanism (world values → disjoint instance sets).
SETUP_ROTATIONS = {
    "form_fields": [
        {"name": "name", "label": "Full name"},
        {"name": "email", "label": "Work email"},
        {"name": "company", "label": "Employer"},
    ],
    "api_code": "ATOM-2026",
    "secret_word": "capybara",
    "longpage_code": "LONGPAGE-7",
    "creds": {"user": "ada", "pass": "engine42"},
    "form_error_message": "Please complete every field before submitting.",
    "headline": "METRO BUSINESS WIRE",
}


def build_library() -> list["CanarySpec"]:
    world = default_world()
    return [
        CanarySpec(
            stack=_stack("setup.relabel_form_fields",
                         world={"form_fields": SETUP_ROTATIONS["form_fields"]},
                         notes="labels change, contract names don't"),
            task_id="form_fill", expect_solvable=True),
        CanarySpec(
            stack=_stack("setup.api_code_rotation",
                         world={"docs": {"3": {"api_code": SETUP_ROTATIONS["api_code"]}}}),
            task_id="find_code", expect_solvable=True),
        CanarySpec(
            stack=_stack("setup.secret_word_rotation",
                         world={"docs": {"2": {"secret_word": SETUP_ROTATIONS["secret_word"]}}}),
            task_id="search_and_click", expect_solvable=True),
        CanarySpec(
            stack=_stack("setup.longpage_code_rotation",
                         world={"longpage_code": SETUP_ROTATIONS["longpage_code"]}),
            task_id="scroll_find", expect_solvable=True),
        CanarySpec(
            stack=_stack("setup.creds_rotation",
                         world={"creds": SETUP_ROTATIONS["creds"]}),
            task_id="login_flow", expect_solvable=True),
        CanarySpec(
            stack=_stack("setup.form_error_copy",
                         world={"form_error_message": SETUP_ROTATIONS["form_error_message"]}),
            task_id="form_validation", expect_solvable=True),
        CanarySpec(
            stack=_stack("setup.headline_change",
                         world={"headline": SETUP_ROTATIONS["headline"]}),
            task_id="extract_headline", expect_solvable=True),
        # Rules positives — harder, still solvable.
        CanarySpec(
            stack=_stack("rules.hide_docs3_link",
                         observe=[RuleSpec("hide_link", {"href": "/docs/3"})],
                         notes="index nav loses docs 3; direct URL still works"),
            task_id="find_code", expect_solvable=True),
        CanarySpec(
            stack=_stack("rules.fail_first_submit",
                         action=[RuleSpec("fail_first_n",
                                          {"method": "POST", "path": "/submit",
                                           "n": 1, "status": 500})],
                         notes="transient failure — a retry must absorb it"),
            task_id="form_fill", expect_solvable=True),
        # Rules negatives — destroy the task's solution; canaries must NOTICE.
        CanarySpec(
            stack=_stack("rules.redact_password_hint",
                         observe=[RuleSpec("redact_text", {"text": "hunter2"})],
                         notes="negative: login hint redacted → unsolvable"),
            task_id="login_flow", expect_solvable=False),
        CanarySpec(
            stack=_stack("rules.redact_pricing_secret",
                         observe=[RuleSpec("redact_text",
                                           {"text": world["docs"]["2"]["secret_word"]})],
                         notes="negative: secret word redacted → unsolvable"),
            task_id="search_and_click", expect_solvable=False),
        CanarySpec(
            stack=_stack("rules.block_search",
                         action=[RuleSpec("block_path", {"path": "/search",
                                                         "status": 404})],
                         notes="negative: search path blocked → unsolvable"),
            task_id="search_and_click", expect_solvable=False),
    ]


@dataclass
class CanarySpec:
    stack: MutationStack
    task_id: str
    expect_solvable: bool


# ---------------------------------------------------------------------------
# Canary runner
# ---------------------------------------------------------------------------

def run_canary(spec: CanarySpec, instance=None) -> dict:
    """One canary: apply stack → mechanical solve → frozen verifier →
    expectation. Also probes the world/evidence firebreak each run."""
    owned = instance is None
    if owned:
        instance = _adapter_EnvInstance()
    try:
        result: dict = {"mutation": spec.stack.name, "task": spec.task_id}
        try:
            instance.apply_stack(spec.stack)
        except Exception as exc:  # noqa: BLE001 — a stack that won't apply
            result.update(solved=False, passed=False,
                          reason=f"stack rejected: {exc}")
            return result

        solver = MECHANICAL_SOLUTIONS[spec.task_id]
        try:
            loop_result = solver(instance, get_task(spec.task_id))
        except Exception as exc:  # noqa: BLE001 — unsolvable is a valid outcome
            result.update(solved=False,
                          reason=f"solver failed: {exc}")
        else:
            task = get_task(spec.task_id)
            try:
                result["solved"] = bool(task["verify"](loop_result, instance.site))
            except Exception as exc:  # noqa: BLE001
                result.update(solved=False, passed=False,
                              reason=f"verifier crashed: {exc}")
                return result
            result.setdefault("reason", "verified" if result["solved"]
                              else "verifier rejected the solved end state")

        # Firebreak probe: evidence keys must be unwritable via the world API.
        try:
            instance.site.load_world_updates({"form_submissions": 99})
            result.update(passed=False,
                          reason="FIREBREAK BROKEN: evidence key accepted by "
                                 "load_world")
            return result
        except ValueError:
            result["firebreak_intact"] = True

        result["passed"] = (result["solved"] == spec.expect_solvable)
        if result["passed"]:
            result["reason"] += f" — as expected (expect_solvable={spec.expect_solvable})"
        return result
    finally:
        instance.reset()
        if owned:
            instance.close()


def run_canary_suite() -> list[dict]:
    return [run_canary(spec) for spec in build_library()]


def _adapter_EnvInstance():
    from adapter import EnvInstance
    return EnvInstance()
