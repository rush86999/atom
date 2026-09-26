# Decision Plane — Operator Guide

> Local calibrated classifiers (Ollaya sidecar) shadowing agent decisions.
> Status: telemetry live, enforcement OFF on all surfaces (see certification gates below).
> Plan history: `docs/architecture/OLLAYA_DECISION_PLAN.md`.

## What it is

Every agent judgment that is classification-shaped (route this? done yet? stuck?
allow this tool call?) gets a second opinion from a small local model
(`laya`, CPU, ~100–200ms warm, zero tokens, zero cost, no PHI leaves the host).
The second opinion is recorded next to the incumbent's pick. Nothing acts on it
until a surface certifies — that is the whole design: shadow → calibrate →
consent-gated enforce, mirroring the stage/fleet routers.

## Surfaces

| Surface | Incumbent | Shadow | Audit table | Gate to certify |
|---|---|---|---|---|
| intent | NLU route / IntentClassifier | `choice` chat/workflow/task | `decision_router_audit` | n≥30, agreement≥0.8, Brier≤0.25 |
| turn | fact extractor (LLM) | 5× `noul` (fact/on-task/done/pending/stuck) | `decision_turn_audit` | would-skip precision≥0.95 at coverage≥0.2 (facts join) |
| gate | sandbox policy | `choice` allow/ask/block + `risky` | `decision_gate_audit` | violation-join review (NOT raw agreement — sandbox default-allows) |

Unmapped NLU categories record as `nlu:<raw>` and never count as agreement.

## Flags (all default off / safe)

`ATOM_OLLAYA_ENABLED` (master) · `ATOM_OLLAYA_SHADOW_{INTENT,TURN,GATE}` ·
`ATOM_OLLAYA_GATE_SAMPLE_RATE` (0.1) · `ATOM_OLLAYA_TIMEOUT_S` (0.8 inline;
shadows use 30s) · `ATOM_OLLAYA_URL/MODEL` · `ATOM_OLLAYA_INTENT_ACT_THRESHOLD`
(0.6) · `ATOM_DECISION_AUTO_ENFORCE` (off|notify|approve|auto) ·
`ATOM_OLLAYA_FORCE_ENFORCE` (env hard-switch — leave OFF until certified).

## Operator surfaces

- `GET /health/decision-router` (public): phase + counts + next action.
- `/api/v1/decision-automation/*` (admin): `status`, `automation`,
  `automation/run-now`, `automation/approve|reject {action_id}`.
- Scripts: `scripts/calibrate_decision_router.py`,
  `scripts/calibrate_turn_judgments.py [--join-facts]` (exit 0 ready / 2 hold).

## Runbooks

**Enable shadows (dev):** set the master + surface flags, restart backend
(no `--reload` — use `scripts/restart_backend.sh`), warm the sidecar
(`ollaya run laya --preset triage ...`), confirm rows via the health endpoint.
**Certify intent:** drive traffic to n≥30 → calibrator READY → automation pass
creates a `certify` approval (approve mode) → admin approves → resolve flips.
**Regression:** automation auto-revokes on failing stats in ANY mode; kill switch
is `ATOM_OLLAYA_ENABLED=false` + restart. Revocation beats certification.
**Cold starts:** model load is ~2s CPU; inline callers abstain below budget,
shadows ride it out. Production wants `OLLAYA_KEEP_ALIVE=30m` + warmup at boot.
Internal SSD only — the portable drive measured 3.5× slower cold loads.

## Known limits (do not regress)

- Small-model confidences run flat on hard calls (e.g. 0.14 floor on `block`);
  thresholds, not raw verdicts, carry the safety. Disagreements at low
  confidence are the system working, not failing.
- Gate telemetry samples 10% at a 0.5s budget; cold windows abstain (coverage,
  not completeness).
- Audit stores hashes + probabilities only — never raw text/args (PHI hygiene).
- Tables self-provision on first write (trust-calibration precedent); fresh
  surfaces read as `collecting`, not `error`.
- `IntentClassifier.classify_intent` had no live callers and a dead `.llm.call`
  path (fixed to `generate_completion`); the live intent seam is the NLU bridge.
