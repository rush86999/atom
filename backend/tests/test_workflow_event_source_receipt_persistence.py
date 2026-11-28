"""Provider confirmation cannot persist into a peer-moved operation scope."""
import asyncio
import pytest
from core.workflow_event_source_enrollment import enroll_source
from core.models import TaskOperationRecord
from tests.test_workflow_event_source_binding import binding_world, saved
from tests.test_workflow_event_source_enrollment import enrollment_world
from tests.test_workflow_event_source_registration import source_world
from tests.test_workflow_event_reservation import event_db


@pytest.mark.parametrize('mode',['normal','refused','timeout'])
def test_scope_moved_during_provider_attempt_is_not_overwritten(binding_world,mode):
    factory,params,args,provider=binding_world
    provider['mode']=mode
    original=args['adapter'].service._make_graph_request.side_effect
    def move_scope():
        with factory() as peer:
            peer.query(TaskOperationRecord).one().tenant_id='peer-tenant';peer.commit()
    async def wire(method,url,token,data=None,**options):
        try:
            result=await original(method,url,token,data,**options)
        except Exception:
            if method=='POST':move_scope()
            raise
        if method=='POST':move_scope()
        return result
    args['adapter'].service._make_graph_request.side_effect=wire
    result=asyncio.run(enroll_source(**args))
    assert result['effect']=='unknown' and result['do_not_repeat'] is True,result
    assert result['operation_id']==saved(factory)['operation_id']
    with factory() as db:
        row=db.query(TaskOperationRecord).one()
        assert row.tenant_id=='peer-tenant'
        assert row.status=='dispatching' and row.result_json is None
    assert sum(c[0]=='POST' for c in provider['calls'])==1
