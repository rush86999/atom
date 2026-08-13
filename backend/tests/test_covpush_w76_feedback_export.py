# -*- coding: utf-8 -*-
"""Coverage wave 76 — core/feedback_export_service (FeedbackExportService).

Real in-memory SQLite (no network, no LLM). Covers the previously-missing
lines 95-116 (export_to_json), 207-240 (export_summary_to_json per-agent +
overall), 263-310 (_get_feedback_data filters + agent_name enrichment),
329-353 (get_export_filters), and the full CSV formula-injection matrix
(CWE-1236: = + - @ prefixes, tab/CR, non-string pass-through) plus the
200-char truncation of original_output/user_correction.
"""
from datetime import datetime, timedelta
import json
from io import StringIO
import csv
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.feedback_export_service import _sanitize_csv_cell, FeedbackExportService
from core.models import AgentFeedback, AgentRegistry, User  # noqa: F401


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_agent(db, agent_id="agent-1"):
    existing = db.query(AgentRegistry).filter(
        AgentRegistry.id == agent_id).first()
    if existing:
        return existing
    agent = AgentRegistry(
        id=agent_id, name=f"Agent {agent_id}", workspace_id="ws-1",
        tenant_id="t1", category="Test", module_path="test",
        class_name="Test",
    )
    db.add(agent)
    db.commit()
    return agent


def _make_user(db, user_id="user-1"):
    existing = db.query(User).filter(User.id == user_id).first()
    if existing:
        return existing
    user = User(id=user_id, email=f"{user_id}@example.com", first_name="T",
                last_name="U", role="member", status="active")
    db.add(user)
    db.commit()
    return user


def _make_feedback(db, feedback_id, *, agent_id="agent-1", user_id="user-1",
                   feedback_type="correction", status="pending",
                   original_output="out", user_correction="fix",
                   thumbs_up_down=None, rating=None, created_days=1,
                   adjudicated_at=None, agent_execution_id=None,
                   input_context=None, ai_reasoning=None,
                   create_agent=True):
    if create_agent:
        _make_agent(db, agent_id)
    _make_user(db, user_id)
    fb = AgentFeedback(
        id=feedback_id,
        agent_id=agent_id,
        user_id=user_id,
        input_context=input_context,
        original_output=original_output,
        user_correction=user_correction,
        feedback_type=feedback_type,
        thumbs_up_down=thumbs_up_down,
        rating=rating,
        status=status,
        ai_reasoning=ai_reasoning,
        created_at=datetime.now() - timedelta(days=created_days),
        adjudicated_at=adjudicated_at,
        agent_execution_id=agent_execution_id,
    )
    db.add(fb)
    db.commit()
    return fb


# ============================================================================
# CSV sanitization (CWE-1236)
# ============================================================================

class TestCsvSanitization:
    @pytest.mark.parametrize("payload", [
        "=cmd|' /C calc'!A0",
        "+SUM(A1:A9)",
        "-2+3+cmd",
        "@import-malicious",
        "=1+2",
        "\t=tab-start",
        "\r=carriage-return",
    ])
    def test_injection_prefixes_are_quoted(self, payload):
        assert _sanitize_csv_cell(payload) == "'" + payload

    @pytest.mark.parametrize("safe", [
        "normal text",
        "0=equals-after-zero",
        "1+2",
        "text@domain",
    ])
    def test_safe_cells_unchanged(self, safe):
        assert _sanitize_csv_cell(safe) == safe

    def test_non_string_values_unchanged(self):
        assert _sanitize_csv_cell(42) == 42
        assert _sanitize_csv_cell(None) is None
        assert _sanitize_csv_cell(3.14) == 3.14


# ============================================================================
# export_to_csv
# ============================================================================

class TestExportCsv:
    def test_export_to_csv_header_and_sanitized_rows(self, db):
        _make_feedback(db, "fb-1", original_output="safe",
                       user_correction="=HARM()", status="adjudicated",
                       adjudicated_at=datetime(2026, 1, 2))
        svc = FeedbackExportService(db)
        csv_data = svc.export_to_csv()
        reader = list(csv.reader(StringIO(csv_data)))
        assert reader[0][0] == "feedback_id"
        row = reader[1]
        assert row[0] == "fb-1"
        assert row[9] == "'=HARM()"  # injection neutralized
        assert row[11]  # created_at present

    def test_export_to_csv_truncates_long_text(self, db):
        long_out = "x" * 500
        long_fix = "y" * 500
        _make_feedback(db, "fb-1", original_output=long_out,
                       user_correction=long_fix)
        svc = FeedbackExportService(db)
        csv_data = svc.export_to_csv()
        reader = list(csv.reader(StringIO(csv_data)))
        assert len(reader[1][8]) == 200
        assert len(reader[1][9]) == 200

    def test_export_to_csv_injection_in_id_and_agent(self, db):
        _make_feedback(db, "=SUM(1,1)", agent_id="=agent",
                       original_output="o", user_correction="c")
        svc = FeedbackExportService(db)
        csv_data = svc.export_to_csv()
        reader = list(csv.reader(StringIO(csv_data)))
        assert reader[1][0] == "'=SUM(1,1)"
        assert reader[1][1] == "'=agent"

    def test_export_to_csv_missing_optional_fields_default_empty(self, db):
        _make_feedback(db, "fb-1", feedback_type=None, status="pending",
                       original_output="o", user_correction="c")
        svc = FeedbackExportService(db)
        csv_data = svc.export_to_csv()
        reader = list(csv.reader(StringIO(csv_data)))
        assert reader[1][5] == ""  # feedback_type

    def test_export_to_csv_empty_result(self, db):
        csv_data = FeedbackExportService(db).export_to_csv()
        assert csv_data.strip() == ",".join([
            "feedback_id", "agent_id", "agent_name", "agent_execution_id",
            "user_id", "feedback_type", "thumbs_up_down", "rating",
            "original_output", "user_correction", "status", "created_at",
            "adjudicated_at"])


