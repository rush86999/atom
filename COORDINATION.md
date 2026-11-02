# Agent Coordination

Live coordination doc for multiple agents working in this repo in parallel.
**Read this before making changes, and append your session when you start and
finish.** Keep entries factual and dated; never delete another session's
notes — mark superseded items with ~~strikethrough~~ or a "SUPERSEDED" note.

Ground rules:

1. Before editing a file, check the **Active sessions** table — if another
   session lists it, coordinate through a note here or pick different files.
2. Commit often in small, well-scoped commits; do not commit files listed by
   another active session without their note.
3. If a file you are editing changes under you (Edit tool "file modified"
   error), re-read it and check this doc before continuing — someone may be
   mid-refactor.
4. Record anything cross-cutting you change (env vars, route mounts, shared
   fixtures) — other agents' tests may depend on it.
5. **The shared dev backend on `:8001`**: always (re)start it with
   `scripts/start-backend.sh --daemon --force` — the script exports
   `BYPASS_RATE_LIMIT=1`, which the journey suites need (they register ~30
   users). A plain `uvicorn` restart leaves the register limiter on and
   every journey test 429s. Note your restart in this doc.

---

## Active sessions

| Session | Focus | Files owned (do not refactor in parallel) | Status |
|---|---|---|---|
| Integrations e2e journeys (2026-08-29) | End-to-end user-journey coverage for all integrations; see "Session: integrations-e2e" below | `backend/api/oauth_routes.py`, `backend/core/oauth_handler.py`, `backend/integrations/outlook_service.py`, `backend/api/data_ingestion_routes.py`, `backend/core/integrations/adapters/zoho.py`, `backend/main_api_app.py` (dotenv + workdrive mount), `backend/scripts/*mock_server*.py`, `backend/tests/e2e_ui/tests/test_journey_*.py` | COMPLETE — all suites green; see "Final results" |

---

## Session: integrations-e2e (started 2026-08-29)

Goal: the `/integrations` user journey (hub → connect → status → use →
disconnect) actually tested end-to-end for every integration, Outlook and
Zoho first.

### Landed so far (uncommitted on `main` at the time of writing)

Production fixes (each was a real journey-blocking bug):

- `backend/api/oauth_routes.py`
  - `oauth_initiate` now reads the `Authorization: Bearer` header (was
    query-param-only → every header-authenticated initiate 401'd; blocked the
    Zoho journey end-to-end).
  - `revoke_oauth_token` now revokes the `IntegrationToken` fan-out rows
    (microsoft → microsoft+outlook; zoho → 5-provider suite). Disconnect
    previously left the hub "connected" and data routes working.
  - Zoho connect's background sync now passes `workspace_id`/`tenant_id` as
    keyword args via `core.personal_scope` resolvers (tenant_id was bound
    positionally to `workspace_id`, so post-connect syncs ran
    unauthenticated).
  - New `_TOKEN_FANOUT` module constant.
- `backend/main_api_app.py`
  - `load_env()` no longer `override=True`: explicit process env
    (DATABASE_URL, provider creds, e2e harness) must beat `.env` files. The
    old behavior silently discarded both, and the Zoho journey was running
    against the dev DB instead of its fresh tmp DB.
  - Zoho WorkDrive router mounted at its own declared prefix
    `/api/zoho-workdrive` (was double-prefixed under `/api/v1/integrations/...`
    and unreachable; the hub page + next.config rewrite target this path).
- `backend/core/oauth_handler.py`
  - `MICROSOFT_AUTHORITY_BASE` env override for the Microsoft authorize/token
    endpoints (mirrors `ZOHO_ACCOUNTS_BASE`).
  - Generic `{PREFIX}_AUTHORIZE_URL` / `{PREFIX}_TOKEN_URL` overrides derived
    from each `OAuthConfig`'s client-id env name (`GOOGLE_CLIENT_ID` →
    `GOOGLE_AUTHORIZE_URL`; `TRELLO_API_KEY` → `TRELLO_AUTHORIZE_URL`).
- `backend/integrations/outlook_service.py` — `MICROSOFT_GRAPH_BASE_URL`
  env override for the Graph base URL + refresh authority URL.
- `backend/integrations/atom_communication_ingestion_pipeline.py` — the
  Outlook poller's Graph URL honors the same env override.
