# Campaign C — two-hour durable assignment (in progress)

Started on an isolated world and ports (`8081` backend, `3141` frontend) so it
does not share another agent's world. The journey harness now takes
`ATOM_JOURNEY_BACKEND`; no hardcoded 8071 remains in the composite scripts.

## Timeline (UTC)

- `15:04:44Z` — campaign start (first attempt; harness/frontend issues)
- `15:37:56Z` — durable external-fact wait reached on run `790dc6cd-…`
- part 2 is valid only after **≥17:37:56Z** (two hours of real elapsed time)

## State at the wait (durable readback)

`state-waiting.json`: run status `waiting`, `waiting_on` an external email with
correlation id `quote-missing-currency-1`, 0 steps executed, served by backend
pid 43328 at source `2d01d31772da-dirty`.

The productive work before the wait is the teaching/conflict/qualification
flow, CSV upload, mapping `Price → Gross Amount`, and assignment creation
(`part1.json`, screenshots in this directory).

## Next actions (after the clock)

1. Restart the backend against the same world and confirm the run is still
   `waiting` with the same teaching/source revisions.
2. Deliver the correlated answer; confirm the same run resumes, the DOCX is
   produced with Arial 11 and the expected total, and completed work is not
   recreated.
3. Exercise duplicate resume and cancellation on **sibling** runs so the
   successful run is unaffected.
4. Controlled uncertain effect → reconcile → retry adds no second effect.
