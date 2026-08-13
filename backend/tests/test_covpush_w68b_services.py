# -*- coding: utf-8 -*-
"""Coverage wave 68b — core/field_guide_service, core/uptime_tracker,
core/business_health_service, core/push_notification_service,
core/memory_consolidation (standalone, zero LLM spend, no network, no real DB).

- field_guide_service: line helpers (_prune_to_budget both heading forms +
  no-heading, _find_or_create_section found/found-at-end/append ±trailing-\n,
  _build_entry ±agent, _default_preamble), filesystem backend CRUD + budget/
  dedup/clear, DB backend (in-memory SQLite) _get_or_create/create/read/write/
  delete/location, service db-vs-fs init, get_field_guide_service singleton +
  db passthrough.
- uptime_tracker: zero-elapsed-total branch (start == now) → 100% uptime.
- business_health_service: db property ±_db, get_daily_priorities (leads w/
  first_name/email fallback, ai_qualification_summary ±, failed jobs, forensics
  vendor/pricing/waste, churn >0.7 / <=0.7, fraud, forensics/risk exceptions,
  AI advice present/absent-rationale/raising/None-service, db.close in finally
  only when no injected _db), get_health_metrics, simulate_decision success/
  exception with a faked AI surface (the real integrations.ai_enhanced_service
  import is absent in this environment → module attrs are None).
- push_notification_service: register_device update/update+tenant/new/
  commit-error, send_notification disabled/no-devices/android-ios-web/
  success-false/per-device token-expired vs other error/outer error/tenant
  filter, FCM v1 high+normal 200/500/legacy-key/not-configured/exception,
  APNs sandbox+prod 200/410/other/exception/data, agent-operation all statuses,
  error_alert severities, approval_request ±expires_at, system_alert all
  severities, get_push_notification_service helper.
- memory_consolidation: consolidate_all_memories success/exception,
  consolidate_tenant success/exception, _archive_old_memories (real in-memory
  SQLite; none/archived-flag-excluded/success/failure/lance-raise/tenant-falsy/
  query-error), _delete_forgotten_memories (fake session — the JSON
  metadata_json.has_key() predicate is unsupported by the model's JSONColumn on
  SQLite; none/delete+commit/per-memory-raise/query-error),
  update_importance_scores recency 7-30d / >=30d / not-updated / None-score /
  query-error, get_memory_consolidation_service helper.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import AgentMemory, AgentRegistry, FieldGuide, MobileDevice  # noqa: F401 (register models)


# ============================================================================
# Shared fixtures / helpers
# ============================================================================

@pytest.fixture()
def db():
    """In-memory SQLite session with the full schema."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_agent(db, agent_id="agent-1", tenant_id="t1"):
    agent = AgentRegistry(
        id=agent_id,
        name=agent_id,
        workspace_id="ws-1",
        tenant_id=tenant_id,
        category="Test",
        module_path="test",
        class_name="Test",
    )
    db.add(agent)
    db.commit()
    return agent


def _make_memory(db, mem_id, *, content="hello", meta=None, importance=0.5,
                 created_days=1, agent_id="agent-1", tenant_id="t1"):
    _make_agent(db, agent_id=agent_id, tenant_id=tenant_id)
    mem = AgentMemory(
        id=mem_id,
        agent_id=agent_id,
        workspace_id="ws-1",
        tenant_id=tenant_id,
        content=content,
        metadata_json=meta,
        importance_score=importance,
        access_count=0,
        created_at=datetime.now(timezone.utc) - timedelta(days=created_days),
    )
    db.add(mem)
    db.commit()
    return mem


class _SessionFactory:
    """sessionmaker substitute bound to the fixture engine (same in-memory DB)."""

    def __init__(self, db_fixture):
        self._sm = sessionmaker(bind=db_fixture.bind)

    def __call__(self, *a, **k):
        return self._sm()


def _session_patch(db_fixture):
    return patch("core.memory_consolidation.SessionLocal", side_effect=_SessionFactory(db_fixture))


class _BoomSession:
    """Session whose query() raises — exercises outer except branches."""

    def __init__(self, exc=RuntimeError("db down")):
        self._exc = exc

    def query(self, model):
        raise self._exc

    def close(self):
        pass


class _FakeQuery:
    """Minimal query double: filter/limit no-ops; all() returns injected rows."""

    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def limit(self, n):
        return self

    def all(self):
        return self._rows


class _FakeDb:
    """Full fake session for _delete_forgotten_memories (JSON has_key unsupported
    by the model's JSONColumn on SQLite, so the real predicate cannot run)."""

    def __init__(self, rows, delete_side_effect=None):
        self.rows = rows
        self.deleted = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self._delete_side_effect = delete_side_effect

    def query(self, model):
        return _FakeQuery(self.rows)

    def delete(self, m):
        if self._delete_side_effect:
            eff = (self._delete_side_effect.pop(0)
                   if isinstance(self._delete_side_effect, list)
                   else self._delete_side_effect)
            if isinstance(eff, Exception):
                raise eff
        self.deleted.append(m)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


# ============================================================================
# core/field_guide_service.py
# ============================================================================

import core.field_guide_service as fgs
from core.field_guide_service import (
    FIELD_GUIDE_MAX_LINES,
    FieldGuideService,
    _build_entry,
    _default_preamble,
    _find_or_create_section,
    _prune_to_budget,
    get_field_guide_service,
)


class TestPruneToBudget:
    def test_within_budget_unchanged(self):
        lines = ["a\n", "b\n"]
        assert _prune_to_budget(lines, 5) is lines

    def test_prunes_no_heading(self):
        lines = ["a\n", "b\n", "c\n", "d\n"]
        assert _prune_to_budget(lines, 2) == ["c\n", "d\n"]

    def test_prunes_preserving_double_hash_header(self):
        lines = ["# Title\n", "## Section\n", "a\n", "b\n", "c\n"]
        out = _prune_to_budget(lines, 3)
        assert out[0] == "# Title\n"
        assert len(out) == 3

    def test_prunes_preserving_triple_hash_header(self):
        lines = ["# Title\n", "### Topic\n", "a\n", "b\n", "c\n"]
        out = _prune_to_budget(lines, 3)
        assert out[0] == "# Title\n"
        assert len(out) == 3


