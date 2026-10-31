"""Workflow execution, versioning, scheduling and conductor scenarios."""
from __future__ import annotations

import asyncio
import time
import uuid

from .common import Ctx, make_agent


def _definition(name: str, services=("database", "database")) -> dict:
    nodes = []
    for i, service in enumerate(services):
        nodes.append({
            "id": f"node-{i+1}",
            "type": "trigger" if i == 0 else "action",
            "title": f"{service} step {i+1}",
            "description": "acceptance step",
            "position": {"x": 100 * i, "y": 100},
            "config": {"service": service, "action": "query", "parameters": {}},
            "connections": [],
        })
    connections = [
        {"id": f"c{i}", "source": f"node-{i}", "target": f"node-{i+1}"}
        for i in range(1, len(nodes))
    ]
    return {
        "name": name,
        "description": "README acceptance workflow",
        "version": "1.0.0",
        "nodes": nodes,
        "connections": connections,
        "triggers": ["manual"],
        "enabled": True,
    }


def _wait_execution(ctx: Ctx, workflow_id: str, timeout=25):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = ctx.get(f"/api/v1/workflows/workflows/{workflow_id}/executions")
        if r.status_code == 200:
            items = r.json()
            last = items
            for item in items:
                if item.get("status") in ("completed", "failed", "cancelled"):
                    return item, items
        time.sleep(0.5)
    return (last[0] if last else None), last


