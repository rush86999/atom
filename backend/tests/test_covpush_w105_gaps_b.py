# -*- coding: utf-8 -*-
"""Coverage wave 105 — remaining long-tail gaps, batch B (verified first).

Real gaps (everything else in the wave-105 list is already >=95%):
1.  core/canvas_sheets_service.py       — 48% -> target >=95%
2.  core/canvas_coding_service.py       — 71% -> target >=95%
3.  core/canvas_terminal_service.py     — 57% -> target >=95%
4.  integrations/universal_webhook_bridge.py — 68% -> target >=95%
5.  core/governance/policy_engine.py    — 69% -> target >=95%
6.  core/mcp_server/tools.py            — 33% -> target >=95%
7.  core/reasoning_chain.py             — 44% -> target >=95%

No network, no real database, no real models. Plain pytest + unittest.mock.
"""
import asyncio
import os
import sys
import types
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import core.agent_integration_gateway  # noqa: F401  (pre-import patch target)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _fake_audit_db(first_audit=None):
    """Session mock whose query(CanvasAudit).filter(...).order_by(...).first()
    returns ``first_audit`` (or None)."""
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = first_audit
    return db


def _audit(details):
    return SimpleNamespace(details_json=details)


# =========================================================================== #
# 1. core/canvas_sheets_service.py
# =========================================================================== #
class TestCanvasSheetsService:
    def _svc(self, db):
        from core.canvas_sheets_service import SpreadsheetCanvasService
        return SpreadsheetCanvasService(db)

    def test_dataclasses(self):
        from core.canvas_sheets_service import SpreadsheetCell, SpreadsheetChart
        cell = SpreadsheetCell("A1", 1, "number", "=SUM(A1)", {"bold": True})
        assert cell.cell_ref == "A1" and cell.formatting == {"bold": True}
        chart = SpreadsheetChart("c1", "bar", "A1:B2", "T")
        assert chart.position == {"row": 0, "col": 0}

    def test_create_success_and_failure(self):
        db = MagicMock()
        svc = self._svc(db)
        res = svc.create_spreadsheet_canvas(
            "u1", "Sheet", {"A1": 1, "B1": "=SUM(A1)"}, formulas=["B1"],
            canvas_id="cid", agent_id="a1", layout="grid")
        assert res["success"] is True
        assert res["cells"]["B1"]["cell_type"] == "formula"
        assert res["cells"]["A1"]["cell_type"] == "text"
        db.add.assert_called_once()
        db.commit.assert_called_once()

        db2 = MagicMock()
        db2.commit.side_effect = RuntimeError("boom")
        res2 = self._svc(db2).create_spreadsheet_canvas("u1", "S", {})
        assert res2["success"] is False and "boom" in res2["error"]
        db2.rollback.assert_called_once()

    def test_update_cell_paths(self):
        # not found
        svc = self._svc(_fake_audit_db(None))
        assert svc.update_cell("c", "u", "A1", 5)["error"] == "Spreadsheet not found"

        # success
        db = _fake_audit_db(_audit({"cells": {"A1": {"value": 1}}}))
        res = self._svc(db).update_cell("c", "u", "A1", 9, "number", "=1+8")
        assert res["success"] is True and res["value"] == 9
        db.add.assert_called_once()

        # exception
        dbx = _fake_audit_db(_audit({"cells": {}}))
        dbx.commit.side_effect = RuntimeError("db down")
        res2 = self._svc(dbx).update_cell("c", "u", "A1", 9)
        assert res2["success"] is False

    def test_update_cell_transactional_commit_and_rollback(self):
        from core.canvas_sheets_service import SpreadsheetCanvasService

        with patch.object(SpreadsheetCanvasService, "update_cell",
                          return_value={"success": True}) as up:
            db = MagicMock()
            res = SpreadsheetCanvasService(db).update_cell_transactional(
                "c", "u", "A1", 42)
            assert res["success"] is True
            up.assert_called_once_with("c", "u", "A1", 42, "text", None)

        with patch.object(SpreadsheetCanvasService, "update_cell") as up:
            db = MagicMock()
            with pytest.raises(ValueError):
                SpreadsheetCanvasService(db).update_cell_transactional(
                    "c", "u", "A1", 42, should_fail=True)
            up.assert_not_called()

    def test_add_chart_and_pivot(self):
        svc = self._svc(_fake_audit_db(None))
        assert svc.add_chart("c", "u", "line", "A1:B2")["error"] == "Spreadsheet not found"
        assert svc.add_pivot_table("c", "u", "s", "p", "A1:C9", ["r"], ["c"], [{"f": "sum"}])["error"] == "Spreadsheet not found"

        db = _fake_audit_db(_audit({"charts": [], "pivot_tables": []}))
        res = self._svc(db).add_chart("c", "u", "bar", "A1:B2", "Sales")
        assert res["success"] is True and res["chart_id"]

        db2 = _fake_audit_db(_audit({"pivot_tables": []}))
        res2 = self._svc(db2).add_pivot_table(
            "c", "u", "data", "pivot", "A1:C9", ["region"], ["qtr"], [{"field": "sales"}])
        assert res2["success"] is True and res2["pivot_id"]

        # exception paths
        dbx = _fake_audit_db(_audit({"charts": []}))
        dbx.commit.side_effect = RuntimeError("x")
        assert self._svc(dbx).add_chart("c", "u", "bar", "A1")["success"] is False
        dby = _fake_audit_db(_audit({"pivot_tables": []}))
        dby.commit.side_effect = RuntimeError("x")
        assert self._svc(dby).add_pivot_table("c", "u", "s", "p", "A1", [], [], [])["success"] is False


