"""Gap-fill coverage for integrations wave B (batch 2)."""
import asyncio
import importlib
import json
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


def _stub_top_modules(names, attrs=None):
    """Create fake top-level modules exporting the given attribute names."""
    attrs = attrs or {}
    stubs = {}
    for name in names:
        mod = MagicMock()
        for attr in attrs.get(name, []):
            setattr(mod, attr, MagicMock)
        stubs[name] = mod
    return stubs


# ---------------------------------------------------------------------------
# atom_ai_integration import-with-services + platform-none gaps
# ---------------------------------------------------------------------------


class TestAtomAIImportWithServices:
    def test_reload_with_all_services(self):
        mod = importlib.import_module("integrations.atom_ai_integration")
        stubs = _stub_top_modules(
            ["atom_discord_integration", "atom_google_chat_integration",
             "atom_ingestion_pipeline", "atom_memory_service", "atom_search_service",
             "atom_slack_integration", "atom_teams_integration", "atom_workflow_service"],
            attrs={
                "atom_slack_integration": ["atom_slack_integration"],
                "atom_teams_integration": ["atom_teams_integration"],
                "atom_google_chat_integration": ["atom_google_chat_integration"],
                "atom_discord_integration": ["atom_discord_integration"],
                "atom_ingestion_pipeline": ["AtomIngestionPipeline"],
                "atom_memory_service": ["AtomMemoryService"],
                "atom_search_service": ["AtomSearchService"],
                "atom_workflow_service": ["AtomWorkflowService"],
            },
        )
        with patch.dict(sys.modules, stubs):
            importlib.reload(mod)
            assert mod.atom_ai_integration.platform_integrations["slack"] is not None
            assert mod.atom_ai_integration.llm_service is not None
        # restore degraded state
        importlib.reload(mod)
        assert mod.atom_ai_integration.platform_integrations["slack"] is None


class TestAtomAIGaps:
    def _svc(self):
        from integrations.atom_ai_integration import AtomAIIntegration
        llm = MagicMock()
        llm.chat_completion = AsyncMock(return_value=json.dumps({"sentiment": "positive"}))
        svc = AtomAIIntegration({"llm_service": llm})
        platform = MagicMock()
        platform.get_unified_workspaces = AsyncMock(return_value=[{
            "id": "w1", "name": "W", "platform": "p", "type": "t", "status": "s",
            "member_count": 1, "channel_count": 1, "icon_url": "", "description": "",
            "capabilities": {}, "integration_data": {},
        }])
        platform.get_unified_channels = AsyncMock(return_value=[{
            "id": "c1", "name": "n", "display_name": "n", "type": "t", "platform": "p",
            "workspace_id": "w1", "workspace_name": "W", "status": "s", "member_count": 1,
            "message_count": 1, "unread_count": 0, "is_private": False, "is_text": True,
            "is_voice": True, "capabilities": {}, "integration_data": {},
        }])
        platform.get_unified_messages = AsyncMock(return_value=[])
        svc.platform_integrations = {"slack": platform, "teams": None}
        svc.atom_memory = MagicMock()
        svc.atom_search = MagicMock()
        return svc

    async def test_platform_none_skip_paths(self):
        svc = self._svc()
        ws = await svc.get_intelligent_workspaces("u1")
        assert len(ws) == 1
        assert await svc.get_intelligent_workspaces("u1")  # cached self.intelligent_workspaces
        assert await svc.get_intelligent_messages("w1", "c1") == []  # empty messages
        svc2 = self._svc()
        svc2.platform_integrations = {"slack": None}
        assert await svc2.get_intelligent_workspaces("u1") == []
        assert await svc2.get_intelligent_messages("w1", "c1") == []
        assert await svc2.send_intelligent_message("w1", "c1", "hi") == {"ok": False, "error": "Unsupported platform"}

    async def test_voice_analysis_flag_false(self):
        svc = self._svc()
        platform = MagicMock()
        platform.get_unified_workspaces = AsyncMock(return_value=[{
            "id": "w1", "name": "W", "platform": "p", "type": "t", "status": "s",
            "member_count": 1, "channel_count": 1, "icon_url": "", "description": "",
            "capabilities": {"voice_chat": False}, "integration_data": {},
        }])
        svc.platform_integrations = {"slack": platform}
        ws = await svc.get_intelligent_workspaces("u1")
        assert ws[0]["ai_features"]["voice_analysis"] is False


