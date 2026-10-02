# Write-path final status — D0, D1, D3, D4

2026-09-27. Order as instructed: **D0+D1 → D3/D5 → D4**, then C16.

## Source identity

`git HEAD` is unchanged at `a8bc48dc1` and therefore does **not** identify this
source. The identity of the fix is the per-file hash set in
`write_path/fingerprints_after.json`, against the pre-change baseline in
`write_path/baseline.json`:

| File | sha256 (16) | vs baseline |
|---|---|---|
| `backend/integrations/chat_orchestrator.py` | `441bcfa7b7c883d1` | **CHANGED** |
| `backend/core/chat_canvas_editor.py` | `11c0d94e80daf106` | **CHANGED** |
| `backend/core/task_lifecycle.py` | `a49d529dc69362e9` | same |
| `backend/core/async_turn_continuation.py` | `13bdf668cba7832b` | same |
| `backend/tools/canvas_crud_tool.py` | `165654770b5dd5bb` | same |
| `backend/tests/test_write_path_d0_negative_control.py` | `d38ebc0417cc41e5` | new (13 cases) |
| `backend/tests/test_chat_canvas_editor.py` | `2578de4ff200685d` | fakes updated |

Exercised on world `c16_d0`, run `run-5cc63f19d3f0`, `:8073`, source_id
`a8bc48dc13e5-dirty.d3c014968762`. The two measured previews are untouched:
`preview_v1` `:3101`/`:8051` and `candidate_fix1` `:3102`/`:8071`, both 10/10.

## Negative control — actual output, both directions

The suite is `backend/tests/test_write_path_d0_negative_control.py`, **13 cases**.

```
PRE-FIX  (candidate_fix1 immutable export, chat_canvas_editor.py
          = 60fc8585e63b112251f6dd8f7e8e069085ef8f349953a0e70f319a9fd575d0bc)

FAILED tests/test_d0_control.py::VerificationBindingNegativeControl::test_wrong_canvas_is_rejected
FAILED tests/test_d0_control.py::VerificationBindingNegativeControl::test_incidental_text_does_not_satisfy_the_intended_change
FAILED tests/test_d0_control.py::VerificationBindingNegativeControl::test_concurrent_update_is_rejected
FAILED tests/test_d0_control.py::VerificationBindingNegativeControl::test_no_audit_id_means_no_verified_operation
FAILED tests/test_d0_control.py::VerificationBindingNegativeControl::test_partial_write_is_rejected
FAILED tests/test_d0_control.py::D0NegativeControl::test_editor_refuses_to_report_success_when_readback_disagrees
FAILED tests/test_d0_control.py::D0NegativeControl::test_verified_write_still_succeeds
7 failed, 2 passed, 19 warnings in 0.32s
```

```
POST-FIX (working tree)

9 passed, 24 warnings in 8.15s      (before the D4 cases were added)
13 passed, 32 warnings in 8.28s     (final suite)
```

The harness copies `core/ + tools/ + integrations/ + api/` from the export to a
temp tree and repoints the test's `BACKEND` there.

**Correction to an earlier claim in this session.** I previously reported
"3 FAILED pre-fix". That measurement was **invalid**: the temp tree contained only
`core/`, so `patch("tools.canvas_crud_tool...")` raised `ModuleNotFoundError` and
every test errored at collection instead of failing an assertion. The numbers
above are from a tree that also contained `tools/`, and the failures are named
per-test assertion failures.

The 2 cases that already passed pre-fix, and why that is correct rather than
suspicious:
- `no reply text can assert the change` — pre-fix also avoided the phrase.
- `a plan asking for nothing cannot succeed` — the pre-existing no-change guard
  already rejected a no-op plan.

## What each fix does

**D0 — success requires verified persistence, bound to the intent.** The store
saying `success: True` is no longer proof. Read-back is unconditional (it used to
run only under `if isinstance(evidence_contract, dict)`, so an ordinary canvas was
never verified). On top of the necessary content equality, verification is bound
to four further things, because equality alone does not prove the *intended*
change — a canvas that already said "30 days" elsewhere would satisfy it while
the named field never moved:

| Bound to | How |
|---|---|
| canvas | the read-back must be this `canvas_id` |
| operation | the store must have recorded an `audit_id` |
| revision | the write must not have raced (`conflict`) |
| changed fields | per op, scoped to the named field: the replacement is present **and** the text it replaced is gone |

