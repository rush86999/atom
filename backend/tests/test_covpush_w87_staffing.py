# -*- coding: utf-8 -*-
"""Coverage wave 87 — core/staffing_advisor (standalone, zero LLM spend,
no network; fake db rows + mocked AI + mocked resource monitor).

- _extract_required_skills: comma-separated str response; list response; dict
  with 'skills' key; unrecognized shape → []; AI exception → [] (logged).
- recommend_staff: no skills extracted → error status; no active users →
  success with empty recommendations; JSON-array skills parsing; comma-list
  skills parsing; unparseable skills → warning + fallback (no crash); None
  skills → no match, skipped; zero-match users skipped; >95% utilized users
  skipped; recommendations sorted by match_score DESC then utilization ASC;
  limit applied; full result envelope (required_skills + recommendations with
  match_score/matched_skills/current_utilization/risk_level).
"""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.staffing_advisor import StaffingAdvisor, staffing_advisor


@contextmanager
def _cm(value):
    yield value


def _run(coro):
    import asyncio
    return asyncio.run(coro)


def _user(user_id="u1", first="Alice", last="Smith", skills=None):
    return SimpleNamespace(
        id=user_id, first_name=first, last_name=last, skills=skills,
        workspace_id="ws-1", status="active",
    )


def _ai_response(response, side_effect=None):
    ai = MagicMock()
    ai.process_with_nlu = AsyncMock(
        return_value=response, side_effect=side_effect
    )
    return ai


class _FakeQuery:
    def __init__(self, rows, exprs=None):
        self._rows = rows
        self._exprs = exprs or []

    def filter(self, *exprs):
        self._exprs.extend(exprs)
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, users):
        self._users = users

    def query(self, model):
        return _FakeQuery(self._users)


class _Monitor:
    def __init__(self, utils):
        self._utils = utils
        self.calculate_utilization = MagicMock(
            side_effect=lambda uid, db=None: self._utils.get(uid, {
                "utilization_percentage": 0,
                "risk_level": "low",
            })
        )


class TestExtractRequiredSkills:
    def test_string_response_split(self):
        with patch("core.staffing_advisor.get_ai_service",
                   return_value=_ai_response("Python, Graphic Design, PM")):
            skills = _run(StaffingAdvisor()._extract_required_skills("desc"))
        assert skills == ["Python", "Graphic Design", "PM"]

    def test_list_response_passthrough(self):
        with patch("core.staffing_advisor.get_ai_service",
                   return_value=_ai_response(["SQL", "React"])):
            assert _run(StaffingAdvisor()._extract_required_skills("d")) == ["SQL", "React"]

    def test_dict_response_with_skills(self):
        with patch("core.staffing_advisor.get_ai_service",
                   return_value=_ai_response({"skills": ["AWS"]})):
            assert _run(StaffingAdvisor()._extract_required_skills("d")) == ["AWS"]

    def test_unrecognized_shape_returns_empty(self):
        with patch("core.staffing_advisor.get_ai_service",
                   return_value=_ai_response(42)):
            assert _run(StaffingAdvisor()._extract_required_skills("d")) == []

    def test_ai_exception_returns_empty(self):
        with patch("core.staffing_advisor.get_ai_service",
                   return_value=_ai_response(None, side_effect=RuntimeError("llm down"))):
            assert _run(StaffingAdvisor()._extract_required_skills("d")) == []


