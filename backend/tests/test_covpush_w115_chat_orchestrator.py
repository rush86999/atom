# -*- coding: utf-8 -*-
"""Coverage wave 115 — integrations/chat_orchestrator.py (51% → 95%+).

Tracked 2026-08-13: probe A (w92/w93/w97/w98/w100/w104/w105/w109 wave cluster)
found chat_orchestrator.py at 51% — the only wave-target module below 95%
(xero_service 22% is covered by w105_xero_routes only through its routes; the
service itself is a separate module, covered at 100% by tests/wave-104-xero
service suites... correction: xero_service remains below 95% and is addressed
in its own wave; this file only closes chat_orchestrator).

Wave 115 closes the remaining ~340 lines (term-missing from probe A):
- __init__ fallbacks: chat-session-manager ImportError (207-209), AI-engines
  ImportError (336-338)
- get_user_sessions both paths (224-251), _load_persisted_sessions no-manager
  early return (256) + load exception (272-273)
- _emit_agent_step success + failure (277-293)
- process_chat_message: dedup success path (379-385), LKGP sticky-hint build
  (399), first cancellation checkpoint (406), LKGP model remember (428-437),
  combined-data/suggested-actions collection (450-453), budget-failure
  precedence (462-464, 481-483), exception path incl. persist-then-return
  (490-502)
- _get_qwen_response: no-service, success, failure, exception, routing
  overrides + sticky-hint kwargs (525-587)
- _analyze_intent NLP success + exception (592-607), _classify_intent mapping
  (611-626), _fallback_intent_analysis keyword branches (630-654)
- _route_to_features handler failure log (711), ComputerUseAgent fallback
  success/tasker/exception (721-746)
- _generate_coordinated_response (759-776), _generate_main_message agent +
  all intent branches (803-852), _generate_next_steps branches (870-885)
- _handle_search_request success/exception (909-936), simple handlers
  (941/1090/1157/1326/1331/1336)
- _handle_task_request extract/empty/truncate/failure/exception (958-1019)
- _handle_workflow_request list/run/not-found/exception/help (1025-1068),
  _handle_scheduling_request (1075-1085)
- _handle_automation_request all agent keywords, missing-config, unavailable
  executor, success, exception (1107-1152)
- _handle_finance_request accounting-unavailable + 5 remaining intents
  (1172, 1196-1218), _handle_crm_request disabled/success/exception
  (1240-1265), _handle_business_health_request simulate/priorities/exception
  (1271-1321)
- _get_or_create_session ownership mismatch (1355-1356) + persist/exception
  (1367-1387), _update_session ChatSession backfill (1430-1434),
  _generate_error_response (1459)
- _handle_agent_request success/budget/exception (1475-1514),
  request_cancellation/_is_cancelled (1528, 1533-1534)

Zero LLM spend, no network, no real DB writes: every external call is mocked.
"""
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import integrations.chat_orchestrator as co


def _make_orch(**kwargs):
    orch = co.ChatOrchestrator()
    orch.ai_engines = {}
    orch.session_manager = None
    orch.conversation_sessions = {}
    orch.llm_service = None
    for k, v in kwargs.items():
        setattr(orch, k, v)
    return orch


def _intent(primary, confidence=0.8, platforms=None):
    return {
        "primary_intent": primary,
        "confidence": confidence,
        "entities": [],
        "platforms": platforms or [],
    }


class TestInitFallbacks:
    def test_session_manager_import_error(self):
        with patch(
            "core.chat_session_manager.get_chat_session_manager",
            side_effect=ImportError("no chat session manager"),
        ):
            orch = co.ChatOrchestrator()
        assert orch.session_manager is None

    def test_ai_engines_import_error(self):
        with patch.dict(sys.modules, {"ai.nlp_engine": None}):
            orch = co.ChatOrchestrator()
        assert orch.ai_engines == {}


class TestGetUserSessions:
    def test_in_memory_fallback(self):
        orch = _make_orch()
        orch.conversation_sessions = {
            "s1": {"id": "s1", "user_id": "u1", "history": []},
            "s2": {"id": "s2", "user_id": "other", "history": []},
        }
        result = orch.get_user_sessions("u1")
        assert list(result.keys()) == ["s1"]

    def test_manager_path_converts_and_caches(self):
        orch = _make_orch()
        orch.session_manager = MagicMock()
        orch.session_manager.list_user_sessions.return_value = [
            {
                "session_id": "s1",
                "user_id": "u1",
                "title": "My chat",
                "created_at": "2026-01-01",
                "last_active": "2026-01-02",
                "history": [{"message": "hi"}],
                "metadata": {"foo": "bar"},
            },
            {
                "session_id": "s2",
                "user_id": "u1",
                "title": None,
                "created_at": None,
                "last_active": None,
                "history": [],
                "metadata": {},
            },
        ]
        orch.conversation_sessions["s1"] = {"id": "s1", "user_id": "other", "history": []}
        result = orch.get_user_sessions("u1")
        assert result["s1"]["title"] == "My chat"
        assert result["s1"]["history"] == [{"message": "hi"}]
        assert result["s1"]["metadata"] == {"foo": "bar"}
        assert result["s2"]["id"] == "s2"
        # s2 was not in memory -> opportunistically cached
        assert orch.conversation_sessions["s2"]["user_id"] == "u1"
        # s1 already present -> left untouched
        assert orch.conversation_sessions["s1"]["user_id"] == "other"


class TestLoadPersistedSessions:
    def test_no_manager_early_return(self):
        orch = _make_orch()
        assert orch._load_persisted_sessions() is None

    def test_load_file_success(self):
        orch = _make_orch()
        orch.session_manager = MagicMock()
        orch.session_manager._load_sessions_file.return_value = [
            {"session_id": "s1", "user_id": "u1", "created_at": "c", "last_active": "l",
             "history": [{"message": "hi"}]},
        ]
        orch._load_persisted_sessions()
        assert orch.conversation_sessions["s1"]["history"] == [{"message": "hi"}]
        assert orch.conversation_sessions["s1"]["last_updated"] == "l"

    def test_load_file_exception(self):
        orch = _make_orch()
        orch.session_manager = MagicMock()
        orch.session_manager._load_sessions_file.side_effect = RuntimeError("disk gone")
        orch._load_persisted_sessions()
        assert orch.conversation_sessions == {}


