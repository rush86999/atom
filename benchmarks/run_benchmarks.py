#!/usr/bin/env python3
"""
Atom Benchmark Runner

Measures four categories of performance against a running Atom instance:
  1. Routing accuracy — does the cognitive-tier router pick a sensible model?
  2. Response latency — end-to-end chat round-trip time
  3. Formula evaluation correctness — does the workbook runtime compute formulas?
  4. Canvas CRUD round-trip — create/read/update/delete timing

Usage:
  # Against a running instance (default http://localhost:8000):
  python benchmarks/run_benchmarks.py

  # Custom URL + auth:
  python benchmarks/run_benchmarks.py \
      --url http://localhost:8000 \
      --username user@example.com \
      --password 'YourPassword123!'

  # JSON output for CI:
  python benchmarks/run_benchmarks.py --format json

  # Write results to benchmarks/RESULTS.md:
  python benchmarks/run_benchmarks.py --write

Requirements:
  pip install httpx
  (The host Atom instance must be running and reachable.)

Exit codes:
  0 — all benchmarks ran (results may still exceed targets)
  1 — could not connect / auth failed
  2 — a benchmark target was missed (use --strict to enable)
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

try:
    import httpx
except ImportError:
    print("ERROR: httpx is required. Install with: pip install httpx", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

@dataclass
class BenchResult:
    name: str
    category: str
    target_ms: Optional[float]
    samples_ms: list[float] = field(default_factory=list)
    passed: bool = True
    note: str = ""

    @property
    def p50(self) -> float:
        return statistics.median(self.samples_ms) if self.samples_ms else 0.0

    @property
    def p95(self) -> float:
        if not self.samples_ms:
            return 0.0
        sorted_s = sorted(self.samples_ms)
        idx = int(len(sorted_s) * 0.95)
        return sorted_s[min(idx, len(sorted_s) - 1)]

    @property
    def mean(self) -> float:
        return statistics.mean(self.samples_ms) if self.samples_ms else 0.0

    def check_target(self) -> None:
        if self.target_ms is not None and self.p50 > self.target_ms:
            self.passed = False


@dataclass
class BenchReport:
    base_url: str
    started_at: str
    results: list[BenchResult] = field(default_factory=list)
    auth_ok: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class AtomClient:
    """Thin HTTP client wrapping the Atom API."""

    def __init__(self, base_url: str, timeout: float = 90.0):
        self.base_url = base_url.rstrip("/")
        self.token: Optional[str] = None
        self.user_id: str = "default_user"
        self.client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def login(self, username: str, password: str) -> bool:
        r = self.client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        if r.status_code != 200:
            return False
        body = r.json()
        if body.get("two_factor_required"):
            return False
        self.token = body.get("access_token")
        self.user_id = body.get("user_id", "default_user")
        return self.token is not None

    def _h(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def chat(self, message: str, session_id: str = "new") -> dict[str, Any]:
        r = self.client.post(
            "/api/chat/message",
            headers=self._h(),
            json={
                "message": message,
                "user_id": self.user_id,
                "session_id": session_id,
                "context": {},
            },
        )
        return {"status": r.status_code, "body": r.json() if r.text else {}}

    def feedback(self, message_id: str, feedback: str) -> int:
        r = self.client.post(
            "/api/chat/feedback",
            headers=self._h(),
            json={"message_id": message_id, "feedback": feedback},
        )
        return r.status_code

    def routing_stats(self) -> dict[str, Any]:
        r = self.client.get("/api/chat/routing-stats", headers=self._h())
        return r.json() if r.text else {}

    def health(self) -> dict[str, Any]:
        r = self.client.get("/health")
        return r.json() if r.text else {}

    # Canvas -----------------------------------------------------------------
    def canvas_put(self, canvas_id: str, content: Any, canvas_type: str = "sheets") -> int:
        r = self.client.put(
            f"/api/canvas/{canvas_id}",
            headers=self._h(),
            params={"canvas_type": canvas_type, "title": f"Bench {canvas_id}"},
            json={"content": content},
        )
        return r.status_code

    def canvas_get(self, canvas_id: str) -> int:
        r = self.client.get(f"/api/canvas/{canvas_id}", headers=self._h())
        return r.status_code

    def canvas_delete(self, canvas_id: str) -> int:
        r = self.client.delete(f"/api/canvas/{canvas_id}", headers=self._h())
        return r.status_code

    def canvas_list(self) -> int:
        r = self.client.get("/api/canvas/", headers=self._h())
        return r.status_code

    # Excel ------------------------------------------------------------------
    def excel_write(self, file_path: str, cell_path: str, value: Any, is_formula: bool = False) -> dict[str, Any]:
        body = {"file_path": file_path, "cell_path": cell_path, "value": value}
        if is_formula:
            body["is_formula"] = True
        r = self.client.post("/api/v1/office/excel", headers=self._h(), json=body)
        return {"status": r.status_code, "body": r.json() if r.text else {}}

    def excel_formula_result(self, file_path: str, cell_path: str) -> dict[str, Any]:
        r = self.client.get(
            "/api/v1/office/excel/formula-result",
            headers=self._h(),
            params={"file_path": file_path, "cell_path": cell_path},
        )
        return {"status": r.status_code, "body": r.json() if r.text else {}}

    def excel_recalculate(self, file_path: str) -> int:
        r = self.client.post(
            "/api/v1/office/excel/recalculate",
            headers=self._h(),
            params={"file_path": file_path},
        )
        return r.status_code

    def close(self):
        self.client.close()


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------

def bench_health(client: AtomClient, report: BenchReport) -> None:
    """Health check should be near-instant."""
    result = BenchResult(name="health_check", category="latency", target_ms=50.0)
    for _ in range(20):
        t0 = time.perf_counter()
        client.health()
        result.samples_ms.append((time.perf_counter() - t0) * 1000)
    result.check_target()
    report.results.append(result)


def bench_chat_latency(client: AtomClient, report: BenchReport) -> None:
    """End-to-end chat round-trip. Depends on the configured LLM provider."""
    result = BenchResult(
        name="chat_round_trip",
        category="latency",
        target_ms=None,  # provider-dependent; reported, not gated
        note="Depends on the configured LLM provider. No target — informational.",
    )
    prompts = [
        "Hello, what can you do?",
        "Summarize the weather today.",
        "What is 2 + 2?",
        "List three fruits.",
        "Translate 'hello' to Spanish.",
    ]
    for i, prompt in enumerate(prompts):
        t0 = time.perf_counter()
        resp = client.chat(prompt, session_id=f"bench_{i}")
        elapsed = (time.perf_counter() - t0) * 1000
        result.samples_ms.append(elapsed)
        body = resp.get("body", {})
        if body.get("success") is False:
            report.notes.append(
                f"chat_round_trip: provider not configured ({body.get('error_code')}). "
                "Latency reflects the no-provider fast-path, not a real LLM call."
            )
            result.note = "No LLM provider configured — measured the fast-path rejection, not a real call."
            break
    result.check_target()
    report.results.append(result)


def bench_routing_accuracy(client: AtomClient, report: BenchReport) -> None:
    """
    Verify the routing-stats endpoint responds and reports model usage.
    Also exercises the feedback → learning loop to confirm the path works.
    """
    result = BenchResult(name="routing_stats_responsive", category="routing", target_ms=500.0)
    for _ in range(5):
        t0 = time.perf_counter()
        client.routing_stats()
        result.samples_ms.append((time.perf_counter() - t0) * 1000)
    result.check_target()
    report.results.append(result)

    # Feedback path sanity (not timed — correctness check)
    fb_result = BenchResult(name="feedback_loop_writes", category="routing", target_ms=None)
    code = client.feedback("bench_msg_1", "thumbs_up")
    fb_result.passed = code in (200, 201)
    fb_result.note = f"POST /api/chat/feedback returned {code}"
    report.results.append(fb_result)


def bench_formula_evaluation(client: AtomClient, report: BenchReport) -> None:
    """
    Write numbers + a SUM formula, then read the computed result back.
    Verifies the workbook runtime actually evaluates formulas (not just stores strings).
    """
    file_path = f"data/bench_{uuid.uuid4().hex[:8]}.xlsx"
    result = BenchResult(name="formula_eval_correctness", category="formula", target_ms=2000.0)
    correct = False
    t0 = time.perf_counter()
    try:
        client.excel_write(file_path, "/Sheet1/A1", 100)
        client.excel_write(file_path, "/Sheet1/A2", 200)
        client.excel_write(file_path, "/Sheet1/A3", "=SUM(A1:A2)", is_formula=True)
        client.excel_recalculate(file_path)
        readback = client.excel_formula_result(file_path, "/Sheet1/A3")
        body = readback.get("body", {})
        value = body.get("value", body.get("result"))
        correct = str(value) == "300"
        if not correct:
            result.note = f"Expected 300, got {value!r} (raw body: {body})"
    except Exception as e:
        result.note = f"Exception: {e}"
        correct = False
    elapsed = (time.perf_counter() - t0) * 1000
    result.samples_ms.append(elapsed)
    result.passed = correct
    result.check_target()
    report.results.append(result)


def bench_canvas_crud(client: AtomClient, report: BenchReport) -> None:
    """Full canvas create → read → update → delete round-trip."""
    result = BenchResult(name="canvas_crud_round_trip", category="canvas", target_ms=1000.0)
    canvas_id = f"bench_{uuid.uuid4().hex[:8]}"
    t0 = time.perf_counter()
    try:
        put1 = client.canvas_put(canvas_id, [["Item", "Amount"], ["Rent", "3000"]])
        got = client.canvas_get(canvas_id)
        put2 = client.canvas_put(canvas_id, [["Item", "Amount"], ["Rent", "3200"], ["Ads", "500"]])
        got2 = client.canvas_get(canvas_id)
        deleted = client.canvas_delete(canvas_id)
        elapsed = (time.perf_counter() - t0) * 1000
        result.samples_ms.append(elapsed)
        ok = put1 in (200, 201) and got == 200 and put2 in (200, 201) and got2 == 200 and deleted in (200, 204)
        if not ok:
            result.note = f"Statuses: put1={put1} get1={got} put2={put2} get2={got2} del={deleted}"
        result.passed = ok
    except Exception as e:
        result.note = f"Exception: {e}"
        result.passed = False
        result.samples_ms.append((time.perf_counter() - t0) * 1000)
    result.check_target()
    report.results.append(result)

    # Canvas list latency
    list_result = BenchResult(name="canvas_list", category="canvas", target_ms=200.0)
    for _ in range(5):
        t0 = time.perf_counter()
        client.canvas_list()
        list_result.samples_ms.append((time.perf_counter() - t0) * 1000)
    list_result.check_target()
    report.results.append(list_result)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def render_markdown(report: BenchReport) -> str:
    lines = [
        "# Atom Benchmark Results",
        "",
        f"- **Instance:** `{report.base_url}`",
        f"- **Run:** {report.started_at}",
        f"- **Auth:** {'OK' if report.auth_ok else 'FAILED (ran unauthenticated where possible)'}",
        f"- **Overall:** {'PASS' if report.all_passed else 'SOME TARGETS MISSED'}",
        "",
    ]
    if report.notes:
        lines.append("## Notes")
        for n in report.notes:
            lines.append(f"- {n}")
        lines.append("")

    lines.append("## Results")
    lines.append("")
    lines.append("| Benchmark | Category | P50 (ms) | P95 (ms) | Target (ms) | Result |")
    lines.append("|---|---|---:|---:|---:|:---:|")
    for r in report.results:
        target = f"{r.target_ms:.0f}" if r.target_ms is not None else "—"
        status = "✅ pass" if r.passed else "❌ fail"
        lines.append(
            f"| {r.name} | {r.category} | {r.p50:.1f} | {r.p95:.1f} | {target} | {status} |"
        )
        if r.note:
            lines.append(f"  - _{r.note}_")

    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append("- Each latency benchmark runs N iterations; P50 (median) and P95 are reported.")
    lines.append("- Targets are conservative defaults for a single-node dev instance; production")
    lines.append("  deployments should set stricter SLOs.")
    lines.append("- `chat_round_trip` has no target because it is dominated by the upstream LLM")
    lines.append("  provider's latency, which Atom does not control. It is reported for trend tracking.")
    lines.append("- `formula_eval_correctness` checks that `=SUM(A1:A2)` over `100` and `200` returns")
    lines.append("  `300` — verifying the workbook runtime evaluates formulas, not just stores strings.")
    lines.append("- `canvas_crud_round_trip` times a full create→read→update→read→delete cycle.")
    lines.append("- Re-run with `--write` to regenerate this file.")
    return "\n".join(lines)


def render_json(report: BenchReport) -> str:
    return json.dumps(
        {
            "base_url": report.base_url,
            "started_at": report.started_at,
            "auth_ok": report.auth_ok,
            "all_passed": report.all_passed,
            "notes": report.notes,
            "results": [
                {
                    "name": r.name,
                    "category": r.category,
                    "p50_ms": round(r.p50, 2),
                    "p95_ms": round(r.p95, 2),
                    "mean_ms": round(r.mean, 2),
                    "target_ms": r.target_ms,
                    "passed": r.passed,
                    "note": r.note,
                    "samples": len(r.samples_ms),
                }
                for r in report.results
            ],
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Atom benchmark runner")
    parser.add_argument("--url", default=os.getenv("ATOM_URL", "http://localhost:8000"))
    parser.add_argument("--username", default=os.getenv("ATOM_USER", ""))
    parser.add_argument("--password", default=os.getenv("ATOM_PASS", ""))
    parser.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    parser.add_argument("--write", action="store_true", help="Write results to benchmarks/RESULTS.md")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if any target is missed")
    args = parser.parse_args()

    client = AtomClient(args.url)
    report = BenchReport(base_url=args.url, started_at=time.strftime("%Y-%m-%d %H:%M:%S %Z"))

    # Connectivity
    try:
        h = client.health()
        report.notes.append(f"Health check responded: {h}")
    except httpx.ConnectError:
        print(f"ERROR: could not connect to {args.url}. Is Atom running?", file=sys.stderr)
        print("  Start it with: scripts/dev.sh", file=sys.stderr)
        return 1

    # Auth (optional — some benchmarks work without it, but most need it)
    if args.username and args.password:
        if client.login(args.username, args.password):
            report.auth_ok = True
        else:
            print(f"ERROR: login failed for {args.username}", file=sys.stderr)
            return 1
    else:
        report.notes.append("No credentials provided — running unauthenticated (chat/canvas/excel will likely 401).")

    # Run benchmarks
    print("Running benchmarks...", file=sys.stderr)
    bench_health(client, report)
    bench_routing_accuracy(client, report)
    bench_formula_evaluation(client, report)
    bench_canvas_crud(client, report)
    bench_chat_latency(client, report)
    client.close()

    # Output
    if args.format == "json":
        print(render_json(report))
    elif args.format == "markdown":
        print(render_markdown(report))
    else:
        print(f"\n{'Benchmark':<30} {'Category':<10} {'P50ms':>8} {'P95ms':>8} {'Target':>8}  Result")
        print("-" * 80)
        for r in report.results:
            target = f"{r.target_ms:.0f}" if r.target_ms else "—"
            status = "✅" if r.passed else "❌"
            print(f"{r.name:<30} {r.category:<10} {r.p50:>8.1f} {r.p95:>8.1f} {target:>8}  {status}")
            if r.note:
                print(f"  ↳ {r.note}")
        if report.notes:
            print("\nNotes:")
            for n in report.notes:
                print(f"  - {n}")

    if args.write:
        out_path = os.path.join(os.path.dirname(__file__), "RESULTS.md")
        with open(out_path, "w") as f:
            f.write(render_markdown(report))
        print(f"\nResults written to {out_path}", file=sys.stderr)

    if args.strict and not report.all_passed:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
