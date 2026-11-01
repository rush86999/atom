# Agent 1 completion bundle — 2026-11-01

One source-bound bundle for the runtime batch, Campaign A (complex teaching),
Campaign C (elapsed durable assignment) and the sibling recovery controls.
Hosted deployment, live sends and broad model campaigns were not performed.

## 1. Identified product source

| Item | Value |
|---|---|
| Repository HEAD at assembly | `d535aa7d3` |
| Product trees at HEAD | `backend/` = `715969f01d23`, `frontend-nextjs/` = `c921cb82e784` |
| Serving backend source (all live runs) | `cf102eeac1ce-dirty.b0c55aa8fb39` (Campaign C) and `cf102eeac1ce-dirty.13b4ffec1724` (Campaign A) |
| Product diff serving → HEAD | **empty** for `backend/` and `frontend-nextjs/` (`git diff cf102eeac1ce..HEAD -- backend frontend-nextjs`) |
| C before the wait | backend tree `68aa1a826d0d` (`2d01d31772da`) |
| C restart/resume | backend tree `715969f01d23` (`cf102eeac1ce`) |

The checkout is **not** clean: one harness file is modified
(`scripts/acceptance/launch_integrated_local_candidate.sh`, which gains
`ATOM_FRONTEND_DIR`). That is the launcher, not product code, and it is included
in this bundle. No product file is uncommitted.

Campaign C deliberately spans a product upgrade **without resetting its clock**:
the wait was created at 15:37:56Z by `2d01…`; the restart at 16:42Z moved the
same stores to `cf102…`, which contains the durable-wait wall-budget fixes
(`02f3ae2cd`, `198b64e51`, `5b8bf1e0c`, `a1862fec7`). The pre-wait receipts and
teaching revision survived unchanged.

### Launcher configuration (both worlds)

```
DATABASE_URL=sqlite:///<world>/atom.db
ATOM_DATA_DIR=<world>/data            LANCEDB_URI=<world>/data/atom_memory
ATOM_OFFICE_DIR=<world>/data/office   ATOM_ASSIGNMENT_OUTPUT_DIR=<world>/data/assignments
ATOM_TASK_LOCK_DIR=<world>/data/task_locks
ATOM_EMAIL_ATTACHMENT_DIR=<world>/data/email_attachments
ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT=1
ATOM_ASSIGNMENT_OUTBOX=<world>/controlled-outbox.jsonl
ATOM_TASK_LIFECYCLE_ENABLED=1  ATOM_PRODUCT_PROFILE=core
ATOM_LOCAL_ONLY=true  ENABLE_SCHEDULER=false  ENABLE_INGESTION_SYNC=false
```

| World | Backend / frontend | Frontend build |
|---|---|---|
| Campaign C `long_run_20261101` | 8081 / 3141 | `fe-8081`, BUILD_ID `7QE4enTmi2vMZH8OCsPQONov` |
| Campaign A `campaign_a_20261101` | 8083 / 3143 | `fe-8083` (retargeted from build `XRUHZA9NReomkgqvnxr-T441`) |
| Recovery controls | 8090 / 3003 | `fe-8090` (same build id) |

No other agent's world, port, store or process was stopped or reused.
Ports 8071/3130 and 8082/8084 were observed busy and left alone.

## 2. Campaign C — durable assignment across a product upgrade

| Event | UTC |
|---|---|
| Start | `15:04:44Z` |
| Productive work (teaching, conflict/qualification refusals, upload, mapping) | `15:04–15:37Z` |
| Durable external wait reached | `15:37:56Z` |
| Real backend stop → restart against the same stores | `16:42:15Z` |
| Correlated answer delivered, assignment completed | `17:26:58Z` |
| Elapsed after the wait at completion | **1 h 49 m** |

**This run does not satisfy the user's 17:37:56Z gate**: it resumed 11 minutes
early. It is kept as the **upgrade/restart control**, not as the elapsed gate:
it proves a waiting assignment survives a real backend restart that moves the
backend tree from `68aa1a826d0d` to `715969f01d23`, keeps its snapshot, and
completes exactly once. Its 2 h 22 m from campaign start is real but is not
the measure the owner set.

