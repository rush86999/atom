"""GraphRAG and goal-run scenarios."""
from __future__ import annotations

import json
import time
import uuid

from .common import Ctx, make_agent


def graphrag(ctx: Ctx) -> None:
    base = "/api/graphrag/api/graphrag"
    ws = ctx.workspace_id or "default"
    suffix = uuid.uuid4().hex[:6]

    # Ingest a document with deterministic pattern entities.
    ingest = ctx.post(f"{base}/ingest", json={
        "doc_id": f"acceptance-graph-{suffix}",
        "text": ("Contact alice@example.com on 2026-10-01 about the Atlas programme. "
                 "Visit https://example.com/atlas for context."),
        "source": "acceptance",
    })
    ents = ctx.get(f"{base}/entities", params={"workspace_id": ws, "limit": 100})
    ent_body = ents.json() if ents.status_code == 200 else {}
    entities = ((ent_body.get("data") or {}).get("entities") or [])
    names = {e.get("name") for e in entities}
    ctx.record("GRAPH-01",
               "verified" if ingest.status_code == 200 and names else "partial",
               [ctx.save("graphrag/ingest.json", {
                   "ingest": {"status": ingest.status_code, "body": ingest.text[:600]},
                   "entity_count": len(entities), "names": sorted(names)[:30],
                   "llm_calls": [c.get("path") for c in
                                 __import__("scripts.readme_acceptance.mock_llm_server",
                                            fromlist=["calls"]).calls()][-5:]})],
               notes=f"entities={len(entities)} names={sorted(names)[:6]}")

    # Add two related entities and an edge for multi-hop/community work.
    a = ctx.post(f"{base}/entities", params={"workspace_id": ws}, json={
        "name": f"Atlas-{suffix}", "type": "project",
        "description": "acceptance project"})
    b = ctx.post(f"{base}/entities", params={"workspace_id": ws}, json={
        "name": f"Borealis-{suffix}", "type": "project",
        "description": "downstream project"})
    rel = ctx.post(f"{base}/relationships", params={"workspace_id": ws}, json={
        "from_entity": f"Atlas-{suffix}", "to_entity": f"Borealis-{suffix}",
        "relationship_type": "depends_on", "description": "acceptance edge"})
    neighbors = ctx.get(f"{base}/entities/{a.json().get('data', {}).get('id', 'missing')}/neighbors"
                        if a.status_code == 200 else f"{base}/entities/missing/neighbors",
                        params={"workspace_id": ws, "depth": 2})
    nbody = neighbors.json() if neighbors.status_code == 200 else {}
    neighbors_data = nbody.get("data") or {}
    neighbor_names = json.dumps(neighbors_data)
    hop_ok = f"Borealis-{suffix}" in neighbor_names or f"Atlas-{suffix}" in neighbor_names
    ctx.record("GRAPH-02", "verified" if hop_ok else "partial",
               [ctx.save("graphrag/hop.json", {
                   "entity_a": a.text[:500], "entity_b": b.text[:500],
                   "relationship": rel.text[:500], "neighbors": nbody})],
               notes=f"two_hop_visible={hop_ok}")

    communities = ctx.post(f"{base}/build-communities",
                           params={"user_id": ctx.admin_id})
    cbody = communities.json() if communities.status_code == 200 else {}
    cdata = cbody.get("data") or {}
    stats = ctx.get(f"{base}/stats", params={"workspace_id": ws})
    ctx.record("GRAPH-03", "verified" if communities.status_code == 200 and cdata else "partial",
               [ctx.save("graphrag/communities.json", {
                   "build": {"status": communities.status_code, "body": cdata},
                   "stats": stats.text[:1000]})],
               notes=f"communities={json.dumps(cdata)[:400]}")

    query = ctx.post(f"{base}/query", json={
        "query": f"Atlas-{suffix}", "workspace_id": ws, "mode": "local"})
    qbody = query.json() if query.status_code == 200 else {}
    ctx.record("GRAPH-05", "partial",
               [ctx.save("graphrag/query.json", {"status": query.status_code,
                                                 "body": qbody})],
               notes="Graph query works at the API; the D3 explorer page itself is "
                     "a browser check (separate UI scenario)")

    # JIT fact verification lives under the admin governance routes. The
    # verifier checks citations as S3 keys or LOCAL FILES (it is not an HTTP
    # fetcher), so cite a real local evidence file rather than a loopback URL.
    citation_path = ctx.world / "evidence" / "jit_citation.txt"
    citation_path.parent.mkdir(parents=True, exist_ok=True)
    citation_path.write_text("acceptance citation evidence\n")
    fact = ctx.post("/api/admin/governance/facts", json={
        "fact": f"Atlas-{suffix} depends on Borealis-{suffix}.",
        "citations": [str(citation_path)],
        "reason": "acceptance", "domain": "operations"})
    fbody = fact.json() if fact.headers.get("content-type", "").startswith("application/json") else {}
    fact_id = fbody.get("id")
    verify = ctx.post("/api/admin/governance/jit/verify-citations", json={
        "citations": [str(citation_path)]})
    vbody = verify.json() if verify.status_code == 200 else {}
    verified_hits = [r for r in (vbody.get("results") or []) if r.get("exists")]
    ctx.record("GRAPH-04", "verified" if fact.status_code in (200, 201) and fact_id and
               verify.status_code == 200 and verified_hits else "partial",
               [ctx.save("graphrag/jit.json", {
                   "fact": {"status": fact.status_code, "body": fbody},
                   "verify": {"status": verify.status_code, "body": vbody},
               })],
               notes=f"fact={fact.status_code} id={fact_id} "
                     f"verify={verify.status_code} verified={len(verified_hits)}")