# ---------------------------------------------------------------------------
# bytewax: stub-import coverage + gap branches
# ---------------------------------------------------------------------------


class TestBytewaxStubImports:
    def test_reload_with_bytewax_stubs(self):
        bytewax_stubs = {}
        for name in ["bytewax", "bytewax.operators", "bytewax.dataflow",
                     "bytewax.inputs", "bytewax.outputs",
                     "bytewax.connectors.stdio"]:
            bytewax_stubs[name] = MagicMock()
        import integrations.bytewax_service as mod
        with patch.dict(sys.modules, bytewax_stubs):
            importlib.reload(mod)
            assert mod.BYTEWAX_AVAILABLE is True
            flow = mod.BytewaxIngestionService.create_dataflow(MagicMock())
            assert flow is not None
        importlib.reload(mod)
        assert mod.BYTEWAX_AVAILABLE is False


class TestBytewaxGaps:
    def _record(self, record_type="order", operation="CREATE", content="Order 123: 49.99 from buyer@example.com"):
        from integrations.atom_ingestion_pipeline import AtomRecordData, RecordType
        rtypes = {"order": RecordType.ORDER, "contact": RecordType.CONTACT,
                  "communication": RecordType.COMMUNICATION, "document": RecordType.DOCUMENT}
        record = AtomRecordData(
            id="rec_1", app_type="shopify", record_type=rtypes[record_type],
            content=content, timestamp=datetime.now(timezone.utc),
            metadata={"workspace_id": "ws1", "user_id": "u1"},
        )
        record.operation = operation
        return record

    async def test_secrets_redaction_no_secrets(self):
        from integrations.bytewax_service import SecretsRedactionOperator
        op = SecretsRedactionOperator()
        redactor = MagicMock()
        redactor.redact.return_value.has_secrets = False
        op.redactor = redactor
        rec = self._record()
        assert op.redact(rec) is rec

    async def test_knowledge_sync_and_error_branches(self):
        from integrations.bytewax_service import KnowledgeExtractionOperator
        op = KnowledgeExtractionOperator(workspace_id="ws1")
        rec = self._record()
        rec.content = "x" * 50
        km = MagicMock()
        km.process_document = AsyncMock()
        op.knowledge_manager = km
        op.automation_settings = MagicMock()
        op.automation_settings.is_extraction_enabled = MagicMock(return_value=True)
        # get_running_loop raises RuntimeError -> sync asyncio.run path
        with patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")), \
             patch("asyncio.run", new=AsyncMock()):
            result = op.extract_knowledge(rec)
        assert result.metadata["_knowledge_extracted"] is True
        # outer except path: get_running_loop raises non-RuntimeError
        with patch("asyncio.get_running_loop", side_effect=ValueError("boom")):
            op.extract_knowledge(rec)
        # graphrag fallback (knowledge manager import fails) + bad metadata json
        rec2 = self._record()
        rec2.content = "y" * 50
        rec2.metadata = "not-json{{"
        op.knowledge_manager = None
        ge = MagicMock()
        ge.ingest_document = MagicMock(return_value={"ok": 1})
        op.graphrag_engine = ge
        with patch("core.knowledge_ingestion.get_knowledge_ingestion",
                   side_effect=ImportError("x")):
            result = op.extract_knowledge(rec2)
        assert result.metadata == "not-json{{"
        ge.ingest_document = MagicMock(side_effect=RuntimeError("x"))
        with patch("core.knowledge_ingestion.get_knowledge_ingestion",
                   side_effect=ImportError("x")):
            op.extract_knowledge(rec2)
        with patch("core.automation_settings.get_automation_settings",
                   side_effect=ImportError("x")):
            op.automation_settings = None
            op._lazy_init()

    async def test_formula_extractor_import_error(self):
        from integrations.bytewax_service import FormulaExtractionOperator
        op = FormulaExtractionOperator(workspace_id="ws1")
        rec = self._record(record_type="document")
        rec.metadata = {"file_path": "/tmp/f.xlsx"}
        with patch("core.formula_extractor.FormulaExtractor", side_effect=ImportError("x")):
            result = op.extract(rec)
        assert result is rec

    async def test_fastembed_model_creation(self):
        import integrations.bytewax_service as mod
        from integrations.bytewax_service import FastEmbedOperator
        fake_cls = MagicMock()
        with patch.object(mod, "TextEmbedding", fake_cls):
            op = FastEmbedOperator()
            model = op._get_model()
            assert model is fake_cls.return_value

    async def test_stub_dataflow_instantiation(self):
        import integrations.bytewax_service as mod
        if not mod.BYTEWAX_AVAILABLE:
            flow = mod.Dataflow("x")
            assert flow.name == "x"

    async def test_ai_coordinator_import_error(self):
        import integrations.bytewax_service as mod
        sink = mod.LanceDBStatelessSinkPartition()
        sink.handler = MagicMock()
        sink.handler.workspace_id = "ws1"
        rec = self._record()
        with patch.dict(sys.modules, {"advanced_workflow_orchestrator": MagicMock()}):
            with patch.dict(sys.modules, {"core.ai_trigger_coordinator": None}):
                sink._trigger_post_ingestion_hooks(rec, "d1")
        with patch.dict(sys.modules, {"advanced_workflow_orchestrator": None}):
            sink._trigger_post_ingestion_hooks(rec, "d1")

    async def test_extraction_enabled_default_true(self):
        from integrations.bytewax_service import KnowledgeExtractionOperator
        op = KnowledgeExtractionOperator(workspace_id="ws1")
        op.automation_settings = None
        assert op._is_extraction_enabled() is True

    async def test_secrets_redactor_import_error(self):
        from integrations.bytewax_service import SecretsRedactionOperator
        op = SecretsRedactionOperator()
        with patch("core.secrets_redactor.get_secrets_redactor",
                   side_effect=ImportError("x")):
            assert op._get_redactor() is None

    async def test_sink_sync_trigger_paths(self):
        import integrations.bytewax_service as mod
        sink = mod.LanceDBStatelessSinkPartition()
        sink.handler = MagicMock()
        sink.handler.workspace_id = "ws1"
        rec = self._record()
        orc = MagicMock()
        orc.orchestrator.trigger_event = AsyncMock()
        with patch.dict(sys.modules, {"advanced_workflow_orchestrator": orc}):
            with patch("asyncio.create_task", side_effect=RuntimeError("no loop")), \
                 patch("asyncio.run", new=AsyncMock()):
                sink._trigger_post_ingestion_hooks(rec, "d1")
        ai = MagicMock()
        ai.on_data_ingested = AsyncMock()
        with patch.dict(sys.modules, {"core.ai_trigger_coordinator": ai}):
            with patch("asyncio.create_task", side_effect=RuntimeError("no loop")), \
                 patch("asyncio.run", new=AsyncMock()):
                sink._trigger_post_ingestion_hooks(rec, "d1")
            with patch("asyncio.create_task", side_effect=RuntimeError("no loop")), \
                 patch("asyncio.run", side_effect=RuntimeError("boom")):
                sink._trigger_post_ingestion_hooks(rec, "d1")

    async def test_sink_write_batch_unknown_and_string_metadata(self):
        import integrations.bytewax_service as mod
        sink = mod.LanceDBStatelessSinkPartition()
        sink.handler = MagicMock()
        sink.handler.add_document = MagicMock(return_value=True)
        rec = self._record()
        rec.metadata = "bad-json{"
        sink.write_batch([rec])
        rec2 = self._record(operation="UPDATE")
        rec2.metadata = "bad-json{"
        sink.write_batch([rec2])

    async def test_create_dataflow_with_patched_ops(self):
        """Build the dataflow graph with patched bytewax globals (no reload)."""
        import integrations.bytewax_service as mod
        op = MagicMock()
        df = MagicMock()
        with patch.object(mod, "BYTEWAX_AVAILABLE", True), \
             patch.object(mod, "op", op), \
             patch.object(mod, "Dataflow", df):
            flow = mod.BytewaxIngestionService.create_dataflow(MagicMock())
            assert flow is not None
            assert op.input.called
            assert op.map.call_count >= 4
            assert op.output.called
        with patch.object(mod, "BYTEWAX_AVAILABLE", False):
            with pytest.raises(RuntimeError):
                mod.BytewaxIngestionService.create_dataflow(MagicMock())

    async def test_queue_partition_max_batch(self):
        from integrations.bytewax_service import BytewaxQueuePartition, get_bytewax_queue
        q = get_bytewax_queue()
        for i in range(10):
            q.put({"i": i})
        part = BytewaxQueuePartition(max_batch_size=3)
        assert len(part.next_batch()) == 3
        assert len(part.next_batch()) == 3
        assert len(part.next_batch()) == 3
        assert len(part.next_batch()) == 1


