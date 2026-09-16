# Router Evidence Reconciliation — audit item 3

**Date:** 2026-09-16 · **Scope:** the learning router's persisted history
(`llm_routing_feedback`), the claim that auto-activation rests on "~90 verdict
rows", and the evidence the trust-horizon decision would rest on.

**Reproduce:** `cd backend && ./venv/bin/python scripts/router_evidence_report.py --db data/atom.db`

**This revision** answers the external review of the previous revision of this
document. The review found four defects in it, all of which were real:

1. the "learned order" was an aggregate satisfaction ranking, not the learned
   router; the "static BPC order" was total historical spend, not BPC;
2. ranking by total spend is not a cost-efficiency ranking (spend tracks call
   volume);
3. savings were quoted from totals for different answer counts (11 vs 25
   answers were being compared);
4. the fabrication band counted ROWS where one generation can produce several.

The fix, the numbers, and a changelog of every claim removed or renamed are
below. §8 states plainly what this document still cannot substantiate.

**Read-only proof.** The script issues `SELECT`s only. Verified by digesting a
frozen copy of the live DB before and after full runs *including* the live
ranker A/B: `rows=379 data_digest=a15aabdcc9c115d0 file_digest=52ef37db743e0857
size=72376320` before and identical after, across repeated runs. (Importing the
application engine applies `PRAGMA journal_mode=WAL` on connect; on this
database that is already the mode, so it is a no-op — on a non-WAL file it would
change the journal mode, never data.)

**Snapshot, not a still image.** The table is being written while this document
was produced: 393 rows at 13:49:26, 399 at 13:50:10 UTC. Every number below is
the 2026-09-16T13:50:10 UTC snapshot, and the appendix is the verbatim stdout of
the command above on that snapshot.

---

## 1. Which fix was implemented

**The preferred one.** The report now imports and runs the ACTUAL router code
over an IDENTICAL candidate set:

- **BPC order** — `core/llm/byok_handler.py::BYOKHandler.get_ranked_providers`,
  called with the same `task_type`, the reconstructed `estimated_tokens`,
  `turn_index=0` and the documented defaults.
- **Learned order** — `core/llm/byok_handler.py::BYOKHandler._rerank_with_learning`
  applied to the very list BPC returned, exactly as `generate_response` does.
  That method can only permute, so the candidate set is identical by
  construction; the report asserts `same_candidate_set` on every run.

Request profiles are reconstructed from the request features the rows actually
persisted (`log_tokens = log2(tokens + 1)` is inverted), so both rankers see the
same features. Complexity is **not** persisted per row, so the A/B is swept over
the full complexity ladder and says so.

Result on this snapshot: **21 of 24 runs produced a different order, and 21 of 24
a different top candidate** — e.g. for a `general`/125-candidate request at
MODERATE, BPC's top is `gpt-5.3-codex-spark` while the learned re-ranker promotes
`deepseek/deepseek-v4-flash-0731` from rank 15 to rank 0.

**This is an ORDERING A/B, not an outcome A/B.** It shows what each ranker does
with the same candidates; it cannot show which order produces better answers,
because the alternative that was never executed still has no observed outcome.

The two descriptive statistics the old revision had mislabelled are kept, but
renamed to what they measure: `observed_satisfaction_ranking` and
`historical_spend_ranking`. Neither is called a router order anywhere.

## 2. What the table holds, and one data-quality finding

399 outcome rows over 398 distinct generations / 267 turns (129 model ids),
15.42 h of one incident's traffic. 67 rows (16.8%) carry no stashed prompt
features and therefore train on task-default features.

**129 of those rows are not outcomes of executed generations.** One turn
(`65ac1668-…`) carries one row per candidate model — 129 rows, 129 distinct model
ids, every row `success=false`, no recorded cost, all written between
13:42:04 and 13:42:19 UTC. A single turn cannot execute 129 models for free; the
shape is a candidate enumeration written into the outcome table. The report
detects this shape, reports it separately (§1.3 of the appendix), and excludes
those model ids from the A/B's "observed models" and from the reconstructed
request profiles. Attribution was not established — the report only proves that
*this script* did not write them; another process was writing to the table
throughout this work.

This matters beyond tidiness: those rows alone are 129 of the 132
"failed generations" and 129 of the 134 generations in the fabrication band.

### Fabrication accounting, per GENERATION

Delegated to `core/llm/fabrication_accounting.account_generations` — the single
ledger, not re-implemented here:

| quantity | value |
|---|---|
| rows | 399 |
| rows collapsed into an already-seen generation | 1 |
| malformed metadata rows | 0 |
| evaluated generations (denominator) | **264** (fabricated 0 + clean 264) |
| fabricated generations (numerator) | **0** → rate **0.0** |
| unprovenanced generations (UNKNOWN, excluded) | **134** |
| availability-classified generations (excluded) | 0 |
| rows carrying any `prompt_features.verdict` | **0** |

The bench's score rule (`user_satisfaction ≤ 0.15`) selects 135 rows = **134
generations**, of which **0** carry a fabrication verdict, **0** an availability
verdict, and **134** are unprovenanced. Those 134 stay **UNKNOWN — never clean,
never fabricated**: absence of provenance cannot establish absence of
fabrication. 132 of them are availability-shaped by the `success` flag, but that
is reported *beside* provenance, not as a substitute for it — and 129 of those
132 are the candidate-sweep rows above.

