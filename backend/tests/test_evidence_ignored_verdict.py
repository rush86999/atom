# -*- coding: utf-8 -*-
"""``evidence_ignored``: a real judgement on a real output, in its own class.

THE INCIDENT THIS PINS
======================

A derivation ask delivered the matched workbook row AND its formulas in the
prompt (``FORMULAS FOR THE MATCHED ROW``, row 235, six formulas). With
byte-identical evidence, one model cited the row and walked the chain while
another replied "the required live-data lookup failed" / asked the user to
confirm which record they meant. The user sees "it didn't look", and nothing in
the ledger recorded it: the outcome row scored 0.7–0.8 (the reply is fluent),
the grounding check never ran on it (the guard is skipped for row-citing
derivations, and a non-citing reply has no figures to check), and the routing
therefore kept choosing the declining route.

WHAT IS ASSERTED HERE
=====================

1. The assessment is a DISTINCT class — not fabrication (nothing was invented),
   not a grounding pass, not a refusal.
2. Generation accounting counts it separately and does NOT let it enlarge the
   fabrication denominator: the bench's rate must stay a statement about
   honesty. A compliance failure must not dilute it, and an invention must not
   dilute the compliance rate.
3. One verdict SLOT per generation, ordered by severity, so a later grounding
   marker cannot erase the judgement and a fabrication is never downgraded.
4. Route attribution: the verdict carries the PROVIDER half of the route, which
   is what makes the fabrication bench work at all — see
   ``TestBenchRouteAttribution``, where the live table's naming
   (``z-ai/glm-5.3-flash`` served by ``openrouter``) is what exposed the bench's
   dead key.
5. The corrective retry goes to a DIFFERENT route, preferring a different
   provider, and keeps the current route only when the ranking offers no other.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm.fabrication_accounting import (  # noqa: E402
    EVIDENCE_VERDICTS,
    FIGURE_VERDICT_RULE,
    FABRICATION_VERDICTS,
    GROUNDING_EVALUATED_VERDICTS,
    account_generations,
    verdict_rank,
)
from core.llm.response_quality import assess_response_quality  # noqa: E402


def _row(row_id, turn, model="m1", score=0.25, features=None):
    return (row_id, turn, model, score, features)


# ---------------------------------------------------------------------------
# 1. The assessment
# ---------------------------------------------------------------------------

class TestEvidenceIgnoredAssessment:
    def test_it_is_a_distinct_low_satisfaction_class(self):
        q = assess_response_quality(
            content="The lookup returned nothing — please confirm the record.",
            evidence_ignored=["row 235 (delivered, not cited)"],
        )
        assert q.issues == ["evidence_ignored"]
        assert q.quality_satisfied is False
        assert q.success is True, "the call DID return — this is a content judgement"
        # Above the fabrication band (0.15): a score inside it would be read as
        # outage-or-invention with no provenance. Below a refusal (0.4): the
        # model contradicts its own prompt, so it is worse than declining.
        assert q.quality_score == pytest.approx(0.25)

    def test_it_is_not_fabrication_and_not_a_grounding_pass(self):
        q = assess_response_quality(content="x", evidence_ignored=["row 235"])
        assert "evidence_ignored" not in FABRICATION_VERDICTS
        assert "evidence_ignored" not in GROUNDING_EVALUATED_VERDICTS
        assert "evidence_ignored" in EVIDENCE_VERDICTS
        assert q.issues[0] not in ("unsupported_figures", "ungrounded_claims")

    def test_an_invented_figure_still_outranks_it(self):
        """A reply that invents AND ignores is a fabrication: the stronger
        claim about the output wins, whichever order the caller passes them."""
        q = assess_response_quality(
            content="x",
            unsupported_figures=["8880"],
            evidence_ignored=["row 235"],
        )
        assert q.issues[0] == "unsupported_figures"
        assert "evidence_ignored" not in q.issues

    def test_no_signal_no_verdict(self):
        q = assess_response_quality(content="A normal substantive answer " * 5)
        assert q.quality_satisfied is True
        assert "evidence_ignored" not in q.issues


# ---------------------------------------------------------------------------
# 2. Accounting: its own class, its own denominator
# ---------------------------------------------------------------------------

class TestAccountingKeepsTheClassesSeparate:
    def test_it_is_counted_but_not_in_the_fabrication_denominator(self):
        acc = account_generations([
            _row("r1", "t1", features={"verdict": "evidence_ignored"}),
        ])
        assert acc.evidence_ignored == 1
        assert acc.fabricated == 0
        assert acc.grounded_ok == 0
        assert acc.generations == 0, (
            "a compliance failure must not enter the denominator the "
            "fabrication bench divides by")
        assert acc.rate is None
        assert acc.evidence_ignored_rate == pytest.approx(1.0)

    def test_a_fabrication_still_reads_one_hundred_percent(self):
        """THE dilution regression: 1 fabrication + 1 ignored-evidence
        generation in the window must NOT read as 0.5. At 0.5 the bench still
        fires, but at 3 fabrications among 12 judged outputs it would read 0.25
        — the threshold — instead of 1.0, which is how a fabricator survives."""
        acc = account_generations([
            _row("r1", "t1", score=0.1, features={"verdict": "unsupported_figures"}),
            _row("r2", "t2", features={"verdict": "evidence_ignored"}),
        ])
        assert acc.fabricated == 1
        assert acc.evidence_ignored == 1
        assert acc.generations == 1
        assert acc.rate == pytest.approx(1.0), "the compliance class diluted honesty"

    def test_the_compliance_rate_has_its_own_denominator(self):
        acc = account_generations([
            _row("r1", "t1", score=0.9, features={"verdict": "grounding_ok"}),
            _row("r2", "t2", score=0.9, features={"verdict": "grounding_ok"}),
            _row("r3", "t3", score=0.25, features={"verdict": "evidence_ignored"}),
        ])
        assert acc.grounded_ok == 2
        assert acc.evidence_ignored == 1
        assert acc.judged_outputs == 3
        assert acc.evidence_ignored_rate == pytest.approx(1 / 3)

    def test_an_ignored_evidence_row_is_not_a_grounding_pass(self):
        """No positive honesty provenance: the grounding check may never have
        run on this generation, and "nothing was checked" must not read clean."""
        acc = account_generations([
            _row("r1", "t1", features={"verdict": "evidence_ignored"}),
        ])
        assert acc.grounded_ok == 0
        assert acc.clean == 0
        assert acc.unknown == 0, "it is a judged output, not an unknown"
        assert acc.availability == 0

    def test_the_stronger_verdict_classifies_a_generation_carrying_both(self):
        acc = account_generations([
            _row("r1", "t1", score=0.9, features={"verdict": "grounding_ok"}),
            _row("r2", "t1", score=0.25, features={"verdict": "evidence_ignored"}),
        ])
        assert acc.rows == 2
        assert acc.evidence_ignored == 1
        assert acc.grounded_ok == 0, (
            "a generation carrying an output judgement must not also be "
            "counted as a grounding pass")
        assert acc.judged_outputs == 1

    def test_it_appears_in_the_report_dict(self):
        acc = account_generations([
            _row("r1", "t1", features={"verdict": "evidence_ignored"}),
        ])
        report = acc.as_dict()
        assert report["evidence_ignored"] == 1
        assert report["judged_outputs"] == 1
        assert report["evidence_ignored_rate"] == pytest.approx(1.0)

    def test_severity_order_is_explicit(self):
        assert verdict_rank("unsupported_figures") > verdict_rank("evidence_ignored")
        assert verdict_rank("evidence_ignored") > verdict_rank("grounding_ok")
        assert verdict_rank("grounding_ok") > verdict_rank(None)
        assert verdict_rank("some_future_verdict") == 0


# ---------------------------------------------------------------------------
# 3./4. Persistence: one verdict slot, route provenance
# ---------------------------------------------------------------------------

@pytest.fixture()
def scratch_feedback_db(tmp_path, monkeypatch):
    """Point core.database.SessionLocal at a scratch SQLite file."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import core.database as database
    from core.models import LLMRoutingFeedback

    db_path = tmp_path / "feedback.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    LLMRoutingFeedback.__table__.create(engine, checkfirst=True)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", Session)
    yield {"engine": engine, "Session": Session, "path": db_path}
    engine.dispose()