# =========================================================================== #
# 2. core/canvas_coding_service.py
# =========================================================================== #
class TestCanvasCodingService:
    def _svc(self, db):
        from core.canvas_coding_service import CodingCanvasService
        return CodingCanvasService(db)

    def test_dataclasses(self):
        from core.canvas_coding_service import CodeFile, DiffHunk, PullRequestReview
        f = CodeFile("f1", "a.py", "print()", "python", "added")
        assert (f.path, f.status) == ("a.py", "added")
        d = DiffHunk("h1", 1, ["a"], 2, ["b"])
        assert d.new_lines == ["b"]
        pr = PullRequestReview("r1", 7, "T", "D", "merged")
        assert pr.status == "merged"

    def test_create_success_and_failure(self):
        db = MagicMock()
        res = self._svc(db).create_coding_canvas(
            "u1", "atom/backend", "main", canvas_id="cid", agent_id="a1")
        assert res["success"] is True and res["repo"] == "atom/backend"
        db.add.assert_called_once()

        db2 = MagicMock()
        db2.commit.side_effect = RuntimeError("boom")
        res2 = self._svc(db2).create_coding_canvas("u1", "r", "b")
        assert res2["success"] is False and "boom" in res2["error"]
        db2.rollback.assert_called_once()

    def test_add_file(self):
        assert self._svc(_fake_audit_db(None)).add_file("c", "u", "x.py", "code")["error"] == "Coding canvas not found"

        db = _fake_audit_db(_audit({"files": []}))
        res = self._svc(db).add_file("c", "u", "main.py", "print()", "python")
        assert res["success"] is True and res["file_id"]
        db.add.assert_called_once()

        dbx = _fake_audit_db(_audit({"files": []}))
        dbx.commit.side_effect = RuntimeError("x")
        assert self._svc(dbx).add_file("c", "u", "m.py", "")["success"] is False

    def test_add_diff(self):
        assert self._svc(_fake_audit_db(None)).add_diff("c", "u", "f", "a", "b")["error"] == "Coding canvas not found"

        db = _fake_audit_db(_audit({"diffs": []}))
        res = self._svc(db).add_diff("c", "u", "f.py", "old", "new")
        assert res["success"] is True and res["diff_id"]

        dbx = _fake_audit_db(_audit({"diffs": []}))
        dbx.commit.side_effect = RuntimeError("x")
        assert self._svc(dbx).add_diff("c", "u", "f.py", "a", "b")["success"] is False


# =========================================================================== #
# 3. core/canvas_terminal_service.py
# =========================================================================== #
class TestCanvasTerminalService:
    def _svc(self, db):
        from core.canvas_terminal_service import TerminalCanvasService
        return TerminalCanvasService(db)

    def test_dataclasses(self):
        from core.canvas_terminal_service import TerminalOutput, FileNode, ProcessInfo
        ts = datetime(2026, 1, 1)
        out = TerminalOutput("o1", "ls", "file", 0, ts)
        assert out.timestamp == ts
        out2 = TerminalOutput("o2", "c", "o")
        assert out2.timestamp is not None
        node = FileNode("n1", "dir", "directory", "/tmp", None, None)
        assert node.children == [] and node.size is None
        proc = ProcessInfo(1, "p", 1.5, 20.0, "root")
        assert proc.user == "root"

    def test_create_success_and_failure(self):
        db = MagicMock()
        res = self._svc(db).create_terminal_canvas(
            "u1", "npm test", canvas_id="cid", agent_id="a1", working_dir="/repo")
        assert res["success"] is True and res["working_dir"] == "/repo"
        db.add.assert_called_once()

        db2 = MagicMock()
        db2.commit.side_effect = RuntimeError("boom")
        res2 = self._svc(db2).create_terminal_canvas("u1", "ls")
        assert res2["success"] is False
        db2.rollback.assert_called_once()

    def test_add_output(self):
        assert self._svc(_fake_audit_db(None)).add_output("c", "u", "ls", "out")["error"] == "Terminal canvas not found"

        db = _fake_audit_db(_audit({"outputs": []}))
        res = self._svc(db).add_output("c", "u", "ls -la", "total 0", 0)
        assert res["success"] is True and res["output_id"]
        db.add.assert_called_once()

        dbx = _fake_audit_db(_audit({"outputs": []}))
        dbx.commit.side_effect = RuntimeError("x")
        assert self._svc(dbx).add_output("c", "u", "ls", "o")["success"] is False

    def test_update_file_tree(self):
        assert self._svc(_fake_audit_db(None)).update_file_tree("c", "u", {})["error"] == "Terminal canvas not found"

        db = _fake_audit_db(_audit({}))
        assert self._svc(db).update_file_tree("c", "u", {"name": "root"})["success"] is True

        dbx = _fake_audit_db(_audit({}))
        dbx.commit.side_effect = RuntimeError("x")
        assert self._svc(dbx).update_file_tree("c", "u", {})["success"] is False


