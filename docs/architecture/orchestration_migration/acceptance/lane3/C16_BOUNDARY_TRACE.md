# C16 — boundary trace: why a single authorized edit has never been observed

Measured 2026-09-27 against the live candidate: world `candidate_fix1`, run
`run-7325767729a0`, backend `:8071`, server pid recorded in
`c16_authorized_edit.json`. Probe:
`acceptance/lane3/authorized_edit_probe.py`.

**Verdict: C16 remains UNPROVEN. First divergent boundary: `interpretation`
with the shipped configuration.**

**And a critical finding supersedes the earlier reading of this case: routing
an edit request to a planner that ACCEPTS it produces a rendered
"Canvas Updated" success for a mutation that never happens.** See §6. The shipped
(unpinned) configuration is the safer one and was left in place.

## 1. The old evidence was measuring the wrong database

`run_isolated.run_single_edit_probe` has failed 7/7 with `audit_rows: []`, and
that emptiness was read as "the edit never ran". It cannot support that
conclusion. The probe seeds and reads `world/data/atom.db`:

```python
# run_isolated.py:3006, 3012
src = sqlite3.connect(f"file:{world / 'fixture' / 'atom.db'}?mode=ro", uri=True)
con = sqlite3.connect(str(world / "data" / "atom.db"))
# run_isolated.py:3088
con.execute("... FROM canvas_audit ...", ...)
```

A `preview_stack` world serves `world/runs/<run>/data/atom.db` — a **different
file**. So on this world the probe writes to one database and observes another,
and `audit_rows: []` is an artifact of that mismatch. The `canvas_audit` table in
the served database has 887 rows, including `action_type='update'`; the sink
works.

This probe therefore refuses to measure anything until the file it reads is the
file the server has open, proven twice — from `/api/health`'s `identity.database`
and independently from `lsof` on the live pid.

## 2. What actually happened, boundary by boundary

| # | Boundary | Result |
|---|---|---|
| 0 | precondition: probing the served database | PASS — `lsof` and the health identity agree |
| 0 | precondition: seeded canvas starts clean | PASS — 0 audit rows, no `30 days` |
| 1 | **interpretation** | **FAIL — first divergence** |
| 1 | the turn reached a real answer | FAIL — `execution_id: None` |
| 1 | the reply is not a content-free stub | PASS — no `"Message processed successfully"` |
| 4 | reservation | PASS — `edit` operation reserved, `status=pending` |
| 5 | effect: exactly one `canvas_audit` row | FAIL — 0 rows |
| 5 | effect: durable canvas content changed | FAIL — still `Quote validity: 15 days` |
| 6 | delivery: does not claim a change that did not happen | FAIL — the reply says "nothing was changed" while also implying the user should clarify |
| 6 | delivery: does not deny a change that did happen | PASS |
| 7 | durability: survives independent readback | PASS (nothing to persist) |

**The safety-relevant behaviour is correct.** The app entered the edit lane,
reserved the operation *before* any effect, applied nothing, and said nothing was
changed. It did not claim a success it did not achieve. That is the fail-closed
behaviour the plan asks for, and it is worth stating plainly: this is not a
system that silently lies about edits.

## 3. The chain, with evidence

```
canvas-edit-shaped request          _canvas_edit_shaped() true
  -> planner consulted             chat_orchestrator.py:13078  _plan_structured(...)
  -> plan returned, wants_edit=False            chat_canvas_editor.py:2122
  -> shared_tool_state["canvas_edit_no_apply_reason"] = "planner_declined"
                                              chat_orchestrator.py:13125
  -> _no_apply_edit branch                      chat_orchestrator.py:6571-6610
  -> honest refusal: "I couldn't safely make that canvas change, so nothing
     was changed."                             chat_orchestrator.py:6599
```

`wants_edit` is decided by an **LLM structured call**, not by code
(`chat_canvas_editor.py:2110`, `CanvasEditPlan`). The prompt itself records that
this is a known weak point:

> *"flash-tier models returned wants_edit=False for clear rebuild requests"*
> — `chat_canvas_editor.py:2085-2087`

For *"change the quote validity from 15 days to 30 days"* — an unambiguous edit —
the planner declined. **C16's blocker is a model/planner routing decision, not a
broken edit path.** The mutation machinery below the planner was never reached,
so it remains untested either way.

## 4. Two real defects found alongside

### D1 — the reserved operation is stranded (`pending`, forever)

```
id                5b060a16-5b8c-49e6-8ec7-8eec62704c9d
operation_id      d5289bbd-026e-414f-bee2-81be503590c4
operation_type    edit
status            pending
created_at        2026-09-27 17:59:13
updated_at        2026-09-27 17:59:13     <- never touched
age               463s and climbing
```

`task_lifecycle.cancel_operation` (`task_lifecycle.py:1295`) exists for precisely
this and says so in its own docstring:

