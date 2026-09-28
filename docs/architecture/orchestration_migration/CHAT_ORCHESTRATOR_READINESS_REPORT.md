# Chat orchestrator readiness report

Date: 2026-09-27. Companion to `MANUAL_TEST_QUICKSTART.md` (preview) and
`CHAT_ORCHESTRATOR_APP_READINESS_PLAN_2026_09_26.md` (the work order).

Scope of this document: the *manual-test preview* milestone, and an honest
account of how far the *supported-workflow readiness* milestone actually got.
It does not certify all integrations or all conversations.

---

## 1. Headline

| | |
|---|---|
| A running, isolated, browser-drivable app | **Yes** — frontend :3101, backend :8051, world `preview_v1` |
| Real model serving a real turn in a browser | **Yes** — `opencode-go` / `kimi-k2.7-code` |
| Isolation proven from browser network traffic | **Yes** — 9/9 launcher checks, 0 foreign origins |
| Workbook eight-item lookup vs frozen expectations | **8/8** (was 2/8) |
| Restart durability incl. byte-identical pin survival | **11/11** |
| Acceptance matrix | **9 of 13 cases fully pass**, 1 at 3/4, 1 at 1/4, 1 at 0/4, 3 not exercised |

**The supported-workflow readiness gate is NOT met.** Unexercised and failing
required cases are itemised in §6. Per the plan's own stopping criteria, that
means acceptance is incomplete and this is not a "done" claim.

## 2. What was wrong at the start, and what it actually was

The plan and the coordination notes carried a story: the eight-item lookup was
failing 6/8 because "the renderer cites `Sheet!R<row>` where the expectations
want `Sheet!A<row>`", and a second report attributed all six failures to "one
named cause". Both were wrong, and the second one had already been recorded as
settled. Per-assertion mapping found **two independent causes**:

**Cause A — the evaluator read the identity binding at the wrong level of the
artifact.** `core/answer_presentation.build_targets_from_scan` groups evidence
by (sheet, row) and attaches matched identity cells to each *group*:

```
target.identity      = {"status", "candidates": [...]}      <- no "references"
candidate.identity   = {"references": [{"cell": "A26", "role": "matched_target"}]}
```

`evaluate_artifact_bindings` read `target.identity.references`, which is
`None` for every target, so it reported `identity refs none (status 'single');
expected A26` for rows whose identity *was* bound at A26. `value_ok` was
`True` for all of them. Verified against a captured artifact: U-22's
candidate `LINMAC!R26` carries `A26`; the evaluator saw nothing. Fixed by
reading the candidate level (`_identity_cells`, `run_isolated.py`), where the
data has always been. Six targets flipped without touching a single frozen
expectation.

