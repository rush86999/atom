# Agent 1 completion bundle — 2026-11-01

One source-bound bundle for the runtime batch, Campaign A (complex teaching),
Campaign C (restart/upgrade control), Campaign C2 (elapsed gate), the sibling
recovery controls and the cancellation repair. Hosted deployment, live sends
and broad model campaigns were not performed.

## 1. Identified product sources

| Item | Value |
|---|---|
| Campaign A / C1 / recovery product | backend tree `715969f01d23`, frontend tree `c921cb82e784` |
| Campaign A serving commits | `cf102eeac1ce-dirty.13b4ffec1724` |
| Campaign C serving commits | `2d01d31772da-dirty…` before the wait; `cf102eeac1ce-dirty…` on restart |
| Campaign C2 start | `d535aa7d36cf` (product `715969f01d23`) |
| **C2 closure (pinned)** | **`414d8add3`** / backend tree `715969f01d23`, worktree `/private/…/c2-pin` |
| **Cancellation repair** | **`f5d2e085a`** / backend tree `d37da0be5943` (frontend unchanged) |
| **Budget pause-credit repair** | **`bec60978b` + `019aa1eeb`** / backend tree `c2963fbcdc8e` |
| **Post-acceptance verified source** | **`f1ef414c3`** / backend tree `c2963fbcdc8e`, frontend `c921cb82e784` (63 focused tests) |
| Launcher memory-path fix | **`d8120737e`** (both `LANCEDB_URI` and `LANCEDB_URI_BASE` at the world root), frontend tree `756642ecb165` |
| Verified launcher/first-use successor | `d8120737e`; documentation HEAD `14b1928e2` |
| Accepted tag (immutable) | `accepted-local-2026-11-01-90pct` → commit `88bf413e8`; known budget defect linked to the repaired successor above |
| Product diff repair vs campaigns | cancellation files plus the budget-credit files (`assignment_executor.py`, `assignment_plan.py`, `test_assignment_executor.py`) |

The campaign sources and the repair source are deliberately distinct: the
repair landed after C2 reached its wait, and C2's wait/resume path does not
exercise cancellation, so C2 is pinned to its original source instead of being
re-run on the repair. Campaign A, C1 and the recovery controls ran on the
pre-repair product tree `715969f01d23`.

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

## 2b. Campaign C2 — the elapsed gate (fresh identity, historical source)

C2 is the separate run that carries the elapsed requirement; its clock was
never reset.

| Item | Value |
|---|---|
| World | `long_run_20261101_b`, backend 8085 / frontend 3145 |
| Run | `cac9cbd6-f72b-4fbb-b106-f0990fc5b191` |
| Assignment | `asg-bc8171a465894137` |
| Teaching revision | `851207ec455336d3+cabba8f03b6894fa+map` |
| Wait reached | `18:04:53Z` |
| Elapsed at closure | **7,239.8 s** (>= 7,200 s) |
| Historical source | `414d8add3112` / backend tree `715969f01d23`, clean pinned worktree `c2-pin` |
| Completed work | `source-1` applied **110.00** (15.10 + 20.20 + 30.30 + 44.40), operation `3e8eba43-…`, **attempts=1** before and after |
| Artifact | 37,211 bytes, SHA-256 `bce1a2ad9f74fc09c81896b282adf9a49a079a89c461d5d5a5bdaf6768fe6a94`, **Arial 11** |
| Effect | exactly **one** controlled outbox line, operation `2a593acd-…` |
| Approval | **explicit**: `send`, payload `ca0ab0a5…`, purpose “Send the prepared response” |

Restarts: pid 66715 → 68921 → 73022 (pinned) → 87659 (final), all against the
same SQLite stores. The run remained `waiting` through the first three; the
final restart sees `achieved` / `completed`, the same artifact hash and one
outbox line.

### Budget snapshots (historical pre-repair source)

| Stage | paused_seconds | waiting_since | active_wait |
|---|---|---|---|
| before response | 0.0 | `18:04:41Z` | null |
| after response | **7251.69** | null | null |
| after approval | 7251.69 | null | null |
| after resume | 7251.69 | null | null |
| after completion | 7251.69 | null | null |
| after duplicate response | 7251.69 | null | null |