## 3. Cost per answer, with denominators

Total spend tracks how many calls a model received, so it is not a
cost-efficiency ranking. Every figure below is **total recorded spend / answered
generations**, and the denominator is printed with it. The numerator includes
failed attempts (they are billed); rows with no recorded cost are excluded and
counted.

| model | answered generations (denominator) | total recorded cost | cost per answer | rows without cost |
|---|---|---|---|---|
| `deepseek/deepseek-v4-flash-0731` | 48 | 0.007998 | **0.000167** | 1 |
| `z-ai/glm-5.3-flash` | 110 | 0.039107 | 0.000356 | 16 |
| `google/gemini-3-flash-preview` | 7 | 0.004051 | 0.000579 | 1 |
| `qwen/qwen3.8-flash` | 101 | 0.117643 | 0.001165 | 2 |

Per-answer saving: `deepseek/deepseek-v4-flash-0731` is **0.000998 per answer**
cheaper than `qwen/qwen3.8-flash` (0.000167 vs 0.001165) — **85.7%** of the
latter's per-answer cost, over **48 vs 101** answered generations. The totals
(0.007998 vs 0.117643) are deliberately NOT compared: those two models answered
different numbers of generations.

On the time-ordered holdout (279 train / 120 holdout rows) the same normalisation
gives `z-ai/glm-5.3-flash` **0.000215 per answer over 6 answers** vs
`qwen/qwen3.8-flash` **0.001175 per answer over 12 answers** (difference 0.00096
per answer, 81.7%). The old revision quoted "$0.0016 vs $0.0116 for 11 vs 25
answers" — a comparison of two totals over different answer counts, which is not
a saving.

## 4. Readiness, not superiority

`learning_router_registry.readiness_report()` on this snapshot: mode `auto`,
re-ranking **enabled: true**, readiness **true** — 399 observations in the
7-day window across 4 models with ≥8 observations each (thresholds ≥30 rows,
≥2 models, ≥8 observations per model).

> **Effective behaviour: readiness threshold met; no executed comparison.**

The threshold is a statement about statistical SUPPLY. It does not establish that
re-ranking beats static BPC, and it cannot: the rows are outcomes of the model
BPC already chose, so there is no counterfactual. The activation claim stands
unchanged; what it is evidence *of* is supply.

## 5. What the "learned" signal actually was in this run

Honesty about the A/B's own inputs: the per-model predictor buckets were **empty**
(`per-model predictor buckets []`) when the report ran, so the served learned
signal was the **EMA telemetry term** keyed `tenant:task:model` — the documented
cold-start handoff inside `_rerank_with_learning`. `ATOM_LEARNING_ROUTER` resolves
to `auto` from a DB row; `ATOM_EMA_ROUTER_ENABLED` resolves to `true` from the
catalog default.

This is not a defect in the comparison — it is what the router actually does —
but it means the A/B exercised the EMA path, not the per-model-predictor path.
Predictors persisted on disk (`data/router_models/per_model/*.pkl`) are loaded
only through `LearningBasedRouter._get_per_model_router`, which is called from
the retraining path; a freshly started process therefore serves EMA-only until a
retrain happens in-process. Whether the `.pkl` predictors would change this
ordering was not measured here.

## 6. Consequences for audit item 2 (the fabrication bench)

1. Zero rows in this table carry any verdict provenance (`verdict_counts = {}`),
   so the bench still cannot distinguish a fabrication verdict from any other
   low score on persisted history.
2. The bench's score rule selects 134 generations, none of them provenanced as
   fabrication; counting them as fabrication (or as "clean") would both be wrong.
3. One generation is written twice (a pure duplicate); one turn is written 129
   times (the candidate sweep). A row-based denominator is inflated by both —
   which is exactly why the accounting is now per generation.
4. The 129-row sweep is worse than noise for the bench: 129 fabricated-looking
   (score 0.0) generations attached to model ids that never ran. Any per-model
   fabrication rate computed over rows would blame 129 models for one process's
   enumeration.

## 7. Recommended trust horizon (unchanged)

Keep automatic activation as-is. Do **not** promote the learned order to primary
until an executed comparison exists with pre-registered criteria
(quality-satisfied rate non-inferior at ±2 pp, p95 latency non-inferior, cost per
answered generation lower) over a representative task mix — this window is 3 task
types with 263 of 399 rows in one `general` bucket, 129 of them the sweep above.

## 8. What could NOT be substantiated

Stated plainly rather than papered over:

1. **No superiority claim is possible from this data.** The holdout contains only
   the executed model's outcome. The report says INCONCLUSIVE by construction and
   requires an executed split (`ATOM_TRAFFIC_SPLIT`-style) or a persisted
   candidate-order log with counterfactual sampling.
2. **Per-decision complexity is not persisted**, so the A/B could not reproduce
   the complexity each historical decision used; it sweeps the whole ladder.
3. **The per-model-predictor path was not exercised** (empty buckets, §5). The
   A/B result is the EMA path's ordering.
4. **The writer of the 129-row sweep was not identified.** The report proves the
   shape and proves this script did not write it; it cannot name the producer
   from the table alone.
5. **The candidate-order log does not exist**, so retrospective disagreements
   cannot be reconstructed; §4's A/B is the live substitute.

## 9. Changelog — claims removed or renamed