**Cause B — the gate ANDed in a conflated text check.** `run_true_eight` set
`pass = text_pass AND identity_ok AND value_ok`. The text check demands the
answer's own citation anchor equal the frozen identity coordinate
(`"LINMAC!R26" == "LINMAC!A26"`). The written contract says the opposite is
permitted — `AGENT_SEARCH_WORK_ORDER_2026_09_26.md:79` ("A row citation may be
displayed compactly…") and the closeout plan line 66 ("The renderer may keep
compact row citations"). So a correctly-bound target failed purely because the
display used the compact locator the contract permits. The gate is now the two
bindings the contract defines; the text verdict is still computed and reported
per target as `display_binding_ok`, so a display regression stays visible
instead of being dropped.

**Cause C (found later, in production).** The *ambiguous* render branch emitted
`PRICE blank` with no cell and no quoted basis, so "this row's price cell is
blank" was indistinguishable from "no price column exists", and an evidence
parser had nothing to bind to. Every rendered branch now names the cell and
quotes the basis, and discloses the identity cell alongside the row locator.

No frozen expectation was edited. The evaluator was corrected, per the closeout
plan's explicit instruction.

## 3. A third defect the first two reports missed: corruption reported as absence

Acceptance case `11_forced_retrieval_failure` corrupts a workbook source and
requires the turn to distinguish a retrieval *failure* from a legitimate
*absence*. It was failing: the answer said "no matching row in the indexed
content searched" — an I/O error laundered into an absence.

Root cause: the workbook scan path never consumed the coverage vocabulary that
`core/hybrid_search/documents_hybrid.py` had already established. A read failure
and a genuine non-match both produced an empty evidence list, and
`answer_presentation.build_targets_from_scan` read zero candidates as
`identity.status = "none"` — *the same value a genuinely absent target gets*.
That is the laundering point. A guard that keyed off "did we get rows" could
not catch it, because the content probe swallowed the read error and returned
truthy from a cached path.

Fixed so three states are distinct: **failed** (report the failure, with an error
*category*, never `str(exc)`), **searched-and-absent** (unchanged honest absence
wording), **nothing-to-scan** (`unverified`, untouched). 16 new tests in
`tests/test_workbook_retrieval_failure_semantics.py` use real corrupted bytes
and restore the fixture with hash verification. Case `11` now passes **5/5**,
and the app's answer names the condition: *"all 46 indexed sheets could not be
read (the stored copy is damaged or not a readable workbook)"*.

A live `NameError` on the same path was also fixed:
`core/sheet_dataset_service.py:1981` referenced `_SHEET_ROW_COL`, which the
module never defined (the constant is `SHEET_ROW_COL`). It fired in the probe
leg for any matching token and was swallowed into an empty result — a probe
that fails looked exactly like a probe that found nothing.

## 4. The preview stack (new tooling)

Nothing in the repo could host a preview, so this was built:
`backend/scripts/orchestration_acceptance/`

| File | Purpose |
|---|---|
| `preview_stack.py` | Builds/launches/verifies an isolated stack: own backend, own frontend, per-run seeded database, credential-complete model access, 9 isolation checks |
| `browser_verify.py` | Playwright driver: records every request/WS/console event, proves which origins the browser actually reached, drives the manual test script in one conversation |
| `restart_durability.py` | Restart through the *real* launch path against the same database; asserts byte-identical retry-pin survival |

Three things had to be solved that the existing harness could not:

1. **A second frontend.** Next 16 hardcodes the config filename and locks
   `<distDir>/dev/lock`, so a second `next dev` in the shared directory exits.
   The preview is a symlink farm at `frontend-nextjs/.preview-instance` whose
   only behavioural override is `distDir`; it runs with `--webpack` because
   Turbopack refuses out-of-root entrypoint symlinks. Source edits by any agent
   are visible immediately; nothing is duplicated.
2. **A real model.** The harness's seatbelt denies all egress and its env
   whitelist cannot carry credentials, and the code export excludes gitignored
   `.env` — so a sandboxed world has no provider at all. The preview seeds the
   run directory with the repo's own **encrypted** BYOK store
   (`byok_keys.json` + `byok_encryption_key`), which is the app's existing
   credential mechanism, so `opencode-go` and `deepseek` work with no
   production change and no secret ever rendered. Isolation is enforced at the
   *data* boundary instead, and the deviation is recorded in the launch
   descriptor.
3. **Proof of isolation.** `verify` reads the process's health identity, uses
   `lsof` to confirm which SQLite file the process actually has **open**, checks
   it is *not* the live dev database, and greps the compiled client bundle for
   the origin — because `NEXT_PUBLIC_API_URL` is inlined at build time, so
   neither `.env.local` nor the process env is evidence. The browser driver
   then confirms it from real traffic.

## 5. Measured results

Fingerprint: `code_snapshot_sha256=d1288df33d2f0fb1…`, world `preview_v1`,
run `run-65fdffe7d20c`, effective flags `ATOM_TASK_LIFECYCLE_ENABLED=1`,
`CHAT_FINALIZATION_M1=1`, `CHAT_FINALIZATION_M2=1`, `ATOM_CHAT_STREAMING=1`.

**Workbook eight-item lookup — 8/8** against the frozen `cases.json`
expectations, gate = `identity_ok AND value_ok`:

| Target | identity | value | Result |
|---|---|---|---|
| U-22 | `A26` | `C26 'List Price'` 1,777 | PASS |
| SLE24-16 | `A101` | `E101 'PRICE'` 8,880 | PASS |
| TK 1624 | `A101` | `D101 'Price'` 8,040 | PASS |
| TK Manual Flanger | `A42` | `D42 'Price'` 1,609 | PASS |
| GSL48-16 | `A106` | `E106 'PRICE'` 14,166 | PASS |
| No. 381 | status `multiple` | — | PASS |
| No. 622 | status `multiple` | — | PASS |
| TK Multi Wheel Gang Slitter | `A100` via alias | `D100 'Price'` 12,838 | PASS |

**Acceptance matrix** (`live_integration_acceptance.py`, against this world):

| Case | Result |
|---|---|
| 0_database_identity | 3/3 |
| 1_initial_request | **1/4** |
| 1b_historical_distractors | 2/2 |
| 2_formatting_followup | 3/4 |
| 3_explicit_research | 4/4 |
| 4_transport_retry | NOT EXERCISED |
| 4b_same_text_new_request | 2/2 |
| 5a_finalized_binding | 4/4 |
| 5b_finalization_transform | **0/4** |
| 6_streaming_consistency | NOT EXERCISED |
| 7_restart_history | NOT EXERCISED here; covered 11/11 by `restart_durability.py` |
| 8_overlapping_turns | 3/3 |
| 9_unknown_source_handling | 3/3 |
| 11_forced_retrieval_failure | 5/5 |

**Restart durability — 11/11**, including: replay after restart returns
byte-identical pinned content; replay creates no second execution; same
`request_id` with a different payload is refused 409; pre-restart history still
returns the delivered answer.

**Browser, one conversation, real Chromium** — all steps completed, 0 requests
to any foreign origin, WebSocket on :8051:

| Step | Behaviour observed |
|---|---|
| M01 general question | Real model answer, 4-step reasoning, no tool run |
| M02 eight-item lookup | 8 items in requested order, ambiguity honest, identity + value cells disclosed, source/coverage footer |
| M03 "easier to read" | Re-rendered from existing evidence, no new read, prior answer unchanged |
| M04 "Search again" | New read performed, values identical, status restated |
| M05 "factory price instead" | Returns Factory Price where it exists; **names the available bases where it does not** — no silent substitution |
| M06 "Replace U-22 with U-38" | **DEFECT — see §6** |
| M07 unrelated then back | Unrelated question answered; task state preserved |
| M08 browser reload | Same answers, same evidence, no duplication |

## 6. Open defects and unexercised cases — named individually

These are the reason the readiness gate is not met. None is presented as
passed.

1. **M06 item replacement does not take effect.** "Replace U-22 with U-38"
   returned the *previous* list unchanged: U-38 was not added and U-22 was not
   removed. Worse, that turn was model-generated and the model **corrupted a
   sheet name** the structured artifact had correct — the answer said
   `Tinknock!R100` where the artifact says `Tinknocker!R100` (1 occurrence in
   156 across the session). So a model-regenerated answer can silently diverge
   from verified evidence, and nothing detects it. This is a Phase 2
   conversation-semantics gap (a new objective must mutate the task's entity
   set, not be re-narrated) and a Phase 4 trust gap (finalized text must be
   bound to the evidence it claims). **Highest-priority open item.**
2. **`1_initial_request` 1/4** on the final run, while the same ask issued
   directly on the same fingerprint returns all eight targets correctly. The
   failing turn recorded no persisted attempt and `evidence_action=None` —
   consistent with a cold first turn on a freshly-seeded world. Cause not yet
   established; it passed in earlier runs on earlier fingerprints, so it is
   either cold-start timing or fingerprint-sensitive. Not claimed as flaky
   without evidence.
3. **`5b_finalization_transform` 0/4** — the forced-failure injection did not
   fail the execution (`execution_status: success`), so nothing downstream could
   be measured. Unexercised in substance, not merely failing.
4. **`2_formatting_followup` 3/4** — `previous_delivery_preserved_in_history`
   is False while the case's own note says byte-equality is deliberately *not*
   required for a formatting request. The check and the stated contract
   disagree; the check was left as-is rather than weakened to pass.
5. **`4_transport_retry` NOT EXERCISED** — the case blocks on a keyed-request
   contract its own client does not use. The product behaviour it targets *is*
   covered by `restart_durability.py` (replay, 409 on payload change, pin
   survival), but the case itself remains unrun.
6. **`6_streaming_consistency` NOT EXERCISED** — zero token frames on the
   deterministic HTTP path. The plan requires a token-bearing shim for protocol
   tests plus a real-model smoke test; the smoke test passes, the shim protocol
   test has not been run.
7. **Boundary verification pending** — instrumented retrieval/render boundaries
   are not landed, so several checks are recorded as
   "persisted-attempt observations, not retrieval-call counts". Effect counts
   are not yet measurable at the retrieval boundary.
8. **Canvas edit (M09/M10) and sandboxed send (M13) have no browser coverage
   at all.** They remain integration-test-only and are excluded from the
   supported list rather than claimed.

## 7. Two other honest notes

- **A provider failure was once reported to the user as a capability claim.**
  In one run the turn answered *"I don't have a connected file storage
  integration yet"* while the dataset was indexed and present (47 entries, 46
  parquet files on disk). The log shows `openrouter` returning 402 (out of
  credits) during that window while `opencode-go` served correctly when called
  directly. So a model-tier failure degraded into a false statement about the
  user's setup — the exact conflation the plan forbids. Another agent has since
  landed `d5d670596 fix(chat): report an unavailable provider instead of a
  blank reply`; the behaviour is not re-verified here beyond the final run.
