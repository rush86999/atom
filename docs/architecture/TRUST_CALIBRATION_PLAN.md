# Trust Calibration Gateway — Integration Plan (Ou-style GP)

> Status: **P0+P1+P2 IMPLEMENTED** (shadow recording live at both ask-paths; certification gate shipped as
> scripts/calibrate_trust_gateway.py). P3 enforcement relaxation is intentionally gated on: real HITL decisions
> accumulating through P1, a PASSING certification run on that production data, and explicit operator consent
> (off|notify|approve|auto). P4 (BOCPD changepoints, per-user posteriors) remains research-grade. Research grounding: Ou 2026,
> "Progressive Autonomy as Preference Learning: A Formalization of Trust
> Calibration for Agentic Tool Use" (arXiv 2605.19151) — a policy gateway
> maintains a Gaussian-process posterior over a latent human risk-tolerance
> function, observed through probit likelihood on **binary approve/deny
> feedback**, and escalates to the human exactly where the approval outcome
> is most uncertain. Non-stationarity via time-decay kernel; abrupt shifts
> via Bayesian online changepoint detection (future phase).
>
> **Orthogonal to the stage router (#58)**: stage router decides *which
> model tier runs a turn* from tool-result signals; the gateway decides
> *whether the human is asked* for a proposed action — separate layers
> sharing one deployment skeleton. Atom already implements Ou's
> deployment pattern everywhere but the inference (shadow → certify →
> per-workload enforce → consent-gated automation → auto-revoke; both
> #56 and #58 do this),
> and the GP version swaps the frequentist two-proportion certification
> for a posterior you can read uncertainty off directly.

> Complementary in-repo precedent: the stage-router and fleet-router
> validation automations already implement the discipline this gateway must
> follow — measure in shadow → certify on audit evidence → consent-gated
> enforce → automatic revoke. This plan reuses that pattern end-to-end.

## 1. Observation streams (already emitted — zero new instrumentation)

| Stream | Binary signal | Features available |
|---|---|---|
| `HITLAction` | approved / rejected | action_type, platform, params, agent_id, priority |
| `AgentProposal` (INTERN action proposals) | approved / rejected | proposed_action JSON, agent tier |
| Training proposal approve/reject (`/api/maturity/training/*`) | approve / reject | capability gaps, agent tier |
| Intervention service resolutions | approved/rejected outcomes | tool, workspace |

Excluded by design: star ratings (ordinal + noisy — handled separately by
the G14 rating nudge), execution successes/failures (not *human* decisions).

## 2. Decision points where escalation happens today

1. `generic_agent._step_act` — HITL pause for any action above the agent's
   maturity tier; escalates the whole class, every time.
2. `atom_meta_agent` Propose-Only — every complexity > 1 action confirms.
3. `integrations/mcp_service._check_hitl_policy` — tenant-flagged risky sends
   (auto-approve only for autonomous tier + tenant opt-in).
4. `selector_confidence` → `ProposalService` partial/ambiguous matches.
5. Automation approval queues (fleet-router / stage-router) — admin attention
   ordering only.

**Bounded false-allows (by construction)**
v* ≥ sn*² = base_noise/w*, so σ² has a noise floor — the ASK band
narrows as evidence concentrates but can never be starved below
base_noise; τ_uncertain (0.15) is set above the 0.05 floor.

**Applies**: gray-zone escalations inside already-authorized envelopes, and
attention allocation over pending approvals.
**Never applies**: complexity-4 CRITICAL actions (deletions/payments stay
human-or-AUTONOMOUS), the deterministic sandbox layer, budget enforcement,
or maturity promotion itself — the GP advises *where* to ask humans, it does
not expand what an agent may do.

## 3. Architecture

```
core/trust_calibration/
├── gp.py         # numpy probit-link GP over signed decisions; PRODUCT
│                 # kernel k_tool × k_ctx × k_time (per-block squared-
│                 # exponential, k_time = pointwise half-life decay
│                 # down-weighting stale evidence); noise folded as
│                 # base/w_i so stale points are noisier AND lower-scale;
│                 # predictive p(approve)=Φ(m*/√(1+v*))
├── features.py   # v1 vector: [complexity(1-4), tier_idx(0-3),
│                 #  is_destructive, platform_risk(0-2)]; tool-family
│                 #  one-hots as v2. Complexity resolution reuses
│                 #  AgentGovernanceService.ACTION_COMPLEXITY.
├── gateway.py    # TrustCalibrationGateway: fit-on-demand with TTL cache,
│                 # assess() -> {p_approve, uncertainty, recommendation}
│                 # recommendation ∈ allow | ask | block (three-tier;
│                 # default ask = fail-safe; never emits allow until
│                 # n_obs >= min and σ² below threshold)
└── service.py    # DB adapters: load_decisions(limit) over HITLAction +
                  # AgentProposal; persistence of assessments for outcome join
```

- Audit table `trust_calibration_assessments` (mirrors
  `llm_stage_router_audit`): features snapshot, predicted p/σ², decision
  context summary (never full params), and later the joined actual outcome.
- Flag `ATOM_TRUST_CALIBRATION_ENABLED` (**default false = off**). When on:
  shadow-only — assessments are recorded, no decision path changes.
- Read-only routes (admin-gated): `GET /api/v1/trust-calibration/{assess,stats}`.

## 4. Phases

### P0 — Spike (shadow, no behavior change)
Package + unit tests (monotonicity, uncertainty growth away from data,
time-decay dominance, empty-data prior → escalate, sqlite seeding from real
HITL/proposal rows) + assess/stats routes + this doc.

### P1 — Live shadow on the HITL path
Every HITL pause created in `_step_act` / `_check_hitl_policy` records an
assessment row; when the human resolves it, the outcome joins → live Brier/
ECE surfaced at `/stats`. Frontend: `MaturityApprovalPanel` sorts pending
items by escalation priority (pure attention allocation, zero risk).

### P2 — Certification before any enforcement
`scripts/calibrate_trust_gateway.py` backtest mirroring the fleet/stage
router gates: holdout Brier ≤ baseline (0.25 for always-0.5), denial-
coverage floor (% of would-be-denied actions correctly flagged), bin-wise
calibration. Readiness computed per workload (reuse
`resolve_agent_policy`-style precedence: env kill-switch > workspace config
> global). No enforcement until certified per-workload.

### P3 — Consent-gated relaxation (automation loop + P3 middleware hook)

Second enforcement surface: `middleware/governance_middleware.py` (the
outbound gatekeeper fronting every integration call) consults the gateway
for its HITL/mask decisions once certified — same allow/ask/block contract.
`off | notify | approve | auto` automation (mirror
`fleet_router_automation`) that may ONLY relax two things, never create new
autonomy: (a) meta-agent Propose-Only confirmations for feature clusters
with p_approve > 0.98 and σ² below threshold; (b) risky-send auto-approval
thresholds in `_check_hitl_policy`. Revocation is always automatic (drift in
Brier trend, or any relaxed action later judged wrong by oracle/user).
Small random exploration fraction keeps decision distribution honest during
certification (the gateway influencing approvals shifts the data otherwise).

### P4 — Non-stationarity upgrades
BOCPD changepoint on top of the decay kernel (paper §6); per-user tolerance
posteriors conditioned on user_id; per-task-domain routing of high-stakes
subtasks to agents with better track records (supervisor trust models).

## 5. Risks & guardrails

| Risk | Mitigation |
|---|---|
| Decision-farming (mass approvals teach permissive tolerance) | Trusted-user filter reuse (admin/specialty match), influence cap per user/day, ratings-style ledger markers |
| Feedback loop distorts training distribution | Exploration ε during shadow/certification; certification uses pre-shadow backtest window |
| Cold start over-trusting | Prior p=0.5 with wide σ² → recommendation = escalate_uncertain (fail-safe matches fail-closed posture) |
| Privacy of logged context | Assessments store feature vectors + summaries, never raw params |
| Alert fatigue / over-escalation | Escalate-at-max-uncertainty is exactly the paper's active-learning objective; τ thresholds tenant-tunable via governance metadata block (mirrors roles_map pattern) |

## 6. Env knobs (planned)

| Variable | Default | Purpose |
|---|---|---|
| `ATOM_TRUST_CALIBRATION_ENABLED` | `false` | Master switch; when true, SHADOW audits only |
| `ATOM_TRUST_CALIBRATION_HALF_LIFE_DAYS` | `30` | Kernel time-decay half-life |
| `ATOM_TRUST_CALIBRATION_MAX_OBS` | `400` | Most-recent observations used per refit |
| `ATOM_TRUST_CALIBRATION_REFIT_TTL` | `300` | Posterior cache seconds |
| `ATOM_TRUST_CALIBRATION_TAU_LOW` | `0.35` | p_approve below → **block** (confident denial, don't ask) |
| `ATOM_TRUST_CALIBRATION_TAU_UNCERTAIN` | `0.15` | variance above → escalate_uncertain |
| `ATOM_TRUST_CALIBRATION_EXPLORATION_EPS` | `0.02` | Random escalation fraction during shadow |

---
*Plan authored Aug 22, 2026 following the R81 journey verification; P0
implementation may proceed directly from §3.*