# =========================================================================== #
# 4. integrations/universal_webhook_bridge.py
# =========================================================================== #
@pytest.mark.asyncio
class TestUniversalWebhookBridge:
    def _bridge(self):
        from integrations.universal_webhook_bridge import UniversalWebhookBridge
        return UniversalWebhookBridge()

    # -- _get_agent_id_by_name ------------------------------------------------
    async def test_agent_lookup_exact_fuzzy_template_none(self):
        b = self._bridge()

        def db_with(agent):
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = agent
            return db

        # exact match
        with patch("core.database.get_db_session",
                   return_value=_ctx(db_with(SimpleNamespace(id="agent-1")))):
            assert await b._get_agent_id_by_name("Alpha") == "agent-1"

        # fuzzy match (first query None, second hit)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [None, SimpleNamespace(id="agent-2")]
        with patch("core.database.get_db_session", return_value=_ctx(db)):
            assert await b._get_agent_id_by_name("Alp") == "agent-2"

        # template match
        db2 = MagicMock()
        db2.query.return_value.filter.return_value.first.return_value = None
        templates = {"finance_agent": {"name": "Finance Agent", "description": "d"}}
        tmpl_mod = types.SimpleNamespace(
            TEMPLATES=templates,
            SpecialtyAgentTemplate=types.SimpleNamespace(TEMPLATES=templates))
        with patch("core.database.get_db_session", return_value=_ctx(db2)), \
             patch.dict(sys.modules, {"core.atom_meta_agent": tmpl_mod}):
            assert await b._get_agent_id_by_name("finance") == "finance_agent"

        # nothing found
        db3 = MagicMock()
        db3.query.return_value.filter.return_value.first.return_value = None
        tmpl_empty = types.SimpleNamespace(
            TEMPLATES={}, SpecialtyAgentTemplate=types.SimpleNamespace(TEMPLATES={}))
        with patch("core.database.get_db_session", return_value=_ctx(db3)), \
             patch.dict(sys.modules, {"core.atom_meta_agent": tmpl_empty}):
            assert await b._get_agent_id_by_name("nope") is None

        # exception path
        with patch("core.database.get_db_session", side_effect=RuntimeError("db")):
            assert await b._get_agent_id_by_name("x") is None

    # -- _get_orchestrator ----------------------------------------------------
    async def test_get_orchestrator_success_and_failure(self):
        b = self._bridge()
        with patch("integrations.chat_orchestrator.ChatOrchestrator") as cls:
            cls.return_value = "orch"
            assert b._get_orchestrator() == "orch"
            assert b._get_orchestrator() == "orch"  # cached
            assert cls.call_count == 1

        b2 = self._bridge()
        err_mod = types.ModuleType("integrations.chat_orchestrator")
        def _boom(*a, **k):
            raise RuntimeError("no orchestrator")
        err_mod.ChatOrchestrator = _boom
        with patch.dict(sys.modules, {"integrations.chat_orchestrator": err_mod}):
            assert b2._get_orchestrator() is None

    # -- _standardize_message remaining platforms -----------------------------
    def test_standardize_platforms(self):
        b = self._bridge()

        m = b._standardize_message("discord", {"author": {"id": "1", "username": "u"}, "channel_id": "ch", "content": "hi", "id": "m1", "guild_id": "g"})
        assert m.sender_id == "1" and m.metadata["author_name"] == "u"
        assert b._standardize_message("discord", {"author": {"bot": True}}) is None

        m = b._standardize_message("teams", {"type": "message", "from": {"id": "t1"}, "channel_id": None, "conversation": {"id": "conv"}, "text": "hi", "id": "i", "channel_data": {"team": {"id": "team"}}, "tenant_id": "tn"})
        assert m.recipient_id == "conv" and m.metadata["team_id"] == "team"
        assert b._standardize_message("teams", {"type": "not_message"}) is None

        m = b._standardize_message("telegram", {"from": {"id": 42, "username": "bob"}, "chat": {"id": 99}, "text": "hi", "message_id": 5})
        assert m.sender_id == "42" and m.recipient_id == "99"
        assert b._standardize_message("telegram", {"from": {}}) is None

        m = b._standardize_message("google_chat", {"type": "MESSAGE", "sender": {"name": "users/x"}, "space": {"name": "spaces/y"}, "text": "hi", "name": "msg", "thread": {"name": "thr"}})
        assert m.recipient_id == "spaces/y" and m.metadata["thread"] == "thr"
        assert b._standardize_message("google_chat", {"type": "ADDED"}) is None

        m = b._standardize_message("twilio", {"From": "+1", "To": "+2", "Body": "hey", "MessageSid": "SM1"})
        assert m.text == "hey" and m.metadata["sms_sid"] == "SM1"

        m = b._standardize_message("matrix", {"sender": "@a:b", "room_id": "!r", "content": {"body": "yo", "msgtype": "m.text"}, "event_id": "e1"})
        assert m.text == "yo" and m.metadata["msgtype"] == "m.text"

        m = b._standardize_message("messenger", {"sender": {"id": "s"}, "recipient": {"id": "r"}, "message": {"text": "hi", "mid": "m"}})
        assert m.metadata["mid"] == "m"

        m = b._standardize_message("line", {"message": {"text": "hi", "id": "m1"}, "source": {"userId": "u", "groupId": "g"}, "replyToken": "tok"})
        assert m.recipient_id == "g" and m.metadata["replyToken"] == "tok"
        m = b._standardize_message("line", {"message": {}, "source": {"roomId": "r"}})
        assert m.recipient_id == "r"
        m = b._standardize_message("line", {"message": {}, "source": {}})
        assert m.recipient_id == "direct"

        m = b._standardize_message("signal", {"envelope": {"source": "+1", "timestamp": 1, "dataMessage": {"message": "hi"}}})
        assert m.text == "hi"
        m = b._standardize_message("signal", {"envelope": {"source": "+1", "syncMessage": {"sentMessage": {"message": "sync"}}}})
        assert m.text == "sync"
        m = b._standardize_message("signal", {"envelope": {}})
        assert m.text == ""

        m = b._standardize_message("agent", {"agent_id": "a", "target_id": "t", "message": "hi", "metadata": {"k": 1}})
        assert m.metadata == {"k": 1}

        m = b._standardize_message("openclaw", {"sender_id": "s", "recipient_id": "r", "content": "hi", "message_id": "m", "thread_ts": "t1"})
        assert m.text == "hi" and m.thread_id == "t1"
        m = b._standardize_message("openclaw", {"text": "fallback"})
        assert m.text == "fallback"

        assert b._standardize_message("unknown_platform", {}) is None

    # -- process_incoming_message ---------------------------------------------
    async def test_process_orchestrator_unavailable_and_route_failure(self):
        b = self._bridge()
        with patch.object(b, "_standardize_message", return_value=None):
            res = await b.process_incoming_message("slack", {})
            assert res["status"] == "ignored"

        msg = SimpleNamespace(
            platform="slack", sender_id="u", recipient_id="ch", text="hello",
            thread_id=None, metadata={"ts": "1"}, raw_payload={})
        with patch.object(b, "_standardize_message", return_value=msg), \
             patch.object(b, "_get_orchestrator", return_value=None):
            res = await b.process_incoming_message("slack", {})
            assert res["status"] == "error"

        orch = AsyncMock()
        orch.process_chat_message.return_value = {"message": "reply"}
        gw = AsyncMock()
        gw.execute_action.side_effect = RuntimeError("route fail")
        with patch.object(b, "_standardize_message", return_value=msg), \
             patch.object(b, "_get_orchestrator", return_value=orch), \
             patch("core.agent_integration_gateway.agent_integration_gateway", gw), \
             patch("core.agent_integration_gateway.ActionType", SimpleNamespace(SEND_MESSAGE="send"), create=True):
            res = await b.process_incoming_message("slack", {})
            assert res["status"] == "success"

        with patch.object(b, "_standardize_message", side_effect=RuntimeError("bad payload")):
            res = await b.process_incoming_message("slack", {})
            assert res["status"] == "error"

    # -- _handle_command --------------------------------------------------------
    def _msg(self, text, platform="slack"):
        from integrations.universal_webhook_bridge import UnifiedIncomingMessage
        return UnifiedIncomingMessage(
            platform=platform, sender_id="u1", recipient_id="ch1", text=text,
            thread_id=None, metadata={"ts": "42"}, raw_payload={})

    async def test_run_command_success_and_error(self):
        b = self._bridge()
        gw = AsyncMock()
        exec_task = AsyncMock()
        with patch("core.agent_integration_gateway.agent_integration_gateway", gw), \
             patch("core.agent_integration_gateway.ActionType", SimpleNamespace(SEND_MESSAGE="send"), create=True), \
             patch("api.agent_routes.execute_agent_task", exec_task), \
             patch("asyncio.create_task") as ct, \
             patch.object(b, "_get_agent_id_by_name", AsyncMock(return_value="agent-9")):
            res = await b.process_incoming_message("slack", {
                "type": "message", "user": "u", "channel": "ch",
                "text": "/run finance analyze spending", "ts": "1"})
            assert res["status"] == "command_triggered" and res["agent"] == "finance"
            ct.assert_called_once()
            gw.execute_action.assert_awaited_once()

        # lookup fails -> falls back to raw agent name; ack gateway explodes -> error
        b2 = self._bridge()
        gw2 = AsyncMock()
        gw2.execute_action.side_effect = RuntimeError("nope")
        with patch.object(b2, "_standardize_message", return_value=self._msg("/run myagent do")), \
             patch("core.agent_integration_gateway.agent_integration_gateway", gw2), \
             patch("core.agent_integration_gateway.ActionType", SimpleNamespace(SEND_MESSAGE="send"), create=True), \
             patch("asyncio.create_task"), \
             patch.object(b2, "_get_agent_id_by_name", AsyncMock(return_value=None)):
            res = await b2.process_incoming_message("slack", {})
            assert res["status"] == "error"

    async def test_run_command_no_args_falls_through(self):
        from integrations.universal_webhook_bridge import UnifiedIncomingMessage
        b = self._bridge()
        msg = UnifiedIncomingMessage(platform="slack", sender_id="u", recipient_id="c",
                                     text="/run", thread_id=None, metadata={}, raw_payload={})
        res = await b._handle_command(msg)
        assert res["status"] == "unsupported_command" and res["command"] == "run"

    async def test_workflow_command(self):
        b = self._bridge()
        gw = AsyncMock()
        orch = MagicMock()
        orch.trigger_event = AsyncMock()
        wf_mod = types.ModuleType("advanced_workflow_orchestrator")
        wf_mod.AdvancedWorkflowOrchestrator = MagicMock(return_value=orch)
        with patch.dict(sys.modules, {"advanced_workflow_orchestrator": wf_mod}), \
             patch("core.agent_integration_gateway.agent_integration_gateway", gw), \
             patch("core.agent_integration_gateway.ActionType", SimpleNamespace(SEND_MESSAGE="send"), create=True), \
             patch("asyncio.create_task") as ct:
            res = await b.process_incoming_message("slack", {
                "type": "message", "user": "u", "channel": "c",
                "text": "/workflow wf-1", "ts": "9"})
            assert res["status"] == "command_triggered" and res["workflow_id"] == "wf-1"
            ct.assert_called_once()

        # failure path
        with patch.dict(sys.modules, {"advanced_workflow_orchestrator": None}), \
             patch.object(b, "_standardize_message", return_value=self._msg("/workflow wf")), \
             patch("asyncio.create_task"):
            # import of a None module entry raises ImportError -> caught
            res2 = await b.process_incoming_message("slack", {})
            assert res2["status"] == "error"

    async def test_agents_command(self):
        b = self._bridge()
        gw = AsyncMock()
        db = MagicMock()
        agents = [SimpleNamespace(name="A", id="a1", description="d1")]
        db.query.return_value.all.return_value = agents
        templates = {"t1": {"name": "T1", "description": "td"}}
        tmpl_mod = types.SimpleNamespace(
            TEMPLATES=templates,
            SpecialtyAgentTemplate=types.SimpleNamespace(TEMPLATES=templates))
        with patch("core.database.get_db_session", return_value=_ctx(db)), \
             patch.dict(sys.modules, {"core.atom_meta_agent": tmpl_mod}), \
             patch("core.agent_integration_gateway.agent_integration_gateway", gw), \
             patch("core.agent_integration_gateway.ActionType", SimpleNamespace(SEND_MESSAGE="send"), create=True):
            res = await b.process_incoming_message("slack", {
                "type": "message", "user": "u", "channel": "c", "text": "/agents", "ts": "1"})
            assert res["status"] == "agents_listed"

        # failure path
        with patch.object(b, "_standardize_message", return_value=self._msg("/agents")), \
             patch("core.database.get_db_session", side_effect=RuntimeError("db")):
            res2 = await b.process_incoming_message("slack", {})
            assert res2["status"] == "error"

    async def test_help_and_status_commands(self):
        b = self._bridge()
        gw = AsyncMock()
        with patch("core.agent_integration_gateway.agent_integration_gateway", gw), \
             patch("core.agent_integration_gateway.ActionType", SimpleNamespace(SEND_MESSAGE="send"), create=True):
            res = await b.process_incoming_message("slack", {
                "type": "message", "user": "u", "channel": "c", "text": "/help", "ts": "1"})
            assert res["status"] == "help_sent"

            res2 = await b.process_incoming_message("whatsapp", {
                "from": "+1", "text": {"body": "/status"}, "id": "m1"})
            assert res2["status"] == "status_sent"
            assert gw.execute_action.await_count == 2

        # status failure path
        gw2 = AsyncMock()
        gw2.execute_action.side_effect = RuntimeError("nope")
        with patch.object(b, "_standardize_message", return_value=self._msg("/status")), \
             patch("core.agent_integration_gateway.agent_integration_gateway", gw2), \
             patch("core.agent_integration_gateway.ActionType", SimpleNamespace(SEND_MESSAGE="send"), create=True):
            res3 = await b.process_incoming_message("slack", {})
            assert res3["status"] == "error"

        # unsupported
        with patch.object(b, "_standardize_message", return_value=self._msg("/bogus")):
            res4 = await b.process_incoming_message("slack", {})
            assert res4["status"] == "unsupported_command"