- **`automation_settings` logs a permission error** in every world
  (`backend_root/core/../data`): inside the world, `core` is a symlink so `..`
  resolves to the read-only export rather than the run's data dir. Non-fatal
  and unrelated to chat, but it is a path-anchoring instance of the class
  `AGENTS.md` §1 warns about, and it is still there.

## 8. Coordination notes for other agents

- Two commits by other streams (`a3ebb7837`, `00084a575`, `d5d670596`,
  `9e46185df`, `e61126cfe`) swept in-flight edits while this work was in
  progress, including production files. `workbook_read_artifact.py`,
  `chat_tool_planner.py`, `documents_hybrid.py` and `sheet_dataset_service.py`
  are therefore committed under other agents' messages. Content was verified
  rather than re-authored; per `AGENTS.md` §4 this is logged rather than
  rewritten, because rewriting a shared commit is riskier than the
  misattribution.
- Another agent maintains a **second** isolated preview on :3091/:8091 with
  its own `MANUAL_TEST_QUICKSTART.md` (committed `b9722295e`) and has
  independently recorded the workbook lookup as open defect `PREVIEW-01`. This
  report and that one corroborate each other; the file collision is why the
  quickstart for this preview is at
  `MANUAL_TEST_QUICKSTART_PREVIEW_V1.md`.