class TestFindOrCreateSection:
    def test_topic_exists_followed_by_other_section(self):
        lines = ["### alpha\n", "x\n", "### beta\n", "y\n"]
        assert _find_or_create_section(lines, "alpha") == 2

    def test_topic_exists_at_end(self):
        lines = ["### alpha\n", "x\n"]
        assert _find_or_create_section(lines, "alpha") == 2

    def test_topic_absent_empty_lines(self):
        lines = []
        idx = _find_or_create_section(lines, "new")
        assert lines[idx - 1] == "### new\n"
        assert idx == len(lines)

    def test_topic_absent_without_trailing_newline(self):
        lines = ["preamble"]
        idx = _find_or_create_section(lines, "new")
        assert lines[0] == "preamble\n"
        assert idx == len(lines)

    def test_topic_absent_with_trailing_newline(self):
        lines = ["preamble\n"]
        idx = _find_or_create_section(lines, "new")
        assert lines[-1] == "### new\n"
        assert idx == len(lines)


class TestBuildEntry:
    def test_with_agent_id(self):
        e = _build_entry("  insight text  ", "agent-9")
        assert e.endswith(" [agent-9] insight text\n")

    def test_without_agent_id(self):
        e = _build_entry("insight", None)
        assert " [None]" not in e
        assert e.endswith("insight\n")

    def test_default_preamble_contains_workspace(self):
        lines = _default_preamble("ws-42")
        assert lines[0] == "# Field Guide — ws-42\n"
        assert len(lines) == 3


class TestFieldGuideServiceFs:
    def test_context_empty(self, tmp_path):
        svc = FieldGuideService(base_dir=tmp_path)
        assert svc.get_field_guide_context("ws1") == ""
        assert svc._storage == "fs"

    def test_context_with_content(self, tmp_path):
        svc = FieldGuideService(base_dir=tmp_path)
        svc.update_field_guide("ws1", "Ops", "Never touch prod")
        ctx = svc.get_field_guide_context("ws1")
        assert ctx.startswith("## 🗺 Workspace Field Guide")
        assert "Never touch prod" in ctx
        assert ctx.endswith("---\n")

    def test_get_raw_guide(self, tmp_path):
        svc = FieldGuideService(base_dir=tmp_path)
        assert svc.get_raw_guide("ws1") == ""
        svc.update_field_guide("ws1", "Ops", "rule one")
        assert "rule one" in svc.get_raw_guide("ws1")

    def test_update_creates_preamble_and_section(self, tmp_path):
        svc = FieldGuideService(base_dir=tmp_path)
        result = svc.update_field_guide("ws1", "Ops", "rule one", agent_id="a1")
        assert result["storage"] == "fs"
        assert result["lines_before"] == 0
        assert result["pruned"] is False
        assert result["lines_after"] > result["lines_before"]
        assert str(tmp_path) in result["path"]

    def test_update_appends_to_existing_section(self, tmp_path):
        svc = FieldGuideService(base_dir=tmp_path)
        svc.update_field_guide("ws1", "Ops", "rule one")
        before = svc.get_raw_guide("ws1")
        result = svc.update_field_guide("ws1", "Ops", "rule two")
        assert result["lines_before"] == len(before.splitlines())
        assert "rule two" in svc.get_raw_guide("ws1")

    def test_update_deduplicates(self, tmp_path):
        svc = FieldGuideService(base_dir=tmp_path)
        svc.update_field_guide("ws1", "Ops", "Important insight")
        before = svc.get_raw_guide("ws1")
        result = svc.update_field_guide("ws1", "Ops", "IMPORTANT INSIGHT")
        assert result["duplicate_skipped"] is True
        assert result["lines_after"] == result["lines_before"]
        assert svc.get_raw_guide("ws1") == before

    def test_update_prunes_to_budget(self, tmp_path):
        svc = FieldGuideService(base_dir=tmp_path)
        result = svc.update_field_guide("ws1", "Ops", "rule", budget=2)
        assert result["pruned"] is True
        assert result["lines_after"] <= 2

    def test_sanitizes_workspace_id_in_path(self, tmp_path):
        svc = FieldGuideService(base_dir=tmp_path)
        result = svc.update_field_guide("ws/../1", "Ops", "rule")
        assert "ws_.._1" in result["path"]

    def test_clear_guide_exists(self, tmp_path):
        svc = FieldGuideService(base_dir=tmp_path)
        svc.update_field_guide("ws1", "Ops", "rule")
        assert svc.clear_guide("ws1") is True
        assert svc.get_raw_guide("ws1") == ""

    def test_clear_guide_missing(self, tmp_path):
        svc = FieldGuideService(base_dir=tmp_path)
        assert svc.clear_guide("ws1") is False


class TestFieldGuideServiceDb:
    def test_db_backend_location(self, db):
        from core.field_guide_service import _DbBackend
        backend = _DbBackend(db)
        assert backend.location("ws1") == "db:field_guides(workspace_id=ws1)"

    def test_db_backend_get_or_create_new(self, db):
        from core.field_guide_service import _DbBackend
        backend = _DbBackend(db)
        row = backend._get_or_create("ws1")
        assert row.workspace_id == "ws1"
        assert db.query(FieldGuide).count() == 1

    def test_db_backend_get_or_create_existing(self, db):
        from core.field_guide_service import _DbBackend
        backend = _DbBackend(db)
        first = backend._get_or_create("ws1")
        second = backend._get_or_create("ws1")
        assert first is second
        assert db.query(FieldGuide).count() == 1

    def test_db_backend_read_missing(self, db):
        from core.field_guide_service import _DbBackend
        assert _DbBackend(db).read("ws1") == ""

    def test_db_backend_read_existing(self, db):
        from core.field_guide_service import _DbBackend
        backend = _DbBackend(db)
        backend.write("ws1", "content", 1)
        assert backend.read("ws1") == "content"

    def test_db_backend_write(self, db):
        from core.field_guide_service import _DbBackend
        _DbBackend(db).write("ws1", "hello world", 2)
        row = db.query(FieldGuide).filter(FieldGuide.workspace_id == "ws1").first()
        assert row.content == "hello world"
        assert row.line_count == 2

    def test_db_backend_delete_existing(self, db):
        from core.field_guide_service import _DbBackend
        backend = _DbBackend(db)
        backend.write("ws1", "x", 1)
        assert backend.delete("ws1") is True
        assert db.query(FieldGuide).count() == 0

    def test_db_backend_delete_missing(self, db):
        from core.field_guide_service import _DbBackend
        assert _DbBackend(db).delete("ws1") is False

    def test_service_db_init_and_update(self, db):
        svc = FieldGuideService(db=db)
        assert svc._storage == "db"
        result = svc.update_field_guide("ws1", "Ops", "db rule", agent_id="a1")
        assert result["storage"] == "db"
        assert result["path"] == "db:field_guides(workspace_id=ws1)"
        assert "db rule" in svc.get_field_guide_context("ws1")

    def test_service_db_raw_and_clear(self, db):
        svc = FieldGuideService(db=db)
        svc.update_field_guide("ws1", "Ops", "rule")
        assert "rule" in svc.get_raw_guide("ws1")
        assert svc.clear_guide("ws1") is True
        assert svc.get_field_guide_context("ws1") == ""