A fresh sibling, **Campaign C2** (`long_run_20261101_b`), was started at
`17:55:59Z` to carry the elapsed gate with an independent run identity:
`cac9cbd6-f72b-4fbb-b106-f0990fc5b191`, assignment
`asg-bc8171a465894137`, revision `851207ec455336d3+cabba8f03b6894fa+map`,
`source-1` applied `110.00` (15.10 + 20.20 + 30.30 + 44.40), durable wait
reached `18:04:53Z`, correlation `quote-missing-currency-2`. C2 is not resumed
before **20:04:53Z**. C's clock was not reset, and C's evidence remains intact.

The C run waited **1 h 48 m** (`budget.paused_seconds = 6525.69`) against a
`max_wall_seconds = 900` budget; the wall-budget fix is what allows the resume.

### Receipts (authoritative assignment steps, not the summary counter)

| Step | Status | Operation | Attempts | Result |
|---|---|---|---|---|
| `source-1` | `applied` | `6fff72ff-1332-4e13-82e7-b34714bdfad9` | **1** | `400.00 USD`, rows C2–C4 |
| `wait` | `applied` | `611d3ac6-6206-4314-817c-c65c61182ded` | 1 | `Delivery term: net 45 days…` |
| `deliverable-1` | `applied` | `1d273a88-e659-450c-a0f9-729d2b5e9eef` | 0 | DOCX |
| `send` | `applied` | `7243572b-25c1-448f-91f0-99de543cbba7` | 0 | controlled provider accepted |

`goal_runs.steps_executed = 0` is a stale summary counter. The completed work is
the `source-1` receipt above: `sum of Gross Amount = 400.00 USD across 3 rows`,
with per-row receipts `C2=100.00`, `C3=250.50`, `C4=49.50` and
`observed_status="confirmed"`. Independent arithmetic: 100.00 + 250.50 + 49.50 =
**400.00**. The assignment id (`asg-247f745f83484fc3`), teaching revision
(`8735dd7b3648a7d8+a52a495bf104849f+map`), mapping (`Price → Gross Amount`,
revision 2) and the `source-1` operation id are unchanged after the restart.
`source-1` was not re-executed (same operation id, `attempts=1`).

Artifact: `sum-price-for-the-integrated-quote-sheet-7ae420b6.docx`,
37 187 bytes, SHA-256 `9c44aeeb503d861180608dd26e393c9366715b86802a94ac167db98a4466d806`,
Normal style **Arial 11.0**; body starts `sum of Gross Amount: 400.00 USD` and
contains the correlated reply fact.

Effect count: **exactly one** controlled outbox line, operation
`7243572b-…`, subject `[Quote] Sum Price for the integrated quote sheet`,
teaching revision unchanged. No second send.

Evidence: `long-run-20261101/part1.json`, `state-waiting.json`,
`state-after-restart.json`, `state-completed.json`, `part2/active-*.docx|png`,
`timing.txt`, `first-conflict.*`, `missing-qualification.*`.

### Correction while waiting (same world)

A `task_scope=revised` document lesson (Calibri 14) was taught **while the run
was waiting**. The active run kept revision `8735…` and produced Arial 11. New
work at revised scope used revision `0ceff61904cb889b+map`, produced
**Calibri 14** and `2225.75 USD` (1250.50 + 900.00 + 75.25), SHA-256
`f875e98b65b27cee63edd174f69968b7c064aaa138ac282184e676985496acb6`.
Run `d74e637f-86c8-4643-91f3-c469e52ff33e`, assignment
`asg-888cbd5d67cf4560`.

## 3. Campaign A — complex teaching through the ordinary UI

Agent `d956a428-d7c1-4399-afa1-95eee5f920ce`; seven lessons were authored through
the canvas **Training** panel (`teach-*` inputs, Teach button) and the guided
employee dialog. No database seeding, DOM mutation or manifest injection was
used for teaching.

| Lesson | Context | Purpose |
|---|---|---|
| quote method (text) | global | sum the named business measure, cite source |
| document protocol | sales / licensed | Arial 11, Summary·Findings·Sources, Item/Value |
| expedited exception | sales / licensed / expedited | Arial 10, Summary·Sources — more specific |
| email protocol | sales / licensed | greeting, signature, `[Quote]` prefix |
| expired instruction | sales / licensed | Courier New 13, effective 2019–2020 |
| conflicting instruction | sales / licensed | Times New Roman 12 (same specificity) |
| grants format | grants / authorized | Georgia 13 — wrong context |

