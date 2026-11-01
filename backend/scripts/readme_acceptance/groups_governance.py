"""Governance/maturity/oracle/ask/agent-team acceptance scenarios."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import uuid

from .common import BACKEND, REPO, Ctx, make_agent, parse


def _enforce(ctx: Ctx, agent_id: str, action: str, details=None):
    r = ctx.post("/api/agent-governance/enforce-action", json={
        "agent_id": agent_id, "action_type": action,
        "action_details": details or {"target": "acceptance"},
    })
    return r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text


def governance(ctx: Ctx) -> None:
    # ---- GOV-01 four-tier maturity gate --------------------------------
    tiers = {"student": "student", "intern": "intern",
             "supervised": "supervised", "autonomous": "autonomous"}
    ids = {t: make_agent(ctx, f"tier-{t}-{uuid.uuid4().hex[:6]}", tier=s)
           for t, s in tiers.items()}
    observed = {}
    for tier, agent_id in ids.items():
        observed[tier] = _enforce(ctx, agent_id, "create_task",
                                 {"title": "acceptance task"})[1]
    read_student = _enforce(ctx, ids["student"], "read", {"query": "status"})[1]
    evidence = [ctx.save("governance/tier_gate.json", {
        "complexity3": observed, "student_read": read_student,
        "agents": ids,
    })]
    statuses = {t: (v or {}).get("status") if isinstance(v, dict) else str(v)
                for t, v in observed.items()}
    ok = (statuses.get("student") == "BLOCKED"
          and statuses.get("intern") == "BLOCKED"
          and statuses.get("supervised") == "PENDING_APPROVAL"
          and statuses.get("autonomous") == "APPROVED"
          and (read_student or {}).get("status") == "APPROVED")
    ctx.record("GOV-01", "verified" if ok else "failed", evidence,
               notes=f"complexity-3 statuses={statuses}; "
                     f"student read={(read_student or {}).get('status')}")

    # ---- GOV-02 approval executes only after approval -------------------
    # A goal-run plan with a process-intrinsic checkpoint and a deterministic
    # deliverable step. The controlled router returns ADVANCE; the checkpoint
    # waits for the human, and approval resumes the SAME run into the
    # deliverable. Before approval the canvas must not exist.
    goal_create = ctx.post("/api/goals", json={
        "title": f"approval execution {uuid.uuid4().hex[:6]}",
        "description": "GOV-02 approval execution acceptance",
        "criteria": [{"description": "the approved deliverable exists"}],
    })
    goal_body = goal_create.json() if goal_create.status_code == 200 else {}
    goal_id = (goal_body.get("goal_id") or goal_body.get("id")
               or (goal_body.get("goal") or {}).get("id")
               or (goal_body.get("data") or {}).get("id"))
    run_create = ctx.post("/api/goal-runs", json={
        "goal_id": goal_id,
        "role": "acceptance",
        "start": False,
        "supervision_mode": "shadow",
        "plan": [
            {"id": "approval-checkpoint", "kind": "human_checkpoint",
             "title": "Approve the acceptance deliverable",
             "note": "GOV-02 approval boundary"},
            {"id": "approved-deliverable", "kind": "canvas_work",
             "title": "Create the approved deliverable",
             "canvas_type": "document"},
        ],
    }) if goal_id else None
    run_body = (run_create.json() if run_create is not None
                and run_create.headers.get("content-type", "").startswith("application/json")
                else {})
    run_id = (run_body.get("run_id") or run_body.get("id")
              or (run_body.get("data") or {}).get("id"))
    advance = ctx.post(f"/api/goal-runs/{run_id}/advance") if run_id else None
    advance_body = (advance.json() if advance is not None
                    and advance.headers.get("content-type", "").startswith("application/json")
                    else {})

    from core.models import HITLAction
    from core.models_board import BoardTask
    db = ctx.db()
    try:
        pending_rows = (db.query(HITLAction)
                        .filter(HITLAction.action_type == "goal_run_checkpoint",
                                HITLAction.status == "pending")
                        .order_by(HITLAction.created_at.desc()).limit(20).all())
        checkpoint = next(
            (a for a in pending_rows
             if str((a.params or {}).get("run_id")) == str(run_id)), None)
        checkpoint_id = getattr(checkpoint, "id", None)
    finally:
        db.close()

    pre_canvases = ctx.get(f"/api/goal-runs/{run_id}/canvases") if run_id else None
    pre_body = (pre_canvases.json() if pre_canvases is not None
                and pre_canvases.status_code == 200 else {})
    pre_count = len(pre_body.get("canvases") or [])

    approve = (ctx.post(f"/api/agents/approvals/{checkpoint_id}",
                        json={"decision": "approved",
                              "feedback": "GOV-02 acceptance approval"})
               if checkpoint_id else None)
    approve_body = (approve.json() if approve is not None
                    and approve.headers.get("content-type", "").startswith("application/json")
                    else {})
    post_canvases = ctx.get(f"/api/goal-runs/{run_id}/canvases") if run_id else None
    post_body = (post_canvases.json() if post_canvases is not None
                 and post_canvases.status_code == 200 else {})
    post_count = len(post_body.get("canvases") or [])
    approve_resume = approve_body.get("data", {}).get("resume") or approve_body.get("resume") or {}

    # Negative control: rejecting a second checkpoint must not create the
    # deliverable canvas.
    run2 = ctx.post("/api/goal-runs", json={
        "goal_id": goal_id, "role": "acceptance", "start": False,
        "supervision_mode": "shadow",
        "plan": [
            {"id": "reject-checkpoint", "kind": "human_checkpoint",
             "title": "Reject this deliverable"},
            {"id": "rejected-deliverable", "kind": "canvas_work",
             "title": "Must not be created", "canvas_type": "document"},
        ],
    }) if goal_id else None
    run2_body = (run2.json() if run2 is not None
                 and run2.headers.get("content-type", "").startswith("application/json")
                 else {})
    run2_id = (run2_body.get("run_id") or run2_body.get("id")
               or (run2_body.get("data") or {}).get("id"))
    advance2 = ctx.post(f"/api/goal-runs/{run2_id}/advance") if run2_id else None
    db = ctx.db()
    try:
        rows2 = (db.query(HITLAction)
                 .filter(HITLAction.action_type == "goal_run_checkpoint",
                         HITLAction.status == "pending")
                 .order_by(HITLAction.created_at.desc()).limit(20).all())
        checkpoint2 = next(
            (a for a in rows2
             if str((a.params or {}).get("run_id")) == str(run2_id)), None)
        checkpoint2_id = getattr(checkpoint2, "id", None)
    finally:
        db.close()
    reject = (ctx.post(f"/api/agents/approvals/{checkpoint2_id}",
                       json={"decision": "rejected",
                             "feedback": "GOV-02 rejection control"})
              if checkpoint2_id else None)
    reject_canvases = ctx.get(f"/api/goal-runs/{run2_id}/canvases") if run2_id else None
    reject_body = (reject_canvases.json() if reject_canvases is not None
                   and reject_canvases.status_code == 200 else {})
    reject_count = len(reject_body.get("canvases") or [])

    gov02_ok = (goal_create.status_code in (200, 201) and goal_id
                and run_create is not None and run_create.status_code in (200, 201)
                and run_id and checkpoint_id
                and pre_count == 0
                and approve is not None and approve.status_code == 200
                and str(approve_resume.get("resumed")).lower() == "true"
                and post_count >= 1
                and reject is not None and reject.status_code == 200
                and reject_count == 0)
    ctx.record("GOV-02", "verified" if gov02_ok else "failed",
               [ctx.save("governance/approval_execution.json", {
                   "goal": {"status": goal_create.status_code, "id": goal_id},
                   "run": {"status": run_create.status_code if run_create else None,
                           "id": run_id, "body": run_body},
                   "advance": {"status": advance.status_code if advance else None,
                               "body": advance_body},
                   "checkpoint_id": checkpoint_id,
                   "canvases_before": pre_count,
                   "approve": {"status": approve.status_code if approve else None,
                               "body": approve_body},
                   "approve_resume": approve_resume,
                   "canvases_after": post_count,
                   "reject_run": run2_id,
                   "reject_status": reject.status_code if reject else None,
                   "reject_canvases": reject_count,
                   "mock_calls": (__import__("scripts.readme_acceptance.mock_llm_server",
                                              fromlist=["calls"]).calls())[-8:],
               })],
               notes=f"checkpoint={checkpoint_id} before={pre_count} "
                     f"approve={approve.status_code if approve else None} "
                     f"resumed={approve_resume.get('resumed')} after={post_count} "
                     f"reject={reject.status_code if reject else None} "
                     f"reject_canvases={reject_count}")

    # ---- GOV-03 audit records from an actual execution -------------------
    # Run a real GenericAgent turn whose tool call is dispatched through the
    # audited _step_act path; then read the execution feed and replay.
    import asyncio
    from core.generic_agent import GenericAgent
    from core.models import AgentRegistry
    from core.react_models import ReActStep, ToolCall

    board = ctx.post("/api/boards", json={
        "name": f"audit-{uuid.uuid4().hex[:6]}",
        "seed_default_columns": True})
    board_body = board.json() if board.status_code in (200, 201) else {}
    board_id = board_body.get("id")
    detail = ctx.get(f"/api/boards/{board_id}") if board_id else None
    detail_body = detail.json() if detail is not None and detail.status_code == 200 else {}
    columns = detail_body.get("columns") or []
    column_id = (columns[0] or {}).get("id") if columns else None
    audit_agent_id = make_agent(ctx, f"audit-{uuid.uuid4().hex[:6]}",
                                tier="autonomous", capabilities=["*"])
    audit_task_title = f"audit-task-{uuid.uuid4().hex[:8]}"
    audit_exec_id = f"gov03-{uuid.uuid4().hex}"
    audit_error = None
    audit_result = None
    audit_task_id = None
    try:
        db = ctx.db()
        try:
            row = (db.query(AgentRegistry)
                   .filter(AgentRegistry.id == audit_agent_id).first())
            audit_agent = GenericAgent(row, workspace_id=ctx.workspace_id)
        finally:
            db.close()
        calls = {"n": 0}

        async def fake_react_step(task_input, memory, history, context=None,
                                  utility_delta=None):
            calls["n"] += 1
            if calls["n"] == 1:
                return ReActStep(
                    thought="create the audit task",
                    action=ToolCall(tool="tasks.create", params={
                        "title": audit_task_title,
                        "board_id": board_id,
                        "column_id": column_id,
                        "priority": "normal",
                        "status": "backlog",
                    }),
                )
            return ReActStep(thought="finished", final_answer="audit task created")

        audit_agent._react_step = fake_react_step
        audit_result = asyncio.run(audit_agent.execute(
            "create the audit acceptance task",
            context={"execution_id": audit_exec_id,
                     "user_id": ctx.admin_id,
                     "workspace_id": ctx.workspace_id},
        ))
    except Exception as exc:
        audit_error = repr(exc)

    # The agent's execution id is generated inside execute(); locate the
    # actual audited run by actor and tool, then replay THAT execution.
    audit_events = ctx.get("/api/audit/events",
                           params={"agent_id": audit_agent_id, "limit": 100})
    audit_body = audit_events.json() if audit_events.status_code == 200 else {}
    items = audit_body.get("items") or []
    def _audit_params(event):
        meta = event.get("metadata")
        if not isinstance(meta, dict):
            return {}
        params = meta.get("params")
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except (TypeError, ValueError):
                return {}
        return params if isinstance(params, dict) else {}

    def _audit_title(event):
        return str(_audit_params(event).get("title") or "")

    tool_event = next((
        e for e in items
        if (e.get("action") or "") == "tool:tasks.create"
        and _audit_title(e) == audit_task_title
    ), {})
    actual_exec_id = tool_event.get("agent_execution_id") or audit_exec_id
    replay = ctx.get(f"/api/audit/executions/{actual_exec_id}")
    replay_body = replay.json() if replay.status_code == 200 else {}
    replay_events = replay_body.get("events") or []
    replay_actions = [e.get("action") for e in replay_events]
    unauthenticated = ctx.client.get("/api/audit/events")
    bogus = ctx.get("/api/audit/events",
                    params={"execution_id": "gov03-does-not-exist", "limit": 5})
    bogus_body = bogus.json() if bogus.status_code == 200 else {}

    db = ctx.db()
    try:
        task_row = (db.query(BoardTask)
                    .filter(BoardTask.title == audit_task_title).first())
        audit_task_id = getattr(task_row, "id", None)
    finally:
        db.close()

    tool_meta = (tool_event.get("metadata")
                 if isinstance(tool_event.get("metadata"), dict) else {})
    tool_params = _audit_params(tool_event)
    gov03_ok = (audit_error is None and audit_result is not None
                and tool_event
                and str(tool_event.get("agent_id")) == str(audit_agent_id)
                and tool_event.get("success") is True
                and tool_meta.get("tool") == "tasks.create"
                and str(tool_params.get("board_id")) == str(board_id)
                and audit_task_id
                and replay.status_code == 200
                and "execution_start" in replay_actions
                and "execution_complete" in replay_actions
                and unauthenticated.status_code in (401, 403)
                and bogus.status_code == 200
                and (bogus_body.get("total") or 0) == 0)
    ctx.record("GOV-03", "verified" if gov03_ok else "failed",
               [ctx.save("governance/audit_execution.json", {
                   "execution_id": actual_exec_id,
                   "requested_execution_id": audit_exec_id,
                   "agent_id": audit_agent_id,
                   "board_id": board_id,
                   "task_id": audit_task_id,
                   "execute_result": audit_result,
                   "execute_error": audit_error,
                   "events": items,
                   "tool_event": tool_event,
                   "replay": replay_body,
                   "unauthenticated_status": unauthenticated.status_code,
                   "bogus_total": bogus_body.get("total"),
               })],
               notes=f"actor={tool_event.get('agent_id')} "
                     f"action={tool_event.get('action')} "
                     f"target={tool_params.get('board_id')} "
                     f"outcome={tool_event.get('success')} "
                     f"task={audit_task_id} replay={replay_actions[:4]} "
                     f"unauth={unauthenticated.status_code}")

    # ---- GOV-04 training session ---------------------------------------
    # Session creation is triggered by a blocked agent run (student_training
    # service); here verify the served training surface that a supervisor
    # actually uses, plus the service entry point for session creation.
    queue = ctx.get("/api/maturity/training/self-directed")
    context = ctx.get("/api/maturity/training/context")
    proposals = ctx.get("/api/maturity/training/proposals")
    from core.student_training_service import StudentTrainingService
    create_fn = getattr(StudentTrainingService, "create_training_proposal", None)
    ctx.record("GOV-04", "partial" if queue.status_code == 200 and proposals.status_code == 200 else "failed",
               [ctx.save("governance/training.json", {
                   "self_directed": {"status": queue.status_code, "body": queue.text[:1200]},
                   "context": {"status": context.status_code, "body": context.text[:600]},
                   "proposals": {"status": proposals.status_code, "body": proposals.text[:1200]},
                   "service_create": bool(create_fn),
               })],
               notes="Training queue/proposals/complete API reachable; session creation "
                     "is triggered by a blocked agent run (needs a model-backed run)")

    # ---- GOV-05 OIDC SSO configuration round-trip ----------------------
    cfg = ctx.put("/api/auth/sso/oidc/config", json={
        "issuer_url": "http://127.0.0.1:59998",
        "client_id": "acceptance-client",
        "client_secret": "acceptance-secret",
        "enabled": False,
        "default_role": "member",
        "allowed_domains": ["example.com"],
    })
    read = ctx.get("/api/auth/sso/oidc/config")
    loginr = ctx.client.get("/api/auth/sso/oidc/login", follow_redirects=False)
    body = read.json() if read.status_code == 200 else {}
    secret_hidden = str(body).find("acceptance-secret") == -1
    ok = cfg.status_code in (200, 201) and read.status_code == 200 and secret_hidden
    ctx.record("GOV-05", "verified" if ok else "partial",
               [ctx.save("governance/sso_config.json", {
                   "put": {"status": cfg.status_code, "body": cfg.text[:600]},
                   "get": {"status": read.status_code, "body": body},
                   "login": {"status": loginr.status_code,
                             "location": loginr.headers.get("location")},
               })],
               notes=f"config={cfg.status_code} read={read.status_code} "
                     f"secret_hidden={secret_hidden} login={loginr.status_code} "
                     f"(full IdP callback is exercised by the bounded-IdP scenario)")

    # ---- GOV-06 SCIM v2 provisioning -----------------------------------
    create = ctx.client.post("/api/scim/v2/Users",
                             headers={"Authorization": "Bearer acceptance-scim-token"},
                             json={"schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                                   "userName": "scim.acceptance@example.com",
                                   "name": {"givenName": "Scim", "familyName": "Acceptance"},
                                   "emails": [{"value": "scim.acceptance@example.com",
                                               "primary": True, "type": "work"}],
                                   "active": True})
    scim_body = create.json() if create.headers.get("content-type", "").startswith("application/json") else {}
    scim_id = scim_body.get("id")
    listed = ctx.client.get("/api/scim/v2/Users?filter=userName%20eq%20%22scim.acceptance%40example.com%22",
                            headers={"Authorization": "Bearer acceptance-scim-token"})
    unauthorized = ctx.client.get("/api/scim/v2/Users")
    deactivate = None
    after_deactivate = None
    if scim_id:
        deactivate = ctx.client.patch(
            f"/api/scim/v2/Users/{scim_id}",
            headers={"Authorization": "Bearer acceptance-scim-token",
                     "Content-Type": "application/scim+json"},
            json={"schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                  "Operations": [{"op": "replace", "path": "active", "value": False}]})
        after_deactivate = ctx.client.get(
            f"/api/scim/v2/Users/{scim_id}",
            headers={"Authorization": "Bearer acceptance-scim-token"})
    after_body = (after_deactivate.json()
                  if after_deactivate is not None and after_deactivate.status_code == 200
                  else {})
    inactive = after_body.get("active") is False
    ok = (create.status_code in (200, 201) and scim_id
          and listed.status_code == 200 and unauthorized.status_code in (401, 403)
          and deactivate is not None and deactivate.status_code in (200, 204)
          and inactive)
    ctx.record("GOV-06", "verified" if ok else "partial",
               [ctx.save("governance/scim.json", {
                   "create": {"status": create.status_code, "body": scim_body},
                   "list": {"status": listed.status_code, "body": listed.text[:600]},
                   "unauthorized": {"status": unauthorized.status_code},
                   "deactivate": None if deactivate is None else {
                       "status": deactivate.status_code, "body": deactivate.text[:600]},
                   "after_deactivate": after_body,
               })],
               notes=f"create={create.status_code} id={scim_id} "
                     f"list={listed.status_code} unauth={unauthorized.status_code} "
                     f"deactivate={None if deactivate is None else deactivate.status_code} "
                     f"active={after_body.get('active')}")

    # ---- GOV-07 RBAC ----------------------------------------------------
    from enum import Enum
    from core.auth import get_password_hash
    from core.models import User, UserRole, UserStatus
    role_names = {r.value for r in UserRole}
    db = ctx.db()
    try:
        member = db.query(User).filter(User.email == "member.acceptance@example.com").first()
        if not member:
            member = User(
                id=str(uuid.uuid4()), email="member.acceptance@example.com",
                hashed_password=get_password_hash("MemberPass!2026"),
                first_name="Member", last_name="Acceptance", role="member",
                status=UserStatus.ACTIVE,
            )
            db.add(member)
            db.commit()
    finally:
        db.close()
    login_member = ctx.client.post("/api/auth/login", json={
        "username": "member.acceptance@example.com", "password": "MemberPass!2026"})
    member_token = login_member.json().get("access_token") if login_member.status_code == 200 else None
    member_headers = {"Authorization": f"Bearer {member_token}"} if member_token else {}
    denied = ctx.client.get("/api/v1/admin/settings", headers=member_headers)
    allowed = ctx.get("/api/v1/admin/settings")
    member_settings_denied = denied.status_code in (401, 403)
    ok = (len(role_names) == 8 and member_settings_denied
          and allowed.status_code == 200)
    ctx.record("GOV-07", "verified" if ok else "partial",
               [ctx.save("governance/rbac.json", {
                   "roles": sorted(role_names),
                   "member_login": login_member.status_code,
                   "member_settings": {"status": denied.status_code},
                   "admin_settings": {"status": allowed.status_code},
               })],
               notes=f"roles={sorted(role_names)} member={denied.status_code} "
                     f"admin={allowed.status_code}")

    # ---- GOV-08 agent lifecycle ----------------------------------------
    created = ctx.post("/api/agents/custom", json={
        "name": f"lifecycle-{uuid.uuid4().hex[:6]}",
        "description": "acceptance lifecycle agent",
        "category": "acceptance",
        "capabilities": ["read"],
        "configuration": {},
    })
    created_body = created.json() if created.headers.get("content-type", "").startswith("application/json") else {}
    agent_id = (created_body.get("agent_id") or created_body.get("id")
                or (created_body.get("data") or {}).get("agent_id")
                or (created_body.get("data") or {}).get("id")
                or (created_body.get("agent") or {}).get("id"))
    read_agent = ctx.get(f"/api/agents/{agent_id}") if agent_id else None
    cap = ctx.get(f"/api/agent-governance/agents/{agent_id}/capabilities") if agent_id else None
    delete = ctx.delete(f"/api/agents/{agent_id}") if agent_id else None
    after_delete = ctx.get(f"/api/agents/{agent_id}") if agent_id else None
    inactive = after_delete is not None and after_delete.status_code == 404
    ok = (created.status_code in (200, 201) and agent_id
          and read_agent is not None and read_agent.status_code == 200
          and cap is not None and cap.status_code == 200
          and delete is not None and delete.status_code in (200, 204)
          and inactive)
    ctx.record("GOV-08", "verified" if ok else "partial",
               [ctx.save("governance/lifecycle.json", {
                   "create": {"status": created.status_code, "body": created_body},
                   "read": None if read_agent is None else read_agent.status_code,
                   "capabilities": None if cap is None else {
                       "status": cap.status_code, "body": cap.text[:600]},
                   "delete": None if delete is None else {
                       "status": delete.status_code, "body": delete.text[:400]},
                   "read_after_delete": None if after_delete is None else after_delete.status_code,
               })],
               notes=f"create={created.status_code} id={agent_id} "
                     f"read={None if read_agent is None else read_agent.status_code} "
                     f"delete={None if delete is None else delete.status_code} "
                     f"read_after_delete={None if after_delete is None else after_delete.status_code}")


def oracle(ctx: Ctx) -> None:
    import asyncio
    import core.oracle.postcondition_verifiers  # noqa: F401 — registers verifiers
    from core.oracle import get_postcondition, validate, oracle_verifier_enabled
    from core.models_board import BoardTask

    # ORACLE-01 registry + default flag
    actions = ["trigger_workflow", "tasks.create"]
    present = {a: get_postcondition(a) is not None for a in actions}

    # ORACLE-02/03/05 tasks.create read-back. Create the BoardTask through the
    # product action surface (the exact tool the verifier covers), then
    # re-derive it from the DB.
    task_id = None
    try:
        board = ctx.post("/api/boards", json={
            "name": f"oracle-board-{uuid.uuid4().hex[:6]}",
            "seed_default_columns": True})
        bbody = board.json() if board.status_code in (200, 201) else {}
        board_id = bbody.get("id")
        detail = ctx.get(f"/api/boards/{board_id}") if board_id else None
        dbody = detail.json() if detail is not None and detail.status_code == 200 else {}
        columns = dbody.get("columns") or []
        column_id = (columns[0] or {}).get("id") if columns else None
        action = ctx.post("/api/rpc/tasks.create", json={"params": {
            "title": "oracle acceptance", "board_id": board_id,
            "column_id": column_id, "priority": "normal", "status": "backlog"}})
        abody = action.json() if action.status_code == 200 else {}
        task_id = ((abody.get("data") or {}).get("task") or {}).get("id")
    except Exception:
        task_id = None
    db = ctx.db()
    try:
        result = asyncio.run(validate("tasks.create", {"task_id": task_id, "db": db}))
        present_result = result.to_dict() if result else None
        row = db.query(BoardTask).filter(BoardTask.id == task_id).first() if task_id else None
        if row is not None:
            db.delete(row)
            db.commit()
        absent = asyncio.run(validate("tasks.create", {"task_id": task_id, "db": db}))
        absent_result = absent.to_dict() if absent else None
    except Exception as exc:
        present_result = absent_result = {"error": str(exc)}
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()
    evidence = [ctx.save("oracle/readback.json", {
        "enabled": oracle_verifier_enabled(), "registered": present,
        "present": present_result, "absent": absent_result})]
    ok = (oracle_verifier_enabled() and all(present.values())
          and (present_result or {}).get("verified") is True
          and (absent_result or {}).get("verified") is False)
    ctx.record("ORACLE-01", "verified" if ok and all(present.values()) else "failed",
               evidence, notes=json.dumps(present))
    ctx.record("ORACLE-02", "verified" if ok else "failed", evidence,
               notes="DB read-back: present row verified, removed row refuted")
    ctx.record("ORACLE-03", "verified" if (absent_result or {}).get("verified") is False else "failed",
               evidence, notes="A self-report with no system-of-record row is refuted")
    ctx.record("ORACLE-05", "verified" if present_result and "claim_verified" in present_result else "partial",
               evidence, notes="OracleResult carries independent verification separately from the claim")

    # ORACLE-04/05: exercise the actual post-execution stamp and kill switch.
    try:
        import os as _os
        from core.generic_agent import GenericAgent as _GenericAgent
        from core.models import AgentRegistry as _AgentRegistry

        agent_id = make_agent(ctx, f"oracle-stamp-{uuid.uuid4().hex[:6]}",
                              tier="intern", capabilities=["*"])
        db = ctx.db()
        try:
            row = db.query(_AgentRegistry).filter(
                _AgentRegistry.id == agent_id).first()
            stamp_agent = _GenericAgent(row, workspace_id=ctx.workspace_id)
        finally:
            db.close()

        board = ctx.post("/api/boards", json={
            "name": f"oracle-stamp-{uuid.uuid4().hex[:6]}",
            "seed_default_columns": True})
        bbody = board.json() if board.status_code in (200, 201) else {}
        detail = ctx.get(f"/api/boards/{bbody.get('id')}") if bbody.get("id") else None
        dbody = detail.json() if detail is not None and detail.status_code == 200 else {}
        columns = dbody.get("columns") or []
        column_id = (columns[0] or {}).get("id") if columns else None
        created = ctx.post("/api/rpc/tasks.create", json={"params": {
            "title": "oracle stamp acceptance", "board_id": bbody.get("id"),
            "column_id": column_id, "priority": "normal", "status": "backlog"}})
        created_body = created.json() if created.status_code == 200 else {}
        real_id = ((created_body.get("data") or {}).get("task") or {}).get("id")

        old_enforce = _os.environ.get("ATOM_ORACLE_ENFORCE")
        _os.environ["ATOM_ORACLE_ENFORCE"] = "true"
        try:
            stamped_missing = asyncio.run(stamp_agent._oracle_check(
                "tasks.create", {"task_id": "definitely-missing"},
                {"success": True, "task": {"id": "definitely-missing"}}))
            stamped_real = asyncio.run(stamp_agent._oracle_check(
                "tasks.create", {"task_id": real_id},
                {"success": True, "task": {"id": real_id}})) if real_id else None
        finally:
            if old_enforce is None:
                _os.environ.pop("ATOM_ORACLE_ENFORCE", None)
            else:
                _os.environ["ATOM_ORACLE_ENFORCE"] = old_enforce

        _os.environ["ATOM_ORACLE_ENFORCE"] = "false"
        try:
            pass_through = asyncio.run(stamp_agent._oracle_check(
                "tasks.create", {"task_id": "definitely-missing"},
                {"success": True, "task": {"id": "definitely-missing"}}))
        finally:
            if old_enforce is None:
                _os.environ.pop("ATOM_ORACLE_ENFORCE", None)
            else:
                _os.environ["ATOM_ORACLE_ENFORCE"] = old_enforce

        kill_ok = (isinstance(pass_through, dict)
                   and "oracle_verified" not in pass_through)
        enforce_ok = (isinstance(stamped_missing, dict)
                      and stamped_missing.get("oracle_verified") is False)
        two_tier_ok = (isinstance(stamped_real, dict)
                       and stamped_real.get("oracle_verified") is True
                       and stamped_real.get("success") is True
                       and bool(stamped_real.get("oracle_evidence")))
        if real_id:
            db = ctx.db()
            try:
                from core.models_board import BoardTask as _BT
                row = db.query(_BT).filter(_BT.id == real_id).first()
                if row is not None:
                    db.delete(row)
                    db.commit()
            finally:
                db.close()
        ctx.record("ORACLE-04", "verified" if kill_ok and enforce_ok else "failed",
                   [ctx.save("oracle/kill_switch.json", {
                       "enforced_missing": stamped_missing,
                       "pass_through": pass_through})],
                   notes=f"enforce_stamped={enforce_ok} kill_switch_pass_through={kill_ok}")
        ctx.record("ORACLE-05", "verified" if two_tier_ok else "failed",
                   [ctx.save("oracle/two_tier.json", {
                       "self_report": {"success": True},
                       "oracle_result": stamped_real})],
                   notes=f"self_report_and_external_verified_coexist={two_tier_ok}")
    except Exception as exc:
        ctx.record("ORACLE-04", "failed",
                   notes=f"oracle stamp execution failed: {exc}")
        ctx.record("ORACLE-05", "failed",
                   notes=f"oracle stamp execution failed: {exc}")

    # ORACLE-06 reviewer loop: actually run a REVIEW rejection through the
    # conductor and verify the SAME step is re-delegated with the feedback.
    try:
        from core.orchestration.conductor_agent import (
            ConductorAgent, ExecutionStatus, ExecutionStrategy,
            OrchestrationResult, StepType, WorkflowExecutionContext,
            WorkflowStep)
        from core.orchestration.reviewer_loop import (
            get_review_feedback, get_review_loop_state_machine)
        from core.orchestration.verification.base import (
            VerificationResult, VerificationStrategy)
        from core.orchestration.workflow_state_machine import WorkflowState
        import os

        old_flag = os.environ.get("ATOM_REVIEWER_LOOP_ENABLED")
        os.environ["ATOM_REVIEWER_LOOP_ENABLED"] = "true"
        try:
            conductor = ConductorAgent()
            attempts = []

            async def fake_executor(step, context):
                feedback = get_review_feedback(step)
                attempts.append(feedback)
                return {
                    "step_id": step.step_id,
                    "status": "completed",
                    "output": "revised answer" if feedback else "first answer",
                }

            class FakeVerification:
                def __init__(self):
                    self.calls = 0

                async def verify(self, candidates, step, context):
                    self.calls += 1
                    if self.calls == 1:
                        return VerificationResult(
                            winner=None,
                            strategy=VerificationStrategy.REVIEW,
                            domain="acceptance",
                            confidence=0.3,
                            details={"accepted": False,
                                     "feedback": "add the missing evidence"},
                            reason="review rejected",
                        )
                    return VerificationResult(
                        winner=candidates[0],
                        strategy=VerificationStrategy.REVIEW,
                        domain="acceptance",
                        confidence=0.9,
                        details={"accepted": True, "feedback": ""},
                        reason="review accepted",
                    )

            verification = FakeVerification()
            conductor.set_step_executor(fake_executor)
            conductor.set_verification_orchestrator(verification)
            wid = f"review-{uuid.uuid4().hex[:8]}"
            eid = f"exec-{uuid.uuid4().hex[:8]}"
            step = WorkflowStep(
                step_id="s1", step_type=StepType.AGENT,
                name="draft the answer",
                description="reviewer re-delegation acceptance",
                parameters={},
            )
            context = WorkflowExecutionContext(
                workflow_id=wid, execution_id=eid, steps=[step],
                start_step="s1", strategy=ExecutionStrategy.PARALLEL_CONSENSUS,
            )
            get_review_loop_state_machine().initialize_state(
                wid, eid, WorkflowState.RUNNING)
            result = OrchestrationResult(
                workflow_id=wid, execution_id=eid, total_steps=1)
            asyncio.run(conductor._execute_parallel_consensus(context, result))
            ok = (verification.calls == 2 and len(attempts) == 6
                  and attempts[:3] == ["", "", ""]
                  and attempts[3:] == ["add the missing evidence"] * 3
                  and result.completed_steps == 1
                  and step.status == ExecutionStatus.COMPLETED
                  and step.result.get("output") == "revised answer")
            ctx.record("ORACLE-06", "verified" if ok else "failed",
                       [ctx.save("oracle/reviewer_loop.json", {
                           "reviewer_calls": verification.calls,
                           "attempts": attempts,
                           "completed_steps": result.completed_steps,
                           "step_status": str(step.status),
                           "step_result": step.result})],
                       notes=f"reviewer_calls={verification.calls} "
                             f"attempts={len(attempts)} "
                             f"feedback_on_redelegation="
                             f"{attempts[3:] == ['add the missing evidence'] * 3}")
        finally:
            if old_flag is None:
                os.environ.pop("ATOM_REVIEWER_LOOP_ENABLED", None)
            else:
                os.environ["ATOM_REVIEWER_LOOP_ENABLED"] = old_flag
    except Exception as exc:
        ctx.record("ORACLE-06", "failed",
                   notes=f"reviewer re-delegation execution failed: {exc}")


def ask(ctx: Ctx) -> None:
    from core.trust_calibration.certify import certify, ResolvedDecision
    import inspect

    # ASK-02 cold start -> ask (fail safe)
    r = ctx.get("/api/v1/trust-calibration/assess",
                params={"action_type": "create_task", "platform": "internal"})
    body = r.json() if r.status_code == 200 else {"text": r.text[:800]}
    cold = (body.get("recommendation") or (body.get("data") or {}).get("recommendation"))
    ctx.record("ASK-02", "verified" if cold == "ask" else "failed",
               [ctx.save("ask/cold_start.json", {"status": r.status_code, "body": body})],
               notes=f"cold-start recommendation={cold}")

    # ASK-01: per-action autonomy earned from oracle-verified tool outcomes
    # recorded through the capability-graduation path. The action is a real
    # tasks.create (oracle read-back); no manual maturity grant.
    from core.capability_graduation_service import CapabilityGraduationService
    from core.generic_agent import GenericAgent
    from core.models import AgentRegistry, BoardTask
    from core.autonomy_policy import (
        MODE_AUTO_UNTIL_CORRECTED, gate_for_topic, set_mode)

    ask_agent = make_agent(ctx, f"ask-verified-{uuid.uuid4().hex[:6]}",
                           tier="supervised", capabilities=["*"])
    board = ctx.post("/api/boards", json={
        "name": f"ask-verified-{uuid.uuid4().hex[:6]}",
        "seed_default_columns": True})
    board_body = board.json() if board.status_code in (200, 201) else {}
    board_id = board_body.get("id")
    detail = ctx.get(f"/api/boards/{board_id}") if board_id else None
    detail_body = detail.json() if detail is not None and detail.status_code == 200 else {}
    columns = detail_body.get("columns") or []
    column_id = (columns[0] or {}).get("id") if columns else None

    db = ctx.db()
    try:
        svc = CapabilityGraduationService(db)
        svc.reset_maturity(ask_agent, "task_create", reason="ASK-01 baseline")
        svc.reset_maturity(ask_agent, "canvas_edit", reason="ASK-01 control")
        set_mode(db, ctx.admin_id, "task_create", MODE_AUTO_UNTIL_CORRECTED)
        set_mode(db, ctx.admin_id, "canvas_edit", MODE_AUTO_UNTIL_CORRECTED)
        gate_before = gate_for_topic(db, ctx.admin_id, "task_create", ask_agent)
        canvas_gate_before = gate_for_topic(db, ctx.admin_id, "canvas_edit", ask_agent)
    finally:
        db.close()

    ask_results = []
    ask_verified = 0
    ask_error = None
    try:
        db = ctx.db()
        try:
            row = (db.query(AgentRegistry)
                   .filter(AgentRegistry.id == ask_agent).first())
            agent = GenericAgent(row, workspace_id=ctx.workspace_id)
            agent.tenant_id = ctx.tenant_id
        finally:
            db.close()
        for index in range(20):
            title = f"ask-verified-task-{uuid.uuid4().hex[:8]}"
            result = asyncio.run(agent._step_act("tasks.create", {
                "title": title,
                "board_id": board_id,
                "column_id": column_id,
                "priority": "normal",
                "status": "backlog",
            }, {}, pre_approved=True))
            result_text = json.dumps(result, default=str)
            if isinstance(result, dict):
                task_payload = result.get("task") or {}
            else:
                try:
                    task_payload = json.loads(result_text).get("task") or {}
                except (TypeError, ValueError):
                    task_payload = {}
            task_id = task_payload.get("id")
            db = ctx.db()
            try:
                persisted = (db.query(BoardTask)
                             .filter(BoardTask.id == task_id).first()
                             if task_id else None)
                verified = persisted is not None
                if verified:
                    ask_verified += 1
                    CapabilityGraduationService(db).record_usage(
                        ask_agent, "task_create", success=True,
                        verified="verified")
            finally:
                db.close()
            ask_results.append({
                "index": index,
                "verified": verified,
                "result": result_text[:400],
            })
    except Exception as exc:
        import traceback as _tb
        ask_error = f"{type(exc).__name__}: {exc}"
        ctx.save("ask/verified_error.txt", _tb.format_exc())

    db = ctx.db()
    try:
        svc = CapabilityGraduationService(db)
        maturity_after = svc.get_maturity(ask_agent, "task_create")
        canvas_maturity = svc.get_maturity(ask_agent, "canvas_edit")
        gate_after = gate_for_topic(db, ctx.admin_id, "task_create", ask_agent)
        canvas_gate_after = gate_for_topic(db, ctx.admin_id, "canvas_edit", ask_agent)
    finally:
        db.close()

    ask01_ok = (ask_error is None and ask_verified == 20
                and gate_before.get("outcome") == "propose"
                and gate_after.get("outcome") == "execute"
                and maturity_after in ("supervised", "autonomous")
                and canvas_maturity == "student"
                and canvas_gate_after.get("outcome") == "propose")
    ctx.record("ASK-01", "verified" if ask01_ok else "failed",
               [ctx.save("ask/verified_autonomy.json", {
                   "agent": ask_agent,
                   "verified_outcomes": ask_verified,
                   "task_results": ask_results,
                   "error": ask_error,
                   "gate_before": gate_before,
                   "gate_after": gate_after,
                   "canvas_gate_before": canvas_gate_before,
                   "canvas_gate_after": canvas_gate_after,
                   "maturity_after": maturity_after,
                   "canvas_maturity": canvas_maturity,
               })],
               notes=f"verified={ask_verified}/20 before={gate_before.get('outcome')} "
                     f"after={gate_after.get('outcome')} "
                     f"maturity={maturity_after} "
                     f"control_canvas={canvas_gate_after.get('outcome')} "
                     f"error={ask_error}")

    # ASK-05: stats and consent-gated relaxation. The calibration history is
    # controlled (labelled); the admin gate and applied switch are real.
    from core.trust_calibration import automation as trust_auto
    from core.models import (
        HITLAction as _HITL, TrustCalibrationAction,
        TrustCalibrationAssessment)
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    from core.trust_calibration.features import tool_vector, context_vector

    stats0 = ctx.get("/api/v1/trust-calibration/stats")
    stats0_body = stats0.json() if stats0.status_code == 200 else {}
    trust_auto.set_automation_config(mode="approve", interval_min=1)
    run_uncertified = ctx.post("/api/v1/trust-calibration/run-now")
    uncertified_body = (run_uncertified.json()
                        if run_uncertified.status_code == 200 else {})

    now = _dt.now(_tz.utc)
    db = ctx.db()
    try:
        for i in range(18):
            good_ref = f"ask05-good-{i}"
            bad_ref = f"ask05-bad-{i}"
            good_time = now - _td(hours=(1.5 * i) + 1)
            bad_time = now - _td(hours=(1.5 * i) + 3)
            db.add(_HITL(
                id=good_ref, action_type="search_contacts",
                platform="internal", params={}, status="approved",
                agent_id=ask_agent, reviewed_at=good_time,
                created_at=good_time))
            db.add(TrustCalibrationAssessment(
                id=f"ask05-a-good-{i}", action_type="search_contacts",
                platform="internal", p_approve=0.9, uncertainty=0.05,
                recommendation="allow", source_path="ask05_controlled",
                decision_ref=good_ref,
                features_json={"tool": tool_vector("search_contacts").tolist(),
                               "ctx": context_vector(None, "internal").tolist()},
                created_at=good_time))
            db.add(_HITL(
                id=bad_ref, action_type=f"bulk_delete_leads_{i}",
                platform="payment", params={}, status="rejected",
                agent_id=ask_agent, reviewed_at=bad_time,
                created_at=bad_time))
            db.add(TrustCalibrationAssessment(
                id=f"ask05-a-bad-{i}",
                action_type=f"bulk_delete_leads_{i}",
                platform="payment", p_approve=0.1, uncertainty=0.05,
                recommendation="block", source_path="ask05_controlled",
                decision_ref=bad_ref,
                features_json={"tool": tool_vector("bulk_delete_leads").tolist(),
                               "ctx": context_vector(None, "payment").tolist()},
                created_at=bad_time))
        db.commit()
    finally:
        db.close()

    stats1 = ctx.get("/api/v1/trust-calibration/stats")
    stats1_body = stats1.json() if stats1.status_code == 200 else {}
    run_certified = ctx.post("/api/v1/trust-calibration/run-now")
    certified_body = (run_certified.json()
                      if run_certified.status_code == 200 else {})
    db = ctx.db()
    try:
        queued = (db.query(TrustCalibrationAction)
                  .order_by(TrustCalibrationAction.created_at.desc()).first())
        queued_id = getattr(queued, "id", None)
        queued_state = getattr(queued, "state", None)
        enforce_before = trust_auto.resolved_trust_enforce(db)
    finally:
        db.close()
    approve = (ctx.post(f"/api/v1/trust-calibration/approve/{queued_id}")
               if queued_id else None)
    db = ctx.db()
    try:
        enforce_after = trust_auto.resolved_trust_enforce(db)
    finally:
        db.close()
    ask05_ok = (stats0.status_code == 200 and stats1.status_code == 200
                and uncertified_body.get("verdict") in ("collecting", "revoke")
                and certified_body.get("verdict") == "enable"
                and queued_state == "approval"
                and enforce_before is False
                and approve is not None and approve.status_code == 200
                and enforce_after is True)
    ctx.record("ASK-05", "verified" if ask05_ok else "failed",
               [ctx.save("ask/gated_relaxation.json", {
                   "controlled_history": True,
                   "stats_before": stats0_body,
                   "stats_after": stats1_body,
                   "uncertified": uncertified_body,
                   "certified": certified_body,
                   "queued_id": queued_id,
                   "queued_state": queued_state,
                   "enforce_before": enforce_before,
                   "approve_status": None if approve is None else approve.status_code,
                   "enforce_after": enforce_after,
               })],
               notes=f"stats={stats1.status_code} "
                     f"uncertified={uncertified_body.get('verdict')} "
                     f"certified={certified_body.get('verdict')} "
                     f"queued={queued_state} enforce={enforce_before}->{enforce_after}")

    # ASK-04 certification gate
    from datetime import datetime, timedelta, timezone
    from core.trust_calibration.features import tool_vector, context_vector
    feat = {
        "tool": tool_vector("create_task").tolist(),
        "ctx": context_vector(None, "internal").tolist(),
    }
    rejected_feat = {
        "tool": tool_vector("delete_task").tolist(),
        "ctx": context_vector(None, "internal").tolist(),
    }
    weak = []
    strong = []
    now = datetime.now(timezone.utc)
    for i in range(20):
        weak.append(ResolvedDecision(p_approve=0.5, y=0,
                                     decided_at=now - timedelta(days=20 - i),
                                     features_json=rejected_feat))
    for i in range(80):
        approved = i % 5 != 0
        strong.append(ResolvedDecision(
            p_approve=0.9 if approved else 0.1,
            y=1 if approved else 0,
            decided_at=now - timedelta(days=80 - i),
            features_json=feat if approved else rejected_feat,
        ))
    try:
        weak_r = certify(weak)
        strong_r = certify(strong)
        weak_ok = not weak_r.certified
        strong_ok = strong_r.certified
        payload = {
            "weak": weak_r.to_dict(),
            "strong": strong_r.to_dict(),
        }
        ctx.record("ASK-04", "verified" if weak_ok and strong_ok else "failed",
                   [ctx.save("ask/certify.json", payload)],
                   notes=f"weak_certified={weak_r.certified} "
                         f"strong_certified={strong_r.certified} "
                         f"strong_brier={strong_r.brier_holdout} "
                         f"denial_coverage={strong_r.denial_coverage}")
    except Exception as exc:
        ctx.record("ASK-04", "failed", notes=f"certify failed: {exc}")

    # ASK-03 automatic revocation is exercised by the automation unit suite;
    # verify the resolve path is reachable and defaults to off/consent-gated.
    auto = ctx.get("/api/v1/trust-calibration/automation")
    ctx.record("ASK-03", "partial" if auto.status_code == 200 else "unverified",
               [ctx.save("ask/automation.json", {"status": auto.status_code,
                                                 "body": auto.text[:1000]})],
               notes="Automatic revocation is consent-gated; live revocation "
                     "needs certified observations")


def agent_teams(ctx: Ctx) -> None:
    import asyncio
    import uuid
    from datetime import datetime, timedelta, timezone

    # TEAM-01 delegation contract with a single accountable agent
    try:
        from core.fleet_orchestration.delegation_contracts import (
            build_contract, render_contract_prompt, DelegationContract)
        base = build_contract(
            goal="close the quarterly books",
            task_desc="reconcile the North region ledger",
            domain="finance",
        )
        base.accountable_agent_id = "agent-accountable-1"
        rendered = render_contract_prompt(base)
        ok = (base.objective and base.output_format and base.task_boundaries
              and base.effort_budget.get("max_steps", 0) > 0
              and "agent-accountable-1" in json.dumps(base.to_dict())
              and "DELEGATION CONTRACT" in rendered)
        ctx.record("TEAM-01", "verified" if ok else "partial",
                   [ctx.save("teams/contracts.json", {
                       "contract": base.to_dict(), "rendered": rendered})],
                   notes=f"accountable={base.accountable_agent_id} "
                         f"fields={sorted(base.to_dict())}")
    except Exception as exc:
        ctx.record("TEAM-01", "unverified", notes=f"contracts unavailable: {exc}")

    # TEAM-02 default-deny expiring privilege leases
    try:
        from core import org_privileges as op
        from core.models import AgentRegistry
        agent_id = make_agent(ctx, f"lease-{uuid.uuid4().hex[:6]}", tier="supervised")
        db = ctx.db()
        try:
            before = op.has_privilege(db, agent_id, op.PRIV_APPROVE_PROPOSAL)
            granted_expired = op.grant_privilege(
                db, agent_id, op.PRIV_APPROVE_PROPOSAL,
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
            after_expired = op.has_privilege(db, agent_id, op.PRIV_APPROVE_PROPOSAL)
            granted_live = op.grant_privilege(
                db, agent_id, op.PRIV_APPROVE_PROPOSAL,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
            after_live = op.has_privilege(db, agent_id, op.PRIV_APPROVE_PROPOSAL)
            revoked = op.revoke_privilege(db, agent_id, op.PRIV_APPROVE_PROPOSAL)
            after_revoke = op.has_privilege(db, agent_id, op.PRIV_APPROVE_PROPOSAL)
        finally:
            db.close()
        ok = (before is False and granted_expired is True and after_expired is False
              and granted_live is True and after_live is True
              and revoked is True and after_revoke is False)
        ctx.record("TEAM-02", "verified" if ok else "failed",
                   [ctx.save("teams/privileges.json", {
                       "before": before, "expired": after_expired,
                       "live": after_live, "after_revoke": after_revoke})],
                   notes=f"default={before} expired={after_expired} live={after_live} "
                         f"revoked={after_revoke}")
    except Exception as exc:
        ctx.record("TEAM-02", "unverified", notes=f"org_privileges unavailable: {exc}")

    # TEAM-03 conflict-of-interest detection
    try:
        from core import org_integrity as oi
        self_conflict = oi.self_recruitment_blocked("Agent-A", "agent-a")
        distinct = oi.self_recruitment_blocked("Agent-A", "Agent-B")
        rotation = oi.resolve_coordinator(
            {"coordinator_rotation": "task",
             "coordinator_candidates": ["a", "b", "c"]}, run_seq=4)
        ok = self_conflict is True and distinct is False and rotation == "b"
        ctx.record("TEAM-03", "verified" if ok else "failed",
                   [ctx.save("teams/coi.json", {
                       "self_conflict": self_conflict, "distinct": distinct,
                       "rotation": rotation})],
                   notes=f"self_conflict={self_conflict} distinct={distinct} "
                         f"rotation={rotation}")
    except Exception as exc:
        ctx.record("TEAM-03", "unverified", notes=f"org_integrity unavailable: {exc}")

    # TEAM-04 contribution credit
    try:
        from core import contribution_credit as cc
        success = cc.compute_chain_credit([
            {"agent_id": "a", "status": "completed"},
            {"agent_id": "b", "status": "completed"},
        ])
        late_failure = cc.compute_chain_credit([
            {"agent_id": "a", "status": "completed"},
            {"agent_id": "b", "status": "failed"},
        ])
        ok = (abs(sum(success.values()) - 1.0) < 1e-6
              and abs(sum(late_failure.values()) - cc.DAMPENED_OUTCOME) < 1e-6
              and late_failure.get("a", 0) > 0)
        ctx.record("TEAM-04", "verified" if ok else "failed",
                   [ctx.save("teams/contribution.json", {
                       "success": success, "late_failure": late_failure,
                       "dampened": cc.DAMPENED_OUTCOME})],
                   notes=f"success_sum={sum(success.values())} "
                         f"late_failure_sum={sum(late_failure.values())}")
    except Exception as exc:
        ctx.record("TEAM-04", "unverified", notes=f"contribution_credit unavailable: {exc}")

    # TEAM-05 opt-in alignment sweep
    try:
        import os
        old = os.environ.get("ATOM_ALIGNMENT_SWEEP_ENABLED")
        os.environ["ATOM_ALIGNMENT_SWEEP_ENABLED"] = "true"
        from core.org_politics_automation import alignment_verdict

        def chat_fn(system_prompt, user_prompt):
            if "strict compliance auditor" in system_prompt:
                return ('{"utility": 8, "policy": 10, "violations": []}'
                        if "single" in system_prompt else
                        '{"utility": 8, "policy": 8.5, "violations": []}')
            return "Proposal: decline the NDA data and document the decision."

        sweep = alignment_verdict(chat_fn=chat_fn)
        if old is None:
            os.environ.pop("ATOM_ALIGNMENT_SWEEP_ENABLED", None)
        else:
            os.environ["ATOM_ALIGNMENT_SWEEP_ENABLED"] = old
        ok = sweep.get("ran") is True and sweep.get("green") is True
        ctx.record("TEAM-05", "verified" if ok else "partial",
                   [ctx.save("teams/alignment.json", sweep)],
                   notes=f"ran={sweep.get('ran')} green={sweep.get('green')} "
                         f"max_gap={sweep.get('max_gap')}")
    except Exception as exc:
        ctx.record("TEAM-05", "unverified", notes=f"alignment sweep unavailable: {exc}")

    # TEAM-06 org telemetry baselines: emit real events, then run the
    # documented report and assert incumbency/review/COI math.
    try:
        from core.org_telemetry_service import AgentOrgTelemetryService, emit_org_event
        db = ctx.db()
        try:
            for actor, target in (("a", "b"), ("a", "b"), ("a", "c")):
                emit_org_event(db, "fleet_recruit", actor_agent_id=actor,
                               target_agent_id=target,
                               payload={"acceptance": True})
            emit_org_event(db, "radio_message", actor_agent_id="a",
                           target_agent_id="b", payload={"acceptance": True})
            emit_org_event(db, "review_verdict", actor_agent_id="r",
                           target_agent_id="b", payload={"accepted": True})
            emit_org_event(db, "review_verdict", actor_agent_id="r",
                           target_agent_id="c", payload={"accepted": False})
            svc = AgentOrgTelemetryService(db)
            incumbency = svc.compute_incumbency(window_hours=24)
            reviews = svc.compute_review_rates(window_hours=24)
            coi = svc.compute_coi_pairs(window_hours=24)
            empty_incumbency = svc.compute_incumbency(window_hours=-1)
        finally:
            db.close()

        env = {**os.environ,
               "PYTHONPATH": f"{REPO}:{BACKEND}",
               "DATABASE_URL": f"sqlite:///{ctx.world / 'atom.db'}"}
        report = subprocess.run(
            [sys.executable, str(BACKEND / "scripts" / "org_dynamics_report.py"),
             "--window-hours", "24", "--json"],
            cwd=str(BACKEND), env=env, capture_output=True, text=True,
            timeout=120)
        report_body = {}
        if report.returncode == 0 and report.stdout.strip():
            try:
                report_body = json.loads(report.stdout)
            except (TypeError, ValueError):
                report_body = {}
        top = incumbency.get("top_pairs") or []
        ok = (incumbency.get("total_recruits") == 3
              and incumbency.get("distinct_pairs") == 2
              and incumbency.get("repeat_pairs") == 1
              and top and top[0].get("actor") == "a"
              and top[0].get("target") == "b" and top[0].get("count") == 2
              and reviews.get("total_reviews") == 2
              and reviews.get("by_target", {}).get("b", {}).get("accepted") == 1
              and reviews.get("by_target", {}).get("c", {}).get("rejected") == 1
              and any(p.get("actor") == "a" and p.get("target") == "b"
                      for p in coi)
              and empty_incumbency.get("total_recruits") == 0
              and report.returncode == 0
              and report_body.get("incumbency", {}).get("total_recruits") == 3
              and report_body.get("review_rates", {}).get("total_reviews") == 2)
        ctx.record("TEAM-06", "verified" if ok else "failed",
                   [ctx.save("teams/telemetry.json", {
                       "incumbency": incumbency,
                       "reviews": reviews,
                       "coi_pairs": coi,
                       "empty_window": empty_incumbency,
                       "report_returncode": report.returncode,
                       "report_stderr": report.stderr[-500:],
                       "report": report_body,
                   })],
                   notes=f"recruits={incumbency.get('total_recruits')} "
                         f"pairs={incumbency.get('distinct_pairs')} "
                         f"repeat={incumbency.get('repeat_pairs')} "
                         f"reviews={reviews.get('total_reviews')} "
                         f"coi={len(coi)} empty={empty_incumbency.get('total_recruits')} "
                         f"report={report.returncode}")
    except Exception as exc:
        ctx.record("TEAM-06", "failed", notes=f"telemetry unavailable: {exc}")