def goals(ctx: Ctx) -> None:
    title = f"Acceptance goal {uuid.uuid4().hex[:6]}"
    create = ctx.post("/api/goals", json={
        "title": title, "description": "README acceptance goal",
        "criteria": [{"description": "produce a result"}],
        "key_results": [{"description": "result exists"}],
    })
    cbody = create.json() if create.status_code == 200 else {}
    goal_id = (cbody.get("goal_id") or cbody.get("id")
               or (cbody.get("goal") or {}).get("id")
               or (cbody.get("data") or {}).get("id"))
    listed = ctx.get("/api/goals")
    ctx.record("CORE-05", "verified" if create.status_code in (200, 201) and goal_id
               and listed.status_code == 200 and title in listed.text else "partial",
               [ctx.save("goals/create.json", {
                   "create": {"status": create.status_code, "body": cbody},
                   "list": {"status": listed.status_code, "body": listed.text[:800]}})],
               notes=f"goal={goal_id}")

    # A stopped run exercises durable status without a model call.
    run = ctx.post("/api/goal-runs", json={
        "goal_id": goal_id, "role": "acceptance", "start": False,
        "plan": [{"step_id": "s1", "description": "deterministic acceptance step"}],
        "supervision_mode": "shadow",
    }) if goal_id else None
    rbody = run.json() if run is not None and run.headers.get("content-type", "").startswith("application/json") else {}
    run_id = rbody.get("run_id") or rbody.get("id") or (rbody.get("data") or {}).get("id")
    read = ctx.get(f"/api/goal-runs/{run_id}") if run_id else None
    rread = read.json() if read is not None and read.status_code == 200 else {}
    status = rread.get("status") or (rread.get("data") or {}).get("status")
    cancel = ctx.post(f"/api/goal-runs/{run_id}/cancel") if run_id else None
    ctx.record("GOAL-05", "verified" if run is not None and run.status_code in (200, 201)
               and run_id and read is not None and read.status_code == 200
               and status and cancel is not None and cancel.status_code in (200, 204) else "partial",
               [ctx.save("goals/run.json", {
                   "run": None if run is None else {"status": run.status_code, "body": rbody},
                   "read": None if read is None else {"status": read.status_code,
                                                      "body": rread},
                   "cancel": None if cancel is None else cancel.status_code,
               })],
               notes=f"run={run_id} status={status} "
                     f"cancel={None if cancel is None else cancel.status_code}")

    # GOAL-01: definition_of_done is evaluated as the loop's done-predicate.
    try:
        from core.agent_objective import Objective, objective_loop_enabled
        objective = Objective(
            goal="produce two steps",
            definition_of_done=lambda state: int(state.get("steps", 0)) >= 2,
        )
        not_done = objective.is_satisfied({"steps": 1, "final_answer": None})
        done = objective.is_satisfied({"steps": 2, "final_answer": "ok"})
        from pathlib import Path as _P
        source = (_P(__file__).resolve().parents[2] / "core" / "generic_agent.py").read_text()
        wired = "is_satisfied(" in source and "objective_loop_enabled" in source
        ctx.record("GOAL-01", "verified" if objective_loop_enabled() and not not_done
                   and done and wired else "partial",
                   [ctx.save("goals/objective.json", {
                       "enabled": objective_loop_enabled(),
                       "not_done": not_done, "done": done,
                       "loop_wired": wired})],
                   notes=f"predicate false->true, loop wired={wired}")
    except Exception as exc:
        ctx.record("GOAL-01", "unverified", notes=f"objective predicate failed: {exc}")

    # GOAL-03: maturity-gated custom action surface.
    try:
        from core.generic_agent import GenericAgent
        from core.models import AgentRegistry
        agent_id = make_agent(ctx, f"objective-{uuid.uuid4().hex[:6]}",
                              tier="intern", capabilities=["*"])
        db = ctx.db()
        try:
            row = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
            agent = GenericAgent(row, workspace_id=ctx.workspace_id)
        finally:
            db.close()

        async def handler(args, context):
            return {"ok": True}

        agent.register_action("acceptance_custom", handler,
                              description="acceptance", min_maturity="INTERN")
        agent._run_maturity = "STUDENT"
        student_visible = agent._custom_action_visible("acceptance_custom")
        agent._run_maturity = "INTERN"
        intern_visible = agent._custom_action_visible("acceptance_custom")
        ctx.record("GOAL-03", "verified" if (not student_visible and intern_visible)
                   else "failed",
                   [ctx.save("goals/custom_action.json", {
                       "student_visible": student_visible,
                       "intern_visible": intern_visible})],
                   notes=f"student={student_visible} intern={intern_visible}")
    except Exception as exc:
        ctx.record("GOAL-03", "unverified", notes=f"custom action surface failed: {exc}")

    # GOAL-02 / GOAL-04 run inside the ReAct loop and need a model.
    for cid, note in (("GOAL-02", "utility target scoring"),
                      ("GOAL-04", "stuck detection")):
        ctx.record(cid, "unverified",
                   notes=f"{note} executes inside the model-backed ReAct loop; "
                         f"no cloud key is used in this world")
