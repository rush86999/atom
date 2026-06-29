"""Workstream B (revised) — cascade routing inside BYOKHandler.

Tests verify the cascade fires only on schema-validation failures, only
once, only when the original model is not already frontier, and that the
escalation target stays inside the same provider family (the structural
BYOK invariant). All tests mock the BYOKHandler internals — no real LLM
calls.

See .planning/HALLUCINATION_MITIGATION_PHASE2_REVISION.md for why
cascade lives inside BYOKHandler rather than LLMService.
"""
from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _clean_mitigation_env(monkeypatch):
    for k in list(os.environ):
        if k.startswith("ATOM_") and (
            "VERIFIED" in k or "CASCADE" in k or "SELF_CONSISTENCY" in k
        ):
            monkeypatch.delenv(k, raising=False)


@pytest.fixture(autouse=True)
def _fake_instructor(monkeypatch):
    """Inject a fake ``instructor`` module so BYOKHandler exercises the
    structured-response code path even when the real package is absent.

    Also stubs the tenant-plan DB lookup so the cascade loop is reachable
    from tests without a live database. Upstream's
    ``generate_structured_response`` opens a real ``get_db_session()`` to
    resolve tenant_plan; if that fails (no DB in test env), the body
    short-circuits at "Managed AI blocked for free tier" and the cascade
    code is never reached.
    """
    fake_module = MagicMock()
    fake_client = MagicMock()
    fake_module.from_openai.return_value = fake_client
    monkeypatch.setitem(sys.modules, "instructor", fake_module)
    from core.llm import byok_handler

    monkeypatch.setattr(byok_handler, "instructor", fake_module, raising=False)
    monkeypatch.setattr(byok_handler, "INSTRUCTOR_AVAILABLE", True)

    # Stub the tenant-plan lookup. The body does:
    #     with get_db_session() as db:
    #         ... db.query(Workspace).filter(...).first()
    #         ... db.query(Tenant).filter(...).first()
    # Yield a mock whose query chain returns a paid-tier workspace + tenant
    # so the "free tier managed AI" early-return never fires.
    fake_db = MagicMock()
    paid_workspace = SimpleNamespace(tenant_id="t-1")
    paid_tenant = SimpleNamespace(plan_type=SimpleNamespace(value="pro"))
    fake_db.query.return_value.filter.return_value.first.side_effect = [
        paid_workspace,
        paid_tenant,
    ]

    class _Ctx:
        def __enter__(self):
            return fake_db

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(byok_handler, "get_db_session", lambda: _Ctx())
    yield fake_client


def _make_handler():
    """Construct a BYOKHandler with mocked clients/db (no real I/O)."""
    from core.llm.byok_handler import BYOKHandler

    handler = BYOKHandler.__new__(BYOKHandler)
    handler.workspace_id = "ws-1"
    handler.tenant_id = "t-1"
    handler.db_session = MagicMock()
    handler.clients = {"openai": MagicMock(), "anthropic": MagicMock()}
    handler.governance = None
    handler._is_trial_restricted = lambda: False
    handler.byok_manager = MagicMock()
    handler.byok_manager.get_tenant_api_key = MagicMock(return_value=None)
    return handler


def _stub_options(handler, options):
    """Patch the chain of calls that produce the ranked options list."""
    handler.analyze_query_complexity = MagicMock(return_value=MagicMock(value="standard"))
    handler.get_ranked_providers = MagicMock(return_value=options)
    handler.get_context_window = MagicMock(return_value=8000)
    handler.truncate_to_context = MagicMock(side_effect=lambda p, *a, **k: p)


def _patch_cascade_helpers(frontier_for_provider="gpt-4o", is_frontier=False):
    """Patch the two hallucination_config helpers the cascade block uses.

    The helpers are imported INSIDE the function body of
    ``generate_structured_response`` (lazy import to avoid any circular-import
    risk with core.models), so we patch them at their source rather than on
    the consumer module.
    """
    return (
        patch("core.hallucination_config.is_frontier_model", return_value=is_frontier),
        patch(
            "core.hallucination_config.get_frontier_model_for_provider",
            return_value=frontier_for_provider,
        ),
    )


