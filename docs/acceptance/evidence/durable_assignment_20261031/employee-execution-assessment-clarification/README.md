# Durable assessment clarification

A gap input produces the smallest useful clarification and a resumable
obligation, not a generic approval request.

## What persists

Each assessment stores, on the canvas itself:

- the original objective (`request.ask`) and request identity (execution id +
  fingerprint);
- source revision, policy revision and manifest revision in force;
- one obligation per unresolved requirement: subject, requirement text,
  answer and answered-at.

It survives a backend restart because it lives in the canvas content, not in a
process cache.

## Answering and resuming

`POST /api/canvas/{id}/capability/assess/{execution_id}/clarify` records
answers against the exact execution:

- an answer for a subject with no open requirement is refused;
- an empty answer is refused;
- answering clears any earlier approval (the inputs changed) and advances the
  assessment concurrency token with the same CAS as approval;
- when every requirement is answered the same canvas and policy are
  re-dispatched, producing a new execution; the old approval cannot authorize
  the new result.

## Controls

`clarification-controls.log` — **6 passed**:

1. the obligation is persisted with objective, identity and revisions;
2. it survives a fresh session (restart-equivalent read);
3. a partial answer keeps the obligation open and invalidates approval;
4. a full answer marks it answered and a resume produces a new execution;
5. an answer for an unknown subject is refused;
6. an answer against a superseded execution is refused as stale.

Not claimed: an autonomous browser journey through clarification. `reconcile`
remains reserved.