# ---------------------------------------------------------------------------
# whatsapp gaps: _create_tables internals, route error paths, bridge routing
# ---------------------------------------------------------------------------


class TestWhatsAppGaps:
    async def test_create_tables_runs(self):
        from integrations.whatsapp_business_integration import WhatsAppBusinessIntegration
        svc = WhatsAppBusinessIntegration(tenant_id="t1", config={"access_token": "t"})
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = MagicMock()
        conn.cursor.return_value.__exit__.return_value = False
        svc.db_connection = conn
        svc._create_tables()
        assert conn.commit.called
        conn2 = MagicMock()
        conn2.cursor.side_effect = Exception("x")
        svc.db_connection = conn2
        with pytest.raises(Exception):
            svc._create_tables()
        svc.db_connection = None
        svc._create_tables()

    async def test_get_credentials_error_branches(self):
        import integrations.whatsapp_business_integration as mod
        svc = mod.WhatsAppBusinessIntegration(tenant_id="t1", config={})
        with pytest.raises(mod.AuthenticationError):
            await svc._get_credentials(None)
        with patch.object(mod.connection_service, "get_connections", return_value=[]):
            with pytest.raises(mod.AuthenticationError):
                await svc._get_credentials("u1")
        with patch.object(mod.connection_service, "get_connections", return_value=[{"id": "c1"}]):
            with patch.object(mod.connection_service, "get_connection_credentials",
                              new=AsyncMock(return_value={"access_token": "a"})):
                creds = await svc._get_credentials("u1")
            assert creds["access_token"] == "a"

    async def test_route_error_paths(self):
        import integrations.whatsapp_business_integration as mod
        svc = MagicMock()
        svc.get_conversations.return_value = []
        svc.get_messages.return_value = []
        with patch.object(mod, "jsonify", side_effect=lambda obj, **kw: obj), \
             patch.object(mod, "whatsapp_integration", svc), \
             patch.object(mod, "request") as req:
            req.args.get.side_effect = Exception("boom")
            resp = mod.get_conversations()
            assert resp[0]["success"] is False
            resp = mod.get_messages("wa1")
            assert resp[0]["success"] is False
            req.args.get.side_effect = None
            req.get_json.side_effect = Exception("boom")
            resp = mod.create_template()
            assert resp[0]["success"] is False

    async def test_process_incoming_message_bridge(self):
        import integrations.whatsapp_business_integration as mod
        svc = MagicMock()
        bridge = MagicMock()
        bridge.universal_webhook_bridge.process_incoming_message = AsyncMock()
        with patch.object(mod, "whatsapp_integration", svc), \
             patch.dict(sys.modules, {"integrations.universal_webhook_bridge": bridge}):
            mod._process_incoming_message({"from": "wa1", "id": "m1", "type": "text",
                                           "text": {"body": "hi"}})
            assert bridge.universal_webhook_bridge.process_incoming_message.called
            bridge.universal_webhook_bridge.process_incoming_message = AsyncMock(side_effect=RuntimeError("x"))
            mod._process_incoming_message({"from": "wa1", "id": "m1", "type": "text"})
            with patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")), \
                 patch("asyncio.run", new=AsyncMock()):
                mod._process_incoming_message({"from": "wa1", "id": "m1", "type": "text"})


