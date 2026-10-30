# Core completion backlog — 2026-10-30

Durable reference: `PRODUCT_GOAL_LEDGER_2026-10-29.md`.
Successor: `242c9a01f` (tag `assignment-successor-2026-10-30-242c9a01f`).
Prior frozen product `a96484324` and rollback `901e5d773` are unchanged.

Classification: **E** engineering proceeds now; **V** isolated verification
proceeds now; **X** external qualification/authorization; **D** explicitly
deferred scope decision.

| # | Goal | Remaining gap | Entry point / consumers | Smallest change | Discriminating test | Class |
|---|---|---|---|---|---|---|
| 1 | Domain-independent work | Two domains were already demonstrated; no new platform assumption found | `assignment_planner.py`, `assignment_executor.py`, `table_selection.py`, `dataset_aggregation.py`, `review_result.py` | None beyond current tests | `test_core_domain_independence.py`, `test_three_domain_confirmation.py`; 578-suite | V |
| 2 | Teaching context/method/protocol | No single current journey proved teach → correction → wrong context → restart | `student_learning_service.py`, `artifact_teaching.py`, renderers | Test the existing journal + applicability path; no new store | `test_teach_correct_different_task_and_restart_journey` | E/V (done) |
| 3 | Unfamiliar sheets/mapping | No architecture change; existing campaign remains valid | `artifact_teaching.py`, `assignment_executor.py`, `assignment_routes.py`, `AssignmentPanel.tsx` | None | B/C/correction/waiting-restart browser flows rerun on successor | V (done) |
| 4 | Connected ingestion/retrieval | Declared Microsoft scope already has revoked/stale/wrong-workspace/coverage controls | `assignment_resources.py`, `sheet_dataset_service.py`, OAuth resolver | None; keep Zoho optional | `test_assignment_resource_boundary.py` controls | V |
| 5 | Large workbooks/formulas | No representative 24-sheet current test; cross-sheet formula text not pinned | `sheet_dataset_service.py`, formula sidecar, `dataset_aggregation.py` | Test-only; publish supported subset | 24-sheet materialization + cross-sheet formula tests | E/V (done) |
| 6 | Excel-like canvas | Supported table adapter already covers filter/edit/recalc/reload/export | capability adapter, office routes | None | `test_canvas_capability_service.py`; XLSX readback | V |
| 7 | Grounded selection/calculation/assessment | Contracts already separated; full-frame and gap controls exist | `table_selection.py`, `dataset_aggregation.py`, `review_result.py` | None | `test_deterministic_aggregate_lane.py`, `test_dataset_aggregation.py` | V |
| 8 | Email/DOCX/PPTX | Draft/format/reopen works; image/chart interpretation excluded | `office_service.py`, email/canvas services, renderers | None; declare rubric and limits | renderer tests + saved-artifact checks | V |
| 9 | User-created canvases | No current test with two differently shaped canvases using the same operations | capability manifests/adapter registry | Test-only; keep table-adapter limit explicit | `test_two_different_user_canvases_share_supported_operations` | E/V (done) |
| 10 | Long-running assignments | Artifact-restart no-duplicate not pinned in one test | GoalRun, task lifecycle, executor checkpoints | Test-only | `test_restart_after_artifact_creation_does_not_recreate_work`; existing wait/crash tests | E/V (done) |
| 11 | Approval/eventual sending | Attachment bytes were bound only by id; no hash check | planner, executor, `EmailCanvasService`, `email_attachment_store` | Add sha256 to staged records, carry hash map in payload, re-hash before transport | attachment-hash tests + planner/executor tests | E (done); real send X |
| 12 | Usability/security/operations | Pre-backup check alone raced live writers; source writer still active | `deploy_release.sh`, `check_freshness.py` | Quiescence check + post-backup and pre-activation rechecks | 22 kit controls incl. stale post-backup/pre-activation | E (done); cutover X |

## Completed in this successor

- Exact attachment-byte approval binding and pre-transport re-hash.
- 24-sheet workbook acceptance, cross-sheet formula text, leading-zero ids and
  blanks.
- Teaching correction/restart journey with wrong-context exclusion.
- Two canvas shapes sharing the same supported operations.
- Artifact-restart no-duplicate work.
- Source-quiescence gate and three freshness checkpoints.
- Current mapping browser flows and 578 affected regressions.

## Remaining boundaries

**External authorization (X)**
- Owner supplies `config/pilot_password`.
- Owner creates `config/APPROVED` with the exact successor identity.
- Owner authorizes stopping the live source writer (pid `19046`) or an
  equivalent quiescence window; refresh first if the source advanced.
- Owner separately authorizes one real-provider send with exact account,
  recipient, payload, attachment hash, permission and reconciliation window.

**Explicitly deferred scope (D)**
- Arbitrary Excel formula compatibility beyond the published subset.
- Embedded image/chart interpretation.
- Arbitrary schema understanding.
- Every future canvas component beyond the table adapter.
- Connectors outside the declared Microsoft scope.
- Multi-worker campaigns and autonomous third-party research.

No original requirement is silently deferred. The deferred items above are
outside the declared supported envelope and remain visibly unclaimed.