class TestEmitAgentStep:
    async def test_success(self):
        orch = _make_orch()
        with patch("core.websockets.get_connection_manager") as gm:
            manager = gm.return_value
            manager.broadcast_event = AsyncMock()
            await orch._emit_agent_step("s1", "system_orchestrator", "exec-1", {
                "step": 2, "thought": "think", "action": "act", "output": "obs",
            })
            manager.broadcast_event.assert_awaited_once()
            kwargs = manager.broadcast_event.await_args
            assert kwargs.args[1] == "agent_step_update"
            payload = kwargs.args[2]
            assert payload["agent_id"] == "system_orchestrator"
            assert payload["execution_id"] == "exec-1"
            assert payload["session_id"] == "s1"
            # `output` from the meta-agent is normalized to `observation`
            # (with the original key kept) for the workspace UI.
            assert payload["step"]["observation"] == "obs"
            assert payload["step"]["output"] == "obs"
            assert payload["step"]["session_id"] == "s1"

    async def test_status_emit(self):
        orch = _make_orch()
        with patch("core.websockets.get_connection_manager") as gm:
            manager = gm.return_value
            manager.broadcast_event = AsyncMock()
            await orch._emit_agent_status("s1", "atom_main", "exec-1", "running")
            manager.broadcast_event.assert_awaited_once()
            kwargs = manager.broadcast_event.await_args
            assert kwargs.args[1] == "agent_status_change"
            assert kwargs.args[2]["status"] == "running"
            assert kwargs.args[2]["execution_id"] == "exec-1"

    async def test_failure_swallowed(self):
        orch = _make_orch()
        with patch("core.websockets.get_connection_manager",
                   side_effect=RuntimeError("ws down")):
            await orch._emit_agent_step("s1", "system_orchestrator", None, {"step": 1})
            await orch._emit_agent_status("s1", "atom_main", None, "failed")


class TestProcessChatMessage:
    async def _setup(self, orch, sid, **overrides):
        orch.conversation_sessions[sid] = {"id": sid, "user_id": "u1", "history": []}
        orch._get_qwen_response = AsyncMock(return_value=None)
        orch._analyze_intent = AsyncMock(return_value=_intent(co.ChatIntent.SEARCH_REQUEST))
        orch._route_to_features = AsyncMock(return_value={})
        for k, v in overrides.items():
            setattr(orch, k, v)

    async def test_dedup_success_path_mutates_history(self):
        orch = _make_orch()
        sid = "w115-dedup"
        orch.conversation_sessions[sid] = {
            "id": sid, "user_id": "u1",
            "history": [{"message": "hello", "response": {"message": "hi there"}}],
        }
        orch._get_qwen_response = AsyncMock(return_value=None)
        orch._analyze_intent = AsyncMock(return_value=_intent(co.ChatIntent.SEARCH_REQUEST))
        orch._route_to_features = AsyncMock(return_value={})
        with patch("core.llm.compression.SESSION_DEDUP_ENABLED", True), \
             patch("core.llm.compression.session_dedup.get_or_create_dedup_index") as gi:
            idx = MagicMock()
            idx.deduplicate.side_effect = lambda t: (t.upper(), 0)
            gi.return_value = idx
            await orch.process_chat_message("u1", "hello", session_id=sid)
        assert orch.conversation_sessions[sid]["history"][0]["message"] == "HELLO"
        assert orch.conversation_sessions[sid]["history"][0]["response"]["message"] == "HI THERE"

    async def test_lkgp_sticky_hint_built_and_passed(self):
        orch = _make_orch()
        sid = "w115-sticky"
        orch.conversation_sessions[sid] = {
            "id": sid, "user_id": "u1", "history": [],
            "last_known_good_model": "deepseek-v4-flash",
            "last_known_good_provider": "opencode-go",
        }
        orch._get_qwen_response = AsyncMock(return_value=None)
        orch._analyze_intent = AsyncMock(return_value=_intent(co.ChatIntent.SEARCH_REQUEST))
        orch._route_to_features = AsyncMock(return_value={})
        with patch("os.getenv", return_value="true"):
            await orch.process_chat_message("u1", "hello", session_id=sid)
        orch._get_qwen_response.assert_called_once()
        assert orch._get_qwen_response.call_args.kwargs["sticky_hint"] == (
            "opencode-go", "deepseek-v4-flash",
        )

    async def test_first_cancellation_checkpoint(self):
        orch = _make_orch()
        sid = "w115-cancel-1"
        await self._setup(orch, sid)
        orch._is_cancelled = MagicMock(side_effect=[True])
        resp = await orch.process_chat_message("u1", "hello", session_id=sid)
        assert resp["cancelled"] is True
        assert resp["success"] is False

    async def test_full_flow_lkgp_remember_and_budget_failure(self):
        orch = _make_orch()
        sid = "w115-flow"
        await self._setup(orch, sid)
        orch._get_qwen_response = AsyncMock(return_value={
            "content": "Here is your answer",
            "model": "deepseek-v4-flash",
            "provider": "opencode-go",
        })
        orch._analyze_intent = AsyncMock(return_value=_intent(co.ChatIntent.SEARCH_REQUEST))
        orch._route_to_features = AsyncMock(return_value={
            co.FeatureType.SEARCH: {
                "success": True,
                "data": {"results": [1, 2]},
                "suggested_actions": ["a", "b", "c"],
            },
            co.FeatureType.AI_ANALYTICS: {
                "success": False,
                "error_code": "budget_exceeded",
                "message": "Run budget exhausted",
                "failure_reason": "monthly cap reached",
            },
        })
        resp = await orch.process_chat_message("u1", "hello", session_id=sid)
        assert resp["success"] is False
        assert resp["error_code"] == "budget_exceeded"
        assert resp["message"] == "Run budget exhausted"
        assert resp["failure_reason"] == "monthly cap reached"
        assert resp["recovery_url"] == "/settings/billing"
        assert resp["model"] == "deepseek-v4-flash"
        assert resp["provider"] == "opencode-go"
        # combined_data + suggested_actions from the successful feature
        assert resp["data"][co.FeatureType.SEARCH.value]["results"] == [1, 2]
        assert resp["suggested_actions"] == ["a", "b", "c"]
        # LKGP remember
        session = orch.conversation_sessions[sid]
        assert session["last_known_good_model"] == "deepseek-v4-flash"
        assert session["last_known_good_provider"] == "opencode-go"

    async def test_template_path_labels_model(self):
        orch = _make_orch()
        sid = "w115-template"
        await self._setup(orch, sid)
        orch._route_to_features = AsyncMock(return_value={
            co.FeatureType.SEARCH: {"success": True, "data": None},
        })
        resp = await orch.process_chat_message("u1", "hello", session_id=sid)
        assert resp["model"] == "template"
        assert resp["provider"] == "template"
        assert "searched" in resp["message"]

    async def test_exception_path_persists_then_returns_error(self):
        orch = _make_orch()
        sid = "w115-exc"
        await self._setup(orch, sid)
        orch._route_to_features = AsyncMock(side_effect=RuntimeError("boom"))
        resp = await orch.process_chat_message("u1", "hello", session_id=sid)
        assert resp["success"] is False
        assert "error processing" in resp["error"].lower()
        # user message survived into history (BUG-125)
        history = orch.conversation_sessions[sid]["history"]
        assert history[-1]["message"] == "hello"

    async def test_exception_path_update_failure_swallowed(self):
        orch = _make_orch()
        sid = "w115-exc2"
        await self._setup(orch, sid)
        orch._route_to_features = AsyncMock(side_effect=RuntimeError("boom"))
        orch._update_session = MagicMock(side_effect=RuntimeError("persist broke"))
        resp = await orch.process_chat_message("u1", "hello", session_id=sid)
        assert resp["success"] is False


