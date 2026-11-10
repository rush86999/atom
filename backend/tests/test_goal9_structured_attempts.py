"""Per-physical-attempt admission for the structured (instructor) path.

The structured cascade already re-entered its recovery loop with a fresh
attempt counter, but its reservation bound used only message text and it had
no multimodal policy. These controls pin the shared contract:

- a recoverable re-issue is a NEW physical attempt (own attempt id, same
  request binding, own reservation/settlement);
- an authoritative numeric-zero price keeps an image request free;
- a priced/unknown image request still refuses before dispatch under hard_stop;
- the request-level accounting refusal stops the cascade (no silent
  re-dispatch without a durable bound).
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

import pytest

from tests.test_goal9_physical_attempts import (
    _IMAGE_MESSAGES,
    _attempt_rows,
    _make_handler,
    _pricing,
    _reservation_pricing,
    _seed,
    host,
)
from core.chat_canvas_editor import CanvasEditPlan

pytest_plugins = ("tests.test_goal9_physical_attempts",)


def _plan():
    return CanvasEditPlan(wants_edit=True, updated_content_json='"ok"')


def _structured(handler, create, **kwargs):
    import core.llm.byok_handler as bh

    def _fake_from_openai(client, **kw):
        return NS(chat=NS(completions=NS(create=create)))

    with patch.object(bh.instructor, "from_openai", _fake_from_openai):
        return asyncio.run(handler.generate_structured_response(
            prompt="update the valid-until date",
            system_instruction="You return only the requested JSON object.",
            response_model=CanvasEditPlan,
            task_type="planning",
            provider_model=("openai", "gpt-4o"),
            allow_moa=False,
            max_tokens=1000,
            **kwargs))


def _handler(monkeypatch, tmp_path):
    return _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        sync={"openai": MagicMock(name="structured-client")})


def test_structured_recovery_retry_gets_own_attempt_and_settlement(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    handler = _handler(monkeypatch, tmp_path)
    create = MagicMock(side_effect=[
        RuntimeError("reasoning is mandatory for this model"),
        _plan(),
    ])
    result = _structured(handler, create, disable_reasoning=True)
    assert isinstance(result, CanvasEditPlan)
    assert create.call_count == 2
    rows = _attempt_rows(host)
    assert len(rows) == 2, [r.attempt_id for r in rows]
    assert len({r.attempt_id for r in rows}) == 2
    assert len({r.request_id for r in rows}) == 1
    # The failed first attempt keeps its reservation; the successful second
    # attempt settles once (unknown usage -> explicit unknown liability).
    assert sum(1 for r in rows if r.billed is True) == 1


def test_structured_zero_price_image_stays_free(
        host, monkeypatch, tmp_path):
    _seed(host, spend=90.0)
    _pricing(monkeypatch, lambda *a, **k: 0.0)
    handler = _handler(monkeypatch, tmp_path)
    create = MagicMock(return_value=_plan())
    result = _structured(handler, create, messages=_IMAGE_MESSAGES)
    assert isinstance(result, CanvasEditPlan)
    assert create.call_count == 1
    rows = _attempt_rows(host)
    assert len(rows) == 1
    assert rows[0].pricing_status == "free"
    assert rows[0].reservation_status == "settled"
    assert float(rows[0].reserved_cost_usd or 0.0) == 0.0


def test_structured_paid_image_refuses_before_dispatch(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=7.0, actual=7.0)
    handler = _handler(monkeypatch, tmp_path)
    create = MagicMock(return_value=_plan())
    result = _structured(handler, create, messages=_IMAGE_MESSAGES)
    assert result is None
    assert create.call_count == 0
    assert _attempt_rows(host) == []