# ---------------------------------------------------------------------------
# B1: flag off → single call, no cascade
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_B1_no_cascade_when_flag_off(_fake_instructor):
    """Flag off → handler does not attempt escalation even on schema error."""
    handler = _make_handler()
    _stub_options(handler, [("openai", "gpt-4o-mini")])

    call_count = {"n": 0}

    def fake_create(**kwargs):
        call_count["n"] += 1
        raise json.JSONDecodeError("schema fail", "doc", 0)

    _fake_instructor.chat.completions.create = fake_create

    p1, p2 = _patch_cascade_helpers()
    with p1, p2:
        result = await handler.generate_structured_response(
            prompt="test",
            system_instruction="sys",
            response_model=dict,
            cascade=False,
        )

    assert result is None
    # Only the original attempt — no escalation.
    assert call_count["n"] == 1


# ---------------------------------------------------------------------------
# B2: first call succeeds → no cascade
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_B2_cascade_skipped_when_first_call_succeeds(_fake_instructor):
    """Success on the first attempt → no escalation."""
    handler = _make_handler()
    _stub_options(handler, [("openai", "gpt-4o-mini")])

    sentinel = SimpleNamespace(_raw_response=None)
    _fake_instructor.chat.completions.create = MagicMock(return_value=sentinel)

    p1, p2 = _patch_cascade_helpers()
    with p1 as is_frontier_spy, p2 as frontier_spy:
        result = await handler.generate_structured_response(
            prompt="test",
            system_instruction="sys",
            response_model=dict,
            cascade=True,
        )

    assert result is sentinel
    # Cascade helpers never consulted on success.
    is_frontier_spy.assert_not_called()
    frontier_spy.assert_not_called()


# ---------------------------------------------------------------------------
# B3: schema-validation failure → escalate to frontier in same family
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_B3_cascade_escalates_on_schema_validation_failure(_fake_instructor):
    """Schema error on gpt-4o-mini → retry on gpt-4o, return its result."""
    handler = _make_handler()
    _stub_options(handler, [("openai", "gpt-4o-mini")])

    calls = []
    frontier_sentinel = SimpleNamespace(_raw_response=None, cascaded=True)

    def fake_create(**kwargs):
        calls.append(kwargs.get("model"))
        if len(calls) == 1:
            raise json.JSONDecodeError("schema fail", "doc", 0)
        return frontier_sentinel

    _fake_instructor.chat.completions.create = fake_create

    p1, p2 = _patch_cascade_helpers(frontier_for_provider="gpt-4o")
    with p1, p2:
        result = await handler.generate_structured_response(
            prompt="test",
            system_instruction="sys",
            response_model=dict,
            cascade=True,
        )

    assert result is frontier_sentinel
    # The first call used the original model; the second used the frontier.
    # Note: BYOKHandler passes model via kwargs; the mock captures it.
    assert len(calls) == 2


# ---------------------------------------------------------------------------
# B4: already frontier → no escalation
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_B4_cascade_skipped_when_already_frontier(_fake_instructor):
    """Schema failure on gpt-4o (already frontier) → no escalation."""
    handler = _make_handler()
    _stub_options(handler, [("openai", "gpt-4o")])

    call_count = {"n": 0}

    def fake_create(**kwargs):
        call_count["n"] += 1
        raise json.JSONDecodeError("schema fail", "doc", 0)

    _fake_instructor.chat.completions.create = fake_create

    # is_frontier_model returns True for gpt-4o.
    p1, p2 = _patch_cascade_helpers(frontier_for_provider="gpt-4o", is_frontier=True)
    with p1, p2 as frontier_spy:
        result = await handler.generate_structured_response(
            prompt="test",
            system_instruction="sys",
            response_model=dict,
            cascade=True,
        )

    assert result is None
    # Only the original frontier call. No escalation.
    assert call_count["n"] == 1
    frontier_spy.assert_not_called()


# ---------------------------------------------------------------------------
# B5: transient error → no cascade
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_B5_cascade_skipped_on_transient_error(_fake_instructor):
    """Network-style error → not a schema failure → no escalation."""
    handler = _make_handler()
    _stub_options(handler, [("openai", "gpt-4o-mini")])

    call_count = {"n": 0}

    def fake_create(**kwargs):
        call_count["n"] += 1
        raise ConnectionError("network down")

    _fake_instructor.chat.completions.create = fake_create

    p1, p2 = _patch_cascade_helpers()
    with p1, p2 as frontier_spy:
        result = await handler.generate_structured_response(
            prompt="test",
            system_instruction="sys",
            response_model=dict,
            cascade=True,
        )

    assert result is None
    assert call_count["n"] == 1
    frontier_spy.assert_not_called()


