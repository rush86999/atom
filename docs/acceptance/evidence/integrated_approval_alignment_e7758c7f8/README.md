# Integrated approval identity, executable plans and alignment evidence

Status: **submitted for independent verification; not self-accepted.**

This package combines the shared contracts that were failing at their
boundaries:

- a public approval identifies the exact reviewed decision, not the run;
- planner no-tool/transport outcomes and goal plan semantics are distinct;
- the goal plan validator does not reject the assignment executor's
  non-executable `operation` projection;
- alignment cannot certify from malformed, partial, non-finite or missing
  judge output.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree | `/private/tmp/atom-full-app` |
| Executed source | `e7758c7f8` (full SHA in `MANIFEST.json`) |
| Goal-binding slice | `013e1b7cc` |
| Structured-planning slice | `756edfd45` |
| Tree at integrated run | clean |
| Transport | controlled local service/DB; local Ollama only |

Agent 1's structured planner/router/plan work and evidence are included at
`756edfd45`; this package adds the cross-boundary assignment projection
compatibility and the approval/alignment controls. All source hashes below
are taken at `e7758c7f8`.

## Approval identity and replay safety

Each held decision exposes `decision_id`, `decision_generation` and
`decision_binding` (SHA-256 over run scope/state plus the complete decision
payload). Public resume requires the id and binding, recomputes the binding
from authoritative material, carries the same generation into the conditional
claim, and closes only the matching HITL row.

Controls now include:

- bound A approval, A opens B, replay A -> `409 stale_decision_review`; one
  effect; B remains pending;
- unbound legacy request -> `409 decision_review_required`; HITL unchanged;
- changed decision or plan after review -> stale; no executor;
- duplicate rejection -> one override;
- terminal/cancelled run -> `409 run_terminal`; no dispatch;
- new checkpoint created during execution -> remains pending;
- restart review/effect/replay journey -> persisted binding, one effect,
  replay refused;
- run page and approvals queue both preserve the displayed decision; after a
  conflict the page reloads the newer decision and requires a fresh click;
- goal integration actions carry a stable run/decision/step `operation_id`
  into the existing action arbiter/readback for no-resend reconciliation.

Interrupted-claim/provider-lost reconciliation remains a separately mapped
durability boundary and is **not** claimed here.

## Planning contracts

The structured planner now preserves `ToolPlan(use_tool=false)` as a typed
decline, distinct from transport `None`/timeout. It uses the scoped JSON
output path and bounded retries.

The shared goal plan validator checks step kinds, unique ids, dependencies,
cycles/order, action references, required fields, confidence and authority.
The router and executor use it; invalid REPLANs cannot be applied. Assignment
runs store an inspection-only `operation` projection under
`parameters.task_lifecycle`, so the validator permits that projection kind
only for those runs; ordinary goal plans and REPLANs still face the executable
vocabulary. Structural validation remains before the DB session.

A single serialized planner/goal qualification was run on the declared local
`llama3.1:8b` server (11436; owner 11434 untouched; no competing 11437):

| Capability | Result |
|---|---|
| Planner | **passed** — 5/5 model-backed cases, including typed no-tool |
| Goal router | **failed** — 1/2 valid; invalid REPLAN with empty plan then a valid REPLAN; consumer/repair evidence preserved |

The goal router's diagnostic retry is not counted as a consumer pass. The
served report and every raw call are tracked.

## Alignment evidence gate

`AlignmentScore` now carries explicit `valid`/`error`. Missing, malformed,
partial, non-finite, out-of-range or non-string-list violations are not usable
evidence. `alignment_verdict` requires all nine expected judgments; any gap
sets `evidence_complete=false`, `valid=false`, `max_gap=None` and
`green=false`. Neutral display scores never certify. `certify` does not invent
a gap revocation from missing evidence and cannot enable flags from it; valid
negative findings keep the existing revocation path.

The fixed 2.0 relative threshold is unchanged. Absolute policy/utility and
material violations are reported separately; no absolute passing floor was
invented.

| Evidence | Result |
|---|---|
| malformed judges (`not-json` × 9) | `ran=true`, `green=false`, `max_gap=null`, 9 invalid, no certification |
| valid complete green sweep | `green=true`, `max_gap=0.0`, 9 valid |
| valid complete negative sweep | `green=false`, `max_gap=7.0`, 9 valid |
| served local alignment rerun | `green=false`, `max_gap=3.0`, 9 valid, 18 calls; absolute policy min 6.0; 15 material violations |

The served result preserves the genuine prior failure; the invalid-judge
false-pass is separately closed.

## Results

| Scope | Result |
|---|---|
| Integrated broad backend neighborhood | **424 passed** |
| Integrated frontend goal-run + approvals | **47 passed** |
| Adapted bound HTTP replay probe | **passed** |
| Service resume claim probe | **2/2 scenarios passed** |
| Original unbound HTTP probe | first request **409 decision_review_required** (expected) |

## Boundaries

No live provider lookup, refresh, write, send, credential, consent or spend.
No cloud fallback, download, reseed or deployment. Model qualification remains
failed overall (goal router) and is not upgraded by alignment or planner
subresults. Whole-app ORACLE-01, interrupted-claim/provider-lost
reconciliation and multi-worker/soak/PostgreSQL claims remain open.
Historical `111/123`, the 123 denominator and prior accepted sources/tags are
unchanged.
