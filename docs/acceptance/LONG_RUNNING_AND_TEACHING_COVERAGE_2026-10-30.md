# Long-running assignments and complex teaching — coverage

Source: `0efe3a9fbdc19414b0615ae033a3823e02d04d75`
Tree: `f1ef5e1faed79cdf974fad0f68269c026510ade3`
Functional baseline: `fda4f2dc9376f20a6e10de6d7d1e55cf16eeffd4`
Local tag: `local-core-2026-10-30-final`

This document distinguishes the transition types that were previously blurred
together. A database-session reload is **not** an application restart. A
mapping-wait recovery is **not** certification of every long-running state.

## 1. Transition classification and evidence

| Required transition | What was actually done | Source-bound evidence |
|---|---|---|
| Database-session reload | Close and reopen the SQLAlchemy session, read the same durable row | `mapping-browser-waiting-restart` result: `durable_unchanged`; `backend/tests/test_assignment_executor.py::test_crash_after_wake_before_advance_recovers` |
| Actual backend process restart | Stop the isolated uvicorn process, start a new process against the same SQLite/LanceDB/office root, authenticate normally | Final composite restart: old PID `30124` → new PID `30602`; `composite-final-0efe3a9fb/restart.json`; `reopened-after-restart.png` |
| Browser close/reopen | Part 1 browser context closed before restart; part 2 used a new browser context and normal login | `part1.json`, `part2-attempt-preserved.log`, `reopened-after-restart.png` |
| Interrupted operation recovery | Recovery paths for a lost worker, running operation, wake-before-advance, and stranded uncertain operation | `test_assignment_executor.py::test_recovery_names_previous_worker_and_marks_uncertain`, `test_ordinary_resume_leaves_healthy_running_operation_intact`, `test_crash_after_wake_before_advance_recovers` |
| Delayed external-event handling | Source completed, durable `wait` step with correlation id, process stopped, restarted, then the correlated response delivered | `part1.json` (`source-1 applied`, `wait waiting`), `verify.json` (completed after restart) |
| Restart after retrieval | The source aggregate `400.00` was applied before the restart and remained | `part1.json`, `durable-state.json` |
| Restart after artifact creation | Completed artifact reopened and downloaded with the same SHA-256 | `active-reload-assignment-artifact.docx` = `f0d902dd...`; `verify.json` |
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
| Communication protocol | Email greeting “Dear colleague,”, signature “Sales team”, subject prefix `[Quote]` | Stored as the email output requirement; no live send |
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

- Final active run `860a8d81-f17b-4bb0-9e87-442d8abbbaa4` kept teaching
  revision `87d15fb70ae01762+bf5d58e747ff9cdf+map` after a new Calibri 14
  lesson was taught while it was waiting.
- The active artifact remained Arial 11 and SHA-256
  `f0d902ddac32f38f8dd6bb1516eb3fbdfc371699537b1d8af7c540a516ded428`.
- New work `c869aa2c-d562-4c3c-8d79-786ce5d88396` used the new revision
  `b9ea9fd7046d2776+map` and produced Calibri 14, result `2225.75`, SHA-256
  `fb87716c3d20299a0e035b7c22e3d8a38b42dee008c88bd5160ae33d2564c241`.

No old calculation was silently mixed with new policy, and the unrelated
active work was not invalidated.

## 4. Composite browser journey

The harness is:
`scripts/acceptance/composite_long_running_part1.py`,
`scripts/acceptance/composite_long_running_part2.py`,
`scripts/acceptance/composite_long_running_verify.py`.

Final campaign evidence:
`docs/acceptance/evidence/durable_assignment_20261030/composite-final-0efe3a9fb/`.
The earlier `composite-long-running-0efe3a9fb/` directory is preserved as a
prior cross-source attempt and is not the final campaign.

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
10. Browser closed; backend PID `30124` stopped; new PID `30602` started on the
    same data root; browser reopened and normal login.
11. Waiting state, objective, source evidence and teaching revision verified.
12. New Calibri 14 lesson taught; active revision unchanged.
13. Correlated response delivered; artifact rendered; exact approval payload
    shown; the final run wrote one controlled outbox line.
14. Page reloaded; status, history, mapping and artifact hash agreed.
15. New revised-scope assignment on a differently shaped source
    (`clean_quote.csv`) used the new teaching revision and produced Calibri 14.

Artifacts:

- `active-assignment-artifact.docx` and
  `active-reload-assignment-artifact.docx` are byte-identical
  (`f0d902dd...`).
- `revised-assignment-artifact.docx` is `fb87716c...`.
- `controlled-outbox-final.jsonl` has exactly one line for the final run;
  `outbox-analysis.json` records one final-run operation and zero duplicate
  operations. The older line in `controlled-outbox-all-runs.jsonl` belongs to
  the preserved prior attempt, not this run.

## 5. Failure and timing twins

The current source was tested with:

- `backend/tests/test_assignment_routes.py`
- `backend/tests/test_assignment_executor.py`
- `backend/tests/test_assignment_send_policy.py`
- `backend/tests/test_assignment_resource_boundary.py`

Result: **86 passed** (`backend-targeted-tests.log`).

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
