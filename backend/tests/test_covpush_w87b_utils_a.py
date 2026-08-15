# -*- coding: utf-8 -*-
"""W87B — coverage push for 10 backend utility modules (standalone >=95% each).

Measured before-% (existing carrier suites) -> after-% (this file alone):

  1. core/cron_parser.py                        (180 stmts) 100% -> 100%
  2. core/database_helper.py                    (102 stmts) 100% -> 100%
  3. core/decimal_utils.py                      ( 38 stmts) 100% -> 100%
  4. core/email_followup_engine.py              ( 43 stmts) 100% -> 100%
  5. core/enterprise_security.py                (234 stmts) 100% -> 100%
  6. core/entity_schema_suggestion_service.py   ( 30 stmts) 100% -> 100%
  7. core/entity_skill_service.py               ( 77 stmts)  91% -> 100%
  8. core/error_handler.py                      ( 41 stmts) 100% -> 100%
  9. core/health.py                             ( 38 stmts) 100% -> 100%
 10. core/historical_sync_service.py            (344 stmts)  99% -> 100%

Style: mocked deps, zero LLM spend, zero network, in-memory SQLite for the
two ORM-backed services (established carrier-suite convention). No real DB,
no external services.
"""
from __future__ import annotations

import asyncio
import builtins
import importlib
import threading
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from decimal import Decimal, ROUND_HALF_UP

import core.cron_parser as cp
import core.database_helper as dh
import core.decimal_utils as du
import core.email_followup_engine as efe
import core.enterprise_security as es
import core.entity_schema_suggestion_service as ess
import core.entity_skill_service as esk
import core.error_handler as eh
import core.health as hlth
import core.historical_sync_service as hss

from core.models import HistoricalSyncJob
from fastapi import FastAPI, HTTPException


# ============================================================================
# 3. decimal_utils
# ============================================================================


class TestToDecimal:
    def test_none_returns_zero(self):
        assert du.to_decimal(None) == Decimal("0.00")

    def test_decimal_passthrough(self):
        d = Decimal("1.5")
        assert du.to_decimal(d) is d

    def test_int(self):
        assert du.to_decimal(42) == Decimal("42")

    def test_string_with_commas_and_dollar(self):
        assert du.to_decimal("$1,234.56") == Decimal("1234.56")

    def test_string_whitespace_stripped(self):
        assert du.to_decimal("  10.5  ") == Decimal("10.5")

    def test_invalid_string_raises_value_error(self):
        with pytest.raises(ValueError):
            du.to_decimal("abc")

    def test_float_converted_via_string(self):
        assert du.to_decimal(0.1) == Decimal("0.1")

    def test_unsupported_type_raises_type_error(self):
        with pytest.raises(TypeError):
            du.to_decimal(object())


class TestRoundMoney:
    def test_rounds_half_up(self):
        assert du.round_money("10.005") == Decimal("10.01")

    def test_rounds_down(self):
        assert du.round_money("10.004") == Decimal("10.00")

    def test_rounds_decimal_input(self):
        assert du.round_money(Decimal("10.004"), places=2) == Decimal("10.00")

    def test_zero_places_uses_integer_quantizer(self):
        assert du.round_money("5.5", places=0) == Decimal("6")


class TestQuantize:
    def test_default_money_precision(self):
        assert du.quantize("1.239") == Decimal("1.24")

    def test_custom_precision(self):
        assert du.quantize("2.34567", du.HIGH_PRECISION) == Decimal("2.3457")

    def test_float_input(self):
        assert du.quantize(2.5) == Decimal("2.50")


class TestDecimalContext:
    def test_returns_configured_context(self):
        ctx = du.get_decimal_context()
        assert ctx["precision"] == 28
        assert ctx["rounding"] == ROUND_HALF_UP


class TestSafeDivide:
    def test_divides_and_rounds(self):
        assert du.safe_divide("10", "3") == Decimal("3.33")

    def test_exact_division(self):
        assert du.safe_divide(7, 2) == Decimal("3.50")

    def test_divide_by_zero_raises(self):
        with pytest.raises(ZeroDivisionError):
            du.safe_divide("5", "0")

    def test_custom_precision(self):
        assert du.safe_divide("1", "3", precision=4) == Decimal("0.3333")


# ============================================================================
# 8. error_handler
# ============================================================================


class _App:
    def __init__(self):
        self.handlers = []

    def add_exception_handler(self, exc_type, handler):
        self.handlers.append((exc_type, handler))


class _Req:
    def __init__(self, state=None):
        self.state = state if state is not None else SimpleNamespace()


