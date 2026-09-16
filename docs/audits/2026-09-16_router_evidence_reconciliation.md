# Router Evidence Reconciliation — audit item 3

**Date:** 2026-09-16 · **Scope:** the learning router's persisted history
(`llm_routing_feedback`) and the claim that auto-activation rests on "~90
verdict rows".

**Reproduce:** `cd backend && ./venv/bin/python scripts/router_evidence_report.py --db data/atom.db`

This document corrects §5.4 of the incident audit. It does not change the
owner's requirement that activation is automatic: the question it answers is
what the activation threshold is *evidence of*, not whether it should fire.

---

## 1. The claim, and what is actually in the table

| Audit claim | Reconciled finding |
|---|---|
| "Re-ranking is now auto-active on ~90 verdict rows" | The table held **170 rows / 168 distinct generations** at 2026-09-16 12:40 UTC, growing at ~12 rows/h. The count is a moving snapshot, not a fixed sample. |
| Rows represent observed routing outcomes | True, but they are **100% automatic outcome observations**. No user-feedback row exists in this table (its only writer is `learning_llm_router._persist_feedback`); explicit thumbs feedback lands elsewhere. "Verdict rows" in the audit conflates auto observations with verdicts. |
| History is available for a trust decision | **Accrual was dead** from `9a4a2a774` until `76cc51bcd` repaired a latent `TypeError` in the `assess_response_quality` call. Zero rows were written in that period. Every row in the table postdates **2026-09-15 22:24 UTC**; the window is **14.2 h** of one incident's own traffic. |
| The bench reads verdict-flagged rows | **0 of 170 rows carry any verdict provenance.** The corrective-signal channel that was supposed to stamp `{"verdict": ...}` into `prompt_features` is not present in any persisted row, so the fabrication bench cannot distinguish a fabrication verdict from any other low score. |
| — | **8 synthetic `probe/*` rows** were written by an earlier session's live verification and purged on 2026-09-15 ~18:40. They are correctly absent; no probe row remains. |

### 1.1 Independent generations vs feedback rows

- 168 distinct `routing_result_id` values for 170 rows ⇒ **2 generations were
  written more than once**:

  | routing_result_id | rows | models | satisfactions |
  |---|---|---|---|
  | `698bd079-…` | 2 | glm-5.3-flash, qwen3.8-flash | 0.0, 0.8 |
  | `ad1fa3e1-…` | 2 | glm-5.3-flash | 0.1, 0.1 |

  The first is a primary attempt plus a **fallback attempt** (correct: each row
  names the model that actually produced output). The second is a **pure
  duplicate** — one generation, two identical fabrication-band rows. Any rate
  computed over rows rather than generations is inflated or deflated by such
  duplicates.
- **67 rows (39.4%) carry `prompt_features = NULL`**, so training falls back to
  task-default features for them (train/serve skew). For `z-ai/glm-5.3-flash`
  it is 41 of 99 rows.

## 2. The 30-row threshold: readiness, not superiority

`learning_history_ready()` asks three questions: ≥30 rows in 7 days, ≥2 models,
≥8 observations each. On the current table that is satisfied (glm 99,
deepseek 35, qwen 34, gemini 2 — the last does not qualify at 8).

That is a statement about **statistical supply**, and nothing more. It does not
establish that re-ranking beats static BPC, and it cannot: the rows are outcomes
of the model BPC *already chose*, so there is no counterfactual. The correct
reading is:

> auto-activation is now *possible* under the documented rule; whether the
> learned order is *better* than static BPC remains untested.

## 3. Held-out evaluation (what can and cannot be concluded)

A time-ordered split (118 train / 52 holdout rows) with the explicit criteria —
**quality-satisfied rate, mean/p95 latency, cost per successful answer** —
produces:

- Learned order from train: `deepseek-v4-flash`, `qwen3.8-flash`, `glm-5.3-flash`
- Static cost-priority order: `deepseek-v4-flash`, `glm-5.3-flash`, `qwen3.8-flash`
- They **agree on the top model** and disagree only in ranks 2–3.
- On the holdout, `deepseek/deepseek-v4-flash-0731` is both the cheapest and the
  fastest by a wide margin (mean 9.6 s vs glm 22.7 s; $0.0016 vs $0.0116 for
  11 vs 25 answers) at 100% quality-satisfied.

The comparison is **inconclusive by construction**. The holdout contains only the
executed model's outcome; the alternative's outcome is *unobserved*. Logging a
"win" for the model that was never run would be exactly the fabrication class
this audit exists to remove. Certifying superiority requires either

1. an executed split (`ATOM_TRAFFIC_SPLIT`-style shadow routing with a persisted
   decision record), or
2. a persisted candidate-order log with counterfactual sampling.

### Recommended trust horizon (pending that evidence)

Keep automatic activation as-is. Do **not** promote the learned order to primary
until an executed comparison exists with pre-registered criteria
(quality-satisfied rate non-inferior at ±2 pp, p95 latency non-inferior, cost
per successful answer lower) over a representative task mix — the current window
is 3 task types, 110 of 170 rows in one `general` bucket.

## 4. Routing disagreements

