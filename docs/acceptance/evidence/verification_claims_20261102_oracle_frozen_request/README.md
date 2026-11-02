# Verification claims batch 1d — frozen authorized request

Status: **submitted for independent verification; not self-accepted.** This
closes the immutable-request defect found in `45d015fa3`, on top of the
TEAM-05 controlled service mechanism and the MEM-07 event-to-pending/review
boundary.

## Executed source

| Item | Value |
|---|---|
| Worktree | `/private/tmp/atom-canvas-successor` |
| Branch | `codex/brennan-canvas-successor-20261101` |
| Previous source | `45d015fa3` (evidence `2854df37c`) |
| Executed source | `0f9796401` |
| Tree at execution | clean |
| Runtime | local service/API tests; no browser claim in this bundle |

## Defect and repair

The previous adapter awaited `action_registry.execute_action(name, arguments,
...)` and only afterwards computed the expected digest and
`oracle_request_binding(name, arguments)`. The handler received the same
mutable mapping by reference, so a handler that changed `arguments["body"]` or
a nested `arguments["to"][0]` also changed the purported immutable expectation.
Both independent probes returned `applied`.

The adapter now:

1. deep-copies the authorized arguments **before any handler invocation or
   await**;
2. computes the canonical provider material digest and operation/provider/
   organization/target binding from that frozen snapshot;
3. validates any supplied `payload_sha256` against the canonical digest and
   refuses **before dispatch** on disagreement;
4. refuses **before dispatch** if a known connected binding cannot be
   constructed or has no canonical digest;
5. dispatches a **separate deep copy** to the handler;
6. never recomputes expectations from handler-mutated arguments or from the
   returned envelope.

The original plan/reviewed request object is not mutated by the handler. The
frozen expected values cannot be overwritten by returned fields because they
are passed as separate `_oracle_expected_*` keys after the result merge.

A durable executor control runs a mutating handler that alters both the body
and a nested recipient, returns a self-consistent altered readback, and is
refuted by the frozen binding. The step becomes `uncertain`, the remote id and
reconciliation requirement are retained, a fresh lifecycle/session reload does
not dispatch a second effect, and reconciliation settles the original operation
without a resend.

## Tests

| Scope | Result |
|---|---|
| Oracle/TEAM/MEM + original, repair and immutable-request probes | **46 passed** |
| Connected actions, quote/document/real-effect (including durable no-resend), canvas assignment | **78 passed** |
| Assignment routes/executor/quote + oracle confidence + serialization/generic-agent oracle | **217 passed** |
| Canvas focused | **127 passed** |
| Teaching neighborhood | **203 passed** |
| Frontend canvas | **7 passed** |

Total: **678 passed**, zero failures in the claimed scopes.

The new controls cover: unchanged request positive, body mutation, nested
recipient mutation, subject/target mutation, operation-id mutation,
organization mutation, supplied digest mismatch refusing before dispatch,
unavailable binding refusing before dispatch, original request immutability,
and durable uncertain/restart/reconciliation with one effect.

## Carried forward

- TEAM-05 remains accepted at the controlled deterministic service seam.
- MEM-07 remains event -> pending candidate -> review; safe autonomous
  application is not claimed.
- Historical `111/123`, connected `6431bcb78`, typed-canvas `4859b0ce2477`,
  canvas assignment/teaching `a87882526323` and tags are unchanged.

## Boundaries

ORACLE coverage is the 6 registered connected mutating actions, all covered,
plus the existing task/workflow verifiers. It is not a whole-application
dispatch/coverage inventory. No live provider lookup, refresh, write, send,
credential/consent change or spend occurred. The concurrent full-app
`remote_id` persistence repair remains with its assignment owner; this bundle
does not modify `/private/tmp/atom-full-app`.
