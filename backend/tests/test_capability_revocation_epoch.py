"""Previously earned credit cannot re-earn a revoked capability."""
from copy import deepcopy

import pytest

from core.capability_graduation_service import CapabilityGraduationService
from core.models import AgentRegistry
from tests.test_autonomy_revocation import store


@pytest.mark.parametrize("historical", [25, 50])
def test_verified_regression_keeps_student_until_new_reentry_credit(store, historical):
    Session, db = store
    agent = db.query(AgentRegistry).filter_by(id="agent-revocation-1").one()
    config = deepcopy(agent.configuration)
    config["capability_stats"]["canvas_edit"].update(
        success=historical, total=historical, verified_success=historical)
    agent.configuration = config
    db.commit()
    service = CapabilityGraduationService(db)
    service.record_usage(agent.id, "canvas_edit", False, "failed_verification")
    db.close()
    with Session() as fresh:
        service = CapabilityGraduationService(fresh)
        assert service.get_maturity("agent-revocation-1", "canvas_edit") == "student"
        for _ in range(service.REVOCATION_REENTRY_SUCCESSES - 1):
            service.record_usage("agent-revocation-1", "canvas_edit", True, "verified")
        assert service.get_maturity("agent-revocation-1", "canvas_edit") == "student"
        service.record_usage("agent-revocation-1", "canvas_edit", True, "verified")
        assert service.get_maturity("agent-revocation-1", "canvas_edit") == "intern"


def test_old_credit_does_not_return_autonomy_after_reentry(store):
    Session, db = store
    agent = db.query(AgentRegistry).filter_by(id="agent-revocation-1").one()
    config = deepcopy(agent.configuration)
    config["capability_stats"]["canvas_edit"].update(
        success=50, total=50, verified_success=50)
    agent.configuration = config
    db.commit()
    service = CapabilityGraduationService(db)
    service.record_usage(agent.id, "canvas_edit", False, "failed_verification")
    for _ in range(service.REVOCATION_REENTRY_SUCCESSES + 1):
        service.record_usage(agent.id, "canvas_edit", True, "verified")
    db.close()
    with Session() as fresh:
        service = CapabilityGraduationService(fresh)
        assert service.get_maturity("agent-revocation-1", "canvas_edit") != "autonomous"


def test_fresh_verified_work_preserves_existing_ladder(store):
    _Session, db = store
    service = CapabilityGraduationService(db)
    for count in range(1, 51):
        service.record_usage("agent-revocation-1", "new_capability", True, "verified")
        if count in (5, 20, 50):
            expected = {5: "intern", 20: "supervised", 50: "autonomous"}[count]
            assert service.get_maturity("agent-revocation-1", "new_capability") == expected


@pytest.mark.parametrize("success,verification", [
    (True, "unverified"), (False, "unverified"), (False, "verified"),
])
def test_bookkeeping_without_a_verified_success_cannot_advance(store, success, verification):
    _Session, db = store
    agent = db.query(AgentRegistry).filter_by(id="agent-revocation-1").one()
    config = deepcopy(agent.configuration)
    config["capability_maturities"]["canvas_edit"] = "student"
    agent.configuration = config
    db.commit()
    service = CapabilityGraduationService(db)
    service.record_usage(agent.id, "canvas_edit", success, verification)
    assert service.get_maturity(agent.id, "canvas_edit") == "student"


def test_existing_revocation_baseline_survives_marker_clear_and_restart(store):
    Session, db = store
    agent = db.query(AgentRegistry).filter_by(id="agent-revocation-1").one()
    config = deepcopy(agent.configuration)
    config["capability_maturities"]["canvas_edit"] = "student"
    config["capability_stats"]["canvas_edit"].update(
        success=44, total=45, verified_success=44)
    config["autonomy_revocations"] = {
        "canvas_edit": {"baseline_verified_success": 25, "epoch": 1}}
    agent.configuration = config
    db.commit()
    service = CapabilityGraduationService(db)
    service.record_usage(agent.id, "canvas_edit", True, "verified")
    assert service.get_maturity(agent.id, "canvas_edit") == "intern"
    db.close()
    with Session() as fresh:
        service = CapabilityGraduationService(fresh)
        for new_count in range(21, 51):
            service.record_usage("agent-revocation-1", "canvas_edit", True, "verified")
            if new_count < 50:
                assert service.get_maturity("agent-revocation-1", "canvas_edit") != "autonomous"
        assert service.get_maturity("agent-revocation-1", "canvas_edit") == "autonomous"


def test_second_regression_starts_another_fresh_epoch(store):
    _Session, db = store
    service = CapabilityGraduationService(db)
    agent_id = "agent-revocation-1"
    for _epoch in range(2):
        service.record_usage(agent_id, "canvas_edit", False, "failed_verification")
        assert service.get_maturity(agent_id, "canvas_edit") == "student"
        for new_count in range(1, 51):
            service.record_usage(agent_id, "canvas_edit", True, "verified")
            if new_count < 20:
                assert service.get_maturity(agent_id, "canvas_edit") == "student"
            elif new_count == 20:
                assert service.get_maturity(agent_id, "canvas_edit") == "intern"
            elif new_count < 50:
                assert service.get_maturity(agent_id, "canvas_edit") != "autonomous"
        assert service.get_maturity(agent_id, "canvas_edit") == "autonomous"
