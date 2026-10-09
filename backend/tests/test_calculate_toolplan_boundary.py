"""Tool-plan → calculate-lane boundary regressions (release case 3).

The failed trial (2026-10-06, manifest BRENNAN_RELEASE_MANIFEST) proved a
planner-shaped datasets.calculate plan could bypass the local lanes and the
whole calculation-record pipeline: the dotted service name fell through to
the generic external-integration branch, whose failure block let the model
self-compute the figure in narration — correct-looking reply, no engine
run, no structured record, no job operation.

These tests pin the SHARED boundary (owner directive 3-4): every
planner-shaped datasets.* plan reaches the same local lanes the derivation
path uses; one request = one recorded calculation operation with its own
inputs; narration alone never satisfies the gate.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import contextmanager

os.environ.setdefault("ATOM_TASK_LIFECYCLE_ENABLED", "1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import AgentRegistry, Base, User

LESSON_RATE_150 = {
    "id": "1451b758f7964e1a9d1878704b7ce054",
    "source": "teacher", "teacher_agent_id": "human_supervisor",
    "topic": "service estimates",
    "lesson": ("Service estimate: estimate = ROUNDUP(hours * rate + "
               "materials, 0). Our service rate is 150 per hour."),
    "learned_at": "2026-10-06T13:22:44.344495+00:00", "scope": "global",
}
LESSON_RATE_200 = {
    **LESSON_RATE_150, "id": "rate200-lesson-0001",
    "lesson": ("Service estimate: estimate = ROUNDUP(hours * rate + "
               "materials, 0). Our service rate is 200 per hour."),
}

Q_MISSING = "Estimate this service job using our taught rates."
Q_175 = ("Estimate this service job using our taught rates "
         "with hours=17.5 materials=0")
Q_12 = ("Estimate this service job using our taught rates "
        "with hours=12 materials=0")

_STATE = {}


@pytest.fixture()
def world():
    """Scratch in-memory DB + one trained agent carrying the REAL
    teaching (verbatim lesson from the dev agent). Never the live DB."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def scratch():
        s = factory()
        try:
            yield s
            s.commit()
        finally:
            s.close()

    import core.database as dbmod
    old = dbmod.get_db_session
    dbmod.get_db_session = scratch
    with scratch() as db:
        db.add(User(id="u-boundary", email="boundary@example.com",
                    first_name="Boundary", last_name="Test", role="user",
                    status="active"))
        db.add(AgentRegistry(
            id="boundary-agent", name="boundary agent", status="active",
            category="trainee", module_path="agents.boundary",
            class_name="BoundaryAgent",
            configuration={"learning": {"log": [LESSON_RATE_150]}}))
    _STATE["factory"] = factory
    yield {"user": "u-boundary", "ws": "default"}
    dbmod.get_db_session = old
    engine.dispose()


def _plan(query, service="datasets.calculate"):
    from core.chat_tool_planner import ToolPlan
    return ToolPlan(use_tool=True, service=service, query=query)


def _run(plan, conv, user="u-boundary"):
    from core.chat_tool_planner import execute_tool_plan
    return asyncio.run(execute_tool_plan(
        plan, user, tenant_id="default",
        context={"conversation_id": conv, "workspace_id": "default"}))


def _job_ops(conv):
    from core.goals.goal_run_service import GoalRunService
    from core.goals.goal_service import GoalService
    from core.task_lifecycle import TaskLifecycle
    factory = _STATE["factory"]
    tl = TaskLifecycle(
        GoalRunService(workspace_id="default", tenant_id="default",
                       session_factory=factory),
        GoalService(workspace_id="default", tenant_id="default",
                    session_factory=factory))
    task = tl.find_active_task(conv)
    if not task:
        return []
    out = []
    for o in (task.get("operations") or []):
        # attach_operation_field merges keys FLAT onto the operation
        # record (op["calculation"]), not under an "extra" envelope
        calc = o.get("calculation") or {}
        proposed = calc.get("proposed")
        if isinstance(proposed, dict):
            value = proposed.get("amount")
        else:
            value = getattr(proposed, "amount", proposed)
        # to_record() serializes inputs_snapshot as "inputs", whose own
        # "inputs" key carries the name→value bindings
        snap = calc.get("inputs") or {}
        bindings = snap.get("inputs") or snap
        out.append({"type": o.get("operation_type"),
                    "status": o.get("status"),
                    "value": value,
                    "inputs": bindings})
    return out


