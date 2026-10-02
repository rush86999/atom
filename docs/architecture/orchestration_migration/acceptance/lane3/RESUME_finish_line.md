# RESUME — finish-line closeout, remaining cases

**Read first:** `FINISH_LINE_STATUS.md` (the only current status),
`FINISH_LINE_EXECUTION_GUIDE_2026_09_28.md` (the assignment),
`CANDIDATE_FREEZE.json` (frozen identity), and the tail of
`../../../../../notes/AGENT_COORDINATION.md`.

**You are resuming authorized work. Do not ask for permission to continue.** The
user has explicitly authorized the remaining cases. No planner changes, no new
framework, no storage cleanup, no extra acceptance requirements.

## Frozen candidate — do not rebuild unless a case requires it

| | |
|---|---|
| World / run | `write_verify_0928` / `run-7240b4691cc1` |
| Ports | backend **:8140**, frontend **:3140** |
| Export sha256 | `f530c509948d947d…` |
| Base commit | `1a953b58934d144b2cd149c557d1243e9e16ea1c` |
| **Planner pin** | **`deepseek/deepseek-v4-pro`** (disclosed; `launch_descriptor.json` → `effective_flags.ATOM_ASYNC_EDIT_PLAN_MODEL`) |
| Unpinned default | `opencode-go/glm-5.3-flash` — **declined every clear edit**; do not generalise F06/F07 to it |
| Fixture | `api-seeded-fixture` (small, app schema, no dev rows) |
| Auth | next-auth CredentialsProvider, world-local `0600` credential; never record the secret |

### "Same candidate" — verified, not assumed

The world was **not rebuilt** after the two harness-driver edits, so the export
fingerprint `f530c509948d947d…` is **unchanged** from the candidate that produced
F06/F07, and **16/16 serving application modules are byte-identical** because the
exported tree is literally the same tree (per-module sha256 in
`CANDIDATE_FREEZE.json`).

Only the **checkout copies** differ; the world export retains the older ones.
Both are **harness drivers, not serving code**:

- `scripts/orchestration_acceptance/provider_shim.py` — tool-name-first selection
  (this is the F03–F05 change; it is what you are about to exercise)
- `scripts/orchestration_acceptance/canvas_write_verify.py` — `--expect/--old/--new/--field`
  added for the F07 second edit

So **F06/F07 retain their existing evidence.** If a case forces a rebuild, record
the **new** export hash **alongside** `f530c509948d947d…` (do not overwrite it) and
re-verify the 16 module hashes; state any difference rather than assuming
equivalence.

## Preserve

- **`:3102` / `:8071`** — the read preview. Do not restart, re-provision or
  re-export it. F12 runs against it read-only.
- **The live dev database** — never open it read-write. No ad-hoc probes.
- No world deletion, no retention apply, no portable-drive relocation.

## Case order and driver

Real-planner browser evidence and controlled effect-layer evidence are **distinct
tracks**. Do not merge them; not all of these need a shim.

| # | Case | Driver | Must prove |
|---|---|---|---|
| 1 | **F03** controlled synchronous edit | `run_isolated.py --cases mutation_overlap` with the shim | live selection (`selected_by=tool`), parser acceptance, **consumption** (capture shows the intended entry served to the `CanvasEditPlan` call), exactly one verified mutation |
| 2 | **F04/F05** background success / failure | shim + `ATOM_ACCEPTED` fork assertions | the fork actually happened **and** the terminal state was recorded, *before* judging delivery. Do not conclude delivery from a notification |
| 3 | **F08** delivery: connected / disconnected / empty channel | D5 driver | subscribe **before** the request; persist, reload, recover once, **no extra mutation** |
| 4 | **F09** overlap / duplicate terminal events | D5 driver | no duplicate message or effect; no cross-turn identity mixing |
| 5 | **F10** keyed replay / payload conflict / restart pin | D5 driver | original response semantics on replay; changed payload conflicts; restart preserves the pin |
| 6 | **F11** effect-before-kill | existing confined test barrier | effect committed, terminal state not; kill externally, restart the same durable run, reconcile, **no duplicate write**. Do not poll for the ~20 ms window |
| 7 | **F12** read-workflow regressions | `browser_verify.py` against **:3102** | chat, lookup, replacement, formatting, re-search, reload |

### Shim consumption evidence (the thing that was missing)

`provider_shim.py` now records, per request, into the capture file:
`selected_by` (`tool` | `substring`), `tool_scoped_entries`, `matched_key`,
`tool_gate_ok`, `tool_gate_wanted`. **Read that capture and quote it.** A stall
is evidence about the script, not the product — record which.

The shim's two `CanvasEditPlan` entries are already **parser-validated offline
against production code** (`tool_calls_present=True`, `wants_edit=True ops=1`,
`plan_contract_violation=None`, 2/2). Re-validate through the live parser in-run
and record the result.

## Persist each case immediately

Append a row to the F01–F12 table in `FINISH_LINE_STATUS.md` **as each case
completes**, with PASS/FAIL/INCONCLUSIVE/NOT RUN, the evidence path, and an
explicit reason. A scenario that never reaches its required branch is
**INCONCLUSIVE, not a pass**. Never remove anything from a denominator.

**If interrupted, resume at the first unfinished case.** Do not rebuild, do not
re-run completed cases, and do not overwrite this file or another stream's
`RESUME.md`. Save next command, first failing assertion, run identity, evidence
paths and file hashes.

## Finish with

1. One **current support table** (F01–F12) linking the frozen candidate, the
   disclosed configuration, results and evidence paths.
2. A handoff recording: preview URL and exact supported model/config/workflows;
   a short manual guide actually performed in the browser; before/after content
   and audit/effect evidence; sanitized traces and screenshots; scoped changes,
   rollback instructions, and **exact unverified limitations**.

## Fixed, do not re-litigate

- **F02a** — the 2026-09-27 subject-for-body incident remains **UNEXPLAINED**.
  Its fixture was deliberately not aligned. Do not claim it fixed.
- **F02b** — current mismatched-target negative test **PASS**, separate from F02a.
- **Unrelated bug, do not fix here:** the frontend requests
  `/api/v1/preferences?user_id=${getCurrentUserId()}&workspace_id=default` — a
  literal un-interpolated template string.
- **PDF worker is fixed-but-partially verified:** the asset is emitted and served
  and runs only as a *module* worker; the running app has still not been observed
  to request it. Report as unverified, not as done.
- **Editing is supported only for the disclosed `deepseek/deepseek-v4-pro` pin.**
  Promotion of the combined preview waits on F03–F05, F08–F12.
