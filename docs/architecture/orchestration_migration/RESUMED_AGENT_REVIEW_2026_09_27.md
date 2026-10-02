# Resumed-agent review and directed next steps

Reviewed: 2026-09-27. This is a source/result review, not a new runtime acceptance run. Receiving agent owns execution; do not wait for nonexistent owners.

## 1. What is current

- HEAD inspected: `a8bc48dc1`, following `161c36358` (resume/report), `91f1652b7` (acceptance/preview), and `cb9bf4fcc` (presentation/failure/task revision).
- Current unstaged work at inspection: `backend/integrations/chat_orchestrator.py` and `acceptance/task_correction_results.json`. Preserve it; this review makes no production edits.
- Latest task-correction result inspected: generated `2026-09-27T09:03:13-0400`, candidate :8071, **0/4 cases passing**. No new acceptance was run by this reviewer.
- Acceptance worlds remain a real local directory, not a symlink. Portable destination is mounted. `df` reports about 21 GiB local free and 1.6 TiB external free. Historical “51 GB” is not a current measurement of reclaimable bytes.
- Relocation watcher was previously stopped. Do not re-arm the idle heuristic.

`RESUME_BRIEF_2026_09_27.md` is useful historical context but its “nothing committed” and active PID/fingerprint claims are not current facts: subsequent commits exist. `RESUME.md` describes a different preview stream. Reconcile their claims against the actual launch manifests instead of choosing whichever narrative seems newer. Do not combine results from different previews.

## 2. Review of the in-flight fix

The current orchestrator diff removes `_pfr_structured_for_turn` from the outer process method and adds `_turn_structured_record` in `_get_qwen_response`, populated beside prefetch, storage-read, and direct-read results. This is a sensible correction to a cross-method scope/freshness hazard. It is not yet evidence that replacement works.

The diff's comment attributes fallback-to-Tasks to a swallowed NameError. Confirm that chain with a captured exception/trace on the pre-fix candidate, rather than declaring it settled from inspection. The previous handoff attributed the same symptom to the intent classifier. These explanations may interact; neither should become another untested “one cause.”

Before promoting the patch:

1. Verify that `workbook_read` at each assignment is the actual structured-result schema expected by `validate_rendered_against_record` and `present_from_record`, not a different metadata object. Trace `_set_structured_result` and all readers.
2. Ensure every applicable path binds the current operation/attempt/revision, including failed reads and presentation-only reuse. “This turn's record” means explicitly selected evidence for this operation; legitimate formatting reuses prior evidence by identity rather than pretending to read again.
3. Add a regression proving the guard executes on each path, and that a stale previous record cannot validate a changed task.
4. Prevent a recognized file continuation from falling through to an unrelated mutating Tasks lane after an internal error. Return an honest incomplete result. Do not fix this by globally disabling task creation or adding replacement-specific keyword routing.
5. Test legitimate standalone task creation as a negative control so continuation handling does not break it.

## 3. Fix task correction before promoting a new preview

Trace the actual request through continuation resolution, task revision, read execution, result persistence, finalization and delivery. Record the first divergent boundary.

Expected sequence:

`resolve active task → validate requested set edit → persist revised entities/order → retrieve for revised objective → bind result to revision/attempt → render and finalize → persist new delivery`

Replacing U-22 with U-38 must remove the outgoing item from the current requested set while retaining immutable historical evidence. Preserve the remaining items' order. Do not claim the correction applied because the answer omitted every item or returned an error.

A replacement does **not** guarantee that the incoming item exists. Correct outcomes include bound evidence, honest ambiguity, absence within successful coverage, or failed retrieval. The selected fixture must establish which is expected. Do not require a price and identity cell for U-38 unless the independently inspected source actually contains them.

Run replacement → formatting → re-search → reload, verify durable state and the displayed set, and confirm no unrelated Tasks row or other mutation was created. Keep replacement excluded from the advertised preview until this passes.

## 4. Repair the evaluator's remaining false-positive/false-negative risks

The inspected JSON shows these specific issues:

- `replacement_performed_a_REAL_retrieval` reports only old/new attempt IDs. That measures identities, not actual invocation. Assert execution-bound scan/provider events and observed outcomes; retain the ID assertion separately.
- `replacement_evidence_action_is_a_read` passes on a reused record whose attempt ID is unchanged. Require that the outcome belongs to the current operation/execution before treating it as a new read.
- `items_not_stale` can pass when both text and record contain the same old list. Compare each independently against the expected revised task entities, not just against each other.
- “Outgoing item absent” passes for an empty parsed list. Pair it with exact nonempty expected-set/order checks; error replies cannot earn successful correction.
- The validator reports `U-22 shows 2` while evidence has 1777: investigate label/basis digits such as `List Price_2`. Parse typed claim spans; do not treat every numeral as a price. Keep wrong-price negative controls so relaxing this does not admit fabricated values.
- `history_has_no_duplicate_turns` uses `len(rows) == 2`. Define which messages the endpoint returns and which requests were issued. Verify unique request/execution/message identities and expected role counts; four rows might be two legitimate user/assistant pairs, not duplication.
- An absent incoming item must be graded on its independently labeled absence/coverage outcome, not fail merely because no value binding exists.