def test_dotted_service_reaches_local_lanes(world):
    """The trial-1 failure shape: service='datasets.calculate' must run
    the LOCAL calculate lanes (grounded engine block), never the generic
    external branch's 'nothing usable' failure block."""
    block = _run(_plan(Q_175), "c-boundary-1")
    assert block and "LIVE TOOL RESULTS" in block
    assert "datasets.calculate" in block
    # the external branch's failure shape must be absent
    assert "returned nothing usable" not in block
    assert "not supported" not in block
    # the engine — not the model — produced the value
    assert "the model did not compute this" in block


def test_missing_input_asks_and_records_nothing(world):
    block = _run(_plan(Q_MISSING), "c-boundary-2")
    assert block and "INPUT NEEDED" in block
    assert "hours" in block and "materials" in block
    assert _job_ops("c-boundary-2") == []


def test_answered_inputs_compute_and_record_one_operation(world):
    block = _run(_plan(Q_175), "c-boundary-3")
    assert block and ("2625" in block or "2,625" in block)
    ops = _job_ops("c-boundary-3")
    calc = [o for o in ops if o["type"] == "calculate"]
    assert len(calc) == 1
    assert calc[0]["status"] == "applied"
    assert str(calc[0]["value"]).startswith("2625")
    assert calc[0]["inputs"].get("hours") == "17.5"
    assert calc[0]["inputs"].get("materials") == "0"


def test_changed_input_recalc_is_its_own_operation(world):
    _run(_plan(Q_175), "c-boundary-4")
    _run(_plan(Q_12), "c-boundary-4")
    calc = [o for o in _job_ops("c-boundary-4") if o["type"] == "calculate"]
    assert len(calc) == 2
    values = sorted(str(c["value"]) for c in calc)
    assert values == ["1800", "2625"]
    # each op carries ITS OWN inputs
    ins = {c["inputs"].get("hours") for c in calc}
    assert ins == {"12", "17.5"}


def test_duplicate_dispatch_does_not_duplicate_operations(world):
    _run(_plan(Q_175), "c-boundary-5")
    _run(_plan(Q_175), "c-boundary-5")
    calc = [o for o in _job_ops("c-boundary-5") if o["type"] == "calculate"]
    assert len(calc) == 1


def test_two_conversations_use_their_own_teaching(world):
    """Two conversations, different taught rates: each computes and
    records from ITS OWN lesson — no cross-conversation record reuse."""
    import core.database as dbmod
    with dbmod.get_db_session() as db:
        db.query(AgentRegistry).filter(
            AgentRegistry.id == "boundary-agent").update(
            {"configuration": {"learning": {"log": [LESSON_RATE_200]}}})
    block = _run(_plan(Q_175), "c-boundary-6")
    assert block and "3500" in block
    ops6 = [o for o in _job_ops("c-boundary-6") if o["type"] == "calculate"]
    assert len(ops6) == 1
    assert str(ops6[0]["value"]).startswith("3500")


def test_missing_input_follow_up_completes_and_records(world):
    """The trial's first two turns in ONE conversation: the missing-input
    ask records nothing (INPUT NEEDED), and the answered follow-up
    completes the calculation and records exactly one operation bound
    to the supplied inputs."""
    ask = _run(_plan(Q_MISSING), "c-boundary-7")
    assert ask and "INPUT NEEDED" in ask
    assert _job_ops("c-boundary-7") == []
    answer = _run(_plan(Q_175), "c-boundary-7")
    assert answer and ("2625" in answer or "2,625" in answer)
    calc = [o for o in _job_ops("c-boundary-7") if o["type"] == "calculate"]
    assert len(calc) == 1
    assert calc[0]["status"] == "applied"
    assert str(calc[0]["value"]).startswith("2625")
    assert calc[0]["inputs"].get("hours") == "17.5"
    assert calc[0]["inputs"].get("materials") == "0"


