# -*- coding: utf-8 -*-
"""Fact-watch: proactive re-checking of live facts an agent grounded on.

Live 2026-09-04: the quoted "WG-350DSAV — In Stock" rested on
stock_on_hand = 1; one sale later the sent email is wrong and nothing
notices. The general mechanism: provider checkers + evidence extractors
registered from the integrations side, one core poller. All mocked —
zero network, DB session faked.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.fact_watch as fw
from core.fact_watch import (
    CHECKERS,
    EXTRACTORS,
    FactWatchService,
    extract_watchable_facts,
    get_fact_watch_service,
    register_checker,
    register_extractor,
)

# provider bindings register at FIRST import and must exist before the
# registry-snapshot fixture takes its baseline — import at module level.
import integrations.fact_watch_providers  # noqa: F401


@pytest.fixture(autouse=True)
def _restore_registries():
    """Registry isolation without breaking the import-once provider
    bindings: snapshot before, restore after."""
    checkers = dict(fw.CHECKERS)
    extractors = dict(fw.EXTRACTORS)
    yield
    fw.CHECKERS.clear()
    fw.CHECKERS.update(checkers)
    fw.EXTRACTORS.clear()
    fw.EXTRACTORS.update(extractors)


@pytest.fixture
def service():
    return FactWatchService(notify_cooldown_seconds=3600)


@pytest.fixture
def fake_db(monkeypatch):
    """Records CanvasAudit rows added by the notify leg."""
    added = []

    class _DB:
        def add(self, obj):
            added.append(obj)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("core.database.get_db_session", lambda: _DB())
    return added


@pytest.fixture
def fake_ws(monkeypatch):
    broadcasts = []

    async def _broadcast(channel, event_type, data):
        broadcasts.append((channel, event_type, data))

    monkeypatch.setattr(
        "core.websockets.manager",
        SimpleNamespace(broadcast_event=_broadcast))
    return broadcasts


class TestProviderRegistry:
    def test_extraction_gated_on_checker(self):
        calls = {"n": 0}

        def _extract(text):
            calls["n"] += 1
            return [("inventory_item", "12345", "stock_on_hand")]

        register_extractor("some_app", _extract)
        # extractor without checker -> nothing watchable, extractor not run
        assert extract_watchable_facts("some_app", "item_id: 12345") == []
        assert calls["n"] == 0

        async def _check(entity_id, user_id):
            return 1

        register_checker("some_app", "inventory_item", _check)
        assert extract_watchable_facts(
            "some_app", "item_id: 12345") == [
            ("inventory_item", "12345", "stock_on_hand")]

    def test_unknown_service_is_free(self):
        assert extract_watchable_facts("gmail", "anything at all") == []


class TestWatchService:
    async def test_register_and_dedupe(self, service):
        async def _check(entity_id, user_id):
            return 1

        register_checker("app", "entity", _check)
        assert await service.register(
            "app", "entity", "e1", "field_name", canvas_id="c1",
            user_id="u1", current_value=5) is True
        # re-registration is NOT a duplicate: explicit bindings update to
        # the latest grounding context, omitted ones keep the old values
        assert await service.register(
            "app", "entity", "e1", "field_name", canvas_id="c2") is False
        watch = service.watches()[0]
        assert watch.canvas_id == "c2"  # latest grounding wins
        assert watch.user_id == "u1"    # omitted -> kept
        assert watch.last_value == 5    # kept: no self-notification on re-grounding

    async def test_register_rejected_without_checker(self, service):
        assert await service.register(
            "no_provider", "entity", "e1", "f") is False
        assert service.watches() == []

    async def test_poll_detects_change_and_fires_once(self, service, fake_db, fake_ws):
        current = {"stock": 1}

        async def _check(entity_id, user_id):
            return current["stock"]

        register_checker("app", "entity", _check)
        await service.register("app", "entity", "e1", "f",
                               user_id="u1", canvas_id="c1",
                               current_value=1)

        current["stock"] = 0  # sold
        events = await service.poll_once()
        assert len(events) == 1
        assert events[0].old_value == 1 and events[0].new_value == 0
        # websocket to the owning user + persisted audit row for the canvas
        assert fake_ws and fake_ws[0][0] == "user:u1"
        assert fake_ws[0][1] == "fact_watch_alert"
        assert fake_ws[0][2]["new_value"] == 0
        assert len(fake_db) == 1

        # unchanged value -> no repeat event, no duplicate notification
        assert await service.poll_once() == []
        assert len(fake_db) == 1

    async def test_reversal_also_notifies(self, service, fake_db, fake_ws):
        current = {"stock": 0}

        async def _check(entity_id, user_id):
            return current["stock"]

        register_checker("app", "entity", _check)
        await service.register("app", "entity", "e1", "f",
                               user_id="u1", current_value=0)
        current["stock"] = 2  # restocked
        events = await service.poll_once()
        assert events[0].new_value == 2

    async def test_failing_checker_skips_tick(self, service):
        async def _check(entity_id, user_id):
            raise RuntimeError("provider down")

        register_checker("app", "entity", _check)
        await service.register("app", "entity", "e1", "f", current_value=1)
        assert await service.poll_once() == []

    async def test_empty_registry_polls_to_nothing(self, service):
        assert await service.poll_once() == []


class TestZohoProvider:
    def test_provider_registration(self):
        import integrations.fact_watch_providers  # noqa: F401 — registers on import
        assert ("zoho_inventory", "inventory_item") in CHECKERS
        assert "zoho_inventory" in EXTRACTORS

    def test_extractor_reads_real_evidence_block(self):
        import integrations.fact_watch_providers  # noqa: F401
        # the actual shape chat_tool_planner renders for slim items
        block = (
            "LIVE TOOL RESULTS (zoho_inventory.search_items, "
            "query='wg-350dsav') — use these to answer:\n"
            "[{'item_id': '13244000000888499', 'name': 'WG-350DSAV', "
            "'sku': '', 'stock_on_hand': 1.0, 'available_stock': 1.0}, "
            "{'item_id': '13244000000900469', 'name': 'WG-350DSAV-1', "
            "'stock_on_hand': 0.0}]")
        facts = extract_watchable_facts("zoho_inventory", block)
        assert ("inventory_item", "13244000000888499", "stock_on_hand") in facts
        assert ("inventory_item", "13244000000900469", "stock_on_hand") in facts
        # deduped
        assert len(facts) == 2

    async def test_checker_uses_check_stock(self, monkeypatch):
        import integrations.fact_watch_providers  # noqa: F401
        seen = {}

        async def _fake_check_stock(self, item_id, token=None,
                                    organization_id=None, user_id=None):
            seen["item_id"] = item_id
            seen["user_id"] = user_id
            return {"item_id": item_id, "name": "WG-350DSAV",
                    "stock_on_hand": 1.0, "available_stock": 1.0}

        monkeypatch.setattr(
            "integrations.zoho_inventory_service.ZohoInventoryService.check_stock",
            _fake_check_stock)
        checker = CHECKERS[("zoho_inventory", "inventory_item")]
        assert await checker("13244000000888499", "user-9") == 1.0
        assert seen["item_id"] == "13244000000888499"
        assert seen["user_id"] == "user-9"

    async def test_checker_maps_error_to_none(self, monkeypatch):
        import integrations.fact_watch_providers  # noqa: F401

        async def _fake_check_stock(self, item_id, **kw):
            return {"error": "Failed to check stock"}

        monkeypatch.setattr(
            "integrations.zoho_inventory_service.ZohoInventoryService.check_stock",
            _fake_check_stock)
        checker = CHECKERS[("zoho_inventory", "inventory_item")]
        assert await checker("1", None) is None


class TestRegisterFromTrace:
    async def test_trace_registration_creates_watches(self):
        # zoho provider bindings are live (module import at file top via
        # the provider tests); the global-style service gets a real watch
        import integrations.fact_watch_providers  # noqa: F401
        service = FactWatchService()
        created = await service.register_from_trace(
            {"service": "zoho_inventory",
             "block": "[{'item_id': '999', 'name': 'X', 'stock_on_hand': 3}]"},
            canvas_id="c1", user_id="u1")
        assert created == 1
        watch = service.watches()[0]
        assert watch.entity_id == "999"
        assert watch.canvas_id == "c1"

    async def test_trace_without_watchable_service_is_noop(self):
        service = FactWatchService()
        assert await service.register_from_trace(
            {"service": "gmail", "block": "some mail"}) == 0
        assert await service.register_from_trace(None) == 0


class TestFreshDataRecording:
    def _plan(self, service="zoho_inventory", query="wg-350dsav"):
        from core.chat_tool_planner import ToolPlan
        return ToolPlan(use_tool=True, service=service,
                        intent="search", query=query)

    async def test_lookup_steps_recorded(self, monkeypatch):
        import core.chat_canvas_editor as cce

        block = ("LIVE TOOL RESULTS (zoho_inventory.search_items, "
                 "query='wg-350dsav') — use these to answer:\n"
                 "[{'item_id': '42', 'name': 'WG-350DSAV', "
                 "'stock_on_hand': 1.0}]")
        monkeypatch.setattr(
            "core.chat_tool_planner.plan_tool_use",
            AsyncMock(return_value=self._plan()))
        monkeypatch.setattr(
            "core.chat_tool_planner.execute_tool_plan",
            AsyncMock(return_value=block))
        # no watchable fact side effects: registry stripped for the test
        monkeypatch.setattr(fw, "EXTRACTORS", {})

        steps = []

        async def _recorder(step_type, action, observation):
            steps.append((step_type, action, observation))

        result = await cce.fetch_fresh_data_section(
            "check if the bandsaw is in stock", [], llm_service=object(),
            user_id="u1", canvas_id="c1", step_recorder=_recorder)
        assert result.ok and "FRESH DATA" in result.section
        assert [s[0] for s in steps] == ["tool_planner", "observation"]
        assert steps[0][1]["tool"] == "zoho_inventory"
        assert steps[0][1]["params"]["query"] == "wg-350dsav"
        assert "wg-350dsav" in steps[0][2]
        assert "stock_on_hand" in steps[1][2]

    async def test_timeout_records_declined_lookup(self, monkeypatch):
        import core.chat_canvas_editor as cce

        async def _slow(*a, **k):
            await __import__("asyncio").sleep(0.5)
            return None

        monkeypatch.setattr(
            "core.chat_tool_planner.plan_tool_use", _slow)
        monkeypatch.setattr(cce, "_FRESH_DATA_TIMEOUT_SECONDS", 0.05)

        steps = []

        async def _recorder(step_type, action, observation):
            steps.append((step_type, observation))

        result = await cce.fetch_fresh_data_section(
            "check stock", [], llm_service=object(), user_id="u1",
            step_recorder=_recorder)
        assert result.needed and not result.ok
        assert steps and "timed out" in steps[0][1]

    async def test_no_recorder_still_works(self, monkeypatch):
        import core.chat_canvas_editor as cce
        monkeypatch.setattr(
            "core.chat_tool_planner.plan_tool_use",
            AsyncMock(return_value=None))
        result = await cce.fetch_fresh_data_section(
            "hello", [], llm_service=object(), user_id="u1")
        assert result.needed is False and result.ok is True
