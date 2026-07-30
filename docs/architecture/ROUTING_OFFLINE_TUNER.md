# Routing Offline Tuner (design)

> **Status: proposed.** This is a design document for a future offline
> weight-tuner. It is **not** wired into the live routing path. The live
> router (predictor + EMA blend + BPC) remains authoritative. See
> [LEARNING_LLM_ROUTER.md](./LEARNING_LLM_ROUTER.md) for the live system.

## Why

The live router adapts online (EMA + per-model predictors learn from each
feedback row), but its **weights** — the `{quality, cost, speed}` emphasis per
task type, the predictor confidence cap, the EMA smoothing factor, the BPC
cost-floor factor — are static defaults. Tuning those weights to a deployment's
actual traffic and model fleet is a multi-objective optimization over the
cost ↔ quality ↔ latency frontier. Research shows this pays off:

- **BOute** (MLSys 2026) co-optimizes routing + deployment via multi-objective
  Bayesian optimization → **38% avg cost reduction** at equal performance
  (up to 61%), or 59% avg throughput gain at equal cost.
- **Multi-Objective Hyperparameter Optimization for LLM/RAG** (arXiv 2502.18635)
  tunes system-level knobs across cost/latency/safety/alignment with a
  Gaussian-process surrogate + `qLogNEHVI` acquisition → superior Pareto front
  vs random/Sobol sampling.
- **OmniRouter** (KDD) frames routing as constrained optimization (minimize
  cost subject to per-query quality), learned from recorded
  (query, model, outcome) pairs.

