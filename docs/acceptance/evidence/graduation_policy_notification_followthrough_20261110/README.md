# Graduation notification await + unsupported policy selector follow-through (2026-11-10)

Status: focused successor checkpoint for independent root verification. This is
**not** a full-graduation, app-completion, or model-competence claim.

## Relationship to the prior freeze

- Prior frozen checkpoint: `7be407677a2d66908228c3b9464eabf739dbf372`
- Prior packet: `docs/acceptance/evidence/graduation_qualification_ui_scope_20261110/`
  (bytes preserved; its final-10 proof remains bound to prior backend source
  `cf2c7c707` and is **not** claimed as this successor's gate).
- **New backend successor:** `93864297ce7a9c77b2c35e05183dec294307d4a7`
- Evidence commit: the commit that adds this directory; it only adds evidence
  files and does not change product source.

## Two finite defects repaired

### 1. Internal graduation notification

`async promote_agent_decision` previously called
`loop.run_until_complete(notif_svc.send_notification(...))` while already inside
the promotion coroutine. That raised `This event loop is already running`,
emitted a never-awaited coroutine warning, and lost the internal notification.

The fix awaits `NotificationService.send_notification` normally, **after** the
durable promotion commit. No new event loop, thread, background runner, store,
schema, or lifecycle was added.

- Actual scratch promotion persists exactly one internal `agent_graduated`
  `Notification` row in the correct tenant/workspace.
- Duplicate operation replay returns before the notification path and adds no
  second row.
- Injected notification failure (raise or soft-fail) leaves the committed
  promotion and history intact and never fabricates delivery.
- Final gate logs contain **zero** `was never awaited` warnings.

### 2. Unsupported owner policy selectors

`AssessmentPolicy` accepted `default_required=False` and nonempty
`exceptions.*.domains` but ignored both. Strict validation now rejects those
currently unsupported non-default selectors as `configuration_required` with
meaningful errors naming the unsupported field. Owner configuration is never
silently ignored.

Preserved and still supported:

- `default_required=True`
- empty `exceptions.*.domains`
- per-tier gates (`tiers.intern/supervised/autonomous`)
- exact owner-listed `agent_ids` exceptions
- nonblank exception reasons
- policy revision/digest and CAS behavior
- current earned tiers and domain action governance

No broad or domain exemption is inferred from mutable agent category/name/
metadata, and no new registry was added.

## Verified gates

| Gate | Command | Result |
|---|---|---|
| **Root combined policy+notification probe at final source** | unchanged `/private/tmp/root-graduation-unused-policy-independent-20261110.py` + `/private/tmp/root-graduation-notification-independent-20261110.py` | **5 passed, exit 0, same_source true, 7/7 captured source parity** |
| Backend qualification controls | scratch SQLite, `pytest tests/api/test_graduation_qualification_join.py -q` | **43 passed** |
| New notification/policy twins | focused selection | **8 passed** |
| Notification service unit tests | `pytest tests/unit/core/test_notification_service.py -q` | **10 passed** |
| Root policy probe after fix | unchanged policy probe | **3 passed** |
| Root notification probe after fix | unchanged notification probe | **2 passed** |

The authoritative source-bound proof is `root-combined-5-review.json` plus
`root-combined-5-controls.log`: 5 passed, `actual_exit: 0`, `same_source: true`,
and all seven captured source hashes match the successor tree.

## Preserved baselines and disclosed warnings

Pre-repair independent baselines are retained, not erased:

- `root-policy-baseline-review.json`:
  `/private/tmp/root-graduation-unused-policy-independent-20261110-ue24nik6`
  — **2 FAIL / 1 PASS** before repair.
- `root-notification-baseline-review.json`:
  `/private/tmp/root-graduation-notification-independent-20261110-9guff86o`
  — **1 FAIL / 1 PASS** before repair.

Remaining warnings are disclosed as-is, not hidden or suppressed: the
FastAPI `regex` deprecation warning and the root `pytest_freezegun` plugin
deprecation warnings. There are no never-awaited coroutine warnings in the
final logs.

`affected-collection-gap.log` records a pre-existing sparse-checkout gap:
`tests/test_assessment_rules_semantics.py` cannot import
`substantive_assessment_campaign` in this worktree. That is a checkout gap, not
a product failure; the notification-service unit suite ran and passed 10/10.

## Honest scope

- Scratch SQLite only. No live development DB, PostgreSQL, provider, model,
  browser, deployment, external email, or external notification send was used.
- Internal `Notification` persistence only; the email leaf was disabled in the
  probes/tests.
- No CI yaml, goal index, PR, merge, new dependency, store, schema, judge, or
  lifecycle change.
- No broad graduation or model-competence acceptance.
