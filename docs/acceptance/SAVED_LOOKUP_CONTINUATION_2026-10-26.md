# Saved-lookup continuation — 2026-10-26

**Scope:** repair the planner-enabled saved-lookup continuation on the frozen
spreadsheet candidate (`e14d3efdd`), preserving the original failure. This is
a repair branch, not a deployment.

## Preserved failure

`planner_failure_preserved/` under the trained-eval evidence directory holds:

- `atom_run2_verbose_confirmation.db` — pending task stored; verbose
  confirmation follow-ups left the task `pending` and never dispatched a read.
- `atom_run6_no_followup.db` — planner-enabled broad review stored the pending
  task and reported that no search ran.
- `metadata_dump.json` — session/message metadata for the affected sessions.

## Harness correction (2026-10-26)

The first evaluation harness did not match the release configuration: it set
`CHAT_FINALIZATION_M1=0`, `CHAT_FINALIZATION_M2=0`,
`ATOM_TASK_LIFECYCLE_ENABLED=0`, and `ATOM_DISABLE_TOOL_PLANNER=1`. The
observed `outcome=null` therefore did not establish a settlement defect. It
also sent a verbose "confirmation" that the production classifier correctly
rejects because it carries substantial new instructions.

The corrected control uses:

- `CHAT_FINALIZATION_M1=1`
- `CHAT_FINALIZATION_M2=1`
- `ATOM_TASK_LIFECYCLE_ENABLED=1`
- `ATOM_DISABLE_TOOL_PLANNER` unset
- exactly `go ahead`, in the same session, agent, and authenticated workspace.

The effective settings are captured in the evidence before the request. No
success override or forced `outcome="completed"` is applied.

## Trace

1. **Lookup proposed.** The first planner-enabled review returns "the lookup
   hasn't run; it is saved" and stores `_pending_file_task` on the session
   (`status=pending`, `attempts=0`).
2. **Confirmation accepted.** On the next turn, exactly `go ahead` matches the
   existing confirmation contract. The task gains `attempts=1` and
   `confirmed_mention`, and its stored original ask is preserved.
3. **First missing transition.** The resume lane restored `_gate_msg` to the
   original review, but `_research_turn`, `_required_research_sources`, and
   the replan obligation were still computed from the bare approval. The
   planner boundary therefore saw `research=False` and never dispatched a
   read.
4. **Fix — judge the resumed turn as the original ask.** `_research_turn` is
   true for a resumed turn, and required-source selection, replan subject /
   field extraction, and the obligation text all use the restored
   `_gate_msg`. A resumed file ask admits its named file as a required
   `datasets` / `documents` source even when no taught lesson names it.
5. **Continuity.** `request_extends_objective` treats a bare approval as
   confirmation, not a new objective. `merge_pending_task` keeps the original
   ask for a still-pending task and does not replace a terminal task with the
   bare approval; the attempt is counted and `confirmed_mention` refreshed.
6. **Verified receipt.** The replan executes the dataset read and produces a
   `file_scoped_read` receipt (`verified=true`, `addresses_requested=true`,
   file name and content hash). That receipt is bound to the pending task
   (`retrieved` → `delivered`) and to the persisted result, including the
   current execution id.
7. **Machine settlement.** The existing criteria verifier resolves
   `source_scoped_retrieval` from the verified receipt. `build_task_outcome`
   now writes that verdict into `objective_met` / `criterion_results` instead
   of leaving them empty. The finalizer carries the execution row's
   `task_outcome` into the envelope and maps only an explicit verdict:
   `true → completed`, `false → failed`, unknown/absent → `null`. A failed
   execution is never rounded to completed.

## Corrected control result

One-order release-config control
(`release_control_20261026/evidence.json`):

- pending task found: **true**
- `go ahead` accepted: **true**
- original request restored: **true**
- planner not disabled: **true**
- finalization M1/M2 on: **true**
- task lifecycle on: **true**
- read dispatched: **true**
- receipt verified / file + hash: **true**
- pending task delivered: **true**
- response cites workbook: **true**
- response `outcome`: **`completed`**
- execution `task_outcome.objective_met`: **true**
- `success_kinds`: `task_success=true`, `tool_success=true`,
  `delivery_success=true`, basis `criteria_met`
- assistant metadata outcome matches response: **true**
- fresh history persisted: **true**

The response is a genuine settlement of the verified read, not a success
override: `objective_met` comes from the existing `criteria_verdict` and the
envelope maps that explicit verdict.