The wait interval was credited **once**; approval, resume, duplicate response
and final restart did not add it again. Duplicate resume returned 200 /
`completed` twice with no extra effect; the duplicate correlated reply returned
404 `No open gap carries this correlation id…`.

**Scope separation:** this run proves elapsed waiting, restart/resume, preserved
completed work, exact artifact and one controlled effect on **its historical
source**. It is **not** verification of the repaired budget code; that is the 63
focused controls on `c2963fbcdc8e`.

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
- **Two different qualifications, kept separate:** deleting the conflicting
  lesson proves *recovery from conflicting teaching* (the start was refused and
  became possible after removal). It is **not** correction history. The
  correction evidence is the revised-teaching/snapshot check: while the active
  run waited, a `task_scope=revised` lesson was added; the active run kept its
  accepted revision and Arial 11, while a new revised run used the new revision
  and Calibri 14. The lesson revision also survives restart.
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

### Cancellation sibling — two distinct cases, stated precisely

1. **Real wait, exact correlation (the control that proves cancellation):**
   recovery run `afe9748b-b813-47f8-bc9a-3b8bb618874c` had an open wait for
   correlation `corr-cancel-…`. It was cancelled through the UI, the cancelled
   state survived a page reload, and a late response to that same correlation
   returned **200** with `assignment.status = cancelled` and **no steps**; the
   outbox stayed at **0** effects. The assignment exists as cancelled and the
   response did not resume it.
2. **Mapping-gap run, unrelated correlation (the 404 case):** abandoned run
   `73ac5c86-16c2-4e39-ad57-eca361c2f369` was waiting for a **mapping
   question** (`question_id 898060d7…`), never for the email correlation
   `campaign-a-missing-term-1`. Its assignment is `cancelled` with both steps
   cancelled and the cancellation in the decision log. The late response
   returned **404** `No open gap carries this correlation id…` because the
   correlation never belonged to that run. This proves the correlation check,
   **not** the cancellation path; the first case proves the cancellation path.

**Defect found here and repaired separately:** after the public API cancel of
the mapping-gap run, the assignment was cancelled and no effect occurred, but
`goal_runs.status`/`waiting_on` still read `waiting`/`human_input`; the
recovery run's late reply also matched its historical wait and produced a
`wake`. The focused repair (`f5d2e085a`, section 4b) projects the terminal state
immediately, clears the live wait, and refuses late replies before matching.
Pre-repair evidence is preserved in
`complex_teaching_20261101/part2/cancellation-proof.json`.

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

## 4b. Cancellation consistency repair (own source identity)

Source `f5d2e085a`, backend tree `d37da0be5943`, developed in an isolated
worktree. Full detail:
`cancellation_repair_20261101/README.md`.

- Root cause: both UI and API call `POST /api/assignments/{run_id}/cancel` →
  `AssignmentExecutor.cancel`, which mutated only the assignment/task ledger;
  `GoalRunService.transition` changed `status` but not `waiting_on`; and
  `record_external_response` matched a cancelled step's historical wait and
  woke it.
- Repair: terminal transitions clear the live `waiting_on`; `cancel` projects
  `cancelled` to the GoalRun and is idempotent; late replies for terminal work
  are refused **before** matching, logged as `external_response_refused`, and
  return **409**; the route/consumer checks see nothing to revive.
- Preserved: assignment step status/history, the step's historical `waiting`
  correlation, decision log, and the first cancellation evidence.
- Public-API controls: correlated-response wait and mapping wait; fresh-session
  read; late reply and gap resolve refused; repeated cancel harmless; resume
  and `find_active_task`/`list_runs(include_terminal=False)` see no active work;
  outbox empty.
- Results: **129 passed** across routes, executor, goal service/events/routes,
  watchdog sweep; the two new public-API cancellation tests pass.

## 4c. Budget pause-credit repair (own source identity)

Source `bec60978b` plus follow-up `019aa1eeb`, backend tree
`c2963fbcdc8e`; full detail `budget_repair_20261101/README.md`.

- Reproduced defect: a legacy budget with `paused_seconds=500` **and** the same
  interval in `waiting_since` was subtracted twice. 1500s of genuine active
  work against a 900s budget reported ~0s and was allowed. The legacy credit
  path also left the live wait in place on retry.
