import pytest
from core.assignment_executor import NeedsContext
from core.assignment_plan import new_assignment,new_step
from core.assignment_readiness import evaluate_step_readiness
from core.doc_freshness_service import EXTRACTION_VERSION
from tests.test_employee_document_freshness import _fixture,_run


def test_current_versioned_extraction_remains_eligible(monkeypatch):
    version=f'ev{EXTRACTION_VERSION}:'+('a'*64)
    binding=_fixture(monkeypatch,indexed=version,sql=version)
    result=_run(binding)
    source=new_step(step_id='read',title='Read current indexed extraction',operation_type='retrieve',adapter='document.text',inputs={'resource_binding':binding},effect='read_only')
    source.update(status='applied',operation_id='op-read',result=result)
    child=new_step(step_id='use',title='Use verified current evidence',operation_type='calculate',adapter='invoice.reconcile',inputs={},requires=[{'kind':'receipt','step_id':'read','require':'verified'}])
    ready=evaluate_step_readiness(child,new_assignment(objective='Use current extraction',steps=[source,child]),task_authorization='read_only')
    assert ready['eligible'],{'binding_version':version,'result_version':result.get('source_version'),'ready':ready}


def test_old_extractor_is_not_promoted_to_current_by_stripping_prefix(monkeypatch):
    digest='a'*64
    binding=_fixture(monkeypatch,indexed='ev3:'+digest,sql=f'ev{EXTRACTION_VERSION}:'+digest)
    with pytest.raises(NeedsContext):
        _run(binding)
