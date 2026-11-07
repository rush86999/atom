"""Unavailable sources yield a wait, and valid indexed revisions retain their namespace."""
import asyncio
import hashlib
from types import SimpleNamespace
import pytest
from tests.test_assignment_routes import route_env
from tests.test_lead_wait_source_disappears import test_accepted_invoice_unavailable_before_consumption_stays_unresolved as _removed_case

pytestmark = pytest.mark.timeout(45)


def test_source_gap_returns_instead_of_syncing_applied_receipt_forever(route_env, tmp_path, monkeypatch):
    from core.assignment_executor import AssignmentExecutor
    original = AssignmentExecutor._source_consumption_gap
    repeats = {}
    def observe(self, assignment, record):
        result = original(self, assignment, record)
        if result:
            step, gap = result
            key = (step['step_id'], gap.get('reason'))
            repeats[key] = repeats.get(key, 0) + 1
            if repeats[key] > 1:
                raise RuntimeError('lead observed repeated identical source gap without yielding')
        return result
    monkeypatch.setattr(AssignmentExecutor, '_source_consumption_gap', observe)
    _removed_case(route_env, tmp_path, monkeypatch, 'removed')
    assert repeats and max(repeats.values()) == 1, 'source gap was repeatedly overwritten by the applied operation instead of yielding a wait'


@pytest.mark.parametrize('revision_kind', ['ev4', 'manual_opaque'])
def test_valid_indexed_source_version_is_not_a_binary_file_digest(route_env, tmp_path, monkeypatch, revision_kind):
    from core.assignment_executor import AssignmentExecutor, _document_text_read
    from core.assignment_plan import new_assignment, new_step
    from core.models import IngestedDocument
    import core.lancedb_handler as lance
    binary = tmp_path/'original.bin'
    binary.write_bytes(b'original binary source bytes distinct from extracted text')
    version = ('ev4:'+hashlib.sha256(binary.read_bytes()).hexdigest()) if revision_kind=='ev4' else 'manual-revision-17'
    doc = IngestedDocument(id='lead-indexed-current', workspace_id='ws-1', tenant_id='tenant-1', file_name=binary.name, file_path=str(binary), file_type='pdf', integration_id='upload', external_id='lead-indexed-current', source_content_hash=version, freshness_status='fresh')
    route_env['db'].add(doc); route_env['db'].commit()
    indexed = {'id':doc.id,'text':'{"po_id":"PO-INDEXED","quantity":"2"}','source':binary.name,'metadata':{'source_content_hash':version,'pg_document_id':doc.id,'workspace_id':'ws-1','tenant_id':'tenant-1'}}
    monkeypatch.setattr(lance,'get_lancedb_handler',lambda workspace:SimpleNamespace(get_document_by_id=lambda table, identity:indexed))
    binding = {'kind':'document','source':'upload','document_id':doc.id,'resource_id':doc.id,'source_version':version,'workspace_id':'ws-1','tenant_id':'tenant-1','access_scope':{'user_id':'lead-1','workspace_id':'ws-1','tenant_id':'tenant-1'}}
    result = asyncio.run(_document_text_read({'resource_binding':binding},{'workspace_id':'ws-1','tenant_id':'tenant-1'}))
    assert result['verification']['status']=='verified'
    step = new_step(step_id='accepted-index', title='Read authorized indexed text', operation_type='retrieve', adapter='document.text', inputs={'resource_binding':binding}, effect='read_only')
    step.update(status='applied',operation_id='accepted-index-operation',result=result)
    assignment = new_assignment(objective='Use verified indexed text',steps=[step])
    problem = AssignmentExecutor(route_env['lifecycle'])._source_consumption_gap(assignment,{})
    assert problem is None, ('valid indexed revision was miscompared with raw binary bytes', problem)
