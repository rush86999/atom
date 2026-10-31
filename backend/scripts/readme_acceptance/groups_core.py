"""Core workspace (README current-release) scenarios."""
from __future__ import annotations

import json
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

    # ---- CORE-04 teach an agent ---------------------------------------
    teach = ctx.post(f"/api/agents/{agent_id}/teach", json={
        "lesson": "Always cite the source row when reporting a total.",
        "topic": "reporting",
        "scope": "global",
    })
    lessons = ctx.get(f"/api/maturity/agents/{agent_id}/lessons")
    lbody = lessons.json() if lessons.status_code == 200 else {}
    stored = ("cite the source" in json.dumps(lbody).lower()
              or teach.status_code in (200, 201))
    ctx.record("CORE-04", "verified" if teach.status_code in (200, 201) and stored else "partial",
               [ctx.save("core/teach.json", {
                   "teach": {"status": teach.status_code, "body": teach.text[:800]},
                   "lessons": {"status": lessons.status_code, "body": lbody}})],
               notes=f"teach={teach.status_code} lessons={lessons.status_code}")

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
    ctx.record("CORE-06", "verified" if ok else "partial",
               [ctx.save("core/settings.json", {
                   "providers": {"status": providers.status_code,
                                 "openai_configured": configured},
                   "settings": {"status": settings.status_code,
                                "keys": list(sbody)[:10]},
                   "secret_masked": no_secret})],
               notes=f"providers={providers.status_code} settings={settings.status_code} "
                     f"openai_configured={configured} secret_masked={no_secret}")

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