def workflows(ctx: Ctx) -> None:
    name = f"acceptance-wf-{uuid.uuid4().hex[:6]}"
    create = ctx.post("/api/v1/workflows/workflows", json=_definition(name))
    created = create.json() if create.headers.get("content-type", "").startswith("application/json") else {}
    wid = created.get("id") or (created.get("data") or {}).get("id")
    reread = ctx.get(f"/api/v1/workflows/workflows/{wid}") if wid else None
    ctx.record("WF-01", "verified" if create.status_code in (200, 201) and wid
               and reread is not None and reread.status_code == 200 else "failed",
               [ctx.save("workflows/create.json", {
                   "create": {"status": create.status_code, "body": created},
                   "reread": None if reread is None else reread.status_code})],
               notes=f"create={create.status_code} id={wid} "
                     f"reread={None if reread is None else reread.status_code}")

    # WF-02 execute
    execute = ctx.post(f"/api/v1/workflows/workflows/{wid}/execute", json={}) if wid else None
    exec_body = execute.json() if execute is not None and execute.headers.get("content-type", "").startswith("application/json") else {}
    execution_id = exec_body.get("execution_id") or (exec_body.get("data") or {}).get("execution_id")
    item, history = _wait_execution(ctx, wid) if wid else (None, None)
    status = (item or {}).get("status")
    detail = ctx.get(f"/api/v1/workflows/workflows/executions/{execution_id}") if execution_id else None
    ok = execute is not None and execute.status_code in (200, 201) and status == "completed"
    ctx.record("WF-02", "verified" if ok else "failed",
               [ctx.save("workflows/execute.json", {
                   "execute": None if execute is None else {
                       "status": execute.status_code, "body": exec_body},
                   "history": history,
                   "detail": None if detail is None else {
                       "status": detail.status_code, "body": detail.text[:1500]},
               })],
               notes=f"execute={None if execute is None else execute.status_code} "
                     f"execution={execution_id} status={status}")

    # WF-03 durable read-back (process restart is a separate script)
    from core.database import SessionLocal
    from core.models import WorkflowExecution as WorkflowExecutionRow
    db = SessionLocal()
    try:
        row = db.query(WorkflowExecutionRow).filter(
            WorkflowExecutionRow.execution_id == execution_id).first() if execution_id else None
        durable = {
            "found": row is not None,
            "status": getattr(row, "status", None),
            "workflow_id": getattr(row, "workflow_id", None),
        }
    finally:
        db.close()
    ctx.record("WF-03", "partial" if durable["found"] else "failed",
               [ctx.save("workflows/durable.json", durable)],
               notes="Execution row persists in the DB; full process-restart "
                     "re-read is the separate restart scenario")

    # WF-04 scheduling
    schedule = ctx.post(f"/api/v1/workflows/workflows/{wid}/schedule", json={
        "trigger_type": "interval",
        "trigger_config": {"minutes": 60},
        "input_data": {},
    }) if wid else None
    schedule_body = schedule.json() if schedule is not None and schedule.headers.get("content-type", "").startswith("application/json") else {}
    job_id = schedule_body.get("job_id")
    jobs = ctx.get("/api/v1/workflows/scheduler/jobs")
    listed = job_id in str(jobs.text) if job_id else False
    remove = ctx.delete(f"/api/v1/workflows/workflows/{wid}/schedule/{job_id}") if job_id else None
    jobs_after = ctx.get("/api/v1/workflows/scheduler/jobs")
    gone = (job_id not in str(jobs_after.text)) if job_id else False
    ok = (schedule is not None and schedule.status_code == 200 and job_id
          and jobs.status_code == 200 and listed and remove is not None
          and remove.status_code == 200 and gone)
    ctx.record("WF-04", "verified" if ok else "partial",
               [ctx.save("workflows/schedule.json", {
                   "schedule": None if schedule is None else {
                       "status": schedule.status_code, "body": schedule_body},
                   "list": {"status": jobs.status_code, "listed": listed},
                   "remove": None if remove is None else remove.status_code,
                   "gone": gone,
               })],
               notes=f"job={job_id} listed={listed} removed={gone}; "
                     f"actual firing requires ENABLE_SCHEDULER (off in this world)")

    # WF-06 versioning + rollback
    version_create = ctx.post(f"/api/v1/workflows/{wid}/versions", json={
        "version_type": "minor", "commit_message": "acceptance v1",
        "tags": ["acceptance"]}) if wid else None
    versions = ctx.get(f"/api/v1/workflows/{wid}/versions") if wid else None
    version_body = versions.json() if versions is not None and versions.status_code == 200 else {}
    version_items = version_body if isinstance(version_body, list) else (
        version_body.get("versions") or version_body.get("data") or [])
    v1 = None
    if isinstance(version_items, list) and version_items:
        v1 = version_items[0].get("version") or version_items[0].get("version_number")
    # change the workflow, create a second version, then roll back to v1
    updated = dict(_definition(name))
    updated["description"] = "README acceptance workflow v2"
    update = ctx.post("/api/v1/workflows/workflows", json={**updated, "id": wid}) if wid else None
    version_create2 = ctx.post(f"/api/v1/workflows/{wid}/versions", json={
        "version_type": "minor", "commit_message": "acceptance v2"}) if wid else None
    rollback = None
    rollback_version = None
    rollback_recorded = False
    if wid and v1 is not None:
        rollback = ctx.post(f"/api/v1/workflows/{wid}/rollback", json={
            "target_version": v1, "rollback_reason": "acceptance rollback"})
        rollback_body = rollback.json() if rollback.headers.get("content-type", "").startswith("application/json") else {}
        rollback_version = ((rollback_body.get("data") or {}).get("rollback_version")
                            or rollback_body.get("rollback_version"))
        versions_after = ctx.get(f"/api/v1/workflows/{wid}/versions")
        after_body = versions_after.json() if versions_after.status_code == 200 else []
        after_items = after_body if isinstance(after_body, list) else []
        rollback_recorded = bool(rollback_version) and any(
            str(v.get("version")) == str(rollback_version) for v in after_items)
    ctx.record("WF-06", "verified" if (version_create is not None and version_create.status_code in (200, 201)
                                       and v1 is not None and rollback is not None
                                       and rollback.status_code in (200, 201)
                                       and rollback_recorded) else "partial",
               [ctx.save("workflows/versioning.json", {
                   "create_v1": None if version_create is None else {
                       "status": version_create.status_code, "body": version_create.text[:800]},
                   "versions": None if versions is None else {
                       "status": versions.status_code, "body": version_body},
                   "update": None if update is None else update.status_code,
                   "create_v2": None if version_create2 is None else version_create2.status_code,
                   "rollback": None if rollback is None else {
                       "status": rollback.status_code, "body": rollback.text[:1200]},
                   "rollback_version": rollback_version,
                   "rollback_recorded": rollback_recorded,
               })],
               notes=f"v1={v1} rollback={None if rollback is None else rollback.status_code} "
                     f"rollback_version={rollback_version} recorded={rollback_recorded}")

    # WF-07 starter templates
    templates = ctx.get("/api/workflow-templates/")
    tbody = templates.json() if templates.status_code == 200 else {}
    items = tbody if isinstance(tbody, list) else (
        tbody.get("templates") or tbody.get("data") or [])
    template_id = None
    if isinstance(items, list) and items:
        template_id = items[0].get("id") or items[0].get("template_id")
    imported = execute_t = None
    if template_id:
        imported = ctx.post(f"/api/workflow-templates/{template_id}/import", json={})
        execute_t = ctx.post(f"/api/workflow-templates/{template_id}/execute", json={})
    ok = templates.status_code == 200 and template_id and imported is not None and imported.status_code in (200, 201)
    ctx.record("WF-07", "verified" if ok else "partial",
               [ctx.save("workflows/templates.json", {
                   "list": {"status": templates.status_code,
                            "count": len(items) if isinstance(items, list) else None},
                   "template_id": template_id,
                   "import": None if imported is None else imported.text[:800],
                   "execute": None if execute_t is None else execute_t.text[:800],
               })],
               notes=f"templates={len(items) if isinstance(items, list) else 'n/a'} "
                     f"import={None if imported is None else imported.status_code}")

    # WF-05 HITL pause/resume: a workflow bound to a below-tier agent needs a
    # model-backed run; the generic approval pause is GOV-02. Record partial
    # with the served approval queue as the connecting evidence.
    queue = ctx.get("/api/agents/approvals/pending")
    ctx.record("WF-05", "partial" if queue.status_code == 200 else "unverified",
               [ctx.save("workflows/hitl_queue.json", {
                   "status": queue.status_code, "body": queue.text[:1000]})],
               notes="Workflow pause/resume needs a model-backed low-maturity agent "
                     "run; the HITL queue itself is exercised by GOV-02")

    # ---- Conductor: five strategies with a deterministic step executor --
    from core.orchestration.conductor_agent import (
        ConductorAgent, ExecutionStrategy, WorkflowStep, StepType)
    strategies = ["sequential", "parallel", "hybrid", "adaptive", "rollback_safe"]
    outcomes = {}
    for strategy in strategies:
        conductor = ConductorAgent()
        calls = []

        async def _exec(step, context, _calls=calls):
            _calls.append(step.step_id)
            return {"step_id": step.step_id, "status": "completed",
                    "output": "acceptance step output"}

        conductor.set_step_executor(_exec)
        step = WorkflowStep(step_id="s1", step_type=StepType.AGENT,
                            name="acceptance", description="acceptance",
                            parameters={})
        result = asyncio.run(conductor.execute_workflow(
            [step], start_step="s1",
            strategy=ExecutionStrategy(strategy)))
        outcomes[strategy] = {
            "status": str(result.status),
            "completed_steps": result.completed_steps,
            "failed_steps": result.failed_steps,
            "executor_calls": calls,
        }
    invalid = ctx.post("/api/v1/workflows/workflows/conductor/execute", json={
        "steps": [{"id": "s1", "name": "acceptance", "parameters": {}}],
        "strategy": "not-a-strategy",
    })
    accepted = [s for s, o in outcomes.items()
                if o["status"].endswith("COMPLETED")
                and o["completed_steps"] == 1
                and o["executor_calls"] == ["s1"]]
    ok = len(accepted) == 5 and invalid.status_code == 422
    ctx.record("ORCH-03", "verified" if ok else "failed",
               [ctx.save("orchestration/conductor.json", {
                   "outcomes": outcomes,
                   "invalid": {"status": invalid.status_code,
                               "body": invalid.text[:400]},
               })],
               notes=f"strategies_executed={accepted} invalid={invalid.status_code}; "
                     f"deterministic executor called once under each strategy")

    # ---- State machine transitions/rollback ----------------------------
    try:
        from core.orchestration.workflow_state_machine import (
            WorkflowStateMachine, WorkflowState, TransitionResult)
        sm = WorkflowStateMachine()
        wid = f"acceptance-{uuid.uuid4().hex[:6]}"
        eid = f"exec-{uuid.uuid4().hex[:6]}"
        sm.initialize_state(wid, eid)
        first = sm.transition(wid, eid, WorkflowState.VALIDATED)
        legal = sm.transition(wid, eid, WorkflowState.QUEUED)
        illegal = sm.transition(wid, eid, WorkflowState.COMPLETED)
        after = sm.get_state(wid)
        ok = (first == TransitionResult.SUCCESS
              and legal == TransitionResult.SUCCESS
              and illegal in (TransitionResult.INVALID, TransitionResult.BLOCKED)
              and after == WorkflowState.QUEUED)
        ctx.record("ORCH-04", "verified" if ok else "failed",
                   [ctx.save("orchestration/state_machine.json", {
                       "first": str(first), "legal": str(legal),
                       "illegal": str(illegal), "state_after": str(after)})],
                   notes=f"legal={legal} illegal={illegal} state={after}")
    except Exception as exc:
        ctx.record("ORCH-04", "unverified", notes=f"state machine unavailable: {exc}")

    # ---- Rollback (versioning) is the workflow rollback evidence ------
    ctx.record("ORCH-05",
               "verified" if (wid and v1 is not None and rollback is not None
                              and rollback.status_code in (200, 201)
                              and rollback_recorded) else "partial",
               [f"workflows/versioning.json"],
               notes=f"Rollback to {v1} created {rollback_version} and the version "
                     f"history contains it = {rollback_recorded}")

    # ---- Queen / Fleet: model-backed; record honestly ------------------
    for cid, note in (("ORCH-01", "Queen workflow blueprint"),
                      ("ORCH-02", "Fleet open-ended task"),
                      ("ORCH-07", "fleet routing audit row")):
        ctx.record(cid, "unverified",
                   notes=f"{note} requires a configured reasoning model at the "
                         f"served boundary; no cloud key is used in this world")

    # ---- Ranked specialist matching (deterministic) --------------------
    try:
        from core.specialist_matcher import SpecialistMatcher
        strong = make_agent(ctx, f"fin-strong-{uuid.uuid4().hex[:4]}",
                            tier="autonomous",
                            capabilities=["finance", "reconciliation", "ledger"])
        weak = make_agent(ctx, f"fin-weak-{uuid.uuid4().hex[:4]}",
                          tier="intern", capabilities=["general"])
        from core.models import AgentRegistry
        db = ctx.db()
        try:
            for aid, category in ((strong, "finance"), (weak, "finance")):
                row = db.query(AgentRegistry).filter(AgentRegistry.id == aid).first()
                row.category = category
                row.confidence_score = 0.95 if aid == strong else 0.3
            db.commit()
            ranked = SpecialistMatcher(db).find_specialists_for_domains(["finance"])
        finally:
            db.close()
        entries = ranked.get("finance") or []
        ids = [e.get("agent_id") for e in entries]
        ok = bool(ids) and ids[0] == strong
        ctx.record("ORCH-06", "verified" if ok else "partial",
                   [ctx.save("orchestration/matcher.json", {
                       "ranked": entries, "strong": strong, "weak": weak})],
                   notes=f"ranked={ids[:3]} strong={strong}")
    except Exception as exc:
        ctx.record("ORCH-06", "unverified", notes=f"matcher unavailable: {exc}")

    # ---- Delegation nesting depth --------------------------------------
    try:
        from core.agent_fleet_service import AgentFleetService
        from core.models import DelegationChain
        db = ctx.db()
        try:
            service = AgentFleetService(db)
            chain = service.initialize_fleet(
                tenant_id=ctx.tenant_id, root_agent_id="a",
                root_task="acceptance depth")
            max_depth = getattr(chain, "max_depth", None)
            first = service.recruit_member(chain.id, "a", "b", "leaf", link_order=1)
            second = service.recruit_member(chain.id, "b", "c", "nested", link_order=2)
            # The model records max_depth, but recruit_member has no depth check;
            # this is the claim under test.
            enforced = False
            try:
                third = service.recruit_member(chain.id, "c", "d", "too-deep",
                                               link_order=int(max_depth or 5) + 2)
                enforced = third is None
            except Exception:
                enforced = True
        finally:
            db.close()
        ctx.record("ORCH-08", "verified" if enforced else "inaccurate",
                   [ctx.save("orchestration/depth.json", {
                       "max_depth": max_depth, "first": getattr(first, "id", None),
                       "second": getattr(second, "id", None),
                       "enforced": enforced})],
                   notes=("DelegationChain stores max_depth but AgentFleetService."
                          "recruit_member does not reject a link beyond it; the "
                          "README/CLAUDE.md enforcement claim is overstated.")
                   if not enforced else "depth enforced")
    except Exception as exc:
        ctx.record("ORCH-08", "unverified", notes=f"DelegationChain unavailable: {exc}")