All required-case IDs remain independent of results. Capture exact execution-bound evidence; never restore recency fallback. Add negative controls for empty answers, stale text plus stale records, reused attempt stamps, incorrect value, and one overlapping turn reading its sibling's artifact.

## 5. Preview and verification sequence

1. Preserve the measured preview; create a separately fingerprinted candidate. Rebuild the immutable export after production changes. Restarting an old export does not test the working tree.
2. Run corrected task-correction acceptance and relevant neighbor tests. Identify code/evaluator/fixture/configuration failures separately.
3. Give the candidate a separate frontend farm and build directory. Do not collide on Next's distDir or edit a running preview's cache.
4. Browser-test real-model chat, eight-item lookup, replacement and its follow-ups, re-search, reload and retry. Verify actual HTTP/WS destinations and exact source/config/database identity.
5. Promote only the measured candidate; publish one current URL/support matrix. Streaming and action/recovery gates remain independently open until tested. Continue the existing C00–C26 plan rather than starting another plan.

## 6. Portable-drive move: separate maintenance operation

The user wants to save local space, but active-world relocation must not happen during candidate testing. Preserve both copies; no opportunistic world deletion. The old `/tmp/finish-aw-swap.sh` is unsuitable: incomplete writer detection, idle-based activation, limited verification, and no launch lock preventing a new writer during the swap.

### Prepare

Inventory current local and external worlds, real paths, sizes, symlinks, manifests, active servers/frontends/build jobs and run ownership. The external copy may contain stale/deleted worlds. Do not run a destructive mirror against the broader portable tree. Prefer a new versioned destination or an explicit reviewed reconciliation plan.

Verify the intended volume identity, filesystem, available space and stable mount path. Implement a launcher preflight that refuses a missing/wrong external volume or dangling root symlink; never silently recreate a local empty store.

### Establish an explicit maintenance window

Save current launch descriptors and stop only the identified acceptance/preview processes and their writers gracefully. Leave the user's :3000/:8001 stack alone unless evidence shows it uses this tree, in which case resolve that dependency explicitly. Fail closed if process/open-file inspection is unavailable. Block new acceptance launches during final sync and swap with a shared maintenance interlock; 90 seconds of quiet is not an interlock.

### Sync and verify

After all writers stop, synchronize source to the intended destination. Preserve permissions and symlink targets, and include SQLite WAL/SHM files if present rather than deleting them to make the copy simpler. A stopped, internally consistent copy is required; capture integrity checks on critical DBs.

Verify a path/type/size/content-hash inventory of retained files and symlink targets, plus critical database integrity and fixture/source manifests. Check all command exit codes. File counts and one manifest hash are insufficient. Exclude only documented rebuildable caches after their processes stop; never exclude logs, evidence, source, DBs or fixtures as “churn.” Keep excluded-file accounting.

### Switch and validate

Rename the local source as a rollback copy, then create the symlink to the verified external destination while the maintenance interlock is held. This is a two-step switch with a brief missing-path interval, not an atomic single operation. Roll back safely if linking or validation fails.

Preserve logical paths in launch descriptors; verify code using resolved physical paths still passes identity checks. Run one representative preview: DB writes/history, workbook read, evidence, retry pin and restart. Record the storage relocation separately from code fingerprints; do not rebuild every world merely because its physical storage moved.

Test missing-drive refusal using a controlled unavailable-target configuration, not by unplugging a mounted active database. Release the interlock only after the smoke test and manifests pass.

### Reclaim

The rename/symlink does not reclaim local bytes. Keep the rollback directory until the user explicitly approves deleting that exact verified backup. Report its current size and expected reclaimed space; do not print or execute a broad wildcard deletion. After approved deletion, measure actual free space. The portable drive must remain connected during subsequent runs.

## 7. Required next report

Provide: exact candidate fingerprint; corrected 4-case results with real invocations and durable revision evidence; browser support matrix and URL; remaining lifecycle cases; and whether relocation is merely staged or actually completed. If maintenance is performed, include stopped/restarted process inventory, verification manifests, rollback path and actual reclaimed space.

Do not make another completion claim based on a successful narration guard alone. The immediate product goal is a truthful task correction in a usable app. The storage goal is verified relocation without disrupting that work.