> *"Release a claimed-but-unperformed operation. Used when a lane reserved and
> claimed an operation and then declined to act: the effect did not happen, so
> the claim must not be left held (**which would block every later attempt at
> the same key**) and must not be recorded as applied."*

Its only caller in the entire codebase is internal
(`task_lifecycle.py:2126`). The canvas-edit no-apply path never calls it.

**The release mechanism is correct and already tested. Only the wiring is
missing.** `finish_edit_turn` (`task_lifecycle.py:2098`) does exactly the right
thing:

```python
if not run_id or not operation_id or not updated:
    if run_id and operation_id and not updated:
        # The operation was reserved and its execution claimed, but
        # the lane declined — so NO effect happened. Release the claim
        # rather than leaving an operation running forever.
        try:
            lifecycle.cancel_operation(run_id, operation_id)
        except Exception:
            pass
```

and `tests/test_task_lifecycle.py::TestRecordEdit::test_declined_edit_releases_the_claim`
already asserts it, with the reasoning spelled out: *"No effect happened, so the
claim is released rather than left held (which would block every later attempt)
or recorded as applied (which would be a lie)."* That test passes.

**So D1 is a missing call, not a broken mechanism.** It is not fixed here, for a
concrete reason. AST inspection of the enclosing `process_chat_message`
(lines 4172–7309) shows `run_id`, `operation_id`, `lifecycle` and `_tlm` are
**not in scope** at the no-apply branch — they are locals of the inner helper at
lines 3114–3210. Wiring it therefore means:

1. the inner helper (≈`chat_orchestrator.py:3114-3160`) must publish its
   `reservation` dict (`{"run_id", "operation_id"}`, already built at `:3143`)
   into `shared_tool_state`; and
2. the no-apply branch (≈`:6585`, before it returns the refusal response) must
   call `_tlm.finish_edit_turn(lifecycle, run_id, operation_id, execution_id,
   updated=False, needs_review=False, success=False)`.

That is a two-site change spanning a 3,000-line function in the most
request-critical file in the repo, which currently contains another lane's staged
work and which the 26/26 browser chain and 4/4 correction result depend on. The
stranding is a leaked claim that I measured; the docstring's predicted *blocking*
is a risk I did **not** demonstrate, because retrying the identical edit produced
the same planner refusal rather than a claim conflict. Trading a proven-green
chat path for an undemonstrained-risk fix is the wrong trade, so the wiring is
recorded as a proposal with its acceptance criterion — the existing
`test_declined_edit_releases_the_claim` — rather than applied blind.

**What I did and did not demonstrate.** The leaked `pending` claim is real and
measured. Its consequence — blocking later attempts at the same key — is
**unproven** in this scenario.

### D2 — the refusal message misattributes the cause

> *"I couldn't safely make that canvas change, so nothing was changed. **Please
> clarify the change and try again.**"*

The change was not unclear. The planner declined it. The plan requires these to be
distinguishable:

> *"Authorization denial, unavailable source, unavailable model and uncertain
> effect are distinguishable."* — app-readiness plan §9

"Please clarify" tells the user their request was ambiguous when the system
simply chose not to act, which sends them to rewrite something that was already
clear. The orchestrator already distinguishes these reasons internally
(`planner_declined` / `planner_error` / `planner_returned_none` /
`explicit_edit_required` / `evidence_declined`) and collapses them into one
user-facing sentence at `chat_orchestrator.py:6590-6620`.

### D3 — the refusal produced no `execution_id`

`execution_id: None` on a turn that reserved an operation. My binding checks
(C14/C15 in the correction runner) require an execution identity per turn, and a
refusal that mutates lifecycle state without one cannot be bound to anything.
Recorded, not fixed.

## 5. Measurement: what the planner actually does

`ATOM_ASYNC_EDIT_PLAN_MODEL=provider/model` pins the planner model; empty means
the router ranks. `planner_wants_edit_measurement.py` calls the real planner with
the real prompt, once per candidate. The **unpinned run is the control** — it
reproduces the production decision.

### A confound in my own first experiment, and what it cost

The first run reported "MODEL-QUALITY BOUND" and I initially read that as *the
model is weak*. It was partly my own fixture. An email canvas's content is a
**JSON document**; my first version seeded bare HTML. With an unparseable canvas
`canvas_crud_tool` fails (`Canvas read failed: Expecting value`) and a planner
can decline for reasons that have nothing to do with the model.

This was found because the *end-to-end* probe surfaced `Canvas read failed`, and
checking the fixture showed `json_valid(content) = 0` on every canvas I had
seeded. Both the probe and the measurement now seed the real JSON shape, the
probe **asserts** it, and the measurement re-ran. Numbers below are from the
corrected run.

| Route | `wants_edit` | ops | latency |
|---|---|---|---|
| **(unpinned) — production control** | **False** | **1** | 9.1s |
| `deepseek/deepseek-flash` | True | 1 | 2.7s |
| `deepseek/deepseek-v4-pro` | True | 1 | 58.4s |
| `opencode-go/glm-5.3` | True | 1 | 18.7s |
| `openrouter/anthropic/claude-sonnet-5` | *invalid* | 0 | 1.3s |

