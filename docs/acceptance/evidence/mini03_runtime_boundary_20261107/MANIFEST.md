# MINI-03 runtime boundary — public-consumer evidence (2026-11-07)

Branch `codex/mini03-runtime-boundary-20261107`, base `4c1bd507d`.
All runs: `TESTING=1` scratch world (repo `backend/tests/conftest.py` forces
`TESTING=1` and rejects any `DATABASE_URL` pointing at the live dev DB;
journeys run on in-memory SQLite per `tests/integration/journeys/conftest.py`).
No VM/Docker/container/provisioning started; the runtime factory stays real
and fails closed before any external contact.

## Requirement scope

Claim inventory `docs/acceptance/readme_feature_readiness_2026-10-31/CLAIM_INVENTORY.md`
MINI-03 (L154): "Run the mini-app in the isolated runtime and receive test
feedback" — entry `RPC action mini_app_dev_run/mini_app_run_tests`; expected
"Runtime executes OR fails closed with an explicit unavailable message".
This bundle proves the fail-closed leg at the ACTUAL public consumer on this
macOS host. MINI-04 (installed persistence) and MINI-05 (microVM isolation +
side chat) are NOT claimed here; they remain separate KVM requirements.

## Baseline (clean worktree at 4c1bd507d, pre-edit run)

`python -m pytest backend/tests/integration/journeys/test_mini_app_harness_journey.py -q`
→ `2 failed, 2 passed`:

- `test_mini_app_harness_journey.py::TestMiniAppHarnessJourney::test_full_authoring_journey`
  — fails at step 2 (line 97): `PUT /api/canvas/{blueprint}/logic` → 403
  `{"detail":"Canvas logic requires an AUTONOMOUS agent. No agent provided."}`.
  The committed MINI-03 chain never reaches its dev_run / mini_app_run
  fail-closed assertions (steps 7 / 11).
- `test_mini_app_harness_journey.py::TestMiniAppHarnessJourney::test_canvas_logic_save_requires_access`
  — same 403 at line 209 on the owner path.

## Why the committed journey was stale (no product defect, test-only repair)

The journey was authored at `0cc756619` (2026-08-06). `d7c297222` (2026-08-26,
R87–R89 hardening) made the canvas-logic governance gate mandatory:
`canvas_routes._enforce_logic_governance` → `CanvasLogicService.check_governance(None)`
now raises `PermissionError` (= 403) for agent-less saves. The production
consumer is unaffected: `frontend-nextjs/components/canvas/MiniAppHarness.tsx`
`handleSave`/`handleDevRun` sends `agent_id` with every save
(`pages/canvas/[id].tsx` derives agentId). The journey simply predated the gate.

Second staleness (would have failed at step 7 even once step 2 was fixed):
the round-06 journey asserted `"Firecracker" or "Rootfs"` in the dev_run
error, but `run_stateful`'s RuntimeError funnel (`core/mini_app_service.py:1437-1451`)
deliberately sanitizes provisioning internals out of the public response and
returns the actionable pointer:

```
Mini-app runtime unavailable on this host. Probe mini_app_status for the
reason; host setup: docs/deployment/FIRECRACKER_HOST_SETUP.md
```

(server-side log keeps the full detail, e.g. `Firecracker runtime unavailable
for mini apps (missing: Linux host with the 'firecracker' binary,
FIRECRACKER_KERNEL_IMAGE=None (vmlinux), FIRECRACKER_ROOTFS_TEMPLATE=...)`).

## Changes (tests + CI only; no product/runtime code touched)

1. `backend/tests/integration/journeys/test_mini_app_harness_journey.py`
   - repair: create a real AUTONOMOUS `AgentRegistry` scratch row and pass
     `agent_id` on the harness PUT bodies (mirrors the shipped harness; the
     R87–R89 gate is exercised, not bypassed);
   - update steps 7 / 11 to the CURRENT sanitized fail-closed message;
   - add the missing join at the public consumer: `mini_app_run_tests` now
     exercised after `mini_app_set_tests` — grading report arrives with every
     case `passed=false` and the same explicit unavailable error, no
     fabricated `stdout`/`state`.
2. `backend/tests/integration/journeys/test_mini_app_runtime_boundary_journey.py`
   (new, 5 controls; production registry + real service + real
   `get_miniapp_runtime` factory — no mocks of those consumers):
   - dev_run on a harmless scaffold → explicit actionable fail-closed at
     `POST /api/rpc/mini_app_dev_run`; owner-only `mini_app_status` probe
     shows the concrete runtime reason; side-effect tripwires: app row /
     canvas row / `CanvasState` row counts unchanged (no registered installed
     instance, nothing executed or persisted);
   - `mini_app_run_tests` → per-case explicit unavailable feedback
     (0/2, `all_passed=false`);
   - cross-user negative: dev_run / run_tests / status probe by a second
     registered user → `Not the app owner` (R54 context identity — and clearly
     an authorization failure, not a runtime failure);
   - `ENVIRONMENT=production` + explicit `ATOM_MINIAAP_RUNTIME=docker-dev` →
     refused at the same public consumer; the owner-only probe names the
     refusal verbatim ("refused … ENVIRONMENT=production"). The factory checks
     production BEFORE contacting any daemon, so this control is
     deterministic on any host — no Docker contact, no images, no containers;
   - dev-mode docker-dev with no reachable daemon → fail-closed at the public
     consumer (skipped when a daemon IS up; the execution half stays with
     `test_miniapp_dev_docker_journey.py`, unchanged and untouched).
3. `.github/workflows/ci.yml` — additive step `Run mini-app runtime-boundary
   journey (MINI-03 fail-closed joins)` in `backend-tests` running the two
   journey files (in-memory SQLite, TESTING=1).

## Post-repair verification (current worktree, same session)

```
python -m pytest backend/tests/integration/journeys/test_mini_app_runtime_boundary_journey.py \
                  backend/tests/integration/journeys/test_mini_app_harness_journey.py -q
→ 9 passed, 29 warnings in 6.66s
```

- `test_mini_app_runtime_boundary_journey.py`: 5/5
- `test_mini_app_harness_journey.py`: 4/4 (baseline failures above now green;
  assertions strengthened, none weakened)
- `backend/tests/integration/journeys/` full collect: 147 tests, no collection errors.
- `test_miniapp_dev_docker_journey.py`: unchanged; module skips without a
  Docker daemon (2 skipped locally, same as before).
- Full app boot within the journeys fixture: Firecracker factory error logged
  server-side only — the public body stays sanitized (verified in captured logs).

## Boundary statement

MINI-03 disposition on this host remains honest `environment_limited` —
execution requires a Linux/KVM host with a provisioned Firecracker rootfs
(operator step, `docs/deployment/FIRECRACKER_HOST_SETUP.md`), or local
docker-dev with Docker Desktop running. Nothing here enabled or approximated a
VM runtime, and no unavailable state was relabeled as successful isolation.
MINI-04/MINI-05 (installed-instance persistence and microVM isolation/side
chat) stay open and separate.