class TestGetFieldGuideService:
    def test_singleton(self):
        with patch.object(fgs, "_default_service", None):
            first = get_field_guide_service()
            assert get_field_guide_service() is first

    def test_db_passthrough_returns_fresh_instance(self, db):
        with patch.object(fgs, "_default_service", None):
            svc = get_field_guide_service(db=db)
            assert isinstance(svc, FieldGuideService)
            assert svc._storage == "db"
            assert get_field_guide_service(db=db) is not svc


# ============================================================================
# core/uptime_tracker.py — zero-elapsed-total branch
# ============================================================================

import core.uptime_tracker as ut
from core.uptime_tracker import UptimeTracker


class _FixedDatetime:
    fixed = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.fixed


class TestUptimeZeroElapsed:
    def test_zero_total_time_reports_100_percent(self):
        db = MagicMock()
        db.execute.return_value.scalar.return_value = 1
        tracker = UptimeTracker(start_time=_FixedDatetime.fixed)
        with patch.object(ut, "datetime", _FixedDatetime):
            metrics = tracker.check_health(db=db)
        assert metrics.uptime_percentage == 100.0
        assert metrics.downtime_percentage == 0.0
        assert metrics.uptime_formatted == "0s"

    def test_zero_total_time_with_downtime_history_still_100(self):
        db = MagicMock()
        db.execute.return_value.scalar.return_value = 1
        tracker = UptimeTracker(start_time=_FixedDatetime.fixed)
        event = SimpleNamespace(duration_seconds=0.0)
        tracker.downtime_events.append(event)
        with patch.object(ut, "datetime", _FixedDatetime):
            metrics = tracker.check_health(db=db)
        assert metrics.uptime_percentage == 100.0
        assert metrics.total_downtime_events == 1


# ============================================================================
# core/business_health_service.py
# ============================================================================

import core.business_health_service as bhs_mod
from core.business_health_service import BusinessHealthService

_LEAD = SimpleNamespace(
    id="L1", first_name="Alice", email="a@x.com", ai_score=90,
    ai_qualification_summary="strong fit", is_converted=False,
    workspace_id="ws1",
)
_LEAD_NO_NAME = SimpleNamespace(
    id="L2", first_name=None, email="b@x.com", ai_score=88,
    ai_qualification_summary=None, is_converted=False, workspace_id="ws1",
)
_JOB = SimpleNamespace(id="J1", agent_identifier="sales-agent", status="failed")


class _BHQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def limit(self, n):
        return self

    def all(self):
        return self._rows


def _bh_db(leads=None, jobs=None):
    db = MagicMock()
    db.query.side_effect = [_BHQuery(leads or []), _BHQuery(jobs or [])]
    return db


def _forensics(raise_factory=False):
    vendor = MagicMock()
    vendor.detect_price_drift = AsyncMock(return_value=[
        {"vendor_id": "v1", "vendor_name": "Acme", "drift_percent": 12},
    ])
    pricing = MagicMock()
    pricing.get_pricing_recommendations = AsyncMock(return_value=[
        {"sku": "SKU1", "item": "Widget", "target_price": 99},
    ])
    waste = MagicMock()
    waste.find_zombie_subscriptions = AsyncMock(return_value=[
        {"subscription_id": "s1", "service_name": "Zoom", "mrr": 20},
    ])
    return {"vendor": vendor, "pricing": pricing, "waste": waste}


def _risk(high_churn=True):
    churn = MagicMock()
    churn.predict_churn_risk = AsyncMock(return_value=[
        {"churn_probability": 0.9 if high_churn else 0.5,
         "customer_id": "c1", "customer_name": "Bob",
         "recommended_action": "call now"},
    ])
    fraud = MagicMock()
    fraud.detect_anomalies = AsyncMock(return_value=[
        {"transaction_id": "t1", "amount": 5000, "flag_reason": "odd timing"},
    ])
    return {"churn": churn, "fraud": fraud}


class _FakeTaskType:
    CONVERSATION_ANALYSIS = "conversation"
    PREDICTIVE_ANALYTICS = "predictive"


class _FakeModelType:
    GPT_4O = "gpt-4o"
    O1_MINI = "o1-mini"


class _FakeServiceType:
    OPENAI = "openai"


class _FakeAIRequest:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _patch_ai_surface(mock_service):
    return [
        patch.object(bhs_mod, "ai_enhanced_service", mock_service),
        patch.object(bhs_mod, "AIRequest", _FakeAIRequest),
        patch.object(bhs_mod, "AITaskType", _FakeTaskType),
        patch.object(bhs_mod, "AIModelType", _FakeModelType),
        patch.object(bhs_mod, "AIServiceType", _FakeServiceType),
    ]


def _run_priorities(db_mock, *, ai_service=None, forensics=None, risk=None):
    forensics_new = _forensics() if forensics is None else forensics
    risk_new = _risk() if risk is None else risk
    patches = [
        patch("core.financial_forensics.get_forensics_services", return_value=forensics_new),
        patch("core.risk_prevention.get_risk_services", return_value=risk_new),
    ]
    if ai_service is not None:
        patches += _patch_ai_surface(ai_service)
    with _CombinedPatches(patches):
        return asyncio.run(BusinessHealthService(db=db_mock).get_daily_priorities("ws1"))


class _CombinedPatches:
    def __init__(self, patches):
        self._patches = patches

    def __enter__(self):
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self._patches):
            p.stop()
        return False


class TestBusinessHealthDbProperty:
    def test_uses_injected_db(self):
        svc = BusinessHealthService(db="injected")
        assert svc.db == "injected"

    def test_falls_back_to_get_db_session(self):
        with patch("core.business_health_service.get_db_session", return_value="fresh") as g:
            svc = BusinessHealthService()
            assert svc.db == "fresh"
            g.assert_called_once_with()


