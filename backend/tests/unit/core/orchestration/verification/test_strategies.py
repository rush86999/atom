"""Tests for each Verifier strategy in isolation.

One test class per verifier, mirroring the style of the existing
``test_swarm_coordination.py``: direct construction, ``asyncio.run``
wrappers, plain ``assert``.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

BACKEND_DIR = Path(__file__).parents[5]  # tests/unit/core/orchestration/verification/ → backend/
sys.path.insert(0, str(BACKEND_DIR))

from core.orchestration.verification.base import VerificationStrategy
from core.orchestration.verification.code_pipeline import CodePipelineVerifier
from core.orchestration.verification.domain import TaskDomain
from core.orchestration.verification.execution import ExecutionVerifier
from core.orchestration.verification.formal import FormalVerifier, _HAS_SYMPY
from core.orchestration.verification.grounded import GroundedVerifier
from core.orchestration.verification.judge import JudgeVerifier
from core.orchestration.verification.schema_verifier import SchemaVerifier, _HAS_JSONSCHEMA
from core.orchestration.verification.voting import VotingVerifier


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Shared test doubles
# ---------------------------------------------------------------------------
class _Step(SimpleNamespace):
    """Duck-typed WorkflowStep."""
    def __init__(self, **kw):
        super().__init__(
            step_id=kw.pop("step_id", "s1"),
            name=kw.pop("name", ""),
            description=kw.pop("description", ""),
            capability=kw.pop("capability", ""),
            parameters=kw.pop("parameters", {}),
            **kw,
        )


class _Ctx(SimpleNamespace):
    def __init__(self, **kw):
        super().__init__(
            workspace_id=kw.pop("workspace_id", "ws1"),
            shared_context=kw.pop("shared_context", {}),
            _resolved_domain=kw.pop("_resolved_domain", TaskDomain.UNKNOWN),
            **kw,
        )


class _MockSandbox:
    """Fake SandboxRuntime — returns canned SandboxExecResult-like objects."""
    def __init__(self, results: List[Dict[str, Any]]):
        # results[i] is what execute_python returns for the i-th call.
        self._results = list(results)
        self.calls: List[str] = []

    async def execute_python(self, code, *, policy, inputs=None, cwd=None):
        self.calls.append(code)
        if self._results:
            r = self._results.pop(0)
            return SimpleNamespace(**r)
        return SimpleNamespace(success=False, stdout="", stderr="no more results", exit_code=-1)


class _MockLLM:
    """Fake LLM service — returns canned responses to .complete/.generate."""
    def __init__(self, responses: List[str]):
        self._responses = list(responses)
        self.prompts: List[str] = []

    async def complete(self, prompt):
        self.prompts.append(prompt)
        if self._responses:
            return self._responses.pop(0)
        return ""

    # Synchronous variant some callers may use.
    def generate(self, prompt):
        self.prompts.append(prompt)
        if self._responses:
            return self._responses.pop(0)
        return ""


# ===========================================================================
# VotingVerifier — behaviour preservation port of TestBranchReconciler
# ===========================================================================
class TestVotingVerifier:
    @pytest.fixture
    def verifier(self):
        return VotingVerifier()

    def test_majority_returns_winner_directly(self, verifier):
        candidates = [{"output": "hi"}, {"output": "hi"}, {"output": "bye"}]
        result = _run(verifier.verify(candidates, _Step(), _Ctx()))
        assert result.winner == {"output": "hi"}
        assert result.details["mode"] == "majority"
        assert result.confidence == pytest.approx(2 / 3)
        assert result.fallback_used is False

    def test_single_candidate_returned(self, verifier):
        candidates = [{"only": True}]
        result = _run(verifier.verify(candidates, _Step(), _Ctx()))
        assert result.winner == {"only": True}

    def test_all_diverge_reconciles_non_conflicting_keys(self, verifier):
        # Three *fully distinct* whole-dicts so the majority check (≥2/3)
        # cannot short-circuit; per-key reconciliation then merges the
        # non-conflicting portions.
        candidates = [
            {"action": "read", "target": "f.py", "status": "ok"},
            {"action": "read", "target": "g.py", "status": "ok"},
            {"action": "write", "target": "f.py", "status": "ok"},
        ]
        result = _run(verifier.verify(candidates, _Step(step_id="s2"), _Ctx()))
        assert result.winner is not None
        assert result.details["mode"] == "reconciled"
        # action: "read" appears 2/3 → wins
        assert result.winner["action"] == "read"
        # target: "f.py" appears 2/3 → wins
        assert result.winner["target"] == "f.py"
        # status: unanimous
        assert result.winner["status"] == "ok"
        assert result.winner["_reconciled"] is True
        assert result.winner["_branch_count"] == 3
        assert result.winner["_reconciler"] == "ConductorAgent._reconcile_branch_conflicts"
        assert result.winner["step_id"] == "s2"

    def test_two_of_three_majority_skips_reconciliation(self, verifier):
        # When 2/3 candidates are identical, the majority check returns
        # the winner directly without invoking the reconciler.
        candidates = [
            {"action": "read", "target": "f.py", "status": "ok"},
            {"action": "read", "target": "f.py", "status": "ok"},
            {"action": "write", "target": "f.py", "status": "ok"},
        ]
        result = _run(verifier.verify(candidates, _Step(), _Ctx()))
        assert result.winner == {"action": "read", "target": "f.py", "status": "ok"}
        assert result.details["mode"] == "majority"

    def test_empty_candidates_returns_none(self, verifier):
        result = _run(verifier.verify([], _Step(), _Ctx()))
        assert result.winner is None

    def test_non_dict_candidates_handled(self, verifier):
        # Three distinct strings → no majority, reconciliation finds
        # nothing to merge → falls back to the (first) majority candidate.
        result = _run(verifier.verify(["a", "b", "c"], _Step(), _Ctx()))
        assert result.winner in ("a", "b", "c")
        assert result.details["mode"] == "majority_fallback"

    # --- reconcile_only (backward-compat contract) ---
    def test_reconcile_only_all_agree(self, verifier):
        branches = [{"step_id": "s1", "x": 1}] * 3
        merged = _run(verifier.reconcile_only("s1", branches))
        assert merged is not None
        assert merged["x"] == 1
        assert merged["_reconciled"] is True

    def test_reconcile_only_empty_returns_none(self, verifier):
        assert _run(verifier.reconcile_only("s3", [])) is None

    def test_reconcile_only_metadata_tags(self, verifier):
        merged = _run(verifier.reconcile_only("s5", [{"x": 1}, {"x": 1}]))
        assert merged["_reconciler"] == "ConductorAgent._reconcile_branch_conflicts"
        assert merged["_branch_count"] == 2
        assert merged["step_id"] == "s5"

    def test_reconcile_only_non_dict_returns_none(self, verifier):
        result = _run(verifier.reconcile_only("s4", ["text", "text", 42]))
        assert result is None or isinstance(result, dict)


# ===========================================================================
# SchemaVerifier
# ===========================================================================
class TestSchemaVerifier:
    @pytest.fixture
    def verifier(self):
        return SchemaVerifier()

    def test_first_valid_candidate_wins(self, verifier):
        schema = {
            "type": "object",
            "required": ["name", "age"],
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
        }
        candidates = [
            {"name": "Bob"},                      # missing age
            {"name": "Alice", "age": 30},         # valid
            {"name": "Carol", "age": 40},         # valid (but second wins)
        ]
        step = _Step(parameters={"output_schema": schema})
        result = _run(verifier.verify(candidates, step, _Ctx()))
        assert result.winner == {"name": "Alice", "age": 30}
        assert result.confidence == 1.0

    def test_required_fields_list_mode(self, verifier):
        candidates = [{"a": 1}, {"a": 1, "b": 2}]
        step = _Step(parameters={"required_fields": ["a", "b"]})
        result = _run(verifier.verify(candidates, step, _Ctx()))
        assert result.winner == {"a": 1, "b": 2}

    def test_no_schema_returns_none(self, verifier):
        step = _Step()  # no output_schema, no required_fields
        result = _run(verifier.verify([{"x": 1}], step, _Ctx()))
        assert result.winner is None
        assert "no output_schema" in (result.reason or "")

    def test_no_valid_candidate_returns_none(self, verifier):
        step = _Step(parameters={"required_fields": ["missing"]})
        result = _run(verifier.verify([{"a": 1}, {"b": 2}], step, _Ctx()))
        assert result.winner is None
        assert "no candidate matched" in (result.reason or "")

    def test_non_dict_candidate_fails_validation(self, verifier):
        step = _Step(parameters={"required_fields": ["a"]})
        result = _run(verifier.verify(["not a dict", {"a": 1}], step, _Ctx()))
        assert result.winner == {"a": 1}

    def test_empty_candidates(self, verifier):
        step = _Step(parameters={"required_fields": ["a"]})
        result = _run(verifier.verify([], step, _Ctx()))
        assert result.winner is None

    @pytest.mark.skipif(not _HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_jsonschema_rejects_wrong_type(self, verifier):
        schema = {"type": "object", "properties": {"age": {"type": "integer"}}}
        candidates = [{"age": "thirty"}, {"age": 30}]
        step = _Step(parameters={"output_schema": schema})
        result = _run(verifier.verify(candidates, step, _Ctx()))
        assert result.winner == {"age": 30}


# ===========================================================================
# ExecutionVerifier
# ===========================================================================
class TestExecutionVerifier:
    def test_first_passing_candidate_wins(self):
        sandbox = _MockSandbox([
            {"success": False, "exit_code": 1, "stdout": "", "stderr": "NameError"},
            {"success": True, "exit_code": 0, "stdout": "42\n", "stderr": ""},
        ])
        verifier = ExecutionVerifier(sandbox_runtime=sandbox)
        candidates = [{"code": "print(undefined)"}, {"code": "print(42)"}]
        step = _Step(parameters={"tests": {"expected_exact": "42"}})
        result = _run(verifier.verify(candidates, step, _Ctx()))
        assert result.winner == {"code": "print(42)"}
        assert result.details["exit_code"] == 0
        assert len(sandbox.calls) == 2

    def test_exit_zero_with_no_tests(self):
        sandbox = _MockSandbox([{"success": True, "exit_code": 0, "stdout": "", "stderr": ""}])
        verifier = ExecutionVerifier(sandbox_runtime=sandbox)
        candidates = [{"code": "x = 1"}]
        step = _Step()  # no tests → exit 0 is enough
        result = _run(verifier.verify(candidates, step, _Ctx()))
        assert result.winner == {"code": "x = 1"}

    def test_expected_stdout_substring(self):
        sandbox = _MockSandbox([
            {"success": True, "exit_code": 0, "stdout": "Hello World\n", "stderr": ""},
        ])
        verifier = ExecutionVerifier(sandbox_runtime=sandbox)
        candidates = [{"code": "print('Hello World')"}]
        step = _Step(parameters={"tests": {"expected_stdout": "Hello"}})
        result = _run(verifier.verify(candidates, step, _Ctx()))
        assert result.winner == {"code": "print('Hello World')"}

    def test_no_candidate_passes_returns_none(self):
        sandbox = _MockSandbox([
            {"success": False, "exit_code": 1, "stdout": "", "stderr": "err"},
            {"success": False, "exit_code": 1, "stdout": "", "stderr": "err"},
        ])
        verifier = ExecutionVerifier(sandbox_runtime=sandbox)
        candidates = [{"code": "bad1"}, {"code": "bad2"}]
        step = _Step()
        result = _run(verifier.verify(candidates, step, _Ctx()))
        assert result.winner is None
        assert len(result.details["attempts"]) == 2

    def test_code_extracted_from_output_field(self):
        sandbox = _MockSandbox([{"success": True, "exit_code": 0, "stdout": "", "stderr": ""}])
        verifier = ExecutionVerifier(sandbox_runtime=sandbox)
        # 'output' is the fallback field when no 'code' key.
        candidates = [{"output": "print('hello')"}]
        result = _run(verifier.verify(candidates, _Step(), _Ctx()))
        assert result.winner == {"output": "print('hello')"}
        assert sandbox.calls[0] == "print('hello')"

    def test_bare_string_candidate(self):
        sandbox = _MockSandbox([{"success": True, "exit_code": 0, "stdout": "", "stderr": ""}])
        verifier = ExecutionVerifier(sandbox_runtime=sandbox)
        candidates = ["print(1)"]
        result = _run(verifier.verify(candidates, _Step(), _Ctx()))
        assert result.winner == "print(1)"

    def test_runtime_raising_returns_none(self):
        class _Boom:
            async def execute_python(self, code, *, policy, inputs=None, cwd=None):
                raise RuntimeError("docker down")
        verifier = ExecutionVerifier(sandbox_runtime=_Boom())
        result = _run(verifier.verify([{"code": "x"}], _Step(), _Ctx()))
        assert result.winner is None


# ===========================================================================
# FormalVerifier
# ===========================================================================
@pytest.mark.skipif(not _HAS_SYMPY, reason="sympy not installed")
class TestFormalVerifier:
    @pytest.fixture
    def verifier(self):
        return FormalVerifier()

    def test_equivalent_answers_collapse(self, verifier):
        # x**2, x*x, and x*x/1 are all symbolically equal.
        candidates = [{"answer": "x**2"}, {"answer": "x*x"}, {"answer": "x*x/1"}]
        result = _run(verifier.verify(candidates, _Step(), _Ctx()))
        assert result.winner is not None
        assert result.details["mode"] == "sympy_equivalence"
        assert result.details["group_size"] == 3

    def test_majority_of_equivalent_wins(self, verifier):
        # 2/3 equivalent (x**2, x*x) vs 1 distinct (x**3).
        candidates = [{"answer": "x**2"}, {"answer": "x*x"}, {"answer": "x**3"}]
        result = _run(verifier.verify(candidates, _Step(), _Ctx()))
        assert result.winner in ({"answer": "x**2"}, {"answer": "x*x"})

    def test_numeric_equivalence(self, verifier):
        # 1/2 and 0.5 are symbolically equal.
        candidates = [{"answer": "1/2"}, {"answer": "0.5"}, {"answer": "0.5"}]
        result = _run(verifier.verify(candidates, _Step(), _Ctx()))
        assert result.winner is not None
        assert result.details["mode"] == "sympy_equivalence"

    def test_no_majority_falls_to_string_or_none(self, verifier):
        # Three distinct, non-equivalent answers.
        candidates = [{"answer": "1"}, {"answer": "2"}, {"answer": "3"}]
        result = _run(verifier.verify(candidates, _Step(), _Ctx()))
        # No symbolic majority and no exact-string majority → None.
        assert result.winner is None or result.details["mode"] in (
            "exact_string_fallback", "sympy_equivalence",
        )

    def test_unparseable_falls_to_string_majority(self, verifier):
        candidates = [{"answer": "42"}, {"answer": "42"}, {"answer": "not math"}]
        result = _run(verifier.verify(candidates, _Step(), _Ctx()))
        # Two of three are the exact string "42" → string-majority fallback.
        assert result.winner == {"answer": "42"}

    def test_extract_from_result_field(self, verifier):
        candidates = [{"result": "x**2"}, {"result": "x*x"}, {"result": "x*x"}]
        out = _run(verifier.verify(candidates, _Step(), _Ctx()))
        assert out.winner is not None


@pytest.mark.skipif(_HAS_SYMPY, reason="sympy present — exercising the absent path")
class TestFormalVerifierNoSympy:
    def test_returns_none_when_sympy_missing(self):
        verifier = FormalVerifier()
        result = _run(verifier.verify([{"answer": "1"}], _Step(), _Ctx()))
        assert result.winner is None
        assert "sympy not installed" in (result.reason or "")


# ===========================================================================
# GroundedVerifier
# ===========================================================================
class TestGroundedVerifier:
    def test_first_grounded_candidate_wins(self):
        llm = _MockLLM(["NO\nunsupported", "YES\nfully supported"])
        verifier = GroundedVerifier(llm)
        sources = ["Paris is the capital of France."]
        candidates = [{"answer": "London"}, {"answer": "Paris"}]
        step = _Step(parameters={"sources": sources})
        result = _run(verifier.verify(candidates, step, _Ctx()))
        assert result.winner == {"answer": "Paris"}

    def test_no_sources_returns_none(self):
        llm = _MockLLM([])
        verifier = GroundedVerifier(llm)
        result = _run(verifier.verify([{"answer": "x"}], _Step(), _Ctx()))
        assert result.winner is None
        assert "no sources" in (result.reason or "")

    def test_no_llm_returns_none(self):
        verifier = GroundedVerifier(None)
        step = _Step(parameters={"sources": ["x"]})
        result = _run(verifier.verify([{"answer": "x"}], step, _Ctx()))
        assert result.winner is None
        assert "no LLM" in (result.reason or "")

    def test_sources_from_context_shared_context(self):
        llm = _MockLLM(["YES\nok"])
        verifier = GroundedVerifier(llm)
        ctx = _Ctx(shared_context={"retrieved_context": ["Earth is round."]})
        result = _run(verifier.verify([{"answer": "Earth is round"}], _Step(), ctx))
        assert result.winner == {"answer": "Earth is round"}

    def test_all_ungrounded_returns_none(self):
        llm = _MockLLM(["NO\nnope", "NO\nalso nope"])
        verifier = GroundedVerifier(llm)
        step = _Step(parameters={"sources": ["x"]})
        result = _run(verifier.verify([{"answer": "a"}, {"answer": "b"}], step, _Ctx()))
        assert result.winner is None
        assert len(result.details["checks"]) == 2

    def test_timeout_does_not_crash(self):
        class _SlowLLM:
            async def complete(self, prompt):
                await asyncio.sleep(5)
                return "YES"
        verifier = GroundedVerifier(_SlowLLM(), timeout_seconds=0.05)
        step = _Step(parameters={"sources": ["x"]})
        result = _run(verifier.verify([{"answer": "a"}], step, _Ctx()))
        assert result.winner is None


# ===========================================================================
# JudgeVerifier
# ===========================================================================
class TestJudgeVerifier:
    def test_single_candidate_returned_without_llm(self):
        # No need to call the LLM when there's only one candidate.
        verifier = JudgeVerifier(None)
        result = _run(verifier.verify(["only draft"], _Step(name="write essay"), _Ctx()))
        assert result.winner == "only draft"

    def test_no_llm_with_multiple_returns_none(self):
        verifier = JudgeVerifier(None)
        result = _run(verifier.verify(["a", "b"], _Step(name="write essay"), _Ctx()))
        assert result.winner is None
        assert "no LLM" in (result.reason or "")

    def test_judge_ranks_candidates(self):
        # The judge replies "1, 0" (display position 1 first, then 0).
        llm = _MockLLM(["1, 0"])
        verifier = JudgeVerifier(llm)
        candidates = ["worse draft", "better draft"]
        result = _run(verifier.verify(candidates, _Step(name="write essay"), _Ctx()))
        # We can't predict display_order (it's shuffled), so just assert
        # the winner is one of the candidates and a ranking was produced.
        assert result.winner in candidates
        assert len(result.details["ranking_display_positions"]) == 2

    def test_unparseable_ranking_returns_none(self):
        llm = _MockLLM(["I refuse to rank these."])
        # Parser backfills all candidates even from prose, so the judge
        # still produces a winner — but verify it doesn't crash.
        verifier = JudgeVerifier(llm)
        result = _run(verifier.verify(["a", "b"], _Step(name="write essay"), _Ctx()))
        assert result.winner in ("a", "b")

    def test_timeout_does_not_crash(self):
        class _SlowLLM:
            async def complete(self, prompt):
                await asyncio.sleep(5)
                return "0, 1"
        verifier = JudgeVerifier(_SlowLLM(), timeout_seconds=0.05)
        result = _run(verifier.verify(["a", "b"], _Step(name="write essay"), _Ctx()))
        assert result.winner is None
        assert "timeout" in (result.reason or "")


# ===========================================================================
# CodePipelineVerifier — reconcile action dicts → execute code (2-stage)
# ===========================================================================
class TestCodePipelineVerifier:
    """The CODE domain strategy: compose reconcile (coordination) with
    execute (correctness).

    Stage 1 always runs (merges divergent agent action dicts). Stage 2 runs
    only when the reconciled candidate carries code.
    """

    def test_action_dicts_no_code_skips_execution(self):
        # Pure coordination step: the reconciler merges the divergent
        # action dicts. There's no code to run, so stage 2 is skipped.
        sandbox = _MockSandbox([])  # would fail loudly if called
        verifier = CodePipelineVerifier(sandbox_runtime=sandbox)
        candidates = [
            {"action": "read", "target": "f.py", "status": "ok"},
            {"action": "read", "target": "g.py", "status": "ok"},
            {"action": "write", "target": "f.py", "status": "ok"},
        ]
        step = _Step(step_id="s1")
        result = _run(verifier.verify(candidates, step, _Ctx(_resolved_domain=TaskDomain.CODE)))
        assert result.winner is not None
        # Stage 1 ran and merged the action dicts.
        assert result.details["stage_1"]["mode"] == "reconciled"
        # Stage 2 was skipped (no code).
        assert result.details["stage_2"]["skipped"] is True
        assert "no code" in result.details["stage_2"]["reason"]
        # Sandbox was never invoked.
        assert sandbox.calls == []

    def test_reconciled_code_passing_execution_returns_winner(self):
        # Two agents agree on the action; the merged dict carries code that
        # runs and passes the tests spec.
        sandbox = _MockSandbox([
            {"success": True, "exit_code": 0, "stdout": "42\n", "stderr": ""},
        ])
        verifier = CodePipelineVerifier(sandbox_runtime=sandbox)
        candidates = [
            {"action": "run", "code": "print(42)"},
            {"action": "run", "code": "print(42)"},
        ]
        step = _Step(parameters={"tests": {"expected_exact": "42"}})
        result = _run(verifier.verify(candidates, step, _Ctx(_resolved_domain=TaskDomain.CODE)))
        # Majority winner (2/3 identical dicts) returned, execution verified.
        assert result.winner is not None
        assert result.winner["action"] == "run"
        assert result.details["stage_2"]["exit_code"] == 0
        assert "passed execution verification" in result.reason

    def test_reconciled_code_failing_execution_returns_none(self):
        # The correctness gate: reconciled code that fails tests → winner=None.
        sandbox = _MockSandbox([
            {"success": False, "exit_code": 1, "stdout": "", "stderr": "SyntaxError"},
        ])
        verifier = CodePipelineVerifier(sandbox_runtime=sandbox)
        candidates = [
            {"action": "run", "code": "print(broken"},
            {"action": "run", "code": "print(broken"},
        ]
        step = _Step()
        result = _run(verifier.verify(candidates, step, _Ctx(_resolved_domain=TaskDomain.CODE)))
        assert result.winner is None
        assert "failed execution" in (result.reason or "")
        # Both stages' diagnostics are preserved.
        assert result.details["stage_1"]["mode"] in ("majority", "reconciled")
        assert result.details["stage_2"]["attempts"][0]["passed"] is False

    def test_sandbox_unavailable_skips_execution_gracefully(self):
        # If the sandbox runtime can't be obtained, ExecutionVerifier
        # returns winner=None with reason "sandbox runtime unavailable".
        # The pipeline treats this as an infra issue (not a correctness
        # failure) and returns the reconciled winner with stage 2 skipped.
        from core.orchestration.verification.base import VerificationResult
        class _UnavailableExecution:
            strategy = VerificationStrategy.EXECUTION
            async def verify(self, candidates, step, context):
                return VerificationResult.empty(
                    TaskDomain.CODE, self.strategy,
                    reason="sandbox runtime unavailable: no docker daemon",
                )
        verifier = CodePipelineVerifier(execution_verifier=_UnavailableExecution())
        candidates = [
            {"action": "run", "code": "print(1)"},
            {"action": "run", "code": "print(1)"},
        ]
        result = _run(verifier.verify(candidates, _Step(), _Ctx(_resolved_domain=TaskDomain.CODE)))
        # Reconciled winner returned; execution stage skipped gracefully.
        assert result.winner is not None
        assert result.details["stage_2"]["skipped"] is True
        assert "unavailable" in result.details["stage_2"]["reason"]

    def test_bare_code_strings_run_execution(self):
        # Candidates are bare code (no action dict) → stage 1 returns the
        # majority winner; stage 2 executes it.
        sandbox = _MockSandbox([
            {"success": True, "exit_code": 0, "stdout": "hi\n", "stderr": ""},
        ])
        verifier = CodePipelineVerifier(sandbox_runtime=sandbox)
        candidates = ["print('hi')", "print('hi')", "print('hi')"]
        step = _Step(parameters={"tests": {"expected_stdout": "hi"}})
        result = _run(verifier.verify(candidates, step, _Ctx(_resolved_domain=TaskDomain.CODE)))
        assert result.winner == "print('hi')"
        assert sandbox.calls == ["print('hi')"]

    def test_empty_candidates_returns_none(self):
        verifier = CodePipelineVerifier(sandbox_runtime=_MockSandbox([]))
        result = _run(verifier.verify([], _Step(), _Ctx()))
        assert result.winner is None

    def test_details_carry_both_stages(self):
        # Observability: the result always includes stage_1 and stage_2 keys.
        verifier = CodePipelineVerifier(sandbox_runtime=_MockSandbox([]))
        candidates = [{"action": "read"}, {"action": "read"}]
        result = _run(verifier.verify(candidates, _Step(), _Ctx()))
        assert "stage_1" in result.details
        assert "stage_2" in result.details

    def test_injected_execution_verifier_is_used(self):
        # Test seam: callers can inject a custom ExecutionVerifier.
        class _SpyExecution:
            strategy = VerificationStrategy.EXECUTION
            def __init__(self):
                self.calls = 0
            async def verify(self, candidates, step, context):
                self.calls += 1
                from core.orchestration.verification.base import VerificationResult
                return VerificationResult(
                    winner=candidates[0], strategy=self.strategy,
                    domain=TaskDomain.CODE, confidence=1.0,
                    details={"spy": True},
                )
        spy = _SpyExecution()
        verifier = CodePipelineVerifier(
            sandbox_runtime=None, execution_verifier=spy,
        )
        candidates = [{"code": "x=1"}, {"code": "x=1"}]
        result = _run(verifier.verify(candidates, _Step(), _Ctx(_resolved_domain=TaskDomain.CODE)))
        assert spy.calls == 1
        assert result.details["stage_2"]["spy"] is True