class TestGetQwenResponse:
    async def test_no_llm_service_returns_none(self):
        orch = _make_orch()
        assert await orch._get_qwen_response("hi", [], None) is None

    async def test_success_with_history(self):
        orch = _make_orch()
        orch.llm_service = MagicMock()
        orch.llm_service.generate_completion = AsyncMock(return_value={
            "success": True, "content": "  Hello world  ", "model": "m1", "provider": "p1",
        })
        history = [
            {"message": "user turn", "response": {"message": "assistant turn"}},
            {"message": "another", "response": {}},
        ]
        res = await orch._get_qwen_response("final", history, None)
        # memory_context is included whenever the assembler returns a block
        # (or None) — subset-compare so an assembled block doesn't fail this.
        assert res["content"] == "Hello world"
        assert res["model"] == "m1"
        assert res["provider"] == "p1"
        assert "memory_context" in res
        messages = orch.llm_service.generate_completion.await_args.kwargs["messages"]
        roles = [m["role"] for m in messages]
        # A memory block is injected as a SECOND system message before history.
        assert roles == ["system", "system", "user", "assistant", "user", "user"]

    async def test_failure_returns_none(self):
        orch = _make_orch()
        orch.llm_service = MagicMock()
        orch.llm_service.generate_completion = AsyncMock(return_value={"success": False})
        assert await orch._get_qwen_response("hi", [], None) is None

    async def test_exception_returns_none(self):
        orch = _make_orch()
        orch.llm_service = MagicMock()
        orch.llm_service.generate_completion = AsyncMock(side_effect=RuntimeError("llm down"))
        assert await orch._get_qwen_response("hi", [], None) is None

    async def test_overrides_and_sticky_hint_forwarded(self):
        orch = _make_orch()
        orch.llm_service = MagicMock()
        orch.llm_service.generate_completion = AsyncMock(return_value={
            "success": True, "content": "ok", "model": "m", "provider": "p",
        })
        await orch._get_qwen_response(
            "hi", [], {"model": "m1", "tier": "fast", "intent": "crm"}, ("p", "m"),
        )
        kwargs = orch.llm_service.generate_completion.await_args.kwargs
        assert kwargs["model"] == "m1"
        assert kwargs["cognitive_tier"] == "fast"
        assert kwargs["intent_override"] == "crm"
        assert kwargs["sticky_hint"] == ("p", "m")
        assert kwargs["tenant_id"] == "default"


class TestAnalyzeIntent:
    async def test_nlp_success(self):
        from ai.nlp_engine import CommandType

        orch = _make_orch()
        nlp = MagicMock()
        nlp.parse_command = AsyncMock(return_value=SimpleNamespace(
            confidence=0.9, entities=["x"], platforms=["slack"], command_type=CommandType.SEARCH,
        ))
        orch.ai_engines = {"nlp": nlp}
        result = await orch._analyze_intent("find x", {})
        assert result["primary_intent"] == co.ChatIntent.SEARCH_REQUEST
        assert result["confidence"] == 0.9
        assert result["platforms"] == ["slack"]

    async def test_nlp_exception_falls_back(self):
        orch = _make_orch()
        nlp = MagicMock()
        nlp.parse_command = AsyncMock(side_effect=RuntimeError("nlp down"))
        orch.ai_engines = {"nlp": nlp}
        result = await orch._analyze_intent("find x", {})
        assert result["primary_intent"] == co.ChatIntent.SEARCH_REQUEST
        assert result["confidence"] == 0.6

    @pytest.mark.parametrize("command_type,expected", [
        ("SEARCH", co.ChatIntent.SEARCH_REQUEST),
        ("CREATE", co.ChatIntent.TASK_MANAGEMENT),
        ("UPDATE", co.ChatIntent.TASK_MANAGEMENT),
        ("SCHEDULE", co.ChatIntent.SCHEDULING),
        ("ANALYZE", co.ChatIntent.DATA_ANALYSIS),
        ("BUSINESS_HEALTH", co.ChatIntent.BUSINESS_HEALTH),
        ("TRIGGER", co.ChatIntent.AUTOMATION_TRIGGER),
        ("WORKFLOW_CREATION", co.ChatIntent.WORKFLOW_CREATION),
        ("REPORT", co.ChatIntent.SEARCH_REQUEST),
    ])
    def test_classify_intent_mapping(self, command_type, expected):
        from ai.nlp_engine import CommandType

        orch = _make_orch()
        assert orch._classify_intent(SimpleNamespace(command_type=CommandType[command_type])) == expected

    @pytest.mark.parametrize("message,expected", [
        ("find the document", co.ChatIntent.SEARCH_REQUEST),
        ("send an email to bob", co.ChatIntent.MESSAGE_SEND),
        ("add a task for tomorrow", co.ChatIntent.TASK_MANAGEMENT),
        ("automate the workflow", co.ChatIntent.WORKFLOW_CREATION),
        ("schedule a meeting", co.ChatIntent.SCHEDULING),
        ("what should i do today", co.ChatIntent.BUSINESS_HEALTH),
        ("simulate hiring impact", co.ChatIntent.BUSINESS_HEALTH),
        ("show my deal pipeline", co.ChatIntent.CRM),
        ("hello there", co.ChatIntent.SEARCH_REQUEST),
    ])
    def test_fallback_intent_branches(self, message, expected):
        orch = _make_orch()
        result = orch._fallback_intent_analysis(message)
        assert result["primary_intent"] == expected
        assert result["confidence"] == 0.6


class TestRouteToFeatures:
    async def test_handler_failure_logged_but_other_succeeds(self):
        orch = _make_orch()
        orch.feature_handlers[co.FeatureType.SEARCH] = AsyncMock(return_value={"success": False})
        orch.feature_handlers[co.FeatureType.AI_ANALYTICS] = AsyncMock(return_value={
            "success": True, "data": {"k": "v"},
        })
        with patch.object(co, "agent_service") as ag:
            ag.execute_task = AsyncMock(return_value={"id": "t", "status": "running"})
            resp = await orch._route_to_features(
                "find x", _intent(co.ChatIntent.SEARCH_REQUEST), {}, None,
            )
        assert co.FeatureType.AI_ANALYTICS in resp
        assert co.FeatureType.SEARCH not in resp
        ag.execute_task.assert_not_awaited()

    async def test_agent_fallback_success(self):
        orch = _make_orch()
        orch.feature_handlers[co.FeatureType.SEARCH] = AsyncMock(return_value={"success": False})
        orch.feature_handlers[co.FeatureType.AI_ANALYTICS] = AsyncMock(return_value={"success": False})
        with patch.object(co, "agent_service") as ag:
            ag.execute_task = AsyncMock(return_value={"id": "t1", "status": "running"})
            resp = await orch._route_to_features(
                "figure out pricing", _intent(co.ChatIntent.SEARCH_REQUEST), {}, None,
            )
        assert ag.execute_task.await_args.kwargs["mode"] == "thinker"
        assert resp[co.FeatureType.AGENT]["data"]["task_id"] == "t1"

    async def test_agent_fallback_tasker_mode(self):
        orch = _make_orch()
        orch.feature_handlers[co.FeatureType.TASKS] = AsyncMock(return_value={"success": False})
        orch.feature_handlers[co.FeatureType.AUTOMATION] = AsyncMock(return_value={"success": False})
        with patch.object(co, "agent_service") as ag:
            ag.execute_task = AsyncMock(return_value={"id": "t2", "status": "running"})
            resp = await orch._route_to_features(
                "create the todo list", _intent(co.ChatIntent.TASK_MANAGEMENT), {}, None,
            )
        assert ag.execute_task.await_args.kwargs["mode"] == "tasker"
        assert resp[co.FeatureType.AGENT]["success"] is True

    async def test_agent_fallback_exception(self):
        orch = _make_orch()
        orch.feature_handlers[co.FeatureType.SEARCH] = AsyncMock(return_value={"success": False})
        orch.feature_handlers[co.FeatureType.AI_ANALYTICS] = AsyncMock(return_value={"success": False})
        with patch.object(co, "agent_service") as ag:
            ag.execute_task = AsyncMock(side_effect=RuntimeError("agent busy"))
            resp = await orch._route_to_features(
                "figure out pricing", _intent(co.ChatIntent.SEARCH_REQUEST), {}, None,
            )
        assert co.FeatureType.AGENT not in resp

    async def test_agent_request_intent_forces_fallback(self):
        orch = _make_orch()
        orch.feature_handlers[co.FeatureType.AGENT] = AsyncMock(return_value={"success": False})
        with patch.object(co, "agent_service") as ag:
            ag.execute_task = AsyncMock(return_value={"id": "t3", "status": "running"})
            resp = await orch._route_to_features(
                "do the complex thing", _intent(co.ChatIntent.AGENT_REQUEST), {}, None,
            )
        assert resp[co.FeatureType.AGENT]["data"]["task_id"] == "t3"