class TestGetDailyPriorities:
    def test_leads_jobs_and_forensics_priorities(self):
        db = _bh_db(leads=[_LEAD, _LEAD_NO_NAME], jobs=[_JOB])
        result = _run_priorities(db)
        priorities = result["priorities"]
        types = [p["type"] for p in priorities]
        assert "GROWTH" in types
        assert "RISK" in types
        assert "STRATEGY" in types
        lead_prio = next(p for p in priorities if p["id"] == "lead_L1")
        assert lead_prio["title"] == "Follow up with Alice"
        assert "strong fit" in lead_prio["description"]
        email_lead = next(p for p in priorities if p["id"] == "lead_L2")
        assert "b@x.com" in email_lead["title"]
        assert "Extremely high conversion" in email_lead["description"]
        assert any(p["id"] == "job_J1" for p in priorities)
        assert any(p["id"] == "drift_v1" for p in priorities)
        assert any(p["id"] == "pricing_SKU1" for p in priorities)
        assert any(p["id"] == "waste_s1" for p in priorities)
        assert any(p["id"] == "churn_c1" for p in priorities)
        assert any(p["id"] == "fraud_t1" for p in priorities)
        assert result["owner_advice"] == "Focus on Sales: Your top leads represent the fastest path to revenue growth."

    def test_low_churn_risk_excluded(self):
        db = _bh_db(leads=[], jobs=[])
        result = _run_priorities(db, risk=_risk(high_churn=False))
        ids = [p["id"] for p in result["priorities"]]
        assert "churn_c1" not in ids
        assert "fraud_t1" in ids

    def test_forensics_exception_is_swallowed(self):
        db = _bh_db(leads=[_LEAD], jobs=[])
        with patch("core.financial_forensics.get_forensics_services",
                   side_effect=RuntimeError("forensics down")):
            with patch("core.risk_prevention.get_risk_services", return_value=_risk()):
                result = asyncio.run(
                    BusinessHealthService(db=db).get_daily_priorities("ws1")
                )
        ids = [p["id"] for p in result["priorities"]]
        assert "drift_v1" not in ids
        assert "lead_L1" in ids

    def test_risk_exception_is_swallowed(self):
        db = _bh_db(leads=[], jobs=[])
        with patch("core.financial_forensics.get_forensics_services", return_value=_forensics()):
            with patch("core.risk_prevention.get_risk_services",
                       side_effect=RuntimeError("risk down")):
                result = asyncio.run(
                    BusinessHealthService(db=db).get_daily_priorities("ws1")
                )
        ids = [p["id"] for p in result["priorities"]]
        assert "churn_c1" not in ids

    def test_ai_advice_from_rationale(self):
        db = _bh_db(leads=[], jobs=[])
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(output_data={"rationale": "Hire a CFO"})
        )
        result = _run_priorities(db, ai_service=ai)
        assert result["owner_advice"] == "Hire a CFO"

    def test_ai_advice_default_when_no_rationale(self):
        db = _bh_db(leads=[], jobs=[])
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(output_data={"other": "x"})
        )
        result = _run_priorities(db, ai_service=ai)
        assert result["owner_advice"].startswith("Focus on Sales")

    def test_ai_advice_default_when_ai_raises(self):
        db = _bh_db(leads=[], jobs=[])
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError("llm down"))
        result = _run_priorities(db, ai_service=ai)
        assert result["owner_advice"].startswith("Focus on Sales")

    def test_ai_service_absent_uses_default_advice(self):
        db = _bh_db(leads=[], jobs=[])
        result = _run_priorities(db, ai_service=None)
        assert result["owner_advice"].startswith("Focus on Sales")

    def test_db_closed_when_no_injected_db(self):
        with patch("core.business_health_service.get_db_session") as g:
            db = _bh_db(leads=[], jobs=[])
            g.return_value = db
            with patch("core.financial_forensics.get_forensics_services",
                       return_value=_forensics()):
                with patch("core.risk_prevention.get_risk_services", return_value=_risk()):
                    asyncio.run(BusinessHealthService().get_daily_priorities("ws1"))
        db.close.assert_called_once_with()

    def test_db_not_closed_when_injected(self):
        db = _bh_db(leads=[], jobs=[])
        with patch("core.financial_forensics.get_forensics_services",
                   return_value=_forensics()):
            with patch("core.risk_prevention.get_risk_services", return_value=_risk()):
                asyncio.run(BusinessHealthService(db=db).get_daily_priorities("ws1"))
        db.close.assert_not_called()


class TestGetHealthMetrics:
    def test_returns_dashboard_grid(self):
        metrics = BusinessHealthService().get_health_metrics("ws1")
        assert set(metrics) == {"cash_runway", "lead_velocity", "active_deals", "churn_risk"}
        assert metrics["cash_runway"]["status"] == "warning"


class TestSimulateDecision:
    def test_success_returns_output_data(self):
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(output_data={"prediction": "profit"})
        )
        with _CombinedPatches(_patch_ai_surface(ai)):
            result = asyncio.run(
                BusinessHealthService().simulate_decision("ws1", "HIRING", {"n": 1})
            )
        assert result == {"prediction": "profit"}
        ai.process_ai_request.assert_awaited_once()

    def test_exception_returns_error_dict(self):
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError("llm down"))
        with _CombinedPatches(_patch_ai_surface(ai)):
            result = asyncio.run(
                BusinessHealthService().simulate_decision("ws1", "CAPEX", {})
            )
        assert result["error"] == "llm down"
        assert "Simulation failed" in result["prediction"]


# ============================================================================
# core/push_notification_service.py
# ============================================================================

import core.push_notification_service as pns
from core.push_notification_service import (
    PushNotificationService,
    get_push_notification_service,
)


def _device(db, user_id="u1", token="tok-1", platform="android", status="active", tenant_id=None):
    dev = MobileDevice(
        id=token,
        user_id=user_id,
        tenant_id=tenant_id,
        device_token=token,
        platform=platform,
        status=status,
        device_info={},
    )
    db.add(dev)
    db.commit()
    return dev


def _http_response(status_code, text="ok"):
    return SimpleNamespace(status_code=status_code, text=text)


def _patch_httpx(response=None, exc=None):
    client = MagicMock()
    if exc is not None:
        client.post = AsyncMock(side_effect=exc)
    else:
        client.post = AsyncMock(return_value=response)
    client.__aenter__.return_value = client
    return patch("httpx.AsyncClient", return_value=client)


