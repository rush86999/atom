# Never-autonomous task baskets — behavior, limits and CI selection

**Status: documentation and CI selection only. Not verified, not shipped.**
This record describes the owner-requested optional never-autonomous task
baskets as implemented in this worktree and records their additive test
selection. Root has not run the ordinary browser journey, the final broader
backend/frontend suites have not been run, and the change is not merged or
post-merge-CI verified. Nothing here promotes the feature to a verified or
shipped state, and nothing here re-scores readiness.

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
  the shipped access point in this source. The page passes `canvasId` and an
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

### Actual local validation, including failures

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

## What remains open

- Root browser verification of the canvas Autonomy tab: empty default, rule
  create/edit/disable/delete, a real matched task and the specific-execution
  approval, plus the fail-closed unknown path.
- The separately owned approval-decision atomicity repair and its regressions.
- Final broader backend/frontend suites, current-main post-merge CI, and the
  actual merge.
- Classifier quality/recall beyond the described lexical limits; no semantic or
  model-quality claim is made.

The original **143 claims / 18 goals**, historical scores and
`app_complete: false` remain intact. This document marks no goal or claim
complete and does not regrade readiness.
