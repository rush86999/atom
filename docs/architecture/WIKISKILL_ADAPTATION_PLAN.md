# WikiSkill Adaptation Plan — compiling agent experience into a persistent wiki

Status: **implemented (phase 1)** · 2026-09-02
Source: Google Research, *WikiSkill: Compiling Agent Experience into Persistent
Knowledge for Skill Evolution* (Tang, Rashtchian, Ferng, Tomkins, Juan, Vu —
[arXiv:2608.27454](https://arxiv.org/abs/2608.27454), Aug 2026).

## 1. The paper, in one section

WikiSkill separates an agent's workspace into three layers and loops over four
steps:

1. **Raw layer** — immutable execution traces.
2. **Wiki layer** — persistent distilled knowledge that *never resets and only
   grows*: `wiki/patterns/` (one page per failure mode / successful strategy,
   with root cause + workaround), `wiki/index.md` (catalog), `wiki/logs.md`
   (evolution log), and `wiki/skill-impact.md` (programmatically appended
   acceptance history: diff, validation score, accept/reject).
3. **Skills layer** — active procedural instructions (`SKILL.md` +
   `PURPOSE.md` linking each skill back to its motivating patterns), which
   **can be rolled back**.

Each outer-loop iteration: a **Wiki Maintainer** LLM analyzes a *balanced
sample* of traces (≤8: up to 5 failing, 3 passing, 15k-char caps), does
root-cause analysis, and patch-edits pattern pages; a **Skill Proposer** reads
the index + the acceptance ledger and makes ONE atomic proposal against a
single skill; a **gate** accepts only on strict validation improvement, else
rolls back the skill — **the wiki is never rolled back**, and rejected
proposals are recorded so they are never re-proposed.

Headline results: Gemini-3.5-Flash 49.5%→68.1% average across 5 benchmarks;
ablations show (a) proposer access to the persistent wiki is worth ~+15%, and
(b) giving the *runtime* agent direct wiki access **hurts** (63.7→60.9) —
knowledge must be compiled into skills, not read raw at inference time.
Negative transfer is real: skills evolved by a weak model dropped a strong
model's SpreadSheet score 50.5%→18.1%.

## 2. What Atom already had (mapping)

| WikiSkill | Atom equivalent (pre-existing) |
|---|---|
| Raw layer | `AgentEpisode` / `EpisodeSegment` / `AgentReasoningStep` (append-only) |
| Skills layer | `playbooks` (versioned, approval-gated), `SkillCandidate` / `ToolMutation` with sandbox validation + rollback |
| Gate | `evolution_pipeline.py` (governance → daily limit → regression → deploy), `verify_panel`, playbook approval flow |
| Wiki layer | **Gap.** Closest was `field_guides` (one 50-line-capped page — the opposite of "grows, per-pattern") and the flat 200-entry lesson log |
| Acceptance ledger | **Missing.** `ToolMutation`/`SkillCandidate` record lifecycle, but nothing feeds acceptance history into the next proposal |

## 3. The six adaptations (all implemented)

### W1 — Skill-impact ledger (`wiki/skill-impact.md` analog)

* **Files:** `core/auto_dev/skill_impact_ledger.py` (new),
  `SkillImpactEntry` model (`core/auto_dev/models.py`), wiring in
  `evolution_pipeline.py`, `memento_engine.py`, `alpha_evolver_engine.py`.
* Every `UnifiedEvolutionPipeline.submit_and_deploy` outcome — accepted, or
  rejected at governance/daily_limit/regression — appends a
  `skill_impact_entries` row: target, source engine, proposal summary,
  unified diff (code mutations), validation stage, reason, status. A
  `record_rollback` hook marks a previously accepted entry `rolled_back`.
* `rejection_history()` renders the ledger as a proposer-context block
  ("SKILL ACCEPTANCE HISTORY … do not re-propose rejected interventions"),
  injected into Memento's and AlphaEvolver's generation prompts, so the
  evolver sees the complete acceptance history before proposing.

### W2 — Knowledge pattern store (`wiki/` analog)

* **Files:** `core/knowledge_pattern_service.py` (new), `KnowledgePattern`
  model (`core/models.py`), maintainer step in
  `core/exchange_memory_maintenance.py`.
* `knowledge_patterns` rows are per-pattern pages: name, kind
  (`failure_mode` | `success_strategy`), root cause, workaround, evidence
  episode/incident IDs, occurrence count, fingerprint dedup (re-observation
  bumps `occurrence_count` and refreshes text — wiki grows, never resets).
* The sleep-time maintenance loop gained a fault-isolated
  `maintain_knowledge_patterns` step (the Wiki Maintainer): samples recent
  traces, distills patterns (LLM when reachable, deterministic fallback from
  `IncidentEval` + `tool_errors` when not — CI/offline installs still
  accumulate wiki).
* `pattern_index()` renders the compact `wiki/index.md` analog for proposer
  prompts (W3's consumers).

### W3 — Mine passing traces, not just failures

* Every pre-existing learning loop was failure-driven (task-fail events,
  corrections). The pattern maintainer samples **up to 5 failing AND up to 3
  passing** traces per cycle (the paper's exact balance) and extracts
  `success_strategy` patterns from passing episodes with verified steps /
  positive supervisor ratings. A missed lesson that keeps recurring costs
  more than a redundant pattern — the wiki tolerates redundancy; the
  fingerprint dedup keeps it bounded.

### W4 — The runtime agent never reads the raw wiki (enforced by construction)

* The paper's strongest ablation: runtime wiki access *hurts*; knowledge
  reaches inference only compiled into skills. Atom enforces this on three
  levels:
  * **By construction** — the wiki read path (`pattern_index` /
    `recent_patterns`) requires an explicit `consumer` label and raises
    `RuntimeWikiAccessError` for anything except `consumer="evolver"`.
    There is no unlabeled way to read the wiki.
  * **By import graph** — a parametrized test sweeps every runtime
    prompt-assembly module (`memory_context_assembler`, `generic_agent`,
    `chat_orchestrator`, `chat_canvas_editor`, `chat_tool_planner`,
    `verify_panel`) and fails if any references a wiki-layer symbol
    (`knowledge_pattern_service`, `KnowledgePattern`,
    `skill_impact_ledger`, `SkillImpactEntry`).
  * **By prompt** — conversely, both offline proposers (Memento,
    AlphaEvolver) render the wiki index into their generation prompts:
    the wiki feeds the proposer, never the inference agent.
* Layer boundaries by function (why pre-existing surfaces stay):
  * `field_guides` = **skills layer** (curated *operational rules* —
    instructions agents execute, the workspace's AGENTS.md analog), so its
    runtime injection is paper-consistent.
  * episode retrieval legs = **raw-layer runtime retrieval**, a persistent-
    memory product feature the paper does not ablate; out of scope.
  * `knowledge_patterns` + `skill_impact_entries` = **the wiki layer**;
    evolver-only, enforced as above.

### W5 — Incident-eval gate on playbook promotion (accept iff validation improves)

* **Files:** `core/playbook_service.py`, `core/incident_eval_runner.py`,
  settings catalog.
* New runtime setting **`ATOM_PLAYBOOK_EVAL_GATE`** (`off` | `shadow` |
  `enforce`, default `shadow` — same rollout grammar as ATOM_PLAYBOOKS).
* When a draft playbook is approved and related incident evals exist (via
  `origin_ids`), the runner replays them: `enforce` blocks `draft → approved`
  while any eval **fails** (skips never block); `shadow` records the replay
  outcome on the playbook (`last_eval_result` column) and approves regardless.
* The wiki stays intact on rejection: a blocked playbook stays `draft`, its
  origin incident evals keep accumulating occurrences.

### W6 — Transfer safety for the experience marketplace (negative-transfer guard)

* **Files:** `core/experience_marketplace/pack_service.py`,
  `ExperienceItem` model.
* Packs now carry **model provenance** (source agent's model/family from
  `AgentRegistry.configuration`); imports stamp it on every `ExperienceItem`.
* Imported items land **quarantined** (`validation_state="pending"`) —
  the paper's negative-transfer case (weak-model skills catastrophically
  degrading a strong model) must not be able to happen silently. New columns:
  `source_model`, `validation_state` (`pending` | `active` | `rejected`;
  legacy NULL rows read as active for backward compatibility).
* `activate_import()` activates after the receiving tenant's incident evals
  replay clean (advisory `pattern` items may auto-activate); `skill` items —
  the catastrophic class in the paper — always wait for explicit review.
  `list_active_items()` is the only sanctioned read path for consumers.

## 4. Schema changes

Alembic `20260902_wikiskill_adaptation`:
* create `knowledge_patterns`, `skill_impact_entries`;
* add `playbooks.last_eval_result` (JSON, nullable);
* add `experience_items.source_model` (String, nullable) and
  `experience_items.validation_state` (String, nullable).

`Base.metadata.create_all` covers fresh dev DBs; the migration covers
existing Postgres installs.

## 5. Flags & rollout

| Flag | Default | Meaning |
|---|---|---|
| `ATOM_PLAYBOOK_EVAL_GATE` | `shadow` | off/shadow/enforce — only `enforce` can block a playbook approval |
| (none for W1/W2/W3) | — | ledger + wiki are write-side only until consumed by the evolvers; no runtime behavior changes |
| (none for W6) | — | imports were already operator-initiated; quarantine only narrows what imports can do |

## 6. Testing

* `tests/test_skill_impact_ledger.py` — ledger write/read, pipeline wiring
  (every gate outcome appends), evolver prompt injection.
* `tests/test_knowledge_patterns.py` — fingerprint dedup/bump, balanced
  sampling caps, deterministic + LLM maintainer, index rendering, W4
  import-graph pin.
* `tests/test_playbook_eval_gate.py` — shadow records + approves; enforce
  blocks on fail, passes on clean replay, skips never block; off is a no-op.
* `tests/test_experience_transfer_safety.py` — import stamps provenance +
  quarantines, active-list exclusion, pattern-auto-activate vs skill-holds,
  reject flow.