def _writer():
    from core.learning_llm_router import LearningBasedRouter

    return LearningBasedRouter.__new__(LearningBasedRouter)


def _feedback(turn, model="z-ai/glm-5.3-flash", score=0.25, provider=None,
              task="question_answering", verdict=None):
    from core.learning_llm_router import RoutingFeedback

    fb = RoutingFeedback(
        routing_result_id=turn,
        tenant_id="default",
        task_type=task,
        model_id=model,
        success=True,
        quality_satisfied=score > 0.15,
        cost_within_budget=True,
        user_satisfaction=score,
        actual_cost=0.0,
        actual_latency_ms=10.0,
        provider_id=provider,
    )
    if verdict:
        fb.verdict = verdict
    return fb


def _rows(scratch):
    from core.models import LLMRoutingFeedback

    with scratch["Session"]() as db:
        return [
            (r.id, r.routing_result_id, r.model_id, r.user_satisfaction,
             r.prompt_features)
            for r in db.query(LLMRoutingFeedback)
            .order_by(LLMRoutingFeedback.created_at.asc()).all()
        ]


def _features(raw):
    return json.loads(raw) if isinstance(raw, str) else (raw or {})


class TestVerdictSlotPrecedence:
    def _evaluated(self, writer, turn, provider=None):
        writer._persist_feedback(
            _feedback(turn, score=0.9, provider=provider,
                      verdict="grounding_ok"),
            {"verdict": "grounding_ok"})

    def _ignored(self, writer, turn, provider=None):
        writer._persist_feedback(
            _feedback(turn, provider=provider, verdict="evidence_ignored"),
            {"verdict": "evidence_ignored"})

    def test_ignored_evidence_replaces_a_grounding_marker(
            self, scratch_feedback_db):
        """Both are true of the reply, but the judgement is the stronger claim
        and it must reach the row — the quality fields follow it, or a restart
        would restore the router's old opinion of the model."""
        writer = _writer()
        self._evaluated(writer, "t1")
        self._ignored(writer, "t1")
        rows = _rows(scratch_feedback_db)
        assert len(rows) == 1, "the judgement added a second row for one generation"
        stored = _features(rows[0][4])
        assert stored["verdict"] == "evidence_ignored"
        assert rows[0][3] == pytest.approx(0.25), (
            "the row kept the outcome's score while claiming ignored evidence")

    def test_a_grounding_marker_cannot_erase_the_judgement(
            self, scratch_feedback_db):
        writer = _writer()
        self._ignored(writer, "t1")
        self._evaluated(writer, "t1")
        rows = _rows(scratch_feedback_db)
        assert len(rows) == 1
        assert _features(rows[0][4])["verdict"] == "evidence_ignored"

    def test_a_fabrication_is_never_downgraded(self, scratch_feedback_db):
        writer = _writer()
        writer._persist_feedback(
            _feedback("t1", score=0.1, verdict="unsupported_figures"),
            {"verdict": "unsupported_figures"})
        self._ignored(writer, "t1")
        self._evaluated(writer, "t1")
        rows = _rows(scratch_feedback_db)
        assert len(rows) == 1
        assert _features(rows[0][4])["verdict"] == "unsupported_figures"
        assert rows[0][3] == pytest.approx(0.1)

    def test_repeating_the_judgement_is_idempotent(self, scratch_feedback_db):
        writer = _writer()
        self._ignored(writer, "t1")
        for _ in range(3):
            self._ignored(writer, "t1")
        assert len(_rows(scratch_feedback_db)) == 1

    def test_the_provider_half_is_stored_with_the_verdict(
            self, scratch_feedback_db):
        writer = _writer()
        self._evaluated(writer, "t1", provider="openrouter")
        self._ignored(writer, "t1", provider="openrouter")
        stored = _features(_rows(scratch_feedback_db)[0][4])
        assert stored["verdict"] == "evidence_ignored"
        assert stored["route_provider"] == "openrouter"

    def test_an_unattributed_verdict_stays_unattributed(
            self, scratch_feedback_db):
        """No provider known → no stamp. A fabricated attribution would aim a
        route-scoped action at a gateway that never served the generation."""
        writer = _writer()
        self._ignored(writer, "t1", provider=None)
        assert "route_provider" not in _features(_rows(scratch_feedback_db)[0][4])