class TestRegisterDevice:
    def test_new_device(self, db):
        svc = PushNotificationService(db, workspace_id="ws1", tenant_id="t1")
        result = asyncio.run(svc.register_device("u1", "tok-new", "android", {"model": "X"}))
        assert result["status"] == "registered"
        assert result["platform"] == "android"
        assert db.query(MobileDevice).count() == 1

    def test_new_device_no_tenant(self, db):
        svc = PushNotificationService(db)
        result = asyncio.run(svc.register_device("u1", "tok-new", "web"))
        assert result["status"] == "registered"
        assert result["device_id"]

    def test_update_existing_device(self, db):
        dev = _device(db)
        svc = PushNotificationService(db, workspace_id="ws1")
        result = asyncio.run(svc.register_device("u1", "tok-1", "ios", {"os": "17"}))
        assert result["status"] == "updated"
        assert result["device_id"] == "tok-1"
        db.refresh(dev)
        assert dev.platform == "ios"
        assert dev.status == "active"

    def test_update_existing_with_tenant_override(self, db):
        dev = _device(db, tenant_id="old-tenant")
        svc = PushNotificationService(db, workspace_id="ws1")
        result = asyncio.run(svc.register_device("u1", "tok-1", "ios", tenant_id="new-tenant"))
        assert result["status"] == "updated"
        db.refresh(dev)
        assert dev.tenant_id == "new-tenant"

    def test_update_existing_keeps_tenant_when_no_override(self, db):
        dev = _device(db, tenant_id="old-tenant")
        svc = PushNotificationService(db)
        asyncio.run(svc.register_device("u1", "tok-1", "ios"))
        db.refresh(dev)
        assert dev.tenant_id == "old-tenant"

    def test_commit_error_returns_error(self, db):
        _device(db)
        svc = PushNotificationService(db)
        with patch.object(svc.db, "commit", side_effect=RuntimeError("db down")):
            result = asyncio.run(svc.register_device("u1", "tok-1", "ios"))
        assert result["status"] == "error"
        assert result["error"] == "db down"


class TestSendNotification:
    def test_disabled_flag(self, db):
        _device(db)
        svc = PushNotificationService(db)
        with patch.object(pns, "PUSH_NOTIFICATIONS_ENABLED", False):
            assert asyncio.run(svc.send_notification("u1", "t", "title", "body")) is False

    def test_no_devices(self, db):
        svc = PushNotificationService(db)
        assert asyncio.run(svc.send_notification("u1", "t", "title", "body")) is False

    def test_android_success(self, db):
        _device(db, token="tok-1", platform="android")
        svc = PushNotificationService(db, workspace_id="ws1", tenant_id="t1")
        with patch.object(
            pns.PushNotificationService, "_send_fcm_notification",
            new=AsyncMock(return_value=True),
        ):
            assert asyncio.run(
                svc.send_notification("u1", "t", "title", "body", {"k": "v"}, priority="high")
            ) is True

    def test_ios_success(self, db):
        _device(db, token="tok-1", platform="ios")
        svc = PushNotificationService(db, workspace_id="ws1")
        with patch.object(
            pns.PushNotificationService, "_send_apns_notification",
            new=AsyncMock(return_value=True),
        ):
            assert asyncio.run(svc.send_notification("u1", "t", "title", "body")) is True

    def test_unsupported_platform_skipped(self, db):
        _device(db, token="tok-1", platform="web")
        _device(db, token="tok-2", platform="android")
        svc = PushNotificationService(db)
        with patch.object(
            pns.PushNotificationService, "_send_fcm_notification",
            new=AsyncMock(return_value=True),
        ):
            assert asyncio.run(svc.send_notification("u1", "t", "title", "body")) is True

    def test_send_failure_returns_false_when_none_sent(self, db):
        _device(db, token="tok-1", platform="android")
        svc = PushNotificationService(db)
        with patch.object(
            pns.PushNotificationService, "_send_fcm_notification",
            new=AsyncMock(return_value=False),
        ):
            assert asyncio.run(svc.send_notification("u1", "t", "title", "body")) is False

    def test_tenant_filter_applied(self, db):
        _device(db, token="tok-1", platform="android", tenant_id="t1")
        _device(db, token="tok-2", platform="android", tenant_id="t2")
        svc = PushNotificationService(db, tenant_id="t1")
        with patch.object(
            pns.PushNotificationService, "_send_fcm_notification",
            new=AsyncMock(return_value=True),
        ) as fcm:
            assert asyncio.run(svc.send_notification("u1", "t", "title", "body")) is True
        assert fcm.await_count == 1

    def test_token_expired_marks_device_inactive(self, db):
        dev = _device(db, token="tok-1", platform="android")
        svc = PushNotificationService(db)
        with patch.object(
            pns.PushNotificationService, "_send_fcm_notification",
            new=AsyncMock(side_effect=RuntimeError("token expired")),
        ):
            assert asyncio.run(svc.send_notification("u1", "t", "title", "body")) is False
        db.refresh(dev)
        assert dev.status == "inactive"

    def test_unregistered_marks_device_inactive(self, db):
        dev = _device(db, token="tok-1", platform="android")
        svc = PushNotificationService(db)
        with patch.object(
            pns.PushNotificationService, "_send_fcm_notification",
            new=AsyncMock(side_effect=RuntimeError("device unregistered")),
        ):
            asyncio.run(svc.send_notification("u1", "t", "title", "body"))
        db.refresh(dev)
        assert dev.status == "inactive"

    def test_other_device_error_keeps_active(self, db):
        dev = _device(db, token="tok-1", platform="android")
        svc = PushNotificationService(db)
        with patch.object(
            pns.PushNotificationService, "_send_fcm_notification",
            new=AsyncMock(side_effect=RuntimeError("network down")),
        ):
            asyncio.run(svc.send_notification("u1", "t", "title", "body"))
        db.refresh(dev)
        assert dev.status == "active"

    def test_outer_error_returns_false(self, db):
        _device(db)
        svc = PushNotificationService(db)
        with patch.object(svc.db, "query", side_effect=RuntimeError("db down")):
            assert asyncio.run(svc.send_notification("u1", "t", "title", "body")) is False