The sonnet row is **not a measurement of sonnet**: openrouter was credit-exhausted
(402, benched 300s) so the router auto-unpinned it, and 1.3s with an empty plan
is the fingerprint of a rejected call. It is reported rather than dropped so the
gap is visible, and it must not be read as "sonnet declines".

### The real diagnosis is narrower than "weak model"

The unpinned route resolves to a specific model, captured from the router's own
log line:

```
BPC cost-priority active (task_type=planning): cheapest capable model
opencode-go/gemini-3-flash (eff.cost=0.000e+00, quality=93, ...)
```

With a valid canvas, that model returns **`wants_edit=False` while emitting
`ops=1`** — it produces the correct edit operation and then sets the flag that
makes the orchestrator discard the entire plan (`chat_canvas_editor.py:2122`).
That is a **self-inconsistent plan from one model**, not general weak-model
quality: the tier the code's own comment blames
(`chat_canvas_editor.py:2085`, "flash-tier models returned wants_edit=False")
is contradicted here, because `deepseek-flash` handles this prompt correctly and
in the least time.

## 6. The decisive negative result: pinning makes the product WORSE

The obvious fix is to pin the planner to a model that accepts. I tested that
end-to-end, through the public boundary, with a valid canvas.

**The planner accepted. The edit then produced a false success claim.**

The reply rendered:

> I'll update the quote validity text in the canvas from 15 days to 30 days now.
>
> **Canvas Updated:**
>
> | Field | Value |
> | **To** | steve@example.com |
> | **Body** | Quote validity: **30 days**. |
>
> *Edit marker: LANE3-EDIT-4056F6E0*
>
> *(The canvas edit is still running in the background — nothing is confirmed
> changed yet.)*

Verified two independent ways, because a false-positive here would be as
damaging as a miss:

- `canvas_audit`: **no row for any canvas in the last 30 minutes**;
- `canvases`: **no canvas anywhere in the world contains "30 days"**.

So the system printed a completed update, with the new value rendered in a table,
for a mutation that exists **nowhere** — and then appended the honest disclaimer
*underneath its own false claim*. The disclaimer is proof the honesty machinery
exists and is being defeated by ordering, not that the system is honest here.

**Therefore pinning the planner was reverted.** Unpinned, the same request
produces the honest refusal (*"nothing was changed"*) and mutates nothing. That
is a better product than a fabricated success, so the shipped configuration is
the safer one and I left it that way. The pin is recorded as a **negative
result**, not a fix.

### The uncomfortable implication

The planner decline is currently acting as an **accidental safety net** over a
broken effect layer. Fixing the routing without fixing the effect layer would
move the product from "honest refusal" to "fabricated success" — strictly worse,
and harder to notice. **The effect layer is the real blocker for C16; the
planner is the cheaper bug.**

## 7. Full defect list for the write path

| # | Defect | Severity | Status |
|---|---|---|---|
| **D0** | Reply renders `**Canvas Updated:**` with the new value when **no mutation occurred** — verified by zero audit rows and zero content change anywhere | **Critical** — a false success claim on an artifact | Open. Blocks C16 and the preview gate |
| D1 | Reserved `edit` operation left `status=pending`, `updated_at == created_at`, forever. Mechanism correct and tested; only the wiring is missing | High — leaked claims | Open, deliberately unfixed (see §4) |
| D2 | Refusal said "Please clarify the change" for a change that was not unclear | Medium — dishonest framing | **Fixed** in the working tree |
| D3 | Refusal returns `execution_id: None` while having reserved lifecycle state | Medium — unbound state | Open. Does not occur on the pinned path, which does return one |
| D4 | `opencode-go/gemini-3-flash` returns `wants_edit=False` with `ops=1` | Medium — self-inconsistent plan discarded wholesale | Open. Currently masked by D0 |
| D5 | Async continuation's terminal event broadcast to an **empty** channel, so a user told "I'll report the outcome" is never told it failed (`outcome=failed dur=272s` after 3 attempts) | High — a promised report that can never arrive | Open |

## 8. What is needed to close C16

1. **D0 first.** A reply must not render a completed mutation that did not
   happen. Until the effect layer either applies the edit or reports failure,
   routing an edit request to an accepting planner is a regression.
2. **Then D4** — either route planning away from the inconsistent model, or stop
   discarding a plan that carries a valid op on the strength of one flag.
3. **Then C16 becomes testable**: one observed mutation at the durable sink, with
   the operation reserved before it, on a canvas this probe has already proven
   is parseable.
4. **D1 and D5** should be fixed on their own merits regardless of C16.

C16 remains **UNPROVEN and unpromotable**. The preview's exclusion of all
artifact-editing capability is correct and must stay.