| # | claim in the previous revision | action | why |
|---|---|---|---|
| 1 | `learned_order_from_train` — a train-slice aggregate satisfaction ranking, presented as "the learned order" | **REMOVED** as a claim; **RENAMED** to `observed_satisfaction_ranking` | the learned router is a per-request candidate re-ranker (per-model predictor + EMA telemetry), not an aggregate satisfaction table. The real re-ranker is now invoked (appendix §4) |
| 2 | `static_cost_priority_order` — total historical spend per model, presented as "the static BPC order" | **REMOVED** as a claim; **RENAMED** to `historical_spend_ranking` | BPC ranks a per-request candidate pool by value score with quality/latency/headroom filters; total spend measures workload volume. The real BPC is now invoked (appendix §4) |
| 3 | `cost_per_successful_answer` = total spend / rows with `success=true` | **REPLACED** by `cost_per_answer` with an explicit `answered_generations` denominator | one generation can be written as several rows; and spend tracks call volume, so rows are the wrong denominator twice over |
| 4 | savings quoted from totals across different answer counts ("$0.0016 vs $0.0116 for 11 vs 25 answers") | **REMOVED**; every saving is recomputed from cost per answer with both denominators printed | totals over different answer counts are not comparable |
| 5 | fabrication-band counts (`rows_in_band`, `misclassified`, `unprovenanced`) treated as if one row were one output | **REPLACED** by generation-level accounting via `core.llm.fabrication_accounting.account_generations` | one generation can produce an outcome row *and* a corrective-verdict row; dividing rows inflates the denominator |
| 6 | a low score with no verdict read as a fabrication/misclassification signal | **KEPT** as a selection band only; every unprovenanced generation is now reported as **UNKNOWN** — never clean, never fabricated | absence of provenance cannot establish absence of fabrication, nor its presence |
| 7 | "disagreements" reconstructed from two descriptive orderings | **REPLACED** by the live A/B of the two real rankers, with the alternative's outcome marked unobserved | the descriptive pair never was a router comparison |
| 8 | — (new) | **ADDED** `suspected_candidate_sweeps` data-quality block | 129 rows shaped like a per-candidate enumeration were inflating failures, model count and the fabrication band |

---

## Appendix — generated report

Exact stdout of:

```
cd backend && ./venv/bin/python scripts/router_evidence_report.py --db data/atom.db
```

# Router evidence — reconciliation

_Generated 2026-09-16T13:50:18.504763+00:00 by `backend/scripts/router_evidence_report.py`._

- Target database: `/Users/rushiparikh/projects/atom/backend/data/atom.db`
- Learned order: REAL learned re-ranker: BYOKHandler._rerank_with_learning over the candidate list BPC returned (see ranker_ab)
- Static order: REAL BPC: BYOKHandler.get_ranked_providers (see ranker_ab)
- Cost basis: cost per ANSWERED generation (total recorded spend / answers); every per-answer figure is printed with its denominator
- Fabrication basis: core.llm.fabrication_accounting.account_generations — per GENERATION, not per row

## 1. What the table actually holds

- **399 outcome rows** across **398 distinct generations / 267 turns** (129 models).
- Answered generations: **266**; generations with no successful attempt: **132**.
- Window: `2026-09-15T22:24:49+00:00` → `2026-09-16T13:50:10+00:00` (**15.42 h**, ~25.88 rows/h).
- Duplicate generations: **4** (132 excess row(s)) — one generation written more than once.
- Rows with **no stashed prompt features**: **67** (16.8%) → these train on task-default features.
- Rows with **no satisfaction score**: **0** (excluded from every score-based band, not read as 0.0).
- Rows belonging to a **suspected candidate sweep**: **129** over **1** turn(s), naming **129** model id(s) — see §1.3; these are NOT executed attempts and **129** of the failed-generation count comes from them.

### 1.1 Fabrication / quality accounting — per GENERATION

`core.llm.fabrication_accounting.account_generations`. The denominator is EVALUATED GENERATIONS, never rows. `unknown` is the unprovenanced residue: it is excluded from both terms and is **not** counted as clean.

- Evaluated generations (denominator): **264** (fabricated 0 + clean 264).
- Fabricated generations (numerator): **0** → rate **0.0**.
- Unprovenanced generations (UNKNOWN, excluded): **134**.
- Availability-classified generations (excluded): **0**.
- Rows collapsed into an already-seen generation: **1**; malformed metadata rows: **0**.

_Selection rule `user_satisfaction <= 0.15` (a score band, not a verdict):_

- Rows in band: **135** (0 row(s) carry no score at all).
- **Generations** in band: **134** — by provenance: {'unknown': 134}.
- Carrying an explicit fabrication verdict: **0**.
- Unprovenanced (**UNKNOWN**, not clean): **134**.
- Availability-shaped by the `success` flag (reported beside, not instead of, provenance): **132** = 129 from suspected candidate sweeps + 3 otherwise.

### 1.2 Accounting by model (generations)

_Models with fewer than 2 row(s) are summarised below the table, not listed (they are present in the JSON report)._

| model | rows | generations | fabricated | clean | unknown | availability | rate | malformed rows |
|---|---|---|---|---|---|---|---|---|
| `z-ai/glm-5.3-flash` | 114 | 108 | 0 | 108 | 5 | 0 | 0.0 | 0 |
| `qwen/qwen3.8-flash` | 103 | 101 | 0 | 101 | 2 | 0 | 0.0 | 0 |
| `deepseek/deepseek-v4-flash-0731` | 49 | 48 | 0 | 48 | 1 | 0 | 0.0 | 0 |
| `google/gemini-3-flash-preview` | 8 | 7 | 0 | 7 | 1 | 0 | 0.0 | 0 |
| _(omitted: 125 model(s) with < 2 row(s) — 125 row(s) total, all in the UNKNOWN column)_ | 125 | 0 | 0 | 0 | 125 | 0 | — | 0 |