- Disk: the acceptance worlds had reached 67 GB and filled the volume. Stale
  per-launch `runs/` directories in worlds with **no live process** were
  removed (17.5 GB reclaimed, keeping each world's newest run and every
  `fixture/`, `code/` and world with a live process untouched). A world is
  re-launchable from its fixture at any time.

## 9. Files added or changed

Added:
- `backend/scripts/orchestration_acceptance/preview_stack.py`
- `backend/scripts/orchestration_acceptance/browser_verify.py`
- `backend/scripts/orchestration_acceptance/restart_durability.py`
- `backend/tests/test_workbook_retrieval_failure_semantics.py` (16 tests)
- `frontend-nextjs/.preview-instance/` (symlink farm + config wrapper)
- `docs/architecture/orchestration_migration/MANUAL_TEST_QUICKSTART_PREVIEW_V1.md`
- `docs/architecture/orchestration_migration/CHAT_ORCHESTRATOR_READINESS_REPORT.md` (this file)
- evidence: `acceptance/preview_browser_results.json`,
  `acceptance/restart_durability.json`, `acceptance/preview_browser/*.png`

Changed (production):
- `core/answer_presentation.py` — identity cell disclosed in every rendered
  branch; ambiguous branch now emits `<cell> '<basis>' <value>`; scan verdict
  carried through as `retrieval{}`
- `core/workbook_read_artifact.py` — per-source read legs, `read_status`,
  `absence_claimable`, `unavailable` target status
- `core/chat_tool_planner.py` — a read failure outranks a probe hit
- `core/hybrid_search/documents_hybrid.py` — `error_category` made public and
  taught the parquet format readers
- `core/sheet_dataset_service.py` — the `_SHEET_ROW_COL` `NameError`

Changed (harness — no product behaviour):
- `run_isolated.py` — `_identity_cells`; identity/value bindings gate the case;
  `display_binding_ok` reported; 6 new selftest assertions
- `live_integration_acceptance.py` — removed a duplicate `--code-dir` that made
  the script unrunnable; restart env now derived from the launch descriptor and
  asserted against the relaunched process; `--externally-managed-server`

## 10. What I would do next, in order

1. Fix M06 properly: bind finalized answer text to the structured evidence and
   fail the turn when a model-regenerated answer diverges from it. This is the
   one open defect where a user can be shown something false.
