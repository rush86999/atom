# Spike: StrandsAgents/strands-decider-2B-hobson-v19 vs real atom decisions (2026-10-01)

Offline eval of the 2B "system one" decision model against decisions recorded in
this repo's own data. No production code touched. Data: 4 real conversation dumps
(`docs/architecture/orchestration_migration/acceptance/fixtures/conversation_*.json`)
+ real intercepted planner calls in `backend/data/acceptance_worlds/learning_loop_01/`.

## Method
- **Seam B — tool gate (binary noul)**: 39 real user messages, hand-labeled by
  applying the `_PLANNER_SYSTEM` rubric verbatim (chat_tool_planner.py:450):
  31 "needs fresh data" / 8 "conversation is enough". 2×2 ablation over
  {message-only, message+context} × {compound, simple question phrasing}.
- **Service choice (5-way choice)**: same 39, labeled subset n=30 (email /
  workdrive / web_search / web_fetch / memory).
- **Seam C — wobble/inability (binary noul)**: 44 real assistant replies,
  mechanically labeled by the repo's own `_INABILITY_RE`
  (chat_orchestrator.py:733). Only 1 positive exists in recorded data.
- **Intent classification seam: dropped.** All 24 recorded CommandIntentResult
  labels in the shim capture are "conversational" — zero class diversity.
- Served locally on Apple silicon (managed arm64 CPython 3.12 + MPS), HTTP API,
  batched questions per state.

## Results

Tool gate — noul did NOT separate the classes in any of 4 configurations:

| config | P(noul) true-class mean | false-class mean | best acc | Brier |
|---|---|---|---|---|
| compound + context | 0.389 | 0.420 | 0.487 | 0.344 |
| compound + message-only | 0.434 | 0.359 | 0.795* | 0.288 |
| simple + context | 0.323 | 0.375 | 0.385 | 0.399 |
| simple + message-only | 0.351 | 0.329 | 0.538 | 0.366 |

*0.795 = class prior (always-yes); recall(false)=0.000 — degenerate.
No threshold separates the classes; both sit in a mushy 0.3–0.45 band.

Service choice — the one clear positive:

| config | top-1 |
|---|---|
| message + context | **0.800** (24/30) |
| message-only | 0.633 (19/30) |

With well-separated probabilities (e.g. 0.96 on an unambiguous email request).
Errors were email↔web_fetch and workdrive→email confusions.

Wobble: positives n=1 → uninformative (that one positive scored noul 0.586,
barely above 0.5; negatives mean 0.292, max 0.770). Direction right, evidence
insufficient. **This repo does not record wobble events with dialogue text** —
first fix if this seam ever matters: capture them.

Latency (local, per request incl. 1–2 questions): median 222–443 ms,
p95 253–683 ms depending on state length.

## Caveats
- n=39 messages (21 unique after dedup), single domain (machinery-quote
  workflow), labels hand-applied by one reviewer. A spike, not a benchmark.
- The tool-gate FAIL is not marginal — class distributions overlap almost
  completely — and matches the model card's own hard-task accuracy (0.505):
  deciding whether *context already contains* the answer requires reading the
  conversation, which is this model's stated weak spot.
- The service-choice WIN matches the card's real strength: picking among
  enumerable, typed options given the state.

## Verdict
Do not wire v19 in as the tool gate — it cannot make that call. The measured
fit for this repo is the **choice seam** (service/intent routing over typed
options, ~350 ms local). If pursued further, the path is the Apache-2.0
training recipe (retrain on atom's own decision logs — needs a CUDA GPU
rental; training on MPS is impractical), plus capturing wobble/intent events
with dialogue text so seams C/A become evaluable at all.