- Repair: clear the matching `active_wait`/`waiting_since` on every credit
  outcome; ignore a `waiting_since` already in the credit ledger; for a legacy
  paused ledger with no live active-wait identity, do not subtract the same
  interval again. A new wait always records `active_wait`, so it is still
  excluded. Genuine active-work exhaustion remains exhausted.
- Controls: legacy double-subtraction, legacy credit clearing, legacy retry,
  recorded credit with stale wait, concurrent external responses, restart while
  waiting. **140 focused tests pass** on `c2963fbcdc8e`.

This repair is recorded as a **post-acceptance correctness repair** in
`docs/acceptance/VERIFIER_ACCEPTANCE_2026-11-01.md`; the accepted tag
`accepted-local-2026-11-01-90pct` is preserved and the old baseline is not
described as unaffected.

C2 ran on `414d8add3` and does not load this repair; its budget snapshots are
historical execution, not a relabelled verification of the repaired code.

## 4d. Launcher memory-path correction and first-use focused smoke

Source `d8120737e`, backend tree `c2963fbcdc8e`, frontend tree
`756642ecb165`.

- Finding: the launcher exported `LANCEDB_URI` but workspace handlers read
  `LANCEDB_URI_BASE`, falling back to `./data/atom_memory` and anchoring to
  `backend/` — the repository-shared memory root. Both variables now point at
  `<world>/data/atom_memory`.
- Verified on a fresh world: `Connecting to LanceDB at
  <world>/data/atom_memory/default_shared`; **zero** repository-shared path
  occurrences. No shared memory was copied, deleted or migrated.
- Focused first-use smoke on current HEAD: assignments panel loads after login,
  Demo Assistant selectable, agents page reachable, no page errors. Evidence:
  `first_use_smoke_20261101/`.
- The full first-use journey was measured at `8b1abd7e6`
  (`docs/demo/FIRST_USE_TEST_2026-11-01.md`: sample job 232990.00, first
  Assignments visit). This focused check at `d8120737e` adds the world-owned
  memory path and first-visit panel load; the full install/sample job was not
  repeated after the memory fix.

**C2 harness version:** the accepted closure ran on corrected working-tree
content before it was committed. Executed SHA-256
`e89d2e8253fcfe6bc5e8167f30b2a57e4361318197e39f8506feea811f23b90b`,
committed as `6747c1957`; the checkout was **not** clean at execution. The
committed content matches the executed content
(`long-run-20261101_b/harness-version.json`).

## 5. Tests run once on the integrated source

| Suite | Source | Result |
|---|---|---|
| Fleet / revocation / no-progress / both workflow suites / training / calibration / world fixture | `715969f01d23` | **48 passed** |
| `tests/test_assignment_executor.py` | `715969f01d23` | **50 passed** |
| Uncertain-effect controls | `715969f01d23` | **3 passed** |
| Browser recovery | `715969f01d23` | **5/5 checks** |
| Cancellation routes/executor/goal suites | `d37da0be5943` | **129 passed** (includes the 50 executor controls) |
| Runtime claim batch re-run | `d37da0be5943` | **48 passed** |
| Uncertain-effect controls re-run | `d37da0be5943` | **3 passed** |
| Browser recovery (pre-repair path) | `715969f01d23` | **5/5 checks** |
| Browser recovery (integrated) | `c2963fbcdc8e` | **5/5 checks** |
| C2 elapsed closure (historical) | `715969f01d23` | completed, 7,239.8s, one effect |
| Cancellation + budget + goal suites | `c2963fbcdc8e` | **140 passed** |
| Verifier-focused subset (61 executor + 2 public-route cancellation) | `c2963fbcdc8e` | **63 passed** |
| Runtime claim batch (integrated) | `c2963fbcdc8e` | **48 passed** |

Evidence: `sibling_controls_20261101/`, `cancellation_repair_20261101/`,
`assignment-recovery-browser-20261101/browser-recovery.json`.

## 6. Claim-by-claim proposed count (denominator unchanged at 123)

The frozen inventory already contains **111 verified / 12 excluded** eligible
claims. The 12 claims that move the verifier's **accepted 99** baseline to 111
are these, exactly; no test-total substitution and no splitting:

### Agent 1 — six runtime claims (evidenced in this bundle)