# ---------------------------------------------------------------------------
# 5. The signal the routing layer consumes
# ---------------------------------------------------------------------------

class TestRecordEvidenceIgnoredSignal:
    @pytest.mark.asyncio
    async def test_it_records_the_verdict_route_and_task(self, monkeypatch):
        from core.learning_llm_router import LearningBasedRouter
        from core.llm import learning_router_registry as reg

        seen = {}

        def fake_persist(self, feedback, features):
            seen["feedback"] = feedback
            seen["features"] = features

        monkeypatch.setattr(LearningBasedRouter, "_persist_feedback", fake_persist)
        monkeypatch.setattr(reg, "get_learning_router_instance",
                            lambda observe_only=False: None)

        ok = await reg.record_evidence_ignored(
            model_id="z-ai/glm-5.3-flash",
            provider_id="openrouter",
            task_type="question_answering",
            tenant_id="default",
            routing_result_id="turn-7",
        )
        assert ok is True
        fb = seen["feedback"]
        assert fb.verdict == "evidence_ignored"
        assert fb.provider_id == "openrouter"
        assert fb.model_id == "z-ai/glm-5.3-flash"
        assert fb.routing_result_id == "turn-7", "the verdict must judge ITS generation"
        assert fb.user_satisfaction == pytest.approx(0.25)
        assert fb.quality_satisfied is False

    @pytest.mark.asyncio
    async def test_no_model_no_row(self, monkeypatch):
        from core.llm import learning_router_registry as reg

        assert await reg.record_evidence_ignored(model_id="") is False

    @pytest.mark.asyncio
    async def test_a_broken_writer_never_raises(self, monkeypatch):
        from core.learning_llm_router import LearningBasedRouter
        from core.llm import learning_router_registry as reg

        def boom(self, feedback, features):
            raise RuntimeError("db down")

        monkeypatch.setattr(LearningBasedRouter, "_persist_feedback", boom)
        monkeypatch.setattr(reg, "get_learning_router_instance",
                            lambda observe_only=False: None)
        assert await reg.record_evidence_ignored(model_id="m1") is False


