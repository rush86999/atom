# Bounded assignment — canvas-edit decline reconsideration (F06/F07)

> ## SUPERSEDED 2026-09-28 ~18:20 EDT — DO NOT IMPLEMENT §2
>
> **This assignment is withdrawn.** Fresh-canvas retesting resolved the question it
> was built on: **F06 PASSED 4/4 on a disclosed pin**
> (`ATOM_ASYNC_EDIT_PLAN_MODEL=deepseek/deepseek-v4-pro`), each run a fresh
> API-created email canvas, 11/11 assertions, `outcome=verified_mutation`, subject
> unchanged, exactly 1 update row, value present after a real reload. **F07's
> legitimate-decline control also PASSED** (delta 0, zero update rows,
> `explicit_no_apply`, 6/6).
>
> The declines that motivated §1 were an **artifact of the reused, marker-contaminated
> canvases**, not a product defect. §1's measurement concern was correct and it is what
> resolved the blocker — but it resolved *against* the need for the mechanism.
>
> **Do not add clean-decline reconsideration for this milestone.** A second planner
> change now risks invalidating the browser success that was just established.
> Freeze scope around the working pinned configuration and finish acceptance.
> Reconsider unpinned-model behaviour later as a **separately measured** improvement.
>
> §3a (retain the `99 days` negative case), §3b (F02 uncorroborated), §3c (ledger
> consolidation) and §3d (symlink relocation dependency) **remain in force**.
>
> **Preserve the verified pinned configuration.** **Record any in-flight patch
> separately — do not overwrite concurrent work.**

Date: 2026-09-28. Assignment from: user. Issued by: read-only diagnosis lane.
Guide: `FINISH_LINE_EXECUTION_GUIDE_2026_09_28.md`.

**Single writer owns this patch.** All other agents are read-only on
`backend/core/chat_canvas_editor.py`, `backend/core/chat_tool_planner.py`,
`backend/integrations/chat_orchestrator.py` and `backend/tools/canvas_crud_tool.py`
until the patch below is verified.

## 0. Correction to an earlier finding of mine

An earlier note from this lane described the single-leg decline as the "root cause"
of the F06 blocker. **That was overstated and is withdrawn.** It is a *candidate
improvement*, not a proven root cause:

- A clean decline receiving one attempt is **not inherently wrong**.
- `_canvas_edit_shaped` is an **intent signal, not authority**. It must never be
  able to override the planner's decision. Any change must ask the model to
  *reassess*, never instruct it to accept.

Measured on: HEAD `1a953b589`, `chat_canvas_editor.py` sha256(16) `53e565e889824b25`,
`chat_orchestrator.py` `e14101821aed9248`, `chat_tool_planner.py` `9ffaad02421039b3`.

> **PROVENANCE DRIFT — re-verify before using §2.** `chat_canvas_editor.py` changed
> from `53e565e8` to `02bfbce9` at ~13:56 while this document was being written; the
> single writer is actively editing that file. The line numbers quoted in §2 shifted
> by roughly +32 (`_plan_structured` call sites moved 2202/2272/2348 → 2223/2306/2382).
> Re-resolve every cited line against the fingerprint you actually patch. The DECLINED
> log line and the early return on a clean decline were both still present at
> `02bfbce9`; no reconsideration leg existed yet at that hash.

## 1. The measurement must be redone before any code changes

Current F06/F07 evidence is **not trustworthy for model behaviour**, because the
canvases were reused across runs and accumulated prior-run markers. The planner
reasoning captured in `write_combined_c16/c16_controlled_bg-failure.json` shows the
model visibly distracted by a marker from an earlier run
(`<!-- C16SYNC-1790560206 -->` still inside the body, alongside
`<!-- C16BG-BG-FAILURE-... -->`). A reused canvas means run N's prompt contains
run N-1's artifacts, so "the model declined" cannot be separated from "the model was
confused by stale content".

**Step 1 (do this first, before touching code):** retest on **fresh API-created
canvases** with identical clean starting content and no prior-run markers. Capture
the actual planner input and the **selected model** for the turn. A provider
availability probe does not identify the model used for the call.

Only if clear, in-scope, supported edits *still* decline on clean canvases does the
reconsideration below become justified.

## 2. Bounded patch (only if step 1 still declines)

Add **one** bounded reconsideration when the existing edit-intent signal conflicts
with a **clean** decline:

- Precondition: `wants_edit=false`, `plan_contract_violation(plan) is None`, and the
  existing `_edit_requested` intent signal is true. Intent signal **gates the
  re-ask**; it does not decide the outcome.
- The re-ask must ask the model to **reassess the request against the canvas**. It
  must not instruct, imply, or steer toward acceptance.
- **A second decline is final.** No further legs.
- At most one reconsideration, including when the first attempt errors, times out,
  or the provider returns nothing. A provider failure must not escalate to a
  retry-until-success loop.

