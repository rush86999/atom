"""Core workspace (README current-release) scenarios."""
from __future__ import annotations

import json
import os
import uuid

from .common import Ctx, make_agent


def core_workspace(ctx: Ctx) -> None:
    # ---- CORE-01 chat turn --------------------------------------------
    agent_id = make_agent(ctx, f"chat-agent-{uuid.uuid4().hex[:6]}",
                          tier="autonomous", capabilities=["*"])
    chat = ctx.post("/api/chat/message", json={
        "message": "Reply with the single word acceptance.",
        "user_id": ctx.admin_id,
        "agent_id": agent_id,
    }, timeout=180)
    cbody = chat.json() if chat.headers.get("content-type", "").startswith("application/json") else {}
    session_id = cbody.get("session_id")
    history = ctx.get(f"/api/chat/history/{session_id}") if session_id else None
    hbody = history.json() if history is not None and history.status_code == 200 else {}
    reply = cbody.get("message") or ""
    ok = (chat.status_code == 200 and cbody.get("success") is True
          and reply and session_id and history is not None and history.status_code == 200)
    ctx.record("CORE-01", "verified" if ok else "partial",
               [ctx.save("core/chat.json", {
                   "status": chat.status_code,
                   "body": cbody if cbody else chat.text[:1200],
                   "history_status": None if history is None else history.status_code,
                   "history": str(hbody)[:1000]})],
               notes=f"chat={chat.status_code} session={session_id} "
                     f"reply={(reply or '')[:80]!r} provider={cbody.get('provider')} "
                     f"model={cbody.get('model')}")

    # ROUTE-06: the chat turn ran through the local OpenAI-compatible server.
    provider = str(cbody.get("provider") or "").lower()
    if ok and provider in ("ollama", "local", "lmstudio", "vllm"):
        ctx.record("ROUTE-06", "verified",
                   [ctx.save("routing/local_served.json", {
                       "provider": cbody.get("provider"),
                       "model": cbody.get("model"),
                       "upstream": "bounded local OpenAI-compatible server"})],
                   notes=f"served by {cbody.get('provider')}/{cbody.get('model')}")

    # MEM-04: persist an episode from the completed execution, then read it
    # back through the episode retrieval API.
    try:
        raw_messages = hbody.get("messages") if isinstance(hbody, dict) else hbody
        messages = raw_messages if isinstance(raw_messages, list) else []
        execution_id = next((m.get("execution_id") for m in messages
                             if isinstance(m, dict) and m.get("execution_id")), None)
        episode_id = None
        if execution_id:
            import asyncio
            from core.episode_service import EpisodeService
            db = ctx.db()
            try:
                episode = asyncio.run(EpisodeService(db).create_episode_from_execution(
                    execution_id=execution_id,
                    task_description="acceptance chat turn",
                    outcome="success", success=True,
                    metadata={"acceptance": True},
                ))
                episode_id = getattr(episode, "id", None)
            finally:
                db.close()
        episodes = ctx.get(f"/api/episodes/{agent_id}/list")
        ebody = episodes.json() if episodes.status_code == 200 else {}
        if isinstance(ebody, list):
            items = ebody
        else:
            data = ebody.get("data")
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("episodes") or ebody.get("episodes") or []
            else:
                items = ebody.get("episodes") or []
        ctx.record("MEM-04", "verified" if episode_id and episodes.status_code == 200
                   and items else "partial",
                   [ctx.save("core/episodes.json", {
                       "execution_id": execution_id, "episode_id": episode_id,
                       "status": episodes.status_code,
                       "count": len(items) if isinstance(items, list) else None,
                       "body": str(ebody)[:1000]})],
                   notes=f"episode={episode_id} episodes={len(items) if isinstance(items, list) else 'n/a'}")
    except Exception as exc:
        import traceback as _tb
        tb = _tb.format_exc()
        ctx.save("core/episode_error.txt", tb)
        ctx.record("MEM-04", "partial",
                   notes=f"episode read failed: {type(exc).__name__}: {exc} [{tb.strip().splitlines()[-2] if tb.strip() else ''}]")

    # ---- CORE-03 canvas review/edit -----------------------------------
    canvas_create = ctx.post("/api/canvas", json={
        "title": f"acceptance-canvas-{uuid.uuid4().hex[:6]}",
        "canvas_type": "document",
    })
    cc = canvas_create.json() if canvas_create.status_code in (200, 201) else {}
    canvas_id = cc.get("id") or cc.get("canvas_id") or (cc.get("data") or {}).get("id")
    update = ctx.put(f"/api/canvas/{canvas_id}",
                     json={"text": "Corrected acceptance content"}) if canvas_id else None
    read = ctx.get(f"/api/canvas/{canvas_id}") if canvas_id else None
    rbody = read.json() if read is not None and read.status_code == 200 else {}
    ok = (canvas_create.status_code in (200, 201) and canvas_id
          and update is not None and update.status_code in (200, 201)
          and "Corrected acceptance content" in json.dumps(rbody))
    ctx.record("CORE-03", "verified" if ok else "partial",
               [ctx.save("core/canvas.json", {
                   "create": {"status": canvas_create.status_code,
                              "body": cc if cc else canvas_create.text[:600]},
                   "update": None if update is None else update.status_code,
                   "read": {"status": None if read is None else read.status_code,
                            "body": rbody}})],
               notes=f"canvas={canvas_id} update={None if update is None else update.status_code}")

    # ---- CORE-04 teach a rule, then observe it applied later -----------
    # The lesson must reach a LATER turn and change its observable answer.
    # A scripted reasoning step is the controlled model: it emits the
    # required citation only when the taught lesson is present in the memory
    # context. This proves the injection/application path, not model quality.
    import asyncio
    from core.generic_agent import GenericAgent
    from core.models import AgentRegistry
    from core.react_models import ReActStep

    lesson_text = "When reporting a total, always include SOURCE_ROW: 42."
    teach = ctx.post(f"/api/agents/{agent_id}/teach", json={
        "lesson": lesson_text,
        "topic": "reporting",
        "scope": "global",
    })
    lessons = ctx.get(f"/api/maturity/agents/{agent_id}/lessons")
    lbody = lessons.json() if lessons.status_code == 200 else {}
    lesson_rows = lbody.get("lessons") if isinstance(lbody, dict) else []
    lesson_id = next((row.get("id") for row in (lesson_rows or [])
                      if "source_row: 42" in json.dumps(row).lower()), None)

    def _run_rule_case(target_agent_id, goal_id=None, marker="SOURCE_ROW: 42",
                       workspace_id=None):
        db = ctx.db()
        try:
            row = (db.query(AgentRegistry)
                   .filter(AgentRegistry.id == target_agent_id).first())
            agent = GenericAgent(
                row, workspace_id=workspace_id or ctx.workspace_id)
        finally:
            db.close()
        seen = {"lessons": []}

        async def fake_react_step(task_input, memory, history, context=None,
                                  utility_delta=None):
            seen["lessons"] = (memory or {}).get("lessons") or []
            has_rule = marker.lower() in json.dumps(seen["lessons"]).lower()
            answer = ("TOTAL=100; " + marker) if has_rule else "TOTAL=100"
            return ReActStep(thought="apply the taught rule",
                             final_answer=answer)

        agent._react_step = fake_react_step
        result = asyncio.run(agent.execute(
            "report the total",
            context={"goal_id": goal_id} if goal_id else {},
        ))
        return result, seen["lessons"]

    applied, applied_lessons = _run_rule_case(agent_id)
    control_agent = make_agent(ctx, f"lesson-control-{uuid.uuid4().hex[:6]}",
                               tier="autonomous", capabilities=["*"])
    # A different workspace has no sibling lessons; same-workspace peers are
    # intentionally visible to each other by product design.
    control_ws = f"lesson-control-ws-{uuid.uuid4().hex[:6]}"
    db = ctx.db()
    try:
        row = (db.query(AgentRegistry)
               .filter(AgentRegistry.id == control_agent).first())
        row.workspace_id = control_ws
        db.commit()
    finally:
        db.close()
    control_result, control_lessons = _run_rule_case(
        control_agent, workspace_id=control_ws)

    # Wrong-context control: a goal-scoped lesson must not ride another goal.
    goal_create = ctx.post("/api/goals", json={
        "title": f"lesson-scope-{uuid.uuid4().hex[:6]}",
        "description": "lesson scope acceptance",
    })
    goal_body = goal_create.json() if goal_create.status_code == 200 else {}
    scope_goal = ((goal_body.get("goal") or {}).get("id")
                  or goal_body.get("goal_id") or goal_body.get("id"))
    scoped_agent = make_agent(ctx, f"lesson-scoped-{uuid.uuid4().hex[:6]}",
                              tier="autonomous", capabilities=["*"])
    scoped_teach = ctx.post(f"/api/agents/{scoped_agent}/teach", json={
        "lesson": "For this goal only, include SOURCE_ROW: 77.",
        "topic": "goal reporting",
        "scope": "goal",
        "goal_id": scope_goal,
    })
    same_goal, same_lessons = _run_rule_case(
        scoped_agent, goal_id=scope_goal, marker="SOURCE_ROW: 77")
    wrong_goal, wrong_lessons = _run_rule_case(
        scoped_agent, goal_id="different-goal", marker="SOURCE_ROW: 77")

    # Corrected-lesson control: rewrite the standing lesson and require the
    # later turn to use the corrected value, not the old one.
    corrected = None
    corrected_result = None
    if lesson_id:
        corrected = ctx.patch(
            f"/api/maturity/agents/{agent_id}/teaching-points/{lesson_id}",
            json={"text": "When reporting a total, always include SOURCE_ROW: 99."})
        corrected_result, corrected_lessons = _run_rule_case(
            agent_id, marker="SOURCE_ROW: 99")

    applied_text = json.dumps(applied.get("output") or "")
    control_text = json.dumps(control_result.get("output") or "")
    same_text = json.dumps(same_goal.get("output") or "")
    wrong_text = json.dumps(wrong_goal.get("output") or "")
    corrected_text = json.dumps((corrected_result or {}).get("output") or "")
    ok = (teach.status_code in (200, 201) and lesson_id
          and "SOURCE_ROW: 42" in applied_text
          and "SOURCE_ROW: 42" not in control_text
          and applied_lessons and not control_lessons
          and scoped_teach.status_code in (200, 201)
          and "SOURCE_ROW: 77" in same_text
          and "SOURCE_ROW: 77" not in wrong_text
          and same_lessons
          and "SOURCE_ROW: 77" not in json.dumps(wrong_lessons).lower()
          and corrected is not None and corrected.status_code == 200
          and "SOURCE_ROW: 99" in corrected_text
          and "SOURCE_ROW: 42" not in corrected_text)
    ctx.record("CORE-04", "verified" if ok else "failed",
               [ctx.save("core/teach_apply.json", {
                   "teach": {"status": teach.status_code, "body": teach.text[:800]},
                   "lesson_id": lesson_id,
                   "applied": {"output": applied.get("output"),
                               "lessons": applied_lessons},
                   "control": {"agent": control_agent,
                               "output": control_result.get("output"),
                               "lessons": control_lessons},
                   "scoped_goal": scope_goal,
                   "same_goal": {"output": same_goal.get("output"),
                                 "lessons": same_lessons},
                   "wrong_goal": {"output": wrong_goal.get("output"),
                                  "lessons": wrong_lessons},
                   "corrected": None if corrected is None else {
                       "status": corrected.status_code,
                       "body": corrected.text[:800]},
                   "corrected_output": (corrected_result or {}).get("output"),
               })],
               notes=f"teach={teach.status_code} lesson={lesson_id} "
                     f"applied={'SOURCE_ROW: 42' in applied_text} "
                     f"control={'SOURCE_ROW: 42' in control_text} "
                     f"same_goal={'SOURCE_ROW: 77' in same_text} "
                     f"wrong_goal={'SOURCE_ROW: 77' in wrong_text} "
                     f"corrected={'SOURCE_ROW: 99' in corrected_text}")

    # ---- CORE-06 settings / provider ----------------------------------
    providers = ctx.get("/api/ai/providers")
    pbody = providers.json() if providers.status_code == 200 else {}
    settings = ctx.get("/api/v1/admin/settings")
    sbody = settings.json() if settings.status_code == 200 else {}
    openai_rows = [p for p in ((pbody.get("data") or {}).get("providers") or [])
                   if ((p.get("provider") or {}).get("id") == "openai")]
    configured = bool(openai_rows)
    no_secret = "sk-acceptance-test-key" not in json.dumps(pbody)
    ok = providers.status_code == 200 and settings.status_code == 200 and configured and no_secret

    # Cached BYOK refresh through the normal Settings -> Chat surface:
    # remove the env fallback, verify chat refuses with no stored key, save a
    # key, chat without restart, replace the key, and delete it again.
    from . import mock_llm_server
    refresh = {"error": None}
    old_env_key = os.environ.pop("OPENAI_API_KEY", None)
    try:
        mock_llm_server.reset()
        deleted = ctx.delete("/api/ai/providers/openai/keys/default")
        chat_after_delete = ctx.post("/api/chat/message", json={
            "message": "reply after key delete",
            "user_id": ctx.admin_id,
            "agent_id": agent_id,
        }, timeout=180)
        delete_body = (chat_after_delete.json()
                       if chat_after_delete.headers.get("content-type", "")
                       .startswith("application/json") else {})
        store1 = ctx.post("/api/ai/providers/openai/keys", json={
            "api_key": "sk-acceptance-refresh-0001",
            "key_name": "default", "environment": "production",
            "label": "CORE-06 refresh acceptance"})
        chat1 = ctx.post("/api/chat/message", json={
            "message": "reply after key save",
            "user_id": ctx.admin_id,
            "agent_id": agent_id,
        }, timeout=180)
        chat1_body = (chat1.json() if chat1.headers.get("content-type", "")
                      .startswith("application/json") else {})
        calls1 = mock_llm_server.calls()
        auth1 = [c.get("authorization") for c in calls1
                 if "sk-acceptance-refresh-0001" in str(c.get("authorization") or "")]
        store2 = ctx.post("/api/ai/providers/openai/keys", json={
            "api_key": "sk-acceptance-refresh-0002",
            "key_name": "default", "environment": "production",
            "label": "CORE-06 refresh acceptance v2"})
        chat2 = ctx.post("/api/chat/message", json={
            "message": "reply after key replace",
            "user_id": ctx.admin_id,
            "agent_id": agent_id,
        }, timeout=180)
        chat2_body = (chat2.json() if chat2.headers.get("content-type", "")
                      .startswith("application/json") else {})
        calls2 = mock_llm_server.calls()
        auth2 = [c.get("authorization") for c in calls2
                 if "sk-acceptance-refresh-0002" in str(c.get("authorization") or "")]
        deleted2 = ctx.delete("/api/ai/providers/openai/keys/default")
        chat3 = ctx.post("/api/chat/message", json={
            "message": "reply after key deletion",
            "user_id": ctx.admin_id,
            "agent_id": agent_id,
        }, timeout=180)
        chat3_body = (chat3.json() if chat3.headers.get("content-type", "")
                      .startswith("application/json") else {})
        refresh_ok = (
            deleted.status_code in (200, 204, 404)
            and chat_after_delete.status_code in (200, 503)
            and delete_body.get("success") is not True
            and store1.status_code in (200, 201)
            and chat1.status_code == 200 and chat1_body.get("success") is True
            and auth1
            and store2.status_code in (200, 201)
            and chat2.status_code == 200 and chat2_body.get("success") is True
            and auth2
            and deleted2.status_code in (200, 204)
            and (chat3.status_code != 200
                 or chat3_body.get("success") is not True)
        )
        refresh = {
            "delete_status": deleted.status_code,
            "chat_after_delete": {"status": chat_after_delete.status_code,
                                  "body": delete_body},
            "store1": store1.status_code,
            "chat1": {"status": chat1.status_code,
                      "success": chat1_body.get("success"),
                      "auth_seen": auth1},
            "store2": store2.status_code,
            "chat2": {"status": chat2.status_code,
                      "success": chat2_body.get("success"),
                      "auth_seen": auth2},
            "delete2_status": deleted2.status_code,
            "chat_after_delete2": {"status": chat3.status_code,
                                   "body": chat3_body},
            "ok": refresh_ok,
        }
        ok = ok and refresh_ok
    except Exception as exc:
        refresh["error"] = f"{type(exc).__name__}: {exc}"
        ok = False
    finally:
        if old_env_key is not None:
            os.environ["OPENAI_API_KEY"] = old_env_key
    ctx.record("CORE-06", "verified" if ok else "partial",
               [ctx.save("core/settings.json", {
                   "providers": {"status": providers.status_code,
                                 "openai_configured": configured},
                   "settings": {"status": settings.status_code,
                                "keys": list(sbody)[:10]},
                   "secret_masked": no_secret,
                   "cached_refresh": refresh})],
               notes=f"providers={providers.status_code} settings={settings.status_code} "
                     f"openai_configured={configured} secret_masked={no_secret} "
                     f"refresh={refresh.get('ok')} error={refresh.get('error')}")

    # ---- CORE-07 product profile --------------------------------------
    profile = ctx.get("/api/product/profile")
    pr = profile.json() if profile.status_code == 200 else {}
    caps = pr.get("capabilities") or {}
    exposed = sorted(k for k, v in caps.items() if v.get("enabled"))
    profile_name = pr.get("profile")
    core_required = {"chat", "documents", "canvas", "agents", "activity", "settings"}
    deferred = {"search", "tasks", "automations", "marketplace", "governance"}
    if profile_name == "core":
        ok = (profile.status_code == 200
              and core_required <= set(exposed)
              and not (deferred & set(exposed)))
    else:
        ok = (profile.status_code == 200 and profile_name == "full"
              and len(exposed) >= 10)
    ctx.record("CORE-07", "verified" if ok else "partial",
               [ctx.save("core/profile.json", pr)],
               notes=f"profile={profile_name} enabled={exposed} "
                     f"deferred_enabled={sorted(deferred & set(exposed))}")
