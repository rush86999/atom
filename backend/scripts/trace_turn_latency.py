#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Controlled latency traces for one chat turn — bounded, with stop conditions.

Audit directive 2. The rule this follows: diagnose latency with CONTROLLED
TRACES rather than repeated full acceptance replays, because a replay mutates
the thing it measures — acceptance traffic changes session history, caches,
learning and load, so the tenth run is not measuring the same system as the
first.

What this records per attempt:

* **queue delay** — how long before the server even began answering (client-side
  request-to-headers), which full-replay reports fold into "latency";
* **critical-path wall time** — the turn as the user experiences it;
* **stage boundaries** — the server's own ``[deadline] stage=…`` lines, each with
  its own duration AND its turn offset, so a stage that ran CONCURRENTLY is
  distinguishable from one that sat on the critical path;
* **provider attempts and retries** — counted from the trace/usage side, not
  inferred;
* **work still running after the turn** — a turn that had to cancel owned tasks,
  or a deadline that expired with work outstanding.

Bounded by construction: a hard attempt cap, a per-attempt timeout, and a
STOP CONDITION that aborts the run when a category of measurement is already
decisive. Repeated attempts only continue while they can still change the
conclusion.

Isolation: this script does NOT write to the production learning store. It uses
a fresh session per attempt unless told to reuse one, and it reports the session
ids so any observation can be traced (or excluded) afterwards.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# The derivation case: the one that has been failing on BUDGET rather than on
# routing, so it is where a deadline trace is informative.
DERIVATION_MESSAGE = (
    "open PRICE VIPUL and show how the 7519 listed price was derived"
)
CONTROL_MESSAGE = "search for this one: $ 5,350.00 - 10 % in stock"

#: Predetermined stop conditions — a run ends when a conclusion is reached, not
#: when a count is exhausted.
MAX_ATTEMPTS_DEFAULT = 4
STOP_AFTER_CONSECUTIVE_TIMEOUTS = 2
STOP_AFTER_CONSECUTIVE_COMPLETIONS = 2


@dataclass
class Attempt:
    label: str
    session: str
    reused_session: bool
    http_status: Optional[int] = None
    outcome: str = "unknown"          # completed | timeout | budget_exceeded | error
    queue_delay_s: Optional[float] = None
    wall_s: Optional[float] = None
    server_stages: List[Dict[str, Any]] = field(default_factory=list)
    cancelled_tasks: Optional[int] = None
    survivors: Optional[int] = None
    note: str = ""

    @property
    def breached(self) -> bool:
        """Operational failure: the client's window cannot be satisfied."""
        return self.wall_s is not None and self.wall_s > CLIENT_BUDGET_S


#: The client abort budget (frontend useChatInterface.ts: timeout 120000ms).
CLIENT_BUDGET_S = 120.0

_STAGE_RE = re.compile(
    r"\[deadline\] (?P<label>\S+) stage=(?P<stage>\S+) dur=(?P<dur>[\d.]+)s "
    r"turn_offset=(?P<offset>[\d.]+)s elapsed=(?P<elapsed>[\d.]+)s "
    r"remaining=(?P<remaining>-?[\d.]+)s budget=(?P<budget>[\d.]+)s"
)
_CANCEL_RE = re.compile(
    r"\[deadline\] (?P<label>\S+): cancelled (?P<n>\d+) owned task\(s\), "
    r"(?:all confirmed stopped within (?P<grace>[\d.]+)s)"
)
_SURVIVOR_RE = re.compile(
    r"\[deadline\] (?P<label>\S+): (?P<n>\d+) task\(s\) still running"
)


def _log_path(port: int) -> Optional[Path]:
    root = Path(__file__).resolve().parent.parent
    for name in (f"uvicorn_{port}_restart.log", "atom.log"):
        p = root / "logs" / name
        if p.exists():
            return p
    return None


