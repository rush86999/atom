# Long-running assignments and complex teaching — coverage

Source: `fc46342ed77df624b8922a0fc4d834935fc4f481`
Tree: `38618c7bc806b741498eab539c14345bb1054efe`
Protocol campaign source: `5ce5f571539ce6444fba696644cf9ddc8924e85b`
Functional baseline: `fda4f2dc9376f20a6e10de6d7d1e55cf16eeffd4`
Local tag: `local-core-2026-10-30-final`

This document distinguishes the transition types that were previously blurred
together. A database-session reload is **not** an application restart. A
mapping-wait recovery is **not** certification of every long-running state.

## 1. Transition classification and evidence

| Required transition | What was actually done | Source-bound evidence |
|---|---|---|
| Database-session reload | Close and reopen the SQLAlchemy session, read the same durable row | `mapping-browser-waiting-restart` result: `durable_unchanged`; `backend/tests/test_assignment_executor.py::test_crash_after_wake_before_advance_recovers` |
| Actual backend process restart | Stop the isolated uvicorn process, start a new process against the same SQLite/LanceDB/office root, authenticate normally | Final composite restart: old PID `34360` → new PID `35413`; `composite-protocol-5ce5f57/restart.json`; `reopened-after-restart.png` |
| Browser close/reopen | Part 1 browser context closed before restart; part 2 used a new browser context and normal login | `part1.json`, `part2-attempt-preserved.log`, `reopened-after-restart.png` |
| Interrupted operation recovery | Recovery paths for a lost worker, running operation, wake-before-advance, and stranded uncertain operation | `test_assignment_executor.py::test_recovery_names_previous_worker_and_marks_uncertain`, `test_ordinary_resume_leaves_healthy_running_operation_intact`, `test_crash_after_wake_before_advance_recovers` |
| Delayed external-event handling | Source completed, durable `wait` step with correlation id, process stopped, restarted, then the correlated response delivered | `part1.json` (`source-1 applied`, `wait waiting`), `verify.json` (completed after restart) |
| Restart after retrieval | The source aggregate `400.00` was applied before the restart and remained | `part1.json`, `durable-state.json` |
| Restart after artifact creation | Completed artifact reopened and downloaded with the same SHA-256 | `active-reload-assignment-artifact.docx` = `323f3431...`; `verify.json` |
| Changed source version | Stale version is refused before read; current version is re-resolved on every read | `test_assignment_routes.py` stale-source controls; `test_assignment_resource_boundary.py` |
| Revoked access | Connected-source grant is re-checked on every read; cached rows are not access | `test_assignment_routes.py::test_supervisor_assignment_rechecks_requester_source_grant`; resource boundary tests |
| Changed attachment invalidating approval | Approval is bound to attachment bytes; changing the artifact invalidates the old request | `test_assignment_executor.py::test_changed_artifact_invalidates_approval`, `test_send_prepare_binds_attachment_bytes_not_just_ids` |
| Expired approval/qualification where supported | Teaching effective-period expiry is enforced; approval expiry is not a claimed feature | Composite expired Courier New lesson excluded; `test_assignment_routes.py` approval controls |
| Uncertain outbound effect | Provider-accepted then worker lost is reconciled, not resent | `test_provider_accepted_then_worker_lost_is_reconciled_not_resent`; historical live-send evidence |
| Duplicate/out-of-order response | Exact correlation is required; a duplicate confirmed reply is idempotent; conflicting reply is refused | `test_external_reply_matches_exact_correlation_once`, `test_mapping_gap_authority_controls_and_idempotent_replay` |
| Response after cancellation | Cancellation prevents the unstarted effect; approval after cancellation is refused | `test_cancellation_prevents_unstarted_effect`, `test_approval_after_cancellation_is_refused`, `test_cancelled_assignment_cannot_be_approved` |
| Cross-workspace teaching/evidence | Workspace scope is checked on source, mapping correction and assignment routes | `test_wrong_workspace_mapping_correction_is_refused`, `test_real_catalog_resource_from_another_workspace_is_refused` |

### Important classification correction

The prior `mapping-browser-waiting-restart` evidence did stop and restart a
real backend process. It is valid for mapping-wait recovery, but it did not
cover: browser close/reopen, a completed source read before restart, a
correlated response delivered after restart, active-task teaching revision
retention, or the exact approval payload after restart. Those are covered by
the new composite run, not inferred from the older mapping evidence.

## 2. Complex teaching policy

The composite taught one coherent policy through the normal Training panel:

| Policy element | Teaching | Result |
|---|---|---|
| General method | “Use the selected authorized sheet, sum the named business measure, cite the source sheet and row count, ask for missing facts.” | Used in the active and revised runs |
| Contextual exception | `task_scope=expedited`: compact Summary/Sources, Arial 10 | Excluded from the standard run; available for expedited work |
| Required qualification | `qualification=licensed` | A start without qualification returned `teaching_context_unresolved`; a licensed start proceeded |
| Effective period | `2026-01-01` … `2027-12-31` | Applied; the expired `2019-01-01` … `2020-01-01` Courier New lesson was excluded |
| Output formatting | Arial 11, headings Summary/Findings/Sources, table columns Item/Value | Inspected in the DOCX Normal style and text |
| Communication protocol | Email greeting “Dear colleague,”, signature “Sales team”, subject prefix `[Quote]` | Present in the approved payload and the controlled outbox bytes; no live send |
| Intentionally conflicting instruction | Arial 11 vs Times New Roman 12, same context/specificity | Start refused with `font_name` and `font_size` conflicts; the conflicting lesson was removed through the UI |
| Similarity vs applicability | The resolver used declared context/conditions, not text similarity | Missing qualification and expired lessons were not silently applied |

The conflict error shown in the browser named the keys and values, e.g.
`font_name: "Arial" vs "Times New Roman"`. It did not choose by recency.

## 3. Active-task teaching revision behavior

The chosen behavior is **retain the accepted snapshot until an explicit
reassessment**. It is exposed in the assignment detail:

> Teaching is snapshotted at start. Later teaching changes apply to new work;
> this assignment keeps its accepted revision until an explicit reassessment.

Evidence:

- Final active run `62588f60-7ee8-4454-8ba3-e98d769d516b` kept teaching
  revision `93e2706cbf20587b+e938ac4c979b4c10+map` after a new Calibri 14
  lesson was taught while it was waiting.
- The active artifact remained Arial 11 and SHA-256
  `323f34314ff3bc00fba4bf60882bd1571bfe052d44dd4b0ab82d2d80421b4101`.
- New work `b65a6d94-77ce-4784-a87f-c2ce7b8f0982` used the new revision
  `922186d7c93cd416+map` and produced Calibri 14, result `2225.75`, SHA-256
  `6670ca2446c9304cf974a6352eb95f5fa80b74cb8f1f0c4b39f66a43e3b4906a`.

No old calculation was silently mixed with new policy, and the unrelated
active work was not invalidated.

## 4. Composite browser journey

The harness is:
`scripts/acceptance/composite_long_running_part1.py`,
`scripts/acceptance/composite_long_running_part2.py`,
`scripts/acceptance/composite_long_running_verify.py`.

Final campaign evidence:
`docs/acceptance/evidence/durable_assignment_20261030/composite-protocol-5ce5f57/`.
The earlier `composite-final-0efe3a9fb/` and `composite-long-running-0efe3a9fb/`
directories are preserved as prior attempts and are not the final campaign.

Browser actions (not API setup) established the agent, the teaching policy,
the conflict and correction, the data upload, the assignment start, the
mapping confirmation, the correlated response and the approval. The API was
used only to read durable state for assertions.

Sequence:

1. Guided agent creation through Agents.
2. Teaching through the Training panel: method, document format, expedited
   exception, email protocol, expired instruction, conflicting instruction.
3. Data upload through Data.
4. First start with the conflicting teaching: refused.
5. Conflicting teaching deleted through the Training panel.
6. Start without qualification: refused with `missing qualification`.
7. Licensed start: created.
8. Mapping `Price → Gross Amount` confirmed through the UI.
9. Durable wait reached; source result `400.00` applied.
10. Browser closed; backend PID `34360` stopped; new PID `35413` started on the
    same data root; browser reopened and normal login.
11. Waiting state, objective, source evidence and teaching revision verified.
12. New Calibri 14 lesson taught; active revision unchanged.
13. Correlated response delivered; artifact rendered; exact approval payload
    shown; the final run wrote one controlled outbox line whose subject starts
    `[Quote]` and whose body starts `Dear colleague,` and ends `Sales team`.
14. Page reloaded; status, history, mapping and artifact hash agreed.
15. New revised-scope assignment on a differently shaped source
    (`clean_quote.csv`) used the new teaching revision and produced Calibri 14.

Artifacts:

- `active-assignment-artifact.docx` and
  `active-reload-assignment-artifact.docx` are byte-identical
  (`323f3431...`).
- `revised-assignment-artifact.docx` is `6670ca24...`.
- `controlled-outbox.jsonl` has exactly one line for the final run; the
  verifier asserts one operation and rejects a duplicate. The email protocol
  bytes are present in that line.
- `wait-negative-control.json` records the contradictory
  `Currency unstated...` reply against a `currency` wait whose source already
  exposes `Currency`: the assignment stayed `waiting`, the response was
  retained as `source_already_provides_fact`, and no artifact was created.

## 5. Wait-value repair — e27ec63a to fc46342

The earlier wait repair treated a column header as an established fact. That
blocked legitimate blank-cell recovery and misclassified an agreeing reply as
a conflict. The corrected resolver reads the bound records' actual values:

