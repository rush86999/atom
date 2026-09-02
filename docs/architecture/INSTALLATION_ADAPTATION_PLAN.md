# Installation Adaptation Plan — Competence Without Code Changes

> **Status**: Phases 1–5 backend implemented (2026-09-02) · **Created**: 2026-09-02 · **Owner**: Agent platform
>
> **Implemented 2026-09-02**: `installation_profiles` / `playbooks` /
> `incident_evals` tables (+ migration `20260902_installation_adaptation`);
> services `installation_profile_service`, `failure_taxonomy`,
> `incident_eval_service` + `incident_eval_runner` (CLI:
> `python -m core.incident_eval_runner`), `playbook_service`,
> `correction_reflection_service`, `send_grounding`,
> `installation_metrics`; APIs `/api/installation/*`, `/api/playbooks/*`;
> wiring: correction capture → eval+reflection (canvas_context_service),
> playbooks + profile identity into the editor prompt (chat_orchestrator →
> chat_canvas_editor), playbook leg in memory_context_assembler,
> grounded-send gate in EmailCanvasService.send_email (ATOM_SEND_GROUNDING,
> shadow default), sleep-time playbook drafting
> (exchange_memory_maintenance), incident-eval gate in the graduation exam.
> Flags: ATOM_PLAYBOOKS, ATOM_SEND_GROUNDING (settings catalog, Learning &
> Verification). Frontend surfaces (wizard, playbooks admin, dashboards) are
> the remaining follow-up — all data is API-complete.
>
> **Motivation**: canvas da27bb76… incident (2026-09-02) + per-install economics

## Problem statement

Every new ATOM installation (new tenant, new industry, new company process)
surfaces new agent failure modes. Fixing them the way we fixed the da27bb76
incident — engineering time spent root-causing one conversation, patching
product code, restarting — does not scale to N installations. The failure
*classes* repeat (unverified claims, guessed identity, lost user edits,
no-op edits reported as success, ignored process rules), but their
*instances* are installation-specific (which claims, whose name, which
process).

**Goal: a new installation reaches supervisor-trusted agent competence
through configuration, onboarding data, and feedback-driven learning —
never through per-install code changes.** Product code changes happen once,
in this repo, as general mechanisms; everything installation-specific is
data the platform learns or is given.

## Research base (what mature systems do)