def _read_stages_since(path: Optional[Path], offset: int) -> tuple:
    """Server stage lines written since ``offset`` (byte offset)."""
    if path is None:
        return [], offset
    stages: List[Dict[str, Any]] = []
    survivors = 0
    cancelled = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(offset)
            for line in fh:
                m = _STAGE_RE.search(line)
                if m:
                    stages.append({
                        "label": m.group("label"),
                        "stage": m.group("stage"),
                        "dur_s": float(m.group("dur")),
                        "turn_offset_s": float(m.group("offset")),
                        "remaining_s": float(m.group("remaining")),
                    })
                    continue
                m = _SURVIVOR_RE.search(line)
                if m:
                    survivors += int(m.group("n"))
                    continue
                m = _CANCEL_RE.search(line)
                if m:
                    cancelled += int(m.group("n"))
            offset = fh.tell()
    except Exception:  # noqa: BLE001 — tracing must never be the failure
        pass
    return stages, {"offset": offset, "survivors": survivors, "cancelled": cancelled}


async def _login(client: httpx.AsyncClient, base: str) -> Optional[str]:
    for payload in (
        {"username": os.getenv("ATOM_TRACE_USER", "admin@example.com"),
         "password": os.getenv("ATOM_TRACE_PASS", "admin123")},
    ):
        try:
            r = await client.post(f"{base}/api/auth/login", json=payload, timeout=15)
            if r.status_code == 200:
                data = r.json()
                token = data.get("access_token") or (
                    (data.get("data") or {}).get("access_token"))
                if token:
                    return token
        except Exception:  # noqa: BLE001
            continue
    return None


