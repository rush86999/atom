# Never-autonomous task baskets — behavior, limits and CI selection

**Status at qualification (pre-merge, 2026-11-16): independently verified locally; merge and exact-head CI pending.**
Product source `d271e25ebc1474cc3fa51fda5f6d2acd8650e51d` passed the
bounded checks below. This is a task-boundary feature qualification, not a
full-app readiness or model-quality claim. The original 143 claims / 18 goals
and `app_complete: false` remain unchanged.

## Release status — merged 2026-11-17

PR [#977](https://github.com/rush86999/atom/pull/977) merged as
`0e9b0dfc9c7ee41b047714c1e1a5fc8a1f2bb464` (tree
`9386a4861e9ed2fef14d96fda64fc5cedba6b3b3`, parent #976
`8b48dd84ad845e79c27bfcfa45cae669586d2b88`). Its exact PR head
`488e956c688383d2a220b05442fb47b51c8cc4f4` had all **15** check runs
successful. Post-merge main CI run
[43985428885](https://github.com/rush86999/atom/actions/runs/43985428885) and
Docker run [43985428863](https://github.com/rush86999/atom/actions/runs/43985428863)
both completed successfully on the exact merge commit. Root independently
re-queried both workflow identities and conclusions on 2026-11-17.

The merge and exact-head CI do not widen the qualification below: the browser
journey, 319 backend checks, 642 CI-contract checks, 110 UI/type checks and
build remain bound to their recorded source. Classification is still lexical,
SQLite was the only migration exercised, and real-model quality and PostgreSQL
concurrency remain unqualified. The current navigation overlay is
[the 2026-11-17 goal map](CURRENT_GOAL_MAP_2026_11_17.md).

The owner requirement is optional, never-autonomous task baskets identified by
difficulty/category/domain combinations. The feature is an **opt-in veto**, not
a new scheduler, classifier or policy registry: the basket list is empty by
default, and a matching task asks a human for one specific execution while the
existing topic/maturity/trust controls continue to run independently.

## Where users reach it

- **Canvas page:** `/canvas/[id]` → right-side **Autonomy** tab
  (`data-testid="canvas-side-tab-autonomy"`), rendered by
  `frontend-nextjs/components/canvas/AutonomyPanel.tsx`.
- **No standalone Settings page hosts these rules.** The canvas Autonomy tab is
  the access point in this source. The page passes `canvasId` and an
  optional accessible `agentId` to the panel; `canvas_id`/`agent_id` affect the
  topic grouping and live gate display only.
- **Rules are user-global, not canvas-local.** The panel is reached from a
  canvas, but every rule is keyed by the authenticated `user_id` and is
  therefore visible on every canvas Autonomy tab for that owner. Canvas
  ownership is checked before canvas context is used; a shared/public canvas
  degrades to the general topic set instead of leaking another user's canvas
  metadata or agent stats.
- **API:** `GET/POST /api/autonomy/never-rules`,
  `PUT/DELETE /api/autonomy/never-rules/{rule_id}`. The existing topic controls
  remain `GET /api/autonomy/topics` and
  `PUT /api/autonomy/topics/{topic}`. All require the authenticated owner;
  cross-user rule ids are not found, and the UI renders a distinct
  owner-only/forbidden state rather than pretending the list is empty.
- **No new runtime setting or feature flag.** Opt-in is creating and enabling a
  rule. No environment variable is required.

## Empty default and UI semantics

- The durable rule list starts empty. With **no enabled rules**, task behavior
  is exactly the pre-existing topic mode plus maturity/trust/calibration/
  revocation gates.
- The UI shows the explicit empty state: “No task rules yet. Everything
  follows its topic setting and normal maturity gates. Add a rule only for
  tasks that must always ask you.”
- A saved **disabled** rule stays visible/editable but never matches. Loading,
  empty, malformed-200/unsupported, forbidden and read-error states are
  distinct; a malformed success response is never rendered as an empty list.
- Creating, editing, disabling or deleting a rule never writes a topic mode or
  default. The panel only configures rules and renders the server’s verdict; it
  does not compute a match or match count locally.
- Per-rule saves send `expected_revision` when the loaded existing rule carries
  a server revision, and use `retry:false` for all rule writes. A `409` keeps
  the draft, disables Save and requires an explicit reload; it never claims
  success or silently retries.
- Unknown stored domain/value selections are preserved when an existing rule is
  edited. The option vocabularies come from the server, and the custom-domain
  hint explicitly says the suggestions are not exhaustive.

## Dimensions and matching rules

The rule shape is:

```json
{"difficulty": ["advanced"], "category": ["code"], "domain": ["finance"]}
```

- **Difficulty:** `simple`, `moderate`, `complex`, `advanced`.
- **Category:** `code`, `math`, `qa`, `extraction`, `planning`, `prose`.
- **Domain:** a lower-case slug (`^[a-z][a-z0-9_-]{1,63}$`). Suggested values
  are `finance`, `hr`, `marketing`, `operations`, `sales`, `support`; custom
  slugs such as `legal-ops` are allowed.
- **AND across dimensions:** every dimension present in one rule must match.
- **OR inside a dimension:** several values in the same dimension are
  alternatives.
- An omitted dimension is unspecified (a wildcard), not “match everything”.
  At least one non-empty dimension is required; a filterless rule is rejected.
- **ANY enabled rule** is sufficient to require review. Disabled rules are
  inert. Multiple matched rules are reported by name/id in the review reason.
- Rules are enabled/disabled per rule; there is no separate global basket
  switch beyond the empty default.

The panel repeats the same contract in its help text (“every dimension you set
must match … several values in one dimension are alternatives. Any enabled rule
is enough to require your approval.”) so it cannot drift from the evaluator.

## Specific-task approval

A matched basket produces a **task-level** human admission before the first
model call/output, even when the task performs no writes or tool calls. The
HITL action type is `never_autonomous_task`.

The approval is for **one exact task execution**, not a blanket waiver and not
a rule change:

- It binds the execution id, the full canonical task material fingerprint, the
  reviewed rule ids **and revisions**, the persisted owner, and the trusted task
  profile. The fingerprint hashes complete task material; it is not truncated
  to a display limit. Unsupported material fails closed with a type-only error.
- Editing a matched rule (new revision), adding a rule, changing the owner/
  scope, changing the execution, or changing the task material means the old
  approval does not cover the new decision. A new task or reclassified task
  needs a fresh review.
- A cold resume reuses only the exact durable authorized admission row: same
  execution, fingerprint, owner/scope, reviewed revisions and a currently
  authorized reviewer. A resume boolean in a payload is not authority.
- If the policy changes while a waiter is pending, the warm path returns
  `policy_changed`/fresh-review rather than granting. If an approval cannot be
  verified or bound, the result is an awaiting-review or controlled-block
  payload, never silent execution.
- Approval never widens or edits the rule, and it does not disable the
  independent topic/maturity/trust/calibration/revocation gates for the rest of
  the task.

Reviewer authority is shared with the existing HITL surfaces, not a second
policy map: a real, active principal in the exact canonical tenant/workspace
must be the persisted owner or a team-lead-or-higher supervisor, and must
satisfy both persisted `required_role` locations. Missing, unknown, inactive,
foreign or rewired bindings are refused (scope refusal is 404; insufficient
authority is 403; stale/rewritten material is 409 at the mounted approval
surfaces).

The separate approval-decision atomicity repair is being handled by another
worker in a separate worktree. This document does not claim that repair, does
not edit its product files/tests, and does not regrade its behavior. When that
worker adds regressions to the existing
`tests/test_never_autonomous_review_authority.py` file, the complete-file CI
selection below picks them up automatically.

## Fail-closed unknown and outage behavior

Unknown is **not** “doesn’t match” and is not a wildcard that bypasses a rule:

- If a rule constrains a dimension whose task value is missing, empty or
  untrusted, the rule is a **potential** match and human review is required.
  The panel renders “may apply … classification data is unavailable” and lists
  the rules only when the server names them.
- A task profile with no trustworthy classification is represented by
  `build_unknown_task_profile()` (a normal server-sourced profile with unknown
  dimensions). Autonomous entry points evaluate configured rules against it; a
  potentially applicable rule still gates the task.
- A policy-store read failure fails **closed** to review. Only the exact case
  of a never-provisioned/absent rules table is treated as “no policy”. A
  corrupt/unreadable persisted rule is surfaced as a potential match, never
  silently dropped.
- If admission evaluation itself fails, the entry returns a controlled blocked
  payload with human approval required. If the task approval exists but cannot
  be trusted/bound, the task stays awaiting a fresh review rather than running.
  No model/memory/effect is reached on these paths.
- Policy-store failure messages never name a matched rule, because no rule was
  proven to match.

## Existing independent autonomy controls

These baskets are additive to, and do not replace or demote, the pre-existing
controls:

- **Per-topic modes:** `human_always`, `auto_if_mature`,
  `auto_until_corrected`. Topic modes and defaults are unchanged.
- **Governance maturity** for the topic’s action (the same complexity lookup the
  runtime uses).
- **Skill-scoped trust** (flag-gated; disabled by default means neutral-pass).
- **Trust-calibration authorization** (flag-gated; disabled by default means
  neutral-pass).
- **Verified-regression revocation.**
- **Correction-reset autonomy cycle** under `auto_until_corrected`.

Task admission is an additional veto. When a rule matches, the task proposes/
requires review even if every other control would allow execution. When no rule
matches, the other controls alone decide, exactly as before. Career graduation
remains agent-wide and is not demoted by a basket rule.

## Truthful classifier support limits

Classification reuses existing deterministic, local classifiers; there is no
new model, no LLM judgment and no provider call in this path. The classifiers
are deliberately coarse and **do not promise semantic understanding or model
quality**:

- **Difficulty** reuses `core.llm.byok_handler.classify_query_complexity` (the
  existing routing classifier): estimated length, regex vocabulary weights,
  code-fence/technical corroboration and an optional task-type override. This
  is task difficulty, **not** the governance `ACTION_COMPLEXITY` integer.
- **Category** reuses the verification cascade’s coarse `TaskDomain` /
  `infer_domain` keyword table. Ties and no-hit text return `unknown`, which the
  profile maps to “not classified.”
- **Domain** reuses `core.domain_attribution.resolve_domain`. The task-profile
  builder calls it with the static business-domain keyword table (no learned
  vocabulary argument), and no match returns no domain. The six suggested
  domains are not exhaustive; custom slugs are accepted.
- A lexical classifier can miss paraphrases or classify a present value
  differently from a human’s reading. Missing values are handled
  conservatively (potential match → review), but a **present** misclassified
  value is treated as authoritative. No semantic-match, recall, precision or
  model-quality guarantee is claimed.
- The UI’s “not classified” note is deliberate: while any rule is enabled,
  absent metadata fails toward review.

## Migration and storage

- Alembic revision `20261116_action_autonomy_rules` (down revision
  `20261113_user_session_token_jti`) creates `action_autonomy_rules`.
- It is a **guarded create-only** migration: it returns without changes if the
  table already exists, reads/backfills/rewrites **no live rows**, and works for
  SQLite and PostgreSQL. Fresh `Base.metadata.create_all` deployments already
  have the table.
- Columns: id, user_id, nullable tenant_id/workspace_id, name (≤120),
  enabled, match_json, revision, created_at, updated_at; indexes on owner and
  owner/tenant/workspace.
- The table starts empty; there is no data migration and no default rule.
  Downgrade drops the table/indexes only if present.
- Writes are fenced by a durable `(id, owner, revision)` conditional UPDATE;
  a peer commit makes the stale writer claim zero rows, roll back and report the
  current revision (mounted PUT → 409). This is persistence, not a second
  policy layer.

## CI selection in this change (additive only)

Two new steps sit in existing jobs; every prior command, environment, gate,
trigger and protection is preserved:

- `backend-core` → **Run never-autonomous task boundary controls** runs all
  five complete files, each in its own Python process with its own absolute
  runner-temp SQLite file under one `mktemp` root:
  `tests/test_never_autonomous_rules.py`,
  `tests/test_never_autonomous_task_scope.py`,
  `tests/test_never_autonomous_rule_write_fences.py`,
  `tests/test_never_autonomous_review_authority.py`,
  `tests/test_never_autonomous_entry_identity.py`.
  `TESTING=1`, `PYTEST_VERSION=ci` and `PYTHON_DOTENV_DISABLED=1` keep the lane
  off `.env` and the repo dev DB. No node-id subsets, deselect, skip,
  `continue-on-error` or changed required check.
- `frontend-typecheck` → **Run never-autonomous task basket UI controls** runs
  the complete `components/canvas/__tests__/AutonomyPanel.test.tsx`. The canvas
  host integration remains in the pre-existing “Native canvas save and
  uncertain-outcome controls” step, which already selects
  `tests/pages/canvas-detail.test.tsx`; that selection is unchanged.
- The parsed backend step was appended to
  `backend/tests/fixtures/ci_backend_additions.json` so the backend lane
  preservation ledger still matches exactly.

### Earlier CI-selection validation (source `63a784823`, before integration repair)

- `tests/test_ci_backend_lane_contract.py tests/test_quickstart_matrix_contract.py`
  → **642 passed** in this worktree, with an absolute scratch `DATABASE_URL`.
- `bash -n` on both new `run` blocks → clean.
- The five-file backend selection was run locally against isolated scratch
  SQLite using the exact CI-shaped per-file loop:
  **4 failed, 68 passed** across the five separate processes. The four failures
  are all in `tests/test_never_autonomous_entry_identity.py` (that file alone:
  **4 failed, 14 passed**); the other four files are **54 passed**. The failures
  are the approval-receipt/outage branches owned by the separate atomicity
  repair, not a reason to skip or deselect anything here:
  `test_changed_suffix_beyond_8000_cannot_resume_old_approval`,
  `test_identical_full_task_cold_resume_reuses_approval`,
  `test_ungrantable_classification_outage_blocks_without_model`, and
  `test_recovery_requires_fresh_review_because_profile_changed`.
  A separate single-process diagnostic run of all five files reported
  **5 failed, 67 passed**; it additionally failed
  `test_workflow_unbound_profile_still_pauses_before_first_step`, which passes
  in its own process. That is ordering/state shared by one collector, which is
  why the CI step keeps one process per file; the extra failure is recorded
  here rather than hidden.
- The UI Jest file was **not run in this pass**: `frontend-nextjs/node_modules`
  is absent, no install was attempted, and no cached-dependency or browser run
  is claimed here.
- No live database, server, browser, credential, network or model provider was
  used.

## Independent integration qualification

- Backend source `134fc85f365c3fd895c03d7bd51d69aab2d84b78`:
  all five complete never-autonomous files **78 passed**; nine affected
  approval/checkpoint/2FA/workflow files **163 passed**. No network or live
  database was available. Backend bytes were unchanged through `b8e9b592d`; the later CI integration repair below is separately qualified.
- The original real second-session rejection race now returns **409**, keeps
  the peer rejection, and grants no durable admission. The rule-update race,
  foreign reviewer refusal, full-material fingerprint, reused-context task
  separation and classifier-outage cases were independently exercised.
- CI/docs source `ef12fdf908052c9dae31b899b058c00c7a9c116b`:
  both complete lane-preservation contracts **642 passed**. Later UI repair
  changes no workflow or backend selection.
- Frontend source `b8e9b592d`: complete AutonomyPanel, canvas-detail and
  approvals-page files **110 passed**; configured TypeScript check
  (`--noEmit --incremental false`) and production webpack build passed using
  cached dependencies with networking denied.
- Existing agent/assignment/workflow/MCP neighborhood at `ef12fdf90`: **298 passed, 2 failed,
  2 skipped**, versus current main `8b48dd84a`: **297 passed, the same 2 failed,
  2 skipped**. The two failures attempt hardcoded `/tmp/w85_cite.txt` and
  `/tmp/evil.pdf` writes outside the root test's permitted temporary tree.
- Existing five-file Meta-agent selection: **401 passed, 2 failed, 6 skipped**
  on both candidate `ef12fdf90` and current main. Failure identities and assertions match
  (`test_spawn_failure_handling`, `test_core_tools_names_constant`, with
  the latter expecting 28 tools where both sources have 30). These are
  recorded paired baseline failures, not represented as a green suite; no
  test or required check was skipped or bypassed to certify this feature.
- Scratch SQLite migration: creates an empty rule table and four indexes;
  repeating upgrade preserves an existing sentinel rule. PostgreSQL runtime
  migration was **not** exercised.
- Normal browser sign-in on an isolated production-built app: empty default,
  native canvas creation, combined difficulty/domain rule creation and page
  reload; edit, disable, enable, confirmed delete; real two-tab stale save
  **409** preserves the draft and explicit reload shows the winning revision.
  After full app restart, fresh sign-in reads the same rule/dimensions with
  **zero rule writes**.
- The initial approval queue hid task text behind a truncated JSON summary.
  The repaired card displays the server-recorded task, classification and
  reason; its separate technical details retain the binding, and the immutable
  task has no Modify control. A real signed-in browser approved one naturally
  classified complex/math/finance **synthetic** task through the public queue
  (**HTTP 200**). With the app stopped, a fresh database session admitted only
  that exact task; changed task material required fresh review. This fixture
  used the real approval writer but no running employee, provider or model;
  the check does not claim model output quality or a completed worker run.

Browser preparation failures were retained and corrected before proceeding;
completed mutations were not replayed. Initial raw-create response capture
was overwritten by a later read-only observation, so no retained raw-create
response is claimed. Native extended-edit/conflict responses, UI state,
approval response and cold-resume adjudication were retained separately.

### CI integration repair and final backend verification

The first PR head `cc5562da8` failed the required backend-core and
backend-oracle lanes. The merge monitor stopped; no failed check was bypassed.
Two test doubles still accepted the old governance signature and rejected
`task_profile`/`never_clearance`, preventing the intended real dispatch
assertions from running. Their named parameters now mirror the production
interface; all original outcome and durability assertions remain. The BPE
fixture additionally checks the exact trusted profile and execution context.

CI also exposed a real ordering defect: admission could stop a resumed task
before reloading an existing uncertain-effect claim. A policy/storage fault
then hid reconciliation provenance. The existing uncertainty ledger now loads
before admission, and an admission stop carries any unresolved operations
forward. The policy verdict stays blocked/awaiting approval; reconciliation
metadata cannot grant approval or report success. A new real-claim regression
combines a matching finance rule, an already-landed uncertain effect and an
unreadable policy/claim store, preserving both safeguards.

Independent root verification on joined product `d271e25eb`:
**319 passed, no skips** across all five complete task-rule files, nine
approval/2FA/workflow files, and the complete BPE, oracle, retry, reconciliation
and run-admission files. Tests used isolated absolute SQLite databases with
networking denied. The frontend, API, policy and workflow definitions are
unchanged by these repairs; earlier frontend/build/browser evidence remains
bound to its stated source, rather than being relabeled as a rerun. The
replacement PR head still required fresh CI/security and main verification at
qualification; the release status above records the later exact-head and merge
result, without claiming post-merge green.

## Remaining release and product limits

- At qualification, exact-head PR CI/security and main-branch merge/post-merge
  workflows still had to pass. The later release status above records the merge
  and 15/15 exact-head result; post-merge #977 CI/Docker were still running at
  this read, so no post-merge green is claimed.
- Classification uses the existing deterministic heuristics described above;
  semantic recall/precision and model-quality guarantees remain unqualified.
- Only SQLite migration/runtime was exercised locally. No live customer data,
  hosted deployment, paid inference or external integration was used.

The original **143 claims / 18 goals**, historical scores and
`app_complete: false` remain intact. This document marks no original goal or
claim complete and does not regrade readiness.