_Omitted model ids: `gpt-5.3-codex-spark`, `glm-5.3-flash`, `glm-5.3`, `gemini-3-flash`, `deepseek-reasoner`, `deepseek/deepseek-reasoner`, `kimi-k2.5`, `deepseek/deepseek-v3.2`, `deepseek-v3-2-251201`, `gmi/deepseek-ai/DeepSeek-V3.2`, `hyperbolic/deepseek-ai/DeepSeek-V3`, `hyperbolic/deepseek-ai/DeepSeek-V3-0324` … (+113 more, full list in the JSON report)._

### 1.3 Suspected candidate sweeps (data quality)

- Rule: one turn with more than 5 distinct model ids, every row success=false, and no recorded cost.
- Turns: **1**; rows: **129**; distinct model ids named: **129**.
- **These rows cannot be outcomes of executed generations. They are reported separately and are NOT treated as observed attempts, answers or evidence about any model.**

| routing_result_id | rows | models | task types | first row | last row |
|---|---|---|---|---|---|
| `65ac1668-7d73-4762-9830-0ea3c6dfeac9` | 129 | 129 | general | 2026-09-16 13:42:04 | 2026-09-16 13:42:19 |

### Generations written more than once

| routing_result_id | kind | rows | models | satisfactions |
|---|---|---|---|---|
| `65ac1668-7d73-4762-9830-0ea3c6dfeac9` | candidate_sweep_shaped | 129 | azure_ai/DeepSeek-V4-Flash-0731, azure_ai/FW-DeepSeek-V3.2, azure_ai/FW-DeepSeek-V4-Pro, azure_ai/deepseek-v3 (+125 more) | [0.0, 0.0, 0.0, 0.0] … |
| `018b8866-b85b-4c22-b0ef-d92d4d5e196c` | multi_model_turn (primary + fallback attempts) | 3 | deepseek/deepseek-v4-flash-0731, qwen/qwen3.8-flash, z-ai/glm-5.3-flash | [0.0, 0.0, 0.7] |
| `698bd079-6116-46e8-85a9-1eff59f355c2` | multi_model_turn (primary + fallback attempts) | 2 | qwen/qwen3.8-flash, z-ai/glm-5.3-flash | [0.0, 0.8] |
| `ad1fa3e1-cbe0-454d-9e78-09a1942e1a2f` | pure_duplicate (same generation written twice) | 2 | z-ai/glm-5.3-flash | [0.1, 0.1] |

A duplicated row inflates any row-based denominator — one generation must not be counted twice.

## 2. Cost per answer (the only basis for a cost comparison)

Total spend depends on how many calls a model received, so it is NOT a cost-efficiency measure. `cost_per_answer` = **total recorded spend / answered generations**; the denominator is printed beside every figure. The numerator includes failed attempts (they are billed).

| model | answered generations (denominator) | failed generations | total recorded cost | cost per answer | mean ms/answer | p95 ms/answer | quality-satisfied % of answers | mean sat/answer | rows w/o cost |
|---|---|---|---|---|---|---|---|---|---|
| `z-ai/glm-5.3-flash` | 110 | 3 | 0.039107 | 0.000356 | 17219.214 | 35365.5 | 97.3 | 0.788 | 16 |
| `qwen/qwen3.8-flash` | 101 | 2 | 0.117643 | 0.001165 | 14407.56 | 35882.3 | 100.0 | 0.841 | 2 |
| `deepseek/deepseek-v4-flash-0731` | 48 | 1 | 0.007998 | 0.000167 | 13461.502 | 27393.7 | 100.0 | 0.807 | 1 |
| `google/gemini-3-flash-preview` | 7 | 1 | 0.004051 | 0.000579 | 1765.096 | 2476.4 | 100.0 | 0.7 | 1 |

_125 model id(s) have no answered generation, so no per-answer figure can exist for them (they appear only in suspected candidate sweeps or failed attempts): `gpt-5.3-codex-spark`, `glm-5.3-flash`, `glm-5.3`, `gemini-3-flash`, `deepseek-reasoner`, `deepseek/deepseek-reasoner`, `kimi-k2.5`, `deepseek/deepseek-v3.2`, `deepseek-v3-2-251201`, `gmi/deepseek-ai/DeepSeek-V3.2`, `hyperbolic/deepseek-ai/DeepSeek-V3`, `hyperbolic/deepseek-ai/DeepSeek-V3-0324` … (+113 more, full list in the JSON report)._

### Per-answer cost comparison

_Basis: cost per ANSWERED generation (total recorded spend / answers); floor 5 answered generations per side._