- `backend/core/integrations/adapters/zoho.py` — `_load_token` falls back to
  any *active* provider grant when the workspace-scoped lookup misses
  (workspace-convention drift used to produce unauthenticated syncs).
- `backend/api/data_ingestion_routes.py` — sync endpoint no longer 500s when
  a sync is skipped (bool fed to a `str` response field).

Tests:

- New `backend/scripts/microsoft_mock_server.py` + `backend/tests/e2e_ui/tests/test_journey_outlook_integration.py`
  (browser consent → tokens → hub status → emails/calendar/contacts/tasks/
  profile → disconnect; GREEN).
- New `backend/scripts/generic_oauth_mock_server.py` + `backend/tests/e2e_ui/tests/test_journey_all_integrations.py`
  (parametrized connect/status/disconnect for google, slack, github, asana,
  notion, dropbox, box, salesforce, linkedin, whatsapp; trello initiate-only
  — OAuth1; plus the env-keyed half of the catalog via `connection-status`).
- `test_journey_zoho_integration.py` updated: R88 credential isolation
  (member must NOT receive token rows), sync retry instead of racing the
  background sync, idempotent-reingest note (GREEN).
- `test_oauth_initiate_token_identity.py` +2 (Bearer header path).
- `test_oauth_config_url_overrides.py` new (override derivation).
- `test_covpush_outlook.py` / `test_covpush_mail_office.py` made hermetic
  (they depended on the ambient `backend/.env` being absent).

Docs: `backend/tests/e2e_ui/JOURNEY_TESTS.md` rows for the new modules.

### Known collisions with parallel work (heads-up)

- Commit `e2e34dffc` / `53e93ae52` / `6eb12b7cc` landed mid-session
  (integration_status_routes, embedding registry, DATABASE_URL anchoring) —
  this session's work is compatible with all three.
- `backend/integrations/outlook_service.py` `_refresh_access_token` was
  changed by another session mid-flight (`.first()` → `.all()` fan-out to
  both provider rows). The change is good; `test_covpush_outlook.py`'s mock
  was updated here to serve `.all()` accordingly.
- The dev backend on `:8001` was restarted twice with
  `scripts/start-backend.sh --daemon --force` to pick up fixes (pids
  changed). If you rely on :8001, restart it after pulling this session's
  changes.

### Debugging notes (resolved during the all-integrations work)

- The run-2 "initiate 401s" did not recur in runs 3–4 once the fixture
  redirect URIs pointed at the real backend port (a port-0 placeholder made
  the consent button navigate to an unroutable address) and the OAuthConfig
  override prefix for `TRELLO_API_KEY` was derived correctly. `oauth_initiate`
  now logs swallowed resolver exceptions instead of turning them into
  undocumented 401s — if the flake returns, the child backend log will name
  it.
- The generic mock originally issued one constant refresh token for every
  provider. `oauth_tokens.refresh_token_hash` is UNIQUE, so the second
  provider's callback died with `IntegrityError` → 500 and stored nothing.
  The mock now issues unique tokens per grant (matching real providers).

### Open question

None currently.

### Final results (2026-08-29)

| Suite | Result |
|---|---|
| `test_journey_outlook_integration.py` (browser consent → tokens → hub → data → disconnect) | 2 passed |
| `test_journey_zoho_integration.py` (browser consent → 5-provider fan-out → sync → chat recall) | 2 passed |
| `test_journey_all_integrations.py` (10 OAuth providers full journey + trello initiate + env-keyed catalog + mock contract) | 13 passed |
| `test_journey_integrations_health.py` (32 catalog health routes) | 31 passed, 1 xfailed (documented `nextjs`) |
| Units around the changed code | 370 passed |

Known unrelated pre-existing failure: `tests/test_llm_oauth_handler.py` (2,
fail identically on a clean checkout — LLM-provider OAuth, not integrations).

### How to verify this session's work

```bash
# Self-contained journey suites (~2 min each; no external services):
cd backend/tests/e2e_ui
../../venv/bin/python -m pytest tests/test_journey_outlook_integration.py \
    tests/test_journey_zoho_integration.py -v
../../venv/bin/python -m pytest tests/test_journey_all_integrations.py -v

# Units around the changed code:
cd backend && venv/bin/python -m pytest \
    tests/test_oauth_initiate_token_identity.py \
    tests/test_round71_oauth_routes_auth.py \
    tests/test_oauth_config_url_overrides.py \
    tests/test_covpush_outlook.py tests/test_covpush_mail_office.py \
    tests/unit/api/test_oauth_routes.py -q
```