# ---------------------------------------------------------------------------
# slack_workflow_automation gaps
# ---------------------------------------------------------------------------


class TestSlackWorkflowAutomationGaps:
    def _wf(self):
        from integrations.slack_workflow_automation import (
            SlackWorkflow, SlackWorkflowAction, SlackWorkflowTrigger,
            WorkflowActionType, WorkflowTriggerType,
        )
        return SlackWorkflow(
            id="wf1", name="WF", description="d",
            triggers=[SlackWorkflowTrigger(
                id="tr1", type=WorkflowTriggerType.MESSAGE, conditions={},
                workspace_id="ws", channel_ids=[], user_ids=[], keywords=[])],
            actions=[SlackWorkflowAction(
                id="a1", type=WorkflowActionType.CREATE_TASK, parameters={})],
            created_by="u", created_at=datetime.now(timezone.utc),
        )

    def _svc(self):
        from integrations.slack_workflow_automation import SlackWorkflowAutomation
        return SlackWorkflowAutomation({})

    def test_reload_with_services(self):
        mod = importlib.import_module("integrations.slack_workflow_automation")
        stubs = _stub_top_modules(
            ["atom_memory_service", "atom_search_service", "communication_service",
             "workflow_engine"],
            attrs={"atom_memory_service": ["AtomMemoryService"],
                   "atom_search_service": ["AtomSearchService"],
                   "communication_service": ["CommunicationService"],
                   "workflow_engine": ["WorkflowEngine"]},
        )
        with patch.dict(sys.modules, stubs):
            importlib.reload(mod)
        importlib.reload(mod)

    async def test_unregister_error_and_memory_paths(self):
        svc = self._svc()
        wf = self._wf()
        memory = MagicMock()
        memory.store = MagicMock()
        svc.memory_service = memory
        svc.register_workflow(wf)
        memory.delete = MagicMock(side_effect=Exception("x"))
        assert svc.unregister_workflow("wf1") is False
        svc.register_workflow(wf)
        memory.delete = MagicMock()
        assert svc.unregister_workflow("wf1") is True
        assert svc.unregister_workflow("wf1") is False

    async def test_execute_workflow_memory_store(self):
        svc = self._svc()
        wf = self._wf()
        memory = MagicMock()
        memory.store = MagicMock()
        svc.memory_service = memory
        svc.register_workflow(wf)
        svc.execute_action = AsyncMock(return_value={"status": "success"})
        execution = await svc.execute_workflow("wf1", {"workspace_id": "ws"})
        assert execution.status == "completed"
        assert memory.store.called

    async def test_send_message_value_error_no_client(self):
        svc = self._svc()
        from integrations.slack_workflow_automation import SlackWorkflowAction, WorkflowActionType
        action = SlackWorkflowAction(id="a1", type=WorkflowActionType.SEND_MESSAGE,
                                     parameters={"channel": "C1", "message": "m"})
        result = await svc.execute_action(action, {"workspace_id": "ws"})
        assert result["status"] == "failed"

    async def test_evaluate_trigger_more_branches(self):
        svc = self._svc()
        from integrations.slack_workflow_automation import SlackWorkflowTrigger, WorkflowTriggerType
        base = {"type": "message", "team_id": "ws", "channel": "C1", "user": "U1", "text": "hi"}
        t = SlackWorkflowTrigger(id="t", type=WorkflowTriggerType.MESSAGE, conditions={},
                                 workspace_id="ws", channel_ids=["C1"], user_ids=["U1"], keywords=["hi"])
        assert await svc._evaluate_trigger(t, base) is True
        assert await svc._evaluate_trigger(t, {**base, "type": "not_message"}) is False
        t2 = SlackWorkflowTrigger(id="t", type=WorkflowTriggerType.FILE_UPLOAD, conditions={},
                                  workspace_id="ws", channel_ids=[], user_ids=[], keywords=[])
        assert await svc._evaluate_trigger(t2, {**base, "type": "message"}) is False
        t3 = SlackWorkflowTrigger(id="t", type=WorkflowTriggerType.CHANNEL_CREATED, conditions={},
                                  workspace_id="ws", channel_ids=[], user_ids=[], keywords=[])
        assert await svc._evaluate_trigger(t3, {**base, "type": "message"}) is False
        t4 = SlackWorkflowTrigger(id="t", type=WorkflowTriggerType.USER_JOIN, conditions={},
                                  workspace_id="ws", channel_ids=[], user_ids=[], keywords=[])
        assert await svc._evaluate_trigger(t4, {**base, "type": "message"}) is False
        t5 = SlackWorkflowTrigger(id="t", type=WorkflowTriggerType.MENTION, conditions={},
                                  workspace_id="ws", channel_ids=[], user_ids=[], keywords=[])
        assert await svc._evaluate_trigger(t5, {**base, "type": "message"}) is True
        assert await svc._evaluate_trigger(t5, {"type": "message"}) is False
        t6 = SlackWorkflowTrigger(id="t", type=WorkflowTriggerType.MESSAGE, conditions={},
                                  workspace_id="ws", channel_ids=[], user_ids=[], keywords=[])
        with patch.object(svc, "_evaluate_trigger", side_effect=RuntimeError("x")):
            await svc.handle_slack_event({"type": "message", "team_id": "ws"})
        # index error branch
        svc.search_service = MagicMock()
        svc.search_service.index = AsyncMock(side_effect=Exception("x"))
        await svc._index_slack_content({"type": "message", "text": "hi"})
        svc2 = self._svc()
        await svc2._index_slack_content({"type": "message"})  # no search service

    async def test_handle_slack_event_no_match(self):
        svc = self._svc()
        executions = await svc.handle_slack_event({"type": "message", "team_id": "ws"})
        assert executions == []