Disagreements cannot be reconstructed retroactively: no component persists the
candidate ordering per decision, so the alternative's outcome is unknown. The
report emits the disagreement it *can* substantiate (train-top vs static-top)
and marks the alternative `unobserved`. A decision-order log is required to do
better; until it exists, disagreement counts in this document are lower bounds.

## 5. Consequences for audit item 2

The same query established two facts that the fabrication-bench correction must
respect:

1. The bench's rule (`user_satisfaction ≤ 0.15`) selects 4 rows, of which
   **0 carry a fabrication verdict** and **1 is availability-shaped** (a
   `success=0` provider exception scored 0.0). Availability failures were being
   counted as fabrication.
2. One of those 4 rows is a **duplicate write of a single generation**, so the
   bench's numerator and denominator can both be inflated for the same event.

---

## Appendix — generated report

# Router evidence — reconciliation

_Generated 2026-09-16T12:40:57.874730+00:00 by `backend/scripts/router_evidence_report.py`._

## 1. What the table actually holds

- **170 outcome rows** across **168 distinct generations** (4 models).
- Window: `2026-09-15T22:24:49+00:00` → `2026-09-16T12:39:24+00:00` (**14.24 h**, ~11.94 rows/h).
- Duplicate generations: **2** (2 excess row(s)) — one generation written more than once.
- Rows with **no stashed prompt features**: **67** (39.4%) → these train on task-default features.

### Provenance carried by the rows

| verdict | rows |
|---|---|
| `(none)` | 170 |

### The fabrication bench's selection rule, audited

Rule `user_satisfaction <= 0.15` selects **4** rows. Of those:

- **0** carry an explicit fabrication verdict.
- **4** carry no verdict at all.
- **4** are selected by the score threshold but are NOT provenanced as fabrication, of which **1** are availability-shaped (provider exception / empty output).

### Generations written more than once

| routing_result_id | rows | models | satisfactions |
|---|---|---|---|
| `698bd079-6116-46e8-85a9-1eff59f355c2` | 2 | qwen/qwen3.8-flash, z-ai/glm-5.3-flash | [0.0, 0.8] |
| `ad1fa3e1-cbe0-454d-9e78-09a1942e1a2f` | 2 | z-ai/glm-5.3-flash | [0.1, 0.1] |

A duplicated row inflates the bench's denominator and, when the duplicate is a fabrication verdict, its numerator — one generation must not be counted twice.

## 2. Observed outcomes by model

| model | rows | success % | quality-satisfied % | mean sat | mean ms | p95 ms | total cost | cost/success | no features |
|---|---|---|---|---|---|---|---|---|---|
| `z-ai/glm-5.3-flash` | 99 | 99.0 | 96.0 | 0.779 | 18099.184 | 35365.5 | 0.036254 | 0.00037 | 41 |
| `deepseek/deepseek-v4-flash-0731` | 35 | 100.0 | 100.0 | 0.809 | 12853.862 | 26052.4 | 0.005712 | 0.000163 | 18 |
| `qwen/qwen3.8-flash` | 34 | 100.0 | 100.0 | 0.837 | 18432.601 | 47459.7 | 0.048471 | 0.001426 | 7 |
| `google/gemini-3-flash-preview` | 2 | 100.0 | 100.0 | 0.7 | 1479.776 | 1487.7 | 0.001156 | 0.000578 | 1 |

## 3. Observed outcomes by task

| task | rows | models | quality-satisfied % |
|---|---|---|---|
| `general` | 110 | 4 | 99.1 |
| `extraction` | 54 | 2 | 100.0 |
| `question_answering` | 6 | 1 | 50.0 |

## 4. Held-out comparison vs static BPC

- Train 118 rows / holdout 52 rows (time-ordered split).
- Learned order from train (quality-satisfied desc): `['deepseek/deepseek-v4-flash-0731', 'qwen/qwen3.8-flash', 'z-ai/glm-5.3-flash']`
- Static cost-priority order: `['deepseek/deepseek-v4-flash-0731', 'z-ai/glm-5.3-flash', 'qwen/qwen3.8-flash']`

| model | holdout rows | quality-satisfied % | mean ms | total cost |
|---|---|---|---|---|
| `deepseek/deepseek-v4-flash-0731` | 11 | 100.0 | 9620.417 | 0.001644 |
| `google/gemini-3-flash-preview` | 1 | 100.0 | 1471.827 | 0.000577 |
| `qwen/qwen3.8-flash` | 15 | 100.0 | 12058.63 | 0.013967 |
| `z-ai/glm-5.3-flash` | 25 | 92.0 | 22724.659 | 0.011574 |

**Held-out comparison is INCONCLUSIVE by construction: the holdout contains only outcomes of the model that was actually executed. Certifying superiority over static BPC requires an executed split (ATOM_TRAFFIC_SPLIT-style) or a persisted candidate-order log with counterfactual sampling.**

## 5. Limitations (read before trusting a horizon)

- Rows are outcomes of the model BPC already chose (observational, not randomised): an unexecuted alternative has no known outcome and is reported as unobserved, never as a win or a loss.
- Accrual began only after the assess_response_quality TypeError was repaired, so the window is one incident's traffic, not a representative workload.
- prompt_features are NULL for rows written without a stashed decision id, so those rows train on task-default features (train/serve skew); see totals.rows_without_prompt_features.
- No decision log persists the candidate ordering, so routing disagreements cannot be reconstructed retroactively.