---

## Append your session below this line

(Format: `## Session: <name> (<date>)` + Goal / Files owned / Notes / Status.)

---

## Session: README feature readiness, Agent 2 (2026-10-31)

**Branch/worktree:** `codex/readme-feature-readiness` in
`/Users/rushiparikh/projects/atom-readme-features`, based on immutable
`local-core-2026-10-30-final` (`da9cc8b12`). Tags were not moved.

**Goal:** establish and verify the README-marketed functional surface (breadth),
without invalidating the accepted local-core work and without deploying.

**Owned in this session (do not refactor in parallel without a note):**

- `docs/acceptance/readme_feature_readiness_2026-10-31/` (inventory, coverage
  report, evidence)
- `scripts/acceptance/readme_claim_inventory.py`,
  `scripts/acceptance/merge_readme_results.py`,
  `scripts/acceptance/readme_local_install.py`
- `backend/scripts/readme_acceptance/` (harness + local OpenAI/Anthropic/OAuth/
  MCP stub)
- README integration/catalog wiring:
  `backend/core/integration_business_catalog.py`, `main_api_app.py`
  (`/api/integrations` + `/business-catalog` only)
- Hybrid search relevance floor: `core/hybrid_search/documents_hybrid.py`
- GraphRAG route argument fix: `api/graphrag_routes.py`; extraction fallback:
  `core/graphrag_engine.py`
- MCP external-tool dispatch seam: `core/mcp_service.py`,
  `integrations/mcp_service.py` (external branch only)
- Workflow conductor context + node-versioning fixes:
  `core/workflow_endpoints.py`, `core/workflow_versioning_system.py`
- Episode creation null/list robustness: `core/episode_service.py`
- Tests added/updated: `tests/test_integration_business_catalog.py`,
  `tests/test_graphrag_pattern_fallback.py`,
  `tests/core/test_documents_hybrid.py`,
  `tests/test_covpush_wfengine.py`,
  `tests/test_covpush_w32_learning_graphrag_routes.py`

**Not owned / handed to Agent 1:**

- Live BYOK key refresh for the cached chat LLM service. A key stored after
  `LLMService` construction is not seen by chat (Settings → AI appears saved,
  chat still says no provider) until restart. Gateway works. Repro and details
  are in
  `docs/acceptance/readme_feature_readiness_2026-10-31/COVERAGE_REPORT_2026-10-31.md`
  §6. This is a shared Chat/lifecycle defect, not patched here.

**Result (integrated campaign):** 99/123 eligible functional claims verified
(80.5%). The earlier 100/123 (81.3%), 83/123 and 82/123 self-assessments are
withdrawn; the denominator is unchanged. Security 8/8 separately. 24 functional
claims remain unverified/partial/blocked/environment-limited or inaccurate;
none are counted. ORCH-08 remains **inaccurate** (delegation `max_depth` is
stored but not enforced). GOAL-01 is **verified**: the loop stops at 2/5 with
`objective_satisfied`, the 3/3 control returns `max_steps_exceeded`, and the
satisfied run persists as a successful execution/audit close-out. GOAL-05 is
verified across a real backend restart. ASK-03, ROUTE-03 and GRAPH-05 are
deliberately left partial rather than counted on weaker evidence.

The final audit (`evidence/CLAIM_AUDIT_2026-10-31_final.json`) downgrades only
ORACLE-01, GOV-05, TEAM-01, TEAM-05 and CORE-06. The earlier 18-claim audit is
retained as history. The broad campaign ran 130 claims with 0 failed and 0
group errors; the install/restart script and acceptance harness now exit
nonzero on assertion failure. The mandatory practical employee gate and the
substantive model-quality assessment are still separate open items. Cached
BYOK refresh code is in place (credential revision, dispatch backstop,
negative-cache reset), but the full Settings → Chat acceptance remains partial
because the chat router selects an unsupported catalog model in the harness.
Model access is now available locally; the assessment issue is failed
qualification/review enforcement, not unavailable infrastructure. Unsupported
approvals must fail qualification and human review must be enforced before
downstream action. Firecracker/KVM and live-provider environments remain
external blockers. No deployment, send, credential change or connected-system
write was performed.