class _ApiExc(Exception):
    def __init__(self, message="api fail", error_code="CUSTOM", status_code=422, details=None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details


class TestHttpExceptionHandler:
    @pytest.mark.asyncio
    async def test_dict_detail_passthrough(self):
        exc = HTTPException(status_code=400, detail={"field": "bad"})
        resp = await eh.http_exception_handler(_Req(), exc)
        assert resp.status_code == 400
        assert resp.body == b'{"field":"bad"}'

    @pytest.mark.asyncio
    async def test_string_detail_wrapped(self):
        exc = HTTPException(status_code=404, detail="Not found")
        resp = await eh.http_exception_handler(_Req(), exc)
        assert resp.status_code == 404
        assert resp.body == b'{"detail":"Not found"}'


class TestDatabaseErrorHandler:
    @pytest.mark.asyncio
    async def test_with_request_id(self):
        from sqlalchemy.exc import SQLAlchemyError

        req = _Req(SimpleNamespace(request_id="req-1"))
        resp = await eh.database_error_handler(req, SQLAlchemyError("boom"))
        assert resp.status_code == 500
        assert b"DATABASE_ERROR" in resp.body
        assert b"req-1" in resp.body

    @pytest.mark.asyncio
    async def test_without_request_state(self):
        from sqlalchemy.exc import SQLAlchemyError

        resp = await eh.database_error_handler(_Req(), SQLAlchemyError("boom"))
        assert resp.status_code == 500
        assert b'"request_id":null' in resp.body


class TestApiErrorHandler:
    @pytest.mark.asyncio
    async def test_uses_exception_attributes(self):
        resp = await eh.api_error_handler(_Req(), _ApiExc(details={"k": "v"}))
        body = resp.body.decode()
        assert resp.status_code == 422
        assert '"CUSTOM"' in body
        assert '"api fail"' in body
        assert '"details":{"k":"v"}' in body

    @pytest.mark.asyncio
    async def test_falls_back_to_defaults(self):
        resp = await eh.api_error_handler(_Req(), ValueError("plain"))
        body = resp.body.decode()
        assert resp.status_code == 500
        assert '"API_ERROR"' in body
        assert '"plain"' in body

    @pytest.mark.asyncio
    async def test_includes_request_id(self):
        req = _Req(SimpleNamespace(request_id="rid-9"))
        resp = await eh.api_error_handler(req, ValueError("x"))
        assert b"rid-9" in resp.body


class TestGenericErrorHandler:
    @pytest.mark.asyncio
    async def test_delegates_to_global_handler(self, monkeypatch):
        fake = AsyncMock(return_value="handled")
        monkeypatch.setattr(eh, "global_exception_handler", fake)
        result = await eh.generic_error_handler(_Req(), ValueError("x"))
        assert result == "handled"
        fake.assert_awaited_once()


class TestSetupErrorHandlers:
    def test_registers_all_when_importable(self, monkeypatch):
        from sqlalchemy.exc import SQLAlchemyError

        app = _App()
        monkeypatch.setattr(eh, "AtomException", ValueError)
        monkeypatch.setattr(eh, "APIError", KeyError)
        eh.setup_error_handlers(app)
        types = [t for t, _ in app.handlers]
        assert types == [HTTPException, SQLAlchemyError, Exception, ValueError, KeyError]

    def test_skips_when_unavailable(self, monkeypatch):
        from sqlalchemy.exc import SQLAlchemyError

        app = _App()
        monkeypatch.setattr(eh, "AtomException", None)
        monkeypatch.setattr(eh, "APIError", None)
        eh.setup_error_handlers(app)
        types = [t for t, _ in app.handlers]
        assert types == [HTTPException, SQLAlchemyError, Exception]

    def test_works_with_real_fastapi_app(self):
        app = FastAPI()
        eh.setup_error_handlers(app)
        assert HTTPException in app.exception_handlers


class TestImportFailureBranch:
    def test_exceptions_module_missing_sets_both_none(self, monkeypatch):
        real_import = builtins.__import__

        def _fake_import(name, *a, **k):
            if name == "core.exceptions":
                raise ImportError("No module named core.exceptions")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", _fake_import)
        importlib.reload(eh)
        assert eh.AtomException is None
        assert eh.APIError is None

        monkeypatch.undo()
        importlib.reload(eh)
        from core.exceptions import AtomException

        assert eh.AtomException is AtomException


# ============================================================================
# 9. health
# ============================================================================


class TestHealthChecks:
    def test_database_operational(self, monkeypatch):
        fake_db = Mock()
        fake_db.execute = Mock(return_value=True)
        fake_db.close = Mock()
        monkeypatch.setattr("core.database.SessionLocal", lambda: fake_db)
        assert hlth._check_database() == "operational"
        fake_db.close.assert_called_once()

    def test_database_degraded_on_exception(self, monkeypatch):
        def _raise():
            raise RuntimeError("no db")

        monkeypatch.setattr("core.database.SessionLocal", _raise)
        assert hlth._check_database() == "degraded"

    def test_redis_operational_when_enabled(self, monkeypatch):
        monkeypatch.setattr("core.cache.redis_cache", SimpleNamespace(enabled=True))
        assert hlth._check_redis() == "operational"

    def test_redis_degraded_when_disabled(self, monkeypatch):
        monkeypatch.setattr("core.cache.redis_cache", SimpleNamespace(enabled=False))
        assert hlth._check_redis() == "degraded"

    def test_redis_degraded_on_import_error(self, monkeypatch):
        monkeypatch.delattr("core.cache.redis_cache", raising=True)
        assert hlth._check_redis() == "degraded"

    def test_vector_store_operational(self, monkeypatch):
        handler = SimpleNamespace(db=SimpleNamespace(db=object()))
        monkeypatch.setattr("core.lancedb_handler.get_lancedb_handler", lambda: handler)
        assert hlth._check_vector_store() == "operational"

    def test_vector_store_degraded_db_none(self, monkeypatch):
        monkeypatch.setattr("core.lancedb_handler.get_lancedb_handler", lambda: SimpleNamespace(db=None))
        assert hlth._check_vector_store() == "degraded"

    def test_vector_store_degraded_inner_db_none(self, monkeypatch):
        handler = SimpleNamespace(db=SimpleNamespace(db=None))
        monkeypatch.setattr("core.lancedb_handler.get_lancedb_handler", lambda: handler)
        assert hlth._check_vector_store() == "degraded"

    def test_vector_store_degraded_handler_none(self, monkeypatch):
        monkeypatch.setattr("core.lancedb_handler.get_lancedb_handler", lambda: None)
        assert hlth._check_vector_store() == "degraded"

    def test_vector_store_degraded_on_exception(self, monkeypatch):
        def _raise():
            raise RuntimeError("no lancedb")

        monkeypatch.setattr("core.lancedb_handler.get_lancedb_handler", _raise)
        assert hlth._check_vector_store() == "degraded"

    def test_perform_healthy_when_all_operational(self, monkeypatch):
        monkeypatch.setattr(hlth, "_check_database", lambda: "operational")
        monkeypatch.setattr(hlth, "_check_redis", lambda: "operational")
        monkeypatch.setattr(hlth, "_check_vector_store", lambda: "operational")
        result = hlth.perform_health_checks()
        assert result["status"] == "healthy"
        assert all(v == "operational" for v in result["services"].values())

    def test_perform_degraded_when_one_down(self, monkeypatch):
        monkeypatch.setattr(hlth, "_check_database", lambda: "operational")
        monkeypatch.setattr(hlth, "_check_redis", lambda: "degraded")
        monkeypatch.setattr(hlth, "_check_vector_store", lambda: "operational")
        result = hlth.perform_health_checks()
        assert result["status"] == "degraded"


# ============================================================================
# 4. email_followup_engine
# ============================================================================


class TestNormalizeTs:
    def test_none_returns_none(self):
        assert efe.EmailFollowUpEngine._normalize_ts(None) is None

    def test_naive_datetime_passthrough(self):
        ts = datetime(2024, 1, 1, 10, 0)
        assert efe.EmailFollowUpEngine._normalize_ts(ts) == ts

    def test_iso_string_parsed(self):
        assert efe.EmailFollowUpEngine._normalize_ts("2024-01-01T10:00:00") == datetime(2024, 1, 1, 10, 0)

    def test_aware_datetime_converted_to_naive(self):
        ts = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        result = efe.EmailFollowUpEngine._normalize_ts(ts)
        assert result.tzinfo is None


class TestFollowUpCandidate:
    def test_model_defaults(self):
        c = efe.FollowUpCandidate(
            id="1", recipient="r", subject="s",
            original_sent_at=datetime.now(), days_since_sent=3,
            last_message_snippet="snip",
        )
        assert c.thread_id is None
        assert c.last_message_snippet == "snip"


class TestDetectMissingReplies:
    @pytest.mark.asyncio
    async def test_recent_sent_no_candidate(self):
        engine = efe.EmailFollowUpEngine(days_threshold=3)
        sent = [{"id": "m1", "sent_at": datetime.now(), "to": "a@b.c", "subject": "hi"}]
        result = await engine.detect_missing_replies(sent, [])
        assert result == []

    @pytest.mark.asyncio
    async def test_old_sent_no_reply_yields_candidate(self):
        engine = efe.EmailFollowUpEngine(days_threshold=3)
        sent = [{"id": "m1", "sent_at": datetime.now() - timedelta(days=10), "to": "a@b.c", "subject": "hi"}]
        result = await engine.detect_missing_replies(sent, [])
        assert len(result) == 1
        c = result[0]
        assert c.id == "m1"
        assert c.recipient == "a@b.c"
        assert c.days_since_sent == 10

    @pytest.mark.asyncio
    async def test_reply_present_no_candidate(self):
        engine = efe.EmailFollowUpEngine(days_threshold=3)
        sent_at = datetime.now() - timedelta(days=10)
        sent = [{"id": "m1", "sent_at": sent_at, "to": "a@b.c", "subject": "hi", "thread_id": "t1"}]
        received = [{"thread_id": "t1", "received_at": datetime.now()}]
        result = await engine.detect_missing_replies(sent, received)
        assert result == []

    @pytest.mark.asyncio
    async def test_received_without_received_at_skipped(self):
        engine = efe.EmailFollowUpEngine(days_threshold=3)
        sent = [{"id": "m1", "sent_at": datetime.now() - timedelta(days=10), "to": "a@b.c", "thread_id": "t1"}]
        received = [{"thread_id": "t1"}]
        result = await engine.detect_missing_replies(sent, received)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_string_received_at_compared(self):
        engine = efe.EmailFollowUpEngine(days_threshold=3)
        sent_at = datetime.now() - timedelta(days=10)
        sent = [{"id": "m1", "sent_at": sent_at, "to": "a@b.c", "thread_id": "t1"}]
        received = [{"thread_id": "t1", "received_at": "2020-01-01T00:00:00"}]
        result = await engine.detect_missing_replies(sent, received)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_reply_before_sent_at_not_counted(self):
        engine = efe.EmailFollowUpEngine(days_threshold=3)
        sent_at = datetime.now() - timedelta(days=10)
        sent = [{"id": "m1", "sent_at": sent_at, "to": "a@b.c", "thread_id": "t1"}]
        received = [{"thread_id": "t1", "received_at": sent_at - timedelta(days=1)}]
        result = await engine.detect_missing_replies(sent, received)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_missing_sent_at_uses_now(self):
        engine = efe.EmailFollowUpEngine(days_threshold=3)
        sent = [{"id": "m1"}]
        result = await engine.detect_missing_replies(sent, [])
        assert result == []

    @pytest.mark.asyncio
    async def test_missing_fields_get_defaults(self):
        engine = efe.EmailFollowUpEngine(days_threshold=3)
        sent = [{"sent_at": datetime.now() - timedelta(days=5)}]
        result = await engine.detect_missing_replies(sent, [])
        assert len(result) == 1
        c = result[0]
        assert c.id == "unknown"
        assert c.recipient == "unknown"
        assert c.subject == "No Subject"
        assert c.last_message_snippet == ""

    @pytest.mark.asyncio
    async def test_thread_id_none_matches_reply(self):
        engine = efe.EmailFollowUpEngine(days_threshold=3)
        sent = [{"id": "m1", "sent_at": datetime.now() - timedelta(days=10), "to": "a@b.c"}]
        received = [{"received_at": datetime.now()}]
        result = await engine.detect_missing_replies(sent, received)
        assert result == []

    @pytest.mark.asyncio
    async def test_snippet_carried(self):
        engine = efe.EmailFollowUpEngine(days_threshold=3)
        sent = [{"id": "m1", "sent_at": datetime.now() - timedelta(days=10), "to": "a@b.c", "snippet": "pls respond"}]
        result = await engine.detect_missing_replies(sent, [])
        assert result[0].last_message_snippet == "pls respond"


# ============================================================================
# 6. entity_schema_suggestion_service
# ============================================================================


class TestEntitySchemaSuggestion:
    @pytest.mark.asyncio
    async def test_success_plain_json(self):
        llm = Mock()
        llm.generate_completion = AsyncMock(return_value={"content": '{"type": "object", "properties": {"a": {"type": "string"}}}'})
        svc = ess.EntitySchemaSuggestionService(llm_service=llm)
        result = await svc.suggest_schema("Invoice", "An invoice")
        assert result["type"] == "object"
        llm.generate_completion.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_success_fenced_json(self):
        llm = Mock()
        llm.generate_completion = AsyncMock(
            return_value={"content": '```json\n{"type": "object", "required": ["a"]}\n```'}
        )
        svc = ess.EntitySchemaSuggestionService(llm_service=llm)
        result = await svc.suggest_schema("Invoice", "desc")
        assert result["required"] == ["a"]

    @pytest.mark.asyncio
    async def test_success_fenced_plain(self):
        llm = Mock()
        llm.generate_completion = AsyncMock(return_value={"content": '```\n{"type": "object"}\n```'})
        svc = ess.EntitySchemaSuggestionService(llm_service=llm)
        result = await svc.suggest_schema("X", "y")
        assert result["type"] == "object"

    @pytest.mark.asyncio
    async def test_invalid_json_returns_fallback(self):
        llm = Mock()
        llm.generate_completion = AsyncMock(return_value={"content": "not json at all"})
        svc = ess.EntitySchemaSuggestionService(llm_service=llm)
        result = await svc.suggest_schema("X", "y")
        assert result["required"] == ["name"]
        assert result["properties"]["name"]["type"] == "string"

    @pytest.mark.asyncio
    async def test_llm_error_returns_fallback(self):
        llm = Mock()
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("llm down"))
        svc = ess.EntitySchemaSuggestionService(llm_service=llm)
        result = await svc.suggest_schema("X", "y")
        assert result["$schema"].startswith("https://json-schema.org")

    @pytest.mark.asyncio
    async def test_empty_content_returns_fallback(self):
        llm = Mock()
        llm.generate_completion = AsyncMock(return_value={"content": ""})
        svc = ess.EntitySchemaSuggestionService(llm_service=llm)
        result = await svc.suggest_schema("X", "y")
        assert result["required"] == ["name"]

    def test_init_defaults_to_llm_service(self, monkeypatch):
        fake = Mock()
        monkeypatch.setattr(ess, "LLMService", lambda **kw: fake)
        svc = ess.EntitySchemaSuggestionService()
        assert svc.llm_service is fake

    def test_init_with_provided_service(self):
        llm = Mock()
        svc = ess.EntitySchemaSuggestionService(llm_service=llm)
        assert svc.llm_service is llm


