"""Agent Radio (lateral agent messaging) scenarios."""
from __future__ import annotations

import asyncio
import json
import uuid

from .common import Ctx, make_agent


def radio(ctx: Ctx) -> None:
    from core.agent_radio import radio_actions as ra
    from core.agent_radio import radio_config

    a1 = make_agent(ctx, f"radio-a-{uuid.uuid4().hex[:6]}", tier="intern")
    a2 = make_agent(ctx, f"radio-b-{uuid.uuid4().hex[:6]}", tier="intern")
    a3 = make_agent(ctx, f"radio-c-{uuid.uuid4().hex[:6]}", tier="intern")
    base = {
        "tenant_id": ctx.tenant_id,
        "workspace_id": ctx.workspace_id,
        "tier": "intern",
    }
    c1 = {**base, "agent_id": a1}
    c2 = {**base, "agent_id": a2}
    c3 = {**base, "agent_id": a3}

    create = asyncio.run(ra.radio_create_thread({
        "name": f"acceptance-radio-{uuid.uuid4().hex[:6]}",
        "member_agent_ids": [a2, a3],
        "scope_hint": "manual",
    }, c1))
    thread_id = create.get("thread_id")
    ctx.record("RADIO-01", "verified" if create.get("success") and thread_id else "failed",
               [ctx.save("radio/create.json", {
                   "enabled": radio_config.radio_enabled(), "create": create})],
               notes=f"thread={thread_id}")

    send = asyncio.run(ra.radio_send_message({
        "thread_id": thread_id,
        "content": "RADIO-TOKEN-4412 please confirm the ledger total.",
        "mention_agent_ids": [a2],
    }, c1)) if thread_id else {}
    inbox = asyncio.run(ra.radio_read_inbox({"thread_id": thread_id}, c2)) if thread_id else {}
    inbox_text = json.dumps(inbox)
    mention_ok = ("RADIO-TOKEN-4412" in inbox_text and a1 in inbox_text)
    ctx.record("RADIO-02", "verified" if send.get("success") and mention_ok else "failed",
               [ctx.save("radio/send.json", {"send": send, "inbox": inbox})],
               notes=f"sent={send.get('success')} mention_delivered={mention_ok}")

    # Budget accounting: set the thread's used budget above the ceiling.
    budget_blocked = None
    if thread_id:
        from core.models import AgentThread
        db = ctx.db()
        try:
            row = db.query(AgentThread).filter(AgentThread.id == thread_id).first()
            if row is not None:
                meta = dict(row.metadata_json or {})
                meta["used_budget_usd"] = radio_config.team_budget_usd() + 1.0
                row.metadata_json = meta
                db.commit()
        finally:
            db.close()
        budget_blocked = asyncio.run(ra.radio_send_message({
            "thread_id": thread_id,
            "content": "this send should be refused by the budget",
            "mention_agent_ids": [a2],
        }, c1))
    ctx.record("RADIO-03", "verified" if (budget_blocked or {}).get("error") == "budget_exceeded"
               else "failed",
               [ctx.save("radio/budget.json", {
                   "ceiling_usd": radio_config.team_budget_usd(),
                   "send": budget_blocked})],
               notes=f"error={(budget_blocked or {}).get('error')}")

    # Wait semantics: an untouched member times out; a delivered mention wakes it.
    first_wait = asyncio.run(ra.radio_wait_for_mention({
        "thread_id": thread_id, "timeout": 1}, c3)) if thread_id else {}
    # Reset the budget so the next send is allowed.
    if thread_id:
        from core.models import AgentThread as AT
        db = ctx.db()
        try:
            row = db.query(AT).filter(AT.id == thread_id).first()
            if row is not None:
                meta = dict(row.metadata_json or {})
                meta.pop("used_budget_usd", None)
                row.metadata_json = meta
                db.commit()
        finally:
            db.close()
    asyncio.run(ra.radio_send_message({
        "thread_id": thread_id,
        "content": "second mention for the wait test",
        "mention_agent_ids": [a3],
    }, c1)) if thread_id else {}
    second_wait = asyncio.run(ra.radio_wait_for_mention({
        "thread_id": thread_id, "timeout": 3}, c3)) if thread_id else {}
    ok = (first_wait.get("timed_out") is True
          and second_wait.get("success") is True
          and second_wait.get("timed_out") is False)
    ctx.record("RADIO-04", "verified" if ok else "partial",
               [ctx.save("radio/wait.json", {
                   "first": first_wait, "second": second_wait})],
               notes=f"first_timeout={first_wait.get('timed_out')} "
                     f"second_delivered={not second_wait.get('timed_out')}")