### Must be preserved unchanged

Authorization (the lifecycle gate upstream), schema/contract validation, target
matching (`_apply_patch_ops` exact-match against real content), revision/conflict
checks, and mutation verification + read-back. The change adds a *planning* leg
only; it must not widen what may be written.

### Tests required

1. Clear edit: first decline, then a valid plan → applied.
2. Legitimate decline twice: **zero** mutations.
3. Read-only question that merely *mentions* edits → no accidental mutation.
4. Missing target, or a plan proposing an unrelated field → no unintended write.
5. At most one reconsideration, including timeout/provider failure.

**Existing mocks that return the same decline are not sufficient.** Tests
`backend/tests/test_chat_canvas_editor.py:204,224,241,616,711` all use
`AsyncMock(return_value=CanvasEditPlan(wants_edit=False))`, which returns the same
answer to every leg. That shape cannot demonstrate the new behaviour and cannot
measure its latency cost. Use **sequenced** responses (decline, then accept) and
assert the call count. Measure and record the added latency — an extra planner leg
is a real cost on every conflicted turn, and the number belongs in the commit.

## 3. Separate items

### 3a. Retain the `99 days` mismatch fixture as a named negative case
`/tmp/d5_finish_line/planner_script.json` now serves `find: "Quote validity: 15 days."`.
The original mismatched string was `Quote validity: 99 days.` The shim log retains
both (17× `99 days`, 6× `15 days`), so the negative case is only partly preserved.
Guide §2: *"Do not align the fixture and erase evidence of the unintended edit."*
Keep the `99 days` variant pinned and named as a negative case.

### 3b. Mark the historical subject-edit allegation correctly
Status: **uncorroborated; original evidence unavailable.**

Measured basis: the word `subject` appears **0** times in the 23-entry shim log;
there is no subject-targeted op in any run. In
`write_combined_c16/c16_controlled_bg-failure.json` the canvas reads
`"subject": "Quote for Steve"` in **both** before and after, with
`has_new_text: false` and `audit_actions: ["create"]` only. "subject" appears in
artifacts solely as a *field name inside canvas JSON*, never as a mutation target.
The record alleged to show a subject write was a stale continuation in the
`write_combined` world, whose results were lost in the 2026-09-28 ~09:32 worlds
deletion (116 result files, cause not established).

**Consequence for the ledger:** current negative tests can pass **without** implying
the historical incident was fixed. F02 is INCONCLUSIVE — unproven *and*
uncorroborated. Do not let a green negative case be reported as closing it.

### 3c. Consolidate the ledger into one current table
`FINISH_LINE_STATUS.md` currently carries **three mutually inconsistent** accounting
blocks: F03 is both FAIL (line 216) and PASS (line 268); F04/F05 are both NOT RUN
(lines 217-218) and PASS (lines 269-270).

- Collapse to a single current table.
- Archive the superseded statuses rather than deleting them.
- **Copy the `/tmp` evidence into the acceptance package with hashes and original
  provenance.** `/tmp/d5_finish_line/*.json` is ephemeral and outside the repo; it
  will not survive. Record source path, mtime and sha256 for each artifact.
- Rerun only where **source identity or branch coverage is missing** — not
  everything, and not nothing.
- Per guide §9, a scenario that never reached its required branch is INCONCLUSIVE,
  not a pass. Do not drop unknowns from the denominator.

### 3d. Do not dismiss the symlink warnings solely because the root is local
Expected vs resolved targets were verified:

```
guard audit-symlinks --all   broken: 0    misanchored: 897
per world: 299 symlinks, 299 resolvable, 0 DANGLING  (x3 worlds = 897)
```

Sampled from `write_verify_0928/backend_root/`:

| link | resolves to | exists | entries |
|---|---|---|---|
| `core` | `<world>/code/backend/core` | yes | 603 |
| `tools` | `<world>/code/backend/tools` | yes | 31 |
| `config` | `<world>/code/backend/config` | yes | 1 |
| `data` | `<world>/runs/run-d3b3f7633097/data` | yes | 16 |

**Interpretation:** every link resolves to real content *inside its own world*, and
`data` correctly points at the run dir holding the served `atom.db` (411 MB, with a
live `-wal`/`-shm`). So `misanchored` is an **anchor-style** finding — the targets are
absolute paths into the worlds root rather than root-relative — and **not** a
missing-data or dangling-target condition today.

It is still not dismissible: these are absolute paths into the tree that AGENTS.md
treats as movable. A future relocation would invalidate all 897 at once, and per
AGENTS.md the silent-empty-acceptance-world failure mode is exactly one where a
launcher succeeds against nothing. Record this as a relocation precondition, not as
a clean bill of health.

## 4. Status

This lane made **no code changes** and did not touch the ledger, the fixture, the
worlds, or any live DB. Storage preflight was re-confirmed OK, no maintenance lock,
worlds root a real local directory.