# ---------------------------------------------------------------------------
# B6: only retries once
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_B6_cascade_only_retries_once(_fake_instructor):
    """Even if the escalation also schema-fails, no second escalation."""
    handler = _make_handler()
    _stub_options(handler, [("openai", "gpt-4o-mini")])

    call_count = {"n": 0}

    def fake_create(**kwargs):
        call_count["n"] += 1
        # Both attempts fail with schema errors.
        raise json.JSONDecodeError("schema fail", "doc", 0)

    _fake_instructor.chat.completions.create = fake_create

    p1, p2 = _patch_cascade_helpers(frontier_for_provider="gpt-4o")
    # After the escalation is attempted, is_frontier_model returns True for
    # the frontier so it can't escalate again. Use a side_effect.
    with patch(
        "core.hallucination_config.is_frontier_model",
        side_effect=lambda m: m == "gpt-4o",
    ), p2:
        result = await handler.generate_structured_response(
            prompt="test",
            system_instruction="sys",
            response_model=dict,
            cascade=True,
        )

    assert result is None
    # Original + one escalation = 2 total. No more.
    assert call_count["n"] == 2


# ---------------------------------------------------------------------------
# B7: log line uses f-string, no kwargs (CLAUDE.md rule)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_B7_cascade_log_uses_fstrings_no_kwargs(_fake_instructor, monkeypatch):
    """The escalation log line must be f-string-only per CLAUDE.md."""
    from core.llm import byok_handler

    handler = _make_handler()
    _stub_options(handler, [("openai", "gpt-4o-mini")])

    def fake_create(**kwargs):
        model = kwargs.get("model", "")
        if "mini" in model:
            raise json.JSONDecodeError("schema fail", "doc", 0)
        return SimpleNamespace(_raw_response=None)

    _fake_instructor.chat.completions.create = fake_create

    captured = []

    def info_spy(msg, *a, **kw):
        captured.append((msg, kw))

    monkeypatch.setattr(byok_handler.logger, "info", info_spy)

    p1, p2 = _patch_cascade_helpers(frontier_for_provider="gpt-4o")
    with p1, p2:
        await handler.generate_structured_response(
            prompt="test",
            system_instruction="sys",
            response_model=dict,
            cascade=True,
        )

    cascade_lines = [t for t in captured if "CASCADE ROUTING" in t[0]]
    assert len(cascade_lines) == 1
    line, kwargs_received = cascade_lines[0]
    assert "gpt-4o-mini" in line
    assert "gpt-4o" in line
    assert "ws-1" in line
    # CLAUDE.md: logger.info must be called with NO kwargs.
    assert kwargs_received == {}


# ---------------------------------------------------------------------------
# B8: provider family preserved (openai → openai)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_B8_cascade_preserves_provider_family(_fake_instructor):
    """OpenAI failure escalates to an OpenAI flagship, not Anthropic."""
    handler = _make_handler()
    _stub_options(handler, [("openai", "gpt-4o-mini")])

    # Replace clients with a dict subclass that records every get().
    class _SpyDict(dict):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.seen = []

        def get(self, key, *a, **k):
            self.seen.append(key)
            return super().get(key, *a, **k)

    openai_client = handler.clients["openai"]
    handler.clients = _SpyDict({"openai": openai_client, "anthropic": MagicMock()})

    def fake_create(**kwargs):
        model = kwargs.get("model", "")
        if "mini" in model:
            raise json.JSONDecodeError("schema fail", "doc", 0)
        return SimpleNamespace(_raw_response=None)

    _fake_instructor.chat.completions.create = fake_create

    with patch(
        "core.hallucination_config.is_frontier_model", return_value=False
    ), patch(
        "core.hallucination_config.get_frontier_model_for_provider",
        return_value="gpt-4o",
    ) as frontier_spy:
        await handler.generate_structured_response(
            prompt="test",
            system_instruction="sys",
            response_model=dict,
            cascade=True,
        )

    # frontier lookup was called with the CURRENT failing provider.
    frontier_spy.assert_called_once_with("openai")
    # Every client fetch went to the openai provider.
    assert all(p == "openai" for p in handler.clients.seen)


# ---------------------------------------------------------------------------
# B9: env-var resolution (Personal edition — no per-tenant override layer)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_B9_env_var_off_then_on_toggles_flag(monkeypatch):
    """Personal edition: env var is the only knob. Toggle works."""
    from core import hallucination_config as hc

    # Default off.
    assert hc.is_cascade_routing_enabled() is False
    # Flip on.
    monkeypatch.setenv("ATOM_CASCADE_ROUTING", "true")
    assert hc.is_cascade_routing_enabled() is True
    # Flip back off.
    monkeypatch.setenv("ATOM_CASCADE_ROUTING", "false")
    assert hc.is_cascade_routing_enabled() is False
