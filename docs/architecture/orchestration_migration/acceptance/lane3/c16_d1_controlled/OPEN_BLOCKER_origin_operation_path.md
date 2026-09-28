# Open blocker — the origin-operation path cannot yet be exercised live

Status: **specific blocker, not a request to continue.** Directive step 1 of the
final sequence is the only controlled-planner item still open.

## What is required

The continuation must reconcile a mutation that the **interactive** attempt
landed, attributed through `origin_operation_id`, with exact attribution,
current-revision verification, and no second mutation. The
continuation's-own-write case explicitly does not substitute.

## What is already proven

- The four-id contract is real and durable: the continuation's `AgentExecution`
  metadata now carries `origin_operation_id`
  (observed live: `50d80bf9-5883-4b74-9b26-e3b649cae60a` against continuation
  `75922b59-9cd8-4f25-8391-f58985e8eb86`).
- `_operation_identity` / `_matched_operation_row` locate the mutation through
  that relationship, verified against the real `c16_d0` evidence: with the origin
  id carried, audit row `b3cb9277` (`operation_id=1e57dfae…`) is found and
  `_classify_preapply` returns `already_applied`; without it, `landed=False`.
- The harness asserts exact attribution and current-revision currency
  (`landed_mutation_attributable_to_this_request`,
  `landed_mutation_is_the_current_revision`), and both are green — but with
  `attribution = continuation`.

## Attempts and what they showed

| Regime | Edit leg | Fork | Who wrote | Attribution |
|---|---|---|---|---|
| budget 25s (old, now refused) | **skipped** — cannot reserve the 40s reply share | no | *interactive* (`1e57dfae`) | origin |
| budget 60s, stall 40s, `first_n=1` | bounded at 20s, cancelled | yes | continuation | continuation |
| budget 60s, stall 40s, `first_n=2` | bounded at 20s, cancelled; continuation also held 43s | yes | continuation | continuation |

Raising `--stall-first-n` holds the continuation's first attempt open, which is
the right lever, but the interactive write still does not appear: the world log
shows no `falling through to the tool path` and no interactive
`update_canvas_content`. The interactive edit is cancelled together with its
bounded wait, so it never applies.

## The precise open question

**In every regime where the fork is actually taken, the interactive edit is
cancelled before it can apply — and in the one regime where an interactive write
did land (`c16_d0`, budget 25s), the leg was skipped entirely and the harness now
correctly refuses that budget because it cannot reach the edit path at all.**

So the two conditions — *fork taken* and *interactive write lands* — have not
yet been shown to coexist. There is a hint worth chasing: the orchestrator's own
comment notes the edit leg can be **pre-started** ("a healthy edit leg pre-started
one"), in which case it is not a child of the bounded wait and can survive it. If
a pre-started leg is what lets the interactive write land, the regime that
produces both conditions is a pre-start, not a longer stall.

## Concrete next probe (not yet run)

1. Determine what triggers the edit-leg **pre-start** (which condition makes the
   orchestrator start the edit leg before the reply leg rather than after).
2. Drive the world into that regime with the shim armed, so the interactive leg's
   structured call is in flight and the fork is taken from a later starvation.
3. Keep `--stall-first-n 2` so the continuation's first attempt is held while the
   interactive write lands.
4. Assert: `attribution = origin`, `landed_operation_id == origin_operation_id`,
   `update_count == 1`, terminal truthful, and
   `no_duplicate_effect_after_reconnect` green.

Until that probe lands, the honest statement is: the origin-operation
reconciliation is **unit-verified against real recorded evidence but not
exercised end-to-end**, and every controlled-planner result on export
`9cdf562d10aa5989` was obtained on the continuation's-own-write path.
