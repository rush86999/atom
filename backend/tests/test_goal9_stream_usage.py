"""Authoritative stream usage — only when the provider actually supplies it.

Streaming did not request usage, but several providers still emit a terminal
usage chunk. When that report is COMPLETE its token counts are authoritative
for THAT physical attempt and settle the same ledger row; absent or partial
usage keeps the conservative reservation as explicit unknown liability.
Transport/semantic failure is never free; a visible delta is never replayed.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from tests.test_goal9_physical_attempts import (
    _attempt_rows,
    _make_handler,
    _pricing,
    _reservation_pricing,
    _seed,
    _stream,
    _visible,
    host,
)

pytest_plugins = ("tests.test_goal9_physical_attempts",)


def _usage_chunk(prompt, completion):
    return SimpleNamespace(choices=[], usage=SimpleNamespace(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=prompt + completion,
    ))


def _partial_usage_chunk(prompt):
    return SimpleNamespace(choices=[], usage=SimpleNamespace(
        prompt_tokens=prompt))


def _handler(monkeypatch, tmp_path, model="gpt-4o"):
    from tests.test_goal9_physical_attempts import _StreamClient
    calls = []
    client = _StreamClient("openai", [], calls)
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": [model]},
        async_={"openai": client})
    return handler, client, calls


def _set_script(client, actions):
    client._script = list(actions)


def test_complete_terminal_usage_settles_priced_attempt(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    handler, client, calls = _handler(monkeypatch, tmp_path)
    _set_script(client, [{"chunks": [
        _visible("hello "), _visible("world"), _usage_chunk(10, 5)]}])
    text = "".join(_stream(handler, "gpt-4o", "openai"))
    assert text == "hello world"
    rows = _attempt_rows(host)
    assert len(rows) == 1
    row = rows[0]
    assert row.billed is True
    assert row.prompt_tokens == 10 and row.completion_tokens == 5
    assert row.cost_usd == pytest.approx(0.25)
    assert row.pricing_status == "priced"
    assert row.reservation_status == "settled"
    assert float(row.reserved_cost_usd or 0.0) == 0.0


def test_absent_usage_stays_unknown_and_reserved(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    handler, client, calls = _handler(monkeypatch, tmp_path)
    _set_script(client, [{"chunks": [_visible("no usage")]}])
    assert "".join(_stream(handler, "gpt-4o", "openai")) == "no usage"
    row = _attempt_rows(host)[0]
    assert row.billed is True
    assert row.cost_usd is None and row.pricing_status == "unknown"
    assert row.reservation_status == "uncertain"
    assert float(row.reserved_cost_usd) == pytest.approx(0.25)


def test_partial_usage_is_not_treated_as_authoritative(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    handler, client, calls = _handler(monkeypatch, tmp_path)
    _set_script(client, [{"chunks": [
        _visible("partial usage"), _partial_usage_chunk(10)]}])
    assert "".join(_stream(handler, "gpt-4o", "openai")) == "partial usage"
    row = _attempt_rows(host)[0]
    assert row.prompt_tokens == 0 and row.completion_tokens == 0
    assert row.cost_usd is None and row.pricing_status == "unknown"
    assert row.reservation_status == "uncertain"


def test_visible_partial_then_failure_is_not_replayed_or_settled(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    handler, client, calls = _handler(monkeypatch, tmp_path)
    _set_script(client, [{
        "chunks": [_visible("PARTIAL"), _usage_chunk(10, 5)],
        "fail_after": 2,
        "fail_exc": RuntimeError("connection dropped mid-stream"),
    }])
    text = "".join(_stream(handler, "gpt-4o", "openai"))
    assert text == "PARTIAL"
    assert len(calls) == 1, "a visible delta must never be replayed"
    row = _attempt_rows(host)[0]
    # The failed attempt keeps its reservation; terminal usage that arrived
    # before the failure is not a successful settlement.
    assert row.billed is False
    assert row.reservation_status == "active"
    assert float(row.reserved_cost_usd) == pytest.approx(0.25)


def test_retry_settles_its_own_attempt_with_usage(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    from tests.test_goal9_physical_attempts import _StreamClient
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path,
        {"openai": ["shared-model"], "deepseek": ["shared-model"]},
        async_={
            "openai": _StreamClient(
                "openai", [{"raise": RuntimeError("controlled failure")}],
                calls),
            "deepseek": _StreamClient(
                "deepseek", [{"chunks": [
                    _visible("SECOND"), _usage_chunk(10, 5)]}], calls),
        })
    text = "".join(_stream(handler, "shared-model", "openai"))
    assert text == "SECOND"
    rows = _attempt_rows(host)
    assert len(rows) == 2, [r.attempt_id for r in rows]
    assert len({r.attempt_id for r in rows}) == 2
    by_provider = {r.provider_id: r for r in rows}
    assert by_provider["openai"].reservation_status == "active"
    assert by_provider["deepseek"].reservation_status == "settled"
    assert by_provider["deepseek"].prompt_tokens == 10
    assert by_provider["deepseek"].cost_usd == pytest.approx(0.25)


def test_usage_with_unknown_pricing_records_tokens_and_keeps_liability(
        host, monkeypatch, tmp_path):
    # No billing cap: unknown pricing is admitted as explicit unknown
    # liability (hard_stop would refuse before dispatch instead).
    _seed(host, spend=0.0, limit=0.0)
    _pricing(monkeypatch, lambda *a, **k: None)
    # A model with no static alias either: the price is genuinely unknown.
    model = "controlled-unknown-stream-model"
    handler, client, calls = _handler(monkeypatch, tmp_path, model=model)
    _set_script(client, [{"chunks": [
        _visible("usage but no price"), _usage_chunk(10, 5)]}])
    assert "".join(_stream(handler, model, "openai")) == (
        "usage but no price")
    row = _attempt_rows(host)[0]
    assert row.prompt_tokens == 10 and row.completion_tokens == 5
    assert row.cost_usd is None and row.pricing_status == "unknown"
    assert row.reservation_status == "uncertain"
