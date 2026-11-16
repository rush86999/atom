# Current-source ordinary skill dispatch in Docker — November 16, 2026

The existing joined `GenericAgent` skill test passed once against a real Docker
container at published source `3316b0fe71a1203a90e0f4ec856d7eb5a08d2f4a`.
The ordinary agent loop dispatched registered `skills.execute`, ran the
reviewed executable and re-read its durable exact receipt through a fresh DB
session. The model decision was scripted; this is execution evidence, not a
real-model skill-selection or whole Goal 6 claim.

## Observed boundary

The unmodified test
`backend/tests/test_reviewed_executable_skill_agent_dispatch_docker.py`
passed in 22.61 seconds. It provisioned isolated synthetic principals, reviewed
and applied the benign skill through the existing approval/registry path, and
ran the real `GenericAgent.execute` loop with a deterministic decision stub.
The security scanner and principal setup were fixtures; this does not verify
live scanner quality, ordinary web authentication or independently generated
skill competence.

The action produced exactly count 4, maximum 11 and sum 26. A fresh DB session
read the successful execution, exact agent/skill/tenant/workspace attribution,
review revision/digest, candidate/executable hashes and registry binding.
The real sandbox receipt reported Docker execution, read-only/network-disabled
ephemeral configuration, successful removal and matching nonce echo.

Root independently pinned the cached `python:3.11-slim` image ID before and
after execution. Docker's own event history identified one fresh exact
container with create, start, die and destroy events. Its ID and exact name
were absent afterward, and every pre-existing container ID remained present.
There was no broad cleanup, image pull or automatic rerun.

## Isolation and evidence

[The filtered receipt](evidence/current_skill_docker_20261116/result.json)
records source, image, review hashes, result, lifecycle and limits. The runtime
used explicit scratch SQLite, workspace-skill storage and an isolated HOME.
No live dev DB or provider credential was used. Host OS policy denied TCP;
a Python socket guard allowed only the exact supplied local Docker socket.
Actual preflight confirmed Docker ping and refusal of owner-app/external TCP
and another Unix socket. Container execution used the existing sandbox.

The preparation helper originally had wrong root/backend paths, implicit cwd
and Python symlink resolution that would lose the cached venv. Those were
corrected before any runtime. An independent fake-subprocess control passed;
its first restricted attempt failed while binding its temporary Unix socket,
before helper execution. The actual Docker case was distinct, one-shot and
successful; neither pure controls nor environment failures were relabelled as
container execution.

## Remaining scope

This does not establish served-model selection quality, unfamiliar skill
quality, every governance failure, concurrent/timeout/soak behavior or native
Firecracker/KVM isolation. The earlier deterministic denial controls remain
separate evidence at their original sources. Original 143 claims and 18 goals
remain unchanged; no further invocation mechanism was added for this test.
