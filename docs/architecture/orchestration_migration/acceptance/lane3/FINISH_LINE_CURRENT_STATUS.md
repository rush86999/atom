# FINISH_LINE_CURRENT_STATUS — compact current state (single source for status)

Date: 2026-09-28, refreshed to the ~19:20 EDT single-writer closeout.
Guide: `FINISH_LINE_EXECUTION_GUIDE_2026_09_28.md`.
This document is **status only**. Detailed evidence is linked, not restated.
Handoff: `RESUME_finish_line.md` · freeze identity: `CANDIDATE_FREEZE.json`.

## Scope decision (in force)

**Do not add clean-decline reconsideration for this milestone.** The bounded
reconsideration is withdrawn — see the SUPERSEDED banner on
`FINISH_LINE_ASSIGNMENT_2026_09_28.md`. A second planner change now risks
invalidating the browser success that was just established.

**Freeze scope around the working pinned configuration and finish acceptance.**

Reconsider unpinned-model behaviour later, as a **separately measured** improvement
on a clean source.

Verified by this lane: no reconsideration mechanism exists in the working tree
(`grep -c "reconsider|reassess"` = 0 at `chat_canvas_editor.py` sha256(16)
`125fc16e`). There is no in-flight patch to preserve or unwind.

## Working configuration (preserve exactly)

| Item | Value |
|---|---|
| Pin env var | `ATOM_ASYNC_EDIT_PLAN_MODEL` — read at `chat_canvas_editor.py:226`, `chat_orchestrator.py:13019` |
| Pinned model | `deepseek/deepseek-v4-pro` (already-authorized provider, seeded BYOK store; no new credential) |
| Configured vs actually selected | agree; `cap=14000 dur=5.8s finish=stop`, recorded in `launch_descriptor.json` → `effective_flags` |
| Unpinned default | `opencode-go/glm-5.3-flash` — declined every clear edit, repeatably. **Cause UNDETERMINED**; **optional follow-up research, NOT a new gate** for the explicitly pinned preview. See "What the pinned runs do NOT establish" below. |

The pin is **real product code**, not a shim. No prompt routing, no hidden fallback,
no shim on the F06 path.

## What the pinned runs do NOT establish

**F06 PASS is scoped to the pinned configuration.** It demonstrates the supported
edit works under a disclosed, explicitly configured model. It does **not** disprove
that the unpinned decline was a measurement artifact, and it does **not** exonerate
the product for the unpinned path.

The unpinned default (`opencode-go/glm-5.3-flash`) declined every clear edit,
repeatably — but those runs used the **reused, marker-contaminated canvases**. The
decisive experiment was never run: **the unpinned default on fresh canvases.** Until
that exists, the unpinned decline has at least three live explanations — canvas
contamination, model capability, or a product defect — and **none has been
eliminated**.

So the earlier sentence "the declines were an artifact of the contaminated canvases,
not a product defect" was **wrong**, and is withdrawn here and in the SUPERSEDED
banner on `FINISH_LINE_ASSIGNMENT_2026_09_28.md`. The correct statement is narrower:
the pinned runs succeeded; the unpinned decline remains **unexplained**.

This does not block the milestone. The pin is a legitimate disclosed configuration
for a scoped preview. Record the unpinned decline as a **separate measured
limitation** and re-measure it later, on a clean source, as its own improvement.

**The unpinned fresh-canvas experiment is optional follow-up research, not a new
gate.** It does not gate the explicitly pinned preview, and its absence must not be
recorded as a blocker. F06/F07 stand on their recorded configuration and fingerprint
and are scoped to exactly that.

## F01–F12 current

Statuses are for the current source identity only. Per guide §9, a scenario that
never reached its required branch is INCONCLUSIVE, not a pass.

