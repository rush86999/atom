# Agent Org Politics & Hierarchy — Integration Plan

> **Created**: Aug 22, 2026 · **Status**: ALL PHASES IMPLEMENTED (P0–P6)
> **Implemented**: P0 telemetry (`agent_org_events` + `core/org_telemetry_service.py` + wire-ins at recruit/radio/review; `scripts/org_dynamics_report.py`), P1 delegation contracts (`core/fleet_orchestration/delegation_contracts.py` wired into `_recruit_fleet` + conductor `_execute_step`; RACI `accountable_agent_id` field), P2 privilege axis (`core/org_privileges.py` + dispatch gate in `mcp_service.call_tool`; flag default OFF), P3 skill-scoped trust (`core/skill_scoped_trust.py` — shrinkage + laundering floor + fast-fail penalty + exploration boost; matcher integration flag-gated; `record_usage` stamps failures_verified/last_outcome_at), P4 contribution credit (`core/contribution_credit.py` — bucket-brigade γ=0.7, Σw=outcome delta, dampened-not-zeroed late failures; wired into `record_fleet_execution_outcome`; flag default OFF), P5 allocator integrity (`core/org_integrity.py` — self-dealing block wired in `_recruit_fleet`, coordinator rotation helpers, diversity floor shadow check, COI signal on link context; flag default OFF), P6 alignment sweep (`tests/e2e/multi_agent_alignment/` — 3 adversarial scenarios × 3 org structures, judge rubric unit-tested, double-gated nightly-only, cost-capped ≤400 tok/call).
> **Enforcement posture**: only P0/P1 are ON by default (additive telemetry + prompts). P2/P3/P4/P5 flags stay OFF until Phase 0 baseline accumulates and the P6 sweep passes — flip order: P3 shadow-diff → pilot → enforce; P2 audit → ON; P5 signals → calibrate.

## 7. Lifecycle automation (implemented)

The rollout is fully automated via `core/org_politics_automation.py` + `api/org_politics_routes.py` (`/api/v1/org-politics/*`, admin-gated), mirroring the stage/fleet-router consent pattern:

- **Modes** `ATOM_ORG_AUTO_ENFORCE` = off | notify | approve (**default**) | auto; cadence `ATOM_ORG_AUTO_INTERVAL_MIN` (default 1440 = daily). Background loop scheduled at app startup.
- **Escalation** (enable a flag) requires: P0 telemetry flowing (≥10 recruit events) AND a green alignment sweep. `approve` queues into `org_politics_actions` + notifies; `auto` applies immediately + notifies.
- **Revocation is always automatic** (every non-off mode): red alignment sweep (gap > 2.0) or ≥20 open COI pairs → immediate revoke + notification. Manual revoke endpoint too.
- **Flag resolution** for P2/P3/P5 live gates: explicit env kill-switch wins > latest applied/revoked action row > default off — flips take effect without restarts (60s TTL cache); an env var still restores prior behavior instantly. P4 remains env-only by design (per-execution supplement).
- **Sweep transport**: opencode-go cheapest-model convention when `ATOM_ALIGNMENT_SWEEP_ENABLED=true` + credentials present (~18 calls/night, ≤400 tok each); without it the pass reports `skipped_reason=sweep_disabled` and no escalation happens (fail-safe).
> **Scope**: Apply 2025–2026 research on agent organizations, hierarchy, and emergent "office politics" to Atom's fleet/meta-agent stack.
> **House rules**: every phase = TDD (failing test first), feature-flagged, shadow-first, kill switch, docs in `docs/architecture/`, no new auth surfaces without governance review.

---

## 1. Research Basis

