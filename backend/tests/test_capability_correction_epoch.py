"""A human correction opens a fresh verified-success epoch at the reset.

Historical lifetime counters stay auditable, but only successes AFTER the
reset may climb the normal 5/20/50 ladder. No failure/regression counts are
invented for a correction.
"""
from copy import deepcopy

from core.autonomy_policy import autonomy_cycle, reset_autonomy_cycle
from core.capability_graduation_service import CapabilityGraduationService
from core.models import AgentRegistry
from tests.test_autonomy_revocation import store


def _configure(db, *, verified=50):
    row = db.get(AgentRegistry, "agent-revocation-1")
    cfg = deepcopy(row.configuration)
    stats = cfg.setdefault("capability_stats", {})
    stats["canvas_edit"] = {
        "success": verified,
        "total": verified,
        "verified_success": verified,
    }
    cfg.setdefault("capability_maturities", {})["canvas_edit"] = "autonomous"
    row.configuration = cfg
    db.commit()
    return row.id


def test_human_correction_does_not_reuse_lifetime_credit(store):
    Session, db = store
    agent_id = _configure(db, verified=50)
    assert reset_autonomy_cycle(
        db, agent_id, "canvas_edit",
        reason="owner corrected the business rule") is True
    db.close()

    with Session() as fresh:
        service = CapabilityGraduationService(fresh)
        assert service.get_maturity(agent_id, "canvas_edit") == "student"
        service.record_usage(agent_id, "canvas_edit", True, "verified")
        assert service.get_maturity(agent_id, "canvas_edit") == "student"
        assert autonomy_cycle(fresh, agent_id, "canvas_edit")["ok"] is False

        cfg = fresh.get(AgentRegistry, agent_id).configuration
        stats = cfg["capability_stats"]["canvas_edit"]
        assert stats["verified_success"] == 51
        assert stats["epoch_baseline_verified_success"] == 50
        assert stats["epoch_baseline_origin"] == "human_correction"
        assert "failures_verified" not in stats


def test_correction_epoch_survives_restart_and_follows_fresh_ladder(store):
    Session, db = store
    agent_id = _configure(db, verified=50)
    assert reset_autonomy_cycle(db, agent_id, "canvas_edit") is True
    db.close()

    with Session() as fresh:
        service = CapabilityGraduationService(fresh)
        for count in range(1, 6):
            service.record_usage(agent_id, "canvas_edit", True, "verified")
            expected = "intern" if count == 5 else "student"
            assert service.get_maturity(agent_id, "canvas_edit") == expected

    # A restarted worker re-reads the persisted baseline, not an in-memory tag.
    with Session() as restarted:
        service = CapabilityGraduationService(restarted)
        assert service.get_maturity(agent_id, "canvas_edit") == "intern"
        for count in range(6, 51):
            service.record_usage(agent_id, "canvas_edit", True, "verified")
            if count < 20:
                expected = "intern"
            elif count < 50:
                expected = "supervised"
            else:
                expected = "autonomous"
            assert service.get_maturity(agent_id, "canvas_edit") == expected


def test_repeated_correction_rebinds_the_baseline_and_keeps_history(store):
    Session, db = store
    agent_id = _configure(db, verified=50)
    assert reset_autonomy_cycle(db, agent_id, "canvas_edit") is True
    for _ in range(5):
        CapabilityGraduationService(db).record_usage(
            agent_id, "canvas_edit", True, "verified")

    # The capability had reached intern again; a second correction starts at
    # the CURRENT lifetime count (55), so those 5 do not count twice.
    assert reset_autonomy_cycle(db, agent_id, "canvas_edit") is True
    db.close()

    with Session() as fresh:
        cfg = fresh.get(AgentRegistry, agent_id).configuration
        stats = cfg["capability_stats"]["canvas_edit"]
        assert stats["verified_success"] == 55
        assert stats["epoch_baseline_verified_success"] == 55
        assert stats["epoch_baseline_origin"] == "human_correction"
        assert "failures_verified" not in stats

        service = CapabilityGraduationService(fresh)
        for count in range(1, 6):
            service.record_usage(agent_id, "canvas_edit", True, "verified")
            expected = "intern" if count == 5 else "student"
            assert service.get_maturity(agent_id, "canvas_edit") == expected


def test_correction_leaves_other_capabilities_untouched(store):
    Session, db = store
    agent_id = _configure(db, verified=50)
    row = db.get(AgentRegistry, agent_id)
    cfg = deepcopy(row.configuration)
    cfg["capability_stats"]["task_create"] = {
        "success": 7, "total": 8, "verified_success": 6,
    }
    cfg["capability_maturities"]["task_create"] = "supervised"
    row.configuration = cfg
    db.commit()

    assert reset_autonomy_cycle(db, agent_id, "canvas_edit") is True
    db.close()

    with Session() as fresh:
        cfg = fresh.get(AgentRegistry, agent_id).configuration
        assert cfg["capability_stats"]["task_create"] == {
            "success": 7, "total": 8, "verified_success": 6,
        }
        assert cfg["capability_maturities"]["task_create"] == "supervised"
        assert cfg["capability_maturities"]["canvas_edit"] == "student"


def test_correction_from_zero_keeps_the_existing_policy_fixture_compatible(store):
    Session, db = store
    agent_id = _configure(db, verified=0)
    assert reset_autonomy_cycle(db, agent_id, "canvas_edit") is True
    db.close()

    with Session() as fresh:
        service = CapabilityGraduationService(fresh)
        assert service.get_maturity(agent_id, "canvas_edit") == "student"
        for _ in range(4):
            service.record_usage(agent_id, "canvas_edit", True, "verified")
        assert service.get_maturity(agent_id, "canvas_edit") == "student"
        service.record_usage(agent_id, "canvas_edit", True, "verified")
        assert service.get_maturity(agent_id, "canvas_edit") == "intern"
        assert autonomy_cycle(fresh, agent_id, "canvas_edit")["ok"] is True


def test_unknown_identity_or_topic_reset_is_reported_truthfully(store):
    _Session, db = store
    assert reset_autonomy_cycle(db, "ghost-agent", "canvas_edit") is False
    assert reset_autonomy_cycle(
        db, "agent-revocation-1", "not-a-topic") is False
