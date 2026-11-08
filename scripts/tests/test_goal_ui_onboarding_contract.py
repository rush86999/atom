"""Acceptance must wait for the wizard and prove durable completion."""
import ast
from pathlib import Path
from types import SimpleNamespace
import pytest
SOURCE=Path(__file__).resolve().parents[1]/'acceptance/browser_goal_utility_ui.py'
def helper():
    node=next(n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='_complete_onboarding_if_present')
    clock=SimpleNamespace(monotonic=lambda:0,sleep=lambda _:None)
    scope={'Any':object,'Dict':dict,'DriverError':RuntimeError,'time':clock}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(SOURCE),'exec'),scope)
    return scope['_complete_onboarding_if_present'],clock
class Surface:
    def __init__(self,completed=False,status=200,persist=True):
        self.completed=completed;self.status=status;self.persist=persist;self.events=[];self.fail_click=False
    def get(self,path):
        assert path=='/api/onboarding/status'
        return SimpleNamespace(status_code=self.status,json=lambda:{'data':{'onboarding_completed':self.completed}})
    def get_by_role(self,role,**kw):
        name=kw['name'];self.events.append(('locate',role,name));surface=self
        class Locator:
            def wait_for(self,**kw):surface.events.append(('wait',name,kw['state']))
            def is_visible(self,**kw):raise AssertionError('is_visible is not a readiness wait')
            def click(self):
                if surface.fail_click:raise RuntimeError('real UI click failed')
                surface.events.append(('click',name))
                if name=='Start Automating' and surface.persist:surface.completed=True
        return Locator()
def test_fresh_account_waits_for_wizard_then_verifies_completion():
    run,_=helper();s=Surface();out=run(s,s)
    assert ('wait','Welcome to Atom','visible') in s.events
    assert s.events.count(('click','Next'))==3
    assert out=={'wizard_seen':True,'dismissed':True,'completion_durable':True}
def test_completed_account_needs_no_new_onboarding():
    run,_=helper();s=Surface(completed=True);out=run(s,s)
    assert out['completion_durable'] and not out['wizard_seen']
    assert not any(e[0]=='click' for e in s.events)
def test_status_failure_is_not_silently_treated_as_absent_wizard():
    run,_=helper();s=Surface(status=503)
    with pytest.raises(RuntimeError,match='status unavailable'):run(s,s)
def test_unknown_completion_is_not_completion():
    run,_=helper();s=Surface(completed=None)
    with pytest.raises(RuntimeError,match='missing completion evidence'):run(s,s)
def test_real_click_failure_is_not_swallowed():
    run,_=helper();s=Surface();s.fail_click=True
    with pytest.raises(RuntimeError,match='real UI click failed'):run(s,s)
def test_closed_wizard_without_persistence_refuses():
    run,clock=helper();times=iter([0,31]);clock.monotonic=lambda:next(times);s=Surface(persist=False)
    with pytest.raises(RuntimeError,match='without durable completion'):run(s,s)