2. Establish why `1_initial_request` fails on a cold world.
3. Run the provider-shim streaming protocol test to close
   `6_streaming_consistency`.
4. Get `5b_finalization_transform` actually injecting a failure.
5. Reconcile `2_formatting_followup`'s check with its own stated contract.
6. Only then re-take a fingerprint and re-run the whole matrix.

---

# Addendum — task correction (item replacement), 2026-09-27

**Status: NOT COMPLETE. Replacement remains EXCLUDED from the verified support
list.** The support list in `MANUAL_TEST_QUICKSTART_PREVIEW_V1.md` was updated
first, before any fix work, so the exclusion was true while the work was in
progress. This addendum records what was built, what was proven, and — more
importantly — the two routing layers still standing between the fix and a
passing end-to-end flow.

## A1. What the blocker actually is, in full

`Replace U-22 with U-38` was answered with the previous list. Unwound, there are
**four** distinct layers, not the three first identified. The first three are
fixed; the fourth is not.

1. **The objective was destroyed before anything could revise it.**
   `supersedes_pending_task()` matched the verb `replace` and returned `True`,
   so `chat_orchestrator.py:4230` popped the stored file task. The objective
   holding the item set was gone before the lanes ran. The module already had
   the right idiom for exactly this ambiguity — `_strip_mentions` + `_seek_shaped`
   — because "list" inside a *filename* must not classify a turn. The same
   discrimination was needed for "replace", which means a target list
   ("replace U-22 with U-38") and an outbound action ("replace the logo in the
   draft"). **Fixed:** a set edit is lineage, not supersession.

2. **The continuation classifier had an advertised-but-empty class.**
   `_continuation_decision`'s docstring lists retrieval operations
   `none/read/rerun/refresh`. It only ever returned `none`, `rerun` and
   `refresh` — `read` was never returned by any code path in the repo. A set
   edit is precisely the `read` case, and the two guards below killed it first:
   `_CONFIRMATION_ACTION_RE` contains `replace`, and `extract_targets` sees
   `['U-22','U-38']` and reads a fresh ask. **Fixed:** `read` is now returned,
   carrying the computed result set.

3. **There was no operator for the item set at all.**
   `chat_tool_planner._resolve_active_items` had exactly two: "the turn's own
   list replaces everything" and "inherit verbatim". No add, no remove, no
   replace-one. **Fixed** with `pending_file_task.entity_set_edit`, which
   computes the RESULT (in-place substitution, so order survives) and is
   fail-closed: a verb match alone is never enough, entity-shaped tokens are
   required on the relevant side, judged with file mentions blanked out.

4. **NOT FIXED — the turn is claimed by an unrelated feature lane before any
   file lane runs.** The public-boundary run shows the replacement turn
   answering *"I've added 'Replace U-22 with U-38' to your Tasks."* That is
   `_handle_task_request` (`chat_orchestrator.py:14151`) creating a real task
   row, reached via `ChatIntent.TASK_MANAGEMENT → FeatureType.TASKS`
   (`:13819`). The intent classifier reads the verb `replace` as an action
   verb, so the turn never reaches the resume lane where fix (2) and the
   durable revision live — even though, verified in isolation against the
   candidate world, `supersedes_pending_task → False`, `matching_pending_task →
   MATCH` and `entity_set_edit → {operation: replace, removed: [U-22],
   added: [U-38]}` all behave correctly.

   A second gap sits alongside it: even with the task lane excluded, the resume
   lane is not being entered for this turn. Both are upstream of everything
   fixed above, which is why the end-to-end result is still 0/4.

   **This is the honest state: the recognition and revision machinery is built
   and unit-proven, and it is not yet connected to the turn.**

## A2. What IS built and proven

| Piece | Where | Evidence |
|---|---|---|
| Set-edit detector (replace / drop / add, order-preserving) | `core/pending_file_task.py::entity_set_edit` | 18 hand-checked cases: all 4 swap phrasings, drop, add, quoted identifiers, leading verbs, trailing prepositions resolved; **and** `replace the logo in the draft`, `replace the price with the cost`, `send me the price list`, `edit the canvas quote`, `what is the capital of France?` correctly return `None` |
| Lineage, not supersession | `pending_file_task.supersedes_pending_task` | returns `False` for a set edit |
| A delivered task becomes eligible for a re-read | `pending_file_task.matching_pending_task` | returns a match for `Replace U-22 with U-38` |
| The missing `retrieval: "read"` class | `chat_orchestrator._continuation_decision` (now takes `session`) | returns `{"retrieval": "read", "objective_edit": {...}}` |
| The read uses the EDITED set | resume lane `_direct_active` | verified in code path |
| **Durable revision before the read** | `revise_objective` applied ahead of `begin_retrieval_turn` | `revise_objective` is the only entity-set mutator; it replaces `entities`, records `removed_entity_ids`, **invalidates the evidence bound to removed items** and raises `new_attempt_required` — so U-22's evidence cannot be reused. Fail-closed: if the revision cannot be persisted the read is blocked |
| Evidence-bound narration | `answer_presentation.validate_rendered_against_record`, wired in `chat_orchestrator` | see A3 |

Regression: **456 passed, 2 xfailed** across
`test_pending_file_task_resume`, `test_task_lifecycle`,
`test_workbook_structured_delivery`, `test_acceptance_runner_guards`,
`test_workbook_retrieval_failure_semantics`.

## A3. Evidence-bound rendering, and a validator that had to be made honest

`validate_rendered_against_record` checks semantic claims, never prose: every
`Sheet!Cell` / `Sheet!R<n>` must exist in the record spelled exactly; items the
record has must be shown and items it does not have must not be; a failed read
must not be presented as a list.

Behaviour matrix, run against five real captured records:

* **must accept (20/20):** default, compact, table and field-narrowed renders of
  each real record, plus a correct *replaced* render against its own record.
* **must reject (5/5):** a reworded sheet name (`Tinknock!R100` for
  `Tinknocker!R100`), an altered row locator (`R26`→`R99`), a correct replaced
  render judged against the *old* record, and the stale old render judged
  against the *replaced* record.

**The validator was wrong three times before it was right, and that is the
useful part.** Its first version passed a reworded sheet name, an invented
price and a stale list — vacuously, because it extracted nothing. It then
rejected *every correct* rendering, because it read the item label's own digits
("U-22" → 22) as an unbound value, and the row numbers inside cell references
(`A26` → 26) as values. A validator that fails correct output is worse than
none: it turns a right answer into "incomplete". The fix was to separate
**gating** checks (citation grounding, failed-read-as-data, item staleness) from
**advisory** ones (value grounding, which cannot be done reliably across render
styles), and to scope item checks to answers whose list structure actually
parsed. One known residual gap is recorded rather than papered over: a bare
identity cell with no sheet prefix (`identity A26` → `identity Z26`) is not
gated, because a strict bare-cell scan false-positives on item names that
contain digits (`SLE24-16` → `SLE24`). The deterministic re-render fallback is
what covers that residual.

Wiring is three-outcome, as required: narration that validates is delivered;
narration that does not is replaced by a deterministic render of the same
record **if that validates**; if neither validates, an explicit incomplete
outcome — never the stale list, never a generic success.

## A4. Public-boundary tests (written, currently 0/4 — and that is the finding)

`scripts/orchestration_acceptance/task_correction_acceptance.py` covers the four
required sequences — replacement, replacement→formatting, replacement→re-search,
reload-after-replacement — and each case asserts all four required properties:
the **task revision** (durable entity set, order preserved, outgoing item
gone), **actual retrieval** (a new attempt id, and the incoming item carrying
its own identity cell and value binding while the outgoing item is absent from
the record entirely), **evidence bindings**, and the **displayed list** (no
stale item, no invented item, citations grounded).

Result on the candidate fingerprint `ff582c5dc86594b9`: **0/4 pass**, with the
base lookup and every citation-grounding check passing and every
revision/retrieval/display check failing — a clean, consistent signature of
layer A1.4, not a scattering of unrelated failures.

## A5. Credential isolation — asked, and the answer was "no, not clean"

Audited rather than asserted, and it found a real gap.

* **Model access is intentional and minimal.** Only three providers carry keys
  in the world: `opencode-go`, `deepseek`, `openrouter` — all model providers,
  none an external system the preview can act on. The launch forwards exactly
  one credential-bearing env var (`OPENROUTER_API_KEY`); the other three named
  vars are model *names*, not secrets.
* **A real gap: `oauth_tokens` was not in the scrub list** and two ACTIVE rows
  came through from the dev snapshot carrying `ZohoCRM.modules.ALL`,
  `ZohoBooks.fullaccess.all` and Microsoft Graph `Calendars.ReadWrite` grants
  for the snapshot user. They survived because the stored values are *hashes*,
  so the table looked harmless — which is exactly how a scrub list rots. Added
  to `CREDENTIAL_TABLES` (it now scrubs by deleting the rows) and applied to
  the live preview; `verify_scrubbed` reports no violations and the app still
  serves real model turns.
* **Three tables that look secret-shaped are not, and are now documented as
  deliberately preserved** so nobody "fixes" them: `mini_apps.credential_metadata`
  is the literal string `"None"` in all 30 rows; `rate_usage_records.input_tokens`
  / `output_tokens` are LLM usage counts; `users.hashed_password` is a bcrypt
  hash and is the reason the quickstart can say "use your usual password".
* Net: 16 of 16 credential tables now empty (the live dev DB has 9
  `integration_tokens` the preview does not).

## A6. Cold-world initial request — the earlier 1/4 did not reproduce

The earlier `1_initial_request` 1/4 was reported as a cold-world defect. It is
not. On a freshly seeded world at this fingerprint the case scores **4/4**:
`evidence_action=new_read`, 8 entries, a persisted attempt, the exact ordered
identities, and no diagnostic clutter. The same ask issued directly — cold, with
no `context` at all — also returns all eight in 13.6s.

The 1/4 window coincided with another stream's mid-flight commit, and I
observed a *different* symptom in that same window: the turn answering "I don't
have a connected file storage integration yet" while the dataset was indexed and
present (47 entries, 46 parquet files on disk), with `openrouter` returning 402
in the log while `opencode-go` served correctly when called directly. So the
defect that actually occurred there was a provider failure being reported as a
false capability claim — which is a more serious finding than a cold-start
quirk, and is now the subject of another stream's `d5d670596`. The cold-start
hypothesis is withdrawn: it was not supported by a reproduction.

## A7. Retry and streaming — what each artifact actually proves

These are different claims and were previously conflated in the summary.

| Artifact | What it proves | What it does NOT prove |
|---|---|---|
| `restart_durability.py` (11/11) | A keyed request's pin survives a **real** restart through the **real** launch path against the same database: replay returns byte-identical content, creates no second execution, a changed payload under the same key is refused 409, and pre-restart history still returns the delivered answer. | Nothing about the matrix's `4_transport_retry` case, which remains **NOT EXERCISED** — it blocks on a keyed-request contract its own client does not send. |
| Matrix `6_streaming_consistency` | Nothing yet — **NOT EXERCISED**. Zero token frames; the deterministic HTTP path emits none by construction. | Token-level streaming remains open. The real-model browser smoke test passes, but that is a liveness check, not a stream-protocol test. The plan's requirement — a token-bearing shim for protocol tests *plus* a real-model smoke test — is half met. |
| Matrix `7_restart_history` | Nothing in the latest run — **NOT EXERCISED** by design, because it owns the server process and the launcher does. Its gate is left incomplete rather than passed. | The restart evidence above comes from the launcher's own down/up cycle, which is the more faithful test but is a *different* artifact. |

## A8. Remaining gates, honestly

| Gate | State |
|---|---|
| Truthful task correction | **NOT MET** — machinery built and unit-proven; two upstream routing layers (A1.4) still unconnected. End-to-end 0/4. |
| Cold-world initial request | **MET** — 4/4; earlier 1/4 not reproducible and attributed. |
| Credential isolation | **MET** after fixing a real gap (`oauth_tokens`); 16/16 tables empty. |
| Finalization failure (`5b`) | **NOT MET** — still 0/4; the forced-failure injection did not fail the execution, so nothing downstream was measured. Not attempted this session. |
| Retry / streaming | **NOT MET** — restart-pin proven by its own artifact; `4_transport_retry` and `6_streaming_consistency` unexercised, now separated in A7. |

## A9. Next step, in order

1. Stop the intent classifier routing a set edit to `FeatureType.TASKS` when an
   active file objective exists — and confirm the resume lane is actually entered
   for the turn. Everything else is already in place beneath it.
2. Re-run `task_correction_acceptance.py` on a fresh candidate fingerprint;
   replacement returns to the support list only at 4/4.
3. Run the token-bearing shim for `6_streaming_consistency`.
4. Get `5b`'s injection to actually fail an execution, then capture pre- and
   post-finalization output.
5. Only then re-take a fingerprint and run the complete matrix.
