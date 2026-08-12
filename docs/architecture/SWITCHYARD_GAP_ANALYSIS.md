# Switchyard Gap Analysis + Stage Router Implementation

> **Status**: Analysis complete (Aug 2026); stage router implemented in
> shadow-first v1 on the agent path. See `CLAUDE.md` #58 and the env-var
> block for flags. Live engineering is tracked in git history.

## 1. What Switchyard is

[NVIDIA-NeMo/Switchyard](https://github.com/NVIDIA-NeMo/Switchyard) is a Rust
LLM proxy: protocol translation (OpenAI Chat / Anthropic Messages / OpenAI
Responses), multi-backend routing (random / LLM-classifier / stage-router /
escalation / custom), and Prometheus metrics. Its routing algorithms are
documented in `docs/routing_algorithms/*.md`.

## 2. Gap analysis vs Atom

Atom already had a substantially larger routing stack (cognitive tier system,
cache-aware router, escalation manager, learning LLM router, BPC registry
routing, LLM gateway with wire-format translation). The genuine gaps:

| Gap | Value | Recommendation | Status |
|---|---|---|---|
| Stage-router (signal-driven turn routing) | High, workload-fragile | Build shadow-first + calibrate | **Implemented (v1)** |
| Weighted-random A/B split | Medium — it's the *measurement* tool | Build as the calibration harness | **Implemented** |
| Escalation handoff notes | Low-Med | Bolt onto tier switches | **Implemented** |
| OpenAI Responses API (`/v1/responses`) | High for gateway compat, zero internally | Gate on an external client asking | Not started |
| Routing transparency headers | Low | Skip — Atom's DB audit supersedes | Skipped |

## 3. Value evidence (citations)

**For routing** (the cost-win premise):
- FrugalGPT (arXiv:2305.05176) — LLM cascades match GPT-4 at up to **98% cost
  reduction**, or +4% accuracy at equal cost.
- RouteLLM (arXiv:2406.18665) — routers cut cost **>2× without quality loss**;
  routers transfer across model pairs.
- Hybrid LLM (ICLR 2024, arXiv:2404.14618) — difficulty router: **40% fewer
  large-model calls, zero quality drop**, tunable quality/cost knob.
- Route-and-Reason (arXiv:2506.05901) — *turn-level* (below request-level)
  routing cut costs **84.46%** — the strongest support for stage routing.
- InferCept (arXiv:2402.01869) — mid-run interception is a real efficiency
  lever (37–40% recompute waste in agent loops).
- Switchyard's own stage-router: SWE-Bench Pro Python-75 calibration,
  corroborative tanh scoring, decision-source taxonomy.

**Caveats** (why shadow-first + calibration):
- RouteGuard (arXiv:2608.07583) — routing gains on RouterBench collapse under
  workload-cluster resampling: the certified gain rested on **3 of 86
  workload cells**; on one benchmark the advisors were statistically
  redundant. Gains are real but **domain-fragile**.
- RouterBench (arXiv:2403.12031) — best routers still far from Oracle.
- Are More LLM Calls All You Need? (arXiv:2403.02419) — performance is
  non-monotonic in extra calls; gains depend on the difficulty mix.

## 4. Fork resolution: where the router lives

Two candidate seams were evaluated:

1. **`select_tier` / `generate_with_cognitive_tier` choke point**
   (byok_handler.py:2546) — architecturally the single tier-selection point
   for the agent path, but **`generate_with_tier` has zero live production
   callers**, and no tool-result history reaches it (Switchyard's stage router
   is meaningless without tool history — pure-chat workloads always fall open).
   → **Declined for v1**; documented as the future home if an agent path ever
   routes through `generate_with_cognitive_tier`.
2. **ReAct loop seams** (`generic_agent._react_step`,
   `atom_meta_agent._react_step`) — the only live paths that carry the
   tool-result history the signals are extracted from. → **Chosen.**
   Both loops accept the same hooks: `decide_for_history` + a model-type
   override (`fast`/`quality`); explicit model pins are never overridden.

## 5. Architecture

```
ReAct loop (generic_agent / atom_meta_agent)
  │  execution_history (Action:/Observation: blocks)
  ▼
core/llm/stage_router.py ── parse_tool_history ──► ToolOutcome[]
  │  extract_signals → severity / spinning / exploring / production_intensity
  │  _score → tanh(signed)  (one full signal ≈ 0.46 < 0.5)
  │  decide → override | dimensions | fall_open
  ▼
StageDecision (id, selected_group, applied_group, split_group,
               confidence, source, rationale, handoff_note)
  │
  ├─ shadow  : audit row only; model type untouched
  ├─ enforce : model type ← capable→"quality" / efficient→"fast";
  │            handoff note appended to system prompt on group switch
  └─ outcome join: byok_handler._record_outcome_feedback reads the
     decision id from a per-request contextvar carrier and writes
     success/quality/cost/latency/model/provider back onto the
     llm_stage_router_audit row (calibration data)
```

**Harness (calibration)**: `core/llm/routing/traffic_split.py` —
`ATOM_TRAFFIC_SPLIT` + `ATOM_STAGE_ROUTING_SPLIT` JSON weights force a
weighted-random arm (`WeightedRandomSplit`) per turn; the audit row records
both the router's would-have pick (`selected_group`) and what actually ran
(`applied_group`). With both arms observed per workload, `scripts/
calibrate_stage_router.py` computes the RESCUE/LOSS quadrants and recommends
per-workload `confidence_threshold` + picker before enforcement.

**Decision sources** (Switchyard taxonomy): `override` (critical error →
capable), `dimensions` (corroborative score ≥ threshold), `fall_open`
(ambiguous → picker default).

## 6. Flags (all default off — no behavior change without opt-in)

```bash
ATOM_STAGE_ROUTING_ENABLED=true         # master switch (default ON = shadow, audit-only; false = kill switch)
ATOM_STAGE_ROUTING_FORCE_ENFORCE=false  # true = live model-type override
ATOM_STAGE_ROUTING_PICKER=efficient_first
ATOM_STAGE_ROUTING_CONFIDENCE_THRESHOLD=0.5
ATOM_STAGE_ROUTING_WINDOW=3
ATOM_TRAFFIC_SPLIT=false                # A/B harness master switch (opt-in; forces traffic arms)
ATOM_STAGE_ROUTING_SPLIT=               # JSON weights, e.g. {"efficient": 0.7, "capable": 0.3}
ATOM_STAGE_ROUTING_SPLIT_SEED=          # optional int for reproducible splits
```

## 6b. When to flip each flag — and why

Operator guidance is also live at `GET /health/stage-router` (phase +
`next_action` + `why` per phase). The table is the same logic in prose:

| Flag | Turn on when | Why |
|---|---|---|
| `ATOM_STAGE_ROUTING_ENABLED=true` | **Now** (already default) | Shadow scoring is free: it measures every turn but changes nothing. Without it there is no data, so no later decision is possible. |
| `ATOM_TRAFFIC_SPLIT=true` + `ATOM_STAGE_ROUTING_SPLIT` weights | Anytime during shadow, **before** calibration | The harness forces known arms so the audit rows contain *both* sides of the comparison (would-have pick vs. what ran and its outcome). Calibration needs both arms; without the harness you only have the default arm's outcomes. |
| `scripts/calibrate_stage_router.py` | When ≥ 1 workload has **both arms** observed at sufficient volume (`GET /health/stage-router` reports this per workload: arm counts + the **minimum detectable gap** at current volume) | Calibration is a statistics problem, not a fixed turn count. Turns differ in task complexity, so "50 turns" is meaningless on its own: detecting a **10-point** success-rate gap needs ~200 outcome rows per arm (two-proportion z-test, 80% power), a 20-point gap ~50, a 5-point gap ~800 (the status endpoint computes this per workload). Ready = both arms observed AND volume enough to *see* the quality difference you care about. |
| `ATOM_STAGE_ROUTING_FORCE_ENFORCE=true` | Only after calibration **justifies it per workload** (RESCUE > LOSS at acceptable cost ratio) | Enforcing before calibration is the documented failure mode for rule/cascade routers: gains are workload-fragile, and the router is still far from Oracle (RouterBench, arXiv:2403.12031). Flipping it blind trades real quality for unmeasured savings. |
| `ATOM_STAGE_ROUTING_ENABLED=false` | Any time routing misbehaves | The kill switch restores the exact pre-stage-router loop instantly. |

**Why not everything-on from day one**: force-enforce before calibration means
routing live traffic on thresholds that were never certified for *your*
workloads — the exact scenario the shadow+calibration design exists to avoid
(FrugalGPT/RouteLLM/Hybrid-LLM prove the *potential* win; RouteGuard proves
the *per-workload* caveat). The traffic split is also deliberately off:
it *forces* model-type arms, which by definition changes live model selection —
it's a measurement instrument, not a default behavior.

### Per-workload control (every agent is at a different phase)

Readiness is per workload (`agent_id`), so enforcement must be too. The
status endpoint reports each workload's own phase
(`sufficiency.<agent_id>.phase`); control is two-layered:

| Control | Scope | Mechanism |
|---|---|---|
| `ATOM_STAGE_ROUTING_ENABLED` | All workloads (kill switch) | Env; false = nothing runs |
| `ATOM_STAGE_ROUTING_FORCE_ENFORCE` | Default policy for agents **without** their own config | Env; the "enforce everywhere" default |
| `configuration["stage_routing"]` on an agent | **That agent only** | JSON in `AgentRegistry.configuration`; `enforce` (bool) **overrides** the global default; `confidence_threshold`/`picker`/`window` are optional per-agent tuning knobs |

### Consent-gated automation (manages the "when to turn on" for you)

`core/llm/stage_router_automation.py` runs the calibration math on a
background cadence (`ATOM_STAGE_ROUTER_AUTO_INTERVAL_MIN`, default 60m) and
acts per mode (`ATOM_STAGE_ROUTER_AUTO_ENFORCE`, default `approve`):

| Mode | Certify verdict | Revoke verdict |
|---|---|---|
| `off` | nothing | nothing |
| `notify` | admin notification only | notification only |
| `approve` (default) | **queues an approval** + notification; config flips only after you approve via the API | applies immediately + notifies |
| `auto` | applies immediately + notifies | applies immediately + notifies |

**Safety rule: escalation requires consent, revocation does not.** A workload
whose capable arm regresses by `ATOM_STAGE_ROUTER_AUTO_REVOKE_GAP` is
automatically flipped back to shadow (fail-safe), then the admin is notified.

Management API (admin-gated, `/api/v1/llm/stage-router/*`):
- `GET /status` — full status incl. automation block (public read-only mirror at `/health/stage-router`)
- `GET /automation` — mode, cadence, last run, pending approval queue
- `POST /automation/run-now` — trigger a pass immediately
- `POST /automation/approve` / `POST /automation/reject` — decide a pending certification (`{"agent_id": "..."}`)
- `POST /automation/config` — runtime mode/interval override (env remains the durable source)

Every action persists in `stage_router_automation_actions` (verdict, mode,
state, arm-stats snapshot) and the admin gets an in-app notification
(`stage_router_certified` / `approval_needed` / `stage_router_revoked` /
`stage_router_ready`). The automation never touches `ATOM_STAGE_ROUTING_FORCE_ENFORCE`
— it writes per-agent `configuration["stage_routing"]`, so each workload
stays on its own certified schedule and the global flag remains the
operator's blanket default.

Manual per-agent override (when the automation is off or you want different
tuning than the pass recommends) — certify ONE agent, leave the rest shadowing:

```json
{
  "stage_routing": {
    "enforce": true,
    "confidence_threshold": 0.45,
    "picker": "capable_first"
  }
}
```

Precedence: per-agent `enforce` always wins over the global flag — an agent
with `"enforce": false` stays in shadow even when the global flag is on, and
a calibrated agent can go live while every other workload keeps collecting.
Audit rows record which layer made the call (`policy_source`:
`global`/`agent-config`) and the effective parameters, so calibration output
can be attributed to the exact policy that produced it.

## 7. Rollout plan

1. ✅ Harness first: weighted-random split + outcome-joined audit logging.
2. ✅ Signal extractors + scorer + decision logic (**default ON, shadow** —
   audit-only, model selection untouched; kill switch
   `ATOM_STAGE_ROUTING_ENABLED=false`).
3. ⏳ Calibration: collect rows per workload, run
   `scripts/calibrate_stage_router.py`, tune thresholds.
4. ⏳ Promote to live behind `ATOM_STAGE_ROUTING_FORCE_ENFORCE`; keep shadow
   logging on for continuous re-certification.

## 8. Fast-follows (not in v1)

- Gateway path (`GatewayService._resolve_route`) — per-api-key calibration;
  no workload concept there, low priority.
- LLM-based severity / DB `status_code` enrichment (v1 uses message markers).
- OpenAI Responses API (`/v1/responses`) — compat item, gate on an external
  client requesting it (OpenAI: "Responses is recommended for all new
  projects"; +3% SWE-bench, 40–80% cache-utilization improvement; Assistants
  API sunset Aug 26, 2026 — platform.openai.com/docs/guides/responses-vs-chat-completions).
- Routing transparency headers (`x-model-router-*`) — rejected; Atom's DB
  audit trail supersedes them.
