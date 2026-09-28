# Lane 3 resume — c16 identity contract (2026-09-27, session 3)

Additive. Does not overwrite `RESUME_c16_background_session2_2026_09_27.md` or any
other stream's resume document. Machine-readable state: `CHECKPOINT.json` here.

## Done and verified (steps 1-3 of the current direction)

**1. Durable lookup repaired.** `durable_continuation()` now binds the measured
database to the *served* configuration: it compares the harness's db against the
server's own `DATABASE_URL` in `<run_dir>/server_env.json` and refuses to conclude
on mismatch. Identity is exact (`metadata.session_id` equality, not a substring
match). It returns a verdict with `lookup_ok` / `lookup_problem` and classifies the
row `missing | duplicate | running | terminal`. `durable_lookup_controls()`
exercises all four on every run and is recorded in the report. An untrustworthy
lookup yields **INCONCLUSIVE**, never "no continuation".

The old query was never wrong — the harness had been reading a *different world
DB* than the server wrote. The cross-check is what makes that class of failure
unable to masquerade as a product result.

**2. Identity contract established.** A canvas edit carries four distinct ids
that are equal by nothing:

| id | meaning |
|---|---|
| `execution_id` | the interactive turn that was answered |
| `origin_operation_id` | that turn's task-lifecycle reservation — **the id the write path stamps on the audit row** |
| `continuation_id` | the background continuation |
| audit row id | the mutation itself |

The fork site passed `execution_id` but **not** the lifecycle operation id, so the
relationship was unreconstructable. It is now carried, persisted durably in the
`AgentExecution` metadata, and `_operation_identity()` / `_matched_operation_row()`
locate the mutation *through* it with exact `operation_id` equality (the JSON SQL
predicate is an optimisation; the equality is the decision).

Verified against the demonstrated evidence:

- old, no origin id → `matched_row: null`, `landed: false`, `preapply: null`
  (proceeds to re-edit and loses the revision race)
- new, origin id carried → `matched_row: audit b3cb9277` (the row that actually
  landed), `landed: true`, `preapply: already_applied`

**3. Reconciliation without repeating.** `already_applied` is no longer claimed on
the probe alone: the matched row must still *be* the canvas's current revision
and belong to this canvas. Superseded or absent revision ⇒ no claim, and the
existing rules decide. This narrows what counts as done. The revision door and
every read-back gate are untouched — no verification was relaxed. The heuristic
revision-attribution branch in `_classify_preapply` is deliberately **unchanged**,
pending the executed trace.

## Fresh candidate frozen

`c16_d1`, port 8075, export `0410e02f13ed5f0c`, identity
`a8bc48dc13e5-dirty.32f44`, preflight green, 46 parquets verified. The snapshot is
byte-identical to the working tree (`core/async_turn_continuation.py`
sha256_16 `822b0ee42f4c3f78` in both), so the identity fix, the `READBACK-DECISION`
diagnostic and the budget-knob pass-through are all genuinely under test.

`preview_v1` (3101/8051) and `candidate_fix1` (3102/8071) untouched and listening.
`c16_d0` left intact as the evidence world for the 16:36 snapshot.

## Not green yet — two open problems

**Case 1 FAILS and case 2 is INCONCLUSIVE on c16_d1.** The harness machinery
itself is green there (`durable_lookup_was_trustworthy`,
`durable_lookup_controls_all_green`, `interactive_budget_knob_reached_the_server`),
and the verdict is correctly *inconclusive* rather than a product failure.

1. **The stall cannot target the edit leg.** The shim matches its script on the
   substring `canvaseditplan` across the whole message blob — and the *reply*
   leg's planner prompt contains that string too. So the armed 40s stall is
   consumed by the reply leg, which then blows the 25s budget itself. The world
   log shows `canvas-edit leg skipped — the reply leg's share of the request is
   all that remains` and `released an unapplied edit claim`: there is no edit leg
   left to starve, so no fork. The shim already captures `tool_names` per request,
   so a discriminator exists — it is not implemented yet.

2. **The shim served nothing at all** on that run (shim log empty) while the
   provider loaded and no fallback markers appeared. Case 1's decline is therefore
   *not* explained by the stall. Diagnose this before trusting either case.

**Design constraint for the fix:** `ATOM_CHAT_REQUEST_DEADLINE_SECONDS` is fixed at
server launch and case 1 and case 2 share one launch, so the short budget also
applies to case 1 — which is why case 1 now declines. Separating them needs two
launches (case 1 on product defaults, then a restart with the short budget for the
background leg) or an equivalent per-leg mechanism.

## Do this next

1. Diagnose the empty shim log on c16_d1.
2. Give the shim a discriminator so the stall lands on the edit leg's structured call.
3. Split the launch so case 1 runs on product defaults and only the background leg
   gets the shortened budget.
4. Re-run case 1 + case 2 to green, then step 5: preserve the server through the
   normal background run and terminate the worker deliberately in a **separate**
   crash case. The stranded row's cause is still undiagnosed.