def _ctx(db):
    """get_db_session() used as context manager wrapping db."""
    db.close = MagicMock()
    ctx = MagicMock()
    ctx.__enter__.return_value = db
    ctx.__exit__.return_value = False
    return ctx


# =========================================================================== #
# 6. core/mcp_server/tools.py
# =========================================================================== #
class TestMCPTools:
    def test_mcp_tool_to_dict(self):
        from core.mcp_server.tools import MCPTool, get_all_tools
        t = MCPTool("n", "d", {"type": "object"}, lambda a: {})
        assert t.to_dict() == {"name": "n", "description": "d", "inputSchema": {"type": "object"}}
        tools = get_all_tools()
        names = {t.name for t in tools}
        assert {"resolve_route", "list_models", "compress_text", "set_compression",
                "get_spend", "get_health", "fusion_generate"} <= names
        for t in tools:
            assert callable(t.handler)

    def test_handle_resolve_route(self):
        from core.mcp_server import tools as T
        handler = MagicMock()
        handler.analyze_query_complexity.return_value = "complex"
        handler.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4"), ("anthropic", "claude")])
        with patch("core.llm.byok_handler.BYOKHandler", return_value=handler):
            res = asyncio.run(T._handle_resolve_route({"prompt": "p", "task_type": "code"}))
        assert res["complexity"] == "complex"
        assert res["total_candidates"] == 2 and res["top_candidates"][0]["provider"] == "openai"

        with patch("core.llm.byok_handler.BYOKHandler", side_effect=RuntimeError("x")):
            res2 = asyncio.run(T._handle_resolve_route({}))
        assert "error" in res2

    def test_handle_list_models(self):
        from core.mcp_server import tools as T
        handler = MagicMock()
        handler._model_registry = {
            "m1": SimpleNamespace(provider="openai", quality_score=9, cost_per_million=1, tier="premium"),
            "m2": "garbage",  # getattr fallbacks kick in
        }
        with patch("core.llm.byok_handler.BYOKHandler", return_value=handler):
            res = asyncio.run(T._handle_list_models({}))
        assert res["total"] == 2
        by_id = {m["model_id"]: m for m in res["models"]}
        assert by_id["m2"]["provider"] == "unknown" and by_id["m2"]["tier"] == "standard"

        with patch("core.llm.byok_handler.BYOKHandler", side_effect=RuntimeError("x")):
            assert "error" in asyncio.run(T._handle_list_models({}))

    def test_handle_compress_text(self):
        from core.mcp_server import tools as T
        pipe = MagicMock()
        pipe.compress_tool_output.return_value = ("compressed", SimpleNamespace(to_dict=lambda: {"ratio": 0.5}))
        with patch("core.llm.compression.get_compression_pipeline", return_value=pipe):
            res = asyncio.run(T._handle_compress_text({"text": "long text"}))
        assert res["compressed_text"] == "compressed" and res["metrics"] == {"ratio": 0.5}

        with patch("core.llm.compression.get_compression_pipeline", side_effect=RuntimeError("x")):
            assert "error" in asyncio.run(T._handle_compress_text({}))

    def test_handle_set_compression(self):
        from core.mcp_server import tools as T
        import core.llm.compression as comp
        old = (comp.COMPRESSION_ENABLED, comp.RTK_ENABLED)
        try:
            res = asyncio.run(T._handle_set_compression({"enabled": False}))
            assert res == {"compression_enabled": False}
            assert comp.COMPRESSION_ENABLED is False and comp.RTK_ENABLED is False
            res2 = asyncio.run(T._handle_set_compression({"enabled": True}))
            assert res2 == {"compression_enabled": True}
        finally:
            comp.COMPRESSION_ENABLED, comp.RTK_ENABLED = old

        with patch.dict(sys.modules, {"core.llm.compression": None}):
            res3 = asyncio.run(T._handle_set_compression({"enabled": True}))
            assert "error" in res3

    def test_handle_get_spend(self):
        from core.mcp_server import tools as T
        tracker = MagicMock()
        tracker.is_budget_exceeded.return_value = True
        mod = types.SimpleNamespace(llm_usage_tracker=tracker)
        with patch.dict(sys.modules, {"core.llm_usage_tracker": mod}):
            res = asyncio.run(T._handle_get_spend({"workspace_id": "ws"}))
        assert res == {"budget_exceeded": True, "workspace": "ws"}

        with patch.dict(sys.modules, {"core.llm_usage_tracker": None}):
            assert "error" in asyncio.run(T._handle_get_spend({}))

    def test_handle_get_health(self):
        from core.mcp_server import tools as T
        monitor = MagicMock()
        monitor.get_provider_health.side_effect = lambda pid: {"state": "open"} if pid == "openai" else None
        mod = types.SimpleNamespace(get_health_monitor=lambda: monitor)
        with patch.dict(sys.modules, {"core.provider_health_monitor": mod}):
            res = asyncio.run(T._handle_get_health({}))
        assert res == {"providers": {"openai": {"state": "open"}}}

        with patch.dict(sys.modules, {"core.provider_health_monitor": None}):
            assert "error" in asyncio.run(T._handle_get_health({}))

    def test_handle_fusion_generate(self):
        from core.mcp_server import tools as T
        handler = MagicMock()
        handler.analyze_query_complexity.return_value = "complex"
        handler.get_ranked_providers = AsyncMock(return_value=[("a", "m1"), ("b", "m2")])
        with patch("core.llm.byok_handler.BYOKHandler", return_value=handler), \
             patch("core.llm.fusion_router.is_fusion_eligible", return_value=True), \
             patch("core.llm.fusion_router.run_fusion",
                   AsyncMock(return_value=("fusion text", {"judge": "gpt"}))) as rf:
            res = asyncio.run(T._handle_fusion_generate({"prompt": "p", "task_type": "chat"}))
        assert res["result"] == "fusion text" and res["metadata"] == {"judge": "gpt"}
        rf.assert_awaited_once()

        with patch("core.llm.byok_handler.BYOKHandler", return_value=handler), \
             patch("core.llm.fusion_router.is_fusion_eligible", return_value=False):
            res2 = asyncio.run(T._handle_fusion_generate({"prompt": "p"}))
        assert "error" in res2 and "Fusion not eligible" in res2["error"]

        with patch("core.llm.byok_handler.BYOKHandler", side_effect=RuntimeError("x")):
            assert "error" in asyncio.run(T._handle_fusion_generate({"prompt": "p"}))


