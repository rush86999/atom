"""Goal 9: coordinated-vision auxiliary dispatch accounting.

Failure-first: ``BYOKHandler._get_coordinated_vision_description`` used to
issue a raw paid ``chat.completions.create`` with SDK-default retries, no
durable admission/reservation, no attempt identity and no settlement. Worse,
its ``except Exception: return None`` swallowed accounting refusal and let the
caller proceed into the main paid dispatch.

These controls double only the transport; the ledger/policy are the real
scratch SQLite store. Every auxiliary vision call must ride the EXISTING
physical-attempt machinery: one retry-disabled wire request, a durable
admission bound before dispatch, an exact/unknown settlement after it, and
workspace/tenant attribution. Paid/unknown image refusal and genuine
numeric-zero free contracts are retained, and accounting refusal must never
cause another paid dispatch (chat, structured, or PDF).
"""
from __future__ import annotations

import asyncio
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from tests.test_goal9_physical_attempts import (
    TENANT,
    WORKSPACE,
    _attempt_rows,
    _make_handler,
    _pricing,
    _seed,
    host,
)
from core.llm.byok_handler import _AccountingBlockedError
from core.models import TokenUsage

pytest_plugins = ("tests.test_goal9_physical_attempts",)


# --------------------------------------------------------------------------
# doubled vision transport (sync OpenAI-shaped, clone-aware)
# --------------------------------------------------------------------------
class _VisionClient:
    """Scripted sync chat transport; records the retry policy it was called on.

    ``with_options`` returns a distinct clone (like the OpenAI SDK) that
    SHARES the script but records the clone's ``max_retries``, so a test can
    prove the wire request was issued by a retry-disabled client.
    """

    def __init__(self, provider_id, script, calls):
        self._provider_id = provider_id
        self._script = script
        self._calls = calls
        self.max_retries = None
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create))

    def with_options(self, **kwargs):
        child = _VisionClient(self._provider_id, self._script, self._calls)
        child.max_retries = kwargs.get("max_retries")
        return child

    def _create(self, **kwargs):
        self._calls.append({
            "provider": self._provider_id,
            "max_retries": self.max_retries,
            "kwargs": kwargs,
        })
        if not self._script:
            raise RuntimeError("unexpected paid dispatch")
        action = self._script.pop(0)
        if isinstance(action, BaseException):
            raise action
        return action


def _response(content="visual description", *, usage=True, model="gpt-4o-mini"):
    response = SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=content),
            finish_reason="stop")],
        model=model,
    )
    if usage:
        response.usage = SimpleNamespace(
            prompt_tokens=100, completion_tokens=20)
    return response


def _handler(monkeypatch, tmp_path, script, calls, catalog=None):
    return _make_handler(
        monkeypatch, tmp_path,
        catalog or {"openai": ["text-model", "gpt-4o-mini"]},
        sync={"openai": _VisionClient("openai", script, calls)})


def _per_token(model, input_tokens, output_tokens):
    return float(input_tokens + output_tokens) * 0.000001


def _vision(handler):
    return asyncio.run(handler._get_coordinated_vision_description(
        image_payload="aGVsbG8=",
        tenant_plan="free",
        is_managed=True,
    ))


# --------------------------------------------------------------------------
# direct helper: admission + retry-off + exact settlement
# --------------------------------------------------------------------------
def test_vision_admits_and_settles_exact_attempt_without_sdk_retries(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0, limit=0)  # observe: unknown image bound admitted
    _pricing(monkeypatch, _per_token)
    calls = []
    handler = _handler(monkeypatch, tmp_path, [_response()], calls)

    assert _vision(handler) == "visual description"

    assert len(calls) == 1
    assert calls[0]["max_retries"] == 0, (
        f"vision dispatch kept hidden SDK retries: {calls[0]}")
    # The wire request is the real image-bearing payload.
    content = calls[0]["kwargs"]["messages"][-1]["content"]
    assert any(part.get("type") == "image_url" for part in content)

    rows = _attempt_rows(host)
    assert len(rows) == 1, [r.attempt_id for r in rows]
    row = rows[0]
    assert row.attempt_id and row.request_id
    assert ":vision:" in row.attempt_id
    assert row.provider_id == "openai"
    assert row.model_name == "gpt-4o-mini"
    assert row.workspace_id == WORKSPACE
    assert row.tenant_id == TENANT
    assert row.prompt_tokens == 100 and row.completion_tokens == 20
    assert row.billed is True
    assert row.cost_usd == pytest.approx(120 * 0.000001)
    assert row.pricing_status == "priced"
    assert row.reservation_status == "settled"


