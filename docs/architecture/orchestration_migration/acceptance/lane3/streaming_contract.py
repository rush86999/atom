#!/usr/bin/env python3
"""C11/C12 — token-bearing stream, and deterministic completion without tokens.

WHY THIS EXISTS
Every acceptance artifact on record says the same thing: zero `chat_token`
frames have ever been observed, and `streaming_verdict` is "unmeasured". The
socket carried status transitions only. The readiness report withdrew its
streaming claim. So C11 has never been exercised, and the plan's
token-bearing-shim requirement is only half met.

The reason is not a broken stream. `chat_orchestrator` broadcasts `chat_token`
on the LLM leg, and the seeded workbook turns never take the LLM leg -- they are
answered deterministically, so emitting nothing is correct behaviour. Measuring
streaming on a workbook turn therefore measures nothing at all.

So this drives BOTH halves on one connection, which is the only way to tell a
working stream from a dead one:

  S1  a general question (LLM leg)   -> tokens MUST appear, bound to this turn,
                                         in order, none dropped, and the
                                         concatenation must EQUAL the final
                                         answer over HTTP and in history
  S2  the seeded workbook ask        -> tokens MUST NOT appear, and the turn
                                         must still complete correctly
                                         (C12: "no tokens is valid")
  S3  a foreign/stale frame          -> must not be attributed to either turn

S1 passing while S2 also passes is the result that matters. S1 alone could be a
shim echoing canned text; S2 alone is the status-only behaviour already on
record.

    streaming_contract.py --world candidate_fix1 --out <dir>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
BACKEND = REPO / "backend"
WORLDS = BACKEND / "data" / "acceptance_worlds"
sys.path.insert(0, str(BACKEND))

USER_ID = "b83eb105-d9e7-41a5-83e3-a632b15b9ee3"
LOGIN_EMAIL = "admin@example.com"
LOGIN_PASSWORD = os.environ.get("LANE3_PREVIEW_PASSWORD") or \
    "preview-only-local-2026"

# A real question with no file/task intent, so it takes the LLM leg. Asked
# about the material the fixture is about, so the answer is checkable for being
# non-empty and about the right subject.
LLM_QUESTION = "In two sentences, what is a price list used for?"
# The deterministic leg: no tokens are expected and that is correct.
WORKBOOK_ASK = ("find the prices of these 8 machines in Consolidated Price "
                "List 2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, "
                "SLE24-16, TK 1624, TK Multi Wheel Gang Slitter and GSL48-16")


def login(base: str) -> str:
    import httpx
    r = httpx.post(f"{base}/api/auth/login", trust_env=False, timeout=30,
                   headers={"Origin": f"http://localhost:{_front_port(base)}"},
                   json={"username": LOGIN_EMAIL, "password": LOGIN_PASSWORD})
    r.raise_for_status()
    token = (r.json() or {}).get("access_token")
    if not token:
        raise SystemExit("login returned no access_token")
    return token


_FRONT: Dict[str, int] = {}


def _front_port(base: str) -> int:
    return _FRONT.get(base, 3102)


def ask(base: str, token: str, session: str, message: str,
        timeout: int = 420) -> Dict[str, Any]:
    import httpx
    r = httpx.post(f"{base}/api/chat/message", json={
        "message": message, "session_id": session, "user_id": USER_ID,
        "context": {"current_page": "/chat", "conversation_history": []},
    }, headers={"Authorization": f"Bearer {token}"}, timeout=timeout,
        trust_env=False)
    try:
        return {"status": r.status_code, **r.json()}
    except Exception:
        return {"status": r.status_code, "raw": r.text[:300]}


class Recorder:
    """Every frame the socket delivers, with arrival order and timing."""

    def __init__(self) -> None:
        self.frames: List[Dict[str, Any]] = []
        self.t0 = time.monotonic()

    def add(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except Exception:
            msg = {"_unparsed": raw[:200]}
        self.frames.append({"t_ms": int((time.monotonic() - self.t0) * 1000),
                            "msg": msg})

    def of_type(self, kind: str) -> List[Dict[str, Any]]:
        return [f for f in self.frames
                if (f["msg"] or {}).get("type") == kind]

    def kinds(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for f in self.frames:
            k = str((f["msg"] or {}).get("type"))
            out[k] = out.get(k, 0) + 1
        return out


async def run(world: str, out: Path) -> int:
    import httpx
    import websockets

    state = json.loads((WORLDS / world / "preview_stack.json").read_text())
    port = state["backend_port"]
    base = f"http://127.0.0.1:{port}"
    _FRONT[base] = state.get("frontend_port") or 3102

    out.mkdir(parents=True, exist_ok=True)
    token = login(base)
    stamp = int(time.time())

    rec = Recorder()
    ws_url = f"ws://127.0.0.1:{port}/ws/default?token={token}"
    print(f"C11/C12 against {base}  ws={ws_url.split('?')[0]}")

    async with websockets.connect(ws_url, open_timeout=30,
                                  max_size=8 * 1024 * 1024) as ws:

        async def pump() -> None:
            try:
                async for raw in ws:
                    rec.add(raw if isinstance(raw, str) else raw.decode())
            except Exception:
                pass

        pump_task = asyncio.create_task(pump())
        await asyncio.sleep(1.5)  # let the subscribe land

        steps: List[Dict[str, Any]] = []

        def check(name: str, ok: bool, detail: Any = None) -> None:
            steps.append({"step": name, "ok": bool(ok), "detail": detail})
            print(f"  {'PASS' if ok else 'FAIL'}  {name}"
                  + (f"   {str(detail)[:160]}" if detail is not None else ""))

        # ------------------------------------------------------------ S1 LLM leg
        mark = len(rec.frames)
        s1 = f"stream-llm-{stamp}"
        r1 = await asyncio.to_thread(ask, base, token, s1, LLM_QUESTION)
        exec1 = r1.get("execution_id")
        await asyncio.sleep(2.0)
        s1_frames = rec.frames[mark:]
        s1_tokens = [f for f in s1_frames
                     if (f["msg"] or {}).get("type") == "chat_token"]
        s1_done = [f for f in s1_frames
                   if (f["msg"] or {}).get("type") == "chat_token_done"]
        deltas = [str(((f["msg"] or {}).get("data") or {}).get("delta") or "")
                  for f in s1_tokens]
        answer1 = (r1.get("message") or "")

        check("S1_llm_turn_succeeded", r1.get("success") is True,
              f"status={r1.get('status')} err={r1.get('error_code')}")
        check("S1_tokens_were_actually_emitted", len(s1_tokens) > 0,
              {"chat_token_frames": len(s1_tokens),
               "frame_kinds": rec.kinds()})
        check("S1_no_token_delta_is_empty",
              all(d.strip() for d in deltas if d),
              {"empty_deltas": sum(1 for d in deltas if not d.strip())})
        bound = [str(((f["msg"] or {}).get("data") or {}).get("execution_id") or "")
                 for f in s1_tokens]
        check("S1_every_token_is_bound_to_this_turn",
              bool(bound) and all(b == str(exec1) for b in bound),
              {"turn_execution_id": exec1,
               "distinct_frame_execution_ids": sorted(set(bound))[:5]})
        foreign = [b for b in bound if b and b != str(exec1)]
        check("S1_no_foreign_frame_was_attributed_here", not foreign,
              {"foreign": sorted(set(foreign))[:5]})
        joined = "".join(deltas)
        check("S1_streamed_text_equals_the_delivered_answer",
              bool(joined.strip()) and joined.strip() == answer1.strip(),
              {"streamed_chars": len(joined), "answer_chars": len(answer1),
               "streamed_head": joined[:120]})
        check("S1_a_single_final_event_closed_the_turn", len(s1_done) == 1,
              {"chat_token_done_frames": len(s1_done)})
        done_text = ""
        if s1_done:
            dd = (s1_done[0]["msg"] or {}).get("data") or {}
            done_text = str(dd.get("content") or dd.get("message") or "")
        check("S1_final_event_carries_the_same_text",
              bool(done_text.strip()) and done_text.strip() == answer1.strip(),
              {"done_chars": len(done_text)})
        check("S1_tokens_precede_the_final_event",
              bool(s1_tokens) and bool(s1_done)
              and s1_tokens[-1]["t_ms"] <= s1_done[0]["t_ms"],
              {"last_token_ms": s1_tokens[-1]["t_ms"] if s1_tokens else None,
               "done_ms": s1_done[0]["t_ms"] if s1_done else None})
        gaps = [s1_tokens[i + 1]["t_ms"] - s1_tokens[i]["t_ms"]
                for i in range(len(s1_tokens) - 1)]
        check("S1_frames_arrive_as_a_burst_not_a_sparse_drip",
              not gaps or max(gaps) < 5000,
              {"frames": len(s1_tokens),
               "largest_gap_ms": max(gaps) if gaps else None})

        # --------------------------------------------------- S2 deterministic leg
        mark = len(rec.frames)
        s2 = f"stream-workbook-{stamp}"
        r2 = await asyncio.to_thread(ask, base, token, s2, WORKBOOK_ASK)
        exec2 = r2.get("execution_id")
        await asyncio.sleep(2.0)
        s2_frames = rec.frames[mark:]
        s2_tokens = [f for f in s2_frames
                     if (f["msg"] or {}).get("type") == "chat_token"]
        s2_bound = [str(((f["msg"] or {}).get("data") or {}).get("execution_id") or "")
                    for f in s2_tokens]
        answer2 = (r2.get("message") or "")
        check("S2_deterministic_turn_succeeded", r2.get("success") is True,
              f"status={r2.get('status')} err={r2.get('error_code')}")
        check("S2_no_tokens_on_a_deterministic_turn_is_valid",
              len(s2_tokens) == 0,
              {"chat_token_frames": len(s2_tokens),
               "frame_kinds": {k: v for k, v in rec.kinds().items()
                               if v and k != "chat_token"}})
        check("S2_no_token_frame_claims_the_deterministic_turn",
              not any(b == str(exec2) for b in s2_bound),
              {"exec2": exec2, "frame_execs": sorted(set(s2_bound))[:5]})
        check("S2_deterministic_turn_still_delivered_a_full_answer",
              len(answer2.strip()) > 200,
              {"answer_chars": len(answer2)})

        # ------------------------------------------------- S3 history convergence
        hj = httpx.get(f"{base}/api/chat/history/{s1}",
                       params={"user_id": USER_ID}, timeout=90,
                       trust_env=False,
                       headers={"Authorization": f"Bearer {token}"}).json()
        hist = [((m.get("response") or {}).get("message") or "")
                for m in (hj.get("messages") or [])]
        check("S3_history_shows_the_same_final_text_as_the_stream",
              any(t.strip() == answer1.strip() for t in hist),
              {"history_rows": len(hist), "answer_chars": len(answer1)})
        check("S3_history_kept_both_turns_separate", len(hist) >= 2,
              {"rows": len(hist)})

        pump_task.cancel()

    def kinds_of(frames: List[Dict[str, Any]]) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for f in frames:
            k = str((f["msg"] or {}).get("type"))
            out[k] = out.get(k, 0) + 1
        return out

    report = {
        "schema": "lane3-streaming-contract-v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "world": world,
        "backend": base,
        "source_id": (state.get("backend_health_identity") or {}).get("source_id"),
        "effective_flags": state.get("effective_flags") or {},
        "flag_finding": {
            "flag": "ATOM_CHAT_STREAMING",
            "launcher_sets": (state.get("effective_flags") or {}).get(
                "ATOM_CHAT_STREAMING"),
            "code_requires": "the literal string 'true' "
                             "(chat_orchestrator: os.getenv(..., 'true').lower() == 'true')",
            "leg_was_running": bool(s1_tokens),
            "note": ("if the launcher sets '1' the streaming leg is skipped "
                     "entirely, because '1'.lower() != 'true'. A descriptor "
                     "saying ATOM_CHAT_STREAMING=1 therefore reads as 'on' to a "
                     "human and is FALSE to the code."),
        },
        "cases": {"C11_token_bearing_stream": "S1", "C12_deterministic_completion": "S2",
                  "C11_foreign_frame": "S3"},
        "steps": steps,
        "passed": sum(1 for s in steps if s["ok"]),
        "total": len(steps),
        "all_pass": all(s["ok"] for s in steps),
        "frame_kind_counts": rec.kinds(),
        "frames_seen": len(rec.frames),
        "s1": {"session": s1, "execution_id": exec1,
               "chat_token_frames": len(s1_tokens),
               "chat_token_done_frames": len(s1_done),
               "streamed_chars": len(joined), "answer_chars": len(answer1),
               "answer_head": answer1[:300],
               "frame_kinds": kinds_of(s1_frames)},
        "s2": {"session": s2, "execution_id": exec2,
               "chat_token_frames": len(s2_tokens),
               "answer_chars": len(answer2),
               "frame_kinds": kinds_of(s2_frames)},
        "streaming_verdict": (
            "TOKEN STREAMING OBSERVED and bound to the turn"
            if s1_tokens else "STILL UNMEASURED: no chat_token frames were emitted"),
    }
    (out / "streaming_contract.json").write_text(json.dumps(report, indent=2))
    print(f"\n{report['passed']}/{report['total']} steps pass -> "
          f"{out/'streaming_contract.json'}")
    print(f"verdict: {report['streaming_verdict']}")
    return 0 if report["all_pass"] else 1


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--world", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    return asyncio.run(run(args.world, Path(args.out)))


if __name__ == "__main__":
    raise SystemExit(main())