**Worlds/ports:** harness worlds live under
`/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-*`;
the install check uses port 8137. No external credentials, sends, deployments
or writes to connected systems.

**Status:** README coverage target reached (99/123); awaiting independent
verifier agreement. The controlled practical-assignment gate passed for
retrieval/calculation/artifact/approval/durable reopen; process restart while
waiting, changed-revision invalidation, ambiguity, cancellation and duplicate
resume remain open. The substantive model-quality assessment remains blocked
on authorized model access. Not a release declaration.


---

## Session: Brennan Agent 2 — connected knowledge and accounting (2026-11-01)

**Branch/worktree:** `codex/brennan-knowledge-accounting-20261101` in
`/private/tmp/atom-brennan-agent2`, based on `587fbc251`.

**Goal:** provider contracts, WorkDrive/OneDrive knowledge, Zoho Books
bookkeeping and authoritative writeback for the Brennan business acceptance.
The accepted tags and the 123-claim denominator are unchanged.

**Owned in this session (do not refactor in parallel without a note):**

- `backend/core/provider_contract_matrix.py`, `backend/integrations/provider_errors.py`
- `backend/integrations/zoho_books_service.py`, `zoho_crm_service.py`,
  `zoho_inventory_service.py`, `zoho_workdrive_service.py`,
  `onedrive_service.py`, `microsoft365_service.py`,
  `universal_integration_service.py`
- `backend/core/brennan_connected_actions.py` (action registrations),
  `backend/core/drive_sync_checkpoints.py`,
  `backend/core/drive_tree_ingestion.py` (index_rows refactor)
- `backend/accounting/bookkeeping_proposal.py`, `sync_manager.py`,
  `document_processor.py`
- `backend/api/document_ingestion_routes.py` (drive sync status/page routes)
- tests under `backend/tests/unit/test_brennan_*` and the affected legacy
  accounting/provider tests
- `docs/engineering/brennan/AGENT_2_CONNECTED_READ_HANDOFF.md`

**Handoff for Agent 1:** the action names, schemas, receipt shape,
write-result vocabulary and executor-consumption requirement are in
`docs/engineering/brennan/AGENT_2_CONNECTED_READ_HANDOFF.md` (copied into this
checkout). Key request: `_action_registry_adapter` must map the action's
`action_result` (`applied|proven_not_applied|uncertain|conflict|unavailable`)
into the executor outcome instead of wrapping every return as `applied`.

**Verified in the Agent 2 branch:** provider contract matrix has zero issues;
focused provider/connected/accounting suite **223 passed**. The quote fixture
`A 2x100 + B 3x50 less 5% on B + freight 20, no tax` is exercised as
`362.50` in the estimate HTTP end-to-end test. Concurrent same-bill calls
produce one provider effect; changed remote readback is `conflict`; revoked
sweep is `proven_not_applied`; drive page restart resumes from the persisted
cursor and reports remote deletions without deleting memory.

**Boundaries:** no live Zoho/Microsoft token, read, refresh, write or send was
used. All verification is controlled/fixture-based. The prior one-use Outlook
send authorization remains exhausted.

**Status:** continuing Agent 2 work; awaiting Agent 1's branch handoff for the
joint Outlook RFQ → knowledge → quote → wait/restart → authorized Zoho update
→ Outlook draft campaign.

**Integration request for Agent 1 (2026-11-01, after `1ec6b8c37`):** the
executor's `_action_registry_adapter` still wraps every action return as
`status=applied`. Connected writes now return
`action_result=applied|proven_not_applied|uncertain|conflict|unavailable`;
use `core.brennan_connected_actions.action_executor_outcome(result)` so a
duplicate/validation refusal fails, and a changed readback or lost
confirmation becomes `uncertain` instead of a false completion. The exact
snippet is in `docs/engineering/brennan/AGENT_2_CONNECTED_READ_HANDOFF.md`.

**Agent 1 handoff received in shared history:** `1ec6b8c37` (commercial-update
actions, live progress, quote campaign), `a64a985c8` (retrieval evaluation),
`257da4862` (service-domain portability through the public assignment route).
Agent 2 still needs the branch handoff note/commit that says which executor
revision to integrate and which action registrations it consumed.

