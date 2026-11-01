# Post-repair normal-app journey — blocked (2026-10-31)

Status: **not produced.** The pre-repair journey
(`employee-execution-integrated-local-journey/`, source `2ca5e7f03`) remains the
only normal-app journey evidence. It is not evidence for the repaired source.

## What was attempted

Clean-source run at `5664c46c5` in an isolated worktree (the main worktree's
ports 8071/3130 are occupied by another agent's acceptance world), backend
`127.0.0.1:8077`, frontend `127.0.0.1:3133`, fresh scratch world, controlled
outbox.

- API login: **200**; browser login reaches `/dashboard`.
- Part 1 (`composite_long_running_part1.py`) stalls before teaching completes.

## Observed stalls

| Step | Result |
|---|---|
| `teach-format-size` fill with an empty value | timeout — the field is disabled when no font is set. Harness now fills only provided format fields. |
| `teach-topic-input` fill after `teach-lesson-input` | timeout, "performing fill action"; page unresponsive for 30 s |
| `describe-job-button` click (direct Playwright probe) | timeout, "performing click action"; the button is visible and enabled |

Both the production build (`next start`) and the dev server (`next dev
--webpack`) show the stall, so it is not a chunk-compilation delay. A direct
Playwright probe reproduced it without the journey harness.

## Interpretation

This is a UI interaction stall on the merged source in the Agents/Training
surface, not a harness locator mistake and not the deterministic engine. It
blocks the ordinary-journey gate. No post-repair journey claim is made.

## Next executable action

1. Reproduce the stall on `/agents` and the Training panel with the browser
   console/performance trace; find the render or effect loop introduced by the
   merge.
2. Fix it, re-run the journey on a clean source, and record the serving
   identity at execution time (`/health` pid/source_id, frontend build id).
3. Keep this note until that run exists; do not rebind metadata to imply it.