class TestRecommendStaff:
    def test_no_required_skills_returns_error(self):
        ai = _ai_response([])
        with patch("core.staffing_advisor.get_ai_service", return_value=ai):
            result = _run(StaffingAdvisor().recommend_staff("desc", "ws-1"))
        assert result["status"] == "error"
        assert "required skills" in result["message"]

    def test_empty_workspace_success(self):
        ai = _ai_response("Python")
        fake_db = _FakeDB([])
        monitor = _Monitor({})
        with patch("core.staffing_advisor.get_ai_service", return_value=ai), \
                patch("core.staffing_advisor.get_db_session", return_value=_cm(fake_db)), \
                patch("core.staffing_advisor.resource_monitor", monitor):
            result = _run(StaffingAdvisor().recommend_staff("desc", "ws-1"))
        assert result["status"] == "success"
        assert result["required_skills"] == ["Python"]
        assert result["recommendations"] == []

    def test_json_list_skills_match(self):
        ai = _ai_response("Python, SQL")
        users = [
            _user("u1", skills='["python", "sql"]'),
            _user("u2", skills='["python"]'),
        ]
        fake_db = _FakeDB(users)
        monitor = _Monitor({})
        with patch("core.staffing_advisor.get_ai_service", return_value=ai), \
                patch("core.staffing_advisor.get_db_session", return_value=_cm(fake_db)), \
                patch("core.staffing_advisor.resource_monitor", monitor):
            result = _run(StaffingAdvisor().recommend_staff("desc", "ws-1"))
        assert result["status"] == "success"
        recs = result["recommendations"]
        assert len(recs) == 2
        u1 = next(r for r in recs if r["user_id"] == "u1")
        assert u1["match_score"] == 100.0
        assert u1["matched_skills"] == ["Python", "SQL"]
        u2 = next(r for r in recs if r["user_id"] == "u2")
        assert u2["match_score"] == 50.0

    def test_comma_list_skills_match(self):
        ai = _ai_response("Python")
        users = [_user("u1", skills="Python, SQL")]
        fake_db = _FakeDB(users)
        monitor = _Monitor({})
        with patch("core.staffing_advisor.get_ai_service", return_value=ai), \
                patch("core.staffing_advisor.get_db_session", return_value=_cm(fake_db)), \
                patch("core.staffing_advisor.resource_monitor", monitor):
            result = _run(StaffingAdvisor().recommend_staff("desc", "ws-1"))
        assert result["recommendations"][0]["user_id"] == "u1"

    def test_unparseable_skills_fall_back_without_crash(self):
        ai = _ai_response("Python")
        users = [_user("u1", skills="[python, sql")]
        fake_db = _FakeDB(users)
        monitor = _Monitor({})
        with patch("core.staffing_advisor.get_ai_service", return_value=ai), \
                patch("core.staffing_advisor.get_db_session", return_value=_cm(fake_db)), \
                patch("core.staffing_advisor.resource_monitor", monitor):
            result = _run(StaffingAdvisor().recommend_staff("desc", "ws-1"))
        assert result["status"] == "success"

    def test_no_skill_users_and_no_match_users_skipped(self):
        ai = _ai_response("Python")
        users = [
            _user("u1", skills=None),
            _user("u2", skills="marketing"),
        ]
        fake_db = _FakeDB(users)
        monitor = _Monitor({})
        with patch("core.staffing_advisor.get_ai_service", return_value=ai), \
                patch("core.staffing_advisor.get_db_session", return_value=_cm(fake_db)), \
                patch("core.staffing_advisor.resource_monitor", monitor):
            result = _run(StaffingAdvisor().recommend_staff("desc", "ws-1"))
        assert result["recommendations"] == []

    def test_over_95_percent_utilization_skipped(self):
        ai = _ai_response("Python")
        users = [_user("u1", skills="Python")]
        fake_db = _FakeDB(users)
        monitor = _Monitor({
            "u1": {"utilization_percentage": 96, "risk_level": "high"},
        })
        with patch("core.staffing_advisor.get_ai_service", return_value=ai), \
                patch("core.staffing_advisor.get_db_session", return_value=_cm(fake_db)), \
                patch("core.staffing_advisor.resource_monitor", monitor):
            result = _run(StaffingAdvisor().recommend_staff("desc", "ws-1"))
        assert result["recommendations"] == []

    def test_utilization_fields_surface_in_recommendation(self):
        ai = _ai_response("Python")
        users = [_user("u1", skills="Python")]
        fake_db = _FakeDB(users)
        monitor = _Monitor({
            "u1": {"utilization_percentage": 55, "risk_level": "medium"},
        })
        with patch("core.staffing_advisor.get_ai_service", return_value=ai), \
                patch("core.staffing_advisor.get_db_session", return_value=_cm(fake_db)), \
                patch("core.staffing_advisor.resource_monitor", monitor):
            result = _run(StaffingAdvisor().recommend_staff("desc", "ws-1"))
        rec = result["recommendations"][0]
        assert rec["name"] == "Alice Smith"
        assert rec["current_utilization"] == 55
        assert rec["risk_level"] == "medium"

    def test_sorting_match_desc_then_utilization_asc(self):
        ai = _ai_response("Python, SQL")
        users = [
            _user("u1", skills="Python"),
            _user("u2", skills="Python"),
            _user("u3", skills="Python, SQL"),
        ]
        fake_db = _FakeDB(users)
        monitor = _Monitor({
            "u1": {"utilization_percentage": 90, "risk_level": "medium"},
            "u2": {"utilization_percentage": 10, "risk_level": "low"},
            "u3": {"utilization_percentage": 50, "risk_level": "low"},
        })
        with patch("core.staffing_advisor.get_ai_service", return_value=ai), \
                patch("core.staffing_advisor.get_db_session", return_value=_cm(fake_db)), \
                patch("core.staffing_advisor.resource_monitor", monitor):
            result = _run(StaffingAdvisor().recommend_staff("desc", "ws-1"))
        assert [r["user_id"] for r in result["recommendations"]] == ["u3", "u2", "u1"]

    def test_limit_applied(self):
        ai = _ai_response("Python")
        users = [_user(f"u{i}", skills="Python") for i in range(5)]
        fake_db = _FakeDB(users)
        monitor = _Monitor({})
        with patch("core.staffing_advisor.get_ai_service", return_value=ai), \
                patch("core.staffing_advisor.get_db_session", return_value=_cm(fake_db)), \
                patch("core.staffing_advisor.resource_monitor", monitor):
            result = _run(StaffingAdvisor().recommend_staff("desc", "ws-1", limit=2))
        assert len(result["recommendations"]) == 2

    def test_module_singleton(self):
        assert isinstance(staffing_advisor, StaffingAdvisor)