def test_both_dispatch_paths_converge_on_one_operation(world):
    """Planner path and derivation-seam path encountering the SAME
    request: both enter execute_tool_plan's calculate lane, whose dedup
    key (request identity + validated context incl. workspace) must
    serve the SAME block — one engine run, one recorded operation."""
    from integrations.chat_orchestrator import _derivation_supplement
    from core.chat_tool_planner import execute_tool_plan

    async def _turn():
        seam_block = await _derivation_supplement(
            Q_175, "u-boundary", None, None, None,
            conversation_id="c-boundary-8", workspace_id="default")
        planner_block = await execute_tool_plan(
            _plan(Q_175), "u-boundary", tenant_id="default",
            context={"conversation_id": "c-boundary-8",
                     "workspace_id": "default"})
        return seam_block, planner_block

    seam_block, planner_block = asyncio.run(_turn())
    assert seam_block and "LIVE TOOL RESULTS" in seam_block
    # the second dispatch reuses the SAME operation's block (dedup hit)
    assert planner_block == seam_block
    calc = [o for o in _job_ops("c-boundary-8") if o["type"] == "calculate"]
    assert len(calc) == 1
    assert str(calc[0]["value"]).startswith("2625")


def test_persistence_failure_is_not_durable_completion(world, monkeypatch):
    """When the job write fails, the block states it in the same breath
    as the result, the published record carries persisted=False, and the
    narration guard rejects 'saved/recorded' claims for that turn."""
    import integrations.chat_orchestrator as orch
    import core.pricing_calculation as P

    monkeypatch.setattr(orch, "_task_lifecycle_for", lambda *a, **k: None)
    block = _run(_plan(Q_175), "c-boundary-9")
    assert block and "2625" in block.replace(",", "")
    # the block itself refuses durable framing
    assert "RECORDING FAILED" in block
    assert "NOT be persisted" in block
    # the published record carries the durable outcome
    allowance = P._calc_narration_allowance(
        block, expected_conversation_id="c-boundary-9",
        expected_user_id="u-boundary")
    assert allowance.get("persisted") is False
    assert any("NOT recorded" in lim
               for lim in allowance.get("limitations") or [])
    # a durable-completion claim is a narration violation; the bare
    # computed figure alone is not
    from integrations.chat_orchestrator import _calc_narration_violations

    claim = _calc_narration_violations(
        "The estimate is 2625 and I have saved it to the job.",
        allowance)
    assert any("saved" in v for v in claim)
    plain = _calc_narration_violations(
        "The estimate is 2625; the recording failed, so it is not "
        "recorded yet.", allowance)
    assert not any("saved" in v or "recorded" in v for v in plain)


def test_incomplete_result_records_waiting_without_value(world):
    """Status semantics are not inflated: an engine-incomplete result
    (unsupported function) publishes NO proposed value, its job
    operation stays WAITING, and the block says NOT COMPUTED."""
    block = _run(_plan("calculate expression NPV(hours, rate) "
                       "with hours=2 rate=150"), "c-boundary-10")
    assert block and "NOT COMPUTED" in block
    ops = _job_ops("c-boundary-10")
    assert len(ops) == 1
    assert ops[0]["type"] == "calculate"
    assert ops[0]["status"] == "waiting"
    # no value was proposed, so nothing can be narrated as the result
    assert ops[0]["value"] is None
    # the block names the real gap — the unsupported function — and
    # never a partial value
    assert "NPV" in block


Q_ANSWER = "17.5 hours, no materials."
Q_RECALC = "Recalculate \u2014 12 hours."


def _pending_question(conv):
    from core.pricing_calculation import _pending_calc_question

    return _pending_calc_question(conv, "default")


