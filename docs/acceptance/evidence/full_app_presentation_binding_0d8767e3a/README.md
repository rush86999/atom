# Canvas presentation postcondition repair — new product source

Status: **submitted for independent verification; not self-accepted.**

This is a new product source, not a documentation-only resubmission. It repairs
the three withheld presentation false passes on top of `f8f8de387`.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree | `/private/tmp/atom-full-app` |
| Executed source | `0d8767e3ac2494dd7a4b88ffc790f898035e8586` |
| Tree at execution | clean |
| Quote world | `full-app-quote-20261102` on `8096` / `3137` |
| Bookkeeping world | `full-app-bookkeeping-presentation-fix` on `8100` / `3146` |
| Runtime identity | both journeys: `source_id=0d8767e3ac24 ... dirty=False` |
| Transport | controlled canvas action and controlled Books ledger; no live provider |

## Repaired false passes

1. **Wrong markdown with matching title.** The audit now persists the exact
   markdown material and a canonical material digest. The verifier compares the
   digest to the frozen authorized content; title and length are diagnostic.
2. **Wrong chart values with matching point count.** The audit now persists the
   complete chart type/data material and digest. Point count is diagnostic.
3. **Old audit certifying a new operation.** The presentation tool returns the
   exact `audit_id` of the row it created. The verifier reads that audit row by
   id and canvas, and requires its governed `operation_id` to equal the frozen
   current operation. It no longer selects the latest canvas audit.

Missing audit id, missing material/digest, missing operation identity, wrong
workspace/tenant, forged returned digest, handler argument mutation, concurrent
presentations and same-content old audits are all refuted. Missing material is
refused before dispatch.

## Identity chain

`action_registry` → `canvas_tool` → `CanvasAudit` → action result → executor
oracle context all carry the same current operation id, workspace/tenant,
canonical material and material digest. The executor freezes the authorized
material before dispatch; returned fields cannot override it.

## Journeys on this source

- Normal quote/service/exception: **17/17 passed**, including real restart,
  action audit count 1 → 1 on duplicate approval, three DOCX fixtures.
- Invoice-to-Books: **12/12 passed**, one create, verified readback,
  restart/reopen and duplicate refusal.

## Tests

- Combined backend matrix: **288 passed** (`backend-tests.log`).
- Independent local-present probes: **3 passed** (`local-present-probe.log`).
- Frontend: **7 passed** (`frontend-tests.log`).

## Coverage classification

`oracle-whole-app-inventory/inventory.json` now separates:

- **6/6 external/provider mutation classes** covered;
- **8/8 local durable mutation classes** covered with shared effect-family
  postconditions;
- **1 plan-output validator** (`goals.decompose`) — structural plan validation,
  explicitly not persisted execution proof;
- 827 mutating HTTP declarations and 311 provider-adapter write methods remain
  unqualified discovery candidates.

This is not whole-app ORACLE-01 closure.

## Exclusions

No live provider lookup, refresh, write, send, credential, consent or spend.
Historical 111/123, connected `6431bcb78`, typed-canvas `4859b0ce2477`,
canvas assignment/teaching `a87882526323` and older evidence bundles are
unchanged.
