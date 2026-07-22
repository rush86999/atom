"""Tests for the domain classification + strategy resolution layer.

Covers:
  * infer_domain keyword matching (one test per domain + UNKNOWN default).
  * resolve_domain explicit-tag override (TaskDomain, value string, name).
  * resolve_strategy explicit override + domain-map fallback.
  * Unrecognised tags fall through to inference / map without crashing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Path bootstrapping — backend/ is the package root.
BACKEND_DIR = Path(__file__).parents[5]  # tests/unit/core/orchestration/verification/ → backend/
sys.path.insert(0, str(BACKEND_DIR))

from core.orchestration.verification.domain import (
    DOMAIN_STRATEGY_MAP,
    TaskDomain,
    infer_domain,
    resolve_domain,
    resolve_strategy,
)
from core.orchestration.verification.base import VerificationStrategy


# ---------------------------------------------------------------------------
# Test doubles — duck-typed steps. Avoids importing WorkflowStep (keeps
# these tests independent of the conductor module).
# ---------------------------------------------------------------------------
class _Step:
    def __init__(self, **kw):
        self.step_id = kw.pop("step_id", "s1")
        self.capability = kw.pop("capability", "")
        self.name = kw.pop("name", "")
        self.description = kw.pop("description", "")
        self.parameters = kw.pop("parameters", {})


# ===========================================================================
# infer_domain
# ===========================================================================
class TestInferDomain:
    @pytest.mark.parametrize(
        "field,text,expected",
        [
            ("capability", "python function implementation", TaskDomain.CODE),
            ("name", "implement the login endpoint", TaskDomain.CODE),
            ("description", "parse JSON and extract fields", TaskDomain.EXTRACTION),
            ("capability", "solve the calculus derivative", TaskDomain.MATH),
            ("description", "answer the user question using retrieved docs", TaskDomain.QA),
            ("name", "write a summary email", TaskDomain.PROSE),
            ("capability", "multi-step plan workflow", TaskDomain.PLANNING),
        ],
    )
    def test_keyword_match(self, field, text, expected):
        step = _Step(**{field: text})
        assert infer_domain(step) == expected

    def test_unknown_when_no_keywords(self):
        assert infer_domain(_Step(name="do the thing")) == TaskDomain.UNKNOWN

    def test_unknown_on_empty_step(self):
        assert infer_domain(_Step()) == TaskDomain.UNKNOWN

    def test_unknown_on_tie(self):
        # "code" and "write" hit CODE and PROSE equally → conservative UNKNOWN.
        step = _Step(description="write some code")
        assert infer_domain(step) == TaskDomain.UNKNOWN

    def test_parameters_are_included_in_haystack(self):
        # task_domain itself is visible in the JSON dump but resolve_domain
        # short-circuits before inference; here we just confirm params text
        # contributes to the score.
        step = _Step(parameters={"hint": "refactor the unittest module"})
        assert infer_domain(step) == TaskDomain.CODE

    def test_higher_score_wins_over_lower(self):
        # "test test test sql" → CODE (3 hits) beats any other domain.
        step = _Step(name="test test test sql endpoint")
        assert infer_domain(step) == TaskDomain.CODE


# ===========================================================================
# resolve_domain (explicit override)
# ===========================================================================
class TestResolveDomain:
    def test_explicit_enum_value(self):
        step = _Step(parameters={"task_domain": TaskDomain.MATH})
        assert resolve_domain(step) == TaskDomain.MATH

    def test_explicit_value_string(self):
        step = _Step(parameters={"task_domain": "code"})
        assert resolve_domain(step) == TaskDomain.CODE

    def test_explicit_name_string_case_insensitive(self):
        step = _Step(parameters={"task_domain": "MATH"})
        assert resolve_domain(step) == TaskDomain.MATH

    def test_unrecognised_tag_falls_through_to_inference(self):
        step = _Step(
            name="implement the python function",
            parameters={"task_domain": "bogus"},
        )
        # Inferred, not UNKNOWN — inference sees "python function implement".
        assert resolve_domain(step) == TaskDomain.CODE

    def test_no_tag_falls_through_to_inference(self):
        step = _Step(name="solve the algebra equation")
        assert resolve_domain(step) == TaskDomain.MATH

    def test_no_tag_no_keywords_returns_unknown(self):
        assert resolve_domain(_Step(name="do the thing")) == TaskDomain.UNKNOWN


# ===========================================================================
# resolve_strategy
# ===========================================================================
class TestResolveStrategy:
    def test_default_map_unknown_to_voting(self):
        step = _Step()
        assert resolve_strategy(step, TaskDomain.UNKNOWN) == VerificationStrategy.VOTING

    def test_default_map_code_to_code_pipeline(self):
        assert resolve_strategy(_Step(), TaskDomain.CODE) == VerificationStrategy.CODE_PIPELINE

    def test_default_map_math_to_formal(self):
        assert resolve_strategy(_Step(), TaskDomain.MATH) == VerificationStrategy.FORMAL

    def test_default_map_qa_to_grounded(self):
        assert resolve_strategy(_Step(), TaskDomain.QA) == VerificationStrategy.GROUNDED

    def test_default_map_extraction_to_schema(self):
        assert resolve_strategy(_Step(), TaskDomain.EXTRACTION) == VerificationStrategy.SCHEMA

    def test_default_map_planning_to_voting(self):
        assert resolve_strategy(_Step(), TaskDomain.PLANNING) == VerificationStrategy.VOTING

    def test_default_map_prose_to_judge(self):
        assert resolve_strategy(_Step(), TaskDomain.PROSE) == VerificationStrategy.JUDGE

    def test_explicit_strategy_override(self):
        step = _Step(parameters={"verification_strategy": "judge"})
        # Override applies regardless of domain.
        assert resolve_strategy(step, TaskDomain.CODE) == VerificationStrategy.JUDGE

    def test_explicit_strategy_override_by_name(self):
        step = _Step(parameters={"verification_strategy": "EXECUTION"})
        assert resolve_strategy(step, TaskDomain.PROSE) == VerificationStrategy.EXECUTION

    def test_unrecognised_strategy_falls_through_to_map(self):
        step = _Step(parameters={"verification_strategy": "bogus"})
        assert resolve_strategy(step, TaskDomain.CODE) == VerificationStrategy.CODE_PIPELINE

    def test_custom_domain_strategy_map(self):
        custom = dict(DOMAIN_STRATEGY_MAP)
        custom[TaskDomain.CODE] = VerificationStrategy.VOTING
        assert resolve_strategy(_Step(), TaskDomain.CODE, custom) == VerificationStrategy.VOTING