| Practice | Evidence | Adopted as |
|---|---|---|
| Per-install knowledge is **data in context**, curated to "the smallest set of high-signal tokens" | Anthropic, [Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents); [Building Effective AI Agents](https://www.anthropic.com/engineering/building-effective-agents) | Prompt legs (§3.1) with priority trimming (already implemented in the editor) |
| Procedures are **procedural memory**: reusable SKILL.md-style playbooks loaded on demand | Anthropic, [Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) + [Agent Skills docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview); [procedural-memory analysis](https://www.techrxiv.org/doi/pdf/10.36227/techrxiv.176857932.25697838/v1) | §3.2 Playbooks ("Vipul's template questions" is one) |
| Idle time consolidates memory; anticipation beats test-time effort (~5x compute reduction) | Letta, [Sleep-time Compute](https://arxiv.org/html/2504.13171v1) ([blog](https://www.letta.com/blog/sleep-time-compute/)) | §3.4 extend `exchange_memory_maintenance.py` |
| Implicit, **binary feedback is abundant**; pairwise preferences are rare — learn from what deployments actually emit | KTO ([arXiv 2402.01306](https://arxiv.org/abs/2402.01306)); [RLUF](https://arxiv.org/html/2505.14946v1) | §3.5 signal capture (corrections, regenerations, rejections) — already mostly built |
| **Production failures become regression eval cases**, run per release | [Promptfoo](https://www.promptfoo.dev/) / [Braintrust](https://www.braintrust.dev/articles/braintrust-vs-promptfoo); [Langfuse on trajectory evals](https://langfuse.com/resources/engineering/ai-agent-evaluation) | §3.3 incident→eval pipeline |
| Multi-tenant agents isolate tenant state and customize via tenant-scoped config, not forks | [Google Cloud multi-tenant agentic AI reference](https://docs.cloud.google.com/architecture/multi-tenant-agentic-ai-system) | §3.1 tenant-scoped profile tables (pattern already used by LanceDB workspaces) |
| Memory layers (Mem0/Zep/Letta) are commodities; the differentiator is consolidation + consistency over changing facts | [2026 comparison roundups](https://particula.tech/blog/agent-memory-frameworks-tested-mem0-zep-letta-cognee-2026) | Do NOT buy/build a new memory layer — ATOM's LanceDB stack covers this; focus on the learning loops around it |

## What ATOM already has (audit 2026-09-02)

The platform is further along than the incident suggests. Existing, production
mechanisms:

- **Correction capture → RLHF signal**: `CanvasContextService.record_user_correction`
  (services/canvas_context_service.py) — wired at `PUT /api/canvas/{id}`; feeds
  `AgentFeedback` + maturity.
- **Taught lessons**: `/teach` (api/agent_onboarding_routes.py) →
  `StudentLearningService` → `_lessons_section()` in the edit planner prompt.
- **Cross-canvas learning**: episodic corrections from similar canvases +
  distilled supervisor patterns (`_similar_lessons_section`,
  `get_correction_patterns`).
- **Exchange memory**: rated examples captured per workspace into LanceDB
  (`exchange_example_service.py`), retrieved into prompts
  (`memory_context_assembler.py`), with off|shadow|enforce rollout
  (`ATOM_EXCHANGE_MEMORY`).
- **Sleep-time maintenance**: hourly loop (`exchange_memory_maintenance.py`) —
  vector backfill, consolidation of ≥3 recurring negatives into pattern
  lessons, shadow→enforce auto-promotion.
- **Autonomy ramp**: `autonomy_policy.py` — MODE_HUMAN_ALWAYS /
  MODE_AUTO_IF_MATURE, trust_check; graduation exam
  (`agent_graduation_service.py`).
- **Evidence grounding rules + one detector** (`core/evidence_grounding.py`).
- **Memory stack**: multi-leg assembler with rerank, episodic segmentation to
  LanceDB, user preferences, canvas context per canvas.
- **Retrieval eval**: `memory_eval*.py` (recall@k).

## Gaps (why installs still need engineers today)

1. **No installation profile** — sender identity, team roster, templates,
   glossary, vendor/process facts exist only in humans' heads or scattered
   preferences. (The da27bb76 "Chandrakant" signature was this gap wearing a
   code bug's clothes; the code fix generalizes identity *plumbing*, but the
   *values* must be per-install data.)
2. **Processes are not first-class** — "Vipul's bandsaw template questions",
   "machine → stock → vendor → new vendor" live in one draft's text. Nothing
   captures, versions, retrieves, or teaches them as reusable playbooks.
3. **Live failures don't become evals** — the da27bb76 fixes got hand-written
   tests; nothing auto-generates regression cases from real corrections/
   incidents, and no behavior eval suite runs per release
   (memory retrieval is the only eval'd surface).
4. **No failure taxonomy/telemetry** — incidents live in chat transcripts;
   nobody can answer "what are this install's top failure classes this week?"
5. **Reflection is manual** — lessons require a supervisor to type /teach;
   sleep-time consolidation only fires on ≥3 repeats of *negatives*.
6. **Grounding is prompt-only on the send path** — rules + one detector for
   chat regen; no structured check that an outbound email's factual claims
   trace to ingested sources or carry hedged wording.
7. **Onboarding is ad-hoc** — no guided capture of profile/playbooks at
   install time; the agent starts from zero credibility.

## Plan

### Phase 0 — General mechanisms from live incidents (DONE 2026-09-02)

Evidence grounding rules + unverified-confirmation regen guard; origin
provenance hydration; no-op edit guard with honest replies; sender-identity
resolution into the editor prompt; autosave flush before co-editor turns.
These are the template for future work: **fix the class in product code once,
and leave the instance-level knowledge to the layers below.**

### Phase 1 — Installation profile as data (≈1 week)

Tenant-scoped `InstallationProfile` (SQL + preference store), editable in an
onboarding/settings UI:

- identity: company name, sender profile, default signature (already stored —
  surface it here), reply-to;
- people: team roster with roles (who is "the dealer", who is internal);
- templates: reusable question sets / document skeletons (seeded from real
  drafts in one click);
- facts: glossary + claims registry (product specs, voltage options) with
  source links — the grounding checker's allowlist;
- integrations: existing 40+ connectors.

Consumed by: editor prompt identity section (exists), conversational path
context, grounding checker (Phase 4), graduation exam (Phase 5).
**Exit**: fresh install completes the wizard; the agent signs correctly and
addresses roles correctly with zero code/config-file edits.

### Phase 2 — Failure telemetry → auto-generated evals (≈2 weeks)

- Failure taxonomy stamped on corrections, no-ops, regenerations, send
  refusals: `grounding | identity | persistence | process | tone | other`
  (classifier can start as rules over the diff; the taxonomy is small).
- New table `incident_evals`: every correction that changed agent output
  yields a replayable case (context snapshot → instruction → expected
  property: "output does not claim X as fact", "output preserves signature",
  "output is not byte-identical to input").
- Runner: reuse `tests/scenarios` harness + memory_eval pattern; expose
  `make evals` (Promptfoo-style CLI is optional, not required); wire into CI
  and into the graduation exam so **a hire cannot promote on an install
  whose regression cases it fails**.
- Weekly per-install report: top failure classes, trend, new auto-evals.

**Exit**: the da27bb76 conversation, replayed from its snapshot, fails
pre-fix code and passes post-fix code — generated automatically from the
correction rows, not hand-written.

### Phase 3 — Playbooks: company processes as procedural memory (≈2–3 weeks)

- `Playbook` model (tenant-scoped): name, trigger conditions (canvas type +
  entity/keyword), steps, template questions, worked examples, source
  (authored | learned), version, approval state.
- Three capture paths, cheapest first:
  1. onboarding wizard (Phase 1 templates graduate into playbooks);
  2. `/teach` upgraded: "always ask material + dimensions before voltage"
     becomes a structured playbook draft, not just a text lesson;
  3. **sleep-time auto-draft**: `exchange_memory_maintenance` extends from
     negatives-only to *pattern → draft playbook* when correction patterns
     recur (KTO-style: use the abundant implicit signal), queued to the
     Training panel for supervisor approval — never auto-enforced.
- Retrieval: relevance-filtered playbook leg in `memory_context_assembler`
  + editor prompt (same priority-trim discipline as `_lessons_section`).
- Enforce rollout mirrors `ATOM_EXCHANGE_MEMORY`: shadow (prompt leg only)
  → enforce (send/edit gates consult playbook coverage).

**Exit**: "focus on Vipul's template" is expressed ONCE; every future
machine-inquiry draft across the install carries the template without
anyone repeating it.

### Phase 4 — Reflection + grounded sends (≈2 weeks, overlaps Phase 3)

- **Post-correction reflection**: when `record_user_correction` fires, a
  fault-isolated background critique (what class? what rule would have
  prevented it?) drafts a lesson/playbook fragment; dedup via the existing
  consolidation service. Supervisor confirms in Training panel (one click).
- **Grounded send gate**: before `POST /api/canvas/email/send`, extract
  factual assertions (specs, availability, pricing); each must (a) match the
  profile facts registry / ingested docs, or (b) carry hedged wording, or
  (c) block with an actionable message. Extends
  `evidence_grounding.asserts_unverified_confirmation` from a chat regen
  guard to a structured send-path check. Supervisor can override (logged) —
  the gate starts in shadow mode and promotes via runtime settings like the
  exchange memory flag.

**Exit**: an email asserting "480V 3-phase is available" without a source
cannot be sent silently on any install.

### Phase 5 — Trust ramp + metrics (ongoing)

- Per-install dashboard: correction rate / 10 turns, repeated-feedback rate
  (same instruction twice = process failure), no-op claim rate (must stay 0),
  grounding coverage, playbook hit rate, time-to-autonomy (install age at
  first AUTO_IF_MATURE promotion).
- Graduation exam runs the install's auto-generated eval suite (Phase 2) as
  a gate; autonomy policy already consumes the result.
- Design the captured signal so a future KTO/RLUF fine-tune is possible
  (store binary accept/reject + context per exchange) — but do NOT fine-tune
  per install now; in-context learning via playbooks/lessons is cheaper,
  auditable, and reversible.

**Exit**: "new install" runbook = deploy → wizard → use → review weekly
report → approve playbooks. Engineer involvement only for product-level
bugs.

## Explicit non-goals

- Per-install forks or config-file patches outside the product.
- A new memory-layer build/buy (LanceDB stack + assembler already cover it).
- Per-tenant weight fine-tuning (revisit only if in-context learning
  demonstrably plateaus and per-exchange signal volume is large).
- Fully autonomous learning without supervisor approval — every
  learned-playbook/lesson path keeps a HITL approval gate (autonomy_policy
  stays the single trust authority).

## Sequencing & dependencies

```
Phase 1 (profile) ──┬─> Phase 4 (grounded sends need the facts registry)
Phase 2 (telemetry) ─┴─> Phase 5 (dashboards read telemetry)
Phase 3 (playbooks) ──> Phase 4 (reflection drafts playbook fragments)
Phase 0 (done) feeds examples into Phase 2's first eval set
```

Phase 2 first if engineering time is split: telemetry + auto-evals make
every later phase measurable and safe to roll out behind shadow flags.
