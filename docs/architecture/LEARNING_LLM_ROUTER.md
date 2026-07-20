# Learning-Based LLM Router

> **Last Updated**: July 12, 2026
>
> **Status**: Fully implemented and wired end-to-end. Flag-gated
> (`ATOM_LEARNING_ROUTER`, default **off**) — when off, behavior is identical
> to the rule-based Cognitive Tier System. When on, the router observes
> outcomes, collects feedback, and re-ranks model candidates using learned
> per-model satisfaction predictors.

## Why This Exists

### ❌ The Problem
Static, rule-based routing strategies (like Benchmark-Price-Capability) select models on fixed benchmark scores. However, they cannot adapt to real-world outcomes: if a model consistently refutes a task type, generates invalid schemas, or experiences latency spikes, the rule-based router continues selecting it.

### 🎯 The Impact
Probabilistic routing models can degrade during runtime due to API outages, API schema changes, or model drift. Blindly routing tasks based on static benchmark profiles increases API token costs and exposes multi-step workflows to cascade failures.

### 🛡️ Our Solution
A hybrid re-ranking system that combines:
1. **Per-Model Predictors (ML-driven)**: Sklearn estimators that predict user satisfaction based on prompt features, dynamically re-ordering the candidate pool as user feedback accumulates.
2. **EMA-Guided Protocol Routing (Metric-driven)**: A running Exponential Moving Average of latency, cost, and execution success, instantly routing traffic around outages or rate-limits without token overhead.

```
                ┌─────────────────────────────────────────┐
                │  POST /api/chat/message                  │
                │  (the LIVE chat endpoint)                │
                └─────────────────────────────────────────┘
                              │
                              ▼
                ┌─────────────────────────────────────────┐
                │  chat_orchestrator → LLMService          │
                │  → BYOKHandler.generate_response         │
                └─────────────────────────────────────────┘
                              │
                              ▼
                ┌─────────────────────────────────────────┐
                │  BPC: get_ranked_providers()             │  Rule-based
                │  (Benchmark-Price-Capability scoring)    │  candidates
                └─────────────────────────────────────────┘
                              │
                              ▼   (flag on + predictor exists)
                ┌─────────────────────────────────────────┐
                │  Learning Router: re-rank candidates     │  Learned
                │  via per-model satisfaction signal       │  re-order
                └─────────────────────────────────────────┘
                              │
                              ▼
                ┌─────────────────────────────────────────┐
                │  Fallback loop: try (provider, model)    │
                │  in ranked order until one succeeds      │
                └─────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
              ┌──────────┐        ┌──────────────┐
              │ success  │        │  failure     │
              └──────────┘        └──────────────┘
                    │                   │
                    ▼                   ▼
              ┌──────────────────────────────────────────┐
              │  _record_outcome_feedback (flag-gated)    │  Quality
              │  assess_response_quality(finish_reason,   │  assessment
              │    content, schema_error, exception)      │
              │  → record_feedback → DB + retrain         │
              └──────────────────────────────────────────┘
                              │
                              ▼
              ┌──────────────────────────────────────────┐
              │  PerModelRouter: trains one sklearn       │  The
              │  estimator per model_id from feedback     │  predictors
              │  (persisted as .pkl, restored on restart) │  accumulate
              └──────────────────────────────────────────┘
```

## Architecture

### Process-wide singleton (`core/llm/learning_router_registry.py`)

The keystone: the router holds in-memory state (per-model predictors, cached
weights, pending decisions) that **must** persist across requests for learning
to accumulate. `get_learning_router_instance()` returns a process-wide
singleton — first call instantiates and hydrates preference data from the DB
(`load_feedback_from_db`). Persisted per-model predictors are restored lazily
from disk (`PerModelRouter.load_all()`) on first access per tenant/task key
(inside `_get_per_model_router`). Subsequent calls return the same object.
Double-checked locking for thread safety.

Without the singleton, every call constructed a throwaway router and predictors
were trained and immediately garbage-collected — the engine was inert.

### Per-model predictors (`core/llm/routing/per_model_router.py`)

Model identity enters routing through **which predictor you query**, not
through a feature. `PerModelRouter` holds one small sklearn estimator
(RandomForest / LogisticRegression, CPU-only) per `model_id`. Each predictor
learns "for *this* model, do prompts like this satisfy users?". At route time,
each candidate model's predictor is queried for a satisfaction probability.