- Cheapest per answer: `deepseek/deepseek-v4-flash-0731` — **0.000167** per answer over **48** answered generation(s) (total recorded cost 0.007998).
- Priciest per answer: `qwen/qwen3.8-flash` — **0.001165** per answer over **101** answered generation(s) (total recorded cost 0.117643).
- Difference per answer: **0.000998** → `deepseek/deepseek-v4-flash-0731` is **85.7%** cheaper per answer than `qwen/qwen3.8-flash`.
- Totals are not compared: the two models answered different numbers of generations (48 vs 101); their raw totals differ by workload as much as by price, so only the per-answer figures are compared.
- No per-answer figure (no answered generation): `azure_ai/DeepSeek-V4-Flash-0731`, `azure_ai/FW-DeepSeek-V3.2`, `azure_ai/FW-DeepSeek-V4-Pro`, `azure_ai/deepseek-v3`, `azure_ai/deepseek-v3-0324`, `azure_ai/deepseek-v3.1`, `azure_ai/deepseek-v3.2`, `azure_ai/deepseek-v3.2-speciale`, `azure_ai/deepseek-v4-flash`, `azure_ai/deepseek-v4-pro`, `crusoe/deepseek-ai/DeepSeek-V3-0324`, `dashscope/deepseek-v4-flash` … (+113 more, full list in the JSON report).

## 3. Observed outcomes by task

| task | rows | generations | answered generations | models (with an answer) | quality-satisfied % of answers |
|---|---|---|---|---|---|
| `general` | 263 | 263 | 131 | 4 (of 129 ids present) | 100.0 |
| `extraction` | 123 | 123 | 123 | 2 (of 2 ids present) | 100.0 |
| `question_answering` | 13 | 12 | 12 | 1 (of 1 ids present) | 75.0 |

## 4. A/B of the ACTUAL rankers (BPC vs learned re-ranking)

_Status: **ok**._

- Method: real implementations: BYOKHandler.get_ranked_providers (BPC) vs BYOKHandler._rerank_with_learning (learned re-ranking) over the same candidate list.
- The learned re-ranker can only PERMUTE the list BPC returned, so both rankers see an identical candidate set; `same_candidate_set` is asserted per run below.
- Learned-signal provenance: mode `auto`, settings `{'ATOM_LEARNING_ROUTER': {'value': 'auto', 'source': 'db'}, 'ATOM_EMA_ROUTER_ENABLED': {'value': True, 'source': 'default'}, 'ATOM_FABRICATION_BENCH': {'value': True, 'source': 'default'}}`, per-model predictor buckets `[]`.
- Observed models (the 4 with at least one ANSWERED generation) — only these are ranked in the table below: `deepseek/deepseek-v4-flash-0731`, `google/gemini-3-flash-preview`, `qwen/qwen3.8-flash`, `z-ai/glm-5.3-flash`.
- `per_model` bucket predictions are only present after an in-process retrain; when the bucket is empty the served learned signal is the EMA telemetry term keyed `tenant:task:model` (the documented cold-start handoff in `_rerank_with_learning`).
- Inputs: `{"cognitive_tier": null, "complexity": "NOT persisted per row \u2014 swept over the full ladder", "estimated_tokens": "median of the persisted prompt features per profile", "is_managed_service": true, "max_quality": null, "observed_models": ["deepseek/deepseek-v4-flash-0731", "google/gemini-3-flash-preview", "qwen/qwen3.8-flash", "z-ai/glm-5.3-flash"], "prefer_cost": true, "profiles": [{"estimated_tokens": 968, "rows_with_these_features": 42, "task_type": "extraction", "token_bucket": 2.0, "tokens_max": 1995, "tokens_min": 505}, {"estimated_tokens": 55, "rows_with_these_features": 29, "task_type": "general", "token_bucket": 0.0, "tokens_max": 89, "tokens_min": 8}, {"estimated_tokens": 329, "rows_with_these_features": 29, "task_type": "extraction", "token_bucket": 1.0, "tokens_max": 495, "tokens_min": 100}, {"estimated_tokens": 2504, "rows_with_these_features": 28, "task_type": "extraction", "token_bucket": 3.0, "tokens_max": 2504, "tokens_min": 2213}, {"estimated_tokens": 1718, "rows_with_these_features": 28, "task_type": "general", "token_bucket": 2.0, "tokens_max": 1955, "tokens_min": 1523}, {"estimated_tokens": 372, "rows_with_these_features": 16, "task_type": "general", "token_bucket": 1.0, "tokens_max": 374, "tokens_min": 370}], "prompt": "synthetic, length 4 x estimated_tokens (the re-ranker derives estimated_tokens = len(prompt) // 4)", "required_capability": null, "requires_structured": false, "requires_tools": false, "task_type": "from each profile", "tenant_id": "default", "tenant_plan": "free", "turn_index": 0, "workspace_id": "default"}`