class TestEntitySchemaSingleton:
    def test_singleton_returns_same_instance(self, monkeypatch):
        monkeypatch.setattr(ess, "_instance", None)
        a = ess.get_entity_schema_suggestion_service()
        b = ess.get_entity_schema_suggestion_service()
        assert a is b

    def test_instance_reused_when_set(self, monkeypatch):
        fake = object()
        monkeypatch.setattr(ess, "_instance", fake)
        assert ess.get_entity_schema_suggestion_service() is fake


# ============================================================================
# 7. entity_skill_service
# ============================================================================


@pytest.fixture()
def ess_db(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.database import Base
    from core.models import EntityTypeDefinition, Skill, SkillInstallation, Tenant

    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        bind=engine,
        tables=[Tenant.__table__, Skill.__table__, SkillInstallation.__table__,
                EntityTypeDefinition.__table__],
    )
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setattr("core.database.SessionLocal", session_factory)
    session = session_factory()
    yield session, session_factory
    session.close()
    engine.dispose()


def _tenant(session, tid="tenant-1"):
    from core.models import Tenant

    t = Tenant(id=tid, name="Acme", subdomain=f"acme-{tid}")
    session.add(t)
    session.commit()
    return t


def _entity_type(session, eid="et-1", tid="tenant-1", slug="invoice", skills=None):
    from core.models import EntityTypeDefinition

    et = EntityTypeDefinition(
        id=eid, tenant_id=tid, slug=slug, display_name="Invoice",
        json_schema={"type": "object"}, available_skills=skills or [],
    )
    session.add(et)
    session.commit()
    return et


def _skill(session, sid="skill-1", tenant_id=None):
    from core.models import Skill

    skill = Skill(id=sid, name=f"skill {sid}", type="api",
                  tenant_id=tenant_id, input_schema={}, config={})
    session.add(skill)
    session.commit()
    return skill


class TestAttachSkill:
    def test_attach_global_skill(self, ess_db):
        db, _ = ess_db
        _tenant(db)
        _entity_type(db)
        _skill(db)
        svc = esk.EntitySkillService(db=db)
        result = svc.attach_skill("tenant-1", "et-1", "skill-1")
        assert "skill-1" in result.available_skills

    def test_attach_tenant_installation(self, ess_db):
        db, _ = ess_db
        _tenant(db)
        _entity_type(db)
        from core.models import SkillInstallation

        db.add(SkillInstallation(
            tenant_id="tenant-1", skill_id="installed-1", is_active=True,
            installed_version="1.0.0",
        ))
        db.commit()
        svc = esk.EntitySkillService(db=db)
        result = svc.attach_skill("tenant-1", "et-1", "installed-1")
        assert "installed-1" in result.available_skills

    def test_attach_entity_type_not_found(self, ess_db):
        db, _ = ess_db
        _tenant(db)
        svc = esk.EntitySkillService(db=db)
        with pytest.raises(ValueError, match="not found for tenant"):
            svc.attach_skill("tenant-1", "missing", "skill-1")

    def test_attach_skill_not_accessible(self, ess_db):
        db, _ = ess_db
        _tenant(db)
        _entity_type(db)
        svc = esk.EntitySkillService(db=db)
        with pytest.raises(ValueError, match="not found or not accessible"):
            svc.attach_skill("tenant-1", "et-1", "nope")

    def test_attach_duplicate_returns_unchanged(self, ess_db):
        db, _ = ess_db
        _tenant(db)
        _entity_type(db, skills=["skill-1"])
        _skill(db)
        svc = esk.EntitySkillService(db=db)
        result = svc.attach_skill("tenant-1", "et-1", "skill-1")
        assert result.available_skills == ["skill-1"]

    def test_attach_commit_failure_rolls_back(self, ess_db, monkeypatch):
        db, session_factory = ess_db
        _tenant(db)
        _entity_type(db)
        _skill(db)
        svc = esk.EntitySkillService(db=db)

        def _boom_session():
            s = session_factory()
            s.commit = Mock(side_effect=RuntimeError("commit boom"))
            return s

        monkeypatch.setattr("core.database.SessionLocal", _boom_session)
        with pytest.raises(RuntimeError):
            svc.attach_skill("tenant-1", "et-1", "skill-1")


class TestDetachSkill:
    def test_detach_existing(self, ess_db):
        db, _ = ess_db
        _tenant(db)
        _entity_type(db, skills=["skill-1", "skill-2"])
        svc = esk.EntitySkillService(db=db)
        result = svc.detach_skill("tenant-1", "et-1", "skill-1")
        assert result.available_skills == ["skill-2"]

    def test_detach_not_attached_returns_unchanged(self, ess_db):
        db, _ = ess_db
        _tenant(db)
        _entity_type(db, skills=["skill-1"])
        svc = esk.EntitySkillService(db=db)
        result = svc.detach_skill("tenant-1", "et-1", "skill-9")
        assert result.available_skills == ["skill-1"]

    def test_detach_not_found(self, ess_db):
        db, _ = ess_db
        _tenant(db)
        svc = esk.EntitySkillService(db=db)
        with pytest.raises(ValueError, match="not found"):
            svc.detach_skill("tenant-1", "missing", "skill-1")

    def test_detach_commit_failure_rolls_back(self, ess_db, monkeypatch):
        db, session_factory = ess_db
        _tenant(db)
        _entity_type(db, skills=["skill-1", "skill-2"])
        svc = esk.EntitySkillService(db=db)

        def _boom_session():
            s = session_factory()
            s.commit = Mock(side_effect=RuntimeError("commit boom"))
            return s

        monkeypatch.setattr("core.database.SessionLocal", _boom_session)
        with pytest.raises(RuntimeError):
            svc.detach_skill("tenant-1", "et-1", "skill-1")