Replace-mode plans (no ops, declared full content) are verified by equality
against the declared content and reported as such, rather than being failed for
having no ops. A plan with neither ops nor declared content cannot succeed.

Unverified → the user-facing text is **regenerated**; the planner's reply is not
used. `write_recorded` is preserved alongside `postcondition_verified: False` so
"attempted but unverified" stays distinct from "rejected".

**D1 — the claim is released when nothing was applied.** The mechanism
(`finish_edit_turn` → `cancel_operation`) already existed and was already tested;
only the call was missing. A new `_release_unapplied_edit` helper runs at the
call site in `process_chat_message`, where the reservation dict is in scope, and
fires whenever a reservation exists and the leg reported neither `updated is True`
nor `postcondition_verified is True`. Proven on a live world:
`released an unapplied edit claim: run=… operation=…` →
`goal_runs…operations[0].status = cancelled`.

**A correction to my own earlier reporting here too.** My first probe read
`task_operation_records.status` and called D1 still-failing. Wrong source:
`TaskOperationRecord`'s docstring says *"The task's own JSON holds the operation
for reading, but a JSON column cannot arbitrate two processes racing… This table
is the arbiter."* Its `status` is a reservation-ledger field and legitimately
stays `pending`. The probe reads `goal_runs.parameters.task_lifecycle.operations[]`.

**D3 — identity on every outcome.** All three outcomes now carry
`execution_id`, `operation_id` and an explicit `outcome`:
`refused` / `unverified` / `completed`. Verified on the refusal path:
`execution_id: 1bb0998b-3274-4140-be09-c36f0224ee18` (previously `None` while
lifecycle state was reserved, orphaning the release).

**D4 — self-contradictory plans get one bounded repair.** `wants_edit=False`
with nonempty operations is a contradiction, not a decline, so it takes exactly
one repair through the existing structured-planning mechanism (mirroring the
patch-failure re-ask), with a suffix naming the contradiction. It explicitly does
**not** execute the operations because they exist, and does **not** treat which
model answered as meaningful — model selection is a routing decision and carries
no authority over whether the canvas may change; authorization is the lifecycle
gate's job upstream. A repair that also declines stays a decline.

## Two measured findings that change the plan

