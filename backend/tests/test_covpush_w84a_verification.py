"""Coverage wave 84a — orchestration verification package (R54 reviewer/debate family).

Modules covered (standalone, zero LLM spend / no network / no real DB):
  1. core/orchestration/verification/base.py
  2. core/orchestration/verification/voting.py
  3. core/orchestration/verification/schema_verifier.py
  4. core/orchestration/verification/execution.py
  5. core/orchestration/verification/formal.py
  6. core/orchestration/verification/grounded.py
  7. core/orchestration/verification/judge.py
  8. core/orchestration/verification/code_pipeline.py
  9. core/orchestration/verification/review.py
 10. core/orchestration/verification/domain.py

Style: mocked deps only (duck-typed steps/contexts, fake LLM services with
canned responses); every async entry point driven through ``asyncio.run``.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.orchestration.verification.base import (
    Verifier,
    VerificationResult,
    VerificationStrategy,
    replace,
    serialise,
)
from core.orchestration.verification.code_pipeline import CodePipelineVerifier
from core.orchestration.verification.domain import (
    DOMAIN_STRATEGY_MAP,
    TaskDomain,
    _coerce_domain,
    _coerce_strategy,
    infer_domain,
    resolve_domain,
    resolve_strategy,
)
from core.orchestration.verification.execution import ExecutionVerifier
from core.orchestration.verification.formal import FormalVerifier
from core.orchestration.verification.grounded import GroundedVerifier
from core.orchestration.verification.judge import JudgeVerifier
from core.orchestration.verification.review import ReviewerVerifier
from core.orchestration.verification.schema_verifier import SchemaVerifier
from core.orchestration.verification.voting import VotingVerifier

import core.orchestration.verification.formal as formal_mod
import core.orchestration.verification.schema_verifier as schema_mod

# ---------------------------------------------------------------------------
# Shared test doubles
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


class _Step:
    """Duck-typed WorkflowStep."""

    def __init__(
        self,
        step_id: str = "s1",
        name: str = "",
        description: str = "",
        capability: str = "",
        parameters: Any = None,
        **extra: Any,
    ) -> None:
        self.step_id = step_id
        self.name = name
        self.description = description
        self.capability = capability
        self.parameters = parameters
        for k, v in extra.items():
            setattr(self, k, v)

    def without(self, attr: str) -> "_Step":
        if hasattr(self, attr):
            delattr(self, attr)
        return self


class _Ctx:
    """Duck-typed verification context."""

    def __init__(self, resolved_domain: Any = TaskDomain.UNKNOWN, **extra: Any) -> None:
        self._resolved_domain = resolved_domain
        self.shared_context = {}
        for k, v in extra.items():
            setattr(self, k, v)


class _Result(SimpleNamespace):
    """Duck-typed sandbox execution result."""

    def __init__(
        self,
        exit_code: int = 0,
        success: bool = True,
        stdout: str = "",
        duration_seconds: float = 0.0,
    ) -> None:
        super().__init__(
            exit_code=exit_code, success=success, stdout=stdout,
            duration_seconds=duration_seconds,
        )


class _SyncLLM:
    """Sync fake LLM — method chosen per constructor."""

    def __init__(self, response: str = "YES\nsupported by sources", method: str = "complete") -> None:
        self._response = response
        self._method = method

    def __getattr__(self, name: str) -> Any:
        if name == self._method:
            def call(prompt: str) -> str:
                return self._response
            return call
        raise AttributeError(name)


class _AsyncLLM:
    """Async fake LLM — method chosen per constructor."""

    def __init__(self, response: str = "YES\nsupported by sources", method: str = "complete") -> None:
        self._response = response
        self._method = method

    def __getattr__(self, name: str) -> Any:
        if name == self._method:
            async def call(prompt: str) -> str:
                return self._response
            return call
        raise AttributeError(name)


# ---------------------------------------------------------------------------
# 1. base.py — strategy enum, result type, verifier ABC, serialise
# ---------------------------------------------------------------------------


class TestVerificationStrategy:
    def test_members_have_expected_values(self):
        assert VerificationStrategy.VOTING.value == "voting"
        assert VerificationStrategy.SCHEMA.value == "schema"
        assert VerificationStrategy.EXECUTION.value == "execution"
        assert VerificationStrategy.FORMAL.value == "formal"
        assert VerificationStrategy.GROUNDED.value == "grounded"
        assert VerificationStrategy.JUDGE.value == "judge"
        assert VerificationStrategy.CODE_PIPELINE.value == "code_pipeline"
        assert VerificationStrategy.REVIEW.value == "review"

    def test_is_str_enum(self):
        assert isinstance(VerificationStrategy.VOTING, str)
        assert VerificationStrategy("voting") is VerificationStrategy.VOTING

    def test_public_surface_exports(self):
        from core.orchestration.verification.base import __all__ as all_names
        for name in ("VerificationStrategy", "VerificationResult", "Verifier", "serialise", "replace"):
            assert name in all_names


class TestVerificationResult:
    def test_construction_and_defaults(self):
        r = VerificationResult(winner={"a": 1}, strategy=VerificationStrategy.VOTING, domain=TaskDomain.UNKNOWN)
        assert r.winner == {"a": 1}
        assert r.strategy is VerificationStrategy.VOTING
        assert r.domain is TaskDomain.UNKNOWN
        assert r.confidence == 0.0
        assert r.fallback_used is False
        assert r.details == {}
        assert r.reason is None

    def test_is_frozen(self):
        r = VerificationResult(winner=None, strategy=VerificationStrategy.VOTING, domain=TaskDomain.UNKNOWN)
        with pytest.raises(FrozenInstanceError):
            r.confidence = 1.0

    def test_empty_returns_no_winner(self):
        r = VerificationResult.empty(
            TaskDomain.MATH, VerificationStrategy.FORMAL, reason="nothing to verify"
        )
        assert r.winner is None
        assert r.strategy is VerificationStrategy.FORMAL
        assert r.domain is TaskDomain.MATH
        assert r.confidence == 0.0
        assert r.fallback_used is False
        assert r.reason == "nothing to verify"
        assert r.details == {}

    def test_empty_default_reason_is_none(self):
        r = VerificationResult.empty(TaskDomain.CODE, VerificationStrategy.CODE_PIPELINE)
        assert r.reason is None
        assert r.winner is None

    def test_dataclass_replace_supported(self):
        r = VerificationResult.empty(TaskDomain.QA, VerificationStrategy.GROUNDED, reason="x")
        r2 = replace(r, winner="candidate", confidence=0.9)
        assert r2.winner == "candidate"
        assert r2.confidence == 0.9
        assert r2.reason == "x"
        assert r.winner is None  # original untouched (frozen)

    def test_details_factory_is_per_instance(self):
        a = VerificationResult.empty(TaskDomain.UNKNOWN, VerificationStrategy.VOTING)
        b = VerificationResult.empty(TaskDomain.UNKNOWN, VerificationStrategy.VOTING)
        a.details["k"] = 1
        assert b.details == {}
        assert a.details is not b.details


class TestSerialise:
    def test_dict_sorted_json(self):
        assert serialise({"b": 1, "a": 2}) == json.dumps({"b": 1, "a": 2}, sort_keys=True)

    def test_list_json(self):
        assert serialise([{"b": 1}, {"a": 2}]) == '[{"b": 1}, {"a": 2}]'

    def test_nested_dict(self):
        assert serialise({"x": {"z": 1, "y": 2}}) == '{"x": {"y": 2, "z": 1}}'

    def test_non_container_uses_str(self):
        assert serialise(42) == "42"
        assert serialise("hello") == "hello"
        assert serialise(None) == "None"
        assert serialise(3.5) == "3.5"
        assert serialise({1, 2}) == "{1, 2}"  # sets are not dict/list → str

    def test_list_with_scalars(self):
        assert serialise([1, 2, 3]) == "[1, 2, 3]"


class TestVerifierABC:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            Verifier()  # type: ignore[abstract]

    def test_subclass_without_verify_cannot_instantiate(self):
        class Missing(Verifier):
            strategy = VerificationStrategy.VOTING

        with pytest.raises(TypeError):
            Missing()  # type: ignore[abstract]

    def test_concrete_subclass_instantiates_with_default_strategy(self):
        class Concrete(Verifier):
            async def verify(self, candidates, step, context):
                return VerificationResult.empty("d", self.strategy)

        v = Concrete()
        assert v.strategy is VerificationStrategy.VOTING

    def test_abstract_body_executes_via_super(self):
        class Probe(Verifier):
            strategy = VerificationStrategy.SCHEMA

            async def verify(self, candidates, step, context):
                result = await super().verify(candidates, step, context)
                return result

        v = Probe()
        assert _run(v.verify([], None, None)) is None  # ABC body is `...` → None


# ---------------------------------------------------------------------------
# 2. voting.py — majority → reconcile → majority-fallback
# ---------------------------------------------------------------------------


class TestVotingVerifier:
    def test_no_candidates_returns_empty(self):
        v = VotingVerifier()
        r = _run(v.verify([], _Step(), _Ctx()))
        assert r.winner is None
        assert r.strategy is VerificationStrategy.VOTING
        assert r.reason == "no candidates"
        assert r.confidence == 0.0

    def test_single_candidate_is_majority(self):
        v = VotingVerifier()
        r = _run(v.verify([{"a": 1}], _Step(), _Ctx()))
        assert r.winner == {"a": 1}
        assert r.details["mode"] == "majority"
        assert r.confidence == 1.0
        assert r.reason == "clear majority"

    def test_unanimous_two_thirds_majority(self):
        v = VotingVerifier()
        candidates = [{"ans": "x"}, {"ans": "x"}, {"ans": "x"}]
        r = _run(v.verify(candidates, _Step(), _Ctx()))
        assert r.winner == {"ans": "x"}
        assert r.details["mode"] == "majority"
        assert r.details["majority_count"] == 3
        assert r.confidence == 1.0

    def test_exactly_two_thirds_majority_wins(self):
        v = VotingVerifier()
        candidates = [{"ans": "x"}, {"ans": "x"}, {"ans": "y"}]
        r = _run(v.verify(candidates, _Step(), _Ctx()))
        assert r.winner == {"ans": "x"}
        assert r.details["mode"] == "majority"
        assert r.confidence == pytest.approx(2 / 3)

    def test_five_candidates_three_identical_is_not_majority(self):
        # ceil(2N/3) = 4 at N=5 — 3/5 (60%) is NOT a majority under the H6 fix.
        v = VotingVerifier()
        candidates = [{"a": 1}, {"a": 1}, {"a": 1}, {"b": 2}, {"c": 3}]
        r = _run(v.verify(candidates, _Step(), _Ctx()))
        # serialised forms differ by extra keys → full divergence → reconcile
        assert r.details["mode"] == "reconciled"
        assert r.winner["a"] == 1

    def test_five_candidates_four_identical_is_majority(self):
        v = VotingVerifier()
        candidates = [{"a": 1}, {"a": 1}, {"a": 1}, {"a": 1}, {"b": 2}]
        r = _run(v.verify(candidates, _Step(), _Ctx()))
        assert r.details["mode"] == "majority"
        assert r.details["majority_count"] == 4
        assert r.confidence == pytest.approx(0.8)

    def test_divergence_reconciles_non_conflicting_keys(self):
        v = VotingVerifier()
        candidates = [
            {"action": "read", "target": "a.py"},
            {"action": "read", "target": "b.py"},
            {"action": "write", "target": "c.py"},
        ]
        r = _run(v.verify(candidates, _Step(step_id="s-div"), _Ctx()))
        assert r.details["mode"] == "reconciled"
        assert r.winner["action"] == "read"       # 2/3 agree
        assert r.winner["target"] == "a.py"       # tie → most frequent (first)
        assert r.winner["_reconciled"] is True
        assert r.winner["step_id"] == "s-div"
        assert r.confidence == pytest.approx(1 / 3)
        assert r.reason == "merged non-conflicting portions of diverging branches"

    def test_divergence_with_non_dict_candidates_falls_back_to_majority(self):
        v = VotingVerifier()
        r = _run(v.verify([1, 2, 3], _Step(), _Ctx()))
        assert r.details["mode"] == "majority_fallback"
        assert r.winner == 1
        assert r.confidence == pytest.approx(1 / 3)
        assert r.reason == "reconciliation empty; fell back to majority winner"

    def test_default_domain_unknown_when_context_missing(self):
        v = VotingVerifier()
        r = _run(v.verify([{"a": 1}], _Step(), SimpleNamespace()))
        assert r.domain == "unknown"

    def test_resolved_domain_passes_through(self):
        v = VotingVerifier()
        r = _run(v.verify([{"a": 1}], _Step(), _Ctx(resolved_domain=TaskDomain.PLANNING)))
        assert r.domain is TaskDomain.PLANNING

    def test_step_id_without_attribute_defaults_question_mark(self):
        v = VotingVerifier()
        r = _run(v.verify([1, 2, 3], SimpleNamespace(), _Ctx()))
        assert r.details["mode"] == "majority_fallback"

    # -- reconcile_only / reconcile_only_sync -------------------------------

    def test_reconcile_only_async_wrapper(self):
        v = VotingVerifier()
        r = _run(v.reconcile_only("s", [{"k": 1}]))
        assert r["k"] == 1
        assert r["_reconciled"] is True
        assert r["_branch_count"] == 1
        assert r["step_id"] == "s"
        assert r["_reconciler"] == "ConductorAgent._reconcile_branch_conflicts"

    def test_reconcile_sync_empty_input_returns_none(self):
        v = VotingVerifier()
        assert v.reconcile_only_sync("s", []) is None

    def test_reconcile_sync_non_dict_inputs_return_none(self):
        v = VotingVerifier()
        assert v.reconcile_only_sync("s", [1, "x"]) is None

    def test_reconcile_sync_agreement_is_safe_zone(self):
        v = VotingVerifier()
        merged = v.reconcile_only_sync("s", [{"k": "v"}, {"k": "v"}])
        assert merged["k"] == "v"
        assert merged["_reconciled"] is True
        assert merged["_branch_count"] == 2
        assert merged["step_id"] == "s"
        assert merged["_reconciler"] == "ConductorAgent._reconcile_branch_conflicts"

    def test_reconcile_sync_nested_dict_values_serialised_for_equality(self):
        v = VotingVerifier()
        merged = v.reconcile_only_sync("s", [{"meta": {"x": 1}}, {"meta": {"x": 1}}])
        assert merged["meta"] == {"x": 1}

    def test_reconcile_sync_disagreement_picks_most_frequent(self):
        v = VotingVerifier()
        merged = v.reconcile_only_sync("s", [{"k": "a"}, {"k": "b"}, {"k": "b"}])
        assert merged["k"] == "b"

    def test_reconcile_sync_ignores_non_dict_branches(self):
        v = VotingVerifier()
        merged = v.reconcile_only_sync("s", [{"k": "a"}, "junk", {"k": "a"}])
        assert merged["k"] == "a"
        assert merged["_branch_count"] == 3

    def test_reconcile_sync_serialise_failure_returns_none(self):
        v = VotingVerifier()
        # json.dumps of a set raises → reconciler swallows → None
        assert v.reconcile_only_sync("s", [{"x": {1, 2}}]) is None

    def test_match_winner_returns_first_matching_candidate(self):
        assert VotingVerifier._match_winner([{"a": 1}, "x"], ['{"a": 1}', "x"], '{"a": 1}') == {"a": 1}

    def test_match_winner_falls_back_to_first_candidate(self):
        assert VotingVerifier._match_winner(["a", "b"], ["a", "b"], "z") == "a"


# ---------------------------------------------------------------------------
# 3. schema_verifier.py — jsonschema + required_fields
# ---------------------------------------------------------------------------


class TestSchemaVerifier:
    SCHEMA = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}

    def test_no_candidates_returns_empty(self):
        v = SchemaVerifier()
        r = _run(v.verify([], _Step(parameters={"output_schema": self.SCHEMA}), _Ctx()))
        assert r.winner is None
        assert r.reason == "no candidates"

    def test_no_schema_configured_returns_empty(self):
        v = SchemaVerifier()
        r = _run(v.verify([{"a": 1}], _Step(parameters={}), _Ctx()))
        assert r.winner is None
        assert r.reason == "no output_schema or required_fields configured on the step"

    def test_jsonschema_valid_candidate_wins(self):
        v = SchemaVerifier()
        r = _run(v.verify([{"a": "x"}], _Step(parameters={"output_schema": self.SCHEMA}), _Ctx()))
        assert r.winner == {"a": "x"}
        assert r.confidence == 1.0
        assert r.details["mode"] == "jsonschema"
        assert r.details["winning_index"] == 0
        assert r.reason == "first candidate matching the configured schema"

    def test_jsonschema_first_valid_of_many_wins(self):
        v = SchemaVerifier()
        candidates = [{"a": 5}, {"a": "ok"}, {"a": "also-ok"}]
        r = _run(v.verify(candidates, _Step(parameters={"output_schema": self.SCHEMA}), _Ctx()))
        assert r.winner == {"a": "ok"}
        assert r.details["winning_index"] == 1

    def test_jsonschema_validation_error_is_recorded(self):
        v = SchemaVerifier()
        r = _run(v.verify([{"a": 5}], _Step(parameters={"output_schema": self.SCHEMA}), _Ctx()))
        assert r.winner is None
        assert r.details["validation_errors"][0]["error"].startswith("jsonschema: ")

    def test_jsonschema_unexpected_exception_is_recorded(self):
        v = SchemaVerifier()
        bad_schema = {"type": "object", "properties": 5}  # SchemaError, not ValidationError
        r = _run(v.verify([{"a": 5}], _Step(parameters={"output_schema": bad_schema}), _Ctx()))
        assert r.winner is None
        assert r.details["validation_errors"][0]["error"].startswith("jsonschema (unexpected): ")

    def test_manual_check_used_when_jsonschema_unavailable(self, monkeypatch):
        monkeypatch.setattr(schema_mod, "_HAS_JSONSCHEMA", False)
        v = SchemaVerifier()
        r = _run(v.verify([{"a": "x"}], _Step(parameters={"output_schema": self.SCHEMA}), _Ctx()))
        assert r.winner == {"a": "x"}
        assert r.details["mode"] == "jsonschema"

    def test_manual_check_missing_required_field(self, monkeypatch):
        monkeypatch.setattr(schema_mod, "_HAS_JSONSCHEMA", False)
        v = SchemaVerifier()
        r = _run(v.verify([{"b": 1}], _Step(parameters={"output_schema": self.SCHEMA}), _Ctx()))
        assert r.winner is None
        assert r.details["validation_errors"][0]["error"] == "missing required fields: ['a']"

    def test_manual_check_wrong_type(self, monkeypatch):
        monkeypatch.setattr(schema_mod, "_HAS_JSONSCHEMA", False)
        v = SchemaVerifier()
        r = _run(v.verify([{"a": 5}], _Step(parameters={"output_schema": self.SCHEMA}), _Ctx()))
        assert r.winner is None
        assert "expected string" in r.details["validation_errors"][0]["error"]

    def test_required_fields_present_wins(self):
        v = SchemaVerifier()
        r = _run(
            v.verify([{"name": "n", "age": 1}], _Step(parameters={"required_fields": ["name", "age"]}), _Ctx())
        )
        assert r.winner == {"name": "n", "age": 1}
        assert r.details["mode"] == "required_fields"

    def test_required_fields_missing(self):
        v = SchemaVerifier()
        r = _run(v.verify([{"name": "n"}], _Step(parameters={"required_fields": ["name", "age"]}), _Ctx()))
        assert r.winner is None
        assert r.details["validation_errors"][0]["error"] == "missing required fields: ['age']"

    def test_non_dict_candidate_rejected(self):
        v = SchemaVerifier()
        r = _run(v.verify(["string"], _Step(parameters={"required_fields": ["a"]}), _Ctx()))
        assert r.winner is None
        assert r.details["validation_errors"][0]["error"] == "expected a dict/object, got str"

    def test_errors_capped_at_ten(self):
        v = SchemaVerifier()
        candidates = [{"a": i} for i in range(12)]  # all fail string type
        r = _run(v.verify(candidates, _Step(parameters={"output_schema": self.SCHEMA}), _Ctx()))
        assert r.winner is None
        assert len(r.details["validation_errors"]) == 10
        assert r.details["candidate_count"] == 12
        assert r.reason == "no candidate matched the configured schema"

    def test_default_domain_unknown(self):
        v = SchemaVerifier()
        r = _run(v.verify([{"a": "x"}], _Step(parameters={"output_schema": self.SCHEMA}), SimpleNamespace()))
        assert r.domain == "unknown"

    # -- _manual_schema_check direct ----------------------------------------

    def test_manual_check_all_type_map_types(self):
        schema = {
            "required": ["s", "i", "n", "b", "arr", "o", "z"],
            "properties": {
                "s": {"type": "string"},
                "i": {"type": "integer"},
                "n": {"type": "number"},
                "b": {"type": "boolean"},
                "arr": {"type": "array"},
                "o": {"type": "object"},
                "z": {"type": "null"},
            },
        }
        ok, why = SchemaVerifier._manual_schema_check(
            {"s": "x", "i": 3, "n": 2.5, "b": True, "arr": [], "o": {}, "z": None}, schema
        )
        assert ok is True and why is None

    def test_manual_check_missing_required(self):
        ok, why = SchemaVerifier._manual_schema_check({"a": 1}, {"required": ["a", "b"]})
        assert ok is False
        assert why == "missing required fields: ['b']"

    def test_manual_check_bool_rejected_for_integer(self):
        ok, why = SchemaVerifier._manual_schema_check(
            {"f": True}, {"properties": {"f": {"type": "integer"}}}
        )
        assert ok is False
        assert "expected integer, got bool" in why

    def test_manual_check_bool_rejected_for_number(self):
        ok, why = SchemaVerifier._manual_schema_check(
            {"f": True}, {"properties": {"f": {"type": "number"}}}
        )
        assert ok is False
        assert "expected number, got bool" in why

    def test_manual_check_wrong_type(self):
        ok, why = SchemaVerifier._manual_schema_check(
            {"f": "x"}, {"properties": {"f": {"type": "integer"}}}
        )
        assert ok is False
        assert why == "field 'f': expected integer, got str"

    def test_manual_check_unknown_type_skipped(self):
        ok, why = SchemaVerifier._manual_schema_check(
            {"f": object()}, {"properties": {"f": {"type": "not-a-real-type"}}}
        )
        assert ok is True and why is None

    def test_manual_check_non_dict_spec_skipped(self):
        ok, why = SchemaVerifier._manual_schema_check({"f": 1}, {"properties": {"f": 5}})
        assert ok is True and why is None

    def test_manual_check_absent_field_skipped(self):
        ok, why = SchemaVerifier._manual_schema_check({}, {"properties": {"f": {"type": "string"}}})
        assert ok is True and why is None

    def test_validate_non_dict(self):
        ok, why = SchemaVerifier._validate("x", None, None)
        assert ok is False
        assert "got str" in why

    def test_validate_required_fields_none_ok(self):
        ok, why = SchemaVerifier._validate({"a": 1}, None, None)
        assert ok is True and why is None


# ---------------------------------------------------------------------------
# 4. execution.py — sandbox as the oracle
# ---------------------------------------------------------------------------


class TestExecutionVerifier:
    def test_no_candidates_returns_empty(self):
        v = ExecutionVerifier(sandbox_runtime=MagicMock())
        r = _run(v.verify([], _Step(), _Ctx()))
        assert r.winner is None
        assert r.reason == "no candidates"

    def test_runtime_acquisition_failure_degrades(self, monkeypatch):
        def boom():
            raise RuntimeError("no docker daemon")

        monkeypatch.setattr("core.sandbox_runtime.get_runtime", boom)
        v = ExecutionVerifier()
        r = _run(v.verify([{"code": "print(1)"}], _Step(), _Ctx()))
        assert r.winner is None
        assert r.reason == "sandbox runtime unavailable: no docker daemon"

    def test_lazy_runtime_acquisition(self, monkeypatch):
        runtime = MagicMock()
        monkeypatch.setattr("core.sandbox_runtime.get_runtime", lambda: runtime)
        v = ExecutionVerifier()
        assert v._get_runtime() is runtime  # resolves through the module import

    def test_injected_runtime_short_circuits(self):
        runtime = MagicMock()
        v = ExecutionVerifier(sandbox_runtime=runtime)
        assert v._get_runtime() is runtime

    def test_first_passing_candidate_wins(self):
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(
            side_effect=[
                _Result(exit_code=0, success=True, stdout="x"),
                _Result(exit_code=0, success=True, stdout="hello"),
            ]
        )
        v = ExecutionVerifier(sandbox_runtime=runtime)
        step = _Step(parameters={"tests": {"expected_stdout": "hello"}})
        candidates = [{"code": "print('x')"}, {"code": "print('hello')"}]
        r = _run(v.verify(candidates, step, _Ctx()))
        assert r.winner == {"code": "print('hello')"}
        assert r.confidence == 1.0
        assert r.details["winning_index"] == 1
        assert r.details["candidate_count"] == 2
        assert r.details["exit_code"] == 0
        assert r.details["duration_seconds"] == 0.0
        assert r.reason == "first candidate that executed and passed the test spec"

    def test_candidate_without_code_skipped_and_continues(self):
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(return_value=_Result())
        v = ExecutionVerifier(sandbox_runtime=runtime)
        r = _run(v.verify([{"action": "read"}, {"code": "print(1)"}], _Step(), _Ctx()))
        assert r.winner == {"code": "print(1)"}
        assert r.details["attempts"][0]["error"] == "no code found in candidate"
        assert r.details["winning_index"] == 1

    def test_runtime_raising_execution_continues(self):
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(side_effect=RuntimeError("boom"))
        v = ExecutionVerifier(sandbox_runtime=runtime)
        r = _run(v.verify([{"code": "x"}], _Step(), _Ctx()))
        assert r.winner is None
        assert r.details["attempts"][0]["error"] == "runtime raised: boom"
        assert r.reason == "no candidate passed execution-based verification"

    def test_all_fail_returns_no_winner(self):
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(return_value=_Result(exit_code=1, success=False))
        v = ExecutionVerifier(sandbox_runtime=runtime)
        r = _run(v.verify([{"code": "x"}], _Step(), _Ctx()))
        assert r.winner is None
        assert r.details["attempts"][0]["exit_code"] == 1
        assert r.details["attempts"][0]["success"] is False
        assert r.details["attempts"][0]["passed"] is False
        assert r.details["candidate_count"] == 1

    def test_bare_string_candidate_extracts_code(self):
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(return_value=_Result())
        v = ExecutionVerifier(sandbox_runtime=runtime)
        r = _run(v.verify(["print(1)"], _Step(), _Ctx()))
        assert r.winner == "print(1)"

    def test_source_key_used_when_no_code_key(self):
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(return_value=_Result())
        v = ExecutionVerifier(sandbox_runtime=runtime)
        r = _run(v.verify([{"source": "print(1)"}], _Step(), _Ctx()))
        assert r.winner == {"source": "print(1)"}

    def test_output_key_used_when_no_code_source(self):
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(return_value=_Result())
        v = ExecutionVerifier(sandbox_runtime=runtime)
        r = _run(v.verify([{"output": "print(1)"}], _Step(), _Ctx()))
        assert r.winner == {"output": "print(1)"}

    def test_domain_defaults_to_unknown(self):
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(return_value=_Result())
        v = ExecutionVerifier(sandbox_runtime=runtime)
        r = _run(v.verify([{"code": "print(1)"}], _Step(), SimpleNamespace()))
        assert r.domain == "unknown"

    # -- _extract_code ------------------------------------------------------

    def test_extract_code_nonempty_str(self):
        assert ExecutionVerifier._extract_code("print(1)") == "print(1)"

    def test_extract_code_empty_str_is_none(self):
        assert ExecutionVerifier._extract_code("") is None
        # whitespace-only strings are truthy → returned as-is (per source contract)
        assert ExecutionVerifier._extract_code("   ") == "   "

    def test_extract_code_dict_key_priority(self):
        assert ExecutionVerifier._extract_code({"code": "c", "source": "s", "output": "o"}) == "c"
        assert ExecutionVerifier._extract_code({"source": "s", "output": "o"}) == "s"
        assert ExecutionVerifier._extract_code({"output": "o"}) == "o"

    def test_extract_code_dict_blank_values_ignored(self):
        assert ExecutionVerifier._extract_code({"code": "", "output": "  "}) is None
        assert ExecutionVerifier._extract_code({"code": 5}) is None

    def test_extract_code_other_types_none(self):
        assert ExecutionVerifier._extract_code(42) is None
        assert ExecutionVerifier._extract_code(["print(1)"]) is None

    # -- _evaluate ----------------------------------------------------------

    def test_evaluate_nonzero_exit(self):
        assert ExecutionVerifier._evaluate(_Result(exit_code=1, success=True), "c", None) == (False, "non-zero exit (1)")

    def test_evaluate_success_false(self):
        assert ExecutionVerifier._evaluate(_Result(exit_code=0, success=False), "c", None) == (False, "non-zero exit (0)")

    def test_evaluate_no_tests_exit_zero_passes(self):
        assert ExecutionVerifier._evaluate(_Result(), "c", None) == (True, "exit 0 with no test spec")
        assert ExecutionVerifier._evaluate(_Result(), "c", []) == (True, "exit 0 with no test spec")

    def test_evaluate_expected_stdout_found(self):
        r = _Result(stdout="hello world")
        assert ExecutionVerifier._evaluate(r, "c", {"expected_stdout": "hello"}) == (True, "test spec satisfied")

    def test_evaluate_expected_stdout_missing(self):
        r = _Result(stdout="goodbye world")
        assert ExecutionVerifier._evaluate(r, "c", {"expected_stdout": "hello"}) == (False, "expected_stdout substring not found")

    def test_evaluate_expected_exact_match_after_strip(self):
        r = _Result(stdout="  42  ")
        assert ExecutionVerifier._evaluate(r, "c", {"expected_exact": "42"}) == (True, "test spec satisfied")

    def test_evaluate_expected_exact_mismatch(self):
        r = _Result(stdout="42")
        assert ExecutionVerifier._evaluate(r, "c", {"expected_exact": "43"}) == (False, "expected_exact mismatch")

    def test_evaluate_both_stdout_keys(self):
        r = _Result(stdout="hello 42")
        assert ExecutionVerifier._evaluate(r, "c", {"expected_stdout": "hello", "expected_exact": "hello 42"}) == (True, "test spec satisfied")

    def test_evaluate_assertion_list_accepted_on_exit_zero(self):
        r = _Result()
        assert ExecutionVerifier._evaluate(r, "c", ["assert 1 == 1", "assert 2 == 2"]) == (True, "2 assertions expected (exit 0 accepted)")

    def test_evaluate_unrecognised_tests_type(self):
        assert ExecutionVerifier._evaluate(_Result(), "c", 42) == (True, "test spec recognised")
        assert ExecutionVerifier._evaluate(_Result(), "c", "tests") == (True, "test spec recognised")

    # -- _build_policy ------------------------------------------------------

    def test_build_policy_explicit_step_policy_wins(self):
        policy = MagicMock()
        step = _Step(parameters={"sandbox_policy": policy})
        assert ExecutionVerifier._build_policy(step, None) is policy

    def test_build_policy_default_with_step_id(self):
        from core.sandbox_policy import SandboxPolicy

        step = _Step(step_id="s9", parameters={})
        policy = ExecutionVerifier._build_policy(step, None)
        assert isinstance(policy, SandboxPolicy)
        assert policy.run_id == "verify-s9"
        assert policy.agent_id == "verification-orchestrator"
        assert policy.max_exec_seconds == 15

    def test_build_policy_default_missing_step_id(self):
        step = _Step(parameters={}).without("step_id")
        policy = ExecutionVerifier._build_policy(step, None)
        assert policy.run_id == "verify-unknown"

    def test_build_policy_step_without_parameters(self):
        policy = ExecutionVerifier._build_policy(SimpleNamespace(), None)
        assert policy.run_id == "verify-unknown"


# ---------------------------------------------------------------------------
# 5. formal.py — sympy equivalence
# ---------------------------------------------------------------------------


class TestFormalVerifier:
    def test_no_candidates_returns_empty(self):
        v = FormalVerifier()
        r = _run(v.verify([], _Step(), _Ctx()))
        assert r.winner is None
        assert r.reason == "no candidates"

    def test_sympy_missing_degrades(self, monkeypatch):
        monkeypatch.setattr(formal_mod, "_HAS_SYMPY", False)
        v = FormalVerifier()
        r = _run(v.verify([{"answer": "x"}], _Step(), _Ctx()))
        assert r.winner is None
        assert r.reason == "sympy not installed; cannot do formal verification"

    def test_symbolic_equivalence_majority_wins(self):
        v = FormalVerifier()
        candidates = [{"answer": "x**2 + 1"}, {"answer": "1 + x**2"}, {"answer": "1 + x"}]
        r = _run(v.verify(candidates, _Step(), _Ctx(resolved_domain=TaskDomain.MATH)))
        assert r.winner == {"answer": "x**2 + 1"}
        assert r.details["mode"] == "sympy_equivalence"
        assert r.details["group_size"] == 2
        assert r.confidence == pytest.approx(2 / 3)
        assert "2/3 parseable answers are symbolically equivalent" in r.reason

    def test_symbolic_equivalence_with_equivalent_but_distinct_strings(self):
        v = FormalVerifier()
        candidates = ["x*x", "x**2", "x + 1"]
        r = _run(v.verify(candidates, _Step(), _Ctx()))
        assert r.winner == "x*x"
        assert r.confidence == pytest.approx(2 / 3)

    def test_parseable_but_no_strict_majority_falls_back(self):
        v = FormalVerifier()
        candidates = ["x+1", "x+1", "x+2", "x+2", "x+3"]
        r = _run(v.verify(candidates, _Step(), _Ctx()))
        assert r.winner is None
        assert r.reason == "no symbolic or exact-string majority"
        assert r.details["mode"] == "no_majority"

    def test_nobody_parses_falls_back_to_exact_string_majority(self):
        v = FormalVerifier()
        candidates = ["2 +", "2 +", "(("]
        r = _run(v.verify(candidates, _Step(), _Ctx()))
        assert r.winner == "2 +"
        assert r.details["mode"] == "exact_string_fallback"
        assert r.details["majority_count"] == 2
        assert r.confidence == pytest.approx(2 / 3)
        assert r.reason == "symbolic parse failed; exact-string majority used"

    def test_mixed_parse_fallback_when_sympy_cannot_split(self):
        # All parse but no equivalence group reaches majority; exact strings disagree.
        v = FormalVerifier()
        candidates = ["x+1", "x+1", "y+2", "y+2", "z+3"]
        r = _run(v.verify(candidates, _Step(), _Ctx()))
        assert r.winner is None

    def test_partial_parse_fallback_via_unparseable_candidates(self):
        v = FormalVerifier()
        candidates = ["2 +", "2 +", "1 + x"]
        r = _run(v.verify(candidates, _Step(), _Ctx()))
        # 1 valid parseable (1 + x) → largest group 1 <= 0.5? no: threshold 0.5, 1 > 0.5 → winner!
        assert r.winner == "1 + x"
        assert r.details["mode"] == "sympy_equivalence"

    def test_fallback_no_majority_returns_none(self):
        v = FormalVerifier()
        candidates = ["2 +", "((", "3 *"]
        r = _run(v.verify(candidates, _Step(), _Ctx()))
        assert r.winner is None
        assert r.details["mode"] == "no_majority"
        assert r.details["distinct"] == 3
        assert r.details["candidate_count"] == 3

    def test_default_domain_unknown(self):
        v = FormalVerifier()
        r = _run(v.verify(["1 + x"], _Step(), SimpleNamespace()))
        assert r.domain == "unknown"

    # -- helpers ------------------------------------------------------------

    def test_extract_answer_dict_key_priority(self):
        assert FormalVerifier._extract_answer({"answer": "a", "result": "r"}) == "a"
        assert FormalVerifier._extract_answer({"result": "r", "value": "v"}) == "r"
        assert FormalVerifier._extract_answer({"value": "v", "output": "o"}) == "v"
        assert FormalVerifier._extract_answer({"output": "o"}) == "o"
        assert FormalVerifier._extract_answer({"nope": 1}) == str({"nope": 1})

    def test_extract_answer_string(self):
        assert FormalVerifier._extract_answer("x + 1") == "x + 1"

    def test_extract_answer_strips(self):
        assert FormalVerifier._extract_answer({"answer": "  2  "}) == "2"

    def test_safe_sympify_empty_text_none(self):
        assert FormalVerifier._safe_sympify("") is None
        assert FormalVerifier._safe_sympify("   ") is None

    def test_safe_sympify_parse_failure_none(self):
        assert FormalVerifier._safe_sympify("2 +") is None
        assert FormalVerifier._safe_sympify("((") is None

    def test_safe_sympify_parses(self):
        assert FormalVerifier._safe_sympify("x**2") is not None

    def test_group_equivalent_simplify_exception_skips_pair(self, monkeypatch):
        import sympy

        real_simplify = sympy.simplify

        def flaky(expr):
            if expr.has(sympy.Symbol("MARKER")):
                raise RuntimeError("simplify boom")
            return real_simplify(expr)

        monkeypatch.setattr(formal_mod.sympy, "simplify", flaky)
        v = FormalVerifier()
        candidates = ["MARKER + 1", "MARKER + 2", "x + 1", "x + 1", "x + 1"]
        r = _run(v.verify(candidates, _Step(), _Ctx()))
        # MARKER pairs raise (skipped); x+1 trio still groups and wins strictly
        assert r.winner == "x + 1"
        assert r.details["mode"] == "sympy_equivalence"
        assert r.details["group_size"] == 3

    def test_group_equivalent_union_transitivity(self):
        v = FormalVerifier()
        exprs = [FormalVerifier._safe_sympify(s) for s in ("x + y + z", "z + y + x", "1 + x")]
        groups = v._group_equivalent(exprs)
        assert sorted(len(g) for g in groups) == [1, 2]

    def test_parse_all_shapes(self):
        v = FormalVerifier()
        parsed = v._parse_all([{"answer": "x"}, "2 +", 5])
        assert parsed[0][1] is not None
        assert parsed[0][2] == "x"
        assert parsed[1][1] is None
        assert parsed[1][2] == "2 +"
        assert parsed[2][1] is not None
        assert parsed[2][2] == "5"


# ---------------------------------------------------------------------------
# 6. grounded.py — LLM faithfulness check
# ---------------------------------------------------------------------------


class TestGroundedVerifier:
    def test_no_candidates_returns_empty(self):
        v = GroundedVerifier()
        r = _run(v.verify([], _Step(), _Ctx()))
        assert r.winner is None
        assert r.reason == "no candidates"

    def test_no_sources_returns_empty(self):
        v = GroundedVerifier(llm_service=_SyncLLM())
        r = _run(v.verify(["answer"], _Step(parameters={}), _Ctx(shared_context={})))
        assert r.winner is None
        assert r.reason == "no sources available for grounding check"

    def test_no_llm_service_returns_empty(self):
        v = GroundedVerifier()
        step = _Step(parameters={"sources": "source text"})
        r = _run(v.verify(["answer"], step, _Ctx()))
        assert r.winner is None
        assert r.reason == "no LLM service configured for grounding check"

    def test_circuit_open_returns_empty(self):
        v = GroundedVerifier(llm_service=_SyncLLM())
        v._circuit._failures = 5
        v._circuit._opened_at = time.time()
        step = _Step(parameters={"sources": "src"})
        r = _run(v.verify(["a"], step, _Ctx()))
        assert r.winner is None
        assert r.reason == "circuit open (fail-open)"

    def test_first_grounded_candidate_wins(self):
        responses = {"A1": "NO\nnot supported", "A2": "YES\nfully supported"}
        v = GroundedVerifier(llm_service=_SyncLLM())
        v._check_faithfulness = AsyncMock(side_effect=lambda answer, sources: {
            "A1": {"grounded": False, "rationale": "not supported"},
            "A2": {"grounded": True, "rationale": "fully supported"},
        }[answer])
        candidates = ["A1", "A2"]
        r = _run(v.verify(candidates, _Step(parameters={"sources": "src"}), _Ctx()))
        assert r.winner == "A2"
        assert r.confidence == 1.0
        assert r.details["winning_index"] == 1
        assert r.details["checks"][0]["grounded"] is False
        assert r.details["checks"][1]["grounded"] is True
        assert r.reason == "first candidate judged grounded against the sources"

    def test_no_candidate_grounded_returns_none(self):
        v = GroundedVerifier(llm_service=_SyncLLM())
        v._check_faithfulness = AsyncMock(
            return_value={"grounded": False, "rationale": "unsupported"}
        )
        r = _run(v.verify(["A1", "A2"], _Step(parameters={"sources": "src"}), _Ctx()))
        assert r.winner is None
        assert r.reason == "no candidate judged grounded against the sources"
        assert len(r.details["checks"]) == 2

    def test_timeout_records_failure_and_continues(self):
        v = GroundedVerifier(llm_service=_SyncLLM(), timeout_seconds=0.01)

        async def slow(answer, sources):
            await asyncio.sleep(0.1)
            return {"grounded": True, "rationale": "late"}

        v._check_faithfulness = slow
        r = _run(v.verify(["A1"], _Step(parameters={"sources": "src"}), _Ctx()))
        assert r.winner is None
        assert r.details["checks"][0]["reason"] == "timeout"
        assert v._circuit._failures == 1

    def test_llm_exception_records_failure_and_continues(self):
        v = GroundedVerifier(llm_service=SimpleNamespace())  # no callable methods

        async def boom(answer, sources):
            raise RuntimeError("judge crashed")

        v._check_faithfulness = boom
        r = _run(v.verify(["A1"], _Step(parameters={"sources": "src"}), _Ctx()))
        assert r.winner is None
        assert r.details["checks"][0]["reason"] == "error: judge crashed"
        assert v._circuit._failures == 1

    def test_success_resets_circuit(self):
        v = GroundedVerifier(llm_service=_SyncLLM())
        v._circuit._failures = 4
        v._check_faithfulness = AsyncMock(
            return_value={"grounded": True, "rationale": "ok"}
        )
        r = _run(v.verify(["A1"], _Step(parameters={"sources": "src"}), _Ctx()))
        assert r.winner == "A1"
        assert v._circuit._failures == 0
        assert v._circuit._opened_at is None

    # -- _collect_sources ---------------------------------------------------

    def test_collect_sources_from_params_string(self):
        step = _Step(parameters={"sources": "single source"})
        assert GroundedVerifier._collect_sources(step, _Ctx()) == "single source"

    def test_collect_sources_from_params_list(self):
        step = _Step(parameters={"sources": ["a", "b"]})
        assert GroundedVerifier._collect_sources(step, _Ctx()) == "a\n\nb"

    def test_collect_sources_from_params_tuple(self):
        step = _Step(parameters={"sources": ("a", "b")})
        assert GroundedVerifier._collect_sources(step, _Ctx()) == "a\n\nb"

    def test_collect_sources_from_shared_context(self):
        step = _Step(parameters={})
        ctx = _Ctx(shared_context={"retrieved_context": ["d1", "d2"]})
        assert GroundedVerifier._collect_sources(step, ctx) == "d1\n\nd2"

    def test_collect_sources_scalar_fallback(self):
        step = _Step(parameters={"sources": 42})
        assert GroundedVerifier._collect_sources(step, _Ctx()) == "42"

    def test_collect_sources_empty_when_absent(self):
        assert GroundedVerifier._collect_sources(_Step(parameters={}), _Ctx()) == ""
        assert GroundedVerifier._collect_sources(SimpleNamespace(), _Ctx()) == ""
        ctx = _Ctx(shared_context={"other": 1})
        assert GroundedVerifier._collect_sources(_Step(parameters={}), ctx) == ""

    def test_collect_sources_shared_not_dict(self):
        ctx = SimpleNamespace(shared_context="not a dict")
        assert GroundedVerifier._collect_sources(_Step(parameters={}), ctx) == ""

    # -- _stringify ---------------------------------------------------------

    def test_stringify_dict_key_priority(self):
        assert GroundedVerifier._stringify({"answer": "a", "output": "o"}) == "a"
        assert GroundedVerifier._stringify({"output": "o", "text": "t"}) == "o"
        assert GroundedVerifier._stringify({"text": "t", "result": "r"}) == "t"
        assert GroundedVerifier._stringify({"result": "r"}) == "r"

    def test_stringify_fallback(self):
        assert GroundedVerifier._stringify("plain") == "plain"
        assert GroundedVerifier._stringify({"nope": 1}) == str({"nope": 1})

    # -- _check_faithfulness ------------------------------------------------

    def test_faithfulness_yes_with_rationale(self):
        v = GroundedVerifier(llm_service=_SyncLLM("YES\nbecause sources support it"))
        result = _run(v._check_faithfulness("a", "s"))
        assert result["grounded"] is True
        assert result["rationale"] == "because sources support it"

    def test_faithfulness_yes_lowercase(self):
        v = GroundedVerifier(llm_service=_SyncLLM("yes indeed\nlooks good"))
        result = _run(v._check_faithfulness("a", "s"))
        assert result["grounded"] is True

    def test_faithfulness_no(self):
        v = GroundedVerifier(llm_service=_SyncLLM("NO\nclaims overreach"))
        result = _run(v._check_faithfulness("a", "s"))
        assert result["grounded"] is False
        assert result["rationale"] == "claims overreach"

    def test_faithfulness_maybe_is_not_grounded(self):
        v = GroundedVerifier(llm_service=_SyncLLM("MAYBE\nunclear"))
        result = _run(v._check_faithfulness("a", "s"))
        assert result["grounded"] is False

    def test_faithfulness_single_line_response(self):
        v = GroundedVerifier(llm_service=_SyncLLM("YES"))
        result = _run(v._check_faithfulness("a", "s"))
        assert result["grounded"] is True
        assert result["rationale"] == ""

    def test_faithfulness_empty_response(self):
        v = GroundedVerifier(llm_service=_SyncLLM(""))
        result = _run(v._check_faithfulness("a", "s"))
        assert result["grounded"] is False
        assert result["rationale"] == ""

    # -- _call_llm ----------------------------------------------------------

    def test_call_llm_complete_sync(self):
        v = GroundedVerifier(llm_service=_SyncLLM("YES\nok", method="complete"))
        assert _run(v._call_llm("p")) == "YES\nok"

    def test_call_llm_complete_async(self):
        v = GroundedVerifier(llm_service=_AsyncLLM("YES\nok", method="complete"))
        assert _run(v._call_llm("p")) == "YES\nok"

    def test_call_llm_generate(self):
        v = GroundedVerifier(llm_service=_SyncLLM("YES\nok", method="generate"))
        assert _run(v._call_llm("p")) == "YES\nok"

    def test_call_llm_invoke(self):
        v = GroundedVerifier(llm_service=_SyncLLM("YES\nok", method="invoke"))
        assert _run(v._call_llm("p")) == "YES\nok"

    def test_call_llm_first_method_raising_falls_to_next(self):
        class Flaky:
            def complete(self, prompt):
                raise RuntimeError("down")

            def generate(self, prompt):
                return "YES\nrecovered"

        v = GroundedVerifier(llm_service=Flaky())
        assert _run(v._call_llm("p")) == "YES\nrecovered"

    def test_call_llm_no_callable_methods_raises(self):
        v = GroundedVerifier(llm_service=SimpleNamespace())
        with pytest.raises(RuntimeError, match="no callable complete/generate/invoke"):
            _run(v._call_llm("p"))

    def test_verify_with_no_callable_llm_degrades(self):
        v = GroundedVerifier(llm_service=SimpleNamespace())
        r = _run(v.verify(["a"], _Step(parameters={"sources": "s"}), _Ctx()))
        assert r.winner is None
        assert "no candidate judged grounded" in r.reason

    # -- circuit breaker ----------------------------------------------------

    def test_circuit_breaker_half_open_probe_allows(self):
        v = GroundedVerifier(llm_service=_SyncLLM("YES\nok"))
        v._circuit._failures = 5
        v._circuit._opened_at = 0.0  # long ago → cooldown elapsed → half-open
        assert v._circuit.allow() is True

    def test_circuit_breaker_opens_after_threshold(self):
        v = GroundedVerifier()
        cb = v._circuit
        for _ in range(4):
            cb.record_failure()
        assert cb.allow() is True          # below threshold
        cb.record_failure()                # hits threshold → opens + warning
        assert cb.allow() is False
        assert cb._opened_at is not None
        cb.record_failure()                # already open → no-op
        assert cb.allow() is False

    def test_circuit_breaker_success_resets(self):
        v = GroundedVerifier()
        cb = v._circuit
        cb.record_failure()
        cb.record_success()
        assert cb._failures == 0
        assert cb._opened_at is None
        assert cb.allow() is True


# ---------------------------------------------------------------------------
# 7. judge.py — LLM-as-judge ranking
# ---------------------------------------------------------------------------


class TestJudgeVerifier:
    def test_no_candidates_returns_empty(self):
        v = JudgeVerifier()
        r = _run(v.verify([], _Step(), _Ctx()))
        assert r.winner is None
        assert r.reason == "no candidates"

    def test_single_candidate_short_circuits(self):
        v = JudgeVerifier()
        r = _run(v.verify(["only"], _Step(), _Ctx()))
        assert r.winner == "only"
        assert r.confidence == 1.0
        assert r.details == {"candidate_count": 1}
        assert r.reason == "only one candidate"

    def test_no_llm_service_returns_empty(self):
        v = JudgeVerifier()
        r = _run(v.verify(["a", "b"], _Step(), _Ctx()))
        assert r.winner is None
        assert r.reason == "no LLM service configured for judging"

    def test_circuit_open_returns_empty(self):
        v = JudgeVerifier(llm_service=_SyncLLM("0, 1"))
        v._circuit._failures = 5
        v._circuit._opened_at = time.time()
        r = _run(v.verify(["a", "b"], _Step(), _Ctx()))
        assert r.winner is None
        assert r.reason == "circuit open (fail-open)"

    def test_ranking_selects_winner_through_display_order(self):
        v = JudgeVerifier(llm_service=_SyncLLM("1, 0", method="complete"))
        r = _run(v.verify(["c0", "c1"], _Step(), _Ctx()))
        assert r.details["ranking_display_positions"] == [1, 0]
        assert r.winner == "c1" or r.winner == "c0"
        # winner must equal candidates[display_order[ranking[0]]]
        assert r.winner == ["c0", "c1"][r.details["display_order"][1]]
        assert r.confidence == 0.5
        assert r.reason == "top-ranked by LLM judge"

    def test_confidence_half_for_two_candidates(self):
        v = JudgeVerifier(llm_service=_SyncLLM("0, 1"))
        r = _run(v.verify(["a", "b"], _Step(), _Ctx()))
        assert r.confidence == 0.5

    def test_timeout_returns_empty(self):
        class Slow:
            def complete(self, prompt):
                return "never used"

        v = JudgeVerifier(llm_service=Slow(), timeout_seconds=0.01)
        v._rank = _slow_rank
        r = _run(v.verify(["a", "b"], _Step(), _Ctx()))
        assert r.winner is None
        assert r.reason.startswith("LLM timeout after")
        assert v._circuit._failures == 1

    def test_llm_error_returns_empty(self):
        class Broken:
            def complete(self, prompt):
                raise RuntimeError("judge broken")

        v = JudgeVerifier(llm_service=Broken())
        r = _run(v.verify(["a", "b"], _Step(), _Ctx()))
        assert r.winner is None
        assert r.reason.startswith("LLM error:")
        assert v._circuit._failures == 1

    def test_success_resets_circuit(self):
        v = JudgeVerifier(llm_service=_SyncLLM("0, 1"))
        v._circuit._failures = 4
        r = _run(v.verify(["a", "b"], _Step(), _Ctx()))
        assert r.winner is not None
        assert v._circuit._failures == 0

    def test_default_domain_unknown(self):
        v = JudgeVerifier(llm_service=_SyncLLM("0, 1"))
        r = _run(v.verify(["a", "b"], _Step(), SimpleNamespace()))
        assert r.domain == "unknown"

    # -- circuit breaker ----------------------------------------------------

    def test_circuit_breaker_half_open_probe_allows(self):
        v = JudgeVerifier(llm_service=_SyncLLM("0, 1"))
        v._circuit._failures = 5
        v._circuit._opened_at = 0.0  # long ago → cooldown elapsed → half-open
        assert v._circuit.allow() is True

    def test_circuit_breaker_opens_after_threshold(self):
        v = JudgeVerifier()
        cb = v._circuit
        for _ in range(4):
            cb.record_failure()
        assert cb.allow() is True          # below threshold
        cb.record_failure()                # hits threshold → opens + warning
        assert cb.allow() is False
        assert cb._opened_at is not None
        cb.record_failure()                # already open → no-op
        assert cb.allow() is False

    def test_circuit_breaker_success_resets(self):
        v = JudgeVerifier()
        cb = v._circuit
        cb.record_failure()
        cb.record_success()
        assert cb._failures == 0
        assert cb._opened_at is None
        assert cb.allow() is True

    # -- _task_description --------------------------------------------------

    def test_task_description_from_description(self):
        step = _Step(description="write a poem", name="named", capability="cap")
        assert JudgeVerifier._task_description(step) == "write a poem"

    def test_task_description_from_name(self):
        step = _Step(description="", name="named")
        assert JudgeVerifier._task_description(step) == "named"

    def test_task_description_from_capability(self):
        step = _Step(description="", name="", capability="cap")
        assert JudgeVerifier._task_description(step) == "cap"

    def test_task_description_from_parameters_prompt(self):
        step = _Step(parameters={"prompt": "the prompt"})
        assert JudgeVerifier._task_description(step) == "the prompt"

    def test_task_description_from_parameters_task(self):
        step = _Step(parameters={"task": "the task"})
        assert JudgeVerifier._task_description(step) == "the task"

    def test_task_description_fallback(self):
        assert JudgeVerifier._task_description(SimpleNamespace()) == "(no task description provided)"
        assert JudgeVerifier._task_description(_Step(parameters={"other": 1})) == "(no task description provided)"

    # -- _stringify ---------------------------------------------------------

    def test_stringify_dict_keys(self):
        assert JudgeVerifier._stringify({"output": "o", "text": "t"}) == "o"
        assert JudgeVerifier._stringify({"text": "t", "answer": "a"}) == "t"
        assert JudgeVerifier._stringify({"answer": "a", "result": "r"}) == "a"
        assert JudgeVerifier._stringify({"result": "r"}) == "r"

    def test_stringify_fallback(self):
        assert JudgeVerifier._stringify("plain") == "plain"
        assert JudgeVerifier._stringify(5) == "5"
        assert JudgeVerifier._stringify({"nope": 1}) == str({"nope": 1})

    # -- _rank --------------------------------------------------------------

    def test_rank_builds_prompt_and_parses(self):
        v = JudgeVerifier(llm_service=_SyncLLM("2, 0, 1"))
        ranking = _run(v._rank(["c0", "c1", "c2"], [2, 0, 1], "task x"))
        assert ranking == [2, 0, 1]

    def test_rank_truncates_long_candidates(self):
        captured = {}

        class CaptureLLM:
            def complete(self, prompt):
                captured["prompt"] = prompt
                return "0"

        v = JudgeVerifier(llm_service=CaptureLLM())
        long_text = "x" * 5000
        _run(v._rank([long_text, "short"], [0, 1], "t"))
        prompt = captured["prompt"]
        assert "…[truncated]" in prompt
        assert "x" * 5000 not in prompt  # truncated, not full
        assert "[1] short" in prompt

    def test_rank_truncated_length(self):
        captured = {}

        class CaptureLLM:
            def complete(self, prompt):
                captured["prompt"] = prompt
                return "0"

        v = JudgeVerifier(llm_service=CaptureLLM())
        long_text = "x" * 4001
        _run(v._rank([long_text], [0], "t"))
        marker = "…[truncated]"
        assert marker in captured["prompt"]
        line = next(l for l in captured["prompt"].split("\n") if l.startswith("[0] "))
        assert line == "[0] " + "x" * 4000 + marker

    # -- _parse_ranking -----------------------------------------------------

    def test_parse_ranking_simple(self):
        assert JudgeVerifier._parse_ranking("2, 0, 1", 3) == [2, 0, 1]

    def test_parse_ranking_leading_prose(self):
        # tokens are comma-separated; "Here is my ranking: 1" is not a digit token
        assert JudgeVerifier._parse_ranking("Here is my ranking: 1, 0, 2", 3) == [0, 2, 1]

    def test_parse_ranking_semicolons(self):
        assert JudgeVerifier._parse_ranking("1; 0; 2", 3) == [1, 0, 2]

    def test_parse_ranking_brackets(self):
        assert JudgeVerifier._parse_ranking("[1], [0], [2]", 3) == [1, 0, 2]

    def test_parse_ranking_duplicates_and_out_of_range(self):
        assert JudgeVerifier._parse_ranking("9, 1, 1, -1, 2", 4) == [1, 2, 0, 3]

    def test_parse_ranking_backfills_omitted(self):
        assert JudgeVerifier._parse_ranking("0, 1", 3) == [0, 1, 2]

    def test_parse_ranking_empty_backfills_all(self):
        assert JudgeVerifier._parse_ranking("", 3) == [0, 1, 2]
        assert JudgeVerifier._parse_ranking("no numbers here", 2) == [0, 1]

    # -- _call_llm ----------------------------------------------------------

    def test_call_llm_complete_sync(self):
        v = JudgeVerifier(llm_service=_SyncLLM("0, 1", method="complete"))
        assert _run(v._call_llm("p")) == "0, 1"

    def test_call_llm_complete_async(self):
        v = JudgeVerifier(llm_service=_AsyncLLM("0, 1", method="complete"))
        assert _run(v._call_llm("p")) == "0, 1"

    def test_call_llm_generate(self):
        v = JudgeVerifier(llm_service=_SyncLLM("0, 1", method="generate"))
        assert _run(v._call_llm("p")) == "0, 1"

    def test_call_llm_invoke(self):
        v = JudgeVerifier(llm_service=_SyncLLM("0, 1", method="invoke"))
        assert _run(v._call_llm("p")) == "0, 1"

    def test_call_llm_skips_raising_method(self):
        class Flaky:
            def complete(self, prompt):
                raise RuntimeError("down")

            def invoke(self, prompt):
                return "1, 0"

        v = JudgeVerifier(llm_service=Flaky())
        assert _run(v._call_llm("p")) == "1, 0"

    def test_call_llm_no_methods_raises(self):
        v = JudgeVerifier(llm_service=SimpleNamespace())
        with pytest.raises(RuntimeError, match="no callable complete/generate/invoke"):
            _run(v._call_llm("p"))


async def _slow_rank(candidates, display_order, task_desc):
    await asyncio.sleep(0.2)
    return [0]


# ---------------------------------------------------------------------------
# 8. code_pipeline.py — reconcile then execute
# ---------------------------------------------------------------------------


class TestCodePipelineVerifier:
    def test_constructor_defaults_build_fresh_stages(self):
        v = CodePipelineVerifier()
        from core.orchestration.verification.voting import VotingVerifier
        from core.orchestration.verification.execution import ExecutionVerifier

        assert isinstance(v._voting, VotingVerifier)
        assert isinstance(v._execution, ExecutionVerifier)

    def test_constructor_with_sandbox_runtime(self):
        runtime = MagicMock()
        v = CodePipelineVerifier(sandbox_runtime=runtime)
        assert v._execution._sandbox_runtime is runtime

    def test_constructor_with_injected_stages(self):
        voting = MagicMock()
        execution = MagicMock()
        v = CodePipelineVerifier(voting_verifier=voting, execution_verifier=execution)
        assert v._voting is voting
        assert v._execution is execution

    def test_no_candidates_returns_empty(self):
        v = CodePipelineVerifier()
        r = _run(v.verify([], _Step(), _Ctx(resolved_domain=TaskDomain.CODE)))
        assert r.winner is None
        assert r.strategy is VerificationStrategy.CODE_PIPELINE
        assert r.reason == "no candidates"

    def test_reconcile_stage_producing_nothing_returns_none(self):
        voting = MagicMock()
        voting.verify = AsyncMock(
            return_value=VerificationResult.empty(TaskDomain.CODE, VerificationStrategy.VOTING)
        )
        v = CodePipelineVerifier(voting_verifier=voting, execution_verifier=MagicMock())
        r = _run(v.verify([{"action": "read"}], _Step(), _Ctx(resolved_domain=TaskDomain.CODE)))
        assert r.winner is None
        assert r.details["stage_2"]["skipped"] is True
        assert r.reason == "reconcile stage produced no candidate"

    def test_pure_action_plan_skips_execution(self):
        voting = MagicMock()
        voting.verify = AsyncMock(
            return_value=VerificationResult(
                winner={"action": "read", "target": "f.py"},
                strategy=VerificationStrategy.VOTING,
                domain=TaskDomain.CODE,
                confidence=0.6,
            )
        )
        v = CodePipelineVerifier(voting_verifier=voting, execution_verifier=MagicMock())
        r = _run(v.verify([{"action": "read", "target": "f.py"}], _Step(), _Ctx(resolved_domain=TaskDomain.CODE)))
        assert r.winner == {"action": "read", "target": "f.py"}
        assert r.confidence == 0.6
        assert r.details["stage_2"]["skipped"] is True
        assert r.details["stage_2"]["reason"] == "no code in reconciled candidate"
        assert r.reason == "reconciled action dicts; no code to execute"

    def test_execution_pass_returns_reconciled_winner(self):
        voting = MagicMock()
        voting.verify = AsyncMock(
            return_value=VerificationResult(
                winner={"code": "print(1)"},
                strategy=VerificationStrategy.VOTING,
                domain=TaskDomain.CODE,
                confidence=0.8,
                details={"mode": "reconciled"},
            )
        )
        execution = MagicMock()
        execution.verify = AsyncMock(
            return_value=VerificationResult(
                winner={"code": "print(1)"},
                strategy=VerificationStrategy.EXECUTION,
                domain=TaskDomain.CODE,
                confidence=1.0,
                details={"exit_code": 0},
            )
        )
        v = CodePipelineVerifier(voting_verifier=voting, execution_verifier=execution)
        r = _run(v.verify([{"code": "print(1)"}], _Step(), _Ctx(resolved_domain=TaskDomain.CODE)))
        assert r.winner == {"code": "print(1)"}
        assert r.confidence == 1.0
        assert r.details["stage_2"]["exit_code"] == 0
        assert r.reason == "reconciled action dicts; code passed execution verification"

    def test_sandbox_unavailable_skips_execution_stage(self):
        voting = MagicMock()
        voting.verify = AsyncMock(
            return_value=VerificationResult(
                winner={"code": "print(1)"},
                strategy=VerificationStrategy.VOTING,
                domain=TaskDomain.CODE,
                confidence=0.6,
            )
        )
        execution = MagicMock()
        execution.verify = AsyncMock(
            return_value=VerificationResult.empty(
                TaskDomain.CODE, VerificationStrategy.EXECUTION,
                reason="sandbox runtime unavailable: no docker",
            )
        )
        v = CodePipelineVerifier(voting_verifier=voting, execution_verifier=execution)
        step = _Step(step_id="s-code")
        r = _run(v.verify([{"code": "print(1)"}], step, _Ctx(resolved_domain=TaskDomain.CODE)))
        assert r.winner == {"code": "print(1)"}
        assert r.confidence == 0.6
        assert r.details["stage_2"]["skipped"] is True
        assert r.reason == "reconciled action dicts; execution skipped (sandbox runtime unavailable: no docker)"

    def test_execution_failure_trips_correctness_gate(self):
        voting = MagicMock()
        voting.verify = AsyncMock(
            return_value=VerificationResult(
                winner={"code": "print(1)"},
                strategy=VerificationStrategy.VOTING,
                domain=TaskDomain.CODE,
                confidence=0.6,
            )
        )
        execution = MagicMock()
        execution.verify = AsyncMock(
            return_value=VerificationResult(
                winner=None,
                strategy=VerificationStrategy.EXECUTION,
                domain=TaskDomain.CODE,
                confidence=0.0,
                details={"attempts": []},
                reason="no candidate passed execution-based verification",
            )
        )
        v = CodePipelineVerifier(voting_verifier=voting, execution_verifier=execution)
        r = _run(v.verify([{"code": "print(1)"}], _Step(), _Ctx(resolved_domain=TaskDomain.CODE)))
        assert r.winner is None
        assert r.confidence == 0.0
        assert r.details["stage_2_reason"] == "no candidate passed execution-based verification"
        assert r.reason == "reconciled code failed execution: no candidate passed execution-based verification"

    def test_domain_defaults_to_unknown(self):
        voting = MagicMock()
        voting.verify = AsyncMock(
            return_value=VerificationResult(
                winner={"action": "read"}, strategy=VerificationStrategy.VOTING,
                domain="unknown", confidence=1.0,
            )
        )
        v = CodePipelineVerifier(voting_verifier=voting, execution_verifier=MagicMock())
        r = _run(v.verify([{"action": "read"}], _Step(), SimpleNamespace()))
        assert r.domain == "unknown"


# ---------------------------------------------------------------------------
# 9. review.py — reviewer accept/reject + re-delegation signal
# ---------------------------------------------------------------------------


class TestReviewerVerifier:
    def test_no_candidates_returns_empty(self):
        v = ReviewerVerifier()
        r = _run(v.verify([], _Step(), _Ctx()))
        assert r.winner is None
        assert r.reason == "no candidates"

    def test_no_llm_accepts_without_review(self):
        v = ReviewerVerifier()
        r = _run(v.verify([{"answer": "x"}], _Step(), _Ctx()))
        assert r.winner == {"answer": "x"}
        assert r.confidence == 0.5
        assert r.details == {"reviewed": False}
        assert r.reason == "no LLM service; accepted without review"

    def test_accept_verdict_keeps_winner(self):
        v = ReviewerVerifier(llm_service=_SyncLLM(
            '{"accept": true, "score": 0.9, "feedback": "solid"}'
        ))
        r = _run(v.verify(["candidate"], _Step(), _Ctx()))
        assert r.winner == "candidate"
        assert r.confidence == 0.9
        assert r.details["reviewed"] is True
        assert r.details["accepted"] is True
        assert r.details["feedback"] == "solid"
        assert r.reason == "review accepted"

    def test_reject_verdict_signals_redelegation(self):
        v = ReviewerVerifier(llm_service=_SyncLLM(
            '{"accept": false, "score": 0.3, "feedback": "lacks evidence"}'
        ))
        r = _run(v.verify(["candidate"], _Step(), _Ctx()))
        assert r.winner is None
        assert r.confidence == 0.3
        assert r.details["accepted"] is False
        assert r.reason == "review rejected — re-delegate: lacks evidence"

    def test_empty_verdict_defaults_accept(self):
        v = ReviewerVerifier(llm_service=_SyncLLM("{}"))
        r = _run(v.verify(["candidate"], _Step(), _Ctx()))
        assert r.winner == "candidate"
        assert r.confidence == 0.7
        assert r.details["accepted"] is True

    def test_first_candidate_is_reviewed(self):
        v = ReviewerVerifier(llm_service=_SyncLLM('{"accept": false, "score": 0.2, "feedback": "no"}'))
        r = _run(v.verify(["first", "second"], _Step(), _Ctx()))
        assert r.winner is None  # first rejected

    def test_timeout_fails_open_to_winner(self):
        class Slow:
            def complete(self, prompt):
                raise RuntimeError("never")

        v = ReviewerVerifier(llm_service=Slow(), timeout_seconds=0.01)
        v._review = _slow_review
        r = _run(v.verify(["candidate"], _Step(), _Ctx()))
        assert r.winner == "candidate"
        assert r.confidence == 0.5
        assert r.details == {"reviewed": False}
        assert r.reason.startswith("review timed out after")

    def test_review_error_fails_open_to_winner(self):
        async def broken_review(candidate, task_desc):
            raise RuntimeError("reviewer crashed")

        v = ReviewerVerifier(llm_service=MagicMock())
        v._review = broken_review
        r = _run(v.verify(["candidate"], _Step(), _Ctx()))
        assert r.winner == "candidate"
        assert r.confidence == 0.5
        assert r.reason == "review errored (reviewer crashed); accepted"

    def test_default_domain_unknown(self):
        v = ReviewerVerifier(llm_service=_SyncLLM('{"accept": true}'))
        r = _run(v.verify(["c"], _Step(), SimpleNamespace()))
        assert r.domain == "unknown"

    # -- _task_description --------------------------------------------------

    def test_task_description_step_none(self):
        assert ReviewerVerifier()._task_description(None) == "(unknown task)"

    def test_task_description_uses_description(self):
        v = ReviewerVerifier()
        assert v._task_description(_Step(description="desc")) == "desc"

    def test_task_description_uses_prompt(self):
        v = ReviewerVerifier()
        step = _Step().without("description")
        step.prompt = "the prompt"
        assert v._task_description(step) == "the prompt"

    def test_task_description_falls_back_to_step_str(self):
        v = ReviewerVerifier()
        step = SimpleNamespace()
        assert v._task_description(step) == str(step)

    # -- _serialise ---------------------------------------------------------

    def test_serialise_success(self):
        assert ReviewerVerifier._serialise({"a": 1}) == '{"a": 1}'

    def test_serialise_fallback_on_serialisation_error(self):
        candidate = {"x": {1, 2}}  # json.dumps raises TypeError on sets
        result = ReviewerVerifier._serialise(candidate)
        assert result == str(candidate)[:2000]

    def test_review_prompt_serialises_failing_candidate(self):
        v = ReviewerVerifier(llm_service=_SyncLLM('{"accept": true, "score": 0.8, "feedback": ""}'))
        r = _run(v.verify([{"x": {1, 2}}], _Step(description="task"), _Ctx()))
        assert r.winner == {"x": {1, 2}}
        assert r.details["reviewed"] is True

    # -- _llm_complete ------------------------------------------------------

    def test_llm_complete_generate_response(self):
        v = ReviewerVerifier(llm_service=_SyncLLM('{"accept": true}', method="generate_response"))
        assert _run(v._llm_complete("p")) == '{"accept": true}'

    def test_llm_complete_complete(self):
        v = ReviewerVerifier(llm_service=_SyncLLM('{"accept": true}', method="complete"))
        assert _run(v._llm_complete("p")) == '{"accept": true}'

    def test_llm_complete_invoke(self):
        v = ReviewerVerifier(llm_service=_SyncLLM('{"accept": true}', method="invoke"))
        assert _run(v._llm_complete("p")) == '{"accept": true}'

    def test_llm_complete_generate(self):
        v = ReviewerVerifier(llm_service=_SyncLLM('{"accept": true}', method="generate"))
        assert _run(v._llm_complete("p")) == '{"accept": true}'

    def test_llm_complete_async_result(self):
        v = ReviewerVerifier(llm_service=_AsyncLLM('{"accept": true}', method="complete"))
        assert _run(v._llm_complete("p")) == '{"accept": true}'

    def test_llm_complete_none_result_becomes_empty(self):
        class NoneLLM:
            def complete(self, prompt):
                return None

        v = ReviewerVerifier(llm_service=NoneLLM())
        assert _run(v._llm_complete("p")) == ""

    def test_llm_complete_missing_early_methods_skipped(self):
        v = ReviewerVerifier(llm_service=_SyncLLM('{"accept": true}', method="complete"))
        assert _run(v._llm_complete("p")) == '{"accept": true}'

    def test_llm_complete_keyword_only_signature(self):
        class KwargsLLM:
            def generate_response(self, *, prompt):
                return '{"accept": true, "score": 0.8, "feedback": "kw"}'

        v = ReviewerVerifier(llm_service=KwargsLLM())
        assert _run(v._llm_complete("p")) == '{"accept": true, "score": 0.8, "feedback": "kw"}'

    def test_llm_complete_keyword_only_async_signature(self):
        class KwargsAsyncLLM:
            async def generate_response(self, *, prompt):
                return '{"accept": true}'

        v = ReviewerVerifier(llm_service=KwargsAsyncLLM())
        assert _run(v._llm_complete("p")) == '{"accept": true}'

    def test_llm_complete_kwargs_form_also_fails(self):
        class KwargsFailLLM:
            def complete(self, *, prompt):
                raise ValueError("nope")

        v = ReviewerVerifier(llm_service=KwargsFailLLM())
        assert _run(v._llm_complete("p")) == ""

    def test_llm_complete_positional_exception_falls_to_next(self):
        class PositionalFailLLM:
            def generate_response(self, prompt):
                raise ValueError("positional boom")

            def complete(self, prompt):
                return '{"accept": true}'

        v = ReviewerVerifier(llm_service=PositionalFailLLM())
        assert _run(v._llm_complete("p")) == '{"accept": true}'

    def test_llm_complete_no_methods_returns_empty(self):
        v = ReviewerVerifier(llm_service=SimpleNamespace())
        assert _run(v._llm_complete("p")) == ""

    # -- _parse_verdict -----------------------------------------------------

    def test_parse_verdict_empty(self):
        assert ReviewerVerifier._parse_verdict("") == {"accept": True, "score": 0.7, "feedback": ""}

    def test_parse_verdict_json(self):
        assert ReviewerVerifier._parse_verdict('{"accept": false, "score": 0.2, "feedback": "gap"}') == {
            "accept": False, "score": 0.2, "feedback": "gap"
        }

    def test_parse_verdict_embedded_in_prose(self):
        verdict = ReviewerVerifier._parse_verdict(
            'Here is my verdict: {"accept": true, "score": 0.9, "feedback": "good"} — done.'
        )
        assert verdict["accept"] is True
        assert verdict["score"] == 0.9

    def test_parse_verdict_invalid_json_falls_back(self):
        assert ReviewerVerifier._parse_verdict("no braces at all") == {
            "accept": True, "score": 0.7, "feedback": ""
        }

    def test_parse_verdict_braces_but_invalid(self):
        assert ReviewerVerifier._parse_verdict("x {not json} y") == {
            "accept": True, "score": 0.7, "feedback": ""
        }


async def _slow_review(candidate, task_desc):
    await asyncio.sleep(0.2)
    return {"accept": True, "score": 0.5, "feedback": ""}


# ---------------------------------------------------------------------------
# 10. domain.py — task-domain classification + strategy resolution
# ---------------------------------------------------------------------------


class TestTaskDomainAndMap:
    def test_enum_values(self):
        assert TaskDomain.UNKNOWN.value == "unknown"
        assert TaskDomain.CODE.value == "code"
        assert TaskDomain.MATH.value == "math"
        assert TaskDomain.QA.value == "qa"
        assert TaskDomain.EXTRACTION.value == "extraction"
        assert TaskDomain.PLANNING.value == "planning"
        assert TaskDomain.PROSE.value == "prose"

    def test_domain_strategy_map(self):
        assert DOMAIN_STRATEGY_MAP[TaskDomain.UNKNOWN] is VerificationStrategy.VOTING
        assert DOMAIN_STRATEGY_MAP[TaskDomain.CODE] is VerificationStrategy.CODE_PIPELINE
        assert DOMAIN_STRATEGY_MAP[TaskDomain.MATH] is VerificationStrategy.FORMAL
        assert DOMAIN_STRATEGY_MAP[TaskDomain.QA] is VerificationStrategy.GROUNDED
        assert DOMAIN_STRATEGY_MAP[TaskDomain.EXTRACTION] is VerificationStrategy.SCHEMA
        assert DOMAIN_STRATEGY_MAP[TaskDomain.PLANNING] is VerificationStrategy.VOTING
        assert DOMAIN_STRATEGY_MAP[TaskDomain.PROSE] is VerificationStrategy.JUDGE


class TestInferDomain:
    def test_empty_step_returns_unknown(self):
        assert infer_domain(_Step()) == TaskDomain.UNKNOWN

    def test_step_without_text_attrs_returns_unknown(self):
        step = SimpleNamespace()  # no capability/name/description/parameters
        assert infer_domain(step) == TaskDomain.UNKNOWN

    def test_code_keywords(self):
        assert infer_domain(_Step(description="implement a python function")) == TaskDomain.CODE

    def test_math_keywords(self):
        assert infer_domain(_Step(description="solve this equation and compute the integral")) == TaskDomain.MATH

    def test_qa_keywords(self):
        assert infer_domain(_Step(description="answer this question citing the document")) == TaskDomain.QA

    def test_extraction_keywords(self):
        assert infer_domain(_Step(description="extract entities and parse into json schema")) == TaskDomain.EXTRACTION

    def test_planning_keywords(self):
        assert infer_domain(_Step(description="plan a workflow and orchestrate agents")) == TaskDomain.PLANNING

    def test_prose_keywords(self):
        assert infer_domain(_Step(description="write a draft email")) == TaskDomain.PROSE

    def test_capability_field_scored(self):
        assert infer_domain(_Step(capability="summarize reports")) == TaskDomain.PROSE

    def test_name_field_scored(self):
        assert infer_domain(_Step(name="debug the api endpoint")) == TaskDomain.CODE

    def test_no_keyword_hits_returns_unknown(self):
        assert infer_domain(_Step(description="zebra giraffe")) == TaskDomain.UNKNOWN

    def test_tie_between_domains_returns_unknown(self):
        assert infer_domain(_Step(description="write calculate")) == TaskDomain.UNKNOWN

    def test_best_score_wins(self):
        assert infer_domain(_Step(description="write a draft email and compute")) == TaskDomain.PROSE

    def test_parameters_keywords_count(self):
        assert infer_domain(_Step(parameters={"query": "refactor the class"})) == TaskDomain.CODE

    def test_non_dict_parameters_str_dump(self):
        assert infer_domain(_Step(parameters="plan the workflow")) == TaskDomain.PLANNING

    def test_parameters_json_failure_falls_back_to_str(self):
        class BadStr:
            def __str__(self):
                raise ValueError("cannot stringify")

        # json.dumps(default=str) calls str() → raises ValueError → caught
        assert infer_domain(_Step(parameters={"bad": BadStr()})) == TaskDomain.UNKNOWN

    def test_empty_parameters_ignored(self):
        assert infer_domain(_Step(parameters={})) == TaskDomain.UNKNOWN

    def test_text_is_lowercased(self):
        assert infer_domain(_Step(description="WRITE A REPORT")) == TaskDomain.PROSE


class TestResolveDomain:
    def test_no_parameters_uses_inference(self):
        step = _Step(description="implement a function")
        assert resolve_domain(step) == TaskDomain.CODE

    def test_params_not_dict_uses_inference(self):
        step = _Step(parameters="implement a function")
        assert resolve_domain(step) == TaskDomain.CODE

    def test_tag_none_uses_inference(self):
        step = _Step(description="write a draft", parameters={"task_domain": None})
        assert resolve_domain(step) == TaskDomain.PROSE

    def test_tag_enum_instance(self):
        step = _Step(parameters={"task_domain": TaskDomain.MATH})
        assert resolve_domain(step) == TaskDomain.MATH

    def test_tag_value_string(self):
        step = _Step(parameters={"task_domain": "code"})
        assert resolve_domain(step) == TaskDomain.CODE

    def test_tag_name_string(self):
        step = _Step(parameters={"task_domain": "CODE"})
        assert resolve_domain(step) == TaskDomain.CODE

    def test_tag_name_case_insensitive(self):
        step = _Step(parameters={"task_domain": "Math"})
        assert resolve_domain(step) == TaskDomain.MATH

    def test_tag_unrecognised_falls_back_to_inference(self, caplog):
        caplog.set_level(10, logger="core.orchestration.verification.domain")
        step = _Step(description="write a draft", parameters={"task_domain": "banana"})
        assert resolve_domain(step) == TaskDomain.PROSE
        assert any("Unrecognised task_domain" in r.message for r in caplog.records)

    def test_coerce_domain_other_types_none(self):
        assert _coerce_domain(123) is None
        assert _coerce_domain(["code"]) is None

    def test_unrecognised_tag_logs_step_id(self, caplog):
        caplog.set_level(10, logger="core.orchestration.verification.domain")
        step = _Step(step_id="s-7", description="write", parameters={"task_domain": "nope"})
        resolve_domain(step)
        assert any("s-7" in r.message for r in caplog.records)


class TestResolveStrategy:
    def test_no_parameters_uses_map(self):
        assert resolve_strategy(_Step(), TaskDomain.CODE) is VerificationStrategy.CODE_PIPELINE

    def test_params_not_dict_uses_map(self):
        assert resolve_strategy(_Step(parameters="x"), TaskDomain.MATH) is VerificationStrategy.FORMAL

    def test_explicit_enum_override(self):
        step = _Step(parameters={"verification_strategy": VerificationStrategy.JUDGE})
        assert resolve_strategy(step, TaskDomain.PLANNING) is VerificationStrategy.JUDGE

    def test_explicit_string_override(self):
        step = _Step(parameters={"verification_strategy": "review"})
        assert resolve_strategy(step, TaskDomain.PROSE) is VerificationStrategy.REVIEW

    def test_explicit_name_string_override(self):
        step = _Step(parameters={"verification_strategy": "CODE_PIPELINE"})
        assert resolve_strategy(step, TaskDomain.UNKNOWN) is VerificationStrategy.CODE_PIPELINE

    def test_explicit_case_insensitive(self):
        step = _Step(parameters={"verification_strategy": "Formal"})
        assert resolve_strategy(step, TaskDomain.UNKNOWN) is VerificationStrategy.FORMAL

    def test_unrecognised_strategy_uses_map(self, caplog):
        caplog.set_level(10, logger="core.orchestration.verification.domain")
        step = _Step(parameters={"verification_strategy": "bogus"})
        assert resolve_strategy(step, TaskDomain.EXTRACTION) is VerificationStrategy.SCHEMA
        assert any("Unrecognised verification_strategy" in r.message for r in caplog.records)

    def test_custom_map_used(self):
        custom = {TaskDomain.CODE: VerificationStrategy.JUDGE}
        assert resolve_strategy(_Step(), TaskDomain.CODE, custom) is VerificationStrategy.JUDGE

    def test_missing_domain_defaults_voting(self):
        assert resolve_strategy(_Step(), TaskDomain.MATH, {}) is VerificationStrategy.VOTING

    def test_coerce_strategy_other_types_none(self):
        assert _coerce_strategy(42) is None
        assert _coerce_strategy(["voting"]) is None

    def test_strategy_tag_with_params_none(self):
        step = _Step(parameters=None)
        assert resolve_strategy(step, TaskDomain.QA) is VerificationStrategy.GROUNDED
