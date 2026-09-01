"""Autonomy policy gating: canvas-topic grouping + the shared
mode × maturity × trust gate (core.autonomy_policy.gate_for_topic).

Regression context (Aug 31, 2026): the Autonomy tab showed only the owner's
static mode per topic — no canvas relevance, and no indication of what the
hire would ACTUALLY do today. The panel and the runtime paths now evaluate
the same gate_for_topic, and the topics shown lead with the ones the open
canvas's type exercises.
"""
import contextlib
from unittest.mock import MagicMock, patch

import pytest

from core import autonomy_policy as ap


@pytest.fixture()
def fresh_db(tmp_path):
    """Brand-new sqlite schema (same way app startup creates it)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.models import Base

    eng = create_engine(f"sqlite:///{tmp_path}/autonomy_gate.db")
    Base.metadata.create_all(bind=eng)
    Sess = sessionmaker(bind=eng, expire_on_commit=False)

    @contextlib.contextmanager
    def db_session():
        s = Sess()
        try:
            yield s
        finally:
            s.close()

    yield db_session
    eng.dispose()


def _gov(allowed=True, agent_status="intern", required="intern"):
    gov = MagicMock()
    gov.can_perform_action.return_value = {
        "allowed": allowed,
        "agent_status": agent_status,
        "required_status": required,
        "reason": "ok" if allowed else "Maturity check failed.",
    }
    return gov


# ───────────── canvas-topic grouping ─────────────


def test_topics_for_canvas_email_vs_default():
    """An email canvas exercises sends/CRM; every other surface is a
    document-ish canvas where edits and tasks are the point."""
    assert ap.topics_for_canvas("email") == ["send_email", "crm_write"]
    assert ap.topics_for_canvas("EMAIL") == ["send_email", "crm_write"]
    assert ap.topics_for_canvas("orchestration") == ["task_create", "canvas_edit"]
    assert ap.topics_for_canvas("document") == ap.DEFAULT_CANVAS_TOPICS
    assert ap.topics_for_canvas("spreadsheet") == ap.DEFAULT_CANVAS_TOPICS
    assert ap.topics_for_canvas(None) == ap.DEFAULT_CANVAS_TOPICS
    assert ap.topics_for_canvas("some-future-type") == ap.DEFAULT_CANVAS_TOPICS


def test_list_topics_flags_canvas_relevance(fresh_db):
    with fresh_db() as db:
        topics = ap.list_topics("u-1", db, canvas_type="email")
        by_topic = {t["topic"]: t for t in topics}
        assert by_topic["send_email"]["canvas_relevant"] is True
        assert by_topic["crm_write"]["canvas_relevant"] is True
        assert by_topic["canvas_edit"]["canvas_relevant"] is False
        assert by_topic["task_create"]["canvas_relevant"] is False

        # No canvas context → nothing is canvas-primary (general-only panel)
        topics = ap.list_topics("u-1", db)
        assert all(t["canvas_relevant"] is False for t in topics)


# ───────────── the shared gate ─────────────


def test_gate_human_always_proposes_even_for_mature_hire(fresh_db):
    with fresh_db() as db:
        ap.set_mode(db, "u-1", "send_email", ap.MODE_HUMAN_ALWAYS)
        with patch(
            "core.service_factory.ServiceFactory.get_governance_service",
            return_value=_gov(allowed=True, agent_status="autonomous"),
        ):
            gate = ap.gate_for_topic(db, "u-1", "send_email", "hire-1")
    assert gate["outcome"] == ap.OUTCOME_PROPOSE
    assert gate["maturity"]["ok"] is True
    assert "approve" in gate["reason"].lower()


def test_gate_auto_plus_mature_executes(fresh_db):
    with fresh_db() as db:
        ap.set_mode(db, "u-1", "canvas_edit", ap.MODE_AUTO_IF_MATURE)
        with patch(
            "core.service_factory.ServiceFactory.get_governance_service",
            return_value=_gov(allowed=True, agent_status="supervised", required="intern"),
        ):
            gate = ap.gate_for_topic(db, "u-1", "canvas_edit", "hire-1")
    assert gate["outcome"] == ap.OUTCOME_EXECUTE
    assert gate["maturity"]["maturity_level"] == "supervised"
    assert gate["maturity"]["required"] == "intern"


def test_gate_auto_plus_immature_proposes(fresh_db):
    with fresh_db() as db:
        with patch(
            "core.service_factory.ServiceFactory.get_governance_service",
            return_value=_gov(allowed=False, agent_status="student", required="intern"),
        ):
            gate = ap.gate_for_topic(db, "u-1", "canvas_edit", "hire-1")
    assert gate["outcome"] == ap.OUTCOME_PROPOSE
    assert gate["maturity"]["ok"] is False
    assert "maturity" in gate["reason"].lower()


def test_gate_without_hire_failopen(fresh_db):
    """No resolved hire (platform assistant) → only the owner's mode gates."""
    with fresh_db() as db:
        gate = ap.gate_for_topic(db, "u-1", "canvas_edit", None)
    assert gate["maturity"]["known"] is False
    assert gate["maturity"]["ok"] is True
    assert gate["outcome"] == ap.OUTCOME_EXECUTE