**1. `gemini-3-flash` is inconsistent across identical runs.** The unpinned route
resolves to `opencode-go/gemini-3-flash` every time (BPC cost-priority, "cheapest
capable"; openrouter is credit-exhausted with 12 × HTTP 402 in the current log).
Against the same prompt and a valid canvas it has produced **both**:
- `wants_edit=False` **with `ops=1`** (earlier, candidate_fix1) — the self-contradiction D4 now repairs;
- a clean `wants_edit=False` with no operations (now, c16_d0) — a legitimate "no".

So D4 fixes the contradiction case and correctly does not fire on the clean
decline. **D4 cannot close C16**, and it should not: "do not perform this edit"
is a valid planner answer, and overriding it is exactly the "execute the
operations merely because they exist" failure the instruction forbids.

**2. D5 is narrower than I reported.** I said the user is "never told" the
continuation failed. That is **wrong**. The durable row is written and committed
before the broadcast (`get_db_session()` commits on clean exit), and it is
retrievable: the world contains
`lane3-edit-1790534554 | assistant | [background continuation — failed of: "in the open canvas…"]`
from the pinned run. A reloaded browser **does** recover the outcome.

What D5 actually lacks is narrower and was **not fixed by this document's
author**; the items below are the state as of 2026-09-27 and are superseded by
`WRITE_PATH_HANDOFF.md`, which records D5 presentation as fixed and verified
(`has_raw_bracket_diagnostic: false`, live delivery and reload recovery both
green, on candidate `90f0354c97a9…`):
- the live toast is lost when the channel is empty, so the user learns only on reload;
- the recovered text is a raw bracketed internal string (`[background
  continuation — failed of: …]`) rather than a rendered outcome;
- there is no status endpoint to ask "what happened to my background edit", so
  recovery depends on the history projection happening to include the row;
- an empty channel must not cause a re-run, and that is untested.

`async_turn_continuation.py` was **unchanged** as of that measurement (hash
identical to baseline), which is why D5 was recorded as open rather than
claimed.

**Update 2026-09-28 (D5 write-path lane).** The zero-effect sentence on that
path is now a VERIFIED claim rather than a hopeful one:
`async_turn_continuation._verified_zero_effect(cont)` gates
"Nothing was changed on the canvas." on two independent durable-store
observations (the canvas's audit trail has not advanced past the fork snapshot,
AND no audit row carries an operation id this continuation legitimately owns)
with a content-hash cross-check; the budget-exhausted and
attempts-exhausted paths both go through
`_zero_effect_sentence(cont)`, and anything that cannot be established yields
"I could not confirm that the canvas is unchanged. Check it before relying on
it." instead. `tests/test_zero_effect_claim.py` (6 cases) pins it.

The same defect class on the SYNCHRONOUS edit path was found and fixed here —
see the handoff's change list: a store refusal is not a zero effect until the
store itself says the append was never attempted, so
`update_canvas_content`/`restore_canvas_version` now report `write_outcome` on
every return and `describe_apply_failure` defaults to uncertain wording
(`tests/test_write_zero_effect_claims.py`, 39 cases).

## C16 status: still UNPROVEN, and the effect layer has never been reached

The probe on the all-fixes build moved the first divergence from
`interpretation` to `effect` — but only because D3 gave the refusal an
`execution_id`. The planner still declines, so **no turn has ever carried a
canvas write through to a durable mutation at any fingerprint.** C16's
`synchronous success` case is unreachable through the real planner, and
`background success` is unreachable for the same reason.

This is why the next step must be a **controlled accepting planner**: inject a
planner that returns a consistent `wants_edit=True` plan so the real
`apply_canvas_edit` → store → read-back → verification path executes for real.
That is effect-layer coverage and must be labelled as such — it is not evidence
that the production planner accepts edits, which it measurably does not.

The controlled planner does **not** exist yet. I stopped short of building it
rather than leave a half-wired injection path in the write path; that is the next
piece of work, and its design constraint is that it must bypass only the planner
call, never authorization, never the store, and never the verification.

## Regression

| Suite | Result |
|---|---|
| `test_chat_canvas_editor.py` + `test_task_lifecycle.py` + `test_write_path_d0_negative_control.py` | **259 passed** then **13 passed** for the control file after D4 |
| acceptance guards, task-correction routing, structured delivery, reply-leg safety, pending-file resume, chat transport, streaming wiring, governance streaming, world storage guard | **410 passed, 2 xfailed** |

`test_chat_canvas_editor.py` required updating because its fakes asserted the old
fiction: 11 tests stubbed `apply_canvas_edit` with a bare `{"success": True}` and
4 patched only the *write* tool while an autouse fixture made `read_canvas`
report not-found — precisely the conditions under which the incident is
invisible. They now use a store that actually persists (`_durable_store`) and a
stub that states verification (`_verified_apply`). No assertion was weakened.

**Three more stale fakes of the same kind, found and fixed 2026-09-28** (each
one asserted the pre-verification fiction, so each one had stopped testing what
it claimed to test):

| Test | What it stubbed | Fix |
|---|---|---|
| `test_canvas_app_editor_fixes.py::test_apply_replace_merge_via_crud_layer` | `update_canvas_content` → `{"success": True}` | a `_persisting_store` fake that records the write and returns its `audit_id` |
| `test_canvas_link_verification.py::test_apply_proceeds_when_all_new_links_live` | the same | the same, inline |
| `test_write_path_d0_negative_control.py::test_inconsistent_plan_gets_one_bounded_repair` | the literal token `SELF-CONSISTENT-INCONTRARY` in the repair prompt | the current wording that names the contradiction (`self-contradictory`) |

## Bottom line

| Defect | State |
|---|---|
| **D0** false success claim | **Fixed.** Unconditional read-back, bound to canvas/operation/revision/fields; 13 controls, 7 failing pre-fix |
| **D1** stranded claim | **Fixed and proven live** — claim released to `cancelled` |
| **D3** identity on every outcome | **Fixed and observed** — `execution_id` present on the refusal |
| **D4** inconsistent plans | **Fixed and unit-proven**; cannot fix a *consistent* decline, by design |
| **D5** terminal-outcome recovery | **Fixed** (presentation verified on `90f0354c97a9…`), and the zero-effect claim on it is now verified rather than asserted; see the 2026-09-28 update above and the handoff |
| **C16** | **UNPROVEN.** Effect layer never reached. Needs the controlled accepting planner |