def test_bare_answer_and_recalc_route_deterministically(world):
    """The exact case-3 trial turns (candidate 78ba06084 trials 1-2
    failed here): T1 asks (no calculate op — the driver contract), T2
    is the owner's BARE answer, T3 a BARE recalculate. Both follow-ups
    resolve from DURABLE job state — pending question, then the last
    applied taught-expression record — each recording its OWN operation
    with its own inputs."""
    ask = _run(_plan(Q_MISSING), "c-boundary-11")
    assert ask and "INPUT NEEDED" in ask
    calc1 = [o for o in _job_ops("c-boundary-11")
             if o["type"] == "calculate"]
    assert calc1 == []  # the asking turn records NO calculate operation
    pending = _pending_question("c-boundary-11")
    assert pending and pending.get("item") == "Service estimate"
    assert sorted(pending["inputs"]["missing"]) == ["hours", "materials"]

    answer = _run(_plan(Q_ANSWER), "c-boundary-11")
    assert answer and "2625" in answer.replace(",", "")
    calc = [o for o in _job_ops("c-boundary-11")
            if o["type"] == "calculate"]
    assert len(calc) == 1
    assert calc[0]["status"] == "applied"
    assert str(calc[0]["value"]).startswith("2625")
    assert calc[0]["inputs"].get("hours") == "17.5"
    assert calc[0]["inputs"].get("materials") == "0"
    # the question this turn answered is settled
    assert _pending_question("c-boundary-11") is None

    recalc = _run(_plan(Q_RECALC), "c-boundary-11")
    assert recalc and "1800" in recalc.replace(",", "")
    calc = [o for o in _job_ops("c-boundary-11")
            if o["type"] == "calculate"]
    assert len(calc) == 2
    assert str(calc[1]["value"]).startswith("1800")
    assert calc[1]["inputs"].get("hours") == "12"
    assert calc[1]["inputs"].get("materials") == "0"


def test_partial_answer_keeps_asking_without_new_record(world):
    """An answer that binds only SOME missing inputs asks again for the
    rest — no new calculate operation, the pending question stays open."""
    _run(_plan(Q_MISSING), "c-boundary-12")
    partial = _run(_plan("17.5 hours"), "c-boundary-12")
    assert partial and "INPUT NEEDED" in partial
    assert "materials" in partial
    calc = [o for o in _job_ops("c-boundary-12")
            if o["type"] == "calculate"]
    assert calc == []
    assert _pending_question("c-boundary-12") is not None