class TestGenerateCoordinatedResponse:
    def test_combines_all_channels(self):
        orch = _make_orch()
        intent = _intent(co.ChatIntent.SEARCH_REQUEST)
        responses = {
            co.FeatureType.SEARCH: {
                "success": True, "data": {"results": [1]},
                "suggested_actions": ["a"], "ui_updates": [{"type": "search_results"}],
            },
            co.FeatureType.TASKS: {
                "success": True, "data": {"task": "x"},
                "suggested_actions": ["b"], "ui_updates": [{"type": "task"}],
                "requires_confirmation": True,
            },
        }
        result = orch._generate_coordinated_response("msg", intent, responses, {"id": "s1"})
        assert result["success"] is True
        assert result["session_id"] == "s1"
        assert result["data"]["search"]["results"] == [1]
        assert result["data"]["tasks"]["task"] == "x"
        assert result["suggested_actions"] == ["a", "b"]
        assert result["ui_updates"] == [{"type": "search_results"}, {"type": "task"}]
        assert result["requires_confirmation"] is True
        assert result["intent"] == "search_request"


class TestGenerateMainMessage:
    def test_agent_response_wins(self):
        orch = _make_orch()
        msg = orch._generate_main_message(
            "q", _intent(co.ChatIntent.AGENT_REQUEST),
            {co.FeatureType.AGENT: {"success": True, "message": "On it!"}},
        )
        assert msg == "On it!"

    def test_search_with_results_count(self):
        orch = _make_orch()
        msg = orch._generate_main_message(
            "find x", _intent(co.ChatIntent.SEARCH_REQUEST),
            {co.FeatureType.SEARCH: {"data": {"results": [1, 2, 3]}}},
        )
        assert msg == "I found 3 results for your search."

    def test_search_empty(self):
        orch = _make_orch()
        msg = orch._generate_main_message(
            "find x", _intent(co.ChatIntent.SEARCH_REQUEST),
            {co.FeatureType.SEARCH: {"data": None}},
        )
        assert "searched" in msg

    def test_message_send_success(self):
        orch = _make_orch()
        msg = orch._generate_main_message(
            "send email", _intent(co.ChatIntent.MESSAGE_SEND),
            {co.FeatureType.COMMUNICATION: {"success": True}},
        )
        assert msg == "Message sent successfully."

    def test_message_send_help(self):
        orch = _make_orch()
        msg = orch._generate_main_message(
            "send email", _intent(co.ChatIntent.MESSAGE_SEND),
            {co.FeatureType.COMMUNICATION: {"success": False}},
        )
        assert "help" in msg

    def test_task_success(self):
        orch = _make_orch()
        msg = orch._generate_main_message(
            "create task", _intent(co.ChatIntent.TASK_MANAGEMENT),
            {co.FeatureType.TASKS: {"success": True, "data": {"message": "Task created"}}},
        )
        assert msg == "Task created"

    def test_task_help(self):
        orch = _make_orch()
        msg = orch._generate_main_message(
            "create task", _intent(co.ChatIntent.TASK_MANAGEMENT),
            {co.FeatureType.TASKS: {"success": False}},
        )
        assert "manage those tasks" in msg

    def test_workflow_created(self):
        orch = _make_orch()
        msg = orch._generate_main_message(
            "make workflow", _intent(co.ChatIntent.WORKFLOW_CREATION),
            {co.FeatureType.WORKFLOWS: {"data": {"wf": 1}}},
        )
        assert "created successfully" in msg

    def test_workflow_help(self):
        orch = _make_orch()
        msg = orch._generate_main_message(
            "make workflow", _intent(co.ChatIntent.WORKFLOW_CREATION),
            {co.FeatureType.WORKFLOWS: {"success": False}},
        )
        assert "automation workflow" in msg

    def test_scheduling_updated(self):
        orch = _make_orch()
        msg = orch._generate_main_message(
            "schedule", _intent(co.ChatIntent.SCHEDULING),
            {co.FeatureType.SCHEDULING: {"data": {"ok": 1}}},
        )
        assert msg == "Schedule updated successfully."

    def test_scheduling_help(self):
        orch = _make_orch()
        msg = orch._generate_main_message(
            "schedule", _intent(co.ChatIntent.SCHEDULING),
            {co.FeatureType.SCHEDULING: {"success": False}},
        )
        assert "scheduling" in msg

    def test_crm_answer(self):
        orch = _make_orch()
        msg = orch._generate_main_message(
            "pipeline", _intent(co.ChatIntent.CRM),
            {co.FeatureType.CRM: {"success": True, "data": {"answer": "5 deals"}}},
        )
        assert msg == "5 deals"

    def test_crm_help(self):
        orch = _make_orch()
        msg = orch._generate_main_message(
            "pipeline", _intent(co.ChatIntent.CRM),
            {co.FeatureType.CRM: {"success": False}},
        )
        assert "CRM" in msg

    def test_business_health_message(self):
        orch = _make_orch()
        msg = orch._generate_main_message(
            "priorities", _intent(co.ChatIntent.BUSINESS_HEALTH),
            {co.FeatureType.BUSINESS_HEALTH: {"success": True, "message": "Focus on X"}},
        )
        assert msg == "Focus on X"

    def test_business_health_help(self):
        orch = _make_orch()
        msg = orch._generate_main_message(
            "priorities", _intent(co.ChatIntent.BUSINESS_HEALTH),
            {co.FeatureType.BUSINESS_HEALTH: {"success": False}},
        )
        assert "business health" in msg

    def test_default_fallback(self):
        orch = _make_orch()
        msg = orch._generate_main_message(
            "whatever", _intent(co.ChatIntent.MULTI_STEP_PROCESS), {},
        )
        assert msg == "I've processed your request across all connected platforms."