| Source values | Reply | Result |
|---|---|---|
| `Currency` column, all blank | `USD` | `missing`; authorized resolution accepted; assignment completed |
| `Currency=USD` on all rows | `USD` | `established`; exact match → `source_fact_confirmed`; assignment completed |
| `Currency=USD` on all rows | `Not USD; use EUR` / `USDX` | `established`; exact comparison refuses agreement; durable conflict |
| `Currency=120` | `20` | `established`; numeric canonical comparison refuses agreement |
| accepted row 2 USD; frame also row 3 EUR | `EUR` | only accepted row 2 inspected; EUR is not evidence |
| column present, file unreadable | `USD` | `unavailable`, not `missing`; stays waiting |
| truncated coverage | `USD` | `incomplete`, not `missing`; stays waiting |
| `Currency=USD` on all rows | `Currency unstated...` | `established`; durable `source_fact_conflict`; assignment stayed waiting; no artifact |
| `Currency=USD` and blank rows | `USD` | `mixed`; durable `source_fact_mixed`; record-specific blank subjects remain unresolved |

### 5.1 One evidence contract for every representation — fc46342

The verifier found two alternate paths that still bypassed the repaired
contract: inline `result.rows` returned before coverage/population checks, and
aggregate subtotal keys could establish an unrelated measure. `fc46342`
validates coverage and accepted population before selecting a representation:

| Evidence shape | Required validation | Failure status |
|---|---|---|
| Inline rows | Receipt not truncated; exact accepted `__sheet_row` identities; fact field present in every row | `incomplete` (absent field is not a blank cell) |
| Parquet | Accepted identities complete and equal to `selected_count`; read filtered to those identities; never scan the whole frame without identities | `incomplete` / `unavailable` |
| Aggregate | Explicit `measure`; explicit `group_by`/`grouping_dimension` equal to the requested fact | `unavailable` (subtotal key cannot establish an unrelated measure) |

The applied result now persists `group_by` alongside `measure`, `values` and
`subtotals`, so the aggregate binding survives the receipt boundary. The
verifier's reproductions now return:

- inline receipt with `truncated=true` → `incomplete`;
- inline receipt accepting rows 2 and 3 but supplying only row 2 →
  `incomplete`;
- `subtotals={"USD": ...}` requested as `Price` → `unavailable`.

The blank-currency assignment survived a real backend restart with the same
artifact SHA-256 `b18c4874c644aff5c0a9cb65951b6d075c0df2f83a442ea8317a15d81a2b679f`
and exactly one applied wait operation. The agreeing twin completed with
`source_fact_confirmed`. Those UI twins and the contradictory negative control
were generated against `e27ec63` and are preserved byte-for-byte in the new
evidence directory; the resolver-only change is covered by the unit-level
twins and the branch matrix on `fc46342`.

Evidence: `wait-value-fc46342/` (preserved `wait-value-e27ec63/` artifacts are
recorded in `wait-value-fc46342/preserved-from.json`).

## 6. Failure and timing twins

The current source was tested with:

- `backend/tests/test_assignment_routes.py`
- `backend/tests/test_assignment_executor.py`
- `backend/tests/test_assignment_send_policy.py`
- `backend/tests/test_assignment_resource_boundary.py`
- `backend/tests/test_accepted_assignment_gate.py`
- `backend/tests/test_deterministic_assignment_plan.py`
- `backend/tests/test_assignment_launcher_guard.py`

Result: **126 passed** (`wait-value-fc46342/backend-targeted-tests.log`).
The executor file alone is **35 passed**; the branch matrix and the public-route
incomplete-inline negative each pass separately.

Teaching regressions:

- `test_artifact_renderers_teaching.py`
- `test_artifact_teaching_context.py`
- `test_chat_teaching.py`
- `test_teaching_point_editing.py`
- `test_workbook_read_artifact.py`

Result: **137 passed** (`wait-value-fc46342/teaching-targeted-tests.log`).

`test_teach_thread_reply.py` still has four failures in this environment; the
same four fail identically on the clean `e27ec63` artifact. They are a
pre-existing Outlook patch-boundary issue, unrelated to wait-fact resolution,
and are recorded in
`wait-value-fc46342/teaching-thread-reply-preexisting.log`.

Frontend AssignmentPanel/TrainingPanel/AgentCard: **31 passed**
(`wait-value-fc46342/frontend-targeted-tests.log`).

Frontend surfaces:

- `AssignmentPanel.test.tsx`
- `TrainingPanel.test.tsx`
- `AgentCard.test.tsx`

Result: **31 passed** (`frontend-targeted-tests.log`).

These tests cover the twins listed in section 1. The composite run adds the
real process restart, browser close/reopen, delayed external event, active
teaching revision, and exact post-restart artifact/approval evidence.

## 6. Unsupported boundaries

- Approval expiry is not a claimed product feature; teaching effective-period
  expiry is.
- Multi-worker campaigns are not claimed; one worker per assignment is the
  verified topology.
- Unrestricted autonomous browsing and non-Microsoft connectors are not
  claimed.
- Arbitrary Excel compatibility, arbitrary schema understanding, embedded
  image/chart interpretation and every future canvas component are not
  claimed.
- The controlled outbox is not a production sender. The separately qualified
  real-provider send remains the only real send; recipient delivery is not
  independently confirmed.