class TestRequestIdentityKey:
    """Final owner correction (2026-10-06): the durable operation key is
    REQUEST/EXECUTION identity + calculation identity. Content alone
    reattributed a later legitimate request to an earlier operation."""

    def _run_exec(self, query, conv, execution_id, user="u-boundary"):
        from core.chat_tool_planner import ToolPlan, execute_tool_plan
        plan = ToolPlan(use_tool=True, service="datasets.calculate",
                        query=query)
        return asyncio.run(execute_tool_plan(
            plan, user, tenant_id="default",
            context={"conversation_id": conv, "workspace_id": "default",
                     "execution_id": execution_id}))

    def _ops_with_attribution(self, conv):
        from core.goals.goal_run_service import GoalRunService
        from core.goals.goal_service import GoalService
        from core.task_lifecycle import TaskLifecycle
        tl = TaskLifecycle(
            GoalRunService(workspace_id="default", tenant_id="default",
                           session_factory=_STATE["factory"]),
            GoalService(workspace_id="default", tenant_id="default",
                        session_factory=_STATE["factory"]))
        task = tl.find_active_task(conv)
        if not task:
            return []
        return [{"id": o.get("operation_id"),
                 "exec": o.get("execution_id"),
                 "amount": (((o.get("calculation") or {})
                             .get("proposed") or {}).get("amount"))}
                for o in (task.get("operations") or [])
                if o.get("operation_type") == "calculate"]

    def test_same_request_two_arms_and_retry_one_operation(self, world):
        """Both dispatch arms of ONE request (different query texts) and
        a retry of that request replay to the SAME operation."""
        conv = "c-reqid-1"
        b1 = self._run_exec(
            "Estimate this service job using our taught rates "
            "with hours=17.5 materials=0", conv, "exec-A")
        b2 = self._run_exec(
            "Estimate this service job using our taught rates — 17.5 "
            "hours, and no materials.", conv, "exec-A")
        assert b1 and "2625" in b1
        assert b2 and "2625" in b2
        # RETRY of the same request: replays to the SAME operation id
        first_id = self._ops_with_attribution(conv)[0]["id"]
        self._run_exec(
            "Estimate this service job using our taught rates "
            "with hours=17.5 materials=0", conv, "exec-A")
        ops = self._ops_with_attribution(conv)
        assert len(ops) == 1, ops
        assert ops[0]["id"] == first_id
        assert ops[0]["exec"] == "exec-A"
        assert str(ops[0]["amount"]).startswith("2625")

    def test_new_request_identical_content_gets_own_operation(self, world):
        """A LATER legitimate request with identical inputs and result
        records its OWN separately attributed operation — the earlier
        operation is not reused and the attribution is not lost."""
        conv = "c-reqid-2"
        self._run_exec(
            "Estimate this service job using our taught rates "
            "with hours=17.5 materials=0", conv, "exec-1")
        self._run_exec(
            "Estimate this service job using our taught rates "
            "with hours=17.5 materials=0", conv, "exec-2")
        ops = self._ops_with_attribution(conv)
        assert len(ops) == 2, ops
        assert {o["exec"] for o in ops} == {"exec-1", "exec-2"}
        assert ops[0]["id"] != ops[1]["id"]
        assert all(str(o["amount"]).startswith("2625") for o in ops)


# -- practical-value run pv-B (2026-10-09): natural-phrasing binding ----
# The live run bound hours=9 but LOST materials to the connector in
# "$120 in materials", so the engine never ran and the reply narrated a
# model-computed figure. These pins hold the full chain: natural inputs
# bind, ONE durable operation records, the block carries the operation
# reference, and the unrecorded-figure guard cannot be exempted by an
# open pending ask.

Q_PV = ("Estimate this service job using our taught rates: "
        "9 hours, $120 in materials.")
Q_COLON = ("Estimate this service job using our taught rates. "
           "hours: 12, materials: $40")


def test_natural_connector_phrasing_binds_and_records(world):
    """'$120 in materials' binds materials — the engine runs, exactly
    ONE durable calculate operation records with ALL THREE inputs, and
    the grounded block carries the operation reference the reply can
    cite (owner assignment step 3)."""
    block = _run(_plan(Q_PV), "c-pv-1")
    assert block and ("1470" in block.replace(",", ""))
    assert "engine-computed" in block
    assert "[calc:result_id=" in block
    calc = [o for o in _job_ops("c-pv-1") if o["type"] == "calculate"]
    assert len(calc) == 1
    assert calc[0]["status"] == "applied"
    assert str(calc[0]["value"]).startswith("1470")
    ins = calc[0]["inputs"]
    assert ins.get("hours") == "9"
    assert ins.get("materials") == "120"
    assert ins.get("rate") == "150"  # the taught default, still the engine's


def test_taught_rates_colon_idiom_does_not_capture(world):
    """The idiomatic opener 'using our taught rates: 14 hours' is
    PHRASING, not a key:value input — the colon must not bind
    rate=<next number> when that number is immediately followed by
    another input name (the mis-bind computed 9*9+120=201; the pin
    caught it before it could ship)."""
    block = _run(_plan(
        "Estimate this service job using our taught rates: 14 hours, "
        "no materials."), "c-pv-2")
    assert block and "2100" in block.replace(",", "")
    calc = [o for o in _job_ops("c-pv-2") if o["type"] == "calculate"]
    assert len(calc) == 1
    ins = calc[0]["inputs"]
    assert ins.get("hours") == "14"
    assert ins.get("materials") == "0"
    assert ins.get("rate") == "150"  # taught default — NOT 14