# ---------------------------------------------------------------------------
# 6. Bench attribution (the dead-key regression)
# ---------------------------------------------------------------------------

def _bench_stub(monkeypatch, min_events=1, rate=0.25):
    from core.llm.byok_handler import BYOKHandler

    monkeypatch.setattr(BYOKHandler, "_FAB_BENCH_MIN_EVENTS", min_events)
    monkeypatch.setattr(BYOKHandler, "_FAB_BENCH_RATE", rate)
    monkeypatch.setenv("ATOM_FABRICATION_BENCH", "1")
    return BYOKHandler.__new__(BYOKHandler)


class TestBenchRouteAttribution:
    """The bench queried ``f"{provider_id}/{model_id}"`` — a key never written.

    Measured on the live table 2026-09-16: 667 rows under
    ``z-ai/glm-5.3-flash``, ZERO under ``openrouter/z-ai/glm-5.3-flash``, while
    7/19 of that model's evaluated generations carried fabrication verdicts. The
    safety exclusion had never fired for any gateway-served model.
    """

    MODEL = "z-ai/glm-5.3-flash"

    def _fabrications(self, writer, provider, turns, rule=FIGURE_VERDICT_RULE):
        for turn in turns:
            features = {"verdict": "unsupported_figures"}
            if rule:
                features["verdict_rule"] = rule
            writer._persist_feedback(
                _feedback(turn, model=self.MODEL, score=0.1, provider=provider,
                          verdict="unsupported_figures"),
                features)

    def test_a_vendor_namespaced_model_is_reachable_by_the_bench(
            self, scratch_feedback_db, monkeypatch):
        writer = _writer()
        self._fabrications(writer, "openrouter", ("t1", "t2", "t3"))
        handler = _bench_stub(monkeypatch, min_events=3, rate=0.25)
        assert handler._fabrication_benched("openrouter", self.MODEL) is True

    def test_another_gateway_serving_the_same_identifier_is_not_benched(
            self, scratch_feedback_db, monkeypatch):
        """Route identity, not model identity: one gateway's verdicts must not
        exclude a different provider's route for the same model string."""
        writer = _writer()
        self._fabrications(writer, "openrouter", ("t1", "t2", "t3"))
        handler = _bench_stub(monkeypatch, min_events=1, rate=0.25)
        assert handler._fabrication_benched("opencode-go", self.MODEL) is False

    def test_legacy_rows_without_a_provider_stamp_still_count(
            self, scratch_feedback_db, monkeypatch):
        """A missing PROVIDER stamp must not discard a verdict — the ledger is
        the record, and the route filter is a refinement of it."""
        writer = _writer()
        self._fabrications(writer, None, ("t1", "t2", "t3"))
        handler = _bench_stub(monkeypatch, min_events=3, rate=0.25)
        assert handler._fabrication_benched("openrouter", self.MODEL) is True

    def test_a_verdict_from_an_unknown_rule_cannot_exclude_a_route(
            self, scratch_feedback_db, monkeypatch):
        """The 27 rows the unsound figure rule wrote carry no rule stamp. They
        stay in the ledger but may not exclude a route: the rule that produced
        them called correctly computed derivation figures "invented" (the live
        log names the chain — 5,625.30 / 7,518 / 1,893.70). Excluding a model
        on that evidence is the manufactured-observation failure, inverted."""
        writer = _writer()
        self._fabrications(writer, "openrouter", ("t1", "t2", "t3"), rule=None)
        handler = _bench_stub(monkeypatch, min_events=1, rate=0.25)
        assert handler._fabrication_benched("openrouter", self.MODEL) is False

    def test_the_rate_ignores_the_compliance_class(
            self, scratch_feedback_db, monkeypatch):
        """One fabrication among three judged outputs is 1/1 evaluated
        generations, not 1/4: the bench must fire."""
        writer = _writer()
        self._fabrications(writer, "openrouter", ("t1",))
        writer._persist_feedback(
            _feedback("t2", model=self.MODEL, provider="openrouter",
                      verdict="grounding_ok"),
            {"verdict": "grounding_ok"})
        for turn in ("t3", "t4", "t5"):
            writer._persist_feedback(
                _feedback(turn, model=self.MODEL, provider="openrouter",
                          verdict="evidence_ignored"),
                {"verdict": "evidence_ignored"})
        handler = _bench_stub(monkeypatch, min_events=1, rate=0.5)
        assert handler._fabrication_benched("openrouter", self.MODEL) is True