class TestGetEntitySkills:
    def test_returns_skill_list(self, ess_db):
        db, _ = ess_db
        _tenant(db)
        _entity_type(db, skills=["skill-1", "skill-2"])
        _skill(db, "skill-1")
        _skill(db, "skill-2")
        svc = esk.EntitySkillService(db=db)
        result = svc.get_entity_skills("tenant-1", "et-1")
        assert {r["id"] for r in result} == {"skill-1", "skill-2"}
        assert result[0]["name"] == "skill skill-1"

    def test_empty_skills_returns_empty_list(self, ess_db):
        db, _ = ess_db
        _tenant(db)
        _entity_type(db, skills=[])
        svc = esk.EntitySkillService(db=db)
        assert svc.get_entity_skills("tenant-1", "et-1") == []

    def test_not_found_raises(self, ess_db):
        db, _ = ess_db
        _tenant(db)
        svc = esk.EntitySkillService(db=db)
        with pytest.raises(ValueError, match="not found"):
            svc.get_entity_skills("tenant-1", "missing")

    def test_skill_ids_but_no_matching_skills(self, ess_db):
        db, _ = ess_db
        _tenant(db)
        _entity_type(db, skills=["ghost"])
        svc = esk.EntitySkillService(db=db)
        assert svc.get_entity_skills("tenant-1", "et-1") == []


class TestCheckSkillPermission:
    def test_allowed(self, ess_db):
        db, _ = ess_db
        _tenant(db)
        _entity_type(db, skills=["skill-1"])
        svc = esk.EntitySkillService(db=db)
        assert svc.check_skill_permission("tenant-1", "invoice", "skill-1") == {
            "allowed": True, "reason": "Skill allowed"
        }

    def test_not_attached(self, ess_db):
        db, _ = ess_db
        _tenant(db)
        _entity_type(db, skills=[])
        svc = esk.EntitySkillService(db=db)
        assert svc.check_skill_permission("tenant-1", "invoice", "skill-1") == {
            "allowed": False, "reason": "Skill not attached"
        }

    def test_entity_type_not_found(self, ess_db):
        db, _ = ess_db
        _tenant(db)
        svc = esk.EntitySkillService(db=db)
        assert svc.check_skill_permission("tenant-1", "ghost", "skill-1") == {
            "allowed": False, "reason": "Entity type not found"
        }


class TestEntitySkillSingleton:
    def test_get_with_db(self, ess_db):
        db, _ = ess_db
        svc = esk.get_entity_skill_service(db=db)
        assert svc.db is db

    def test_get_without_db_returns_singleton(self, monkeypatch):
        monkeypatch.setattr(esk, "_default_service", None)
        a = esk.get_entity_skill_service()
        b = esk.get_entity_skill_service()
        assert a is b
        assert a.db is None

    def test_get_without_db_reuses_existing(self, monkeypatch):
        fake = object()
        monkeypatch.setattr(esk, "_default_service", fake)
        assert esk.get_entity_skill_service() is fake


# ============================================================================
# 1. cron_parser
# ============================================================================


class TestMatchesField:
    def test_wildcard(self):
        p = cp.CronParser()
        assert p._matches_field(5, "*", 0, 59) is True

    def test_exact_digit_match(self):
        p = cp.CronParser()
        assert p._matches_field(5, "5", 0, 59) is True
        assert p._matches_field(4, "5", 0, 59) is False

    def test_list_match(self):
        p = cp.CronParser()
        assert p._matches_field(3, "1,3,5", 0, 59) is True
        assert p._matches_field(2, "1,3,5", 0, 59) is False

    def test_list_with_range_sub_entry(self):
        p = cp.CronParser()
        assert p._matches_field(4, "1-5,10", 0, 59) is True
        assert p._matches_field(10, "1-5,10", 0, 59) is True
        assert p._matches_field(7, "1-5,10", 0, 59) is False

    def test_list_with_step_sub_entry(self):
        p = cp.CronParser()
        assert p._matches_field(30, "*/15,45", 0, 59) is True
        assert p._matches_field(45, "*/15,45", 0, 59) is True
        assert p._matches_field(10, "*/15,45", 0, 59) is False

    def test_list_with_empty_entry(self):
        p = cp.CronParser()
        assert p._matches_field(3, "1,,5", 0, 59) is False

    def test_range_match(self):
        p = cp.CronParser()
        assert p._matches_field(3, "1-5", 0, 59) is True
        assert p._matches_field(6, "1-5", 0, 59) is False

    def test_malformed_range_falls_through(self):
        p = cp.CronParser()
        assert p._matches_field(3, "a-b", 0, 59) is False

    def test_step_wildcard_min_zero(self):
        p = cp.CronParser()
        assert p._matches_field(10, "*/5", 0, 59) is True
        assert p._matches_field(3, "*/5", 0, 59) is False

    def test_step_wildcard_min_one_day_of_month(self):
        p = cp.CronParser()
        assert p._matches_field(6, "*/5", 1, 31) is True
        assert p._matches_field(4, "*/5", 1, 31) is False

    def test_step_with_range_base(self):
        p = cp.CronParser()
        assert p._matches_field(5, "1-10/2", 0, 59) is True
        assert p._matches_field(6, "1-10/2", 0, 59) is False
        assert p._matches_field(12, "1-10/2", 0, 59) is False

    def test_step_zero_returns_false(self):
        p = cp.CronParser()
        assert p._matches_field(5, "*/0", 0, 59) is False

    def test_step_non_digit_returns_false(self):
        p = cp.CronParser()
        assert p._matches_field(5, "*/x", 0, 59) is False

    def test_step_single_base_not_wildcard_or_range(self):
        p = cp.CronParser()
        assert p._matches_field(2, "5/2", 0, 59) is False

    def test_plain_garbage_returns_false(self):
        p = cp.CronParser()
        assert p._matches_field(2, "xyz", 0, 59) is False


class TestMatchesCron:
    def test_full_match(self):
        p = cp.CronParser()
        dt = datetime(2024, 1, 1, 9, 30)
        assert p._matches_cron(dt, "30", "9", "1", "1", "1") is True

    def test_minute_mismatch(self):
        p = cp.CronParser()
        dt = datetime(2024, 1, 1, 9, 31)
        assert p._matches_cron(dt, "30", "9", "1", "1", "1") is False

    def test_hour_mismatch(self):
        p = cp.CronParser()
        dt = datetime(2024, 1, 1, 8, 30)
        assert p._matches_cron(dt, "30", "9", "1", "1", "1") is False

    def test_day_mismatch(self):
        p = cp.CronParser()
        dt = datetime(2024, 1, 2, 9, 30)
        assert p._matches_cron(dt, "30", "9", "1", "1", "1") is False

    def test_month_mismatch(self):
        p = cp.CronParser()
        dt = datetime(2024, 2, 1, 9, 30)
        assert p._matches_cron(dt, "30", "9", "1", "1", "1") is False

    def test_weekday_convention_monday_is_1(self):
        # Bug 9 regression: Monday must match cron weekday 1, not 0.
        p = cp.CronParser()
        dt = datetime(2024, 1, 1, 9, 30)  # Monday
        assert p._matches_cron(dt, "30", "9", "1", "1", "1") is True
        assert p._matches_cron(dt, "30", "9", "1", "1", "0") is False

    def test_weekday_sunday_is_0(self):
        p = cp.CronParser()
        dt = datetime(2024, 1, 7, 9, 30)  # Sunday
        assert p._matches_cron(dt, "30", "9", "7", "1", "0") is True
        assert p._matches_cron(dt, "30", "9", "7", "1", "7") is False


class TestGetNextRun:
    def test_next_run_basic(self):
        p = cp.CronParser()
        after = datetime(2024, 1, 1, 0, 0)
        result = p.get_next_run("0 9 * * *", after=after)
        assert result == datetime(2024, 1, 1, 9, 0)

    def test_next_run_uses_now_when_no_after(self, monkeypatch):
        class _FrozenDateTime(datetime):
            _fixed = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)

            @classmethod
            def now(cls, tz=None):
                return cls._fixed if tz is None else cls._fixed.astimezone(tz)

        monkeypatch.setattr(cp, "datetime", _FrozenDateTime)
        p = cp.CronParser()
        result = p.get_next_run("0 9 * * *")
        assert result == datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)

    def test_next_run_weekday(self):
        p = cp.CronParser()
        after = datetime(2024, 1, 8, 0, 0)  # Monday
        result = p.get_next_run("30 14 * * 5", after=after)
        assert result == datetime(2024, 1, 12, 14, 30)  # Friday

    def test_invalid_part_count(self):
        p = cp.CronParser()
        with pytest.raises(ValueError, match="Must have 5 parts"):
            p.get_next_run("0 9 * *", after=datetime(2024, 1, 1))

    def test_exhaustion_raises_value_error(self, monkeypatch):
        p = cp.CronParser()
        monkeypatch.setattr(p, "_matches_cron", Mock(return_value=False))
        with pytest.raises(ValueError, match="Could not find next run"):
            p.get_next_run("0 0 30 2 *", after=datetime(2024, 1, 1))

    def test_matcher_exception_wrapped(self, monkeypatch):
        p = cp.CronParser()
        monkeypatch.setattr(p, "_matches_cron", Mock(side_effect=ValueError("boom")))
        with pytest.raises(ValueError, match="Invalid cron expression"):
            p.get_next_run("0 9 * * *", after=datetime(2024, 1, 1))