class TestGenerateNextSteps:
    @pytest.mark.parametrize("intent,expected_first", [
        (co.ChatIntent.WORKFLOW_CREATION, "Review the workflow steps"),
        (co.ChatIntent.TASK_MANAGEMENT, "Set up automatic task creation"),
        (co.ChatIntent.CRM, "View sales pipeline"),
        (co.ChatIntent.SEARCH_REQUEST, "Refine your search with more specific terms"),
    ])
    def test_branches(self, intent, expected_first):
        orch = _make_orch()
        steps = orch._generate_next_steps(_intent(intent), {})
        assert steps[0] == expected_first
        assert len(steps) == 3

    def test_general_only(self):
        orch = _make_orch()
        steps = orch._generate_next_steps(_intent(co.ChatIntent.SCHEDULING), {})
        assert len(steps) == 3
        assert steps == [
            "Ask me to connect more services",
            "Explore automation opportunities",
            "Check your dashboard for insights",
        ]


class TestSearchHandler:
    async def test_success_with_data_intelligence(self):
        orch = _make_orch()
        orch.ai_engines = {"data_intelligence": MagicMock()}
        orch.ai_engines["data_intelligence"].search_unified_entities.return_value = ["r1", "r2"]
        result = await orch._handle_search_request(
            "find leads", _intent(co.ChatIntent.SEARCH_REQUEST, platforms=["slack"]), {}, None,
        )
        assert result["success"] is True
        assert result["data"]["results"] == ["r1", "r2"]
        assert result["data"]["platforms_searched"] == ["slack"]
        assert result["ui_updates"] == [{"type": "search_results", "data": ["r1", "r2"]}]

    async def test_success_without_engine(self):
        orch = _make_orch()
        result = await orch._handle_search_request(
            "find leads", _intent(co.ChatIntent.SEARCH_REQUEST), {}, None,
        )
        assert result["success"] is True
        assert result["data"]["results"] == []

    async def test_exception(self):
        orch = _make_orch()
        orch.ai_engines = {"data_intelligence": MagicMock()}
        orch.ai_engines["data_intelligence"].search_unified_entities.side_effect = RuntimeError("idx")
        result = await orch._handle_search_request(
            "find leads", _intent(co.ChatIntent.SEARCH_REQUEST), {}, None,
        )
        assert result == {"success": False, "error": "search_failed"}


class TestSimpleHandlers:
    @pytest.mark.parametrize("handler_name", [
        "_handle_communication_request",
        "_handle_integration_request",
        "_handle_ai_analytics_request",
        "_handle_document_request",
        "_handle_social_media_request",
        "_handle_hr_request",
        "_handle_ecommerce_request",
    ])
    async def test_returns_success(self, handler_name):
        orch = _make_orch()
        result = await getattr(orch, handler_name)("msg", {}, {}, None)
        assert result["success"] is True


class TestTaskHandler:
    async def test_extract_task_details_path(self):
        orch = _make_orch()
        orch.ai_engines = {"data_intelligence": MagicMock()}
        orch.ai_engines["data_intelligence"].extract_task_details.return_value = {
            "title": "Buy milk", "description": "2% gallon",
        }
        with patch("core.unified_task_endpoints.create_task",
                   new=AsyncMock(return_value={"success": True,
                                               "task": SimpleNamespace(id="t-9")})) as create_task:
            result = await orch._handle_task_request("buy milk", {}, {}, None)
        assert result["success"] is True
        assert result["data"]["task"]["title"] == "Buy milk"
        assert result["data"]["task"]["description"] == "2% gallon"
        create_task.assert_awaited_once()

    async def test_prefix_cleaned_and_no_colon(self):
        orch = _make_orch()
        with patch("core.unified_task_endpoints.create_task",
                   new=AsyncMock(return_value={"success": True,
                                               "task": SimpleNamespace(id="t-10")})) as create_task:
            result = await orch._handle_task_request(
                "create a reminder to call John", {}, {}, None,
            )
        assert result["success"] is True
        assert result["data"]["task"]["title"] == "Call John"
        assert result["data"]["task"]["description"] == ""
        create_task.assert_awaited_once()

    async def test_empty_clean_msg_falls_back_to_full_message(self):
        orch = _make_orch()
        with patch("core.unified_task_endpoints.create_task",
                   new=AsyncMock(return_value={"success": True,
                                               "task": SimpleNamespace(id="t-12")})) as create_task:
            result = await orch._handle_task_request("create a reminder", {}, {}, None)
        assert result["success"] is True
        assert result["data"]["task"]["title"] == "Create a reminder"
        create_task.assert_awaited_once()

    async def test_long_title_truncated(self):
        orch = _make_orch()
        long_msg = "create a task " + "x" * 60
        with patch("core.unified_task_endpoints.create_task",
                   new=AsyncMock(return_value={"success": True,
                                               "task": SimpleNamespace(id="t-11")})) as create_task:
            result = await orch._handle_task_request(long_msg, {}, {}, None)
        assert result["success"] is True
        assert result["data"]["task"]["title"].endswith("...")
        assert len(result["data"]["task"]["title"]) == 50
        create_task.assert_awaited_once()

    async def test_failure_response(self):
        orch = _make_orch()
        with patch("core.unified_task_endpoints.create_task",
                   new=AsyncMock(return_value={"success": False})):
            result = await orch._handle_task_request("create a task to ship", {}, {}, None)
        assert result["success"] is False
        assert result["error"] == "Internal task creation failed."

    async def test_exception(self):
        orch = _make_orch()
        with patch("core.unified_task_endpoints.create_task",
                   new=AsyncMock(side_effect=RuntimeError("db down"))):
            result = await orch._handle_task_request("create a task to ship", {}, {}, None)
        assert result["success"] is False
        assert result["error"] == "task_creation_failed"