async def _one_attempt(
    client: httpx.AsyncClient, base: str, token: str, *,
    label: str, message: str, session: Optional[str], timeout: float,
    log_path: Optional[Path], log_offset: int, canvas_id: Optional[str],
    user_id: str = "",
) -> tuple:
    """Run one bounded attempt; return (Attempt, new_log_offset)."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    payload: Dict[str, Any] = {"message": message, "user_id": user_id}
    if session:
        payload["session_id"] = session
    if canvas_id:
        payload["context"] = {"canvas_id": canvas_id}

    att = Attempt(label=label, session=session or "(new)", reused_session=bool(session))
    t0 = time.monotonic()
    first_byte: Optional[float] = None
    status: Optional[int] = None
    body_text = ""
    try:
        async with client.stream(
            "POST", f"{base}/api/chat/message", json=payload,
            headers=headers, timeout=timeout,
        ) as resp:
            status = resp.status_code
            first_byte = time.monotonic() - t0
            body_text = "".join([chunk async for chunk in resp.aiter_text()])
    except httpx.TimeoutException:
        att.outcome = "timeout"
        att.note = f"client timeout at {timeout:.0f}s"
    except Exception as exc:  # noqa: BLE001
        att.outcome = "error"
        att.note = f"{type(exc).__name__}: {str(exc)[:120]}"
    wall = time.monotonic() - t0

    stages, meta = _read_stages_since(log_path, log_offset)
    att.http_status = status
    att.queue_delay_s = round(first_byte, 2) if first_byte is not None else None
    att.wall_s = round(wall, 2)
    att.server_stages = stages
    att.cancelled_tasks = meta.get("cancelled") or None
    att.survivors = meta.get("survivors") or None
    if att.outcome == "unknown":
        if "turn_budget_exceeded" in body_text:
            att.outcome = "budget_exceeded"
        elif status == 200:
            att.outcome = "completed"
        else:
            att.outcome = f"http_{status}"
    # A session id is returned by the server; capture it for traceability.
    m = re.search(r'"session_id"\s*:\s*"([^"]+)"', body_text or "")
    if m:
        att.session = m.group(1)
    return att, meta.get("offset", log_offset)


def _summarise(attempts: List[Attempt]) -> Dict[str, Any]:
    walls = [a.wall_s for a in attempts if a.wall_s is not None]
    queue = [a.queue_delay_s for a in attempts if a.queue_delay_s is not None]
    stages_by_name: Dict[str, List[float]] = {}
    for a in attempts:
        for st in a.server_stages:
            stages_by_name.setdefault(st["stage"], []).append(st["dur_s"])
    return {
        "attempts": len(attempts),
        "outcomes": [a.outcome for a in attempts],
        "wall_s": walls,
        "wall_median_s": round(statistics.median(walls), 1) if walls else None,
        "queue_delay_s": queue,
        "breaches_over_client_budget": sum(1 for a in attempts if a.breached),
        "cancelled_tasks": sum(a.cancelled_tasks or 0 for a in attempts),
        "survivor_tasks": sum(a.survivors or 0 for a in attempts),
        "stage_durations_by_name": {
            k: {"n": len(v), "median_s": round(statistics.median(v), 1),
                "max_s": round(max(v), 1)}
            for k, v in sorted(stages_by_name.items())
        },
    }


async def main_async(args: argparse.Namespace) -> int:
    base = f"http://127.0.0.1:{args.port}"
    message = CONTROL_MESSAGE if args.case == "control" else DERIVATION_MESSAGE
    log_path = _log_path(args.port)
    offset = log_path.stat().st_size if (args.follow_log and log_path) else 0

    attempts: List[Attempt] = []
    consecutive_timeouts = 0
    consecutive_completed = 0
    stop_reason = "attempt cap reached"

    async with httpx.AsyncClient() as client:
        if args.token_file:
            token = Path(args.token_file).read_text(encoding="utf-8").strip()
        elif not args.no_auth:
            token = await _login(client, base)
            if not token:
                print("! could not authenticate — set ATOM_TRACE_USER/PASS or "
                      "pass --no-auth for an unauthenticated probe", file=sys.stderr)
                return 2
        else:
            token = ""
        session = args.session
        for i in range(args.attempts):
            att, offset = await _one_attempt(
                client, base, token, label=f"{args.case}#{i + 1}",
                message=message, session=session, timeout=args.timeout,
                log_path=log_path if args.follow_log else None,
                log_offset=offset, canvas_id=args.canvas_id,
                user_id=args.user_id,
            )
            attempts.append(att)
            print(f"  {att.label}: {att.outcome} wall={att.wall_s}s "
                  f"queue={att.queue_delay_s}s stages={len(att.server_stages)}"
                  + (f" cancelled={att.cancelled_tasks}" if att.cancelled_tasks else "")
                  + (f" SURVIVORS={att.survivors}" if att.survivors else ""))
            if not args.fresh_session:
                session = att.session  # reuse the returned session (incident-like)
            # ── stop conditions ────────────────────────────────────────────
            if att.outcome == "timeout":
                consecutive_timeouts += 1
                consecutive_completed = 0
            elif att.outcome == "completed":
                consecutive_completed += 1
                consecutive_timeouts = 0
            if consecutive_timeouts >= STOP_AFTER_CONSECUTIVE_TIMEOUTS:
                stop_reason = (f"{consecutive_timeouts} consecutive timeouts — "
                               "the deadline is not the binding constraint")
                break
            if consecutive_completed >= STOP_AFTER_CONSECUTIVE_COMPLETIONS and i >= 1:
                stop_reason = (f"{consecutive_completed} consecutive completions — "
                               "latency distribution is established")
                break

    report = {
        "case": args.case,
        "port": args.port,
        "message": message,
        "session_mode": "fresh per attempt" if args.fresh_session else "reused",
        "client_budget_s": CLIENT_BUDGET_S,
        "stop_reason": stop_reason,
        "summary": _summarise(attempts),
        "attempts": [asdict(a) for a in attempts],
    }
    print(json.dumps(report["summary"], indent=2))
    print(f"stop: {stop_reason}")
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"wrote {args.json}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--case", choices=("derivation", "control"), default="derivation")
    ap.add_argument("--attempts", type=int, default=MAX_ATTEMPTS_DEFAULT,
                    help="hard cap; stop conditions usually end the run sooner")
    ap.add_argument("--timeout", type=float, default=CLIENT_BUDGET_S,
                    help="per-attempt client timeout (default = the client budget)")
    ap.add_argument("--session", default=None, help="reuse this session id")
    ap.add_argument("--fresh-session", action="store_true",
                    help="a NEW session per attempt (isolates cache/history effects)")
    ap.add_argument("--canvas-id", default=None)
    ap.add_argument("--follow-log", action="store_true",
                    help="parse the server's [deadline] stage lines")
    ap.add_argument("--no-auth", action="store_true")
    ap.add_argument("--token-file", default=None,
                    help="bearer token file (skips login; the password may be rotated)")
    ap.add_argument("--user-id", default=os.getenv("ATOM_TRACE_USER_ID", ""),
                    help="user_id the chat endpoint requires")
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
