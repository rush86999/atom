# Independent review request — assignment start boundary

Frozen candidate: `44b62a6bb` on `whole-app/successor-f5f`
Preserved executor evidence: `efc4bc9d5`.

Please review read-only; do not restart the owner's runtime or run a live
send.

## Scope

1. `POST /api/assignments` and `core/assignment_planner.py`:
   accepted objective, employee/agent scope, teaching resolution, explicit
   sources/deliverables, capability planning and pre-execution validation.
2. The Start durable work form and Assignments tab / page wiring.
3. `core/assignment_launcher_guard.py` and the browser acceptance server:
   disposable-path proof, forbidden live/release/source paths, marker-gated
   reset, no unconditional deletion on import.
4. The two-domain start acceptance:
   `docs/acceptance/ASSIGNMENT_START_2026-10-29.md` and
   `docs/acceptance/evidence/durable_assignment_20261029/browser-start/`.

## Questions for the reviewer

- Can a model-proposed or caller-proposed step reach an unregistered adapter,
  a missing prerequisite, an external effect without approval, or a different
  workspace?
- Does the planning boundary accidentally grant permissions from the
  objective, teaching, source locator or deliverable declaration?
- Is the accepted objective and teaching revision preserved through
  validation and execution?
- Does the start form/route genuinely re-enter the same executor and durable
  state, rather than create a parallel path?
- Does the launcher guard actually refuse live/release/source directories and
  avoid deletion without the marker plus explicit reset?
- Do the browser-start and restart evidence demonstrate the same state the
  backend ledger records?

## Known boundaries

- Controlled outbox only; no live provider acceptance or delivery.
- One worker process per assignment is the verified topology.
- Production Outlook send still requires a prepared canvas and the existing
  approval path.
- No deployment, credential change or source modification.