class TestWorkflowHandler:
    async def test_list_empty(self):
        orch = _make_orch()
        with patch.object(co, "load_workflows", return_value=[]):
            result = await orch._handle_workflow_request("list workflows", {}, {}, None)
        assert result["success"] is True
        assert result["message"] == "No workflows found."

    async def test_list_success(self):
        orch = _make_orch()
        workflows = [{"name": "Daily Report"}, {"name": "Nightly Backup"}]
        with patch.object(co, "load_workflows", return_value=workflows):
            result = await orch._handle_workflow_request("show workflows", {}, {}, None)
        assert result["success"] is True
        assert "Daily Report" in result["message"]
        assert result["data"]["results"] == workflows
        assert result["suggested_actions"] == ["Run Daily Report", "Run Nightly Backup"]

    async def test_run_success(self):
        orch = _make_orch()
        workflows = [{"name": "Daily Report", "workflow_id": "wf-1"}]
        engine = MagicMock()
        engine.execute_workflow_definition = AsyncMock()
        with patch.object(co, "load_workflows", return_value=workflows), \
             patch.object(co, "AutomationEngine", return_value=engine):
            result = await orch._handle_workflow_request("run daily report", {}, {}, None)
        assert result["success"] is True
        assert "started" in result["message"]
        engine.execute_workflow_definition.assert_awaited_once()

    async def test_run_execution_exception(self):
        orch = _make_orch()
        workflows = [{"name": "Daily Report", "workflow_id": "wf-1"}]
        engine = MagicMock()
        engine.execute_workflow_definition = AsyncMock(side_effect=RuntimeError("exec failed"))
        with patch.object(co, "load_workflows", return_value=workflows), \
             patch.object(co, "AutomationEngine", return_value=engine):
            result = await orch._handle_workflow_request("run daily report", {}, {}, None)
        assert result["success"] is False
        assert "Failed to run workflow" in result["message"]

    async def test_run_not_found(self):
        orch = _make_orch()
        workflows = [{"name": "Daily Report", "workflow_id": "wf-1"}]
        with patch.object(co, "load_workflows", return_value=workflows):
            result = await orch._handle_workflow_request("run payroll", {}, {}, None)
        assert result["success"] is False
        assert "not found" in result["message"]

    async def test_help_message(self):
        orch = _make_orch()
        result = await orch._handle_workflow_request("what can you do", {}, {}, None)
        assert result["success"] is True
        assert "list or run" in result["message"]


class TestSchedulingHandler:
    async def test_schedule_keyword(self):
        orch = _make_orch()
        result = await orch._handle_scheduling_request("schedule the daily report", {}, {}, None)
        assert result["success"] is True
        assert "Please specify the workflow and time" in result["message"]

    async def test_default(self):
        orch = _make_orch()
        result = await orch._handle_scheduling_request("hello", {}, {}, None)
        assert result["success"] is True
        assert "Scheduling logic" in result["data"]["message"]


class TestAutomationHandler:
    @pytest.mark.parametrize("message,agent_id,name", [
        ("check competitor prices", "competitive_intel", "Competitive Intelligence Agent"),
        ("run inventory stock check", "inventory_reconcile", "Inventory Reconciliation Agent"),
        ("run payroll check", "payroll_guardian", "Payroll Guardian Agent"),
    ])
    async def test_agent_keywords_success(self, message, agent_id, name):
        orch = _make_orch()
        with patch.object(co, "execute_agent_task", new=AsyncMock()) as exec_task:
            result = await orch._handle_automation_request(message, {}, {"id": "s1"}, None)
        assert result["success"] is True
        assert result["data"]["agent_id"] == agent_id
        assert name in result["message"]
        exec_task.assert_awaited_once_with(agent_id, {
            "trigger": "chat_user", "session_id": "s1", "request": message,
        })

    async def test_missing_config_not_found(self):
        orch = _make_orch()
        with patch.object(co, "AGENTS", {}), \
             patch.object(co, "execute_agent_task", new=AsyncMock()):
            result = await orch._handle_automation_request(
                "check competitor prices", {}, {}, None,
            )
        assert result["success"] is False
        assert "not found" in result["message"]

    async def test_executor_unavailable(self):
        orch = _make_orch()
        with patch.object(co, "execute_agent_task", None):
            result = await orch._handle_automation_request(
                "check competitor prices", {}, {}, None,
            )
        assert result["success"] is False
        assert result["message"] == "Agent execution is not available."

    async def test_executor_exception(self):
        orch = _make_orch()
        with patch.object(co, "execute_agent_task",
                          new=AsyncMock(side_effect=RuntimeError("exec down"))):
            result = await orch._handle_automation_request(
                "check competitor prices", {}, {}, None,
            )
        assert result["success"] is False
        assert result["error"] == "agent_start_failed"


class TestFinanceHandler:
    async def test_accounting_services_unavailable(self):
        orch = _make_orch()
        with patch.object(co, "get_automation_settings",
                          return_value=SimpleNamespace(is_accounting_enabled=lambda: True)), \
             patch.object(co, "AccountingAssistant", None):
            result = await orch._handle_finance_request("p&l", {}, {}, None)
        assert result["success"] is False
        assert "not available" in result["message"]

    async def test_check_close_readiness(self):
        orch = _make_orch()
        db = MagicMock()
        with patch.object(co, "get_automation_settings",
                          return_value=SimpleNamespace(is_accounting_enabled=lambda: True)), \
             patch.object(co, "SessionLocal", return_value=db), \
             patch.object(co, "AccountingAssistant") as AA, \
             patch.object(co, "CloseChecklistAgent") as CCA:
            AA.return_value.process_query = AsyncMock(return_value={
                "intent": "check_close_readiness", "params": {"period": "2026-08"},
            })
            CCA.return_value.run_close_check = AsyncMock(return_value=[{"item": "recon"}])
            result = await orch._handle_finance_request(
                "close readiness", {}, {"workspace_id": "ws-1"}, None,
            )
        assert result["success"] is True
        assert "2026-08" in result["data"]["answer"]
        assert result["data"]["close_check"] == [{"item": "recon"}]
        assert "Disclaimer" in result["data"]["answer"]
        db.close.assert_called_once()

    async def test_get_tax_estimate(self):
        orch = _make_orch()
        db = MagicMock()
        with patch.object(co, "get_automation_settings",
                          return_value=SimpleNamespace(is_accounting_enabled=lambda: True)), \
             patch.object(co, "SessionLocal", return_value=db), \
             patch.object(co, "AccountingAssistant") as AA, \
             patch.object(co, "TaxService") as TS:
            AA.return_value.process_query = AsyncMock(return_value={"intent": "get_tax_estimate"})
            TS.return_value.estimate_tax_liability = MagicMock(return_value=1234.5)
            result = await orch._handle_finance_request(
                "tax estimate", {}, {"workspace_id": "ws-1"}, None,
            )
        assert result["success"] is True
        assert result["data"]["tax_estimate"] == 1234.5
        assert "tax liability" in result["data"]["answer"]

    async def test_get_cash_forecast(self):
        orch = _make_orch()
        db = MagicMock()
        with patch.object(co, "get_automation_settings",
                          return_value=SimpleNamespace(is_accounting_enabled=lambda: True)), \
             patch.object(co, "SessionLocal", return_value=db), \
             patch.object(co, "AccountingAssistant") as AA, \
             patch.object(co, "FPAService") as FPA:
            AA.return_value.process_query = AsyncMock(return_value={"intent": "get_cash_forecast"})
            FPA.return_value.get_13_week_forecast = MagicMock(return_value={"weeks": 13})
            result = await orch._handle_finance_request(
                "cash forecast", {}, {"workspace_id": "ws-1"}, None,
            )
        assert result["success"] is True
        assert result["data"]["forecast"] == {"weeks": 13}
        assert "13-week" in result["data"]["answer"]

    async def test_run_scenario(self):
        orch = _make_orch()
        db = MagicMock()
        with patch.object(co, "get_automation_settings",
                          return_value=SimpleNamespace(is_accounting_enabled=lambda: True)), \
             patch.object(co, "SessionLocal", return_value=db), \
             patch.object(co, "AccountingAssistant") as AA, \
             patch.object(co, "FPAService") as FPA:
            AA.return_value.process_query = AsyncMock(return_value={
                "intent": "run_scenario", "params": {"scenarios": ["s1"]},
            })
            FPA.return_value.run_scenario = MagicMock(return_value={"outcome": "ok"})
            result = await orch._handle_finance_request(
                "run scenario", {}, {"workspace_id": "ws-1"}, None,
            )
        assert result["success"] is True
        assert result["data"]["scenario_results"] == {"outcome": "ok"}
        assert "scenario" in result["data"]["answer"].lower()

    async def test_get_intercompany_report(self):
        orch = _make_orch()
        db = MagicMock()
        with patch.object(co, "get_automation_settings",
                          return_value=SimpleNamespace(is_accounting_enabled=lambda: True)), \
             patch.object(co, "SessionLocal", return_value=db), \
             patch.object(co, "AccountingAssistant") as AA, \
             patch.object(co, "IntercompanyManager") as ICM:
            AA.return_value.process_query = AsyncMock(
                return_value={"intent": "get_intercompany_report"})
            ICM.return_value.generate_elimination_report = MagicMock(return_value={"rows": 4})
            result = await orch._handle_finance_request(
                "intercompany report", {}, {"workspace_id": "ws-1"}, None,
            )
        assert result["success"] is True
        assert result["data"]["intercompany_report"] == {"rows": 4}
        assert "intercompany" in result["data"]["answer"].lower()