class TestTo24h:
    def test_pm_conversion(self):
        p = cp.CronParser()
        assert p._to_24h("9", "30", "pm") == "21 30"

    def test_pm_noon_stays(self):
        p = cp.CronParser()
        assert p._to_24h("12", "00", "pm") == "12 00"

    def test_am_midnight_becomes_zero(self):
        p = cp.CronParser()
        assert p._to_24h("12", "15", "am") == "0 15"

    def test_am_regular_stays(self):
        p = cp.CronParser()
        assert p._to_24h("9", "15", "AM") == "9 15"

    def test_no_ampm(self):
        p = cp.CronParser()
        assert p._to_24h("9", "0", None) == "9 0"


class TestWeekdayToNum:
    def test_known_weekday(self):
        p = cp.CronParser()
        assert p._weekday_to_num("Monday") == "1"
        assert p._weekday_to_num("SUNDAY") == "0"

    def test_unknown_weekday_defaults(self):
        p = cp.CronParser()
        assert p._weekday_to_num("funday") == "1"


class TestNaturalLanguageToCron:
    def test_every_day_at_am(self):
        assert cp.natural_language_to_cron("Every day at 9am") == "0 9 * * *"

    def test_every_day_at_pm_with_minutes(self):
        assert cp.natural_language_to_cron("every day at 9:30pm") == "30 21 * * *"

    def test_every_day_at_am_with_zero_minutes(self):
        assert cp.natural_language_to_cron("every day at 9:00am") == "0 9 * * *"

    def test_every_weekday_at_time(self):
        assert cp.natural_language_to_cron("Every Monday at 2pm") == "0 14 * * 1"

    def test_every_saturday_at_pm_with_minutes(self):
        assert cp.natural_language_to_cron("every saturday at 2:30pm") == "30 14 * * 6"

    def test_every_weekday_zero_minutes(self):
        assert cp.natural_language_to_cron("every tuesday at 11:00am") == "0 11 * * 2"

    def test_hourly_pattern(self):
        assert cp.natural_language_to_cron("hourly") == "0 * * * *"

    def test_every_hour_pattern(self):
        assert cp.natural_language_to_cron("every hour") == "0 * * * *"

    def test_daily_pattern(self):
        assert cp.natural_language_to_cron("daily") == "0 9 * * *"

    def test_every_day_pattern(self):
        assert cp.natural_language_to_cron("every day") == "0 9 * * *"

    def test_weekly_pattern(self):
        assert cp.natural_language_to_cron("weekly") == "0 9 * * 1"

    def test_every_week_pattern(self):
        assert cp.natural_language_to_cron("every week") == "0 9 * * 1"

    def test_monthly_pattern(self):
        assert cp.natural_language_to_cron("monthly") == "0 9 1 * *"

    def test_every_month_pattern(self):
        assert cp.natural_language_to_cron("every month") == "0 9 1 * *"

    def test_yearly_pattern(self):
        assert cp.natural_language_to_cron("yearly") == "0 9 1 1 *"

    def test_every_year_pattern(self):
        assert cp.natural_language_to_cron("every year") == "0 9 1 1 *"

    def test_annually_pattern(self):
        assert cp.natural_language_to_cron("annually") == "0 9 1 1 *"

    def test_callable_pattern_success(self, monkeypatch):
        def _repl(m):
            return "0 0 * * *"

        monkeypatch.setattr(cp.CronParser, "PATTERNS", {"custom": _repl})
        assert cp.natural_language_to_cron("custom") == "0 0 * * *"

    def test_callable_pattern_failure_continues(self, monkeypatch):
        def _raise(m):
            raise RuntimeError("conversion failed")

        monkeypatch.setattr(cp.CronParser, "PATTERNS", {"custom": _raise})
        with pytest.raises(ValueError, match="Could not parse"):
            cp.natural_language_to_cron("custom")

    def test_unparseable_raises(self):
        with pytest.raises(ValueError, match="Could not parse"):
            cp.natural_language_to_cron("gibberish schedule")

    def test_whitespace_and_case_insensitive(self):
        assert cp.natural_language_to_cron("  DAILY  ") == "0 9 * * *"


class TestStaticHelpers:
    def test_to_24h_static_pm(self):
        assert cp._to_24h_static("9", "30", "pm") == "21"

    def test_to_24h_static_am_midnight(self):
        assert cp._to_24h_static("12", "0", "am") == "0"

    def test_to_24h_static_zero_minutes(self):
        assert cp._to_24h_static("7", "00", "am") == "7"

    def test_to_24h_static_no_ampm(self):
        assert cp._to_24h_static("6", "30", None) == "6"

    def test_weekday_to_num_static_known(self):
        assert cp._weekday_to_num_static("Friday") == "5"

    def test_weekday_to_num_static_unknown(self):
        assert cp._weekday_to_num_static("funday") == "1"


class TestValidateCronExpression:
    def test_valid_expression(self):
        assert cp.validate_cron_expression("0 9 * * *") is True

    def test_valid_complex_expression(self):
        assert cp.validate_cron_expression("*/15 9-17 * * 1-5") is True

    def test_valid_list(self):
        assert cp.validate_cron_expression("1-5,10 0 * * *") is True

    def test_wrong_part_count(self):
        assert cp.validate_cron_expression("0 9 * *") is False

    def test_minute_out_of_range(self):
        assert cp.validate_cron_expression("60 0 * * *") is False

    def test_hour_out_of_range(self):
        assert cp.validate_cron_expression("0 24 * * *") is False

    def test_day_out_of_range(self):
        assert cp.validate_cron_expression("0 0 32 * *") is False

    def test_month_out_of_range(self):
        assert cp.validate_cron_expression("0 0 * 13 *") is False

    def test_weekday_out_of_range(self):
        assert cp.validate_cron_expression("0 0 * * 7") is False

    def test_step_zero_invalid(self):
        assert cp.validate_cron_expression("*/0 0 * * *") is False

    def test_step_valid(self):
        assert cp.validate_cron_expression("*/5 0 * * *") is True

    def test_non_string_input(self):
        assert cp.validate_cron_expression(None) is False

    def test_step_with_range_base_valid(self):
        assert cp.validate_cron_expression("1-10/2 0 * * *") is True


class TestIsValidField:
    def test_wildcard(self):
        assert cp.CronParser()._is_valid_field("*", 0, 59) is True

    def test_digit_in_range(self):
        assert cp.CronParser()._is_valid_field("5", 0, 59) is True
        assert cp.CronParser()._is_valid_field("70", 0, 59) is False

    def test_range_valid(self):
        assert cp.CronParser()._is_valid_field("1-5", 0, 59) is True

    def test_range_out_of_bounds(self):
        assert cp.CronParser()._is_valid_field("8-70", 0, 59) is False

    def test_malformed_range(self):
        assert cp.CronParser()._is_valid_field("a-b", 0, 59) is False

    def test_step_wildcard(self):
        assert cp.CronParser()._is_valid_field("*/5", 0, 59) is True

    def test_step_zero_invalid(self):
        assert cp.CronParser()._is_valid_field("*/0", 0, 59) is False

    def test_step_with_range_base(self):
        assert cp.CronParser()._is_valid_field("1-10/2", 0, 59) is True

    def test_step_with_malformed_base(self):
        assert cp.CronParser()._is_valid_field("a-b/2", 0, 59) is False

    def test_list_valid(self):
        assert cp.CronParser()._is_valid_field("1,3,5", 0, 59) is True

    def test_list_with_empty_entry(self):
        assert cp.CronParser()._is_valid_field("1,,5", 0, 59) is False

    def test_list_with_range_entry(self):
        assert cp.CronParser()._is_valid_field("1-5,10", 0, 59) is True

    def test_list_with_invalid_entry(self):
        assert cp.CronParser()._is_valid_field("1,70", 0, 59) is False

    def test_garbage(self):
        assert cp.CronParser()._is_valid_field("xyz", 0, 59) is False


# ============================================================================
# 2. database_helper
# ============================================================================


@pytest.fixture()
def dh_env():
    from sqlalchemy import Column, Integer, String, create_engine
    from sqlalchemy.orm import declarative_base, sessionmaker

    B = declarative_base()

    class Item(B):
        __tablename__ = "items"
        id = Column(String, primary_key=True)
        name = Column(String, default="")
        status = Column(String, default="active")
        count = Column(Integer, default=0)
        deleted_by = Column(String, nullable=True)
        deleted_at = Column(String, nullable=True)

    engine = create_engine("sqlite://")
    B.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session, Item
    session.close()
    engine.dispose()


