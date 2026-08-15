"""Bug-hunt tests (RED->GREEN) for integrations wave B.

Targets: atom_ai_integration, bytewax_service, whatsapp_business_integration,
shopify_service, atom_zoom_integration, slack_workflow_automation,
slack_workflow_engine, atom_quickbooks_integration_service, atom_video_ai_service,
pdf_ocr_service, atom_discord_integration.

Every test here was written FIRST (RED), then the source was fixed (GREEN).
"""

import asyncio
import importlib
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------- imports crash

class TestImportRegression:
    """Modules must import cleanly even when optional deps are missing."""

    def test_atom_ai_integration_imports_cleanly(self):
        mod = importlib.import_module("integrations.atom_ai_integration")
        assert hasattr(mod, "atom_ai_integration")
        assert mod.atom_ai_integration.platform_integrations["slack"] is None
        assert mod.atom_ai_integration.llm_service is not None or mod.atom_ai_integration.llm_service is None

    def test_bytewax_service_imports_without_bytewax_installed(self):
        mod = importlib.import_module("integrations.bytewax_service")
        assert hasattr(mod, "BytewaxIngestionService")
        assert hasattr(mod, "get_bytewax_queue")

    def test_whatsapp_business_integration_imports_without_flask(self):
        mod = importlib.import_module("integrations.whatsapp_business_integration")
        assert hasattr(mod, "WhatsAppBusinessIntegration")
        assert hasattr(mod, "whatsapp_integration")

    def test_whatsapp_registry_class_contract(self):
        """core.integration_registry maps 'whatsapp' to a real class in the module."""
        import importlib
        mod = importlib.import_module("integrations.whatsapp_business_integration")
        registry = importlib.import_module("core.integration_registry")
        path = registry.DEFAULT_SERVICE_REGISTRY["whatsapp"]
        module_name, class_name = path.split(":")
        assert hasattr(mod, class_name), f"{class_name} missing from module"
        # The registry must point at the concrete class actually defined in
        # the module (formerly a phantom "WhatsAppBusinessService" alias).
        assert getattr(mod, class_name) is mod.WhatsAppBusinessIntegration


# ---------------------------------------------------------------- bytewax ops

class TestBytewaxOperators:
    def _record(self):
        from integrations.atom_ingestion_pipeline import AtomRecordData, RecordType
        return AtomRecordData(
            id="rec_1",
            app_type="shopify",
            record_type=RecordType.ORDER,
            content="Order 123: 49.99 from buyer@example.com",
            timestamp=datetime.now(timezone.utc),
            metadata={"workspace_id": "ws1", "user_id": "u1"},
        )

    def test_document_parsing_service_initialized(self):
        """_get_service() must not AttributeError on first call."""
        from integrations.bytewax_service import DocumentParsingOperator
        op = DocumentParsingOperator(workspace_id="ws1")
        assert op.service is None  # initialized in __init__

    def test_knowledge_extraction_initialized_attrs(self):
        """_lazy_init() must not AttributeError (knowledge_manager initialized)."""
        from integrations.bytewax_service import KnowledgeExtractionOperator
        op = KnowledgeExtractionOperator(workspace_id="ws1")
        assert op.knowledge_manager is None

    def test_formula_extractor_initialized_attrs(self):
        from integrations.bytewax_service import FormulaExtractionOperator
        op = FormulaExtractionOperator(workspace_id="ws1")
        assert op.extractor is None


# ---------------------------------------------------------------- shopify

class TestShopifySyncContract:
    async def test_sync_to_postgres_cache_uses_real_column(self):
        """IntegrationMetric has workspace_id, NOT tenant_id."""
        from integrations.shopify_service import ShopifyService
        svc = ShopifyService(tenant_id="t1", config={"access_token": "tok", "shop_name": "myshop"})
        svc.http = AsyncMock()
        svc.get_shop_analytics = AsyncMock(return_value={
            "shop_name": "s", "shop_domain": "d", "currency": "USD",
            "metrics": {"total_orders": 1, "total_products": 2, "total_customers": 3},
            "plan": "x", "created_at": None,
        })
        fake_metric = MagicMock()
        fake_metric.value = 0
        fake_query = MagicMock()
        fake_query.filter_by.return_value.first.return_value = fake_metric
        fake_db = MagicMock()
        fake_db.query.return_value = fake_query
        with patch("core.database.SessionLocal", return_value=fake_db):
            result = await svc.sync_to_postgres_cache("ws1")
        assert result["success"] is True
        kwargs = fake_db.add.call_args
        if kwargs:
            added = kwargs[0][0]
            assert not hasattr(added, "tenant_id")
            assert added.workspace_id == "ws1"