| task | est. tokens | complexity | candidates | same set | orders identical | BPC top | learned top | top changed | BPC rank → learned rank (observed models) |
|---|---|---|---|---|---|---|---|---|---|
| `extraction` | 968 | SIMPLE | 91 | True | False | `minimax-m2.5` | `deepseek/deepseek-v4-flash-0731` | True | `deepseek/deepseek-v4-flash-0731`=3→0, `google/gemini-3-flash-preview`=-→-, `qwen/qwen3.8-flash`=24→1, `z-ai/glm-5.3-flash`=-→- |
| `extraction` | 968 | MODERATE | 98 | True | False | `minimax-m2.5` | `deepseek/deepseek-v4-flash-0731` | True | `deepseek/deepseek-v4-flash-0731`=4→0, `google/gemini-3-flash-preview`=-→-, `qwen/qwen3.8-flash`=25→1, `z-ai/glm-5.3-flash`=-→- |
| `extraction` | 968 | COMPLEX | 91 | True | False | `minimax-m2.5` | `deepseek/deepseek-v4-flash-0731` | True | `deepseek/deepseek-v4-flash-0731`=3→0, `google/gemini-3-flash-preview`=-→-, `qwen/qwen3.8-flash`=24→1, `z-ai/glm-5.3-flash`=-→- |
| `extraction` | 968 | ADVANCED | 2 | True | True | `qwen/qwen3.8-flash` | `qwen/qwen3.8-flash` | False | `deepseek/deepseek-v4-flash-0731`=-→-, `google/gemini-3-flash-preview`=-→-, `qwen/qwen3.8-flash`=0→0, `z-ai/glm-5.3-flash`=-→- |
| `general` | 55 | SIMPLE | 118 | True | False | `gpt-5.3-codex-spark` | `deepseek/deepseek-v4-flash-0731` | True | `deepseek/deepseek-v4-flash-0731`=17→0, `google/gemini-3-flash-preview`=95→1, `qwen/qwen3.8-flash`=5→3, `z-ai/glm-5.3-flash`=2→2 |
| `general` | 55 | MODERATE | 125 | True | False | `gpt-5.3-codex-spark` | `deepseek/deepseek-v4-flash-0731` | True | `deepseek/deepseek-v4-flash-0731`=15→0, `google/gemini-3-flash-preview`=102→1, `qwen/qwen3.8-flash`=5→3, `z-ai/glm-5.3-flash`=2→2 |
| `general` | 55 | COMPLEX | 118 | True | False | `gpt-5.3-codex-spark` | `deepseek/deepseek-v4-flash-0731` | True | `deepseek/deepseek-v4-flash-0731`=17→0, `google/gemini-3-flash-preview`=95→1, `qwen/qwen3.8-flash`=5→3, `z-ai/glm-5.3-flash`=2→2 |
| `general` | 55 | ADVANCED | 29 | True | False | `gpt-5.3-codex-spark` | `google/gemini-3-flash-preview` | True | `deepseek/deepseek-v4-flash-0731`=-→-, `google/gemini-3-flash-preview`=12→0, `qwen/qwen3.8-flash`=9→2, `z-ai/glm-5.3-flash`=5→1 |
| `extraction` | 329 | SIMPLE | 91 | True | False | `minimax-m2.5` | `deepseek/deepseek-v4-flash-0731` | True | `deepseek/deepseek-v4-flash-0731`=3→0, `google/gemini-3-flash-preview`=-→-, `qwen/qwen3.8-flash`=24→1, `z-ai/glm-5.3-flash`=-→- |
| `extraction` | 329 | MODERATE | 98 | True | False | `minimax-m2.5` | `deepseek/deepseek-v4-flash-0731` | True | `deepseek/deepseek-v4-flash-0731`=4→0, `google/gemini-3-flash-preview`=-→-, `qwen/qwen3.8-flash`=25→1, `z-ai/glm-5.3-flash`=-→- |
| `extraction` | 329 | COMPLEX | 91 | True | False | `minimax-m2.5` | `deepseek/deepseek-v4-flash-0731` | True | `deepseek/deepseek-v4-flash-0731`=3→0, `google/gemini-3-flash-preview`=-→-, `qwen/qwen3.8-flash`=24→1, `z-ai/glm-5.3-flash`=-→- |
| `extraction` | 329 | ADVANCED | 2 | True | True | `qwen/qwen3.8-flash` | `qwen/qwen3.8-flash` | False | `deepseek/deepseek-v4-flash-0731`=-→-, `google/gemini-3-flash-preview`=-→-, `qwen/qwen3.8-flash`=0→0, `z-ai/glm-5.3-flash`=-→- |
| `extraction` | 2504 | SIMPLE | 91 | True | False | `minimax-m2.5` | `deepseek/deepseek-v4-flash-0731` | True | `deepseek/deepseek-v4-flash-0731`=3→0, `google/gemini-3-flash-preview`=-→-, `qwen/qwen3.8-flash`=24→1, `z-ai/glm-5.3-flash`=-→- |
| `extraction` | 2504 | MODERATE | 98 | True | False | `minimax-m2.5` | `deepseek/deepseek-v4-flash-0731` | True | `deepseek/deepseek-v4-flash-0731`=4→0, `google/gemini-3-flash-preview`=-→-, `qwen/qwen3.8-flash`=25→1, `z-ai/glm-5.3-flash`=-→- |
| `extraction` | 2504 | COMPLEX | 91 | True | False | `minimax-m2.5` | `deepseek/deepseek-v4-flash-0731` | True | `deepseek/deepseek-v4-flash-0731`=3→0, `google/gemini-3-flash-preview`=-→-, `qwen/qwen3.8-flash`=24→1, `z-ai/glm-5.3-flash`=-→- |
| `extraction` | 2504 | ADVANCED | 2 | True | True | `qwen/qwen3.8-flash` | `qwen/qwen3.8-flash` | False | `deepseek/deepseek-v4-flash-0731`=-→-, `google/gemini-3-flash-preview`=-→-, `qwen/qwen3.8-flash`=0→0, `z-ai/glm-5.3-flash`=-→- |
| `general` | 1718 | SIMPLE | 118 | True | False | `gpt-5.3-codex-spark` | `deepseek/deepseek-v4-flash-0731` | True | `deepseek/deepseek-v4-flash-0731`=17→0, `google/gemini-3-flash-preview`=95→1, `qwen/qwen3.8-flash`=5→3, `z-ai/glm-5.3-flash`=2→2 |
| `general` | 1718 | MODERATE | 125 | True | False | `gpt-5.3-codex-spark` | `deepseek/deepseek-v4-flash-0731` | True | `deepseek/deepseek-v4-flash-0731`=15→0, `google/gemini-3-flash-preview`=102→1, `qwen/qwen3.8-flash`=5→3, `z-ai/glm-5.3-flash`=2→2 |
| `general` | 1718 | COMPLEX | 118 | True | False | `gpt-5.3-codex-spark` | `deepseek/deepseek-v4-flash-0731` | True | `deepseek/deepseek-v4-flash-0731`=17→0, `google/gemini-3-flash-preview`=95→1, `qwen/qwen3.8-flash`=5→3, `z-ai/glm-5.3-flash`=2→2 |
| `general` | 1718 | ADVANCED | 29 | True | False | `gpt-5.3-codex-spark` | `google/gemini-3-flash-preview` | True | `deepseek/deepseek-v4-flash-0731`=-→-, `google/gemini-3-flash-preview`=12→0, `qwen/qwen3.8-flash`=9→2, `z-ai/glm-5.3-flash`=5→1 |
| `general` | 372 | SIMPLE | 118 | True | False | `gpt-5.3-codex-spark` | `deepseek/deepseek-v4-flash-0731` | True | `deepseek/deepseek-v4-flash-0731`=17→0, `google/gemini-3-flash-preview`=95→1, `qwen/qwen3.8-flash`=5→3, `z-ai/glm-5.3-flash`=2→2 |
| `general` | 372 | MODERATE | 125 | True | False | `gpt-5.3-codex-spark` | `deepseek/deepseek-v4-flash-0731` | True | `deepseek/deepseek-v4-flash-0731`=15→0, `google/gemini-3-flash-preview`=102→1, `qwen/qwen3.8-flash`=5→3, `z-ai/glm-5.3-flash`=2→2 |
| `general` | 372 | COMPLEX | 118 | True | False | `gpt-5.3-codex-spark` | `deepseek/deepseek-v4-flash-0731` | True | `deepseek/deepseek-v4-flash-0731`=17→0, `google/gemini-3-flash-preview`=95→1, `qwen/qwen3.8-flash`=5→3, `z-ai/glm-5.3-flash`=2→2 |
| `general` | 372 | ADVANCED | 29 | True | False | `gpt-5.3-codex-spark` | `google/gemini-3-flash-preview` | True | `deepseek/deepseek-v4-flash-0731`=-→-, `google/gemini-3-flash-preview`=12→0, `qwen/qwen3.8-flash`=9→2, `z-ai/glm-5.3-flash`=5→1 |

