"""Reasoning-mandatory endpoints: retry without the disable switch, and learn.

OpenRouter (and some self-hosted gateways) serve models that REQUIRE reasoning
and reject the disable switch with::

    400 - {'error': {'message': 'Reasoning is mandatory for this endpoint and
                      cannot be disabled.'}}

``BYOKHandler.generate_structured_response`` has an except block meant to catch
exactly this and retry once WITHOUT ``extra_body`` (byok_handler.py:4319). In
the live 2026-09-10 log that retry NEVER fired: its log line appears 0 times,
every structured attempt fails with the 400, and the stage silently burns the
attempt before moving to the next provider. Observed on
``openrouter/z-ai/glm-5.3-flash`` (13x) and, after the canvas-editor pin was
removed, on ``openrouter/openai/gpt-5-mini`` too -- i.e. the bug is
model-agnostic and gets MORE reachable as routing becomes dynamic.

Two contracts are pinned here:
1. The retry actually happens (the request is re-issued without the disable
   switch) so the attempt is not wasted.
2. The pair is MEMOIZED, so later calls skip sending the switch to a model
   already known to reject it — mirroring ``_TOOLCHOICE_UNSUPPORTED``.
"""
from __future__ import annotations

import itertools
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("TESTING", "1")

_MANDATORY_MSG = (
    "Error code: 400 - {'error': {'message': 'Reasoning is mandatory for this "
    "endpoint and cannot be disabled.', 'code': 400}}"
)


class _Http400(Exception):
    pass


@pytest.fixture(autouse=True)
def _fake_instructor(monkeypatch):
    """Fake instructor whose create() records every ``extra_body`` it is given.

    Raises the mandatory-reasoning 400 whenever ``extra_body`` carries the
    disable switch; succeeds (with a stand-in parsed object) otherwise.
    """
    from core.llm import byok_handler

    calls: list = []

    def _from_openai(client):
        def _create(**kwargs):
            calls.append(kwargs)
            eb = kwargs.get("extra_body")
            if eb and "reasoning" in eb:
                raise _Http400(_MANDATORY_MSG)
            return SimpleNamespace(ok=True)
        return SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
        )

    fake_module = MagicMock()
    fake_module.from_openai.side_effect = _from_openai
    fake_module.Mode = SimpleNamespace(JSON="json")
    monkeypatch.setitem(sys.modules, "instructor", fake_module)
    monkeypatch.setattr(byok_handler, "instructor", fake_module, raising=False)
    monkeypatch.setattr(byok_handler, "INSTRUCTOR_AVAILABLE", True)

    fake_db = MagicMock()
    paid_workspace = SimpleNamespace(tenant_id="t-1")
    paid_tenant = SimpleNamespace(id="t-1", plan_type=SimpleNamespace(value="pro"))
    fake_db.query.return_value.filter.return_value.first.side_effect = itertools.cycle(
        [paid_workspace, paid_tenant]
    )

    class _Ctx:
        def __enter__(self):
            return fake_db

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(byok_handler, "get_db_session", lambda: _Ctx())

    # The parsed result after a successful create: the handler validates the
    # response against response_model, so give it a permissive stub.
    monkeypatch.setattr(
        byok_handler, "_parse_structured_result",
        lambda *a, **k: "PARSED", raising=False,
    )
    return calls


def _handler():
    from core.llm.byok_handler import AwaitableResult, BYOKHandler

    handler = BYOKHandler.__new__(BYOKHandler)
    handler.workspace_id = "ws-1"
    handler.tenant_id = "t-1"
    handler.db_session = MagicMock()
    handler.clients = {"openrouter": MagicMock()}
    handler.async_clients = {}
    handler.governance = None
    handler._is_trial_restricted = lambda: False
    handler.byok_manager = MagicMock()
    handler.byok_manager.get_tenant_api_key = MagicMock(return_value=None)
    handler.analyze_query_complexity = MagicMock(return_value=MagicMock(value="standard"))
    handler.get_ranked_providers = MagicMock(
        return_value=AwaitableResult([("openrouter", "reasoning-only-model")])
    )
    handler.get_context_window = MagicMock(return_value=8000)
    handler.truncate_to_context = MagicMock(side_effect=lambda p, *a, **k: p)
    # Reset the memo between tests (module-level, like _TOOLCHOICE_UNSUPPORTED).
    from core.llm import byok_handler as bh
    bh._REASONING_MANDATORY.clear()
    return handler


def _call(handler):
    return handler.generate_structured_response(
        prompt="plan",
        system_instruction="json",
        response_model=object,
        disable_reasoning=True,
    )


@pytest.mark.asyncio
async def test_retry_drops_the_disable_switch(_fake_instructor):
    handler = _handler()
    await _call(handler)

    assert len(_fake_instructor) == 2, (
        "expected the mandatory-reasoning 400 to be retried once without "
        f"extra_body; got {len(_fake_instructor)} attempt(s)"
    )
    assert "extra_body" in _fake_instructor[0], "first attempt must send the switch"
    assert "extra_body" not in _fake_instructor[1], (
        "the retry must drop the disable switch or it will 400 again"
    )


@pytest.mark.asyncio
async def test_memoized_so_later_calls_skip_the_switch(_fake_instructor):
    handler = _handler()
    await _call(handler)
    first_round = len(_fake_instructor)

    # A SECOND call to the same model must not re-send the doomed switch.
    await _call(handler)

    later = _fake_instructor[first_round:]
    assert len(later) == 1, (
        "memoized model should need exactly one attempt on later calls; "
        f"got {len(later)}"
    )
    assert "extra_body" not in later[0]
