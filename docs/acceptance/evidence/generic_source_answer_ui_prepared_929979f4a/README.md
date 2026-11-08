# Prepared ordinary-UI authorized-source episode

**STATUS: PREPARED — NOT LAUNCHED. Root owns the single browser run.**

Prepared source: `929979f4a4a279668020118b613d4f2eaafe0dd2`
Driver: `scripts/acceptance/browser_agent_source_answer.py`
Fixture: `scripts/acceptance/fixtures/browser_agent_source_answer_shim.json`
Work order: `WORK_ORDER.md` (also under `docs/acceptance/`)

## Gates in this packet

- TypeScript `tsc --noEmit -p tsconfig.json` on clean prepared source:
  **exit 0**, no install/npx. Exact command and raw output in
  `typescript-noemit.log` / `typescript-noemit.exit.json`.
- Prepared driver preflight: **ok=true**, 3 ReActStep envelopes, source marker
  `UI-SOURCE-AUTH-7F3C`, action gated on source content, final gated on Oracle.
  Raw report in `source-preflight.json`.
- Prepared-harness + accepted per-file identity tests: **23 passed**, exit 0
  (`scripts-prepared-tests.log`).
- Root independent source/process/namespace gate at `0509877ed`:
  **exit 0, 22 passed** (`root-gate-reference.json`; raw files remain in
  `/private/tmp/root-generic-source-binding-recheck.*`).

## Explicit blocker

The post-gate probe commit `1ac32d015` added
`backend/tests/test_lead_generic_source_scope_cas.py`. It fails **4/4**
(`workspace_id`, `tenant_id`, `user_id`, `params`) on the current source: a peer
change to the durable wait scope/params after source read is not blocked by the
pending claim. Raw run: `post-gate-scope-cas-fail.log`; summary:
`post-gate-scope-cas-finding.json`.

Backend/API/UI/test runtime was **not modified** for this preparation
checkpoint. Root must resolve or coordinate that API-gate failure before running
the ordinary UI episode. The prepared UI path is not a workaround.

## What is prepared

One ordinary user, one job/execution, one fresh world: normal login/onboarding;
Run objective; durable source question; ordinary Assignments-page upload;
upload-alone inert; same wait after return; real backend/frontend restart; same
job/execution/wait; authorized-source picker; source-only answer; registered
`tasks.create`; default Oracle verified; one task; authoritative UI/API/DB
readback; source content actually in the served prompt; no new objective or
manual advance.

Only loopback provider responses are authored and labelled **SIMULATED MODEL
DECISIONS / CONTROLLED TRANSPORT**. No world, browser, model, provider, account,
credential, send, spend, install, download or deployment ran here. This is not
self-acceptance and does not claim full TASK-WAIT-01 or full-app completion.
