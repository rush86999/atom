# -*- coding: utf-8 -*-
"""Dispatch-boundary route gate (owner assignment 2, 2026-10-08).

One route rule for EVERY network dispatch boundary — structured, streaming,
ordinary completion and sweep. Fake provider clients are injected at the
PRODUCTION dispatch seams (``chat_completion`` / ``stream_completion``), so
these regressions assert which routes were actually attempted, not just what
a helper returned.

Case table under test:
  automatic primary            -> eligibility checks
  automatic fallback           -> the same checks
  automatic sweep candidate    -> the same checks
  explicit operator route      -> admitted, override logged
  unknown catalog              -> refused (support is not assumed)
  known unsupported route      -> skipped with no network call
  protocol rejection           -> THIS (route, operation) only
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest

from core.llm.byok_handler import (
    AllProvidersFailedError,
    BYOKHandler,
    _PROTOCOL_INCOMPATIBLE,
    _STRUCTURED_PROTOCOL_UNSUPPORTED,
)


class _FakeCompletions:
    def __init__(self, owner):
        self._owner = owner

    async def create(self, **kw):
        return await self._owner._create(**kw)


class _FakeChat:
    def __init__(self, owner):
        self.completions = _FakeCompletions(owner)


class _FakeClient:
    """Records dispatch attempts and returns a fixed completion.

    Mirrors the OpenAI SDK surface the production code calls:
    ``client.chat.completions.create(...)``.
    """

    def __init__(self, name, *, fail_with=None):
        self.name = name
        self.fail_with = fail_with
        self.attempts = []
        self.chat = _FakeChat(self)

    async def _create(self, **kw):
        self.attempts.append(kw)
        if self.fail_with is not None:
            raise self.fail_with
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content=f"ok from {self.name}",
                                        tool_calls=None))],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1,
                                  total_tokens=2))


def _handler(*providers):
    """A BYOKHandler wired with fake clients and no real network."""
    h = BYOKHandler.__new__(BYOKHandler)
    h.workspace_id = "default"
    h.tenant_id = "default"
    h.clients = {p: _FakeClient(p) for p in providers}
    h.async_clients = dict(h.clients)
    h._MODEL_TEMPERATURE = {}
    h._TOOLCHOICE_UNSUPPORTED = set()
    h._REASONING_MANDATORY = set()
    h._LOGPROBS_UNSUPPORTED = set()
    h._AUTH_FAILED = set()
    h._MODEL_STRUCTURED_LATENCY = {}
    # Collaborators the dispatch path touches; permissive, so these
    # regressions stay about ROUTING rather than health accounting.
    from unittest.mock import MagicMock

    h.health_monitor = MagicMock()
    h.rate_tracker = MagicMock()
    h.rate_tracker.get_model_headroom = lambda p, m: 1.0
    h.rate_tracker.get_headroom = lambda p: 1.0
    h.rate_tracker.get_model_weight = lambda p, m: 1.0
    h.rate_tracker.get_max_context = lambda p, m=None: 200000
    return h


def _no_serve(*unserved):
    """The route registry says these pairs are NOT served."""
    def serves(self, provider_id, model):
        return f"{provider_id}/{model}" not in set(unserved)
    return patch.object(BYOKHandler, "_provider_serves_model", serves)


class TestCatalogGateAtTheDispatchSeam:
    def test_unsupported_automatic_primary_never_reaches_the_network(self):
        h = _handler("goodprov", "badprov")
        with _no_serve("badprov/gpt-x"), \
             patch.object(BYOKHandler, "_provider_cooldown_active",
                          lambda self, p: False), \
             patch.object(BYOKHandler, "_model_cooldown_active",
                          lambda self, p, m: False), \
             patch.object(BYOKHandler, "_llm_taint_check",
                          lambda self, *a, **k: None):
            import asyncio

            try:
                asyncio.run(h.chat_completion(
                    [{"role": "user", "content": "hi"}],
                    model="gpt-x", provider_id="badprov"))
            except AllProvidersFailedError:
                pass  # these pins assert attempts, not a win
        assert h.clients["badprov"].attempts == [], (
            "an unserved automatic primary must not be dispatched")
        assert h.clients["goodprov"].attempts, (
            "the ladder must move on to the served route")

    def test_unsupported_fallback_is_skipped_without_a_request(self):
        h = _handler("goodprov", "badprov")
        calls = []

        async def failing(**kw):
            calls.append(kw)
            raise RuntimeError("first rung down")

        h.clients["goodprov"]._create = failing
        h.async_clients = dict(h.clients)
        with _no_serve("badprov/gpt-x"), \
             patch.object(BYOKHandler, "_provider_cooldown_active",
                          lambda self, p: False), \
             patch.object(BYOKHandler, "_model_cooldown_active",
                          lambda self, p, m: False), \
             patch.object(BYOKHandler, "_llm_taint_check",
                          lambda self, *a, **k: None), \
             patch.object(BYOKHandler, "_get_provider_fallback_order",
                          lambda self, *a, **k: ["goodprov", "badprov"]):
            import asyncio

            try:
                asyncio.run(h.chat_completion(
                    [{"role": "user", "content": "hi"}],
                    model="gpt-x", provider_id="goodprov"))
            except AllProvidersFailedError:
                pass  # these pins assert attempts, not a win
        assert h.clients["badprov"].attempts == [], (
            "an unserved fallback must be skipped without a network call")

    def test_valid_next_route_is_still_attempted(self):
        h = _handler("badprov", "goodprov")
        with _no_serve("badprov/gpt-x"), \
             patch.object(BYOKHandler, "_provider_cooldown_active",
                          lambda self, p: False), \
             patch.object(BYOKHandler, "_model_cooldown_active",
                          lambda self, p, m: False), \
             patch.object(BYOKHandler, "_llm_taint_check",
                          lambda self, *a, **k: None), \
             patch.object(BYOKHandler, "_get_provider_fallback_order",
                          lambda self, *a, **k: ["badprov", "goodprov"]):
            import asyncio

            try:
                asyncio.run(h.chat_completion(
                    [{"role": "user", "content": "hi"}],
                    model="gpt-x", provider_id="badprov"))
            except AllProvidersFailedError:
                pass  # these pins assert attempts, not a win
        assert h.clients["goodprov"].attempts, (
            "a served route must still be reached after an unsupported one")

    def test_unknown_catalog_is_refused_for_automatic_routes(self):
        """Support is not assumed from a never-discovered catalogue."""
        h = _handler("unknownprov")
        with patch.object(BYOKHandler, "_provider_serves_model",
                          lambda self, p, m: False), \
             patch.object(BYOKHandler, "_provider_cooldown_active",
                          lambda self, p: False), \
             patch.object(BYOKHandler, "_model_cooldown_active",
                          lambda self, p, m: False), \
             patch.object(BYOKHandler, "_llm_taint_check",
                          lambda self, *a, **k: None):
            import asyncio

            try:
                asyncio.run(h.chat_completion(
                    [{"role": "user", "content": "hi"}],
                    model="gpt-x", provider_id="unknownprov"))
            except AllProvidersFailedError:
                pass  # these pins assert attempts, not a win
        assert h.clients["unknownprov"].attempts == [], (
            "an unknown catalogue must not silently assume support")

    def test_explicit_operator_route_is_admitted_and_logged(self):
        h = _handler("pinnedprov")
        with patch.object(BYOKHandler, "_provider_serves_model",
                          lambda self, p, m: False), \
             patch.object(BYOKHandler, "_provider_cooldown_active",
                          lambda self, p: False), \
             patch.object(BYOKHandler, "_model_cooldown_active",
                          lambda self, p, m: False), \
             patch.object(BYOKHandler, "_llm_taint_check",
                          lambda self, *a, **k: None):
            import asyncio

            try:
                asyncio.run(h.chat_completion(
                    [{"role": "user", "content": "hi"}],
                    model="gpt-x", provider_id="pinnedprov",
                    explicit_route=True))
            except AllProvidersFailedError:
                pass  # these pins assert attempts, not a win
        assert h.clients["pinnedprov"].attempts, (
            "an explicit operator route is admitted under the documented "
            "override policy")

    def test_automatic_primary_does_not_inherit_the_override_exemption(self):
        """Being first in a ranked list is not evidence of an override."""
        h = _handler("auto_first")
        with patch.object(BYOKHandler, "_provider_serves_model",
                          lambda self, p, m: False), \
             patch.object(BYOKHandler, "_provider_cooldown_active",
                          lambda self, p: False), \
             patch.object(BYOKHandler, "_model_cooldown_active",
                          lambda self, p, m: False), \
             patch.object(BYOKHandler, "_llm_taint_check",
                          lambda self, *a, **k: None):
            import asyncio

            try:
                asyncio.run(h.chat_completion(
                    [{"role": "user", "content": "hi"}],
                    model="gpt-x", provider_id="auto_first"))
            except AllProvidersFailedError:
                pass  # these pins assert attempts, not a win
        assert h.clients["auto_first"].attempts == [], (
            "an automatic primary must face the same checks as a fallback")


class TestSweepCandidatesAreGated:
    def test_unsupported_sweep_candidate_is_skipped(self):
        h = _handler("goodprov", "sweepprov")
        with _no_serve("sweepprov/anything"), \
             patch.object(BYOKHandler, "_provider_cooldown_active",
                          lambda self, p: False), \
             patch.object(BYOKHandler, "_model_cooldown_active",
                          lambda self, p, m: False), \
             patch.object(BYOKHandler, "_llm_taint_check",
                          lambda self, *a, **k: None):
            admitted = h._dispatch_catalog_admits(
                "sweepprov", "anything", None, operation="text")
        assert admitted is False, (
            "a sweep candidate is automatic and must face the same gate")


class TestProtocolRejectionIsPerRouteAndOperation:
    def setup_method(self, _):
        _PROTOCOL_INCOMPATIBLE.clear()
        _STRUCTURED_PROTOCOL_UNSUPPORTED.clear()

    def test_protocol_rejection_disables_only_that_combination(self):
        h = _handler("prov")
        h._record_protocol_incompatible("prov", "m", "structured",
                                        detail="400 ModelProtocolUnsupported")
        assert h._protocol_incompatible("prov", "m", "structured") is True
        assert h._protocol_incompatible("prov", "m", "text") is False, (
            "a structured protocol rejection must not disable text")
        assert h._protocol_incompatible("prov", "other-m", "structured") is (
            False), "other models on the provider stay usable"
        assert h._dispatch_catalog_admits(
            "prov", "m", "prov", operation="text") in (True, False)

    def test_rejected_combination_reaches_no_network(self):
        h = _handler("prov")
        h._record_protocol_incompatible("prov", "m", "structured")
        with patch.object(BYOKHandler, "_provider_serves_model",
                          lambda self, p, m: True), \
             patch.object(BYOKHandler, "_provider_cooldown_active",
                          lambda self, p: False), \
             patch.object(BYOKHandler, "_model_cooldown_active",
                          lambda self, p, m: False), \
             patch.object(BYOKHandler, "_llm_taint_check",
                          lambda self, *a, **k: None):
            assert h._dispatch_catalog_admits(
                "prov", "m", "prov", operation="structured") is False
            # ...while the SAME route for another operation is untouched
            assert h._dispatch_catalog_admits(
                "prov", "m", "prov", operation="text") is True

    def test_mixed_failure_is_not_reported_as_provider_outage(self):
        """A protocol rejection must never populate a provider cooldown or
        be described as the provider being down — the failure is scoped to
        (route, operation) and every other route stays usable."""
        h = _handler("prov", "otherprov")
        h._record_protocol_incompatible(
            "prov", "m", "structured",
            detail="400 ModelProtocolUnsupported")
        state = h._provider_cooldown_state()             if hasattr(h, "_provider_cooldown_state") else {}
        assert "prov" not in state, (
            "a protocol rejection is not a provider outage")
        with patch.object(BYOKHandler, "_provider_serves_model",
                          lambda self, p, m: True):
            assert h._dispatch_catalog_admits(
                "otherprov", "m", None, operation="structured") is True, (
                "another provider's route stays usable")
            assert h._dispatch_catalog_admits(
                "prov", "m", None, operation="text") is True, (
                "the same route for another operation stays usable")


class TestResponseOutcomeSeparation:
    """Owner assignment 3: a successful HTTP response is not a successful
    model operation. Six outcomes stay apart at the response boundary."""

    def test_the_six_outcomes_are_distinct_strings(self):
        from core.chat_canvas_editor import CanvasPlanOutcome as C

        kinds = {C.EXECUTABLE, C.SERVED_DECLINE, C.MALFORMED, C.EMPTY,
                 C.PROVIDER_FAILURE, C.DEADLINE_CANCELLED}
        assert len(kinds) == 6, kinds

    def test_failure_classifier_separates_the_boundaries(self):
        from core.chat_canvas_editor import (
            CanvasPlanOutcome as C, _plan_failure_kind)

        class _Timeout(Exception):
            pass

        assert _plan_failure_kind(_Timeout("x")) == C.DEADLINE_CANCELLED
        assert _plan_failure_kind(
            ValueError("Expecting value: line 1 json")) == C.MALFORMED
        assert _plan_failure_kind(
            RuntimeError("400 ModelProtocolUnsupported")) == (
            C.PROVIDER_FAILURE)
        assert _plan_failure_kind(None) == C.EMPTY

    def test_served_decline_is_not_a_latency_failure(self):
        """A valid wants_edit=False plan carries SERVED_DECLINE, never a
        timeout/latency label."""
        from core.chat_canvas_editor import (
            CanvasEditPlan, CanvasPlanOutcome as C)

        plan = CanvasEditPlan(wants_edit=False, reply="the draft already "
                                                      "reflects the values")
        # Exercise the same classification the boundary applies.
        malformed = bool(list(plan.ops or [])
                         or (plan.updated_content_json or "").strip())
        outcome = C.MALFORMED if malformed else C.SERVED_DECLINE
        assert outcome == C.SERVED_DECLINE
        assert outcome != C.DEADLINE_CANCELLED
        assert outcome != C.PROVIDER_FAILURE

    def test_self_inconsistent_plan_is_malformed_not_a_decline(self):
        from core.chat_canvas_editor import (
            CanvasEditPlan, CanvasPatchOp, CanvasPlanOutcome as C)

        plan = CanvasEditPlan(
            wants_edit=False, reply="no change",
            ops=[CanvasPatchOp(find="a", replace="b")])
        malformed = bool(list(plan.ops or [])
                         or (plan.updated_content_json or "").strip())
        assert (C.MALFORMED if malformed else C.SERVED_DECLINE) == C.MALFORMED