| Claim | Proposed | Control |
|---|---|---|
| ORCH-08 | verified | whole-graph depth/cycle/scope; descendant push over limit refused without mutation; wide-shallow allowed |
| TEAM-01 | verified | exactly-one accountable delegation contract; zero/two/duplicate rejected |
| ASK-03 | verified | fail-closed revocation; 1/19 successes still blocked; clears at 20; second regression resets; unreadable store refuses |
| GOAL-04 | verified | real loop stops before the third equivalent call; critique read back from a scratch LanceDB |
| WF-05 | verified | real persisted `ExecutionStateManager`: deny → pause → approve → once → new engine adds 0 |
| GOV-04 | verified | start/guidance/approval/evidence/completion/promotion; repeated start reuses; no evidence no promotion |

### Agent 2 — six product claims (owned by Agent 2; not independently run here)

`CORE-06`, `ROUTE-06`, `ROUTE-03`, `GRAPH-05`, `INST-01`, `GOV-05` — each is
marked verified in the shared inventory with its own evidence; this bundle does
not re-run them.

### Arithmetic

`99 (accepted baseline) + 6 (Agent 1 runtime) + 6 (Agent 2 product) = 111/123`
(90.2%). The denominator is unchanged; no partial implementation is counted.

### The 12 excluded from the 123 (not counted, with reason)

| Claim | Status | Reason |
|---|---|---|
| ORCH-01 | unverified | plain-language workflow generation; no model-backed control in this candidate |
| ORCH-02 | unverified | open-ended TASK routing; no model-backed control |
| ORCH-07 | unverified | fleet-routing audit decision; no model-backed control |
| ORACLE-01 | partial | registry/postcondition verifiers incomplete |
| TEAM-05 | partial | nightly alignment automation path not exercised |
| MEM-07 | unverified | evolution harness disabled in this controlled world |
| MINI-03 | environment_limited | isolated mini-app runtime not available |
| MINI-04 | environment_limited | mini-app install/reopen not available |
| MINI-05 | architecture_only | microVM isolation is architectural, not exercised |
| INT-09 | blocked_external | 46+ live external accounts not authorized |
| ROUTE-07 | unverified | opencode-go custom rate limits not exercised |
| GOAL-02 | unverified | utility scoring is model-backed; no cloud key used |

Reserves remain `TEAM-05`, `MEM-07`, `GOAL-02`; they are **not** needed for the
proposal above and are not counted.

## 7. Limitations stated plainly

- **Taught rounding is not exposed in the teaching UI.** The canvas panel has no
  rounding field; `MethodSpec.rounding` applies only in chat/`conversation_learning`,
  and `calculation_expression` (whose formula language supports `ROUND`) is
  authorable only through the API/raw format JSON, not the panel. Campaign A
  therefore verifies deterministic calculation (sum) and exact independent
  arithmetic, not a UI-taught rounding rule. **Frozen-inventory check:** no
  counted claim promises taught rounding — the only "round" matches are
  round-trip claims (OIDC, workbook values, OAuth tokens, MCP schemas). No claim
  is being counted for it, so no claim is left uncounted; it is recorded as a
  product limitation, not a claimed capability.
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
- The campaign serving checkout carried one modified harness file (the launcher
  `ATOM_FRONTEND_DIR` override) at the time; it is committed in the bundle, and
  C2's pinned worktree is clean. No product file was uncommitted during a run.
- Effects are controlled transport only. No live Microsoft read and no real
  Outlook send were performed; the accepted qualifications for those remain at
  their previous scope.
- C2's closure is source-bound to `414d8add3`; the cancellation repair
  `f5d2e085a` and budget repair `019aa1eeb` are later product sources. C2 does
  not exercise cancellation or the repaired budget ledger; it is historical
  execution evidence, not verification of those repairs.
- **First-use focused smoke is recorded** on `d8120737e` (panel loads, Demo
  Assistant selectable, no page errors) together with the world-owned memory
  path. The full journey remains the measured `8b1abd7e6` run; the install and
  sample job were not repeated after the memory fix.
- The C2 closure harness was executed from a non-clean working tree; the exact
  executed content hash is recorded and matches its commit `6747c1957`.
- The accepted tag `accepted-local-2026-11-01-90pct` is preserved. The
  post-acceptance budget finding is appended to
  `docs/acceptance/VERIFIER_ACCEPTANCE_2026-11-01.md`; the old baseline is not
  described as unaffected.

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
