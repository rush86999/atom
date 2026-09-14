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
| `GET /agents/{id}/sale-readiness` | advisory evidence + paid blockers (owner or admin — the evidence view leaks the agent's track record) |
| `POST /agents/{id}/publish` | package for sale (owner or admin; 409 on gate failures) |
| `POST /templates/{template_id}/push` | push a packaged listing to the SaaS `ingest-listing` (publisher or admin; idempotent by default — the local template records its last push, `force=true` re-pushes) |
| `POST /install-remote` | install from a central listing as a managed agent (member+; paid listings require the explicit `paid_override` assertion — local mirror of the SaaS entitlement gate) |
| `GET /templates/{id}` | buyer-safe listing: identity, price, ratings, `verified_record`, aggregate guidance counts — **never** the manifest or memory bundle (managed-agent model: prompts/experience resolve server-side at execution time) |

Installation stays on the existing `install_agent` path (SaaS + local
fallback).

## 4b. The marketplace server (atom-saas)

The central marketplace **server lives with the atom-saas app**
(`/atom-saas/backend-saas`); the self-hosted atom instance is the client.
Server side (landed in atom-saas@`b4c2055225`):

- `publish_agent` computes `verified_record` **natively from the SaaS's
  own `goal_runs` rows** (the SaaS ships the same goals module) with the
  same shape as the instance-side computation, and enforces the same
  paid gate (price > 0 requires ≥ 1 verified achieved run). Achieved
  runs' plan step titles ship as sanitized golden paths alongside the
  execution-derived ones.
- `browse_agents` / `get_template_listing` serve `verified_record` +
  aggregate guidance counts; manifest/memory stay server-only.
- `POST /api/agent-marketplace/ingest-listing` + `ingest_remote_listing`:
  a self-hosted instance pushes its packaged listing
  (`POST /api/agent-marketplace/templates/{id}/push` →
  `publish_listing_to_saas` → `publish_listing_sync`). **Federation auth
  (required)**: the call authenticates with `X-Instance-ID` + 
  `X-Federation-Key` headers (`backend-saas/api/dependencies/
  federation_auth.py:validate_federation_peer` — the instance id must be a
  registered, active `MarketplaceInstance`; the key must equal an accepted
  `FederationConnection.shared_secret`, which for atom instances is the
  `ATOM_SAAS_API_TOKEN`). The atom client (`core/atom_saas_client.py`)
  sends exactly those headers; `ATOM_SAAS_INSTANCE_ID` configures the
  registered instance id. For federation callers the server pins
  `source_instance_id` to the authenticated peer — the body field is not
  trusted. The payload must carry the platform-computed
  `verified_record` (free-text listings by hand are refused), and the
  listing lands **PENDING admin approval** — the same queue as local
  publishes, which is the trust boundary for evidence not computed by the
  server itself. `agent_templates.source_instance_id` records provenance.
- **Server re-sanitization is PARTIAL (correction 2026-09-13)**:
  `ingest_remote_listing` re-sanitizes only `description`,
  `heuristics[].resolution` and `golden_paths[].sequence`. Everything else
  — `configuration.system_prompt`, `configuration.playbooks`, `name`,
  `category` — is stored and served as sent. Sanitization of those fields
  is therefore the INSTANCE's job at packaging time
  (`package_agent_for_sale`: entity tokenization, PII redaction, and —
  since 2026-09-13 — key-shaped secret redaction `sk-…`/`ghp_…`/`AKIA…`/
  `xox…`/`Bearer …` via `experience_marketplace/sanitizer.redact_secrets`).
  The server should extend its re-sanitization to the remaining free-text
  fields (handoff note, 2026-09-13).
- Schema: `agent_templates.verified_record` (JSON) + `source_instance_id`
  (indexed), migration `20260912_agent_verified_record` chained on the
  `goal_runs` head of the SaaS alembic graph.

So the full sell path is: agent works goal runs on the instance →
`package_agent_for_sale` (evidence computed, listing live locally) →
`publish_listing_to_saas` → SaaS admin approval → browsable on the
central marketplace with its verified record → another instance installs
→ installs seed evidence-honest confidence + the publisher's playbooks →
its runs report usage back to the listing.

## 5. Schema

`agent_templates.verified_record` (nullable JSON) — migration
`20260912_agent_verified_record` + `core.sqlite_schema_repair`
`ensure_sqlite_columns(engine, AgentTemplate)` self-heal for drifted dev
files.

Tests: `backend/tests/test_agent_marketplace_goal_runs.py` (verified-record
math, achieved-only golden paths, override heuristics, entity/PII leak
checks, paid gate, re-publish block, readiness, local-install seeding +
idempotent playbook materialization, terminal-run usage reporting; since
2026-09-13 also idempotent-push + push/install-remote route guards).
Companion suites (2026-09-13): `test_marketplace_packaging_redaction.py`
(key-shaped secret redaction + playbook workspace scoping),
`test_goal_run_access_control.py` (cross-workspace IDOR),
`test_atom_saas_client.py` (federation headers + sync-loop safety),
`test_goal_run_watchdog_sweep.py` (bounded operator waits + stale sweep),
`test_sql_json.py` (dialect-portable JSON comparison).
Pre-existing failure NOT caused by this work:
`test_covpush_core_c.py::TestAgentMarketplaceService::test_install_agent_success`
asserts `OperationErrorResolution` rows that the current install path does
not create — fails at clean HEAD too (verified via stash).
`test_agent_marketplace_service.py::TestSkillInstallation::test_install_agent_handles_template_not_found`
also fails identically at clean HEAD (verified via worktree 2026-09-13).
