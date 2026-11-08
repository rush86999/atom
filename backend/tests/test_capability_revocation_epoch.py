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
