"""Offline eval of StrandsAgents/strands-decider-2B-hobson-v19 against real
recorded decisions from this repo's acceptance fixtures.

Seams:
  B. Tool gate (binary): does answering the latest user message need FRESH
     data from a connected tool? Labels: hand-applied planner rubric
     (labels_tool_gate.json) over real user messages.
  C. Wobble / inability (binary): does the assistant reply claim it lacks
     access/ability/data? Labels: the repo's own _INABILITY_RE
     (chat_orchestrator.py:733), applied mechanically.

Usage: python run_eval.py --port 8477
Requires: strands-decider serve StrandsAgents/strands-decider-2B-hobson-v19 --port <port>
"""
import argparse
import json
import statistics
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
EV = HERE / "eval_data"

TOOL_GATE_Q = (
    "Does answering this latest user message require fetching fresh data "
    "from a connected tool (mailbox, file storage, or web), or is the "
    "conversation itself enough?"
)
TOOL_GATE_Q_SIMPLE = (
    "Would answering this message need fresh data from a connected tool?"
)
INABILITY_Q = (
    "Does this assistant reply claim that it lacks the access, ability, or "
    "data needed to do what was asked?"
)
SERVICE_Q = "Which connected service should provide the fresh data?"


def ask(port, state, questions):
    body = json.dumps({"state": state[:6000], "questions": questions}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/systemone",
        data=body,
        headers={"content-type": "application/json"},
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.loads(r.read())
    out["_client_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return out


def build_state(msg, mode="context"):
    if mode == "message_only":
        return msg["content"]
    parts = []
    for c in msg.get("context", [])[:-1]:
        parts.append(f"{c['role']}: {c['content']}")
    parts.append(f"user (latest message): {msg['content']}")
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8477)
    ap.add_argument("--state-mode", default="context", choices=["context", "message_only"])
    ap.add_argument("--phrasing", default="compound", choices=["compound", "simple"])
    ap.add_argument("--skip-wobble", action="store_true")
    args = ap.parse_args()
    gate_q = TOOL_GATE_Q if args.phrasing == "compound" else TOOL_GATE_Q_SIMPLE

    labels = json.loads((HERE / "labels_tool_gate.json").read_text())["labels"]
    service_options = json.loads((HERE / "labels_tool_gate.json").read_text())["service_options"]
    msgs = json.loads((EV / "user_messages_for_labeling.json").read_text())
    replies = json.loads((EV / "assistant_replies_inability.json").read_text())

    # --- probe response shape once ---
    probe = ask(args.port, "hello", {"t": {"type": "noul", "instructions": "Is this a greeting?"}})
    print("probe response keys:", sorted(probe.keys()))
    print("probe answers:", json.dumps(probe.get("answers"), indent=1)[:400])
    (HERE / "eval_data" / "probe_response.json").write_text(json.dumps(probe, indent=1))

    # --- Seam B: tool gate ---
    rows = []
    for m in msgs:
        lab = labels.get(m["id"])
        if lab is None:
            continue
        qs = {"tool_gate": {"type": "noul", "instructions": gate_q}}
        if lab["service"]:
            svc_id = {"email search": "email", "workdrive file search": "workdrive"}[lab["service"]]
            qs["service"] = {
                "type": "choice",
                "instructions": SERVICE_Q,
                "criteria": {
                    "email": "email search",
                    "workdrive": "workdrive file search",
                    "web_search": "web search",
                    "web_fetch": "web fetch",
                    "memory": "memory",
                },
            }
        r = ask(args.port, build_state(m, args.state_mode), qs)
        rows.append({"id": m["id"], "label": lab, "response": r})
    (HERE / "eval_data" / "raw_tool_gate.json").write_text(json.dumps(rows, indent=1))

    def ans(row, name):
        a = row["response"]["answers"][name]
        return a

    # --- Seam C: wobble/inability ---
    wrows = []
    if not args.skip_wobble:
        for a in replies:
            r = ask(args.port, a["content"], {"wobble": {"type": "noul", "instructions": INABILITY_Q}})
            wrows.append({"id": a["id"], "label": a["inability_label"], "response": r})
        (HERE / "eval_data" / "raw_wobble.json").write_text(json.dumps(wrows, indent=1))

    # --- metrics (noul value key resolved from probe) ---
    def noul_value(a):
        if "noul" in a:
            return float(a["noul"])
        for k in ("value", "answer", "score", "probability"):
            if k in a:
                return float(a[k])
        return float(list(a.values())[0])

    def choice_pick(a):
        return a.get("choice")
        return None

    print("\n=== Seam B: tool gate (n>=%d) ===" % len(rows))
    y_true = [r["label"]["use_tool"] for r in rows]
    p_yes = [noul_value(ans(r, "tool_gate")) for r in rows]
    lat = [r["response"].get("latency_ms") or r["response"]["_client_ms"] for r in rows]
    for thr in (0.3, 0.5, 0.7):
        pred = [p >= thr for p in p_yes]
        tp = sum(1 for t, p in zip(y_true, pred) if t and p)
        fp = sum(1 for t, p in zip(y_true, pred) if not t and p)
        fn = sum(1 for t, p in zip(y_true, pred) if t and not p)
        tn = sum(1 for t, p in zip(y_true, pred) if not t and not p)
        acc = (tp + tn) / len(y_true)
        rec_t = tp / (tp + fn) if tp + fn else float("nan")
        rec_f = tn / (tn + fp) if tn + fp else float("nan")
        print(f"  thr={thr}: acc={acc:.3f} recall(true)={rec_t:.3f} "
              f"recall(false)={rec_f:.3f}  tp={tp} fp={fp} fn={fn} tn={tn}")
    brier = statistics.mean((p - (1.0 if t else 0.0)) ** 2 for p, t in zip(p_yes, y_true))
    conf = [ans(r, "tool_gate").get("confidence") for r in rows]
    print(f"  brier(noul as P)={brier:.3f}  latency_ms med={statistics.median(lat)} "
          f"p95={sorted(lat)[int(0.95*len(lat))-1]}")
    for cls in (True, False):
        vals = [p for p, t in zip(p_yes, y_true) if t is cls]
        print(f"  noul class={cls}: n={len(vals)} mean={statistics.mean(vals):.3f} "
              f"min={min(vals):.3f} max={max(vals):.3f}")

    # dedup view by message text
    seen = {}
    for r, p, t in zip(rows, p_yes, y_true):
        key = r["id"].split("#")[0] + "|" + next(
            m["content"] for m in msgs if m["id"] == r["id"])
        seen.setdefault(key, []).append((t, p))
    if len(seen) < len(rows):
        dup_pred = [(statistics.mean(ps) >= 0.5, ts[0]) for ts, ps in
                    [([t for t, _ in v], [p for _, p in v]) for v in seen.values()]]
        acc = statistics.mean(p == t for p, t in dup_pred)
        print(f"  dedup-by-message n={len(dup_pred)} acc(0.5)={acc:.3f}")

    # choice demo on labeled subset (labels use verbose names; compare by id)
    svc_id_map = {"email search": "email", "workdrive file search": "workdrive"}
    have = [(r, ans(r, "service")) for r in rows if "service" in r["response"]["answers"]]
    svc_lab = [(svc_id_map[r["label"]["service"]], choice_pick(a)) for r, a in have if r["label"]["service"]]
    if svc_lab:
        top1 = statistics.mean(p == t for t, p in svc_lab)
        print(f"  service choice top1 (n={len(svc_lab)}): {top1:.3f}")
        for (t, p), r in list(zip(svc_lab, [r for r, _ in have]))[:12]:
            flag = "OK " if t == p else "MISS"
            print(f"    {flag} true={t:22s} pred={p}")

    print("\n=== Seam C: wobble/inability (n=%d) ===" % len(wrows))
    if wrows:
        wv = [(w["label"], noul_value(ans(w, "wobble"))) for w in wrows]
        pos = [v for t, v in wv if t]
        neg = [v for t, v in wv if not t]
        print(f"  positives n={len(pos)} noul mean={statistics.mean(pos) if pos else float('nan'):.3f}")
        print(f"  negatives n={len(neg)} noul mean={statistics.mean(neg):.3f} "
              f"max={max(neg):.3f}  frac<0.5={statistics.mean(v < 0.5 for v in neg):.3f}")
        for w in wrows:
            if w["label"]:
                a = ans(w, "wobble")
                print("  POS", w["id"], "noul=", a)

    (HERE / "eval_data" / "summary.json").write_text(json.dumps({
        "tool_gate": {"n": len(rows), "p_yes": p_yes, "y_true": y_true, "latency_ms": lat,
                      "state_mode": args.state_mode},
        "wobble": {"n": len(wrows), "values": wv if wrows else []},
    }, indent=1))
    print("\nraw + summary written to eval_data/")


if __name__ == "__main__":
    main()