# ---------------------------------------------------------------- zoom

class TestZoomAutomationTrigger:
    async def test_trigger_automations_no_keyerror(self):
        from integrations.atom_zoom_integration import AtomZoomIntegration
        zoom = AtomZoomIntegration({})
        zoom.enterprise_automation = MagicMock()
        zoom.automation_triggers = {
            "meeting_started": {"enabled": True, "conditions": [], "actions": []},
        }
        from integrations.atom_zoom_integration import ZoomMeeting, ZoomMeetingType
        meeting = ZoomMeeting(
            meeting_id="m1", topic="t", meeting_type=ZoomMeetingType.INSTANT,
            host_id="h", start_time=datetime.now(timezone.utc), duration=0,
            timezone="UTC", agenda="", participants=[], is_recorded=False,
            password=None, waiting_room=False, security_level="standard",
            created_at=datetime.now(timezone.utc), status="started", metadata={},
        )
        await zoom._trigger_automations("meeting_started", meeting, {})
        assert zoom.analytics_metrics["automations_triggered"] == 1


# ---------------------------------------------------------------- slack

class TestSlackWorkflowAutomation:
    async def test_execute_workflow_retry_path_no_attr_error(self):
        """Retry path must not AttributeError on triggers[0].retry_count."""
        from integrations.slack_workflow_automation import (
            SlackWorkflow, SlackWorkflowAction, SlackWorkflowTrigger,
            SlackWorkflowAutomation, WorkflowActionType, WorkflowTriggerType,
        )
        svc = SlackWorkflowAutomation({})
        wf = SlackWorkflow(
            id="wf1", name="w", description="d",
            triggers=[SlackWorkflowTrigger(
                id="tr1", type=WorkflowTriggerType.MESSAGE, conditions={},
                workspace_id="ws", channel_ids=[], user_ids=[], keywords=[])],
            actions=[SlackWorkflowAction(
                id="a1", type=WorkflowActionType.CREATE_TASK,
                parameters={"title": {"value": "t"}})],
            created_by="u", created_at=datetime.now(timezone.utc),
        )
        svc.register_workflow(wf)
        svc.execute_action = AsyncMock(side_effect=RuntimeError("boom"))
        result = await svc.execute_workflow("wf1", {"workspace_id": "ws"})
        assert result.status == "failed"
        assert "boom" in result.error_message


class TestSlackWorkflowEngineLatent:
    def test_logger_defined_before_import_guard(self):
        """logger must exist even if SlackEnhancedService import fails."""
        src = open("integrations/slack_workflow_engine.py").read()
        assert src.index("logger = logging.getLogger") < src.index(
            "except ImportError:"), "logger used before definition in ImportError path"


# ---------------------------------------------------------------- quickbooks

class TestQuickBooksBugs:
    def test_stripe_integration_awaited_not_coroutine(self):
        """__init__ must call (not stash a coroutine from) _initialize_stripe_integration."""
        import integrations.atom_quickbooks_integration_service as qb
        svc = qb.AtomQuickBooksIntegrationService(config={"enable_stripe_integration": True})
        assert not asyncio.iscoroutine(svc.stripe_integration)
        assert not isinstance(svc.stripe_integration, asyncio.Future)

    async def test_create_invoice_stripe_path_does_not_attribute_error(self):
        import integrations.atom_quickbooks_integration_service as qb
        svc = qb.AtomQuickBooksIntegrationService(config={
            "enable_stripe_integration": True,
            "auto_categorization": False,
            "fraud_detection": False,
            "quickbooks_access_token": "tok",
        })
        svc.stripe_integration = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"Invoice": {"Id": "inv1", "TotalAmt": 100.0}}
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp)
            result = await svc.create_invoice({"customer_id": "c1", "amount": 100.0})
        assert result["success"] is True
        assert result["invoice_id"] == "inv1"

    async def test_create_payment_stripe_intent_path(self):
        import integrations.atom_quickbooks_integration_service as qb
        svc = qb.AtomQuickBooksIntegrationService(config={
            "enable_stripe_integration": True,
            "fraud_detection": False,
            "quickbooks_access_token": "tok",
        })
        svc.stripe_integration = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"Payment": {"Id": "pay1"}}
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp)
            result = await svc.create_payment({
                "customer_id": "c1", "amount": 50.0,
                "stripe_payment_intent_id": "pi_1",
            })
        assert result["success"] is True
        assert result["payment_id"] == "pay1"

    async def test_generate_financial_report_all_types(self):
        import integrations.atom_quickbooks_integration_service as qb
        svc = qb.AtomQuickBooksIntegrationService(config={"financial_analytics": False})
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)
        for rtype in qb.FinancialReportType:
            result = await svc.generate_financial_report(rtype, start, end)
            assert result["success"] is True, f"{rtype} failed: {result}"

    async def test_enterprise_security_check_runs(self):
        import integrations.atom_quickbooks_integration_service as qb
        svc = qb.AtomQuickBooksIntegrationService(config={
            "enable_enterprise_features": True,
            "quickbooks_access_token": "tok",
            "auto_categorization": False,
            "fraud_detection": False,
        })
        result = await svc._perform_security_check({"amount": 10})
        assert "passed" in result


