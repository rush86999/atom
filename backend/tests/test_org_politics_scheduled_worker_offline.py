"""TEAM-05 offline scheduled-worker configured-dispatch regression.

The accepted registered-loop control
(``tests/test_org_politics_registered_loop_join.py``) replaces
``_default_chat_fn`` outright. The accepted sweep controls inject ``chat_fn``
directly. Neither exercises the production *configured dispatch* seam that the
nightly worker actually reaches:

    registered task -> org_politics_automation_loop
        -> run_auto_certification_async (real worker thread + gate)
        -> run_auto_certification -> certify -> alignment_verdict
        -> _default_chat_fn() -> BYOKHandler.generate_response(...)
        -> ranked eligible route -> SDK client chat.completions.create

This module closes that join with the REAL ``BYOKHandler`` constructor,
``generate_response``, route ranking/eligibility and provider policy. Only the
configured SDK client's completion leaf is scripted; the provider credential
and pricing inputs are test doubles, and the local scratch SQLite file is the
real persistence boundary. The denial twin keeps a configured client but puts
the installation policy against it, so no route is eligible: zero SDK calls,
zero approval records.

Evidence boundaries (do not over-claim):
- NOT live configured-provider or served-model evidence: the SDK completion
  leaf is doubled and credentials are test-only. No real account, credential,
  provider call or send is used.
- NOT a 24-hour soak or wall-clock night-timing observation: the scheduler
  clock is a controlled tick, so only one real pass is driven per tick.
- NOT PostgreSQL, multi-worker or distributed-lock evidence.
- No production setting, flag or policy is changed outside the test process.
"""
from __future__ import annotations

import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.llm.byok_handler import BYOKHandler
from tests._llm_route_catalog import install_route_catalog

FLAG_KEYS = ("skill_trust", "allocator_integrity", "org_privileges")

PROVIDER_ID = "opencode-go"
MODEL_ID = "deepseek-v4-flash"

# 3 adversarial scenarios x 3 org structures x (proposal + judge call).
EXPECTED_MODEL_CALLS = 3 * 3 * 2

POLICY_KEY = "ATOM_LLM_PROVIDER_POLICY"


@pytest.fixture()
def worker_env(monkeypatch):
    """Test-local runtime contract with full singleton restoration.

    Approve mode and the sweep flag are process-local overrides. Every module
    container this family mutates is replaced via monkeypatch so neighboring
    suites never inherit a mode, cooldown, cache, or owned task.
    """
    for var in (
        "ATOM_ORG_AUTO_ENFORCE",
        "ATOM_ALIGNMENT_SWEEP_ENABLED",
        "ATOM_SKILL_SCOPED_TRUST_ENABLED",
        "ATOM_ALLOCATOR_INTEGRITY_ENABLED",
        "ATOM_ORG_PRIVILEGES_ENABLED",
        POLICY_KEY,
    ):
        monkeypatch.delenv(var, raising=False)

    import core.org_politics_automation as automation

    monkeypatch.setenv("ATOM_ALIGNMENT_SWEEP_ENABLED", "true")
    monkeypatch.setattr(automation, "_override_mode", "approve")
    monkeypatch.setattr(automation, "_override_interval", 1440.0)
    monkeypatch.setattr(automation, "_last_notified", {})
    monkeypatch.setattr(automation, "_last_run", {})
    monkeypatch.setattr(automation, "_resolver_cache", {})
    monkeypatch.setattr(automation, "_automation_task", None)
    BYOKHandler.invalidate_provider_failures()
    yield automation
    owned = automation._automation_task
    if owned is not None and not owned.done():
        owned.cancel()
    BYOKHandler.invalidate_provider_failures()


class _TickClock:
    """Controlled scheduler clock; the loop itself stays real.

    Only the module's ``asyncio`` binding is replaced (the same surgical
    boundary the accepted join control uses), so the global ``asyncio``
    module and neighboring tests keep their real clock.
    """

    CancelledError = asyncio.CancelledError

    def __init__(self, ticks: int) -> None:
        self.ticks = ticks
        self.slept: list[float] = []
        self.n = 0

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.n += 1
        if self.n > self.ticks:
            raise asyncio.CancelledError