class TestFcmNotification:
    def test_v1_success_high_priority(self, db, monkeypatch):
        monkeypatch.setenv("FCM_PROJECT_ID", "proj-1")
        monkeypatch.setenv("FCM_ACCESS_TOKEN", "tok")
        svc = PushNotificationService(db)
        device = SimpleNamespace(id="d1", device_token="dev-tok")
        with _patch_httpx(_http_response(200)) as ac:
            result = asyncio.run(svc._send_fcm_notification(device, "T", "B", {"k": "v"}, "high"))
        assert result is True
        payload = ac.return_value.post.await_args.kwargs["json"]
        assert payload["message"]["android"]["priority"] == "high"
        assert payload["message"]["token"] == "dev-tok"

    def test_v1_success_normal_priority(self, db, monkeypatch):
        monkeypatch.setenv("FCM_PROJECT_ID", "proj-1")
        monkeypatch.setenv("FCM_ACCESS_TOKEN", "tok")
        svc = PushNotificationService(db)
        device = SimpleNamespace(id="d1", device_token="dev-tok")
        with _patch_httpx(_http_response(200)) as ac:
            result = asyncio.run(svc._send_fcm_notification(device, "T", "B", None, "normal"))
        assert result is True
        payload = ac.return_value.post.await_args.kwargs["json"]
        assert "android" not in payload["message"]

    def test_v1_error_status(self, db, monkeypatch):
        monkeypatch.setenv("FCM_PROJECT_ID", "proj-1")
        monkeypatch.setenv("FCM_ACCESS_TOKEN", "tok")
        svc = PushNotificationService(db)
        device = SimpleNamespace(id="d1", device_token="dev-tok")
        with _patch_httpx(_http_response(500, text="boom")):
            assert asyncio.run(
                svc._send_fcm_notification(device, "T", "B", None, "normal")
            ) is False

    def test_v1_exception(self, db, monkeypatch):
        monkeypatch.setenv("FCM_PROJECT_ID", "proj-1")
        monkeypatch.setenv("FCM_ACCESS_TOKEN", "tok")
        svc = PushNotificationService(db)
        device = SimpleNamespace(id="d1", device_token="dev-tok")
        with _patch_httpx(exc=RuntimeError("timeout")):
            assert asyncio.run(
                svc._send_fcm_notification(device, "T", "B", None, "normal")
            ) is False

    def test_legacy_key_warns_and_skips(self, db, monkeypatch):
        monkeypatch.delenv("FCM_PROJECT_ID", raising=False)
        monkeypatch.delenv("FCM_ACCESS_TOKEN", raising=False)
        svc = PushNotificationService(db)
        device = SimpleNamespace(id="d1", device_token="dev-tok")
        with patch.object(pns, "FCM_SERVER_KEY", "legacy-key"):
            assert asyncio.run(
                svc._send_fcm_notification(device, "T", "B", None, "normal")
            ) is False

    def test_not_configured(self, db, monkeypatch):
        monkeypatch.delenv("FCM_PROJECT_ID", raising=False)
        monkeypatch.delenv("FCM_ACCESS_TOKEN", raising=False)
        svc = PushNotificationService(db)
        device = SimpleNamespace(id="d1", device_token="dev-tok")
        with patch.object(pns, "FCM_SERVER_KEY", None):
            assert asyncio.run(
                svc._send_fcm_notification(device, "T", "B", None, "normal")
            ) is False


class TestApnsNotification:
    def test_sandbox_success(self, db, monkeypatch):
        monkeypatch.setenv("APNS_USE_SANDBOX", "true")
        svc = PushNotificationService(db)
        device = SimpleNamespace(id="d1", device_token="dev-tok")
        with _patch_httpx(_http_response(200)) as ac:
            result = asyncio.run(svc._send_apns_notification(device, "T", "B", {"k": "v"}, "high"))
        assert result is True
        url = ac.return_value.post.await_args.args[0]
        assert url.startswith("https://api.sandbox.push.apple.com/3/device/")
        payload = ac.return_value.post.await_args.kwargs["json"]
        assert payload["custom_data"] == {"k": "v"}
        assert payload["aps"]["sound"] == "default"

    def test_prod_normal_priority_sound_none(self, db, monkeypatch):
        monkeypatch.delenv("APNS_USE_SANDBOX", raising=False)
        svc = PushNotificationService(db)
        device = SimpleNamespace(id="d1", device_token="dev-tok")
        with _patch_httpx(_http_response(200)) as ac:
            assert asyncio.run(
                svc._send_apns_notification(device, "T", "B", None, "normal")
            ) is True
        url = ac.return_value.post.await_args.args[0]
        assert url.startswith("https://api.push.apple.com/3/device/")

    def test_token_expired_410(self, db):
        svc = PushNotificationService(db)
        device = SimpleNamespace(id="d1", device_token="dev-tok")
        with _patch_httpx(_http_response(410)):
            assert asyncio.run(
                svc._send_apns_notification(device, "T", "B", None, "normal")
            ) is False

    def test_other_status(self, db):
        svc = PushNotificationService(db)
        device = SimpleNamespace(id="d1", device_token="dev-tok")
        with _patch_httpx(_http_response(503)):
            assert asyncio.run(
                svc._send_apns_notification(device, "T", "B", None, "normal")
            ) is False

    def test_exception(self, db):
        svc = PushNotificationService(db)
        device = SimpleNamespace(id="d1", device_token="dev-tok")
        with _patch_httpx(exc=RuntimeError("timeout")):
            assert asyncio.run(
                svc._send_apns_notification(device, "T", "B", None, "normal")
            ) is False