| ID | Status | Evidence |
|---|---|---|
| F01 | **PASS** | 15/15 launch checks, 16/16 serving modules matched to the immutable export, 0 from the mutable checkout. |
| F02a | **UNEXPLAINED / UNCORROBORATED** | Historical subject-edit incident. Original evidence unavailable. See "F02" below — do not close on F02b. |
| F02b | **PASS** | Current mismatched-target negative test. Does **not** claim F02a fixed. |
| F03 | **NOT RUN** | **Precondition now MET and verified offline against production code:** both `CanvasEditPlan` entries in `fixtures/provider_shim/mutation_overlap.json` parse through the real `CanvasEditPlan` model and real structured-parser helpers — `tool_calls_present=True`, `wants_edit=True ops=1`, `plan_contract_violation=None`, 2/2. Selection made unambiguous: `provider_shim.py` now selects by **exact advertised tool name first**, prompt substring only as fallback, recording `selected_by` / `tool_scoped_entries` / `gate_missed`. **Consumption still unproven** — no live shim+server run yet. Not blocked by the planner decline. |
| F04 | NOT RUN | Controlled background success. |
| F05 | NOT RUN | Controlled background failure. |
| F06 | **PASS 4/4 — pinned config only** | Real browser, real planner, fresh API-created email canvas each run: body 15→30 days, subject unchanged, exactly 1 update row, `canvas_audit` delta 1, distinct operation-linked audit id, value present after real reload, `outcome=verified_mutation`, 11/11. Live dev DB unchanged (887 / 2026-09-26 10:37:11.129501). **Scope: the disclosed DeepSeek pin only — see "What the pinned runs do NOT establish".** |
| F07 | **PASS** | **Second DISTINCT real-planner edit**, fresh email canvas, real browser: payment terms `Net 30` → `Net 45`, body changed, subject unchanged, exactly 1 update row, world delta exactly 1, operation-linked audit `e8f4e709…`, value present after a real reload, `verified_mutation`, **11/11**. Legitimate-decline control **separate and still PASS** (delta 0, zero update rows, `explicit_no_apply`, 6/6) — a decline was not counted as completion of a supported edit. |
| F08 | NOT RUN | Connected / disconnected / empty-channel recovery. |
| F09 | NOT RUN | Overlap / duplicate terminal events. |
| F10 | NOT RUN | Keyed retry, payload conflict, restart pin. |
| F11 | NOT RUN | Effect-before-kill reconciliation. |
| F12 | NOT RUN | Read-preview regressions. |

**Remaining work:** F03/F04/F05 (controlled) · F08–F11 (delivery/recovery) ·
F12 (read regressions). **The combined preview is NOT promoted.**

## Two evidence tracks — keep separate, never merge

| Track | World | Holds | Status |
|---|---|---|---|
| **1 — pinned browser** | `write_verify_0928` | Retained **F06/F07** real-browser evidence (disclosed DeepSeek pin). Remaining cases pending. | **Authoritative for F06/F07.** |
| **2 — controlled runs** | `write_combined` | Newer controlled-run evidence, with the assertion gaps from review still open. | **Not acceptance.** |

**`write_combined`'s "15/15" (`/tmp/d5_finish_line/c16_controlled_sync.json`, world
`write_combined`, generated 12:55, shim pin `local_ba16366a/shim-1`) must NOT overwrite
track 1 and must NOT become overall acceptance.** It is a shim-injected controlled run
on a different world and a different fingerprint, and its branch assertions are the
ones under repair. Repairing them does not retroactively promote it past track 1.

## Live serving identity — re-verified 2026-09-28 ~19:45 EDT

A published manifest records a **verified state at freeze time**. It is not permanent
proof of what the server is running now. Re-checked live:

| Check | Result |
|---|---|
| Serving pid | **60503**, started 13:53:50, `_app.py` on :8140 |
| `cwd` | `…/acceptance_worlds/write_verify_0928/backend_root` (the export) |
| `database` | `…/write_verify_0928/runs/run-7240b4691cc1/data/atom.db` |
| `source_id` | `1a953b58934d-dirty.237b34508fe4` |
| **16 recorded serving modules vs export on disk** | **16/16 MATCH, 0 drift, 0 absent** |
| `integrations.chat_orchestrator` (export) | `e14101821aed` — byte-identical to freeze |
| `mutable_bleed` | `[]` |

