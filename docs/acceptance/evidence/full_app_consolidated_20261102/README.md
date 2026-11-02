# Consolidated full-app candidate — taught artifacts + accepted oracle + one evolution lifecycle

Status: **submitted for independent verification; not self-accepted.**

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree used for the run | `/private/tmp/atom-consolidated-clean` (separate clean worktree) |
| Executed source | `2b5db4b985cada1baf3edc0b554227f44d9b7b2d` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime identity | `source_id=2b5db4b985ca ... dirty=False` |
| Frontend build | `4LIiyOI205pK5RCpBKH87` |
| World | `/private/tmp/atom-consolidated-clean/backend/data/acceptance_worlds/full-app-consolidated-20261102` |
| Ports | API `8101`, frontend `3142` |
| Transport | controlled canvas action; no live provider |

The world is a copy of the durable `full-app-quote-20261102` world (same
Agent/teaching history), relabelled for the clean worktree. No reseed and no
schema change. It is separate from the other agent's `8098/3139` and
`8097` worlds, which were left running and untouched.

## What is integrated

- **Taught artifacts (from the full-app line):** receipt-derived
  document/spreadsheet/presentation deliverables, artifact lessons resolved at
  assignment creation, applied-operation `remote_id`/`provider_ref`, and the
  `canvas_audit` postcondition for `canvas.present_markdown`.
- **Accepted connected oracle line (`6d62855d0..0f9796401`, inventory
  `95454de7a`):** frozen authorized-request snapshots before dispatch,
  canonical provider/operation/organization/target bindings, six connected
  mutation verifiers, fail-closed readback, and the whole-app inventory.
- **One oracle consumer contract:** the assignment adapter uses the accepted
  frozen-request block; the branch's duplicate inner gate was removed. A
  refutation or unreadable verdict settles the dispatched mutation as
  `uncertain` with the remote identity preserved.
- **One evolution lifecycle:** the parallel HITL
  `agent_evolution_candidate` store was deleted. GenericAgent tool failures
  now call the existing `record_tool_error` signal; episode finalization
  merges it, downgrades a nominal success to partial, emits the TaskEvent, and
  ReflectionEngine/Memento files one pending `SkillCandidate` reviewed through
  the existing Auto-Dev routes.

## Consolidated journey (17/17)

The normal application is used end to end: `/login`, typed canvas creation from
real CSV bytes, derive, lesson promotion, ordinary assignment, real process
restart, approval, download, source change, duplicate continuation, service
and exception variants, cancellation.

Measured, not label-only:

- The pending operation id and approval payload digest are **identical before
  and after the restarted processes**; status is still `awaiting_approval`
  with `remote_id=null` (`442a74d6…`, payload `5c44a7f4…`).
- The duplicate approval returns `404` and the durable `canvas_audit` count for
  the action remote id is **1 before and 1 after** (`0c327289…`).
- Quote `350.00` (sha256 `bb80c677…`), service `630.00 CAD` (`dadc880f…`),
  exception `3 / 170.00` (`b873c87e…`); all three normal styles are
  **Georgia 18** and carry receipt provenance.

## Oracle registry union

`oracle-registry.txt` lists the nine verifiers loaded through the production
path: the six connected mutations, `tasks.create`, `trigger_workflow`, and
`canvas.present_markdown`. The regenerated inventory:

- 90 registered actions; 6 external mutations, **6 covered**;
- 9 local durable mutations, **2 covered** (`tasks.create`,
  `canvas.present_markdown`);
- 827 mutating HTTP routes and 311 provider-adapter writes remain outside the
  registry and are explicitly unqualified.

## Tests on this source

- Backend combined matrix: **428 passed** (`backend-tests.log`), including the
  accepted connected-oracle probes, immutable-request controls, canvas-audit
  positives/negatives, scheduled-entry controls, canonical Memento candidate
  controls, and the full-app assignment set.
- Frontend canvas panels: **7 passed** (`frontend-tests.log`).

## Open, not included in this source

Another agent's effect-family verifiers (canvas update/restore/present-chart,
goal families), controlled Books adapter and invoice-to-Books journey were
in-flight and uncommitted while this candidate was frozen. They are **not**
part of `2b5db4b98`; that work and its bookkeeping loop remain open. Also open:
whole-app oracle coverage beyond the nine verifiers, TEAM-05's real LLM sweep
transport, MEM-07's approval/apply half and post-restart consumption,
ORCH/GOAL model work, MINI Linux/KVM, INT/ROUTE live authorization.

## Exclusions

- No live provider lookup, refresh, write, send, credential, consent or spend.
- No database reseed; the durable world was copied and relabelled.
- The earlier bundles (`full_app_quote_journey_20261102`,
  `full_app_batch_20261102`, `claim_progress_20261102`,
  `oracle_whole_app_inventory_20261102`) are unchanged.
- The 123-feature denominator and historical 111/123 are unchanged.
