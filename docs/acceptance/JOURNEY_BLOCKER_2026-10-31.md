# Post-repair normal-app journey — SUPERSEDED (2026-10-31)

**Status: superseded.** The blocker below was an acceptance-harness interaction
problem, not a product render loop. The journey executed successfully on clean
source `31ba9725e02a` and is recorded in
`docs/acceptance/evidence/durable_assignment_20261031/employee-execution-integrated-local-journey-repaired/`.

## Resolution

The harness now:

- waits for the training panel in `attached` state instead of requiring it to
  be visible while an onboarding overlay covers it;
- dismisses overlays and Escape-closes dialogs before filling the teaching
  form;
- fills only the optional format fields the lesson supplies (the empty
  `teach-format-size` field is disabled until a font is chosen).

With those harness fixes, part 1 reached the external-fact wait, the backend
was really restarted, part 2 resumed the same run, and verification passed:
active **550.00** (Arial 11), revised **500.00** (Calibri 14), one controlled
outbox line, negative controls passed. Serving identity during execution was
`31ba9725e02a`, `dirty=false`, PIDs 64333 → 64859.

## Historical note

The original observation — a 30-second Playwright stall on
`teach-topic-input` and `describe-job-button` in both production and dev
builds — was real for the unmodified harness. It did not reproduce once the
panel was allowed to attach and overlays were dismissed. No product code was
changed to produce the successful run; only the acceptance harness was
stabilized.
