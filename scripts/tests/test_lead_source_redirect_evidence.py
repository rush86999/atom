import importlib.util
from pathlib import Path
import pytest

@pytest.fixture()
def driver():
    p=Path(__file__).resolve().parents[2]/'scripts/acceptance/browser_agent_source_answer.py'
    spec=importlib.util.spec_from_file_location('lead_source_ui',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

@pytest.mark.parametrize('location,expected',[('',False),('https://foreign.example/api/agents/a/run',False),('/api/agents/a/run?operation_id=operation-1',True),('/api/agents/a/run?operation_id=other',False)])
def test_redirect_location_binds_actual_response_node(driver,location,expected):
    common={'method':'POST','origin':'http://localhost:3000','operation_id':'operation-1','body_sha256':'ab'*32}
    posts=[{**common,'path':'/api/agents/a/run/','request_id':'parent-id','request_key':'parent-material','redirected_to_id':'child-id'}, {**common,'path':'/api/agents/a/run','request_id':'child-id','request_key':'child-material','redirected_from_id':'parent-id'}]
    responses=[{'request_id':'parent-id','request_key':'parent-material','status':307,'location':location},{'request_id':'child-id','request_key':'child-material','status':200}]
    success={'request_id':'child-id','request_key':'child-material','status':200,'job_id':'job1','execution_id':'exec1'}
    result=driver._classify_run_admissions(posts,responses,success)
    assert result['ok'] is expected,(location,result)