### Refusals and correction

- **Conflicting teaching** (equal specificity) refused the start:
  `Teaching cannot govern this assignment until the missing context is confirmed. (font_name: "Arial" vs "Times New Roman"; font_size: 11 vs 12)`.
  The conflicting point was then deleted through the visible
  `teaching-point-delete` button (native confirm accepted), not through an API
  shortcut.
- **Missing qualification** refused the start; the same form with
  `qualification=licensed` started the run.
- **Unfamiliar mapping** surfaced the real mapping card; `Gross Amount` was
  chosen in the UI and written into the snapshot (`+map`).
- **Wrong-context exclusion**: the journal still holds the grants lesson, but
  the sales assignment's effective lessons are only the document (`49caa9ad…`)
  and email (`3da8215c…`) points; the expired and grants points are absent.
- **Ordered policy with exception**: an `expedited` run used revision
  `5bb5ae1fa2056534+map` and produced **Arial 10** (the more specific lesson)
  with the same `506.00` total, SHA-256
  `97b8cdfa85043b4f85c5b60dedd27ca10ff86dd8f0a0df2d6afe8fa884a6ff74`.
  Run `51baf7c2-ea5f-4eef-85b0-9cb1da26e80d`.

### Completed work

Active run `bb3d4339-d263-4e5c-830d-5f9a5f9eb681`, assignment
`asg-093a9c2e68764474`: `source-1` applied `506.00` (120.25 + 330.75 + 55.00),
durable wait, real backend restart, correlated answer, completed with
revision `9780f6026a41e803+a5a0483fc5ee4030+map` and **Arial 11**, 37 196 bytes,
SHA-256 `2afda9a3bf48720fccdaf621b9ca382dbefd03cac6009acae51b80bd59c699d1`;
one controlled outbox line (`d099ddf4-…`).

Correction while waiting: the Calibri 14 lesson was taught before the answer was
delivered; the active run kept Arial 11. New revised work used revision
`94bf025c6c5dfd2e+map`, produced **Calibri 14** and `676.50 USD`
(240.50 + 315.25 + 120.75), SHA-256
`1c6e8b05ad8eeca130422114ea176b61b32a404f7ae17a4a14c9cd46ade42a8e`
(run `4bbc6800-ad2d-4f2e-87e9-e694bc40293a`).

### Cancellation sibling

An abandoned mapping run from a failed harness attempt
(`73ac5c86-16c2-4e39-ad57-eca361c2f369`) was cancelled (`status=cancelled`).
A late correlated reply then returned **404**:
`No open gap carries this correlation id. The response was not used to resume work.`
Outbox remained at 1 line.

### Clarification boundary

A chat request naming the sales quote protocol at standard scope but omitting
qualification returned a typed pending clarification:
`Before I can apply the taught method, I need to confirm: qualification (one of: licensed); task_scope (one of: revised, expedited).`
No value was invented; the answer `licensed` was recorded as
`authority=user_confirmation`. The assignment form separately supplied the
remaining scope and executed against the unfamiliar sheet. Evidence:
`complex_teaching_20261101/part2/clarification*.json`.

## 4. Sibling recovery controls (separate run identities)

`assignment_recovery_ui.cjs` on the current candidate: **5/5 checks passed**.

1. wait → real backend restart → browser resume; one completion.
2. changed source revision refuses stale mapping work; completed/mapped work
   preserved.
3. ambiguous mapping identity is refused (409) until the sheet/version is named.
4. cancellation persists across reload and refuses a late response.
5. **duplicate concurrent resume dispatches once**: `calcSteps=1`,
   `calcResults=1`, `afterEffects=0`.

Uncertain external effect (controlled adapter, real executor):
`test_provider_accepted_then_worker_lost_is_reconciled_not_resent` and the
post-effect timeout/runtime-error controls pass. Provider accepted → worker
lost records `status=uncertain`, `needs_reconciliation=true`, **one** outbox
line; `reconcile_step(... "applied")` then `execute` leaves the outbox at
**one** line (no automatic resend). Evidence: `/tmp/uncertain2.log` (3 passed)
and the test bodies in `backend/tests/test_assignment_executor.py`.