- Runs where the two rankers produced different orders: **21/24**; runs where the TOP candidate changed: **21/24**.

**This is an ORDERING A/B, not an outcome A/B.** It shows what each ranker does with the same candidates and the same request features. It cannot show which order produces better answers: the alternative that was never executed still has no observed outcome. Certifying superiority requires an executed split (`ATOM_TRAFFIC_SPLIT`-style) or a persisted candidate-order log with counterfactual sampling.

| tenant:task bucket | per-model predictors served | EMA models served (with an observed answer) | EMA models total |
|---|---|---|---|
| `default:extraction` | *(none — cold predictor bucket)* | ['deepseek/deepseek-v4-flash-0731', 'qwen/qwen3.8-flash'] | 2 |
| `default:general` | *(none — cold predictor bucket)* | ['deepseek/deepseek-v4-flash-0731', 'google/gemini-3-flash-preview', 'qwen/qwen3.8-flash', 'z-ai/glm-5.3-flash'] | 129 |

## 5. Automatic activation: readiness, not superiority

- Mode `auto` → re-ranking enabled: **True**; readiness check: **True**.
- Observations in the 7-day window: **399**; models with >= 8 observations: **4** (thresholds: >=30 rows, >=2 models).
- Reported reason: _active — 399 observations across 4 models; re-ranking by fabrication/quality history_

_The readiness numbers come from a live re-query through the application engine at A/B time, so they can differ from the snapshot row count in §1 when the table is being written concurrently._

**Effective behaviour: readiness threshold met; no executed comparison.** The threshold is a statement about statistical SUPPLY. It does not establish that re-ranking beats static BPC, and it cannot: the rows are outcomes of the model BPC already chose, so there is no counterfactual. The activation claim stands; what it is evidence OF is supply, not superiority.

## 6. Held-out evaluation (observational)

- Train 279 rows / holdout 120 rows (time-ordered split).
- `observed_satisfaction_ranking` (DESCRIPTIVE: train-slice quality-satisfied rate desc — NOT the learned router): `['deepseek/deepseek-v4-flash-0731', 'qwen/qwen3.8-flash', 'z-ai/glm-5.3-flash']`
- `historical_spend_ranking` (DESCRIPTIVE: train-slice total spend asc — NOT BPC): `['deepseek/deepseek-v4-flash-0731', 'z-ai/glm-5.3-flash', 'qwen/qwen3.8-flash']`
- Orderings require >= 8 answered generations; excluded: `azure_ai/deepseek-v4-flash`, `dashscope/deepseek-v4-flash`, `dashscope/deepseek-v4-flash-0731`, `databricks/databricks-deepseek-v4-flash-0731`, `deepinfra/deepseek-ai/DeepSeek-R1-Distill-Llama-70B`, `deepinfra/deepseek-ai/DeepSeek-V3.2`, `deepseek-reasoner`, `deepseek-v3-2-251201`, `deepseek-v4-flash-free`, `deepseek/deepseek-reasoner`, `deepseek/deepseek-v3.2`, `fireworks_ai/accounts/fireworks/models/deepseek-v4-flash` … (+18 more, full list in the JSON report).