def test_vision_without_usage_keeps_unknown_liability(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0, limit=0)
    _pricing(monkeypatch, _per_token)
    calls = []
    handler = _handler(monkeypatch, tmp_path, [_response(usage=False)], calls)

    assert _vision(handler) == "visual description"
    row = _attempt_rows(host)[0]
    assert row.billed is True
    assert row.prompt_tokens == 0 and row.completion_tokens == 0
    assert row.cost_usd is None and row.pricing_status == "unknown"
    assert row.reservation_status == "uncertain"


def test_vision_provider_failure_leaves_durable_active_attempt(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0, limit=0)
    _pricing(monkeypatch, _per_token)
    calls = []
    handler = _handler(
        monkeypatch, tmp_path,
        [RuntimeError("controlled vision transport failure")], calls)

    assert _vision(handler) is None
    assert len(calls) == 1
    rows = _attempt_rows(host)
    assert len(rows) == 1, "failed paid attempt left no durable record"
    assert rows[0].reservation_status == "active"
    assert rows[0].cost_usd is None


# --------------------------------------------------------------------------
# paid/unknown image refusal + genuine free contract retained
# --------------------------------------------------------------------------
def test_vision_unknown_image_price_refuses_before_dispatch(
        host, monkeypatch, tmp_path):
    _seed(host, spend=90.0, limit=100.0)  # hard_stop with headroom
    _pricing(monkeypatch, _per_token)  # positive text price; image unknown
    calls = []
    handler = _handler(monkeypatch, tmp_path, [_response()], calls)

    with pytest.raises(_AccountingBlockedError):
        _vision(handler)
    assert calls == [], "unknown image price dispatched anyway"
    assert _attempt_rows(host) == []


def test_vision_missing_price_refuses_before_dispatch(
        host, monkeypatch, tmp_path):
    _seed(host, spend=90.0, limit=100.0)
    _pricing(monkeypatch, lambda *a, **k: None)
    calls = []
    handler = _handler(monkeypatch, tmp_path, [_response()], calls)

    with pytest.raises(_AccountingBlockedError):
        _vision(handler)
    assert calls == []
    assert _attempt_rows(host) == []


def test_vision_authoritative_zero_price_keeps_free_contract(
        host, monkeypatch, tmp_path):
    _seed(host, spend=90.0, limit=100.0)  # hard_stop, no headroom left
    _pricing(monkeypatch, lambda *a, **k: 0.0)  # authoritative numeric zero
    calls = []
    handler = _handler(monkeypatch, tmp_path, [_response()], calls)

    assert _vision(handler) == "visual description"
    assert len(calls) == 1
    row = _attempt_rows(host)[0]
    assert row.cost_usd == pytest.approx(0.0)
    assert float(row.reserved_cost_usd) == pytest.approx(0.0)
    assert row.reservation_status == "settled"


# --------------------------------------------------------------------------
# chat caller: same job binding, and refusal stops the MAIN paid dispatch
# --------------------------------------------------------------------------
def test_chat_vision_and_main_dispatch_share_request_but_not_attempts(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0, limit=0)
    _pricing(monkeypatch, _per_token)
    calls = []
    handler = _handler(
        monkeypatch, tmp_path,
        [_response("vision text"), _response("main answer", model="text-model")],
        calls)
    handler._model_supports_vision = Mock(return_value=False)
    handler.get_ranked_providers = AsyncMock(
        return_value=[("openai", "text-model")])

    answer = asyncio.run(handler.generate_response(
        "click the button", image_payload="aGVsbG8="))

    assert answer == "main answer"
    assert len(calls) == 2, calls
    assert calls[0]["max_retries"] == 0, "vision retry policy not disabled"
    assert calls[1]["max_retries"] is None, "main dispatch retry policy changed"
    assert calls[0]["kwargs"]["model"] == "gpt-4o-mini"
    assert calls[1]["kwargs"]["model"] == "text-model"

    rows = _attempt_rows(host)
    assert len(rows) == 2, [r.attempt_id for r in rows]
    assert len({r.request_id for r in rows}) == 1, "job binding split"
    assert len({r.attempt_id for r in rows}) == 2, "attempt identity reused"
    vision_rows = [r for r in rows if ":vision:" in r.attempt_id]
    assert len(vision_rows) == 1
    assert vision_rows[0].workspace_id == WORKSPACE
    assert vision_rows[0].tenant_id == TENANT


