# Focused independent review — connected assignment delta

Reviewed frozen candidate: `40b3367d9` on `whole-app/successor-f5f`.
Preserved start boundary: `44b62a6bb`.
Preserved correction pass: `322981bcc`.
Preserved executor freeze: `efc4bc9d5`.

Review scope: `backend/api/assignment_routes.py`,
`core/assignment_planner.py`, `core/assignment_resources.py`,
`core/assignment_executor.py`, `core/assignment_controlled_transport.py`,
the guided/explicit browser evidence, and the connected acceptance evidence.

No live provider was contacted. No source, credential or deployment change was
made.

## Material findings reproduced

### 1. Short source-version prefixes were accepted

`resolve_assignment_source` accepted `actual_version.startswith(expected)`.
A one-character prefix could satisfy the active-version check, weakening
source-version identity.

Repair: require exact active version equality. Discovery and read bindings
already carry the full content hash.

Control: `test_short_version_prefix_cannot_satisfy_active_version` — a
one-character prefix is refused with `stale_source_version`.

### 2. Supervisor-assigned work rechecked the assignee, not the requester

The route resolves source access with the authenticated requester. A
supervisor can assign the work to another employee, so the executor’s
`employee_id` is the assignee. `_recheck_binding` loaded that assignee and
compared it to the binding’s `access_scope.user_id` (the requester), which
would fail every supervisor-assigned connected read.

Repair: recheck the binding’s authenticated requester (`access_scope.user_id`)
and verify that reader remains active and inside the assignment
workspace/tenant. The task still records the assignee as the employee.

Control: `test_supervisor_assignment_rechecks_requester_source_grant` — a
supervisor starts a connected assignment for `member-1`; the source step
applies under `lead-1`’s active grant and the assignment completes.

### 3. A sum over zero eligible rows could report “applied” with no result

The aggregate adapter accepted an empty filtered set as `complete`; the
artifact then had no calculation fact. A no-eligible-rows sum is not a
certified result.

Repair: `dataset.aggregate` now raises a durable `records` clarification when
a `sum` selects zero rows. A `count` of zero remains a valid result.

Control: `test_sum_over_zero_eligible_rows_is_a_clarification`.

### 4. `action.registry` did not enforce the accepted action class

The concrete action’s effect was checked, but a registered read action could
run with no accepted `retrieve` scope because the adapter’s generic
`required_actions` list was empty.

Repair: after resolving the concrete action, a read-only action requires
accepted `retrieve`; a mutating/external action requires accepted `outbound`.
The existing effect-mismatch and approval checks remain.

Controls: `test_action_registry_read_requires_accepted_retrieval` (rejected
under `calculate`-only, accepted under `retrieve`) plus the existing
write-declared-retrieval rejection.

### 5. Multi-result and multi-source artifact evidence was under-checked

Artifact validation checked only the first row set and accepted any one
calculation fact. A multi-currency or multi-source artifact could omit a
required result or an entire source’s evidence.

Repair:

- required calculation/aggregate facts must all appear in the saved artifact;
- optional external evidence remains optional;
- multi-source artifacts must contain at least one actual value from every
  source row set;
- the artifact composer now includes every source row set, not only the first.

Controls: `test_artifact_with_missing_required_result_is_rejected`,
`test_bounded_taught_method_job_with_wait_and_draft` (two sources, both
represented), plus the existing connected sum/count acceptance.

## No material finding in

- Approval payload binding and changed-payload invalidation: existing controls
  still pass.
- Uncertain external-effect reconciliation: existing controls still pass.
- Formula sidecar/`__sheet_row` preservation: real Parquet controls pass.
- Full-frame aggregation: `dataset.aggregate` filters the complete
  materialized frame, not a display page; the connected acceptance verifies
  rows 2/3/4 and the total.
- Public path/output authority: public proposals still cannot supply a path or
  choose an output location.

## Verification after repairs

- Focused backend suite: **134 passed**.
- Connected scratch acceptance: **passed** (`85.00`, `3`, reopened).
- Bounded taught-method job: **passed** (taught expression, two sources,
  external correction `1.2`, document + formatted draft, restart).
- Guided browser and explicit browser evidence from `40b3367d9` remain valid
  for their separate claims.

## Remaining open checks

- Live OneDrive guided start against the previously ingested workbook:
  blocked because `MICROSOFT_CLIENT_ID` and `MICROSOFT_CLIENT_SECRET` are not
  present in this runtime. No replacement catalog row or grant was seeded.
- Live changed-source refresh: blocked on the same configuration plus the
  disposable-source authorization. The prepared protocol and probe workbook
  remain unchanged.
- Arbitrary/compound taught methods and multi-source calculations remain
  bounded: unsupported or ambiguous methods clarify; only the demonstrated
  sum/count and one taught scalar method are claimed.
- Production send remains controlled-only.