# ───────────── trust leg (flag-gated, R8 skill-scoped) ─────────────


def _agent(session, agent_id, verified, total):
    from core.models import AgentRegistry

    session.add(
        AgentRegistry(
            id=agent_id,
            name=f"hire-{agent_id}",
            category="Operations",
            role="agent",
            type="personal",
            capabilities=[],
            module_path="operations.test",
            class_name="TestAgent",
            status="supervised",
            configuration={
                "capability_stats": {
                    "send_email": {"total": total, "verified_success": verified}
                }
            },
        )
    )
    session.commit()


def test_trust_gate_off_is_neutral_pass(fresh_db):
    """Flag off (default) → no trust gating anywhere; panel says so."""
    with fresh_db() as db:
        _agent(db, "hire-1", verified=0, total=20)
        check = ap.trust_check(db, "hire-1", "send_email")
    assert check["enabled"] is False
    assert check["ok"] is True


def test_trust_gate_low_score_demotes_to_propose(fresh_db):
    """Verified ratio 0.2 < 0.6 bar → propose, even with policy + maturity
    green. Only VERIFIED successes count — unverified inflation never earns
    autonomy (graduation policy parity)."""
    with fresh_db() as db:
        _agent(db, "hire-1", verified=2, total=10)
        ap.set_mode(db, "u-1", "send_email", ap.MODE_AUTO_IF_MATURE)
        with patch(
            "core.skill_scoped_trust.skill_scoped_trust_enabled", return_value=True
        ), patch(
            "core.service_factory.ServiceFactory.get_governance_service",
            return_value=_gov(allowed=True),
        ):
            gate = ap.gate_for_topic(db, "u-1", "send_email", "hire-1")
            check = ap.trust_check(db, "hire-1", "send_email")
    assert check["enabled"] is True
    assert check["ok"] is False
    assert gate["outcome"] == ap.OUTCOME_PROPOSE
    assert "trust" in gate["reason"].lower()


def test_trust_gate_high_score_executes(fresh_db):
    with fresh_db() as db:
        _agent(db, "hire-1", verified=9, total=10)
        ap.set_mode(db, "u-1", "send_email", ap.MODE_AUTO_IF_MATURE)
        with patch(
            "core.skill_scoped_trust.skill_scoped_trust_enabled", return_value=True
        ), patch(
            "core.service_factory.ServiceFactory.get_governance_service",
            return_value=_gov(allowed=True),
        ):
            gate = ap.gate_for_topic(db, "u-1", "send_email", "hire-1")
    assert gate["outcome"] == ap.OUTCOME_EXECUTE


def test_trust_gate_unknown_agent_failopen(fresh_db):
    with fresh_db() as db, patch(
        "core.skill_scoped_trust.skill_scoped_trust_enabled", return_value=True
    ):
        check = ap.trust_check(db, "ghost-agent", "send_email")
    assert check["enabled"] is False
    assert check["ok"] is True


def test_gate_topics_have_governance_metadata():
    """Every policy topic must carry its runtime action + maturity bar so the
    panel never shows a topic it cannot explain."""
    for topic in ap.TOPICS:
        meta = ap.TOPIC_GATES[topic]
        assert meta["governance_action"]
        assert meta["min_maturity"] in ("student", "intern", "supervised", "autonomous")
        assert meta["trust_domain"]
        assert 0.0 < float(meta.get("trust_threshold", ap.AUTONOMY_TRUST_THRESHOLD)) <= 1.0