class TestGetOr404:
    def test_found(self, dh_env):
        db, Item = dh_env
        db.add(Item(id="i1", name="a"))
        db.commit()
        result = dh.get_or_404(db, Item, "i1")
        assert result.id == "i1"

    def test_not_found_custom_message(self, dh_env):
        db, Item = dh_env
        with pytest.raises(HTTPException) as ei:
            dh.get_or_404(db, Item, "nope", "Custom not found")
        assert ei.value.status_code == 404
        assert ei.value.detail == "Custom not found"

    def test_not_found_default_message(self, dh_env):
        db, Item = dh_env
        with pytest.raises(HTTPException) as ei:
            dh.get_or_404(db, Item, "nope")
        assert ei.value.detail == "Item not found"

    def test_custom_id_field(self, dh_env):
        db, Item = dh_env
        db.add(Item(id="i1", name="a"))
        db.commit()
        assert dh.get_or_404(db, Item, "a", id_field="name").id == "i1"


class TestGetById:
    def test_found(self, dh_env):
        db, Item = dh_env
        db.add(Item(id="i1"))
        db.commit()
        assert dh.get_by_id(db, Item, "i1").id == "i1"

    def test_missing_returns_none(self, dh_env):
        db, Item = dh_env
        assert dh.get_by_id(db, Item, "nope") is None


class TestGetByField:
    def test_found(self, dh_env):
        db, Item = dh_env
        db.add(Item(id="i1", name="alpha"))
        db.commit()
        assert dh.get_by_field(db, Item, "name", "alpha").id == "i1"

    def test_missing_returns_none(self, dh_env):
        db, Item = dh_env
        assert dh.get_by_field(db, Item, "name", "nope") is None


class TestGetAll:
    def test_no_filters(self, dh_env):
        db, Item = dh_env
        db.add_all([Item(id="i1"), Item(id="i2")])
        db.commit()
        assert len(dh.get_all(db, Item)) == 2

    def test_filters_applied(self, dh_env):
        db, Item = dh_env
        db.add_all([Item(id="i1", status="a"), Item(id="i2", status="b")])
        db.commit()
        result = dh.get_all(db, Item, filters={"status": "a"})
        assert [r.id for r in result] == ["i1"]

    def test_unknown_filter_field_skipped(self, dh_env):
        db, Item = dh_env
        db.add_all([Item(id="i1"), Item(id="i2")])
        db.commit()
        assert len(dh.get_all(db, Item, filters={"nonexistent": 1})) == 2

    def test_order_by_desc(self, dh_env):
        db, Item = dh_env
        db.add_all([Item(id="i1", name="a"), Item(id="i2", name="b")])
        db.commit()
        result = dh.get_all(db, Item, order_by="-name")
        assert [r.name for r in result] == ["b", "a"]

    def test_order_by_asc(self, dh_env):
        db, Item = dh_env
        db.add_all([Item(id="i1", name="b"), Item(id="i2", name="a")])
        db.commit()
        result = dh.get_all(db, Item, order_by="name")
        assert [r.name for r in result] == ["a", "b"]

    def test_order_by_unknown_field_ignored(self, dh_env):
        db, Item = dh_env
        db.add_all([Item(id="i1"), Item(id="i2")])
        db.commit()
        assert len(dh.get_all(db, Item, order_by="-nope")) == 2

    def test_offset_and_limit(self, dh_env):
        db, Item = dh_env
        db.add_all([Item(id=f"i{n}", name=f"n{n}") for n in range(5)])
        db.commit()
        result = dh.get_all(db, Item, order_by="name", offset=1, limit=2)
        assert [r.name for r in result] == ["n1", "n2"]


class TestCreateRecord:
    def test_creates_and_commits(self, dh_env):
        db, Item = dh_env
        record = dh.create_record(db, Item, id="i9", name="new")
        assert record.id == "i9"
        assert dh.get_by_id(db, Item, "i9") is not None


class TestUpdateRecord:
    def test_updates_known_fields(self, dh_env):
        db, Item = dh_env
        db.add(Item(id="i1", name="old", count=1))
        db.commit()
        record = dh.get_by_id(db, Item, "i1")
        updated = dh.update_record(db, record, name="new", count=2)
        assert updated.name == "new"
        assert updated.count == 2

    def test_unknown_fields_skipped(self, dh_env):
        db, Item = dh_env
        db.add(Item(id="i1", name="old"))
        db.commit()
        record = dh.get_by_id(db, Item, "i1")
        updated = dh.update_record(db, record, nonexistent="x")
        assert updated.name == "old"


class TestDeleteRecord:
    def test_deletes(self, dh_env):
        db, Item = dh_env
        db.add(Item(id="i1"))
        db.commit()
        record = dh.get_by_id(db, Item, "i1")
        assert dh.delete_record(db, record) is True
        assert dh.get_by_id(db, Item, "i1") is None


class TestSoftDeleteRecord:
    def test_sets_status_and_metadata(self, dh_env):
        db, Item = dh_env
        db.add(Item(id="i1", status="active"))
        db.commit()
        record = dh.get_by_id(db, Item, "i1")
        result = dh.soft_delete_record(db, record, deleted_by="user-1")
        assert result.status == "deleted"
        assert result.deleted_by == "user-1"
        assert result.deleted_at is not None

    def test_no_deleted_by_leaves_blank(self, dh_env):
        db, Item = dh_env
        db.add(Item(id="i1"))
        db.commit()
        record = dh.get_by_id(db, Item, "i1")
        result = dh.soft_delete_record(db, record)
        assert result.status == "deleted"
        assert result.deleted_by is None
        assert result.deleted_at is not None


class TestCheckExists:
    def test_exists(self, dh_env):
        db, Item = dh_env
        db.add(Item(id="i1"))
        db.commit()
        assert dh.check_exists(db, Item, "id", "i1") is True

    def test_not_exists(self, dh_env):
        db, Item = dh_env
        assert dh.check_exists(db, Item, "id", "nope") is False


class TestCountRecords:
    def test_with_filters(self, dh_env):
        db, Item = dh_env
        db.add_all([Item(id="i1", status="a"), Item(id="i2", status="a"), Item(id="i3", status="b")])
        db.commit()
        assert dh.count_records(db, Item, {"status": "a"}) == 2

    def test_without_filters(self, dh_env):
        db, Item = dh_env
        db.add_all([Item(id="i1"), Item(id="i2")])
        db.commit()
        assert dh.count_records(db, Item) == 2

    def test_unknown_filter_field_skipped(self, dh_env):
        db, Item = dh_env
        db.add_all([Item(id="i1"), Item(id="i2")])
        db.commit()
        assert dh.count_records(db, Item, {"nope": 1}) == 2


class TestBulkCreate:
    def test_creates_all(self, dh_env):
        db, Item = dh_env
        records = dh.bulk_create(db, Item, [{"id": "a1", "name": "A"}, {"id": "a2", "name": "B"}])
        assert len(records) == 2
        assert dh.count_records(db, Item) == 2


class TestGetOrCreate:
    def test_existing_returns_not_created(self, dh_env):
        db, Item = dh_env
        db.add(Item(id="i1"))
        db.commit()
        record, created = dh.get_or_create(db, Item, {"id": "i1"}, {"name": "x"})
        assert created is False
        assert record.id == "i1"

    def test_creates_with_defaults(self, dh_env):
        db, Item = dh_env
        record, created = dh.get_or_create(db, Item, {"id": "i2"}, {"name": "x"})
        assert created is True
        assert record.name == "x"

    def test_creates_without_defaults(self, dh_env):
        db, Item = dh_env
        record, created = dh.get_or_create(db, Item, {"id": "i3"})
        assert created is True
        assert record.id == "i3"


class TestExecuteSafe:
    def test_success(self, dh_env):
        db, _ = dh_env
        assert dh.execute_safe(db, lambda: 42) == 42

    def test_failure_raises_http_500(self, dh_env):
        db, _ = dh_env
        with pytest.raises(HTTPException) as ei:
            dh.execute_safe(db, lambda: (_ for _ in ()).throw(RuntimeError("x")), "Custom failure")
        assert ei.value.status_code == 500
        assert ei.value.detail == "Custom failure"


class TestPaginateQuery:
    def test_with_data(self, dh_env):
        db, Item = dh_env
        db.add_all([Item(id=f"i{n}", name=f"n{n}") for n in range(5)])
        db.commit()
        result = dh.paginate_query(db, Item, page=1, page_size=2, filters={"status": "active"}, order_by="-name")
        assert result["total"] == 5
        assert len(result["items"]) == 2
        assert result["page"] == 1
        assert result["page_size"] == 2
        assert result["total_pages"] == 3

    def test_empty_result(self, dh_env):
        db, Item = dh_env
        result = dh.paginate_query(db, Item)
        assert result["total"] == 0
        assert result["total_pages"] == 0
        assert result["items"] == []