| # | Finding | Source |
|---|---|---|
| R1 | Company-style hierarchy (governance → execution → compliance) beats flat MAS on quality AND cuts tokens 46–79% | [OrgAgent, arXiv 2604.01020](https://arxiv.org/abs/2604.01020) |
| R2 | Explicit delegation contracts (objective + output format + tool guidance + task boundaries) + effort-scaling rules are the top production levers | Anthropic orchestrator-worker engineering post |
| R3 | Accountability placement changes outcomes **only when the protocol routes the deliverable through the accountable agent**; org design must be learned/re-validated per model binding | [IMACS, arXiv 2607.25446](https://arxiv.org/html/2607.25446) |
| R4 | Separate **Permission** (what you can see/touch) from **Privilege** (what org-state changes you can authorize); Operation/Review/Supervision role separation; expiring leases; independent kill switch | [Fluid Structure, Rigid Record, arXiv 2608.08516](https://arxiv.org/html/2608.08516) |
| R5 | Multi-agent orgs are more effective but **less aligned** than single agents; misalignment amplifies with task decomposition and miscommunication; hierarchical/hub-and-spoke can drop below the Pareto frontier | [arXiv 2604.10290](https://arxiv.org/html/2604.10290) |
| R6 | Agents reproduce human governance failures: corruption when allocator roles carry rewards, extreme incumbency bias (first manager re-elected ~100% in homogeneous pools), honesty collapses under anonymity; fixes = term limits, transparency, model-family diversity | ["Politician/Liar/Obedient Worker", arXiv 2608.09574](https://arxiv.org/html/2608.09574) |
| R7 | Governance structure is a stronger driver of integrity than model identity; stress-test under governance-like constraints before granting authority | [Corruption in Multi-Agent Governance, arXiv 2603.18894](https://arxiv.org/html/2603.18894) |
| R8 | Trust must be **skill-scoped**, not global; empirical-Bayes borrowing across correlated skills helps but creates a reputation-laundering channel; bound cross-skill pooling | [Skill-Conditional Reputation, arXiv 2606.14200](https://arxiv.org/html/2606.14200v1) |
| R9 | Reputation updates should be slow-to-gain / fast-to-lose, with cold-start exploration weight, decay, and auditable ledgers | Agent Patterns Catalog: Trust & Reputation Routing |
| R10 | Marginal-contribution (Shapley-style) credit assignment aligns self-interested specialists; bucket-brigade backward value flow gives decentralized credit along a chain | Shapley-Coop; Economy of Minds (arXiv 2606.02859) |
| R11 | Internal credit markets allocate resources down an org chart with zero-profit intermediation (Google TPU market) | [Budget Descent, arXiv 2607.22159](https://arxiv.org/html/2607.22159) |
| R12 | Same-model/persona agents show in-group favoritism; leadership turnover only occurs in mixed-family groups → diversity is a governance requirement | Persona-Induced Bias (arXiv 2511.11789) + R6 |

---

## 2. Gap Analysis vs Atom Today

| Atom already has | Gap research exposes |
|---|---|
| Maturity tiers (STUDENT→AUTONOMOUS) gate *tool* access (#1, P2 capability bindings) | No distinct **privilege axis** for org-state changes (approve/promote/publish/grant) — R4 |
| Fleet recruitment via `SpecialistMatcher` + audit (#56) | Recruitment scores on the **global** `confidence_score`; per-capability stats exist in `CapabilityGraduationService` but don't feed matcher scoring, have no decay/asymmetry/exploration — R8/R9 |
| Delegation chains with max depth (#56) | Delegation payloads lack explicit contracts (objective/output-format/boundaries) — R2 |
| Reviewer re-delegation loop (#54) | Reviewer ≠ Accountable; no RACI tag routing the deliverable through one accountable agent — R3 |
| Outcome verification gates graduation (#35) | Credit for fleet runs is uniform per specialist; no marginal-contribution attribution — R10 |
| Agent Radio lateral messaging (#55) | Radio + allocator = deal-making surface (R6) with no firewall between social influence and selection |
| Shadow-mode validation pipelines (fleet router, stage router) | No multi-agent alignment sweep in e2e; fleets never tested for alignment drift — R5/R7 |
| Queen/Meta-agent prompts | Effort-scaling rules exist implicitly via stage router; delegation prompts unstructured — R2 |

---

## 3. Phases

### Phase 0 — Audit & Telemetry Baseline (no behavior change)
**Goal**: Measure current org dynamics before touching anything.
- Emit structured events for: who recruited whom (`fleet_routing_audit` join), radio thread participation vs subsequent recruitment decisions, reviewer accept/reject rates by agent pair.
- New append-only table `agent_org_events` (pattern: the G14 rating-boost ledger entries written into `AgentFeedback.ai_reasoning` — but as a proper table, not overloading that Text column): `(ts, run_id, event_type, actor_agent_id, target_agent_id, payload_json)` behind `ATOM_ORG_TELEMETRY_ENABLED` (default ON, append-only).
- Tests: event emission on recruit/radio/review paths; no PII in payloads.
**Deliverable**: baseline report script (`backend/scripts/org_dynamics_report.py`) — incumbency stats (same specialist recruited repeatedly?), reviewer favoritism index, radio-influence correlation. This is our version of R6/R12 measurement.

### Phase 1 — Delegation Contracts + Effort Scaling (R2)
**Goal**: Every fleet/conductor delegation carries a typed contract.
- `DelegationContract` dataclass in `core/fleet_orchestration/fleet_execution_models.py`: `objective`, `output_format`, `tool_guidance`, `task_boundaries`, `effort_budget` (max steps/tool-calls).
- Wire into `AtomMetaAgent._recruit_fleet` + `core/orchestration/conductor_agent.py`: contract rendered into specialist system prompt; effort budget enforced by existing sandbox caps (`ATOM_SANDBOX_MAX_TOOL_CALLS` path) rather than new machinery.
- Effort scaling rules table (complexity → expected specialist count/call budget) mirroring stage-router config style.
- Flag `ATOM_DELEGATION_CONTRACTS_ENABLED` (default ON — additive prompt/schema change).
- Tests: contracts present in recruited prompts; budget breach terminates worker; malformed contract fails closed to plain delegation.

### Phase 2 — Privilege Axis (Permission ≠ Privilege) (R4)
**Goal**: Split "can use tools" from "can change org state".
- New `org_privileges` set on AgentRegistry, stored inside the existing `configuration` JSON column (same home as `capability_maturities` — no migration needed; guarded batch DDL only if a dedicated column is later preferred): `approve_proposal`, `promote_agent`, `publish_skill`, `spawn_agent`, `grant_privilege`, `halt_run`.
- Default = empty (no org-state privileges) regardless of tier. Tier raises the *ceiling*; privileges grant specific rights inside it — two keys, not one.
- Enforcement point: same seam as P2 (`core/capability_resolver.py` + `integrations/mcp_service.call_tool`) extended with a privilege check before any registry action that mutates org state (HITL approve, graduation promote, marketplace publish).
- Expiring leases: privilege grants carry `expires_at`; renewal requires a fresh governance check (reuse `GovernanceCache` TTL pattern).
- Flag `ATOM_ORG_PRIVILEGES_ENABLED` (default OFF → ON after audit). Kill switch restores tier-only behavior instantly.
- Tests: agent with tier AUTONOMOUS but no privilege cannot publish/approve; expired lease rejected; lease renewal audited.

### Phase 3 — Skill-Scoped Reputation (R8, R9, R12)
**Goal**: Recruitment trust becomes per-capability, asymmetric, exploration-aware.
> **Verified codebase note**: Atom already has per-capability maturity — `CapabilityGraduationService` stores `capability_stats`/`capability_maturities` per capability in `AgentRegistry.configuration` (verified-gated, 5/20/50 thresholds). What is global-only is `AgentRegistry.confidence_score` (Float), and **that global value is what `SpecialistMatcher` scores on today** (`_W_CONFIDENCE * confidence`). P3 upgrades recruitment scoring, reusing the existing per-capability store — it does not invent a new one.
- Extend `SpecialistMatcher.find_specialists_for_domains` (core/specialist_matcher.py:174): replace the global-confidence term with `trust(agent, domain)` = empirical-Bayes shrunk Beta posterior built from `configuration.capability_stats[domain]` (and correlated domains via DOMAIN_ALIASES, coupling β≈0.1 — the paper's safe knee), plus a structural floor: zero direct evidence on the target domain caps borrowed score (laundering guard).
- Update asymmetry in `CapabilityGraduationService.record_usage`: success increments stay slow (+1 verified counter, unchanged); add fast-fail penalty (e.g., −0.05 trust on `failed_verification`) and time decay read-side; cold-start exploration term routes a small % of eligible tasks to unrouted capable agents.
- Data source: existing outcome joins (`byok_handler._record_outcome_feedback` → `fleet_routing_audit.success/actual_model`) already keyed per execution; join through `roster_json` for per-specialist outcomes.
- Flag `ATOM_SKILL_SCOPED_TRUST_ENABLED` (default OFF; shadow-compute alongside incumbent matcher first — log both picks into `fleet_routing_audit`, diff rate reported by Phase 0 script).
- Tests: shrinkage math property tests; laundering scenario (strong farm-skill record cannot lift unevidenced target past floor); asymmetric update; cold-start exploration bounded; graduation thresholds unchanged when flag off.

### Phase 4 — Marginal-Contribution Credit (R10)
**Goal**: Graduation inputs reflect contribution, not presence.
- On fleet completion, walk the delegation chain backward ("bucket brigade"): each step's outcome delta (verified by oracle #53 where available) yields a marginal contribution weight; store per-specialist weights in `AgentExecution` metadata.
- Feed weights into `capability_graduation_service` confidence updates (replaces uniform credit when available; falls back silently otherwise).
- Keep it deterministic (outcome deltas, not LLM judging) — Shapley estimation over LLM judges is explicitly out of scope for v1.
- Flag `ATOM_CONTRIBUTION_CREDIT_ENABLED` (default OFF; opt-in per workspace like radio teams).
- Tests: chain of 3 specialists → weights sum ≈ outcome delta; failure isolation (failed step doesn't poison upstream positive contributions); graduation unchanged when flag off.

### Phase 5 — Allocator Integrity Controls (R6, R7, R3)
**Goal**: Make the recruiter role incorruptible-by-construction, ahead of any autonomy expansion.
- Firewall: radio thread participation between candidate A and recruiting agent within N days is recorded and surfaced as a conflict-of-interest signal in `fleet_routing_audit` (shadow only — informs, never blocks, until calibrated).
- Rotation: coordinator/recruiter role per team rotates (config `config/lateral_teams/*.yaml` at repo root — `coding_team.yaml` exists today; add `coordinator_rotation: task|daily|fixed` key); no self-recruitment (an agent cannot select itself or an agent that selected it in the same run). Note: recruitment is migrating from `AtomMetaAgent._recruit_fleet` (core/atom_meta_agent.py:1880) to `RecruitmentIntelligenceService` — integrity hooks go in the service so both paths inherit them.
- RACI tag: workflow/conductor tasks gain optional `accountable_agent_id`; the deliverable's final review routes through that agent (extends #54 reviewer loop — IMACS's finding that accountability matters exactly when the deliverable routes through the accountable party).
- Diversity floor: when >1 model family is configured, recruitment candidates must span ≥2 families for teams ≥3 (R6/R12: homogeneous pools entrench incumbents). Two data sources verified: `AgentRegistry.diversity_profile` (strategy traits, already a column) and `fleet_routing_audit.actual_model/actual_provider` (outcome-join gives real model family per specialist).
- Flag `ATOM_ALLOCATOR_INTEGRITY_ENABLED` (default OFF; each sub-control independently toggleable).
- Tests: rotation produces different coordinators across runs; self-dealing blocked; COI signal emitted; RACI-routed review reaches accountable agent; diversity constraint respected/skipped when single-family.

### Phase 6 — Multi-Agent Alignment Sweep (R5, R7)
**Goal**: Fleets get the same alignment scrutiny as single agents.
- New e2e suite `backend/tests/e2e/multi_agent_alignment/`: fixed adversarial-task battery (the "AI consultancy" pattern: business-value pressure vs policy constraints) run across {single agent, fleet-hierarchical, fleet-flat} × {benign, red-teamed system prompts}.
- Scoring: utility + policy-violation rubric via existing judge infra (`core/llm/action_judge.py` pattern); assert fleet misalignment gap stays under threshold before any enforcement flip of Phases 3–5.
- Flag: test-suite only (no runtime flag); wired into CI nightly, not PR-gating initially.
- Tests: the suite itself; determinism via seeds; cost cap per run (opencode-go cheapest-model convention from env docs).

### Deferred / explicitly out of scope (v1)
- **Internal compute-credit market** (R11): interesting once multi-workspace spend exists; BPC/stage router already does cost steering. Revisit after Phase 0 telemetry shows real contention.
- **Agent elections** (R6): Atom coordinators are appointed by config, not elected — incumbency risk is low; revisit if teams become long-lived.
- **Talent-market packaging à la OMC**: Atom's marketplace + skills already cover ~70%; portable identity packages tracked as a marketplace roadmap item, not here.

---

## 4. Sequencing & Dependencies

```
P0 telemetry ──► P3 skill-trust (needs outcomes+audit join)
              └► P5 integrity (COI needs radio+recruit join)
P1 contracts ──── independent, ship first (cheapest win)
P2 privileges ─── independent; do BEFORE expanding any agent autonomy
P4 credit ──────► depends on P0 + oracle (#53) availability
P6 alignment ───► validates P3+P5 before their enforce flip
```

| Phase | Est. size | Risk | Rollout |
|---|---|---|---|
| 0 telemetry | S | Low (append-only) | ON default |
| 1 contracts | S | Low (prompt additive) | ON default, flag kill switch |
| 2 privileges | M | Medium (auth surface) | OFF → shadow audit → ON |
| 3 skill trust | M | Medium (routing change) | shadow-diff → pilot → enforce |
| 4 credit | M | Medium (learning signal) | opt-in per workspace |
| 5 integrity | M | Low (mostly guards) | shadow signals → enforce |
| 6 alignment suite | M | Low (test-only) | nightly |

## 5. Success Criteria
- Phase 0 report shows measurable baselines (incumbency rate, COI incidence, diff-rate for skill-trust) within 2 weeks of enablement.
- No regression in fleet task success (joined outcome rows) when Phases 3/5 flip to enforce.
- Multi-agent alignment gap (fleet vs single) quantified and under agreed threshold, or enforcement flips stay off (fail-safe, matching R7).

## 6. References
Full paper links in §1. Related internal docs: `docs/architecture/FLEET_ORCHESTRATION.md`, `docs/architecture/AGENT_RADIO.md`, `docs/architecture/ORACLE_VERIFICATION.md`, `docs/security/TRUST_VS_SANDBOX.md`.
