import runpy,time,json,os
from pathlib import Path
h=runpy.run_path(str(Path(__file__).with_name("driver_helpers.py")))
h["_start"].__globals__["WORKER"]=Path(__file__).with_name("worker.py")
h["_start"].__globals__["BACKEND"]=Path("/private/tmp/atom-source-trigger-lead-review/backend")

def test_accepted_information_survives_crash_and_triggers_same_job(tmp_path,monkeypatch):
    s=tmp_path/"world"; p,port,log,_=h["_start"](s,"initial.log")
    try:
        code,start=h["_call"](port,"/api/agents/a1/run?operation_id=lead-accepted-crash",{"parameters":{"sync":True,"task_input":"Create the closing task"}})
        assert code==202,(code,start)
        data=start["data"];jid=data["job_id"];rid=data["execution_id"];wait=data["wait_receipt"]
        assert data["job_status"]=="waiting"
    finally:h["_stop"](p,log,kill=True)
    monkeypatch.setenv("LEAD_CRASH_AFTER_ANSWER","1")
    p2,port2,log2,_=h["_start"](s,"accepted-crash.log")
    try:
        try:h["_call"](port2,f"/api/agents/a1/jobs/{jid}/answer",{"answer":h["ANSWER"],"correlation_id":wait["correlation_id"]})
        except (ConnectionError,OSError):pass
        assert p2.wait(timeout=15)==17
    finally:h["_stop"](p2,log2,kill=True)
    persisted=h["_state"](s)
    assert persisted["waits"][0]["status"]=="approved",persisted
    assert persisted["tasks"]==[],persisted
    monkeypatch.delenv("LEAD_CRASH_AFTER_ANSWER")
    p3,port3,log3,_=h["_start"](s,"successor.log")
    try:
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            final=h["_state"](s)
            if final["jobs"][0]["status"]=="success":break
            time.sleep(.1)
        (s/"lead-state.json").write_text(json.dumps({"job_id":jid,"execution_id":rid,"accepted_before_restart":persisted,"after_restart":final},indent=2))
        assert final["jobs"][0]["status"]=="success", "Durably accepted information did not trigger same-job continuation after production recovery helper restart: "+json.dumps(final)
        assert len(final["tasks"])==1
    finally:h["_stop"](p3,log3,kill=False)
