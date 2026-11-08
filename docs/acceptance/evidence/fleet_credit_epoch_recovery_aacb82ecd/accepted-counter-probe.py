"""Public correction reset must not borrow lifetime success for autonomy."""
from copy import deepcopy
from core.autonomy_policy import reset_autonomy_cycle, autonomy_cycle
from core.capability_graduation_service import CapabilityGraduationService
from core.models import AgentRegistry
from tests.test_autonomy_revocation import store


def test_human_correction_does_not_reuse_lifetime_credit(store, monkeypatch):
    import importlib.util
    import core.capability_graduation_service as current
    global CapabilityGraduationService
    spec=importlib.util.spec_from_file_location("root_accepted_d9_capability", "/private/tmp/root-accepted-d9-capability-reset-baseline.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    CapabilityGraduationService=module.CapabilityGraduationService
    monkeypatch.setattr(current,"CapabilityGraduationService",CapabilityGraduationService)
    Session,db=store
    row=db.get(AgentRegistry,'agent-revocation-1')
    cfg=deepcopy(row.configuration)
    cfg['capability_stats']['canvas_edit'].update(success=50,total=50,verified_success=50)
    cfg['capability_maturities']['canvas_edit']='autonomous'
    row.configuration=cfg;db.commit()
    assert reset_autonomy_cycle(db,row.id,'canvas_edit',reason='owner corrected the business rule') is True
    db.close()
    with Session() as fresh:
        service=CapabilityGraduationService(fresh)
        assert service.get_maturity('agent-revocation-1','canvas_edit')=='student'
        service.record_usage('agent-revocation-1','canvas_edit',True,'verified')
        assert autonomy_cycle(fresh,'agent-revocation-1','canvas_edit')['ok'] is False
