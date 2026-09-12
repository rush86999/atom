# Agent Marketplace × Goal Runs — selling agents on verified evidence

> **Status**: implemented 2026-09-12 (backend). The marketplace model for
> *selling agents* (`AgentTemplate` / `AgentInstallation`, the managed-agent
> IP model in `core/agent_marketplace_service.py` + `core/marketplace_runtime.py`)
> now integrates with the goal-run system: **the product is the agent's
> verified track record**, computed by the platform from `GoalRun` rows —
> never authored by the publisher.

Research grounding (per AGENTS.md §3): agent-marketplace trust discussions
converge on **verifiable identity + trust scores / public verified metrics
over marketing claims** (CrewAI's
[AgentGraph trust-verification proposal](https://github.com/crewAIInc/crewAI/issues/5153),
[marketplace leaderboard discussions](https://www.reddit.com/r/crewai/comments/1ej2jeq/ai_multiagent_marketplace_validaterefute_this_idea/));
this repo's own EXPERIENCE_MARKETPLACE.md states the rule as *"verified
credibility, not marketing claims."* The goal-run loop (see
GOAL_RUN_ORCHESTRATION.md, incl. the 2026-09-12 agent-executes model) is
what produces that evidence: durable runs, decided by the agent, with
terminal outcomes the platform can count.

## 1. The seller side — packaging (`package_agent_for_sale`)

`AgentMarketplaceService.package_agent_for_sale(agent_id, price, …)` turns a
TRAINED agent into a listing. Everything evidence-shaped is COMPUTED:

| Listing part | Source | Rule |
|---|---|---|
| `verified_record` (new `agent_templates.verified_record` JSON column) | GoalRun rows for the agent | runs {achieved/failed/cancelled/active/total}, achieved_rate (judged outcomes only), steps_executed, human_interventions, decisions, supervision_modes, roles, **maturity_at_publish** |
| `anonymized_memory_bundle.golden_paths` | **ACHIEVED** runs only | the plan step-title sequences that led to achieved goals (≤5 paths × ≤20 steps) — feeds the runtime's PROVEN SEQUENCES prompt block buyers already get |
| `anonymized_memory_bundle.heuristics` | decision-log `override` entries | the supervisor's corrections become "when X → do Y" resolutions (≤10) — the PROVEN PLAYBOOK block |
| `configuration.playbooks` | Playbook rows | **approved only** (drafts never ship), ≤20 — the process a buyer's `goal_runs.start` seeds plans from (`seed_plan_for_run` matches them by keywords) |
| `configuration.system_prompt` / `role` | agent config + specialty/category | the persona, sanitized |

Sanitization layers: `strip_credentials` over manifest + bundle (P5
blueprint security); the Experience-Marketplace sanitizer for text
(GraphNode entity names pre-registered as role tokens → customer/company
names ship as `company_001`-style tokens; PII regex redaction); length
caps everywhere.

**Paid-listing gate**: `price > 0` requires ≥1 verified achieved goal run.
Free listings are always allowed. **No re-publishing**: a
marketplace-managed (installed) agent cannot be packaged again — selling
someone else's listing is not a listing.

`sale_readiness(agent_id)` is the advisory pre-publish view (the evidence a
listing would carry + paid blockers), mirroring the workflow-template
readiness pattern the marketplace UI already consumes.

## 2. The buyer side — evidence-honest installs

`install_agent` (which now also serves LOCAL listings when the SaaS fetch
returns nothing — self-hosted sales work end-to-end):

- **Tier stays `intern`** — marketplace convention; trust is re-earned from
  LOCAL outcomes. But the starting confidence inside the intern band scales
  with the verified record instead of a flat 0.55:
  `min(0.69, 0.55 + achieved×0.03 + verified_steps×0.001)`.
- `configuration.seed_evidence` records `{source_template_id,
  verified_record}` — buyer transparency + graduation evidence. (Fixing this
  surfaced a latent bug: the old config update mutated the JSON dict in
  place and re-assigned the same object — invisible to SQLAlchemy, so even
  `capabilities` never actually persisted; the config is now rebuilt as a
  new dict.)
- The publisher's **approved playbooks are materialized** into the buyer's
  tenant as approved `Playbook` rows (`origin_ids=["marketplace:<template>"]`,
  idempotent by fingerprint) — so the installed agent's first
  `goal_runs.start` seeds a real plan, and its runs immediately accrue the
  buyer's own verified record.

## 3. The feedback loop — runs report usage

When a goal run worked by a **managed** (installed) agent reaches a
terminal state, `GoalRunService._on_terminal` reports
`MarketplaceUsageTracker.track_usage(item_type="agent",
item_id=template_id, success=achieved)` (fault-isolated). Seller analytics
and buyer ratings ride on verified outcomes from the same loop that
produced the listing's evidence — not on reviews alone.

## 4. HTTP surface (`api/agent_marketplace_routes.py`, `/api/agent-marketplace`)

| Route | What |
|---|---|
| `GET /agents/{id}/sale-readiness` | advisory evidence + paid blockers (any signed-in user) |
| `POST /agents/{id}/publish` | package for sale (owner or admin; 409 on gate failures) |
| `GET /templates/{id}` | buyer-safe listing: identity, price, ratings, `verified_record`, aggregate guidance counts — **never** the manifest or memory bundle (managed-agent model: prompts/experience resolve server-side at execution time) |

Installation stays on the existing `install_agent` path (SaaS + local
fallback).

## 5. Schema

`agent_templates.verified_record` (nullable JSON) — migration
`20260912_agent_verified_record` + `core.sqlite_schema_repair`
`ensure_sqlite_columns(engine, AgentTemplate)` self-heal for drifted dev
files.

Tests: `backend/tests/test_agent_marketplace_goal_runs.py` (verified-record
math, achieved-only golden paths, override heuristics, entity/PII leak
checks, paid gate, re-publish block, readiness, local-install seeding +
idempotent playbook materialization, terminal-run usage reporting).
Pre-existing failure NOT caused by this work:
`test_covpush_core_c.py::TestAgentMarketplaceService::test_install_agent_success`
asserts `OperationErrorResolution` rows that the current install path does
not create — fails at clean HEAD too (verified via stash).