class TestNotificationVariants:
    def _svc(self, db):
        return PushNotificationService(db)

    def test_agent_operation_completed(self, db):
        svc = self._svc(db)
        with patch.object(svc, "send_notification", new=AsyncMock(return_value=True)) as sn:
            assert asyncio.run(svc.send_agent_operation_notification(
                "u1", "Agent", "analysis", "completed")) is True
        kwargs = sn.await_args.kwargs
        assert kwargs["title"] == "✅ Agent Completed"
        assert kwargs["body"] == "Successfully completed analysis"
        assert kwargs["notification_type"] == "agent_operation"

    def test_agent_operation_failed(self, db):
        svc = self._svc(db)
        with patch.object(svc, "send_notification", new=AsyncMock(return_value=True)) as sn:
            asyncio.run(svc.send_agent_operation_notification(
                "u1", "Agent", "analysis", "failed"))
        assert sn.await_args.kwargs["title"] == "❌ Agent Failed"

    def test_agent_operation_awaiting_approval(self, db):
        svc = self._svc(db)
        with patch.object(svc, "send_notification", new=AsyncMock(return_value=True)) as sn:
            asyncio.run(svc.send_agent_operation_notification(
                "u1", "Agent", "analysis", "awaiting_approval"))
        assert sn.await_args.kwargs["title"] == "⏸️ Awaiting Approval"

    def test_agent_operation_other_status_with_context(self, db):
        svc = self._svc(db)
        with patch.object(svc, "send_notification", new=AsyncMock(return_value=True)) as sn:
            asyncio.run(svc.send_agent_operation_notification(
                "u1", "Agent", "analysis", "running", context="halfway"))
        kwargs = sn.await_args.kwargs
        assert kwargs["title"] == "ℹ️ Agent Update"
        assert "halfway" in kwargs["body"]

    def test_agent_operation_other_status_no_context(self, db):
        svc = self._svc(db)
        with patch.object(svc, "send_notification", new=AsyncMock(return_value=True)) as sn:
            asyncio.run(svc.send_agent_operation_notification(
                "u1", "Agent", "analysis", "running"))
        assert "analysis" in sn.await_args.kwargs["body"]

    def test_error_alert_warning(self, db):
        svc = self._svc(db)
        with patch.object(svc, "send_notification", new=AsyncMock(return_value=True)) as sn:
            asyncio.run(svc.send_error_alert("u1", "INTEGRATION", "failed"))
        kwargs = sn.await_args.kwargs
        assert kwargs["title"] == "⚠️ Error: INTEGRATION"
        assert kwargs["priority"] == "high"

    def test_error_alert_critical(self, db):
        svc = self._svc(db)
        with patch.object(svc, "send_notification", new=AsyncMock(return_value=True)) as sn:
            asyncio.run(svc.send_error_alert("u1", "SYSTEM", "boom", severity="critical"))
        assert sn.await_args.kwargs["title"] == "🚨 Critical: SYSTEM"

    def test_error_alert_info_normal_priority(self, db):
        svc = self._svc(db)
        with patch.object(svc, "send_notification", new=AsyncMock(return_value=True)) as sn:
            asyncio.run(svc.send_error_alert("u1", "SYSTEM", "info", severity="info"))
        assert sn.await_args.kwargs["priority"] == "normal"

    def test_approval_request_no_expiry(self, db):
        svc = self._svc(db)
        with patch.object(svc, "send_notification", new=AsyncMock(return_value=True)) as sn:
            asyncio.run(svc.send_approval_request(
                "u1", "ag1", "Agent", "delete file", [{"label": "Approve"}]))
        kwargs = sn.await_args.kwargs
        assert kwargs["title"] == "🔔 Approval Required"
        assert kwargs["priority"] == "high"
        assert kwargs["data"]["expires_at"] is None

    def test_approval_request_with_expiry(self, db):
        svc = self._svc(db)
        expiry = datetime(2026, 2, 1, tzinfo=timezone.utc)
        with patch.object(svc, "send_notification", new=AsyncMock(return_value=True)) as sn:
            asyncio.run(svc.send_approval_request(
                "u1", "ag1", "Agent", "delete file", [], expires_at=expiry))
        assert sn.await_args.kwargs["data"]["expires_at"] == expiry.isoformat()

    def test_system_alert_critical(self, db):
        svc = self._svc(db)
        with patch.object(svc, "send_notification", new=AsyncMock(return_value=True)) as sn:
            asyncio.run(svc.send_system_alert("u1", "CPU", "high", severity="critical"))
        kwargs = sn.await_args.kwargs
        assert kwargs["title"] == "🚨 Critical Alert"
        assert kwargs["priority"] == "high"

    def test_system_alert_warning(self, db):
        svc = self._svc(db)
        with patch.object(svc, "send_notification", new=AsyncMock(return_value=True)) as sn:
            asyncio.run(svc.send_system_alert("u1", "CPU", "high", severity="warning"))
        assert sn.await_args.kwargs["title"] == "⚠️ Warning"

    def test_system_alert_info(self, db):
        svc = self._svc(db)
        with patch.object(svc, "send_notification", new=AsyncMock(return_value=True)) as sn:
            asyncio.run(svc.send_system_alert("u1", "CPU", "ok"))
        kwargs = sn.await_args.kwargs
        assert kwargs["title"] == "ℹ️ Info"
        assert kwargs["priority"] == "normal"


class TestGetPushNotificationService:
    def test_returns_instance(self, db):
        svc = get_push_notification_service(db)
        assert isinstance(svc, PushNotificationService)
        assert svc.db is db


# ============================================================================
# core/memory_consolidation.py
# ============================================================================

from core.memory_consolidation import (
    MemoryConsolidationService,
    get_memory_consolidation_service,
    memory_consolidation_service,
)


class TestConsolidateAllMemories:
    def test_success_adds_duration_and_last_run(self):
        svc = MemoryConsolidationService(workspace_id="ws-1", tenant_id="t1")
        svc.consolidate_tenant = AsyncMock(
            return_value={"tenant_id": "t1", "memories_archived": 2,
                          "memories_deleted": 1, "errors": []}
        )
        result = asyncio.run(svc.consolidate_all_memories())
        assert result["memories_archived"] == 2
        assert isinstance(result["duration_seconds"], float)
        assert isinstance(result["last_run"], str)

    def test_exception_returns_error_dict(self):
        svc = MemoryConsolidationService()
        svc.consolidate_tenant = AsyncMock(side_effect=RuntimeError("boom"))
        result = asyncio.run(svc.consolidate_all_memories())
        assert result["status"] == "error"
        assert "boom" in result["error"]


class TestConsolidateTenant:
    def test_success_counts(self):
        svc = MemoryConsolidationService()
        svc._archive_old_memories = AsyncMock(return_value=3)
        svc._delete_forgotten_memories = AsyncMock(return_value=2)
        result = asyncio.run(svc.consolidate_tenant("t1"))
        assert result == {"tenant_id": "t1", "memories_archived": 3,
                          "memories_deleted": 2, "errors": []}

    def test_exception_records_error(self):
        svc = MemoryConsolidationService()
        svc._archive_old_memories = AsyncMock(side_effect=RuntimeError("arch fail"))
        result = asyncio.run(svc.consolidate_tenant("t1"))
        assert result["memories_archived"] == 0
        assert len(result["errors"]) == 1
        assert "arch fail" in result["errors"][0]


