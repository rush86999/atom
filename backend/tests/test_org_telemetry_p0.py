"""P0 — Agent org-dynamics telemetry (AGENT_ORG_POLITICS_PLAN.md Phase 0).

Implements:
- core/models.py: AgentOrgEvent (append-only ``agent_org_events`` table)
- core/org_telemetry_service.py: AgentOrgTelemetryService + compute helpers
  (incumbency, review acceptance rates, radio→recruit COI pairs)
- Wire-in points: fleet recruitment (_recruit_fleet), radio thread attach
  (radio_adapter.attach_thread_for_chain), radio message send
  (radio_service.send_message), reviewer verdicts (review.py).

Style: isolated in-memory sqlite, zero LLM spend, no network.
Flag ATOM_ORG_TELEMETRY_ENABLED default ON; emission never raises.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def db():
    from core.models import AgentOrgEvent, AgentThread, LateralMessage

    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    AgentOrgEvent.__table__.create(engine)
    AgentThread.__table__.create(engine)
    LateralMessage.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def telemetry(db):
    from core.org_telemetry_service import AgentOrgTelemetryService

    return AgentOrgTelemetryService(db)


# ============================================================================
# Model + service basics
# ============================================================================


class TestAgentOrgEventModel:
    def test_table_exists_and_roundtrip(self, db):
        from core.models import AgentOrgEvent

        row = AgentOrgEvent(
            event_type="fleet_recruit",
            actor_agent_id="atom_main",
            target_agent_id="spec_finance",
            chain_id="chain-1",
            payload_json={"domain": "finance"},
        )
        db.add(row)
        db.commit()
        got = db.query(AgentOrgEvent).filter_by(event_type="fleet_recruit").first()
        assert got is not None
        assert got.actor_agent_id == "atom_main"
        assert got.target_agent_id == "spec_finance"
        assert got.payload_json["domain"] == "finance"

    def test_event_type_indexed_column_present(self):
        from core.models import AgentOrgEvent

        cols = {c.name for c in AgentOrgEvent.__table__.columns}
        assert {
            "id", "created_at", "event_type", "actor_agent_id",
            "target_agent_id", "execution_id", "chain_id",
            "workspace_id", "tenant_id", "payload_json",
        } <= cols


class TestEmit:
    def test_emit_writes_row_and_returns_it(self, telemetry, db):
        row = telemetry.emit(
            "fleet_recruit",
            actor_agent_id="atom_main",
            target_agent_id="spec_sales",
            chain_id="c1",
            payload={"domain": "sales"},
        )
        assert row is not None
        assert row.id
        assert db.query(type(row)).count() == 1

    def test_emit_flag_off_writes_nothing(self, telemetry, db, monkeypatch):
        monkeypatch.setenv("ATOM_ORG_TELEMETRY_ENABLED", "false")
        row = telemetry.emit("fleet_recruit", actor_agent_id="a", target_agent_id="b")
        assert row is None
        from core.models import AgentOrgEvent

        assert db.query(AgentOrgEvent).count() == 0

    def test_emit_never_raises_on_db_error(self, telemetry):
        class ExplodingDb:
            def add(self, _):
                raise RuntimeError("disk on fire")

            def commit(self):
                raise RuntimeError("disk on fire")

        svc = type(telemetry)(ExplodingDb())
        assert svc.emit("review_verdict", target_agent_id="x") is None

    def test_emit_fleet_recruit_one_row_per_member(self, telemetry, db):
        rows = telemetry.emit_fleet_recruit(
            coordinator_agent_id="atom_main",
            members=[
                {"agent_id": "s1", "domain": "finance"},
                {"agent_id": "s2", "domain": "sales"},
            ],
            chain_id="c9",
        )
        from core.models import AgentOrgEvent

        assert len(rows) == 2
        pairs = {
            (r.actor_agent_id, r.target_agent_id) for r in rows
        }
        assert ("atom_main", "s1") in pairs and ("atom_main", "s2") in pairs
        assert db.query(AgentOrgEvent).count() == 2


# ============================================================================
# Compute helpers (the report math)
# ============================================================================


class TestComputeIncumbency:
    def test_repeated_pair_is_incumbent(self, telemetry):
        for _ in range(4):
            telemetry.emit("fleet_recruit", actor_agent_id="coord", target_agent_id="s1")
        telemetry.emit("fleet_recruit", actor_agent_id="coord", target_agent_id="s2")
        report = telemetry.compute_incumbency()
        top = report["top_pairs"][0]
        assert top["actor"] == "coord"
        assert top["target"] == "s1"
        assert top["count"] == 4
        assert report["repeat_pair_ratio"] >= 0.5


class TestComputeReviewRates:
    def test_acceptance_rates_per_target(self, telemetry):
        for _ in range(3):
            telemetry.emit(
                "review_verdict", target_agent_id="s1",
                payload={"accepted": True},
            )
        telemetry.emit(
            "review_verdict", target_agent_id="s1",
            payload={"accepted": False},
        )
        rates = telemetry.compute_review_rates()
        assert rates["by_target"]["s1"]["accepted"] == 3
        assert rates["by_target"]["s1"]["rejected"] == 1


class TestComputeCoiPairs:
    def test_radio_then_recruit_flags_coi(self, telemetry):
        # s_radio messages coord (social contact), then coord recruits s_radio
        telemetry.emit(
            "radio_message", actor_agent_id="s_radio",
            target_agent_id="coord", payload={},
        )
        telemetry.emit(
            "fleet_recruit", actor_agent_id="coord",
            target_agent_id="s_radio", payload={},
        )
        coi = telemetry.compute_coi_pairs(window_hours=24 * 30)
        assert ("coord", "s_radio") in [(c["actor"], c["target"]) for c in coi]

    def test_unrelated_pairs_not_flagged(self, telemetry):
        telemetry.emit("fleet_recruit", actor_agent_id="coord", target_agent_id="stranger")
        assert telemetry.compute_coi_pairs(window_hours=720) == []


# ============================================================================
# Wire-in points
# ============================================================================


class TestRadioAttachEmits:
    def test_attach_thread_emits_event(self, db, monkeypatch):
        from core.agent_radio import radio_adapter
        from core.models import AgentOrgEvent

        monkeypatch.setattr(
            "core.agent_radio.radio_config.radio_enabled", lambda: True
        )

        class Triggered:
            triggered = True
            reasons = ["test"]

        monkeypatch.setattr(
            "core.agent_radio.radio_adapter.should_attach_thread",
            lambda task: Triggered(),
        )

        thread = radio_adapter.attach_thread_for_chain(
            db,
            chain_id="chain-x",
            task_description="coordinate across teams",
            team_agent_ids=["a1", "a2"],
            created_by_agent_id="atom_main",
        )
        assert thread is not None
        evt = (
            db.query(AgentOrgEvent)
            .filter_by(event_type="radio_thread_attach")
            .first()
        )
        assert evt is not None
        assert evt.target_agent_id == "chain-x"


class TestRadioMessageEmits:
    def test_send_message_emits_event(self, db):
        from core.agent_radio import radio_service
        from core.models import AgentOrgEvent

        thread = radio_service.create_thread(
            db,
            name="t",
            created_by_agent_id="coord",
            member_agent_ids=["peer"],
        )
        msg = radio_service.send_message(
            db,
            thread_id=thread.id,
            from_agent_id="peer",
            content="hello @coord",
            to_agent_id="coord",
        )
        assert msg.id
        evt = (
            db.query(AgentOrgEvent)
            .filter_by(event_type="radio_message")
            .first()
        )
        assert evt is not None
        assert evt.actor_agent_id == "peer"
        assert evt.target_agent_id == "coord"


class TestReviewerVerdictEmits:
    @pytest.fixture
    def owned_session_is_test_db(self, db, monkeypatch):
        """Route emit_org_event's self-opened session to this test's sqlite."""
        import contextlib

        @contextlib.contextmanager
        def fake_session():
            yield db

        monkeypatch.setattr("core.database.get_db_session", fake_session)

    @pytest.mark.asyncio
    async def test_rejected_review_emits_event(
        self, db, owned_session_is_test_db
    ):
        from core.orchestration.verification.review import ReviewerVerifier
        from core.models import AgentOrgEvent

        class FakeLLM:
            def generate_response(self, prompt):
                return '{"accept": false, "score": 0.2, "feedback": "gap"}'

        verifier = ReviewerVerifier(FakeLLM())

        class Step:
            description = "do the thing"
            step_id = "step-42"

        result = await verifier.verify([{"answer": "partial"}], Step(), context=None)
        assert result.winner is None  # rejected

        evt = (
            db.query(AgentOrgEvent)
            .filter_by(event_type="review_verdict")
            .first()
        )
        assert evt is not None
        assert evt.payload_json["accepted"] is False

    @pytest.mark.asyncio
    async def test_accepted_review_emits_event(
        self, db, owned_session_is_test_db
    ):
        from core.orchestration.verification.review import ReviewerVerifier
        from core.models import AgentOrgEvent

        class FakeLLM:
            def generate_response(self, prompt):
                return '{"accept": true, "score": 0.9, "feedback": ""}'

        verifier = ReviewerVerifier(FakeLLM())

        class Step:
            description = "do the thing"
            step_id = "step-7"

        await verifier.verify([{"answer": "full"}], Step(), context=None)
        evt = (
            db.query(AgentOrgEvent)
            .filter_by(event_type="review_verdict")
            .first()
        )
        assert evt is not None
        assert evt.payload_json["accepted"] is True


class TestRecruitHelperUsedByMetaAgent:
    def test_meta_agent_source_wires_helper(self):
        import inspect

        from core import atom_meta_agent

        src = inspect.getsource(atom_meta_agent.AtomMetaAgent._recruit_fleet)
        assert "emit_fleet_recruit" in src or "emit_org_event" in src
