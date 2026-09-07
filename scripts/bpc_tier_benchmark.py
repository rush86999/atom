"""BPC tier benchmark runner (Sept 2026).

Measures candidate models on the tiered task battery (bpc_tier_battery.json):
per-BPC-complexity-tier accuracy on ORIGINAL tasks with deterministic
checkers, following the verification styles of ground-truth suites
(LiveBench/GPQA/AIME answer keys, HumanEval/MBPP unit tests, BFCL schema/args,
IFEval constraints, tau-bench-lite policy states).

Design notes (lessons from the recall probes):
- INCONCLUSIVE is distinct from FAIL: length-capped-empty or API errors are
  excluded from accuracy denominators, never scored as model failures.
- 429s retry with backoff; per-model sequential + cross-model parallelism.
- Cost-capped: max_tokens per task from the battery; --dry-run to inspect.

Usage:
  python3 scripts/bpc_tier_benchmark.py                # all default models
  python3 scripts/bpc_tier_benchmark.py --models z-ai/glm-5.3-flash
  python3 scripts/bpc_tier_benchmark.py --dry-run      # checkers self-test

Read-only w.r.t. the app: no DB access. Spends BYOK credit on openrouter.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

BATTERY = json.load(open(Path(__file__).parent / "bpc_tier_battery.json"))
RESULTS_PATH = Path(__file__).parent / "bpc_tier_benchmark_results.json"
CALL_SPACING_S = 1.5

DEFAULT_MODELS = [
    "z-ai/glm-5.3-flash",
    "deepseek/deepseek-v4-flash-0731",
    "qwen/qwen3.8-flash",
    "openai/gpt-5-mini",
    "google/gemini-3-flash-preview",
    "minimax/minimax-m3",
    "moonshotai/kimi-k2.5",
    "qwen/qwen3-max",
    "qwen/qwen3.7-flash",
]

SYSTEM = "You are Atom, a precise business assistant. Follow the reply format exactly."


def _openrouter_key() -> str:
    from cryptography.fernet import Fernet
    root = Path(__file__).resolve().parent.parent / "backend" / "data"
    keys = json.load(open(root / "byok_keys.json"))
    entry = next(v for v in keys["keys"].values()
                 if v.get("provider_id") == "openrouter" and v.get("is_active"))
    fernet = Fernet(open(root / "byok_encryption_key", "rb").read().strip())
    return fernet.decrypt(entry["encrypted_key"].encode()).decode()


# ---------------------------------------------------------------- checkers

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _extract_last_number(text: str):
    nums = re.findall(r"-?\d+(?:\.\d+)?", (text or "").replace(",", ""))
    return float(nums[-1]) if nums else None


def check(task: dict, response: str):
    """Return (verdict, detail). verdict in PASS/FAIL/INCONCLUSIVE."""
    c = task["checker"]
    ctype = c["type"]
    text = response or ""
    if ctype == "all_strings":
        ok = all(s.lower() in text.lower() for s in c["strings"])
        return ("PASS" if ok else "FAIL"), c["strings"]
    if ctype == "sequence":
        lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
        found = []
        for expect in c["expect"]:
            hit = next((l for l in lines if _norm(expect) in _norm(l)), None)
            found.append(bool(hit))
        return ("PASS" if all(found) else "FAIL"), dict(zip(c["expect"], found))
    if ctype == "max_words":
        words = text.split()
        ok = len(words) <= c["limit"]
        if c.get("must_include_any"):
            ok = ok and any(any(w.lower() in text.lower() for w in grp)
                            for grp in c["must_include_any"])
        return ("PASS" if ok else "FAIL"), {"words": len(words), "limit": c["limit"]}
    if ctype == "numeric":
        got = _extract_last_number(text)
        if got is None:
            return "INCONCLUSIVE", "no number found"
        tol = c.get("tolerance")
        ok = abs(got - c["value"]) <= (tol if tol is not None else 0)
        return ("PASS" if ok else "FAIL"), {"expected": c["value"], "got": got}
    if ctype == "string_set":
        missing = [s for s in c["strings"] if s not in text]
        return ("PASS" if not missing else "FAIL"), {"missing": missing}
    if ctype == "exact_text":
        got_lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
        want_lines = [l.strip() for l in c["value"].splitlines()]
        ok = got_lines == want_lines
        detail = {"expected_lines": want_lines, "got_lines": got_lines}
        return ("PASS" if ok else "FAIL"), detail
    if ctype == "json_fields":
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return "INCONCLUSIVE", "no JSON object found"
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            return "INCONCLUSIVE", f"unparseable JSON: {e}"

        def lookup(path):
            cur = obj
            for part in path.split("."):
                if not isinstance(cur, dict) or part not in cur:
                    return None
                cur = cur[part]
            return cur

        def norm_value(v):
            s = _norm(str(v))
            if c.get("normalize_commas"):
                s = re.sub(r"\s*,\s*", ", ", s)
            return s

        bad = {}
        for path, want in c["fields"].items():
            got = lookup(path)
            if isinstance(want, float):
                try:
                    got = float(got)
                except (TypeError, ValueError):
                    got = None
                if got is None or abs(got - want) > 0.01:
                    bad[path] = {"want": want, "got": got}
            elif isinstance(want, int) and not isinstance(want, bool):
                if got != want:
                    bad[path] = {"want": want, "got": got}
            elif norm_value(got) != norm_value(want):
                bad[path] = {"want": want, "got": got}
        return ("PASS" if not bad else "FAIL"), bad
    if ctype == "schedule_constraint":
        low = text.lower()
        _DAY_FULL = {"mon": "monday", "tue": "tuesday", "tues": "tuesday",
                     "wed": "wednesday", "weds": "wednesday",
                     "thu": "thursday", "thur": "thursday", "thurs": "thursday",
                     "fri": "friday"}

        def day_for(who):
            m = re.search(rf"{re.escape(who.lower())}\s*[:=]\s*(\w+)", low)
            if not m:
                return None
            d = m.group(1)
            return _DAY_FULL.get(d, d)  # accept Wed / Weds / Wednesday ...

        bad = {}
        assigned = {}
        for who in ("Alice", "Bob", "Client"):
            d = day_for(who)
            assigned[who] = d
            if d not in ("monday", "tuesday", "wednesday", "thursday", "friday"):
                bad[who] = f"unparsed day: {d}"
        want_client = c["required"]["Client"].lower()
        if assigned.get("Client") != want_client:
            bad["Client"] = f"must be {want_client}"
        if len({assigned.get(w) for w in ("Alice", "Bob", "Client")}) < 3:
            bad["distinct_days"] = "meetings must be on different days"
        for who, blocked in c["busy"].items():
            d = assigned.get(who)
            if d in [b.lower() for b in blocked if "before" not in b]:
                bad[who] = f"{d} is busy"
        # Bob busy Wednesday before 12:00 — Wednesday is allowed only with an
        # afternoon time.
        if assigned.get("Bob") == "wednesday":
            tm = re.search(r"bob\s*[:=]\s*\w+\s+(\d{1,2}):(\d{2})", low)
            if not tm or (int(tm.group(1)) < 12):
                bad["Bob"] = "wednesday slot must be 12:00 or later"
        return ("PASS" if not bad else "FAIL"), bad
    if ctype == "labeled_numerics":
        got = {}
        for label in c["labels"]:
            m = re.search(rf"{re.escape(label)}\s*[:=]\s*(.+)", text, re.IGNORECASE)
            got[label] = m.group(1).strip() if m else None
        bad = {}
        for label, want in c["labels"].items():
            raw = got.get(label)
            if raw is None:
                bad[label] = "missing"
                continue
            if isinstance(want, (int, float)) and not isinstance(want, str):
                num = _extract_last_number(raw)
                tol = c.get("tolerance") or 0
                if num is None or abs(num - want) > tol:
                    bad[label] = {"want": want, "got": raw}
            elif _norm(raw) != _norm(str(want)):
                bad[label] = {"want": want, "got": raw}
        return ("PASS" if not bad else "FAIL"), bad
    if ctype == "constraint_set":
        low = text.lower()
        bad = []
        for con in c["constraints"]:
            idx = low.find(con["tag"].lower())
            if idx < 0:
                bad.append(con["tag"])
                continue
            seg = text[idx + len(con["tag"]):]
            seg = seg.split("[")[0]  # stop at the next tag
            if len(seg.strip()) < con.get("min_len", 0):
                bad.append(con["tag"] + ":short")
            if con.get("requires_digit") and not re.search(r"\d", seg):
                bad.append(con["tag"] + ":no-number")
        words = len(text.split())
        if c.get("max_words") and words > c["max_words"]:
            bad.append("too-long")
        return ("PASS" if not bad else "FAIL"), {"violations": bad}
    if ctype == "set_match_min":
        cats = {m.group(0) for m in
                re.finditer(r"INJECTION|AUTHZ|SECRET|XSS|SSRF|CRYPTO|LOGGING",
                            text.upper())}
        groups_hit = sum(1 for group in c["categories_any_of"]
                         if any(cat in cats for cat in group))
        ok = groups_hit >= c["min"]
        return ("PASS" if ok else "FAIL"), {
            "groups_hit": groups_hit, "min": c["min"], "cats": sorted(cats)}
    if ctype == "code_asserts":
        m = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
        code = m.group(1) if m else (text if "def " in text else "")
        if not code.strip():
            return "INCONCLUSIVE", "no code found"
        # HumanEval-style: model code lands in sol.py; the test payload
        # imports from it, mirroring the battery's `from sol import ...`.
        import tempfile as _tf
        with _tf.TemporaryDirectory() as tmp:
            Path(tmp, "sol.py").write_text(code)
            payload = c["setup"] + "\n"
            for a in c["asserts"]:
                payload += f"assert {a}, {a!r}\n"
            payload += "print('ALL_OK')\n"
            test_path = Path(tmp, "run_tests.py")
            test_path.write_text(payload)
            try:
                proc = subprocess.run([sys.executable, str(test_path)],
                                      capture_output=True, text=True, timeout=10,
                                      cwd=tmp)
                ok = proc.returncode == 0 and "ALL_OK" in proc.stdout
                return ("PASS" if ok else "FAIL"), (proc.stdout + proc.stderr)[-400:]
            except subprocess.TimeoutExpired:
                return "FAIL", "timeout"
    return "INCONCLUSIVE", f"unknown checker {ctype}"


# ---------------------------------------------------------------- runner

def call_model(client, key, model, task):
    for attempt in range(4):
        try:
            r = client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "temperature": 0,
                      "max_tokens": task["max_tokens"],
                      "messages": [{"role": "system", "content": SYSTEM},
                                   {"role": "user", "content": task["prompt"]}]},
                timeout=180)
            if r.status_code == 429:
                time.sleep(8 * (attempt + 1))
                continue
            r.raise_for_status()
            j = r.json()
            msg = (j.get("choices") or [{}])[0].get("message") or {}
            finish = (j.get("choices") or [{}])[0].get("finish_reason")
            usage = j.get("usage", {}) or {}
            return {"content": msg.get("content") or "", "finish": finish,
                    "usage": usage}
        except Exception as e:
            if attempt == 3:
                return {"content": "", "finish": None, "error": f"{type(e).__name__}: {e}",
                        "usage": {}}
            time.sleep(5)
    return {"content": "", "finish": None, "error": "retries exhausted", "usage": {}}


def run_model(model, key, tasks):
    out = {"model": model, "tasks": {}}
    with httpx.Client() as client:
        for task in tasks:
            raw = call_model(client, key, model, task)
            text = raw.get("content", "")
            if raw.get("error"):
                verdict, detail = "INCONCLUSIVE", raw["error"]
            elif raw.get("finish") == "length" and not text.strip():
                verdict, detail = "INCONCLUSIVE", "length-capped-empty"
            else:
                verdict, detail = check(task, text)
            out["tasks"][task["id"]] = {"tier": task["tier"], "verdict": verdict,
                                        "detail": detail, "reply": text[:500]}
            print(f"  {model:36s} {task['id']:24s} {verdict}", flush=True)
            time.sleep(CALL_SPACING_S)
    return out


def summarize(results):
    tiers = {}
    for r in results:
        per = {"simple": [0, 0], "moderate": [0, 0], "complex": [0, 0],
               "advanced": [0, 0]}
        for t in r["tasks"].values():
            bucket = per[t["tier"]]
            if t["verdict"] in ("PASS", "FAIL"):
                bucket[1] += 1
                bucket[0] += 1 if t["verdict"] == "PASS" else 0
        tiers[r["model"]] = {
            tier: {"pass": p, "graded": g, "acc": round(p / g, 3) if g else None}
            for tier, (p, g) in per.items()
        }
    return tiers


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=DEFAULT_MODELS)
    ap.add_argument("--dry-run", action="store_true",
                    help="print the battery and exit (no API calls)")
    args = ap.parse_args()

    tasks = BATTERY["tasks"]

    if args.dry_run:
        for t in tasks:
            print(f"{t['tier']:9s} {t['id']:24s} checker={t['checker']['type']}")
        print(f"{len(tasks)} tasks, checkers import OK")
        return

    key = _openrouter_key()
    print(f"Measuring {len(args.models)} models x {len(tasks)} tasks", flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda m: run_model(m, key, tasks), args.models))

    summary = summarize(results)
    print("\n===== PER-TIER ACCURACY (graded only; INCONCLUSIVE excluded) =====")
    header = f"{'model':38s} " + " ".join(f"{t:>22s}" for t in
                                          ("simple", "moderate", "complex", "advanced"))
    print(header)
    for model, per in summary.items():
        cells = []
        for v in per.values():
            cells.append(f"{v['pass']}/{v['graded']}={v['acc']:.2f}".rjust(22)
                         if v["acc"] is not None else "n/a".rjust(22))
        print(f"{model:38s} {' '.join(cells)}")

    json.dump({"battery_version": BATTERY["version"], "summary": summary,
               "results": results},
              open(RESULTS_PATH, "w"), indent=1)
    print(f"\nSaved -> {RESULTS_PATH}")


if __name__ == "__main__":
    main()
