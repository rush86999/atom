"""Read-only failure diagnostics for synthetic scoped task fixtures; no producer patch."""
import json, os, inspect, sys
from pathlib import Path
import pytest

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != 'call' or not report.failed or 'multiday' not in item.nodeid:
        return
    env = item.funcargs.get('real_env')
    if env is None:
        return
    record = {'nodeid': item.nodeid, 'oracle_flags': {k: os.environ.get(k) for k in ['ATOM_ORACLE_ENFORCE','ATOM_ORACLE_VERIFIER_ENABLED']}}
    try:
        from core.oracle import get_postcondition
        fn = get_postcondition('tasks.create')
        record['verifier'] = {'module': getattr(fn,'__module__',None),'name':getattr(fn,'__name__',None),'source':inspect.getsourcefile(fn) if fn else None}
        from core.models import AgentJob
        with env.SessionLocal() as db:
            record['jobs'] = [{'id':j.id,'status':j.status,'summary':j.result_summary,'logs':j.logs} for j in db.query(AgentJob).all()]
    except Exception as exc:
        record['diagnostic_error_class'] = type(exc).__name__
    target=Path(os.environ['ROOT_MULTIDAY_DIAGNOSTIC_OUT'])
    with target.open('a') as stream:
        stream.write(json.dumps(record,default=str)+'\n')