class TestCrmHandler:
    async def test_disabled(self):
        orch = _make_orch()
        with patch.object(co, "get_automation_settings",
                          return_value=SimpleNamespace(is_sales_enabled=lambda: False)):
            result = await orch._handle_crm_request("pipeline", {}, {}, None)
        assert result["success"] is False
        assert "disabled" in result["message"].lower()

    async def test_success(self):
        orch = _make_orch()
        db = MagicMock()
        fake_sales = types.ModuleType("sales.assistant")
        fake_sales.SalesAssistant = MagicMock()
        fake_sales.SalesAssistant.return_value.answer_sales_query = AsyncMock(
            return_value="The complete sales answer"
        )
        with patch.object(co, "get_automation_settings",
                          return_value=SimpleNamespace(is_sales_enabled=lambda: True)), \
             patch.object(co, "SessionLocal", return_value=db), \
             patch.dict(sys.modules, {"sales.assistant": fake_sales}):
            result = await orch._handle_crm_request(
                "pipeline", {}, {"workspace_id": "ws-1"}, None,
            )
        assert result["success"] is True
        assert result["data"]["answer"] == "The complete sales answer"
        assert result["message"] == "The complete sales answer..."
        db.close.assert_called_once()

    async def test_exception(self):
        orch = _make_orch()
        db = MagicMock()
        fake_sales = types.ModuleType("sales.assistant")
        fake_sales.SalesAssistant = MagicMock()
        fake_sales.SalesAssistant.return_value.answer_sales_query = AsyncMock(
            side_effect=RuntimeError("crm down")
        )
        with patch.object(co, "get_automation_settings",
                          return_value=SimpleNamespace(is_sales_enabled=lambda: True)), \
             patch.object(co, "SessionLocal", return_value=db), \
             patch.dict(sys.modules, {"sales.assistant": fake_sales}):
            result = await orch._handle_crm_request("pipeline", {}, {}, None)
        assert result["success"] is False
        assert result["error"] == "crm_handler_failed"
        db.close.assert_called_once()


class TestBusinessHealthHandler:
    def _patch_service(self, svc):
        fake_mod = types.ModuleType("core.business_health_service")
        fake_mod.business_health_service = svc
        return patch.dict(sys.modules, {"core.business_health_service": fake_mod})

    async def test_simulate_hiring(self):
        orch = _make_orch()
        svc = MagicMock()
        svc.simulate_decision = AsyncMock(return_value={
            "prediction": "Positive", "roi": 2.5, "breakeven": 6,
        })
        with self._patch_service(svc):
            result = await orch._handle_business_health_request(
                "what if we hire 2 engineers", {}, {"workspace_id": "ws-1"}, None,
            )
        assert result["success"] is True
        assert svc.simulate_decision.await_args.args[1] == "HIRING"
        assert "Positive" in result["message"]
        assert "2.5" in result["message"]
        assert "6" in result["message"]

    async def test_simulate_capex(self):
        orch = _make_orch()
        svc = MagicMock()
        svc.simulate_decision = AsyncMock(return_value={"prediction": "Ok"})
        with self._patch_service(svc):
            await orch._handle_business_health_request(
                "simulate spend 10k on servers", {}, {"workspace_id": "ws-1"}, None,
            )
        assert svc.simulate_decision.await_args.args[1] == "CAPEX"

    async def test_simulate_general(self):
        orch = _make_orch()
        svc = MagicMock()
        svc.simulate_decision = AsyncMock(return_value={"prediction": "Ok"})
        with self._patch_service(svc):
            result = await orch._handle_business_health_request(
                "what is the impact of opening a new office", {}, {"workspace_id": "ws-1"}, None,
            )
        assert result["success"] is True
        assert svc.simulate_decision.await_args.args[1] == "GENERAL"

    async def test_priorities(self):
        orch = _make_orch()
        svc = MagicMock()
        svc.get_daily_priorities = AsyncMock(return_value={
            "priorities": [{"priority": "High", "title": "Follow up", "description": "Call Bob"}],
            "owner_advice": "Focus on cash",
        })
        with self._patch_service(svc):
            result = await orch._handle_business_health_request(
                "what should i do today", {}, {"workspace_id": "ws-1"}, None,
            )
        assert result["success"] is True
        assert "Daily Strategy Insight" in result["message"]
        assert "Follow up" in result["message"]

    async def test_priorities_empty(self):
        orch = _make_orch()
        svc = MagicMock()
        svc.get_daily_priorities = AsyncMock(return_value={"priorities": [], "owner_advice": ""})
        with self._patch_service(svc):
            result = await orch._handle_business_health_request(
                "what should i do today", {}, {"workspace_id": "ws-1"}, None,
            )
        assert result["success"] is True
        assert "No urgent actions identified" in result["message"]

    async def test_exception(self):
        orch = _make_orch()
        svc = MagicMock()
        svc.get_daily_priorities = AsyncMock(side_effect=RuntimeError("bh down"))
        with self._patch_service(svc):
            result = await orch._handle_business_health_request(
                "what should i do today", {}, {"workspace_id": "ws-1"}, None,
            )
        assert result == {"success": False, "error": "business_health_failed"}


