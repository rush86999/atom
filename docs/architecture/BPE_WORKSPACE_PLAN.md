# BPE Runtime Workspace Plan

**Status:** Phases 0–3 LANDED 2026-08-28, all gaps closed. AUTOMATED (2026-08-29): the whole subsystem self-regulates — consult gating auto-activates from recorded episode evidence (default AUTO; explicit env overrides), evolution auto-applies when the population has ≥3 distinct evaluated genomes with best fitness ≥0.25 (announced via `bpe.automation` spans), consolidation runs in the nightly sweep. Kill-switches: `ATOM_BPE_AUTOMATION=off` (master), per-subsystem `ATOM_BPE_CONSULT_POLICY` / `ATOM_BPE_EVOLUTION` tri-state. Flag-on pilot confirmed live (real agent run, value_ema recorded). workspace + meta-actions + flag-off shadow rendering (GenericAgent **and** AtomMetaAgent), consult policy (complexity + value EMA + annealing, flag-off shadow), note consolidation + nightly sweep, durable workspace persistence with restore-on-restart, harness-evolution telemetry feed, AlphaEvolve-lite population search over workspace bounds (proposal-only until `ATOM_BPE_EVOLUTION_ENABLED`). Remaining: live flag-on A/B rollout + golden-task eval (needs a running environment); Phase 4 trajectory distillation (research-gated).
**Source research:** EvoHarness-RL — "Learning Self-Evolving Runtime Harness for Long-Horizon LLM Agents" (Meta AI + UIUC, Aug 2026, [arXiv:2608.05446](https://arxiv.org/abs/2608.05446)); VentureBeat coverage: "Meta researchers taught an 8B AI model to match Claude Opus 4.5 — without the frontier price tag."
**Audience:** AI Engineers, Researchers
**Related docs:** [HARNESS_EVOLUTION.md](HARNESS_EVOLUTION.md) (offline patch mining), [AGENT_MEMORY_UNIFICATION_PLAN.md](AGENT_MEMORY_UNIFICATION_PLAN.md) (turn-time memory retrieval), [LEARNING_LLM_ROUTER.md](LEARNING_LLM_ROUTER.md) (EMA learned routing), [CONTEXT_MEMORY.md](CONTEXT_MEMORY.md) (turn facts)

---

## 1. TL;DR

Meta's EvoHarness-RL shows that the **harness — not the model — is trainable**: an 8B model (Qwen3-8B) given a *policy-facing external state workspace* (Belief / Progress / Experience) plus four meta-actions (`track`/`commit`/`recall`/`note`) reaches **96.9% on ALFWorld**, matching Claude Opus 4.5's ReAct score (96.4%) and beating GPT-5 ReAct (60.7%), SkillRL (89.9%), and SkillOS (80.2%).

Two findings are directly actionable for Atom **without any weight training**:

1. **The workspace interface alone is worth +8.5 pts for a small model and +22–26 pts for frontier models at prompt time** (GPT-4.1: 47.9→70.0; GPT-5: 60.7→85.0). Exposing structured Belief/Progress/Experience state to the agent — before any learning — is the cheap, immediate win.
2. **Frozen memory loses to learned consult policy.** Frozen-memory baselines (ExpeL, ReasoningBank applied frozen, MemP, ACE) score 49–56% vs 80–97% for methods that learn *when/how* to consult memory. Atom already has the memory substrate; what's missing is (a) a unified policy-facing workspace view and (b) a learned, cost-aware policy for consulting it.

This plan adapts the BPE (Belief, Progress, Experience) workspace to Atom's ReAct agents in four phases: workspace service → prompt-time meta-actions → learned cost-aware consult policy → background consolidation + harness evolution. A fifth, research-gated phase sketches trajectory distillation via the existing student/maturity pipeline.

---

## 2. Research Summary

### 2.1 The BPE workspace

At each step *t* the harness renders a policy-facing state **H_t = (B_t, P_t, E_t)**:

| Component | Content | Paper's grounding | Atom analog |
|---|---|---|---|
| **Belief (B_t)** | Persistent estimate of the environment: task-relevant facts, object/entity states, relations. Updated in the *background* after every step (rule-based parser in ALFWorld — no LLM call); only read on demand. | Edge capacity 48 | GraphRAG entities/edges, `business_facts`, VFS document state, canvas state |
| **Progress (P_t)** | Execution status as bounded subgoal records (subgoal, status). Updated **only when the policy commits**. | Cap: 8 subgoals | **Gap** — no per-conversation subgoal tracker today; `Objective.definition_of_done` is the partial precedent |
| **Experience (E_t)** | Cross-episode knowledge in 4 categories: general skills, task-specific skills, common mistakes, search priors. Actively consolidated (add/update/remove, LFU eviction) — **not append-only**. | 80 entries/category, recall returns top-3/category | `agent_experience` (LanceDB), skill registry, formula memory |

### 2.2 The four meta-actions

Unified action space: **A = A_env ∪ A_bpe**. Harness actions **consume the same step/budget as environment actions** — the agent must learn that consultation has a cost.

- `track[x]` — read belief (one entity, or a compact global summary)
- `commit[x]` — write a subgoal/status update to Progress
- `recall[q]` — retrieve from Experience (three query modes: what/where, how-to procedures, mistakes to avoid)
- `note[x]` — write a temporary insight; consolidated into Experience *outside the rollout loop*

### 2.3 Training recipe (for reference; not Phase 1–3 scope)

- **Stage 1 — SFT:** Claude Opus as teacher runs the same BPE interface on 500 training games; only successful episodes kept → 87 trajectories / 1,153 action pairs. Teacher made ~18% harness calls: commit 202, recall 114, note 55, track 34. Student (Qwen3-8B) fine-tuned on next-action prediction.
- **Stage 2 — Cost-aware GRPO:** reward `R = 10·1[solved] + λ_eff·R_eff + λ_div(u)·R_div − λ_spam·R_spam − λ_inv·R_inv`, where `R_eff = max(0, 1 − |τ|/70)` granted only on success (this is what makes consultation cost-aware), and λ_div anneals cosinely (explore the harness early, specialize late).

### 2.4 Dynamics worth copying

- **Harness annealing (policy-side):** during RL, harness-call frequency decays to ~1 call/episode; `recall` persists longest, `commit`/`note` decay toward zero. Routines get internalized; consultation becomes selective.
- **Harness evolution (harness-side):** Experience store is reshaped at epoch boundaries by a consolidator LLM (merge redundant entries, evict rarely-used) — "a compact, task-adaptive state substrate rather than passive append-only memory."
- **Environment adapter:** BPE is a *functional interface*, not a fixed schema. Domain-specific internals live behind the adapter; the coordination layer is shared. This is the pattern Atom should copy for chat vs. workflow vs. research surfaces.

### 2.5 Key numbers (ALFWorld, seen split, success rate)

| Method | Backbone | SR |
|---|---|---|
| ReAct | Qwen3-8B | 47.9% |
| EvoHarness-Base (prompt-time only) | Qwen3-8B | 56.4% (+8.5) |
| EvoHarness-SFT | Qwen3-8B | 68.6% |
| **EvoHarness-RL** | **Qwen3-8B** | **96.9% (+49.0)** |
| ReAct / +prompt-time BPE | Claude Opus 4.5 | 96.4% / 98.5% |
| ReAct / +prompt-time BPE | GPT-4.1 | 47.9% / 70.0% (+22.1) |
| ReAct / +prompt-time BPE | GPT-5 | 60.7% / 85.0% (+25.7) |
| SkillOS / SkillRL (trainable) | Qwen3-8B / Qwen2.5-7B | 80.2% / 89.9% |
| Frozen memory (ExpeL, ReasoningBank-frozen, MemP, ACE) | Qwen3-8B | 49.3–55.7% |

Unseen split: 50.0 → 77.6 (Base) → 69.4 (SFT) → **86.6** (RL). Ablations: removing Experience hurts most (56.4→48.6); Belief and Progress removal each cost ~6 pts; components act synergistically.

### 2.6 Related work landscape (2025–2026: "the harness becomes the object of evolution")

- [ReasoningBank](https://arxiv.org/abs/2509.25140) (Google) — memory of reasoning from successes *and failures*
- [SkillOS](https://arxiv.org/abs/2605.06614) — RL-learned skill curation (procedural memory)
- [SkillRL](https://openreview.net/pdf?id=56D2hjARkn) (ICLR 2026) — recursive skill-augmented RL
- [Harness-1](https://github.com/pat-jj/harness-1) — RL inside a stateful search harness
- Living-Harness, Evo-Harness, RewardHarness, [EvoTrainer](https://arxiv.org/abs/2606.03108) — training-side harness co-evolution

Consensus across the line: **the differentiator is learning when/how to consult state, not the memory content itself.**

### 2.7 Memento & AlphaEvolve — how the adjacent self-evolution lines slot in

**[Memento](https://arxiv.org/abs/2508.16153)** ("Fine-tuning LLM Agents without Fine-tuning LLMs", 2025) is the training-free learning counterpart to EvoHarness-RL's weight training: a case bank of past (task, trajectory, outcome) episodes, retrieval-based "memory reading", a *neural case-selection policy* deciding which case guides the current action, and environment-feedback-driven *memory rewriting* instead of gradient updates. Results: 79.4% GAIA test (top-1), +4.7–9.6 pts on out-of-distribution tasks. Mapping to this plan:

- Case bank ≈ the **Experience leg** — Atom's `agent_experience` + episodes already store the case fields; no new store needed.
- Neural case-selection ≈ the **Phase 2 consult policy**. Our EMA value scoring is the cheap v1; Memento's learned selector (a small scorer trained from outcome feedback, `RoutingFeedback`-style) is the upgrade path if EMA plateaus.
- Memory rewriting ≈ **Phase 3 consolidation** (add/update/remove, not append-only) — the paper independently validates the non-append-only posture.
- Key contrast: Memento learns *what to retrieve* (harness static); EvoHarness learns *when to touch the harness at all* (cost-aware, annealing). Phase 2 should treat consult-gating as primary and case-selection refinement as secondary.

**[AlphaEvolve](https://arxiv.org/abs/2506.13131)** (DeepMind) is the offline-evolution grandparent of the 2026 self-evolving-harness line (Living-Harness, Evo-Harness, EvoTrainer): population-based search over artifacts — LLM mutation proposals, an evaluator, and a MAP-elites-style evolutionary database keeping diverse high-fitness candidates. Mapping to this plan:

- It generalizes **Phase 3**: Atom's `harness_evolution_service` currently mines weaknesses → proposes *one* micro-patch → sandbox-validates. The AlphaEvolve upgrade treats the harness itself as a genome — BPE workspace params (subgoal cap, category set, recall mode, workspace-block template, consult thresholds) as evolvable genes — with fitness scored from episode outcomes + `bpe.*` telemetry spans, and a small population of candidate configs maintained per agent family.
- Atom already has the three prerequisites: mutation proposer (evolution services), evaluator (episodes + spans), validation gate (copy-write sandbox). What's missing is only the *population* (keep N candidate harness configs + fitness history instead of one winner) and diversity-bucketed selection.
- Cost posture: evolutionary search is rollout-hungry — keep it offline, narrow (workspace params + prompt patches only, never weights), small-N, and behind the same supervisor-approval gates as harness patches.

**Synthesis** — three "who evolves" layers, in increasing cost: (1) consult/memory policy, training-free (Memento; plan Phase 2); (2) the harness configuration (AlphaEvolve-style; plan Phase 3); (3) model weights (EvoHarness-RL GRPO; out of scope). The BPE workspace is the shared substrate all three act on — which is why it lands first.


---

## 3. Mapping to Atom (what exists, what's missing)

Exists and reusable:

- **Meta-action registry** — `backend/core/action_registry.py` (`@register_action`, `ActionDefinition` with preconditions) is the exact home for `track`/`commit`/`recall`/`note`.
- **Prompt injection points** — `GenericAgent._react_step` system-prompt build and `AtomMetaAgent._react_step`; a bounded `WORKSPACE` block slots beside the existing `RELEVANT MEMORY` block from `memory_context_assembler.py`.
- **Experience substrate** — `WorldModelService` (`agent_experience`, `business_facts`), skill registry, `recall_experiences` multi-leg recall, `assemble_memory_context` bounded blocks.
- **Turn-time write pattern** — fire-and-forget turn-fact extraction (`turn_fact_extractor.py`) is the established non-blocking write path for `note`.
- **Learned cost-aware policy precedent** — `LearningBasedRouter` (EMA quality/latency, `RoutingFeedback`), `stage_router` (signal→tier, shadow-first, A/B). The consult policy mirrors these.
- **Harness evolution precedent** — `harness_evolution_service.py` already mines `agent_reasoning_steps` failures into per-agent patches.
- **Consolidation precedent** — `memory_consolidation_service.py` (mem0-style ADD/UPDATE/INVALIDATE, nightly).

Missing (the gaps this plan fills):

1. **No unified policy-facing workspace view** — memory legs are assembled for the prompt, but there is no first-class (B, P, E) state object the agent acts on.
2. **No per-conversation progress/subgoal tracker** — chat sessions hold history/title/intent only; `definition_of_done` exists but subgoal status isn't tracked or rendered.
3. **No cost model on memory/meta actions** — recall is free and un-metered today; nothing teaches or gates consultation.
4. **No consult-value feedback loop** — we never measure whether a `recall`/`track` actually helped the episode.

---

## 4. Design

### 4.1 New module: `backend/core/bpe/`

```
backend/core/bpe/
  workspace.py        # BPEWorkspace: (B, P, E) container, per (workspace_id, agent_id, session/execution)
  adapter.py          # BPEAdapter protocol: domain-specific grounding (chat / workflow / research)
  actions.py          # track/commit/recall/note ActionDefinitions for action_registry
  consult_policy.py   # cost-aware gating + EMA value scoring (Phase 2)
  consolidation.py    # background Experience consolidation hooks (Phase 3)
  telemetry.py        # span emission: action, trigger, tokens, outcome attribution
```

**Workspace contract** (mirrors the paper's functional-interface pattern):

- `render(agent, session) -> BPEBlock` — bounded text block for the ReAct system prompt (char-capped per component, like the assembler's legs).
- `apply(action, payload)` — the four meta-actions; `commit` bounded to 8 subgoals; `note` writes to a temp buffer only.
- Persistence: Progress + note-buffer in the execution/session record; Experience rides existing `agent_experience`/skills with LFU-style caps added.

### 4.2 Meta-action wiring

| Meta-action | Backing store | Notes |
|---|---|---|
| `workspace.track` | GraphRAG `get_context_for_ai`, `business_facts`, VFS `documents.ls/cat` summaries, canvas state | Read-only, background-updated views (Belief is maintained *off* the hot path) |
| `workspace.commit` | New `AgentSubgoal` rows (or `AgentExecution.metadata["bpe_progress"]`) keyed to session/execution | Cap 8; drives a rendered checklist; pairs with `Objective.definition_of_done` |
| `workspace.recall` | `WorldModelService.recall_experiences` + skill retrieval, query modes: procedures / mistakes / entity-facts | Top-3 per category; re-uses existing legs |
| `workspace.note` | Temp buffer → fire-and-forget write into turn-fact/episode pipeline (never blocks the turn) | Consolidated asynchronously |

### 4.3 Cost model (Phase 2)

- Harness actions are **metered steps**: each consult consumes step budget and is recorded in `agent_reasoning_steps` with a `bpe_action` provenance field (extends `_persist_reasoning_step`).
- Consult policy gates by complexity tier (`cognitive_tier_system` / `QueryComplexity`): simple turns get no workspace block; long-horizon turns get full BPE.
- EMA value scoring per (agent, meta-action): did an episode with a consult succeed / finish faster / fewer steps than the agent's baseline? Mirrors `RoutingFeedback` → `stash_decision`.
- **Annealing analog:** as an agent's per-pattern consult value decays (the routine is internalized in its prompt/skills), the policy suppresses `commit`/`note` suggestions first, keeps `recall` longest — the paper's decay ordering.

### 4.4 Consolidation + evolution (Phase 3)

- Extend `memory_consolidation_service` with BPE Experience consolidation: add/update/remove, dedupe, LFU eviction at category caps — runs nightly/offline, never in the turn path.
- Feed BPE telemetry (which recalls preceded success, which notes never got used) into `harness_evolution_service.mine_weaknesses` as a new signal source → per-agent prompt patches ("for invoice tasks, recall procedures first").

---

## 5. Phased Plan

### Phase 0 — Workspace foundation (P0)
1. `backend/core/bpe/workspace.py` + `adapter.py` with the chat-surface adapter first; unit tests for bounds (subgoal cap, block char caps, LFU).
2. Persistence for Progress + note buffer on the execution record; migration per repo standards (StaticPool roundtrip test).
3. Telemetry spans for every workspace read/write.

### Phase 1 — Prompt-time harness (the immediate win; paper's "Base" config)
1. Register the four meta-actions in `action_registry` (maturity-gated visibility: expose to INTERN+ initially).
2. Render the BPE block in `GenericAgent._react_step` and `AtomMetaAgent._react_step` beside the memory block; agent decides to consult like any other tool.
3. **Shadow-first rollout** per Switchyard convention: render + log consults without changing behavior, then enable per-agent behind a flag (`ATOM_BPE_WORKSPACE_ENABLED`), A/B against baseline.
4. Eval: task success rate, harness-call rate/episode, token overhead delta on a fixed golden task set (reuse `memory_eval` harness + `agent_reasoning_steps` for traces).
5. Exit criterion: ≥ neutral success with bounded token overhead (< +10% prompt tokens), positive trend on long-horizon tasks.

### Phase 2 — Cost-aware consult policy (learned, no weight training)
1. `consult_policy.py`: complexity-gated workspace exposure + per-action EMA value scores from outcome feedback; consults metered against step budget.
2. Annealing: suppress `commit`/`note` prompts as per-pattern value decays; keep `recall`.
3. Surface policy state in agent maturity/graduation metrics (evidence: consult-value history as part of episode evidence).
4. Exit criterion: harness-call rate declines over an agent's episodes at equal-or-better success (the annealing signature), spam rate < 5% of steps.

### Phase 3 — Harness evolution integration (LANDED 2026-08-28)
1. ✅ BPE-aware consolidation sweeps (`core/bpe/consolidation.py`, wired into `memory_consolidator.consolidate_workspace`).
2. ✅ Harness-evolution telemetry feed: `core/bpe/telemetry_feed.py` → `HarnessEvolutionService.mine_weaknesses` (errored consults + negative-value agents as standard weakness patterns). AlphaEvolve-lite search: `core/bpe/evolution.py` — population over workspace-bound genomes, fitness = value EMA − call-rate drift penalty, apply flag-gated (`ATOM_BPE_EVOLUTION_ENABLED`); see §2.7.
3. ✅ Durable workspace persistence (`core/bpe/persistence.py`): JSON-per-workspace store, lazy restore on registry miss.

### Phase 4 — Trajectory distillation via student pipeline (research-gated, default OFF)
- Mature AUTONOMOUS agents running with BPE become "teachers": their successful BPE-annotated trajectories (`agent_reasoning_steps` + workspace diffs) are candidate SFT pairs for STUDENT agents, gated by the existing evidence rules (`InsufficientTrainingEvidenceError`, ≥3 episodes, supervisor approval via maturity routes). This reproduces the paper's Stage-1 apprenticeship without new infrastructure. Weight-level RL (Stage 2) is **out of scope** — document as future work pending a training cluster.

---

## 6. Metrics & Evaluation

| Metric | Source | Paper anchor |
|---|---|---|
| Task success rate (golden set, seen + novel tasks) | memory_eval / episode outcomes | 96.9 vs 47.9 headline |
| Harness-call rate per episode | `agent_reasoning_steps.bpe_action` | anneals to ~1/episode |
| Token overhead (prompt + consult results) | gateway spans | R_eff cost mechanism |
| Recall precision@3 / usage of recalled entries | telemetry on recalled entry hits | top-3 per category |
| Subgoal commitment rate + completion | Progress records | cap 8, commit-driven |
| Spam rate (no-op consults) | consult policy | R_spam penalty analog |

## 7. Risks & Mitigations

- **Prompt bloat** → hard char caps per component (assembler precedent); complexity gating.
- **Harness-action spam** → metered budget + annealing + spam-rate monitoring.
- **Stale/harmful Experience** → consolidation with remove (not just add), LFU eviction, sensitivity ceiling pre-filter already in `WorldModelService`.
- **Surface sprawl** → adapter pattern: ship chat-surface adapter first; workflow/research adapters follow only after Phase 1 proves value.
- **Novelty risk (SFT dip on unseen tasks)** → Phase 4 is evidence-gated; prompt-time + policy phases don't overfit to a teacher.

## 8. Testing & Doc Conventions

- Red-first TDD per `docs/testing/TDD_METHODOLOGY.md`; append session entry to `docs/testing/TESTED_FILES_TRACKER.md` for every touched file; 80% coverage goal on `backend/core/bpe/`.
- Unit tests for bounds/caps/LFU; property tests for workspace render determinism; integration tests against `action_registry` execution; A/B analysis in the Switchyard harness.
- Update this doc's Status markers per phase; register the doc in `docs/INDEX.md` (done).