**A working-tree change does not invalidate the frozen preview.** `chat_orchestrator.py`
is now `6cadd0a1` in the checkout (mtime 15:12:55) and `chat_canvas_editor.py` is
`a834756e` (15:12:10) — **both edited after the server started** — yet the export the
server imports is unchanged. That change is inert for this candidate: **no rebuild and
no rerun is warranted merely because the checkout moved.**

**Before any further acceptance, confirm the serving process still uses the export and
its recorded module hashes.** Re-run the 16-module on-disk comparison; do not rely on
this record. Note: `lsof` reports 0 open `.py` handles under the export because Python
closes source files after import — that is not evidence of anything, in either
direction. Only the hash comparison establishes serving identity.

## Frozen candidate identity (established by the single writer, ~19:20 EDT)

**"Same candidate" was measured, not assumed.** After the F06/F07 runs, two files
inside the world export changed, so equivalence could not be taken for granted:
**16/16 serving application modules are byte-identical** (per-module sha256 in
`CANDIDATE_FREEZE.json`). The only changes inside the export are two **harness
drivers, not serving code**: `provider_shim.py` (tool-name-first selection) and
`canvas_write_verify.py` (`--expect/--old/--new/--field`, added for the F07 second
edit). **F06/F07 therefore retain their evidence.**

| Item | Value |
|---|---|
| Base commit | `1a953b58934d144b2cd149c557d1243e9e16ea1c` |
| Export | `f530c509948d947d` |
| World / run | `write_verify_0928` / `run-7240b4691cc1` |
| Ports | :8140 backend · :3140 frontend |
| Planner pin | `deepseek/deepseek-v4-pro` (disclosed in `launch_descriptor.json`) |
| Fixture | `api-seeded-fixture` · mutable bleed 0 |
| Preserve | :3102 / :8071 and the live dev DB |

**If any case forces a rebuild, the export hash changes and all 16 module hashes must
be re-verified and stated — not assumed.** File hashes of the *working tree* do not
establish what a serving process executed; only the per-module hash comparison
against the export does.

**Editing is supported only for the disclosed DeepSeek pin, and only for the measured
browser body-edit workflow.** The unpinned default `opencode-go/glm-5.3-flash`
declined every clear edit; that result is **not generalised**.

## `write_verify_0928` is PRESERVE-ONLY

`export_sha256 = f530c509948d947db10ce47772723839b73a4f0a48e78ca869a90df26a124e42`,
`mutable_bleed = []`. This world/export is the **sole home of the retained F06/F07
pinned-browser evidence** and is **preserve-only**. Production fixes must **not** be
made inside it — chasing a fix in the export would destroy the evidence it exists to
hold.

Work that remains, in order:

1. **Repair the acceptance assertions in the HARNESS** (outside the world export —
   drivers, not serving code), so a decline, stall, or non-branch-reaching run cannot
   be recorded as a pass.
2. **Reproduce and fix F09's missing overlapping-turn terminal outcome IN THE
   CHECKOUT** — a production-path fix, so it lands in working-tree source.
3. **Create a NEW immutable candidate** for the production change, then run the
   affected gates and the remaining cases (F03–F05, F08, F10–F12) against it.
4. **Publish results BY FINGERPRINT**, distinguishing **RETAINED** (F06/F07 on
   `write_verify_0928` / `f530c509948d947d`, 16/16 verified) from **NEWLY VERIFIED**
   (the new candidate). Never blend the two into one number; a retained result does
   not transfer to a new fingerprint unless re-run, and the limitation must be named.

**Explicitly unverified:** PDF rendering. The worker fix is correct and the asset is
served and module-runnable, but the running app has still not been seen to request
it. Do not claim PDF rendering works.

**Known unrelated bug, not repaired:** the frontend requests
`/api/v1/preferences?user_id=${getCurrentUserId()}&workspace_id=default` — a literal
un-interpolated template string.

## F02 — keep separate from the passing negative test