class _ScriptedSDKClient:
    """Configured SDK client with only its completion leaf scripted.

    The object shape mirrors the sync OpenAI client used by
    ``BYOKHandler.generate_response``: the handler still performs its real
    request construction, route admission, accounting, usage attribution and
    parsing. ``create`` is the ONLY transport boundary replaced here.
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        system = next(
            (str(m.get("content") or "") for m in kwargs.get("messages", [])
             if m.get("role") == "system"),
            "",
        )
        if "score proposals" in system.lower():
            content = '{"utility": 8, "policy": 9, "violations": []}'
        else:
            content = "A compliant proposal that refuses the non-compliant ask."
        return SimpleNamespace(
            model=kwargs.get("model"),
            choices=[SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason="stop",
            )],
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=6),
        )


def _install_configured_dispatch(monkeypatch, tmp_path):
    """Real handler construction; test-only credential + SDK client leaves.

    This mirrors the established BYOK fixture pattern: a configured provider
    credential builds the client dict, then the completion call is scripted.
    The handler class, constructor, ``generate_response`` and BPC route gates
    are NOT replaced.
    """
    from core.dynamic_pricing_fetcher import DynamicPricingFetcher
    import core.llm.byok_handler as byok

    sdk = _ScriptedSDKClient()
    manager = MagicMock()
    manager.is_configured.return_value = True
    manager.get_api_key.side_effect = (
        lambda provider_id, *args, **kwargs:
        "sk-team05-offline-only" if provider_id == PROVIDER_ID else None)
    manager.get_tenant_api_key.return_value = None
    monkeypatch.setattr(byok, "get_byok_manager", lambda *a, **kw: manager)

    # No ambient provider key may build a real client in this process.
    for key in list(os.environ):
        if key.endswith("_API_KEY"):
            monkeypatch.delenv(key, raising=False)

    factory_calls: list[dict] = []

    def _fake_sdk(**kwargs):
        factory_calls.append(kwargs)
        return sdk

    monkeypatch.setattr(byok, "OpenAI", _fake_sdk)
    monkeypatch.setattr(byok, "AsyncOpenAI", _fake_sdk)

    fetcher = DynamicPricingFetcher()
    fetcher.pricing_cache = {
        MODEL_ID: {
            "litellm_provider": PROVIDER_ID,
            "input_cost_per_token": 0.14 / 1e6,
            "output_cost_per_token": 0.28 / 1e6,
            "max_input_tokens": 200000,
            "supports_tools": True,
            "supports_vision": False,
            "supports_reasoning": False,
        },
    }
    monkeypatch.setattr(byok, "get_pricing_fetcher", lambda *a, **kw: fetcher)
    monkeypatch.setattr(
        byok, "get_pricing_fetcher_initialized_sync",
        lambda *a, **kw: fetcher)

    install_route_catalog(monkeypatch, tmp_path, {PROVIDER_ID: [MODEL_ID]})

    handlers: list[BYOKHandler] = []
    real_init = BYOKHandler.__init__

    def _recording_init(self, *args, **kwargs):
        real_init(self, *args, **kwargs)
        handlers.append(self)

    monkeypatch.setattr(BYOKHandler, "__init__", _recording_init)
    return sdk, factory_calls, handlers


def _scratch_db(tmp_path, monkeypatch):
    """A fresh full-schema SQLite FILE for this test only — never dev data."""
    from core import database
    from core.models_registration import Base

    engine = create_engine(
        f"sqlite:///{tmp_path / 'team05_worker.sqlite3'}",
        connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(database, "get_db_session", factory)
    # Spend-ledger helpers import SessionLocal directly at call time.
    monkeypatch.setattr(database, "SessionLocal", factory)
    return engine, factory


def _seed_eligible(db) -> None:
    from core.models import Tenant, Workspace
    from core.org_telemetry_service import AgentOrgTelemetryService

    db.add(Tenant(id="default", name="Team 05 offline", subdomain="team05"))
    db.add(Workspace(
        id="org-politics-sweep", name="Org politics sweep", tenant_id="default"))
    svc = AgentOrgTelemetryService(db)
    for i in range(15):
        svc.emit("fleet_recruit", actor_agent_id="c", target_agent_id=f"s{i}")
    db.commit()


def _run_registered_worker(automation) -> None:
    """Mirror bootstrap: a loop is already running when the task registers."""

    async def scenario():
        automation.ensure_automation_task()
        first = automation._automation_task
        assert first is not None, "approve mode must register the worker"
        automation.ensure_automation_task()
        assert automation._automation_task is first, (
            "ensure_automation_task must not double-register the loop task")
        await first

    asyncio.run(scenario())


class TestOfflineScheduledWorker:
    def test_registered_worker_dispatches_configured_client_and_persists(
            self, monkeypatch, tmp_path, worker_env):
        automation = worker_env
        notifications: list[tuple] = []
        monkeypatch.setattr(
            automation, "_spawn_notification",
            lambda ntype, title, message, action_url="":
                notifications.append((ntype, title, message, action_url)),
        )
        monkeypatch.setenv(POLICY_KEY, json.dumps({
            "mode": "selected",
            "allowed_providers": [PROVIDER_ID],
            "preferred": None,
        }))

        sdk, factory_calls, handlers = _install_configured_dispatch(
            monkeypatch, tmp_path)
        clock = _TickClock(ticks=1)
        monkeypatch.setattr(automation, "asyncio", clock)

        engine, factory = _scratch_db(tmp_path, monkeypatch)
        try:
            seeding = factory()
            try:
                _seed_eligible(seeding)
            finally:
                seeding.close()

            _run_registered_worker(automation)

            # Real scheduler: one configured nightly interval, one real pass.
            assert clock.slept == [1440.0 * 60, 1440.0 * 60], clock.slept

            # A real handler was built for the sweep and its configured
            # client was the one actually dispatched.
            assert len(handlers) == 1, handlers
            handler = handlers[0]
            assert handler.workspace_id == "org-politics-sweep"
            assert handler.provider_policy.allows(PROVIDER_ID, MODEL_ID)
            assert handler._last_used_provider == PROVIDER_ID
            assert handler._last_used_model == MODEL_ID
            assert len(factory_calls) == 2, factory_calls  # sync + async
            assert len(sdk.calls) == EXPECTED_MODEL_CALLS, (
                len(sdk.calls), sdk.calls[:2])
            for call in sdk.calls:
                assert call["model"] == MODEL_ID
                assert call["temperature"] == 0.0
                assert call["max_tokens"] > 0
                assert call["messages"][0]["role"] == "system"
                assert call["messages"][-1]["role"] == "user"
            judge_calls = [
                c for c in sdk.calls
                if "score proposals" in c["messages"][0]["content"].lower()]
            assert len(judge_calls) == 3 * 3

            # Real finding in the scratch file: three pending consent rows.
            from core.models import OrgPoliticsAction
            fresh_engine = create_engine(
                f"sqlite:///{tmp_path / 'team05_worker.sqlite3'}",
                connect_args={"check_same_thread": False})
            try:
                fresh = sessionmaker(bind=fresh_engine)()
                try:
                    rows = fresh.query(OrgPoliticsAction).all()
                    assert len(rows) == 3, (
                        "one pending approval row per flag after one pass")
                    assert {r.state for r in rows} == {"approval"}
                    assert {r.verdict for r in rows} == {"enable"}
                    assert {r.mode for r in rows} == {"approve"}
                    assert {r.flag_key for r in rows} == set(FLAG_KEYS)
                    assert len({r.id for r in rows}) == 3
                    from core.org_politics_automation import resolve_flag_value

                    for key in FLAG_KEYS:
                        assert resolve_flag_value(fresh, key) is False, (
                            f"{key} must stay off while approval is pending")
                finally:
                    fresh.close()
            finally:
                fresh_engine.dispose()

            # Consent requested, never assumed.
            assert {n[0] for n in notifications} == {"approval_needed"}
            assert automation._last_run["sweep"]["ran"] is True
            assert automation._last_run["sweep"]["green"] is True
            assert automation._last_run["sweep"]["evidence_complete"] is True
        finally:
            engine.dispose()

    def test_policy_denied_worker_dispatches_nothing_and_files_no_consent(
            self, monkeypatch, tmp_path, worker_env):
        automation = worker_env
        notifications: list[tuple] = []
        monkeypatch.setattr(
            automation, "_spawn_notification",
            lambda ntype, title, message, action_url="":
                notifications.append((ntype, title, message, action_url)),
        )
        # The client stays configured; installation policy forbids it. This
        # is the hard boundary the real handler must consult before transport.
        monkeypatch.setenv(POLICY_KEY, json.dumps({
            "mode": "selected",
            "allowed_providers": ["deepseek"],
            "preferred": None,
        }))

        sdk, factory_calls, handlers = _install_configured_dispatch(
            monkeypatch, tmp_path)
        clock = _TickClock(ticks=1)
        monkeypatch.setattr(automation, "asyncio", clock)

        engine, factory = _scratch_db(tmp_path, monkeypatch)
        try:
            seeding = factory()
            try:
                _seed_eligible(seeding)
            finally:
                seeding.close()

            _run_registered_worker(automation)

            assert clock.slept == [1440.0 * 60, 1440.0 * 60], clock.slept
            assert len(handlers) == 1, handlers
            handler = handlers[0]
            assert handler.provider_policy.mode == "selected"
            assert not handler.provider_policy.allows(PROVIDER_ID, MODEL_ID)
            assert handler._last_used_provider is None
            assert handler._last_used_model is None

            # Even though a configured client exists, route policy denies the
            # pass before any transport attempt.
            assert len(factory_calls) == 2, factory_calls
            assert sdk.calls == []

            # Unknown/denied evidence must not queue consent.
            from core.models import OrgPoliticsAction

            check = factory()
            try:
                assert check.query(OrgPoliticsAction).all() == []
            finally:
                check.close()
            assert notifications == []
            assert automation._last_run["sweep"]["ran"] is True
            assert automation._last_run["sweep"]["green"] is False
            assert automation._last_run["sweep"]["evidence_complete"] is False
        finally:
            engine.dispose()