class TestArchiveOldMemories:
    def test_no_old_memories(self, db):
        _make_memory(db, "m1", created_days=1)
        svc = MemoryConsolidationService(workspace_id="ws-1", tenant_id="t1")
        with _session_patch(db), patch("core.memory_consolidation.get_lancedb_handler") as lh:
            assert asyncio.run(svc._archive_old_memories("t1")) == 0
        lh.assert_not_called()

    def test_archived_flag_memories_excluded(self, db):
        _make_memory(db, "m1", meta={"_archived": "true"}, created_days=10)
        svc = MemoryConsolidationService(workspace_id="ws-1", tenant_id="t1")
        with _session_patch(db), patch("core.memory_consolidation.get_lancedb_handler") as lh:
            assert asyncio.run(svc._archive_old_memories("t1")) == 0
        lh.assert_not_called()

    def test_archives_and_marks(self, db):
        _make_memory(db, "m1", content="old fact", meta=None, created_days=10)
        lancedb = MagicMock()
        lancedb.add_document = AsyncMock(return_value=True)
        svc = MemoryConsolidationService(workspace_id="ws-1", tenant_id="t1")
        with _session_patch(db), patch("core.memory_consolidation.get_lancedb_handler",
                                       return_value=lancedb):
            assert asyncio.run(svc._archive_old_memories("t1")) == 1
        lancedb.add_document.assert_awaited_once()
        refreshed = db.query(AgentMemory).filter(AgentMemory.id == "m1").first()
        assert refreshed.metadata_json["_archived"] == "true"
        assert "_archived_at" in refreshed.metadata_json

    def test_add_document_false_does_not_count(self, db):
        _make_memory(db, "m1", meta={}, created_days=10)
        lancedb = MagicMock()
        lancedb.add_document = AsyncMock(return_value=False)
        svc = MemoryConsolidationService(workspace_id="ws-1", tenant_id="t1")
        with _session_patch(db), patch("core.memory_consolidation.get_lancedb_handler",
                                       return_value=lancedb):
            assert asyncio.run(svc._archive_old_memories("t1")) == 0
        refreshed = db.query(AgentMemory).filter(AgentMemory.id == "m1").first()
        assert "_archived" not in (refreshed.metadata_json or {})

    def test_add_document_raise_rolls_back(self, db):
        _make_memory(db, "m1", meta={}, created_days=10)
        lancedb = MagicMock()
        lancedb.add_document = AsyncMock(side_effect=RuntimeError("lance down"))
        svc = MemoryConsolidationService(workspace_id="ws-1", tenant_id="t1")
        with _session_patch(db), patch("core.memory_consolidation.get_lancedb_handler",
                                       return_value=lancedb):
            assert asyncio.run(svc._archive_old_memories("t1")) == 0

    def test_tenant_id_falsy_skips_filter(self, db):
        _make_memory(db, "m1", content="old", meta=None, created_days=10)
        lancedb = MagicMock()
        lancedb.add_document = AsyncMock(return_value=True)
        svc = MemoryConsolidationService(workspace_id="ws-1", tenant_id="t1")
        with _session_patch(db), patch("core.memory_consolidation.get_lancedb_handler",
                                       return_value=lancedb):
            assert asyncio.run(svc._archive_old_memories("")) == 1

    def test_query_error_returns_zero(self, db):
        svc = MemoryConsolidationService(workspace_id="ws-1", tenant_id="t1")
        with patch("core.memory_consolidation.SessionLocal", return_value=_BoomSession()):
            assert asyncio.run(svc._archive_old_memories("t1")) == 0


class TestDeleteForgottenMemories:
    def _run(self, svc, fake_db):
        with patch("core.memory_consolidation.SessionLocal", return_value=fake_db):
            return asyncio.run(svc._delete_forgotten_memories("t1"))

    def test_no_forgotten_memories(self):
        svc = MemoryConsolidationService(workspace_id="ws-1", tenant_id="t1")
        fake = _FakeDb(rows=[])
        assert self._run(svc, fake) == 0
        assert fake.closed is True

    def test_deletes_and_commits(self):
        rows = [SimpleNamespace(id="m1", importance_score=0.1),
                SimpleNamespace(id="m2", importance_score=0.05)]
        svc = MemoryConsolidationService(workspace_id="ws-1", tenant_id="t1")
        fake = _FakeDb(rows=rows)
        assert self._run(svc, fake) == 2
        assert [m.id for m in fake.deleted] == ["m1", "m2"]
        assert fake.commits == 2

    def test_per_memory_error_rolls_back_and_continues(self):
        rows = [SimpleNamespace(id="m1", importance_score=0.1),
                SimpleNamespace(id="m2", importance_score=0.05)]
        svc = MemoryConsolidationService(workspace_id="ws-1", tenant_id="t1")
        fake = _FakeDb(rows=rows, delete_side_effect=[RuntimeError("db down"), None])
        assert self._run(svc, fake) == 1
        assert fake.deleted == ["m2"]
        assert fake.rollbacks == 1

    def test_query_error_returns_zero(self):
        svc = MemoryConsolidationService(workspace_id="ws-1", tenant_id="t1")
        with patch("core.memory_consolidation.SessionLocal",
                   return_value=_BoomSession(RuntimeError("query exploded"))):
            assert asyncio.run(svc._delete_forgotten_memories("t1")) == 0


class TestUpdateImportanceScores:
    def test_recency_boost_between_7_and_30_days(self, db):
        _make_agent(db)
        mem = AgentMemory(
            id="m1", agent_id="agent-1", workspace_id="ws-1", tenant_id="t1",
            content="x", importance_score=0.5, access_count=0,
            last_accessed_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        db.add(mem)
        db.commit()
        svc = MemoryConsolidationService(workspace_id="ws-1", tenant_id="t1")
        with _session_patch(db):
            assert svc.update_importance_scores("t1") == 1
        refreshed = db.query(AgentMemory).filter(AgentMemory.id == "m1").first()
        assert refreshed.importance_score == pytest.approx(0.6, abs=1e-6)

    def test_no_recency_boost_after_30_days(self, db):
        _make_agent(db)
        mem = AgentMemory(
            id="m1", agent_id="agent-1", workspace_id="ws-1", tenant_id="t1",
            content="x", importance_score=0.5, access_count=0,
            last_accessed_at=datetime.now(timezone.utc) - timedelta(days=60),
        )
        db.add(mem)
        db.commit()
        svc = MemoryConsolidationService(workspace_id="ws-1", tenant_id="t1")
        with _session_patch(db):
            assert svc.update_importance_scores("t1") == 0

    def test_score_unchanged_within_tolerance_not_updated(self, db):
        _make_agent(db)
        mem = AgentMemory(
            id="m1", agent_id="agent-1", workspace_id="ws-1", tenant_id="t1",
            content="x", importance_score=0.5, access_count=0,
            last_accessed_at=datetime.now(timezone.utc) - timedelta(days=60),
        )
        db.add(mem)
        db.commit()
        svc = MemoryConsolidationService(workspace_id="ws-1", tenant_id="t1")
        with _session_patch(db):
            assert svc.update_importance_scores("t1") == 0
        refreshed = db.query(AgentMemory).filter(AgentMemory.id == "m1").first()
        assert refreshed.importance_score == pytest.approx(0.5, abs=1e-6)

    def test_null_importance_score_uses_base(self, db):
        _make_agent(db)
        mem = AgentMemory(
            id="m1", agent_id="agent-1", workspace_id="ws-1", tenant_id="t1",
            content="x", importance_score=None, access_count=0,
            last_accessed_at=datetime.now(timezone.utc) - timedelta(days=60),
        )
        db.add(mem)
        db.commit()
        svc = MemoryConsolidationService(workspace_id="ws-1", tenant_id="t1")
        with _session_patch(db):
            assert svc.update_importance_scores("t1") == 0

    def test_query_error_returns_zero(self):
        svc = MemoryConsolidationService(workspace_id="ws-1", tenant_id="t1")
        with patch("core.memory_consolidation.SessionLocal", return_value=_BoomSession()):
            assert svc.update_importance_scores("t1") == 0


class TestServiceHelper:
    def test_get_memory_consolidation_service_singleton(self):
        assert get_memory_consolidation_service() is memory_consolidation_service
        assert memory_consolidation_service.consolidation_stats["memories_archived"] == 0