# ============================================================================
# export_to_json & summary
# ============================================================================

class TestExportJson:
    def test_export_to_json_shape_and_filters(self, db):
        _make_feedback(db, "fb-1", feedback_type="correction")
        _make_feedback(db, "fb-2", feedback_type="rating")
        svc = FeedbackExportService(db)
        data = svc.export_to_json(feedback_type="rating")
        parsed = json.loads(data)
        assert parsed["total_records"] == 1
        assert parsed["feedback"][0]["id"] == "fb-2"
        assert parsed["filters"]["feedback_type"] == "rating"

    def test_export_to_json_empty(self, db):
        parsed = json.loads(FeedbackExportService(db).export_to_json())
        assert parsed["total_records"] == 0

    def test_export_summary_to_json_per_agent(self, db):
        _make_feedback(db, "fb-1")
        svc = FeedbackExportService(db)
        with patch("core.feedback_analytics.FeedbackAnalytics"
                   ".get_agent_feedback_summary",
                   return_value={"total": 1, "avg_rating": 4.0}):
            parsed = json.loads(svc.export_summary_to_json(agent_id="agent-1"))
        assert parsed["agent_id"] == "agent-1"
        assert parsed["agent_name"] == "Agent agent-1"
        assert parsed["summary"]["total"] == 1

    def test_export_summary_to_json_agent_without_registry_row(self, db):
        _make_feedback(db, "fb-1", agent_id="ghost-agent",
                       create_agent=False)
        svc = FeedbackExportService(db)
        with patch("core.feedback_analytics.FeedbackAnalytics"
                   ".get_agent_feedback_summary",
                   return_value={"total": 1}):
            parsed = json.loads(svc.export_summary_to_json(
                agent_id="ghost-agent"))
        assert parsed["agent_name"] == ""

    def test_export_summary_to_json_overall(self, db):
        _make_feedback(db, "fb-1")
        svc = FeedbackExportService(db)
        with patch("core.feedback_analytics.FeedbackAnalytics"
                   ".get_feedback_statistics",
                   return_value={"total": 1, "positive": 1}):
            parsed = json.loads(svc.export_summary_to_json())
        assert parsed["summary"]["total"] == 1
        assert "agent_id" not in parsed


# ============================================================================
# _get_feedback_data & get_export_filters
# ============================================================================

class TestDataRetrieval:
    def test_get_feedback_data_applies_all_filters(self, db):
        _make_feedback(db, "fb-1", agent_id="agent-1",
                       feedback_type="correction", status="pending",
                       created_days=1)
        _make_feedback(db, "fb-2", agent_id="agent-2",
                       feedback_type="correction", status="pending",
                       created_days=1)
        _make_feedback(db, "fb-3", agent_id="agent-1",
                       feedback_type="rating", status="pending",
                       created_days=1)
        _make_feedback(db, "fb-4", agent_id="agent-1",
                       feedback_type="correction", status="adjudicated",
                       created_days=40)  # outside the 30-day window
        svc = FeedbackExportService(db)
        data = svc._get_feedback_data(
            agent_id="agent-1", days=30, feedback_type="correction",
            status="pending")
        assert [d["id"] for d in data] == ["fb-1"]
        assert data[0]["agent_name"] == "Agent agent-1"
        assert data[0]["created_at"] is not None
        assert data[0]["adjudicated_at"] is None

    def test_get_feedback_data_limit(self, db):
        for i in range(5):
            _make_feedback(db, f"fb-{i}", original_output=f"o{i}",
                           user_correction=f"c{i}")
        svc = FeedbackExportService(db)
        assert len(svc._get_feedback_data(limit=2)) == 2

    def test_get_feedback_data_orders_newest_first(self, db):
        _make_feedback(db, "old", created_days=10, original_output="old",
                       user_correction="c")
        _make_feedback(db, "new", created_days=1, original_output="new",
                       user_correction="c")
        svc = FeedbackExportService(db)
        assert svc._get_feedback_data()[0]["id"] == "new"

    def test_get_export_filters(self, db):
        _make_feedback(db, "fb-1", feedback_type="correction",
                       status="pending")
        _make_feedback(db, "fb-2", feedback_type="rating", status="pending")
        _make_feedback(db, "fb-3", feedback_type=None, status="adjudicated")
        _make_feedback(db, "fb-4", agent_id="ghost", feedback_type="comment",
                       status="pending", create_agent=False)
        svc = FeedbackExportService(db)
        filters = svc.get_export_filters(db)
        agent_ids = [a["id"] for a in filters["agents"]]
        assert "agent-1" in agent_ids
        assert "ghost" not in agent_ids  # no AgentRegistry row -> excluded
        assert sorted(filters["feedback_types"]) == ["comment", "correction",
                                                     "rating"]
        assert set(filters["statuses"]) == {"pending", "adjudicated"}
        agents = {a["id"]: a for a in filters["agents"]}
        assert agents["agent-1"]["name"] == "Agent agent-1"

    def test_get_export_filters_empty(self, db):
        filters = FeedbackExportService(db).get_export_filters(db)
        assert filters == {"agents": [], "feedback_types": [], "statuses": []}