| model | answered generations (denominator) | quality-satisfied % of answers | mean ms/answer | total recorded cost | cost per answer |
|---|---|---|---|---|---|
| `deepseek/deepseek-v4-flash-0731` | 4 | 100.0 | 11835.697 | 0.000874 | 0.000218 |
| `google/gemini-3-flash-preview` | 2 | 100.0 | 1647.065 | 0.001138 | 0.000569 |
| `qwen/qwen3.8-flash` | 12 | 100.0 | 11436.477 | 0.014097 | 0.001175 |
| `z-ai/glm-5.3-flash` | 6 | 100.0 | 10474.027 | 0.001292 | 0.000215 |

_96 model id(s) in the holdout slice have no answered generation and therefore no per-answer figure: `azure_ai/DeepSeek-V4-Flash-0731`, `azure_ai/FW-DeepSeek-V3.2`, `azure_ai/FW-DeepSeek-V4-Pro`, `azure_ai/deepseek-v3`, `azure_ai/deepseek-v3-0324`, `azure_ai/deepseek-v3.1`, `azure_ai/deepseek-v3.2`, `azure_ai/deepseek-v3.2-speciale`, `azure_ai/deepseek-v4-pro`, `crusoe/deepseek-ai/DeepSeek-V3-0324`, `dashscope/deepseek-v4-pro`, `databricks/databricks-deepseek-v4-pro-0813` … (+84 more, full list in the JSON report)._

- Holdout cost per answer: `z-ai/glm-5.3-flash` **0.000215** over **6** answer(s) vs `qwen/qwen3.8-flash` **0.001175** over **12** answer(s) → difference **0.00096** per answer (81.7% of the higher per-answer cost).
- Totals are not compared: the two models answered different numbers of generations (6 vs 12); their raw totals differ by workload as much as by price, so only the per-answer figures are compared.

**Held-out comparison is INCONCLUSIVE by construction: the holdout contains only outcomes of the model that was actually executed. It can show that a model was EXECUTED and OBSERVED; it cannot establish that one model is SUPERIOR. Certifying superiority over static BPC requires an executed split (ATOM_TRAFFIC_SPLIT-style) or a persisted candidate-order log with counterfactual sampling.**

## 7. Limitations (read before trusting a horizon)

- Rows are outcomes of the model BPC already chose (observational, not randomised): an unexecuted alternative has no known outcome and is reported as unobserved, never as a win or a loss.
- An observational holdout can establish that a model was EXECUTED and OBSERVED; it cannot establish that one model is SUPERIOR.
- Accrual began only after the assess_response_quality TypeError was repaired, so the window is one incident's traffic, not a representative workload.
- prompt_features are NULL for rows written without a stashed decision id, so those rows train on task-default features (train/serve skew); see totals.rows_without_prompt_features.
- No decision log persists the candidate ordering per decision, so retrospective routing disagreements cannot be reconstructed; the A/B in section 4 evaluates the rankers LIVE over reconstructed request profiles instead.
- per-decision complexity is NOT persisted, so the ranker A/B is swept over the whole complexity ladder rather than reproducing the complexity each historical decision actually used.
- Cost per answer divides ALL recorded spend (failed attempts included, since they are billed) by the number of answered generations; rows with no recorded cost are excluded from the numerator and counted in rows_without_cost.

## 8. Changelog — claims removed or renamed

| claim | action | why |
|---|---|---|
| "learned_order_from_train" presented a train-slice aggregate satisfaction ranking as the learned router's order | REMOVED as a claim; RENAMED to `observed_satisfaction_ranking` | the learned router is a per-request candidate re-ranker (per-model predictor + EMA telemetry), not an aggregate satisfaction table; the real re-ranker is now invoked in the A/B (section 4) |
| "static_cost_priority_order" presented total historical spend per model as the static BPC order | REMOVED as a claim; RENAMED to `historical_spend_ranking` | BPC ranks a per-request candidate pool by value score, and total spend measures workload volume, not routing order |
| "cost/success" divided total spend by ROWS with success=true | REPLACED by `cost_per_answer` with an explicit `answered_generations` denominator | one generation can be written as several rows, and total spend depends on how many calls a model received |
| savings quoted from totals across models with different answer counts (e.g. a total for 11 answers vs a total for 25 answers) | REMOVED; every saving is recomputed from cost per answer with both denominators printed | totals across different answer counts are not comparable |
| the fabrication band's row counts (rows_in_band / misclassified / unprovenanced) as if one row were one evaluated output | REPLACED by generation-level accounting via `core.llm.fabrication_accounting.account_generations` | one generation can produce an outcome row AND a corrective verdict row; dividing rows inflates the denominator |
| a low score with no verdict counted as a misclassification/fabrication signal | KEPT as a selection band, but every unprovenanced generation is reported as UNKNOWN (never clean, never fabricated) | absence of provenance cannot establish absence of fabrication — nor its presence |