This solves the fundamental problem that a single classifier on prompt
features alone can't learn model selection — it can only learn "do prompts
like this satisfy users?" (which is task-level, not model-level). Per-model
predictors learn model-specific outcome patterns.

- `train(model_id, examples)` — fits an estimator; persists to
  `{model_path}/per_model/{model_id}.pkl` + a JSON sidecar.
- `predict_satisfaction(model_id, features)` — returns P(satisfaction) in
  [0,1], or `None` for cold start (no predictor → caller falls back).
- `confidence(model_id)` — a 0..0.3 blend weight scaling with sample count,
  so early noisy predictors don't dominate and a well-trained predictor
  meaningfully steers routing.

### Quality assessment (`core/llm/response_quality.py`)

`assess_response_quality` derives real outcome signals from observable
response characteristics, replacing dead placeholder fields
(`quality_satisfied` was always True; `user_satisfaction` always None):

| Signal | Source | `quality_satisfied` |
|--------|--------|---------------------|
| Truncation | `finish_reason == "length"` (previously never read) | False |
| Empty content | content is blank | False |
| Refusal | content starts with a refusal marker | False |
| Schema error | structured-output validation failed (`is_schema_err`) | False (API succeeded) |
| Exception | the API call raised | `success=False` |
| Normal | substantive, complete response | True, score 0.7–0.95 |

The score is a **graded heuristic proxy**, not a substitute for real user
feedback. It lets predictors learn "model X truncates long prompts" /
"model Y fails structured output" — far better than all-True placeholders.

### DB persistence (`LLMRoutingFeedback` + migration `20260711`)

Feedback write-throughs to the `llm_routing_feedback` table so learned data
survives restarts. On startup, the singleton hydrates from the DB. Columns:
`routing_result_id`, `tenant_id`, `task_type`, `model_id`, outcome booleans,
optional metrics, and `prompt_features` (the 10-feature vector, as JSON, so
training reproduces the exact features the decision used).

### Prompt-feature capture (train/serve consistency)

At route time, `_extract_request_features` computes a 10-feature vector
(log_tokens, token_bucket, task one-hots, has_code, has_numbers,
avg_word_length). The `routing_result_id` correlates each decision to its
features, so when feedback arrives, predictors train on the **same** features
used to make the decision — eliminating train/serve skew. Defense-in-depth
fallback: evicted/restarted ids degrade gracefully to task-level defaults.

## The flag

`ATOM_LEARNING_ROUTER=true` (default: off). When off:
- No router is instantiated (zero overhead — a cheap boolean check).
- The `/api/chat/feedback` endpoint returns 200 without recording.
- Model selection is pure BPC (identical to today).

When on:
- Outcome observation records every response (text, structured, streamed).
- Re-ranking fires once a predictor exists with enough data.
- The dashboard shows real stats.

The flag defaults off so enabling in production is a deliberate operational
decision. The system is designed to be safe to enable: cold start is a pure
no-op, every integration is best-effort (errors fall back to BPC), and the
re-rank only re-orders BPC's already-filtered list.

## The user journey

1. **User sends a chat message** → `POST /api/chat/message` → orchestrator →
   `LLMService.generate_completion` → `BYOKHandler.generate_response`.
2. **Model is visible**: the response carries `model` / `provider`, shown as a
   subtle badge on each assistant message (`ChatMessage.tsx`).
3. **BPC ranks candidates**, then the learning router re-ranks (flag-gated).
4. **Response succeeds/fails** → `_record_outcome_feedback` assesses quality
   and records feedback (automatic data flywheel).
5. **User gives feedback**: thumbs up/down + comment, or **regenerate**
   (implicit negative signal for the old response). POSTs to the live
   `/api/chat/feedback` carrying the model identity.
6. **Dashboard**: `/settings/routing` shows feedback samples, per-model
   success rates, and learning status.

## Key files