# ---------------------------------------------------------------------------
# 7./8. The corrective retry route
# ---------------------------------------------------------------------------

class TestCrossRouteRetrySelection:
    def _pick(self, routes, served):
        from integrations.chat_orchestrator import _cross_route_retry_route

        return _cross_route_retry_route(routes, served)

    def test_a_different_provider_wins(self):
        served = ("openrouter", "z-ai/glm-5.3-flash")
        assert self._pick(
            [("openrouter", "qwen/qwen3.8-flash"), ("deepseek", "deepseek-flash")],
            served) == ("deepseek", "deepseek-flash")

    def test_a_different_model_on_the_same_provider_beats_the_same_model_elsewhere(self):
        served = ("openrouter", "z-ai/glm-5.3-flash")
        assert self._pick(
            [("openrouter", "z-ai/glm-5.3-flash"), ("deepseek", "z-ai/glm-5.3-flash"),
             ("openrouter", "qwen/qwen3.8-flash")],
            served) == ("openrouter", "qwen/qwen3.8-flash")

    def test_a_route_change_beats_repeating_the_failed_attempt(self):
        served = ("openrouter", "m1")
        assert self._pick([("deepseek", "m1")], served) == ("deepseek", "m1")

    def test_no_other_route_means_no_change(self):
        served = ("openrouter", "m1")
        assert self._pick([], served) is None
        assert self._pick([("openrouter", "m1")], served) is None
        assert self._pick(None, served) is None

    def test_malformed_route_entries_are_ignored(self):
        served = ("openrouter", "m1")
        assert self._pick([("x",), ("", "m2"), ("p", "m2")], served) == ("p", "m2")