class TestGetOrCreateSession:
    def test_ownership_mismatch_creates_fresh(self):
        orch = _make_orch()
        orch.conversation_sessions["s1"] = {"id": "s1", "user_id": "other", "history": []}
        session = orch._get_or_create_session("u1", "s1", {"channel_id": "ch-1"})
        assert session["id"] != "s1"
        assert session["user_id"] == "u1"
        assert session["channel_id"] == "ch-1"
        assert orch.conversation_sessions["s1"]["user_id"] == "other"

    def test_existing_same_user_returned(self):
        orch = _make_orch()
        orch.conversation_sessions["s1"] = {"id": "s1", "user_id": "u1", "history": []}
        session = orch._get_or_create_session("u1", "s1")
        assert session["id"] == "s1"

    def test_new_session_persisted(self):
        orch = _make_orch()
        orch.session_manager = MagicMock()
        session = orch._get_or_create_session(
            "u1", "new-s", {"channel_id": "ch-1", "thread_id": "th-1"},
        )
        assert session["channel_id"] == "ch-1"
        assert session["thread_id"] == "th-1"
        orch.session_manager.create_session.assert_called_once_with(
            user_id="u1", session_id="new-s", channel_id="ch-1", thread_id="th-1",
        )

    def test_new_session_persist_exception_swallowed(self):
        orch = _make_orch()
        orch.session_manager = MagicMock()
        orch.session_manager.create_session.side_effect = RuntimeError("db busy")
        session = orch._get_or_create_session("u1", "new-s", None)
        assert session["id"] == "new-s"


class TestUpdateSession:
    def test_chat_session_backfill_and_messages(self):
        orch = _make_orch()
        db = MagicMock()
        session_row = MagicMock()
        session_row.channel_id = None
        session_row.thread_id = None
        db.query.return_value.filter.return_value.first.return_value = session_row
        cm = MagicMock()
        cm.__enter__.return_value = db
        with patch("core.database.get_db_session", return_value=cm):
            orch._update_session(
                {"id": "s1", "channel_id": "ch-1", "thread_id": "th-1", "history": []},
                "user msg", {"message": "assistant msg"}, {"primary_intent": co.ChatIntent.SEARCH_REQUEST},
            )
        assert session_row.channel_id == "ch-1"
        assert session_row.thread_id == "th-1"
        assert db.add.call_count == 2

    def test_append_history_and_response_string(self):
        orch = _make_orch()
        session = {"id": "s2", "history": []}
        orch._update_session(session, "hello", "plain string response", {})
        assert session["history"][0]["message"] == "hello"
        assert session["history"][0]["response"] == "plain string response"


class TestAgentRequestHandler:
    def _fake_atom(self, execute_return):
        fake = types.ModuleType("core.atom_meta_agent")
        fake.AgentTriggerMode = SimpleNamespace(MANUAL="manual")
        fake.get_atom_agent = MagicMock()
        fake.get_atom_agent.return_value.execute = AsyncMock(return_value=execute_return)
        return fake

    async def test_success(self):
        orch = _make_orch()
        orch._emit_agent_step = AsyncMock()
        orch._emit_agent_status = AsyncMock()
        fake = self._fake_atom({
            "final_output": "Done!", "actions_executed": [{"a": 1}], "spawned_agent": None,
            "execution_id": "exec-9",
        })
        with patch.dict(sys.modules, {"core.atom_meta_agent": fake}):
            result = await orch._handle_agent_request(
                "research competitors", _intent(co.ChatIntent.AGENT_REQUEST),
                {"id": "s1", "user_id": "u1"}, {"extra": 1},
            )
        assert result["status"] == "success"
        assert result["success"] is True
        assert result["message"] == "Done!"
        assert result["actions_taken"] == [{"a": 1}]
        assert result["feature"] == "agent"
        execute = fake.get_atom_agent.return_value.execute
        assert execute.await_args.kwargs["trigger_mode"] == "manual"
        assert execute.await_args.kwargs["context"]["user_id"] == "u1"
        assert execute.await_args.kwargs["context"]["extra"] == 1
        # Live trace: a step_callback is wired and the run is bracketed by
        # running → success lifecycle broadcasts.
        assert callable(execute.await_args.kwargs["step_callback"])
        statuses = [c.args[3] for c in orch._emit_agent_status.await_args_list]
        assert statuses == ["running", "success"]
        assert orch._emit_agent_status.await_args_list[-1].args[2] == "exec-9"

    async def test_step_callback_streams_normalized_steps(self):
        orch = _make_orch()
        orch._emit_agent_step = AsyncMock()
        orch._emit_agent_status = AsyncMock()
        captured = {}

        async def execute_side_effect(**kwargs):
            captured["callback"] = kwargs["step_callback"]
            await kwargs["step_callback"]({
                "step": 1, "thought": "t", "action": "a",
                "output": "o", "execution_id": "exec-7",
            })
            return {"final_output": "ok", "execution_id": "exec-7"}

        fake = self._fake_atom(None)
        fake.get_atom_agent.return_value.execute = AsyncMock(side_effect=execute_side_effect)
        with patch.dict(sys.modules, {"core.atom_meta_agent": fake}):
            await orch._handle_agent_request(
                "do a thing", _intent(co.ChatIntent.AGENT_REQUEST),
                {"id": "s1", "user_id": "u1"}, None,
            )
        orch._emit_agent_step.assert_awaited_once_with("s1", "atom_main", "exec-7", {
            "step": 1, "thought": "t", "action": "a",
            "output": "o", "execution_id": "exec-7",
        })

    async def test_budget_failure_propagated(self):
        orch = _make_orch()
        orch._emit_agent_step = AsyncMock()
        orch._emit_agent_status = AsyncMock()
        fake = self._fake_atom({"final_output": None, "failure_reason": "cost cap", "execution_id": "exec-2"})
        with patch.dict(sys.modules, {"core.atom_meta_agent": fake}):
            result = await orch._handle_agent_request(
                "big job", _intent(co.ChatIntent.AGENT_REQUEST), {"id": "s1"}, None,
            )
        assert result["status"] == "budget_exceeded"
        assert result["success"] is False
        assert result["error_code"] == "budget_exceeded"
        assert result["failure_reason"] == "cost cap"
        statuses = [c.args[3] for c in orch._emit_agent_status.await_args_list]
        assert statuses == ["running", "failed"]

    async def test_exception(self):
        orch = _make_orch()
        orch._emit_agent_step = AsyncMock()
        orch._emit_agent_status = AsyncMock()
        fake = types.ModuleType("core.atom_meta_agent")
        fake.AgentTriggerMode = SimpleNamespace(MANUAL="manual")
        fake.get_atom_agent = MagicMock(side_effect=RuntimeError("atom down"))
        with patch.dict(sys.modules, {"core.atom_meta_agent": fake}):
            result = await orch._handle_agent_request(
                "big job", _intent(co.ChatIntent.AGENT_REQUEST), {"id": "s1"}, None,
            )
        assert result["status"] == "error"
        assert result["error"] == "agent_request_failed"
        # get_atom_agent() itself raised before the running broadcast, so only
        # the terminal failed status is emitted from the except path.
        statuses = [c.args[3] for c in orch._emit_agent_status.await_args_list]
        assert statuses == ["failed"]


class TestCancellation:
    def test_request_cancellation_and_consume(self):
        orch = _make_orch()
        orch.request_cancellation("s1")
        assert orch._is_cancelled("s1") is True
        assert orch._is_cancelled("s1") is False
        assert orch._is_cancelled("other") is False
