# Real 48-hour wait and authorized continuation — November 16, 2026

A retained synthetic job survived a real **48.0203-hour** wait and process
loss, then resumed the same job and execution after its authorized answer.
This is a bounded Goal 10 / TASK-WAIT-01 result at source
`2f2b376a0daa8049edd91121fbec42acada15aea`, not a current-main or live-model
readiness claim.

## Observed boundary

The durable wait began November 14 at 06:42:25 UTC. The original process was
hard-killed. The stricter elapsed origin was 06:42:25.414033 UTC; the driver
refused early execution and used the real host UTC clock without an override.
After November 16 at 06:42:25.414033 UTC, a new process recovered the exact
same job, execution, pending question and server-owned correlation.

Before the answer, independent read-only SQL confirmed the original waiting
timestamp, zero task effects and no model continuation. The successor was
stopped. A further process accepted the synthetic title **Quarterly close
checklist** through the public job-answer route and ran the real registered
`tasks.create` action. Its ORACLE readback was verified.

The job and execution became successful with exactly one durable task.
The original wait recorded the exact accepted answer and correlation.
An identical answer replay returned `already_resumed` without a second effect;
a different late answer returned 409. The bound verifier asserted those HTTP
results. Independent SQL after shutdown confirmed the same successful job,
execution and single task; both owned successor processes were absent.

## Method and evidence

The fixture uses real OS processes, SQLite, production loop/registry/recovery
and public agent routes. Model transport is scripted and authentication uses
a seeded principal dependency override. No live provider or external
integration was called. It is not an ordinary login/browser episode.

[The result receipt](evidence/real48h_wait_20261116/result.json) records the
accepted scope and verifier SHA. The retained private world, start/resume
receipts, API result, process logs and independent SQL adjudication remain in
`/private/tmp/atom-elapsed-wait-driver/`. The original permanent fixture is
`backend/tests/test_agent_generic_information_wait_process.py` and its process
worker. Running its short tests does not recreate the real elapsed wait.

## Remaining scope

This result does not verify real-model judgment, unfamiliar task quality,
current-main 48-hour behavior, independent-work scheduling, partial answers,
cancellation or every long-task outcome. Those requirements remain separate.
The completed case and its one-shot answer claim must not be rearmed or
replayed as a new elapsed-time result. Original claim identities, all 18 goals
and the historical score are unchanged.