# =========================================================================== #
# 7. core/reasoning_chain.py
# =========================================================================== #
class TestReasoningChainModule:
    def _tracker(self):
        from core.reasoning_chain import ReasoningTracker
        return ReasoningTracker()

    def _step(self, **kw):
        from core.reasoning_chain import ReasoningStep, ReasoningStepType
        base = dict(
            id="s1", step_type=ReasoningStepType.DECISION, description="pick agent",
            inputs={"q": 1}, outputs={"a": 2}, confidence=0.8,
            duration_ms=12.5, timestamp=datetime.now(timezone.utc))
        base.update(kw)
        return ReasoningStep(**base)

    def test_step_and_chain_basics(self):
        from core.reasoning_chain import ReasoningChain
        chain = ReasoningChain(execution_id="e1", started_at=datetime.now(timezone.utc))
        step = self._step()
        chain.add_step(step)
        assert chain.get_step("s1") is step
        assert chain.get_step("nope") is None
        step.add_feedback(SimpleNamespace(feedback_type="approve"))

    def test_to_mermaid_and_to_dict(self):
        from core.reasoning_chain import FeedbackType, ReasoningChain
        chain = ReasoningChain(
            execution_id="e1", started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc), final_outcome="done",
            total_duration_ms=5.0, agent_id="ag1")
        s1 = self._step(id="s1", description="first step of reasoning")
        s2 = self._step(id="s2", description="second " * 10, parent_id="s1", agent_id="ag1")
        from core.reasoning_chain import ReasoningFeedback
        s1.feedback.append(ReasoningFeedback(
            id="f1", step_id="s1", chain_id="e1", user_id="u1", user_specialty="fin",
            is_trusted=True, feedback_type=FeedbackType.APPROVE, comment="good"))
        s2.feedback.append(ReasoningFeedback(
            id="f2", step_id="s2", chain_id="e1", user_id="u2", user_specialty=None,
            is_trusted=False, feedback_type=FeedbackType.REJECT, comment="bad"))
        chain.add_step(s1)
        chain.add_step(s2)

        mermaid = chain.to_mermaid()
        assert mermaid.startswith("graph TD")
        assert "step0" in mermaid and "step0 --> step1" in mermaid
        assert "✅" in mermaid and "❌" in mermaid

        d = chain.to_dict()
        assert d["execution_id"] == "e1" and d["step_count"] == 2
        assert d["completed_at"] is not None and d["final_outcome"] == "done"
        assert d["steps"][0]["feedback"][0]["type"] == "approve"
        assert d["steps"][0]["feedback"][0]["is_trusted"] is True
        assert d["steps"][1]["agent_id"] == "ag1"
        assert "mermaid_diagram" in d

    def test_tracker_lifecycle(self):
        t = self._tracker()
        cid = t.start_chain("exec-1", agent_id="ag")
        assert cid == "exec-1" and t.get_chain(cid).agent_id == "ag"

        # auto-start chain when adding step with unknown/absent id
        from core.reasoning_chain import ReasoningStepType
        step = t.add_step(step_type=ReasoningStepType.INTENT_ANALYSIS,
                          description="auto chain", inputs={"i": 1}, outputs={"o": 1},
                          confidence=0.5, duration_ms=1, metadata={"k": "v"}, agent_id="ag")
        assert step.metadata == {"k": "v"} and step.agent_id == "ag"
        auto_id = t._current_chain_id
        assert t.get_chain(auto_id).steps[0] is step

        # explicit chain_id
        step2 = t.add_step(step_type=ReasoningStepType.ACTION,
                           description="explicit", chain_id=cid)
        assert t.get_chain(cid).get_step(step2.id) is step2

        # unknown chain_id -> auto-starts a new chain
        t3 = self._tracker()
        step3 = t3.add_step(step_type=ReasoningStepType.MEMORY_QUERY,
                            description="unknown chain", chain_id="brand-new")
        assert t3.get_chain("brand-new").get_step(step3.id) is step3
        # no current chain id at all -> also auto-starts
        t4 = self._tracker()
        assert t4._current_chain_id is None
        t4.add_step(step_type=ReasoningStepType.MEMORY_QUERY, description="auto")
        assert t4._current_chain_id is not None

        chain = t.complete_chain(outcome="ok", chain_id=cid)
        assert chain.final_outcome == "ok" and chain.completed_at is not None
        assert chain.total_duration_ms >= 0
        assert t.complete_chain(chain_id="missing") is None
        empty = self._tracker()
        assert empty.complete_chain() is None  # no current chain

        t2 = self._tracker()
        c_old = t2.start_chain("old")
        t2.get_chain("old").started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        c_new = t2.start_chain("new")
        assert t2.get_all_chains()[0].execution_id == "new"
        assert t2.get_all_chains(limit=1)[0].execution_id == "new"
        assert t2.get_pending_feedback() == []

    @pytest.mark.asyncio
    async def test_submit_step_feedback_paths(self):
        from core.reasoning_chain import FeedbackType, ReasoningStepType
        t = self._tracker()
        cid = t.start_chain("fb-chain")
        step = t.add_step(step_type=ReasoningStepType.ACTION,
                          description="d", chain_id=cid, agent_id="ag1")

        # missing chain / missing step
        assert await t.submit_step_feedback("nope", "x", "u", FeedbackType.APPROVE, "c") is None
        assert await t.submit_step_feedback(cid, "nope", "u", FeedbackType.APPROVE, "c") is None

        applied = AsyncMock()
        with patch.object(t, "_check_user_trust", AsyncMock(return_value=(True, "finance"))), \
             patch.object(t, "_apply_feedback_to_agent", applied):
            fb = await t.submit_step_feedback(
                cid, step.id, "u1", FeedbackType.REJECT, "bad", suggested_alternative="alt")
        assert fb.is_trusted and fb.user_specialty == "finance"
        assert fb.suggested_alternative == "alt"
        assert step.feedback[0] is fb
        applied.assert_awaited_once()
        assert t.get_pending_feedback() == [fb]  # unprocessed

        with patch.object(t, "_check_user_trust", AsyncMock(return_value=(False, None))), \
             patch.object(t, "_apply_feedback_to_agent", AsyncMock()) as ap2:
            fb2 = await t.submit_step_feedback(cid, step.id, "u2", FeedbackType.SUGGEST, "hmm")
        assert fb2.is_trusted is False
        ap2.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_check_user_trust(self):
        import core.reasoning_chain as rc
        t = self._tracker()

        def db_with(user, agent=None):
            db = MagicMock()
            db.query.return_value.filter.return_value.first.side_effect = [user, agent]
            return db

        from core.models import UserRole
        admin = SimpleNamespace(role=UserRole.SUPER_ADMIN, specialty="fin")
        with patch("core.database.get_db_session", return_value=_ctx(db_with(admin))):
            trusted, spec = await t._check_user_trust("admin", None)
        assert trusted is True and spec == "fin"

        ws_admin = SimpleNamespace(role=UserRole.WORKSPACE_ADMIN, specialty=None)
        with patch("core.database.get_db_session", return_value=_ctx(db_with(ws_admin))):
            assert (await t._check_user_trust("ws", None))[0] is True

        # specialty match with agent
        user = SimpleNamespace(role=UserRole.USER if hasattr(UserRole, "USER") else "user", specialty="Finance")
        agent = SimpleNamespace(category="finance")
        with patch("core.database.get_db_session", return_value=_ctx(db_with(user, agent))):
            trusted, spec = await t._check_user_trust("u", "ag")
        assert trusted is True and spec == "Finance"

        # specialty mismatch / missing agent / no specialty
        agent2 = SimpleNamespace(category="sales")
        with patch("core.database.get_db_session", return_value=_ctx(db_with(user, agent2))):
            assert (await t._check_user_trust("u", "ag"))[0] is False
        user_nospec = SimpleNamespace(role="user", specialty=None)
        with patch("core.database.get_db_session", return_value=_ctx(db_with(user_nospec, agent2))):
            assert (await t._check_user_trust("u", "ag"))[0] is False

        # user not found
        with patch("core.database.get_db_session", return_value=_ctx(db_with(None))):
            assert (await t._check_user_trust("ghost", None)) == (False, None)

        # exception
        with patch("core.database.get_db_session", side_effect=RuntimeError("db")):
            assert (await t._check_user_trust("u", None)) == (False, None)

    @pytest.mark.asyncio
    async def test_apply_feedback_to_agent(self):
        from core.reasoning_chain import FeedbackType, ReasoningFeedback
        t = self._tracker()

        step = self._step(agent_id=None)
        await t._apply_feedback_to_agent(Mock(), step)  # no agent -> early return

        def _fb(ftype):
            return ReasoningFeedback(
                id="f", step_id="s", chain_id="c", user_id="u", user_specialty=None,
                is_trusted=True, feedback_type=ftype, comment="c")

        gov = MagicMock()
        gov_mod = types.SimpleNamespace(AgentGovernanceService=MagicMock(return_value=gov))
        step_pos = self._step(agent_id="ag")
        with patch.dict(sys.modules, {"core.agent_governance_service": gov_mod}), \
             patch("core.database.get_db_session", return_value=_ctx(MagicMock())):
            await t._apply_feedback_to_agent(_fb(FeedbackType.APPROVE), step_pos)
        # R81d: fixed signature (user_id was passed positionally as `positive`,
        # plus a nonexistent is_positive kwarg -> TypeError -> swallowed).
        gov._update_confidence_score.assert_called_once_with(
            "ag", positive=True, impact_level="high")

        gov2 = MagicMock()
        gov_mod2 = types.SimpleNamespace(AgentGovernanceService=MagicMock(return_value=gov2))
        step_neg = self._step(agent_id="ag2")
        with patch.dict(sys.modules, {"core.agent_governance_service": gov_mod2}), \
             patch("core.database.get_db_session", return_value=_ctx(MagicMock())):
            await t._apply_feedback_to_agent(_fb(FeedbackType.REJECT), step_neg)
        gov2._update_confidence_score.assert_called_once_with(
            "ag2", positive=False, impact_level="high")

        # suggest/explain types: no confidence update
        gov3 = MagicMock()
        gov_mod3 = types.SimpleNamespace(AgentGovernanceService=MagicMock(return_value=gov3))
        with patch.dict(sys.modules, {"core.agent_governance_service": gov_mod3}), \
             patch("core.database.get_db_session", return_value=_ctx(MagicMock())):
            await t._apply_feedback_to_agent(_fb(FeedbackType.SUGGEST), self._step(agent_id="ag3"))
        gov3._update_confidence_score.assert_not_called()

        # exception path swallowed
        with patch.dict(sys.modules, {"core.agent_governance_service": None}):
            await t._apply_feedback_to_agent(_fb(FeedbackType.APPROVE), self._step(agent_id="ag"))

    def test_global_tracker(self):
        import core.reasoning_chain as rc
        t = rc.get_reasoning_tracker()
        assert t is rc.get_reasoning_tracker()
        assert isinstance(t, rc.ReasoningTracker)
