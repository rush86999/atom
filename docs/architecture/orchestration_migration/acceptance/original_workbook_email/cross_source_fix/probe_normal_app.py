# -*- coding: utf-8 -*-
"""Normal-app probe: cross-source routing on the LIVE dev stack (:8001).

Registers a disposable user through the public API (the dev DB's own
precedent: the seeded test-* users), then drives:

  turn 1  the verbatim eight-machine price ask  -> deterministic read
          (control: the fix must not break the read lane);
  turn 2  the cross-source follow-up with a DIFFERENT person and a
          DIFFERENT messaging surface (Priya / text message — proving the
          routing carries no incident-specific name or channel):
          must NOT be a deterministic price re-run.

Read-only with respect to existing data: creates only its own user rows
and its own chat session. Prints a compact verdict; writes the full
capture to --out.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid

import httpx

STORED_ASK = (
    "find the prices of these 8 machines in Consolidated Price List "
    "2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, SLE24-16, "
    "TK 1624, TK Multi Wheel Gang Slitter and GSL48-16")
EIGHT = [
    "No. 381", "U-22", "No. 622", "TK Manual Flanger", "SLE24-16",
    "TK 1624", "TK Multi Wheel Gang Slitter", "GSL48-16"]
# Same sentence shape as the incident; different person + channel.
CROSS_SOURCE_VARIANT = (
    "check Priya's text message and or description in workbook to find "
    "correct sheet and row from workbook for confirmation")


async def main() -> int:
    import asyncio

    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    ap.add_argument("--out", required=True)
    ap.add_argument("--token", default="",
                    help="reuse an existing JWT instead of registering")
    args = ap.parse_args()

    client = httpx.AsyncClient(trust_env=False, timeout=420)
    base = args.base
    stamp = uuid.uuid4().hex[:8]
    email = f"crosssrc-probe-{stamp}@example.com"
    password = f"probe-{stamp}-pass"

    token = args.token
    reg = None
    if not token:
        reg = (await client.post(f"{base}/api/auth/register", json={
            "username": email, "email": email, "password": password,
            "first_name": "Cross", "last_name": "Source"})).json()
        token = (reg.get("access_token")
                 or (reg.get("data") or {}).get("access_token"))
        if not token:
            # Some builds return the user without a token -> log in.
            login = (await client.post(f"{base}/api/auth/login", json={
                "username": email, "password": password})).json()
            token = (login.get("access_token")
                     or (login.get("data") or {}).get("access_token"))
        if not token:
            print(json.dumps({"register_failed": reg}, indent=1)[:600])
            return 2
    headers = {"Authorization": f"Bearer {token}"}
    me = (await client.get(f"{base}/api/auth/me", headers=headers)).json()
    user_id = str(me.get("id") or (me.get("data") or {}).get("id") or "")

    session = f"crosssrc-probe-{int(time.time())}"
    result = {"base": base, "user_email": email, "user_id": user_id,
              "session_id": session, "turns": []}

    async def send(msg: str):
        t0 = time.time()
        r = (await client.post(
            f"{base}/api/chat/message", headers=headers,
            json={"message": msg, "session_id": session,
                  "user_id": user_id,
                  "request_id": f"req-{uuid.uuid4().hex[:12]}"})).json()
        r["_latency_s"] = round(time.time() - t0, 2)
        return r

    r1 = await send(STORED_ASK)
    result["turns"].append({"n": 1, "response": r1})
    answer1 = str(r1.get("message") or "")
    found1 = [t for t in EIGHT if t.lower() in answer1.lower()]
    result["control_turn1"] = {
        "execution_id": r1.get("execution_id"),
        "model": r1.get("model"),
        "deterministic_delivery": (r1.get("data") or {}).get(
            "deterministic_delivery"),
        "items_found": found1,
        "eight_delivered": len(found1) >= 6,
    }

    r2 = await send(CROSS_SOURCE_VARIANT)
    result["turns"].append({"n": 2, "response": r2})
    answer2 = str(r2.get("message") or "")
    repeat = (
        "8880" in answer2 and "SLE24-16" in answer2
        and len([t for t in EIGHT if t.lower() in answer2.lower()]) >= 6)
    result["cross_source_turn2"] = {
        "execution_id": r2.get("execution_id"),
        "model": r2.get("model"),
        "provider": r2.get("provider"),
        "deterministic_delivery": (r2.get("data") or {}).get(
            "deterministic_delivery"),
        "answer_chars": len(answer2),
        "price_table_repeat": repeat,
        "routed_to_planning": (
            r2.get("model") != "deterministic"
            and not (r2.get("data") or {}).get("deterministic_delivery")
            and not repeat),
        "answer_text": answer2[:5000],
    }

    await client.aclose()
    with open(args.out, "w") as fh:
        json.dump(result, fh, indent=2, default=str)
    ok = (result["control_turn1"]["eight_delivered"]
          and result["cross_source_turn2"]["routed_to_planning"])
    print(json.dumps({
        "eight_delivered": result["control_turn1"]["eight_delivered"],
        "routed_to_planning":
            result["cross_source_turn2"]["routed_to_planning"],
        "turn2_model": result["cross_source_turn2"]["model"],
        "out": args.out}, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    import asyncio
    sys.exit(asyncio.run(main()))
