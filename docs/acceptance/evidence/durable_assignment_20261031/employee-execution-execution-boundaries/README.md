# Execution boundaries — post-effect errors and hard cost/time budgets

This bundle closes the two execution defects the verifier reproduced after the
two-domain journey was accepted.

## 1. Post-effect errors are uncertain, not failed-before-effect

A generic exception after an external adapter has been invoked may mean the
effect landed. The executor now:

- records `uncertain` + `needs_reconciliation`, with a receipt
  `observed_status=uncertain`, for an ordinary runtime error, parse error,
  timeout or cancellation after an external dispatch;
- never automatically resends an uncertain effect;
- uses retryable `failed_before_effect` only when a trusted adapter raises
  `ExternalOutcomeNotApplied` or carries `effect_possible=False`;
- keeps local/read-only errors as ordinary failures.

Controls: post-effect `RuntimeError`, post-effect parse error, post-effect
timeout (remaining wall budget), post-effect `CancelledError`, and a trusted
before-effect refusal. Each uncertain control leaves exactly one delivered
effect and a second `execute` does not add another.

## 2. Cost is a reservation, not a stop-after-overspend threshold

Before dispatch the executor reserves the adapter's declared conservative
`max_cost_usd` upper bound under the assignment CAS. A hard budget:

- refuses the operation before dispatch when
  `committed + outstanding reservations + bound > limit`;
- refuses a cost-bearing adapter that declares no bound;
- accounts for concurrent reservations and retries (the reservation is on the
  assignment, not the worker);
- settles actual cost on success, the reserved bound on uncertainty, and zero
  on a proven no-effect failure; an actual overrun is recorded as a violation.

A soft limit requires an explicit `soft_limit_authorized_by`, is recorded as
`cost_mode=soft`, and exposes `soft_limit_exceeded` instead of implying the
limit held. Wall time is enforced *during* the operation with a remaining-budget
timeout, not only between steps.

Controls: a $10 bound under a $5 hard limit is refused with zero dispatches; a
second $2 bound after a $4 reservation is refused; concurrent reservations
leave only the first reservation; a soft limit completes and exposes the
overrun; an unbounded cost-bearing adapter is refused.

## Result

`execution-boundaries.log`: **81 passed**, 0 failed (assignment executor +
routes, including the new controls).

The accepted browser journey was rerun on this source (`b7ee7ee22`): **5/5**,
2 controlled effects, 0 assignment approvals. See
`../two-domain-autonomous-journey/`.

## Scope

- controlled outbox only; no live provider or real send;
- one worker for the browser run; concurrent reservation covered at the
  executor boundary;
- cost bounds are adapter-declared; a cost-bearing adapter without a bound is
  refused under a hard budget rather than guessed.