def test_true_colon_pairs_bind_their_own_values(world):
    """Owner release-close step 2, correct-binding branch: a REAL
    key:value list ('hours: 12, materials: $40') binds each input to
    ITS OWN value — never the phrasational colon mis-bind."""
    block = _run(_plan(
        "Estimate this service job using our taught rates. "
        "hours: 12, materials: $40"), "c-pv-2b")
    assert block and "1840" in block.replace(",", "")
    calc = [o for o in _job_ops("c-pv-2b") if o["type"] == "calculate"]
    assert len(calc) == 1
    ins = calc[0]["inputs"]
    assert ins.get("hours") == "12"
    assert ins.get("materials") == "40"
    assert ins.get("rate") == "150"  # taught default — untouched


def test_same_inputs_two_conversations_two_owned_operations(world):
    """Owner release-close step 4: repeated identical inputs in
    DIFFERENT conversations each record their own correctly attributed
    operation (per-conversation idempotency), while a retry inside one
    conversation does not duplicate (pinned above)."""
    _run(_plan(Q_PV), "c-iso-A")
    _run(_plan(Q_PV), "c-iso-B")
    ops_a = [o for o in _job_ops("c-iso-A") if o["type"] == "calculate"]
    ops_b = [o for o in _job_ops("c-iso-B") if o["type"] == "calculate"]
    assert len(ops_a) == 1 and len(ops_b) == 1
    assert str(ops_a[0]["value"]).startswith("1470")
    assert str(ops_b[0]["value"]).startswith("1470")
    for o in (ops_a[0], ops_b[0]):
        assert o["inputs"].get("hours") == "9"
        assert o["inputs"].get("materials") == "120"


def test_missing_input_block_has_no_computed_figure(world):
    """Negative boundary (owner assignment step 4), block level: when
    inputs are missing the ask records NO operation and presents NO
    computed figure — nothing that could be narrated as an engine
    result."""
    block = _run(_plan(Q_MISSING), "c-pv-3")
    assert block and "INPUT NEEDED" in block
    assert "do not guess" in block.lower() or "do not\n                              guess" in block
    assert _job_ops("c-pv-3") == []
    # no engine value anywhere in the ask block
    import re as _re
    assert not _re.search(r"[Vv]alue \(computed\)", block)
    assert "engine-computed" not in block


def test_authority_figure_detector_flags_pvB_shape(world):
    """Negative boundary (owner assignment step 4), guard level: the
    pv-B reply — money figure + 'taught formula' authority + a soft
    flag that is NOT a disclosure phrase — must be flagged, while an
    honestly disclosed figure and a plain ask are not. The orchestrator
    replacement condition consumes this detector; the pv-B escape
    (pending-ask-open exemption) is removed at the call site."""
    from integrations.chat_orchestrator import (
        _reply_claims_unrecorded_teaching_figure as detect,
    )

    pvb_reply = (
        "Using the taught formula Service estimate: ROUNDUP(hours * rate "
        "+ materials, 0):\n\n9 \u00d7 150 = 1,350 \u2192 1,350 + 120 = "
        "1,470 \u2192 estimated service job: $1,470\n\nOne flag for "
        "transparency: the calculator run on my side bound hours = 9 and "
        "rate = 150 but returned \u201cmaterials: INPUT NEEDED\u201d "
        "\u2014 it did not independently bind the $120. So the $1,470 "
        "follows from applying the taught formula to the materials "
        "figure you supplied.")
    assert detect(pvb_reply), "the pv-B shape must be flagged"

    disclosed = ("$1,470 is the model's arithmetic, not run through the "
                 "engine \u2014 no record exists.")
    assert not detect(disclosed), "honest disclosure must pass"

    plain_ask = ("Which materials cost should I use for the estimate?")
    assert not detect(plain_ask), "ask-only replies carry no figure"