| File | Role |
|------|------|
| `backend/core/learning_llm_router.py` | `LearningBasedRouter`: route/score/retrain/feedback, `build_feedback` |
| `backend/core/llm/learning_router_registry.py` | The process-wide singleton |
| `backend/core/llm/routing/per_model_router.py` | Per-model sklearn predictors |
| `backend/core/llm/response_quality.py` | `assess_response_quality` (finish_reason/content/schema/exception) |
| `backend/core/llm/byok_handler.py` | Re-ranking + outcome observation hooks (generate/structured/stream) |
| `backend/integrations/chat_routes.py` | Live `/api/chat/feedback` + `/api/chat/routing-stats` endpoints |
| `backend/integrations/chat_orchestrator.py` | Threads model/provider to the response |
| `backend/core/models.py` | `LLMRoutingFeedback` ORM model |
| `backend/alembic/versions/20260711_add_llm_routing_feedback.py` | DB migration |
| `frontend-nextjs/components/GlobalChat/ChatMessage.tsx` | Model badge + feedback + regenerate |
| `frontend-nextjs/hooks/chat/useChatInterface.ts` | `handleFeedback` + `handleRegenerate` |
| `frontend-nextjs/pages/settings/routing.tsx` | Routing dashboard |

## EMA-Guided Protocol Routing (Round 48)

To address potential high-variance loops in pure LLM or ML-based routing, the router supports an optional **Exponential Moving Average (EMA)** protocol routing mode, enabled by setting the environment flag:

```bash
ATOM_EMA_ROUTER_ENABLED=true
```

### The Mechanism

When enabled, candidate re-ranking uses a running EMA of model execution performance rather than raw neural/voters predictors. For each `(tenant, task, model)` combination, the router tracks:
1. **Success rate** (based on quality verification and completion signals).
2. **Execution latency** (response speed).
3. **Token/execution cost**.

The fitness score is computed as:

$$S_{t+1}(m, k) = \alpha \cdot \text{Score}_t(m, k) + (1 - \alpha) \cdot S_t(m, k)$$

Where:
- $\alpha = 0.2$ is the smoothing weight prioritizing recent outcomes.
- $\text{Score}_t$ is calculated dynamically from weighted combinations of success, normalized cost, and normalized latency.

This provides zero-token overhead routing decisions based strictly on historical empirical evidence, optimizing overall workflow determinism.

## Relationship to the Cognitive Tier System

The two systems are complementary, not competing:
- **Cognitive Tier** (`cognitive_tier_system.py`): the live rule-based
  classifier. Picks the tier/complexity → BPC ranks candidates.
- **Learning Router** (`learning_llm_router.py`): the learned layer. Re-ranks
  BPC's candidates based on observed outcomes.

The learning router never replaces BPC's candidate filtering — it only
re-orders the already-approved list. This means the live pricing cache
(hundreds of dynamically-refreshed models) remains the source of truth for
eligibility, while the learning router decides the *order* based on what it
has learned works.

## Limitations (honest)

- **Quality is a heuristic proxy.** `assess_response_quality` catches
  truncation, empty/refusal, and schema failures — but it can't judge whether
  a substantive response is *correct* or *helpful*. Real user satisfaction
  (thumbs up/down, regenerate) is the strongest signal; the heuristic fills
  the gap automatically.
- **Single-provider setups yield 1 candidate.** Re-ranking needs ≥2 candidates
  to matter. If only one provider has a live key, the learning router has
  nothing to choose among (it logs a debug note; this is expected, not a bug).
- **CPU-only, lightweight.** All training/inference is scikit-learn (small
  RandomForest/LogisticRegression). Runs on any end-user laptop. Sub-50ms
  routing latency, sub-second retraining.

## EMA Protocol Telemetry & Administrative Dashboard

When `ATOM_EMA_ROUTER_ENABLED=true` is active, real-time performance telemetry is exposed via `GET /api/chat/routing-stats` and rendered visually in the administrative UI at `/settings/routing`.

**Exposed Telemetry Metrics**:
- **EMA Score**: Decayed overall suitability score combining success rate, latency, and cost.
- **Success Rate**: Exponentially decayed success ratio ($S_{t+1} = \alpha S_{\text{new}} + (1 - \alpha) S_t$).
- **Avg Latency (ms)**: Real-time execution response latency.
- **Avg Cost ($)**: Decayed average token expenditure per model call.

---

## References

- RouteLLM: Learning to Route (arXiv:2406.18665)
- [Cognitive Tier System](./COGNITIVE_TIER_SYSTEM.md) — the live rule-based router
- [LLM Service API](../api/LLM_SERVICE_API.md) — BYOKHandler / BPC algorithm