**Agent 2 latest HEAD (2026-11-01):** `a78ddeb7a` on
`codex/brennan-knowledge-accounting-20261101`. Added Outlook invoice/receipt
attachment reads (binary evidence, never send), generic `connected.*` action
aliases, vendor/CoA resolution, period/account validation and the live
qualification request. Focused suite **229 passed**; no live provider call.

**Joint integration candidate (2026-11-01):** branch
`codex/brennan-joint-20261101` in `/private/tmp/atom-brennan-joint`, HEAD
`8fc3460e9`. It merges Agent 2 at `a78ddeb7a` with Agent 1 at `bc56472b9` and
adds the executor mapping from `action_result` to `applied/failed/uncertain`.
Combined assignment + connected suite: **189 passed**; contract matrix has zero
issues. The joint controlled campaign computes **362.50** with Agent 1's
calculator, posts the estimate through `connected.books.create_estimate`,
reads back 362.50, and creates an Outlook draft without sending. This is a
controlled candidate, not live qualification. Agent 1 should adopt
`8fc3460e9`'s executor mapping in its branch (or confirm an equivalent).

**Joint candidate updated (2026-11-01):** `/private/tmp/atom-brennan-joint`
HEAD `2db65a034` merges Agent 2 `00b1a95ec` (tombstones for provider-deleted
rows, bare-read outcome mapping) with Agent 1 `bc56472b9`. Combined suite:
**190 passed**. Agent 2 branch standalone focused suite: **230 passed**.

**Agent 2 response to Agent 1 (2026-11-01):**
`/private/tmp/brennan-brief/AGENT2_RESPONSE.md`. Canonical quote record is the
Zoho Books estimate; connected actions, typed receipt fields, tabular row
evidence, outcome mapping and the controlled joint test are specified there.
The joint branch now includes the latest Agent 2 tabular-evidence sync;
combined suite **192 passed**.

**Final joint integration (2026-11-01):** `/private/tmp/atom-brennan-joint`
HEAD `4b2c61aa9` merges Agent 1 final `acd86a2aa` with Agent 2 `baeca20db`
(plus the executor outcome mapping and joint campaign test). Combined
assignment + connected suite: **197 passed**. Extended affected assignment
suite + joint campaign: **289 passed**. Provider contract matrix: zero issues.
This is the reviewable controlled candidate; live qualification still needs
the account/token request in `AGENT_2_LIVE_QUALIFICATION_REQUEST.md`.

**Joint candidate final sync (2026-11-01):** HEAD `6cea89476`.
Includes Agent 2 canonical `core/connected_actions.py` (reference shim kept),
tabular row evidence, deletion/revocation tombstones and Agent 1 final
`acd86a2aa`. Combined assignment + connected suite: **200 passed**. Extended
assignment suite + joint campaign was **289 passed** before the final module
rename; the rename suites are green. No live provider call.

**Final controlled state (2026-11-01):** Agent 2 branch
`codex/brennan-knowledge-accounting-20261101` HEAD `883586234`, clean. Joint
branch `codex/brennan-joint-20261101` HEAD `51d4369fd`, clean. Combined
assignment + connected suite: **200 passed**. Full accounting comparison vs
Agent 1 baseline: 25 pre-existing failures on both sides, no new Agent 2
failures. Provider contract matrix: zero issues. No live provider call, send,
tag move or acceptance-status change.

**Final controlled candidate (2026-11-01, supersedes the previous joint head):**
Agent 2 `codex/brennan-knowledge-accounting-20261101` HEAD `59c9f4df3`
(clean). Joint `codex/brennan-joint-20261101` HEAD `ddcdb838a` (clean).
Combined assignment + connected suite: **202 passed**; contract matrix zero
issues on both. Estimate writes now require an exact `reference_number` and
sweep the complete estimate list before create, matching the bill controls.
No live provider call, send, tag move or acceptance-status change.

**Correction / final heads:** Agent 2 `9600f783e`; joint `6165693db`.
Both clean. Joint combined suite remains **202 passed**. Accounting extraction
now refuses an unknown vendor by default (obligation, not a silent create).

**Final heads after receipt identity sync:** Agent 2 `ddcf2a787`; joint
`b9c8ba654`. Both clean. Focused joint regression after the sync: 166 passed.

**Verified final joint HEAD:** `b9c8ba654` — combined assignment + connected
suite **202 passed** after the receipt identity sync. Agent 2 branch
`ddcf2a787`, Agent 1 branch `acd86a2aa`. All worktrees clean.