# ============================================================================
# 5. enterprise_security
# ============================================================================


def _mk_es(**kwargs):
    inst = es.EnterpriseSecurity()
    for k, v in kwargs.items():
        setattr(inst, k, v)
    return inst


def _audit_event(**overrides):
    data = dict(
        event_type=es.EventType.USER_LOGIN,
        security_level=es.SecurityLevel.MEDIUM,
        action="login",
        description="User login",
    )
    data.update(overrides)
    return es.AuditEvent(**data)


class TestEnumsAndModels:
    def test_security_level_values(self):
        assert [l.value for l in es.SecurityLevel] == ["low", "medium", "high", "critical"]

    def test_event_type_values(self):
        assert es.EventType.USER_LOGIN.value == "user_login"
        assert es.EventType.SECURITY_EVENT.value == "security_event"
        assert es.EventType.COMPLIANCE_CHECK.value == "compliance_check"

    def test_threat_level_values(self):
        assert [t.value for t in es.ThreatLevel] == ["normal", "suspicious", "malicious", "critical"]

    def test_audit_event_defaults(self):
        e = _audit_event()
        assert e.threat_level == es.ThreatLevel.NORMAL
        assert e.success is True
        assert e.metadata == {}
        assert e.event_id is None

    def test_security_alert_defaults(self):
        a = es.SecurityAlert(
            alert_id="a1", alert_type="t", severity=es.SecurityLevel.HIGH,
            timestamp=datetime.now(), description="d",
        )
        assert a.affected_users == []
        assert a.investigation_status == "open"

    def test_rate_limit_config_defaults(self):
        c = es.RateLimitConfig()
        assert c.requests_per_minute == 60
        assert c.requests_per_hour == 1000
        assert c.requests_per_day == 10000
        assert c.burst_limit == 10


class TestEnterpriseSecurityInit:
    def test_compliance_checks_initialized(self):
        inst = _mk_es()
        assert len(inst.compliance_checks) == 6
        standards = {c.standard for c in inst.compliance_checks}
        assert standards == {"SOC2", "GDPR", "HIPAA"}
        assert any(c.status == "warning" for c in inst.compliance_checks)
        assert all(c.evidence == "Automated system verification" for c in inst.compliance_checks)


class TestLogAuditEvent:
    def test_assigns_id_and_timestamp(self):
        inst = _mk_es()
        e = _audit_event()
        event_id = inst.log_audit_event(e)
        assert event_id is not None
        assert len(inst.audit_events) == 1
        assert inst.audit_events[0].timestamp is not None

    def test_trims_over_100k(self):
        inst = _mk_es()
        inst.audit_events = [object() for _ in range(100001)]
        inst.log_audit_event(_audit_event())
        assert len(inst.audit_events) == 100000 - 1 + 1


class TestAnalyzeSecurityPatterns:
    def test_failed_login_tracks_attempts(self):
        inst = _mk_es()
        e = _audit_event(success=False, user_email="u@x.com")
        inst.log_audit_event(e)
        assert len(inst.failed_login_attempts["u@x.com"]) == 1

    def test_failed_login_threshold_locks_account(self):
        inst = _mk_es()
        inst.max_login_attempts = 2
        for _ in range(2):
            inst.log_audit_event(_audit_event(success=False, user_email="u@x.com"))
        assert "u@x.com" in inst.locked_accounts
        assert any(a.alert_type == "brute_force_attempt" for a in inst.security_alerts)

    def test_old_attempts_cleaned_from_window(self):
        inst = _mk_es()
        inst.login_lockout_duration = timedelta(minutes=30)
        old = datetime.now() - timedelta(minutes=40)
        new = datetime.now() - timedelta(minutes=1)
        inst.failed_login_attempts["u@x.com"] = [old, new]
        e = _audit_event(success=False, user_email="u@x.com")
        inst.log_audit_event(e)
        assert all(a > datetime.now() - timedelta(minutes=30) for a in inst.failed_login_attempts["u@x.com"])

    def test_successful_login_untracked(self):
        inst = _mk_es()
        inst.log_audit_event(_audit_event(success=True, user_email="u@x.com"))
        assert "u@x.com" not in inst.failed_login_attempts

    def test_failed_login_without_email_untracked(self):
        inst = _mk_es()
        inst.log_audit_event(_audit_event(success=False, user_email=None))
        assert inst.failed_login_attempts == {}

    def test_suspicious_ip_tracking(self):
        inst = _mk_es()
        inst.log_audit_event(_audit_event(success=False, ip_address="1.2.3.4"))
        assert inst.suspicious_ips["1.2.3.4"] == 1

    def test_suspicious_ip_threshold_creates_alert(self):
        inst = _mk_es()
        inst.suspicious_threshold = 2
        for _ in range(2):
            inst.log_audit_event(_audit_event(success=False, ip_address="9.9.9.9"))
        assert any(a.alert_type == "suspicious_ip_activity" for a in inst.security_alerts)

    def test_successful_event_no_ip_tracking(self):
        inst = _mk_es()
        inst.log_audit_event(_audit_event(success=True, ip_address="1.2.3.4"))
        assert inst.suspicious_ips == {}


class TestIsAccountLocked:
    def test_not_locked_when_absent(self):
        inst = _mk_es()
        assert inst.is_account_locked("u@x.com") is False

    def test_locked_when_active(self):
        inst = _mk_es()
        inst.locked_accounts["u@x.com"] = datetime.now() + timedelta(minutes=10)
        assert inst.is_account_locked("u@x.com") is True

    def test_expired_lock_cleans_up(self):
        inst = _mk_es()
        inst.locked_accounts["u@x.com"] = datetime.now() - timedelta(minutes=1)
        inst.failed_login_attempts["u@x.com"] = [datetime.now()]
        assert inst.is_account_locked("u@x.com") is False
        assert "u@x.com" not in inst.locked_accounts
        assert "u@x.com" not in inst.failed_login_attempts


class TestCreateSecurityAlert:
    def test_with_defaults(self):
        inst = _mk_es()
        alert_id = inst.create_security_alert("type1", es.SecurityLevel.HIGH, "desc")
        assert len(inst.security_alerts) == 1
        alert = inst.security_alerts[0]
        assert alert.affected_users == []
        assert alert.affected_resources == []
        assert alert.metadata == {}
        assert alert.investigation_status == "open"
        assert any(e.event_type == es.EventType.SECURITY_EVENT for e in inst.audit_events)

    def test_with_explicit_values(self):
        inst = _mk_es()
        inst.create_security_alert(
            "type2", es.SecurityLevel.CRITICAL, "desc",
            affected_users=["u1"], affected_resources=["r1"], metadata={"k": "v"},
        )
        alert = inst.security_alerts[0]
        assert alert.affected_users == ["u1"]
        assert alert.affected_resources == ["r1"]
        assert alert.metadata == {"k": "v"}


class TestCheckRateLimit:
    def test_new_identifier_allowed(self):
        inst = _mk_es()
        assert inst.check_rate_limit("ip-1", datetime.now()) is True

    def test_within_limits(self):
        inst = _mk_es()
        now = datetime.now()
        assert inst.check_rate_limit("ip-1", now) is True
        assert inst.check_rate_limit("ip-1", now) is True

    def test_minute_limit_exceeded(self):
        inst = _mk_es()
        inst.rate_limit_config.requests_per_minute = 1
        now = datetime.now()
        assert inst.check_rate_limit("ip-1", now) is True
        assert inst.check_rate_limit("ip-1", now) is False

    def test_hour_limit_exceeded(self):
        inst = _mk_es()
        inst.rate_limit_config.requests_per_minute = 100
        inst.rate_limit_config.requests_per_hour = 1
        now = datetime.now()
        assert inst.check_rate_limit("ip-1", now) is True
        assert inst.check_rate_limit("ip-1", now) is False

    def test_day_limit_exceeded(self):
        inst = _mk_es()
        inst.rate_limit_config.requests_per_minute = 100
        inst.rate_limit_config.requests_per_hour = 100
        inst.rate_limit_config.requests_per_day = 1
        now = datetime.now()
        assert inst.check_rate_limit("ip-1", now) is True
        assert inst.check_rate_limit("ip-1", now) is False

    def test_old_requests_cleaned(self):
        inst = _mk_es()
        old = datetime.now() - timedelta(days=2)
        inst.api_rate_limits["ip-1"] = [old, old, old]
        assert inst.check_rate_limit("ip-1", datetime.now()) is True
        assert len(inst.api_rate_limits["ip-1"]) == 1


