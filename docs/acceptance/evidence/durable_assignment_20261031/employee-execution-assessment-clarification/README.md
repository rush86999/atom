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

## Hardening (8123f12c6)

- each obligation carries a stable `requirement_id` (execution + subject +
  ordinal + requirement), so two requirements on one subject cannot collapse;
- a subject-only answer is refused as `ambiguous_requirement` when more than
  one requirement is open; answers may be reordered by id;
- unknown ids and conflicting replays are refused;
- when the source/policy/manifest revision moves, answers are preserved as
  history and the result is `reassessment_required`; they are never silently
  transferred to the new rules;
- readiness is re-read immediately before resume, closing the race between
  recording an answer and dispatching the reassessment.

`clarification-hardening.log`: **18 passed** (clarification + route tests). The resumed prompt also names the accepted source/policy/manifest revisions the answers were given against.

Not claimed: an autonomous browser journey through clarification. `reconcile`
remains reserved.

## Requirement identity and revision binding (2026-10-31)

The verifier reproduced two gaps:

1. two requirements on one subject collapsed onto one answer slot, so
   "Confirm the amount" was stored against "Confirm delivery term";
2. changing the policy after the assessment still let the old execution's
   answer record and mark ready-to-resume.

Repair:

- every obligation carries a stable `requirement_id` derived from
  (execution, subject, ordinal, requirement text);
- an answer must identify that `requirement_id`; a subject-only answer is
  accepted **only** when the subject has exactly one open requirement and is
  otherwise refused as `ambiguous_requirement` with the candidate ids;
- duplicate answers for one obligation with different text are refused as
  `conflicting_answer`;
- source, policy, manifest **and canvas** revisions are validated before
  recording an answer and again immediately before resumed dispatch;
- when a revision moved, the answer is preserved under `historical_answers`
  with the accepted revisions and `reason: revisions_changed`, the obligation
  stays open, and the result is `state=reassessment_required`,
  `outcome=refuse` — never silently transferred.

### Route continuation

`test_clarify_route_consumes_saved_answers_into_generation` drives the public
routes and captures what generation receives: the original objective, the
`requirement_id`, subject, requirement text and answer, plus an
`ACCEPTED REVISIONS` block with the source/policy/manifest revisions. The
resumed assessment has a new execution and is not authorized by the old
approval.

### Controls

14 service controls + 1 route continuation control pass, including two
requirements on one subject, reordered answers, conflicting replay, changed
policy, changed source, and restart read.