**Status: historical incident UNEXPLAINED and UNCORROBORATED. Original evidence
unavailable.** Measured basis: `subject` appears 0 times in the 23-entry shim log; no
subject-targeted op exists in any run; in
`write_combined_c16/c16_controlled_bg-failure.json` the subject reads
`"Quote for Steve"` in **both** before and after, `has_new_text: false`,
`audit_actions: ["create"]` only. The record alleged to show a subject write was a
stale continuation in the `write_combined` world, lost in the 2026-09-28 ~09:32
worlds deletion (116 result files, cause not established).

**A passing current negative test (F02b) does NOT close F02a.** Do not report a green
negative case as evidence the historical incident was fixed.

**Retain the `99 days` mismatch fixture as a named negative case.**
`/tmp/d5_finish_line/planner_script.json` now serves `15 days`; the original
mismatched string was `Quote validity: 99 days.` Shim log retains both (17×/6×).
Guide §2: do not align the fixture and erase evidence of the unintended edit.

## Symlinks — relocation dependency, not an empty world

`world_storage_guard audit-symlinks --all` → `broken: 0`, `misanchored: 897`
(299/world × 3; **299/299 resolvable, 0 dangling**).

Sampled from `write_verify_0928/backend_root/`: `core`→603 entries, `tools`→31,
`config`→1, `data`→`runs/run-d3b3f7633097/data` (16), all resolving **inside their own
world**; `data` correctly targets the run dir holding the served 411 MB `atom.db`.

**Interpretation:** every link resolves to real content. This is an **anchor-style**
finding (absolute paths into the worlds root rather than root-relative), **not**
current evidence of an empty world and **not** a dangling-target condition.

**Preserve this audit for the maintenance/relocation procedure.** All 897 are absolute
paths into the tree AGENTS.md treats as movable, so a future relocation invalidates
them at once — and the silent-empty-acceptance-world mode is exactly a launcher
succeeding against nothing. Record as a relocation precondition.

## Open ledger defect (needs fixing by the single writer)

`FINISH_LINE_STATUS.md` is **not** a valid current status and now actively
contradicts verified results. It carries **two** F01–F12 tables:

- lines 146–159: F01 INCOMPLETE, everything else NOT RUN.
- lines 214–225: F03 **FAIL**, F06 **FAIL** (`wants_edit=False`), F07 NOT RUN.

Both are stale. Line 219 records F06 as FAIL, but F06 is **verified PASS 4/4**.
Anyone reading the ledger today would conclude the supported edit failed.

Required: collapse to **one** current table matching this document; **archive** the
superseded statuses rather than deleting them; **copy the `/tmp/d5_finish_line/*.json`
evidence into the acceptance package** with sha256 + original path + mtime (it is
ephemeral and outside the repo, so it will not survive). Rerun only where source
identity or branch coverage is missing.

Still open as of this refresh. The `CANDIDATE_FREEZE.json`, `RESUME_finish_line.md`
and this document are the current trio; `FINISH_LINE_STATUS.md` is legacy.

## Published handoff

`acceptance/lane3/RESUME_finish_line.md` — the single handoff. Carries the frozen
identity, the verified-equivalence result, the preserve list (**:3102 / :8071** and
the live dev DB), the ordered remaining case list **with the appropriate driver per
case** (not all need a shim), the consumption evidence to quote from the shim capture
(`selected_by`, `tool_scoped_entries`, `gate_missed`), the instruction to persist each
case immediately and resume at the first unfinished one, and the fixed verdicts not to
re-litigate. It states explicitly that the next session resumes **authorized** work
without another permission round.

## Log hygiene

`notes/AGENT_COORDINATION.md` is **66 MB** and is becoming counterproductive — it
must be grepped, not read, and it forces full-file rewrites to stay current.

- Keep status here, with links to detailed evidence.
- **Append only brief pointers to the coordination log during active work.**
- **Do not rewrite the shared log** while other sessions are active in it.

## Status of this lane

No code changes, no ledger edit, no fixture/world/live-DB change. Storage preflight
re-confirmed OK, no maintenance lock, worlds root a real local directory.