## 5. Tests run once on the integrated source

| Suite | Result |
|---|---|
| Fleet / revocation / no-progress / both workflow suites / training / calibration / world fixture | **48 passed** |
| `tests/test_assignment_executor.py` | **50 passed** |
| Uncertain-effect controls | **3 passed** |
| Browser recovery | **5/5 checks** |

Logs: `/tmp/runtime-batch-final.log`, `/tmp/executor-final.log`,
`assignment-recovery-browser-20261101/browser-recovery.json`.

## 6. Claim-count proposal (no denominator change)

This bundle supplies independent evidence for the six submitted runtime claims:

| Claim | Control supplied here |
|---|---|
| ORCH-08 | whole-graph depth/cycle/scope, descendant push over limit refused without mutation |
| TEAM-01 | exactly-one accountable delegation contract |
| ASK-03 | revocation fail-closed, re-entry at 20, second regression resets, unreadable store refuses |
| GOAL-04 | real loop stops before the third equivalent call; critique read back from a scratch LanceDB |
| WF-05 | real persisted `ExecutionStateManager`: deny → pause → approve → once → new engine adds 0 |
| GOV-04 | start/guidance/approval/evidence/completion/promotion; repeated start reuses; no evidence no promotion |

The practical gates (Campaign A, Campaign C, recovery controls) support the
existing durable-work boundaries (GOAL-05, WF-03, CORE-04, INST-05) but this
bundle does **not** count them as new claim IDs. I am not claiming 111/123 from
this bundle alone: the 123-claim denominator is unchanged, partial
implementations are not counted, and Agent 2's breadth claims remain a separate
submission. Reserve claims named in the task table: TEAM-05, MEM-07, GOAL-02.

## 7. Limitations stated plainly

- **Taught rounding is not exposed in the teaching UI.** The canvas panel has no
  rounding field; `MethodSpec.rounding` applies only in chat/`conversation_learning`,
  and `calculation_expression` (whose formula language supports `ROUND`) is
  authorable only through the API/raw format JSON, not the panel. Campaign A
  therefore verifies deterministic calculation (sum) and exact independent
  arithmetic, not a UI-taught rounding rule.
- **Exception scopes over-ask in chat clarification.** A general request that
  matches an exception lesson is asked for the exception's `task_scope` too,
  because `resolve_teaching_contract` unions every relevant lesson's missing
  context keys. The ask is typed and refuses to guess, but it is broader than a
  human would be.
- **LanceDB path**: this build resolves memory to
  `backend/data/atom_memory/default_shared` even with `LANCEDB_URI` /
  `ATOM_LANCEDB_URI` set. SQLite users, teaching journal, assignment state and
  artifacts are world-scoped; memory isolation is **not** claimed. The
  GOAL-04 scratch-store control uses its own LanceDB directory.
- `goal_runs.steps_executed` is not authoritative; the assignment step receipts
  are.
- The serving checkout is dirty by one harness file; it is not called clean.
- Effects are controlled transport only. No live Microsoft read and no real
  Outlook send were performed; the accepted qualifications for those remain at
  their previous scope.

## 8. Superseded / failed attempts

- Campaign C first attempts failed on frontend build/login and teaching-panel
  flakiness before any durable wait; the attempt that reached the wait at
  15:37:56Z is the one preserved. `part2.json` was not produced because the
  script's follow-on revised run could not find an un-uploaded CSV; the active
  run's completion is recorded independently in `state-completed.json`, the
  downloaded DOCX and the outbox. The failed follow-on is preserved, not hidden.
- Campaign A part 2 hit the same missing-revised-source problem after completing
  the active run; the active completion evidence is preserved and the
  revised/expedited runs were completed by
  `scripts/acceptance/revised_scope_run.py`. The orphan waiting run was
  cancelled as a sibling control.
- Earlier accepted tags `local-core-2026-10-30-final` → `da9cc8b12` and
  `conversation-learning-2026-10-30` → `d2b297deb` are untouched.