def test_chat_accounting_refusal_does_not_reach_main_paid_dispatch(
        host, monkeypatch, tmp_path):
    _seed(host, spend=90.0, limit=100.0)  # hard_stop; image price unknown
    _pricing(monkeypatch, _per_token)
    calls = []
    handler = _handler(monkeypatch, tmp_path, [_response()], calls)
    handler._model_supports_vision = Mock(return_value=False)
    handler.get_ranked_providers = AsyncMock(
        return_value=[("openai", "text-model")])

    answer = asyncio.run(handler.generate_response(
        "click the button", image_payload="aGVsbG8="))

    assert "could not be authorized" in answer
    assert calls == [], f"accounting refusal fell through to paid dispatch: {calls}"
    assert _attempt_rows(host) == []


# --------------------------------------------------------------------------
# structured caller: refusal stops before any paid dispatch
# --------------------------------------------------------------------------
def test_structured_accounting_refusal_does_not_reach_paid_dispatch(
        host, monkeypatch, tmp_path):
    _seed(host, spend=90.0, limit=100.0)
    _pricing(monkeypatch, _per_token)
    calls = []
    handler = _handler(monkeypatch, tmp_path, [_response()], calls)
    handler._model_supports_vision = Mock(return_value=False)
    handler.get_ranked_providers = AsyncMock(
        return_value=[("openai", "text-model")])

    class _Model:
        @staticmethod
        def model_json_schema():
            return {"type": "object", "properties": {}}

    result = asyncio.run(handler.generate_structured_response(
        prompt="click the button",
        system_instruction="be precise",
        response_model=_Model,
        image_payload="aGVsbG8=",
    ))

    assert result is None
    assert calls == [], f"accounting refusal fell through to paid dispatch: {calls}"
    assert _attempt_rows(host) == []


# --------------------------------------------------------------------------
# PDF caller: one attempt per extracted image, shared document request id
# --------------------------------------------------------------------------
def _pdf_service(handler, png_data, image_count=2):
    from integrations.pdf_processing.pdf_ocr_service import PDFOCRService

    service = PDFOCRService()
    service.use_byok = True
    service.byok_manager = MagicMock()
    service.byok_manager.get_handler = Mock(return_value=handler)

    class FakePage:
        def get_images(self, full=True):
            return [(i + 1, 0, 0, 0, 0, 0, 0) for i in range(image_count)]

    class FakeDoc:
        page_count = 1

        def __getitem__(self, idx):
            return FakePage()

        def extract_image(self, xref):
            return {"ext": "png", "width": 300, "height": 200,
                    "image": png_data}

        def close(self):
            pass

    return service, FakeDoc()


def _png_bytes():
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (300, 200), color="green").save(buffer, format="PNG")
    return buffer.getvalue()


def _run_pdf(monkeypatch, service, doc):
    import sys
    import types

    fitz_mod = types.ModuleType("fitz")
    fitz_mod.open = Mock(return_value=doc)
    monkeypatch.setitem(sys.modules, "fitz", fitz_mod)
    monkeypatch.delitem(sys.modules, "pdf2image", raising=False)
    return asyncio.run(
        service._extract_and_process_images(b"pdf", True))


def test_pdf_each_image_is_a_physical_attempt_in_one_job(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0, limit=0)
    _pricing(monkeypatch, _per_token)
    calls = []
    handler = _handler(
        monkeypatch, tmp_path,
        [_response("chart one"), _response("chart two")], calls)
    service, doc = _pdf_service(handler, _png_bytes(), image_count=2)

    result = _run_pdf(monkeypatch, service, doc)

    assert result["success"] is True
    assert len(calls) == 2
    assert all(call["max_retries"] == 0 for call in calls)
    rows = _attempt_rows(host)
    assert len(rows) == 2, [r.attempt_id for r in rows]
    assert len({r.request_id for r in rows}) == 1
    assert rows[0].request_id.startswith("pdf-vision-")
    assert len({r.attempt_id for r in rows}) == 2
    assert all(":vision:" in r.attempt_id for r in rows)
    assert all(r.reservation_status == "settled" for r in rows)
    assert result["image_descriptions"][0]["ai_description"] == "chart one"


def test_pdf_accounting_refusal_never_dispatches(
        host, monkeypatch, tmp_path):
    _seed(host, spend=90.0, limit=100.0)
    _pricing(monkeypatch, _per_token)
    calls = []
    handler = _handler(monkeypatch, tmp_path, [_response()], calls)
    service, doc = _pdf_service(handler, _png_bytes(), image_count=2)

    result = _run_pdf(monkeypatch, service, doc)

    assert result["success"] is True
    assert calls == [], f"refused PDF images dispatched: {calls}"
    assert _attempt_rows(host) == []
    assert all("ai_description" not in item
               for item in result["image_descriptions"])