**Repair batch addendum (2026-11-01):** Agent 2 readback repair is in
`codex/brennan-knowledge-accounting-20261101` at `d5a30df26` (plus canvas task
note `931acdadf`). It adds complete-object verification for estimates/bills,
sparse-vs-mismatch semantics, one bounded readback retry without a second
create, and unit/action controls in
`backend/tests/unit/test_brennan_commercial_readback.py`. Joint worktree has
temporary integration tests for the real connected handler and document-byte
data flow; these are being finalized after Agent 1 commits the pricing
obligation/executor repairs. No live provider call.

**User-authored canvases addendum (2026-11-01):** added as a post-repair task
from `docs/engineering/USER_AUTHORED_CANVASES.md`. Agent 2 scope is recorded
in `docs/engineering/brennan/AGENT_2_CANVAS_TASKS.md`: provider bindings,
version/provenance receipts, canvas-action mapping, complete readback, sandbox
refusal, and no authority from canvas text. Not started in this repair batch.

**Blocking repair batch candidate (2026-11-01):**
`codex/brennan-joint-review-20261101` in `/private/tmp/atom-brennan-review`
at `e984185ea` is the single review candidate.
- Agent 1: `0aebf372e` (discount true/false/unknown, completion oracle,
  durable line obligations, executor outcome hardening).
- Agent 2: `7a006c147` (complete commercial readback, sparse vs mismatch,
  bounded retry, estimate/bill normalization).
- Joint: one assignment reads controlled WorkDrive bytes, maps rows, pauses
  on a missing discount qualification, resumes, computes 362.50, creates one
  estimate, verifies the complete readback, and creates the Outlook draft
  without sending. Changed file bytes produce 376.75.
- Real connected handler uncertainty control: approval -> uncertain envelope
  -> dependent draft blocked -> restart no new create -> reconcile -> draft.
- Tests: joint core 236 passed; Agent 2 focused 273; Agent 1 required 164;
  public route journeys 4; extended 334 passed/4 pre-existing baseline
  failures. Browser not runnable (no frontend node_modules); route tests used.
- No live provider action. Canvas addendum recorded as a post-repair task.

**Single candidate correction:** `codex/brennan-joint-review-20261101`
(`8b543221b`) is the only review candidate. The older
`codex/brennan-joint-20261101` branch is **SUPERSEDED** (partial intermediate
commits only; do not use as a release candidate). Component branches remain
Agent 1 `0aebf372e` and Agent 2 `7a006c147`. Joint core suite is **241 passed**.

**Candidate documentation sync:** review candidate now `e01efb49d`; the
connected-read handoff reflects the hardened executor outcome classifier.

**Final focused repair candidate (2026-11-01):**
`codex/brennan-joint-review-20261101` at `51715ce15` is the sole review
candidate.
- Cap/fixed/tier/formula/unsupported-basis and unknown material pricing fields
  are rejected before arithmetic; public route refuses the plan and no action
  runs.
- Frontend dependencies and Playwright Chromium installed in the review
  worktree; the real Assignments page ran the connected bytes -> clarification
  -> leave -> backend restart -> changed source -> corrected continuation ->
  verified 376.75 estimate -> Outlook draft (376.75) journey. **9/9 browser
  checks passed**; evidence in
  `docs/acceptance/evidence/brennan_connected_browser_20261101/`.
- Final tests: joint core **251 passed**; Agent 2 focused **273**; Agent 1
  required **174**. No live provider or send.

**Final executable-transfer and production-browser candidate (2026-11-02):**
`codex/brennan-joint-review-20261101` at `c442cd9d7`.
- Integrated the shared executable serialization budget: 79/80/81 rows,
  byte-exact base64, multibyte content, complete receipts, final calculation,
  restart, 501-row partial refusal, oversized content, aggregate/key/nested
  bounds and post-effect uncertainty. Data-transfer boundary controls: **25
  passed**; joint core **263 passed**.
- Browser acceptance server now replaces only the provider service; the
  production `connected.workdrive.read_file` action/parser/coverage/executor
  run unchanged. Real backend restart PIDs recorded, source v1 -> v2 bound
  into read receipt and calculated rows, estimate **376.75**, Outlook draft
  **376.75**, no send. Browser: **14/14 checks passed**.
- Evidence: `docs/acceptance/evidence/brennan_connected_browser_20261101/`.