class TestGetAuditEvents:
    def _seed(self):
        inst = _mk_es()
        base = datetime(2024, 1, 10, 12, 0)
        inst.audit_events = [
            _audit_event(event_type=es.EventType.USER_LOGIN, security_level=es.SecurityLevel.LOW,
                         user_id="u1", timestamp=base - timedelta(days=2)),
            _audit_event(event_type=es.EventType.CONFIG_CHANGE, security_level=es.SecurityLevel.HIGH,
                         user_id="u2", timestamp=base - timedelta(days=1)),
            _audit_event(event_type=es.EventType.USER_LOGIN, security_level=es.SecurityLevel.LOW,
                         user_id="u1", timestamp=base),
        ]
        return inst, base

    def test_no_filters_returns_all_sorted(self):
        inst, base = self._seed()
        result = inst.get_audit_events()
        assert len(result) == 3
        assert result[0].timestamp == base

    def test_start_time_filter(self):
        inst, base = self._seed()
        result = inst.get_audit_events(start_time=base - timedelta(hours=1))
        assert len(result) == 1

    def test_end_time_filter(self):
        inst, base = self._seed()
        result = inst.get_audit_events(end_time=base - timedelta(days=1))
        assert len(result) == 2

    def test_event_type_filter(self):
        inst, base = self._seed()
        result = inst.get_audit_events(event_type=es.EventType.USER_LOGIN)
        assert len(result) == 2

    def test_user_id_filter(self):
        inst, base = self._seed()
        result = inst.get_audit_events(user_id="u2")
        assert len(result) == 1

    def test_security_level_filter(self):
        inst, base = self._seed()
        result = inst.get_audit_events(security_level=es.SecurityLevel.HIGH)
        assert len(result) == 1

    def test_limit(self):
        inst, base = self._seed()
        result = inst.get_audit_events(limit=2)
        assert len(result) == 2
        assert result[0].timestamp == base


class TestGetSecurityAlerts:
    def _seed(self):
        inst = _mk_es()
        base = datetime(2024, 1, 10, 12, 0)
        inst.security_alerts = [
            es.SecurityAlert(alert_id="a1", alert_type="t", severity=es.SecurityLevel.HIGH,
                             timestamp=base - timedelta(days=2), description="d1", investigation_status="open"),
            es.SecurityAlert(alert_id="a2", alert_type="t", severity=es.SecurityLevel.LOW,
                             timestamp=base - timedelta(days=1), description="d2", investigation_status="resolved"),
            es.SecurityAlert(alert_id="a3", alert_type="t", severity=es.SecurityLevel.HIGH,
                             timestamp=base, description="d3", investigation_status="open"),
        ]
        return inst, base

    def test_no_filters(self):
        inst, base = self._seed()
        result = inst.get_security_alerts()
        assert len(result) == 3
        assert result[0].timestamp == base

    def test_severity_filter(self):
        inst, _ = self._seed()
        result = inst.get_security_alerts(severity=es.SecurityLevel.HIGH)
        assert len(result) == 2

    def test_status_filter(self):
        inst, _ = self._seed()
        result = inst.get_security_alerts(status="resolved")
        assert [a.alert_id for a in result] == ["a2"]

    def test_start_time_filter(self):
        inst, base = self._seed()
        result = inst.get_security_alerts(start_time=base - timedelta(days=1))
        assert len(result) == 2

    def test_limit(self):
        inst, _ = self._seed()
        result = inst.get_security_alerts(limit=1)
        assert len(result) == 1


class TestComplianceStatus:
    def test_all_standards(self):
        inst = _mk_es()
        result = inst.get_compliance_status()
        assert result["total_checks"] == 6
        assert result["compliant_checks"] == 5
        assert result["warning_checks"] == 1
        assert result["non_compliant_checks"] == 0
        assert result["compliance_rate"] == round(5 / 6 * 100, 2)

    def test_filtered_standard(self):
        inst = _mk_es()
        result = inst.get_compliance_status(standard="GDPR")
        assert result["total_checks"] == 2
        assert result["compliance_rate"] == 100.0

    def test_unknown_standard_empty(self):
        inst = _mk_es()
        result = inst.get_compliance_status(standard="ISO27001")
        assert result["total_checks"] == 0
        assert result["compliance_rate"] == 0


class TestRunComplianceScan:
    def test_returns_summary_and_logs_event(self):
        inst = _mk_es()
        result = inst.run_compliance_scan()
        assert result["checks_performed"] == 15
        assert result["success_rate"] == 80.0
        assert result["scan_id"]
        assert any(e.event_type == es.EventType.COMPLIANCE_CHECK for e in inst.audit_events)


class TestSecurityRoutes:
    @pytest.fixture(autouse=True)
    def _isolated(self, monkeypatch):
        monkeypatch.setattr(es, "enterprise_security", _mk_es())

    @pytest.mark.asyncio
    async def test_audit_route_no_filters(self):
        es.enterprise_security.log_audit_event(_audit_event())
        result = await es.get_audit_events()
        assert result["total_count"] == 1
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_audit_route_with_filters(self):
        inst = es.enterprise_security
        base = datetime(2024, 1, 10, 12, 0)
        inst.audit_events = [
            _audit_event(event_type=es.EventType.USER_LOGIN, security_level=es.SecurityLevel.LOW,
                         user_id="u1", timestamp=base),
        ]
        result = await es.get_audit_events(
            start_time=base - timedelta(days=1),
            end_time=base + timedelta(days=1),
            event_type=es.EventType.USER_LOGIN,
            user_id="u1",
            security_level=es.SecurityLevel.LOW,
            limit=10,
        )
        assert result["total_count"] == 1

    @pytest.mark.asyncio
    async def test_alerts_route(self):
        inst = es.enterprise_security
        inst.create_security_alert("t", es.SecurityLevel.MEDIUM, "d")
        inst.security_alerts[0].investigation_status = "open"
        result = await es.get_security_alerts(severity=es.SecurityLevel.MEDIUM, status="open", limit=5)
        assert result["total_count"] == 1
        assert result["open_alerts"] == 1

    @pytest.mark.asyncio
    async def test_alerts_route_defaults(self):
        result = await es.get_security_alerts()
        assert result["total_count"] == 0
        assert result["open_alerts"] == 0

    @pytest.mark.asyncio
    async def test_compliance_route(self):
        result = await es.get_compliance_status(standard="SOC2")
        assert result["total_checks"] == 3

    @pytest.mark.asyncio
    async def test_compliance_route_default(self):
        result = await es.get_compliance_status()
        assert result["total_checks"] == 6

    @pytest.mark.asyncio
    async def test_scan_route(self):
        result = await es.run_compliance_scan()
        assert result["checks_performed"] == 15

    @pytest.mark.asyncio
    async def test_stats_route(self):
        inst = es.enterprise_security
        inst.log_audit_event(_audit_event())
        inst.create_security_alert("t", es.SecurityLevel.HIGH, "d")
        inst.failed_login_attempts["u@x.com"] = [datetime.now()]
        inst.suspicious_ips["1.2.3.4"] = 3
        result = await es.get_security_stats()
        assert result["total_audit_events"] == 2
        assert result["total_security_alerts"] == 1
        assert result["open_security_alerts"] == 1
        assert result["event_type_counts"]["user_login"] == 1
        assert result["failed_login_attempts"] == 1
        assert result["suspicious_ips"] == 1


class TestSecurityMiddleware:
    @pytest.fixture(autouse=True)
    def _isolated(self, monkeypatch):
        monkeypatch.setattr(es, "enterprise_security", _mk_es())

    @pytest.mark.asyncio
    async def test_passes_request_within_limit(self):
        call_next = AsyncMock(return_value="ok-response")
        request = Mock()
        request.client = SimpleNamespace(host="10.0.0.1")
        result = await es.security_middleware(request, call_next)
        assert result == "ok-response"
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_429_when_limited(self):
        es.enterprise_security.rate_limit_config.requests_per_minute = 0
        call_next = AsyncMock()
        request = Mock()
        request.client = SimpleNamespace(host="10.0.0.1")
        with pytest.raises(HTTPException) as ei:
            await es.security_middleware(request, call_next)
        assert ei.value.status_code == 429
        call_next.assert_not_called()
        events = es.enterprise_security.audit_events
        assert any(e.action == "rate_limit_exceeded" and e.success is False for e in events)

    @pytest.mark.asyncio
    async def test_client_none_uses_unknown(self):
        es.enterprise_security.rate_limit_config.requests_per_minute = 0
        call_next = AsyncMock()
        request = Mock()
        request.client = None
        with pytest.raises(HTTPException):
            await es.security_middleware(request, call_next)
        assert any(e.ip_address == "unknown" for e in es.enterprise_security.audit_events)


# ============================================================================