The common thread: **replay observed outcomes** to evaluate candidate configs,
search the Pareto frontier (don't scalarize), warm-start from current weights,
and keep the search **off the hot path** — tune offline, deploy the resulting
weights, repeat on a schedule.

> **What this replaces:** the deleted `optimize_routing_configuration()` — a
> stub that returned four canned heuristics validated against *invented*
> estimates and wrote a result dict nothing consumed. This design is the
> version that actually adds value.

## Scope: what to tune (decision variables)

All are parameters the live router already reads, so the tuner writes results
back through existing mechanisms — no new hot-path code.

| Parameter | Where it lives | Range | Effect |
|-----------|----------------|-------|--------|
| `{quality, cost, speed}` weights per task type | `_router_cache` (via `_get_learned_weights` / `_set_cached_weights`) | each ∈ [0,1], sum = 1 | Base score emphasis |
| Predictor confidence cap | `PerModelRouter.confidence(max_weight=…)` | [0.1, 0.5] | How much the learned predictor steers vs the rule-based base |
| EMA smoothing factor | `ATOM_EMA_ALPHA` / `_ema_alpha()` | (0.05, 0.5] | Online-signal responsiveness vs stability |
| BPC cost-floor factor | `_EMA_SCORE_WEIGHT` / BPC pool-relative floor multiplier | [0.1, 1.0] | How strongly cheap/local models are preferred |

~5–7 continuous parameters per task type — small enough for Bayesian
optimization to be sample-efficient.

## Objectives (replayed from real observations)

Each candidate weight-set is scored by **replaying** a stratified sample of
recorded outcomes — **no live LLM calls**:

- **Satisfaction** (maximize): aggregate `success AND quality_satisfied` over
  the replayed rows, weighted by the candidate's predictor/blend. Source:
  `_preference_data`.
- **Total cost** (minimize): sum of `actual_cost` × routing-probability under
  the candidate weights. Source: `_ema_scores[...]["cost"]` + `_preference_data`.
- **p95 latency** (minimize): 95th-percentile `actual_latency_ms` under the
  candidate. Source: `_ema_scores[...]["latency"]`.

These three objectives are genuinely in tension (cheaper models cost less but
satisfy less); the tuner surfaces the **Pareto frontier** rather than collapsing
to one scalar.

## Method

**Primary: Gaussian-process MOBO with `qLogNEHVI`** (per arXiv 2502.18635 —
handles the noisy, non-deterministic nature of LLM outcomes via noisy
hypervolume improvement). Library: `botorch` + `ax`.

**Fallback (no new heavy dep): random-restart + Pareto-frontier search.** Sample
N candidate weight-sets (Sobol/random), evaluate each via replay, keep the
non-dominated set. Simpler than BO; BOute/OmniRouter show the win is mostly from
*using real observations + frontier search*, not from the surrogate specifically.
A good first iteration; upgrade to GP-MOBO once the replay harness is proven.

### Cold start & new models
- **Warm-start** from current defaults (`_get_learned_weights` + the documented
  defaults) so the first iteration doesn't pay the full exploration tax.
- **New models** have few observations → high surrogate uncertainty (BO) /
  naturally underexplored (random) → the acquisition function explores them
  first (the bandit/UCB property, OrcaRouter-style).

## Write-back (how it reaches live routing)

The winning weights are stored via the **existing** `_set_cached_weights`
mechanism — the same one `_retrain_router` uses to publish learned weights:

```python
router._set_cached_weights(
    cache_key=f"{tenant_id}:{task_type}",
    weights={"quality": q, "cost": c, "speed": s},
    tenant_id=tenant_id,
)
```

`_get_learned_weights` returns them on the next request. No change to
`_score_candidates` / `_rerank_with_learning` / the EMA loop. The tuned
predictor-cap / alpha / cost-floor are written to a small config that those
read at startup or via the existing env-var path.

## Cadence & guardrails

- **Offline batch only.** Nightly/weekly job, or an admin-triggered endpoint.
  Never per-request (routing-time budget is <10ms; GP evaluation is not).
- **Min-sample gate.** Skip a task type unless it has ≥ ~200 feedback rows
  (stratified). Below that, the online blend (EMA + predictor) already adapts
  and the tuner has too little signal — see the caveat below.
- **Never regress below baseline.** The deployed weights must not score worse
  on all three objectives than the current defaults; keep the baseline as a
  Pareto member and only replace if the candidate dominates.
- **Audit log.** Record each tuning run (params explored, frontier, chosen
  weights, objectives) so changes are reviewable/rollback-able.

## Honest caveat — when *not* to build this

The biggest win in the papers comes from **having enough observed outcomes to
replay**. This is a single-tenant app with sparse explicit feedback. If feedback
volume is thin (a few dozen rows per task type), the tuner has little signal and
the **existing online blend — which already adapts per-request — is the right
call**. The tuner pays off most once you've accumulated hundreds+ of feedback
rows per task type.

**Recommendation:** build the replay harness first (it's useful for observability
regardless — "what would the cost/quality/latency have been under different
weights?"). Add the BO search once feedback volume justifies it. Until then,
the live predictor+EMA blend is sufficient and matches production practice
(RouteLLM, OrcaRouter).

## Relationship to Arbor

Arbor (the hypothesis-tree framework) is **not** part of this design. Arbor is a
solution-space *refinement* tool (rank/prune candidate code diffs / workflow
steps); it is the wrong mechanism for weight-space optimization and adds
latency-irrelevant ceremony. The deleted stub used Arbor's `RoutingHypothesisNode`
purely as scaffolding that computed nothing real. If a tree search is ever wanted
for routing, it belongs in an **offline** config explorer — but BO is the
better-fit method here per the research.

## References
- [BOute: Cost-Efficient LLM Serving with Heterogeneous LLMs (MLSys 2026)](https://mlsys.org/virtual/2026/poster/3572)
- [Multi-Objective Hyperparameter Optimization for LLM and RAG Systems (arXiv 2502.18635)](https://arxiv.org/html/2502.18635v1)
- [OmniRouter: Budget and Performance Controllable Multi-LLM Routing (KDD)](https://kdd.org/exploration_files/p107_Omnirouter_camera_ready.pdf)
- [OrcaRouter: Production-Oriented LLM Router with Hybrid Offline-Online Learning](https://arxiv.org/html/2605.30736v1)
- [Efficient Tuning of Online Systems Using Bayesian Optimization (Meta Research)](https://research.facebook.com/blog/2018/9/efficient-tuning-of-online-systems-using-bayesian-optimization/)
- [RouteLLM (arXiv 2406.18665)](https://arxiv.org/html/2406.18665v4)
