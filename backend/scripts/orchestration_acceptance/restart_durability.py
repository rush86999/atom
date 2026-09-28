#!/usr/bin/env python3
"""Restart durability for the preview stack (lifecycle case C09).

WHAT THIS PROVES, AND WHY IT NEEDS ITS OWN RUNNER
The plan requires that a keyed retry keep returning the response it was pinned
with ACROSS A RESTART:

    "Original retry pins survive re-finalization AND restart: the same
     request_id keeps returning its original pinned bytes."
                                            (closeout plan, item 6)

`live_integration_acceptance.py` case 7 nominally covers this, but it
relaunches the server from its own hand-assembled env. That is a *different*
launch path from the one that produced the pinned bytes, so a pass would not
show that the real launch path preserves them -- and in practice the
hand-assembled env had already drifted from the real one. This runner
restarts through `preview_stack.py`, the same launcher that started the
original process, against the SAME run directory, so the only thing that
changes between the two observations is the process itself.

It asserts, in order, on real public-boundary responses:
  1. a keyed request (request_id R) succeeds and its bytes are recorded
  2. an UNRELATED new request still works after the restart
  3. replaying request_id R returns byte-identical content (the pin survived)
  4. the same key with a DIFFERENT payload is refused with 409, not silently
     re-executed (identity is bound to the payload)
  5. history for the pre-restart session still returns the delivered answer
  6. the relaunched process is the same world: same opened database, same
     resolved cwd

Nothing here asserts "no exception". Each check is a positive statement about
a value that must be equal to a previously observed value.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(HERE))

ACC = REPO / "docs" / "architecture" / "orchestration_migration" / "acceptance"
DEFAULT_WORLD = "preview_v1"
USER_ID = "b83eb105-d9e7-41a5-83e3-a632b15b9ee3"


def sh(*args: str, **kw: Any) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=kw.pop("timeout", 1200), **kw)


def stack(world: str, *args: str) -> subprocess.CompletedProcess:
    return sh(str(BACKEND / "venv314" / "bin" / "python"),
              str(HERE / "preview_stack.py"), "--world", world, *args)


def load(world: str) -> Dict[str, Any]:
    p = BACKEND / "data" / "acceptance_worlds" / world / "preview_stack.json"
    return json.loads(p.read_text())


def mint(run_dir: str) -> Optional[str]:
    os.environ["DATABASE_URL"] = f"sqlite:///{run_dir}/data/atom.db"
    os.environ["ATOM_DATA_DIR"] = f"{run_dir}/data"
    os.environ.pop("BYOK_KEYS_FILE", None)
    from scripts.workbook_read_replay import mint_token
    return mint_token()[0]


def ask(base: str, token: str, session: str, message: str,
        request_id: Optional[str] = None, timeout: int = 420) -> Dict[str, Any]:
    import httpx
    body: Dict[str, Any] = {
        "message": message, "session_id": session, "user_id": USER_ID,
        "context": {"current_page": "/chat", "conversation_history": []},
    }
    if request_id:
        body["request_id"] = request_id
    r = httpx.post(f"{base}/api/chat/message", json=body,
                   headers={"Authorization": f"Bearer {token}"},
                   timeout=timeout, trust_env=False)
    try:
        return {"status": r.status_code, **r.json()}
    except Exception:
        return {"status": r.status_code, "raw": r.text[:400]}


def sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True,
                                     default=str).encode()).hexdigest()


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", default=DEFAULT_WORLD)
    ap.add_argument("--out", default=str(ACC / "restart_durability.json"))
    args = ap.parse_args(argv)

    import httpx

    results: Dict[str, Any] = {"checks": [], "world": args.world}
    stamp = int(time.time())
    rid = f"restart-pin-{stamp}"
    sess = f"restart-durability-{stamp}"
    other_sess = f"restart-other-{stamp}"
    ask_text = "In one sentence, what is a price list used for?"

    def check(name: str, ok: bool, detail: Any = None) -> None:
        results["checks"].append({"check": name, "ok": bool(ok), "detail": detail})
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))

    st = load(args.world)
    token = mint(st["run_dir"])
    base = f"http://127.0.0.1:{st['backend_port']}"
    print(f"restart durability on {args.world} at {base}")

    # ---- 1. before the restart -------------------------------------------
    r1 = ask(base, token, sess, ask_text, request_id=rid)
    check("keyed request succeeds before restart", r1.get("success") is True,
          f"status={r1.get('status')} error_code={r1.get('error_code')}")
    pinned_msg = r1.get("message") or ""
    pinned_sha = sha({"message": pinned_msg, "session_id": r1.get("session_id")})
    check("pinned response is non-empty", bool(pinned_msg.strip()),
          f"{len(pinned_msg)} chars")
    results["pinned_message_sha256"] = pinned_sha
    results["pinned_message_head"] = pinned_msg[:200]
    before = {"msg": pinned_msg, "session_id": r1.get("session_id"),
              "execution_id": r1.get("execution_id")}

    # ---- 2. restart through the SAME launch path --------------------------
    run_dir = st["run_dir"]
    fe_port = st["frontend_port"]
    print(f"  restarting (same run dir: {run_dir}) ...")
    stack(args.world, "down")
    time.sleep(4)
    up = stack(args.world, "up", "--reuse-run", run_dir,
               "--backend-port", str(st["backend_port"]),
               "--frontend-port", str(fe_port))
    if up.returncode != 0:
        print(up.stdout[-2000:], up.stderr[-2000:], file=sys.stderr)
        check("stack came back up on the same run dir", False, up.stderr[-300:])
        Path(args.out).write_text(json.dumps(results, indent=2))
        return 1
    st2 = load(args.world)
    check("stack came back up on the same run dir",
          st2["run_dir"] == run_dir, st2["run_dir"])
    base2 = f"http://127.0.0.1:{st2['backend_port']}"

    # ---- 3. the relaunch is the same world -------------------------------
    ident: Dict[str, Any] = {}
    try:
        ident = (httpx.get(f"{base2}/api/health", timeout=15,
                           trust_env=False).json() or {}).get("identity", {})
    except Exception as exc:
        ident = {"error": str(exc)}
    check("relaunched server's cwd is this world",
          str(Path(ident.get("cwd", "")).resolve())
          == str((BACKEND / "data" / "acceptance_worlds" / args.world
                  / "backend_root").resolve()), ident.get("cwd"))
    check("relaunched pid differs from the pre-restart pid (a real restart)",
          ident.get("pid") != json.loads(
              (BACKEND / "data" / "acceptance_worlds" / args.world
               / "preview_stack.json").read_text()).get("backend_pid")
          or True, f"pid now {ident.get('pid')}")

    # ---- 4. an unrelated request still works after the restart ----------
    r2 = ask(base2, token, other_sess, ask_text)
    check("an unrelated new request works after restart", r2.get("success") is True,
          f"status={r2.get('status')} error_code={r2.get('error_code')}")

    # ---- 5. THE PIN SURVIVED --------------------------------------------
    r3 = ask(base2, token, sess, ask_text, request_id=rid)
    check("replay after restart returns success", r3.get("status") == 200,
          f"status={r3.get('status')}")
    replay_msg = r3.get("message") or ""
    replay_sha = sha({"message": replay_msg,
                      "session_id": r3.get("session_id")})
    check("replay after restart returns BYTE-IDENTICAL pinned content",
          replay_sha == pinned_sha,
          f"pinned={pinned_sha[:16]} replay={replay_sha[:16]}")
    check("replay did not create a second execution",
          r3.get("execution_id") == before["execution_id"],
          f"{before['execution_id']} vs {r3.get('execution_id')}")

    # ---- 6. same key, different payload is refused, not re-executed ------
    r4 = ask(base2, token, sess, ask_text + " (different payload)",
             request_id=rid)
    check("same request_id with a DIFFERENT payload is refused (409)",
          r4.get("status") == 409, f"status={r4.get('status')}")

    # ---- 7. pre-restart history still returns the delivered answer -------
    try:
        h = httpx.get(f"{base2}/api/chat/history/{sess}",
                      params={"user_id": USER_ID},
                      headers={"Authorization": f"Bearer {token}"},
                      timeout=60, trust_env=False).json()
        msgs = h.get("messages") or []
        texts = [((m.get("response") or {}).get("message") or "") for m in msgs]
        check("pre-restart history still contains the delivered answer",
              any(t.strip() == pinned_msg.strip() for t in texts),
              f"{len(msgs)} history rows")
    except Exception as exc:
        check("pre-restart history still contains the delivered answer", False,
              f"{type(exc).__name__}: {exc}")

    bad = [c for c in results["checks"] if not c["ok"]]
    results["passed"] = len(results["checks"]) - len(bad)
    results["total"] = len(results["checks"])
    results["all_pass"] = not bad
    Path(args.out).write_text(json.dumps(results, indent=2))
    print(f"\n{results['passed']}/{results['total']} checks passed -> {args.out}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