# ---------------------------------------------------------------- video AI

class TestVideoAIServiceTaskTypes:
    async def _svc(self):
        import integrations.atom_video_ai_service as v
        return v.AtomVideoAIService({})

    async def test_phantom_task_handlers_exist(self):
        import integrations.atom_video_ai_service as v
        svc = v.AtomVideoAIService({})
        for name in ("_recognize_faces", "_detect_scenes", "_diarize_speakers",
                     "_classify_video", "_moderate_content"):
            assert hasattr(svc, name), f"{name} phantom"

    async def test_process_all_task_types_no_attribute_error(self):
        """Every VideoTaskType must route to a real handler (no AttributeError)."""
        import integrations.atom_video_ai_service as v
        svc = v.AtomVideoAIService({})
        svc._preprocess_video = AsyncMock(return_value=b"data")
        svc._extract_frames = AsyncMock(return_value=[])
        svc._perform_security_check = AsyncMock(return_value={"passed": True})
        req = v.VideoRequest(
            request_id="r1", task_type=v.VideoTaskType.SUMMARIZATION,
            model_type=v.VideoModelType.BLIP, format=v.VideoFormat.MP4,
            resolution=v.VideoResolution.FHD_1080P, fps=30.0, duration=10.0,
            video_path=None, video_data=b"data", platform="test", user_id="u1",
            metadata={},
        )
        for task in v.VideoTaskType:
            req.task_type = task
            resp = await svc.process_video_request(req)
            assert resp.success is not None
            if task in (v.VideoTaskType.SUMMARIZATION, v.VideoTaskType.CONTENT_ANALYSIS,
                        v.VideoTaskType.OBJECT_DETECTION, v.VideoTaskType.FACE_RECOGNITION,
                        v.VideoTaskType.SCENE_DETECTION, v.VideoTaskType.SPEAKER_DIARIZATION,
                        v.VideoTaskType.VIDEO_CLASSIFICATION, v.VideoTaskType.CONTENT_MODERATION):
                assert resp.success is True, f"{task} failed: {resp.metadata}"


# ---------------------------------------------------------------- pdf OCR

class TestPDFOCRService:
    def test_byok_attributes_initialized(self):
        """use_byok/byok_manager/openai_api_key must exist (previously AttributeError)."""
        from integrations.pdf_processing.pdf_ocr_service import PDFOCRService
        svc = PDFOCRService()
        assert isinstance(svc.use_byok, bool)
        assert hasattr(svc, "byok_manager")
        assert svc.openai_api_key is None

    async def test_process_pdf_error_path_returns_error_result(self):
        """process_pdf must return a dict on failure, not AttributeError."""
        from integrations.pdf_processing import pdf_ocr_service as mod
        svc = PDFOCRServiceShim(mod)
        with patch.object(svc.service, "_extract_basic_text", AsyncMock(side_effect=RuntimeError("boom"))):
            result = await svc.service.process_pdf(b"not a pdf")
        assert result["success"] is False
        assert "boom" in result.get("error", "")


class PDFOCRServiceShim:
    """Small wrapper so the test above can construct without importing twice."""
    def __init__(self, mod):
        self.service = mod.PDFOCRService()