class TestGuardWiring:
    """Source-level assertions, in this suite's existing style: the guard must
    record the ROUTE that answered and retry on a DIFFERENT one."""

    def _src(self):
        import integrations.chat_orchestrator as co

        return open(co.__file__, encoding="utf-8").read()

    def test_the_served_route_is_captured_before_any_regeneration(self):
        src = self._src()
        stream_pos = src.index(
            "_streamed = _strip_protocol_tags(_full, captured=_reasoning_parts)")
        route_pos = src.index("_stream_route = (", stream_pos)
        guard_pos = src.index("_derivation_reply_ignored_the_row(\n", route_pos)
        assert route_pos < guard_pos, (
            "the handler's last-used route is overwritten by every later call, "
            "so it must be read before the guards regenerate")

    def test_the_guard_records_the_verdict_with_the_provider(self):
        src = self._src()
        assert "record_evidence_ignored(" in src
        block = src[src.index("record_evidence_ignored("):]
        block = block[:block.index("_row_hint = \"\"")]
        assert "provider_id=str(_stream_route[0] or \"\")" in block
        assert "model_id=str(_stream_route[1] or \"\")" in block
        assert "_last_feedback_decision_id" in block, (
            "the verdict must judge the generation that produced the reply")

    def test_the_retry_uses_the_selected_route_and_never_a_literal_model(self):
        src = self._src()
        block = src[src.index("_retry_route = _cross_route_retry_route("):]
        block = block[:block.index("_fixed = _strip_protocol_tags")]
        assert "_retry_model = _retry_route[1]" in block
        assert '"sticky_hint"' in block
        assert "model=_retry_model" in block
        for literal in ('"gpt-5', "'gpt-5", '"z-ai/', '"deepseek-v4-pro"'):
            assert literal not in block, "the retry must not pin a literal model"

    def test_a_derivation_verdict_is_withheld_from_the_ledger(self):
        """The figure check may still REGENERATE on a derivation turn — that is
        a cheap quality retry — but it must not write a fabrication verdict:
        the delivered formulas make every correct result absent from the
        evidence text. The ledger entry is what steers routing."""
        src = self._src()
        assert "_figures_derivable = bool(" in src
        assert 'if _figures_derivable:' in src
        # The suppression is STATED in the log at both call sites — a withheld
        # verdict must be visible, never silent.
        assert src.count('"[figure-grounding] fabrication verdict "') == 1
        assert src.count('"[verify-panel] fabrication verdict "') == 1
        assert src.count("withheld: the delivered evidence") == 2
        # Both writers are gated: the deterministic check and the panel.
        assert src.count("if _figures_derivable:") == 2

    def test_the_panel_verdict_carries_its_own_rule(self):
        """A verdict is only usable as exclusion evidence with the rule that
        produced it; the panel is a different rule from the figure check."""
        src = self._src()
        assert 'rule="panel_v1"' in src

    def test_the_figure_rule_default_is_stamped_by_the_writer(self):
        """The registry writer stamps the rule, so every route recorded through
        it is exclusion-eligible — the caller cannot forget."""
        from core.llm.learning_router_registry import record_fabrication_signal
        import inspect

        src = inspect.getsource(record_fabrication_signal)
        assert "FIGURE_VERDICT_RULE" in src
        assert "verdict_rule=rule or FIGURE_VERDICT_RULE" in src

    def test_the_non_streaming_leg_has_the_same_guard(self):
        src = self._src()
        assert "DERIVATION GUARD (non-streaming path)" in src
        assert "_fb_routes: List[tuple] = []" in src, (
            "the non-streaming leg needs the ranked routes initialised or it "
            "raises (or silently repeats the failed route)")


# ---------------------------------------------------------------------------
# 9. The rule stamp must encode WHAT WAS VERIFIED, not the code version
# ---------------------------------------------------------------------------

class TestFigureVerdictRuleReflectsContext:
    """Live 2026-09-16 (shared instance, `logs/uvicorn_8001_restart.log`): the
    evidence-absence check flagged `$4,815.00` — a value STORED in the workbook
    row — on a reply it had no derivation cross-check for, and the row went in
    stamped bench-eligible. A verdict no independent check confirms may not
    exclude a route, so the rule records the context:

    * the workbook CONTRADICTED the reply's arithmetic → proof → exclusion-eligible;
    * the evidence-absence heuristic alone → recorded, never exclusion evidence.
    """

    def test_only_a_contradicted_derivation_is_exclusion_evidence(self):
        from core.llm.fabrication_accounting import (
            CURRENT_VERDICT_RULES,
            FIGURE_HEURISTIC_RULE,
            FIGURE_VERDICT_RULE,
        )

        assert FIGURE_VERDICT_RULE in CURRENT_VERDICT_RULES
        assert FIGURE_HEURISTIC_RULE not in CURRENT_VERDICT_RULES
        assert FIGURE_HEURISTIC_RULE != FIGURE_VERDICT_RULE

    def test_the_orchestrator_picks_the_rule_by_context(self):
        import inspect

        import integrations.chat_orchestrator as co

        src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
        assert "_fig_rule = (" in src
        assert "if _derivation_contradicted" in src
        assert "else FIGURE_HEURISTIC_RULE" in src
        assert "rule=_fig_rule," in src

    MODEL = "z-ai/glm-5.3-flash"

    def test_a_heuristic_verdict_cannot_bench(self, scratch_feedback_db,
                                              monkeypatch):
        """Same rows, different rule, different outcome: the context stamp is
        what decides whether the ledger may remove a route."""
        from core.llm.fabrication_accounting import FIGURE_HEURISTIC_RULE

        writer = _writer()
        for turn in ("t1", "t2", "t3"):
            writer._persist_feedback(
                _feedback(turn, model=self.MODEL, score=0.1,
                          provider="openrouter", verdict="unsupported_figures"),
                {"verdict": "unsupported_figures",
                 "verdict_rule": FIGURE_HEURISTIC_RULE})
        handler = _bench_stub(monkeypatch, min_events=1, rate=0.25)
        assert handler._fabrication_benched("openrouter", self.MODEL) is False