## Combined evaluation (planner enabled, no supplied rows)

Evidence: `combined_eval_repair_20261026/evidence.json` (scratch world). The
run taught the policy, reviewed O-1001, reviewed O-1010 before correction,
taught the O-1010 credit-hold correction, reviewed O-1010 before restart,
performed a real app restart, and reviewed O-1010 again. No Order rows were
supplied in any prompt.

- **Teaching:** O-1001 → **Process**, citing `Orders` row 2 and the values.
- **Correction, pre-restart:** O-1010 → **Escalate**, citing **M. Chen** and
  **2026-10-25** (credit hold).
- **Correction, post-restart:** O-1010 → **Escalate**, citing **M. Chen** and
  **2026-10-25**; the lesson log and retrieval still contain the correction.
- **Settlement:** every reviewed turn returned `outcome=completed`; the
  execution `task_outcome.objective_met` is `true`; assistant metadata and
  fresh history agree in every case.
- **Zero unauthorized actions:** canvas audit unchanged (`create`,
  `agent_attached`, `data_loaded`), `task_operation_records=0`, `tasks=0`, no
  outbound/send/edit/approve operation, workbook SHA-256 unchanged.

The first combined run exposed a real product failure behind the corrected
configuration: file-scoped turns skipped **all** memory/lesson assembly when
the read succeeded. The correction was stored and retrievable, but never
entered the prompt, so O-1010 was processed after restart. The repair adds a
lessons-only assembly path for file-scoped turns, retrieves lessons for the
pending task's original ask (not the bare `go ahead`), and states explicitly
that training lessons are policy, not a file-value substitute. The failing
pre-fix evidence is preserved as
`combined_eval_repair_20261026/evidence_before_lesson_fix.json`.

**Disclosed baseline limitation:** with no supplied rows, the pre-correction
O-1010 read returned Status and Unit Price but not the Currency field, so the
model escalated on the base policy's “uncertain currency” rule rather than
recommending Process. This is the known file-read projection limitation (the
read does not return the full row contract); it is not a correction failure.
The correction itself is applied and persists across restart.

## Tests

Focused suite (`test_memory_context_assembler.py`,
`test_l2_guard_order.py`, `test_pending_file_task_resume.py`,
`test_cross_source_followup_routing.py`, `test_dataset_aggregation.py`,
`test_finalization_m1.py`, `test_finalization_m2.py`,
`test_outcome_resolution.py`, `test_fallback_honesty.py`,
`test_objective_evidence_flow.py`, `test_search_outcome_contracts.py`,
`test_acceptance_harness_integrity.py`):

- Repair branch: **519 passed, 23 failed, 2 xfailed**.
- Frozen baseline: **507 passed, 23 failed, 2 xfailed**.
- The same 23 named failures exist on both sides (known refresh/cross-source
  and objective-evidence test gaps, plus one order-dependent shared-state
  failure that passes in isolation on both sides). No new failure was
  introduced.
- New tests cover bare-approval resume, `resume_operation`, terminal-task
  merge, the finalizer's explicit-verdict mapping (completed / failed /
  unknown / failed-execution precedence), and lessons-only assembly for
  file-scoped turns.

## Remaining gaps and limits

- The one-order controls and the combined teaching/correction/restart run are
  green on retrieval, settlement, correction, and zero unauthorized actions.
  A five-order / full-group review still reaches the product's fixed turn
  budget (`turn_budget_exceeded`); the captured
  `ATOM_CHAT_TURN_BUDGET_SECONDS=180` does not change the product's
  `budget=95.0s` deadline. A full group review is therefore still not
  demonstrated.
- The file-scoped read still returns a partial row projection (for O-1010,
  Status and Unit Price but not Currency), so the pre-correction baseline
  escalated on the base policy's uncertain-currency rule instead of
  recommending Process. The full row contract (currency, both approvals,
  manager exception, notes) is not yet demonstrated.
- The policy basis in the one-order response is explicitly a draft: the
  workbook was retrieved, but the policy document itself was not. Do not
  describe the prior behavioral result — policy-conditioned recommendations
  and the O-1010-specific correction on supplied rows — as autonomous workbook
  retrieval. It remains a separate, prompt-supplied-rows result.
- The spreadsheet role-clarification flow and the required-input filter
  limitation remain disclosed; filter-language expansion was not combined
  with role correction here.
- This repair branch is **not deployed**. The pilot remains the separate
  `c912375de` release; deployment is a separate boundary.
